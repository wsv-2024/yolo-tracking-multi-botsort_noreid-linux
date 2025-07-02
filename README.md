# YOLO Tracking Multi Image - Version 2.0

Dieses Projekt implementiert ein multi-kamerales Tracking- und Kennzeichenerkennungssystem basierend auf YOLO mit **Camera 2 als primärer Detektor**. Das System führt intelligentes Kennzeichen-Matching zwischen Kameras durch und erstellt simultane Screenshots aller Kameras für jedes Event.

## 🏗️ System-Architektur

### **Detection Flow:**
1. **Primary Detection (Camera 2)**: Alle Schifferkennungen starten hier
2. **License Matching**: Exit-Events von Camera 1/3 werden mit Camera 2 Events gematcht
3. **Timeout Handling**: 20-Minuten Timeout bei fehlenden Exit-Events
4. **Event Documentation**: Simultane Screenshots aller Kameras mit YOLO-Labels

### **Key Features:**
- ✅ Camera 2 Primary Detection mit Kennzeichenerkennung
- ✅ Intelligentes License-Matching zwischen Kameras
- ✅ 20-Minuten Timeout-Regel für unvollständige Durchfahrten
- ✅ Simultane 3-Kamera Event-Screenshots
- ✅ Zentralisierte CSV-Ausgabe mit Pairing-Status
- ✅ Gewerbliche Kennzeichen-Identifikation aus `1.txt`
- ✅ Erweiterte OCR mit Multi-Method-Ansatz und Qualitätsbewertung
- ✅ Real-Time Performance-Monitoring und -Optimierung

---

## 📁 Repository-Struktur & Vollständige Skript-Dokumentation

### 🎯 Core Application Files

#### **main.py** - Haupteinstiegspunkt & Prozess-Orchestrierung

**Zweck:** Zentraler Orchestrator für alle Multiprocessing-Worker des Systems

**Funktionalität:**
- Lädt aktive Location aus `active_location.txt` und Stream-Konfiguration aus `config.ini`
- Initialisiert Shared-Memory-Objekte für Interprocess-Kommunikation
- Startet und koordiniert Preview-, Tracking- und Aggregator-Prozesse
- Verwaltet graceful shutdown aller Prozesse bei SIGTERM/SIGINT

**Abhängigkeiten:**
- `config_utils.py` - Konfigurationsverwaltung
- `image_utils.py` - Bildverarbeitung
- `preview.py` - Live-Preview-Worker
- `tracking.py` - YOLO-Tracking-Worker
- `aggregator_events.py` - Event-Aggregation

**Ein-/Ausgabe:**
- **Input:** `active_location.txt`, `config.ini`, `1.txt`
- **Output:** Orchestrierte Prozesse, Console-Logs

**Konfiguration:**
- Location automatisch aus `active_location.txt`
- Stream-Anzahl automatisch basierend auf `config.ini`
- Timeout für Event-Aggregation: 20 Minuten (Standard)

**Verwendung:**
```bash
python main.py
```

---

#### **tracking.py** - Core Tracking & OCR Engine

**Zweck:** Haupttracking-Worker mit YOLO-Objekterkennung und erweiterten OCR-Funktionen

**Funktionalität:**
- YOLO-Modell-Initialisierung mit automatischem GPU/CPU-Fallback
- Echtzeit-Video-Stream-Verarbeitung mit Object-Tracking
- Multi-Frame OCR-Tracking für konsistente Kennzeichenerkennung
- Line-Crossing-Detektion mit konfigurierbaren Linien
- Event-Screenshot-Erstellung für alle Kameras simultan
- Globale Farbverwaltung für konsistente Visualisierung

**Abhängigkeiten:**
- `ultralytics` - YOLO-Modell
- `easyocr` - OCR-Engine
- `torch` - Deep Learning Framework
- `config_utils.py` - Farbkonfiguration
- `image_utils.py` - Erweiterte OCR-Funktionen

**Ein-/Ausgabe:**
- **Input:** RTSP-Stream, YOLO-Modell (`best.pt`), Tracking-Config (`botsort.yaml`)
- **Output:** Event-Queue, Preview-Frames, Event-Screenshots

**Parameter:**
- `cam_idx`: Kamera-Index (1-3)
- `stream_url`: RTSP-URL des Video-Streams
- `location`: Location-Name für Dateipfade
- `line1/line2`: Kontrolllinien-Positionen
- `orientation`: "vertical" oder "horizontal"
- `commercial_licenses`: Set bekannter gewerblicher Kennzeichen

**OCR-Features:**
- Multi-Method OCR-Ansatz (Standard, Detailed, Paragraph, Enhanced)
- Adaptive Bildvorverarbeitung basierend auf Tageszeit
- Bildqualitätsbewertung vor OCR-Verarbeitung
- SmartOCRValidator für intelligente Text-Validierung
- Multi-Frame-Konsensus für robuste Kennzeichenerkennung

**Konfiguration:**
- YOLO-Modell: `best.pt` (austauschbar)
- OCR-Sprachen: Englisch/Deutsch (erweiterbar)
- Confidence-Schwellenwerte über `config.ini`
- Bildqualitäts-Schwellenwerte über `config.ini`
- Line-Positionen über `config.ini`

---

#### **aggregator_events.py** - Event Processing & CSV Generation

**Zweck:** Zentraler Event-Aggregator mit Camera 2 als Primary Detection

**Funktionalität:**
- Wartet auf Events von allen Kameras und implementiert Matching-Logik
- Camera 2 fungiert als primärer Detektor - alle Events starten hier
- Exit-Events von Camera 1/3 werden mit Camera 2 Events gematcht
- Timeout-Management für unvollständige Durchfahrten (20 Minuten)
- CSV-Ausgabe mit detailliertem Pairing-Status
- Automatische Zeitbucket-Generierung für Event-Matching

**Abhängigkeiten:**
- `pandas` - CSV-Verarbeitung
- `image_utils.py` - Filename-Sanitization

**Ein-/Ausgabe:**
- **Input:** Event-Queue von Tracking-Workern
- **Output:** CSV-Dateien in `saved_data/{location}/csv/`

**Parameter:**
- `event_queue`: Multiprocessing Queue mit Events
- `location`: Location-Name für Ausgabepfad
- `stop_event`: Signal für Prozess-Beendigung
- `flush_interval`: Sekunden zwischen CSV-Schreibvorgängen (Standard: 120s)
- `timeout_minutes`: Minuten für Event-Timeout (Standard: 20)

**CSV-Ausgabeformat:**
```csv
track_id,class_id,class_name,direction,entry_timestamp,exit_timestamp,location,extracted_text,identified_licence_number,ocr_confidence,confidence,pairing_status,ocr_method_used,frame_quality_score
```

**Matching-Logik:**
- Zeitbucket-basiertes Matching (5-Minuten-Fenster)
- Klassen-ID und Richtungsübereinstimmung
- Zeitbasierte Toleranz für asynchrone Events
- Automatische Timeout-Behandlung für unvollständige Passagen

---

#### **preview.py** - Live Preview Display

**Zweck:** Zeigt alle Kamera-Feeds nebeneinander in einem einzigen Fenster

**Funktionalität:**
- Side-by-side Anzeige aller verfügbaren Kameras
- Real-Time FPS-Anzeige pro Kamera
- Täglicher Zähler für erkannte Boote
- Farbcodierte Titelleiste mit System-Status

**Abhängigkeiten:**
- `cv2` - OpenCV für Bildanzeige
- `numpy` - Array-Verarbeitung

**Ein-/Ausgabe:**
- **Input:** JPEG-Frame-Queues von Tracking-Workern
- **Output:** Live-Display-Fenster

**Parameter:**
- `queues`: Liste von Multiprocessing-Queues mit JPEG-Frames
- `daily_counter`: Shared Counter für tägliche Boot-Zählung

