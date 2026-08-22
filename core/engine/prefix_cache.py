# ==============================================================================
# core/engine/prefix_cache.py — Reusing the KV of what the model already read
#
# A chat turn hands the model the whole conversation again. Without a cache the
# transformers path re-runs attention over every prior turn before producing a
# single new token, so turn ten pays for turns one to nine a second time and the
# wait grows with the conversation -- the opposite of what a user expects.
#
# llama.cpp does this internally: it compares the incoming tokens with the ones
# it evaluated last and keeps the matching head. This is the same idea for the
# transformers path, done explicitly:
#
#   1. Remember the token ids of the last generation and the KV cache they left.
#   2. On the next request, find the longest common token prefix.
#   3. Crop the cache to that length and let generate() prefill only the tail.
#
# The whole thing rests on the prefix being stable across turns, which is why
# the system prompt was split by lifetime first (see core/chat/chat_runner.py):
# a clock in the system message moves the divergence point to token zero and
# this cache can never hit.
# ==============================================================================
import threading
from typing import Any, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

# Below this many shared tokens the bookkeeping costs more than the prefill it
# saves, and a near-empty cache is not worth holding VRAM for.
MIN_REUSABLE_TOKENS = 64


class PrefixKVCache:
    """
    Holds one conversation's KV cache between turns.

    One, not many: the engine keeps a single model resident, and a second
    cached conversation would occupy VRAM the plan reserved for the first. The
    cache follows whichever conversation spoke last, which is the one about to
    speak again.
    """

    __slots__ = ("_ids", "_cache", "_model_name", "_max_tokens", "_lock",
                 "hits", "misses", "tokens_reused", "tokens_prefilled")

    def __init__(self, max_tokens: int = 0):
        self._ids: List[int] = []
        self._cache: Any = None
        self._model_name: Optional[str] = None
        self._max_tokens = max_tokens
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.tokens_reused = 0
        self.tokens_prefilled = 0

    # ------------------------------------------------------------- lifecycle

    def configure(self, model_name: Optional[str], max_tokens: int) -> None:
        """
        Binds the cache to a model and a ceiling.

        The ceiling is the context the placement plan already reserved KV for,
        so holding a cache up to that length spends memory that was budgeted
        rather than memory that was not.
        """
        with self._lock:
            if model_name != self._model_name:
                self._reset_locked()
            self._model_name = model_name
            self._max_tokens = max_tokens

    def clear(self, reason: str = "") -> None:
        with self._lock:
            had = bool(self._cache)
            self._reset_locked()
        if had and reason:
            log.debug("[PrefixCache] cleared (%s)", reason)

    def _reset_locked(self) -> None:
        self._ids = []
        self._cache = None

    # ----------------------------------------------------------------- reuse

    def take(self, input_ids: List[int], model_name: str) -> Tuple[Any, int]:
        """
        The reusable cache for this prompt, cropped, and how many tokens it covers.

        Returns (None, 0) when nothing is reusable. Ownership of the returned
        cache passes to the caller: generate() mutates it in place, so it must
        not stay referenced here while a generation is running.
        """
        with self._lock:
            if self._cache is None or model_name != self._model_name:
                self.misses += 1
                return None, 0

            shared = _common_prefix_length(self._ids, input_ids)

            # The cache must not cover the whole prompt: the model needs at
            # least one token to attend to, and a cache as long as the input
            # leaves generate() nothing to forward.
            shared = min(shared, len(input_ids) - 1)

            if shared < MIN_REUSABLE_TOKENS:
                self.misses += 1
                self._reset_locked()
                return None, 0

            cache = self._cache
            self._cache = None                 # handed over, not shared
            self._ids = []

        try:
            cache.crop(shared)
        except Exception as exc:
            # A cache implementation without crop, or one that refuses: fall
            # back to a full prefill rather than feeding a mismatched cache,
            # which would corrupt the answer rather than merely slow it down.
            log.debug("[PrefixCache] crop unavailable (%s); full prefill", exc)
            self.misses += 1
            return None, 0

        self.hits += 1
        self.tokens_reused += shared
        log.debug("[PrefixCache] reusing %d of %d prompt tokens", shared, len(input_ids))
        return cache, shared

    def store(self, sequence_ids: List[int], cache: Any, model_name: str) -> None:
        """Keeps the cache left by a finished generation, for the next turn."""
        if cache is None or not sequence_ids:
            return
        if self._max_tokens and len(sequence_ids) > self._max_tokens:
            # Past the reserved window this stops being a saving and becomes a
            # second copy of the context sitting in VRAM.
            log.debug(
                "[PrefixCache] sequence of %d tokens exceeds the %d reserved; "
                "not retained", len(sequence_ids), self._max_tokens,
            )
            self.clear()
            return
        with self._lock:
            self._ids = list(sequence_ids)
            self._cache = cache
            self._model_name = model_name

    # ------------------------------------------------------------- telemetry

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "model": self._model_name,
            "cached_tokens": len(self._ids),
            "max_tokens": self._max_tokens or None,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round((self.hits / total) * 100, 1) if total else 0.0,
            "tokens_reused": self.tokens_reused,
            "tokens_prefilled": self.tokens_prefilled,
            "prefill_saved_percent": (
                round(
                    self.tokens_reused
                    / max(self.tokens_reused + self.tokens_prefilled, 1) * 100, 1
                )
            ),
        }


def _common_prefix_length(a: List[int], b: List[int]) -> int:
    """How many leading tokens two sequences share."""
    limit = min(len(a), len(b))
    index = 0
    while index < limit and a[index] == b[index]:
        index += 1
    return index
