# ==============================================================================
# core/training/capacity.py — Quante istanze parallele regge un modello
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Stima e misura quante richieste in parallelo un modello puo' davvero servire.

Serve a due cose che sono la stessa cosa vista da due lati: accorciare i run di
benchmark, e sapere quanti agenti concorrenti l'hardware regge con quel modello.

Due livelli, perche' uno solo mente:

* `estimate_capacity` — conto a tavolino su VRAM libera e peso del modello.
  Immediato, ma ignora come il servitore e' configurato.
* `probe_parallel_capacity` — misura vera: manda richieste identiche a livelli di
  concorrenza crescenti e guarda dove il throughput smette di salire.

La misura conta perche' la stima puo' essere ottimistica per un motivo che non si
vede dalla VRAM: Ollama serve una richiesta alla volta per modello se
`OLLAMA_NUM_PARALLEL` vale 1. Con quel valore, alzare i worker del benchmark non
accorcia niente — le richieste si accodano. Il probe riconosce questa firma
(throughput piatto al crescere della concorrenza) e la riporta come collo di
bottiglia di configurazione, non di hardware.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import json
import os
import threading
import time
import uuid

import requests

from core.logger import get_logger

log = get_logger(__name__)

PROFILES_FILE = os.path.join("training_lab", "capacity_profiles.json")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

_profiles_lock = threading.RLock()
_probe_jobs: dict[str, dict] = {}       # probe_id -> stato vivo
_probe_threads: dict[str, threading.Thread] = {}

#: Livelli di concorrenza provati, salvo diversa indicazione.
DEFAULT_LEVELS = (1, 2, 4, 8)
#: Token generati da ogni richiesta di prova: abbastanza da misurare, non tanti
#: da rendere lenta la misura.
PROBE_TOKENS = 64
#: Efficienza minima (accelerazione ottenuta / concorrenza) perche' un livello
#: sia adatto a lavoro *interattivo*: sotto, ogni richiesta aspetta le altre.
EFFICIENCY_THRESHOLD = 0.6
#: Guadagno minimo di throughput rispetto al livello precedente perche' valga la
#: pena salire ancora, quando l'obiettivo e' finire prima un lotto.
MIN_THROUGHPUT_GAIN = 0.10

PROBE_PROMPT = ("List three prime numbers greater than one hundred and briefly "
                "explain how you can tell that each one is prime.")


# ==============================================================================
# PROFILI SALVATI
# ==============================================================================

def _load_profiles() -> dict:
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as err:
        log.warning("Profili di capacita' illeggibili: %s", err)
        return {}


def _save_profile(model: str, profile: dict) -> None:
    os.makedirs("training_lab", exist_ok=True)
    with _profiles_lock:
        profiles = _load_profiles()
        profiles[model] = profile
        tmp = PROFILES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(profiles, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, PROFILES_FILE)


def get_profile(model: str) -> dict | None:
    """Ultima misura salvata per un modello, se esiste."""
    return _load_profiles().get(model)


def list_profiles() -> dict:
    return _load_profiles()


# ==============================================================================
# STATO DELL'HARDWARE E DEL SERVITORE
# ==============================================================================

