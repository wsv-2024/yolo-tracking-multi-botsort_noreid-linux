import re
import cv2
import numpy as np
import unicodedata
import os
import configparser


def get_available_locations(config_path: str = "config.ini") -> list:
    """Automatisch alle verfügbaren Locations aus der config.ini laden."""
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding='utf-8')
        
        # Alle Sections außer 'email' und 'ocr_settings' sind Locations
        excluded_sections = {'email', 'ocr_settings', 'colors', 'DEFAULT'}
        locations = [section for section in cfg.sections() 
                    if section not in excluded_sections]
        
        print(f"Verfügbare Locations aus config.ini: {locations}")
        return locations
    except Exception as e:
        print(f"WARNUNG: Konnte config.ini nicht lesen: {e}")
        # Fallback auf bekannte Locations
        return ['Fürstenberg', 'Diemitz', 'Bredereiche']


def get_global_class_colors(config_path: str = "config.ini") -> dict:
    """
    Lädt globale Farbzuweisung für die spezifischen Bootsklassen.
    Stellt sicher, dass alle Streams die gleichen Farben verwenden.
    
    Returns:
        GlobalColorMapper: Objekt für konsistente Farbzuweisung
    """
    # Lade benutzerdefinierte Farben aus config.ini
    configured_colors = _load_colors_from_config(config_path)
    
    # Erstelle Color Mapper mit Fallback-Logik
    color_mapper = GlobalColorMapper(configured_colors)
    
    print(f"Zentrale Farbverwaltung initialisiert mit {len(configured_colors)} vordefinierten Farben")
    if configured_colors:
        print("Konfigurierte Farben:")
        for class_name, color in configured_colors.items():
            print(f"  {class_name}: BGR{color}")
    
    return color_mapper


def _load_colors_from_config(config_path: str) -> dict:
    """
    Hilfsfunktion: Lädt Farben aus der [colors] Sektion der config.ini.
    
    Returns:
        dict: Mapping von Klassennamen zu BGR-Farbwerten
    """
    class_colors = {}
    
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding='utf-8')
        
        if 'colors' in cfg:
            colors_section = cfg['colors']
            print("Lade benutzerdefinierte Farben aus config.ini...")
            
            for class_name in colors_section:
                color_str = colors_section.get(class_name)
                try:
                    # Format: "B,G,R" oder "(B,G,R)"
                    color_str = color_str.strip('()')
                    b, g, r = map(int, color_str.split(','))
                    
                    # Validiere Farbwerte
                    if 0 <= b <= 255 and 0 <= g <= 255 and 0 <= r <= 255:
                        class_colors[class_name] = (b, g, r)
                        print(f"  {class_name}: BGR({b},{g},{r})")
                    else:
                        print(f"WARNUNG: Ungültige Farbwerte für {class_name}: ({b},{g},{r})")
                        
                except ValueError:
                    print(f"WARNUNG: Ungültiges Farbformat für {class_name}: {color_str}")
        else:
            print("Keine [colors] Sektion in config.ini gefunden - verwende automatische Farbzuweisung")
        
    except Exception as e:
        print(f"WARNUNG: Konnte Farbkonfiguration nicht laden: {e}")
    
    return class_colors


