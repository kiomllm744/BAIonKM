#!/usr/bin/env python3
"""
Download the database file from Google Drive if it doesn't exist.
Run this script once after deployment to set up the database.
"""
import os
import requests

# Google Drive file ID - UPDATE THIS with your actual file ID
# Get from the sharing link: https://drive.google.com/file/d/FILE_ID_HERE/view
GDRIVE_FILE_ID = "1VuGmIvan8cXLai2LvzF1WUwI5FqTKtrB"

DB_PATH = os.path.join(os.path.dirname(__file__), "diseaseportal.db")

def download_from_gdrive(file_id: str, destination: str):
    """Download a file from Google Drive."""
    print(f"Downloading database to {destination}...")
    
    # Google Drive direct download URL
    url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
    
    session = requests.Session()
    response = session.get(url, stream=True)
    
    # Handle large file confirmation
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            url = f"https://drive.google.com/uc?export=download&confirm={value}&id={file_id}"
            response = session.get(url, stream=True)
            break
    
    # Save the file
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(destination, 'wb') as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    percent = (downloaded / total_size) * 100
                    print(f"\rProgress: {percent:.1f}%", end="")
    
    print(f"\nDownload complete! Size: {os.path.getsize(destination) / (1024*1024):.1f} MB")

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        print(f"Database already exists at {DB_PATH}")
        size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        print(f"Size: {size_mb:.1f} MB")
    else:
        if GDRIVE_FILE_ID == "YOUR_GOOGLE_DRIVE_FILE_ID_HERE":
            print("ERROR: Please update GDRIVE_FILE_ID in this script!")
            print("1. Upload diseaseportal.db to Google Drive")
            print("2. Get the shareable link")
            print("3. Copy the file ID from the URL")
            print("   Example: https://drive.google.com/file/d/ABC123XYZ/view")
            print("   File ID would be: ABC123XYZ")
        else:
            download_from_gdrive(GDRIVE_FILE_ID, DB_PATH)
