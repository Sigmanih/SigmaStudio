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


def clear_system_memory(clear_tasks: bool = True, clear_history: bool = True) -> Dict[str, Any]:
    """
    Clears all previous stored tasks, context logs, agent cache, stops active
    background tasks, and unloads any model from VRAM/RAM.
    """
    global _SHUTDOWN_PERFORMED
    _SHUTDOWN_PERFORMED = False  # allow clean trigger

    shutdown_all_tasks()
    _SHUTDOWN_PERFORMED = False  # reset for next use

    cleaned_items = []

    # 1. Clear tasks.json
    if clear_tasks:
        try:
            from core.store import tasks_store
            tasks_store.save([])
            cleaned_items.append("tasks_roadmap")
        except Exception as exc:
            log.error("[SystemCleanup] Impossibile pulire tasks_store: %s", exc)

    # 2. Clear agent_tasks_cache.json
    try:
        from core.store import agent_tasks_store
        agent_tasks_store.save({})
        cleaned_items.append("agent_tasks_cache")
    except Exception as exc:
        log.error("[SystemCleanup] Impossibile pulire agent_tasks_store: %s", exc)

    # 3. Clear context shares & chat logs if requested
    if clear_history:
        try:
            from core.context_broker import context_broker
            context_broker.shares.clear()
            cleaned_items.append("context_shares")
        except Exception as exc:
            log.debug("[SystemCleanup] Errore reset context_broker: %s", exc)

    # 4. Clear model downloader completed/failed task list
    try:
        from core.modules.sigma_model_hub.backend.downloader_engine import downloader_manager
        with downloader_manager.lock:
            downloader_manager.tasks.clear()
            cleaned_items.append("download_tasks_history")
    except Exception as exc:
        log.debug("[SystemCleanup] Errore pulizia tasks download: %s", exc)

    # 5. Clear model uploader task list
    try:
        from core.modules.sigma_model_hub.backend.uploader_engine import uploader_manager
        if uploader_manager:
            uploader_manager.tasks.clear()
            cleaned_items.append("upload_tasks_history")
    except Exception as exc:
        log.debug("[SystemCleanup] Errore pulizia tasks upload: %s", exc)

    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    return {
        "success": True,
        "message": "Memoria e task precedenti ripuliti con successo. Processi di background arrestati e RAM/VRAM liberate.",
        "cleaned": cleaned_items,
    }


def handle_system_clear_memory(self):
    """POST / GET /api/system/clear-memory — Pulisce memoria, task, cronologia e processi attivi."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        clear_tasks = bool(body.get("clear_tasks", True))
        clear_history = bool(body.get("clear_history", True))
        res = clear_system_memory(clear_tasks=clear_tasks, clear_history=clear_history)
        self.send_json_response(res)
    except Exception as exc:
        log.error("Error in handle_system_clear_memory: %s", exc)
        self.send_json_response({"success": False, "error": str(exc)}, 500)


# Register atexit handler so normal Python exit also detaches all tasks
atexit.register(shutdown_all_tasks)
