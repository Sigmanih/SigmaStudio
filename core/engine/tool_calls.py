# ==============================================================================
# core/engine/tool_calls.py — Ricomposizione delle tool call in streaming
# Sigma Studio v8 — Engine
# ==============================================================================
"""Le tool call arrivano a pezzi, e vanno rimesse insieme allo stesso modo.

Serve in due direzioni opposte e finora stava scritta solo in una: quando Sigma
fa da provider verso altri applicativi, e quando Sigma chiama un provider
esterno per conto proprio. Due copie della stessa ricomposizione sarebbero due
occasioni di sbagliare in modo diverso sullo stesso formato.
"""

import uuid
from typing import Any, Dict, List


class ToolCallAccumulator:
    """Ricompone le tool_calls che arrivano spezzate nei delta.

    Vengono trasmesse come frammenti numerati: il nome in uno, gli argomenti in
    venti, e nulla garantisce che siano contigui. Accumulare per indice e'
    l'unico modo di ottenere JSON valido alla fine; concatenare in ordine di
    arrivo fonde due chiamate in una appena il modello ne emette due.
    """

    def __init__(self) -> None:
        self._per_index: Dict[int, Dict[str, Any]] = {}

    def add(self, deltas: Any) -> None:
        if not isinstance(deltas, list):
            return
        for delta in deltas:
            if not isinstance(delta, dict):
                continue
            idx = delta.get("index")
            idx = int(idx) if isinstance(idx, int) else len(self._per_index)
            slot = self._per_index.setdefault(
                idx,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            if delta.get("id"):
                slot["id"] = str(delta["id"])
            if delta.get("type"):
                slot["type"] = str(delta["type"])
            fn = delta.get("function") or {}
            if fn.get("name"):
                slot["function"]["name"] = str(fn["name"])
            if fn.get("arguments"):
                slot["function"]["arguments"] += str(fn["arguments"])

    def result(self) -> List[Dict[str, Any]]:
        """Le chiamate complete, in ordine di indice, con un id se mancava."""
        out = []
        for idx in sorted(self._per_index):
            call = self._per_index[idx]
            if not call["function"]["name"]:
                continue
            if not call["id"]:
                # Un client correla il risultato alla chiamata per id: senza,
                # non saprebbe a quale delle due sta rispondendo.
                call["id"] = f"call_{uuid.uuid4().hex[:20]}"
            out.append(call)
        return out