**Layout-Konfiguration:**
- Fensterbreite: 3 × 640px + 2 × 20px Spacer = 1960px
- Fensterhöhe: 30px Titel + 30px Info + 360px Kamera = 420px
- Spacer-Breite zwischen Kameras: 20px
- Titelleiste: RGB(239,239,239) mit schwarzem Text

**Steuerung:**
- Taste 'q': Beenden der Preview

---

### 🛠️ Utility Modules

#### **image_utils.py** - Erweiterte Bildverarbeitung & OCR-Engine

**Zweck:** Fortschrittliche Bildverarbeitung, OCR-Optimierung und intelligente Text-Validierung

**Kernklassen:**

**`SmartOCRValidator`** - Intelligente OCR-Validierung
- Automatische Text-Typ-Erkennung (Kennzeichen, Bootsnamen, Unbekannt)
- Format-spezifische Korrekturen und Validierung
- Ähnlichkeitssuche mit bekannten Lizenzen
- Umfassende Score-Berechnung für OCR-Qualität

**`MultiFrameOCRTracker`** - Multi-Frame OCR-Tracking
- Frame-übergreifende Konsensus-Bildung
- Automatische Cleanup alter Tracks
- Gewichtete Score-Berechnung für beste Ergebnisse

**Hauptfunktionen:**

**`perform_ocr_on_license_enhanced()`** - Verbesserte OCR-Pipeline
- Multi-Method OCR-Ansatz (4 verschiedene Methoden)
- Adaptive Bildvorverarbeitung basierend auf Tageszeit
- Bildqualitätsbewertung vor OCR-Verarbeitung
- Erweiterte Fehlerbehandlung und Logging

**`enhance_image_preprocessing()`** - Erweiterte Bildvorverarbeitung
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- TV-Chambolle Denoising
- Adaptive Thresholding
- Morphological Operations
- Edge Enhancement
- Multi-Scale Processing

**`calculate_frame_quality()`** - Bildqualitätsbewertung
- Schärfe-Messung durch Laplacian-Varianz
- Kontrast-Berechnung
- Helligkeit-Analyse
- Kombinierter Quality-Score

**Abhängigkeiten:**
- `cv2` - OpenCV für Bildverarbeitung
- `numpy` - Numerische Operationen
- `scikit-image` - Erweiterte Bildverarbeitung
- `difflib` - String-Ähnlichkeitsvergleich

**Konfiguration über `config.ini`:**
```ini
[ocr_settings]
enable_clahe = true
enable_denoising = true
scale_factor = 2.0
min_confidence = 0.3
max_frame_history = 5
min_frame_quality = 100.0
enable_gpu_acceleration = true
```

**Performance-Features:**
- Schwierige Fälle werden automatisch in `difficult_cases/` gespeichert
- Detailliertes Performance-Logging in `logs/ocr_performance.jsonl`
- Real-Time OCR-Statistics und -Monitoring

---

#### **config_utils.py** - Konfigurationsverwaltung & Validierung

**Zweck:** Zentrale Verwaltung aller Konfigurationsdateien mit Validierung und globaler Farbverwaltung

**Hauptfunktionen:**

**`load_active_location()`** - Location-Verwaltung
- Lädt aktive Location aus `active_location.txt`
- Validiert Existenz in `config.ini`
- UTF-8 Support für deutsche Umlaute

**`load_config()`** - Stream-Konfiguration
- Lädt RTSP-URLs und Line-Konfiguration pro Location
- Validiert Orientierung (vertical/horizontal)
- Automatische Stream-Anzahl-Erkennung

**`load_ocr_config()`** - OCR-Einstellungen
- Lädt alle OCR-Parameter aus `config.ini`
- Standard-Fallback-Werte
- Automatische Verzeichniserstellung

**`GlobalColorMapper`** - Zentrale Farbverwaltung
- Konsistente Farbzuweisung über alle Streams
- Konfigurierbare Farben pro Bootsklasse
- Automatische Fallback-Farben
- Performance-Übersicht und Empfehlungen

**Abhängigkeiten:**
- `configparser` - INI-Datei-Verarbeitung
- `matplotlib` - Performance-Charts (optional)

**Unterstützte Locations:**
- Automatische Erkennung aus `config.ini`
- UTF-8 Support: Fürstenberg, Diemitz, Bredereiche
- Erweiterbar durch neue `[location]` Sektionen

**Validierungsfunktionen:**
- `validate_location_exists()` - Prüft Location in config.ini
- `validate_color_configuration()` - Validiert Farbkonfiguration
- `create_new_location_template()` - Generiert Templates für neue Locations

---

### 📊 Monitoring & Maintenance

#### **ocr_monitor.py** - OCR Performance Analysis & Monitoring

**Zweck:** Detaillierte Überwachung und Analyse der OCR-Performance mit Real-Time-Monitoring

**Hauptklasse: `OCRPerformanceMonitor`**

**Funktionalität:**
- Real-Time OCR-Performance-Tracking
- Historische Datenanalyse mit Zeitfenster-Filtern
- Performance-Charts und detaillierte Reports
- Method-Vergleiche und Optimierungsempfehlungen
- Automatische Problemerkennung und Alerting

**Kern-Features:**

**Performance-Analyse:**
- Erfolgsraten nach Zeitfenstern (1h, 24h, Woche, Gesamt)
- Methoden-Vergleich mit Confidence und Verarbeitungszeit
- Textlängen-Analyse und Format-Erkennung
- Problematische Fälle mit niedrigen Confidence-Werten

**Chart-Generierung:**
- Erfolgsrate über Zeit (Stunden-basiert)
- Methoden-Vergleich mit farbkodierten Balken
- Confidence-Verteilungshistogramm
- Ausgabe als hochauflösende PNG-Dateien

**Real-Time Monitoring:**
- Live-Aktualisierung alle 10 Sekunden
- Konsolen-Display mit aktuellen Statistiken
- Überwachung der letzten 100 OCR-Aufrufe

**Abhängigkeiten:**
- `matplotlib` - Chart-Generierung
- `pandas` - Datenanalyse
- `json` - Log-Datei-Verarbeitung

**Verwendung:**
```bash
# Performance-Report generieren
python ocr_monitor.py --report

# Performance-Charts erstellen
python ocr_monitor.py --charts

# Real-Time Monitoring starten
python ocr_monitor.py --monitor

# Kurzer Status (Standard)
python ocr_monitor.py
```

**Output-Dateien:**
- `ocr_report.txt` - Detaillierter Performance-Report
- `charts/success_rate_over_time.png` - Erfolgsrate-Verlauf
- `charts/method_comparison.png` - Methoden-Vergleich
- `charts/confidence_distribution.png` - Confidence-Verteilung

**Empfehlungssystem:**
- Automatische Warnungen bei Erfolgsrate < 70%
- GPU-Beschleunigung-Empfehlungen bei langsamer Verarbeitung
- Bildqualitäts-Optimierung bei niedriger Confidence
- Best-Practice-Empfehlungen basierend auf Datenanalyse

---

#### **Azure_blob_upload.py** - Cloud Data Synchronization

**Zweck:** Automatische Synchronisation lokaler Daten mit Azure Blob Storage

**Funktionalität:**
- Timestamp-basierte Synchronisation vermeidet Duplikate
- Upload von CSV-Dateien und Event-Screenshots
- Location-aware Verzeichnisstruktur
- Robuste Fehlerbehandlung und Retry-Logik

**Upload-Targets:**
- **CSV-Dateien:** `saved_data/{location}/csv/` → `CSV_output/Yolo_Multi/`
- **Event-Screenshots:** `saved_data/{location}/events/` → `model-inputs/Yolo-Multi/`

