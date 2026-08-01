# ==============================================================================
# core/training/datasets.py — HuggingFace & Local Dataset Manager
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Dataset management for LLM training: featured datasets list, HuggingFace Hub
search, local dataset import (JSONL, JSON, CSV, TXT), and dataset deletion.
"""

import json
import os
import shutil
import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote, urlencode
from urllib.error import URLError
from core.logger import get_logger

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TRAINING_DIR = BASE_DIR / "training"
DATASETS_DIR = TRAINING_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

HF_API_BASE = "https://huggingface.co/api/datasets"

FEATURED_DATASETS = [
    {"id":"tatsu-lab/alpaca","name":"Alpaca","author":"tatsu-lab","category":"instruction","category_label":"Instruction Tuning","description":"52K instruction-following demonstrations generati da text-davinci-003.","downloads":3_200_000,"likes":2100,"size_category":"1K<n<10K","license":"cc-by-nc-4.0","task_categories":["text-generation"],"tags":["instruction-following","alpaca","llm","training"],"url":"https://huggingface.co/datasets/tatsu-lab/alpaca","split":"train","text_field":"text","recommended_method":"lora_unsloth","difficulty":"beginner","vram_min_gb":8},
    {"id":"databricks/databricks-dolly-15k","name":"Dolly 15K","author":"databricks","category":"instruction","category_label":"Instruction Tuning","description":"15K dati di instruction following scritti da dipendenti Databricks.","downloads":2_100_000,"likes":1800,"size_category":"10K<n<100K","license":"cc-by-sa-3.0","task_categories":["text-generation"],"tags":["instruction-following","dolly","databricks","commercial"],"url":"https://huggingface.co/datasets/databricks/databricks-dolly-15k","split":"train","text_field":"instruction","recommended_method":"lora_unsloth","difficulty":"beginner","vram_min_gb":8},
    {"id":"teknium/OpenHermes-2.5","name":"OpenHermes 2.5","author":"teknium","category":"instruction","category_label":"Instruction Tuning","description":"1M+ esempi instruction tuning di alta qualità da diverse fonti.","downloads":4_500_000,"likes":3200,"size_category":"1M<n<10M","license":"apache-2.0","task_categories":["text-generation","instruction-following"],"tags":["openhermes","instruction","high-quality","chat"],"url":"https://huggingface.co/datasets/teknium/OpenHermes-2.5","split":"train","text_field":"text","recommended_method":"trl_sft","difficulty":"intermediate","vram_min_gb":12},
    {"id":"HuggingFaceH4/ultrachat_200k","name":"UltraChat 200K","author":"HuggingFaceH4","category":"instruction","category_label":"Instruction Tuning","description":"200K conversazioni multi-turn filtrate e curate da UltraChat.","downloads":2_800_000,"likes":1500,"size_category":"100K<n<1M","license":"mit","task_categories":["conversational","text-generation"],"tags":["chat","multiturn","zephyr","mistral"],"url":"https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k","split":"train_sft","text_field":"messages","recommended_method":"trl_sft","difficulty":"intermediate","vram_min_gb":16},
    {"id":"Open-Orca/OpenOrca","name":"Open-Orca","author":"Open-Orca","category":"instruction","category_label":"Instruction Tuning","description":"3.2M esempi di reasoning chain-of-thought da GPT-4.","downloads":3_900_000,"likes":2800,"size_category":"1M<n<10M","license":"other","task_categories":["text-generation","question-answering"],"tags":["orca","gpt4","reasoning","chain-of-thought"],"url":"https://huggingface.co/datasets/Open-Orca/OpenOrca","split":"train","text_field":"response","recommended_method":"trl_sft","difficulty":"intermediate","vram_min_gb":16},
    {"id":"sahil2801/CodeAlpaca-20k","name":"CodeAlpaca 20K","author":"sahil2801","category":"code","category_label":"Code Training","description":"20K istruzioni di coding generate con self-instruct.","downloads":820_000,"likes":650,"size_category":"10K<n<100K","license":"cc-by-4.0","task_categories":["text-generation","text2text-generation"],"tags":["code","python","instruction","alpaca"],"url":"https://huggingface.co/datasets/sahil2801/CodeAlpaca-20k","split":"train","text_field":"output","recommended_method":"lora_unsloth","difficulty":"beginner","vram_min_gb":8},
    {"id":"iamtarun/python_code_instructions_18k_alpaca","name":"Python Code Instructions 18K","author":"iamtarun","category":"code","category_label":"Code Training","description":"18K istruzioni Python con output codice completo.","downloads":450_000,"likes":320,"size_category":"10K<n<100K","license":"apache-2.0","task_categories":["text-generation"],"tags":["python","code","instruction"],"url":"https://huggingface.co/datasets/iamtarun/python_code_instructions_18k_alpaca","split":"train","text_field":"prompt","recommended_method":"lora_unsloth","difficulty":"beginner","vram_min_gb":8},
    {"id":"bigcode/starcoderdata","name":"StarCoder Data","author":"bigcode","gated":True,"category":"code","category_label":"Code Training","description":"783GB di codice sorgente in 86 linguaggi.","downloads":1_800_000,"likes":1200,"size_category":"1M<n<10M","license":"other","task_categories":["text-generation"],"tags":["code","multi-language","pretrain","starcoder"],"url":"https://huggingface.co/datasets/bigcode/starcoderdata","split":"python","text_field":"content","recommended_method":"full_pretrain","difficulty":"advanced","vram_min_gb":40},
    {"id":"meta-math/MetaMathQA","name":"MetaMathQA","author":"meta-math","category":"math","category_label":"Math & Reasoning","description":"395K problemi matematici con soluzioni step-by-step.","downloads":2_200_000,"likes":1900,"size_category":"100K<n<1M","license":"mit","task_categories":["question-answering","text-generation"],"tags":["math","reasoning","gsm8k","step-by-step"],"url":"https://huggingface.co/datasets/meta-math/MetaMathQA","split":"train","text_field":"response","recommended_method":"lora_unsloth","difficulty":"intermediate","vram_min_gb":8},
    {"id":"openai/gsm8k","name":"GSM8K","author":"openai","config":"main","category":"math","category_label":"Math & Reasoning","description":"8.5K problemi matematici di scuola media di alta qualità.","downloads":3_100_000,"likes":2400,"size_category":"1K<n<10K","license":"mit","task_categories":["question-answering"],"tags":["math","grade-school","benchmark","openai"],"url":"https://huggingface.co/datasets/openai/gsm8k","split":"train","text_field":"answer","recommended_method":"lora_unsloth","difficulty":"beginner","vram_min_gb":4},
    {"id":"qwedsacf/competition_math","name":"MATH","author":"qwedsacf","config":"default","category":"math","category_label":"Math & Reasoning","description":"12.5K problemi di matematica avanzata.","downloads":980_000,"likes":820,"size_category":"10K<n<100K","license":"mit","task_categories":["question-answering"],"tags":["math","olympiad","advanced","algebra"],"url":"https://huggingface.co/datasets/qwedsacf/competition_math","split":"train","text_field":"solution","recommended_method":"trl_sft","difficulty":"advanced","vram_min_gb":12},
    {"id":"roneneldan/TinyStories","name":"TinyStories","author":"roneneldan","category":"pretrain","category_label":"Pre-Training","description":"2M+ storie brevi e semplici generate da GPT.","downloads":2_000_000,"likes":1600,"size_category":"1M<n<10M","license":"other","task_categories":["text-generation"],"tags":["pretrain","stories","small-model","consumer-gpu"],"url":"https://huggingface.co/datasets/roneneldan/TinyStories","split":"train","text_field":"text","recommended_method":"full_pretrain","difficulty":"beginner","vram_min_gb":4},
    {"id":"Skylion007/openwebtext","name":"OpenWebText","author":"Skylion007","config":"plain_text","category":"pretrain","category_label":"Pre-Training","description":"Open replica di WebText (dataset GPT-2).","downloads":3_000_000,"likes":2100,"size_category":"1M<n<10M","license":"cc-by-4.0","task_categories":["text-generation"],"tags":["pretrain","web","gpt2","general"],"url":"https://huggingface.co/datasets/Skylion007/openwebtext","split":"train","text_field":"text","recommended_method":"full_pretrain","difficulty":"advanced","vram_min_gb":24},
    {"id":"monology/pile-uncopyrighted","name":"The Pile (uncopyrighted)","author":"monology","config":"default","category":"pretrain","category_label":"Pre-Training","description":"825GB dataset diversificato.","downloads":4_800_000,"likes":3500,"size_category":"1B<n<10B","license":"mit","task_categories":["text-generation"],"tags":["pretrain","diverse","eleutherai","gpt-j","large"],"url":"https://huggingface.co/datasets/monology/pile-uncopyrighted","split":"train","text_field":"text","recommended_method":"full_pretrain","difficulty":"advanced","vram_min_gb":80},
    {"id":"FreedomIntelligence/alpaca-gpt4-italian","name":"Alpaca GPT-4 Italiano","author":"FreedomIntelligence","config":"default","category":"multilingual","category_label":"Multilingue / ITA","description":"Istruzioni in italiano generate con GPT-4.","downloads":120_000,"likes":95,"size_category":"10K<n<100K","license":"cc-by-sa-3.0","task_categories":["text-generation"],"tags":["italian","instruction","dolly","multilingual"],"url":"https://huggingface.co/datasets/FreedomIntelligence/alpaca-gpt4-italian","split":"train","text_field":"output","recommended_method":"lora_unsloth","difficulty":"beginner","vram_min_gb":8},
    {"id":"Helsinki-NLP/opus-100","name":"OPUS-100","author":"Helsinki-NLP","config":"en-it","category":"multilingual","category_label":"Multilingue / ITA","description":"100 lingue, coppie di traduzione.","downloads":1_500_000,"likes":980,"size_category":"100K<n<1M","license":"cc-by-4.0","task_categories":["translation"],"tags":["translation","multilingual","100-languages","opus"],"url":"https://huggingface.co/datasets/Helsinki-NLP/opus-100","split":"train","text_field":"translation","recommended_method":"trl_sft","difficulty":"intermediate","vram_min_gb":12},
]


def get_featured_datasets() -> dict:
    categories = {}
    for ds in FEATURED_DATASETS:
        cat = ds["category"]
        if cat not in categories:
            categories[cat] = {"id": cat, "label": ds["category_label"], "datasets": []}
        categories[cat]["datasets"].append(ds)
    return {"success": True, "categories": list(categories.values()), "total": len(FEATURED_DATASETS)}


def _get_urlopen():
    th = sys.modules.get("core.training_handler")
    if th and hasattr(th, "urlopen"):
        return th.urlopen
    return urlopen


def search_hf_datasets(query: str, limit: int = 20) -> dict:
    try:
        params = urlencode({"search": query, "limit": min(limit, 50), "full": "true", "sort": "downloads", "direction": -1})
        req = Request(f"{HF_API_BASE}?{params}", headers={"User-Agent": "SigmaStudio/7.0"})
        fn_urlopen = _get_urlopen()
        with fn_urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        results = []
        for ds in raw:
            results.append({
                "id": ds.get("id", ""), "name": ds.get("id", ""), "author": ds.get("author", ""),
                "description": (ds.get("description") or "")[:300], "downloads": ds.get("downloads", 0),
                "likes": ds.get("likes", 0), "tags": ds.get("tags", [])[:8],
                "size_category": (ds.get("cardData") or {}).get("size_categories", ["unknown"])[0] if ds.get("cardData") else "unknown",
                "license": (ds.get("cardData") or {}).get("license", "unknown") if ds.get("cardData") else "unknown",
                "task_categories": (ds.get("cardData") or {}).get("task_categories", []) if ds.get("cardData") else [],
                "url": f"https://huggingface.co/datasets/{ds.get('id', '')}", "last_modified": ds.get("lastModified", ""),
            })
        return {"success": True, "results": results, "total": len(results)}
    except URLError as e:
        return {"success": False, "error": f"Connessione HuggingFace fallita: {e}", "results": []}
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def get_hf_dataset_info(dataset_id: str) -> dict:
    try:
        url = f"{HF_API_BASE}/{quote(dataset_id, safe='/')}"
        req = Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
        fn_urlopen = _get_urlopen()
        with fn_urlopen(req, timeout=10) as resp:
            ds = json.loads(resp.read().decode("utf-8"))
        structure = describe_hf_structure(dataset_id)
        preview = []
        if structure.get("config"):
            # L'anteprima va chiesta sul config e sullo split che il dataset ha
            # davvero: dare per scontato "default/train" la faceva fallire in
            # silenzio su gsm8k (main/socratic), openwebtext (plain_text) e su
            # tutti quelli divisi per lingua.
            try:
                preview_url = (
                    "https://datasets-server.huggingface.co/first-rows"
                    f"?dataset={quote(dataset_id, safe='/')}"
                    f"&config={quote(structure['config'])}"
                    f"&split={quote(structure['splits'][0])}")
                with fn_urlopen(Request(preview_url, headers={"User-Agent": "SigmaStudio/7.0"}),
                                timeout=8) as prev_resp:
                    rows = json.loads(prev_resp.read().decode("utf-8")).get("rows", [])[:3]
                    preview = [r.get("row", {}) for r in rows]
            except Exception as exc:
                log.debug("anteprima di %s non disponibile: %s", dataset_id, exc)
        return {"success": True, "id": ds.get("id", dataset_id), "description": ds.get("description") or "",
                "downloads": ds.get("downloads", 0), "likes": ds.get("likes", 0), "tags": ds.get("tags", []),
                "cardData": ds.get("cardData", {}), "preview": preview,
                "gated": bool(ds.get("gated")),
                **{k: structure[k] for k in ("config", "configs", "splits", "structure_error")
                   if k in structure},
                "url": f"https://huggingface.co/datasets/{dataset_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _splits_for(dataset_id: str, config: str) -> list[str]:
    """Gli split di un config preciso, quando non e' quello dedotto."""
    url = ("https://datasets-server.huggingface.co/splits"
           f"?dataset={quote(dataset_id, safe='/')}&config={quote(config)}")
    try:
        req = Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
        with _get_urlopen()(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return [e["split"] for e in payload.get("splits", []) if e.get("split")]
    except Exception:
        return []


def describe_hf_structure(dataset_id: str) -> dict:
    """Config e split che un dataset offre davvero, chiesti a HuggingFace.

    Il catalogo scritto a mano invecchia: i dataset vengono spostati, resi
    gated o divisi in sottoinsiemi, e un id che ieri funzionava oggi risponde
    401. Interrogare la struttura al momento della registrazione evita di
    salvarne uno che poi fallirebbe a training avviato.
    """
    url = ("https://datasets-server.huggingface.co/splits"
           f"?dataset={quote(dataset_id, safe='/')}")
    try:
        req = Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
        with _get_urlopen()(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"structure_error": str(exc)}

    entries = payload.get("splits") or []
    if not entries:
        return {"structure_error": payload.get("error") or "nessuno split dichiarato"}

    configs = []
    for entry in entries:
        if entry.get("config") and entry["config"] not in configs:
            configs.append(entry["config"])
    # "default" quando c'e', altrimenti il primo: e' l'ordine in cui HuggingFace
    # stessa presenta i sottoinsiemi.
    config = "default" if "default" in configs else (configs[0] if configs else "")
    splits = [e["split"] for e in entries if e.get("config") == config and e.get("split")]
    return {"config": config, "configs": configs, "splits": splits}


# HuggingFace ha ritirato gli id "canonici" senza namespace: huggingface_hub
# pretende 'namespace/name' e un id nudo solleva HfUriError. I dataset sono stati
# spostati sotto l'organizzazione che li mantiene. Questa mappa permette di
# accettare comunque il nome storico, ancora presente in guide e tutorial.
LEGACY_HF_DATASETS = {
    "wikitext": "Salesforce/wikitext",
    "openwebtext": "Skylion007/openwebtext",
    "tiny_shakespeare": "karpathy/tiny_shakespeare",
    "tiny_stories": "roneneldan/TinyStories",
    "imdb": "stanfordnlp/imdb",
    "squad": "rajpurkar/squad",
    "squad_v2": "rajpurkar/squad_v2",
    "glue": "nyu-mll/glue",
    "ag_news": "fancyzhx/ag_news",
    "xsum": "EdinburghNLP/xsum",
    "cnn_dailymail": "abisee/cnn_dailymail",
    "billsum": "FiscalNote/billsum",
    "gsm8k": "openai/gsm8k",
    "wikipedia": "wikimedia/wikipedia",
    "yelp_review_full": "Yelp/yelp_review_full",
    "daily_dialog": "li2017dailydialog/daily_dialog",
    "alpaca": "tatsu-lab/alpaca",
    "dolly": "databricks/databricks-dolly-15k",
    "oasst1": "OpenAssistant/oasst1",
}


# Config di default per i dataset che ne hanno piu' d'uno. Senza, load_dataset
# si ferma e chiede quale sottoinsieme usare; il fallback generico del loader
# prenderebbe il primo in ordine alfabetico, che spesso non e' quello utile
# (wikitext-2 invece di wikitext-103, 1.0.0 invece di 3.0.0).
HF_DATASET_CONFIGS = {
    "openai/gsm8k": "main",
    "Salesforce/wikitext": "wikitext-103-raw-v1",
    "abisee/cnn_dailymail": "3.0.0",
    "wikimedia/wikipedia": "20231101.en",
}


def resolve_hf_dataset_id(dataset_id: str) -> str:
    """Namespaced id per un dataset HuggingFace, accettando i nomi storici."""
    if not dataset_id or "/" in dataset_id:
        return dataset_id
    return LEGACY_HF_DATASETS.get(dataset_id.lower(), dataset_id)


def import_local_dataset(source_path: str, dataset_name: str = None, format_hint: str = "auto") -> dict:
    th = sys.modules.get("core.training_handler")
    target_datasets_dir = getattr(th, "DATASETS_DIR", DATASETS_DIR) if th else DATASETS_DIR
    src = Path(source_path)
    if not src.exists():
        return {"success": False, "error": f"File non trovato: {source_path}"}
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in (dataset_name or src.stem))
    ds_id = f"local_{name}_{int(time.time())}"
    dest_dir = target_datasets_dir / ds_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / src.name
    shutil.copy2(src, dest_file)
    suffix = src.suffix.lower()
    row_count = 0; columns = []; preview = []
    try:
        if suffix in [".jsonl", ".ndjson"]:
            with open(dest_file, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line: continue
                    row_count += 1
                    if i < 3:
                        obj = json.loads(line)
                        if not columns: columns = list(obj.keys())
                        preview.append(obj)
        elif suffix == ".json":
            with open(dest_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                row_count = len(data)
                if data:
                    columns = list(data[0].keys()) if isinstance(data[0], dict) else []
                    preview = data[:3]
            elif isinstance(data, dict):
                for split_data in data.values():
                    if isinstance(split_data, list):
                        row_count += len(split_data)
                        if not preview and split_data:
                            columns = list(split_data[0].keys()) if isinstance(split_data[0], dict) else []
                            preview = split_data[:3]
        elif suffix == ".csv":
            with open(dest_file, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []
                for i, row in enumerate(reader):
                    row_count += 1
                    if i < 3: preview.append(dict(row))
        elif suffix == ".txt":
            with open(dest_file, encoding="utf-8") as f:
                lines = [l.rstrip() for l in f if l.strip()]
            row_count = len(lines); columns = ["text"]
            preview = [{"text": l} for l in lines[:3]]
            jsonl_path = dest_dir / (src.stem + ".jsonl")
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(json.dumps({"text": line}, ensure_ascii=False) + "\n")
    except Exception as e:
        return {"success": False, "error": f"Errore parsing file: {e}"}
    meta = {"id": ds_id, "name": name, "source": "local", "source_path": str(src), "file": str(dest_file),
            "format": suffix.lstrip("."), "row_count": row_count, "columns": columns, "preview": preview,
            "created_at": datetime.now().isoformat(), "size_bytes": src.stat().st_size}
    (dest_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "dataset": meta}


def register_hf_dataset(dataset_id: str, split: str = "train",
                        config: str = "") -> dict:
    th = sys.modules.get("core.training_handler")
    fn_get_info = getattr(th, "get_hf_dataset_info", get_hf_dataset_info) if th else get_hf_dataset_info
    target_datasets_dir = getattr(th, "DATASETS_DIR", DATASETS_DIR) if th else DATASETS_DIR

    info = fn_get_info(dataset_id)
    if not info["success"]: return info

    # Un dataset che non espone la propria struttura non e' addestrabile:
    # meglio dirlo adesso che scoprirlo quando il run e' gia' partito.
    if info.get("structure_error") and not info.get("configs"):
        gated = info.get("gated")
        return {"success": False, "error": (
            f"'{dataset_id}' non è utilizzabile: {info['structure_error']}."
            + (" Il dataset è ad accesso ristretto: accetta le condizioni su "
               "huggingface.co e imposta il tuo HF Token in Account & Voce."
               if gated else
               " Potrebbe essere stato spostato o ritirato."))}

    configs = info.get("configs") or []
    # Ordine di precedenza: quello chiesto esplicitamente, poi quello dichiarato
    # dal catalogo, infine quello dedotto. Serve per i dataset divisi per lingua
    # come opus-100, dove il primo config in ordine alfabetico e' 'af-en' e non
    # ha nulla a che fare con quello che si vuole addestrare.
    featured = next((d for d in FEATURED_DATASETS if d["id"] == dataset_id), {})
    preferred = config or featured.get("config") or ""
    config = preferred if (not configs or preferred in configs) else (info.get("config") or "")
    if not config:
        config = info.get("config") or ""
    available = info.get("splits") or []
    # Lo split chiesto potrebbe non esistere in questo config: si ripiega su
    # 'train' se c'e', altrimenti sul primo disponibile, e lo si dice.
    if config != info.get("config"):
        # Cambiando config cambiano anche gli split disponibili.
        available = [e for e in _splits_for(dataset_id, config)] or available
    resolved_split, note = (split or featured.get("split") or "train"), ""
    if available and resolved_split not in available:
        split = resolved_split
        resolved_split = "train" if "train" in available else available[0]
        note = f"lo split '{split}' non esiste, uso '{resolved_split}'"

    ds_id = f"hf_{dataset_id.replace('/', '_')}_{int(time.time())}"
    dest_dir = target_datasets_dir / ds_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta = {"id": ds_id, "name": dataset_id.split("/")[-1], "source": "huggingface", "hf_id": dataset_id,
            "split": resolved_split, "config": config, "configs": configs, "splits": available,
            "note": note,
            "description": info.get("description", ""), "downloads": info.get("downloads", 0),
            "likes": info.get("likes", 0), "tags": info.get("tags", []), "preview": info.get("preview", []),
            "created_at": datetime.now().isoformat()}
    (dest_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "dataset": meta}


def list_imported_datasets() -> dict:
    th = sys.modules.get("core.training_handler")
    target_datasets_dir = getattr(th, "DATASETS_DIR", DATASETS_DIR) if th else DATASETS_DIR
    search_dirs = [target_datasets_dir, target_datasets_dir.parent / "Private", target_datasets_dir.parent / "Private" / "datasets"]
    datasets = []
    seen_ids = set()
    for s_dir in search_dirs:
        if s_dir.exists():
            for meta_file in s_dir.glob("**/meta.json"):
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    ds_id = meta.get("id")
                    if ds_id and ds_id not in seen_ids:
                        seen_ids.add(ds_id)
                        datasets.append(meta)
                except Exception:
                    pass
    return {"success": True, "datasets": datasets, "total": len(datasets)}


def list_datasets() -> dict:
    return list_imported_datasets()


def delete_dataset(dataset_id: str) -> dict:
    th = sys.modules.get("core.training_handler")
    target_datasets_dir = getattr(th, "DATASETS_DIR", DATASETS_DIR) if th else DATASETS_DIR
    safe_name = dataset_id.replace("/", "_").replace("\\", "_")
    target_dir = target_datasets_dir / safe_name
    if not target_dir.exists():
        for alt_dir in [target_datasets_dir.parent / "Private" / safe_name, target_datasets_dir.parent / "Private" / "datasets" / safe_name]:
            if alt_dir.exists():
                target_dir = alt_dir
                break
    if not target_dir.exists():
        return {"success": False, "error": f"Dataset '{dataset_id}' non trovato."}
    try:
        shutil.rmtree(target_dir)
        return {"success": True, "message": f"Dataset '{dataset_id}' eliminato con successo."}
    except Exception as exc:
        return {"success": False, "error": f"Errore durante l'eliminazione: {exc!s}"}
