#!/bin/bash
set -e

# PIDs für die verschiedenen Prozesse
MAIN_PID=""
AZURE_PID=""

# Funktion zum Starten von main.py
start_main() {
  echo "Starte main.py..."
  python main.py &
  MAIN_PID=$!
}

# Funktion zum Starten des Azure Upload Loops
start_azure_upload_loop() {
  echo "Starte Azure Upload Loop (alle 2 Minuten)..."
  {
    while true; do
      echo "$(date): Führe Azure Blob Upload aus..."
      python Azure_blob_upload.py
      echo "$(date): Azure Upload abgeschlossen. Warte 2 Minuten..."
      sleep 120  # 2 Minuten = 120 Sekunden
    done
  } &
  AZURE_PID=$!
}

# Funktion zur sauberen Beendigung aller Prozesse
cleanup() {
  echo
  echo "Beende alle Prozesse..."

  # Beende main.py
  if [ -n "$MAIN_PID" ]; then
    if kill -0 "$MAIN_PID" 2>/dev/null; then
      echo "Beende main.py (PID $MAIN_PID)..."
      kill "$MAIN_PID" 2>/dev/null || true
      echo "main.py wurde beendet."
    else
      echo "PID $MAIN_PID existiert nicht mehr, überspringe."
    fi
  fi

  # Beende Azure Upload Loop
  if [ -n "$AZURE_PID" ]; then
    if kill -0 "$AZURE_PID" 2>/dev/null; then
      echo "Beende Azure Upload Loop (PID $AZURE_PID)..."
      kill "$AZURE_PID" 2>/dev/null || true
      echo "Azure Upload Loop wurde beendet."
    else
      echo "PID $AZURE_PID existiert nicht mehr, überspringe."
    fi
  fi

  wait
  exit 0
}

# Fang SIGTERM und SIGINT ab, um cleanup auszuführen
trap cleanup SIGTERM SIGINT

# Starte beide Prozesse
start_main
start_azure_upload_loop

echo "Beide Prozesse gestartet:"
echo "  - main.py (PID: $MAIN_PID)"
echo "  - Azure Upload Loop (PID: $AZURE_PID)"
echo "Drücke Ctrl+C zum Beenden..."

# Warte, bis einer der Prozesse endet oder ein SIGTERM/SIGINT reinkommt
wait
