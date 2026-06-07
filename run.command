#!/bin/bash
# ==========================================================================
# Disease Portal - macOS launcher
#
# This is the macOS twin of run.bat (Windows). Both live in the repo and are
# kept in sync via git, so whichever machine you are on you can launch the whole
# project with a single double-click (Finder) or ./run.command (Terminal).
#
# On a fresh machine it sets itself up: creates the virtual environment,
# installs dependencies (only when requirements.txt changes), downloads the
# database if missing, builds the disease + ClinGen indexes (skipped if already
# present), opens the browser, and starts the app.
# ==========================================================================
cd "$(dirname "$0")" || exit 1

echo "=================================================="
echo "           Disease Portal - launcher"
echo "=================================================="
echo

# --- 1) Create the virtual environment on first run / fresh machine ---
if [ ! -x ".venv/bin/python" ]; then
    echo "[setup] Creating virtual environment (.venv)..."
    python3 -m venv .venv
    if [ ! -x ".venv/bin/python" ]; then
        echo "[error] Could not create the virtual environment."
        echo "        Install Python 3 first: https://www.python.org/downloads/  (or: brew install python)"
        read -r -p "Press Enter to close..."
        exit 1
    fi
fi

PY=".venv/bin/python"

# --- 2) Install/update dependencies only when requirements.txt changes ---
if ! cmp -s requirements.txt ".venv/.installed_requirements.txt"; then
    echo "[setup] Installing/updating dependencies (first time can take a minute)..."
    "$PY" -m pip install --upgrade pip
    if ! "$PY" -m pip install -r requirements.txt; then
        echo "[error] Dependency installation failed. See messages above."
        read -r -p "Press Enter to close..."
        exit 1
    fi
    cp requirements.txt ".venv/.installed_requirements.txt"
fi

# --- 3) Make sure the local database exists (downloads it if missing) ---
if [ ! -f "diseaseportal.db" ]; then
    echo "[setup] Local database not found - downloading..."
    "$PY" download_db.py
fi

# --- 3b) Build the full disease index if missing (lets you browse all diseases) ---
"$PY" build_disease_index.py

# --- 3c) Build the ClinGen clinical-validity overlay if missing ---
"$PY" build_clingen_index.py

# --- 4) Pick a port. macOS often runs AirPlay Receiver / Control Center on
#        port 5000, which would block the app, so fall back to 5001 if taken. ---
PORT=5000
if lsof -nP -i :5000 >/dev/null 2>&1; then
    PORT=5001
    echo "[info] Port 5000 is busy (likely macOS AirPlay Receiver) - using port $PORT instead."
fi
export PORT

# --- 5) Open the browser a few seconds after the server starts ---
( sleep 3; open "http://localhost:$PORT" ) >/dev/null 2>&1 &

# --- 6) Run the app (press Ctrl+C in this window to stop) ---
echo
echo "[run] Starting at http://localhost:$PORT   (press Ctrl+C here to stop)"
echo
"$PY" app.py

echo
echo "[stopped] The server has stopped. You can close this window."
read -r -p "Press Enter to close..."
