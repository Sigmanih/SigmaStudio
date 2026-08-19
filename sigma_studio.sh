#!/usr/bin/env bash
# Sigma Studio — Linux/macOS Launcher
# Usage: ./sigma_studio.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python 3
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "[SIGMA] ERROR: Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Delegate to unified launcher
exec $PYTHON sigma_launcher.py "$@"