def _nvidia_devices() -> list[dict]:
    """GPU CUDA in ordine di bus PCI, con gli indici che CUDA usera' davvero.

    Interrogare nvidia-smi invece di riusare la lista generale dell'hardware non
    e' un doppione: quella elenca anche le schede non-CUDA (una iGPU DirectML,
    per dire) e le numera per posizione in elenco. Legare un'istanza a
    `CUDA_VISIBLE_DEVICES` con quell'indice significa colpire la scheda
    sbagliata appena la macchina ha una GPU in piu' del previsto.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
    except Exception as err:
        log.debug("nvidia-smi non disponibile: %s", err)
        return []

    devices = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            devices.append({
                "index": int(parts[0]),
                "name": parts[1],
                "backend": "cuda",
                "vram_total_gb": round(int(parts[2]) / 1024, 2),
                "vram_free_gb": round(int(parts[3]) / 1024, 2),
            })
        except ValueError:
            continue
    return devices


def cuda_devices() -> list[dict]:
    """Acceleratori utilizzabili, con indici validi per CUDA_VISIBLE_DEVICES."""
    devices = _nvidia_devices()
    if devices:
        return devices

    # Nessuna NVIDIA (o nvidia-smi assente): si ripiega sull'inventario generale,
    # tenendo solo i backend che Ollama sfrutta per l'inferenza.
    try:
        from core.training_handler import get_hardware_info
        hardware = get_hardware_info().get("hardware", {})
    except Exception as err:
        log.debug("Informazioni hardware non disponibili: %s", err)
        return []

    accelerators = [g for g in hardware.get("gpu", []) if g.get("backend") in ("cuda", "rocm")]
    return [{
        "index": position,
        "name": g.get("name", ""),
        "backend": g.get("backend", ""),
        "vram_total_gb": g.get("vram_total_gb", 0),
        "vram_free_gb": g.get("vram_free_gb", 0),
    } for position, g in enumerate(accelerators)]


def _gpu_snapshot() -> dict:
    """Fotografia della memoria disponibile su acceleratori e RAM."""
    gpus = cuda_devices()
    ram_free = 0.0
    try:
        from core.training_handler import get_hardware_info
        ram_free = round(get_hardware_info().get("hardware", {}).get("ram", {}).get("free_gb", 0), 2)
    except Exception:
        pass

    return {
        "gpus": gpus,
        # Un modello vive su una GPU sola: la capacita' di una singola istanza la
        # detta la scheda piu' capiente, non la somma delle schede.
        "usable_vram_gb": round(max((g["vram_free_gb"] for g in gpus), default=0.0), 2),
        "total_vram_gb": round(sum(g["vram_free_gb"] for g in gpus), 2),
        "ram_free_gb": ram_free,
        "spread_enabled": os.environ.get("OLLAMA_SCHED_SPREAD", "0") not in ("0", "", "false"),
    }


def _ollama_num_parallel() -> int | None:
    """OLLAMA_NUM_PARALLEL come lo vede Sigma, o None se non impostato.

    Attenzione: e' l'ambiente di *questo* processo. Il servitore Ollama gira per
    conto suo e puo' essere partito con un valore diverso, quindi questo dato
    vale come indizio per spiegare una curva piatta, mai come verdetto: quello
    lo da' la misura.
    """
    raw = os.environ.get("OLLAMA_NUM_PARALLEL", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except ValueError:
        return None


def _model_size_gb(model: str) -> float:
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        if res.status_code == 200:
            for entry in res.json().get("models", []):
                if entry.get("name") == model:
                    return round(entry.get("size", 0) / (1024 ** 3), 2)
    except Exception as err:
        log.debug("Peso del modello %s non recuperabile: %s", model, err)
    return 0.0


# ==============================================================================
# STIMA
# ==============================================================================

def _slots_on(free_gb: float, size_gb: float, per_slot_gb: float) -> int:
    """Richieste concorrenti che una singola scheda regge con quel modello."""
    if size_gb <= 0 or free_gb < size_gb:
        return 0
    return max(1, min(32, int((free_gb - size_gb) // per_slot_gb) + 1))


def estimate_capacity(model: str) -> dict:
    """Capacita' parallela del modello, scheda per scheda e sul pool attuale.

    Due numeri diversi, perche' rispondono a domande diverse:

    * `max_parallel_now` — quanto si ottiene con gli endpoint accesi adesso.
    * `max_parallel_potential` — quanto darebbe tutto l'hardware presente.

    Divergono perche' un servitore Ollama carica il modello su **una** GPU: le
    altre schede restano ferme finche' non hanno un endpoint proprio. La
    differenza fra i due numeri e' esattamente cio' che si guadagna aggiungendone
    uno, ed e' il motivo per cui `idle_gpus` viene riportato.
    """
    from core.training.endpoints import active_endpoints

    snapshot = _gpu_snapshot()
    size_gb = _model_size_gb(model)
    devices = snapshot["gpus"]
    # Cache KV per slot: circa un decimo del peso del modello alle finestre di
    # contesto tipiche, con un minimo per i modelli molto piccoli.
    per_slot_gb = max(0.12, round(size_gb * 0.10, 2))

    endpoints = active_endpoints()
    reachable = [e for e in endpoints if e.get("reachable")]
    # Un endpoint senza GPU dichiarata sta sulla prima scheda: e' cio' che fa
    # Ollama quando nessuno gli restringe CUDA_VISIBLE_DEVICES.
    bound = {e.get("gpu_index") if e.get("gpu_index") is not None else 0 for e in reachable}

    per_gpu = []
    for device in devices:
        slots = _slots_on(device["vram_free_gb"], size_gb, per_slot_gb)
        per_gpu.append({
            **device,
            "fits": slots > 0,
            "max_parallel": slots,
            "has_endpoint": device["index"] in bound,
        })

    potential = sum(g["max_parallel"] for g in per_gpu)
    now = sum(g["max_parallel"] for g in per_gpu if g["has_endpoint"])
    idle = [g for g in per_gpu if g["fits"] and not g["has_endpoint"]]

    base = {
        "model": model,
        "model_size_gb": size_gb,
        "per_slot_gb": per_slot_gb,
        "usable_vram_gb": snapshot["usable_vram_gb"],
        "total_vram_gb": snapshot["total_vram_gb"],
        "hardware": snapshot,
        "gpus": per_gpu,
        "endpoints": [{"url": e["url"], "gpu_index": e.get("gpu_index"),
                       "reachable": e.get("reachable", False)} for e in endpoints],
        "endpoint_count": len(reachable),
        "idle_gpus": idle,
    }

    if size_gb <= 0:
        return {**base, "max_parallel": 1, "max_parallel_now": 1, "max_parallel_potential": 1,
                "fits_in_vram": False, "placement": "sconosciuto",
                "note": "Modello non trovato sugli endpoint: impossibile stimare."}

    if potential == 0:
        # Non entra in nessuna scheda: gira su CPU, dove il limite sono i core e
        # la banda di memoria, non la VRAM.
        cpu_slots = max(1, min(4, (os.cpu_count() or 4) // 4))
        largest = snapshot["usable_vram_gb"]
        return {**base, "max_parallel": cpu_slots, "max_parallel_now": cpu_slots,
                "max_parallel_potential": cpu_slots, "fits_in_vram": False,
                "placement": "CPU / RAM",
                "note": (f"Il modello ({size_gb} GB) supera la VRAM libera della scheda piu' "
                         f"capiente ({largest} GB): gira su CPU e il parallelismo rende poco.")}

    note = (f"{per_slot_gb} GB per richiesta concorrente. "
            f"Con gli endpoint attivi: {now} in parallelo.")
    if idle:
        names = ", ".join(f"GPU {g['index']} ({g['name']}, +{g['max_parallel']})" for g in idle)
        note += (f" Inutilizzate: {names}. Un servitore Ollama carica il modello su una sola "
                 "scheda: serve un endpoint dedicato per ognuna delle altre.")

    return {**base,
            "max_parallel": max(1, now),
            "max_parallel_now": max(1, now),
            "max_parallel_potential": max(1, potential),
            "fits_in_vram": True,
            "placement": "GPU",
            "note": note}


# ==============================================================================
# MISURA
# ==============================================================================

def _single_request(model: str, timeout: int, url: str = "") -> dict:
    """Una richiesta di prova; misura token generati e durata."""
    payload = {
        "model": model,
        "prompt": PROBE_PROMPT,
        "stream": False,
        "think": False,
        # Seed fisso e temperatura 0: ogni richiesta fa lo stesso lavoro, quindi
        # le differenze fra livelli vengono dalla concorrenza, non dal testo.
        "options": {"temperature": 0.0, "seed": 42, "num_predict": PROBE_TOKENS},
    }
    started = time.time()
    try:
        res = requests.post(f"{url or OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        elapsed = time.time() - started
        if res.status_code != 200:
            return {"ok": False, "error": f"HTTP {res.status_code}", "seconds": elapsed, "tokens": 0}
        data = res.json()
        return {
            "ok": True,
            "seconds": elapsed,
            "tokens": data.get("eval_count") or 0,
            "load_seconds": round((data.get("load_duration") or 0) / 1e9, 3),
        }
    except Exception as err:
        return {"ok": False, "error": str(err)[:200], "seconds": time.time() - started, "tokens": 0}


def _run_level(model: str, level: int, timeout: int, endpoints: list[str] | None = None) -> dict:
    """Lancia `level` richieste insieme e misura il throughput complessivo.

    Le richieste girano a turno sugli endpoint del pool: con piu' servitori, e'
    quello che mette al lavoro tutte le schede invece della sola prima.
    """
    urls = endpoints or [OLLAMA_URL]
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=level) as pool:
        results = list(pool.map(
            lambda i: _single_request(model, timeout, urls[i % len(urls)]), range(level)))
    wall = max(time.time() - started, 0.001)

    ok = [r for r in results if r["ok"]]
    tokens = sum(r["tokens"] for r in ok)
    latencies = sorted(r["seconds"] for r in ok)
    return {
        "concurrency": level,
        "requests": level,
        "succeeded": len(ok),
        "failed": level - len(ok),
        "wall_seconds": round(wall, 2),
        "total_tokens": tokens,
        "aggregate_tokens_per_sec": round(tokens / wall, 2),
        "avg_latency_ms": int(sum(latencies) / len(latencies) * 1000) if latencies else 0,
        "max_latency_ms": int(latencies[-1] * 1000) if latencies else 0,
        "errors": [r.get("error") for r in results if not r["ok"]][:3],
    }


def adaptive_levels(estimate: dict, cap: int = 32) -> list[int]:
    """Scala di concorrenze da provare, tarata sull'hardware presente.

    Raddoppia fino al tetto che la VRAM consente, e ci si ferma: su una macchina
    con una scheda piccola non ha senso arrivare a 32, su una con quattro schede
    fermarsi a 8 nasconderebbe meta' della capacita'. Una lista fissa uguale per
    tutti sbaglia in entrambe le direzioni.
    """
    ceiling = max(1, min(int(estimate.get("max_parallel_potential", 1) or 1), cap))
    levels, step = [], 1
    while step <= ceiling:
        levels.append(step)
        step *= 2
    if levels and levels[-1] != ceiling:
        levels.append(ceiling)
    return levels or [1]


def probe_parallel_capacity(model: str, levels=None, timeout: int = 180,
                            progress=None) -> dict:
    """Misura fino a che concorrenza il modello continua a rendere.

    Sale di livello finche' il throughput complessivo cresce in modo utile. Il
    consiglio finale e' il livello piu' alto che mantiene un'efficienza
    accettabile: oltre, si aggiunge attesa senza aggiungere lavoro svolto.
    """
    from core.training.endpoints import healthy_urls

    estimate = estimate_capacity(model)
    levels = sorted({int(n) for n in (levels or adaptive_levels(estimate)) if int(n) >= 1})
    num_parallel = _ollama_num_parallel()
    urls = healthy_urls()

    # Un giro a vuoto per endpoint: senza, il primo livello pagherebbe il
    # caricamento dei pesi e sembrerebbe lentissimo, falsando ogni confronto.
    for url in urls:
        warmup = _single_request(model, timeout, url)
        if not warmup["ok"]:
            return {
                "success": False,
                "model": model,
                "error": f"{url} non risponde: {warmup.get('error', 'errore sconosciuto')}",
                "estimate": estimate,
            }

    measurements: list[dict] = []
    baseline_tps = 0.0
    previous_tps = 0.0
    interactive_best = 1   # ottimo per latenza: quanti agenti servire bene
    throughput_best = 1    # ottimo per lotto: quanto in fretta finisce un run

    for index, level in enumerate(levels):
        if progress:
            progress(index, len(levels), level)
        result = _run_level(model, level, timeout, urls)

        if result["succeeded"] == 0:
            result["note"] = "Nessuna richiesta completata a questo livello."
            measurements.append(result)
            break

        tps = result["aggregate_tokens_per_sec"]
        if baseline_tps <= 0:
            baseline_tps = tps

        speedup = (tps / baseline_tps) if baseline_tps > 0 else 1.0
        efficiency = speedup / level if level else 0.0
        gain = ((tps / previous_tps) - 1.0) if previous_tps > 0 else 1.0

        result["speedup"] = round(speedup, 2)
        result["efficiency"] = round(efficiency, 2)
        result["gain"] = round(gain, 3)
        # Due giudizi separati sullo stesso campione, perche' rispondono a
        # domande diverse: reggere N agenti senza farli aspettare, oppure
        # macinare un lotto nel minor tempo.
        result["useful"] = efficiency >= EFFICIENCY_THRESHOLD and result["failed"] == 0
        result["faster"] = gain >= MIN_THROUGHPUT_GAIN and result["failed"] == 0
        measurements.append(result)

        if result["useful"]:
            interactive_best = level
        if result["faster"] or level == 1:
            throughput_best = level

        if result["failed"] > 0 or gain < MIN_THROUGHPUT_GAIN:
            # Salire ancora non fa finire prima: si smette di misurare.
            result["note"] = "Saturazione raggiunta: livelli superiori non provati."
            break
        previous_tps = tps

    verdict = _interpret(measurements, num_parallel, estimate, throughput_best, interactive_best)
    profile = {
        "model": model,
        "measured_at": datetime.datetime.now().isoformat(),
        "recommended_parallel": verdict["recommended_parallel"],
        # Quanti agenti concorrenti la macchina serve senza farli aspettare: e'
        # un numero piu' basso del throughput ottimo, e va letto a parte.
        "recommended_agents": interactive_best,
        "max_useful_parallel": throughput_best,
        "estimate": estimate,
        "measurements": measurements,
        "ollama_num_parallel": num_parallel,
        "bottleneck": verdict["bottleneck"],
        "advice": verdict["advice"],
        "peak_tokens_per_sec": max((m["aggregate_tokens_per_sec"] for m in measurements), default=0),
        # La misura vale per la topologia con cui e' stata fatta: aggiungere un
        # endpoint la rende obsoleta, e la UI deve poterlo dire.
        "endpoints": urls,
        "endpoint_count": len(urls),
        "levels_tested": levels,
    }
    _save_profile(model, profile)
    return {"success": True, **profile}


def _interpret(measurements: list[dict], num_parallel: int | None, estimate: dict,
               throughput_best: int, interactive_best: int = 1) -> dict:
    """Traduce le misure in un collo di bottiglia e un consiglio leggibile."""
    recommended = throughput_best
    if len(measurements) < 2:
        return {
            "recommended_parallel": max(1, recommended),
            "bottleneck": "sconosciuto",
            "advice": "Misura incompleta: prova con piu' livelli di concorrenza.",
        }

    top = measurements[-1]
    scaled = any(m.get("speedup", 1.0) > 1.3 for m in measurements[1:])

    # Firma della serializzazione: la concorrenza sale, il throughput no. Con
    # OLLAMA_NUM_PARALLEL=1 il servitore accoda, e nessun aumento dei worker del
    # benchmark puo' cambiarlo — e' configurazione, non hardware.
    if not scaled and (num_parallel == 1 or num_parallel is None):
        return {
            "recommended_parallel": 1,
            "bottleneck": "OLLAMA_NUM_PARALLEL",
            "advice": ("Il throughput non cresce con la concorrenza: Ollama sta servendo una "
                       "richiesta alla volta. In Sigma OLLAMA_NUM_PARALLEL vale "
                       f"{num_parallel or 'non impostato'}, ma conta il valore con cui e' partito "
                       f"il servizio. La VRAM reggerebbe circa {estimate.get('max_parallel', 1)} "
                       "istanze: imposta la variabile e riavvia Ollama per usarle."),
        }

    if not scaled:
        return {
            "recommended_parallel": 1,
            "bottleneck": "calcolo",
            "advice": ("La GPU e' già satura con una sola richiesta: il parallelismo non "
                       "accorcia il benchmark per questo modello."),
        }

    if top.get("failed", 0) > 0:
        return {
            "recommended_parallel": max(1, recommended),
            "bottleneck": "memoria",
            "advice": (f"Errori a concorrenza {top['concurrency']}: il limite pratico e' "
                       f"{recommended} richieste insieme."),
        }

    peak = max(m["aggregate_tokens_per_sec"] for m in measurements)
    speedup = max((m.get("speedup", 1.0) for m in measurements), default=1.0)
    idle = estimate.get("idle_gpus") or []
    advice = (f"{recommended} richieste in parallelo danno il throughput massimo "
              f"({peak} tok/s, {speedup}x rispetto a una sola): e' il valore che fa finire "
              f"prima un benchmark. Per agenti interattivi, oltre {interactive_best} "
              "la latenza di ognuno inizia a crescere.")
    if idle:
        names = ", ".join(f"GPU {g['index']} ({g['name']})" for g in idle)
        advice += (f" {names} non risulta in uso: avviando un endpoint dedicato "
                   "il tetto sale ancora.")
    return {
        "recommended_parallel": max(1, recommended),
        "bottleneck": "nessuno" if recommended >= max(m["concurrency"] for m in measurements) else "throughput",
        "advice": advice,
    }


# ==============================================================================
# MISURA IN BACKGROUND
# ==============================================================================

def start_capacity_probe(model: str, levels=None) -> dict:
    """Avvia la misura in un thread: dura decine di secondi, non blocca la UI."""
    probe_id = f"cap_{uuid.uuid4().hex[:8]}"
    _probe_jobs[probe_id] = {
        "id": probe_id, "model": model, "status": "running",
        "progress": 0, "current_level": None, "levels": list(levels) if levels else [],
        "started_at": datetime.datetime.now().isoformat(), "result": None,
    }

    def worker():
        def on_progress(index, total, level):
            _probe_jobs[probe_id].update({
                "progress": int((index / max(total, 1)) * 100),
                "current_level": level,
            })
        try:
            result = probe_parallel_capacity(model, levels, progress=on_progress)
            _probe_jobs[probe_id].update({
                "status": "completed" if result.get("success") else "failed",
                "progress": 100, "result": result,
            })
        except Exception as err:
            log.error("Misura di capacita' per %s non riuscita: %s", model, err)
            _probe_jobs[probe_id].update({"status": "failed", "progress": 100,
                                          "result": {"success": False, "error": str(err)}})
        finally:
            _probe_threads.pop(probe_id, None)

    thread = threading.Thread(target=worker, daemon=True)
    _probe_threads[probe_id] = thread
    thread.start()
    return {"success": True, "probe_id": probe_id, "model": model, "status": "running"}


def get_probe_status(probe_id: str) -> dict:
    job = _probe_jobs.get(probe_id)
    if not job:
        return {"success": False, "error": f"Misura {probe_id} non trovata"}
    return {"success": True, **job}


# ==============================================================================
# RISOLUZIONE DELLA CONCORRENZA
# ==============================================================================

def resolve_concurrency(model: str, requested) -> tuple[int, str]:
    """Traduce la concorrenza richiesta in un numero, spiegando da dove viene.

    `auto` usa l'ultima misura del modello se c'e', altrimenti la stima da VRAM:
    e' cio' che rende dinamico il parallelismo invece di lasciarlo a un numero
    scelto a mano che l'hardware potrebbe non reggere.
    """
    # Un valore assente vale "auto": meglio dedurlo dall'hardware che ripiegare
    # su 1 e rallentare il run senza motivo.
    if requested is None or (isinstance(requested, str) and requested.strip().lower() in ("auto", "")):
        profile = get_profile(model)
        if profile and profile.get("recommended_parallel"):
            value = int(profile["recommended_parallel"])
            return max(1, value), f"auto: misurato il {profile.get('measured_at', '')[:10]}"
        estimate = estimate_capacity(model)
        # Il tetto e' prudenza contro un servitore che accoda: se Ollama serve
        # una richiesta alla volta, alzare i worker non serve a niente. Ma su
        # questa macchina non e' cosi', misurato il 2026-08-02 su 24 richieste
        # a qwen2.5:0.5b-instruct: 1w 7.7 req/s, 4w 26.5, 8w 37.6, 16w 41.8.
        # Fermarsi a 4 costava il 42% del throughput. Per i modelli grandi il
        # limite lo mette comunque la VRAM (`max_parallel_now`), e li' 4 e 2
        # rendono uguale — Qwythos 9B: 2w 2.66 req/s, 4w 2.65.
        ceiling = 8 * max(1, int(estimate.get("endpoint_count", 1) or 1))
        value = min(int(estimate.get("max_parallel_now", 1) or 1), ceiling)
        return max(1, value), "auto: stima da VRAM (nessuna misura disponibile)"

    try:
        value = int(requested)
    except (TypeError, ValueError):
        return 1, "valore non valido, ripiego su 1"
    return max(1, min(value, 32)), "impostato manualmente"
