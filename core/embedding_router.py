"""Fast Multilingual Router using Sentence Transformers / Embedding Similarity.

Replaces generative routing with lightweight, high-precision vector similarity
against pre-defined anchor intents. Provides sub-10ms intent classification on CPU.
"""

import os
import json
import time
from pathlib import Path
from core.logger import get_logger

# numpy is imported where it is used, not here. This module is on the critical
# path of every chat message, and it has a pure-standard-library fallback that
# works without numpy or sentence-transformers -- which is the configuration on
# a Raspberry Pi, on a fresh CPU-only install, and anywhere the ML extras have
# not been built yet. A module-level import would make the import itself fail
# there, and take routing down with it.

from core import paths

log = get_logger("sigma.embedding_router")

EMBEDDINGS_FILE = paths.training_dir() / "jobs" / "router_embeddings.json"

# In-memory anchor dataset
ANCHORS = [
    # Math Researcher - LOOP (Creation)
    {"text": "scrivimi un argomento sugli esponenziali", "mode": "LOOP", "agent": "math_researcher", "intent": "create_topic_file", "actions": ["create_module", "create_file"]},
    {"text": "scrivi un modulo su analisi 1", "mode": "LOOP", "agent": "math_researcher", "intent": "create_topic_file", "actions": ["create_module", "create_file"]},
    {"text": "crea un documento sulla teoria dei gruppi", "mode": "LOOP", "agent": "math_researcher", "intent": "create_topic_file", "actions": ["create_module", "create_file"]},
    {"text": "genera l'argomento sulle serie di Taylor", "mode": "LOOP", "agent": "math_researcher", "intent": "create_topic_file", "actions": ["create_module", "create_file"]},
    {"text": "write a markdown file about differential equations", "mode": "LOOP", "agent": "math_researcher", "intent": "create_topic_file", "actions": ["create_module", "create_file"]},
    
    # Math Researcher - INFO (Explanations)
    {"text": "cos'è la derivata?", "mode": "INFO", "agent": "math_researcher", "intent": "explain_concept", "actions": []},
    {"text": "spiegami il teorema di Pitagora", "mode": "INFO", "agent": "math_researcher", "intent": "explain_concept", "actions": []},
    {"text": "qual è la definizione formale di limite?", "mode": "INFO", "agent": "math_researcher", "intent": "explain_concept", "actions": []},
    {"text": "what is a logarithm?", "mode": "INFO", "agent": "math_researcher", "intent": "explain_concept", "actions": []},

    # Code Architect - LOOP
    {"text": "scrivi uno script python per quicksort", "mode": "LOOP", "agent": "code_architect", "intent": "edit_code", "actions": ["create_file"]},
    {"text": "correggi il bug in chat_handler.py", "mode": "LOOP", "agent": "code_architect", "intent": "debug_code", "actions": ["read_file", "edit_file"]},
    {"text": "crea un componente React per la tabella", "mode": "LOOP", "agent": "code_architect", "intent": "edit_code", "actions": ["create_file"]},
    {"text": "write a python function to parse json", "mode": "LOOP", "agent": "code_architect", "intent": "edit_code", "actions": ["create_file"]},

    # Code Architect - INFO
    {"text": "come funziona il decoratore @property in python?", "mode": "INFO", "agent": "code_architect", "intent": "explain_concept", "actions": []},
    {"text": "spiega il pattern MVC", "mode": "INFO", "agent": "code_architect", "intent": "explain_concept", "actions": []},

    # Deletion & Removal Anchors
    {"text": "elimina l'argomento frattali", "mode": "LOOP", "agent": "sigma_architect", "intent": "delete_topic", "actions": ["delete_file"]},
    {"text": "cancella l'argomento esponenziali", "mode": "LOOP", "agent": "sigma_architect", "intent": "delete_topic", "actions": ["delete_file"]},
    {"text": "elimina il topic matematica", "mode": "LOOP", "agent": "sigma_architect", "intent": "delete_topic", "actions": ["delete_file"]},
    {"text": "rimuovi l'argomento analisi", "mode": "LOOP", "agent": "sigma_architect", "intent": "delete_topic", "actions": ["delete_file"]},
    {"text": "cancella il file vecchio.md", "mode": "LOOP", "agent": "code_architect", "intent": "delete_file", "actions": ["delete_file"]},
    {"text": "delete topic fractals", "mode": "LOOP", "agent": "sigma_architect", "intent": "delete_topic", "actions": ["delete_file"]},
    {"text": "remove file test.py", "mode": "LOOP", "agent": "code_architect", "intent": "delete_file", "actions": ["delete_file"]},

    # Assistant / Greetings
    {"text": "ciao chi sei?", "mode": "INFO", "agent": "sigma_assistant", "intent": "general_chat", "actions": []},
    {"text": "buongiorno", "mode": "INFO", "agent": "sigma_assistant", "intent": "general_chat", "actions": []},
    {"text": "hello what can you do?", "mode": "INFO", "agent": "sigma_assistant", "intent": "general_chat", "actions": []},

    # ---------------------------------------------------------------------
    # The specialist desks the pattern cascade in prompt_builder can route to.
    # They live here too because the cascade only fires on the literal stems it
    # lists, and a request phrased around the subject rather than its keywords
    # used to fall through to a full model pass. Anchors are the cheap way to
    # cover the paraphrase. Both languages, because the product is used in
    # both, and an anchor set that is Italian-only routes English requests to
    # the front desk by accident.
    # ---------------------------------------------------------------------

    # Visualization & charts
    {"text": "fammi un grafico interattivo con d3", "mode": "LOOP", "agent": "viz_designer", "intent": "build_visualization", "actions": ["create_file"]},
    {"text": "visualizza questi dati in un diagramma", "mode": "LOOP", "agent": "viz_designer", "intent": "build_visualization", "actions": ["create_file"]},
    {"text": "draw a chart of this distribution", "mode": "LOOP", "agent": "viz_designer", "intent": "build_visualization", "actions": ["create_file"]},

    # Testing
    {"text": "scrivi i test pytest per questa funzione", "mode": "LOOP", "agent": "test_engineer", "intent": "write_tests", "actions": ["create_file"]},
    {"text": "quanto è la copertura dei test?", "mode": "INFO", "agent": "test_engineer", "intent": "explain_concept", "actions": []},
    {"text": "add unit tests for this module", "mode": "LOOP", "agent": "test_engineer", "intent": "write_tests", "actions": ["create_file"]},

    # Physics
    {"text": "spiegami l'equazione di Schrodinger", "mode": "INFO", "agent": "physics_professor", "intent": "explain_concept", "actions": []},
    {"text": "come funziona la relatività ristretta?", "mode": "INFO", "agent": "physics_professor", "intent": "explain_concept", "actions": []},
    {"text": "explain thermodynamics entropy", "mode": "INFO", "agent": "physics_professor", "intent": "explain_concept", "actions": []},

    # Chemistry
    {"text": "bilancia questa reazione chimica", "mode": "INFO", "agent": "chemistry_professor", "intent": "explain_concept", "actions": []},
    {"text": "calcola il ph di questa soluzione", "mode": "INFO", "agent": "chemistry_professor", "intent": "explain_concept", "actions": []},
    {"text": "explain covalent bonds in organic molecules", "mode": "INFO", "agent": "chemistry_professor", "intent": "explain_concept", "actions": []},

    # Medicine
    {"text": "cosa significa questo referto medico?", "mode": "INFO", "agent": "medico_divulgatore", "intent": "explain_concept", "actions": []},
    {"text": "quali sono i sintomi e la terapia?", "mode": "INFO", "agent": "medico_divulgatore", "intent": "explain_concept", "actions": []},
    {"text": "explain how this drug works physiologically", "mode": "INFO", "agent": "medico_divulgatore", "intent": "explain_concept", "actions": []},

    # Legal
    {"text": "questa clausola contrattuale è valida?", "mode": "INFO", "agent": "consulente_legale", "intent": "explain_concept", "actions": []},
    {"text": "cosa prevede il gdpr per questi dati?", "mode": "INFO", "agent": "consulente_legale", "intent": "explain_concept", "actions": []},
    {"text": "review this contract for compliance risks", "mode": "INFO", "agent": "consulente_legale", "intent": "explain_concept", "actions": []},

    # Finance
    {"text": "fammi una valutazione dcf di questa azienda", "mode": "LOOP", "agent": "financial_analyst", "intent": "analyze_data", "actions": ["create_file"]},
    {"text": "come leggo questo bilancio?", "mode": "INFO", "agent": "financial_analyst", "intent": "explain_concept", "actions": []},
    {"text": "analyse the portfolio return and risk", "mode": "INFO", "agent": "financial_analyst", "intent": "analyze_data", "actions": []},

    # Data science
    {"text": "addestra un modello di regressione su questo dataset", "mode": "LOOP", "agent": "data_scientist", "intent": "analyze_data", "actions": ["create_file"]},
    {"text": "fai una eda con pandas su questi dati", "mode": "LOOP", "agent": "data_scientist", "intent": "analyze_data", "actions": ["create_file"]},
    {"text": "which clustering algorithm fits this data?", "mode": "INFO", "agent": "data_scientist", "intent": "explain_concept", "actions": []},

    # Languages & translation
    {"text": "traduci questo testo in inglese", "mode": "INFO", "agent": "docente_lingue", "intent": "translate", "actions": []},
    {"text": "correggi la grammatica di questa frase in francese", "mode": "INFO", "agent": "docente_lingue", "intent": "translate", "actions": []},
    {"text": "translate this paragraph into spanish", "mode": "INFO", "agent": "docente_lingue", "intent": "translate", "actions": []},

    # Structural / mechanical engineering
    {"text": "calcola il momento flettente di questa trave", "mode": "INFO", "agent": "ingegnere_strutturista", "intent": "explain_concept", "actions": []},
    {"text": "verifica a taglio della sezione in acciaio", "mode": "INFO", "agent": "ingegnere_strutturista", "intent": "explain_concept", "actions": []},
    {"text": "compute von mises stress for this part", "mode": "INFO", "agent": "ingegnere_strutturista", "intent": "explain_concept", "actions": []},

    # Copywriting & storytelling
    {"text": "scrivi un post instagram per questo lancio", "mode": "LOOP", "agent": "copywriter_storyteller", "intent": "write_copy", "actions": ["create_file"]},
    {"text": "inventa una storia breve su un faro", "mode": "LOOP", "agent": "copywriter_storyteller", "intent": "write_copy", "actions": ["create_file"]},
    {"text": "write ad copy for this landing page", "mode": "LOOP", "agent": "copywriter_storyteller", "intent": "write_copy", "actions": ["create_file"]},

    # Exams & grading
    {"text": "preparami un quiz a risposta multipla su questo argomento", "mode": "LOOP", "agent": "academic_examiner", "intent": "build_exam", "actions": ["create_file"]},
    {"text": "correggi questo compito e dammi un voto", "mode": "INFO", "agent": "academic_examiner", "intent": "grade", "actions": []},
    {"text": "build a grading rubric for this assignment", "mode": "LOOP", "agent": "academic_examiner", "intent": "build_exam", "actions": ["create_file"]},

    # Web research & journalism
    {"text": "cerca sul web le ultime notizie su questo tema", "mode": "INFO", "agent": "online_journalist", "intent": "web_research", "actions": ["search_web"]},
    {"text": "fammi una rassegna stampa aggiornata", "mode": "INFO", "agent": "online_journalist", "intent": "web_research", "actions": ["search_web"]},
    {"text": "fact check this claim online", "mode": "INFO", "agent": "online_journalist", "intent": "web_research", "actions": ["search_web"]},

    # Architecture & roadmap
    {"text": "come è strutturato il progetto e quale roadmap seguiamo?", "mode": "INFO", "agent": "sigma_architect", "intent": "explain_architecture", "actions": []},
    {"text": "progetta l'architettura di questo modulo", "mode": "LOOP", "agent": "sigma_architect", "intent": "explain_architecture", "actions": ["create_file"]},
    {"text": "plan the system architecture for this feature", "mode": "LOOP", "agent": "sigma_architect", "intent": "explain_architecture", "actions": ["create_file"]},
]

