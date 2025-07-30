import os
import shutil
import datetime
from azure.storage.blob import BlobServiceClient
from datetime import timezone
import sys

# Import sanitize_filename for consistent directory naming (but don't use it for location names)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from image_utils import sanitize_filename

# Using Windows version Azure Storage Account Key
AZURE_STORAGE_CONNECTION_STRING = (
    "XXXX"
)
CONTAINER_NAME = "wsv3"

def get_active_location():
    """Load the active location preserving original name with umlauts."""
    try:
        with open("active_location.txt", "r", encoding="utf-8") as f:
            location = f.read().strip()
        return location  # Return original location name without sanitization
    except FileNotFoundError:
        print("active_location.txt not found, using default location")
        return "default"

# Get original location name for consistent directory names
LOCATION = get_active_location()

local_directory_csv = f"saved_data/{LOCATION}/csv"
local_directory_events = f"saved_data/{LOCATION}/events"

# Backup directories
backup_directory_csv = f"saved_data/{LOCATION}/csv_backup"
backup_directory_events = f"saved_data/{LOCATION}/events_backup"

# Updated blob directories according to requirements
blob_directory_csv = "CSV_output/Yolo_Multi/"
blob_directory_events = "model-inputs/Yolo-Multi/"


def list_existing_blobs(connection_string, container_name, blob_directory):
    """Fetches all blob names in a specific directory on Azure."""
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=blob_directory)
    return set(os.path.basename(blob.name) for blob in blobs)


def list_existing_event_blobs(connection_string, container_name, blob_directory):
    """Fetches all event directory names and their files from Azure."""
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=blob_directory)
    
    event_files = {}
    for blob in blobs:
        # Extract event name and filename from blob path
        # Format: "model-inputs/Yolo-Multi/event_name/filename"
        blob_path = blob.name
        if blob_path.count('/') >= 2:
            parts = blob_path.split('/')
            event_name = parts[2]  # event directory name
            filename = parts[3] if len(parts) > 3 else ""
            
            if event_name not in event_files:
                event_files[event_name] = set()
            if filename:
                event_files[event_name].add(filename)
    
    return event_files


def upload_to_azure_blob(connection_string, container_name, blob_name, file_path):
    """Upload file to Azure Blob with overwrite=False (Windows version strategy)."""
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)
    
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=False)
    print(f"[{datetime.datetime.now()}] Uploaded: {file_path} → {blob_name}")


def process_csv_files(local_directory, blob_directory, backup_directory, existing_blobs):
    """Process CSV files using Windows version strategy."""
    if not os.path.exists(local_directory):
        print(f"CSV directory {local_directory} does not exist, skipping...")
        return
    
    os.makedirs(backup_directory, exist_ok=True)
    
    for filename in os.listdir(local_directory):
        if not filename.endswith(".csv"):
            continue
        
        local_path = os.path.join(local_directory, filename)
        if not os.path.isfile(local_path):
            continue
        
        if filename in existing_blobs:
            print(f"[{datetime.datetime.now()}] Skipping {filename} - already exists in blob")
            continue  # Already uploaded

        blob_name = blob_directory + filename
        try:
            upload_to_azure_blob(
                AZURE_STORAGE_CONNECTION_STRING,
                CONTAINER_NAME,
                blob_name,
                local_path,
            )
            # Move to backup folder
            backup_path = os.path.join(backup_directory, filename)
            shutil.move(local_path, backup_path)
            print(f"[{datetime.datetime.now()}] Moved {filename} to backup")
        except Exception as ex:
            print(f"[{datetime.datetime.now()}] Failed to upload {local_path}: {ex}")


def process_event_directories(local_directory, blob_directory, backup_directory, existing_event_files):
    """Process event directories using Windows version strategy."""
    if not os.path.exists(local_directory):
        print(f"Events directory {local_directory} does not exist, skipping...")
        return
    
    os.makedirs(backup_directory, exist_ok=True)
    
    for event_dir in os.listdir(local_directory):
        event_path = os.path.join(local_directory, event_dir)
        if not os.path.isdir(event_path):
            continue
        
        event_name = os.path.basename(event_path)
        existing_files_in_event = existing_event_files.get(event_name, set())
        
        # Check if any new files exist in this event directory
        new_files_found = False
        files_to_upload = []
        
        for filename in os.listdir(event_path):
            file_path = os.path.join(event_path, filename)
            if os.path.isfile(file_path) and filename not in existing_files_in_event:
                files_to_upload.append((filename, file_path))
                new_files_found = True
        
        if not new_files_found:
            print(f"[{datetime.datetime.now()}] Skipping event '{event_name}' - all files already exist in blob")
            continue
        
        # Upload new files
        uploaded_files = 0
        event_backup_dir = os.path.join(backup_directory, event_name)
        os.makedirs(event_backup_dir, exist_ok=True)
        
        print(f"[{datetime.datetime.now()}] Processing event directory: {event_name}")
        
        for filename, file_path in files_to_upload:
            blob_name = f"{blob_directory}{event_name}/{filename}"
            try:
                upload_to_azure_blob(
                    AZURE_STORAGE_CONNECTION_STRING,
                    CONTAINER_NAME,
                    blob_name,
                    file_path
                )
                # Move to backup folder
                backup_file_path = os.path.join(event_backup_dir, filename)
                shutil.move(file_path, backup_file_path)
                uploaded_files += 1
            except Exception as ex:
                print(f"[{datetime.datetime.now()}] Failed to upload {file_path}: {ex}")
        
        print(f"[{datetime.datetime.now()}] Uploaded {uploaded_files} new files from event '{event_name}'")
        
        # If event directory is now empty, move it to backup
        if not os.listdir(event_path):
            try:
                os.rmdir(event_path)
                print(f"[{datetime.datetime.now()}] Removed empty event directory: {event_path}")
            except OSError:
                print(f"[{datetime.datetime.now()}] Could not remove event directory: {event_path}")


def main():
    try:
        print(f"[{datetime.datetime.now()}] Starting upload script...")
        print(f"Using location: {LOCATION}")
        print(f"CSV directory: {local_directory_csv}")
        print(f"Events directory: {local_directory_events}")
        
        # List existing blobs for CSV files
        print(f"[{datetime.datetime.now()}] Checking existing CSV blobs...")
        csv_blobs = list_existing_blobs(
            AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME, blob_directory_csv
        )
        print(f"[{datetime.datetime.now()}] Found {len(csv_blobs)} existing CSV files in blob")
        
        # List existing blobs for event directories
        print(f"[{datetime.datetime.now()}] Checking existing event blobs...")
        event_blobs = list_existing_event_blobs(
            AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME, blob_directory_events
        )
        print(f"[{datetime.datetime.now()}] Found {len(event_blobs)} existing event directories in blob")
        
        # Process CSV files
        process_csv_files(
            local_directory_csv, blob_directory_csv, backup_directory_csv, csv_blobs
        )
        
        # Process Event directories
        process_event_directories(
            local_directory_events, blob_directory_events, backup_directory_events, event_blobs
        )
        
        print(f"[{datetime.datetime.now()}] Upload script finished.")
        
    except Exception as ex:
        print(f"[{datetime.datetime.now()}] Error in main process: {ex}")


if __name__ == "__main__":
    main()
