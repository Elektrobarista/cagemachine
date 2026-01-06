import pygame
import threading
import time
import os

class AudioController:
    """Controller für serverseitiges Audio-Playback mit pygame.mixer"""
    
    def __init__(self, intro_path=None, loop_path=None):
        # pygame.mixer initialisieren mit optimierten Parametern für nahtlose Loops
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        
        if intro_path is None or loop_path is None:
            raise ValueError("intro_path und loop_path müssen angegeben werden")
        
        self.intro_path = intro_path
        self.loop_path = loop_path
        self.state = "stopped"  # stopped, intro, queued, looping, paused, stopping
        self.lock = threading.Lock()
        self.transition_thread = None
        self.fadeout_thread = None
        self.position_thread = None
        self.loop_thread = None  # Thread für Loop-Übergang nach gequeuedem Track
        self._previous_state = None  # Merkt sich vorherigen State beim Pause
        self._transition_thread_id = None  # ID des aktuellen transition_threads
        
        # Preload Sound-Objekte für Dauer-Erkennung
        self.intro_duration = None
        self.loop_duration = None
        self.current_position = 0.0
        
        try:
            intro_sound = pygame.mixer.Sound(self.intro_path)
            self.intro_duration = intro_sound.get_length()
        except:
            pass
        
        try:
            loop_sound = pygame.mixer.Sound(self.loop_path)
            self.loop_duration = loop_sound.get_length()
        except:
            pass
        
    def get_status(self):
        """Gibt aktuellen Status zurück"""
        with self.lock:
            status_map = {
                "stopped": "bereit",
                "intro": "Intro läuft …",
                "queued": "Intro läuft (Loop vorbereitet) …",
                "looping": "Loop läuft (Endlosschleife) …",
                "paused": "pausiert",
                "stopping": "wird gestoppt …"
            }
            return {
                "status": self.state,
                "message": status_map.get(self.state, "unbekannt")
            }
    
    def start(self):
        """Startet Audio: Intro → Loop"""
        # Prüfe State und bestimme ob Resume nötig ist
        needs_resume = False
        with self.lock:
            if self.state == "paused":
                # Resume von Pause - merken für nach Lock-Release
                needs_resume = True
            elif self.state in ["intro", "queued", "looping"]:
                # Bereits am Laufen, nichts tun
                return
            elif self.state == "stopping":
                # Fade-Out läuft bereits, nichts tun
                return
            else:
                # Neuer Start: Stoppe alles vorher
                pygame.mixer.music.stop()
                self.state = "intro"
                
                # Prüfe ob Dateien existieren
                if not os.path.exists(self.intro_path):
                    self.state = "stopped"
                    raise FileNotFoundError(f"Intro-Datei nicht gefunden: {self.intro_path}")
                if not os.path.exists(self.loop_path):
                    self.state = "stopped"
                    raise FileNotFoundError(f"Loop-Datei nicht gefunden: {self.loop_path}")
                
                # Intro abspielen
                pygame.mixer.music.load(self.intro_path)
                pygame.mixer.music.play()
                
                # Thread für nahtlosen Übergang zu Loop
                # Invalidiere alten Thread falls vorhanden
                self._transition_thread_id = None
                self.transition_thread = threading.Thread(
                    target=self._transition_to_loop,
                    daemon=True
                )
                self.transition_thread.start()
                
                # Thread für Position-Tracking starten
                self.position_thread = threading.Thread(
                    target=self._track_position,
                    daemon=True
                )
                self.position_thread.start()
                return
        
        # Falls pausiert: Lock ist jetzt freigegeben, kann resume() sicher aufrufen
        if needs_resume:
            self.resume()
    
    def _transition_to_loop(self):
        """Überwacht Intro und startet Loop nahtlos"""
        # Speichere Thread-ID für Prüfung ob Thread noch gültig ist
        current_thread_id = threading.get_ident()
        with self.lock:
            # Setze Thread-ID, damit andere Threads wissen, dass dieser aktiv ist
            self._transition_thread_id = current_thread_id
            # Berechne aktuelle Position im Intro
            try:
                pos_ms = pygame.mixer.music.get_pos()
                current_pos = pos_ms / 1000.0 if pos_ms >= 0 else 0.0
            except:
                current_pos = 0.0
        
        # Verwende vorher geladene Dauer oder lade neu
        intro_duration = self.intro_duration
        if intro_duration is None:
            try:
                intro_sound = pygame.mixer.Sound(self.intro_path)
                intro_duration = intro_sound.get_length()
                self.intro_duration = intro_duration
            except:
                intro_duration = None
        
        if intro_duration:
            # Berechne verbleibende Zeit bis Queue-Zeitpunkt
            # Queue früher (0.5-1s vor Ende) für besseres Buffering
            # Für kurze Intros: Verwende 50% der Dauer, mindestens 0.1s
            # Für längere Intros: 1s vor Ende
            if intro_duration < 1.5:
                # Kurze Intros: Queue bei 50% der Dauer
                queue_time = max(0.1, intro_duration * 0.5)
            else:
                # Längere Intros: Queue 1s vor Ende
                queue_time = intro_duration - 1.0
            
            # Berechne verbleibende Wartezeit basierend auf aktueller Position
            remaining_time = max(0, queue_time - current_pos)
            
            # Warte in kleinen Schritten und prüfe regelmäßig ob Thread noch gültig ist
            elapsed = 0.0
            check_interval = 0.1
            while elapsed < remaining_time:
                time.sleep(check_interval)
                elapsed += check_interval
                with self.lock:
                    if self.state != "intro" or self._transition_thread_id != current_thread_id:
                        # State geändert oder Thread nicht mehr gültig, beende
                        return
            
            with self.lock:
                # Prüfe nochmal ob Thread noch gültig ist und State noch "intro"
                if self.state == "intro" and self._transition_thread_id == current_thread_id:
                    # Queue Loop für nahtlosen Übergang
                    pygame.mixer.music.queue(self.loop_path)
                    # State auf "queued" setzen, nicht "looping" - Loop startet erst später
                    self.state = "queued"
            
            # Starte Thread für nahtlosen Loop-Übergang nach gequeueten Track
            # Nur wenn Queue erfolgreich war (State ist "queued")
            with self.lock:
                if self.state == "queued":
                    self.loop_thread = threading.Thread(
                        target=self._start_loop_after_queue,
                        daemon=True
                    )
                    self.loop_thread.start()
        else:
            # Fallback: Warte bis Intro fertig ist
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                with self.lock:
                    if self.state != "intro":
                        return
            
            # Intro ist fertig, starte Loop
            with self.lock:
                if self.state == "intro":
                    pygame.mixer.music.load(self.loop_path)
                    pygame.mixer.music.play(loops=-1)
                    self.state = "looping"
    
    def _start_loop_after_queue(self):
        """Startet Loop mit Endlosschleife nach gequeueten Track"""
        # Der gequeuete Loop spielt einmal nahtlos nach dem Intro
        # Um eine Endlosschleife zu haben, müssen wir den Loop mit loops=-1 neu starten
        # ABER: Wir sollten den gequeueden Loop einmal durchlaufen lassen, bevor wir neu starten
        # Das Problem: queue() spielt nur einmal, also müssen wir nach dem ersten Durchlauf
        # den Loop mit loops=-1 neu starten. Das erfordert stop(), was eine kleine Lücke erzeugt.
        # 
        # Lösung: Warte bis der gequeuete Loop fast fertig ist (0.05s vor Ende),
        # dann starte den Loop mit loops=-1 nahtlos. Die Lücke ist minimal.
        
        # Ermittle Loop-Dauer (sollte bereits geladen sein, aber sicherheitshalber)
        loop_duration = self.loop_duration
        if loop_duration is None:
            try:
                loop_sound = pygame.mixer.Sound(self.loop_path)
                loop_duration = loop_sound.get_length()
                self.loop_duration = loop_duration
            except:
                loop_duration = None
        
        if loop_duration:
            # Warte bis gequeueter Loop fast fertig ist (0.05s vor Ende für nahtlosen Übergang)
            # Da Intro bereits fertig ist, warte nur noch die Loop-Dauer minus 0.05s
            wait_time = max(0, loop_duration - 0.05)
            
            # Warte, aber prüfe regelmäßig ob gestoppt wurde
            elapsed = 0.0
            check_interval = 0.05  # Kleinere Intervalle für präziseres Timing
            while elapsed < wait_time:
                time.sleep(check_interval)
                elapsed += check_interval
                with self.lock:
                    if self.state not in ["queued", "looping"]:
                        # Wurde gestoppt oder pausiert
                        return
        else:
            # Fallback: Warte bis gequeueter Track fast fertig ist
            # Verwende get_busy() aber mit Timeout
            start_time = time.time()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
                with self.lock:
                    if self.state not in ["queued", "looping"]:
                        return
                # Timeout nach 5 Minuten (Sicherheit)
                if time.time() - start_time > 300:
                    break
            # Warte noch 0.05s vor Ende (Schätzung)
            time.sleep(0.05)
        
        # Starte Loop mit Endlosschleife für nahtlosen Übergang
        # Wichtig: Der gequeuete Loop ist jetzt fast fertig, starte nahtlos mit loops=-1
        with self.lock:
            if self.state == "queued":
                # Der gequeuete Loop spielt einmal durch. Um nahtlos zu loopen,
                # müssen wir den Loop mit loops=-1 neu starten. Das erfordert stop(),
                # aber da wir fast am Ende sind, ist die Lücke minimal.
                pygame.mixer.music.stop()
                pygame.mixer.music.load(self.loop_path)
                pygame.mixer.music.play(loops=-1)
                self.state = "looping"
                # Setze Position auf Loop-Start, damit Scrubber nicht zurückspringt
                if self.intro_duration:
                    self.current_position = self.intro_duration
    
    def pause(self):
        """Pausiert aktuelles Audio"""
        with self.lock:
            if self.state in ["intro", "queued", "looping"]:
                pygame.mixer.music.pause()
                # Speichere vorherigen State für Resume
                self._previous_state = self.state
                self.state = "paused"
            # Wenn "stopping", nichts tun - Fade-Out läuft bereits
    
    def resume(self):
        """Setzt pausiertes Audio fort"""
        with self.lock:
            if self.state == "paused":
                pygame.mixer.music.unpause()
                # Stelle vorherigen State wieder her
                if self._previous_state:
                    self.state = self._previous_state
                else:
                    # Fallback falls _previous_state nicht gesetzt wurde
                    self.state = "intro"
                
                # Stelle sicher, dass Position-Thread läuft
                if self.position_thread is None or not self.position_thread.is_alive():
                    self.position_thread = threading.Thread(
                        target=self._track_position,
                        daemon=True
                    )
                    self.position_thread.start()
                
                # Stelle sicher, dass transition_thread läuft (falls State "intro" ist)
                if self.state == "intro":
                    if self.transition_thread is None or not self.transition_thread.is_alive():
                        self.transition_thread = threading.Thread(
                            target=self._transition_to_loop,
                            daemon=True
                        )
                        self.transition_thread.start()
                
                # Stelle sicher, dass Loop-Thread läuft (falls State "queued" ist)
                if self.state == "queued":
                    if self.loop_thread is None or not self.loop_thread.is_alive():
                        self.loop_thread = threading.Thread(
                            target=self._start_loop_after_queue,
                            daemon=True
                        )
                        self.loop_thread.start()
    
    def stop(self):
        """Stoppt Audio mit Fade-Out (2 Sekunden)"""
        with self.lock:
            if self.state == "stopped" or self.state == "stopping":
                # Bereits gestoppt oder Fade-Out läuft bereits
                return
            
            # Setze State sofort auf "stopping" um mehrfache Aufrufe zu verhindern
            self.state = "stopping"
            
            # Starte Fade-Out in separatem Thread
            self.fadeout_thread = threading.Thread(
                target=self._fadeout_and_stop,
                daemon=True
            )
            self.fadeout_thread.start()
    
    def _fadeout_and_stop(self):
        """Führt Fade-Out durch und stoppt Audio"""
        # Fade-Out über 2 Sekunden - OHNE Lock, da fadeout() nicht blockierend ist
        # fadeout() startet den Fade-Out-Prozess und kehrt sofort zurück
        # Der Lock wird nur für State-Änderungen benötigt, nicht für fadeout() selbst
        pygame.mixer.music.fadeout(2000)
        
        # Warte bis Fade-Out fertig ist (ohne Lock, da nur lesend)
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
            # Prüfe regelmäßig ob State geändert wurde (z.B. durch start())
            with self.lock:
                if self.state != "stopping":
                    # State wurde geändert (z.B. durch start()), beende Fade-Out
                    return
        
        # Audio komplett stoppen und zurücksetzen
        with self.lock:
            # Prüfe nochmal ob State noch "stopping" ist (könnte durch start() geändert worden sein)
            if self.state == "stopping":
                pygame.mixer.music.stop()
                self.state = "stopped"
                self._previous_state = None
                self.current_position = 0.0
    
    def _track_position(self):
        """Überwacht Position kontinuierlich"""
        while True:
            with self.lock:
                # Prüfe State innerhalb des Locks für Thread-Safety
                if self.state not in ["intro", "queued", "looping"]:
                    break
                
                # Hole Position und berechne sie innerhalb des Locks
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    if self.state == "intro" or self.state == "queued":
                        # Intro oder gequeueter Track läuft noch
                        self.current_position = pos_ms / 1000.0
                    elif self.state == "looping":
                        # Position im Loop berechnen
                        loop_pos = pos_ms / 1000.0
                        # Modulo loop_duration, damit Position innerhalb der Loop-Dauer bleibt
                        # Wichtig: Modulo innerhalb des Locks, damit current_position konsistent ist
                        if self.loop_duration and self.loop_duration > 0:
                            loop_pos = loop_pos % self.loop_duration
                        if self.intro_duration:
                            self.current_position = self.intro_duration + loop_pos
                        else:
                            self.current_position = loop_pos
                # Wenn pos_ms < 0, behalte current_position bei (nicht aktualisieren)
            
            time.sleep(0.2)  # Update alle 200ms
    
    def get_position(self):
        """Gibt aktuelle Position zurück (Sekunden)"""
        with self.lock:
            return self.current_position
    
    def get_duration(self):
        """Gibt Gesamtdauer zurück (Intro + Loop)"""
        with self.lock:
            total = 0.0
            if self.intro_duration:
                total += self.intro_duration
            if self.loop_duration:
                total += self.loop_duration
            return total if total > 0 else None
    
    def set_position(self, seconds):
        """Springt zu bestimmter Position"""
        with self.lock:
            if self.state == "stopped" or self.state == "stopping":
                return False
            
            # Wenn intro_duration nicht bekannt ist, können wir nicht zuverlässig seeken
            if self.intro_duration is None:
                return False
            
            # Handle paused state: Setze Position ohne zu spielen
            was_paused = (self.state == "paused")
            if was_paused:
                # Stelle vorherigen State wieder her für Position-Berechnung
                if self._previous_state:
                    temp_state = self._previous_state
                else:
                    temp_state = "intro"
            else:
                temp_state = self.state
            
            # "queued" bedeutet Intro läuft noch, behandle wie "intro" (für beide Fälle)
            if temp_state == "queued":
                temp_state = "intro"
            
            # Prüfe ob Position im Intro- oder Loop-Bereich liegt
            if seconds < self.intro_duration:
                # Position im Intro-Bereich
                if temp_state == "intro" or (was_paused and temp_state == "intro"):
                    if was_paused:
                        # Während Pause: Lade Intro, setze Position, starte und pausiere sofort
                        pygame.mixer.music.stop()
                        pygame.mixer.music.load(self.intro_path)
                        pygame.mixer.music.play()
                        try:
                            pygame.mixer.music.set_pos(seconds)
                        except:
                            pass
                        pygame.mixer.music.pause()  # Pausiere sofort, damit unpause() funktioniert
                        self.current_position = seconds
                        self._previous_state = "intro"
                        return True
                    else:
                        # Versuche Position zu setzen (funktioniert nur bei bestimmten Formaten)
                        try:
                            pygame.mixer.music.set_pos(seconds)
                            self.current_position = seconds
                            # Wenn wir im Intro sind und Position geändert wurde, starte transition_thread neu
                            if self.state == "intro":
                                # Invalidiere alten Thread durch Änderung der Thread-ID
                                # Der alte Thread wird durch ID-Check beendet
                                self._transition_thread_id = None
                                # Starte neuen Thread mit korrekter Timing-Berechnung
                                self.transition_thread = threading.Thread(
                                    target=self._transition_to_loop,
                                    daemon=True
                                )
                                self.transition_thread.start()
                            return True
                        except:
                            # set_pos() nicht unterstützt, ignoriere
                            return False
                elif temp_state == "looping" or (was_paused and temp_state == "looping"):
                    # Wenn Loop läuft, können wir nicht ins Intro springen
                    # Stoppe Loop und starte Intro neu
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(self.intro_path)
                    if was_paused:
                        # Während Pause: Setze Position, starte und pausiere sofort
                        pygame.mixer.music.play()
                        try:
                            pygame.mixer.music.set_pos(seconds)
                        except:
                            pass
                        pygame.mixer.music.pause()  # Pausiere sofort, damit unpause() funktioniert
                        self._previous_state = "intro"
                    else:
                        pygame.mixer.music.play()
                        try:
                            pygame.mixer.music.set_pos(seconds)
                        except:
                            pass
                        self.state = "intro"
                        # Invalidiere alten Thread durch Änderung der Thread-ID
                        # Der alte Thread wird durch ID-Check beendet
                        self._transition_thread_id = None
                        # Starte transition_thread neu, da Position geändert wurde
                        self.transition_thread = threading.Thread(
                            target=self._transition_to_loop,
                            daemon=True
                        )
                        self.transition_thread.start()
                    self.current_position = seconds
                    return True
            else:
                # Position im Loop-Bereich
                loop_pos = seconds - (self.intro_duration or 0)
                if loop_pos < 0:
                    loop_pos = 0
                
                if temp_state == "looping" or (was_paused and temp_state == "looping"):
                    if was_paused:
                        # Während Pause: Lade Loop, setze Position, starte und pausiere sofort
                        pygame.mixer.music.stop()
                        pygame.mixer.music.load(self.loop_path)
                        pygame.mixer.music.play(loops=-1)
                        try:
                            pygame.mixer.music.set_pos(loop_pos)
                        except:
                            pass
                        pygame.mixer.music.pause()  # Pausiere sofort, damit unpause() funktioniert
                        self.current_position = seconds
                        self._previous_state = "looping"
                        return True
                    else:
                        # Versuche Position im Loop zu setzen
                        try:
                            pygame.mixer.music.set_pos(loop_pos)
                            self.current_position = seconds
                            return True
                        except:
                            # set_pos() nicht unterstützt
                            return False
                elif temp_state == "intro" or (was_paused and temp_state == "intro"):
                    # Wenn noch Intro läuft, starte Loop
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(self.loop_path)
                    if was_paused:
                        # Während Pause: Setze Position, starte und pausiere sofort
                        pygame.mixer.music.play(loops=-1)
                        try:
                            pygame.mixer.music.set_pos(loop_pos)
                        except:
                            pass
                        pygame.mixer.music.pause()  # Pausiere sofort, damit unpause() funktioniert
                        self._previous_state = "looping"
                    else:
                        pygame.mixer.music.play(loops=-1)
                        try:
                            pygame.mixer.music.set_pos(loop_pos)
                        except:
                            pass
                        self.state = "looping"
                    self.current_position = seconds
                    return True
            
            return False