_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Fast, lightweight 117MB multilingual model
            _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            log.info("Loaded SentenceTransformer router model successfully")
        except Exception as e:
            log.warning("Could not load SentenceTransformer: %s", e)
            _model = False
    return _model if _model else None

_anchor_embeddings = None

def _get_anchor_embeddings():
    global _anchor_embeddings
    model = _get_model()
    if not model:
        return None, None
    if _anchor_embeddings is None:
        texts = [a["text"] for a in ANCHORS]
        _anchor_embeddings = model.encode(texts, normalize_embeddings=True)
    return _anchor_embeddings, ANCHORS

def _fallback_similarity_classify(message: str) -> dict | None:
    """Fallback n-gram TF-IDF cosine similarity classifier when sentence-transformers is missing."""
    import math
    from collections import Counter

    def get_tokens(text):
        words = [w.lower() for w in text.split() if len(w) > 1]
        bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words)-1)]
        return Counter(words + bigrams)

    q_counts = get_tokens(message)
    q_norm = math.sqrt(sum(v*v for v in q_counts.values()))
    if q_norm == 0:
        return None

    best_score = -1.0
    best_match = None

    for anchor in ANCHORS:
        a_counts = get_tokens(anchor["text"])
        a_norm = math.sqrt(sum(v*v for v in a_counts.values()))
        if a_norm == 0:
            continue
        
        dot = sum(count * a_counts.get(token, 0) for token, count in q_counts.items())
        score = dot / (q_norm * a_norm)
        
        if score > best_score:
            best_score = score
            best_match = anchor

    if best_match and best_score > 0.15:
        log.info("[Router] Fallback TF-IDF Router [score=%.2f]: '%s...' -> mode=%s agent=%s", 
                 best_score, message[:30], best_match["mode"], best_match["agent"])
        return {
            "mode": best_match["mode"],
            "agent": best_match["agent"],
            "intent": best_match["intent"],
            "actions": best_match["actions"],
            "confidence": round(best_score, 3)
        }
    return None

