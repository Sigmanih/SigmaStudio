# ==============================================================================
# core/harness/laya_router.py — System-1 Decision Router & Hardware Dispatcher
# Sigma Studio v8 — Agent Harness (Kernel-side)
# ==============================================================================
"""Router decisionale ultra-rapido (System-1) basato su Laya per il runtime agente e chat.

Offre classificazione di intent, stima di complessità e decisioni di retry
in 15-30 ms tramite forward pass diretto dei logits, senza generare token.

Posizionamento Hardware Differenziato:
- Se sono presenti 2+ GPU (es. GPU 0 = RTX 5070 Ti, GPU 1 = RTX 5060), assegna
  Laya a 'cuda:1' per lasciare la VRAM della GPU primaria al 100% per il modello LLM.
- Supporta DirectML (iGPU / AMD / Intel) e CPU multi-thread con AVX-512/AVX2.
"""
from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("harness.laya_router")

# ──────────────────────────────────────────────────────────────────────── stato

_agent = None
_agent_lock = threading.Lock()
_load_error: Optional[str] = None
_load_time_ms: float = 0.0
_target_device: Optional[str] = None
_stats = {"calls": 0, "total_ms": 0.0, "errors": 0}


def get_target_device() -> str:
    """Determina il device migliore per Laya preservando la GPU primaria per l'LLM."""
    global _target_device
    if _target_device is not None:
        return _target_device

    # Override esplicito da variabile di ambiente
    custom = os.environ.get("SIGMA_LAYA_DEVICE", "").strip().lower()
    if custom:
        _target_device = custom
        return _target_device

    # Override da configurazione di sistema (config.json o ai_config)
    try:
        from core.ai_providers import load_ai_config
        cfg = load_ai_config()
        configured_dev = (cfg.get("laya_device") or cfg.get("router_device") or "").strip().lower()
        if configured_dev:
            _target_device = configured_dev
            return _target_device
    except Exception:
        pass

    try:
        import torch
        if torch.cuda.is_available():
            count = torch.cuda.device_count()
            if count > 1:
                # GPU secondaria (es. RTX 5060) dedicata a Laya/Embedding
                _target_device = "cuda:1"
                log.info("[LayaRouter] Trovate %d GPU: selezionata GPU secondaria 'cuda:1'", count)
                return _target_device
            else:
                # Singola GPU: default su cuda:0 oppure cpu se configurato
                _target_device = "cuda:0"
                return _target_device
    except Exception as exc:
        log.debug("[LayaRouter] Rilevamento CUDA non riuscito: %s", exc)

    # Fallback su CPU
    _target_device = "cpu"
    return _target_device


def _get_agent():
    """Carica il modello Laya una sola volta in modo thread-safe (singleton)."""
    global _agent, _load_error, _load_time_ms
    if _agent is not None:
        return _agent

    with _agent_lock:
        if _agent is not None:
            return _agent
        try:
            import laya
            dev = get_target_device()
            t0 = time.perf_counter()
            log.info("[LayaRouter] Inizializzazione Laya sul device '%s'...", dev)
            _agent = laya.load(device=dev)
            _load_time_ms = (time.perf_counter() - t0) * 1000
            log.info(
                "[LayaRouter] Modello pronto in %.0f ms sul device '%s'",
                _load_time_ms, dev,
            )
            return _agent
        except Exception as exc:
            _load_error = str(exc)
            log.warning("[LayaRouter] Modello Laya non disponibile (%s). Routing disattivato.", exc)
            return None


# ──────────────────────────────────────────────────────────── criteri di triage

ROUTER_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "intent": {
        "type": "choice",
        "instructions": "Qual e' l'intento prevalente della richiesta dell'utente?",
        "criteria": {
            "code": "Scrivere, debuggare, modificare, spiegare codice o file di progetto",
            "chat": "Conversazione informale, saluti, domande generiche o filosofiche che non toccano codice o file",
            "search": "Ricerca su internet, documentazione esterna o ultime notizie",
            "system": "Comandi operativi di shell, eliminazione file o operazioni di sistema",
        },
    },
    "complexity": {
        "type": "choice",
        "instructions": "Qual e' il livello di complessita' e ragionamento richiesto?",
        "criteria": {
            "low": "Richiesta semplice, diretta, fattibile senza ragionamento multi-passo",
            "high": "Problema complesso, architettura, refactoring esteso o logica articolata",
        },
    },
    "retry": {
        "type": "choice",
        "instructions": "Il tool ha restituito un output utile o un errore che richiede retry?",
        "criteria": {
            "ok": "L'output contiene dati validi o risultato utile",
            "retry": "L'esecuzione ha fallito o e' incompleta e merita un retry immediato",
        },
    },
    "failure_diagnosis": {
        "type": "choice",
        "instructions": "Qual e' la natura del fallimento del tool e come deve reagire l'agente?",
        "criteria": {
            "transient": "Errore temporaneo di timeout, rete o risorsa occupata: riprovare immediatamente",
            "wrong_path": "Percorso file non esistente o non trovato: serve esplorare con glob o list_dir",
            "syntax_or_diff": "Errore di sintassi, diff non applicabile o old_string non trovata: rileggere e correggere",
            "permission_or_fatal": "Permesso negato o errore fatale non recuperabile senza intervento",
        },
    },
}


