import re
import cv2
import numpy as np
import time
import json
import os
from collections import defaultdict, deque
from skimage import filters
from skimage.restoration import denoise_tv_chambolle
import difflib
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum


class TextType(Enum):
    """Enum für verschiedene Text-Typen mit spezifischen Validierungsregeln."""
    LICENSE_PLATE = "license_plate"
    BOAT_NAME = "boat_name" 
    UNKNOWN = "unknown"


@dataclass
class OCRResult:
    """Datenklasse für strukturierte OCR-Ergebnisse."""
    text: str
    confidence: float
    text_type: TextType
    format_confidence: float
    corrected_text: str
    method: str
    quality_score: float
    validation_details: Dict
    final_score: float


class SmartOCRValidator:
    """Intelligente OCR-Validierung mit korrigierter Sonderzeichen-Filterung."""
    
    def __init__(self, commercial_licenses: set = None):
        self.commercial_licenses = commercial_licenses or set()
        
        # Deutsche Bootsnamen-Patterns (erweitert)
        self.boat_name_patterns = [
            r'^[A-Z]{2,4}\s*\d{1,4}$',        # MS 123, ABC 1234
            r'^[A-Z][a-z]+\s*\d*$',           # Marina, Seeadler
            r'^[A-Z][a-z]+\s+[A-Z][a-z]+$',   # Blaue Adria
            r'^[A-Z]{2,8}$',                  # NORDWIND
            r'^\d{1,4}\s*[A-Z]{2,4}$',       # 123 MS
            r'^[A-Z][a-z]+\s+[IV]+$',        # Maria II
        ]
        
        # Erweiterte Kennzeichen-Patterns für deutsche Bootslizenzen
        self.license_patterns = [
            r'^[A-Z]{1,3}-[A-Z]{1,2}\s?\d{1,4}$',     # AB-A 170
            r'^[A-Z]{1,3}-\d{1,4}\s{0,2}V?$',         # BAR-3097 V
            r'^\d{6}-[A-Z]$',                          # 123456-A
            r'^[A-Z]{3}\s\d{5}$',                     # BSR 24138
            r'^[A-Z]{3}\s\d{3}-\d{3}$',              # HST 433-100
            r'^[A-Z]{2}\s[A-Z]\s\d{5}[A-Z]?$',       # TO E 48620F
            r'^[A-Z]{2,4}\s?\d{2,6}[A-Z]?$',         # Allgemein flexibler
        ]
        
        # Format-spezifische Korrekturen für OCR-Fehler
        self.license_corrections = {
            '0': 'O', '|': 'I', '1': 'I', '5': 'S', '8': 'B', 
            '6': 'G', '9': 'g', 'cl': 'd', 'rn': 'm'
        }
        
        self.boat_name_corrections = {
            '0': 'O', '|': 'I', '1': 'I', '5': 'S', '8': 'B',
            'rn': 'm', 'vv': 'w', 'VV': 'W', 'ii': 'n'
        }
        
        # NEUE FEATURE: Erlaubte vs. zu entfernende Sonderzeichen
        self.allowed_special_chars = {
            TextType.LICENSE_PLATE: set(['-', ' ']),  # Nur Bindestrich und Leerzeichen
            TextType.BOAT_NAME: set(['-', ' ', 'ä', 'ö', 'ü', 'Ä', 'Ö', 'Ü', 'ß'])  # Deutsche Umlaute erlaubt
        }
        
        # Häufige deutsche Bootsnamen-Wörter für bessere Erkennung
        self.common_boat_words = {
            'maria', 'adler', 'wind', 'see', 'stern', 'nord', 'süd', 
            'ost', 'west', 'blau', 'weiß', 'rot', 'gold', 'silber',
            'freiheit', 'hoffnung', 'traum', 'stolz', 'mut'
        }
    
    def detect_text_type(self, text: str) -> Tuple[TextType, float]:
        """Erkennt den Text-Typ und gibt Confidence zurück."""
        if not text or len(text) < 2:
            return TextType.UNKNOWN, 0.0
        
        text_clean = text.strip()
        
        # Kennzeichen-Erkennung
        license_score = 0.0
        for pattern in self.license_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                license_score = 0.9
                break
        
        # Zusätzliche Kennzeichen-Indikatoren
        if re.search(r'^[A-Z]{1,3}-', text_clean):
            license_score = max(license_score, 0.7)
        if re.search(r'\d{3,6}', text_clean) and len(text_clean) <= 12:
            license_score = max(license_score, 0.6)
        
        # Bootsnamen-Erkennung
        boat_score = 0.0
        for pattern in self.boat_name_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                boat_score = 0.8
                break
        
        # Erweiterte Bootsnamen-Erkennung
        text_lower = text_clean.lower()
        for word in self.common_boat_words:
            if word in text_lower:
                boat_score = max(boat_score, 0.7)
                break
        
        # Längere Texte sind eher Bootsnamen
        if len(text_clean) > 8 and not re.search(r'^[A-Z]{1,3}-', text_clean):
            boat_score = max(boat_score, 0.6)
        
        # Entscheidung basierend auf höchster Confidence
        if license_score > boat_score and license_score > 0.5:
            return TextType.LICENSE_PLATE, license_score
        elif boat_score > 0.5:
            return TextType.BOAT_NAME, boat_score
        else:
            return TextType.UNKNOWN, max(license_score, boat_score)
    
    def remove_invalid_special_chars(self, text: str, text_type: TextType) -> str:
        """NEUE FUNKTION: Entfernt ungültige Sonderzeichen basierend auf Text-Typ."""
        if not text:
            return text
        
        # Hole erlaubte Zeichen für diesen Text-Typ
        allowed_chars = self.allowed_special_chars.get(text_type, set())
        
        # Baue erlaubte Zeichen-Set: Buchstaben + Zahlen + erlaubte Sonderzeichen
        valid_chars = set()
        valid_chars.update('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
        valid_chars.update('0123456789')
        valid_chars.update(allowed_chars)
        
        # Filtere nur erlaubte Zeichen
        cleaned_text = ''.join(char for char in text if char in valid_chars)
        
        # Debug-Info wenn Zeichen entfernt wurden
        removed_chars = set(text) - set(cleaned_text)
        if removed_chars:
            print(f"Sonderzeichen-Filter: Entfernt '{removed_chars}' aus '{text}' -> '{cleaned_text}'")
        
        return cleaned_text
    
    def apply_format_specific_corrections(self, text: str, text_type: TextType) -> str:
        """Wendet format-spezifische Korrekturen an UND entfernt ungültige Sonderzeichen."""
        if not text:
            return text
        
        corrected = text
        
        # SCHRITT 1: OCR-Fehler korrigieren
        if text_type == TextType.LICENSE_PLATE:
            # Kennzeichen-spezifische Korrekturen
            for wrong, right in self.license_corrections.items():
                corrected = corrected.replace(wrong, right)
            
            # Spezielle Kennzeichen-Korrekturen
            corrected = re.sub(r'(\d)\s+(\w)', r'\1\2', corrected)  # Lücken schließen
            corrected = re.sub(r'([A-Z])\s+(\d)', r'\1 \2', corrected)  # Korrekte Lücken
            
        elif text_type == TextType.BOAT_NAME:
            # Bootsnamen-spezifische Korrekturen
            for wrong, right in self.boat_name_corrections.items():
                corrected = corrected.replace(wrong, right)
            
            # Kapitalisierung korrigieren
            words = corrected.split()
            corrected_words = []
            for word in words:
                if word.isdigit():
                    corrected_words.append(word)
                elif word.isupper() and len(word) > 3:
                    corrected_words.append(word.capitalize())
                else:
                    corrected_words.append(word)
            corrected = ' '.join(corrected_words)
        
        # SCHRITT 2: KRITISCH - Ungültige Sonderzeichen entfernen
        corrected = self.remove_invalid_special_chars(corrected, text_type)
        
        # SCHRITT 3: Mehrfache Leerzeichen normalisieren
        corrected = re.sub(r'\s+', ' ', corrected).strip()
        
        return corrected
    
    def validate_format_comprehensive(self, text: str, text_type: TextType) -> Tuple[bool, float, Dict]:
        """Umfassende Format-Validierung - jetzt ohne Sonderzeichen-Check da schon bereinigt."""
        if not text:
            return False, 0.0, {'reason': 'empty_text'}
        
        text_clean = text.strip()
        details = {'original_length': len(text), 'cleaned_length': len(text_clean)}
        
        # Grundlegende Validierung
        if len(text_clean) < 2:
            return False, 0.0, {**details, 'reason': 'too_short'}
        
        if len(text_clean) > 25:
            return False, 0.2, {**details, 'reason': 'too_long'}
        
        # ENTFERNT: Sonderzeichen-Check (da bereits in apply_format_specific_corrections bereinigt)
        # Alte Logik war hier das Problem!
        
        confidence = 0.5  # Basis-Confidence
        
        if text_type == TextType.LICENSE_PLATE:
            return self._validate_license_format(text_clean, details)
        elif text_type == TextType.BOAT_NAME:
            return self._validate_boat_name_format(text_clean, details)
        else:
            # Unbekannter Typ - versuche beide Validierungen
            lic_valid, lic_conf, _ = self._validate_license_format(text_clean, {})
            boat_valid, boat_conf, _ = self._validate_boat_name_format(text_clean, {})
            
            if lic_valid or boat_valid:
                return True, max(lic_conf, boat_conf), {**details, 'reason': 'fallback_validation'}
            else:
                return False, max(lic_conf, boat_conf) * 0.5, {**details, 'reason': 'unknown_format'}
    
    def _validate_license_format(self, text: str, details: Dict) -> Tuple[bool, float, Dict]:
        """Spezifische Kennzeichen-Validierung."""
        confidence = 0.0
        
        # Pattern-Matching
        for i, pattern in enumerate(self.license_patterns):
            if re.match(pattern, text, re.IGNORECASE):
                confidence = 0.9 - (i * 0.05)  # Erste Patterns haben höhere Confidence
                details['matched_pattern'] = i
                break
        
        # Zusätzliche Validierungen
        if re.search(r'^[A-Z]{1,3}-', text):
            confidence = max(confidence, 0.7)
            details['has_prefix'] = True
        
        if re.search(r'\d{3,6}', text):
            confidence = max(confidence, 0.6)
            details['has_numbers'] = True
        
        # Längen-Validierung
        if 5 <= len(text) <= 12:
            confidence += 0.1
        
        # Format-Konsistenz
        if text.isupper() or (text[0].isupper() and any(c.isdigit() for c in text)):
            confidence += 0.1
        
        return confidence > 0.5, confidence, details
    
    def _validate_boat_name_format(self, text: str, details: Dict) -> Tuple[bool, float, Dict]:
        """Spezifische Bootsnamen-Validierung."""
        confidence = 0.0
        
        # Pattern-Matching
        for i, pattern in enumerate(self.boat_name_patterns):
            if re.match(pattern, text, re.IGNORECASE):
                confidence = 0.8 - (i * 0.05)
                details['matched_pattern'] = i
                break
        
        # Wort-basierte Erkennung
        text_lower = text.lower()
        for word in self.common_boat_words:
            if word in text_lower:
                confidence = max(confidence, 0.7)
                details['contains_boat_word'] = word
                break
        
        # Struktur-Validierung
        if re.search(r'^[A-Z][a-z]+', text):  # Kapitalisiert
            confidence += 0.1
            details['properly_capitalized'] = True
        
        if len(text) > 6:  # Bootsnamen sind oft länger
            confidence += 0.1
            details['reasonable_length'] = True
        
        # Deutsche Zeichen
        if any(c in text for c in 'äöüÄÖÜß'):
            confidence += 0.15
            details['contains_german_chars'] = True
        
        return confidence > 0.4, confidence, details
    
    def similarity_matching_enhanced(self, text: str, text_type: TextType) -> Tuple[str, float]:
        """Erweiterte Ähnlichkeitssuche mit bekannten Lizenzen."""
        if not text or not self.commercial_licenses:
            return text, 0.0
        
        best_match = text
        best_ratio = 0.0
        
        # Verschiedene Matching-Strategien je nach Text-Typ
        for license_num in self.commercial_licenses:
            if text_type == TextType.LICENSE_PLATE:
                # Exakte und fuzzy Matches für Kennzeichen
                ratio = difflib.SequenceMatcher(None, text.upper(), license_num.upper()).ratio()
                
                # Zusätzlich: Levenshtein-ähnliche Bewertung
                if len(text) == len(license_num):
                    char_matches = sum(1 for a, b in zip(text.upper(), license_num.upper()) if a == b)
                    char_ratio = char_matches / len(text)
                    ratio = max(ratio, char_ratio)
                
            else:
                # Für Bootsnamen: Lockerere Ähnlichkeits-Kriterien
                ratio = difflib.SequenceMatcher(None, text.lower(), license_num.lower()).ratio()
            
            if ratio > best_ratio and ratio > 0.75:  # Höhere Schwelle für bessere Qualität
                best_ratio = ratio
                best_match = license_num
        
        return best_match, best_ratio
    
    def calculate_comprehensive_score(self, ocr_result: OCRResult) -> float:
        """Berechnet einen umfassenden Score für das OCR-Ergebnis."""
        if not ocr_result.text:
            return 0.0
        
        # Basis-Score aus OCR-Confidence
        score = ocr_result.confidence * 0.3
        
        # Format-Confidence gewichtet nach Text-Typ
        format_weight = 0.3 if ocr_result.text_type != TextType.UNKNOWN else 0.15
        score += ocr_result.format_confidence * format_weight
        
        # Bildqualität
        quality_factor = min(1.0, ocr_result.quality_score / 200.0)
        score += quality_factor * 0.2
        
        # Text-Länge (optimal je nach Typ)
        length_factor = self._calculate_length_factor(ocr_result.text, ocr_result.text_type)
        score *= length_factor
        
        # Korrektur-Bonus wenn Text korrigiert wurde
        if ocr_result.corrected_text != ocr_result.text:
            score += 0.1
        
        # Method-spezifische Anpassungen
        method_weights = {
            'standard': 1.0,
            'detailed': 1.1, 
            'paragraph': 0.9,
            'enhanced': 1.2,
            'consensus': 1.3
        }
        method_key = ocr_result.method.split('_')[0]
        score *= method_weights.get(method_key, 1.0)
        
        # Validierungs-Details berücksichtigen
        if 'matched_pattern' in ocr_result.validation_details:
            score += 0.1
        
        if 'contains_boat_word' in ocr_result.validation_details:
            score += 0.15
        
        return min(1.0, score)
    
    def _calculate_length_factor(self, text: str, text_type: TextType) -> float:
        """Berechnet Längen-Faktor basierend auf Text-Typ."""
        length = len(text)
        
        if text_type == TextType.LICENSE_PLATE:
            # Kennzeichen: optimal 6-12 Zeichen
            if 6 <= length <= 12:
                return 1.0
            elif 4 <= length <= 15:
                return 0.9
            else:
                return 0.7
        
        elif text_type == TextType.BOAT_NAME:
            # Bootsnamen: optimal 4-20 Zeichen
            if 4 <= length <= 20:
                return 1.0
            elif 2 <= length <= 25:
                return 0.8
            else:
                return 0.6
        
        else:
            # Unbekannt: konservative Bewertung
            if 3 <= length <= 15:
                return 0.8
            else:
                return 0.6
    
    def process_ocr_result(self, text: str, confidence: float, method: str, quality_score: float) -> OCRResult:
        """Hauptfunktion: Verarbeitet ein OCR-Ergebnis durch die gesamte Validierungs-Pipeline."""
        
        # 1. Text-Typ erkennen
        text_type, type_confidence = self.detect_text_type(text)
        
        # 2. Format-spezifische Korrekturen anwenden UND Sonderzeichen entfernen
        corrected_text = self.apply_format_specific_corrections(text, text_type)
        
        # 3. Umfassende Format-Validierung (jetzt ohne Sonderzeichen-Check)
        is_valid, format_confidence, validation_details = self.validate_format_comprehensive(
            corrected_text, text_type
        )
        
        # 4. Ähnlichkeitssuche mit bekannten Lizenzen
        final_text, similarity_score = self.similarity_matching_enhanced(corrected_text, text_type)
        
        # Verwende Ähnlichkeits-Match wenn signifikant besser
        if similarity_score > 0.8:
            final_text = final_text
            format_confidence = max(format_confidence, similarity_score)
            validation_details['similarity_match'] = similarity_score
        else:
            final_text = corrected_text
        
        # 5. OCRResult erstellen
        ocr_result = OCRResult(
            text=text,
            confidence=confidence,
            text_type=text_type,
            format_confidence=format_confidence,
            corrected_text=final_text,
            method=method,
            quality_score=quality_score,
            validation_details=validation_details,
            final_score=0.0  # Wird im nächsten Schritt berechnet
        )
        
        # 6. Finalen Score berechnen
        ocr_result.final_score = self.calculate_comprehensive_score(ocr_result)
        
        return ocr_result
    
    def get_validation_summary(self, ocr_result: OCRResult) -> str:
        """Erstellt eine menschenlesbare Zusammenfassung der Validierung."""
        summary_parts = []
        
        summary_parts.append(f"Text-Typ: {ocr_result.text_type.value}")
        summary_parts.append(f"Format-Confidence: {ocr_result.format_confidence:.3f}")
        summary_parts.append(f"Final-Score: {ocr_result.final_score:.3f}")
        
        if ocr_result.corrected_text != ocr_result.text:
            summary_parts.append(f"Korrigiert: '{ocr_result.text}' → '{ocr_result.corrected_text}'")
        
        if 'similarity_match' in ocr_result.validation_details:
            similarity = ocr_result.validation_details['similarity_match']
            summary_parts.append(f"Ähnlichkeits-Match: {similarity:.3f}")
        
        return " | ".join(summary_parts)


# ========================================================================================
# LEGACY-FUNKTIONEN FÜR KOMPATIBILITÄT (unverändert - bleiben bestehen)
# ========================================================================================

def sanitize_filename(text: str) -> str:
    """Return a filesystem friendly version of the text while preserving location names."""
    location_names = ['Fürstenberg', 'Diemitz', 'Bredereiche']
    if text in location_names:
        return text
    
    text = text.replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_üöäÜÖÄß]", "", text)


