# ==============================================================================
# core/training/endpoints.py — Pool di servitori Ollama
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Gestisce l'insieme di endpoint Ollama su cui Sigma distribuisce il lavoro.

Il motivo per cui questo modulo esiste, verificato sulla macchina e non dedotto:
un servitore Ollama carica un modello su **una sola** GPU. Con due schede, un
modello da 5 GB occupa la prima e lascia la seconda a zero — e nessun valore di
`OLLAMA_NUM_PARALLEL` la sveglia, perche' quella variabile moltiplica gli slot
sull'istanza già caricata, non le istanze.

Per usare tutte le schede servono piu' servitori, uno per GPU, ognuno con il suo
`CUDA_VISIBLE_DEVICES` e la sua porta. Questo modulo li scopre, li sorveglia e —
su richiesta esplicita — li avvia.

Niente e' cablato al numero di GPU o alla porta 11434: il pool vale per una
macchina con una scheda, per una con otto, e per endpoint remoti.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time

import requests

from core.logger import get_logger

log = get_logger(__name__)

CONFIG_FILE = "config.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11434
#: Porte sondate quando si cercano istanze già in ascolto.
DISCOVERY_PORTS = tuple(range(11434, 11444))
HEALTH_TIMEOUT = 2

#: Registro su disco delle istanze avviate da Sigma. Deve sopravvivere al
#: processo che le ha lanciate: sono servitori indipendenti, e tenerne traccia
#: solo in memoria significava lasciarli vivi senza piu' un modo per fermarli.
INSTANCES_FILE = os.path.join("training_lab", "ollama_instances.json")

_lock = threading.RLock()
_managed: dict[int, subprocess.Popen] = {}   # porta -> processo, se avviato qui


# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================

def _load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=4, ensure_ascii=False)
    os.replace(tmp, CONFIG_FILE)


def _normalize(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def configured_endpoints() -> list[dict]:
    """Endpoint salvati dall'utente in config.json, in ordine di preferenza."""
    raw = _load_config().get("ollama_endpoints") or []
    out = []
    for entry in raw:
        if isinstance(entry, str):
            entry = {"url": entry}
        url = _normalize(entry.get("url", ""))
        if url:
            out.append({
                "url": url,
                "gpu_index": entry.get("gpu_index"),
                "label": entry.get("label", ""),
            })
    return out


def save_endpoints(endpoints: list[dict]) -> None:
    with _lock:
        cfg = _load_config()
        cfg["ollama_endpoints"] = [{
            "url": _normalize(e.get("url", "")),
            "gpu_index": e.get("gpu_index"),
            "label": e.get("label", ""),
        } for e in endpoints if _normalize(e.get("url", ""))]
        _save_config(cfg)


# ==============================================================================
# SCOPERTA E SALUTE
# ==============================================================================

def check_endpoint(url: str) -> dict:
    """Interroga un endpoint: raggiungibile, quanti modelli, quali caricati."""
    url = _normalize(url)
    info = {"url": url, "reachable": False, "models": 0, "loaded": [], "error": ""}
    try:
        res = requests.get(f"{url}/api/tags", timeout=HEALTH_TIMEOUT)
        if res.status_code != 200:
            info["error"] = f"HTTP {res.status_code}"
            return info
        info["reachable"] = True
        info["models"] = len(res.json().get("models", []))
    except Exception as err:
        info["error"] = str(err)[:120]
        return info

    try:
        running = requests.get(f"{url}/api/ps", timeout=HEALTH_TIMEOUT)
        if running.status_code == 200:
            info["loaded"] = [{
                "name": m.get("name", ""),
                "vram_gb": round(m.get("size_vram", 0) / (1024 ** 3), 2),
            } for m in running.json().get("models", [])]
    except Exception as err:
        log.debug("Stato dei modelli di %s non leggibile: %s", url, err)
    return info


def discover_endpoints(ports=DISCOVERY_PORTS) -> list[str]:
    """Cerca servitori Ollama già in ascolto sulle porte tipiche.

    Sonda in parallelo: in sequenza, dieci porte chiuse costerebbero dieci
    timeout uno dopo l'altro.
    """
    import concurrent.futures

    def probe(port: int) -> str | None:
        url = f"http://{DEFAULT_HOST}:{port}"
        try:
            res = requests.get(f"{url}/api/tags", timeout=1)
            return url if res.status_code == 200 else None
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tuple(ports))) as pool:
        found = list(pool.map(probe, ports))
    return [url for url in found if url]


