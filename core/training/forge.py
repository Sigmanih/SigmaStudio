# ==============================================================================
# core/training/forge.py — SLM Forge: modelli piccoli da zero
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Costruzione di Small Language Model partendo da zero.

A differenza del fine-tuning, qui il modello **non esiste**: si sceglie
un'architettura, si addestra (o si riusa) un tokenizer, e si allena su corpus
italiani presi da HuggingFace. L'addestramento può essere:

  * `dataset`  — solo cross-entropy sul testo (pre-training classico);
  * `distill`  — solo distillazione dai logit di un modello insegnante;
  * `both`     — combinazione pesata dei due, di solito la più efficiente:
                 il testo dà i fatti, l'insegnante dà la distribuzione.

Vincolo della distillazione: studente e insegnante devono condividere il
vocabolario, altrimenti i logit non sono confrontabili. Quando la distillazione
è attiva il tokenizer viene quindi ereditato dall'insegnante.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

from core.logger import get_logger
from core.training import gpu as gpu_layer

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
HF_API = "https://huggingface.co/api"


# ------------------------------------------------------------- architetture

# Preset in stile Llama: l'architettura più supportata dai convertitori GGUF e
# da llama.cpp, quindi un modello forgiato qui è direttamente distribuibile.
ARCHITECTURES = [
    {
        "id": "nano", "label": "Nano · ~6M", "params_m": 6,
        "hidden_size": 256, "num_hidden_layers": 6, "num_attention_heads": 8,
        "num_key_value_heads": 4, "intermediate_size": 688, "max_position_embeddings": 512,
        "desc": "Giocattolo didattico: si allena in minuti, impara la grammatica di base",
        "vram_gb": 2, "tokens_suggested_m": 100,
    },
    {
        "id": "micro", "label": "Micro · ~25M", "params_m": 25,
        "hidden_size": 512, "num_hidden_layers": 8, "num_attention_heads": 8,
        "num_key_value_heads": 4, "intermediate_size": 1376, "max_position_embeddings": 1024,
        "desc": "Frasi coerenti su un dominio ristretto. Ore di training",
        "vram_gb": 4, "tokens_suggested_m": 500,
    },
    {
        "id": "mini", "label": "Mini · ~60M", "params_m": 60,
        "hidden_size": 640, "num_hidden_layers": 12, "num_attention_heads": 10,
        "num_key_value_heads": 5, "intermediate_size": 1720, "max_position_embeddings": 1024,
        "desc": "Il più piccolo che regge un'istruzione semplice dopo il fine-tuning",
        "vram_gb": 6, "tokens_suggested_m": 1000,
    },
    {
        "id": "small", "label": "Small · ~120M", "params_m": 120,
        "hidden_size": 768, "num_hidden_layers": 16, "num_attention_heads": 12,
        "num_key_value_heads": 4, "intermediate_size": 2048, "max_position_embeddings": 2048,
        "desc": "Scala GPT-2. Utile davvero su un dominio, con distillazione",
        "vram_gb": 8, "tokens_suggested_m": 3000,
    },
    {
        "id": "base", "label": "Base · ~350M", "params_m": 350,
        "hidden_size": 1024, "num_hidden_layers": 24, "num_attention_heads": 16,
        "num_key_value_heads": 8, "intermediate_size": 2816, "max_position_embeddings": 2048,
        "desc": "Il massimo sensato su GPU consumer partendo da zero. Giorni di training",
        "vram_gb": 16, "tokens_suggested_m": 10000,
    },
]

TRAINING_MODES = [
    {"id": "dataset", "label": "Solo dataset",
     "desc": "Cross-entropy sul testo. Nessun insegnante, il modello impara dal corpus"},
    {"id": "distill", "label": "Solo distillazione",
     "desc": "Imita i logit di un modello grande. Converge prima, eredita il vocabolario"},
    {"id": "both", "label": "Dataset + distillazione",
     "desc": "Somma pesata: il testo dà i fatti, l'insegnante la distribuzione. Consigliato"},
]

