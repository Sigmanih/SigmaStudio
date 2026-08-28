# ==============================================================================
# core/system_cleanup.py — Comprehensive System Task Teardown & Memory Purge
# Sigma Studio — Graceful Shutdown & Memory Cleanup Manager
# ==============================================================================
from __future__ import annotations
import os
import gc
import atexit
from typing import Dict, Any
from core.logger import get_logger

log = get_logger("system_cleanup")

_SHUTDOWN_PERFORMED = False


def _safe_log(level: str, msg: str, *args):
    """Logs safely without raising ValueError if file streams are closed during atexit."""
    try:
        import sys
        import logging
        if sys is None:
            return
        old_raise = logging.raiseExceptions
        logging.raiseExceptions = False
        try:
            getattr(log, level, log.info)(msg, *args)
        finally:
            logging.raiseExceptions = old_raise
    except Exception:
        pass


def shutdown_all_tasks():
    """
    Gracefully stops all running background tasks, workers, child processes,
    and unloads loaded models when Sigma Studio is shutting down or resetting.
    """
    global _SHUTDOWN_PERFORMED
    if _SHUTDOWN_PERFORMED:
        return
    _SHUTDOWN_PERFORMED = True

    _safe_log("info", "[SystemCleanup] Disconnessione e arresto ordinato di tutti i task in esecuzione...")

    # 1. Cancel active Model Downloads
    try:
        from core.modules.sigma_model_hub.backend.downloader_engine import downloader_manager
        with downloader_manager.lock:
            for task in list(downloader_manager.tasks.values()):
                if getattr(task, "status", None) in ("downloading", "queued"):
                    task.cancel()
                    _safe_log("info", "[SystemCleanup] Annullato download task %s (%s)", task.task_id, getattr(task, "filename", ""))
    except Exception as exc:
        _safe_log("debug", "[SystemCleanup] Avviso arresto downloads: %s", exc)

    # 2. Cancel active Model Uploads
    try:
        from core.modules.sigma_model_hub.backend.uploader_engine import uploader_manager
        if uploader_manager:
            for task in list(uploader_manager.tasks.values()):
                if getattr(task, "status", None) in ("uploading", "queued"):
                    task.cancel()
                    _safe_log("info", "[SystemCleanup] Annullato upload task %s (%s)", task.task_id, getattr(task, "repo_id", ""))
    except Exception as exc:
        _safe_log("debug", "[SystemCleanup] Avviso arresto uploads: %s", exc)

    # 3. Stop running GGUF Conversion jobs
    try:
        from core.engine.gguf_converter import gguf_converter
        for job in getattr(gguf_converter, "jobs", {}).values():
            if getattr(job, "status", None) in ("converting", "quantizing", "queued"):
                job.status = "cancelled"
                _safe_log("info", "[SystemCleanup] Annullata conversione GGUF %s", getattr(job, "job_id", ""))
    except Exception as exc:
        _safe_log("debug", "[SystemCleanup] Avviso arresto conversioni: %s", exc)

    # 4. Stop running Pipelines
    try:
        from core.pipeline_engine import active_pipeline_state
        if active_pipeline_state.get("is_running"):
            active_pipeline_state["is_running"] = False
            active_pipeline_state["status"] = "stopped"
            _safe_log("info", "[SystemCleanup] Arrestata pipeline attiva")
    except Exception as exc:
        _safe_log("debug", "[SystemCleanup] Avviso arresto pipeline: %s", exc)

    # 5. Unload active model from SigmaEngine (free VRAM & RAM)
    try:
        from core.engine.unified_runtime import sigma_engine
        if sigma_engine.loaded_model_name:
            _safe_log("info", "[SystemCleanup] Scaricamento modello SigmaEngine '%s'...", sigma_engine.loaded_model_name)
            sigma_engine.unload()
    except Exception as exc:
        _safe_log("debug", "[SystemCleanup] Avviso scaricamento modello: %s", exc)

    # 6. Clear agent temporary tasks cache
    try:
        from core.store import agent_tasks_store
        agent_tasks_store.save({})
    except Exception as exc:
        _safe_log("debug", "[SystemCleanup] Avviso reset agent_tasks_store: %s", exc)

    # 7. Force garbage collection and CUDA cache cleanup
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    _safe_log("info", "[SystemCleanup] Tutti i task sono stati staccati e le risorse liberate.")