def is_license_completely_inside_boat(lic_box, boat_box) -> bool:
    """Check if a licence bounding box lies completely within a boat box."""
    return (
        lic_box[0] >= boat_box[0]
        and lic_box[1] >= boat_box[1]
        and lic_box[2] <= boat_box[2]
        and lic_box[3] <= boat_box[3]
    )


def get_adaptive_ocr_params(hour=None, weather_condition="sunny"):
    """Dynamische Anpassung basierend auf Tageszeit und Wetter."""
    if hour is None:
        hour = time.localtime().tm_hour
    
    if weather_condition == "dark" or hour < 6 or hour > 20:
        return {"brightness_boost": 1.3, "contrast_factor": 1.5}
    elif weather_condition == "bright":
        return {"brightness_boost": 0.8, "contrast_factor": 1.2}
    return {"brightness_boost": 1.0, "contrast_factor": 1.0}


def calculate_frame_quality(crop):
    """Bewertet die Bildqualität für OCR."""
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop
    
    # Berechne Schärfe (Varianz des Laplacian)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Berechne Kontrast
    contrast = gray.std()
    
    # Berechne Helligkeit
    brightness = gray.mean()
    
    # Kombinierter Quality Score
    quality_score = (sharpness * 0.5) + (contrast * 0.3) + (min(brightness, 255-brightness) * 0.2)
    return quality_score