**Abhängigkeiten:**
- `azure-storage-blob` - Azure SDK
- `image_utils.py` - Filename-Sanitization

**Sync-Logik:**
- Vergleicht lokale Datei-Timestamps mit Blob-Timestamps
- Uploaded nur neuere Dateien
- Erhält Verzeichnisstruktur in der Cloud
- Separate Behandlung für CSV-Dateien und Event-Verzeichnisse

**Konfiguration:**
```python
AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;..."
CONTAINER_NAME = "wsv3"
```

**Verwendung:**
```bash
python Azure_blob_upload.py
```

**Event-Upload:**
- Komplett-Upload ganzer Event-Verzeichnisse
- Zeitstempel-Vergleich auf Verzeichnisebene
- Upload aller Dateien (.jpg + .txt) pro Event

---

### ⚙️ Configuration Files

#### **config.ini** - Zentrale Systemkonfiguration

**Zweck:** Hauptkonfigurationsdatei für alle System-Einstellungen

**Sektionen:**

**`[email]` - E-Mail-Benachrichtigungen**
```ini
smtp_server = smtp.gmail.com
smtp_port = 587
email_address = wsvschiffszaehlung@gmail.com
email_password = WSV@1234
recipients = email1@domain.com,email2@domain.com
```

**`[ocr_settings]` - OCR-Optimierung**
```ini
# Bildvorverarbeitung
enable_clahe = true
enable_denoising = true
enable_sharpening = true
scale_factor = 2.0

# OCR-Parameter
min_confidence = 0.3
max_ocr_attempts = 3
enable_multi_frame = true
max_frame_history = 5

# Qualitätsschwellen
min_frame_quality = 100.0
min_text_length = 2
max_text_length = 20

# Performance-Optimierungen
enable_gpu_acceleration = true
enable_parallel_processing = true
frame_skip_threshold = 50.0

# Logging und Monitoring
enable_performance_logging = true
enable_difficult_cases_saving = true
log_directory = logs
difficult_cases_directory = difficult_cases
```

**`[colors]` - Farbkonfiguration für Bootsklassen**
```ini
muscle_boat = 0,255,255
passenger_boat = 255,165,0
motorboat_with_cabin = 0,255,0
motorboat_without_cabin = 0,200,0
sailboat_with_cabin = 255,0,0
sailboat_without_cabin = 200,0,0
licence = 0,0,255
```

**`[{Location}]` - Location-spezifische Stream-Konfiguration**
```ini
[Diemitz]
rtsp_url_1 = rtsp://admin:P@ssword3@192.168.21.20:554/h264Preview_03_main
line1_position_1 = 536
line2_position_1 = 464
orientation_1 = horizontal
rtsp_url_2 = rtsp://admin:P@ssword3@192.168.21.20:554/h264Preview_01_sub
line1_position_2 = 713
line2_position_2 = 788
orientation_2 = vertical
rtsp_url_3 = rtsp://admin:P@ssword3@192.168.21.20:554/h264Preview_02_main
line1_position_3 = 536
line2_position_3 = 464
orientation_3 = horizontal
```

---

#### **active_location.txt** - Location Selector

**Zweck:** Definiert die aktive Location für das System

**Format:** Ein-Zeilen-Datei mit Location-Namen
```
Diemitz
```

**Anforderungen:**
- Muss exakt einem Section-Namen in `config.ini` entsprechen
- UTF-8 Encoding für deutsche Umlaute
- Wird von allen Komponenten für Pfad-Generierung verwendet

**Verwendung:**
- Von `main.py` beim Start geladen
- Bestimmt aktive Stream-Konfiguration
- Verwendet für Ausgabe-Verzeichnisstruktur

---

#### **1.txt** - Commercial License Database

**Zweck:** Datenbank bekannter gewerblicher Kennzeichen für automatische Identifikation

**Format:** Ein Kennzeichen pro Zeile
```
AB-CD 123
XY-Z 456
BSR 24138
```

**Features:**
- UTF-8 Encoding für Sonderzeichen
- Automatische Ähnlichkeitserkennung bei OCR-Fehlern
- Verwendung für "identified_licence_number" Klassifikation
- Erweiterte Fuzzy-Matching-Algorithmen

---

### 🤖 AI Model Files

#### **best.pt** - YOLO Detection Model

**Zweck:** Trainiertes YOLOv11-Modell für Boot- und Kennzeichen-Erkennung

**Eigenschaften:**
- Dateigröße: ~119MB (via Git LFS)
- PyTorch-Format (.pt)
- Unterstützt verschiedene Input-Größen
- GPU/CPU-kompatibel mit automatischem Fallback

**Unterstützte Klassen:**
- muscle_boat
- passenger_boat  
- motorboat_with_cabin
- motorboat_without_cabin
- sailboat_with_cabin
- sailboat_without_cabin
- licence

**Konfiguration:**
- Confidence-Schwellenwert: 0.5 (Standard)
- Image-Size: 640px (Standard)
- Austauschbar gegen andere YOLO-Modelle

---

#### **botsort.yaml** - Object Tracking Configuration

**Zweck:** Konfiguration für BoTSORT Object-Tracking-Algorithmus

**Parameter:**
```yaml
track_high_thresh: 0.5      # Schwellenwert für erste Assoziation
track_low_thresh: 0.1       # Schwellenwert für zweite Assoziation  
track_buffer: 30            # Buffer für Track-Lebensdauer
match_thresh: 0.8           # Matching-Schwellenwert zwischen Frames
```

**Features:**
- Robustes Tracking auch bei Okklusion
- Automatische Track-ID-Verwaltung
- Optimiert für maritime Objekte

---

### 🚀 Deployment & Containerization

#### **Dockerfile** - Container Definition

**Zweck:** Docker-Container für GPU-beschleunigte YOLO/OCR-Verarbeitung

**Base Image:** `ultralytics/ultralytics` (CUDA-enabled)

**Features:**
- NVIDIA GPU-Unterstützung mit automatischem Fallback
- Automatische EasyOCR-Modell-Downloads beim Build
- Cross-platform Line-Ending-Handling (dos2unix)
- X11-Forwarding für GUI-Support
- Volume-Mounts für persistente Daten

**Build-Prozess:**
```bash
# Systemabhängigkeiten installieren
RUN apt-get update && apt-get install -y build-essential libgl1-mesa-glx dos2unix

# Python-Dependencies installieren
RUN pip install --no-cache-dir -r requirements.txt

# EasyOCR-Modelle vorab herunterladen
RUN python3 -c "import easyocr; reader = easyocr.Reader(['en', 'de'])"
```

**Runtime-Konfiguration:**
- DISPLAY-Variable für X11-Forwarding
- NVIDIA-Runtime für GPU-Zugriff
- Shared Memory: 32GB für Large Models

---

#### **docker-compose.yml** - Container Orchestration

**Zweck:** Docker Compose für einfache Container-Verwaltung und Deployment

**Services:**

**`yolo-tracking`:**
```yaml
services:
  yolo-tracking:
    build:
      context: .
      dockerfile: Dockerfile
    shm_size: 32g
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - /home/active_location.txt:/app/active_location.txt:ro
      - ./saved_data:/app/saved_data
      - /tmp/.X11-unix:/tmp/.X11-unix
    environment:
      - DISPLAY=${DISPLAY}
      - NVIDIA_VISIBLE_DEVICES=all
    restart: always
```

**Features:**
- GPU-Reservation und -Zugriff
- Volume-Mounts für Konfiguration und Daten
- X11-Forwarding für GUI-Applications
- Restart-Policy für Produktionsumgebung
- Shared Memory für Large Model Inference

**Verwendung:**
```bash
# Development
docker-compose up

# Production
docker-compose up -d
```

---

#### **start.sh** - Application Launcher & Process Manager

**Zweck:** Wrapper-Script für koordinierten Start/Stop aller Anwendungskomponenten

