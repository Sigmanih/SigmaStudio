# ==============================================================================
# core/sandbox_manager.py — Virtual Environment & Sandbox Management
# Sigma Studio v7 — Gestisce venv Python, node_modules, e sandbox isolate
# per permettere all'AI di installare pacchetti, eseguire build, test, ecc.
# ==============================================================================
"""Sandbox manager for Sigma Studio.
- Creazione/gestione virtualenv Python
- Installazione pacchetti pip/npm
- Esecuzione comandi in sandbox isolate
- Registrazione stato sandbox in sandboxes.json"""

import os
import json
import subprocess
import sys
import datetime
import shutil

SANDBOXES_FILE = "sandboxes.json"
ALLOWED_SANDBOX_DIRS = frozenset({
    'sigma_studio', 'core', 'data', 'scratch', 'manifesti', 'viz',
})


# ==============================================================================
# VENV / NPM Auto-setup
# ==============================================================================

def ensure_venv():
    """Create and activate Python virtual environment if not exists.
    Returns (success, message)."""
    venv_dir = '.venv'
    if os.path.isdir(venv_dir) and os.path.isfile(os.path.join(venv_dir, 'pyvenv.cfg')):
        return True, "VENV già esistente"
    
    try:
        print(f"[SANDBOX] Creazione virtual environment in {venv_dir}...")
        result = subprocess.run(
            [sys.executable, '-m', 'venv', venv_dir],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return False, f"Errore creazione venv: {result.stderr[:200]}"
        
        # Install basic packages
        pip_cmd = _get_pip_path()
        if pip_cmd:
            print("[SANDBOX] Installazione pacchetti base...")
            subprocess.run(
                [pip_cmd, 'install', 'requests', 'beautifulsoup4', 'lxml'],
                capture_output=True, text=True, timeout=120
            )
        
        return True, f"VENV creato in {venv_dir}"
    except Exception as e:
        return False, f"Errore creazione venv: {str(e)}"


def ensure_npm():
    """Install npm packages for sigma_studio if not exists.
    Returns (success, message)."""
    node_modules = 'sigma_studio/node_modules'
    package_json = 'sigma_studio/package.json'
    
    if os.path.isdir(node_modules) and os.path.isfile(package_json):
        return True, "node_modules già esistente"
    
    if not os.path.isfile(package_json):
        return False, "package.json non trovato in sigma_studio/"
    
    npm_cmd = shutil.which('npm') or shutil.which('npm.cmd')
    if not npm_cmd:
        return False, "npm non trovato nel PATH"
    
    try:
        print("[SANDBOX] Installazione npm packages...")
        result = subprocess.run(
            [npm_cmd, 'install', '--no-audit', '--no-fund'],
            cwd='sigma_studio', capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            return False, f"npm install fallito: {result.stderr[:300]}"
        return True, "npm packages installati"
    except subprocess.TimeoutExpired:
        return False, "Timeout npm install (180s)"
    except Exception as e:
        return False, f"Errore npm: {str(e)}"


def _get_pip_path():
    """Get the pip executable path based on OS."""
    venv_dir = '.venv'
    if os.name == 'nt':
        pip = os.path.join(venv_dir, 'Scripts', 'pip.exe')
        python = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        pip = os.path.join(venv_dir, 'bin', 'pip')
        python = os.path.join(venv_dir, 'bin', 'python')
    
    if os.path.isfile(pip):
        return pip
    if os.path.isfile(python):
        # Use python -m pip as fallback
        return [python, '-m', 'pip']
    return None


# ==============================================================================
# SANDBOX STATE
# ==============================================================================

def _load_sandboxes():
    """Load sandbox state from JSON file."""
    if os.path.exists(SANDBOXES_FILE):
        try:
            with open(SANDBOXES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"sandboxes": [], "last_id": 0}


def _save_sandboxes(data):
    """Save sandbox state to JSON file."""
    with open(SANDBOXES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


# ==============================================================================
# SANDBOX OPERATIONS
# ==============================================================================

def create_sandbox(name, template="python", install_deps=True):
    """Create a new sandbox project.
    
    Args:
        name: Project name (used as directory name)
        template: "python" | "node" | "fullstack"
        install_deps: Auto-install dependencies
    
    Returns:
        (success, sandbox_info_or_error)
    """
    # Validate name
    safe_name = name.lower().replace(' ', '_').replace('/', '_')
    if not safe_name:
        return False, "Nome progetto non valido"
    
    project_dir = f"projects/{safe_name}"
    os.makedirs(project_dir, exist_ok=True)
    
    sandbox = {
        "id": None,
        "name": safe_name,
        "dir": project_dir,
        "template": template,
        "created": datetime.datetime.now().isoformat(),
        "venv_created": False,
        "npm_installed": False,
        "status": "created",
    }
    
    try:
        if template in ("python", "fullstack"):
            # Create Python venv
            venv_result = subprocess.run(
                [sys.executable, '-m', 'venv', os.path.join(project_dir, '.venv')],
                capture_output=True, text=True, timeout=60
            )
            if venv_result.returncode == 0:
                sandbox["venv_created"] = True
                if install_deps:
                    pip_path = os.path.join(project_dir, '.venv', 'Scripts' if os.name == 'nt' else 'bin', 'pip')
                    pip_cmd = pip_path if os.path.isfile(pip_path) else [sys.executable, '-m', 'pip']
                    subprocess.run(
                        [pip_cmd, 'install', 'pytest', 'numpy'] if isinstance(pip_cmd, str) else pip_cmd + ['install', 'pytest', 'numpy'],
                        capture_output=True, text=True, timeout=120
                    )
        
        if template in ("node", "fullstack"):
            # Create package.json and install
            package = {"name": safe_name, "version": "1.0.0", "private": True, "scripts": {"test": "echo ok"}}
            with open(os.path.join(project_dir, 'package.json'), 'w') as f:
                json.dump(package, f, indent=2)
            
            npm_cmd = shutil.which('npm') or shutil.which('npm.cmd')
            if npm_cmd and install_deps:
                subprocess.run(
                    [npm_cmd, 'install', '--no-audit', '--no-fund'],
                    cwd=project_dir, capture_output=True, text=True, timeout=180
                )
            sandbox["npm_installed"] = True
        
        sandbox["status"] = "ready"
        
        # Register in sandboxes.json
        data = _load_sandboxes()
        data["last_id"] += 1
        sandbox["id"] = data["last_id"]
        data["sandboxes"].append(sandbox)
        _save_sandboxes(data)
        
        return True, sandbox
    except Exception as e:
        sandbox["status"] = "error"
        return False, f"Errore creazione sandbox: {str(e)}"


def run_in_sandbox(sandbox_id, cmd, cwd=None, timeout=120):
    """Run a command inside a sandbox.
    
    Args:
        sandbox_id: Sandbox ID
        cmd: Command to execute (string or list)
        cwd: Working directory relative to sandbox root
        timeout: Timeout in seconds
    
    Returns:
        (success, result_dict)
    """
    data = _load_sandboxes()
    sandbox = next((s for s in data["sandboxes"] if s["id"] == sandbox_id), None)
    if not sandbox:
        return False, {"error": f"Sandbox {sandbox_id} non trovata"}
    
    # Build working directory
    base_dir = sandbox["dir"]
    if cwd:
        base_dir = os.path.join(base_dir, cwd)
    
    if not os.path.isdir(base_dir):
        return False, {"error": f"Directory {base_dir} non trovata"}
    
    # Activate venv if Python template
    shell_cmd = cmd
    if sandbox["template"] in ("python", "fullstack") and sandbox.get("venv_created"):
        venv_activate = os.path.join(sandbox["dir"], '.venv', 'Scripts' if os.name == 'nt' else 'bin', 'activate')
        if os.name == 'nt':
            # Windows: use the venv python directly
            python_path = os.path.join(sandbox["dir"], '.venv', 'Scripts', 'python.exe')
            if os.path.isfile(python_path):
                shell_cmd = f'"{python_path}" -c "{cmd}"' if '"' not in cmd else cmd
        else:
            # Unix: source activate then run
            shell_cmd = f'. "{venv_activate}" && {cmd}'
    
    try:
        result = subprocess.run(
            shell_cmd if isinstance(shell_cmd, str) else shell_cmd,
            shell=True, capture_output=True, text=True, timeout=timeout,
            cwd=base_dir, encoding='utf-8', errors='replace'
        )
        return result.returncode == 0, {
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "exit_code": result.returncode,
            "cmd": cmd[:200],
            "sandbox_id": sandbox_id,
        }
    except subprocess.TimeoutExpired:
        return False, {"error": f"Timeout ({timeout}s)", "cmd": cmd[:200], "sandbox_id": sandbox_id}
    except Exception as e:
        return False, {"error": str(e), "cmd": cmd[:200], "sandbox_id": sandbox_id}


def install_package(sandbox_id, package, manager="auto"):
    """Install a package in a sandbox.
    
    Args:
        sandbox_id: Sandbox ID
        package: Package name (e.g. "numpy", "react")
        manager: "pip" | "npm" | "auto"
    
    Returns:
        (success, message)
    """
    data = _load_sandboxes()
    sandbox = next((s for s in data["sandboxes"] if s["id"] == sandbox_id), None)
    if not sandbox:
        return False, f"Sandbox {sandbox_id} non trovata"
    
    # Auto-detect manager
    if manager == "auto":
        if sandbox["template"] in ("python",):
            manager = "pip"
        elif sandbox["template"] in ("node",):
            manager = "npm"
        elif sandbox["template"] == "fullstack":
            manager = "pip"  # default to pip for fullstack
    
    try:
        if manager == "pip":
            pip_path = os.path.join(sandbox["dir"], '.venv', 'Scripts' if os.name == 'nt' else 'bin', 'pip')
            if not os.path.isfile(pip_path):
                pip_path = os.path.join(sandbox["dir"], '.venv', 'Scripts' if os.name == 'nt' else 'bin', 'python.exe')
                result = subprocess.run(
                    [pip_path, '-m', 'pip', 'install', package] if pip_path.endswith('.exe') else [sys.executable, '-m', 'pip', 'install', package],
                    capture_output=True, text=True, timeout=120, cwd=sandbox["dir"]
                )
            else:
                result = subprocess.run(
                    [pip_path, 'install', package],
                    capture_output=True, text=True, timeout=120, cwd=sandbox["dir"]
                )
        elif manager == "npm":
            npm_cmd = shutil.which('npm') or shutil.which('npm.cmd')
            if not npm_cmd:
                return False, "npm non trovato"
            result = subprocess.run(
                [npm_cmd, 'install', package, '--save', '--no-audit'],
                capture_output=True, text=True, timeout=120, cwd=sandbox["dir"]
            )
        else:
            return False, f"Manager sconosciuto: {manager}"
        
        if result.returncode == 0:
            return True, f"{package} installato con {manager}"
        else:
            return False, f"Errore installazione {package}: {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout installazione {package}"
    except Exception as e:
        return False, f"Errore: {str(e)}"


def destroy_sandbox(sandbox_id, keep_src=True):
    """Destroy a sandbox (remove venv/node_modules).
    
    Args:
        sandbox_id: Sandbox ID
        keep_src: If True, only remove venv and node_modules, keep source files
    
    Returns:
        (success, message)
    """
    data = _load_sandboxes()
    sandbox = next((s for s in data["sandboxes"] if s["id"] == sandbox_id), None)
    if not sandbox:
        return False, f"Sandbox {sandbox_id} non trovata"
    
    sandbox_dir = sandbox["dir"]
    
    try:
        if keep_src:
            # Remove only venv and node_modules
            venv_dir = os.path.join(sandbox_dir, '.venv')
            nm_dir = os.path.join(sandbox_dir, 'node_modules')
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir, ignore_errors=True)
            if os.path.isdir(nm_dir):
                shutil.rmtree(nm_dir, ignore_errors=True)
            sandbox["venv_created"] = False
            sandbox["npm_installed"] = False
        else:
            # Remove entire directory
            if os.path.isdir(sandbox_dir):
                shutil.rmtree(sandbox_dir, ignore_errors=True)
        
        sandbox["status"] = "destroyed"
        _save_sandboxes(data)
        return True, f"Sandbox {sandbox_id} {'pulita' if keep_src else 'eliminata'}"
    except Exception as e:
        return False, f"Errore: {str(e)}"


def list_sandboxes():
    """List all sandboxes."""
    data = _load_sandboxes()
    return data["sandboxes"]


def get_sandbox(sandbox_id):
    """Get a single sandbox by ID."""
    data = _load_sandboxes()
    return next((s for s in data["sandboxes"] if s["id"] == sandbox_id), None)


# ==============================================================================
# API Handlers
# ==============================================================================

def handle_sandbox_create(self):
    """POST /api/sandbox/create — Create a new sandbox."""
    try:
        req = self.read_json_body()
        name = req.get("name", "sandbox_" + datetime.datetime.now().strftime("%H%M%S"))
        template = req.get("template", "python")
        install_deps = req.get("install_deps", True)
        
        success, result = create_sandbox(name, template, install_deps)
        if success:
            return self.send_json_response({"success": True, "sandbox": result})
        return self.send_json_response({"success": False, "error": result}, 400)
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)


def handle_sandbox_run(self):
    """POST /api/sandbox/run — Run a command in a sandbox."""
    try:
        req = self.read_json_body()
        sandbox_id = int(req.get("sandbox_id", 0))
        cmd = req.get("cmd", "")
        cwd = req.get("cwd", "")
        timeout = int(req.get("timeout", 120))
        
        if not sandbox_id or not cmd:
            return self.send_json_response({"error": "sandbox_id e cmd richiesti"}, 400)
        
        success, result = run_in_sandbox(sandbox_id, cmd, cwd, timeout)
        return self.send_json_response({
            "success": success,
            "result": result
        })
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)


def handle_sandbox_install(self):
    """POST /api/sandbox/install — Install a package in a sandbox."""
    try:
        req = self.read_json_body()
        sandbox_id = int(req.get("sandbox_id", 0))
        package = req.get("package", "")
        manager = req.get("manager", "auto")
        
        success, message = install_package(sandbox_id, package, manager)
        return self.send_json_response({"success": success, "message": message})
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)


def handle_sandbox_list(self):
    """GET /api/sandbox/list — List all sandboxes."""
    try:
        return self.send_json_response({"sandboxes": list_sandboxes()})
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)


def handle_sandbox_destroy(self):
    """POST /api/sandbox/destroy — Destroy a sandbox."""
    try:
        req = self.read_json_body()
        sandbox_id = int(req.get("sandbox_id", 0))
        keep_src = req.get("keep_src", True)
        
        success, message = destroy_sandbox(sandbox_id, keep_src)
        return self.send_json_response({"success": success, "message": message})
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)