@dataclass
class LayaDecision:
    """Risultato standardizzato di una decisione System-1."""
    intent: str = "chat"
    intent_confidence: float = 0.0
    complexity: str = "low"
    complexity_confidence: float = 0.0
    elapsed_ms: float = 0.0
    device: str = "cpu"
    raw: Dict[str, Any] = field(default_factory=dict)
    fallback: bool = False

    @property
    def should_skip_tools(self) -> bool:
        """True se l'intento e' pura chat e non richiede iniezione di schemi di tool."""
        return self.intent == "chat"

    @property
    def prefers_fast_model(self) -> bool:
        """True se la complessita' e' bassa e puo' essere gestita dal modello leggero."""
        return self.complexity == "low"


def triage_chat(message: str) -> LayaDecision:
    """Classifica istantaneamente (15-30 ms) intento e complessità del prompt utente."""
    if not message or not message.strip():
        return LayaDecision(fallback=True)

    agent = _get_agent()
    if agent is None:
        return LayaDecision(fallback=True, device=get_target_device())

    t0 = time.perf_counter()
    try:
        q = {
            "intent": ROUTER_QUESTIONS["intent"],
            "complexity": ROUTER_QUESTIONS["complexity"],
        }
        raw_res = agent.predict(message.strip(), q)
        elapsed = (time.perf_counter() - t0) * 1000

        answers = raw_res.get("answers", {})
        intent_info = answers.get("intent", {})
        comp_info = answers.get("complexity", {})

        _stats["calls"] += 1
        _stats["total_ms"] += elapsed

        return LayaDecision(
            intent=intent_info.get("choice", "chat"),
            intent_confidence=float(intent_info.get("answer_confidence", 0.0)),
            complexity=comp_info.get("choice", "low"),
            complexity_confidence=float(comp_info.get("answer_confidence", 0.0)),
            elapsed_ms=elapsed,
            device=get_target_device(),
            raw=raw_res,
            fallback=False,
        )
    except Exception as exc:
        _stats["errors"] += 1
        log.debug("[LayaRouter] Triage fallito: %s", exc)
        return LayaDecision(fallback=True, device=get_target_device())


def decide_tool_retry(tool_name: str, output_text: str, error_text: str = "") -> bool:
    """Valuta in 15 ms se l'output di un tool merita un retry immediato nell'harness."""
    agent = _get_agent()
    if agent is None or not error_text:
        return bool(error_text)

    prompt = f"Tool: {tool_name}\nError: {error_text}\nOutput: {output_text[:500]}"
    try:
        raw = agent.predict(prompt, {"retry": ROUTER_QUESTIONS["retry"]})
        choice = raw.get("answers", {}).get("retry", {}).get("choice", "ok")
        return choice == "retry"
    except Exception:
        return bool(error_text)


def diagnose_tool_failure(tool_name: str, error_text: str, output_text: str = "") -> Dict[str, Any]:
    """Diagnosi in ~15 ms dell'errore di un tool per suggerire l'azione immediata nell'harness."""
    agent = _get_agent()
    t0 = time.perf_counter()
    if agent is None or not error_text:
        is_transient = any(w in error_text.lower() for w in ("timeout", "timed out", "busy", "temporary", "connection reset"))
        return {
            "category": "transient" if is_transient else "general",
            "action": "retry" if is_transient else "replan",
            "hint": "Guasto temporaneo: riprova la chiamata." if is_transient else "Verifica parametri e percorso prima di proseguire.",
            "confidence": 0.5,
            "elapsed_ms": 0.0,
            "fallback": True,
        }

    prompt = f"Tool: {tool_name}\nError: {error_text[:300]}\nOutput: {output_text[:300]}"
    try:
        raw = agent.predict(prompt, {"failure_diagnosis": ROUTER_QUESTIONS["failure_diagnosis"]})
        elapsed = (time.perf_counter() - t0) * 1000
        choice = raw.get("answers", {}).get("failure_diagnosis", {}).get("choice", "wrong_path")
        conf = float(raw.get("answers", {}).get("failure_diagnosis", {}).get("answer_confidence", 0.0))

        hints = {
            "transient": "Guasto temporaneo di I/O o timeout: riprova subito la chiamata.",
            "wrong_path": "Il percorso non esiste: verifica con 'list_dir' o 'glob' prima di procedere.",
            "syntax_or_diff": "Il blocco cercato o la sintassi non combacia: rileggi le righe esatte con 'read_file'.",
            "permission_or_fatal": "Operazione negata o non consentita: modifica il piano evitando questo tool.",
        }
        actions = {
            "transient": "retry",
            "wrong_path": "replan",
            "syntax_or_diff": "replan",
            "permission_or_fatal": "giveup",
        }
        _stats["calls"] += 1
        _stats["total_ms"] += elapsed
        return {
            "category": choice,
            "action": actions.get(choice, "replan"),
            "hint": hints.get(choice, "Verifica parametri prima di proseguire."),
            "confidence": conf,
            "elapsed_ms": round(elapsed, 1),
            "fallback": False,
        }
    except Exception as exc:
        _stats["errors"] += 1
        return {
            "category": "general",
            "action": "replan",
            "hint": "Verifica parametri e percorso.",
            "confidence": 0.0,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "fallback": True,
        }


def get_router_status() -> Dict[str, Any]:
    """Restituisce lo stato attuale del router per telemetria e diagnostica."""
    avg_ms = (_stats["total_ms"] / _stats["calls"]) if _stats["calls"] > 0 else 0.0
    return {
        "loaded": _agent is not None,
        "device": get_target_device(),
        "load_time_ms": round(_load_time_ms, 1),
        "total_calls": _stats["calls"],
        "avg_latency_ms": round(avg_ms, 1),
        "errors": _stats["errors"],
        "last_error": _load_error,
    }
