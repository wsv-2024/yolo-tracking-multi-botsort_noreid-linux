import cv2
import numpy as np

def preview_worker(queues, daily_counter=None):
    """Display all camera feeds side by side in einem Fenster mit einer Titelleiste in RGB(239,239,239).

    Parameters
    ----------
    queues : list[mp.Queue]
        Queues containing JPEG-encoded frames for each stream.
    daily_counter : multiprocessing.Value, optional
        Counter, wie viele Boote heute gezählt wurden.
    """
    import queue

    window_name = "Live Preview - Alle Kameras"

    # Höhe der Leiste oberhalb der Kameraansichten, in der der gelbe Text stehen soll
    title_h = 30
    # Höhe der Infozeile über jeder Kamera (z.B. "Cam 1: 13.9 FPS")
    info_h = 30
    # Höhe jeder einzelnen Kameradarstellung (jeweils 360 px)
    cam_h = 360
    # Breite jeder Kameradarstellung (jeweils 640 px)
    cam_w = 640
    # Breite des grauen Spacers zwischen den Kamerafenstern
    spacer_w = 20

    # Rechnerisch Gesamtbreite: 3 Kameras + 2 Spacer
    total_w = cam_w * 3 + spacer_w * 2
    # Gesamtgröße des Fensters: title_h (Titelleiste) + info_h + cam_h
    total_h = title_h + info_h + cam_h

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, total_w, total_h)

    # Platzhalter für die letzten Frames + FPS
    last_frames = [np.zeros((cam_h, cam_w, 3), dtype=np.uint8) for _ in queues]
    last_fps = [0.0 for _ in queues]

    # Spacer zwischen den Kamerafenstern (hellgrau)
    spacer = np.full((info_h + cam_h, spacer_w, 3), 200, dtype=np.uint8)

    while True:
        # 1) Aus jedem Queue das neueste Frame (JPEG) holen und decodieren
        for i, q in enumerate(queues):
            try:
                item = q.get_nowait()
                if isinstance(item, dict):
                    jpg = item.get("frame")
                    last_fps[i] = item.get("fps", 0.0)
                else:
                    jpg = item
                frm = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frm is not None:
                    last_frames[i] = cv2.resize(frm, (cam_w, cam_h))
            except queue.Empty:
                # Wenn kein neues Frame verfügbar, einfach den alten behalten
                pass

        # 2) Für jedes Kamerabild eine Infozeile (schwarz) mit FPS-Label oben hinzufügen
        frames_with_info = []
        for i, frm in enumerate(last_frames):
            info = np.zeros((info_h, cam_w, 3), dtype=np.uint8)
            label = f"Cam {i + 1}: {last_fps[i]:.1f} FPS"
            cv2.putText(
                info,
                label,
                (5, info_h - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),  # Weißer Text für FPS-Label
                2,
            )
            # Infozeile oben, Kamera-Bild unten
            frames_with_info.append(np.vstack([info, frm]))

        # 3) Alle drei Frames nebeneinander mit Spacer dazwischen
        combined = np.hstack(
            [
                frames_with_info[0],
                spacer,
                frames_with_info[1],
                spacer,
                frames_with_info[2],
            ]
        )

        # 4) Tageszähler auslesen
        daily = daily_counter.value if daily_counter is not None else 0
        text = f"Heute: {daily}"

        # 5) Titelleiste in RGB(239,239,239) erstellen, darauf den gelben Text mittig zeichnen
        title_bar = np.full((title_h, combined.shape[1], 3), (239, 239, 239), dtype=np.uint8)

        # Textgröße berechnen, um horizontal zu zentrieren
        (text_w, text_h), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
        )
        text_x = (combined.shape[1] - text_w) // 2
        # Vertikaler Text-Offset innerhalb der Titelleiste (Basislinie knapp unterhalb des oberen Randes)
        text_y = title_h - 8

        # Gelb: (B=0, G=255, R=255)
        cv2.putText(
            title_bar,
            text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
        )

        # 6) Titelleiste (hellgrau) über das kombinierte Bild stapeln
        final_frame = np.vstack([title_bar, combined])

        # 7) Im Fenster anzeigen
        cv2.imshow(window_name, final_frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()
