@echo off
title Sigma Studio Server
cd /d "%~dp0"

:: Check for virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo [SIGMA_SERVER] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [SIGMA_SERVER] Failed to create venv. Press any key to exit.
        pause >nul
        exit /b 1
    )
)

:: Activate virtual environment
echo [SIGMA_SERVER] Activating virtual environment...
call .venv\Scripts\activate.bat

:: Check for Python
where python >nul 2>nul
if errorlevel 1 (
    echo [SIGMA_SERVER] Python not found! Install Python first.
    pause >nul
    exit /b 1
)

:: Check for npm
where npm >nul 2>nul
if not errorlevel 1 (
    echo [SIGMA_SERVER] Cleaning Vite cache...
    if exist sigma_studio\node_modules\.vite (
        rmdir /s /q sigma_studio\node_modules\.vite
    )
    echo [SIGMA_SERVER] Removing old build...
    if exist sigma_studio\dist (
        rmdir /s /q sigma_studio\dist
    )
    echo [SIGMA_SERVER] Building frontend assets...
    cd sigma_studio
    call npx vite build
    cd ..
)

:: Kill any existing Python server on port 8000
echo [SIGMA_SERVER] Stopping any existing server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /f /pid %%a >nul 2>nul
)
timeout /t 1 >nul

:: Run server
echo [SIGMA_SERVER] Starting fresh server on http://localhost:8000
python sigma_server.py

:: Deactivate venv automatically when server exits
echo [SIGMA_SERVER] Stopping virtual environment...
call deactivate
echo [SIGMA_SERVER] Server stopped. Virtual environment deactivated.
timeout /t 2 >nul