#!/usr/bin/env python3
"""
Download the prebuilt database (herbs + disease catalogue + ClinGen) if it is
not already present. Run once at deploy/build time.

The DB is hosted as a GitHub Release asset on the project repo (public, served
from GitHub's CDN -- reliable and auth-free). Override the source with the
DB_DOWNLOAD_URL env var if you move it elsewhere.
"""
import os
import sys
import requests

# Public GitHub Release asset (default). To publish/update it:
#   gh release create db-v1 diseaseportal.db   # first time
#   gh release upload db-v1 diseaseportal.db --clobber   # to replace later
DB_DOWNLOAD_URL = os.environ.get(
    "DB_DOWNLOAD_URL",
    "https://github.com/kiomllm744/BAIonKM/releases/download/db-v1/diseaseportal.db",
)

# In prod the DB lives on a persistent disk (DB_PATH=/var/data/diseaseportal.db);
# locally it defaults to the repo directory.
DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), "diseaseportal.db")

# A valid DB is ~37 MB. Anything well under this is an empty/partial/HTML-error
# file, which must not be allowed to shadow the real database.
MIN_DB_BYTES = 5 * 1024 * 1024  # 5 MB floor
SQLITE_MAGIC = b"SQLite format 3\x00"

VERIFY_SSL = os.environ.get("EXTERNAL_API_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
HTTP_TIMEOUT = (15, 180)  # (connect, read) seconds


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


def download_db(url: str, destination: str):
    """Download the database from `url` into `destination` atomically."""
    print(f"Downloading database from {url} ...")
    response = requests.get(url, stream=True, timeout=HTTP_TIMEOUT, verify=VERIFY_SSL)
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        raise RuntimeError(
            "Download URL returned an HTML page, not the database file "
            "(asset missing, repo private, or wrong URL)."
        )

    tmp = destination + ".tmp"
    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    try:
        with open(tmp, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"\rProgress: {downloaded / total * 100:.1f}%", end="")
        print()

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
    # Ensure the target directory exists (the persistent-disk mount, or a local dir).
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    if is_valid_db(DB_PATH):
        size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        print(f"Database already present and valid at {DB_PATH} ({size_mb:.1f} MB)")
    else:
        if os.path.exists(DB_PATH):
            print(f"Existing DB at {DB_PATH} is invalid/too small; re-downloading.")
            os.remove(DB_PATH)
        try:
            download_db(DB_DOWNLOAD_URL, DB_PATH)
        except Exception as exc:
            print(f"ERROR: database download failed: {exc}", file=sys.stderr)
            sys.exit(1)
