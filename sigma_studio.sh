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

# 2. Check and auto-install Node.js (>= 20 LTS) if not present or too old
NODE_VER=0
if command -v node &>/dev/null; then
    NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
fi

if [ ! -f "sigma_studio/dist/index.html" ] && [ "$NODE_VER" -lt 20 ]; then
    echo -e "\033[93m[SIGMA] Node.js is not installed or version < 20 (found '$NODE_VER'). Installing Node.js 20.x LTS...\033[0m"
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y curl ca-certificates
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif command -v brew &>/dev/null; then
        brew install node
    fi
fi

# 3. Delegate to unified launcher
exec $PYTHON sigma_launcher.py "$@"
