# ==============================================================================
# core/pipeline/self_healing.py — Pipeline Self-Correction & Review Loop
# Sigma Studio v7 — Modular Pipeline Sub-package
# ==============================================================================
"""Handles self-correction loops, node revision feedback, and iterative AI corrections
when node validation or computational test scripts detect errors.
"""

import re
from core.logger import get_logger

log = get_logger(__name__)

MAX_FEEDBACK_ITERATIONS = 3


def _evaluate_condition(node_result: dict, condition: dict) -> bool:
    """Evaluate conditional branch edge for DAG pipeline execution.
    
    Args:
        node_result: Output dict from executed node.
        condition: Condition dict e.g. {"field": "status", "operator": "eq", "value": "success"}
    """
    if not condition:
        return True
        
    field = condition.get("field", "status")
    operator = condition.get("operator", "eq")
    target_val = condition.get("value", "")
    
    actual_val = node_result.get(field, node_result.get("output", ""))
    
    if operator == "eq":
        return str(actual_val).lower() == str(target_val).lower()
    elif operator == "neq":
        return str(actual_val).lower() != str(target_val).lower()
    elif operator == "contains":
        return str(target_val).lower() in str(actual_val).lower()
    elif operator == "matches":
        return bool(re.search(target_val, str(actual_val), re.IGNORECASE))
    
    return True


def _get_role_instructions(role: str, node_label: str) -> str:
    """Return specific instructions for an agent role in pipeline execution."""
    r_lower = role.lower()
    if "architect" in r_lower or "pianificat" in r_lower:
        return (
            "Il tuo compito è analizzare l'obiettivo globale e scomporlo in file e moduli concreti.\n"
            "Produce un piano strutturato indicando i file da creare sotto data/\n"
            "Formato file consigliato: Path: `data/<topic_slug>/01_modulo/teoria/<nome>.md`"
        )
    elif "test" in r_lower or "coder" in r_lower or "programmat" in r_lower:
        return (
            "Il tuo compito è scrivere ed eseguire test unitari in Python per validare la teoria.\n"
            "Usa sympy e numpy per le verifiche matematiche.\n"
            "Formatta i file con: Path: `data/<topic_slug>/01_modulo/test/test_<nome>.py` e blocco ```python"
        )
    elif "engineer" in r_lower or "matematic" in r_lower or "teoric" in r_lower:
        return (
            "Il tuo compito è scrivere la trattazione formale completa in Markdown LaTeX.\n"
            "Includi definizioni, teoremi, dimostrazioni ed esempi.\n"
            "Formatta i file con: Path: `data/<topic_slug>/01_modulo/teoria/<nome>.md` e blocco ```markdown"
        )
    elif "viz" in r_lower or "disegn" in r_lower or "grafic" in r_lower:
        return (
            "Il tuo compito è creare visualizzazioni interattive in HTML/JS (D3.js / Chart.js).\n"
            "Formatta i file con: Path: `data/<topic_slug>/01_modulo/viz/<nome>.html` e blocco ```html"
        )
    elif "revis" in r_lower or "review" in r_lower:
        return (
            "Il tuo compito è revisionare rigorosamente tutto il lavoro svolto dagli altri nodi.\n"
            "Verifica correttezza formale, test unitari e file generati.\n"
            "Rispondi in formato JSON: {\"approved\": true/false, \"score\": 1-100, \"feedback\": \"...\", \"corrections\": [...]}"
        )
    return f"Esegui il compito assegnato per il nodo '{node_label}' con il massimo rigore."
