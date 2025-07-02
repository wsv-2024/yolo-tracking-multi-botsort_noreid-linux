import os
import time
import cv2
import torch
import easyocr
import pandas as pd
import multiprocessing as mp

from ultralytics import YOLO

from config_utils import get_global_class_colors
from image_utils import (
    sanitize_filename, 
    perform_ocr_on_license_enhanced, 
    enhanced_find_license_for_boat,
    MultiFrameOCRTracker,
    calculate_frame_quality,
    get_adaptive_ocr_params
)


def track_worker(
    cam_idx: int,
    stream_url: str,
    location: str,
    line1: int,
    line2: int,
    orientation: str,
    commercial_licenses: set,
    q: mp.Queue,
    event_queue: mp.Queue,
    screenshot_events: dict,
    num_cams: int,
    daily_counter: mp.Value,
    daily_lock: mp.Lock,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    det_model = YOLO("best.pt").to(device)
    ocr_reader = easyocr.Reader(["en", "de"], gpu=torch.cuda.is_available())
    
    # Globale Farbverwaltung verwenden - jetzt konsistent über alle Streams
    global_color_mapper = get_global_class_colors()
    
    print(f"Track Worker {cam_idx}: Globale Farbverwaltung initialisiert")
    print(f"Track Worker {cam_idx}: Bereits definierte Farben: {list(global_color_mapper.get_all_known_colors().keys())}")

    # Multi-Frame OCR Tracker initialisieren
    ocr_tracker = MultiFrameOCRTracker(max_frame_history=5)

    # Use original location name for directory paths
    event_base_dir = os.path.join("saved_data", location, "events")
    os.makedirs(event_base_dir, exist_ok=True)

    def create_event_screenshots_for_all_cameras(event_id, all_camera_frames):
        """Create screenshots and YOLO labels for all cameras for a specific event."""
        try:
            dir_path = os.path.join(event_base_dir, event_id)
            os.makedirs(dir_path, exist_ok=True)

            success_count = 0
            for camera_id, frame_data in all_camera_frames.items():
                frame = frame_data.get('frame')
                tracked_objects = frame_data.get('objects', [])
                
                if frame is None:
                    print(f"Track Worker {cam_idx}: Kein Frame für Kamera {camera_id} verfügbar")
                    continue
                
                base_name = f"{event_id}_camera{camera_id}"
                img_path = os.path.join(dir_path, base_name + ".jpg")
                txt_path = os.path.join(dir_path, base_name + ".txt")

                # Speichere das Bild
                cv2.imwrite(img_path, frame)
                print(f"Track Worker {cam_idx}: Event-Screenshot gespeichert: {img_path}")

                # Erstelle YOLO Labels
                lines = []
                h, w, _ = frame.shape
                
                for obj in tracked_objects:
                    try:
                        x1, y1, x2, y2 = obj['bbox']
                        cls_id = obj['cls_id']
                        
                        # Berechne normalisierte YOLO-Koordinaten
                        cx = ((x1 + x2) / 2) / w
                        cy = ((y1 + y2) / 2) / h
                        bw = (x2 - x1) / w
                        bh = (y2 - y1) / h
                        
                        # Validiere Koordinaten
                        if 0 <= cx <= 1 and 0 <= cy <= 1 and 0 < bw <= 1 and 0 < bh <= 1:
                            line = f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"
                            lines.append(line)
                        
                    except Exception as obj_e:
                        print(f"Track Worker {cam_idx}: Fehler bei getrackte Objekt: {obj_e}")
                        continue

                # Schreibe die .txt-Datei
                with open(txt_path, "w", encoding="utf-8") as f:
                    if lines:
                        f.write("\n".join(lines))
                        print(f"Track Worker {cam_idx}: {len(lines)} Objekte in {txt_path} gespeichert")
                    else:
                        f.write("")  # Leere Datei erstellen
                        print(f"Track Worker {cam_idx}: Leere Label-Datei erstellt: {txt_path}")

                if os.path.exists(txt_path):
                    success_count += 1

            print(f"Track Worker {cam_idx}: Event-Screenshots erstellt für {success_count}/{len(all_camera_frames)} Kameras")
            return success_count > 0

        except Exception as e:
            print(f"Track Worker {cam_idx}: Fehler beim Event-Screenshot {event_id}: {e}")
            import traceback
            print(f"Track Worker {cam_idx}: Detaillierter Fehler: {traceback.format_exc()}")
            return False

    # FPS tracking
    fps_start = time.time()
    fps_frames = 0
    fps_val = 0.0

    track_info = {}
    
    # OCR-Konfiguration laden
    min_frame_quality = 100.0  # Aus config.ini
    max_ocr_attempts = 3       # Aus config.ini
    min_confidence = 0.3       # Aus config.ini

    print(f"Track Worker {cam_idx}: Initialisiere YOLO stream...")

    try:
        stream = det_model.track(
            source=stream_url,
            tracker="botsort.yaml",
            conf=0.5,
            show=False,
            stream=True,
            imgsz=640,
            device=device,
        )
    except Exception as e:
        print(f"Track Worker {cam_idx}: Fehler beim Verbinden mit Stream {stream_url}: {e}")
        return

    print(f"Track Worker {cam_idx}: Stream gestartet, beginne Verarbeitung...")

    # Cleanup Timer für alte OCR-Tracks
    last_cleanup = time.time()

    try:
        for result in stream:
            if result is None or result.boxes is None:
                continue

            raw_frame = result.orig_img.copy()
            disp_frame = raw_frame.copy()
            h, w, _ = raw_frame.shape

            fps_frames += 1
            now_f = time.time()
            if now_f - fps_start >= 1.0:
                fps_val = fps_frames / (now_f - fps_start)
                fps_frames = 0
                fps_start = now_f

            # Cleanup alte OCR-Tracks alle 60 Sekunden
            if now_f - last_cleanup > 60:
                ocr_tracker.cleanup_old_tracks()
                last_cleanup = now_f

            if orientation == "vertical":
                cv2.line(disp_frame, (line1, 0), (line1, h), (0, 255, 255), 2)
                cv2.line(disp_frame, (line2, 0), (line2, h), (0, 0, 255), 2)
            else:
                cv2.line(disp_frame, (0, line1), (w, line1), (0, 255, 255), 2)
                cv2.line(disp_frame, (0, line2), (w, line2), (0, 0, 255), 2)

            # Sammle alle Objekte in diesem Frame
            current_frame_objects = []
            boats = []
            licenses = []
            
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                tid = int(box.id.item()) if box.id is not None else None
                cls_id = int(box.cls[0])
                class_name = det_model.names.get(cls_id, 'unknown')
                conf_score = float(box.conf[0])
                bbox = (int(x1), int(y1), int(x2), int(y2))
                
                # Füge zu aktuellen Frame-Objekten hinzu
                current_frame_objects.append({
                    'bbox': bbox,
                    'cls_id': cls_id,
                    'class_name': class_name,
                    'conf': conf_score,
                    'tid': tid
                })
                
                # Label-Erstellung - ID zuerst, dann Bootstyp, dann Confidence
                if tid is not None:
                    label = f"ID:{tid} {class_name} {conf_score:.2f}"
                else:
                    label = f"{class_name} {conf_score:.2f}"
                
                # ZENTRALE FARBZUWEISUNG - Konsistent über alle Streams
                box_color = global_color_mapper.get_color(class_name)
                
                # Textfarbe: Weiß für bessere Lesbarkeit auf farbigem Hintergrund
                text_color = (255, 255, 255)  # Weiß
                
                cv2.rectangle(disp_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), box_color, 2)
                
                # Textgröße berechnen
                (text_width, text_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
                )
                
                # Position für Text und Hintergrund-Box
                text_x = bbox[0]
                text_y = max(text_height + 5, bbox[1] - 5)
                
                # Farbiger Hintergrund passend zum Rahmen für bessere Lesbarkeit
                padding = 2
                background_color = box_color
                cv2.rectangle(
                    disp_frame,
                    (text_x - padding, text_y - text_height - padding),
                    (text_x + text_width + padding, text_y + baseline + padding),
                    background_color,  # Farbiger Hintergrund passend zum Rahmen
                    -1  # Gefüllt
                )
                
                # Weißen Text über die farbige Box zeichnen
                cv2.putText(
                    disp_frame,
                    label,
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    text_color,
                    2,
                )

                # Erweiterte OCR-Verarbeitung für Lizenzen
                if class_name == 'licence':
                    # Prüfe Bildqualität vor OCR
                    crop_for_quality = raw_frame[bbox[1]:bbox[3], bbox[0]:bbox[2]]
                    quality_score = calculate_frame_quality(crop_for_quality)
                    
                    if quality_score > min_frame_quality:
                        # Verwende verbesserte OCR
                        text, ocr_conf, method, preprocessing_methods = perform_ocr_on_license_enhanced(
                            raw_frame, bbox, ocr_reader, commercial_licenses, min_frame_quality
                        )
                        
                        licenses.append({
                            'bbox': bbox, 
                            'text': text, 
                            'conf': ocr_conf,
                            'method': method,
                            'quality_score': quality_score,
                            'preprocessing_methods': preprocessing_methods
                        })
                        
                        # Erweiterte Visualisierung für OCR-Ergebnisse - auf 2 Stellen begrenzt
                        if text and ocr_conf > min_confidence:
                            ocr_label = f"OCR: {text} ({ocr_conf:.2f})"
                            cv2.putText(
                                disp_frame,
                                ocr_label,
                                (bbox[0], bbox[3] + 15),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.4,
                                (0, 255, 0),  # Grün für erfolgreiche OCR
                                1,
                            )
                    else:
                        # Niedrige Qualität - markiere als problematisch
                        licenses.append({
                            'bbox': bbox, 
                            'text': '', 
                            'conf': 0.0,
                            'method': 'quality_too_low',
                            'quality_score': quality_score,
                            'preprocessing_methods': []
                        })
                        
                        cv2.putText(
                            disp_frame,
                            f"Low Quality: {quality_score:.1f}",
                            (bbox[0], bbox[3] + 15),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.4,
                            (0, 0, 255),  # Rot für schlechte Qualität
                            1,
                        )
                else:
                    boats.append({
                        'bbox': bbox,
                        'tid': tid,
                        'cls_id': cls_id,
                        'class_name': class_name,
                        'conf': conf_score,
                    })

            # Aktuellen Frame in shared dict speichern für Event-Screenshots
            screenshot_events[cam_idx] = {
                'frame': raw_frame.copy(),
                'objects': current_frame_objects,
                'timestamp': time.time()
            }

            # Enhanced Tracking Logic für alle Kameras
            for boat in boats:
                tid = boat['tid']
                if tid is None:
                    continue
                    
                x1, y1, x2, y2 = boat['bbox']
                center_x = (x1 + x2) / 2.0
                center_y = (y1 + y2) / 2.0
                cur_pos = center_x if orientation == "vertical" else center_y
    
                # Verwende verbesserte Lizenz-Suche
                best_lic = enhanced_find_license_for_boat(
                    boat['bbox'], licenses, raw_frame, ocr_reader, commercial_licenses
                )
                
                lic_text = best_lic['text'] if best_lic else ''
                lic_conf = best_lic['ocr_confidence'] if best_lic else 0.0
                lic_method = best_lic['method'] if best_lic else 'no_license'
                identified = 'yes' if lic_text and lic_text in commercial_licenses else 'no'
    
                # Multi-Frame OCR Tracking
                if best_lic and lic_text:
                    ocr_tracker.add_detection(tid, lic_text, lic_conf, lic_method)
    
                if tid not in track_info:
                    track_info[tid] = {
                        'cls_id': boat['cls_id'],
                        'class_name': boat['class_name'],
                        'conf': boat['conf'],
                        'prev_pos': cur_pos,
                        'cross1_r': False,
                        'cross1_l': False,
                        'cross2_r': False,
                        'cross2_l': False,
                        'last_frame': raw_frame.copy(),
                        'last_box': (x1, y1, x2, y2),
                        'log': False,
                        'extracted_text': lic_text,
                        'ocr_conf': lic_conf,
                        'identified': identified,
                        'ocr_method': lic_method,
                        'frame_quality_score': best_lic.get('quality_score', 0) if best_lic else 0,
                        'preprocessing_methods': best_lic.get('preprocessing_methods', []) if best_lic else [],
                        'ocr_processing_time': 0.0,
                    }
                else:
                    tr = track_info[tid]
                    tr['last_frame'] = raw_frame.copy()
                    tr['last_box'] = (x1, y1, x2, y2)
                    if boat['conf'] > tr['conf']:
                        tr['conf'] = boat['conf']
                    
                    # Update OCR-Informationen nur bei besserer Confidence
                    if lic_conf and lic_conf > tr['ocr_conf']:
                        tr['extracted_text'] = lic_text
                        tr['ocr_conf'] = lic_conf
                        tr['identified'] = identified
                        tr['ocr_method'] = lic_method
                        if best_lic:
                            tr['frame_quality_score'] = best_lic.get('quality_score', 0)
                            tr['preprocessing_methods'] = best_lic.get('preprocessing_methods', [])
    
                tr = track_info[tid]
                prev_pos = tr['prev_pos']
                tr['prev_pos'] = cur_pos
    
                if prev_pos is not None:
                    if prev_pos <= line1 < cur_pos:
                        tr['cross1_r'] = True
                    if prev_pos >= line1 > cur_pos:
                        tr['cross1_l'] = True
                    if prev_pos <= line2 < cur_pos:
                        tr['cross2_r'] = True
                    if prev_pos >= line2 > cur_pos:
                        tr['cross2_l'] = True
    
                    crossed_r = tr['cross1_r'] and tr['cross2_r']
                    crossed_l = tr['cross1_l'] and tr['cross2_l']
    
                    if (crossed_r or crossed_l) and not tr['log']:
                        ts = time.strftime('%Y%m%d_%H%M%S')
                        event_id = f"{ts}_{sanitize_filename(tr['class_name'])}_{sanitize_filename(location)}"
                        
                        print(f"Track Worker {cam_idx}: Line-Crossing erkannt! Event: {event_id}")
                        
                        direction = (
                            'right' if orientation == 'vertical' else 'down'
                        ) if crossed_r else (
                            'left' if orientation == 'vertical' else 'up'
                        )
                        
                        # Hole finales OCR-Ergebnis aus Multi-Frame Tracking
                        final_text, final_conf, final_method = ocr_tracker.get_best_result(tid)
                        
                        # Verwende Multi-Frame Ergebnis falls verfügbar und besser
                        if final_text and final_conf > tr['ocr_conf']:
                            tr['extracted_text'] = final_text
                            tr['ocr_conf'] = final_conf
                            tr['ocr_method'] = final_method
                            tr['identified'] = 'yes' if final_text in commercial_licenses else 'no'
                        
                        # Erstelle Event-Screenshots für alle Kameras
                        all_camera_frames = {}
                        for i in range(1, num_cams + 1):
                            if i in screenshot_events:
                                frame_data = screenshot_events[i]
                                # Nur verwenden wenn Frame nicht zu alt ist (max 5 Sekunden)
                                if time.time() - frame_data.get('timestamp', 0) < 5:
                                    all_camera_frames[i] = frame_data
                        
                        if all_camera_frames:
                            success = create_event_screenshots_for_all_cameras(event_id, all_camera_frames)
                            if success:
                                print(f"Track Worker {cam_idx}: Event-Screenshots erfolgreich erstellt für {event_id}")
                            else:
                                print(f"Track Worker {cam_idx}: WARNUNG - Event-Screenshots fehlgeschlagen für {event_id}")
                        
                        # CSV-Event mit vollständiger Precision erstellen (unverändert)
                        event = {
                            'camera': cam_idx,
                            'track_id': tid,
                            'class_id': tr['cls_id'],
                            'class_name': tr['class_name'],
                            'direction': direction,
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'location': location,
                            'extracted_text': tr['extracted_text'],
                            'identified_licence_number': tr['identified'],
                            'ocr_confidence': tr['ocr_conf'],  # Vollständige Precision für CSV
                            'confidence': tr['conf'],          # Vollständige Precision für CSV
                            'ocr_method_used': tr['ocr_method'],
                            'ocr_processing_time': tr['ocr_processing_time'],
                            'frame_quality_score': tr['frame_quality_score'],
                            'preprocessing_methods': ",".join(tr['preprocessing_methods']),
                        }
                        event_queue.put(event)
                        tr['log'] = True

                        # Console-Output mit 2 Stellen für bessere Lesbarkeit
                        print(f"Track Worker {cam_idx}: Objekt {tid} geloggt - Richtung: {direction}")
                        print(f"Track Worker {cam_idx}: OCR: '{tr['extracted_text']}' (Conf: {tr['ocr_conf']:.2f}, Method: {tr['ocr_method']})")

            # Frame in die Queue für Preview schreiben
            try:
                ret, jpg = cv2.imencode('.jpg', disp_frame)
                if ret:
                    q.put_nowait({"frame": jpg.tobytes(), "fps": fps_val})
            except Exception:
                # Queue ist voll - das ist normal, ignorieren
                pass

    except Exception as e:
        print(f"Track Worker {cam_idx}: Fehler in der Hauptschleife: {e}")
        import traceback
        print(f"Track Worker {cam_idx}: Detaillierter Fehler: {traceback.format_exc()}")
    finally:
        print(f"Track Worker {cam_idx}: Beendet")
        
        # Zeige finale Farbzuweisungen für diesen Stream
        final_colors = global_color_mapper.get_all_known_colors()
        print(f"Track Worker {cam_idx}: Finale Farbzuweisungen: {final_colors}")