class GlobalColorMapper:
    """
    Zentrale Klasse für konsistente Farbzuweisung über alle Streams.
    Speziell angepasst für die definierten Bootsklassen.
    """
    
    # Definierte Bootsklassen mit optimalen Standard-Farben
    BOAT_CLASSES = {
        'muscle_boat': (0, 255, 255),              # Gelb - Auffällig für Sportboote
        'passenger_boat': (255, 165, 0),           # Orange - Gut sichtbar für Passagiere
        'motorboat_with_cabin': (0, 255, 0),       # Grün - Standard Motorboot
        'motorboat_without_cabin': (0, 200, 0),    # Dunkelgrün - Offenes Motorboot
        'sailboat_with_cabin': (255, 0, 0),        # Blau - Klassisch für Segelboote
        'sailboat_without_cabin': (200, 0, 0),     # Dunkelblau - Kleinere Segelboote
        'licence': (0, 0, 255),                    # Rot - Sehr wichtig für Kennzeichen
    }
    
    def __init__(self, predefined_colors: dict):
        self._predefined = predefined_colors.copy()
        self._cache = {}
        
        print(f"GlobalColorMapper initialisiert für Bootsklassen:")
        print(f"  - Konfigurierte Farben: {len(self._predefined)}")
        print(f"  - Unterstützte Klassen: {len(self.BOAT_CLASSES)}")
        
        # Zeige welche Klassen konfiguriert sind vs. Standard verwenden
        for class_name in self.BOAT_CLASSES.keys():
            if class_name in self._predefined:
                print(f"  ✅ {class_name}: Konfiguriert")
            else:
                print(f"  🔧 {class_name}: Standard-Farbe")
    
    def get_color(self, class_name: str) -> tuple:
        """
        Gibt die BGR-Farbe für eine Bootsklasse zurück.
        Garantiert konsistente Farben über alle Streams.
        """
        # 1. Priorität: Konfigurierte Farben aus config.ini
        if class_name in self._predefined:
            return self._predefined[class_name]
        
        # 2. Priorität: Cache (bereits zugewiesene Farben)
        if class_name in self._cache:
            return self._cache[class_name]
        
        # 3. Priorität: Standard-Farben für bekannte Bootsklassen
        if class_name in self.BOAT_CLASSES:
            color = self.BOAT_CLASSES[class_name]
            self._cache[class_name] = color
            print(f"Standard-Farbe verwendet: {class_name} -> BGR{color}")
            return color
        
        # 4. Fallback für unbekannte Klassen: Grau
        fallback_color = (128, 128, 128)  # Grau
        self._cache[class_name] = fallback_color
        print(f"WARNUNG: Unbekannte Klasse '{class_name}' -> BGR{fallback_color} (Grau)")
        return fallback_color
    
    def get_all_known_colors(self) -> dict:
        """Gibt alle bekannten Farbzuweisungen zurück."""
        result = self._predefined.copy()
        result.update(self._cache)
        return result
    
    def get_config_coverage(self) -> dict:
        """Gibt Statistiken über die Farbkonfiguration zurück."""
        configured_boat_classes = [c for c in self.BOAT_CLASSES.keys() if c in self._predefined]
        total_boat_classes = len(self.BOAT_CLASSES)
        configured_count = len(configured_boat_classes)
        
        return {
            'total_boat_classes': total_boat_classes,
            'configured_classes': configured_count,
            'unconfigured_classes': total_boat_classes - configured_count,
            'coverage_percentage': (configured_count / total_boat_classes * 100),
            'configured_list': configured_boat_classes,
            'unconfigured_list': [c for c in self.BOAT_CLASSES.keys() if c not in self._predefined]
        }
    
    def get_recommended_config(self) -> str:
        """Erstellt empfohlene Konfiguration für nicht-konfigurierte Klassen."""
        unconfigured = [c for c in self.BOAT_CLASSES.keys() if c not in self._predefined]
        
        if not unconfigured:
            return "Alle Bootsklassen sind bereits konfiguriert! ✅"
        
        config_lines = ["# Empfohlene Farbkonfiguration für fehlende Klassen:"]
        for class_name in unconfigured:
            color = self.BOAT_CLASSES[class_name]
            config_lines.append(f"{class_name} = {color[0]},{color[1]},{color[2]}")
        
        return "\n".join(config_lines)


def create_color_config_template(config_path: str = "config.ini"):
    """Erstellt eine Vorlage für Farbkonfiguration der spezifischen Bootsklassen."""
    template = """
# Farbkonfiguration für Bootsklassen
# Format: klassenname = B,G,R (BGR-Werte von 0-255)

[colors]
# Spezifische Bootsklassen mit optimierten Farben
muscle_boat = 0,255,255
passenger_boat = 255,165,0
motorboat_with_cabin = 0,255,0
motorboat_without_cabin = 0,200,0
sailboat_with_cabin = 255,0,0
sailboat_without_cabin = 200,0,0
licence = 0,0,255

# Farberklärung:
# muscle_boat          = Gelb      - Auffällig für Sportboote
# passenger_boat       = Orange    - Gut sichtbar für Passagierboote  
# motorboat_with_cabin = Grün      - Standard für Motorboote mit Kabine
# motorboat_without_cabin = Dunkelgrün - Offene Motorboote
# sailboat_with_cabin  = Blau      - Klassisch für große Segelboote
# sailboat_without_cabin = Dunkelblau - Kleinere Segelboote
# licence              = Rot       - Sehr wichtig für Kennzeichen
"""
    
    print("Vorlage für Bootsklassen-Farbkonfiguration:")
    print("="*60)
    print(template)
    print("="*60)
    print(f"Fügen Sie diese Sektion zur {config_path} hinzu, um Farben anzupassen.")
    
    return template


