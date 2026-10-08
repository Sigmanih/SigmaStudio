#!/usr/bin/env bash
set -e

echo "=============================================================================="
echo " SIGMA STUDIO | Unified Pipeline Rebuild & Hot-Reload"
echo "=============================================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
cd "$ROOT_DIR"

echo "[1/3] Verifica e installazione dipendenze Python..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
    pip install -q -r requirements.txt
else
    pip install -q -r requirements.txt
fi

echo "[2/3] Compilazione bundle frontend React 19 + Vite 8..."
cd sigma_studio
if [ -f "package.json" ]; then
    npm run build
fi
cd ..

echo "[3/3] Sincronizzazione registry moduli..."
python3 -c "from core.data_handler import rebuild_modules_meta; rebuild_modules_meta()"

echo ""
echo "=============================================================================="
echo " [OK] Ricompilazione completata con successo!"
echo "=============================================================================="
