import pygame
import threading
import time
import os
import json

class AudioController:
    """Controller für serverseitiges Audio-Playback mit pygame.mixer"""
    
    def _dbg_log(self, run_id, hypothesis_id, location, message, data=None):
        # #region agent log
        # Bug 1 Fix: Debug-Logging entfernt - war nur für temporäres Debugging
        # Hardcodierter Pfad würde auf anderen Systemen fehlschlagen
        # Falls Debug-Logging benötigt wird, sollte es über ein konfigurierbares Logging-System erfolgen
        pass
        # #endregion

    def __init__(self, intro_path=None, loop_path=None):
        # pygame.mixer initialisieren mit optimierten Parametern für nahtlose Loops
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        
        if intro_path is None or loop_path is None:
            raise ValueError("intro_path und loop_path müssen angegeben werden")
        
        self.intro_path = intro_path
        self.loop_path = loop_path
        self.state = "stopped"  # stopped, intro, looping, paused, stopping
        self.lock = threading.Lock()
        self.transition_thread = None
        self.fadeout_thread = None
        self.position_thread = None
        self.loop_thread = None  # Thread für Loop-Übergang nach gequeueten Track
        self._previous_state = None  # Merkt sich vorherigen State beim Pause

        def _resolve_audio_path(primary_path):
            # Versuche primären Pfad zu laden (zur Validierung)
            try:
                pygame.mixer.Sound(primary_path)
                return primary_path
            except Exception:
                # Fallback: wenn .ogg -> .mp3
                if primary_path.lower().endswith(".ogg"):
                    mp3_path = primary_path[:-4] + ".mp3"
                    if os.path.exists(mp3_path):
                        try:
                            pygame.mixer.Sound(mp3_path)
                            return mp3_path
                        except Exception:
                            pass
            return primary_path

        # Resolved playback paths (mit Fallback)
        self.intro_play_path = _resolve_audio_path(self.intro_path)
        self.loop_play_path = _resolve_audio_path(self.loop_path)

        # Log initiale Dateiinformationen
        intro_info = None
        loop_info = None
        try:
            intro_stat = os.stat(self.intro_play_path)
            intro_info = {"exists": True, "size": intro_stat.st_size}
        except FileNotFoundError:
            intro_info = {"exists": False}
        try:
            loop_stat = os.stat(self.loop_play_path)
            loop_info = {"exists": True, "size": loop_stat.st_size}
        except FileNotFoundError:
            loop_info = {"exists": False}
        self._dbg_log("midstop", "H1", "audio_controller.py:__init__", "init_paths", {
            "intro_play_path": self.intro_play_path,
            "loop_play_path": self.loop_play_path,
            "intro_info": intro_info,
            "loop_info": loop_info,
        })
        
        # Preload Sound-Objekte für Dauer-Erkennung (mit resolved paths)
        self.intro_duration = None
        self.loop_duration = None
        self.current_position = 0.0
        
        try:
            intro_sound = pygame.mixer.Sound(self.intro_play_path)
            self.intro_duration = intro_sound.get_length()
        except:
            pass
        
        try:
            loop_sound = pygame.mixer.Sound(self.loop_play_path)
            self.loop_duration = loop_sound.get_length()
        except:
            pass
        
        # (Optional) Dateien prüfen
        
    def get_status(self):
        """Gibt aktuellen Status zurück"""
        with self.lock:
            status_map = {
                "stopped": "bereit",
                "intro": "Intro läuft …",
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
            elif self.state in ["intro", "looping"]:
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
                if not os.path.exists(self.intro_play_path):
                    self.state = "stopped"
                    raise FileNotFoundError(f"Intro-Datei nicht gefunden oder ungültig: {self.intro_play_path}")
                if not os.path.exists(self.loop_play_path):
                    self.state = "stopped"
                    raise FileNotFoundError(f"Loop-Datei nicht gefunden oder ungültig: {self.loop_play_path}")
                
                # Intro abspielen
                try:
                    pygame.mixer.music.load(self.intro_play_path)
                    pygame.mixer.music.play()
                    self._dbg_log("midstop", "H2", "audio_controller.py:start", "intro_loaded", {
                        "intro_play_path": self.intro_play_path,
                        "state": self.state
                    })
                except Exception as e:
                    self._dbg_log("midstop", "H2", "audio_controller.py:start", "intro_load_failed", {
                        "intro_play_path": self.intro_play_path,
                        "error": str(e)
                    })
                    self.state = "stopped"
                    raise
                
                # Thread für Übergang zu Loop
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
    
    def start_at_position(self, seconds):
        """Startet Audio ab einer bestimmten Position (in Sekunden)"""
        # Bug 1 Fix: Prüfe intro_duration OHNE Lock zu halten, um Deadlock zu vermeiden
        with self.lock:
            intro_duration_check = self.intro_duration
        
        # Wenn intro_duration nicht bekannt ist, starte normal (OHNE Lock)
        if intro_duration_check is None:
            self.start()
            return
        
        # Lock wieder erwerben für den Rest der Operation
        with self.lock:
            if seconds < 0:
                seconds = 0
            
            # Stoppe alles vorher
            pygame.mixer.music.stop()
            
            # Prüfe ob Dateien existieren
            if not os.path.exists(self.intro_play_path):
                self.state = "stopped"
                raise FileNotFoundError(f"Intro-Datei nicht gefunden oder ungültig: {self.intro_play_path}")
            if not os.path.exists(self.loop_play_path):
                self.state = "stopped"
                raise FileNotFoundError(f"Loop-Datei nicht gefunden oder ungültig: {self.loop_play_path}")
            
            if seconds < intro_duration_check:
                # Position im Intro-Bereich
                self.state = "intro"
                try:
                    pygame.mixer.music.load(self.intro_play_path)
                    pygame.mixer.music.play()
                    # Versuche Position zu setzen
                    try:
                        pygame.mixer.music.set_pos(seconds)
                    except:
                        # set_pos() nicht unterstützt, ignoriere
                        pass
                    self.current_position = seconds
                    
                    # Thread für Übergang zu Loop
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
                except Exception as e:
                    self.state = "stopped"
                    raise
            else:
                # Position im Loop-Bereich - starte direkt Loop
                loop_pos = seconds - intro_duration_check
                if loop_pos < 0:
                    loop_pos = 0
                
                self.state = "looping"
                try:
                    pygame.mixer.music.load(self.loop_play_path)
                    pygame.mixer.music.play(loops=-1)
                    # Versuche Position im Loop zu setzen
                    try:
                        pygame.mixer.music.set_pos(loop_pos)
                    except:
                        # set_pos() nicht unterstützt, ignoriere
                        pass
                    self.current_position = seconds
                    
                    # Bug 2 Fix: Starte auch den continuous_loop_queue Thread für nahtlose Loops
                    self.loop_thread = threading.Thread(
                        target=self._continuous_loop_queue,
                        daemon=True
                    )
                    self.loop_thread.start()
                    
                    # Thread für Position-Tracking starten
                    self.position_thread = threading.Thread(
                        target=self._track_position,
                        daemon=True
                    )
                    self.position_thread.start()
                except Exception as e:
                    self.state = "stopped"
                    raise
    
    def _transition_to_loop(self):
        """Queue Loop nahtlos vor Ende des Intros mit optimiertem Fade-Out, dann starte kontinuierliches Looping"""
        # Überwache Position und queue basierend auf tatsächlicher Playback-Position
        # statt auf get_length() (kann ungenau sein)
        
        check_interval = 0.02  # Sehr häufige Checks für präziseren Übergang (20ms)
        intro_duration_estimate = self.intro_duration or 600  # Fallback-Schätzung
        
        # Optimierte Fade-Dauer für nahtloseren Übergang (länger und sanfter)
        fade_duration = 0.5  # 0.5 Sekunden Fade für sanfteren Übergang
        
        # Queue Loop noch früher für maximalen Puffer und nahtloseren Übergang
        queue_time_before_end = 4.0  # 4 Sekunden vor Ende für mehr Sicherheit
        
        while True:
            time.sleep(check_interval)
            
            with self.lock:
                if self.state != "intro":
                    return
                
                # Hole aktuelle Position
                try:
                    pos_ms = pygame.mixer.music.get_pos()
                    if pos_ms >= 0:
                        current_pos = pos_ms / 1000.0
                        
                        # Queue Loop früher für nahtloseren Übergang
                        if current_pos >= intro_duration_estimate - queue_time_before_end:
                            # Queue ersten Loop
                            pygame.mixer.music.queue(self.loop_play_path)
                            # Queue zweiten Loop für noch mehr Sicherheit (falls erster nicht nahtlos genug)
                            try:
                                pygame.mixer.music.queue(self.loop_play_path)
                            except:
                                # Falls zweites Queue nicht möglich, ist das ok
                                pass
                            
                            # Starte Thread für kontinuierliches Looping
                            self.loop_thread = threading.Thread(
                                target=self._continuous_loop_queue,
                                daemon=True
                            )
                            self.loop_thread.start()
                            
                            # Starte optimierten Fade-Out-Thread
                            fade_thread = threading.Thread(
                                target=self._fade_out_intro_optimized,
                                args=(fade_duration,),
                                daemon=True
                            )
                            fade_thread.start()
                            
                            # Setze State auf "looping" sobald Loop gequeued ist
                            # Der gequeuete Loop wird nahtlos nach dem Intro spielen
                            self.state = "looping"
                            if self.intro_duration:
                                self.current_position = self.intro_duration
                            return
                except:
                    pass
                
                # Fallback: Wenn Musik gestoppt ist, starte Loop direkt
                if not pygame.mixer.music.get_busy():
                    # Intro ist fertig, starte Loop
                    pygame.mixer.music.load(self.loop_play_path)
                    pygame.mixer.music.play(loops=-1)
                    self.state = "looping"
                    if self.intro_duration:
                        self.current_position = self.intro_duration
                    return
    
    def _fade_out_intro_optimized(self, fade_duration):
        """Optimierter Volume-Fade-Out am Ende des Intros für nahtloseren Übergang"""
        # Warte bis kurz vor Ende des Intros, dann führe einen sanften Volume-Fade durch
        if self.intro_duration is None:
            return
        
        check_interval = 0.005  # Sehr häufige Checks (5ms) für präzises Timing
        fade_start_time = self.intro_duration - fade_duration
        
        # Hole initiales Volume (Fallback auf 1.0 wenn nicht verfügbar)
        try:
            initial_volume = pygame.mixer.music.get_volume()
        except:
            initial_volume = 1.0
        
        # Timeout-Schutz: Stelle Volume nach maximal fade_duration + 0.5 Sekunden wieder her
        max_fade_time = fade_duration + 0.5
        fade_start_wall_time = None
        volume_restored = False
        
        # Warte bis Fade-Start-Zeit erreicht ist
        while True:
            time.sleep(check_interval)
            
            with self.lock:
                if self.state != "looping":
                    # State hat sich geändert, stelle Volume wieder her und beende
                    if not volume_restored:
                        try:
                            pygame.mixer.music.set_volume(initial_volume)
                        except:
                            pass
                        volume_restored = True
                    return
                
                try:
                    pos_ms = pygame.mixer.music.get_pos()
                    if pos_ms >= 0:
                        current_pos = pos_ms / 1000.0
                        
                        # Wenn wir kurz vor Ende sind, starte optimierten Volume-Fade
                        if current_pos >= fade_start_time and current_pos < self.intro_duration:
                            # Merke Start-Zeit des Fade-Outs
                            if fade_start_wall_time is None:
                                fade_start_wall_time = time.time()
                            
                            # Berechne Fade-Progress (0.0 = Anfang, 1.0 = Ende)
                            fade_progress = (current_pos - fade_start_time) / fade_duration
                            fade_progress = min(1.0, max(0.0, fade_progress))
                            
                            # Optimierte Fade-Kurve: Exponentielle Kurve für sanfteren Übergang
                            # Verwendet eine quadratische Kurve für natürlicheren Fade
                            fade_curve = fade_progress * fade_progress  # Quadratische Kurve
                            
                            # Sanfter Fade-Out: Volume von initial_volume auf 20% (statt 30%)
                            # für nahtloseren Übergang zum Loop
                            min_volume_ratio = 0.2  # Fade auf 20% des Originals
                            target_volume = initial_volume * (1.0 - fade_curve * (1.0 - min_volume_ratio))
                            try:
                                pygame.mixer.music.set_volume(target_volume)
                            except:
                                pass
                            
                            # Timeout-Check: Wenn zu viel Zeit vergangen ist, stelle Volume wieder her
                            if fade_start_wall_time is not None:
                                elapsed_fade_time = time.time() - fade_start_wall_time
                                if elapsed_fade_time >= max_fade_time:
                                    if not volume_restored:
                                        try:
                                            pygame.mixer.music.set_volume(initial_volume)
                                        except:
                                            pass
                                        volume_restored = True
                                    return
                            
                            if current_pos >= self.intro_duration:
                                # Intro ist vorbei, stelle Volume sofort wieder her für Loop
                                if not volume_restored:
                                    try:
                                        pygame.mixer.music.set_volume(initial_volume)
                                    except:
                                        pass
                                    volume_restored = True
                                return
                        elif current_pos >= self.intro_duration:
                            # Intro ist bereits vorbei, stelle Volume wieder her
                            if not volume_restored:
                                try:
                                    pygame.mixer.music.set_volume(initial_volume)
                                except:
                                    pass
                                volume_restored = True
                            return
                        elif fade_start_wall_time is not None:
                            # Fade wurde gestartet, aber Position ist wieder kleiner (Loop läuft)
                            # Stelle Volume sofort wieder her
                            elapsed_fade_time = time.time() - fade_start_wall_time
                            if elapsed_fade_time >= fade_duration:
                                if not volume_restored:
                                    try:
                                        pygame.mixer.music.set_volume(initial_volume)
                                    except:
                                        pass
                                    volume_restored = True
                                return
                except:
                    # Bei Fehler: Stelle Volume sicherheitshalber wieder her nach Timeout
                    if fade_start_wall_time is not None:
                        elapsed_fade_time = time.time() - fade_start_wall_time
                        if elapsed_fade_time >= max_fade_time:
                            if not volume_restored:
                                try:
                                    pygame.mixer.music.set_volume(initial_volume)
                                except:
                                    pass
                                volume_restored = True
                            return
                    pass
                
                # Wenn Musik gestoppt ist, stelle Volume wieder her und beende
                if not pygame.mixer.music.get_busy():
                    if not volume_restored:
                        try:
                            pygame.mixer.music.set_volume(initial_volume)
                        except:
                            pass
                        volume_restored = True
                    return
    
    def _continuous_loop_queue(self):
        """Queued kontinuierlich neue Loops für nahtlose Endlosschleife"""
        # Statt den Loop zu stoppen und neu zu starten, queuen wir kontinuierlich
        # neue Loops, bevor der aktuelle fertig ist. Das ist nahtloser.
        
        loop_duration = self.loop_duration
        if loop_duration is None:
            try:
                loop_sound = pygame.mixer.Sound(self.loop_play_path)
                loop_duration = loop_sound.get_length()
                self.loop_duration = loop_duration
            except:
                loop_duration = None
        
        if loop_duration is None:
            # Fallback: Wenn loop_duration nicht bekannt ist, verwende alte Methode
            return
        
        check_interval = 0.02  # Sehr häufige Checks (20ms) für präzises Timing
        loop_started = False
        last_queued_time = None
        queue_time_before_end = 0.8  # Queue neuen Loop 0.8s vor Ende für mehr Sicherheit
        
        while True:
            time.sleep(check_interval)
            
            # Bug 2 Fix: Prüfe get_busy() außerhalb des Locks, um Lock-Zeit zu minimieren
            music_busy = pygame.mixer.music.get_busy()
            
            with self.lock:
                if self.state != "looping":
                    return
                
                if not music_busy:
                    # Musik gestoppt - könnte sein, dass gequeueter Loop nicht gestartet hat
                    # Bug 2 Fix: Lock freigeben vor sleep, um andere Threads nicht zu blockieren
                    pass
            
            # Bug 2 Fix: Sleep außerhalb des Lock-Blocks
            if not music_busy:
                time.sleep(0.1)
                # Prüfe nochmal nach Sleep
                music_busy_after_sleep = pygame.mixer.music.get_busy()
                with self.lock:
                    if self.state != "looping":
                        return
                    if not music_busy_after_sleep:
                        # Starte Loop manuell und queue sofort einen weiteren
                        pygame.mixer.music.load(self.loop_play_path)
                        pygame.mixer.music.play()
                        pygame.mixer.music.queue(self.loop_play_path)
                        last_queued_time = time.time()
                        loop_started = True
                        continue
                continue
            
            # Position-Überwachung innerhalb des Locks
            with self.lock:
                if self.state != "looping":
                    return
                
                # Überwache Position im Loop
                try:
                    pos_ms = pygame.mixer.music.get_pos()
                    if pos_ms >= 0:
                        current_pos = pos_ms / 1000.0
                        
                        # Erkennung: Wenn Position sehr klein ist (< 0.1s), hat Loop gestartet
                        if not loop_started and current_pos < 0.1:
                            loop_started = True
                        
                        # Wenn Loop gestartet hat, queue einen neuen Loop bevor der aktuelle fertig ist
                        if loop_started:
                            # Berechne verbleibende Zeit im aktuellen Loop
                            remaining_time = loop_duration - current_pos
                            
                            # Queue neuen Loop wenn wir nah am Ende sind und noch keinen gequeued haben
                            # oder wenn genug Zeit seit dem letzten Queue vergangen ist
                            should_queue = False
                            if remaining_time <= queue_time_before_end:
                                if last_queued_time is None:
                                    should_queue = True
                                else:
                                    # Stelle sicher, dass wir nicht zu häufig queuen
                                    time_since_last_queue = time.time() - last_queued_time
                                    if time_since_last_queue >= loop_duration - queue_time_before_end:
                                        should_queue = True
                            
                            if should_queue:
                                try:
                                    pygame.mixer.music.queue(self.loop_play_path)
                                    last_queued_time = time.time()
                                except:
                                    # Queue fehlgeschlagen, versuche es später erneut
                                    pass
                except:
                    pass
    
    
    def pause(self):
        """Pausiert aktuelles Audio"""
        with self.lock:
            if self.state in ["intro", "looping"]:
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
                
                # Bug 3 Fix: Stelle sicher, dass loop_thread läuft (falls State "looping" ist)
                if self.state == "looping":
                    if self.loop_thread is None or not self.loop_thread.is_alive():
                        self.loop_thread = threading.Thread(
                            target=self._continuous_loop_queue,
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
                if self.state not in ["intro", "looping"]:
                    break
                
                # Hole Position und berechne sie innerhalb des Locks
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    if self.state == "intro":
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
            
            
            # Prüfe ob Position im Intro- oder Loop-Bereich liegt
            if seconds < self.intro_duration:
                # Position im Intro-Bereich
                if temp_state == "intro" or (was_paused and temp_state == "intro"):
                    if was_paused:
                        # Während Pause: Lade Intro, setze Position, starte und pausiere sofort
                        pygame.mixer.music.stop()
                        pygame.mixer.music.load(self.intro_play_path)
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
                                # Starte neuen Thread
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
                    pygame.mixer.music.load(self.intro_play_path)
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
                        pygame.mixer.music.load(self.loop_play_path)
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
                    pygame.mixer.music.load(self.loop_play_path)
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