def validate_color_configuration(config_path: str = "config.ini") -> bool:
    """Validiert die Farbkonfiguration für die spezifischen Bootsklassen."""
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding='utf-8')
        
        if 'colors' not in cfg:
            print("Info: Keine [colors] Sektion in config.ini gefunden")
            print("Das System verwendet Standard-Farben für alle Bootsklassen.")
            return True
        
        colors_section = cfg['colors']
        valid = True
        
        # Validiere alle konfigurierten Farben
        for class_name in colors_section:
            color_str = colors_section.get(class_name)
            try:
                color_str = color_str.strip('()')
                b, g, r = map(int, color_str.split(','))
                
                # Validiere Farbwerte
                if not (0 <= b <= 255 and 0 <= g <= 255 and 0 <= r <= 255):
                    print(f"FEHLER: Ungültige Farbwerte für {class_name}: ({b},{g},{r})")
                    print("Farbwerte müssen zwischen 0 und 255 liegen.")
                    valid = False
                
            except ValueError:
                print(f"FEHLER: Ungültiges Farbformat für {class_name}: {color_str}")
                print("Format sollte sein: 'B,G,R' (z.B. '255,0,0' für rot)")
                valid = False
        
        # Zeige Konfigurationsstatus für alle Bootsklassen
        boat_classes = ['muscle_boat', 'passenger_boat', 'motorboat_with_cabin', 
                       'motorboat_without_cabin', 'sailboat_with_cabin', 
                       'sailboat_without_cabin', 'licence']
        
        configured = [c for c in boat_classes if c in colors_section]
        unconfigured = [c for c in boat_classes if c not in colors_section]
        
        print(f"\nKonfigurationsstatus der Bootsklassen:")
        print(f"✅ Konfiguriert ({len(configured)}): {', '.join(configured) if configured else 'Keine'}")
        print(f"🔧 Standard-Farben ({len(unconfigured)}): {', '.join(unconfigured) if unconfigured else 'Keine'}")
        
        if valid:
            print(f"\n✅ Farbkonfiguration ist gültig")
        
        return valid
        
    except Exception as e:
        print(f"Fehler bei der Validierung der Farbkonfiguration: {e}")
        return False


# ========================================================================================
# BESTEHENDE FUNKTIONEN (unverändert)
# ========================================================================================

def sanitize_filename(text: str, config_path: str = "config.ini") -> str:
    """Return a filesystem friendly version of the text while preserving location names exactly."""
    # Automatisch alle Locations aus der config.ini laden
    available_locations = get_available_locations(config_path)
    
    # Preserve location names exactly as they appear in config.ini
    if text in available_locations:
        return text
    
    # For non-location text (like file names), apply minimal sanitization
    text = text.replace(" ", "_")
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    return text


def is_license_completely_inside_boat(lic_box, boat_box) -> bool:
    """Check if a licence bounding box lies completely within a boat box."""
    return (
        lic_box[0] >= boat_box[0]
        and lic_box[1] >= boat_box[1]
        and lic_box[2] <= boat_box[2]
        and lic_box[3] <= boat_box[3]
    )