# Corpus italiani noti, come punto di partenza. La ricerca dinamica su
# HuggingFace resta il modo principale per trovarne altri.
FEATURED_IT_DATASETS = [
    {"id": "HuggingFaceFW/fineweb-2", "config": "ita_Latn", "split": "train",
     "text_field": "text", "label": "FineWeb-2 italiano",
     "desc": "Web filtrato di alta qualità, il corpus generalista di riferimento"},
    {"id": "wikimedia/wikipedia", "config": "20231101.it", "split": "train",
     "text_field": "text", "label": "Wikipedia italiana",
     "desc": "Enciclopedico, pulito, ottimo per il pre-training iniziale"},
    {"id": "gsarti/clean_mc4_it", "config": "tiny", "split": "train",
     "text_field": "text", "label": "mC4 italiano (clean)",
     "desc": "Common Crawl ripulito per l'italiano, varie dimensioni"},
    {"id": "PleIAs/Italian-PD", "config": None, "split": "train",
     "text_field": "text", "label": "Italian Public Domain",
     "desc": "Libri e documenti di pubblico dominio in italiano"},
]

# Verificati sull'hub: un id inesistente qui farebbe fallire il fine-tuning
# dopo ore di pre-training già completato.
FEATURED_IT_INSTRUCT = [
    {"id": "FreedomIntelligence/alpaca-gpt4-italian", "config": None, "split": "train",
     "label": "Alpaca GPT-4 italiano", "desc": "Istruzioni di qualità superiore, tradotte"},
    {"id": "teelinsan/camoscio_cleaned", "config": None, "split": "train",
     "label": "Camoscio (ripulito)", "desc": "Alpaca italiano, la versione pulita"},
    {"id": "mchl-labs/stambecco_data_it", "config": None, "split": "train",
     "label": "Stambecco", "desc": "Dataset istruzioni nativo italiano"},
    {"id": "FreedomIntelligence/evol-instruct-italian", "config": None, "split": "train",
     "label": "Evol-Instruct italiano", "desc": "Istruzioni via evoluzione progressiva"},
]


def dataset_exists(dataset_id: str, timeout: int = 10) -> dict:
    """Verifica che un dataset esista davvero sull'hub.

    Serve a scoprirlo *prima* di avviare il run: un id sbagliato nel dataset di
    istruzioni si manifesterebbe solo alla fine del pre-training.
    """
    if not dataset_id:
        return {"exists": False, "error": "id vuoto"}
    try:
        info = _hf_get("datasets/" + dataset_id, {}, timeout)
        return {"exists": True, "id": info.get("id", dataset_id),
                "downloads": info.get("downloads", 0),
                "gated": bool(info.get("gated"))}
    except Exception as exc:
        return {"exists": False, "id": dataset_id, "error": str(exc)}

# Punto di partenza per la distillazione. La ricerca dinamica
# (`search_teacher_models`) resta il modo principale per trovarne altri: una
# lista fissa invecchia e, soprattutto, non sa dire se un modello è diventato
# ad accesso riservato.
#
# I Minerva (nativi italiani, vocabolario compatto) sarebbero gli insegnanti
# ideali ma sono `gated`: richiedono di accettare i termini sull'hub. Restano
# selezionabili, con l'avviso, perché una volta ottenuto l'accesso sono la
# scelta migliore per un modello italiano compatto.
TEACHER_MODELS = [
    {"id": "Qwen/Qwen2.5-0.5B-Instruct", "label": "Qwen2.5 0.5B Instruct",
     "vocab": 151936, "gated": False,
     "desc": "Leggero, multilingue, sempre accessibile"},
    {"id": "Qwen/Qwen2.5-1.5B-Instruct", "label": "Qwen2.5 1.5B Instruct",
     "vocab": 151936, "gated": False,
     "desc": "Insegnante più forte, richiede più VRAM"},
    {"id": "Qwen/Qwen2.5-3B-Instruct", "label": "Qwen2.5 3B Instruct",
     "vocab": 151936, "gated": False,
     "desc": "Distillazione di qualità, serve una GPU capiente"},
    {"id": "sapienzanlp/Minerva-350M-base-v1.0", "label": "Minerva 350M (nativo IT)",
     "vocab": 32768, "gated": True,
     "desc": "Vocabolario compatto: il migliore per SLM italiani. Richiede accesso"},
    {"id": "sapienzanlp/Minerva-1B-base-v1.0", "label": "Minerva 1B (nativo IT)",
     "vocab": 32768, "gated": True,
     "desc": "Più forte del 350M, stesso vocabolario compatto. Richiede accesso"},
]


