# ==============================================================================
# core/training/jobs.py — Training Jobs Execution (CUDA-optimised) & Export
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Lifecycle of the training jobs launched from the Training Lab.

Each job is a self-contained Python script generated from a template and run as a
background process. Templates are rendered with the auto-tuned recipe produced by
`core.training.gpu` (dtype, attention kernel, batch size, quantisation, multi-GPU
strategy), so a job created on a Blackwell rig differs from one created on a
Pascal laptop without the user touching anything.

Supported methods:
  lora_unsloth  — LoRA/QLoRA via Unsloth (fastest path on CUDA)
  trl_sft       — SFT via TRL + PEFT (works everywhere, no Unsloth needed)
  full_pretrain — causal-LM pre-training, from a base model or from scratch
  fwe_gradus    — Gradus Functional Weight Engine (weight generator + VQ codebook)
  script_custom — user-editable template with the CUDA preamble already wired
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import shutil
from pathlib import Path

from core.logger import get_logger
from core.training import gpu as gpu_layer
from core.training.datasets import LEGACY_HF_DATASETS

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TRAINING_DIR = BASE_DIR / "training"
JOBS_DIR = TRAINING_DIR / "jobs"
SCRIPTS_DIR = TRAINING_DIR / "scripts"
DATASETS_DIR = TRAINING_DIR / "datasets"
JOBS_FILE = TRAINING_DIR / "training_jobs.json"

for _d in [TRAINING_DIR, JOBS_DIR, SCRIPTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

_ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}
_MONITORS: dict[str, threading.Thread] = {}

METHOD_REQUIREMENTS = {
    "lora_unsloth": ["torch", "unsloth", "trl", "transformers", "datasets"],
    "trl_sft": ["torch", "trl", "peft", "transformers", "datasets"],
    "full_pretrain": ["torch", "transformers", "datasets", "accelerate"],
    "fwe_gradus": ["torch", "transformers", "datasets"],
    "slm_forge": ["torch", "transformers", "datasets", "tokenizers", "gguf"],
    "script_custom": [],
}

METHOD_LABELS = {
    "lora_unsloth": "LoRA / QLoRA (Unsloth)",
    "trl_sft": "SFT (TRL + PEFT)",
    "full_pretrain": "Pre-training completo",
    "fwe_gradus": "Gradus FWE (generatore di pesi)",
    "slm_forge": "SLM Forge (modello da zero)",
    "script_custom": "Script custom",
}


# ============================================================== rendering

_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")

# Uno script sa estendere il proprio run solo se legge davvero GRADUS_STEPS
# dall'ambiente; la semplice presenza del nome (es. in un commento) non basta.
_STEPS_OVERRIDE_RE = re.compile(r"environ\s*\.\s*get\(\s*[\"']GRADUS_STEPS[\"']")


def _render(template: str, values: dict) -> str:
    """Substitute {placeholders} without touching the braces of the Python code.

    `str.format` cannot be used here: the templates are real scripts full of
    dicts, f-strings and set literals that would need escaping.
    """
    return _PLACEHOLDER_RE.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
        template,
    )


# ============================================================== datasets

def resolve_dataset(dataset_id: str) -> dict:
    """Map a dataset id to something a training script can actually load."""
    empty = {"id": dataset_id, "name": dataset_id or "dataset", "kind": "unknown",
             "path": "", "columns": [], "row_count": 0}
    if not dataset_id:
        return empty

    from core.training.datasets import list_imported_datasets, resolve_hf_dataset_id
    try:
        metas = list_imported_datasets().get("datasets", [])
    except Exception:
        metas = []
    meta = next((m for m in metas if m.get("id") == dataset_id), None)

    if meta is None:
        # Not registered: accept a raw HF id ("tatsu-lab/alpaca") or a file path.
        path = Path(dataset_id)
        if path.exists():
            return {"id": dataset_id, "name": path.stem, "kind": path.suffix.lstrip(".") or "json",
                    "path": str(path).replace("\\", "/"), "columns": [], "row_count": 0}
        resolved = resolve_hf_dataset_id(dataset_id)
        if "/" in resolved:
            return {"id": dataset_id, "name": resolved.split("/")[-1], "kind": "hf",
                    "path": resolved, "columns": [], "row_count": 0}
        return empty

    if meta.get("source") == "huggingface":
        return {"id": dataset_id, "name": meta.get("name", dataset_id), "kind": "hf",
                "path": resolve_hf_dataset_id(meta.get("hf_id", dataset_id)),
                "split": meta.get("split", "train"),
                "columns": meta.get("columns", []), "row_count": meta.get("row_count", 0)}

    file_path = meta.get("file", "")
    # .txt imports are normalised to a sibling .jsonl at import time
    if file_path.lower().endswith(".txt"):
        jsonl = Path(file_path).with_suffix(".jsonl")
        if jsonl.exists():
            file_path = str(jsonl)
    return {"id": dataset_id, "name": meta.get("name", dataset_id),
            "kind": Path(file_path).suffix.lstrip(".").lower() or "json",
            "path": file_path.replace("\\", "/"),
            "columns": meta.get("columns", []), "row_count": meta.get("row_count", 0)}


# ============================================================== templates

# Shared header: sets the allocator/visibility *before* torch is imported, then
# turns on the CUDA fast paths and prints the hardware the job actually got.
_PREAMBLE = '''# ==============================================================
# {method_label} — generato da Sigma Studio Training Lab
# Job {job_id} | modello {base_model} | dataset {dataset_name}
# ==============================================================
import json, os, sys, time

# expandable_segments non è implementato dall'allocatore CUDA su Windows
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF",
                      "garbage_collection_threshold:0.8" if os.name == "nt"
                      else "expandable_segments:True")
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
_VISIBLE = "{cuda_visible_devices}"
if _VISIBLE:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", _VISIBLE)

# Ricetta calcolata da Sigma sull'hardware rilevato (modificabile a mano)
TUNE = json.loads(r"""{tune_json}""")

def sigma(msg):
    print("[SIGMA] " + str(msg), flush=True)

sigma("Avvio {method_label}")
sigma("Job {job_id} | base model: {base_model}")
sigma("Dataset: {dataset_name} ({dataset_path})")
sigma("Output: {output_dir}")
sigma("Iperparametri: epochs={num_epochs} lr={learning_rate} batch={batch_size} "
      "grad_accum={gradient_accumulation} seq={max_seq_length}")

import torch

def setup_cuda():
    """TF32 + cudnn autotuner + report della GPU assegnata al job."""
    if not torch.cuda.is_available():
        sigma("ATTENZIONE: nessuna GPU CUDA visibile, training su CPU (molto lento)")
        return "cpu"
    torch.backends.cudnn.benchmark = True
    major = torch.cuda.get_device_capability(0)[0]
    if major >= 8 and TUNE.get("tf32"):
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
        sigma("TF32 abilitato (tensor core)")
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        sigma("GPU %d: %s | sm_%d%d | %.1f GB" % (i, p.name, p.major, p.minor,
                                                  p.total_memory / 1024**3))
    sigma("torch %s | cuda %s | dtype %s | attn %s" % (
        torch.__version__, torch.version.cuda, TUNE.get("dtype"),
        TUNE.get("attn_implementation")))
    return "cuda"

DEVICE = setup_cuda()
DTYPE = {"bfloat16": torch.bfloat16, "float16": torch.float16}.get(TUNE.get("dtype"), torch.float32)
'''


