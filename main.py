import os
import multiprocessing as mp

from config_utils import (
    load_active_location,
    load_config,
    load_commercial_licenses,
)
from image_utils import sanitize_filename
from preview import preview_worker
from tracking import track_worker
from aggregator_events import aggregator_worker

# Ensure UDP transport for RTSP
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"


def main():
    location = load_active_location()
    cfg = load_config(location)
    commercial = load_commercial_licenses()

    # Use the location name directly from active_location.txt
    # Only apply sanitize_filename to dynamic content, not location names
    location_for_paths = location  # Keep original location name with umlauts

    manager = mp.Manager()
    daily_counter = manager.Value('i', 0)
    daily_lock = manager.Lock()
    # Shared dict für Event-Screenshots von allen Kameras
    screenshot_events = manager.dict()
    
    num_cams = len(cfg['streams'])
    queues = [mp.Queue(maxsize=2) for _ in cfg['streams']]
    event_queue = mp.Queue()
    stop_event = mp.Event()

    # Erstelle zentrale Verzeichnisse mit original location name
    base_save_dir = os.path.join("saved_data", location_for_paths)
    os.makedirs(os.path.join(base_save_dir, "csv"), exist_ok=True)
    os.makedirs(os.path.join(base_save_dir, "events"), exist_ok=True)

    print(f"Starting tracking system for location: {location}")
    print(f"Directory name: {location_for_paths}")
    print(f"Save directory: {base_save_dir}")
    print(f"Number of cameras: {num_cams}")
    print("Primary detection: Camera 2")
    print("License matching: Camera 1 & 3")

    # Preview Process
    preview = mp.Process(target=preview_worker, args=(queues, daily_counter))
    preview.start()

    # Aggregator Process with original location name
    aggregator = mp.Process(
        target=aggregator_worker,
        args=(event_queue, location_for_paths, stop_event, daily_counter, daily_lock, 120, 20),
    )
    aggregator.start()

    # Tracking Processes für alle Kameras with original location name
    procs = []
    for i, stream in enumerate(cfg['streams'], start=1):
        print(f"Starting tracking worker for Camera {i}: {stream['url']}")
        p = mp.Process(
            target=track_worker,
            args=(
                i,
                stream['url'],
                location_for_paths,  # Original location name with umlauts
                stream['line1'],
                stream['line2'],
                stream['orientation'],
                commercial,
                queues[i - 1],
                event_queue,
                screenshot_events,
                num_cams,
                daily_counter,
                daily_lock,
            ),
        )
        p.start()
        procs.append(p)

    print("All processes started. Waiting for completion...")

    try:
        # Warte auf alle Tracking-Prozesse
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        print("Shutdown requested...")
        for p in procs:
            p.terminate()

    # Stoppe Preview
    preview.terminate()
    preview.join()

    # Stoppe Aggregator
    stop_event.set()
    aggregator.join()

    print("All processes terminated. System shutdown complete.")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
