@echo off
setlocal
title Disease Portal
cd /d "%~dp0"

echo ==================================================
echo            Disease Portal - launcher
echo ==================================================
echo.

REM --- 1) Create the virtual environment on first run / fresh machine ---
if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment ^(.venv^)...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [error] Could not create the virtual environment.
        echo         Make sure Python 3 is installed ^(https://www.python.org/downloads/^).
        pause
        exit /b 1
    )
)

REM --- 2) Install/update dependencies only when requirements.txt changes ---
fc /b requirements.txt ".venv\.installed_requirements.txt" >nul 2>&1
if errorlevel 1 (
    echo [setup] Installing/updating dependencies ^(first time can take a minute^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [error] Dependency installation failed. See messages above.
        pause
        exit /b 1
    )
    copy /y requirements.txt ".venv\.installed_requirements.txt" >nul
)

REM --- 3) Make sure the local database exists (downloads it if missing) ---
if not exist "diseaseportal.db" (
    echo [setup] Local database not found - downloading...
    ".venv\Scripts\python.exe" download_db.py
)

REM --- 4) Open the browser a few seconds after the server starts ---
start "" /b powershell -NoProfile -Command "Start-Sleep 3; Start-Process 'http://localhost:5000'"

REM --- 5) Run the app (press Ctrl+C in this window to stop) ---
echo.
echo [run] Starting at http://localhost:5000   (press Ctrl+C here to stop)
echo.
".venv\Scripts\python.exe" app.py

echo.
echo [stopped] The server has stopped. You can close this window.
pause
