@echo off
setlocal enabledelayedexpansion

echo ==============================================================================
echo  SIGMA STUDIO ^| Unified Pipeline Rebuild ^& Hot-Reload
echo ==============================================================================
echo.

cd /d "%~dp0\.."

echo [1/3] Verifica e installazione dipendenze Python...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    pip install -q -r requirements.txt
) else (
    echo [!] Virtual environment .venv non trovato, utilizzo interprete globale.
    pip install -q -r requirements.txt
)

echo [2/3] Compilazione bundle frontend React 19 + Vite 8...
cd sigma_studio
if exist "package.json" (
    call npm run build
) else (
    echo [ERROR] package.json non trovato in sigma_studio/
    exit /b 1
)
cd ..

echo [3/3] Sincronizzazione registry moduli ed aggiornamento stamp...
python -c "from core.data_handler import rebuild_modules_meta; rebuild_modules_meta()"

echo.
echo ==============================================================================
echo  [OK] Ricompilazione completata con successo!
echo  Puoi riavviare o aggiornare la pagina nel browser (F5).
echo ==============================================================================
pause
