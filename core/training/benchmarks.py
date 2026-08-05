# ==============================================================================
# core/training/benchmarks.py — Official Model Benchmark & Evaluation Engine
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Motore di valutazione sui benchmark ufficiali:

1. MMLU (Massive Multitask Language Understanding — 57 materie)
2. MMLU-Pro (scelta multipla ad alto ragionamento, fino a 10 opzioni)
3. GSM8K (Grade School Math 8K)
4. MATH (matematica olimpica / competizioni)
5. HumanEval (completamento ed esecuzione di codice Python)
6. MBPP (Mostly Basic Python Problems)
7. ARC (AI2 Reasoning Challenge — scienze)
8. HellaSwag (buon senso)
9. TruthfulQA (allucinazioni e veridicita')
10. GPQA (domande di livello specialistico)
11. BIG-Bench Hard (BBH — ragionamento multi-step, 27 task)

Modalita' dataset integrale, seed deterministico (42), temperatura 0.0 e
certificato di riproducibilita' SHA-256.

Il giudizio di ogni risposta sta in `core.training.answer_parser`: una risposta
che contiene piu' scelte in conflitto, o nessuna scelta riconoscibile, non e' un
errore del modello ma un esito **da valutare a parte**, e viene contata nella
coda di revisione invece di finire fra i fallimenti.
"""

import datetime
import hashlib
import random
import json
import os
import re
import threading
import time
import uuid

import requests

from core.logger import get_logger
from core.training import benchmark_store as store
from core.training.answer_parser import (
    REVIEW_VERDICTS, VERDICT_AMBIGUOUS, VERDICT_ERROR, VERDICT_FAIL,
    VERDICT_PASS, VERDICT_UNPARSABLE,
    extract_chosen_letter, grade_answer, grade_code_result,
)

log = get_logger(__name__)

BENCHMARKS_FILE = os.path.join("training_lab", "official_benchmark_results.json")
BENCHMARK_CACHE_DIR = os.path.join("training_lab", "benchmark_cache")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

_benchmark_lock = threading.RLock()
_cancel_requested: set[str] = set()   # job in attesa di annullamento
_pause_requested: set[str] = set()    # job in attesa di pausa
_active_threads: dict[str, threading.Thread] = {}  # job_id -> thread worker

#: Ogni quanti quesiti versare il buffer degli esiti su disco.
_FLUSH_EVERY = 25
#: Intervallo minimo fra due scritture dell'indice job durante un run.
_PROGRESS_INTERVAL_SEC = 1.5

# `extract_chosen_letter` resta importato per i chiamanti storici e per i test.
__all__ = [
    "get_available_models_for_benchmark", "get_suite_info", "get_benchmark_items",
    "download_suite", "start_benchmark_run", "list_benchmark_jobs", "get_job_detail",
    "pause_benchmark_job", "resume_benchmark_job", "cancel_benchmark_job",
    "delete_benchmark_job", "extract_chosen_letter", "OFFICIAL_BENCHMARKS_INFO",
    "audit_benchmark_job",
]


# ==============================================================================
# INDICE DEI JOB (solo metadati e metriche: il dettaglio sta in benchmark_store)
# ==============================================================================

def _ensure_dir():
    os.makedirs("training_lab", exist_ok=True)
    if not os.path.exists(BENCHMARKS_FILE):
        with open(BENCHMARKS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def _load_benchmarks() -> list[dict]:
    _ensure_dir()
    try:
        with open(BENCHMARKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    changed = False
    for job in data:
        # I run salvati col vecchio schema portano il dettaglio inline: va
        # spostato nello store, altrimenti ogni polling rispedisce megabyte.
        if store.migrate_inline_results(job):
            changed = True
        if job.get("status") in ("running", "executing"):
            jid = job.get("id", "")
            thread = _active_threads.get(jid)
            if thread is None or not thread.is_alive():
                job["status"] = "interrupted"
                job["updated_at"] = datetime.datetime.now().isoformat()
                changed = True
                log.warning("Job benchmark %s risultava in corso senza worker: marcato 'interrupted'.", jid)
    if changed:
        _save_benchmarks(data)
    return data


def _save_benchmarks(benchmarks: list[dict]):
    _ensure_dir()
    with _benchmark_lock:
        tmp = BENCHMARKS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(benchmarks, f, indent=2, ensure_ascii=False)
        os.replace(tmp, BENCHMARKS_FILE)


def _update_job_state(job_id: str, updates: dict):
    """Fonde `updates` nel job indicato, unendo metriche e riproducibilita'."""
    with _benchmark_lock:
        benchmarks = _load_benchmarks()
        for job in benchmarks:
            if job.get("id") == job_id:
                nested = {k: updates[k] for k in ("metrics", "reproducibility") if k in updates}
                job.update({k: v for k, v in updates.items() if k not in nested})
                for key, value in nested.items():
                    if isinstance(value, dict):
                        job.setdefault(key, {}).update(value)
                    else:
                        job[key] = value
                break
        _save_benchmarks(benchmarks)


# ==============================================================================
# MODELLI DISPONIBILI
# ==============================================================================

#: Famiglie che non generano testo: valutarle produce solo errori HTTP.
_NON_GENERATIVE_HINTS = ("embed", "embedding", "bge-", "gte-", "e5-", "reranker", "rerank",
                         "nomic-embed", "mxbai-embed", "all-minilm")


def _is_generative(name: str, details: dict) -> bool:
    lowered = (name or "").lower()
    if any(hint in lowered for hint in _NON_GENERATIVE_HINTS):
        return False
    return (details or {}).get("family", "").lower() not in ("bert", "nomic-bert")


def _param_size(details: dict) -> str:
    return (details or {}).get("parameter_size", "") or ""


def get_available_models_for_benchmark() -> list[dict]:
    """Modelli Ollama installati, pronti per la valutazione.

    La lista alimenta la select della UI, quindi arriva già deduplicata, senza i
    modelli di embedding (che non rispondono a `/api/generate`) e ordinata per
    dimensione: i piccoli in cima, dove serve per i test rapidi in parallelo.
    """
    models: list[dict] = []
    reachable = False
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        reachable = res.status_code == 200
        if reachable:
            seen: set[str] = set()
            for m in res.json().get("models", []):
                name = m.get("name", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                details = m.get("details", {}) or {}
                if not _is_generative(name, details):
                    continue
                size_gb = round(m.get("size", 0) / (1024 ** 3), 2)
                models.append({
                    "id": name,
                    "name": name,
                    "provider": "Ollama",
                    "size_gb": size_gb,
                    "family": details.get("family", "") or "",
                    "parameter_size": _param_size(details),
                    "quantization": details.get("quantization_level", "") or "",
                    "modified_at": m.get("modified_at", ""),
                    "details": details,
                    "is_active": True,
                })
    except Exception as err:
        log.debug("Elenco modelli Ollama non recuperabile: %s", err)

    models.sort(key=lambda m: (m.get("size_gb") or 0, m.get("name", "")))
    return models


def get_benchmark_models_payload() -> dict:
    """Modelli + stato del servizio, per distinguere "nessun modello" da "Ollama giù"."""
    models = get_available_models_for_benchmark()
    ollama_up = True
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
    except Exception:
        ollama_up = False
    return {
        "success": True,
        "models": models,
        "count": len(models),
        "ollama_available": ollama_up,
        "ollama_url": OLLAMA_URL,
    }


# ==============================================================================
# DATASET UFFICIALI
# ==============================================================================

OFFICIAL_BENCHMARKS_INFO = {
    "mmlu": {
        "name": "MMLU",
        "description": "Massive Multitask Language Understanding (57 materie: medicina, legge, fisica, matematica, economia...)",
        "type": "multiple_choice",
        "dataset": "cais/mmlu",
    },
    "mmlu_pro": {
        "name": "MMLU-Pro",
        "description": "Versione avanzata ad alto ragionamento con 10 opzioni e quesiti complessi",
        "type": "multiple_choice",
        "dataset": "TIGER-Lab/MMLU-Pro",
    },
    "gsm8k": {
        "name": "GSM8K",
        "description": "Grade School Math (problemi aritmetici con passaggi logici)",
        "type": "math_reasoning",
        "dataset": "openai/gsm8k",
    },
    "math": {
        "name": "MATH",
        "description": "Problemi matematici olimpici avanzati (algebra, calcolo, teoria dei numeri)",
        "type": "advanced_math",
        "dataset": "qwedsacf/competition_math",
    },
    "humaneval": {
        "name": "HumanEval",
        "description": "Completamento ed esecuzione di codice Python (pass@1 su test unitari reali)",
        "type": "code_execution",
        "dataset": "openai/openai_humaneval",
    },
    "mbpp": {
        "name": "MBPP",
        "description": "Mostly Basic Python Problems (sfide Python di base, verificate per esecuzione)",
        "type": "code_execution",
        "dataset": "google-research-datasets/mbpp",
    },
    "arc": {
        "name": "ARC",
        "description": "AI2 Reasoning Challenge (quesiti scientifici di ragionamento)",
        "type": "multiple_choice",
        "dataset": "allenai/ai2_arc",
    },
    "hellaswag": {
        "name": "HellaSwag",
        "description": "Valutazione del buon senso e continuazione naturale degli eventi",
        "type": "multiple_choice",
        "dataset": "Rowan/hellaswag",
    },
    "truthfulqa": {
        "name": "TruthfulQA",
        "description": "Rilevamento delle allucinazioni e veridicita' delle risposte",
        "type": "multiple_choice",
        "dataset": "truthfulqa/truthful_qa",
    },
    "gpqa": {
        "name": "GPQA",
        "description": "Graduate-Level Google-Proof Q&A (domande di livello specialistico universitario)",
        "type": "multiple_choice",
        "dataset": "ankner/gpqa",
    },
    "bbh": {
        "name": "BIG-Bench Hard",
        "description": "27 task complessi di ragionamento multi-step e logica simbolica",
        "type": "multi_step_reasoning",
        "dataset": "lukaemon/bbh",
    },
}

#: Suite verificate eseguendo i test ufficiali invece di confrontare testo.
CODE_SUITES = ("humaneval", "mbpp")

#: I 27 task di BIG-Bench Hard. Prima ne veniva scaricato solo il primo, quindi
#: "BBH" misurava soltanto le espressioni booleane.
BBH_TASKS = (
    "boolean_expressions", "causal_judgement", "date_understanding", "disambiguation_qa",
    "dyck_languages", "formal_fallacies", "geometric_shapes", "hyperbaton",
    "logical_deduction_five_objects", "logical_deduction_seven_objects",
    "logical_deduction_three_objects", "movie_recommendation", "multistep_arithmetic_two",
    "navigate", "object_counting", "penguins_in_a_table", "reasoning_about_colored_objects",
    "ruin_names", "salient_translation_error_detection", "snarks", "sports_understanding",
    "temporal_sequences", "tracking_shuffled_objects_five_objects",
    "tracking_shuffled_objects_seven_objects", "tracking_shuffled_objects_three_objects",
    "web_of_lies", "word_sorting",
)


def _get_hf_token() -> str:
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f).get("hf_token", "")
    except Exception:
        return ""


def _get_cache_path(suite_id: str) -> str:
    return os.path.join(BENCHMARK_CACHE_DIR, f"{suite_id}.json")


def _is_cached(suite_id: str) -> bool:
    return os.path.exists(_get_cache_path(suite_id))


def _load_cached(suite_id: str) -> list[dict]:
    path = _get_cache_path(suite_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as err:
        log.warning("Cache %s illeggibile: %s", suite_id, err)
        return []


def _save_cache(suite_id: str, items: list[dict]):
    os.makedirs(BENCHMARK_CACHE_DIR, exist_ok=True)
    path = _get_cache_path(suite_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _mc_item(suite_id: str, suite_name: str, index: int, category: str, prompt: str,
             labels: list[str], texts: list[str], correct_label: str) -> dict:
    """Costruisce un item a scelta multipla con opzioni etichettate."""
    correct_idx = labels.index(correct_label) if correct_label in labels else -1
    correct_text = texts[correct_idx] if 0 <= correct_idx < len(texts) else ""
    return {
        "id": f"{suite_id}_{index}",
        "suite": suite_id,
        "suite_name": suite_name,
        "category": category,
        "prompt": prompt,
        "options": [f"{lbl}) {txt}" for lbl, txt in zip(labels, texts)],
        "correct_choice": correct_label,
        "correct_answer": f"{correct_label}) {correct_text}",
        "expected_keywords": [correct_text] if correct_text else [],
    }


def _letters(count: int) -> list[str]:
    return [chr(65 + i) for i in range(count)]


def download_suite(suite_id: str) -> dict:
    """Scarica e mette in cache i quesiti ufficiali di una suite (o di tutte)."""
    if suite_id == "all":
        totals, errors = 0, {}
        for sid in OFFICIAL_BENCHMARKS_INFO:
            result = download_suite(sid)
            if result.get("success"):
                totals += result.get("count", 0)
            else:
                errors[sid] = result.get("error", "errore sconosciuto")
        return {
            "success": not errors,
            "count": totals,
            "suite": "all",
            "errors": errors,
            "error": "; ".join(f"{k}: {v}" for k, v in errors.items()) if errors else "",
        }

    if suite_id not in OFFICIAL_BENCHMARKS_INFO:
        return {"success": False, "error": f"Suite sconosciuta: {suite_id}"}

    try:
        from datasets import load_dataset
    except ImportError:
        return {"success": False, "error": "Pacchetto 'datasets' non installato: pip install datasets"}

    token = _get_hf_token() or None
    out: list[dict] = []

    try:
        if suite_id == "mmlu":
            for i, item in enumerate(load_dataset("cais/mmlu", "all", split="test", token=token)):
                choices = item.get("choices", []) or []
                labels = _letters(len(choices))
                answer_idx = item.get("answer", -1)
                correct = labels[answer_idx] if isinstance(answer_idx, int) and 0 <= answer_idx < len(labels) else ""
                out.append(_mc_item(suite_id, "MMLU", i, item.get("subject", ""),
                                    item.get("question", ""), labels, choices, correct))

        elif suite_id == "mmlu_pro":
            for i, item in enumerate(load_dataset("TIGER-Lab/MMLU-Pro", split="test", token=token)):
                choices = item.get("options", []) or []
                labels = _letters(len(choices))
                out.append(_mc_item(suite_id, "MMLU-Pro", i, item.get("category", ""),
                                    item.get("question", ""), labels, choices,
                                    (item.get("answer", "") or "").strip().upper()))

        elif suite_id == "gsm8k":
            for i, item in enumerate(load_dataset("openai/gsm8k", "main", split="test", token=token)):
                answer_full = item.get("answer", "")
                match = re.search(r"####\s*(.+)", answer_full)
                out.append({
                    "id": f"{suite_id}_{i}", "suite": suite_id, "suite_name": "GSM8K",
                    "category": "Math", "prompt": item.get("question", ""), "options": [],
                    "correct_choice": match.group(1).strip() if match else "",
                    "correct_answer": answer_full,
                    "expected_keywords": [match.group(1).strip()] if match else [],
                })

        elif suite_id == "math":
            for i, item in enumerate(load_dataset("qwedsacf/competition_math", split="train", token=token)):
                solution = item.get("solution", "")
                match = re.search(r"\\boxed\{(.+?)\}", solution)
                out.append({
                    "id": f"{suite_id}_{i}", "suite": suite_id, "suite_name": "MATH",
                    "category": item.get("type", ""), "prompt": item.get("problem", ""), "options": [],
                    "correct_choice": match.group(1).strip() if match else "",
                    "correct_answer": solution,
                    "expected_keywords": [match.group(1).strip()] if match else [],
                })

        elif suite_id == "humaneval":
            for i, item in enumerate(load_dataset("openai/openai_humaneval", split="test", token=token)):
                solution = item.get("canonical_solution", "")
                out.append({
                    "id": f"{suite_id}_{i}", "suite": suite_id, "suite_name": "HumanEval",
                    "category": "Code", "prompt": item.get("prompt", ""), "options": [],
                    "correct_choice": solution, "correct_answer": solution,
                    "expected_keywords": [],
                    # Senza `test` ed `entry_point` non esiste pass@1: la suite
                    # si misura eseguendo queste asserzioni, non confrontando testo.
                    "verification": {
                        "test": item.get("test", ""),
                        "entry_point": item.get("entry_point", ""),
                    },
                })

        elif suite_id == "mbpp":
            for i, item in enumerate(load_dataset("google-research-datasets/mbpp", split="test", token=token)):
                code = item.get("code", "")
                out.append({
                    "id": f"{suite_id}_{i}", "suite": suite_id, "suite_name": "MBPP",
                    "category": "Code", "prompt": item.get("text", ""), "options": [],
                    "correct_choice": code, "correct_answer": code, "expected_keywords": [],
                    "verification": {
                        "test_list": list(item.get("test_list", []) or []),
                        "test_setup_code": item.get("test_setup_code", "") or "",
                    },
                })

        elif suite_id == "arc":
            for i, item in enumerate(load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test", token=token)):
                choices = item.get("choices", {}) or {}
                out.append(_mc_item(suite_id, "ARC", i, "Science", item.get("question", ""),
                                    list(choices.get("label", [])), list(choices.get("text", [])),
                                    item.get("answerKey", "")))

        elif suite_id == "hellaswag":
            for i, item in enumerate(load_dataset("Rowan/hellaswag", split="validation", token=token)):
                endings = item.get("endings", []) or []
                labels = _letters(len(endings))
                label = str(item.get("label", ""))
                correct = labels[int(label)] if label.isdigit() and int(label) < len(labels) else ""
                out.append(_mc_item(suite_id, "HellaSwag", i, "Reasoning", item.get("ctx", ""),
                                    labels, endings, correct))

        elif suite_id == "truthfulqa":
            ds = load_dataset("truthfulqa/truthful_qa", "multiple_choice", split="validation", token=token)
            for i, item in enumerate(ds):
                targets = item.get("mc1_targets", {}) or {}
                choices = list(targets.get("choices", []))
                marks = list(targets.get("labels", []))
                labels = _letters(len(choices))
                idx = marks.index(1) if 1 in marks else -1
                out.append(_mc_item(suite_id, "TruthfulQA", i, "Truthfulness", item.get("question", ""),
                                    labels, choices, labels[idx] if 0 <= idx < len(labels) else ""))

        elif suite_id == "gpqa":
            import random
            for i, item in enumerate(load_dataset("ankner/gpqa", split="train", token=token)):
                question = item.get("Question") or item.get("question", "")
                correct_answer = item.get("Correct Answer") or item.get("answer", "")
                wrong = [item.get(f"Incorrect Answer {j}", "") for j in (1, 2, 3)
                         if item.get(f"Incorrect Answer {j}")]
                if not wrong:
                    wrong = list(item.get("incorrect_answers", []) or [])
                options = [correct_answer] + wrong
                # Mescolare col seed dell'indice evita che la risposta giusta
                # sia sempre in prima posizione, restando riproducibile.
                random.Random(i).shuffle(options)
                labels = _letters(len(options))
                idx = options.index(correct_answer) if correct_answer in options else 0
                out.append(_mc_item(suite_id, "GPQA", i, "Expert QA", question, labels, options,
                                    labels[idx] if idx < len(labels) else ""))

        elif suite_id == "bbh":
            loaded_tasks, failed_tasks = 0, []
            for task in BBH_TASKS:
                try:
                    ds = load_dataset("lukaemon/bbh", task, split="test", token=token)
                except Exception as err:
                    failed_tasks.append(task)
                    log.debug("Task BBH %s non caricato: %s", task, err)
                    continue
                loaded_tasks += 1
                for i, item in enumerate(ds):
                    target = (item.get("target", "") or "").strip()
                    out.append({
                        "id": f"{suite_id}_{task}_{i}", "suite": suite_id,
                        "suite_name": "BIG-Bench Hard", "category": task.replace("_", " ").title(),
                        "prompt": item.get("input", ""), "options": [],
                        "correct_choice": target, "correct_answer": target,
                        "expected_keywords": [target] if target else [],
                    })
            if not loaded_tasks:
                return {"success": False, "error": "Nessun task BBH scaricabile"}
            if failed_tasks:
                log.warning("Task BBH saltati: %s", ", ".join(failed_tasks))

        if not out:
            return {"success": False, "error": f"Nessun quesito ottenuto per {suite_id}"}

        _save_cache(suite_id, out)
        return {"success": True, "count": len(out), "suite": suite_id}

    except Exception as err:
        log.error("Errore nel download di %s: %s", suite_id, err)
        return {"success": False, "error": str(err)}


def get_suite_info(suite_id: str) -> dict:
    """Stato di una suite: presenza in cache, numero di quesiti, dettagli."""
    if suite_id == "all":
        suites, total, all_cached = {}, 0, True
        for sid in OFFICIAL_BENCHMARKS_INFO:
            info = get_suite_info(sid)
            suites[sid] = info
            total += info.get("count", 0)
            all_cached = all_cached and info.get("cached", False)
        return {
            "success": True, "suite": "all", "cached": all_cached, "count": total,
            "name": "Tutti i Benchmark Ufficiali", "suites": suites,
            "cached_suites": sum(1 for s in suites.values() if s.get("cached")),
            "total_suites": len(suites),
        }

    meta = OFFICIAL_BENCHMARKS_INFO.get(suite_id, {})
    cached = _is_cached(suite_id)
    items = _load_cached(suite_id) if cached else []
    path = _get_cache_path(suite_id)

    categories = sorted({(i.get("category") or "") for i in items[:5000] if i.get("category")})

    # Una cache di suite di codice scaricata prima che salvassimo i test
    # ufficiali non permette il pass@1: va segnalato, non subito.
    needs_refresh = bool(
        suite_id in CODE_SUITES and items and not (items[0].get("verification") or {})
    )
    # Una cache BBH con pochissime categorie viene da quando scaricavamo un solo
    # task su 27: il punteggio direbbe "BBH" misurando un sottoinsieme minimo.
    if suite_id == "bbh" and items and len(categories) < 5:
        needs_refresh = True
    return {
        "success": True,
        "suite": suite_id,
        "cached": cached,
        "count": len(items),
        "name": meta.get("name", suite_id),
        "description": meta.get("description", ""),
        "type": meta.get("type", ""),
        "dataset": meta.get("dataset", ""),
        "categories": categories[:60],
        "size_mb": round(os.path.getsize(path) / (1024 ** 2), 2) if cached else 0,
        "needs_refresh": needs_refresh,
    }


#: Frazione del campione riservata alla **verifica**. Un ciclo automatico che
#: decide guardando gli stessi quesiti su cui poi riporta il punteggio non
#: migliora il modello: scala quella classifica. Il set di selezione guida le
#: decisioni, il set di verifica non viene mai guardato durante il ciclo ed e'
#: l'unico numero che si comunica.
HOLDOUT_FRACTION = 0.5


def split_selection_holdout(items: list[dict], fraction: float = HOLDOUT_FRACTION
                            ) -> tuple[list[dict], list[dict]]:
    """Divide i quesiti in set di selezione e set di verifica.

    La divisione e' deterministica e stratificata per suite: due modelli
    valutati sullo stesso campione vedono la stessa partizione, altrimenti il
    confronto appaiato non sarebbe piu' appaiato.
    """
    rng = random.Random(1337)
    by_suite: dict[str, list[dict]] = {}
    for item in items:
        by_suite.setdefault(item.get("suite", "?"), []).append(item)

    selection, holdout = [], []
    for suite in sorted(by_suite):
        pool = sorted(by_suite[suite], key=lambda i: str(i.get("id", "")))
        rng.shuffle(pool)
        cut = int(len(pool) * (1 - fraction))
        selection.extend(pool[:cut])
        holdout.extend(pool[cut:])
    return selection, holdout


#: Quesiti minimi che ogni suite ottiene in un campione, quando ce ne stanno.
#: Sotto questa soglia una suite non dice niente di utile; a zero, sparisce.
_MIN_PER_SUITE = 5


def _stratified_sample(by_suite: dict[str, list[dict]], total: int) -> list[dict]:
    """A sample where every suite is represented, not just the big ones.

    Un campione casuale sull'unione delle suite le pesa per dimensione: MMLU ha
    14.042 quesiti e GSM8K 1.319, quindi su 100 estrazioni GSM8K ne prende due
    — e capita che ne prenda zero. E' successo davvero: un modello messo a punto
    proprio su GSM8K e' stato confrontato con la sua base su un campione che di
    GSM8K non conteneva un solo quesito.

    Qui ogni suite riceve prima una quota minima, e il resto viene diviso in
    proporzione. Il seed e' fisso: due modelli valutati con lo stesso `total`
    vedono gli stessi quesiti, che e' cio' che rende il confronto appaiato.
    """
    rng = random.Random(42)
    suites = {sid: found for sid, found in by_suite.items() if found}
    if not suites:
        return []

    floor = min(_MIN_PER_SUITE, max(1, total // len(suites)))
    quota = {sid: min(floor, len(found)) for sid, found in suites.items()}

    remaining = total - sum(quota.values())
    if remaining > 0:
        spare = {sid: len(found) - quota[sid] for sid, found in suites.items()}
        pool = sum(spare.values())
        if pool > 0:
            for sid, extra in spare.items():
                quota[sid] += min(extra, int(remaining * extra / pool))
    # Gli arrotondamenti lasciano qualche posto libero: vanno alle suite che
    # hanno ancora quesiti da offrire, in ordine di grandezza.
    leftover = total - sum(quota.values())
    for sid in sorted(suites, key=lambda s: -len(suites[s])):
        if leftover <= 0:
            break
        room = len(suites[sid]) - quota[sid]
        take = min(room, leftover)
        quota[sid] += take
        leftover -= take

    out: list[dict] = []
    for sid, found in suites.items():
        take = min(quota[sid], len(found))
        if take:
            out.extend(rng.sample(found, take))
    return out


def get_benchmark_items(suite_id: str, mode: str = "full", num_samples: int = 0) -> list[dict]:
    """Quesiti da valutare; scarica la suite se manca dalla cache."""
    if suite_id == "all":
        by_suite: dict[str, list[dict]] = {}
        for sid in OFFICIAL_BENCHMARKS_INFO:
            found = get_benchmark_items(sid, mode="full", num_samples=0)
            if found:
                by_suite[sid] = found
        items = [item for found in by_suite.values() for item in found]
        if mode == "sample" and 0 < num_samples < len(items):
            items = _stratified_sample(by_suite, num_samples)
        return items

    if not _is_cached(suite_id):
        result = download_suite(suite_id)
        if not result.get("success"):
            log.error("Download di %s non riuscito: %s", suite_id, result.get("error"))
            return []

    items = _load_cached(suite_id)
    if mode == "sample" and 0 < num_samples < len(items):
        items = random.Random(42).sample(items, num_samples)
    return items


# ==============================================================================
# ESECUZIONE
# ==============================================================================

def _prepare_benchmark_payload(item: dict, model_name: str) -> dict:
    """Prompt e parametri di generazione per un quesito.

    Il tetto di token e' scelto per tipo di suite: sulla scelta multipla una
    finestra corta e' parte della misura, perche' lascia spazio a una sola
    risposta — con 100 token i modelli piccoli enumerano piu' opzioni e l'esito
    diventa ambiguo invece di essere una scelta.
    """
    suite = item.get("suite", "")
    options = item.get("options", [])
    base_options = {"temperature": 0.0, "seed": 42, "top_p": 1.0}

    if options:
        prompt = f"Question: {item['prompt']}\n\n" + "\n".join(options)
        prompt += "\n\nAnswer with ONLY the letter of the correct option.\nAnswer:"
        return {
            "model": model_name,
            "system": ("You are a multiple-choice benchmark engine. Reply with exactly one "
                       "option letter and nothing else. No explanation, no punctuation, no markdown."),
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {**base_options, "num_predict": 24, "stop": ["\n\n", "Question:", "Explanation"]},
        }

    if suite in ("gsm8k", "math"):
        # Il ragionamento va PRIMA della risposta. Chiedere il risultato sulla
        # prima riga costringe il modello a sparare un numero senza aver fatto
        # i conti e poi a giustificarlo: si misura quanto indovina a freddo,
        # non quanto sa ragionare — ed e' esattamente cio' che GSM8K esiste per
        # misurare. E' anche la causa delle risposte doppie, una in apertura e
        # una vera in chiusura.
        prompt = (f"Question: {item['prompt']}\n\n"
                  "Solve the problem step by step. When you are done, write the final "
                  "answer on its own last line, inside \\boxed{...} (e.g. \\boxed{49}). "
                  "Give exactly one final answer and stop there.")
        return {
            "model": model_name,
            "system": ("You are an expert mathematical problem solver. Reason step by step, "
                       "then end your reply with the final result inside \\boxed{...} on the "
                       "last line. Give exactly one final answer and write nothing after it."),
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {**base_options, "num_predict": 1024},
        }

    if suite in CODE_SUITES:
        prompt = (f"Task: {item['prompt']}\n\n"
                  "Write a complete, self-contained Python solution inside a single ```python "
                  "code block. Include the full function definition and any imports it needs.")
        return {
            "model": model_name,
            "system": "You are an expert Python engineer. Output only working code in one code block.",
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {**base_options, "num_predict": 768},
        }

    prompt = f"Task: {item['prompt']}\n\nGive only the final answer, with no explanation.\nAnswer:"
    return {
        "model": model_name,
        "system": ("You are a reasoning benchmark engine. Reply with the final answer only, "
                   "in the shortest possible form."),
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {**base_options, "num_predict": 96, "stop": ["\n\n"]},
    }


# Versione del protocollo di prompting. Va nell'impronta di riproducibilita':
# due run con prompt diversi non sono confrontabili, e senza questo marcatore
# nulla nel certificato lo direbbe.
#   1 — risposta sulla prima riga, poi il ragionamento (ritirato: misurava
#       quanto il modello indovina prima di fare i conti)
#   2 — ragionamento passo passo, risposta finale in chiusura
PROMPT_PROTOCOL = 2

GRADER_VERSION = "sigma.answer_parser/3"


def _request_timeout(suite: str) -> int:
    """Timeout HTTP per suite: matematica e codice generano molto piu' testo."""
    if suite in ("gsm8k", "math"):
        return 300
    if suite in CODE_SUITES:
        return 240
    return 90


def _grade(item: dict, output_text: str) -> dict:
    """Verdetto di un quesito, con esecuzione dei test per le suite di codice."""
    if (item.get("suite") or "").lower() in CODE_SUITES:
        from core.training.code_exec import run_code_item
        return grade_code_result(run_code_item(item, output_text))
    return grade_answer(item, output_text)


def _empty_metrics() -> dict:
    return {
        "overall_score": 0, "accuracy_pct": 0, "decided_accuracy_pct": 0,
        "tokens_per_sec": 0, "avg_latency_ms": 0, "total_tokens": 0,
        "tests_passed": 0, "tests_failed": 0, "tests_total": 0,
        "tests_ambiguous": 0, "tests_unparsable": 0, "tests_error": 0,
        "tests_review": 0, "review_pct": 0,
    }


def _compute_metrics(counts: dict, total_done: int, planned_total: int,
                     total_tokens: int, total_duration: float, latency_sum_ms: int) -> dict:
    """Aggrega i contatori in metriche, separando lo score dal giudizio sospeso.

    Due accuratezze, perche' misurano cose diverse:
    `overall_score` e' lo score ufficiale (giuste su totale, gli item da rivedere
    pesano come non superati), `decided_accuracy_pct` guarda solo i quesiti in cui
    il modello ha effettivamente scelto.
    """
    passed = counts.get(VERDICT_PASS, 0)
    failed = counts.get(VERDICT_FAIL, 0)
    review = sum(counts.get(v, 0) for v in REVIEW_VERDICTS)
    decided = passed + failed
    return {
        "overall_score": round((passed / planned_total) * 100, 2) if planned_total else 0,
        "accuracy_pct": round((passed / planned_total) * 100, 2) if planned_total else 0,
        "decided_accuracy_pct": round((passed / decided) * 100, 2) if decided else 0,
        "tokens_per_sec": round(total_tokens / total_duration, 2) if total_duration > 0 else 0,
        "avg_latency_ms": int(latency_sum_ms / total_done) if total_done else 0,
        "total_tokens": total_tokens,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_total": total_done,
        "tests_ambiguous": counts.get(VERDICT_AMBIGUOUS, 0),
        "tests_unparsable": counts.get(VERDICT_UNPARSABLE, 0),
        "tests_error": counts.get(VERDICT_ERROR, 0),
        "tests_review": review,
        "review_pct": round((review / total_done) * 100, 2) if total_done else 0,
    }


def start_benchmark_run(model_name: str, suite_id: str = "all", num_samples: int = 0,
                        mode: str = "full", concurrency=4) -> dict:
    """Avvia un run di valutazione su worker paralleli.

    `concurrency` accetta anche "auto": in quel caso il numero di richieste
    contemporanee lo decide `core.training.capacity`, dall'ultima misura del
    modello o, se manca, dalla stima sulla VRAM libera.
    """
    from core.training.capacity import resolve_concurrency

    job_id = f"bm_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    now = datetime.datetime.now().isoformat()
    suite_meta = OFFICIAL_BENCHMARKS_INFO.get(suite_id, {})
    suite_name = suite_meta.get("name") or ("Tutti i Benchmark Ufficiali" if suite_id == "all" else suite_id.upper())
    is_full = mode == "full" or num_samples == 0
    workers, concurrency_source = resolve_concurrency(model_name, concurrency)

    job = {
        "id": job_id,
        "model": model_name,
        "suite": suite_id,
        "suite_name": suite_name,
        "execution_mode": mode,
        "concurrency": workers,
        "concurrency_source": concurrency_source,
        "status": "preparing",
        "progress": 0,
        "created_at": now,
        "updated_at": now,
        "reproducibility": {
            "temperature": 0.0,
            "seed": 42,
            "reproducible_hash": "",
            "mode": "FULL_DATASET_100%_CLEAN" if is_full else "AUDIT_SAMPLE",
        },
        "metrics": _empty_metrics(),
    }

    with _benchmark_lock:
        benchmarks = _load_benchmarks()
        benchmarks.insert(0, job)
        _save_benchmarks(benchmarks)

    thread = threading.Thread(
        target=_worker_run_official_benchmark,
        args=(job_id, model_name, suite_id, mode, num_samples, workers),
        daemon=True,
    )
    _active_threads[job_id] = thread
    thread.start()
    return job


def _worker_run_official_benchmark(job_id: str, model_name: str, suite_id: str,
                                   mode: str, num_samples: int, concurrency: int):
    """Esegue i quesiti su un pool di worker, versando gli esiti nello store."""
    import concurrent.futures

    from core.training.endpoints import EndpointPool

    # Con piu' servitori Ollama (uno per GPU) le richieste si alternano fra loro:
    # e' cio' che mette al lavoro tutte le schede invece della sola prima.
    pool_endpoints = EndpointPool()

    # Il download della suite puo' durare minuti: il job resta 'preparing' cosi'
    # la UI non mostra 0% "in corso" mentre in realta' sta scaricando.
    items = get_benchmark_items(suite_id, mode, num_samples)
    total = len(items)
    if total == 0:
        _update_job_state(job_id, {
            "status": "failed", "progress": 100,
            "error": f"Nessun quesito disponibile per la suite '{suite_id}'",
            "updated_at": datetime.datetime.now().isoformat(),
        })
        _active_threads.pop(job_id, None)
        return

    _update_job_state(job_id, {
        "status": "running", "progress": 0, "items_planned": total,
        "endpoints": list(pool_endpoints.urls),
        "updated_at": datetime.datetime.now().isoformat(),
    })

    counts: dict[str, int] = {}
    buffer: list[dict] = []
    completed = tokens_total = latency_sum = 0
    duration_total = 0.0
    last_progress = time.time()
    lock = threading.Lock()

    def flush(force: bool = False):
        """Versa il buffer su disco e aggiorna metriche/progresso, con freno."""
        nonlocal buffer, last_progress
        with lock:
            if not force and len(buffer) < _FLUSH_EVERY:
                return
            pending, buffer = buffer, []
            snapshot = (dict(counts), completed, tokens_total, duration_total, latency_sum)
        if pending:
            store.append_results(job_id, pending)
        now = time.time()
        if force or now - last_progress >= _PROGRESS_INTERVAL_SEC:
            last_progress = now
            done_counts, done, toks, dur, lat = snapshot
            _update_job_state(job_id, {
                "progress": min(100, int((done / total) * 100)),
                "updated_at": datetime.datetime.now().isoformat(),
                "metrics": _compute_metrics(done_counts, done, total, toks, dur, lat),
            })

    def process(index: int, item: dict):
        nonlocal completed, tokens_total, latency_sum, duration_total

        if job_id in _cancel_requested:
            return
        while job_id in _pause_requested:
            if job_id in _cancel_requested:
                return
            time.sleep(0.5)

        started = time.time()
        output_text, tok_per_sec, tokens = "", 0, 0
        transport_error = ""
        # `lease` tiene conto di quante richieste ha in volo ogni servitore e
        # sceglie il piu' scarico: con schede di velocita' diversa e' cio' che
        # impedisce alla piu' lenta di diventare il freno di tutte.
        # `lease` conta quante richieste ha in volo ogni servitore e sceglie il
        # piu' scarico: con schede di velocita' diversa e' cio' che impedisce
        # alla piu' lenta di diventare il freno di tutte. Il rilascio avviene
        # anche se la richiesta esplode, altrimenti quell'endpoint resterebbe
        # "occupato" per sempre e smetterebbe di ricevere lavoro.
        with pool_endpoints.lease() as endpoint:
            try:
                payload = _prepare_benchmark_payload(item, model_name)
                resp = requests.post(f"{endpoint}/api/generate", json=payload,
                                     timeout=_request_timeout(item.get("suite", "")))
                elapsed = time.time() - started
                if resp.status_code == 200:
                    data = resp.json()
                    output_text = (data.get("response") or "").strip()
                    if not output_text:
                        output_text = (data.get("thinking") or "").strip()
                    eval_count = data.get("eval_count") or len(output_text.split())
                    eval_ns = data.get("eval_duration") or 0
                    tok_per_sec = (round(eval_count / (eval_ns / 1e9), 2) if eval_ns > 0
                                   else round(eval_count / max(elapsed, 0.01), 2))
                    tokens = eval_count
                else:
                    transport_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as err:
                elapsed = time.time() - started
                transport_error = str(err)[:200]

        if transport_error:
            # Nessuna risposta dal modello: l'item va segnato come errore di
            # esecuzione. La versione precedente scriveva qui la risposta
            # corretta come se il modello l'avesse prodotta, e quel testo veniva
            # poi valutato — gonfiando il punteggio con la verita' di base.
            graded = {
                "verdict": VERDICT_ERROR, "passed": False, "needs_review": True,
                "parsed": {"status": "unparsable", "value": None, "tier": "",
                           "confidence": "none", "candidates": [], "rejected": [],
                           "reason": f"Modello non raggiungibile: {transport_error}"},
            }
            output_text = ""
        else:
            graded = _grade(item, output_text)

        result = {
            "id": item.get("id", f"item_{index}"),
            "index": index,
            "suite": item.get("suite", ""),
            "suite_name": item.get("suite_name", ""),
            "category": item.get("category", ""),
            "prompt": item.get("prompt", ""),
            "options": item.get("options", []),
            "given_answer": output_text,
            "correct_answer": item.get("correct_answer", ""),
            "correct_choice": item.get("correct_choice", ""),
            "verdict": graded["verdict"],
            "passed": graded["passed"],
            "needs_review": graded["needs_review"],
            "parsed": graded.get("parsed", {}),
            "execution": graded.get("execution"),
            "error": transport_error,
            "endpoint": endpoint,
            "tokens_per_sec": tok_per_sec,
            "latency_ms": int(elapsed * 1000),
            "tokens": tokens,
        }

        with lock:
            completed += 1
            tokens_total += tokens
            duration_total += elapsed
            latency_sum += int(elapsed * 1000)
            counts[graded["verdict"]] = counts.get(graded["verdict"], 0) + 1
            buffer.append(result)
        flush()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(process, i, item) for i, item in enumerate(items)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as err:
                    log.warning("Quesito benchmark non completato: %s", err)
    finally:
        flush(force=True)

    cancelled = job_id in _cancel_requested
    _cancel_requested.discard(job_id)
    _pause_requested.discard(job_id)

    metrics = _compute_metrics(counts, completed, total, tokens_total, duration_total, latency_sum)
    # L'impronta copre modello, suite ed esito completo: due run identici la
    # riproducono, e un run con conteggi diversi no.
    fingerprint = (f"{model_name}:{suite_id}:{total}:{completed}:"
                   f"{metrics['tests_passed']}:{metrics['tests_failed']}:"
                   f"{metrics['tests_review']}:{tokens_total}:seed42:temp0.0:"
                   f"prompt{PROMPT_PROTOCOL}:{GRADER_VERSION}")
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16].upper()

    _update_job_state(job_id, {
        "status": "cancelled" if cancelled else "completed",
        "progress": min(100, int((completed / total) * 100)) if cancelled else 100,
        "updated_at": datetime.datetime.now().isoformat(),
        "metrics": metrics,
        "reproducibility": {
            "temperature": 0.0,
            "seed": 42,
            "reproducible_hash": f"SHA256-{digest}",
            "dataset_items_planned": total,
            "dataset_items_processed": completed,
            "dataset_coverage": f"{round((completed / total) * 100, 1)}%",
            "mode": "FULL_DATASET_100%_CLEAN" if mode == "full" else "AUDIT_SAMPLE",
            "grader": GRADER_VERSION,
            "prompt_protocol": PROMPT_PROTOCOL,
        },
    })
    # Deregistrato solo dopo l'ultimo aggiornamento: togliendolo prima, il
    # ricaricamento dell'indice vedeva un job "running" senza worker e lo
    # marcava interrotto un istante prima di scriverlo come completato.
    _active_threads.pop(job_id, None)
    log.info("Job benchmark %s terminato: %s/%s superati, %s da rivedere.",
             job_id, metrics["tests_passed"], completed, metrics["tests_review"])


# ==============================================================================
# CONSULTAZIONE E CONTROLLO DEI JOB
# ==============================================================================

def list_benchmark_jobs() -> list[dict]:
    """Elenco dei job con metriche aggregate, senza il dettaglio dei quesiti."""
    return _load_benchmarks()


def get_job_detail(job_id: str, page: int = 1, page_size: int = 15,
                   verdict: str = "all", suite: str = "all", query: str = "") -> dict:
    """Una pagina di esiti di un job, con riepilogo per suite e per verdetto."""
    job = next((j for j in _load_benchmarks() if j.get("id") == job_id), None)
    if not job:
        return {"success": False, "error": f"Job {job_id} non trovato"}
    payload = store.read_page(job_id, page, page_size, verdict, suite, query)
    payload.update({
        "job": job,
        "verdict_counts": store.verdict_counts(job_id),
        "suite_breakdown": store.suite_breakdown(job_id),
    })
    return payload


def get_review_queue(job_id: str) -> dict:
    """Quesiti da valutare a parte: risposta duplice, illeggibile o in errore."""
    job = next((j for j in _load_benchmarks() if j.get("id") == job_id), None)
    if not job:
        return {"success": False, "error": f"Job {job_id} non trovato"}
    items = store.read_review_queue(job_id)
    return {
        "success": True,
        "job_id": job_id,
        "model": job.get("model", ""),
        "suite": job.get("suite_name") or job.get("suite", ""),
        "count": len(items),
        "verdict_counts": store.verdict_counts(job_id),
        "items": items,
    }


def pause_benchmark_job(job_id: str) -> bool:
    with _benchmark_lock:
        benchmarks = _load_benchmarks()
        for job in benchmarks:
            if job.get("id") == job_id and job.get("status") in ("running", "executing"):
                _pause_requested.add(job_id)
                job["status"] = "paused"
                job["updated_at"] = datetime.datetime.now().isoformat()
                _save_benchmarks(benchmarks)
                log.info("Job benchmark %s: pausa richiesta.", job_id)
                return True
    return False


def resume_benchmark_job(job_id: str) -> bool:
    with _benchmark_lock:
        benchmarks = _load_benchmarks()
        for job in benchmarks:
            if job.get("id") == job_id and job.get("status") == "paused":
                _pause_requested.discard(job_id)
                job["status"] = "running"
                job["updated_at"] = datetime.datetime.now().isoformat()
                _save_benchmarks(benchmarks)
                log.info("Job benchmark %s: ripresa richiesta.", job_id)
                return True
    return False


def cancel_benchmark_job(job_id: str) -> bool:
    with _benchmark_lock:
        benchmarks = _load_benchmarks()
        for job in benchmarks:
            if job.get("id") == job_id and job.get("status") in ("running", "paused", "preparing"):
                _pause_requested.discard(job_id)
                _cancel_requested.add(job_id)
                job["status"] = "cancelling"
                job["updated_at"] = datetime.datetime.now().isoformat()
                _save_benchmarks(benchmarks)
                log.info("Job benchmark %s: annullamento richiesto.", job_id)
                return True
    return False


def delete_benchmark_job(job_id: str) -> bool:
    _pause_requested.discard(job_id)
    _cancel_requested.add(job_id)
    with _benchmark_lock:
        benchmarks = _load_benchmarks()
        remaining = [j for j in benchmarks if j.get("id") != job_id]
        if len(remaining) == len(benchmarks):
            return False
        _save_benchmarks(remaining)
    store.delete_results(job_id)
    _active_threads.pop(job_id, None)
    return True


def audit_benchmark_job(job_id: str) -> dict:
    """Verifica che i verdetti di un run reggano, quesito per quesito.

    Un punteggio si legge solo dopo questo: dice quanti verdetti sono stati
    dati per il motivo giusto, e mostra quelli che non lo sono.
    """
    from core.training.audit import audit_run

    # L'audit guarda il run intero: paginarlo lo renderebbe cieco proprio sui
    # quesiti che non stanno nella prima pagina. `read_page` limita comunque la
    # pagina a un tetto suo, quindi si scorre finche' ci sono pagine.
    rows: list[dict] = []
    page, pages = 1, 1
    while page <= pages:
        chunk = store.read_page(job_id, page=page, page_size=1000)
        rows.extend(chunk.get("results", []))
        pages = chunk.get("pages", 1)
        page += 1
    if not rows:
        return {"success": False, "error": f"Nessun esito salvato per il job '{job_id}'."}
    result = audit_run(rows)
    result["job_id"] = job_id
    return result
