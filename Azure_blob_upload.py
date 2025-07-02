import os
import datetime
from azure.storage.blob import BlobServiceClient
from datetime import timezone
import sys

# Import sanitize_filename for consistent directory naming (but don't use it for location names)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from image_utils import sanitize_filename

AZURE_STORAGE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=https;AccountName=wsv3storage;AccountKey=3JjCkbAaCZE18ikMLfNYOh7XRrXXk7ikUc0TNanUV8LvLCxi1+E9fJ3YPzfNcUo/"
    "x2idKQaeAhMa+AStlbSYYA==;EndpointSuffix=core.windows.net"
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

# Updated blob directories according to requirements
blob_directory_csv = "CSV_output/Yolo_Multi/"
blob_directory_events = "model-inputs/Yolo-Multi/"


def upload_to_azure_blob(connection_string, container_name, blob_name, file_path):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        blob_client = container_client.get_blob_client(blob_name)

        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        print(f"File '{file_path}' uploaded as '{blob_name}'.")
    except Exception as ex:
        print(f"Error uploading file '{file_path}': {ex}")


def extract_location(filename):
    try:
        return filename.split("_")[2]  # Annahme: '20250306_121218_Diemitz_motorboat...'
    except IndexError:
        return "unknown"


def get_latest_blob_timestamp_by_location(connection_string, container_name, blob_directory, location):
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    latest_blob_time = None

    for blob in container_client.list_blobs(name_starts_with=blob_directory):
        blob_name = os.path.basename(blob.name)
        blob_location = extract_location(blob_name)

        if blob_location == location:
            blob_time = blob.last_modified
            if latest_blob_time is None or blob_time > latest_blob_time:
                latest_blob_time = blob_time

    return latest_blob_time


def find_new_files(directory, file_extension, connection_string, container_name, blob_directory):
    new_files = []
    
    # Check if directory exists
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist, skipping...")
        return new_files

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)

        if filename.endswith(file_extension) and os.path.isfile(file_path):
            location = extract_location(filename)
            latest_blob_time = get_latest_blob_timestamp_by_location(
                connection_string, container_name, blob_directory, location
            )

            file_modified_time = datetime.datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).replace(tzinfo=timezone.utc)

            if latest_blob_time is None or file_modified_time > latest_blob_time:
                new_files.append(file_path)

    return new_files


def get_latest_event_blob_timestamp(connection_string, container_name, blob_directory, event_name):
    """Get the latest timestamp of any file in an event directory from the blob."""
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    latest_blob_time = None
    event_blob_prefix = f"{blob_directory}{event_name}/"

    for blob in container_client.list_blobs(name_starts_with=event_blob_prefix):
        blob_time = blob.last_modified
        if latest_blob_time is None or blob_time > latest_blob_time:
            latest_blob_time = blob_time

    return latest_blob_time


def get_latest_local_event_timestamp(event_dir_path):
    """Get the latest modification timestamp of any file in the local event directory."""
    latest_local_time = None
    
    for filename in os.listdir(event_dir_path):
        file_path = os.path.join(event_dir_path, filename)
        if os.path.isfile(file_path):
            file_modified_time = datetime.datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).replace(tzinfo=timezone.utc)
            
            if latest_local_time is None or file_modified_time > latest_local_time:
                latest_local_time = file_modified_time
    
    return latest_local_time


def find_new_event_directories(base_directory, connection_string, container_name, blob_directory):
    """Find new or modified event directories to upload."""
    new_events = []
    
    if not os.path.exists(base_directory):
        print(f"Events directory {base_directory} does not exist, skipping...")
        return new_events
    
    for event_dir in os.listdir(base_directory):
        event_path = os.path.join(base_directory, event_dir)
        if os.path.isdir(event_path):
            event_name = os.path.basename(event_path)
            
            # Get latest timestamp from blob
            latest_blob_time = get_latest_event_blob_timestamp(
                connection_string, container_name, blob_directory, event_name
            )
            
            # Get latest timestamp from local event directory
            latest_local_time = get_latest_local_event_timestamp(event_path)
            
            # Upload if blob doesn't exist or local files are newer
            if latest_blob_time is None or (latest_local_time and latest_local_time > latest_blob_time):
                new_events.append(event_path)
                print(f"Event '{event_name}' will be uploaded (local: {latest_local_time}, blob: {latest_blob_time})")
            else:
                print(f"Event '{event_name}' is up to date, skipping...")
    
    return new_events


def upload_event_directory(event_dir_path, connection_string, container_name, blob_base_directory):
    """Upload all files (images, txt, etc.) in an event directory."""
    event_name = os.path.basename(event_dir_path)
    uploaded_files = 0
    
    print(f"Uploading event directory: {event_name}")
    
    for filename in os.listdir(event_dir_path):
        file_path = os.path.join(event_dir_path, filename)
        if os.path.isfile(file_path):
            blob_name = f"{blob_base_directory}{event_name}/{filename}"
            upload_to_azure_blob(connection_string, container_name, blob_name, file_path)
            uploaded_files += 1
    
    print(f"Uploaded {uploaded_files} files from event '{event_name}'")


def main():
    try:
        print(f"Using location: {LOCATION}")
        print(f"CSV directory: {local_directory_csv}")
        print(f"Events directory: {local_directory_events}")
        
        # Upload CSV files
        new_csv_files = find_new_files(
            local_directory_csv, ".csv", AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME, blob_directory_csv
        )

        if new_csv_files:
            for file_path in new_csv_files:
                blob_name = blob_directory_csv + os.path.basename(file_path)
                upload_to_azure_blob(
                    AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME, blob_name, file_path
                )
        else:
            print("No new CSV files found to upload.")

        # Upload Event directories
        new_event_dirs = find_new_event_directories(
            local_directory_events, AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME, blob_directory_events
        )

        if new_event_dirs:
            for event_dir in new_event_dirs:
                upload_event_directory(
                    event_dir, AZURE_STORAGE_CONNECTION_STRING, CONTAINER_NAME, blob_directory_events
                )
        else:
            print("No new event directories found to upload.")

    except Exception as ex:
        print(f"Error in main process: {ex}")


if __name__ == "__main__":
    main()