def active_endpoints(refresh: bool = True) -> list[dict]:
    """Il pool effettivo: configurato se c'e', altrimenti scoperto.

    Restituisce sempre almeno l'endpoint predefinito, cosi' il resto del codice
    non deve gestire il caso "nessun pool".
    """
    configured = configured_endpoints()
    if not configured:
        urls = discover_endpoints() if refresh else []
        default = _normalize(os.environ.get("OLLAMA_HOST", f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"))
        if default not in urls:
            urls.insert(0, default)
        configured = [{"url": u, "gpu_index": None, "label": ""} for u in urls]

    if not refresh:
        return configured

    for endpoint in configured:
        endpoint.update(check_endpoint(endpoint["url"]))
        endpoint["managed"] = _port_of(endpoint["url"]) in _managed
    return configured


def healthy_urls() -> list[str]:
    """URL raggiungibili, nell'ordine in cui distribuire le richieste."""
    urls = [e["url"] for e in active_endpoints() if e.get("reachable")]
    if urls:
        return urls
    # Nessuna sonda andata a buon fine: si tenta comunque il predefinito, cosi'
    # un errore di rete momentaneo non blocca del tutto un run.
    return [_normalize(os.environ.get("OLLAMA_HOST", f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"))]


def _port_of(url: str) -> int:
    try:
        return int(url.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return DEFAULT_PORT


# ==============================================================================
# ISTANZE LOCALI AGGIUNTIVE
# ==============================================================================

def _load_instances() -> list[dict]:
    try:
        with open(INSTANCES_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_instances(instances: list[dict]) -> None:
    os.makedirs("training_lab", exist_ok=True)
    tmp = INSTANCES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(instances, fh, indent=2)
    os.replace(tmp, INSTANCES_FILE)


def _remember_instance(port: int, pid: int, gpu_index: int) -> None:
    with _lock:
        instances = [i for i in _load_instances() if i.get("port") != port]
        instances.append({
            "port": port, "pid": pid, "gpu_index": gpu_index,
            "url": f"http://{DEFAULT_HOST}:{port}",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        _save_instances(instances)


def _forget_instance(port: int) -> dict | None:
    with _lock:
        instances = _load_instances()
        found = next((i for i in instances if i.get("port") == port), None)
        _save_instances([i for i in instances if i.get("port") != port])
        return found


def managed_instances() -> list[dict]:
    """Istanze avviate da Sigma, con lo stato attuale di ognuna."""
    out = []
    for entry in _load_instances():
        health = check_endpoint(entry.get("url", ""))
        out.append({**entry, "reachable": health["reachable"], "loaded": health["loaded"]})
    return out


def _kill_pid(pid: int) -> bool:
    """Termina un processo per PID, su Windows come su POSIX."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=15)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception as err:
        log.warning("Terminazione del processo %s non riuscita: %s", pid, err)
        return False


def instance_env(gpu_index: int, backend: str = "cuda") -> dict:
    """Variabili che legano un servitore Ollama a una sola scheda.

    Non basta `CUDA_VISIBLE_DEVICES`. Verificato sui log di avvio: Ollama scopre
    le GPU anche via Vulkan, e quel percorso ignora la variabile CUDA — con due
    schede NVIDIA, l'istanza "legata" alla seconda vedeva comunque la prima e ci
    caricava sopra il modello, perche' e' la piu' capiente. Spegnere il backend
    che non serve e' cio' che rende l'assegnazione effettiva.
    """
    backend = (backend or "cuda").lower()
    env = {
        # Ordine per bus PCI: allinea l'indice a quello di nvidia-smi e lo rende
        # stabile fra macchine diverse.
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
    }
    if backend == "cuda":
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
        env["OLLAMA_VULKAN"] = "0"
    elif backend == "rocm":
        env["ROCR_VISIBLE_DEVICES"] = str(gpu_index)
        env["HIP_VISIBLE_DEVICES"] = str(gpu_index)
        env["OLLAMA_VULKAN"] = "0"
    else:  # vulkan e affini: il filtro ha un nome tutto suo
        env["GGML_VK_VISIBLE_DEVICES"] = str(gpu_index)
    return env


def instance_command(gpu_index: int, port: int, backend: str = "cuda") -> dict:
    """Il comando che lega un servitore Ollama a una GPU precisa.

    Esposto anche come testo perche' l'utente possa avviarlo a mano, in un
    terminale che sopravvive a Sigma, invece di dipendere da questo processo.
    """
    env = {**instance_env(gpu_index, backend),
           "OLLAMA_HOST": f"{DEFAULT_HOST}:{port}",
           "OLLAMA_NUM_PARALLEL": "4"}
    return {
        "gpu_index": gpu_index,
        "port": port,
        "backend": backend,
        "url": f"http://{DEFAULT_HOST}:{port}",
        "env": env,
        "windows_cmd": " && ".join([*(f"set {k}={v}" for k, v in env.items()), "ollama serve"]),
        "powershell_cmd": "; ".join([*(f'$env:{k}="{v}"' for k, v in env.items()), "ollama serve"]),
        "bash_cmd": " ".join(f"{k}={v}" for k, v in env.items()) + " ollama serve",
    }


def free_port(start: int = DEFAULT_PORT + 1) -> int:
    """Prima porta libera dopo quella predefinita."""
    import socket
    for port in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((DEFAULT_HOST, port)) != 0:
                return port
    return start


def start_instance(gpu_index: int, port: int | None = None, wait: int = 25,
                   backend: str = "cuda") -> dict:
    """Avvia un servitore Ollama legato a una GPU e lo registra nel pool.

    Azione esplicita: mette in piedi un servizio che resta vivo finche' non lo si
    ferma. Non viene mai lanciata da sola, solo su richiesta dell'utente.
    """
    binary = shutil.which("ollama")
    if not binary:
        return {"success": False, "error": "Eseguibile 'ollama' non trovato nel PATH"}

    port = port or free_port()
    url = f"http://{DEFAULT_HOST}:{port}"
    if check_endpoint(url)["reachable"]:
        return {"success": False, "error": f"La porta {port} risponde già: endpoint attivo"}

    env = os.environ.copy()
    env.update(instance_env(gpu_index, backend))
    env["OLLAMA_HOST"] = f"{DEFAULT_HOST}:{port}"
    # Ogni istanza deve poter servire piu' richieste insieme, altrimenti si
    # aggiunge una GPU ma si resta a una richiesta per volta.
    env["OLLAMA_NUM_PARALLEL"] = os.environ.get("OLLAMA_NUM_PARALLEL_POOL", "4")

    try:
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            [binary, "serve"], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creation,
        )
    except Exception as err:
        return {"success": False, "error": f"Avvio non riuscito: {err}"}

    deadline = time.time() + wait
    while time.time() < deadline:
        if check_endpoint(url)["reachable"]:
            with _lock:
                _managed[port] = process
            _remember_instance(port, process.pid, gpu_index)
            _register(url, gpu_index)
            log.info("Istanza Ollama avviata su GPU %s, porta %s (pid %s).",
                     gpu_index, port, process.pid)
            return {"success": True, "url": url, "port": port, "gpu_index": gpu_index,
                    "pid": process.pid}
        if process.poll() is not None:
            return {"success": False, "error": "Il processo Ollama e' terminato subito dopo l'avvio"}
        time.sleep(1)

    process.terminate()
    return {"success": False, "error": f"Nessuna risposta da {url} entro {wait}s"}


def stop_instance(port: int) -> dict:
    """Ferma un'istanza avviata da Sigma e la toglie dal pool.

    Funziona anche quando Sigma e' stato riavviato da quando l'istanza e' partita:
    il PID viene dal registro su disco, non dalla memoria di questo processo.
    """
    with _lock:
        process = _managed.pop(port, None)
    record = _forget_instance(port)

    if process is not None:
        try:
            process.terminate()
            process.wait(timeout=10)
        except Exception as err:
            log.warning("Arresto dell'istanza sulla porta %s: %s", port, err)
    elif record and record.get("pid"):
        if not _kill_pid(int(record["pid"])):
            return {"success": False, "error": f"Processo {record['pid']} non terminabile"}
    elif not record:
        return {"success": False, "error": f"Nessuna istanza registrata sulla porta {port}"}

    _unregister(f"http://{DEFAULT_HOST}:{port}")
    return {"success": True, "port": port}


def stop_all_instances() -> dict:
    """Ferma ogni istanza avviata da Sigma, comprese quelle di sessioni passate."""
    ports = {i["port"] for i in _load_instances()} | set(_managed)
    stopped = [port for port in ports if stop_instance(port).get("success")]
    return {"success": True, "stopped": sorted(stopped)}


def _register(url: str, gpu_index: int | None) -> None:
    """Aggiunge un endpoint alla configurazione, senza duplicarlo."""
    endpoints = configured_endpoints() or [
        {"url": _normalize(f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"), "gpu_index": 0, "label": "predefinito"}
    ]
    url = _normalize(url)
    if any(e["url"] == url for e in endpoints):
        return
    endpoints.append({"url": url, "gpu_index": gpu_index, "label": f"GPU {gpu_index}"})
    save_endpoints(endpoints)


def _unregister(url: str) -> None:
    url = _normalize(url)
    remaining = [e for e in configured_endpoints() if e["url"] != url]
    save_endpoints(remaining)


def add_endpoint(url: str, gpu_index=None, label: str = "") -> dict:
    """Registra un endpoint esterno (altra macchina, altro servizio)."""
    url = _normalize(url)
    if not url:
        return {"success": False, "error": "URL non valido"}
    health = check_endpoint(url)
    if not health["reachable"]:
        return {"success": False, "error": f"{url} non risponde: {health['error']}"}
    endpoints = configured_endpoints()
    if any(e["url"] == url for e in endpoints):
        return {"success": False, "error": "Endpoint già presente nel pool"}
    endpoints.append({"url": url, "gpu_index": gpu_index, "label": label})
    save_endpoints(endpoints)
    return {"success": True, "url": url, "models": health["models"]}


def remove_endpoint(url: str) -> dict:
    url = _normalize(url)
    before = configured_endpoints()
    after = [e for e in before if e["url"] != url]
    if len(after) == len(before):
        return {"success": False, "error": "Endpoint non presente"}
    save_endpoints(after)
    return {"success": True, "url": url}


# ==============================================================================
# DISTRIBUZIONE DEL CARICO
# ==============================================================================

class EndpointPool:
    """Assegna a turno le richieste agli endpoint sani.

    Un giro semplice basta: i quesiti di un benchmark hanno costo simile, quindi
    alternare in tondo tiene le GPU occupate senza bisogno di misurare la coda
    di ognuna.
    """

    def __init__(self, urls: list[str] | None = None):
        self.urls = list(urls) if urls else healthy_urls()
        self._index = 0
        self._guard = threading.Lock()

    def __len__(self) -> int:
        return len(self.urls)

    def next(self) -> str:
        with self._guard:
            url = self.urls[self._index % len(self.urls)]
            self._index += 1
            return url

    def describe(self) -> str:
        return ", ".join(self.urls)
