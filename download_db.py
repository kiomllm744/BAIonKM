#!/usr/bin/env python3
"""
Download the database file from Google Drive if it doesn't exist.
Run this script once after deployment to set up the database.
"""
import os
import sys
import requests

# Google Drive file ID - UPDATE THIS with your actual file ID
# Get from the sharing link: https://drive.google.com/file/d/FILE_ID_HERE/view
GDRIVE_FILE_ID = "1VuGmIvan8cXLai2LvzF1WUwI5FqTKtrB"

DB_PATH = os.path.join(os.path.dirname(__file__), "diseaseportal.db")

# A valid DB is ~37 MB. Anything well under this is an empty/partial/HTML-error
# file (e.g. an empty SQLite created by the app, or a Google Drive error page),
# which must not be allowed to shadow the real database.
MIN_DB_BYTES = 5 * 1024 * 1024  # 5 MB floor
SQLITE_MAGIC = b"SQLite format 3\x00"

# Honour the same SSL toggle as the rest of the app (institutional proxies).
VERIFY_SSL = os.environ.get("EXTERNAL_API_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
HTTP_TIMEOUT = (15, 120)  # (connect, read) seconds


def _looks_like_sqlite(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(16) == SQLITE_MAGIC
    except OSError:
        return False


def is_valid_db(path: str) -> bool:
    """A usable DB exists, is large enough, and has the SQLite header."""
    return (
        os.path.exists(path)
        and os.path.getsize(path) >= MIN_DB_BYTES
        and _looks_like_sqlite(path)
    )


def download_from_gdrive(file_id: str, destination: str):
    """Download a file from Google Drive into `destination` atomically."""
    print(f"Downloading database to {destination}...")
    url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"

    session = requests.Session()
    response = session.get(url, stream=True, timeout=HTTP_TIMEOUT, verify=VERIFY_SSL)
    response.raise_for_status()

    # Handle large-file confirmation token
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            url = f"https://drive.google.com/uc?export=download&confirm={value}&id={file_id}"
            response = session.get(url, stream=True, timeout=HTTP_TIMEOUT, verify=VERIFY_SSL)
            response.raise_for_status()
            break

    # If Drive returns an HTML page (quota exceeded, file removed, login wall),
    # it is NOT the database -- fail instead of writing a corrupt file.
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        raise RuntimeError(
            "Google Drive returned an HTML page, not the database file "
            "(quota exceeded, file unshared, or wrong file ID)."
        )

    tmp = destination + ".tmp"
    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0
    try:
        with open(tmp, "wb") as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        print(f"\rProgress: {downloaded / total_size * 100:.1f}%", end="")
        print()

        # Validate the downloaded file before letting it replace anything.
        if downloaded < MIN_DB_BYTES or not _looks_like_sqlite(tmp):
            raise RuntimeError(
                f"Downloaded file is invalid ({downloaded / (1024*1024):.2f} MB, "
                f"sqlite header={_looks_like_sqlite(tmp)}). Aborting."
            )

        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    print(f"Download complete! Size: {os.path.getsize(destination) / (1024*1024):.1f} MB")


if __name__ == "__main__":
    if is_valid_db(DB_PATH):
        size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        print(f"Database already exists and looks valid at {DB_PATH} ({size_mb:.1f} MB)")
    else:
        if os.path.exists(DB_PATH):
            # An existing-but-invalid file (empty/partial) would otherwise block the
            # download forever -- remove it so we can fetch a clean copy.
            print(f"Existing DB at {DB_PATH} is invalid/too small; re-downloading.")
            os.remove(DB_PATH)
        try:
            download_from_gdrive(GDRIVE_FILE_ID, DB_PATH)
        except Exception as exc:
            print(f"ERROR: database download failed: {exc}", file=sys.stderr)
            sys.exit(1)
