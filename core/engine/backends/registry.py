# ==============================================================================
# core/engine/backends/registry.py — Hardware-aware backend selection
#
# Picks the runtime for a given checkpoint on the current machine. Selection is
# a filter then a ranking: a backend must be installed and able to read the
# format before its preference score is even considered, so the engine never
# nominates a runtime that cannot start.
# ==============================================================================
from typing import Dict, Any, List, Optional, Type

from core.logger import get_logger
from core.engine.model_inspector import ModelFacts
from core.engine.backends.base import InferenceBackend
from core.engine.backends.llamacpp_backend import LlamaCppBackend

log = get_logger(__name__)

# Registration order is irrelevant to selection, which is score-driven.
_BACKENDS: List[Type[InferenceBackend]] = [LlamaCppBackend]


def register_backend(backend: Type[InferenceBackend]) -> None:
    """Adds a backend to the selection pool."""
    if backend not in _BACKENDS:
        _BACKENDS.append(backend)


def all_backends() -> List[Type[InferenceBackend]]:
    return list(_BACKENDS)


def select_backend(
    facts: ModelFacts, hardware: Dict[str, Any]
) -> Optional[Type[InferenceBackend]]:
    """Returns the highest-scoring backend able to run this model here."""
    candidates = []
    for backend in _BACKENDS:
        available, _ = backend.availability()
        if not available:
            continue
        if not backend.supports(facts, hardware):
            continue
        candidates.append((backend.score(facts, hardware), backend))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    chosen = candidates[0][1]
    log.info(
        "[BackendRegistry] '%s' (%s) -> %s",
        facts.name, facts.weight_format, chosen.name,
    )
    return chosen


def capability_report(hardware: Dict[str, Any]) -> Dict[str, Any]:
    """
    What this machine can run, and why not otherwise.

    Surfaces the missing dependency rather than a bare unavailable flag, so an
    unsupported format points at its fix instead of a dead end.
    """
    report: Dict[str, Any] = {}
    for backend in _BACKENDS:
        available, reason = backend.availability()
        report[backend.name] = {
            "available": available,
            "reason": reason,
            "formats": list(backend.supported_formats),
        }
    return report


def explain_unsupported(facts: ModelFacts) -> str:
    """Message for a format no installed backend can load."""
    handlers = [
        backend for backend in _BACKENDS
        if facts.weight_format in backend.supported_formats
    ]
    if not handlers:
        return (
            f"Nessun backend conosce il formato '{facts.weight_format}' "
            f"per '{facts.name}'."
        )
    reasons = "; ".join(f"{b.name}: {b.availability()[1]}" for b in handlers)
    return (
        f"'{facts.name}' e' in formato {facts.weight_format}, gestito da "
        f"{', '.join(b.name for b in handlers)}, ma non e' utilizzabile qui. {reasons}"
    )
