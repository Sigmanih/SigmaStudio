@echo off
:: ============================================================================
:: Sigma Studio - Installazione delle dipendenze su Windows
::
:: Una riga sola di lavoro: `sigma_launcher.py --install`. Tutto il resto qui
:: dentro e' trovare un Python con cui eseguirla.
::
:: Prima installava per conto suo, e sbagliava in due modi. Usava
:: requirements.txt, che tira giu' l'intero stack CUDA anche su una macchina
:: senza scheda NVIDIA — parecchi gigabyte che non serviranno mai — mentre il
:: launcher sceglie il file giusto per l'acceleratore che ha trovato. E teneva
:: una seconda procedura di installazione accanto a quella vera, che nessuno
:: aggiornava insieme all'altra.
:: ============================================================================
title Sigma Studio - Installazione
cd /d "%~dp0"

echo.
echo   Sigma Studio - installazione delle dipendenze
echo.

set "SIGMA_PY="
py -3 --version >nul 2>&1 && set "SIGMA_PY=py -3"
if not defined SIGMA_PY (
    python --version >nul 2>&1 && set "SIGMA_PY=python"
)

if not defined SIGMA_PY (
    echo   Python 3 non trovato.
    echo.
    echo   Installalo da https://www.python.org/downloads/ ^(serve la 3.10 o
    echo   successiva^), spuntando "Add Python to PATH", poi rilancia.
    echo.
    pause
    exit /b 1
)

%SIGMA_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo   Sigma Studio richiede Python 3.10 o successivo.
    %SIGMA_PY% -c "import sys; print('   Versione trovata: ' + sys.version.split()[0])"
    echo.
    pause
    exit /b 1
)

:: Virtualenv, pacchetti Python per questo acceleratore, Node, runtime GGUF e
:: build del frontend: li fa tutti il launcher, nello stesso ordine su ogni
:: sistema operativo.
%SIGMA_PY% sigma_launcher.py --install

if errorlevel 1 (
    echo.
    echo   Installazione non riuscita. Il messaggio qui sopra dice dove.
    echo.
    pause
    exit /b 1
)

echo.
echo   Fatto. Avvia Sigma Studio con sigma_studio.bat
echo.
pause
