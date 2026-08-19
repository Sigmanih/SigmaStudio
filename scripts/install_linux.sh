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

# Check/Install Node.js
if ! command -v npm &>/dev/null; then
    echo -e "\033[93m[SIGMA] Node.js/npm not found. Installing via apt...\033[0m"
    sudo apt-get install -y nodejs npm
else
    echo -e "\033[92m[SIGMA] Node.js/npm found.\033[0m"
fi

# Check/Install git
if ! command -v git &>/dev/null; then
    echo -e "\033[93m[SIGMA] Git not found. Installing...\033[0m"
    sudo apt-get install -y git
fi

echo -e "\033[92m[SIGMA] System dependencies met. Running python installer...\033[0m"
python3 sigma_launcher.py --install
