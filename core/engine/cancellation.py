# ==============================================================================
# core/engine/cancellation.py — Stopping a generation that nobody is reading
#
# The client aborts its fetch when the user presses stop, or closes the tab, or
# loses the network. None of that reached the engine: the SSE writer swallowed
# the broken pipe and the generation thread ran on to max_new_tokens. On a
# single-resident-model engine that is worse than wasted electricity -- the
# abandoned answer holds the model while the next request waits for it.
#
# A token is a threading.Event with a reason attached. Nothing here imports
# torch or any runtime, so the same object travels through the transformers
# path, the llama.cpp path and the HTTP providers on every platform.
# ==============================================================================
import threading
from typing import Any, Optional

from core.logger import get_logger

log = get_logger(__name__)


class CancellationToken:
    """Signals, across threads, that a generation is no longer wanted."""

    __slots__ = ("_event", "_reason")

    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason: Optional[str] = None

    def cancel(self, reason: str = "client_disconnected") -> None:
        """Idempotent: the first reason is the one that gets reported."""
        if not self._event.is_set():
            self._reason = reason
            self._event.set()
            log.debug("[Cancel] generation cancelled: %s", reason)

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    def __bool__(self) -> bool:
        """``if token:`` reads as "was this cancelled"."""
        return self._event.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._event.wait(timeout)


def is_cancelled(token: Any) -> bool:
    """
    Tolerant check for the many call sites that may or may not have a token.

    Callers that predate cancellation pass None, and a few pass a bare
    threading.Event; both must behave as "not cancelled" rather than raise in
    the middle of a generation loop.
    """
    if token is None:
        return False
    try:
        if isinstance(token, CancellationToken):
            return token.cancelled
        if isinstance(token, threading.Event):
            return token.is_set()
        checker = getattr(token, "cancelled", None)
        if isinstance(checker, bool):
            return checker
        if callable(checker):
            return bool(checker())
    except Exception:                       # never let this break generation
        return False
    return False


def stopping_criteria_for(token: Any):
    """
    A transformers ``StoppingCriteriaList`` that ends generation on cancel.

    Returns None when there is nothing to watch or when transformers is not
    importable here, so the caller can pass the result straight through to
    ``generate`` either way.
    """
    if token is None:
        return None
    try:
        from transformers import StoppingCriteria, StoppingCriteriaList
    except Exception:
        return None

    class _Cancelled(StoppingCriteria):
        # Called once per decoded token, so it must stay a flag read.
        def __call__(self, input_ids, scores, **kwargs) -> bool:
            return is_cancelled(token)

    return StoppingCriteriaList([_Cancelled()])