def enhance_image_preprocessing(crop, params=None):
    """Erweiterte Bildvorverarbeitung für bessere OCR-Ergebnisse."""
    if params is None:
        params = get_adaptive_ocr_params()
    
    methods_used = []
    
    # Zu Graustufen konvertieren
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop.copy()
    
    # 1. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    methods_used.append("CLAHE")
    
    # 2. Brightness und Contrast Anpassung
    enhanced = cv2.convertScaleAbs(enhanced, 
                                  alpha=params["contrast_factor"], 
                                  beta=(params["brightness_boost"] - 1.0) * 50)
    methods_used.append("brightness_contrast")
    
    # 3. Denoising
    try:
        enhanced = denoise_tv_chambolle(enhanced, weight=0.1, eps=0.0002, n_iter_max=50)
        enhanced = (enhanced * 255).astype(np.uint8)
        methods_used.append("denoising")
    except:
        # Fallback zu cv2 denoising
        enhanced = cv2.fastNlMeansDenoising(enhanced)
        methods_used.append("cv2_denoising")
    
    # 4. Adaptive Thresholding
    adaptive_thresh = cv2.adaptiveThreshold(enhanced, 255, 
                                          cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)
    methods_used.append("adaptive_threshold")
    
    # 5. Morphological Operations
    kernel = np.ones((2,2), np.uint8)
    morph = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_CLOSE, kernel)
    morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)
    methods_used.append("morphology")
    
    # 6. Edge Enhancement
    edges = cv2.Canny(enhanced, 50, 150)
    enhanced_edges = cv2.addWeighted(enhanced, 0.8, edges, 0.2, 0)
    methods_used.append("edge_enhancement")
    
    # 7. Multiple Scale Processing
    scales = [1.0, 1.5, 2.0, 2.5]
    processed_images = []
    
    for scale in scales:
        if scale != 1.0:
            h, w = enhanced.shape
            new_h, new_w = int(h * scale), int(w * scale)
            scaled = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        else:
            scaled = enhanced
        processed_images.append(scaled)
    
    processed_images.extend([adaptive_thresh, morph, enhanced_edges])
    methods_used.append("multi_scale")
    
    return processed_images, methods_used


