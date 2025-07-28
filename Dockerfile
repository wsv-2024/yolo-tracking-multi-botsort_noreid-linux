# Verwende das offizielle NVIDIA PyTorch Image mit CUDA-Unterstützung
FROM ultralytics/ultralytics

# Setze Umgebungsvariablen
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Installiere Systemabhängigkeiten und bereinige anschließend
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gnupg \
    libgl1-mesa-glx \
    libgtk2.0-dev \
	dos2unix \
    pkg-config \
    unixodbc-dev \
    freetds-dev \
    freetds-bin \
    tdsodbc \
    && rm -rf /var/lib/apt/lists/*

# Configure FreeTDS ODBC driver
RUN echo "[FreeTDS]" > /etc/odbcinst.ini \
    && echo "Description = FreeTDS Driver" >> /etc/odbcinst.ini \
    && echo "Driver = /usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so" >> /etc/odbcinst.ini \
    && echo "Setup = /usr/lib/x86_64-linux-gnu/odbc/libtdsS.so" >> /etc/odbcinst.ini \
    && echo "CPTimeout = " >> /etc/odbcinst.ini \
    && echo "CPReuse = " >> /etc/odbcinst.ini

# Kopiere Anwendungsdateien
COPY requirements.txt .
# Kopiere alle Python-Skripte
COPY *.py .
COPY best.pt .
COPY start.sh .
COPY config.ini .
COPY botsort.yaml .
COPY 1.txt .

# Erstelle Datenverzeichnisse
RUN mkdir -p saved_data/images saved_data/csv saved_data/full_screenshots

# Konvertiere Zeilenenden von start.sh zu Unix-Format
RUN dos2unix start.sh

# Installiere Python-Abhängigkeiten
RUN pip install --upgrade pip && \
    pip uninstall -y opencv-python-headless && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir opencv-python==4.7.0.72 && \
    python3 -c "import easyocr; reader = easyocr.Reader(['en', 'de']); print('Models downloaded')"

# Setze die DISPLAY-Umgebungsvariable auf den Host
ENV DISPLAY=${DISPLAY}

# Stelle sicher, dass das start.sh Skript ausführbar ist
RUN chmod +x start.sh

# Optional: Überprüfen Sie den Inhalt des Arbeitsverzeichnisses
RUN ls -la /app

# Starte das Start-Skript
CMD ["./start.sh"]