def perform_ocr_on_license(frame, bbox, reader):
    """Run OCR on the cropped license plate region."""
    x1, y1, x2, y2 = map(int, bbox)
    h, w = frame.shape[:2]
    x1, x2 = max(0, x1), min(w - 1, x2)
    y1, y2 = max(0, y1), min(h - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return "", 0.0
    crop = frame[y1:y2, x1:x2]
    try:
        res = reader.readtext(crop)
        if res:
            best = max(res, key=lambda x: x[2])
            return best[1].strip(), best[2]
    except Exception:
        pass
    return "", 0.0


def find_license_for_boat(boat_bbox, licenses_data):
    """Return the license box with highest confidence fully inside the boat box."""
    best_lic = None
    best_conf = 0.0
    for lic in licenses_data:
        if is_license_completely_inside_boat(lic['bbox'], boat_bbox) and lic['conf'] > best_conf:
            best_conf = lic['conf']
            best_lic = lic
    return best_lic


def load_active_location(path: str = "active_location.txt") -> str:
    """Return the currently active location from the given file."""
    if not os.path.exists(path):
        error_msg = f"FEHLER: {path} nicht gefunden!"
        print("="*60)
        print(error_msg)
        print("Das System kann ohne active_location.txt nicht funktionieren.")
        print("Bitte erstellen Sie die Datei mit dem gewünschten Standort.")
        print("="*60)
        raise FileNotFoundError(f"{path} nicht gefunden.")
    
    with open(path, "r", encoding="utf-8") as f:
        location = f.read().strip()
    
    # Validierung: Prüfe ob Location in config.ini existiert
    validate_location_exists(location)
    
    return location


def validate_location_exists(location: str, config_path: str = "config.ini") -> bool:
    """Validiert ob die angegebene Location in der config.ini existiert."""
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding='utf-8')
        
        if location not in cfg.sections():
            available_locations = get_available_locations(config_path)
            error_msg = f"""
KONFIGURATIONSFEHLER: Location '{location}' nicht in config.ini gefunden!

Verfügbare Locations in config.ini:
{chr(10).join(f"  - {loc}" for loc in available_locations)}

Bitte:
1. Überprüfen Sie active_location.txt (aktuelle Location: '{location}')
2. Oder fügen Sie [{location}] Sektion zur config.ini hinzu mit:
   rtsp_url_1 = rtsp://...
   line1_position_1 = ...
   line2_position_1 = ...
   orientation_1 = ...
   (und entsprechend für _2 und _3)
"""
            print("="*80)
            print(error_msg)
            print("="*80)
            raise ValueError(f"Location '{location}' nicht in config.ini definiert.")
        
        return True
    except Exception as e:
        if "nicht in config.ini definiert" in str(e):
            raise  # Re-raise unsere eigene Fehlermeldung
        else:
            print(f"WARNUNG: Konnte Location nicht validieren: {e}")
            return False


def load_config(location: str, path: str = "config.ini"):
    """Load stream configuration for a location from the ini file."""
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding='utf-8')
    
    if location not in cfg:
        available_locations = get_available_locations(path)
        error_msg = f"""
KONFIGURATIONSFEHLER: Location '{location}' nicht in {path} gefunden!

Verfügbare Locations:
{chr(10).join(f"  - {loc}" for loc in available_locations)}

Mögliche Lösungen:
1. Korrigieren Sie active_location.txt
2. Fügen Sie [{location}] zur config.ini hinzu
"""
        print("="*60)
        print(error_msg)
        print("="*60)
        raise ValueError(f"Location '{location}' nicht in {path}.")
    
    sec = cfg[location]
    streams = []
    
    for i in range(1, 4):
        url = sec.get(f"rtsp_url_{i}")
        if not url:
            continue
        line1 = sec.getint(f"line1_position_{i}", fallback=0)
        line2 = sec.getint(f"line2_position_{i}", fallback=0)
        orientation = sec.get(f"orientation_{i}")
        if not orientation:
            raise ValueError(
                f"orientation_{i} fehlt in Abschnitt '{location}' in {path}"
            )
        orientation = orientation.lower()
        if orientation not in {"vertical", "horizontal"}:
            raise ValueError(
                f"Ungültige Orientierung '{orientation}' für orientation_{i} in Abschnitt '{location}'."
            )
        streams.append(
            {
                "url": url,
                "line1": line1,
                "line2": line2,
                "orientation": orientation,
            }
        )
    
    print(f"Konfiguration geladen für Location '{location}': {len(streams)} Streams")
    return {"streams": streams}