def search_teacher_models(query: str = "", limit: int = 30,
                          italian_only: bool = True) -> dict:
    """Cerca insegnanti per la distillazione direttamente sull'hub.

    Come per i dataset: una lista scritta a mano invecchia e non sa dire quali
    modelli siano diventati ad accesso riservato. Qui si interroga l'hub e si
    riporta lo stato `gated`, che è la causa più frequente di fallimento a
    metà run.
    """
    params = {"filter": "text-generation", "sort": "downloads", "direction": -1,
              "limit": max(1, min(int(limit), 100)), "full": "false"}
    if italian_only:
        params["filter"] = "text-generation,it"
    if query:
        params["search"] = query

    try:
        raw = _hf_get("models", params)
    except Exception as exc:
        log.warning("ricerca insegnanti: %s", exc)
        return {"success": False, "error": str(exc), "models": [],
                "featured": TEACHER_MODELS}

    models = []
    for item in raw:
        model_id = item.get("id")
        if not model_id:
            continue
        gated = item.get("gated")
        models.append({
            "id": model_id,
            "downloads": item.get("downloads", 0),
            "likes": item.get("likes", 0),
            "gated": bool(gated) and gated != "False",
            "tags": item.get("tags", []),
            "url": f"https://huggingface.co/{model_id}",
        })

    return {"success": True, "query": query, "total": len(models),
            "models": models, "featured": TEACHER_MODELS}


def model_accessible(model_id: str, timeout: int = 10) -> dict:
    """Il modello esiste ed è scaricabile con le credenziali correnti?

    Distingue i tre casi che l'utente deve poter separare: assente, riservato
    (serve accettare i termini) e disponibile — perché il rimedio è diverso.
    """
    if not model_id:
        return {"accessible": False, "error": "id vuoto"}
    try:
        info = _hf_get("models/" + model_id, {}, timeout)
    except Exception as exc:
        message = str(exc)
        if "403" in message:
            return {"accessible": False, "gated": True, "id": model_id,
                    "error": "Accesso riservato: accetta i termini sulla pagina del "
                             "modello con il tuo account HuggingFace, poi riprova.",
                    "url": f"https://huggingface.co/{model_id}"}
        return {"accessible": False, "id": model_id, "error": message}

    gated = info.get("gated")
    is_gated = bool(gated) and gated != "False"
    vocab = None
    for key in ("config", "cardData"):
        section = info.get(key) or {}
        if isinstance(section, dict) and section.get("vocab_size"):
            vocab = section["vocab_size"]
            break

    return {
        "accessible": not is_gated,
        "gated": is_gated,
        "id": info.get("id", model_id),
        "downloads": info.get("downloads", 0),
        "vocab_size": vocab,
        "url": f"https://huggingface.co/{model_id}",
        "error": ("Modello ad accesso riservato: accetta i termini sulla sua pagina "
                  "HuggingFace (serve essere autenticati), poi riprova."
                  if is_gated else None),
    }

EXPORT_FORMATS = [
    {"id": "safetensors", "label": "HuggingFace (safetensors)", "always": True,
     "desc": "Formato nativo: transformers, vLLM, TGI"},
    {"id": "gguf_f16", "label": "GGUF F16", "desc": "llama.cpp / Ollama, precisione piena"},
    {"id": "gguf_q8", "label": "GGUF Q8_0", "desc": "8 bit: metà spazio, qualità quasi identica"},
    {"id": "gguf_q4", "label": "GGUF Q4_0", "desc": "4 bit: il più compatto, per girare ovunque"},
    {"id": "ollama", "label": "Registrazione in Ollama", "desc": "Crea il modello e lo rende usabile subito"},
]


# ------------------------------------------------------------- HF discovery