def perform_ocr_on_license_enhanced(frame, bbox, reader, commercial_licenses=None, quality_threshold=100.0):
    """VERBESSERTE HAUPTFUNKTION: OCR mit korrigierter Sonderzeichen-Filterung."""
    x1, y1, x2, y2 = map(int, bbox)
    h, w = frame.shape[:2]
    x1, x2 = max(0, x1), min(w - 1, x2)
    y1, y2 = max(0, y1), min(h - 1, y2)
    
    if x2 <= x1 or y2 <= y1:
        return "", 0.0, "error", []
    
    crop = frame[y1:y2, x1:x2]
    
    # Bildqualität prüfen
    quality_score = calculate_frame_quality(crop)
    if quality_score < quality_threshold:
        return "", 0.0, "quality_too_low", []
    
    # Smart Validator initialisieren - JETZT MIT KORRIGIERTER SONDERZEICHEN-FILTERUNG
    validator = SmartOCRValidator(commercial_licenses)
    
    # Adaptive Parameter basierend auf Tageszeit
    params = get_adaptive_ocr_params()
    
    # Erweiterte Bildvorverarbeitung
    processed_images, methods_used = enhance_image_preprocessing(crop, params)
    
    # Multi-Method OCR Ansatz
    ocr_candidates = []
    ocr_methods = [
        {'detail': 0, 'paragraph': False, 'name': 'standard'},
        {'detail': 1, 'paragraph': False, 'name': 'detailed'},
        {'detail': 0, 'paragraph': True, 'name': 'paragraph'},
        {'detail': 1, 'paragraph': True, 'name': 'enhanced'}
    ]
    
    for img_idx, processed_img in enumerate(processed_images[:6]):  # Limitiere auf 6 Bilder
        for method in ocr_methods:
            try:
                start_time = time.time()
                results = reader.readtext(processed_img, 
                                        detail=method['detail'],
                                        paragraph=method['paragraph'])
                execution_time = time.time() - start_time
                
                if results:
                    if method['detail'] == 0:
                        # Paragraph mode - results ist direkt der Text
                        text = results.strip() if isinstance(results, str) else str(results).strip()
                        confidence = 0.7  # Default confidence für paragraph mode
                    else:
                        # Detail mode - results ist Liste von (bbox, text, conf)
                        best = max(results, key=lambda x: x[2])
                        text = best[1].strip()
                        confidence = best[2]
                    
                    if text:  # Nur nicht-leere Texte verarbeiten
                        # KRITISCH: SmartOCRValidator mit korrigierter Sonderzeichen-Filterung
                        method_name = f"{method['name']}_img{img_idx}"
                        ocr_result = validator.process_ocr_result(text, confidence, method_name, quality_score)
                        
                        ocr_candidates.append({
                            'ocr_result': ocr_result,
                            'execution_time': execution_time,
                            'original_text': text,
                            'original_confidence': confidence
                        })
                        
            except Exception as e:
                print(f"OCR Fehler bei {method['name']}: {e}")
                continue
    
    # Bestes Ergebnis auswählen basierend auf final_score
    if not ocr_candidates:
        return "", 0.0, "no_results", methods_used
    
    # Sortiere nach final_score (höchster zuerst)
    best_candidate = max(ocr_candidates, key=lambda x: x['ocr_result'].final_score)
    best_ocr_result = best_candidate['ocr_result']
    
    # Speichere schwierige Fälle für Analyse
    if best_ocr_result.final_score < 0.5:
        save_difficult_cases_enhanced(crop, ocr_candidates)
    
    # Performance Logging mit erweiterten Informationen
    log_ocr_performance_enhanced(best_ocr_result, best_candidate['execution_time'])
    
    # Debug-Output für Entwicklung
    validation_summary = validator.get_validation_summary(best_ocr_result)
    print(f"OCR-Validierung: {validation_summary}")
    
    # WICHTIG: corrected_text wird zurückgegeben - jetzt OHNE Sonderzeichen!
    return (
        best_ocr_result.corrected_text,  # <- Hier werden die bereinigten Texte zurückgegeben
        best_ocr_result.confidence, 
        best_ocr_result.method,
        methods_used
    )