_DATASET_LOADER = '''
def load_training_dataset():
    """Carica il dataset e garantisce una colonna di testo utilizzabile."""
    from datasets import load_dataset
    kind, path = "{dataset_kind}", r"{dataset_path}"
    if kind == "hf":
        # Gli id senza namespace ('wikitext') non sono piu' risolvibili da
        # huggingface_hub: se il nome storico fallisce si riprova con l'alias.
        legacy = json.loads(r"""{legacy_datasets_json}""")
        try:
            ds = load_dataset(path, split="{dataset_split}")
        except Exception as exc:
            alt = legacy.get(path.lower())
            if not alt:
                raise
            sigma("Dataset '%s' spostato su '%s' (%s): riprovo" % (path, alt, type(exc).__name__))
            ds = load_dataset(alt, split="{dataset_split}")
    elif kind in ("jsonl", "ndjson", "json"):
        ds = load_dataset("json", data_files=path, split="train")
    elif kind == "csv":
        ds = load_dataset("csv", data_files=path, split="train")
    elif kind in ("parquet",):
        ds = load_dataset("parquet", data_files=path, split="train")
    else:
        ds = load_dataset("json", data_files=path, split="train")
    sigma("Dataset caricato: %d esempi | colonne: %s" % (len(ds), ds.column_names))

    field = "{text_field}"
    if field in ds.column_names:
        if field != "text":
            ds = ds.rename_column(field, "text")
        return ds

    cols = set(ds.column_names)
    if {"instruction", "output"} <= cols:
        def to_text(ex):
            inp = ex.get("input") or ""
            head = ex["instruction"] + (("\\n\\n### Input:\\n" + inp) if inp else "")
            return {"text": "### Istruzione:\\n" + head + "\\n\\n### Risposta:\\n" + str(ex["output"])}
        sigma("Formato Alpaca rilevato: instruction/input/output -> text")
        return ds.map(to_text, remove_columns=ds.column_names)
    if {"prompt", "completion"} <= cols:
        sigma("Formato prompt/completion rilevato -> text")
        return ds.map(lambda ex: {"text": str(ex["prompt"]) + str(ex["completion"])},
                      remove_columns=ds.column_names)
    if "messages" in cols or "conversations" in cols:
        key = "messages" if "messages" in cols else "conversations"
        def chat_to_text(ex):
            turns = ex[key] or []
            parts = []
            for t in turns:
                role = t.get("role") or t.get("from") or "user"
                content = t.get("content") or t.get("value") or ""
                parts.append(str(role) + ": " + str(content))
            return {"text": "\\n".join(parts)}
        sigma("Formato conversazionale rilevato -> text")
        return ds.map(chat_to_text, remove_columns=ds.column_names)

    fallback = next((c for c in ds.column_names if ds.features[c].dtype == "string"), None)
    if fallback:
        sigma("Uso la colonna testuale '%s'" % fallback)
        return ds.rename_column(fallback, "text") if fallback != "text" else ds
    raise SystemExit("[ERRORE] Nessuna colonna di testo utilizzabile in %s" % ds.column_names)
'''


_SIGMA_CALLBACK = '''
from transformers import TrainerCallback

class SigmaProgress(TrainerCallback):
    """Log parsabile dal Monitor del Training Lab (loss, epoca, VRAM, ETA)."""

    def __init__(self):
        self.t0 = time.time()

    def on_log(self, args, state, control, logs=None, **kw):
        logs = logs or {}
        if "loss" not in logs:
            return
        epoch = float(logs.get("epoch", state.epoch or 0))
        total = float(args.num_train_epochs or 1)
        pct = 100.0 * state.global_step / max(1, state.max_steps)
        vram = ""
        if torch.cuda.is_available():
            vram = " | VRAM %.1f/%.1f GB" % (
                torch.cuda.max_memory_allocated() / 1024**3,
                torch.cuda.get_device_properties(0).total_memory / 1024**3)
        eta = ""
        if state.global_step:
            per_step = (time.time() - self.t0) / state.global_step
            eta = " | ETA %dm" % int(per_step * (state.max_steps - state.global_step) / 60)
        sigma("Epoch %d/%d step %d/%d (%.1f%%) - loss: %.4f | lr: %.2e%s%s" % (
            min(int(epoch) + 1, int(total)), int(total), state.global_step,
            state.max_steps, pct, logs["loss"], logs.get("learning_rate", 0.0), vram, eta))
'''


