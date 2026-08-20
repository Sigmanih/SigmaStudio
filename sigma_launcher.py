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
import re
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

    info = {
        "os": system,
        "arch": machine,
        "is_arm": is_arm,
        "is_raspberry_pi": is_raspberry_pi,
        "is_apple_silicon": is_apple_silicon,
        "is_windows": is_windows,
        "is_linux": is_linux,
        "is_darwin": is_darwin
    }
    info.update(detect_compute_backend(info))
    return info


def _nvidia_smi_cuda_version():
    """CUDA version the installed driver supports, as (major, minor), or None."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(["nvidia-smi"], stderr=subprocess.DEVNULL,
                                      timeout=20).decode("utf-8", "replace")
    except Exception:
        return None
    # Driver builds label this differently ("CUDA Version" on older releases,
    # "CUDA UMD Version" on newer ones); both mean the highest CUDA runtime this
    # driver can load, which is what bounds the wheel we may install.
    match = re.search(r"CUDA(?:\s+UMD)?\s+Version:\s*(\d+)\.(\d+)", out)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _has_nvidia_gpu():
    """True only when a driver answers for a real device."""
    if not shutil.which("nvidia-smi"):
        return False
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL, timeout=20,
        ).decode("utf-8", "replace").strip()
        return bool(out)
    except Exception:
        return False


def detect_compute_backend(platform_info):
    """
    Which accelerator this machine actually has.

    Drives both the requirements set and the llama.cpp build, so a Raspberry Pi
    is never handed a CUDA wheel and an NVIDIA box is never left on CPU kernels.
    Detection is by probe, never by assuming what a given OS implies.
    """
    if platform_info.get("is_apple_silicon"):
        return {"compute": "metal", "cuda_version": None}

    if _has_nvidia_gpu():
        cuda = _nvidia_smi_cuda_version()
        return {"compute": "cuda", "cuda_version": cuda}

    # ROCm has no prebuilt llama.cpp wheels; it still selects the CPU torch set
    # and a source build, which is what the AMD path needs anyway.
    if platform_info.get("is_linux") and (
        shutil.which("rocminfo") or os.path.isdir("/opt/rocm")
    ):
        return {"compute": "rocm", "cuda_version": None}

    return {"compute": "cpu", "cuda_version": None}

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
    python_exe, _ = ensure_venv()
    print_log("[SIGMA] Checking and ensuring Python dependencies are installed...", Colors.OKCYAN)

    def run_pip(req_file):
        if os.path.exists(req_file):
            print_log(f"[SIGMA] Installing {req_file}...", Colors.OKCYAN)
            try:
                subprocess.check_call([python_exe, "-m", "pip", "install", "--default-timeout=120", "--retries", "5", "-r", req_file])
                return True
            except subprocess.CalledProcessError as e:
                print_log(f"[SIGMA] Warning: pip install returned error: {e}", Colors.WARNING)
                return False
        return False

    req_dir = "requirements"
    if not os.path.exists(req_dir):
        print_log("[SIGMA] 'requirements' directory not found, falling back to requirements.txt.", Colors.WARNING)
        run_pip("requirements.txt")
        return

    # Base requirements
    run_pip(os.path.join(req_dir, "base.txt"))

    # Platform specific. The set follows the accelerator that was detected, not
    # the operating system: a Linux box without an NVIDIA driver gets the CPU
    # wheels, which is both correct and several gigabytes smaller.
    compute = platform_info.get("compute", "cpu")
    if platform_info["is_darwin"]:
        run_pip(os.path.join(req_dir, "apple.txt"))
    elif compute == "cuda":
        if not run_pip(os.path.join(req_dir, "cuda.txt")):
            run_pip(os.path.join(req_dir, "cpu.txt"))
    else:
        run_pip(os.path.join(req_dir, "cpu.txt"))

    install_inference_kernels(platform_info)

    print_log("[SIGMA] Python dependencies ready.", Colors.OKGREEN)


# ==============================================================================
# Inference kernels
#
# The GGUF runtime is not a normal requirement: the same package name has to be
# built or fetched differently per accelerator, and on ARM there is no wheel at
# all. Leaving it out of the requirement files meant every fresh install could
# download a GGUF model and then fail to run it -- which is exactly the error
# this block exists to prevent.
# ==============================================================================

# Attempts are recorded so a build that cannot succeed on this machine is not
# retried on every single launch. `--install` ignores the record and retries.
_KERNEL_STAMP_NAME = ".sigma_kernels.json"


def _kernel_stamp_path():
    venv_dir, _, _, _ = get_venv_paths()
    return os.path.join(venv_dir, _KERNEL_STAMP_NAME)


def _read_kernel_stamp():
    try:
        with open(_kernel_stamp_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_kernel_stamp(data):
    try:
        with open(_kernel_stamp_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _module_installed(python_exe, module):
    try:
        subprocess.check_call([python_exe, "-c", f"import {module}"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _llama_cpp_wheel_indexes(platform_info):
    """
    Prebuilt llama-cpp-python wheel indexes to try, best match first.

    The CUDA index is keyed by the version the driver reports; nearby tags are
    tried after it because the published set lags new driver releases. An empty
    entry means plain PyPI, which is the right answer on macOS (Metal is built
    in) and the only answer on ARM, where the package builds from source.
    """
    base = "https://abetlen.github.io/llama-cpp-python/whl"

    if platform_info.get("compute") == "cpu" and not platform_info.get("is_arm"):
        # x86 CPU wheels are published too, and are far preferable to spending
        # minutes compiling llama.cpp on a machine that has no accelerator.
        return [f"{base}/cpu", None]

    if platform_info.get("compute") != "cuda":
        return [None]

    tags = []
    cuda = platform_info.get("cuda_version")
    if cuda:
        major, minor = cuda
        # A driver runs any CUDA runtime up to the one it reports, so start at
        # the exact match and walk down.
        for candidate in range(minor, max(minor - 3, -1), -1):
            tags.append(f"cu{major}{candidate}")
    # The published set lags new driver releases; these are the tags that have
    # actually been built, tried after anything the driver hinted at.
    for fallback in ("cu125", "cu124", "cu123", "cu122", "cu121"):
        if fallback not in tags:
            tags.append(fallback)

    return [f"{base}/{tag}" for tag in tags] + [None]


def _index_serves_package(index_url, package="llama-cpp-python", timeout=8):
    """
    Whether a PEP 503 index actually publishes this package.

    Driver versions run ahead of the published wheel set, so most of the
    candidate tags 404. Checking here turns each miss into one HTTP request
    instead of a full pip resolution. A network failure returns True: better to
    let pip try than to skip a tag because the check itself could not run.
    """
    import urllib.request
    import urllib.error

    url = f"{index_url.rstrip('/')}/{package}/"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def _ensure_build_toolchain(platform_info):
    """
    cmake and a C++ compiler, needed wherever llama.cpp builds from source.

    Returns False when the toolchain is missing and cannot be installed, so the
    caller reports what to run instead of starting a build that cannot finish.
    """
    if shutil.which("cmake") and (shutil.which("c++") or shutil.which("g++") or shutil.which("cc")):
        return True

    if platform_info.get("is_linux") and shutil.which("apt-get"):
        print_log("[SIGMA] Installing build toolchain for llama.cpp (build-essential, cmake)...", Colors.OKCYAN)
        subprocess.run(["sudo", "apt-get", "update", "-y"], check=False)
        subprocess.run(["sudo", "apt-get", "install", "-y", "build-essential", "cmake"], check=False)
        return bool(shutil.which("cmake"))

    return bool(shutil.which("cmake"))


def install_inference_kernels(platform_info, force=False):
    """
    Installs the llama.cpp GGUF runtime for the accelerator on this machine.

    Cheap when already present: an import check short-circuits before pip is
    ever invoked, so this costs nothing on a normal launch.
    """
    python_exe, _ = ensure_venv()

    if _module_installed(python_exe, "llama_cpp"):
        return True

    compute = platform_info.get("compute", "cpu")
    key = f"llama_cpp:{compute}:{platform_info.get('arch')}:{sys.version_info.major}.{sys.version_info.minor}"
    stamp = _read_kernel_stamp()

    if not force and stamp.get(key, {}).get("status") == "failed":
        print_log(
            "[SIGMA] GGUF runtime (llama-cpp-python) not installed and a previous "
            "attempt failed; skipping. Retry with: python sigma_launcher.py --install",
            Colors.WARNING,
        )
        return False

    print_log(f"[SIGMA] Installing GGUF runtime (llama-cpp-python) for '{compute}'...", Colors.OKCYAN)

    # Only Linux gets the toolchain gate: macOS ships arm64 wheels on PyPI and
    # clang with the command line tools, so blocking there would refuse an
    # install that would have worked.
    needs_source_build = platform_info.get("is_linux") and (
        platform_info.get("is_arm") or compute == "rocm"
    )
    if needs_source_build and not _ensure_build_toolchain(platform_info):
        print_log(
            "[SIGMA] llama-cpp-python must be compiled on this architecture and no "
            "toolchain was found. Install it and relaunch:\n"
            "  sudo apt-get install -y build-essential cmake python3-dev",
            Colors.WARNING,
        )
        stamp[key] = {"status": "failed", "reason": "toolchain missing"}
        _write_kernel_stamp(stamp)
        return False

    if needs_source_build:
        print_log(
            "[SIGMA] No prebuilt wheel is published for this architecture: llama.cpp "
            "will be compiled from source. This runs once and can take several "
            "minutes on a small board.",
            Colors.WARNING,
        )

    env = os.environ.copy()
    if compute == "metal":
        env.setdefault("CMAKE_ARGS", "-DGGML_METAL=on")
    elif compute == "rocm":
        env.setdefault("CMAKE_ARGS", "-DGGML_HIPBLAS=on")

    if platform_info.get("is_raspberry_pi") or platform_info.get("is_arm"):
        # Limita a 2 core su Raspberry Pi per evitare cali di tensione (brownout), surriscaldamento ed esaurimento RAM
        env.setdefault("CMAKE_BUILD_PARALLEL_LEVEL", "2")


    for index_url in _llama_cpp_wheel_indexes(platform_info):
        if index_url and not _index_serves_package(index_url):
            continue
        cmd = [python_exe, "-m", "pip", "install", "--default-timeout=120",
               "llama-cpp-python>=0.3.0"]
        if index_url:
            # --only-binary matters: an index tag that was never published 404s,
            # and without it pip would quietly fall back to PyPI and compile a
            # CPU-only build, reporting success while dropping GPU offload.
            cmd += ["--extra-index-url", index_url, "--only-binary=:all:"]
            print_log(f"[SIGMA] Trying prebuilt wheels from {index_url}", Colors.OKCYAN)
        else:
            print_log("[SIGMA] Falling back to a source build from PyPI...", Colors.OKCYAN)
        try:
            subprocess.check_call(cmd, env=env)
        except subprocess.CalledProcessError:
            continue
        if _module_installed(python_exe, "llama_cpp"):
            stamp[key] = {"status": "ok", "index": index_url or "pypi"}
            _write_kernel_stamp(stamp)
            print_log("[SIGMA] GGUF runtime ready: modelli .gguf eseguibili.", Colors.OKGREEN)
            return True

    stamp[key] = {"status": "failed", "reason": "pip install failed"}
    _write_kernel_stamp(stamp)
    print_log(
        "[SIGMA] WARNING: llama-cpp-python could not be installed. Safetensors "
        "models still work; GGUF checkpoints will not load until it is present.",
        Colors.WARNING,
    )
    return False


def _get_path_hash(path):
    sha1 = hashlib.sha1()
    if not os.path.exists(path):
        return sha1.hexdigest()
    if os.path.isfile(path):
        try:
            with open(path, 'rb') as f:
                while True:
                    buf = f.read(4096)
                    if not buf:
                        break
                    sha1.update(buf)
        except Exception:
            pass
        return sha1.hexdigest()

    for root, _, files in os.walk(path):
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

_get_directory_hash = _get_path_hash

def check_node_version():
    """Return major version number of Node.js (e.g. 18, 20, 22) or 0 if not found."""
    try:
        cmd = ["node.exe"] if os.name == 'nt' else ["node"]
        out = subprocess.check_output(cmd + ["-v"], stderr=subprocess.DEVNULL).decode().strip()
        if out.startswith("v"):
            return int(out.lstrip("v").split(".")[0])
    except Exception:
        pass
    return 0

def auto_install_node_npm():
    """Attempt to automatically install or upgrade to Node.js (>= 20 LTS) using the system package manager."""
    print_log("[SIGMA] Installing/Upgrading Node.js (>= 20 LTS) and npm...", Colors.OKCYAN)
    system = platform.system().lower()
    
    try:
        if system == "linux":
            if shutil.which("apt-get"):
                print_log("[SIGMA] Setting up NodeSource Node.js 20.x LTS repository for Debian/Ubuntu/Raspberry Pi...", Colors.OKCYAN)
                if not shutil.which("curl"):
                    subprocess.run(["sudo", "apt-get", "update", "-y"], check=False)
                    subprocess.run(["sudo", "apt-get", "install", "-y", "curl", "ca-certificates"], check=False)
                cmd = "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
                subprocess.run(["bash", "-c", cmd], check=False)
            elif shutil.which("dnf"):
                subprocess.run(["sudo", "dnf", "install", "-y", "nodejs", "npm"], check=False)
            elif shutil.which("pacman"):
                subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"], check=False)
            elif shutil.which("apk"):
                subprocess.run(["sudo", "apk", "add", "nodejs", "npm"], check=False)
        elif system == "darwin":
            if shutil.which("brew"):
                print_log("[SIGMA] Installing/Upgrading node via Homebrew...", Colors.OKCYAN)
                subprocess.run(["brew", "install", "node"], check=False)
        elif system == "windows":
            if shutil.which("winget"):
                print_log("[SIGMA] Installing Node.js via winget...", Colors.OKCYAN)
                subprocess.run(["winget", "install", "OpenJS.NodeJS.LTS", "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"], check=False)
    except Exception as e:
        print_log(f"[SIGMA] Auto-install attempt ended: {e}", Colors.WARNING)

def ensure_frontend():
    print_log("[SIGMA] Checking frontend...", Colors.OKCYAN)
    
    frontend_dir = os.path.abspath("sigma_studio")
    dist_dir = os.path.join(frontend_dir, "dist")
    src_dir = os.path.join(frontend_dir, "src")
    pkg_json = os.path.join(frontend_dir, "package.json")
    node_modules_dir = os.path.join(frontend_dir, "node_modules")
    hash_file = os.path.join(frontend_dir, ".build_stamp")
    
    # Check for npm and Node.js version
    npm_bin = shutil.which("npm")
    if not npm_bin and os.name == 'nt':
        npm_bin = shutil.which("npm.cmd")
        
    node_ver = check_node_version()
    
    # Vite 8 requires Node.js >= 20.19.0 or >= 22.12.0
    if not npm_bin or (node_ver > 0 and node_ver < 20):
        if node_ver > 0 and node_ver < 20:
            print_log(f"[SIGMA] Detected Node.js v{node_ver}, but Vite requires Node.js >= 20. Upgrading...", Colors.WARNING)
        auto_install_node_npm()
        npm_bin = shutil.which("npm") or (shutil.which("npm.cmd") if os.name == 'nt' else None)
        node_ver = check_node_version()
        
    if not npm_bin or (node_ver > 0 and node_ver < 20):
        if os.path.exists(os.path.join(dist_dir, "index.html")):
            print_log("[SIGMA] WARNING: Node.js >= 20 not found. Using pre-built frontend in sigma_studio/dist.", Colors.WARNING)
            return
        else:
            print_log("[SIGMA] ERROR: Node.js (>= 20 LTS) is required to build the frontend.", Colors.FAIL, True)
            print_log("[SIGMA] Please install Node.js 20 LTS manually:\n  - Debian/Ubuntu/Raspberry Pi: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs\n  - macOS: brew install node\n  - Windows: winget install OpenJS.NodeJS.LTS", Colors.WARNING)
            sys.exit(1)

    # Reusing SHA-1 fingerprint logic pattern
    package_json_hash = _get_directory_hash(pkg_json)
    src_hash = _get_directory_hash(src_dir)
    current_hash = hashlib.sha1((package_json_hash + src_hash).encode('utf-8')).hexdigest()
    
    built_hash = ""
    if os.path.exists(hash_file):
        try:
            with open(hash_file, "r", encoding="utf-8") as f:
                built_hash = f.read().strip()
        except Exception:
            pass
            
    needs_build = (built_hash != current_hash) or not os.path.exists(os.path.join(dist_dir, "index.html"))
    
    if needs_build:
        print_log("[SIGMA] Frontend build required. Preparing assets...", Colors.OKCYAN)
        lock_file = os.path.join(frontend_dir, "package-lock.json")
        
        if not os.path.exists(node_modules_dir):
            print_log("[SIGMA] Installing frontend dependencies (npm install)...", Colors.OKCYAN)
            subprocess.run([npm_bin, "install", "--include=optional"], cwd=frontend_dir, check=False)
            
        print_log("[SIGMA] Running Vite build (npm run build)...", Colors.OKCYAN)
        res = subprocess.run([npm_bin, "run", "build"], cwd=frontend_dir)
        
        # Self-healing for cross-platform optionalDependencies bug (e.g. missing native rolldown/esbuild binding on arm64)
        if res.returncode != 0:
            print_log("[SIGMA] Build failed due to missing platform native bindings. Cleaning stale node_modules & package-lock.json for fresh install...", Colors.WARNING)
            if os.path.exists(node_modules_dir):
                shutil.rmtree(node_modules_dir, ignore_errors=True)
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except Exception:
                    pass
            print_log("[SIGMA] Reinstalling frontend dependencies with optional native packages...", Colors.OKCYAN)
            subprocess.run([npm_bin, "install", "--include=optional"], cwd=frontend_dir, check=False)
            print_log("[SIGMA] Retrying Vite build...", Colors.OKCYAN)
            res = subprocess.run([npm_bin, "run", "build"], cwd=frontend_dir)
        
        if res.returncode == 0:
            try:
                with open(hash_file, "w", encoding="utf-8") as f:
                    f.write(current_hash)
            except Exception:
                pass
            print_log("[SIGMA] Frontend build complete.", Colors.OKGREEN)
        else:
            print_log("[SIGMA] WARNING: Frontend build failed. Checking for existing dist folder...", Colors.WARNING)
            if not os.path.exists(os.path.join(dist_dir, "index.html")):
                print_log("[SIGMA] ERROR: No valid frontend build found in sigma_studio/dist.", Colors.FAIL, True)
                sys.exit(1)
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
    print(f"  - llama_cpp installed: {_module_installed(python_exe, 'llama_cpp')}")
    
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
    parser.add_argument("--no-llama", "--skip-inference-kernels", dest="skip_inference_kernels", action="store_true", help="Skip compiling llama-cpp-python (start Sigma Studio immediately)")
    args = parser.parse_args()

    platform_info = detect_platform()

    if args.info:
        show_system_info()
        return

    if args.install:
        ensure_venv()
        activate_venv_env()
        install_dependencies(platform_info)
        # Explicit --install means "try again", including builds that failed
        # before and are skipped on a normal launch.
        if not args.skip_inference_kernels:
            install_inference_kernels(platform_info, force=True)
        ensure_frontend()
        return

    # Default Start Sequence
    print_log("[SIGMA] Starting Sigma Studio...", Colors.HEADER)
    ensure_venv()
    activate_venv_env()
    install_dependencies(platform_info)
    
    if args.check:
        print_log("[SIGMA] Environment checks passed.", Colors.OKGREEN)
        return
        
    ensure_frontend()
    kill_stale_port(8000)
    set_hardware_env()
    launch_server()

if __name__ == "__main__":
    main()
