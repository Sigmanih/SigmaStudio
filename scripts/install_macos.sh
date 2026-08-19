#!/usr/bin/env bash
# Sigma Studio - macOS Installation Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo -e "\033[96m[SIGMA] Starting macOS Installation...\033[0m"

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo -e "\033[91m[SIGMA] ERROR: Homebrew is required but not found.\033[0m"
    echo -e "\033[93m[SIGMA] Install it via: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\033[0m"
    exit 1
fi

# Check/Install Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "\033[93m[SIGMA] Python 3 not found. Installing via Homebrew...\033[0m"
    brew install python@3.11
else
    echo -e "\033[92m[SIGMA] Python 3 found.\033[0m"
fi

# Check/Install Node.js
if ! command -v npm &>/dev/null; then
    echo -e "\033[93m[SIGMA] Node.js not found. Installing via Homebrew...\033[0m"
    brew install node
else
    echo -e "\033[92m[SIGMA] Node.js/npm found.\033[0m"
fi

echo -e "\033[92m[SIGMA] System dependencies met. Running python installer...\033[0m"
python3 sigma_launcher.py --install
