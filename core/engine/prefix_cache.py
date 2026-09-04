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
#
# **Perche' piu' di uno slot.** Una sola conversazione in cache basta finche' ce
# n'e' una sola. Un harness a ruoli ne alterna diverse sullo stesso modello —
# Architect, Coder, Tester — e ognuna ha il proprio system prompt, quindi il
# proprio prefisso. Con un unico slot il passaggio da un ruolo all'altro
# sfratta il prefisso dell'altro, e alternandoli non si riusa mai nulla: il
# caso peggiore possibile, ottenuto proprio quando la cache servirebbe di piu'.
# Gli slot sono chiavi arbitrarie (il ruolo, la sessione) con sfratto LRU e un
# tetto basso, perche' ogni slot e' KV che resta in VRAM.
# ==============================================================================
import os
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

# Below this many shared tokens the bookkeeping costs more than the prefill it
# saves, and a near-empty cache is not worth holding VRAM for.
MIN_REUSABLE_TOKENS = 64

#: Quanti prefissi tenere insieme. Due di default: copre l'alternanza fra due
#: ruoli, che e' il caso reale, senza raddoppiare la VRAM occupata dalla cache.
#: Si alza con SIGMA_PREFIX_CACHE_SLOTS quando la macchina ha memoria da
#: spendere e i ruoli in gioco sono di piu'.
DEFAULT_MAX_SLOTS = 2

#: Lo slot di chi non ne chiede uno: la chat normale, che di conversazioni
#: correnti ne ha una sola.
DEFAULT_SLOT = "default"


def _max_slots_from_env() -> int:
    try:
        valore = int(os.environ.get("SIGMA_PREFIX_CACHE_SLOTS", DEFAULT_MAX_SLOTS))
    except (TypeError, ValueError):
        return DEFAULT_MAX_SLOTS
    return max(1, min(valore, 8))


class PrefixKVCache:
    """
    Holds the KV cache of one or more conversations between turns.

    Ogni slot e' indipendente: chiave, token e cache. Il modello invece e' uno
    solo — quello residente — e cambiarlo invalida tutto, perche' un KV nato
    da altri pesi non e' riutilizzabile, e' sbagliato.
    """

    __slots__ = ("_slots", "_model_name", "_max_tokens", "_max_slots", "_lock",
                 "hits", "misses", "tokens_reused", "tokens_prefilled", "evictions")

    def __init__(self, max_tokens: int = 0, max_slots: Optional[int] = None):
        #: chiave -> (token ids, cache). Ordinato per uso: il primo e' il piu'
        #: vecchio, ed e' quello che si sfratta.
        self._slots: "OrderedDict[str, Tuple[List[int], Any]]" = OrderedDict()
        self._model_name: Optional[str] = None
        self._max_tokens = max_tokens
        self._max_slots = int(max_slots) if max_slots else _max_slots_from_env()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.tokens_reused = 0
        self.tokens_prefilled = 0
        self.evictions = 0

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

    def clear(self, reason: str = "", slot: Optional[str] = None) -> None:
        """Svuota tutti gli slot, o soltanto quello indicato."""
        with self._lock:
            if slot is None:
                aveva = bool(self._slots)
                self._reset_locked()
            else:
                aveva = self._slots.pop(slot, None) is not None
        if aveva and reason:
            log.debug("[PrefixCache] cleared %s (%s)", slot or "all slots", reason)

    def _reset_locked(self) -> None:
        self._slots.clear()

    def _evict_locked(self) -> None:
        while len(self._slots) > self._max_slots:
            chiave, _ = self._slots.popitem(last=False)
            self.evictions += 1
            log.debug("[PrefixCache] slot '%s' sfrattato (LRU)", chiave)

    # ----------------------------------------------------------------- reuse

    def take(
        self,
        input_ids: List[int],
        model_name: str,
        slot: str = DEFAULT_SLOT,
    ) -> Tuple[Any, int]:
        """
        The reusable cache for this prompt, cropped, and how many tokens it covers.

        Returns (None, 0) when nothing is reusable. Ownership of the returned
        cache passes to the caller: generate() mutates it in place, so it must
        not stay referenced here while a generation is running.

        Il confronto avviene solo dentro lo slot richiesto. Cercare il miglior
        prefisso fra tutti gli slot sembrerebbe piu' furbo, ma due ruoli
        divergono gia' nel system prompt: si pagherebbe la scansione per
        trovare, quasi sempre, meno dei token minimi.
        """
        slot = slot or DEFAULT_SLOT
        with self._lock:
            voce = self._slots.get(slot)
            if voce is None or model_name != self._model_name:
                self.misses += 1
                return None, 0

            ids_memorizzati, cache = voce
            shared = _common_prefix_length(ids_memorizzati, input_ids)

            # The cache must not cover the whole prompt: the model needs at
            # least one token to attend to, and a cache as long as the input
            # leaves generate() nothing to forward.
            shared = min(shared, len(input_ids) - 1)

            if shared < MIN_REUSABLE_TOKENS:
                self.misses += 1
                self._slots.pop(slot, None)
                return None, 0

            self._slots.pop(slot, None)        # handed over, not shared

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
        log.debug(
            "[PrefixCache] slot '%s': riusati %d dei %d token di prompt",
            slot, shared, len(input_ids),
        )
        return cache, shared

    def store(
        self,
        sequence_ids: List[int],
        cache: Any,
        model_name: str,
        slot: str = DEFAULT_SLOT,
    ) -> None:
        """Keeps the cache left by a finished generation, for the next turn."""
        if cache is None or not sequence_ids:
            return
        slot = slot or DEFAULT_SLOT
        if self._max_tokens and len(sequence_ids) > self._max_tokens:
            # Past the reserved window this stops being a saving and becomes a
            # second copy of the context sitting in VRAM.
            log.debug(
                "[PrefixCache] sequence of %d tokens exceeds the %d reserved; "
                "not retained", len(sequence_ids), self._max_tokens,
            )
            self.clear(slot=slot)
            return
        with self._lock:
            if model_name != self._model_name:
                # Il modello e' cambiato sotto: ogni prefisso precedente e'
                # nato da altri pesi e non e' piu' confrontabile.
                self._reset_locked()
                self._model_name = model_name
            self._slots.pop(slot, None)
            self._slots[slot] = (list(sequence_ids), cache)
            self._evict_locked()

    # ------------------------------------------------------------- telemetry

    def stats(self) -> dict:
        total = self.hits + self.misses
        with self._lock:
            per_slot: Dict[str, int] = {
                chiave: len(ids) for chiave, (ids, _) in self._slots.items()
            }
        return {
            "model": self._model_name,
            "slots": per_slot,
            "slots_used": len(per_slot),
            "max_slots": self._max_slots,
            "evictions": self.evictions,
            "cached_tokens": sum(per_slot.values()),
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
    """How many leading token ids the two sequences share."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n