def _hf_get(path: str, params: dict, timeout: int = 15):
    url = f"{HF_API}/{path}?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def search_italian_datasets(query: str = "", limit: int = 30,
                            instruct: bool = False) -> dict:
    """Cerca dataset in italiano su HuggingFace, in tempo reale.

    Il filtro `language:it` è quello ufficiale dell'hub: restituisce i dataset
    che dichiarano l'italiano nei metadati, non una lista congelata qui dentro.
    """
    params = {"filter": "language:it", "sort": "downloads", "direction": -1,
              "limit": max(1, min(int(limit), 100)), "full": "false"}
    if query:
        params["search"] = query

    try:
        raw = _hf_get("datasets", params)
    except Exception as exc:
        log.warning("ricerca dataset italiani: %s", exc)
        return {"success": False, "error": str(exc), "datasets": [],
                "featured": FEATURED_IT_INSTRUCT if instruct else FEATURED_IT_DATASETS}

    datasets = [{
        "id": item.get("id"),
        "downloads": item.get("downloads", 0),
        "likes": item.get("likes", 0),
        "tags": item.get("tags", []),
        "updated_at": item.get("lastModified"),
        "url": f"https://huggingface.co/datasets/{item.get('id')}",
    } for item in raw if item.get("id")]

    return {
        "success": True,
        "query": query,
        "total": len(datasets),
        "datasets": datasets,
        "featured": FEATURED_IT_INSTRUCT if instruct else FEATURED_IT_DATASETS,
    }


def dataset_configs(dataset_id: str) -> dict:
    """Config e split disponibili di un dataset: servono a caricarlo davvero.

    Molti corpus multilingua (FineWeb-2, mC4, Wikipedia) espongono l'italiano
    come *config*, non come dataset separato: senza il nome giusto il
    caricamento fallisce o scarica la lingua sbagliata.
    """
    try:
        raw = _hf_get("datasets/" + dataset_id, {})
    except Exception as exc:
        return {"success": False, "error": str(exc), "configs": []}

    configs = []
    for item in (raw.get("cardData") or {}).get("configs", []) or []:
        name = item.get("config_name") if isinstance(item, dict) else item
        if name:
            configs.append(name)
    if not configs:
        for sibling in raw.get("siblings", []) or []:
            name = (sibling.get("rfilename") or "").split("/")[0]
            if name and name not in configs and "." not in name:
                configs.append(name)

    italian = [c for c in configs
               if any(tag in c.lower() for tag in ("ita", "it_", "_it", ".it", "italian"))]
    return {
        "success": True,
        "dataset_id": dataset_id,
        "configs": configs[:200],
        "italian_configs": italian[:50],
        "suggested": (italian or configs or [None])[0],
    }


# ------------------------------------------------------------- ricette

