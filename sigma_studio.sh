#!/usr/bin/env bash
# Sigma Studio — Universal POSIX Launcher (Linux, Raspberry Pi, macOS)
# Usage: ./sigma_studio.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Check Python 3
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo -e "\033[93m[SIGMA] Python 3 not found. Attempting installation via package manager...\033[0m"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -y && sudo apt-get install -y python3 python3-pip python3-venv
        PYTHON=python3
    elif command -v brew &>/dev/null; then
        brew install python3
        PYTHON=python3
    else
        echo -e "\033[91m[SIGMA] ERROR: Python 3 not found. Please install Python 3.10+\033[0m"
        exit 1
    fi
fi

# 2. Check and auto-install Node.js and npm if not present and no dist/ folder exists
if ! command -v npm &>/dev/null; then
    if [ ! -f "sigma_studio/dist/index.html" ]; then
        echo -e "\033[93m[SIGMA] Node.js/npm not found. Installing nodejs and npm...\033[0m"
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -y && sudo apt-get install -y nodejs npm
        elif command -v brew &>/dev/null; then
            brew install node
        fi
    fi
fi

# 3. Delegate to unified launcher
exec $PYTHON sigma_launcher.py "$@"
