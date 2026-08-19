#!/usr/bin/env python3
"""Sigma Studio — Universal Cross-Platform Launcher

Single entry point for all platforms: Windows, Linux, macOS, Raspberry Pi.
Usage:
    python sigma_launcher.py              # Start Sigma Studio
    python sigma_launcher.py --install    # Install/update dependencies
    python sigma_launcher.py --check      # Verify environment without starting
    python sigma_launcher.py --info       # Show system capabilities
"""

import sys
import os
import platform
import subprocess
import argparse
import venv
import json
import hashlib
import glob
import shutil

# Ensure Python >= 3.10
if sys.version_info < (3, 10):
    print("[SIGMA] ERROR: Python 3.10 or higher is required.")
    sys.exit(1)

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_log(msg, color=Colors.OKBLUE, is_error=False):
    # Enable Windows ANSI support if needed
    if os.name == 'nt':
        os.system('color')
    
    formatted = f"{color}{msg}{Colors.ENDC}"
    if is_error:
        print(formatted, file=sys.stderr)
    else:
        print(formatted)

def detect_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    is_windows = system == "windows"
    is_linux = system == "linux"
    is_darwin = system == "darwin"
    is_arm = "arm" in machine or "aarch" in machine
    is_apple_silicon = is_darwin and is_arm
    
    # Simple check for Raspberry Pi
    is_raspberry_pi = False
    if is_linux and is_arm:
        try:
            with open("/sys/firmware/devicetree/base/model", "r") as f:
                if "Raspberry Pi" in f.read():
                    is_raspberry_pi = True
        except FileNotFoundError:
            pass

    return {
        "os": system,
        "arch": machine,
        "is_arm": is_arm,
        "is_raspberry_pi": is_raspberry_pi,
        "is_apple_silicon": is_apple_silicon,
        "is_windows": is_windows,
        "is_linux": is_linux,
        "is_darwin": is_darwin
    }

def get_venv_paths():
    venv_dir = os.path.abspath(".venv")
    if os.name == "nt":
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
        bin_dir = os.path.join(venv_dir, "Scripts")
    else:
        python_exe = os.path.join(venv_dir, "bin", "python")
        pip_exe = os.path.join(venv_dir, "bin", "pip")
        bin_dir = os.path.join(venv_dir, "bin")
    
    return venv_dir, python_exe, pip_exe, bin_dir

def ensure_venv():
    venv_dir, python_exe, pip_exe, bin_dir = get_venv_paths()
    
    if not os.path.exists(python_exe):
        print_log("[SIGMA] Creating virtual environment (.venv)...", Colors.OKCYAN)
        try:
            venv.create(venv_dir, with_pip=True)
            print_log("[SIGMA] Virtual environment created successfully.", Colors.OKGREEN)
        except Exception as e:
            print_log(f"[SIGMA] ERROR: Failed to create virtual environment: {e}", Colors.FAIL, True)
            sys.exit(1)
    else:
        print_log("[SIGMA] Virtual environment found.", Colors.OKCYAN)
        
    return python_exe, pip_exe

def activate_venv_env():
    venv_dir, _, _, bin_dir = get_venv_paths()
    print_log(f"[SIGMA] Activating virtual environment in current process...", Colors.OKCYAN)
    
    os.environ["VIRTUAL_ENV"] = venv_dir
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    
    # Remove PYTHONHOME if it's set
    if "PYTHONHOME" in os.environ:
        del os.environ["PYTHONHOME"]

def install_dependencies(platform_info):
    _, pip_exe = ensure_venv()
    print_log("[SIGMA] Checking and installing dependencies...", Colors.OKCYAN)

    def run_pip(req_file):
        if os.path.exists(req_file):
            print_log(f"[SIGMA] Installing {req_file}...", Colors.OKCYAN)
            subprocess.check_call([pip_exe, "install", "-r", req_file])
            return True
        return False

    req_dir = "requirements"
    if not os.path.exists(req_dir):
        print_log("[SIGMA] 'requirements' directory not found, falling back to requirements.txt.", Colors.WARNING)
        run_pip("requirements.txt")
        return

    # Base requirements
    run_pip(os.path.join(req_dir, "base.txt"))

    # Platform specific
    if platform_info["is_apple_silicon"] or platform_info["is_darwin"]:
        run_pip(os.path.join(req_dir, "apple.txt"))
    elif platform_info["is_windows"] or platform_info["is_linux"]:
        if not platform_info["is_raspberry_pi"]:
            if not run_pip(os.path.join(req_dir, "cuda.txt")):
                run_pip(os.path.join(req_dir, "cpu.txt"))
        else:
            run_pip(os.path.join(req_dir, "cpu.txt"))

    print_log("[SIGMA] Dependencies installed.", Colors.OKGREEN)

def _get_directory_hash(directory):
    sha1 = hashlib.sha1()
    if not os.path.exists(directory):
        return sha1.hexdigest()
    
    for root, _, files in os.walk(directory):
        for names in sorted(files):
            filepath = os.path.join(root, names)
            try:
                with open(filepath, 'rb') as f:
                    while True:
                        buf = f.read(4096)
                        if not buf:
                            break
                        sha1.update(buf)
            except Exception:
                pass
    return sha1.hexdigest()

