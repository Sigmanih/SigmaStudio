@echo off
title Sigma Studio Server
cd /d "%~dp0"

:: 1. Virtual Environment Check & Activation
if not exist ".venv\Scripts\activate.bat" (
    echo [SIGMA_SERVER] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [SIGMA_SERVER] Failed to create venv. Press any key to exit.
        pause
        exit /b 1
    )
)

echo [SIGMA_SERVER] Activating virtual environment...
call .venv\Scripts\activate.bat

:: 2. Stop Any Stale Process on Port 8000
echo [SIGMA_SERVER] Checking for stale processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /f /pid %%a >nul 2>nul
)

:: 3. High-Performance Hardware Environment & Resilient Local SSL
set PYTHONHTTPSVERIFY=0
set CUDA_VISIBLE_DEVICES=0,1
set OLLAMA_NUM_PARALLEL=4
set OLLAMA_MAX_LOADED_MODELS=2
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_KEEP_ALIVE=24h
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
set OMP_NUM_THREADS=12
set MKL_NUM_THREADS=12

:: 4. Start Unified Server
echo [SIGMA_SERVER] Starting Sigma Studio on http://localhost:8000...
python sigma_server.py

:: 5. Handle Exit
if errorlevel 1 (
    echo [SIGMA_SERVER] Server stopped with error.
    pause
)