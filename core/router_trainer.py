"""Router Trainer & Intent Classifier Module for Sigma Studio.

Provides:
- `classify_intent_with_ailo(message)`: Primary fast intent classification via fine-tuned Ailo-152M.
- `classify_agent_with_router(message)`: Fallback via Ollama sigma-router model.
- `ensure_sigma_router_model()`: Registers the lightweight sigma-router model in Ollama.
- `generate_routing_dataset()`: Builds JSONL fine-tuning dataset for the router.
- `log_routing_feedback(...)`: Saves mis-classifications for incremental retraining.

Intent JSON schema:
  {
    "mode":       "LOOP" | "INFO" | "PLAN",
    "agent":      "<agent_id>",
    "intent":     "<intent_type>",
    "actions":    ["<action1>", ...]
    "confidence": 0.0-1.0   (optional, from Ailo)
  }
"""

import os
import re
import json
import time
import threading
import requests
from functools import lru_cache
from pathlib import Path
from core.logger import get_logger
from core.agent_registry import get_all_agents

log = get_logger("sigma.router")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

from core import paths

ADAPTER_META   = paths.training_dir() / "jobs" / "sigma-router-ailo" / "model_meta.json"
FEEDBACK_LOG   = paths.training_dir() / "datasets" / "sigma_feedback.jsonl"
ROUTER_MODEL_NAME = "sigma-router"
BASE_MODEL_NAME   = "sigma-alpaca-3b:latest"

VALID_MODES   = {"LOOP", "INFO", "PLAN"}
VALID_AGENTS  = {
    "math_researcher", "code_architect", "viz_designer",
    "test_engineer", "proof_reviewer", "sigma_architect", "sigma_assistant",
}

# ---------------------------------------------------------------------------
# Ailo-152M Local Inference
# ---------------------------------------------------------------------------
# The fine-tuned adapter is loaded lazily (once) in a thread-safe manner.
# Falls back gracefully to Ollama router if model not available.

_ailo_model     = None
_ailo_tokenizer = None
_ailo_lock      = threading.Lock()
_ailo_available = None   # None = not yet checked


def _load_ailo_model():
    """Load the fine-tuned Ailo router model. Called once, thread-safe."""
    global _ailo_model, _ailo_tokenizer, _ailo_available

    if not ADAPTER_META.exists():
        log.debug("Ailo router adapter not found at %s (not yet trained)", ADAPTER_META)
        _ailo_available = False
        return False

    try:
        meta = json.loads(ADAPTER_META.read_text(encoding="utf-8"))
        adapter_path = Path(meta.get("adapter_path", ""))
        if not adapter_path.exists():
            log.warning("Ailo adapter path not found: %s", adapter_path)
            _ailo_available = False
            return False

        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import PeftModel
        import torch

        base_model_id = meta.get("base_model", "xxrickyxx/ailo-152m")

        log.info("Loading Ailo-152M router from %s ...", adapter_path)
        tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        base = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base, str(adapter_path))
        model.eval()

        _ailo_tokenizer = tokenizer
        _ailo_model = model
        _ailo_available = True
        log.info("✅ Ailo router loaded successfully (CPU inference)")
        return True

    except Exception as e:
        log.warning("Could not load Ailo router model: %s", e)
        _ailo_available = False
        return False


def _ensure_ailo_loaded() -> bool:
    """Ensure Ailo model is loaded (lazy, thread-safe)."""
    global _ailo_available
    if _ailo_available is True:
        return True
    if _ailo_available is False:
        return False
    with _ailo_lock:
        if _ailo_available is None:
            _load_ailo_model()
    return _ailo_available is True


SYSTEM_PROMPT_ROUTER = (
    "Sei il Router Intelligente di Sigma Studio. "
    "Analizza la richiesta dell'utente e rispondi ESCLUSIVAMENTE con un oggetto JSON valido "
    'con i campi: "mode" (LOOP|INFO|PLAN), "agent", "intent", "actions" (lista). '
    "Agenti: math_researcher, code_architect, viz_designer, test_engineer, "
    "proof_reviewer, sigma_architect, sigma_assistant. Rispondi SOLO con JSON."
)


def _build_router_prompt(message: str) -> str:
    """Build the formatted prompt for Ailo inference."""
    return (
        f"<|system|>\n{SYSTEM_PROMPT_ROUTER}<|end|>\n"
        f"<|user|>\n{message}<|end|>\n"
        f"<|assistant|>\n"
    )