**Funktionalität:**
- Startet `main.py` und Azure-Upload-Loop parallel
- Signal-Handling für graceful shutdown (SIGTERM, SIGINT)
- Automatisches Cleanup aller Child-Prozesse
- Error-Recovery und Process-Monitoring

**Prozess-Management:**
```bash
# Startet main.py
start_main() {
  python main.py &
  MAIN_PID=$!
}

# Startet Azure Upload Loop (alle 2 Minuten)
start_azure_upload_loop() {
  while true; do
    python Azure_blob_upload.py
    sleep 120
  done &
  AZURE_PID=$!
}
```

**Cleanup-Logik:**
- Überwacht PIDs aller gestarteten Prozesse
- Beendet Prozesse in korrekter Reihenfolge
- Wartet auf saubere Beendigung vor Exit

**Verwendung:**
```bash
./start.sh                  # Startet komplettes System
# Ctrl+C für graceful shutdown
```

---

### 📋 Data Files & Dependencies

#### **requirements.txt** - Python Dependencies

**Zweck:** Definiert alle Python-Package-Abhängigkeiten mit Versionskompatibilität

**Core Dependencies:**
```txt
ultralytics                 # YOLOv11-Implementierung
easyocr                    # OCR-Engine für Texterkennnung
azure-storage-blob         # Cloud-Upload-Funktionalität
torch                      # Deep Learning Framework
opencv-python==4.7.0.72   # Computer Vision (fixe Version)
scikit-image>=0.19.0       # Erweiterte Bildverarbeitung
matplotlib>=3.5.0          # Charts und Visualisierung
pandas                     # CSV-Verarbeitung
numpy<2                    # Numerische Operationen (Version < 2)
```

**Optionale Performance-Dependencies:**
```txt
# GPU-Beschleunigung (uncomment für CUDA)
# cupy-cuda11x             # Für CUDA 11.x
# cupy-cuda12x             # Für CUDA 12.x
```

**Installation:**
```bash
pip install -r requirements.txt
```

---

#### **.gitattributes** - Git LFS Configuration

**Zweck:** Konfiguriert Git Large File Storage für das YOLO-Modell

```
*.pt filter=lfs diff=lfs merge=lfs -text
```

**Managed Files:**
- `best.pt` - YOLO-Modell (119MB)
- Automatisches LFS-Tracking für alle .pt-Dateien

---

#### **config.xlaunch** - X11 Server Configuration

**Zweck:** VcXsrv-Konfiguration für Windows X11-Server (Docker GUI-Support)

**XML-Konfiguration:**
```xml
<XLaunch WindowMode="MultiWindow" 
         ClientMode="NoClient" 
         Clipboard="True" 
         DisableAC="True"/>
```

**Verwendung:** 
- Für Docker-GUI-Support unter Windows
- Ermöglicht cv2.imshow() in Containern
- Alternative zu nativen Linux X11-Servern

---

## 🔄 System-Workflows

### **Haupt-Workflow:**
1. **Initialisierung:** `main.py` lädt Konfiguration und startet Worker-Prozesse
2. **Stream-Processing:** `tracking.py` verarbeitet RTSP-Streams mit YOLO+OCR
3. **Event-Detection:** Line-Crossing-Events werden erkannt und Screenshots erstellt
4. **Event-Aggregation:** `aggregator_events.py` matcht Events zwischen Kameras
5. **Data-Output:** CSV-Dateien und Event-Screenshots werden generiert
6. **Cloud-Sync:** `Azure_blob_upload.py` synchronisiert Daten zur Cloud
7. **Monitoring:** `ocr_monitor.py` überwacht System-Performance

### **OCR-Workflow:**
1. **Qualitätsprüfung:** Frame-Qualität wird vor OCR bewertet
2. **Preprocessing:** Adaptive Bildverbesserung je nach Bedingungen
3. **Multi-Method OCR:** 4 verschiedene OCR-Ansätze parallel
4. **Smart-Validation:** Intelligente Text-Typ-Erkennung und Korrektur
5. **Multi-Frame-Tracking:** Konsensus über mehrere Frames
6. **Performance-Logging:** Detaillierte Metriken für Optimierung

### **Event-Matching-Workflow:**
1. **Primary Detection:** Camera 2 erkennt Schiff (startet Event)
2. **Exit-Waiting:** System wartet auf Exit-Event von Camera 1/3
3. **Time-Bucket-Matching:** Events werden zeitlich gematcht (5-Min-Fenster)
4. **License-Selection:** Bestes OCR-Ergebnis wird ausgewählt
5. **CSV-Creation:** Event wird mit Pairing-Status in CSV geschrieben
6. **Timeout-Handling:** Nach 20 Min ohne Exit → CSV ohne Match

---

## 🛠️ Setup & Installation

### **Grundinstallation:**

1. **Location-Konfiguration:**
   ```bash
   echo "Diemitz" > /home/active_location.txt
   sudo chmod 644 /home/active_location.txt
   ```

2. **Stream-Konfiguration:**
   - Passe `config.ini` für RTSP-Streams an
   - Konfiguriere Line-Positionen pro Kamera
   - Setze Orientierung (`vertical`/`horizontal`)

3. **Lizenz-Datenbank:**
   - Fülle `1.txt` mit bekannten gewerblichen Kennzeichen
   - Ein Kennzeichen pro Zeile
   - UTF-8 Encoding verwenden

4. **Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### **Docker-Deployment:**

1. **X11-Setup (für GUI):**
   ```bash
   xhost +local:docker
   export DISPLAY=:0
   ```

2. **Container-Start:**
   ```bash
   docker-compose up -d
   ```

3. **Logs verfolgen:**
   ```bash
   docker-compose logs -f
   ```

### **Entwicklungsumgebung:**

```bash
# Direkt starten
python main.py

# Mit Azure-Upload
./start.sh

# OCR-Monitoring
python ocr_monitor.py --monitor

# Performance-Analyse
python ocr_monitor.py --report --charts
```

---

## 📊 Output-Struktur

### **Verzeichnis-Layout:**
```
saved_data/
├── {location}/
│   ├── csv/                           # CSV-Ausgabe
│   │   └── live_{location}_{timestamp}_aggregated.csv
│   └── events/                        # Event-Screenshots
│       └── {event_id}/
│           ├── {event_id}_camera1.jpg + .txt
│           ├── {event_id}_camera2.jpg + .txt
│           └── {event_id}_camera3.jpg + .txt
├── logs/
│   └── ocr_performance.jsonl          # OCR-Performance-Logs
└── difficult_cases/                   # Schwierige OCR-Fälle
    ├── {timestamp}_crop.jpg
    └── {timestamp}_analysis.json
```

### **CSV-Ausgabeformat:**
```csv
track_id,class_id,class_name,direction,entry_timestamp,exit_timestamp,location,extracted_text,identified_licence_number,ocr_confidence,confidence,pairing_status,ocr_method_used,frame_quality_score
123,0,boat,right,2025-01-15 14:30:15,2025-01-15 14:32:18,Diemitz,AB-CD 123,yes,0.95,0.87,paired_with_cam3,enhanced_img2,245.7
456,0,boat,left,2025-01-15 14:35:10,timeout,Diemitz,XY-Z 789,no,0.73,0.91,timeout_no_exit_match,consensus_3frames_score0.832,189.3
```

### **YOLO-Label-Format (.txt):**
```
class_id center_x center_y width height
0 0.512345 0.678901 0.123456 0.234567
6 0.345678 0.456789 0.067891 0.089012
```

---

## 📈 Performance-Optimierung

### **OCR-Optimierung:**
- **GPU-Beschleunigung:** `enable_gpu_acceleration = true` in config.ini
- **Qualitätsschwellen:** Erhöhe `min_frame_quality` für bessere Ergebnisse
- **Multi-Frame-OCR:** `max_frame_history = 5` für robuste Erkennung
- **Bildvorverarbeitung:** Aktiviere CLAHE und Denoising

