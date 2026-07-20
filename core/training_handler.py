"""
Training Handler — Sigma Studio v7.0
Gestione completa del ciclo di vita per training e fine-tuning di LLM.

Funzionalità:
  - Ricerca dataset HuggingFace (API pubblica, senza auth)
  - Import dataset locali (JSONL, CSV, TXT)
  - Creazione e gestione job di training
  - Avvio in subprocess isolato con log streaming
  - Export verso Ollama (GGUF + Modelfile auto-generated)
  - Integrazione con task_handler per notifiche Sigma
"""
import json
import os
import subprocess
import sys
import threading
import time
import uuid
import csv
import shutil
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from urllib.error import URLError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
TRAINING_DIR = BASE_DIR / "data" / "training"
DATASETS_DIR = TRAINING_DIR / "datasets"
JOBS_DIR = TRAINING_DIR / "jobs"
SCRIPTS_DIR = TRAINING_DIR / "scripts"
JOBS_FILE = TRAINING_DIR / "training_jobs.json"

for _d in [TRAINING_DIR, DATASETS_DIR, JOBS_DIR, SCRIPTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Job state helpers
# ---------------------------------------------------------------------------

def _load_jobs() -> dict:
    if JOBS_FILE.exists():
        try:
            return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_jobs(jobs: dict):
    JOBS_FILE.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# HuggingFace Dataset Search
# ---------------------------------------------------------------------------

HF_API_BASE = "https://huggingface.co/api/datasets"

def search_hf_datasets(query: str, limit: int = 20) -> dict:
    """
    Cerca dataset su HuggingFace Hub tramite API pubblica.
    Restituisce lista con nome, descrizione, downloads, likes, tags, size.
    """
    try:
        params = urlencode({
            "search": query,
            "limit": min(limit, 50),
            "full": "true",
            "sort": "downloads",
            "direction": -1,
        })
        url = f"{HF_API_BASE}?{params}"
        req = Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
        with urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        results = []
        for ds in raw:
            results.append({
                "id": ds.get("id", ""),
                "name": ds.get("id", ""),
                "author": ds.get("author", ""),
                "description": (ds.get("description") or "")[:300],
                "downloads": ds.get("downloads", 0),
                "likes": ds.get("likes", 0),
                "tags": ds.get("tags", [])[:8],
                "size_category": ds.get("cardData", {}).get("size_categories", ["unknown"])[0] if ds.get("cardData") else "unknown",
                "license": ds.get("cardData", {}).get("license", "unknown") if ds.get("cardData") else "unknown",
                "task_categories": ds.get("cardData", {}).get("task_categories", []) if ds.get("cardData") else [],
                "url": f"https://huggingface.co/datasets/{ds.get('id', '')}",
                "last_modified": ds.get("lastModified", ""),
            })
        return {"success": True, "results": results, "total": len(results)}

    except URLError as e:
        return {"success": False, "error": f"Connessione HuggingFace fallita: {e}", "results": []}
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def get_hf_dataset_info(dataset_id: str) -> dict:
    """Ottieni info dettagliate e anteprima di un dataset HuggingFace."""
    try:
        url = f"{HF_API_BASE}/{quote(dataset_id, safe='')}"
        req = Request(url, headers={"User-Agent": "SigmaStudio/7.0"})
        with urlopen(req, timeout=10) as resp:
            ds = json.loads(resp.read().decode("utf-8"))

        # Prova a ottenere preview (primii 3 esempi) via datasets-server
        preview = []
        try:
            preview_url = f"https://datasets-server.huggingface.co/first-rows?dataset={quote(dataset_id, safe='')}&config=default&split=train"
            preview_req = Request(preview_url, headers={"User-Agent": "SigmaStudio/7.0"})
            with urlopen(preview_req, timeout=8) as prev_resp:
                prev_data = json.loads(prev_resp.read().decode("utf-8"))
                rows = prev_data.get("rows", [])[:3]
                preview = [r.get("row", {}) for r in rows]
        except Exception:
            pass

        return {
            "success": True,
            "id": ds.get("id", dataset_id),
            "description": ds.get("description") or "",
            "downloads": ds.get("downloads", 0),
            "likes": ds.get("likes", 0),
            "tags": ds.get("tags", []),
            "cardData": ds.get("cardData", {}),
            "preview": preview,
            "url": f"https://huggingface.co/datasets/{dataset_id}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Local Dataset Import
# ---------------------------------------------------------------------------

def import_local_dataset(source_path: str, dataset_name: str = None, format_hint: str = "auto") -> dict:
    """
    Importa un dataset da file locale (JSONL, JSON, CSV, TXT).
    Copia nella cartella datasets/ e registra i metadati.
    """
    src = Path(source_path)
    if not src.exists():
        return {"success": False, "error": f"File non trovato: {source_path}"}

    name = dataset_name or src.stem
    # Sanify name
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    ds_id = f"local_{name}_{int(time.time())}"
    dest_dir = DATASETS_DIR / ds_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / src.name
    shutil.copy2(src, dest_file)

    # Detect format + count rows
    suffix = src.suffix.lower()
    row_count = 0
    columns = []
    preview = []

    try:
        if suffix in [".jsonl", ".ndjson"]:
            with open(dest_file, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    row_count += 1
                    if i < 3:
                        obj = json.loads(line)
                        if not columns:
                            columns = list(obj.keys())
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
                # HF-style split dict
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
                    if i < 3:
                        preview.append(dict(row))
        elif suffix == ".txt":
            with open(dest_file, encoding="utf-8") as f:
                lines = [l.rstrip() for l in f if l.strip()]
            row_count = len(lines)
            columns = ["text"]
            preview = [{"text": l} for l in lines[:3]]
            # Convert to JSONL for uniformity
            jsonl_path = dest_dir / (src.stem + ".jsonl")
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(json.dumps({"text": line}, ensure_ascii=False) + "\n")
    except Exception as e:
        return {"success": False, "error": f"Errore parsing file: {e}"}

    meta = {
        "id": ds_id,
        "name": name,
        "source": "local",
        "source_path": str(src),
        "file": str(dest_file),
        "format": suffix.lstrip("."),
        "row_count": row_count,
        "columns": columns,
        "preview": preview,
        "created_at": datetime.now().isoformat(),
        "size_bytes": src.stat().st_size,
    }
    (dest_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "dataset": meta}


def register_hf_dataset(dataset_id: str, split: str = "train") -> dict:
    """
    Registra un dataset HuggingFace come riferimento locale (senza scaricare tutto).
    Il training script userà datasets.load_dataset() a runtime.
    """
    info = get_hf_dataset_info(dataset_id)
    if not info["success"]:
        return info

    ds_id = f"hf_{dataset_id.replace('/', '_')}_{int(time.time())}"
    dest_dir = DATASETS_DIR / ds_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": ds_id,
        "name": dataset_id.split("/")[-1],
        "source": "huggingface",
        "hf_id": dataset_id,
        "split": split,
        "description": info.get("description", ""),
        "downloads": info.get("downloads", 0),
        "tags": info.get("tags", []),
        "preview": info.get("preview", []),
        "created_at": datetime.now().isoformat(),
    }
    (dest_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "dataset": meta}


def list_datasets() -> dict:
    """Lista tutti i dataset registrati (locali + HF)."""
    datasets = []
    if DATASETS_DIR.exists():
        for ds_dir in sorted(DATASETS_DIR.iterdir()):
            meta_file = ds_dir / "meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    datasets.append(meta)
                except Exception:
                    pass
    return {"success": True, "datasets": datasets}


def delete_dataset(dataset_id: str) -> dict:
    """Elimina un dataset registrato."""
    ds_dir = DATASETS_DIR / dataset_id
    if ds_dir.exists():
        shutil.rmtree(ds_dir)
        return {"success": True}
    return {"success": False, "error": "Dataset non trovato"}


# ---------------------------------------------------------------------------
# Training Job Templates
# ---------------------------------------------------------------------------

# Template scripts per vari metodi di training
SCRIPT_TEMPLATES = {
    "lora_unsloth": '''#!/usr/bin/env python3
"""
LoRA Fine-tuning con Unsloth — generato da Sigma Studio
Job ID: {job_id} | Dataset: {dataset_name} | Model: {base_model}
"""
import json, os, sys

print("[SIGMA] Avvio training LoRA con Unsloth...")
print(f"[SIGMA] Base model: {base_model}")
print(f"[SIGMA] Dataset: {dataset_path}")
print(f"[SIGMA] Output: {output_dir}")
print(f"[SIGMA] Epochs: {num_epochs} | LR: {learning_rate} | Batch: {batch_size}")

try:
    from unsloth import FastLanguageModel
    import torch
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import load_dataset
except ImportError as e:
    print(f"[ERRORE] Dipendenza mancante: {{e}}")
    print("[SIGMA] Installa: pip install unsloth trl transformers datasets")
    sys.exit(1)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{base_model}",
    max_seq_length={max_seq_length},
    dtype=None,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r={lora_r},
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha={lora_alpha},
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# Caricamento dataset
ds_path = "{dataset_path}"
if ds_path.startswith("hf:"):
    dataset = load_dataset(ds_path[3:], split="{dataset_split}")
elif ds_path.endswith(".jsonl"):
    dataset = load_dataset("json", data_files=ds_path, split="train")
elif ds_path.endswith(".csv"):
    dataset = load_dataset("csv", data_files=ds_path, split="train")
else:
    dataset = load_dataset("json", data_files=ds_path, split="train")

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="{text_field}",
    max_seq_length={max_seq_length},
    args=TrainingArguments(
        per_device_train_batch_size={batch_size},
        gradient_accumulation_steps={gradient_accumulation},
        warmup_steps=5,
        num_train_epochs={num_epochs},
        learning_rate={learning_rate},
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=42,
        output_dir="{output_dir}",
        report_to="none",
    ),
)

print("[SIGMA] Inizio training...")
trainer.train()
print("[SIGMA] Training completato!")

# Salva il modello
model.save_pretrained("{output_dir}/lora_model")
tokenizer.save_pretrained("{output_dir}/lora_model")
print(f"[SIGMA] Modello salvato in: {output_dir}/lora_model")
''',

    "trl_sft": '''#!/usr/bin/env python3
"""
SFT Training con TRL — generato da Sigma Studio
Job ID: {job_id} | Dataset: {dataset_name} | Model: {base_model}
"""
import json, sys, torch

print("[SIGMA] Avvio SFT Training con TRL...")
print(f"[SIGMA] Base model: {base_model}")
print(f"[SIGMA] Output: {output_dir}")

try:
    from trl import SFTTrainer, SFTConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from datasets import load_dataset
    from peft import LoraConfig
except ImportError as e:
    print(f"[ERRORE] Dipendenza mancante: {{e}}")
    print("[SIGMA] Installa: pip install trl transformers peft datasets accelerate")
    sys.exit(1)

tokenizer = AutoTokenizer.from_pretrained("{base_model}")
model = AutoModelForCausalLM.from_pretrained("{base_model}", torch_dtype=torch.float16, device_map="auto")

ds_path = "{dataset_path}"
if ds_path.startswith("hf:"):
    dataset = load_dataset(ds_path[3:], split="{dataset_split}")
else:
    dataset = load_dataset("json", data_files=ds_path, split="train")

peft_config = LoraConfig(r={lora_r}, lora_alpha={lora_alpha}, target_modules="all-linear", task_type="CAUSAL_LM")

sft_config = SFTConfig(
    output_dir="{output_dir}",
    num_train_epochs={num_epochs},
    per_device_train_batch_size={batch_size},
    learning_rate={learning_rate},
    logging_steps=1,
    report_to="none",
    dataset_text_field="{text_field}",
    max_seq_length={max_seq_length},
)

trainer = SFTTrainer(model=model, args=sft_config, train_dataset=dataset, peft_config=peft_config)
print("[SIGMA] Training in corso...")
trainer.train()
trainer.save_model("{output_dir}/final_model")
print("[SIGMA] Completato!")
''',

    "script_custom": '''#!/usr/bin/env python3
"""
Training Script Custom — generato da Sigma Studio
Sostituisci questo script con il tuo codice di training.
"""
import time, sys

config = {config_json}
print("[SIGMA] Script custom — sostituisci con il tuo training code")
print(f"[SIGMA] Config: {{config}}")

# Simulazione progress per testing
for i in range(1, 11):
    print(f"[SIGMA] Epoch {{i}}/10 — loss: {{1.0 / i:.4f}}")
    time.sleep(0.5)

print("[SIGMA] Training completato (script simulazione)")
'''
}


# ---------------------------------------------------------------------------
# Training Job Management
# ---------------------------------------------------------------------------

# In-memory registry per processi attivi
_active_processes: dict[str, subprocess.Popen] = {}
_log_buffers: dict[str, list[str]] = {}


def create_training_job(config: dict) -> dict:
    """
    Crea un nuovo job di training con la configurazione data.
    Config keys: base_model, dataset_id, method, hyperparams, output_name
    """
    job_id = str(uuid.uuid4())[:8]
    output_dir = str(JOBS_DIR / job_id / "output")
    os.makedirs(output_dir, exist_ok=True)

    # Risolvi il dataset
    dataset_meta = {}
    dataset_id = config.get("dataset_id", "")
    if dataset_id:
        ds_dir = DATASETS_DIR / dataset_id
        meta_file = ds_dir / "meta.json"
        if meta_file.exists():
            dataset_meta = json.loads(meta_file.read_text(encoding="utf-8"))

    hyperparams = config.get("hyperparams", {})
    method = config.get("method", "script_custom")
    base_model = config.get("base_model", "unsloth/llama-3.2-3b-instruct")

    # Determina dataset_path
    if dataset_meta.get("source") == "huggingface":
        dataset_path = f"hf:{dataset_meta.get('hf_id', dataset_id)}"
        dataset_split = dataset_meta.get("split", "train")
    elif dataset_meta.get("file"):
        dataset_path = dataset_meta["file"]
        dataset_split = "train"
    else:
        dataset_path = ""
        dataset_split = "train"

    # Genera script dal template
    tmpl_key = method if method in SCRIPT_TEMPLATES else "script_custom"
    script_content = SCRIPT_TEMPLATES[tmpl_key].format(
        job_id=job_id,
        base_model=base_model,
        dataset_name=dataset_meta.get("name", "unknown"),
        dataset_path=dataset_path,
        dataset_split=dataset_split,
        output_dir=output_dir,
        num_epochs=hyperparams.get("num_epochs", 3),
        learning_rate=hyperparams.get("learning_rate", 2e-4),
        batch_size=hyperparams.get("batch_size", 2),
        max_seq_length=hyperparams.get("max_seq_length", 2048),
        lora_r=hyperparams.get("lora_r", 16),
        lora_alpha=hyperparams.get("lora_alpha", 16),
        gradient_accumulation=hyperparams.get("gradient_accumulation", 4),
        text_field=hyperparams.get("text_field", "text"),
        config_json=json.dumps(config),
    )

    script_path = JOBS_DIR / job_id / "train.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script_content, encoding="utf-8")

    job = {
        "id": job_id,
        "status": "ready",
        "base_model": base_model,
        "method": method,
        "dataset_id": dataset_id,
        "dataset_name": dataset_meta.get("name", ""),
        "output_name": config.get("output_name", f"sigma_{job_id}"),
        "output_dir": output_dir,
        "script_path": str(script_path),
        "hyperparams": hyperparams,
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "finished_at": None,
        "pid": None,
        "exit_code": None,
        "log_lines": [],
    }

    jobs = _load_jobs()
    jobs[job_id] = job
    _save_jobs(jobs)
    return {"success": True, "job": job}


def start_training_job(job_id: str) -> dict:
    """Avvia un job di training in subprocess."""
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return {"success": False, "error": "Job non trovato"}
    if job["status"] == "running":
        return {"success": False, "error": "Job già in esecuzione"}

    script_path = job["script_path"]
    if not os.path.exists(script_path):
        return {"success": False, "error": "Script non trovato"}

    log_path = str(Path(job["output_dir"]).parent / "train.log")

    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(BASE_DIR),
        )
        _active_processes[job_id] = proc
        _log_buffers[job_id] = []

        job["status"] = "running"
        job["started_at"] = datetime.now().isoformat()
        job["pid"] = proc.pid
        jobs[job_id] = job
        _save_jobs(jobs)

        # Thread per leggere output in background
        def _reader():
            try:
                with open(log_path, "w", encoding="utf-8") as lf:
                    for line in proc.stdout:
                        line = line.rstrip()
                        _log_buffers[job_id].append(line)
                        # keep last 500 lines
                        if len(_log_buffers[job_id]) > 500:
                            _log_buffers[job_id] = _log_buffers[job_id][-500:]
                        lf.write(line + "\n")
                        lf.flush()
                exit_code = proc.wait()
                j2 = _load_jobs()
                if job_id in j2:
                    j2[job_id]["status"] = "completed" if exit_code == 0 else "failed"
                    j2[job_id]["exit_code"] = exit_code
                    j2[job_id]["finished_at"] = datetime.now().isoformat()
                    _save_jobs(j2)
                _active_processes.pop(job_id, None)
            except Exception as e:
                j2 = _load_jobs()
                if job_id in j2:
                    j2[job_id]["status"] = "failed"
                    j2[job_id]["finished_at"] = datetime.now().isoformat()
                    _save_jobs(j2)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        return {"success": True, "job_id": job_id, "pid": proc.pid}

    except Exception as e:
        job["status"] = "failed"
        jobs[job_id] = job
        _save_jobs(jobs)
        return {"success": False, "error": str(e)}


def stop_training_job(job_id: str) -> dict:
    """Termina un job in esecuzione."""
    proc = _active_processes.get(job_id)
    if not proc:
        return {"success": False, "error": "Processo non attivo"}
    try:
        proc.terminate()
        time.sleep(0.5)
        if proc.poll() is None:
            proc.kill()
        jobs = _load_jobs()
        if job_id in jobs:
            jobs[job_id]["status"] = "stopped"
            jobs[job_id]["finished_at"] = datetime.now().isoformat()
            _save_jobs(jobs)
        _active_processes.pop(job_id, None)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_job_status(job_id: str) -> dict:
    """Restituisce lo stato corrente di un job."""
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return {"success": False, "error": "Job non trovato"}
    return {"success": True, "job": job}


def get_job_logs(job_id: str, offset: int = 0) -> dict:
    """Restituisce le ultime righe di log di un job."""
    # Live logs from buffer
    if job_id in _log_buffers:
        lines = _log_buffers[job_id]
        return {"success": True, "lines": lines[offset:], "total": len(lines)}
    # Fallback to log file
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return {"success": False, "error": "Job non trovato"}
    log_path = Path(job["output_dir"]).parent / "train.log"
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        return {"success": True, "lines": lines[offset:], "total": len(lines)}
    return {"success": True, "lines": [], "total": 0}


def list_jobs() -> dict:
    """Lista tutti i job (in ordine cronologico inverso)."""
    jobs = _load_jobs()
    jobs_list = sorted(jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)
    # Add live status from process table
    for j in jobs_list:
        if j["id"] in _active_processes:
            j["status"] = "running"
        j["log_line_count"] = len(_log_buffers.get(j["id"], []))
    return {"success": True, "jobs": jobs_list}


def delete_job(job_id: str) -> dict:
    """Elimina un job e i suoi file."""
    stop_training_job(job_id)  # no-op if not running
    jobs = _load_jobs()
    if job_id in jobs:
        job_dir = JOBS_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
        del jobs[job_id]
        _save_jobs(jobs)
        return {"success": True}
    return {"success": False, "error": "Job non trovato"}


# ---------------------------------------------------------------------------
# Export to Ollama
# ---------------------------------------------------------------------------

def export_to_ollama(job_id: str, model_name: str, system_prompt: str = "") -> dict:
    """
    Genera un Modelfile Ollama dal modello trainato e lo crea via API Ollama.
    Funziona con modelli GGUF nella cartella output del job.
    """
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return {"success": False, "error": "Job non trovato"}
    if job["status"] not in ("completed",):
        return {"success": False, "error": f"Job non completato (stato: {job['status']})"}

    output_dir = Path(job["output_dir"])
    # Cerca file GGUF
    gguf_files = list(output_dir.rglob("*.gguf"))
    # Cerca modello base HF
    model_dirs = [d for d in output_dir.rglob("config.json") if d.parent != output_dir]

    if gguf_files:
        from_line = f"FROM {gguf_files[0]}"
    elif model_dirs:
        from_line = f"FROM {model_dirs[0].parent}"
    else:
        # Fallback: usa il base model originale come riferimento
        from_line = f"FROM {job.get('base_model', 'llama3.2')}"

    default_system = f"""Sei un modello fine-tuned da Sigma Studio.
Job ID: {job_id}
Base model: {job.get('base_model', 'unknown')}
Dataset: {job.get('dataset_name', 'unknown')}
Training completato il: {job.get('finished_at', 'unknown')}"""

    system_content = system_prompt or default_system
    modelfile_content = f"""{from_line}
SYSTEM \"\"\"{system_content}\"\"\"
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
"""

    # Salva il Modelfile
    modelfile_path = output_dir.parent / "Modelfile"
    modelfile_path.write_text(modelfile_content, encoding="utf-8")

    # Chiama API Ollama per creare il modello
    try:
        import urllib.request
        payload = json.dumps({"name": model_name, "modelfile": modelfile_content}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/create",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result_raw = resp.read().decode("utf-8")
            # Ollama restituisce stream di JSON lines
            lines = [l for l in result_raw.strip().split("\n") if l]
            last = json.loads(lines[-1]) if lines else {}
            if last.get("status") == "success" or last.get("status") == "":
                jobs[job_id]["exported_to_ollama"] = model_name
                _save_jobs(jobs)
                return {"success": True, "model_name": model_name, "modelfile_path": str(modelfile_path)}
    except Exception as e:
        pass  # Ollama potrebbe non essere raggiungibile, ma il Modelfile è comunque generato

    jobs[job_id]["exported_to_ollama"] = model_name
    _save_jobs(jobs)
    return {
        "success": True,
        "model_name": model_name,
        "modelfile_path": str(modelfile_path),
        "modelfile_content": modelfile_content,
        "note": "Modelfile generato. Esegui manualmente: ollama create " + model_name + " -f " + str(modelfile_path)
    }


# ---------------------------------------------------------------------------
# Hardware Info -- Multi-GPU aware, nvidia-smi primary, torch secondary
# ---------------------------------------------------------------------------

def _query_nvidia_smi():
    """Query nvidia-smi for ALL installed GPUs (always-reliable primary source).
    Works regardless of PyTorch/CUDA status - critical for RTX 50xx Blackwell GPUs.
    """
    gpus = []
    try:
        fields = (
            "index,name,memory.total,memory.free,memory.used,"
            "driver_version,pcie.link.gen.current,pcie.link.width.current,"
            "compute_cap,utilization.gpu,temperature.gpu,power.draw,power.limit"
        )
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, encoding="utf-8",
        )
        if result.returncode != 0:
            return gpus
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue

            def sf(v, d=0.0):
                try:
                    return float(str(v).strip())
                except Exception:
                    return d

            def si(v, d=0):
                try:
                    return int(float(str(v).strip()))
                except Exception:
                    return d

            g = {
                "index":          si(parts[0] if len(parts) > 0 else "0"),
                "name":           parts[1] if len(parts) > 1 else "Unknown GPU",
                "vram_total_mb":  sf(parts[2] if len(parts) > 2 else "0"),
                "vram_free_mb":   sf(parts[3] if len(parts) > 3 else "0"),
                "vram_used_mb":   sf(parts[4] if len(parts) > 4 else "0"),
                "vram_total_gb":  round(sf(parts[2] if len(parts) > 2 else "0") / 1024, 1),
                "vram_free_gb":   round(sf(parts[3] if len(parts) > 3 else "0") / 1024, 1),
                "driver_version": parts[5].strip() if len(parts) > 5 else "unknown",
                "pcie_gen":       si(parts[6] if len(parts) > 6 else "0"),
                "pcie_width":     si(parts[7] if len(parts) > 7 else "0"),
                "compute_cap":    parts[8].strip() if len(parts) > 8 else "unknown",
                "gpu_util_pct":   sf(parts[9] if len(parts) > 9 else "0"),
                "temp_c":         sf(parts[10] if len(parts) > 10 else "0"),
                "power_draw_w":   sf(parts[11] if len(parts) > 11 else "0"),
                "power_limit_w":  sf(parts[12] if len(parts) > 12 else "0"),
            }
            gpus.append(g)
    except FileNotFoundError:
        pass  # nvidia-smi not available
    except Exception:
        pass
    return gpus


def _query_nvidia_smi_processes():
    """Query active GPU compute/graphics processes per GPU bus ID."""
    processes = []
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_bus_id,pid,process_name,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, encoding="utf-8"
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    proc_name = parts[2]
                    if proc_name and proc_name != "[Insufficient Permissions]":
                        clean_name = os.path.basename(proc_name)
                    else:
                        clean_name = "System / Process"
                    processes.append({
                        "bus_id": parts[0],
                        "pid": parts[1],
                        "process_name": clean_name,
                        "full_path": parts[2],
                        "used_memory_mb": parts[3] if len(parts) > 3 else "N/A"
                    })
    except Exception:
        pass
    return processes


def _check_torch_cuda():
    """Check PyTorch CUDA availability with detailed diagnostics."""
    result = {
        "torch_available": False,
        "torch_version": None,
        "torch_cuda_version": None,
        "cuda_available": False,
        "cuda_device_count": 0,
        "torch_gpu_list": [],
        "cuda_error": None,
        "cudnn_version": None,
    }
    try:
        import torch
        result["torch_available"] = True
        result["torch_version"] = torch.__version__
        result["torch_cuda_version"] = getattr(torch.version, "cuda", None)
        try:
            result["cudnn_version"] = str(torch.backends.cudnn.version())
        except Exception:
            pass
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                cuda_ok = torch.cuda.is_available()
            except Exception as e:
                result["cuda_error"] = str(e)
                cuda_ok = False
        result["cuda_available"] = cuda_ok
        if cuda_ok:
            try:
                result["cuda_device_count"] = torch.cuda.device_count()
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    result["torch_gpu_list"].append({
                        "index": i,
                        "name": props.name,
                        "vram_gb": round(props.total_memory / (1024 ** 3), 1),
                        "compute_capability": f"{props.major}.{props.minor}",
                        "multi_processor_count": props.multi_processor_count,
                    })
            except Exception as e:
                result["cuda_error"] = str(e)
        else:
            try:
                torch.cuda.init()
            except Exception as e:
                result["cuda_error"] = str(e)
    except ImportError:
        result["cuda_error"] = "PyTorch not installed"
    return result


def _build_cuda_fix(gpus, torch_info):
    """Build actionable fix instructions based on GPU/driver/torch situation."""
    fix = {
        "has_issue": False, "issue_type": None, "severity": "ok",
        "title": "", "description": "", "commands": [], "docs_url": "",
    }
    if not gpus:
        fix.update({
            "has_issue": True, "severity": "error", "issue_type": "no_gpu",
            "title": "Nessuna GPU rilevata da nvidia-smi",
            "description": "Verifica che i driver NVIDIA siano installati correttamente.",
            "commands": ["nvidia-smi", "dxdiag"],
        })
        return fix
    if not torch_info["torch_available"]:
        fix.update({
            "has_issue": True, "severity": "error", "issue_type": "no_torch",
            "title": "PyTorch non installato",
            "description": "Installa PyTorch con supporto CUDA 12.8+.",
            "commands": [
                "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128",
            ],
            "docs_url": "https://pytorch.org/get-started/locally/",
        })
        return fix
    if torch_info["cuda_available"]:
        return fix  # All good

    fix["has_issue"] = True
    fix["severity"] = "warning"
    # Detect Blackwell (RTX 50xx) -- compute cap 12.x
    blackwell = [g for g in gpus if str(g.get("compute_cap", "")).startswith("12")]
    if blackwell:
        names = ", ".join(g["name"] for g in blackwell)
        fix.update({
            "issue_type": "blackwell_compat",
            "title": f"RTX 50xx Blackwell ({names}): GPU OK via nvidia-smi, CUDA runtime incompatibile",
            "description": (
                "Le GPU RTX 50xx (architettura Blackwell, compute cap 12.x) richiedono PyTorch "
                "compilato con CUDA 13.0. Prova i comandi nell'ordine indicato. "
                "Una volta risolto, il training distribuito multi-GPU sara' automatico con device_map='auto'."
            ),
            "commands": [
                "pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu130",
                "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128 --force-reinstall",
                "pip install torch==2.9.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130",
            ],
            "docs_url": "https://pytorch.org/get-started/locally/",
        })
    else:
        driver = gpus[0].get("driver_version", "?")
        torch_cv = torch_info.get("torch_cuda_version") or ""
        fix.update({
            "issue_type": "cuda_driver_mismatch",
            "title": f"Mismatch CUDA runtime: torch cu{torch_cv} vs driver {driver}",
            "description": "Reinstalla PyTorch con la versione CUDA compatibile con il driver installato.",
            "commands": [
                "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128 --force-reinstall",
                "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --force-reinstall",
            ],
            "docs_url": "https://pytorch.org/get-started/locally/",
        })
    return fix


def get_hardware_info():
    """
    Rileva TUTTE le GPU disponibili con informazioni complete e diagnostica CUDA.

    Strategia multi-layer:
      1. nvidia-smi (sempre, fonte primaria affidabile, vede tutte le GPU hardware)
      2. PyTorch CUDA (fonte secondaria, rileva device runtime)
      3. Diagnostics + fix instructions quando CUDA non funziona
      4. Multi-GPU info per training distribuito (device_map='auto')
    """
    # 1. nvidia-smi -- primary, always reliable
    smi_gpus = _query_nvidia_smi()

    # 2. PyTorch CUDA
    torch_info = _check_torch_cuda()

    # 3. RAM
    ram_total_gb = ram_used_gb = ram_free_gb = 0.0
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram_total_gb = round(vm.total / (1024 ** 3), 1)
        ram_used_gb  = round(vm.used / (1024 ** 3), 1)
        ram_free_gb  = round(vm.available / (1024 ** 3), 1)
    except ImportError:
        try:
            import ctypes
            class MEMSTATEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength",            ctypes.c_ulong),
                    ("dwMemoryLoad",        ctypes.c_ulong),
                    ("ullTotalPhys",        ctypes.c_ulonglong),
                    ("ullAvailPhys",        ctypes.c_ulonglong),
                    ("ullTotalPageFile",    ctypes.c_ulonglong),
                    ("ullAvailPageFile",    ctypes.c_ulonglong),
                    ("ullTotalVirtual",     ctypes.c_ulonglong),
                    ("ullAvailVirtual",     ctypes.c_ulonglong),
                    ("sullAvailExt",        ctypes.c_ulonglong),
                ]
            stat = MEMSTATEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            ram_total_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
            ram_free_gb  = round(stat.ullAvailPhys / (1024 ** 3), 1)
            ram_used_gb  = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024 ** 3), 1)
        except Exception:
            pass

    # 4. Merge torch GPU details into smi_gpus entries
    if torch_info["cuda_available"] and torch_info["torch_gpu_list"]:
        torch_by_idx = {g["index"]: g for g in torch_info["torch_gpu_list"]}
        for sg in smi_gpus:
            t = torch_by_idx.get(sg["index"])
            if t:
                sg["compute_capability"]    = t.get("compute_capability", sg.get("compute_cap", "?"))
                sg["multi_processor_count"] = t.get("multi_processor_count", 0)
                sg["cuda_visible"]          = True
            else:
                sg["cuda_visible"] = False
    else:
        for sg in smi_gpus:
            sg["cuda_visible"] = torch_info["cuda_available"]

    # 5. Diagnostics
    cuda_fix = _build_cuda_fix(smi_gpus, torch_info)

    # 6. Multi-GPU info
    gpu_count  = len(smi_gpus)
    total_vram = sum(g.get("vram_total_gb", 0) for g in smi_gpus)
    if gpu_count > 1:
        mgpu_desc = (
            f"{gpu_count} GPU rilevate -- training distribuito automatico con "
            f"device_map='auto' (HuggingFace Accelerate). VRAM totale: {total_vram:.1f} GB"
        )
    elif smi_gpus:
        mgpu_desc = f"1 GPU: {smi_gpus[0]['name']} ({smi_gpus[0].get('vram_total_gb', 0)} GB VRAM)"
    else:
        mgpu_desc = "Nessuna GPU hardware rilevata"

    multi_gpu = {
        "available":     gpu_count > 1,
        "gpu_count":     gpu_count,
        "total_vram_gb": round(total_vram, 1),
        "strategy":      "device_map_auto" if gpu_count > 1 else "single",
        "description":   mgpu_desc,
    }

    # 7. Active GPU Processes
    processes = _query_nvidia_smi_processes()

    return {
        "success": True,
        "hardware": {
            # GPU list (always from nvidia-smi, never empty if hardware present)
            "gpu":               smi_gpus,
            "gpu_count":         gpu_count,
            "processes":         processes,
            # CPU
            "cpu_count":         os.cpu_count() or 1,
            # RAM
            "ram_gb":            ram_total_gb,
            "ram_used_gb":       ram_used_gb,
            "ram_free_gb":       ram_free_gb,
            # CUDA / PyTorch
            "cuda_available":    torch_info["cuda_available"],
            "cuda_device_count": torch_info["cuda_device_count"],
            "torch_available":   torch_info["torch_available"],
            "torch_version":     torch_info.get("torch_version"),
            "torch_cuda_version":torch_info.get("torch_cuda_version"),
            "cudnn_version":     torch_info.get("cudnn_version"),
            "cuda_error":        torch_info.get("cuda_error"),
            # Diagnostics + fix
            "cuda_fix":  cuda_fix,
            # Multi-GPU
            "multi_gpu": multi_gpu,
        }
    }
