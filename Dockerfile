# Verwende Ubuntu mit Python
FROM ubuntu:22.04

# Installiere Python und Basis-Tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Setze Arbeitsverzeichnis
WORKDIR /app

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
CMD ["python3", "app.py"]

