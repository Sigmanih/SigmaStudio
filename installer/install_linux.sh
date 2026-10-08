#!/usr/bin/env bash
# Sigma Studio - Linux Installation Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo -e "\033[96m[SIGMA] Starting Linux (Debian/Ubuntu) Installation...\033[0m"

# Update apt
echo -e "\033[94m[SIGMA] Updating apt package lists...\033[0m"
sudo apt-get update -y

# Check/Install Python 3 and venv
if ! command -v python3 &>/dev/null; then
    echo -e "\033[93m[SIGMA] Python 3 not found. Installing...\033[0m"
    sudo apt-get install -y python3 python3-pip python3-venv
else
    echo -e "\033[92m[SIGMA] Python 3 found.\033[0m"
    # Ensure venv is installed for debian/ubuntu
    sudo apt-get install -y python3-venv || true
fi

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

# Check/Install git
if ! command -v git &>/dev/null; then
    echo -e "\033[93m[SIGMA] Git not found. Installing...\033[0m"
    sudo apt-get install -y git
fi

echo -e "\033[92m[SIGMA] System dependencies met. Running python installer...\033[0m"
python3 sigma_launcher.py --install
