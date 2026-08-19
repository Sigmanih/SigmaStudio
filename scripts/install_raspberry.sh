#!/usr/bin/env bash
# Sigma Studio - Raspberry Pi (ARM64) Installation Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo -e "\033[96m[SIGMA] Starting Raspberry Pi Installation...\033[0m"
echo -e "\033[93m[SIGMA] WARNING: CUDA is not available on Raspberry Pi. Training Lab features will be limited or run in CPU mode.\033[0m"

# Update apt
echo -e "\033[94m[SIGMA] Updating apt package lists...\033[0m"
sudo apt-get update -y

# Check/Install Python 3 and venv, plus ARM specific deps
echo -e "\033[94m[SIGMA] Ensuring Python 3 and ARM64 system dependencies are installed...\033[0m"
sudo apt-get install -y python3 python3-pip python3-venv git \
    libatlas-base-dev \
    libjpeg-dev \
    libopenblas-dev

# Check/Install Node.js
if ! command -v npm &>/dev/null; then
    echo -e "\033[93m[SIGMA] Node.js/npm not found. Installing via apt...\033[0m"
    sudo apt-get install -y nodejs npm
else
    echo -e "\033[92m[SIGMA] Node.js/npm found.\033[0m"
fi

echo -e "\033[92m[SIGMA] System dependencies met. Running python installer...\033[0m"
python3 sigma_launcher.py --install