def load_ocr_config(path: str = "config.ini") -> dict:
    """Load OCR configuration settings from config file."""
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding='utf-8')
    
    default_ocr_settings = {
        # Bildvorverarbeitung
        'enable_clahe': True,
        'enable_denoising': True,
        'enable_sharpening': True,
        'scale_factor': 2.0,
        
        # OCR-Parameter
        'min_confidence': 0.3,
        'max_ocr_attempts': 3,
        'enable_multi_frame': True,
        'max_frame_history': 5,
        
        # Qualitätsschwellen
        'min_frame_quality': 100.0,
        'min_text_length': 2,
        'max_text_length': 20,
        
        # Performance-Optimierungen
        'enable_gpu_acceleration': True,
        'enable_parallel_processing': True,
        'frame_skip_threshold': 50.0,
        
        # Logging und Monitoring
        'enable_performance_logging': True,
        'enable_difficult_cases_saving': True,
        'log_directory': 'logs',
        'difficult_cases_directory': 'difficult_cases'
    }
    
    if 'ocr_settings' in cfg:
        ocr_sec = cfg['ocr_settings']
        
        # Boolean Werte
        for key in ['enable_clahe', 'enable_denoising', 'enable_sharpening', 
                   'enable_multi_frame', 'enable_gpu_acceleration', 
                   'enable_parallel_processing', 'enable_performance_logging', 
                   'enable_difficult_cases_saving']:
            if key in ocr_sec:
                default_ocr_settings[key] = ocr_sec.getboolean(key)
        
        # Float Werte
        for key in ['scale_factor', 'min_confidence', 'min_frame_quality', 
                   'frame_skip_threshold']:
            if key in ocr_sec:
                default_ocr_settings[key] = ocr_sec.getfloat(key)
        
        # Integer Werte
        for key in ['max_ocr_attempts', 'max_frame_history', 'min_text_length', 
                   'max_text_length']:
            if key in ocr_sec:
                default_ocr_settings[key] = ocr_sec.getint(key)
        
        # String Werte
        for key in ['log_directory', 'difficult_cases_directory']:
            if key in ocr_sec:
                default_ocr_settings[key] = ocr_sec.get(key)
    
    # Erstelle notwendige Verzeichnisse
    for dir_key in ['log_directory', 'difficult_cases_directory']:
        dir_path = default_ocr_settings[dir_key]
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
    
    print(f"OCR-Konfiguration geladen:")
    print(f"  - Multi-Frame OCR: {default_ocr_settings['enable_multi_frame']}")
    print(f"  - Min. Bildqualität: {default_ocr_settings['min_frame_quality']}")
    print(f"  - Min. Confidence: {default_ocr_settings['min_confidence']}")
    print(f"  - Frame History: {default_ocr_settings['max_frame_history']}")
    print(f"  - GPU-Beschleunigung: {default_ocr_settings['enable_gpu_acceleration']}")
    
    return default_ocr_settings


def load_commercial_licenses(path: str = "1.txt") -> set:
    """Load commercial license numbers from a text file."""
    plates = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            plates = {ln.strip() for ln in f if ln.strip()}
        print(f"Loaded {len(plates)} commercial licenses from {path}")
    else:
        print(f"Warning: {path} nicht gefunden. Identifizierung deaktiviert.")
    return plates


