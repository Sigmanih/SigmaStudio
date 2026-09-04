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
    echo -e "\033[93m[SIGMA] Python 3 non trovato. Installazione automatica...\033[0m"
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -y && sudo apt-get install -y python3 python3-pip python3-venv
        PYTHON=python3
    elif command -v brew &>/dev/null; then
        brew install python3
        PYTHON=python3
    else
        echo -e "\033[91m[SIGMA] ERRORE: Python 3 non trovato. Installa Python 3.10+\033[0m"
        exit 1
    fi
fi

# 2. Check and auto-install Node.js (>= 20 LTS) if not present or too old
NODE_VER=0
if command -v node &>/dev/null; then
    NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
fi

if [ ! -f "sigma_studio/dist/index.html" ] && [ "$NODE_VER" -lt 20 ]; then
    echo -e "\033[93m[SIGMA] Node.js non presente o versione < 20 (trovato '$NODE_VER'). Installazione Node.js 20.x LTS...\033[0m"
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y curl ca-certificates
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif command -v brew &>/dev/null; then
        brew install node
    fi
fi

# 3. Check and Auto-Build Native llama-server if missing or incompatible with system GLIBC
LLAMA_FOUND=0
RUNTIME_DIR="store/engine_runtime"
NATIVE_DIR="$RUNTIME_DIR/native"

# Cerca se esiste già un llama-server funzionante
if [ -d "$RUNTIME_DIR" ]; then
    for srv in $(find "$RUNTIME_DIR" -name "llama-server" -type f 2>/dev/null); do
        if [ -x "$srv" ]; then
            if "$srv" --version &>/dev/null; then
                LLAMA_FOUND=1
                break
            fi
        fi
    done
fi

# Se non esiste o fallisce (es. GLIBC mancante), compila nativamente ad hoc per questo hardware
if [ "$LLAMA_FOUND" -eq 0 ]; then
    ARCH=$(uname -m)
    echo -e "\033[96m[SIGMA] Rilevamento runtime GGUF per architettura $ARCH...\033[0m"
    echo -e "\033[93m[SIGMA] Nessun binario compatibile con la libc di sistema. Avvio compilazione nativa ottimizzata ad hoc...\033[0m"

    # Installa strumenti di compilazione se mancanti
    if command -v apt-get &>/dev/null; then
        if ! command -v cmake &>/dev/null || ! command -v g++ &>/dev/null; then
            echo -e "\033[94m[SIGMA] Installazione pacchetti di compilazione (cmake, build-essential, git)...\033[0m"
            sudo apt-get update -y && sudo apt-get install -y cmake build-essential git
        fi
    fi

    BUILD_TMP="/tmp/sigma_llama_build_$$"
    mkdir -p "$BUILD_TMP"
    mkdir -p "$NATIVE_DIR"

    echo -e "\033[94m[SIGMA] Download dei sorgenti llama.cpp...\033[0m"
    git clone --depth 1 https://github.com/ggml-org/llama.cpp "$BUILD_TMP/llama.cpp" || true

    if [ -d "$BUILD_TMP/llama.cpp" ]; then
        echo -e "\033[94m[SIGMA] Compilazione nativa (ottimizzata con istruzioni della CPU locale)...\033[0m"
        CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
        cd "$BUILD_TMP/llama.cpp"
        cmake -B build -DGGML_NATIVE=ON -DGGML_BUILD_SERVER=ON -DCMAKE_BUILD_TYPE=Release
        cmake --build build --config Release -j"$CORES" --target llama-server

        if [ -f "build/bin/llama-server" ]; then
            cp build/bin/llama-server "$SCRIPT_DIR/$NATIVE_DIR/llama-server"
            cp build/bin/*.so* "$SCRIPT_DIR/$NATIVE_DIR/" 2>/dev/null || true
            chmod +x "$SCRIPT_DIR/$NATIVE_DIR/llama-server"
            echo -e "\033[92m[SIGMA] Runtime nativo compilato con successo in $NATIVE_DIR/llama-server!\033[0m"
        fi
        cd "$SCRIPT_DIR"
        rm -rf "$BUILD_TMP"
    fi
fi

# 4. Delegate to unified launcher
exec $PYTHON sigma_launcher.py "$@"
