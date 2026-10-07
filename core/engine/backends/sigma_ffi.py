# ==============================================================================
# core/engine/backends/sigma_ffi.py — Direct C-ABI In-Process FFI Binding
#
# Interfaccia nativa C-ABI verso sigma-ffi (.dll / .so).
# Bypassa la serializzazione JSON IPC per inferenza e telemetria diretta in-process.
# ==============================================================================
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)


class SigmaFfiTelemetry(ctypes.Structure):
    """Layout C allineato a SigmaFfiTelemetry in crates/sigma-ffi/src/lib.rs."""
    _fields_ = [
        ("prefill_us", ctypes.c_uint64),
        ("queue_us", ctypes.c_uint64),
        ("decode_us", ctypes.c_uint64),
        ("ipc_us", ctypes.c_uint64),
        ("total_processed", ctypes.c_uint64),
        ("pending_tasks", ctypes.c_uint32),
        ("pages_allocated", ctypes.c_uint32),
        ("pages_total", ctypes.c_uint32),
        ("radix_hit_rate_pct", ctypes.c_float),
        ("fragmentation_ratio", ctypes.c_float),
    ]


_DLL_CANDIDATE_NAMES = (
    "sigma_ffi.dll" if sys.platform.startswith("win") else "libsigma_ffi.so"
)

_LIB: Optional[ctypes.CDLL] = None
_CTX: Optional[ctypes.c_void_p] = None
_IS_INITIALIZED = False


def _find_library_path() -> Optional[Path]:
    """Cerca la libreria compilata in target o cartelle di runtime."""
    base_proj = Path(__file__).resolve().parents[3] / "projects" / "sigma_engine_rust"
    candidates = [
        base_proj / "target" / "release" / _DLL_CANDIDATE_NAMES,
        base_proj / "target" / "release" / "deps" / _DLL_CANDIDATE_NAMES,
        base_proj / "target" / "debug" / _DLL_CANDIDATE_NAMES,
        base_proj / "target" / "debug" / "deps" / _DLL_CANDIDATE_NAMES,
        Path(__file__).resolve().parent / _DLL_CANDIDATE_NAMES,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def init_ffi() -> bool:
    """Carica la libreria condivisa C-ABI e crea il contesto FFI."""
    global _LIB, _CTX, _IS_INITIALIZED
    if _IS_INITIALIZED:
        return _LIB is not None

    _IS_INITIALIZED = True
    lib_path = _find_library_path()
    if not lib_path:
        log.debug("[SigmaFFI] Libreria condivisa nativa %s non presente su disco", _DLL_CANDIDATE_NAMES)
        return False

    try:
        _LIB = ctypes.CDLL(str(lib_path))
        _LIB.sigma_ffi_version.restype = ctypes.c_char_p
        _LIB.sigma_ffi_create_context.restype = ctypes.c_void_p
        _LIB.sigma_ffi_destroy_context.argtypes = [ctypes.c_void_p]
        _LIB.sigma_ffi_submit_task.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
        ]
        _LIB.sigma_ffi_submit_task.restype = ctypes.c_int32
        _LIB.sigma_ffi_poll_telemetry.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SigmaFfiTelemetry),
        ]
        _LIB.sigma_ffi_poll_telemetry.restype = ctypes.c_int32
        _LIB.sigma_ffi_compact_kv.argtypes = [ctypes.c_void_p]
        _LIB.sigma_ffi_compact_kv.restype = ctypes.c_int32

        _CTX = _LIB.sigma_ffi_create_context()
        ver = _LIB.sigma_ffi_version().decode("utf-8", errors="replace")
        log.info("[SigmaFFI] Inizializzato binding nativo C-ABI in-process (%s da %s)", ver, lib_path)
        return True
    except Exception as exc:
        log.warning("[SigmaFFI] Impossibile caricare FFI nativo: %s", exc)
        _LIB = None
        _CTX = None
        return False


def is_ffi_available() -> bool:
    """Verifica se il binding C-ABI in-process è attivo."""
    if not _IS_INITIALIZED:
        init_ffi()
    return _LIB is not None and _CTX is not None


def get_ffi_telemetry() -> Optional[Dict[str, Any]]:
    """Campiona la telemetria real-time ad alta risoluzione via FFI."""
    if not is_ffi_available():
        return None

    telem = SigmaFfiTelemetry()
    try:
        ret = _LIB.sigma_ffi_poll_telemetry(_CTX, ctypes.byref(telem))
        if ret == 0:
            return {
                "latency_breakdown": {
                    "prefill_us": int(telem.prefill_us),
                    "queue_us": int(telem.queue_us),
                    "decode_us": int(telem.decode_us),
                    "ipc_us": int(telem.ipc_us),
                },
                "total_processed": int(telem.total_processed),
                "pending_tasks": int(telem.pending_tasks),
                "pages_allocated": int(telem.pages_allocated),
                "pages_total": int(telem.pages_total),
                "radix_hit_rate_pct": float(telem.radix_hit_rate_pct),
                "fragmentation_ratio": float(telem.fragmentation_ratio),
                "in_process_ffi": True,
            }
    except Exception as exc:
        log.debug("[SigmaFFI] Errore campionamento telemetria: %s", exc)
    return None


def submit_tokens_ffi(tokens: List[int], task_id: int = 1, priority: int = 1) -> bool:
    """Invia un flusso di token bypassando JSON IPC."""
    if not is_ffi_available() or not tokens:
        return False
    try:
        arr_type = ctypes.c_uint32 * len(tokens)
        c_arr = arr_type(*tokens)
        ret = _LIB.sigma_ffi_submit_task(_CTX, ctypes.c_uint64(task_id), ctypes.c_uint8(priority), c_arr, len(tokens))
        return ret == 0
    except Exception as exc:
        log.debug("[SigmaFFI] Errore submit_tokens_ffi: %s", exc)
        return False
