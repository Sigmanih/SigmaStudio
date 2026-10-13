@echo off
:: ============================================================================
:: Sigma Studio - Avvio su Windows
::
:: Questo file non installa niente e non decide niente: trova un Python
:: utilizzabile e passa la mano a sigma_launcher.py, che e' l'unico posto dove
:: sta la procedura di installazione.
::
:: Prima faceva altro, ed e' il motivo per cui una copia appena clonata non
:: partiva: creava il virtualenv, lo attivava e lanciava subito il server. Il
:: virtualenv era vuoto. Il server rispondeva con quattro avvisi di moduli
:: mancanti e poi moriva su "No module named 'uvicorn'", mentre il frontend
:: falliva con "vite non e' riconosciuto". Nessuno dei due era il vero errore:
:: mancava il passaggio di installazione, che su Linux e macOS c'era da sempre
:: perche' sigma_studio.sh delegava al launcher e questo file no.
::
:: Anche le variabili d'ambiente sono sparite da qui. Erano scritte a mano
:: (CUDA_VISIBLE_DEVICES=0,1 su una macchina con una scheda sola, dodici thread
:: su qualunque processore): il launcher le ricava dall'hardware vero e da
:: config.json.
:: ============================================================================
title Sigma Studio
cd /d "%~dp0"

:: 1. Un Python utilizzabile. `py -3` e' l'avviatore ufficiale di Windows e
::    trova l'installazione giusta anche quando `python` punta all'alias del
::    Microsoft Store, che non e' un interprete e apre il negozio.
set "SIGMA_PY="
py -3 --version >nul 2>&1 && set "SIGMA_PY=py -3"
if not defined SIGMA_PY (
    python --version >nul 2>&1 && set "SIGMA_PY=python"
)

if not defined SIGMA_PY (
    echo.
    echo   Python 3 non trovato.
    echo.
    echo   Installalo da https://www.python.org/downloads/ ^(serve la 3.10 o
    echo   successiva^) e ricordati di spuntare "Add Python to PATH" durante
    echo   l'installazione. Poi rilancia questo file.
    echo.
    pause
    exit /b 1
)

:: 2. La versione minima si verifica qui: piu' avanti fallirebbe dentro una
::    dipendenza, con un messaggio che non nomina Python.
%SIGMA_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Sigma Studio richiede Python 3.10 o successivo.
    %SIGMA_PY% -c "import sys; print('   Versione trovata: ' + sys.version.split()[0])"
    echo   Aggiorna da https://www.python.org/downloads/ e rilancia.
    echo.
    pause
    exit /b 1
)

:: 3. Da qui in poi decide il launcher: virtualenv, dipendenze Python, Node,
::    runtime GGUF, build del frontend e avvio. Gli argomenti passano attraverso,
::    cosi' `sigma_studio.bat --install` e `--check` funzionano come su POSIX.
%SIGMA_PY% sigma_launcher.py %*

if errorlevel 1 (
    echo.
    echo   [SIGMA] Avvio interrotto. Il messaggio qui sopra dice perche'.
    echo   Se il problema riguarda le dipendenze, prova:  sigma_studio.bat --install
    echo.
    pause
)