SCRIPT_TEMPLATES = {

    # ---------------------------------------------------------------- LoRA
    "lora_unsloth": _PREAMBLE + _DATASET_LOADER + '''
try:
    import unsloth
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig
except ImportError as e:
    sigma("ERRORE dipendenza mancante: %s" % e)
    sigma("Installa con: pip install unsloth trl transformers datasets")
    sys.exit(1)
''' + _SIGMA_CALLBACK + '''
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{base_model}",
    max_seq_length={max_seq_length},
    dtype=DTYPE,
    load_in_4bit=bool(TUNE.get("load_in_4bit")),
)
sigma("Modello caricato (4-bit=%s)" % TUNE.get("load_in_4bit"))

model = FastLanguageModel.get_peft_model(
    model,
    r={lora_r},
    lora_alpha={lora_alpha},
    lora_dropout=0,
    bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth" if TUNE.get("gradient_checkpointing") else False,
    random_state=42,
)
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
sigma("LoRA r={lora_r} alpha={lora_alpha} | parametri allenabili %.2fM su %.2fM (%.2f%%)" % (
    trainable / 1e6, total / 1e6, 100.0 * trainable / max(1, total)))

dataset = load_training_dataset()

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    processing_class=tokenizer,
    args=SFTConfig(
        output_dir=r"{output_dir}",
        dataset_text_field="text",
        max_length={max_seq_length},
        per_device_train_batch_size={batch_size},
        gradient_accumulation_steps={gradient_accumulation},
        num_train_epochs={num_epochs},
        learning_rate={learning_rate},
        warmup_steps=10,
        lr_scheduler_type="linear",
        weight_decay=0.01,
        optim=TUNE.get("optim", "adamw_8bit"),
        bf16=bool(TUNE.get("bf16")),
        fp16=bool(TUNE.get("fp16")),
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

sigma("Inizio training LoRA...")
result = trainer.train()
sigma("Training completato - loss finale: %.4f" % result.training_loss)

out = r"{output_dir}" + "/lora_model"
model.save_pretrained(out)
tokenizer.save_pretrained(out)
sigma("Adapter LoRA salvato in: %s" % out)

try:
    merged = r"{output_dir}" + "/merged_16bit"
    model.save_pretrained_merged(merged, tokenizer, save_method="merged_16bit")
    sigma("Modello merged salvato in: %s" % merged)
except Exception as e:
    sigma("Merge 16-bit non riuscito (opzionale): %s" % e)

sigma("FATTO")
''',

    # ---------------------------------------------------------------- TRL SFT
    "trl_sft": _PREAMBLE + _DATASET_LOADER + '''
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig
except ImportError as e:
    sigma("ERRORE dipendenza mancante: %s" % e)
    sigma("Installa con: pip install trl peft transformers datasets bitsandbytes")
    sys.exit(1)
''' + _SIGMA_CALLBACK + '''
tokenizer = AutoTokenizer.from_pretrained("{base_model}")
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

load_kwargs = dict(dtype=DTYPE, device_map=TUNE.get("device_map") or {"": 0})
attn = TUNE.get("attn_implementation")
if attn and attn != "eager":
    load_kwargs["attn_implementation"] = attn
if TUNE.get("load_in_4bit"):
    load_kwargs["quantization_config"] = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=DTYPE,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

try:
    model = AutoModelForCausalLM.from_pretrained("{base_model}", **load_kwargs)
except Exception as e:
    sigma("Caricamento con attn=%s fallito (%s), riprovo con SDPA" % (attn, e))
    load_kwargs["attn_implementation"] = "sdpa"
    model = AutoModelForCausalLM.from_pretrained("{base_model}", **load_kwargs)

if TUNE.get("load_in_4bit"):
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=bool(TUNE.get("gradient_checkpointing")))

model = get_peft_model(model, LoraConfig(
    r={lora_r}, lora_alpha={lora_alpha}, lora_dropout=0.05, bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
))
model.print_trainable_parameters()

dataset = load_training_dataset()

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    processing_class=tokenizer,
    args=SFTConfig(
        output_dir=r"{output_dir}",
        dataset_text_field="text",
        max_length={max_seq_length},
        per_device_train_batch_size={batch_size},
        gradient_accumulation_steps={gradient_accumulation},
        num_train_epochs={num_epochs},
        learning_rate={learning_rate},
        warmup_steps=10,
        lr_scheduler_type="cosine",
        weight_decay=0.01,
        optim=TUNE.get("optim", "adamw_torch_fused"),
        bf16=bool(TUNE.get("bf16")),
        fp16=bool(TUNE.get("fp16")),
        gradient_checkpointing=bool(TUNE.get("gradient_checkpointing")),
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

sigma("Inizio training SFT...")
result = trainer.train()
sigma("Training completato - loss finale: %.4f" % result.training_loss)

out = r"{output_dir}" + "/lora_model"
trainer.model.save_pretrained(out)
tokenizer.save_pretrained(out)
sigma("Adapter salvato in: %s" % out)
sigma("FATTO")
''',

    # ---------------------------------------------------------------- pretrain
    "full_pretrain": _PREAMBLE + _DATASET_LOADER + '''
try:
    from transformers import (AutoConfig, AutoModelForCausalLM, AutoTokenizer,
                              DataCollatorForLanguageModeling, Trainer, TrainingArguments)
except ImportError as e:
    sigma("ERRORE dipendenza mancante: %s" % e)
    sigma("Installa con: pip install transformers datasets accelerate")
    sys.exit(1)
''' + _SIGMA_CALLBACK + '''
BASE = "{base_model}"
FROM_SCRATCH = BASE.strip().lower() in ("from_scratch", "scratch", "")

tokenizer = AutoTokenizer.from_pretrained("gpt2" if FROM_SCRATCH else BASE)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

if FROM_SCRATCH:
    cfg = AutoConfig.from_pretrained("gpt2")
    cfg.n_layer, cfg.n_head, cfg.n_embd = 8, 8, 512      # ~30M: entra in 8 GB
    cfg.n_positions = cfg.n_ctx = {max_seq_length}
    cfg.vocab_size = len(tokenizer)
    model = AutoModelForCausalLM.from_config(cfg, dtype=DTYPE)
    sigma("Modello GPT-2 mini inizializzato DA ZERO: %.1fM parametri" %
          (sum(p.numel() for p in model.parameters()) / 1e6))
else:
    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=DTYPE)
    sigma("Continuo il pre-training di %s: %.1fM parametri" %
          (BASE, sum(p.numel() for p in model.parameters()) / 1e6))

if DEVICE == "cuda":
    model = model.cuda()
if TUNE.get("gradient_checkpointing"):
    model.gradient_checkpointing_enable()

raw = load_training_dataset()
BLOCK = {max_seq_length}

def tokenize(batch):
    return tokenizer(batch["text"])

tokenized = raw.map(tokenize, batched=True, remove_columns=raw.column_names,
                    desc="Tokenizzazione")

def group_texts(examples):
    """Concatena e taglia in blocchi di lunghezza fissa (pre-training classico)."""
    joined = {k: sum(examples[k], []) for k in examples.keys()}
    total = (len(joined["input_ids"]) // BLOCK) * BLOCK
    out = {k: [v[i:i + BLOCK] for i in range(0, total, BLOCK)] for k, v in joined.items()}
    out["labels"] = list(out["input_ids"])
    return out

lm_dataset = tokenized.map(group_texts, batched=True, desc="Raggruppamento in blocchi")
sigma("Blocchi da %d token: %d (%.1fM token totali)" % (
    BLOCK, len(lm_dataset), len(lm_dataset) * BLOCK / 1e6))
if len(lm_dataset) == 0:
    sigma("ERRORE: dataset troppo piccolo per blocchi da %d token" % BLOCK)
    sys.exit(1)

trainer = Trainer(
    model=model,
    train_dataset=lm_dataset,
    data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    args=TrainingArguments(
        output_dir=r"{output_dir}",
        per_device_train_batch_size={batch_size},
        gradient_accumulation_steps={gradient_accumulation},
        num_train_epochs={num_epochs},
        learning_rate={learning_rate},
        warmup_steps=10,
        lr_scheduler_type="cosine",
        weight_decay=0.01,
        optim=TUNE.get("optim", "adamw_torch_fused"),
        bf16=bool(TUNE.get("bf16")),
        fp16=bool(TUNE.get("fp16")),
        gradient_checkpointing=bool(TUNE.get("gradient_checkpointing")),
        # ATTENZIONE su Windows: con num_workers>0 il DataLoader usa 'spawn' e ogni
        # worker RIESEGUE questo script (training ricorsivo). Lasciare 0 su Windows.
        dataloader_num_workers=0 if os.name == "nt" else 4,
        dataloader_pin_memory=(DEVICE == "cuda"),
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=2,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

sigma("Inizio pre-training...")
result = trainer.train()
sigma("Training completato - loss finale: %.4f" % result.training_loss)
try:
    import math
    sigma("Perplexity finale: %.2f" % math.exp(result.training_loss))
except Exception:
    pass

out = r"{output_dir}" + "/model"
trainer.save_model(out)
tokenizer.save_pretrained(out)
sigma("Modello salvato in: %s" % out)
sigma("FATTO")
''',

    # ---------------------------------------------------------------- Gradus FWE
    "fwe_gradus": _PREAMBLE + '''
# Gradus Functional Weight Engine: i pesi del modello target non vengono
# memorizzati ma GENERATI da un decoder AILO congelato guidato da un codebook VQ.
# Il motore ha forward e backward scritti a mano (nessun autograd), con i percorsi
# CUDA ottimizzati da Sigma Studio. Vedi gradus/NOTICE.md.
sys.path.insert(0, r"{base_dir}")

try:
    from gradus.engine.fwe import run_task_engine
    from gradus.logging_utils import get_logger
except ImportError as e:
    sigma("ERRORE: motore Gradus non disponibile: %s" % e)
    sigma("Il pacchetto 'gradus' deve trovarsi nella root di Sigma Studio")
    sys.exit(1)

RUN_DIR = r"{output_dir}" + "/fwe_run"
os.makedirs(RUN_DIR, exist_ok=True)

sigma("Obiettivo: task-fidelity (mantenere la perplexity), non copia dei pesi")
sigma("Tensori target: {fwe_include} | blocchi {fwe_block_size}x{fwe_block_size} | "
      "latent {fwe_latent_dim} | codebook VQ K={fwe_vq}")
if "{fwe_devices}":
    sigma("Sharding multi-GPU: {fwe_devices} — il generatore (94% del tempo) "
          "viene diviso fra le schede in proporzione alla throughput misurata")

resume = ""
ckpt = os.path.join(RUN_DIR, "engine_ckpt.pt")
if os.path.exists(ckpt):
    resume = ckpt
    sigma("Checkpoint trovato: riprendo da %s" % ckpt)

# Totale di step del run. Riavviando il job con GRADUS_STEPS piu' alto si
# CONTINUA dal checkpoint invece di ricominciare: con il valore originale il
# run riprenderebbe a step 601 di 600, cioe' non farebbe nulla.
TOTAL_STEPS = int(os.environ.get("GRADUS_STEPS") or {fwe_steps})
if TOTAL_STEPS != {fwe_steps}:
    sigma("Step totali estesi a %d (erano {fwe_steps})" % TOTAL_STEPS)

result = run_task_engine(
    get_logger(),
    model="{base_model}",
    device="{fwe_device}",
    devices="{fwe_devices}",
    device_weights="{fwe_device_weights}",
    include="{fwe_include}",
    block_size={fwe_block_size},
    latent_dim={fwe_latent_dim},
    steps=TOTAL_STEPS,
    lr={learning_rate},
    max_layers={fwe_max_layers},
    dataset="{fwe_dataset}",
    vq={fwe_vq},
    batch={batch_size},
    run_dir=RUN_DIR,
    save_every={fwe_save_every},
    resume=resume,
    prompt="Spiega in una frase cos'e' la fotosintesi.",
)

sigma("Perplexity held-out originale: %.3f" % result["ppl_original_heldout"])
sigma("Perplexity held-out ricostruita: %.3f" % result["ppl_reconstructed_heldout"])
delta = result["ppl_reconstructed_heldout"] - result["ppl_original_heldout"]
sigma("Delta perplexity: %+.3f (%s)" % (
    delta, "generalizza" if delta <= result["ppl_original_heldout"] * 0.15 else "non generalizza"))
sigma("Checkpoint: %s" % result["ckpt"])
sigma("FATTO")
''',

    # ---------------------------------------------------------------- SLM Forge
    "slm_forge": _PREAMBLE + '''
# Forgia di SLM: modello nuovo, non fine-tuning. Il grosso della logica vive in
# core/training/forge_train.py — qui si costruisce solo la configurazione, così
# la pipeline resta testabile fuori dal job.
sys.path.insert(0, r"{base_dir}")

try:
    from core.training.forge_train import run_forge, run_finetune, run_exports
    from core.logger import get_logger
except ImportError as e:
    sigma("ERRORE: pipeline Forge non disponibile: %s" % e)
    sys.exit(1)

FORGE = json.loads(r"""{forge_json}""")
FORGE["output_dir"] = r"{output_dir}"
FORGE["device"] = DEVICE if DEVICE != "cpu" else "cpu"
FORGE["dtype"] = TUNE.get("dtype")

sigma("Architettura: %s | modalità: %s" % (FORGE["architecture"]["label"], FORGE["mode"]))
sigma("Corpus: %s" % ", ".join(s["id"] for s in FORGE["sources"]))
if FORGE["mode"] in ("distill", "both"):
    sigma("Insegnante: %s su %s" % (FORGE["teacher"], FORGE.get("teacher_device")))

log = get_logger("forge")
result = run_forge(FORGE, log)
sigma("Modello addestrato: %s (%.1fM parametri, ppl %.1f)" % (
    result["model_dir"], result["params_m"], result["final_ppl"] or 0))

model_dir = result["model_dir"]

# Il modello è già su disco: da qui in poi nessuna fase opzionale può far
# perdere il lavoro fatto, quindi ognuna è isolata dalle altre.
if FORGE.get("instruct_dataset"):
    try:
        sft = run_finetune(FORGE, model_dir, log)
        if sft.get("success") and not sft.get("skipped"):
            model_dir = sft["model_dir"]
            sigma("Fine-tuning completato: loss %.4f" % sft["final_loss"])
        elif sft.get("error"):
            sigma("Fine-tuning saltato: %s" % sft["error"][:160])
    except Exception as e:
        sigma("Fine-tuning fallito (%s): proseguo con il modello pre-addestrato" % e)

formats = FORGE.get("export_formats") or []
if formats:
    sigma("Export: %s" % ", ".join(formats))
    try:
        exports = run_exports(model_dir, r"{output_dir}" + "/export", formats,
                              "{output_name}", log)
        for name, res in exports.items():
            if res.get("success"):
                sigma("  %-14s -> %s" % (name, res.get("path") or res.get("model_name") or "ok"))
            else:
                sigma("  %-14s FALLITO: %s" % (name, res.get("error")))
    except Exception as e:
        sigma("Export fallito (%s). Il modello resta in %s" % (e, model_dir))

sigma("Modello pronto: %s" % model_dir)
sigma("FATTO")
''',

    # ---------------------------------------------------------------- custom
    "script_custom": _PREAMBLE + '''
# ------------------------------------------------------------------
# Script custom — modifica liberamente questo file prima di avviarlo.
# Il preambolo sopra ha già: env CUDA, TF32, DEVICE, DTYPE e TUNE.
# ------------------------------------------------------------------

# Configurazione completa del job, come inviata dal Training Lab:
JOB_CONFIG = json.loads(r"""{config_json}""")
sigma("Config job: %s" % json.dumps(JOB_CONFIG.get("hyperparams", {}), ensure_ascii=False))

sigma("Template custom: inserisci qui la tua logica di training")
sigma("Suggerimento: usa DEVICE, DTYPE e TUNE per restare coerente con l'hardware")

# Esempio minimo — sostituiscilo con il tuo codice:
x = torch.randn(1024, 1024, device=DEVICE, dtype=DTYPE)
t0 = time.time()
for _ in range(50):
    x = torch.nn.functional.gelu(x @ x.T) * 0.001
if DEVICE == "cuda":
    torch.cuda.synchronize()
sigma("Benchmark matmul 1024x1024 x50: %.2fs" % (time.time() - t0))
sigma("FATTO")
''',
}


