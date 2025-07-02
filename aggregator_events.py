import os
import time
import queue
import pandas as pd
from collections import defaultdict
from image_utils import sanitize_filename


def _choose_best_text(evt1: dict, evt2: dict):
    """Select the better OCR result between two events."""
    text1 = evt1.get("extracted_text", "") or ""
    text2 = evt2.get("extracted_text", "") or ""

    # One empty, one not -> return the non-empty
    if text1 and not text2:
        return evt1
    if text2 and not text1:
        return evt2

    # Both empty -> higher OCR confidence wins
    if not text1 and not text2:
        return evt1 if evt1.get("ocr_confidence", 0) >= evt2.get("ocr_confidence", 0) else evt2

    # Both non-empty: longer text wins, tie -> higher OCR confidence
    if len(text1) > len(text2):
        return evt1
    if len(text2) > len(text1):
        return evt2
    return evt1 if evt1.get("ocr_confidence", 0) >= evt2.get("ocr_confidence", 0) else evt2


def aggregator_worker(
    event_queue,
    location,
    stop_event,
    daily_counter=None,
    daily_lock=None,
    flush_interval=120,
    timeout_minutes=20,
):
    """Aggregate events from cameras with Camera 2 as primary detection.

    Parameters
    ----------
    event_queue : mp.Queue
        Queue with raw events from the tracking workers.
    location : str
        Name of the current location (original name with umlauts).
    stop_event : mp.Event
        Signals when the process should terminate.
    daily_counter : multiprocessing.Value, optional
        Shared counter for boats that completely left the lock.
    daily_lock : multiprocessing.Lock, optional
        Synchronization primitive for updating ``daily_counter``.
    flush_interval : int, optional
        Seconds between writing accumulated CSV rows to disk.
    timeout_minutes : int, optional
        Minutes to wait for exit camera before creating CSV without license match.
    """
    # Use original location name for directory paths
    save_dir = os.path.join("saved_data", location, "csv")
    os.makedirs(save_dir, exist_ok=True)

    # Events waiting for completion: {(class_id, direction, timestamp_rounded): event_data}
    pending_events = {}
    csv_rows = []
    last_flush = time.time()
    timeout_seconds = timeout_minutes * 60

    def _get_time_bucket(timestamp_str, bucket_minutes=5):
        """Round timestamp to nearest bucket for matching."""
        try:
            ts = time.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            epoch = time.mktime(ts)
            bucket_epoch = (epoch // (bucket_minutes * 60)) * (bucket_minutes * 60)
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(bucket_epoch))
        except:
            return timestamp_str

    def flush_rows():
        nonlocal csv_rows, last_flush
        if not csv_rows:
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        # Only sanitize the timestamp and filename parts, preserve location
        csv_path = os.path.join(
            save_dir,
            f"live_{sanitize_filename(location)}_{ts}_aggregated.csv",
        )
        pd.DataFrame(csv_rows).to_csv(csv_path, index=False, encoding="utf-8")
        print(f"Aggregator: Saved {len(csv_rows)} records to {csv_path}")
        csv_rows.clear()
        last_flush = time.time()

    def create_final_csv_row(cam2_event, exit_event=None):
        """Create final CSV row from camera 2 event and optional exit event."""
        # Choose best license text if exit event exists
        if exit_event:
            best_evt = _choose_best_text(cam2_event, exit_event)
            confidence = max(cam2_event.get("confidence", 0), exit_event.get("confidence", 0))
            # Mark as paired
            paired_info = f"paired_with_cam{exit_event.get('camera')}"
        else:
            best_evt = cam2_event
            confidence = cam2_event.get("confidence", 0)
            paired_info = "timeout_no_exit_match"

        return {
            "track_id": cam2_event.get("track_id"),
            "class_id": cam2_event.get("class_id"),
            "class_name": cam2_event.get("class_name"),
            "direction": cam2_event.get("direction"),
            "entry_timestamp": cam2_event.get("timestamp"),
            "exit_timestamp": exit_event.get("timestamp") if exit_event else "timeout",
            "location": location,  # Original location name
            "extracted_text": best_evt.get("extracted_text", ""),
            "identified_licence_number": best_evt.get("identified_licence_number", "no"),
            "ocr_confidence": best_evt.get("ocr_confidence", 0),
            "confidence": confidence,
            "pairing_status": paired_info,
        }

    def check_timeouts():
        """Check for timed out events and create CSV rows."""
        current_time = time.time()
        timed_out_keys = []
        
        for key, event_data in pending_events.items():
            event_time_str = event_data.get("timestamp")
            try:
                event_time = time.mktime(time.strptime(event_time_str, '%Y-%m-%d %H:%M:%S'))
                if current_time - event_time > timeout_seconds:
                    timed_out_keys.append(key)
            except:
                # If we can't parse the time, remove it anyway
                timed_out_keys.append(key)
        
        for key in timed_out_keys:
            event_data = pending_events.pop(key)
            print(f"Aggregator: Timeout for event {key}, creating CSV without exit match")
            row = create_final_csv_row(event_data)
            csv_rows.append(row)
            
            # Increment daily counter for timed out boats
            if daily_counter is not None and daily_lock is not None:
                with daily_lock:
                    daily_counter.value += 1

    while not stop_event.is_set() or not event_queue.empty() or pending_events:
        try:
            evt = event_queue.get(timeout=1)
        except queue.Empty:
            evt = None

        if evt:
            cam = evt.get("camera")
            direction = evt.get("direction")
            class_id = evt.get("class_id")
            timestamp = evt.get("timestamp")
            time_bucket = _get_time_bucket(timestamp)

            print(f"Aggregator: Received event - Cam{cam}, Direction: {direction}, Class: {class_id}")

            if cam == 2:
                # Primary detection camera - start new tracking
                # Key for matching: (class_id, direction, time_bucket)
                event_key = (class_id, direction, time_bucket)
                pending_events[event_key] = evt
                print(f"Aggregator: Added pending event with key {event_key}")
                
            elif cam in [1, 3]:
                # Exit cameras - try to match with pending camera 2 events
                expected_direction = direction  # Use the same direction logic
                
                # Look for matching pending event
                matching_key = None
                for key in pending_events.keys():
                    key_class, key_direction, key_time = key
                    if (key_class == class_id and 
                        key_direction == expected_direction and
                        abs(time.mktime(time.strptime(timestamp, '%Y-%m-%d %H:%M:%S')) - 
                            time.mktime(time.strptime(pending_events[key].get("timestamp"), '%Y-%m-%d %H:%M:%S'))) < timeout_seconds):
                        matching_key = key
                        break
                
                if matching_key:
                    # Found match - create final CSV row
                    cam2_event = pending_events.pop(matching_key)
                    print(f"Aggregator: Found match for {matching_key} with cam{cam}")
                    
                    row = create_final_csv_row(cam2_event, evt)
                    csv_rows.append(row)
                    
                    # Increment daily counter for completed boats
                    if daily_counter is not None and daily_lock is not None:
                        with daily_lock:
                            daily_counter.value += 1
                else:
                    print(f"Aggregator: No matching pending event found for cam{cam} event")

        # Check for timeouts periodically
        check_timeouts()

        # Flush CSV if needed
        if time.time() - last_flush >= flush_interval and csv_rows:
            flush_rows()

    # Final cleanup - process any remaining pending events as timeouts
    for event_data in pending_events.values():
        row = create_final_csv_row(event_data)
        csv_rows.append(row)
    
    flush_rows()
    print("Aggregator: Finished processing all events")
