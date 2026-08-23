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

:: Always ensure Python dependencies are installed (pip skips already-installed packages)
echo [SIGMA_SERVER] Ensuring Python dependencies are installed...
pip install -r requirements.txt
if errorlevel 1 (
    echo [SIGMA_SERVER] WARNING: Some Python dependencies may have warnings. Continuing...
)

:: Ensure GGUF inference kernel (llama-cpp-python) is installed for hardware acceleration
echo [SIGMA_SERVER] Ensuring GGUF inference runtime (llama-cpp-python) is installed...
python -c "import llama_cpp" >nul 2>nul
if errorlevel 1 (
    echo [SIGMA_SERVER] llama-cpp-python not found. Auto-installing optimized build for detected hardware...
    python sigma_launcher.py --install
)

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
    if not exist "sigma_studio\node_modules" (
        echo [SIGMA_SERVER] Installing Frontend dependencies - npm install...
        cd sigma_studio
        call npm install
        if errorlevel 1 (
            echo [SIGMA_SERVER] WARNING: npm install returned an error.
        )
        cd ..
    )
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
    call npm run build
    if errorlevel 1 (
        echo [SIGMA_SERVER] WARNING: Frontend build failed.
    )
    cd ..
) else (
    echo [SIGMA_SERVER] WARNING: Node.js/npm not found. Skipping automatic frontend build.
    if not exist "sigma_studio\dist" (
        echo [SIGMA_SERVER] ERROR: Frontend build folder sigma_studio\dist is missing and Node.js/npm is not installed.
        echo [SIGMA_SERVER] Please install Node.js to build the frontend.
        pause
        exit /b 1
    )
)

:: Kill any existing Python server on port 8000
echo [SIGMA_SERVER] Stopping any existing server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /f /pid %%a >nul 2>nul
)
timeout /t 1 >nul

:: High-Performance Hardware Acceleration Environment
set CUDA_VISIBLE_DEVICES=0,1
set OLLAMA_NUM_PARALLEL=4
set OLLAMA_MAX_LOADED_MODELS=2
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_KEEP_ALIVE=24h
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
set OMP_NUM_THREADS=12
set MKL_NUM_THREADS=12

:: Run server
echo [SIGMA_SERVER] Starting fresh server with Multi-GPU and FlashAttention on http://localhost:8000
python sigma_server.py

:: Deactivate venv automatically when server exits
echo [SIGMA_SERVER] Stopping virtual environment...
call deactivate
echo [SIGMA_SERVER] Server stopped. Virtual environment deactivated.
timeout /t 2 >nul