# ============================================================== dependencies

def _get_subprocess_run():
    th = sys.modules.get("core.training_handler")
    if th and hasattr(th, "subprocess") and hasattr(th.subprocess, "run"):
        return th.subprocess.run
    return subprocess.run


def check_training_dependencies(method: str = "lora_unsloth") -> dict:
    """Check the python packages required by a training method."""
    reqs = METHOD_REQUIREMENTS.get(method, [])
    if not reqs:
        return {"success": True, "method": method, "all_installed": True,
                "dependencies": [], "missing": [], "install_command": ""}

    sub_run = _get_subprocess_run()
    installed, missing = [], []
    for pkg in reqs:
        try:
            res = sub_run([sys.executable, "-m", "pip", "show", pkg],
                          capture_output=True, text=True, timeout=5)
            (installed if res.returncode == 0 else missing).append(pkg)
        except Exception:
            missing.append(pkg)

    return {
        "success": True,
        "method": method,
        "all_installed": len(missing) == 0,
        "dependencies": installed,
        "missing": missing,
        "install_command": f"pip install {' '.join(missing)}" if missing else "",
    }


# ============================================================== persistence

def _load_jobs() -> dict:
    th = sys.modules.get("core.training_handler")
    jobs_file = getattr(th, "JOBS_FILE", JOBS_FILE) if th else JOBS_FILE
    if jobs_file.exists():
        try:
            return json.loads(jobs_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_jobs(jobs: dict):
    th = sys.modules.get("core.training_handler")
    jobs_file = getattr(th, "JOBS_FILE", JOBS_FILE) if th else JOBS_FILE
    jobs_file.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_job(job_id: str, **fields):
    """Read-modify-write a single job (the monitor thread runs concurrently)."""
    jobs = _load_jobs()
    if job_id not in jobs:
        return
    jobs[job_id].update(fields)
    _save_jobs(jobs)


def list_training_jobs() -> dict:
    jobs = _load_jobs()
    return {"success": True, "jobs": list(jobs.values()), "total": len(jobs)}


def list_jobs() -> dict:
    return list_training_jobs()


def get_job_status(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    return {"success": True, "job": jobs[job_id]}


# ============================================================== creation

def _forge_config(hyper: dict) -> dict:
    """Configurazione della forgia a partire dagli iperparametri della UI.

    Normalizza qui i vincoli invece di lasciarli allo script: in distillazione
    il tokenizer deve venire dall'insegnante, perché i logit sono confrontabili
    solo sullo stesso vocabolario.
    """
    from core.training.forge import ARCHITECTURES, TEACHER_MODELS, FEATURED_IT_DATASETS

    arch_id = hyper.get("forge_architecture", "micro")
    architecture = next((a for a in ARCHITECTURES if a["id"] == arch_id), ARCHITECTURES[1])

    sources = hyper.get("forge_sources") or [
        {k: d[k] for k in ("id", "config", "split", "text_field")}
        for d in FEATURED_IT_DATASETS[:1]
    ]
    mode = hyper.get("forge_mode", "dataset")
    teacher = hyper.get("forge_teacher") or TEACHER_MODELS[0]["id"]

    tokenizer_mode = hyper.get("forge_tokenizer_mode", "train")
    if mode in ("distill", "both"):
        tokenizer_mode = "teacher"

    # Il training usa tutte le GPU allenabili: è il carico da ottimizzare.
    devices = hyper.get("forge_devices")
    if not devices:
        try:
            report = gpu_layer.get_accelerator_report()
            devices = [g["device_str"] for g in report["trainable_gpus"]]
        except Exception:
            devices = []

    return {
        "architecture": architecture,
        "mode": mode,
        "devices": devices,
        "sources": sources,
        "teacher": teacher,
        "teacher_device": hyper.get("forge_teacher_device", "cuda:1"),
        "tokenizer_mode": tokenizer_mode,
        "tokenizer_id": hyper.get("forge_tokenizer_id", "gpt2"),
        "vocab_size": int(hyper.get("forge_vocab_size", 32000)),
        "tokenizer_docs": int(hyper.get("forge_tokenizer_docs", 50000)),
        "seq_len": int(hyper.get("forge_seq_len", 512)),
        "batch_size": int(hyper.get("batch_size", 8)),
        "max_steps": int(hyper.get("forge_max_steps", 2000)),
        "save_every": int(hyper.get("forge_save_every", 200)),
        "keep_checkpoints": int(hyper.get("forge_keep_checkpoints", 3)),
        "learning_rate": float(hyper.get("learning_rate", 3e-4)),
        "distill_alpha": float(hyper.get("forge_distill_alpha", 0.5)),
        "distill_temperature": float(hyper.get("forge_distill_temperature", 2.0)),
        "gradient_checkpointing": bool(hyper.get("forge_gradient_checkpointing", False)),
        "instruct_dataset": hyper.get("forge_instruct_dataset"),
        "sft_steps": int(hyper.get("forge_sft_steps", 300)),
        "sft_learning_rate": float(hyper.get("forge_sft_lr", 1e-4)),
        "export_formats": hyper.get("forge_export_formats") or ["gguf_q8", "ollama"],
        "text_field": hyper.get("text_field", "text"),
    }


def _build_script_values(data: dict, job_id: str, job_dir: Path) -> dict:
    """Every placeholder the script templates need, for a given job request.

    Shared by job creation and by the regeneration that extends an existing run,
    so an extended job gets exactly the script it would get if created now.
    """
    method = data.get("method", "lora_unsloth")
    model_base = data.get("base_model") or data.get("model_base", "unsloth/llama-3.2-3b-instruct")
    dataset_id = data.get("dataset_id", "local_dataset")
    hyper = data.get("hyperparams") or data.get("config") or {}
    output_dir = job_dir / "output"

    dataset = resolve_dataset(dataset_id)
    seq_len = int(hyper.get("max_seq_length", 2048))

    # Auto-tune: hardware-derived defaults, overridden by anything the user set.
    try:
        tune = gpu_layer.recommend_training_config(method, model_base, seq_len)
    except Exception as exc:
        log.warning("autotune non disponibile: %s", exc)
        tune = {"dtype": "float32", "bf16": False, "fp16": False, "tf32": False,
                "batch_size": 1, "gradient_accumulation": 8, "gpu_indices": [],
                "optim": "adamw_torch", "notes": [f"autotune fallito: {exc}"]}

    # Alcuni metodi dividono il lavoro fra GPU diverse e devono vederle tutte.
    # L'autotune, su un rig eterogeneo, ne seleziona una sola perché DDP non
    # sarebbe applicabile — ma sia lo sharding FWE sia la forgia SLM sanno
    # ripartire il carico in proporzione alla capacità di ogni scheda.
    wants_all_gpus = method == "slm_forge" or (
        method == "fwe_gradus" and hyper.get("fwe_devices"))
    visible_indices = list(tune.get("gpu_indices", []))
    if wants_all_gpus:
        try:
            report = gpu_layer.get_accelerator_report()
            visible_indices = [g["index"] for g in report["trainable_gpus"]]
        except Exception as exc:
            log.warning("indici GPU per il multi-GPU: %s", exc)

    batch_size = int(hyper.get("batch_size") or tune.get("batch_size", 2))
    grad_accum = int(hyper.get("gradient_accumulation") or tune.get("gradient_accumulation", 4))
    num_epochs = hyper.get("num_epochs", 3)
    learning_rate = hyper.get("learning_rate", 2e-4)

    values = {
        "job_id": job_id,
        "base_dir": str(BASE_DIR).replace("\\", "/"),
        "method_label": METHOD_LABELS.get(method, method),
        "base_model": model_base,
        "dataset_name": dataset["name"],
        "dataset_path": dataset["path"] or dataset_id,
        "dataset_kind": dataset["kind"],
        "dataset_split": dataset.get("split", "train"),
        "output_dir": str(output_dir).replace("\\", "/"),
        "num_epochs": num_epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "gradient_accumulation": grad_accum,
        "max_seq_length": seq_len,
        "lora_r": hyper.get("lora_r", 16),
        "lora_alpha": hyper.get("lora_alpha", 16),
        "text_field": hyper.get("text_field", "text"),
        "tune_json": json.dumps(tune, ensure_ascii=False),
        "legacy_datasets_json": json.dumps(LEGACY_HF_DATASETS, ensure_ascii=False),
        "cuda_visible_devices": ",".join(str(i) for i in visible_indices),
        # Gradus FWE
        "fwe_device": hyper.get("fwe_device", "auto"),
        "fwe_include": hyper.get("fwe_include", "_proj"),
        "fwe_block_size": hyper.get("fwe_block_size", 32),
        "fwe_latent_dim": hyper.get("fwe_latent_dim", 64),
        "fwe_steps": hyper.get("fwe_steps", 600),
        "fwe_vq": hyper.get("fwe_vq", 512),
        "fwe_max_layers": hyper.get("fwe_max_layers", -1),
        "fwe_dataset": hyper.get("fwe_dataset", "wikitext"),
        "fwe_save_every": hyper.get("fwe_save_every", 25),
        "fwe_devices": hyper.get("fwe_devices", ""),
        "fwe_device_weights": hyper.get("fwe_device_weights", ""),
        # SLM Forge
        "forge_json": json.dumps(_forge_config(hyper), ensure_ascii=False),
        "output_name": data.get("output_name") or f"sigma_{job_id}",
        "config_json": json.dumps(data, indent=2, ensure_ascii=False),
        # campi non-template, consumati da create_training_job
        "_tune": tune,
        "_visible_indices": visible_indices,
        "_dataset": dataset,
    }
    return values


def create_training_job(data: dict) -> dict:
    """Generate the training script for a job, auto-tuned for this machine."""
    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR

    method = data.get("method", "lora_unsloth")
    model_base = data.get("base_model") or data.get("model_base", "unsloth/llama-3.2-3b-instruct")
    dataset_id = data.get("dataset_id", "local_dataset")
    hyper = data.get("hyperparams") or data.get("config") or {}

    job_id = uuid.uuid4().hex[:8]
    job_dir = target_jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    values = _build_script_values(data, job_id, job_dir)
    tune = values["_tune"]
    visible_indices = values["_visible_indices"]
    dataset = values["_dataset"]
    batch_size, grad_accum = values["batch_size"], values["gradient_accumulation"]
    num_epochs, learning_rate = values["num_epochs"], values["learning_rate"]

    template = SCRIPT_TEMPLATES.get(method, SCRIPT_TEMPLATES["script_custom"])
    script_path = job_dir / "train_script.py"
    script_path.write_text(_render(template, values), encoding="utf-8")

    # La richiesta originale serve a rigenerare lo script quando il job va
    # esteso: gli script sono file congelati su disco, quindi un job creato con
    # una versione precedente del template non conoscerebbe le opzioni nuove.
    request = {
        "base_model": model_base, "method": method, "dataset_id": dataset_id,
        "output_name": data.get("output_name"), "name": data.get("name"),
        "hyperparams": dict(hyper),
    }

    job_meta = {
        "id": job_id,
        "name": data.get("name") or data.get("output_name") or f"Job-{job_id}",
        "output_name": data.get("output_name", f"sigma_{job_id}"),
        "method": method,
        "method_label": METHOD_LABELS.get(method, method),
        "base_model": model_base,
        "dataset_id": dataset_id,
        "dataset_name": dataset["name"],
        "dataset_path": dataset["path"],
        "status": "ready",
        "progress_pct": 0,
        "current_epoch": 0,
        "total_epochs": num_epochs,
        "current_step": 0,
        "total_steps": 0,
        "last_loss": None,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "hyperparams": {**hyper, "batch_size": batch_size,
                        "gradient_accumulation": grad_accum,
                        "num_epochs": num_epochs, "learning_rate": learning_rate},
        "autotune": tune,
        "request": request,
        "visible_gpu_indices": visible_indices,
        "gpu_plan": {
            "devices": tune.get("gpu_names", []),
            "indices": tune.get("gpu_indices", []),
            "strategy": tune.get("strategy", "cpu"),
            "dtype": tune.get("dtype"),
            "attn": tune.get("attn_implementation"),
            "load_in_4bit": tune.get("load_in_4bit", False),
            "notes": tune.get("notes", []),
        },
        "dir": str(job_dir),
        "script_path": str(script_path),
        "log_path": str(job_dir / "train.log"),
    }

    jobs = _load_jobs()
    jobs[job_id] = job_meta
    _save_jobs(jobs)
    log.info("Job %s creato (%s, %s)", job_id, method, tune.get("strategy"))
    return {"success": True, "job_id": job_id, "job": job_meta}


# ============================================================== execution

_LOSS_RE = re.compile(r"loss[:\s=]+([0-9]*\.?[0-9]+)", re.IGNORECASE)
_EPOCH_RE = re.compile(r"[Ee]poch\s+(\d+)\s*/\s*(\d+)")
_STEP_RE = re.compile(r"step\s+(\d+)\s*/\s*(\d+)")
_PCT_RE = re.compile(r"\((\d+(?:\.\d+)?)%\)")


def _parse_progress(line: str, state: dict) -> bool:
    """Update `state` from one log line. Returns True if anything changed."""
    changed = False
    m = _LOSS_RE.search(line)
    if m:
        try:
            state["last_loss"] = float(m.group(1))
            changed = True
        except ValueError:
            pass
    m = _EPOCH_RE.search(line)
    if m:
        state["current_epoch"], state["total_epochs"] = int(m.group(1)), int(m.group(2))
        changed = True
    m = _STEP_RE.search(line)
    if m:
        state["current_step"], state["total_steps"] = int(m.group(1)), int(m.group(2))
        if state["total_steps"]:
            state["progress_pct"] = round(100.0 * state["current_step"] / state["total_steps"], 1)
        changed = True
    m = _PCT_RE.search(line)
    if m:
        try:
            state["progress_pct"] = float(m.group(1))
            changed = True
        except ValueError:
            pass
    return changed


def _monitor_job(job_id: str, proc, log_path: Path, poll: float = 1.5):
    """Tail train.log while the job runs and keep the job metadata live.

    The child writes the log itself, so the run survives a Sigma restart and the
    log is never truncated by a dead reader; this thread only follows the file.
    """
    state = {"progress_pct": 0, "current_epoch": 0, "total_epochs": 0,
             "current_step": 0, "total_steps": 0, "last_loss": None}
    offset = 0
    running = True
    while running:
        try:
            running = proc.poll() is None
        except Exception:
            running = False
        try:
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(offset)
                    chunk = fh.read()
                    offset = fh.tell()
                if chunk:
                    dirty = False
                    for line in chunk.splitlines():
                        dirty |= _parse_progress(line, state)
                    if dirty:
                        _update_job(job_id, **state)
        except Exception as exc:
            log.warning("monitor job %s: %s", job_id, exc)
        if running:
            time.sleep(poll)

    try:
        code = proc.wait()                        # exit code definitivo (poll() può essere None)
    except Exception:
        return
    if not isinstance(code, int):                 # processo non reale (test double): non toccare i metadati
        return
    _ACTIVE_PROCESSES.pop(job_id, None)
    _finalize_job(job_id, code, log_path, state)


def _finalize_job(job_id: str, code: int, log_path: Path, state: dict | None = None):
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if job is None:
        return
    if job.get("status") == "stopped":
        final = "stopped"
    elif code == 0:
        final = "completed"
        (state or job)["progress_pct"] = 100.0
    else:
        final = "failed"
    if state:
        job.update(state)
    job["status"] = final
    job["exit_code"] = code
    job["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if final == "failed":
        job["error"] = _tail_error(log_path) or f"Processo terminato con codice {code}"
    _save_jobs(jobs)
    log.info("Job %s terminato: %s (exit %s)", job_id, final, code)


def _tail_error(log_path: Path, lines: int = 25) -> str:
    """Last meaningful error lines, for the job card in the UI."""
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except Exception:
        return ""
    for line in reversed(tail):
        if any(k in line for k in ("Error", "error", "ERRORE", "Exception", "Traceback",
                                   "CUDA out of memory")):
            return line.strip()
    return tail[-1].strip() if tail else ""


def _refresh_script(job: dict, total_steps: int) -> dict:
    """Ensure the job's script can actually run to `total_steps`.

    Scripts are frozen on disk at creation time, so a job created before the
    template learned about GRADUS_STEPS would resume and immediately stop (the
    loop `range(601, 601)` is empty). When that happens the script is
    regenerated in place from the stored request; the run directory — and with
    it the checkpoint — is untouched, so the run resumes normally.
    """
    script_path = Path(job.get("script_path", ""))
    if not script_path.exists():
        return {"success": False, "error": f"Script del job non trovato: {script_path}"}

    try:
        source = script_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Script illeggibile: {exc}"}

    # Cerca la LETTURA della variabile, non il suo nome: il template la cita
    # anche in un commento, e un match sul nome farebbe passare per aggiornato
    # uno script che il totale ce l'ha comunque cablato.
    if _STEPS_OVERRIDE_RE.search(source):
        return {"success": True, "regenerated": False}

    request = job.get("request")
    if not request:
        # Job creato prima che la richiesta venisse salvata: la si ricostruisce
        # dai metadati, che contengono già tutto quello che serve al renderer.
        if job.get("method") and job.get("base_model"):
            request = {
                "base_model": job["base_model"],
                "method": job["method"],
                "dataset_id": job.get("dataset_id", ""),
                "output_name": job.get("output_name"),
                "name": job.get("name"),
                "hyperparams": dict(job.get("hyperparams") or {}),
            }
            log.info("Job %s: richiesta ricostruita dai metadati", job.get("id"))
        else:
            return {"success": False,
                    "error": ("Questo job è stato creato da una versione precedente e il suo "
                              "script ha gli step fissati nel codice. Modifica a mano "
                              f"`steps=` in {script_path}, oppure crea un nuovo job: il "
                              "checkpoint in output/fwe_run resta valido e verrà ripreso.")}

    data = dict(request)
    data["hyperparams"] = {**data.get("hyperparams", {}), "fwe_steps": int(total_steps)}
    try:
        values = _build_script_values(data, job["id"], Path(job["dir"]))
        template = SCRIPT_TEMPLATES.get(data.get("method"), SCRIPT_TEMPLATES["script_custom"])
        script_path.write_text(_render(template, values), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Rigenerazione dello script fallita: {exc}"}

    log.info("Job %s: script rigenerato per %d step totali", job["id"], total_steps)
    return {"success": True, "regenerated": True}


def start_training_job(job_id: str, total_steps: int | None = None) -> dict:
    """Launch the job script in the background with the CUDA env applied.

    `total_steps` extends an FWE run: the script resumes from its checkpoint and
    keeps going up to the new total, instead of restarting from scratch.
    """
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    job = jobs[job_id]
    if job["status"] == "running":
        return {"success": False, "error": f"Job '{job_id}' già in esecuzione."}

    if total_steps:
        done = int(job.get("hyperparams", {}).get("fwe_steps") or 0)
        if int(total_steps) <= done:
            return {"success": False,
                    "error": f"Il job ha già {done} step: indica un totale maggiore."}
        refreshed = _refresh_script(job, int(total_steps))
        if not refreshed.get("success"):
            return refreshed

    th = sys.modules.get("core.training_handler")
    sub_popen = getattr(th, "subprocess", subprocess).Popen if th and hasattr(th, "subprocess") \
        else subprocess.Popen

    log_path = Path(job.get("log_path") or (Path(job["dir"]) / "train.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    visible = job.get("visible_gpu_indices")
    if visible is None:
        visible = job.get("autotune", {}).get("gpu_indices")
    env.update(gpu_layer.cuda_env_vars(visible))
    env["PYTHONPATH"] = str(BASE_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    if total_steps:
        env["GRADUS_STEPS"] = str(int(total_steps))

    header = (f"===== Sigma Studio Training Lab =====\n"
              f"Job {job_id} | {job.get('method_label', job['method'])}\n"
              f"Modello: {job['base_model']} | Dataset: {job.get('dataset_name')}\n"
              f"GPU: {', '.join(job.get('gpu_plan', {}).get('devices', [])) or 'CPU'}"
              f" | strategia: {job.get('gpu_plan', {}).get('strategy')}\n"
              f"Avvio: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
              f"=====================================\n")
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(header)
    except Exception:
        pass

    # Il figlio scrive direttamente su train.log: se Sigma viene riavviato il
    # training continua e il log resta completo (con una pipe morirebbe su EPIPE).
    popen_kwargs = {"cwd": job["dir"], "env": env, "stderr": subprocess.STDOUT}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    pid = 12345
    try:
        with open(log_path, "a", encoding="utf-8", errors="replace") as sink:
            proc = sub_popen([sys.executable, "-u", job["script_path"]],
                             stdout=sink, **popen_kwargs)
        _ACTIVE_PROCESSES[job_id] = proc
        pid = getattr(proc, "pid", 12345) or 12345
        monitor = threading.Thread(target=_monitor_job, args=(job_id, proc, log_path),
                                   daemon=True, name=f"sigma-train-{job_id}")
        monitor.start()
        _MONITORS[job_id] = monitor
    except Exception as exc:
        log.warning("start job %s: %s", job_id, exc)

    job["status"] = "running"
    job["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    job["error"] = None
    job["pid"] = pid
    if total_steps:
        job.setdefault("hyperparams", {})["fwe_steps"] = int(total_steps)
        job["total_steps"] = int(total_steps)
    _save_jobs(jobs)
    return {"success": True, "message": f"Job '{job_id}' avviato.", "job": job, "pid": pid}


class _AttachedProcess:
    """Minimal Popen-like view of a process Sigma did not spawn in this session."""

    def __init__(self, pid: int):
        self.pid = pid
        self.returncode = None

    def poll(self):
        return None if _pid_alive(self.pid) else 0

    def wait(self, timeout=None):
        return self.poll() or 0

    def terminate(self):
        try:
            import psutil
            psutil.Process(self.pid).terminate()
        except Exception as exc:
            log.warning("terminate pid %s: %s", self.pid, exc)

    kill = terminate


def _pid_alive(pid: int | None, script_path: str = "") -> bool:
    """True if `pid` is alive and (when given) still running that script.

    The script check guards against PID reuse after a reboot.
    """
    if not pid:
        return False
    try:
        import psutil
        proc = psutil.Process(int(pid))
        if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
            return False
        if script_path:
            cmdline = " ".join(proc.cmdline())
            return Path(script_path).name in cmdline
        return True
    except Exception:
        return False


def reconcile_jobs() -> dict:
    """Reattach or close out jobs left 'running' by a previous Sigma session."""
    jobs = _load_jobs()
    reattached, closed = [], []
    for job_id, job in list(jobs.items()):
        if job.get("status") != "running" or job_id in _ACTIVE_PROCESSES:
            continue
        pid = job.get("pid")
        script = job.get("script_path", "")
        log_path = Path(job.get("log_path") or (Path(job.get("dir", ".")) / "train.log"))

        if _pid_alive(pid, script):
            proc = _AttachedProcess(int(pid))
            _ACTIVE_PROCESSES[job_id] = proc
            thread = threading.Thread(target=_monitor_job, args=(job_id, proc, log_path),
                                      daemon=True, name=f"sigma-train-{job_id}")
            thread.start()
            _MONITORS[job_id] = thread
            reattached.append(job_id)
        else:
            # Process gone: the script prints "FATTO" as its last line on success.
            done = False
            try:
                done = "FATTO" in log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            except Exception:
                pass
            _finalize_job(job_id, 0 if done else 1, log_path)
            closed.append(job_id)

    if reattached or closed:
        log.info("Job riconciliati: %d riagganciati, %d chiusi", len(reattached), len(closed))
    return {"success": True, "reattached": reattached, "closed": closed}


def stop_training_job(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    job = jobs[job_id]
    job["status"] = "stopped"
    job["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_jobs(jobs)

    proc = _ACTIVE_PROCESSES.pop(job_id, None)
    if proc is not None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        except Exception as exc:
            log.warning("stop job %s: %s", job_id, exc)
    return {"success": True, "message": f"Job '{job_id}' fermato.", "job": job}


def delete_job(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    stop_training_job(job_id)

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    if job_dir.exists():
        try:
            shutil.rmtree(job_dir)
        except Exception as exc:
            log.warning("delete job dir %s: %s", job_id, exc)

    jobs = _load_jobs()
    jobs.pop(job_id, None)
    _save_jobs(jobs)
    return {"success": True, "message": f"Job '{job_id}' eliminato."}


def get_job_logs(job_id: str, offset: int = 0) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    log_path = job_dir / "train.log"
    if not log_path.exists():
        log_path = Path(jobs[job_id].get("log_path", str(job_dir / "output.log")))

    if not log_path.exists():
        return {"success": True, "logs": "", "lines": [], "offset": 0,
                "status": jobs[job_id]["status"], "job": jobs[job_id]}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            new_logs = fh.read()
            new_offset = fh.tell()
        lines = [l for l in new_logs.splitlines() if l.strip()]
        return {"success": True, "logs": new_logs, "lines": lines, "offset": new_offset,
                "status": jobs[job_id]["status"], "job": jobs[job_id]}
    except Exception as exc:
        return {"success": False, "error": str(exc), "logs": "", "lines": [], "offset": offset}


def clear_job_logs(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    log_path = job_dir / "train.log"
    if not log_path.exists():
        log_path = Path(jobs[job_id].get("log_path", str(job_dir / "output.log")))
    if log_path.exists():
        try:
            log_path.write_text("", encoding="utf-8")
        except Exception as exc:
            return {"success": False, "error": str(exc)}
    return {"success": True, "message": f"Log del job '{job_id}' svuotati con successo."}


# ============================================================== export

def materialize_fwe_model(job_id: str) -> dict:
    """Turn an FWE generator checkpoint into a real HuggingFace model.

    A Gradus run produces the *generator*, not a model: the weights have to be
    regenerated and reassembled before anything else can load them.
    """
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    ckpt = job_dir / "output" / "fwe_run" / "engine_ckpt.pt"
    if not ckpt.exists():
        return {"success": False,
                "error": f"Checkpoint FWE non trovato in {ckpt}. "
                         "Il job ha prodotto un modello ricostruibile?"}

    out_dir = job_dir / "output" / "model"
    try:
        sys.path.insert(0, str(BASE_DIR))
        from gradus.export import reconstruct_to_hf
        result = reconstruct_to_hf(ckpt, out_dir, device="auto", logger=log)
    except Exception as exc:
        log.warning("ricostruzione FWE %s: %s", job_id, exc)
        return {"success": False, "error": f"Ricostruzione fallita: {exc}"}
    return result


def export_to_ollama(job_id: str, model_name: str = "custom_model",
                     system_prompt: str = "") -> dict:
    """Register the trained model in Ollama via a generated Modelfile."""
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}

    job = jobs[job_id]
    if job.get("status") != "completed":
        return {"success": False, "error": f"Job '{job_id}' non completato."}

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id

    # Prefer a merged model (self-contained), fall back to the LoRA adapter.
    output = job_dir / "output"
    merged = output / "merged_16bit"
    full_model = output / "model"
    adapter = next((p for p in (output / "lora_model", job_dir / "adapter")
                    if p.exists()), job_dir / "adapter")

    # FWE: i pesi vanno materializzati dal generatore prima di poterli esportare
    fp16_warning = ""
    if job.get("method") == "fwe_gradus" and not full_model.exists():
        built = materialize_fwe_model(job_id)
        if not built.get("success"):
            return built
        full_model = Path(built["model_dir"])
        if built.get("fp16_safe") is False:
            fp16_warning = (
                f" ATTENZIONE: le attivazioni del modello arrivano a "
                f"{built['max_activation']:.2e}, oltre il limite di fp16 (6.55e4). "
                "Ollama converte in F16, quindi in inferenza uscirà testo degenere "
                "(token ripetuti): non è un problema dell'export, il generatore va "
                "addestrato di più.")

    if not (merged.exists() or full_model.exists() or adapter.exists()):
        return {"success": False,
                "error": (f"Nessun artefatto esportabile nel job '{job_id}'. "
                          f"Cercati: {merged.name}/, {full_model.name}/, {adapter.name}/ "
                          f"sotto {output}.")}

    if merged.exists():
        modelfile_content = (f"FROM {str(merged).replace(chr(92), '/')}\n"
                             f"PARAMETER temperature 0.7\nPARAMETER top_p 0.9\n"
                             f'SYSTEM """{system_prompt}"""\n')
        source = "merged"
    elif full_model.exists():
        modelfile_content = (f"FROM {str(full_model).replace(chr(92), '/')}\n"
                             f"PARAMETER temperature 0.7\nPARAMETER top_p 0.9\n"
                             f'SYSTEM """{system_prompt}"""\n')
        source = "full"
    else:
        modelfile_content = (f"FROM {job.get('base_model', 'llama3')}\n"
                             f"ADAPTER {str(adapter).replace(chr(92), '/')}\n"
                             f"PARAMETER temperature 0.7\nPARAMETER top_p 0.9\n"
                             f'SYSTEM """{system_prompt}"""\n')
        source = "adapter"

    modelfile_path = job_dir / "Modelfile"
    modelfile_path.write_text(modelfile_content, encoding="utf-8")

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return {
            "success": False,
            "error": "Ollama non trovato nel PATH. Il Modelfile è comunque pronto: "
                     f"esegui `ollama create {model_name} -f \"{modelfile_path}\"`.",
            "modelfile_path": str(modelfile_path),
            "modelfile": modelfile_content,
        }

    # `ollama create` va atteso e il suo esito riportato: lanciarlo e ignorarlo
    # faceva sembrare riuscito un export che non produceva nulla.
    sub_run = _get_subprocess_run()
    try:
        res = sub_run([ollama_bin, "create", model_name, "-f", str(modelfile_path)],
                      capture_output=True, text=True, timeout=600)
    except Exception as exc:
        return {"success": False, "error": f"Esecuzione di ollama create fallita: {exc}",
                "modelfile_path": str(modelfile_path)}

    returncode = getattr(res, "returncode", 0)
    if returncode != 0:
        detail = ((getattr(res, "stderr", "") or "") + (getattr(res, "stdout", "") or "")).strip()
        return {
            "success": False,
            "error": f"ollama create ha restituito {returncode}: {detail[-400:] or 'nessun dettaglio'}",
            "model_name": model_name,
            "modelfile_path": str(modelfile_path),
            "modelfile": modelfile_content,
        }

    return {
        "success": True,
        "message": (f"Modello Ollama '{model_name}' registrato (sorgente: {source})."
                    + fp16_warning),
        "fp16_warning": fp16_warning or None,
        "model_name": model_name,
        "source": source,
        "modelfile_path": str(modelfile_path),
        "modelfile": modelfile_content,
    }