def _format_bytes(bytes_count: int) -> str:
    """Formats bytes into human readable string (B, KB, MB, GB)."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


def _get_dir_size_and_count(dir_path: str | os.PathLike) -> tuple[int, int]:
    """Returns (total_bytes, file_count) for a directory tree safely."""
    total_size = 0
    file_count = 0
    p = os.path.abspath(dir_path)
    if not os.path.exists(p):
        return 0, 0
    if os.path.isfile(p):
        try:
            return os.path.getsize(p), 1
        except OSError:
            return 0, 0
    for root, _, files in os.walk(p):
        for f in files:
            fp = os.path.join(root, f)
            try:
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
                    file_count += 1
            except OSError:
                continue
    return total_size, file_count


def get_cleanup_stats() -> Dict[str, Any]:
    """
    Computes real-time sizes, counts, and reclaimable resources for all system areas:
    - Active Background Tasks & Memory (RAM/VRAM)
    - Tasks & Roadmap files
    - Chat & Execution History
    - File Backup Snapshots (.sigma_backups)
    - Temp & Python Caches
    """
    from core import paths

    # 1. Memory & Resident Models
    loaded_model = None
    loaded_engine = None
    try:
        from core.engine.unified_runtime import sigma_engine
        loaded_model = sigma_engine.loaded_model_name
        loaded_engine = getattr(sigma_engine, "active_provider", None)
    except Exception:
        pass

    vram_bytes = 0
    try:
        import torch
        if torch.cuda.is_available():
            vram_bytes = torch.cuda.memory_allocated()
    except Exception:
        pass

    ram_bytes = 0
    try:
        import psutil
        process = psutil.Process(os.getpid())
        ram_bytes = process.memory_info().rss
    except Exception:
        pass

    # 2. Background Tasks Count
    active_downloads = 0
    try:
        from core.modules.sigma_model_hub.backend.downloader_engine import downloader_manager
        with downloader_manager.lock:
            active_downloads = sum(1 for t in downloader_manager.tasks.values() if getattr(t, "status", None) in ("downloading", "queued"))
    except Exception:
        pass

    active_conversions = 0
    try:
        from core.engine.gguf_converter import gguf_converter
        active_conversions = sum(1 for j in getattr(gguf_converter, "jobs", {}).values() if getattr(j, "status", None) in ("converting", "quantizing", "queued"))
    except Exception:
        pass

    # 3. Tasks files size
    data_dir = str(paths.data_dir()) if hasattr(paths, "data_dir") else "data"
    dev_tasks_file = os.path.join(data_dir, "developer_tasks.json")
    tasks_file = os.path.join(data_dir, "tasks.json")
    agent_tasks_file = os.path.join(data_dir, "agent_tasks_cache.json")
    training_jobs_file = os.path.join(data_dir, "training_jobs.json")

    tasks_bytes = 0
    tasks_count = 0
    for tf in (dev_tasks_file, tasks_file, agent_tasks_file, training_jobs_file):
        if os.path.exists(tf):
            try:
                tasks_bytes += os.path.getsize(tf)
                tasks_count += 1
            except OSError:
                pass

    # 4. History and context shares
    history_bytes = 0
    history_count = 0
    conversations_dir = os.path.join(data_dir, "conversations")
    if os.path.exists(conversations_dir):
        sz, cnt = _get_dir_size_and_count(conversations_dir)
        history_bytes += sz
        history_count += cnt

    # 5. Backup Snapshots (.sigma_backups)
    backups_dir = os.path.join(os.getcwd(), ".sigma_backups")
    backups_bytes, backups_count = _get_dir_size_and_count(backups_dir)

    # 6. Cache & Temp Files
    cache_bytes = 0
    cache_count = 0
    for root_dir in ("core", "tests"):
        for root, dirs, files in os.walk(root_dir):
            if "__pycache__" in dirs:
                pyc_dir = os.path.join(root, "__pycache__")
                sz, cnt = _get_dir_size_and_count(pyc_dir)
                cache_bytes += sz
                cache_count += cnt
            if ".pytest_cache" in dirs:
                pyt_dir = os.path.join(root, ".pytest_cache")
                sz, cnt = _get_dir_size_and_count(pyt_dir)
                cache_bytes += sz
                cache_count += cnt

    total_disk_bytes = tasks_bytes + history_bytes + backups_bytes + cache_bytes

    return {
        "success": True,
        "memory": {
            "loaded_model": loaded_model,
            "provider": loaded_engine,
            "vram_bytes": vram_bytes,
            "vram_formatted": _format_bytes(vram_bytes) if vram_bytes > 0 else "0 B",
            "ram_bytes": ram_bytes,
            "ram_formatted": _format_bytes(ram_bytes) if ram_bytes > 0 else "~350 MB",
            "is_model_loaded": bool(loaded_model)
        },
        "background_tasks": {
            "active_downloads": active_downloads,
            "active_conversions": active_conversions,
            "total_active": active_downloads + active_conversions
        },
        "tasks": {
            "bytes": tasks_bytes,
            "formatted": _format_bytes(tasks_bytes),
            "count": tasks_count,
            "description": f"{tasks_count} registri task salvati (Developer Studio, Roadmap, Training)"
        },
        "history": {
            "bytes": history_bytes,
            "formatted": _format_bytes(history_bytes),
            "count": history_count,
            "description": f"{history_count} file di cronologia chat e sessioni salvate"
        },
        "backups": {
            "bytes": backups_bytes,
            "formatted": _format_bytes(backups_bytes),
            "count": backups_count,
            "description": f"{backups_count} snapshot di backup file (.sigma_backups)"
        },
        "cache": {
            "bytes": cache_bytes,
            "formatted": _format_bytes(cache_bytes),
            "count": cache_count,
            "description": f"{cache_count} file di cache Python e temporanei"
        },
        "total_disk_bytes": total_disk_bytes,
        "total_disk_formatted": _format_bytes(total_disk_bytes)
    }


def execute_selective_cleanup(options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes selective cleanup based on user choices without stopping Sigma Studio:
    - free_memory (bool): Unloads resident LLM models and triggers garbage collection.
    - stop_background_tasks (bool): Cancels running downloads, conversions, and background jobs.
    - clear_tasks (bool): Cleans tasks.json, developer_tasks.json and agent cache.
    - clear_history (bool): Cleans conversation logs and context shares.
    - clear_backups (bool): Removes snapshots in .sigma_backups.
    - clear_cache (bool): Clears Python bytecode and test cache.
    """
    from core import paths
    cleaned = []
    freed_bytes_estimate = 0

    # 1. Free Memory (RAM/VRAM)
    if options.get("free_memory", True):
        try:
            from core.engine.unified_runtime import sigma_engine
            if sigma_engine.loaded_model_name:
                model_name = sigma_engine.loaded_model_name
                sigma_engine.unload()
                cleaned.append(f"Modello '{model_name}' scaricato dalla VRAM")
        except Exception as e:
            log.warning("Memory free error: %s", e)

        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                cleaned.append("Cache CUDA VRAM liberata")
        except Exception:
            pass
        cleaned.append("Garbage Collection eseguita (RAM liberata)")

    # 2. Stop Background Tasks
    if options.get("stop_background_tasks", False):
        try:
            from core.modules.sigma_model_hub.backend.downloader_engine import downloader_manager
            with downloader_manager.lock:
                for task in list(downloader_manager.tasks.values()):
                    if getattr(task, "status", None) in ("downloading", "queued"):
                        task.cancel()
            cleaned.append("Download in corso arrestati")
        except Exception:
            pass

        try:
            from core.engine.gguf_converter import gguf_converter
            for job in getattr(gguf_converter, "jobs", {}).values():
                if getattr(job, "status", None) in ("converting", "quantizing", "queued"):
                    job.status = "cancelled"
            cleaned.append("Conversioni GGUF arrestate")
        except Exception:
            pass

    # 3. Clear Tasks
    if options.get("clear_tasks", False):
        data_dir = str(paths.data_dir()) if hasattr(paths, "data_dir") else "data"
        for fname in ("developer_tasks.json", "tasks.json", "agent_tasks_cache.json"):
            fp = os.path.join(data_dir, fname)
            if os.path.exists(fp):
                try:
                    freed_bytes_estimate += os.path.getsize(fp)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write("[]" if "tasks" in fname else "{}")
                    cleaned.append(f"Registro {fname} azzerato")
                except Exception as e:
                    log.warning("Clear task file %s error: %s", fname, e)

    # 4. Clear History
    if options.get("clear_history", False):
        try:
            from core.context_broker import context_broker
            context_broker.shares.clear()
            cleaned.append("Context Broker shares azzerate")
        except Exception:
            pass

        data_dir = str(paths.data_dir()) if hasattr(paths, "data_dir") else "data"
        conversations_dir = os.path.join(data_dir, "conversations")
        if os.path.exists(conversations_dir):
            import shutil
            sz, _ = _get_dir_size_and_count(conversations_dir)
            freed_bytes_estimate += sz
            shutil.rmtree(conversations_dir, ignore_errors=True)
            os.makedirs(conversations_dir, exist_ok=True)
            cleaned.append("Cronologia sessioni chat rimossa")

    # 5. Clear Backups
    if options.get("clear_backups", False):
        backups_dir = os.path.join(os.getcwd(), ".sigma_backups")
        if os.path.exists(backups_dir):
            import shutil
            sz, _ = _get_dir_size_and_count(backups_dir)
            freed_bytes_estimate += sz
            shutil.rmtree(backups_dir, ignore_errors=True)
            os.makedirs(backups_dir, exist_ok=True)
            cleaned.append(f"Snapshot backup rimossi ({_format_bytes(sz)})")

    # 6. Clear Cache
    if options.get("clear_cache", False):
        import shutil
        for root_dir in ("core", "tests"):
            for root, dirs, _ in os.walk(root_dir):
                if "__pycache__" in dirs:
                    pyc = os.path.join(root, "__pycache__")
                    sz, _ = _get_dir_size_and_count(pyc)
                    freed_bytes_estimate += sz
                    shutil.rmtree(pyc, ignore_errors=True)
                if ".pytest_cache" in dirs:
                    pyt = os.path.join(root, ".pytest_cache")
                    sz, _ = _get_dir_size_and_count(pyt)
                    freed_bytes_estimate += sz
                    shutil.rmtree(pyt, ignore_errors=True)
        cleaned.append("Cache temporanee e bytecode rimosse")

    gc.collect()

    return {
        "success": True,
        "message": "Pulizia selettiva completata con successo. Sigma Studio è attivo e le risorse sono state liberate.",
        "cleaned": cleaned,
        "freed_disk_bytes": freed_bytes_estimate,
        "freed_disk_formatted": _format_bytes(freed_bytes_estimate)
    }


def clear_system_memory(clear_tasks: bool = True, clear_history: bool = True) -> Dict[str, Any]:
    """Legacy wrapper for clearing memory, tasks and background tasks."""
    return execute_selective_cleanup({
        "free_memory": True,
        "stop_background_tasks": True,
        "clear_tasks": clear_tasks,
        "clear_history": clear_history,
        "clear_backups": False,
        "clear_cache": True
    })


def handle_system_clear_memory(self):
    """POST / GET /api/system/clear-memory — Legacy route adapter."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        res = execute_selective_cleanup(body)
        self.send_json_response(res)
    except Exception as exc:
        log.error("Error in handle_system_clear_memory: %s", exc)
        self.send_json_response({"success": False, "error": str(exc)}, 500)


# Register atexit handler so normal Python exit also detaches all tasks
atexit.register(shutdown_all_tasks)