### **System-Performance:**
- **CUDA-Installation:** Für GPU-beschleunigte Inference
- **Shared Memory:** Mindestens 32GB für Container
- **Stream-Optimierung:** UDP-Transport für RTSP-Streams
- **Parallelisierung:** Multi-Worker für große Kamera-Setups

### **Monitoring:**
- **Real-Time-Überwachung:** `python ocr_monitor.py --monitor`
- **Performance-Reports:** Regelmäßige Analyse mit `--report --charts`
- **Schwierige Fälle:** Überwache `difficult_cases/` für Optimierung
- **Log-Analyse:** Verwende `logs/ocr_performance.jsonl` für Trends

---

## 🔧 Troubleshooting

### **Häufige Probleme:**

**RTSP-Stream-Verbindung:**
```bash
# Test RTSP-Stream
ffplay rtsp://admin:password@192.168.x.x:554/stream

# Überprüfe Netzwerk-Konnektivität  
ping 192.168.x.x
```

**OCR-Performance:**
```bash
# Performance-Analyse
python ocr_monitor.py --report

# GPU-Status prüfen
nvidia-smi

# EasyOCR-Test
python -c "import easyocr; print('OCR OK')"
```

**Docker-GUI-Probleme:**
```bash
# X11-Berechtigung
xhost +local:docker

# Display-Variable prüfen
echo $DISPLAY

# Container-GUI-Test
docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ubuntu:20.04 xclock
```

**Speicherprobleme:**
```bash
# Shared Memory prüfen
df -h /dev/shm

# Container-Memory
docker stats

# System-Memory
free -h
```

---

## 🎯 Best Practices

### **Produktionsumgebung:**
- **Backup-Strategie:** Regelmäßige Backups von `saved_data/`
- **Log-Rotation:** Implementiere Log-Rotation für `logs/`
- **Health-Checks:** Nutze `camera_monitor.py` für Überwachung
- **Resource-Monitoring:** Überwache GPU/CPU/Memory-Usage
- **Security:** Externalisiere Credentials aus config.ini

### **Entwicklung:**
- **Git LFS:** Für große Modell-Dateien (.pt)
- **Testing:** Teste neue Locations vor Produktions-Deployment
- **OCR-Tuning:** Nutze `difficult_cases/` für Model-Verbesserung
- **Performance-Profiling:** Regelmäßige Analyse mit ocr_monitor.py

### **Skalierung:**
- **Multi-Location:** Verwende separate Container pro Location
- **Load-Balancing:** Verteile Kameras auf mehrere Systeme
- **Cloud-Storage:** Automatische Synchronisation für Redundanz
- **Monitoring-Dashboard:** Zentrale Überwachung aller Standorte

---

## 📞 Support & Wartung

### **Logs & Debugging:**
- **Haupt-Logs:** Console-Output von `main.py`
- **OCR-Performance:** `logs/ocr_performance.jsonl`
- **Schwierige Fälle:** `difficult_cases/` mit Analysen
- **Docker-Logs:** `docker-compose logs -f`

### **Wartungsaufgaben:**
- **Tägliche:** Prüfe `daily_counter` in Preview
- **Wöchentliche:** OCR-Performance-Report generieren
- **Monatliche:** `difficult_cases/` analysieren und Modell verbessern
- **Quartalsweise:** System-Update und Dependency-Updates

------------------------------------English Version--------------------------------
# YOLO Tracking Multi Image - Version 2.0

This project implements a multi-camera tracking and license plate recognition system based on YOLO with **Camera 2 as primary detector**. The system performs intelligent license matching between cameras and creates simultaneous screenshots from all cameras for each event.

## 🏗️ System Architecture

### **Detection Flow:**
1. **Primary Detection (Camera 2)**: All vessel detections start here
2. **License Matching**: Exit events from Camera 1/3 are matched with Camera 2 events
3. **Timeout Handling**: 20-minute timeout for missing exit events
4. **Event Documentation**: Simultaneous screenshots of all cameras with YOLO labels

### **Key Features:**
- ✅ Camera 2 Primary Detection with license plate recognition
- ✅ Intelligent license matching between cameras
- ✅ 20-minute timeout rule for incomplete passages
- ✅ Simultaneous 3-camera event screenshots
- ✅ Centralized CSV output with pairing status
- ✅ Commercial license identification from `1.txt`
- ✅ Enhanced OCR with multi-method approach and quality assessment
- ✅ Real-time performance monitoring and optimization

---

## 📁 Repository Structure & Complete Script Documentation

### 🎯 Core Application Files

#### **main.py** - Main Entry Point & Process Orchestration

**Purpose:** Central orchestrator for all multiprocessing workers in the system

**Functionality:**
- Loads active location from `active_location.txt` and stream configuration from `config.ini`
- Initializes shared memory objects for interprocess communication
- Starts and coordinates preview, tracking, and aggregator processes
- Manages graceful shutdown of all processes on SIGTERM/SIGINT

**Dependencies:**
- `config_utils.py` - Configuration management
- `image_utils.py` - Image processing
- `preview.py` - Live preview worker
- `tracking.py` - YOLO tracking worker
- `aggregator_events.py` - Event aggregation

**Input/Output:**
- **Input:** `active_location.txt`, `config.ini`, `1.txt`
- **Output:** Orchestrated processes, console logs

**Configuration:**
- Location automatically from `active_location.txt`
- Stream count automatically based on `config.ini`
- Timeout for event aggregation: 20 minutes (default)

**Usage:**
```bash
python main.py
```

---

#### **tracking.py** - Core Tracking & OCR Engine

**Purpose:** Main tracking worker with YOLO object detection and enhanced OCR functions

**Functionality:**
- YOLO model initialization with automatic GPU/CPU fallback
- Real-time video stream processing with object tracking
- Multi-frame OCR tracking for consistent license plate recognition
- Line-crossing detection with configurable lines
- Event screenshot creation for all cameras simultaneously
- Global color management for consistent visualization

**Dependencies:**
- `ultralytics` - YOLO model
- `easyocr` - OCR engine
- `torch` - Deep learning framework
- `config_utils.py` - Color configuration
- `image_utils.py` - Enhanced OCR functions

**Input/Output:**
- **Input:** RTSP stream, YOLO model (`best.pt`), tracking config (`botsort.yaml`)
- **Output:** Event queue, preview frames, event screenshots

**Parameters:**
- `cam_idx`: Camera index (1-3)
- `stream_url`: RTSP URL of video stream
- `location`: Location name for file paths
- `line1/line2`: Control line positions
- `orientation`: "vertical" or "horizontal"
- `commercial_licenses`: Set of known commercial licenses

**OCR Features:**
- Multi-method OCR approach (Standard, Detailed, Paragraph, Enhanced)
- Adaptive image preprocessing based on time of day
- Image quality assessment before OCR processing
- SmartOCRValidator for intelligent text validation
- Multi-frame consensus for robust license recognition

**Configuration:**
- YOLO model: `best.pt` (exchangeable)
- OCR languages: English/German (expandable)
- Confidence thresholds via `config.ini`
- Image quality thresholds via `config.ini`
- Line positions via `config.ini`

---

#### **aggregator_events.py** - Event Processing & CSV Generation

**Purpose:** Central event aggregator with Camera 2 as primary detection

**Functionality:**
- Waits for events from all cameras and implements matching logic
- Camera 2 functions as primary detector - all events start here
- Exit events from Camera 1/3 are matched with Camera 2 events
- Timeout management for incomplete passages (20 minutes)
- CSV output with detailed pairing status
- Automatic time bucket generation for event matching

