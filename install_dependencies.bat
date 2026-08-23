@echo off
title Sigma Studio - Installer Dipendenze
cd /d "%~dp0"

echo =======================================================
echo          Sigma Studio Dependency Installer
echo =======================================================
echo.

:: 1. Creazione / Controllo Ambiente Virtuale Python
if not exist ".venv\Scripts\activate.bat" (
    echo [SIGMA_INSTALL] Creazione ambiente virtuale Python (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [SIGMA_INSTALL] ERRORE: Impossibile creare l'ambiente virtuale. Assicurati che Python sia installato.
        pause
        exit /b 1
    )
)

echo [SIGMA_INSTALL] Attivazione ambiente virtuale...
call .venv\Scripts\activate.bat

echo [SIGMA_INSTALL] Aggiornamento pip...
python -m pip install --upgrade pip

echo [SIGMA_INSTALL] Installazione librerie Python da requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [SIGMA_INSTALL] AVVISO: Alcune dipendenze Python potrebbero aver restituito un avviso. Continuando...
)

echo [SIGMA_INSTALL] Installazione runtime GGUF e kernel di inferenza (llama-cpp-python)...
python sigma_launcher.py --install

:: 2. Controllo ed Installazione Dipendenze Frontend Node.js
where npm >nul 2>nul
if not errorlevel 1 (
    echo [SIGMA_INSTALL] Installazione dipendenze Frontend Node.js - npm...
    cd sigma_studio
    call npm install
    echo [SIGMA_INSTALL] Compilazione frontend assets - npm run build...
    call npm run build
    cd ..
) else (
    echo [SIGMA_INSTALL] NOTA: Node.js/npm non trovato. Verra utilizzata la build pre-compilata in sigma_studio/dist.
)

echo.
echo =======================================================
echo       Installazione completata con successo!
echo =======================================================
echo Puoi ora avviare Sigma Studio eseguendo sigma_studio.bat
echo.
pause