def create_ocr_performance_dashboard():
    """Erstelle ein einfaches OCR-Performance Dashboard."""
    import json
    from collections import defaultdict
    import matplotlib.pyplot as plt
    from datetime import datetime, timedelta
    
    performance_file = "logs/ocr_performance.jsonl"
    if not os.path.exists(performance_file):
        print("Keine OCR-Performance-Daten verfügbar.")
        return
    
    # Lade Performance-Daten
    data = []
    with open(performance_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except:
                continue
    
    if not data:
        print("Keine gültigen OCR-Performance-Daten gefunden.")
        return
    
    # Analysiere Performance
    total_ocr_calls = len(data)
    successful_ocr = len([d for d in data if d.get('text', '')])
    success_rate = (successful_ocr / total_ocr_calls) * 100 if total_ocr_calls > 0 else 0
    
    avg_confidence = sum(d.get('confidence', 0) for d in data) / len(data)
    avg_processing_time = sum(d.get('execution_time', 0) for d in data) / len(data)
    
    # Erfolgsraten nach Methoden
    method_stats = defaultdict(lambda: {'total': 0, 'success': 0, 'avg_conf': 0})
    for d in data:
        method = d.get('method', 'unknown')
        method_stats[method]['total'] += 1
        if d.get('text', ''):
            method_stats[method]['success'] += 1
        method_stats[method]['avg_conf'] += d.get('confidence', 0)
    
    print("\n" + "="*50)
    print("OCR-PERFORMANCE DASHBOARD")
    print("="*50)
    print(f"Gesamt OCR-Aufrufe: {total_ocr_calls}")
    print(f"Erfolgreiche OCR: {successful_ocr}")
    print(f"Erfolgsrate: {success_rate:.1f}%")
    print(f"Durchschnittliche Confidence: {avg_confidence:.3f}")
    print(f"Durchschnittliche Verarbeitungszeit: {avg_processing_time:.3f}s")
    
    print("\nMethoden-Statistiken:")
    for method, stats in method_stats.items():
        success_rate_method = (stats['success'] / stats['total']) * 100
        avg_conf_method = stats['avg_conf'] / stats['total']
        print(f"  {method}: {success_rate_method:.1f}% Erfolg, Ø Conf: {avg_conf_method:.3f}")
    
    # Zeitliche Analyse (letzte 24h)
    now = datetime.now()
    last_24h = now - timedelta(hours=24)
    recent_data = [d for d in data if datetime.fromtimestamp(d.get('timestamp', 0)) > last_24h]
    
    if recent_data:
        recent_success = len([d for d in recent_data if d.get('text', '')])
        recent_success_rate = (recent_success / len(recent_data)) * 100
        print(f"\nLetzte 24h: {len(recent_data)} OCR-Aufrufe, {recent_success_rate:.1f}% Erfolg")
    
    print("="*50)


def get_ocr_status_summary():
    """Gibt eine kurze Zusammenfassung des OCR-Status zurück."""
    import json
    from datetime import datetime, timedelta
    
    performance_file = "logs/ocr_performance.jsonl"
    if not os.path.exists(performance_file):
        return "Keine OCR-Daten verfügbar"
    
    try:
        # Lese die letzten 100 Einträge
        with open(performance_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        recent_data = []
        for line in recent_lines:
            try:
                recent_data.append(json.loads(line))
            except:
                continue
        
        if not recent_data:
            return "Keine gültigen OCR-Daten gefunden"
        
        successful = len([d for d in recent_data if d.get('text', '')])
        success_rate = (successful / len(recent_data)) * 100
        avg_conf = sum(d.get('confidence', 0) for d in recent_data) / len(recent_data)
        
        return f"OCR Status: {success_rate:.1f}% Erfolg, Ø Conf: {avg_conf:.3f} ({len(recent_data)} Aufrufe)"
    
    except Exception as e:
        return f"Fehler beim OCR-Status: {e}"


def create_new_location_template(location_name: str, config_path: str = "config.ini"):
    """Erstellt eine Vorlage für eine neue Location in der config.ini."""
    template = f"""
# Vorlage für neue Location: {location_name}
# Bitte ergänzen Sie die tatsächlichen Werte

[{location_name}]
rtsp_url_1 = rtsp://admin:PASSWORD@IP_ADRESSE:554/h264Preview_01_main
line1_position_1 = 450
line2_position_1 = 500
orientation_1 = horizontal

rtsp_url_2 = rtsp://admin:PASSWORD@IP_ADRESSE:554/h264Preview_02_sub  
line1_position_2 = 950
line2_position_2 = 1000
orientation_2 = vertical

rtsp_url_3 = rtsp://admin:PASSWORD@IP_ADRESSE:554/h264Preview_03_main
line1_position_3 = 350
line2_position_3 = 400
orientation_3 = horizontal
"""
    
    print(f"Vorlage für Location '{location_name}':")
    print("="*60)
    print(template)
    print("="*60)
    print(f"Bitte fügen Sie diese Konfiguration zur {config_path} hinzu und passen Sie die Werte an.")
    
    return template