**Dependencies:**
- `pandas` - CSV processing
- `image_utils.py` - Filename sanitization

**Input/Output:**
- **Input:** Event queue from tracking workers
- **Output:** CSV files in `saved_data/{location}/csv/`

**Parameters:**
- `event_queue`: Multiprocessing queue with events
- `location`: Location name for output path
- `stop_event`: Signal for process termination
- `flush_interval`: Seconds between CSV write operations (default: 120s)
- `timeout_minutes`: Minutes for event timeout (default: 20)

**CSV Output Format:**
```csv
track_id,class_id,class_name,direction,entry_timestamp,exit_timestamp,location,extracted_text,identified_licence_number,ocr_confidence,confidence,pairing_status,ocr_method_used,frame_quality_score
```

**Matching Logic:**
- Time bucket-based matching (5-minute windows)
- Class ID and direction matching
- Time-based tolerance for asynchronous events
- Automatic timeout handling for incomplete passages

---

#### **preview.py** - Live Preview Display

**Purpose:** Shows all camera feeds side by side in a single window

**Functionality:**
- Side-by-side display of all available cameras
- Real-time FPS display per camera
- Daily counter for detected vessels
- Color-coded title bar with system status

**Dependencies:**
- `cv2` - OpenCV for image display
- `numpy` - Array processing

**Input/Output:**
- **Input:** JPEG frame queues from tracking workers
- **Output:** Live display window

**Parameters:**
- `queues`: List of multiprocessing queues with JPEG frames
- `daily_counter`: Shared counter for daily vessel count

**Layout Configuration:**
- Window width: 3 × 640px + 2 × 20px spacer = 1960px
- Window height: 30px title + 30px info + 360px camera = 420px
- Spacer width between cameras: 20px
- Title bar: RGB(239,239,239) with black text

**Controls:**
- Key 'q': Exit preview

---

### 🛠️ Utility Modules

#### **image_utils.py** - Advanced Image Processing & OCR Engine

**Purpose:** Advanced image processing, OCR optimization, and intelligent text validation

**Core Classes:**

**`SmartOCRValidator`** - Intelligent OCR Validation
- Automatic text type detection (license plates, boat names, unknown)
- Format-specific corrections and validation
- Similarity search with known licenses
- Comprehensive score calculation for OCR quality

**`MultiFrameOCRTracker`** - Multi-Frame OCR Tracking
- Cross-frame consensus building
- Automatic cleanup of old tracks
- Weighted score calculation for best results

**Main Functions:**

**`perform_ocr_on_license_enhanced()`** - Enhanced OCR Pipeline
- Multi-method OCR approach (4 different methods)
- Adaptive image preprocessing based on time of day
- Image quality assessment before OCR processing
- Extended error handling and logging

**`enhance_image_preprocessing()`** - Advanced Image Preprocessing
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- TV-Chambolle Denoising
- Adaptive Thresholding
- Morphological Operations
- Edge Enhancement
- Multi-Scale Processing

**`calculate_frame_quality()`** - Image Quality Assessment
- Sharpness measurement via Laplacian variance
- Contrast calculation
- Brightness analysis
- Combined quality score

**Dependencies:**
- `cv2` - OpenCV for image processing
- `numpy` - Numerical operations
- `scikit-image` - Advanced image processing
- `difflib` - String similarity comparison

**Configuration via `config.ini`:**
```ini
[ocr_settings]
enable_clahe = true
enable_denoising = true
scale_factor = 2.0
min_confidence = 0.3
max_frame_history = 5
min_frame_quality = 100.0
enable_gpu_acceleration = true
```

**Performance Features:**
- Difficult cases automatically saved to `difficult_cases/`
- Detailed performance logging in `logs/ocr_performance.jsonl`
- Real-time OCR statistics and monitoring

---

#### **config_utils.py** - Configuration Management & Validation

**Purpose:** Central management of all configuration files with validation and global color management

**Main Functions:**

**`load_active_location()`** - Location Management
- Loads active location from `active_location.txt`
- Validates existence in `config.ini`
- UTF-8 support for German umlauts

**`load_config()`** - Stream Configuration
- Loads RTSP URLs and line configuration per location
- Validates orientation (vertical/horizontal)
- Automatic stream count detection

**`load_ocr_config()`** - OCR Settings
- Loads all OCR parameters from `config.ini`
- Default fallback values
- Automatic directory creation

**`GlobalColorMapper`** - Central Color Management
- Consistent color assignment across all streams
- Configurable colors per vessel class
- Automatic fallback colors
- Performance overview and recommendations

**Dependencies:**
- `configparser` - INI file processing
- `matplotlib` - Performance charts (optional)

**Supported Locations:**
- Automatic detection from `config.ini`
- UTF-8 support: Fürstenberg, Diemitz, Bredereiche
- Expandable through new `[location]` sections

**Validation Functions:**
- `validate_location_exists()` - Checks location in config.ini
- `validate_color_configuration()` - Validates color configuration
- `create_new_location_template()` - Generates templates for new locations

---

### 📊 Monitoring & Maintenance

#### **ocr_monitor.py** - OCR Performance Analysis & Monitoring

**Purpose:** Detailed monitoring and analysis of OCR performance with real-time monitoring

**Main Class: `OCRPerformanceMonitor`**

**Functionality:**
- Real-time OCR performance tracking
- Historical data analysis with time window filters
- Performance charts and detailed reports
- Method comparisons and optimization recommendations
- Automatic problem detection and alerting

**Core Features:**

**Performance Analysis:**
- Success rates by time windows (1h, 24h, week, total)
- Method comparison with confidence and processing time
- Text length analysis and format recognition
- Problematic cases with low confidence values

**Chart Generation:**
- Success rate over time (hourly based)
- Method comparison with color-coded bars
- Confidence distribution histogram
- Output as high-resolution PNG files

**Real-Time Monitoring:**
- Live updates every 10 seconds
- Console display with current statistics
- Monitoring of last 100 OCR calls

**Dependencies:**
- `matplotlib` - Chart generation
- `pandas` - Data analysis
- `json` - Log file processing

**Usage:**
```bash
# Generate performance report
python ocr_monitor.py --report

# Create performance charts
python ocr_monitor.py --charts

# Start real-time monitoring
python ocr_monitor.py --monitor

# Quick status (default)
python ocr_monitor.py
```

**Output Files:**
- `ocr_report.txt` - Detailed performance report
- `charts/success_rate_over_time.png` - Success rate timeline
- `charts/method_comparison.png` - Method comparison
- `charts/confidence_distribution.png` - Confidence distribution

**Recommendation System:**
- Automatic warnings for success rate < 70%
- GPU acceleration recommendations for slow processing
- Image quality optimization for low confidence
- Best practice recommendations based on data analysis

---

#### **Azure_blob_upload.py** - Cloud Data Synchronization

**Purpose:** Automatic synchronization of local data with Azure Blob Storage

**Functionality:**
- Timestamp-based synchronization avoids duplicates
- Upload of CSV files and event screenshots
- Location-aware directory structure
- Robust error handling and retry logic

**Upload Targets:**
- **CSV Files:** `saved_data/{location}/csv/` → `CSV_output/Yolo_Multi/`
- **Event Screenshots:** `saved_data/{location}/events/` → `model-inputs/Yolo-Multi/`

**Dependencies:**
- `azure-storage-blob` - Azure SDK
- `image_utils.py` - Filename sanitization

**Sync Logic:**
- Compares local file timestamps with blob timestamps
- Uploads only newer files
- Maintains directory structure in cloud
- Separate handling for CSV files and event directories

**Configuration:**
```python
AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;..."
CONTAINER_NAME = "wsv3"
```

**Usage:**
```bash
python Azure_blob_upload.py
```