def save_difficult_cases_enhanced(crop, ocr_candidates, score_threshold=0.5):
    """Erweiterte Speicherung schwieriger OCR-Fälle mit Validierungs-Details."""
    try:
        os.makedirs("difficult_cases", exist_ok=True)
        
        max_score = max([c['ocr_result'].final_score for c in ocr_candidates]) if ocr_candidates else 0
        if max_score < score_threshold:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(f"difficult_cases/{timestamp}_crop.jpg", crop)
            
            # Erweiterte Metadaten speichern
            analysis_data = {
                'timestamp': timestamp,
                'max_final_score': max_score,
                'candidates_count': len(ocr_candidates),
                'candidates': []
            }
            
            for candidate in ocr_candidates:
                ocr_result = candidate['ocr_result']
                candidate_data = {
                    'original_text': candidate['original_text'],
                    'corrected_text': ocr_result.corrected_text,
                    'text_type': ocr_result.text_type.value,
                    'confidence': ocr_result.confidence,
                    'format_confidence': ocr_result.format_confidence,
                    'final_score': ocr_result.final_score,
                    'method': ocr_result.method,
                    'validation_details': ocr_result.validation_details
                }
                analysis_data['candidates'].append(candidate_data)
            
            with open(f"difficult_cases/{timestamp}_analysis.json", "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)
                
    except Exception as e:
        print(f"Fehler beim Speichern schwieriger Fälle: {e}")


def log_ocr_performance_enhanced(ocr_result: OCRResult, execution_time: float):
    """Erweiterte OCR-Performance-Protokollierung."""
    try:
        log_entry = {
            "timestamp": time.time(),
            "original_text": ocr_result.text,
            "corrected_text": ocr_result.corrected_text,
            "text_type": ocr_result.text_type.value,
            "confidence": ocr_result.confidence,
            "format_confidence": ocr_result.format_confidence,
            "final_score": ocr_result.final_score,
            "method": ocr_result.method,
            "execution_time": execution_time,
            "quality_score": ocr_result.quality_score,
            "validation_details": ocr_result.validation_details,
            "text_length": len(ocr_result.corrected_text) if ocr_result.corrected_text else 0
        }
        
        os.makedirs("logs", exist_ok=True)
        with open("logs/ocr_performance.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Fehler beim erweiterten OCR-Performance Logging: {e}")


class MultiFrameOCRTracker:
    """Multi-Frame-Tracking für konsistente OCR-Ergebnisse mit SmartOCRValidator."""
    
    def __init__(self, max_frame_history=5, commercial_licenses=None):
        self.max_frame_history = max_frame_history
        self.detections = defaultdict(lambda: deque(maxlen=max_frame_history))
        self.validator = SmartOCRValidator(commercial_licenses)
    
    def add_detection(self, track_id, text, confidence, method):
        """Füge eine neue OCR-Erkennung hinzu mit Validierung."""
        if text:  # Nur nicht-leere Texte hinzufügen
            # Validiere die Erkennung
            ocr_result = self.validator.process_ocr_result(text, confidence, method, 150.0)
            
            detection_entry = {
                'ocr_result': ocr_result,
                'timestamp': time.time()
            }
            
            self.detections[track_id].append(detection_entry)
    
    def get_best_result(self, track_id):
        """Hole das beste Ergebnis für eine Track-ID basierend auf SmartOCRValidator-Scores."""
        if track_id not in self.detections or not self.detections[track_id]:
            return "", 0.0, "no_data"
        
        detections = list(self.detections[track_id])
        
        # Wenn nur eine Erkennung vorhanden
        if len(detections) == 1:
            ocr_result = detections[0]['ocr_result']
            return ocr_result.corrected_text, ocr_result.confidence, ocr_result.method
        
        # Konsensus-Algorithmus basierend auf SmartOCRValidator-Scores
        text_groups = defaultdict(list)
        for detection in detections:
            ocr_result = detection['ocr_result']
            text_groups[ocr_result.corrected_text].append(detection)
        
        # Bewerte jede Text-Gruppe
        best_text = ""
        best_confidence = 0.0
        best_method = ""
        best_score = 0.0
        
        for text, group_detections in text_groups.items():
            # Gewichteter Score: Häufigkeit + durchschnittlicher final_score
            frequency_weight = len(group_detections) / len(detections)
            avg_final_score = sum(d['ocr_result'].final_score for d in group_detections) / len(group_detections)
            avg_confidence = sum(d['ocr_result'].confidence for d in group_detections) / len(group_detections)
            
            # Kombinierter Konsensus-Score
            consensus_score = (frequency_weight * 0.4) + (avg_final_score * 0.6)
            
            if consensus_score > best_score:
                best_score = consensus_score
                best_text = text
                best_confidence = avg_confidence
                best_method = f"consensus_{len(group_detections)}frames_score{best_score:.3f}"
        
        return best_text, best_confidence, best_method
    
    def cleanup_old_tracks(self, max_age_seconds=300):
        """Entferne alte Track-IDs."""
        current_time = time.time()
        tracks_to_remove = []
        
        for track_id, detections in self.detections.items():
            if detections:
                last_detection_time = detections[-1]['timestamp']
                if current_time - last_detection_time > max_age_seconds:
                    tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            del self.detections[track_id]


def enhanced_find_license_for_boat(boat_bbox, licenses_data, raw_frame, ocr_reader, commercial_licenses=None):
    """Erweiterte Lizenz-Suche mit SmartOCRValidator."""
    best_lic = None
    best_score = 0.0
    validator = SmartOCRValidator(commercial_licenses)
    
    for lic in licenses_data:
        if is_license_completely_inside_boat(lic['bbox'], boat_bbox):
            # Verwende die verbesserte OCR mit SmartOCRValidator
            text, confidence, method, preprocessing_methods = perform_ocr_on_license_enhanced(
                raw_frame, lic['bbox'], ocr_reader, commercial_licenses
            )
            
            # Der finale Score kommt bereits aus SmartOCRValidator
            # Zusätzlich Detection-Confidence einbeziehen
            combined_score = (lic['conf'] * 0.2) + (confidence * 0.8)
            
            if combined_score > best_score:
                best_score = combined_score
                best_lic = {
                    'bbox': lic['bbox'],
                    'conf': lic['conf'],
                    'text': text,
                    'ocr_confidence': confidence,
                    'method': method,
                    'preprocessing_methods': preprocessing_methods,
                    'combined_score': combined_score
                }
    
    return best_lic


# Legacy-Funktionen für Kompatibilität (bleiben unverändert)
def correct_common_ocr_errors(text):
    """Legacy-Funktion - jetzt durch SmartOCRValidator ersetzt."""
    if not text:
        return text
    
    corrections = {
        '0': 'O', '|': 'I', '5': 'S', '1': 'I', '8': 'B', '6': 'G', '9': 'g',
        'rn': 'm', 'cl': 'd', 'vv': 'w', 'VV': 'W'
    }
    
    corrected = text
    for wrong, right in corrections.items():
        corrected = corrected.replace(wrong, right)
    
    return corrected


def validate_german_boat_name_format(text):
    """Legacy-Funktion - jetzt durch SmartOCRValidator ersetzt."""
    validator = SmartOCRValidator()
    text_type, type_conf = validator.detect_text_type(text)
    if text_type == TextType.BOAT_NAME:
        return True, type_conf
    return False, 0.0


def validate_license_plate_format(text):
    """Legacy-Funktion - jetzt durch SmartOCRValidator ersetzt."""
    validator = SmartOCRValidator()
    text_type, type_conf = validator.detect_text_type(text)
    if text_type == TextType.LICENSE_PLATE:
        return True, type_conf
    return False, 0.0


def similarity_check_with_known_licenses(text, known_licenses):
    """Legacy-Funktion - jetzt durch SmartOCRValidator ersetzt."""
    validator = SmartOCRValidator(known_licenses)
    corrected_text, similarity_score = validator.similarity_matching_enhanced(text, TextType.LICENSE_PLATE)
    return corrected_text, similarity_score


def score_ocr_result(text, confidence, method, quality_score):
    """Legacy-Funktion - jetzt durch SmartOCRValidator ersetzt."""
    validator = SmartOCRValidator()
    ocr_result = validator.process_ocr_result(text, confidence, method, quality_score)
    return ocr_result.final_score


def save_difficult_cases(crop, ocr_results, confidence_threshold=0.5):
    """Legacy-Funktion für Kompatibilität."""
    save_difficult_cases_enhanced(crop, ocr_results, confidence_threshold)


def log_ocr_performance(text, confidence, method, execution_time):
    """Legacy-Funktion für Kompatibilität."""
    # Erstelle ein einfaches OCRResult für Legacy-Unterstützung
    validator = SmartOCRValidator()
    ocr_result = validator.process_ocr_result(text, confidence, method, 150.0)
    log_ocr_performance_enhanced(ocr_result, execution_time)


def find_license_for_boat(boat_bbox, licenses_data):
    """Fallback-Funktion für Kompatibilität."""
    best_lic = None
    best_conf = 0.0
    for lic in licenses_data:
        if is_license_completely_inside_boat(lic['bbox'], boat_bbox) and lic['conf'] > best_conf:
            best_conf = lic['conf']
            best_lic = lic
    return best_lic


def perform_ocr_on_license(frame, bbox, reader):
    """Einfache Legacy-OCR-Funktion für Kompatibilität."""
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