def _parse_intent_json(raw: str) -> dict | None:
    """Extract and validate intent JSON from model output."""
    raw = raw.strip()
    # Try direct parse first
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from surrounding text
        m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not m:
            return None
        try:
            d = json.loads(m.group())
        except json.JSONDecodeError:
            return None

    # Validate required fields
    mode  = str(d.get("mode", "")).upper()
    agent = str(d.get("agent", "")).lower().replace("-", "_")

    if mode not in VALID_MODES:
        return None
    if agent not in VALID_AGENTS:
        # Try to find closest agent
        for va in VALID_AGENTS:
            if va in agent or agent in va:
                agent = va
                break
        else:
            agent = "sigma_assistant"

    return {
        "mode":    mode,
        "agent":   agent,
        "intent":  str(d.get("intent", "general_chat")),
        "actions": [str(a) for a in d.get("actions", [])],
    }


@lru_cache(maxsize=128)
def _cached_ailo_classify(message: str) -> str | None:
    """Cached inference — identical messages return immediately (0ms)."""
    return _run_ailo_inference(message)


def _run_ailo_inference(message: str) -> str | None:
    """Run Ailo-152M inference and return raw JSON string or None."""
    import torch
    prompt = _build_router_prompt(message)
    inputs = _ailo_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        outputs = _ailo_model.generate(
            **inputs,
            max_new_tokens=80,
            do_sample=False,       # greedy — deterministic, fast
            temperature=1.0,
            pad_token_id=_ailo_tokenizer.eos_token_id,
        )
    # Decode only the generated part (after the prompt)
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return _ailo_tokenizer.decode(generated, skip_special_tokens=True).strip()


def classify_intent_with_ailo(message: str, timeout: float = 5.0) -> dict | None:
    """Classify user intent using fast embedding router or fine-tuned Ailo-152M.

    Returns:
        dict with keys: mode, agent, intent, actions
        None if classification failed

    Performance: ~5-15ms via SentenceTransformers or ~50-150ms via Ailo.
    """
    if not message or not message.strip():
        return None

    # Priority 1: Fast Multilingual Vector Router (handles Italian/English perfectly, 5ms)
    try:
        from core.embedding_router import classify_intent_multilingual
        emb_res = classify_intent_multilingual(message)
        if emb_res:
            return emb_res
    except Exception as e:
        log.debug("Embedding router check failed: %s", e)

    if not _ensure_ailo_loaded():
        return None

    t0 = time.time()
    try:
        raw = _cached_ailo_classify(message.strip().lower())
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        if not raw:
            return None

        result = _parse_intent_json(raw)
        if result:
            log.info(
                "🧠 Ailo Router [%sms]: '%s...' → mode=%s agent=%s",
                elapsed_ms, message[:40], result["mode"], result["agent"]
            )
        return result

    except Exception as e:
        log.warning("Ailo inference error: %s", e)
        return None


# ---------------------------------------------------------------------------
# Online Feedback Logging (for incremental retraining)
# ---------------------------------------------------------------------------

def log_routing_feedback(
    message: str,
    predicted_mode: str,
    actual_mode: str,
    predicted_agent: str,
    actual_agent: str,
    outcome: str = "unknown",
):
    """Log a routing mis-classification for later incremental fine-tuning.

    Args:
        message:         Original user message
        predicted_mode:  What Ailo predicted (e.g. "INFO")
        actual_mode:     What actually happened (e.g. "LOOP")
        predicted_agent: Predicted agent ID
        actual_agent:    Actual agent that handled the request
        outcome:         "correct" | "wrong_mode" | "wrong_agent" | "both_wrong"
    """
    if predicted_mode == actual_mode and predicted_agent == actual_agent:
        return  # Nothing to log if correct

    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp":       time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message":         message,
        "predicted_mode":  predicted_mode,
        "actual_mode":     actual_mode,
        "predicted_agent": predicted_agent,
        "actual_agent":    actual_agent,
        "outcome":         outcome,
    }
    try:
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.debug("Feedback logged: %s → %s (was %s)", message[:30], actual_mode, predicted_mode)
    except Exception as e:
        log.warning("Failed to log feedback: %s", e)