**Event Upload:**
- Complete upload of entire event directories
- Timestamp comparison at directory level
- Upload of all files (.jpg + .txt) per event

---

### ⚙️ Configuration Files

#### **config.ini** - Central System Configuration

**Purpose:** Main configuration file for all system settings

**Sections:**

**`[email]` - Email Notifications**
```ini
smtp_server = smtp.gmail.com
smtp_port = 587
email_address = wsvschiffszaehlung@gmail.com
email_password = WSV@1234
recipients = email1@domain.com,email2@domain.com
```

**`[ocr_settings]` - OCR Optimization**
```ini
# Image preprocessing
enable_clahe = true
enable_denoising = true
enable_sharpening = true
scale_factor = 2.0

# OCR parameters
min_confidence = 0.3
max_ocr_attempts = 3
enable_multi_frame = true
max_frame_history = 5

# Quality thresholds
min_frame_quality = 100.0
min_text_length = 2
max_text_length = 20

# Performance optimizations
enable_gpu_acceleration = true
enable_parallel_processing = true
frame_skip_threshold = 50.0

# Logging and monitoring
enable_performance_logging = true
enable_difficult_cases_saving = true
log_directory = logs
difficult_cases_directory = difficult_cases
```

**`[colors]` - Color Configuration for Vessel Classes**
```ini
muscle_boat = 0,255,255
passenger_boat = 255,165,0
motorboat_with_cabin = 0,255,0
motorboat_without_cabin = 0,200,0
sailboat_with_cabin = 255,0,0
sailboat_without_cabin = 200,0,0
licence = 0,0,255
```

**`[{Location}]` - Location-specific Stream Configuration**
```ini
[Diemitz]
rtsp_url_1 = rtsp://admin:P@ssword3@192.168.21.20:554/h264Preview_03_main
line1_position_1 = 536
line2_position_1 = 464
orientation_1 = horizontal
rtsp_url_2 = rtsp://admin:P@ssword3@192.168.21.20:554/h264Preview_01_sub
line1_position_2 = 713
line2_position_2 = 788
orientation_2 = vertical
rtsp_url_3 = rtsp://admin:P@ssword3@192.168.21.20:554/h264Preview_02_main
line1_position_3 = 536
line2_position_3 = 464
orientation_3 = horizontal
```

---

#### **active_location.txt** - Location Selector

**Purpose:** Defines the active location for the system

**Format:** Single-line file with location name
```
Diemitz
```

**Requirements:**
- Must exactly match a section name in `config.ini`
- UTF-8 encoding for German umlauts
- Used by all components for path generation

**Usage:**
- Loaded by `main.py` at startup
- Determines active stream configuration
- Used for output directory structure

---

#### **1.txt** - Commercial License Database

**Purpose:** Database of known commercial licenses for automatic identification

**Format:** One license per line
```
AB-CD 123
XY-Z 456
BSR 24138
```

**Features:**
- UTF-8 encoding for special characters
- Automatic similarity detection for OCR errors
- Used for "identified_licence_number" classification
- Enhanced fuzzy matching algorithms

---

### 🤖 AI Model Files

#### **best.pt** - YOLO Detection Model

**Purpose:** Trained YOLOv11 model for vessel and license plate detection

**Properties:**
- File size: ~119MB (via Git LFS)
- PyTorch format (.pt)
- Supports various input sizes
- GPU/CPU compatible with automatic fallback

**Supported Classes:**
- muscle_boat
- passenger_boat  
- motorboat_with_cabin
- motorboat_without_cabin
- sailboat_with_cabin
- sailboat_without_cabin
- licence

**Configuration:**
- Confidence threshold: 0.5 (default)
- Image size: 640px (default)
- Exchangeable with other YOLO models

---

#### **botsort.yaml** - Object Tracking Configuration

**Purpose:** Configuration for BoTSORT object tracking algorithm

**Parameters:**
```yaml
track_high_thresh: 0.5      # Threshold for first association
track_low_thresh: 0.1       # Threshold for second association  
track_buffer: 30            # Buffer for track lifetime
match_thresh: 0.8           # Matching threshold between frames
```

**Features:**
- Robust tracking even with occlusion
- Automatic track ID management
- Optimized for maritime objects

---

### 🚀 Deployment & Containerization

#### **Dockerfile** - Container Definition

**Purpose:** Docker container for GPU-accelerated YOLO/OCR processing

**Base Image:** `ultralytics/ultralytics` (CUDA-enabled)

**Features:**
- NVIDIA GPU support with automatic fallback
- Automatic EasyOCR model downloads during build
- Cross-platform line ending handling (dos2unix)
- X11 forwarding for GUI support
- Volume mounts for persistent data

**Build Process:**
```bash
# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libgl1-mesa-glx dos2unix

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models
RUN python3 -c "import easyocr; reader = easyocr.Reader(['en', 'de'])"
```

**Runtime Configuration:**
- DISPLAY variable for X11 forwarding
- NVIDIA runtime for GPU access
- Shared memory: 32GB for large models

---

#### **docker-compose.yml** - Container Orchestration

**Purpose:** Docker Compose for easy container management and deployment

**Services:**

**`yolo-tracking`:**
```yaml
services:
  yolo-tracking:
    build:
      context: .
      dockerfile: Dockerfile
    shm_size: 32g
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - /home/active_location.txt:/app/active_location.txt:ro
      - ./saved_data:/app/saved_data
      - /tmp/.X11-unix:/tmp/.X11-unix
    environment:
      - DISPLAY=${DISPLAY}
      - NVIDIA_VISIBLE_DEVICES=all
    restart: always
```

**Features:**
- GPU reservation and access
- Volume mounts for configuration and data
- X11 forwarding for GUI applications
- Restart policy for production environment
- Shared memory for large model inference

**Usage:**
```bash
# Development
docker-compose up

# Production
docker-compose up -d
```

---

#### **start.sh** - Application Launcher & Process Manager

**Purpose:** Wrapper script for coordinated start/stop of all application components

**Functionality:**
- Starts `main.py` and Azure upload loop in parallel
- Signal handling for graceful shutdown (SIGTERM, SIGINT)
- Automatic cleanup of all child processes
- Error recovery and process monitoring

**Process Management:**
```bash
# Start main.py
start_main() {
  python main.py &
  MAIN_PID=$!
}

# Start Azure upload loop (every 2 minutes)
start_azure_upload_loop() {
  while true; do
    python Azure_blob_upload.py
    sleep 120
  done &
  AZURE_PID=$!
}
```

**Cleanup Logic:**
- Monitors PIDs of all started processes
- Terminates processes in correct order
- Waits for clean termination before exit

**Usage:**
```bash
./start.sh                  # Start complete system
# Ctrl+C for graceful shutdown
```

---

### 📋 Data Files & Dependencies

#### **requirements.txt** - Python Dependencies

**Purpose:** Defines all Python package dependencies with version compatibility

**Core Dependencies:**
```txt
ultralytics                 # YOLOv11 implementation
easyocr                    # OCR engine for text recognition
azure-storage-blob         # Cloud upload functionality
torch                      # Deep learning framework
opencv-python==4.7.0.72   # Computer vision (fixed version)
scikit-image>=0.19.0       # Advanced image processing
matplotlib>=3.5.0          # Charts and visualization
pandas                     # CSV processing
numpy<2                    # Numerical operations (version < 2)
```

**Optional Performance Dependencies:**
```txt
# GPU acceleration (uncomment for CUDA)
# cupy-cuda11x             # For CUDA 11.x
# cupy-cuda12x             # For CUDA 12.x
```

**Installation:**
```bash
pip install -r requirements.txt
```

---

#### **.gitattributes** - Git LFS Configuration

**Purpose:** Configures Git Large File Storage for the YOLO model

```
*.pt filter=lfs diff=lfs merge=lfs -text
```

