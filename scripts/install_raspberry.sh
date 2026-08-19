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

# Check/Install Node.js (>= 20 LTS required by Vite 8)
NODE_VER=0
if command -v node &>/dev/null; then
    NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
fi

if [ "$NODE_VER" -lt 20 ]; then
    echo -e "\033[93m[SIGMA] Node.js version is '$NODE_VER' (< 20). Installing Node.js 20.x LTS via NodeSource...\033[0m"
    sudo apt-get install -y curl ca-certificates
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo -e "\033[92m[SIGMA] Node.js $(node -v) found (>= 20).\033[0m"
fi

# Clean stale cross-platform node_modules/package-lock.json if ARM64 native bindings missing
if [ -d "sigma_studio/node_modules" ] && [ ! -d "sigma_studio/node_modules/@rolldown/binding-linux-arm64-gnu" ]; then
    echo -e "\033[93m[SIGMA] Cleaning stale node_modules for fresh ARM64 native bindings...\033[0m"
    rm -rf sigma_studio/node_modules sigma_studio/package-lock.json
fi

echo -e "\033[92m[SIGMA] System dependencies met. Running python installer...\033[0m"
python3 sigma_launcher.py --install