def classify_intent_multilingual(message: str) -> dict | None:
    """Classify message intent using vector similarity against anchor intents."""
    if not message or not message.strip():
        return None

    model = _get_model()
    if not model:
        return _fallback_similarity_classify(message)

    try:
        import numpy as np
    except ImportError:
        return _fallback_similarity_classify(message)

    t0 = time.time()
    embeddings, anchors = _get_anchor_embeddings()
    if embeddings is None:
        return _fallback_similarity_classify(message)

    query_emb = model.encode([message], normalize_embeddings=True)[0]
    similarities = np.dot(embeddings, query_emb)
    best_idx = int(np.argmax(similarities))
    best_score = float(similarities[best_idx])
    
    elapsed_ms = round((time.time() - t0) * 1000, 1)
    match = anchors[best_idx]
    
    # Threshold check: if score is too low, fall back
    if best_score < 0.35:
        log.debug("Multilingual router low confidence (score=%.2f) for: %s", best_score, message[:40])
        return None

    res = {
        "mode": match["mode"],
        "agent": match["agent"],
        "intent": match["intent"],
        "actions": match["actions"],
        "confidence": round(best_score, 3)
    }
    log.info("🧠 Embedding Router [%sms, score=%.2f]: '%s...' -> mode=%s agent=%s", 
             elapsed_ms, best_score, message[:30], res["mode"], res["agent"])
    return res
