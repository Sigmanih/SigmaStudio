"""Router Trainer & Intent Classifier Module for Sigma Studio.

Provides:
- `ensure_sigma_router_model()`: Registers the lightweight dedicated `sigma-router` model in Ollama.
- `classify_agent_with_router(message)`: Ultra-fast (<200ms) LLM intent classification.
- `generate_routing_dataset()`: Builds JSONL fine-tuning dataset for training custom routing models.
"""

import os
import re
import json
import time
import requests
from core.logger import get_logger
from core.agent_registry import get_all_agents

log = get_logger("sigma.router")

ROUTER_MODEL_NAME = "sigma-router"
BASE_MODEL_NAME = "sigma-alpaca-3b:latest"


def ensure_sigma_router_model() -> bool:
    """Ensure the custom `sigma-router` model exists in Ollama."""
    try:
        # Check existing models
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            if any(ROUTER_MODEL_NAME in m for m in models):
                return True

        # Build sigma-router model with custom system prompt
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
            "parameters": {
                "temperature": 0.0,
                "num_predict": 12
            },
            "stream": False
        }
        res = requests.post("http://localhost:11434/api/create", json=payload, timeout=30)
        if res.status_code == 200:
            log.info("Successfully initialized dedicated '%s' model in Ollama", ROUTER_MODEL_NAME)
            return True
        else:
            log.warning("Could not create '%s': %s", ROUTER_MODEL_NAME, res.text[:200])
    except Exception as exc:
        log.warning("Ollama router creation skipped: %s", exc)
    return False


def classify_agent_with_router(message: str, timeout: float = 8.0) -> str:
    """Classify the user prompt using the dedicated lightweight `sigma-router` model.

    Returns:
        Manifesto path string (e.g. 'manifesti/math_researcher.md') or empty string if unclassified.
    """
    if not message or not message.strip():
        return ""

    t0 = time.time()
    try:
        model_name = "sigma-router:latest"
        res = requests.post("http://localhost:11434/api/chat", json={
            "model": model_name,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 12}
        }, timeout=timeout)

        if res.status_code == 200:
            dur = round((time.time() - t0) * 1000, 1)
            raw = res.json().get("message", {}).get("content", "").strip()
            
            # Match against known agent IDs
            match = re.search(r'\b(math_researcher|code_architect|viz_designer|test_engineer|proof_reviewer|sigma_architect|sigma_assistant|sigma_admin)\b', raw, re.IGNORECASE)
            if match:
                agent_id = match.group(1).lower()
                manifesto_path = f"manifesti/{agent_id}.md"
                if os.path.exists(manifesto_path):
                    log.info("🧠 Model Router ('%s' in %sms) -> agent: %s", ROUTER_MODEL_NAME, dur, agent_id)
                    return manifesto_path
    except Exception as exc:
        log.debug("Router model query failed (%s), falling back", exc)
    
    return ""


def generate_routing_dataset(output_path: str = "data/router_dataset.jsonl") -> int:
    """Generate fine-tuning dataset pairs for custom model training.

    Format: JSONL {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
    """
    dataset = [
        {"input": "Vorrei studiare le proprietà degli insiemi aperti in R^n", "target": "math_researcher"},
        {"input": "Dimostrami il teorema di Bayes in modo formale", "target": "math_researcher"},
        {"input": "Calcola la convergenza della serie armonica alternata", "target": "math_researcher"},
        {"input": "Come trovare la misura di Lebesgue di un intervallo?", "target": "math_researcher"},
        {"input": "Possiamo formulare un modello basato sulle catene di Markov?", "target": "math_researcher"},
        {"input": "Dimostra il principio di induzione per n > 0", "target": "math_researcher"},
        {"input": "Qual è il teorema fondamentale dell'algebra?", "target": "math_researcher"},
        {"input": "Spiegami la distribuzione di Poisson in teoria della probabilità", "target": "math_researcher"},
        {"input": "Scrivi uno script python per ordinare una lista con quicksort", "target": "code_architect"},
        {"input": "Crea un componente React per mostrare una tabella dati", "target": "code_architect"},
        {"input": "Refattorizza questa funzione python per migliorare le prestazioni", "target": "code_architect"},
        {"input": "Trova e correggi il bug in questo codice JavaScript", "target": "code_architect"},
        {"input": "Crea un grafico D3 interattivo per la distribuzione", "target": "viz_designer"},
        {"input": "Disegna un diagramma di flusso in HTML e Canvas", "target": "viz_designer"},
        {"input": "Genera una mappa concettuale visiva in SVG", "target": "viz_designer"},
        {"input": "Scrivi gli unit test con pytest per la classe data_handler", "target": "test_engineer"},
        {"input": "Verifica le asserzioni di questo test in python", "target": "test_engineer"},
        {"input": "Esamina e confuta la seguente dimostrazione del Lemma", "target": "proof_reviewer"},
        {"input": "Esegui una peer review su questo whitepaper matematico", "target": "proof_reviewer"},
        {"input": "Pianifica la roadmap dei moduli del progetto Sigma", "target": "sigma_architect"},
        {"input": "Definisci l'architettura dei moduli per la libreria", "target": "sigma_architect"},
        {"input": "Ciao, chi sei e cosa puoi fare?", "target": "sigma_assistant"},
        {"input": "Buongiorno, mi spieghi come funziona la piattaforma?", "target": "sigma_assistant"},
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for item in dataset:
            entry = {
                "messages": [
                    {"role": "system", "content": "Sei l'Orchestratore di Sigma Studio. Classifica la richiesta dell'utente con l'ID dell'agente prescelto."},
                    {"role": "user", "content": item["input"]},
                    {"role": "assistant", "content": item["target"]}
                ]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1

    log.info("Generated fine-tuning dataset with %d items at '%s'", count, output_path)
    return count
