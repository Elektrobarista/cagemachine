# Verwende Python 3.10 als Basis-Image
FROM python:3.10-slim

# Setze Arbeitsverzeichnis
WORKDIR /app

# Installiere System-Abhängigkeiten für pygame (SDL2, Audio-Libraries)
RUN apt-get update && apt-get install -y \
    libsdl2-dev \
    libsdl2-mixer-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiere requirements.txt und installiere Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere Anwendungsdateien
COPY . .

# Exponiere Port 3000
EXPOSE 3000

# Setze Umgebungsvariable für Flask
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Starte die Anwendung
CMD ["python", "app.py"]