def forge_defaults(architecture: str = "", mode: str = "both") -> dict:
    """Ricetta consigliata per l'hardware presente."""
    report = gpu_layer.get_accelerator_report()
    caps = report["capabilities"]
    trainable = report["trainable_gpus"]

    # Con più schede il training è data-parallelo: OGNI GPU tiene una replica
    # intera del modello. Il limite è quindi la scheda più piccola, non la più
    # grande — dimensionare sulla maggiore porta a un OOM sulla minore.
    multi = len(trainable) > 1
    vram = caps.get("min_vram_gb", 0.0) if multi else caps.get("max_vram_gb", 0.0)

    usable = [a for a in ARCHITECTURES if a["vram_gb"] <= max(2.0, vram)]
    chosen = next((a for a in ARCHITECTURES if a["id"] == architecture),
                  usable[-1] if usable else ARCHITECTURES[0])

    notes = []
    if vram and multi:
        smallest = min(trainable, key=lambda g: g.get("vram_total_gb", 0))
        notes.append(f"Training su {len(trainable)} GPU: ogni scheda tiene una replica, "
                     f"quindi il limite è la più piccola ({smallest['name']}, {vram:g} GB) "
                     f"- architettura '{chosen['label']}'.")
    elif vram:
        notes.append(f"{vram:g} GB disponibili: architettura '{chosen['label']}' consigliata.")
    else:
        notes.append("Nessuna GPU: solo l'architettura Nano è praticabile, e lentamente.")
    if len(trainable) > 1 and mode in ("distill", "both"):
        notes.append("Anche l'insegnante viene replicato su ogni scheda che allena: "
                     "pesa sulla VRAM di entrambe, non solo della seconda.")

    teacher_device = "cuda:1" if len(trainable) > 1 else "cuda:0"
    teacher_id = TEACHER_MODELS[0]["id"]
    if mode in ("distill", "both"):
        teacher_vocab = next((t["vocab"] for t in TEACHER_MODELS if t["id"] == teacher_id), 32000)
        # Embedding + testa di output valgono 2 × vocab × hidden parametri: con un
        # insegnante dal vocabolario largo il modello cresce ben oltre la taglia
        # nominale dell'architettura, e può non entrare più in VRAM.
        embedding_m = 2 * teacher_vocab * chosen["hidden_size"] / 1e6
        total_m = chosen["params_m"] + embedding_m
        notes.append("Distillazione attiva: lo studente eredita il tokenizer "
                     "dell'insegnante (i logit devono avere lo stesso vocabolario).")
        if embedding_m > chosen["params_m"] * 0.5:
            notes.append(
                f"Attenzione: il vocabolario dell'insegnante ({teacher_vocab:,} token) "
                f"aggiunge ~{embedding_m:.0f}M parametri di sole embedding, portando il "
                f"modello a ~{total_m:.0f}M invece di {chosen['params_m']}M. "
                "Per un modello compatto scegli un insegnante con vocabolario "
                "piccolo (Minerva, 32.768 token).")

    return {
        "success": True,
        "architecture": chosen["id"],
        "architectures": ARCHITECTURES,
        "modes": TRAINING_MODES,
        "mode": mode,
        "teacher": teacher_id,
        "teachers": TEACHER_MODELS,
        "teacher_device": teacher_device,
        "datasets": FEATURED_IT_DATASETS,
        "instruct_datasets": FEATURED_IT_INSTRUCT,
        "export_formats": EXPORT_FORMATS,
        "vocab_size": 32000,
        "seq_len": min(1024, chosen["max_position_embeddings"]),
        "batch_size": max(1, int(vram // 4)) if vram else 1,
        "learning_rate": 3e-4,
        "max_steps": 2000,
        "distill_alpha": 0.5,
        "distill_temperature": 2.0,
        "save_every": 200,
        "gpu": caps.get("arch"),
        "vram_gb": vram,
        "notes": notes,
    }


def estimate_run(architecture: str, seq_len: int, batch_size: int,
                 max_steps: int, mode: str = "both") -> dict:
    """Ordine di grandezza di token processati e durata.

    Le velocità sono empiriche per GPU Ampere+; servono a dare una scala, non a
    promettere un tempo esatto.
    """
    arch = next((a for a in ARCHITECTURES if a["id"] == architecture), ARCHITECTURES[0])
    tokens = seq_len * batch_size * max_steps

    # token/s indicativi, scalati sulla dimensione del modello
    base_rate = 120_000 / max(1, arch["params_m"]) ** 0.55
    if mode == "both":
        base_rate *= 0.45          # forward dell'insegnante a ogni step
    elif mode == "distill":
        base_rate *= 0.5
    seconds = tokens / max(1.0, base_rate)

    suggested = arch["tokens_suggested_m"] * 1_000_000
    return {
        "tokens_total": tokens,
        "tokens_millions": round(tokens / 1e6, 1),
        "tokens_suggested_millions": arch["tokens_suggested_m"],
        "coverage_pct": round(100.0 * tokens / suggested, 1) if suggested else None,
        # due decimali: sui run brevi un solo decimale appiattirebbe a "0.1h"
        # anche configurazioni che differiscono del doppio
        "hours": round(seconds / 3600, 2),
        "minutes": round(seconds / 60, 1),
        "params_m": arch["params_m"],
        "note": ("Con meno token del suggerito il modello resta acerbo: "
                 "va bene per provare la pipeline, non per un modello utile."
                 if tokens < suggested * 0.1 else ""),
    }


def forge_status() -> dict:
    """Tutto quello che serve alla schermata Forge in una chiamata."""
    defaults = forge_defaults()
    return {
        "success": True,
        "defaults": defaults,
        "architectures": ARCHITECTURES,
        "modes": TRAINING_MODES,
        "teachers": TEACHER_MODELS,
        "datasets": FEATURED_IT_DATASETS,
        "instruct_datasets": FEATURED_IT_INSTRUCT,
        "export_formats": EXPORT_FORMATS,
    }