**Managed Files:**
- `best.pt` - YOLO model (119MB)
- Automatic LFS tracking for all .pt files

---

#### **config.xlaunch** - X11 Server Configuration

**Purpose:** VcXsrv configuration for Windows X11 server (Docker GUI support)

**XML Configuration:**
```xml
<XLaunch WindowMode="MultiWindow" 
         ClientMode="NoClient" 
         Clipboard="True" 
         DisableAC="True"/>
```

**Usage:** 
- For Docker GUI support on Windows
- Enables cv2.imshow() in containers
- Alternative to native Linux X11 servers

---

## 🔄 System Workflows

### **Main Workflow:**
1. **Initialization:** `main.py` loads configuration and starts worker processes
2. **Stream Processing:** `tracking.py` processes RTSP streams with YOLO+OCR
3. **Event Detection:** Line-crossing events are detected and screenshots created
4. **Event Aggregation:** `aggregator_events.py` matches events between cameras
5. **Data Output:** CSV files and event screenshots are generated
6. **Cloud Sync:** `Azure_blob_upload.py` synchronizes data to cloud
7. **Monitoring:** `ocr_monitor.py` monitors system performance

### **OCR Workflow:**
1. **Quality Check:** Frame quality is assessed before OCR
2. **Preprocessing:** Adaptive image enhancement based on conditions
3. **Multi-Method OCR:** 4 different OCR approaches in parallel
4. **Smart Validation:** Intelligent text type detection and correction
5. **Multi-Frame Tracking:** Consensus over multiple frames
6. **Performance Logging:** Detailed metrics for optimization

### **Event Matching Workflow:**
1. **Primary Detection:** Camera 2 detects vessel (starts event)
2. **Exit Waiting:** System waits for exit event from Camera 1/3
3. **Time Bucket Matching:** Events are temporally matched (5-min windows)
4. **License Selection:** Best OCR result is selected
5. **CSV Creation:** Event is written to CSV with pairing status
6. **Timeout Handling:** After 20 min without exit → CSV without match

---

## 🛠️ Setup & Installation

### **Basic Installation:**

1. **Location Configuration:**
   ```bash
   echo "Diemitz" > /home/active_location.txt
   sudo chmod 644 /home/active_location.txt
   ```

2. **Stream Configuration:**
   - Adapt `config.ini` for RTSP streams
   - Configure line positions per camera
   - Set orientation (`vertical`/`horizontal`)

3. **License Database:**
   - Fill `1.txt` with known commercial licenses
   - One license per line
   - Use UTF-8 encoding

4. **Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### **Docker Deployment:**

1. **X11 Setup (for GUI):**
   ```bash
   xhost +local:docker
   export DISPLAY=:0
   ```

2. **Container Start:**
   ```bash
   docker-compose up -d
   ```

3. **Follow Logs:**
   ```bash
   docker-compose logs -f
   ```

### **Development Environment:**

```bash
# Direct start
python main.py

# With Azure upload
./start.sh

# OCR monitoring
python ocr_monitor.py --monitor

# Performance analysis
python ocr_monitor.py --report --charts
```

---

## 📊 Output Structure

### **Directory Layout:**
```
saved_data/
├── {location}/
│   ├── csv/                           # CSV output
│   │   └── live_{location}_{timestamp}_aggregated.csv
│   └── events/                        # Event screenshots
│       └── {event_id}/
│           ├── {event_id}_camera1.jpg + .txt
│           ├── {event_id}_camera2.jpg + .txt
│           └── {event_id}_camera3.jpg + .txt
├── logs/
│   └── ocr_performance.jsonl          # OCR performance logs
└── difficult_cases/                   # Difficult OCR cases
    ├── {timestamp}_crop.jpg
    └── {timestamp}_analysis.json
```

### **CSV Output Format:**
```csv
track_id,class_id,class_name,direction,entry_timestamp,exit_timestamp,location,extracted_text,identified_licence_number,ocr_confidence,confidence,pairing_status,ocr_method_used,frame_quality_score
123,0,boat,right,2025-01-15 14:30:15,2025-01-15 14:32:18,Diemitz,AB-CD 123,yes,0.95,0.87,paired_with_cam3,enhanced_img2,245.7
456,0,boat,left,2025-01-15 14:35:10,timeout,Diemitz,XY-Z 789,no,0.73,0.91,timeout_no_exit_match,consensus_3frames_score0.832,189.3
```

### **YOLO Label Format (.txt):**
```
class_id center_x center_y width height
0 0.512345 0.678901 0.123456 0.234567
6 0.345678 0.456789 0.067891 0.089012
```

---

## 📈 Performance Optimization

### **OCR Optimization:**
- **GPU Acceleration:** `enable_gpu_acceleration = true` in config.ini
- **Quality Thresholds:** Increase `min_frame_quality` for better results
- **Multi-Frame OCR:** `max_frame_history = 5` for robust recognition
- **Image Preprocessing:** Enable CLAHE and denoising

### **System Performance:**
- **CUDA Installation:** For GPU-accelerated inference
- **Shared Memory:** Minimum 32GB for containers
- **Stream Optimization:** UDP transport for RTSP streams
- **Parallelization:** Multi-worker for large camera setups

### **Monitoring:**
- **Real-Time Monitoring:** `python ocr_monitor.py --monitor`
- **Performance Reports:** Regular analysis with `--report --charts`
- **Difficult Cases:** Monitor `difficult_cases/` for optimization
- **Log Analysis:** Use `logs/ocr_performance.jsonl` for trends

---

## 🔧 Troubleshooting

### **Common Issues:**

**RTSP Stream Connection:**
```bash
# Test RTSP stream
ffplay rtsp://admin:password@192.168.x.x:554/stream

# Check network connectivity  
ping 192.168.x.x
```

**OCR Performance:**
```bash
# Performance analysis
python ocr_monitor.py --report

# Check GPU status
nvidia-smi

# EasyOCR test
python -c "import easyocr; print('OCR OK')"
```

**Docker GUI Issues:**
```bash
# X11 permission
xhost +local:docker

# Check display variable
echo $DISPLAY

# Container GUI test
docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ubuntu:20.04 xclock
```

**Memory Issues:**
```bash
# Check shared memory
df -h /dev/shm

# Container memory
docker stats

# System memory
free -h
```

---

## 🎯 Best Practices

### **Production Environment:**
- **Backup Strategy:** Regular backups of `saved_data/`
- **Log Rotation:** Implement log rotation for `logs/`
- **Health Checks:** Use `camera_monitor.py` for monitoring
- **Resource Monitoring:** Monitor GPU/CPU/Memory usage
- **Security:** Externalize credentials from config.ini

### **Development:**
- **Git LFS:** For large model files (.pt)
- **Testing:** Test new locations before production deployment
- **OCR Tuning:** Use `difficult_cases/` for model improvement
- **Performance Profiling:** Regular analysis with ocr_monitor.py

### **Scaling:**
- **Multi-Location:** Use separate containers per location
- **Load Balancing:** Distribute cameras across multiple systems
- **Cloud Storage:** Automatic synchronization for redundancy
- **Monitoring Dashboard:** Central monitoring of all sites

---

## 📞 Support & Maintenance

### **Logs & Debugging:**
- **Main Logs:** Console output from `main.py`
- **OCR Performance:** `logs/ocr_performance.jsonl`
- **Difficult Cases:** `difficult_cases/` with analysis
- **Docker Logs:** `docker-compose logs -f`

### **Maintenance Tasks:**
- **Daily:** Check `daily_counter` in preview
- **Weekly:** Generate OCR performance report
- **Monthly:** Analyze `difficult_cases/` and improve model
- **Quarterly:** System update and dependency updates



---

*Last Updated: 2025-06-18*
*Version: 2.0 - Multi-Camera Event Matching with Enhanced OCR*



