#!/usr/bin/env bash
# Sigma Studio - macOS Start Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

python3 sigma_launcher.py