def ensure_frontend():
    print_log("[SIGMA] Checking frontend...", Colors.OKCYAN)
    
    # Check for npm
    try:
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print_log("[SIGMA] ERROR: npm is not found. Please install Node.js and npm.", Colors.FAIL, True)
        sys.exit(1)

    # Reusing SHA-1 fingerprint logic pattern
    package_json_hash = _get_directory_hash("package.json")
    src_hash = _get_directory_hash("src")
    current_hash = hashlib.sha1((package_json_hash + src_hash).encode('utf-8')).hexdigest()
    
    hash_file = os.path.join("dist", ".build_hash")
    built_hash = ""
    if os.path.exists(hash_file):
        with open(hash_file, "r") as f:
            built_hash = f.read().strip()
            
    if built_hash != current_hash or not os.path.exists("dist"):
        print_log("[SIGMA] Frontend changes detected. Building...", Colors.OKCYAN)
        
        if not os.path.exists("node_modules"):
            print_log("[SIGMA] Installing node modules...", Colors.OKCYAN)
            subprocess.run(["npm", "install"], check=True)
            
        print_log("[SIGMA] Running Vite build...", Colors.OKCYAN)
        
        # Clean old dist
        if os.path.exists("dist"):
            shutil.rmtree("dist")
            
        subprocess.run(["npm", "run", "build"], check=True)
        
        # Save hash
        os.makedirs("dist", exist_ok=True)
        with open(hash_file, "w") as f:
            f.write(current_hash)
            
        print_log("[SIGMA] Frontend build complete.", Colors.OKGREEN)
    else:
        print_log("[SIGMA] Frontend is up to date.", Colors.OKGREEN)

def kill_stale_port(port=8000):
    print_log(f"[SIGMA] Checking for stale processes on port {port}...", Colors.OKCYAN)
    
    try:
        if os.name == 'nt':
            # Windows
            cmd = f'netstat -ano | findstr :{port}'
            out = subprocess.check_output(cmd, shell=True).decode()
            pids = set()
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and 'LISTENING' in line:
                    pids.add(parts[-1])
            for pid in pids:
                if pid != '0':
                    print_log(f"[SIGMA] Killing PID {pid} on port {port}...", Colors.WARNING)
                    subprocess.call(['taskkill', '/f', '/pid', pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == 'Darwin':
            # macOS
            cmd = f'lsof -ti :{port} | xargs kill -9'
            subprocess.call(cmd, shell=True, stderr=subprocess.DEVNULL)
        else:
            # Linux
            cmd = f'fuser -k {port}/tcp'
            subprocess.call(cmd, shell=True, stderr=subprocess.DEVNULL)
    except Exception:
        # Ignore errors if port is not in use or command fails
        pass

def set_hardware_env():
    print_log("[SIGMA] Configuring hardware environment variables...", Colors.OKCYAN)
    config_path = "config.json"
    
    # Default configs
    hardware_cfg = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                hardware_cfg = data.get("hardware", {})
        except Exception as e:
            print_log(f"[SIGMA] Warning: Failed to parse config.json: {e}", Colors.WARNING)
            
    # Set OMP_NUM_THREADS
    threads = hardware_cfg.get("num_threads", os.cpu_count())
    os.environ["OMP_NUM_THREADS"] = str(threads)
    
    # CUDA config
    cuda_devices = hardware_cfg.get("cuda_visible_devices", "")
    if cuda_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_devices
        
    # Ollama overrides
    if "ollama_host" in hardware_cfg:
        os.environ["OLLAMA_HOST"] = hardware_cfg["ollama_host"]
        
    # Platform specific PyTorch memory allocator config
    if os.name != 'nt':
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = hardware_cfg.get("pytorch_alloc_conf", "expandable_segments:True")
        
    print_log(f"[SIGMA] Hardware config applied. Threads: {threads}", Colors.OKCYAN)

def launch_server():
    python_exe, _ = ensure_venv()
    
    print_log("[SIGMA] Launching Sigma Studio Server...", Colors.OKGREEN)
    
    # Instead of running directly, we invoke the server with the venv python
    try:
        subprocess.run([python_exe, "sigma_server.py"])
    except KeyboardInterrupt:
        print_log("\n[SIGMA] Server stopped by user.", Colors.OKBLUE)
    except Exception as e:
        print_log(f"[SIGMA] ERROR running server: {e}", Colors.FAIL, True)

def show_system_info():
    print_log("[SIGMA] System Information", Colors.HEADER)
    info = detect_platform()
    for k, v in info.items():
        print(f"  - {k}: {v}")
        
    python_exe, _ = ensure_venv()
    activate_venv_env()
    
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        print_log("\n[SIGMA] Hardware Capabilities:", Colors.HEADER)
        hw_info = UniversalHardwareProbe.probe_all()
        print(json.dumps(hw_info, indent=2))
    except ImportError:
        print_log("\n[SIGMA] Warning: core.engine.hardware_probe not found. Proceeding with basic info.", Colors.WARNING)

def main():
    parser = argparse.ArgumentParser(description="Sigma Studio Universal Launcher")
    parser.add_argument("--install", action="store_true", help="Install or update dependencies")
    parser.add_argument("--check", action="store_true", help="Verify environment without starting")
    parser.add_argument("--info", action="store_true", help="Show system capabilities")
    args = parser.parse_args()

    platform_info = detect_platform()

    if args.info:
        show_system_info()
        return

    if args.install:
        ensure_venv()
        activate_venv_env()
        install_dependencies(platform_info)
        ensure_frontend()
        return

    # Default Start Sequence
    print_log("[SIGMA] Starting Sigma Studio...", Colors.HEADER)
    ensure_venv()
    activate_venv_env()
    
    if args.check:
        print_log("[SIGMA] Environment checks passed.", Colors.OKGREEN)
        return
        
    ensure_frontend()
    kill_stale_port(8000)
    set_hardware_env()
    launch_server()

if __name__ == "__main__":
    main()
