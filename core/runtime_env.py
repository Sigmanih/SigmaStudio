# ==============================================================================
# core/runtime_env.py — Process-wide hardware environment
#
# The numerical libraries under Sigma Studio (torch, numpy/BLAS, llama.cpp's own
# OpenMP build) read their thread counts and device visibility from environment
# variables, and they read them once, when they are first imported. So this has
# to run before anything else touches them, and it has to run on every entry
# point -- `python sigma_server.py`, `uvicorn core.fastapi_app:app`, a worker
# started by the launcher -- not just the one that happens to be documented.
#
# It is deliberately conservative about what it sets. An environment variable
# invented here overrides a deployment's own choice, and a wrong one is
# invisible: nobody debugging a slow board thinks to check whether the server
# pinned CUDA_VISIBLE_DEVICES to two cards that do not exist.
# ==============================================================================
import json
import os
import sys

from core.logger import get_logger

log = get_logger(__name__)

_applied = False


def _config() -> dict:
    try:
        from core.model_paths import project_root
        path = os.path.join(project_root(), "config.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        log.debug("[RuntimeEnv] config.json non leggibile: %s", exc)
        return {}


def _cuda_device_count() -> int:
    """
    How many CUDA devices this machine really has, without importing torch.

    Importing torch here would cost several seconds of startup on every entry
    point and, worse, would read CUDA_VISIBLE_DEVICES before we have decided
    what it should be.
    """
    try:
        import ctypes
        for lib in ("libcuda.so.1", "nvcuda.dll", "libcuda.dylib"):
            try:
                cuda = ctypes.CDLL(lib)
            except OSError:
                continue
            if cuda.cuInit(0) != 0:
                return 0
            count = ctypes.c_int(0)
            if cuda.cuDeviceGetCount(ctypes.byref(count)) != 0:
                return 0
            return max(count.value, 0)
    except Exception as exc:
        log.debug("[RuntimeEnv] Rilevamento CUDA non riuscito: %s", exc)
    return 0


def _thread_budget() -> int:
    """
    Threads the math libraries may use.

    Physical cores, not logical: BLAS and OpenMP kernels are already saturating
    each core's vector units, so a second thread on the same core contends for
    them instead of adding throughput. One core is left to the event loop on
    small machines, where there is no spare capacity to absorb the contention
    and the web UI is the only way to see what the engine is doing.
    """
    try:
        import psutil
        physical = psutil.cpu_count(logical=False) or 0
    except Exception:
        physical = 0
    physical = physical or os.cpu_count() or 4
    return max(physical - 1, 1) if physical <= 4 else physical


def apply_hardware_env(force: bool = False) -> dict:
    """
    Applies device visibility, threading and credentials to this process.

    Returns what was applied, for logging. Safe to call more than once: the
    second call is a no-op unless forced, because the libraries have already
    read these values by then and changing them would only make the log lie.
    """
    global _applied
    if _applied and not force:
        return {}

    applied: dict = {}
    cfg = _config()
    hw = cfg.get("hardware", {}) if isinstance(cfg, dict) else {}

    # --- accelerator visibility ---------------------------------------------
    # Only ever set when the deployment asked for a specific selection. The old
    # unconditional default of "0,1" claimed two NVIDIA devices on every
    # machine, which on a board with none is merely noise but on a workstation
    # with three cards silently hides the third.
    devices = hw.get("cuda_visible_devices")
    cuda_count = _cuda_device_count()
    applied["cuda_devices_detected"] = cuda_count
    if devices in (None, "", "auto"):
        # Nothing is set when devices are present: the default already exposes
        # all of them, and naming them freezes the list at startup.
        pass
    elif cuda_count > 0:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(devices)
        applied["CUDA_VISIBLE_DEVICES"] = str(devices)
    else:
        # A device list configured on a machine with no CUDA driver is stale
        # config travelling with the repository, not an instruction. Applying
        # it would leave a variable that misdescribes the machine to every
        # library that reads it later.
        log.debug(
            "[RuntimeEnv] cuda_visible_devices='%s' ignorato: nessun device "
            "CUDA rilevato su questa macchina.", devices,
        )

    # --- external Ollama, when one is in use ---------------------------------
    for key, value in (
        ("OLLAMA_NUM_PARALLEL", hw.get("ollama_num_parallel")),
        ("OLLAMA_MAX_LOADED_MODELS", hw.get("ollama_max_loaded_models")),
        ("OLLAMA_KEEP_ALIVE", hw.get("ollama_keep_alive")),
    ):
        if value not in (None, ""):
            os.environ[key] = str(value)
            applied[key] = str(value)

    # --- CUDA allocator ------------------------------------------------------
    # expandable_segments cuts fragmentation across load/unload cycles, but it
    # is a CUDA feature: setting it on a machine with no CUDA is a variable
    # that will confuse the next person to read the environment.
    if sys.platform != "win32" and (
        devices not in (None, "", "auto") or _cuda_device_count() > 0
    ):
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        applied["PYTORCH_CUDA_ALLOC_CONF"] = os.environ["PYTORCH_CUDA_ALLOC_CONF"]

    # --- CPU threading -------------------------------------------------------
    threads = str(hw.get("cpu_threads") or _thread_budget())
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(key, threads)
    applied["threads"] = threads

    # --- Hugging Face credentials -------------------------------------------
    hf_token = cfg.get("hf_token", "") if isinstance(cfg, dict) else ""
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGINGFACE_TOKEN"] = hf_token
        applied["hf_token"] = f"{hf_token[:8]}..." if len(hf_token) > 8 else "set"

    _applied = True
    return applied