def get_feedback_stats() -> dict:
    """Return statistics about logged routing feedback."""
    if not FEEDBACK_LOG.exists():
        return {"total": 0, "file": str(FEEDBACK_LOG)}
    total = wrong_mode = wrong_agent = both_wrong = 0
    with open(FEEDBACK_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                total += 1
                pm, am = e.get("predicted_mode"), e.get("actual_mode")
                pa, aa = e.get("predicted_agent"), e.get("actual_agent")
                if pm != am and pa != aa:
                    both_wrong += 1
                elif pm != am:
                    wrong_mode += 1
                elif pa != aa:
                    wrong_agent += 1
            except Exception:
                pass
    return {
        "total": total,
        "wrong_mode": wrong_mode,
        "wrong_agent": wrong_agent,
        "both_wrong": both_wrong,
        "file": str(FEEDBACK_LOG),
    }


# ---------------------------------------------------------------------------
# Ollama Fallback Router (existing implementation)
# ---------------------------------------------------------------------------

def ensure_sigma_router_model() -> bool:
    """Ensure the custom `sigma-router` model exists in Ollama if Ollama is running."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=0.5)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            if any(ROUTER_MODEL_NAME in m for m in models):
                return True

            system_prompt = """Sei l'Orchestratore e Centralino Intelligente di Sigma Studio.
Classifica l'intenzione dell'utente. Rispondi ESCLUSIVAMENTE con l'ID dell'agente prescelto tra i seguenti:
- math_researcher (matematica, probabilità, teoremi, formule, dimostrazioni, equazioni, fisica o teoria)
- code_architect (programmazione, scrittura o modifica codice, script python, react, bug, refactoring)
- viz_designer (grafici d3, canvas, diagrammi, layout visivi)
- test_engineer (unit test, pytest, asserzioni)
- proof_reviewer (revisione o confutazione di dimostrazioni)
- sigma_architect (architettura di sistema, moduli, roadmap)
- sigma_assistant (saluti, conversazione generale, aiuto)

Rispondi SOLO ed ESCLUSIVAMENTE con l'ID dell'agente (es. math_researcher). NESSUN ALTRO TESTO."""

            payload = {
                "name": ROUTER_MODEL_NAME,
                "from": BASE_MODEL_NAME,
                "system": system_prompt,
                "parameters": {"temperature": 0.0, "num_predict": 12},
                "stream": False
            }
            res = requests.post("http://localhost:11434/api/create", json=payload, timeout=30)
            if res.status_code == 200:
                log.info("Initialized '%s' model in Ollama", ROUTER_MODEL_NAME)
                return True
    except Exception:
        pass
    return False


def classify_agent_with_router(message: str, timeout: float = 8.0) -> str:
    """Classify user prompt using the Ollama sigma-router model (fallback).

    Returns:
        Manifesto path string (e.g. 'manifesti/math_researcher.md') or empty string.
    """
    if not message or not message.strip():
        return ""

    t0 = time.time()
    try:
        res = requests.post("http://localhost:11434/api/chat", json={
            "model": "sigma-router:latest",
            "messages": [{"role": "user", "content": message}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 12}
        }, timeout=timeout)

        if res.status_code == 200:
            dur = round((time.time() - t0) * 1000, 1)
            raw = res.json().get("message", {}).get("content", "").strip()
            match = re.search(
                r'\b(math_researcher|code_architect|viz_designer|test_engineer|'
                r'proof_reviewer|sigma_architect|sigma_assistant|sigma_admin)\b',
                raw, re.IGNORECASE
            )
            if match:
                agent_id = match.group(1).lower()
                manifesto_path = f"manifesti/{agent_id}.md"
                if os.path.exists(manifesto_path):
                    log.info("🧠 Ollama Router (%sms) → agent: %s", dur, agent_id)
                    return manifesto_path
    except Exception as exc:
        log.debug("Router model query failed (%s), falling back", exc)

    return ""


# ---------------------------------------------------------------------------
# Dataset generation (maintained for backward compatibility)
# ---------------------------------------------------------------------------

def generate_routing_dataset(output_path: str = "training/datasets/router_dataset.jsonl") -> int:
    """Generate a basic routing fine-tuning dataset.

    For the full Ailo fine-tuning dataset, use:
        python training/scripts/generate_sigma_intent_dataset.py
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dataset = [
        {"input": "Vorrei studiare le proprietà degli insiemi aperti in R^n", "target": "math_researcher"},
        {"input": "Dimostrami il teorema di Bayes in modo formale", "target": "math_researcher"},
        {"input": "Calcola la convergenza della serie armonica alternata", "target": "math_researcher"},
        {"input": "Come trovare la misura di Lebesgue di un intervallo?", "target": "math_researcher"},
        {"input": "Possiamo formulare un modello basato sulle catene di Markov?", "target": "math_researcher"},
        {"input": "Scrivi uno script python per ordinare una lista con quicksort", "target": "code_architect"},
        {"input": "Crea un componente React per mostrare una tabella dati", "target": "code_architect"},
        {"input": "Refattorizza questa funzione python per migliorare le prestazioni", "target": "code_architect"},
        {"input": "Crea un grafico D3 interattivo per la distribuzione", "target": "viz_designer"},
        {"input": "Scrivi gli unit test con pytest per la classe data_handler", "target": "test_engineer"},
        {"input": "Esamina e confuta la seguente dimostrazione del Lemma", "target": "proof_reviewer"},
        {"input": "Pianifica la roadmap dei moduli del progetto Sigma", "target": "sigma_architect"},
        {"input": "Ciao, chi sei e cosa puoi fare?", "target": "sigma_assistant"},
    ]

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for item in dataset:
            entry = {
                "messages": [
                    {"role": "system", "content": "Sei l'Orchestratore di Sigma Studio. Classifica la richiesta con l'ID dell'agente."},
                    {"role": "user", "content": item["input"]},
                    {"role": "assistant", "content": item["target"]}
                ]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1

    log.info("Generated routing dataset: %d items at '%s'", count, output_path)
    return count
