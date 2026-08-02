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

import hashlib
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
from core.training.datasets import HF_DATASET_CONFIGS, LEGACY_HF_DATASETS

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
    "merge_adapter": ["torch", "peft", "transformers"],
}

METHOD_LABELS = {
    "lora_unsloth": "LoRA / QLoRA (Unsloth)",
    "trl_sft": "SFT (TRL + PEFT)",
    "full_pretrain": "Pre-training completo",
    "fwe_gradus": "Gradus FWE (generatore di pesi)",
    "slm_forge": "SLM Forge (modello da zero)",
    "script_custom": "Script custom",
    "merge_adapter": "Merge dell'adapter nel modello",
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


# Versione del template da cui nasce uno script, scritta come prima riga del
# file generato: serve a riconoscere gli script vecchi quando il template viene
# corretto (vedi _sync_script_template).
_TEMPLATE_TAG_RE = re.compile(r"^# SIGMA_TEMPLATE: ([0-9a-f]+)", re.MULTILINE)


def _template_fingerprint(method: str) -> str:
    template = SCRIPT_TEMPLATES.get(method, SCRIPT_TEMPLATES["script_custom"])
    return hashlib.sha1(template.encode("utf-8")).hexdigest()[:12]


def _render_script(method: str, values: dict) -> str:
    """Render a job script, tagged with the template version it came from."""
    template = SCRIPT_TEMPLATES.get(method, SCRIPT_TEMPLATES["script_custom"])
    return f"# SIGMA_TEMPLATE: {_template_fingerprint(method)}\n" + _render(template, values)


# ============================================================ base model

# Repo id HuggingFace: "owner/nome" o "nome". I due punti non sono ammessi —
# è proprio quello che distingue un repo da un tag Ollama.
_HF_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,94}"
                         r"(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,94})?$")


def resolve_base_model(model_id: str) -> str:
    """Normalise the base model id, or explain why it can't be trained.

    Il selettore elenca anche i modelli installati in Ollama, ma quelli sono
    blob GGUF: nessun trainer li sa caricare, e un tag Ollama
    ("owner/nome:latest") non è nemmeno un repo id valido, quindi
    `from_pretrained` muore con un HFValidationError illeggibile a run già
    avviato. Meglio intercettarlo qui, mentre l'utente ha ancora il form
    davanti.
    """
    name = (model_id or "").strip().replace("\\", "/").rstrip("/")
    if not name:
        raise ValueError("Nessun modello base selezionato.")
    if Path(name).is_dir():
        return name
    if _HF_REPO_RE.match(name):
        return name

    if ":" in name:
        stem = name.rsplit(":", 1)[0].rsplit("/", 1)[-1]
        raise ValueError(
            f"'{model_id}' è un tag Ollama, non un modello addestrabile. "
            "Ollama conserva solo pesi GGUF quantizzati, che né TRL+PEFT né "
            "Unsloth sanno caricare: il fine-tuning parte dai safetensors "
            f"originali. Cerca '{stem}' su huggingface.co e incolla il repo id "
            "(es. 'owner/Nome-Modello') in «Modello Custom».")

    raise ValueError(
        f"'{model_id}' non è un repo id HuggingFace valido né una cartella "
        "locale di pesi. Usa 'owner/nome' oppure il percorso di una directory "
        "che contenga config.json.")


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
                # Config accertato interrogando HuggingFace alla registrazione:
                # vale piu' della tabella di default, che copre solo i casi noti.
                "config": meta.get("config", ""),
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
        # Molti dataset (gsm8k, wikitext, cnn_dailymail...) sono divisi in
        # sottoinsiemi e senza config load_dataset si rifiuta di indovinare.
        configs = json.loads(r"""{dataset_configs_json}""")

        # Config accertato alla registrazione del dataset: batte la tabella.
        declared = "{dataset_config}"

        def _load_hf(repo):
            name = declared or configs.get(repo)
            try:
                return load_dataset(repo, name, split="{dataset_split}")
            except ValueError as exc:
                if name or "onfig name is missing" not in str(exc):
                    raise
                from datasets import get_dataset_config_names
                available = get_dataset_config_names(repo)
                if not available:
                    raise
                sigma("Dataset '%s' ha piu' config %s: uso '%s'"
                      % (repo, available, available[0]))
                return load_dataset(repo, available[0], split="{dataset_split}")

        try:
            ds = _load_hf(path)
        except Exception as exc:
            alt = legacy.get(path.lower())
            if not alt:
                raise
            sigma("Dataset '%s' spostato su '%s' (%s): riprovo" % (path, alt, type(exc).__name__))
            ds = _load_hf(alt)
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
    # gsm8k, squad e simili. Senza questo ramo il fallback prenderebbe la prima
    # colonna stringa — la domanda — e si addestrerebbe senza mai la risposta.
    for q, a in (("question", "answer"), ("question", "answers"), ("input", "output")):
        if {q, a} <= cols:
            sigma("Formato %s/%s rilevato -> text" % (q, a))
            return ds.map(
                lambda ex, q=q, a=a: {
                    "text": "### Istruzione:\\n" + str(ex[q]) + "\\n\\n### Risposta:\\n" + str(ex[a])},
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


VALIDATION_FRACTION = {validation_fraction}
MAX_EXAMPLES = {max_examples}


def load_train_and_eval():
    """Dataset di training piu' la fetta tenuta da parte per la validation.

    Senza dati mai visti la loss non distingue fra "ha imparato il compito" e
    "ha imparato gli esempi": la validation e' l'unico modo per accorgersi
    dell'overfitting mentre il run e' ancora in corso. Il seed e' fisso, cosi'
    due run sullo stesso dataset restano confrontabili fra loro.
    """
    ds = load_training_dataset()

    # Sottoinsieme: su un dataset da centinaia di migliaia di esempi un'epoca
    # intera dura ore, e per specializzare un modello quasi mai serve tutto.
    # Il taglio e' deterministico (seed fisso) e mescolato, non i primi N: i
    # dataset sono spesso ordinati per categoria, e prendere la testa
    # significherebbe addestrare su una fetta sola del compito.
    if 0 < MAX_EXAMPLES < len(ds):
        ds = ds.shuffle(seed=42).select(range(MAX_EXAMPLES))
        sigma("Sottoinsieme: %d esempi estratti (seed 42)" % len(ds))

    if VALIDATION_FRACTION <= 0:
        return ds, None
    # Sotto qualche decina di esempi la fetta di validation sarebbe cosi'
    # piccola che la sua loss oscillerebbe piu' del segnale che deve misurare.
    if len(ds) < 40:
        sigma("Dataset di %d esempi: validation disattivata (troppo pochi)" % len(ds))
        return ds, None
    split = ds.train_test_split(test_size=VALIDATION_FRACTION, seed=42)
    sigma("Split: %d esempi di training, %d di validation (%.0f%%)" % (
        len(split["train"]), len(split["test"]), VALIDATION_FRACTION * 100))
    return split["train"], split["test"]
'''


_SIGMA_CALLBACK = '''
import math
from transformers import TrainerCallback


def sigma_metric(**fields):
    """Riga machine-readable per il Monitor, accanto a quella leggibile.

    Il Monitor legge questa invece di dedurre i numeri con una regex sul testo:
    aggiungere una metrica non richiede piu' toccare il parser, e i valori
    arrivano senza passare da un arrotondamento di formattazione.
    """
    clean = {k: v for k, v in fields.items() if v is not None}
    try:
        print("[SIGMA-METRIC] " + json.dumps(clean), flush=True)
    except (TypeError, ValueError):
        pass


class SigmaProgress(TrainerCallback):
    """Log parsabile dal Monitor del Training Lab (loss, epoca, VRAM, ETA)."""

    def __init__(self):
        self.t0 = time.time()
        # Tempi degli ultimi step, per una stima che segua l'andamento reale.
        self.recent = []
        # Step visti *da questo processo*. Dopo una ripresa `global_step` parte
        # dal checkpoint (301, 500...) mentre il cronometro parte da zero:
        # dividere il tempo per `global_step` dava frazioni di secondo per step
        # e un "ETA 0m" su un run di ore.
        self.seen = 0

    def on_evaluate(self, args, state, control, metrics=None, **kw):
        metrics = metrics or {}
        eval_loss = metrics.get("eval_loss")
        if eval_loss is None:
            return
        # exp() di una loss grande esplode e il numero smette di dire qualcosa:
        # oltre 20 la perplexity significa comunque "non ne ha idea".
        ppl = math.exp(min(float(eval_loss), 20.0)) if eval_loss > 0 else None
        sigma("Validation step %d - eval_loss: %.4f | perplexity: %s" % (
            state.global_step, eval_loss, ("%.2f" % ppl) if ppl else "n/d"))
        sigma_metric(step=state.global_step, epoch=state.epoch,
                     eval_loss=float(eval_loss), perplexity=ppl,
                     eval_runtime=metrics.get("eval_runtime"))

    def on_log(self, args, state, control, logs=None, **kw):
        logs = logs or {}
        if "loss" not in logs:
            return
        epoch = float(logs.get("epoch", state.epoch or 0))
        total = float(args.num_train_epochs or 1)
        pct = 100.0 * state.global_step / max(1, state.max_steps)
        vram = ""
        used_gb = total_gb = None
        if torch.cuda.is_available():
            used_gb = torch.cuda.max_memory_allocated() / 1024**3
            total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            vram = " | VRAM %.1f/%.1f GB" % (used_gb, total_gb)
        # La VRAM va nella serie, non solo nel testo: e' l'unico modo perche' il
        # Monitor possa accorgersi da solo che la scheda e' satura.
        sigma_metric(step=state.global_step, epoch=logs.get("epoch", state.epoch),
                     loss=logs.get("loss"),
                     learning_rate=logs.get("learning_rate"),
                     grad_norm=logs.get("grad_norm"),
                     vram_gb=round(used_gb, 2) if used_gb else None,
                     vram_total_gb=round(total_gb, 2) if total_gb else None,
                     elapsed_s=round(time.time() - self.t0, 1))
        now = time.time()
        self.seen += 1
        self.recent.append(now)
        if len(self.recent) > 21:
            self.recent.pop(0)
        eta = ""
        if state.global_step:
            # La stima guarda gli ultimi step, non la media dall'inizio: se il
            # training rallenta — VRAM esaurita, throttling — una media di vita
            # continua a promettere il tempo di quando andava bene, e il crollo
            # resta invisibile proprio quando servirebbe vederlo.
            if len(self.recent) >= 3:
                per_step = (self.recent[-1] - self.recent[0]) / (len(self.recent) - 1)
            elif self.seen > 1:
                per_step = (now - self.t0) / (self.seen - 1)
            else:
                per_step = 0.0
            eta = (" | ETA %dm" % int(per_step * (state.max_steps - state.global_step) / 60)
                   if per_step > 0 else " | ETA —")
            lifetime = (now - self.t0) / max(1, self.seen - 1)
            # Un rallentamento di questa entita' non e' rumore: va detto.
            if per_step > lifetime * 2.5 and self.seen > 20:
                eta += " (RALLENTATO: %.0fs/step contro %.0fs iniziali)" % (per_step, lifetime)
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
RESUME_ADAPTER = r"{resume_adapter}"

# Continuazione: si riparte dall'adapter del job precedente invece che da uno
# nuovo. Unsloth risale da solo al modello base leggendo adapter_config.json,
# quindi qui basta puntargli la cartella dell'adapter.
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=RESUME_ADAPTER or "{base_model}",
    max_seq_length={max_seq_length},
    dtype=DTYPE,
    load_in_4bit=bool(TUNE.get("load_in_4bit")),
)
sigma("Modello caricato (4-bit=%s)" % TUNE.get("load_in_4bit"))

if RESUME_ADAPTER:
    sigma("Riprendo l'adapter LoRA da: %s" % RESUME_ADAPTER)
    FastLanguageModel.for_training(model)
else:
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


# Ogni valutazione e' un passaggio completo sulla fetta di validation: a cadenza
# fissa, su un run lungo, diventa la voce di costo principale. Qui la cadenza si
# adatta perche' il numero di valutazioni resti circa costante — abbastanza da
# vedere la curva, non tante da rallentare il training.
TARGET_EVALS = 18


def eval_interval(n_examples):
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    return max({eval_steps}, int(steps / TARGET_EVALS) or {eval_steps})


def save_interval(n_examples):
    """Ogni quanti step lasciare un checkpoint da cui poter ripartire."""
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    # Almeno 20 punti di ripresa, mai piu' fitti di 100 step (scrivere un
    # checkpoint costa) e mai piu' radi di 2000 (perderne di piu' fa male).
    return int(min(2000, max(100, steps // 20)))

train_dataset, eval_dataset = load_train_and_eval()
EVAL_EVERY = eval_interval(len(train_dataset))
SAVE_EVERY = save_interval(len(train_dataset))
sigma("Checkpoint ogni %d step in %s" % (SAVE_EVERY, r"{output_dir}"))
if eval_dataset is not None:
    sigma("Validation ogni %d step su %d esempi tenuti da parte"
          % (EVAL_EVERY, len(eval_dataset)))

trainer = SFTTrainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    processing_class=tokenizer,
    args=SFTConfig(
        output_dir=r"{output_dir}",
        dataset_text_field="text",
        eval_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=EVAL_EVERY,
        # La valutazione non calcola gradienti: puo' usare batch piu' larghi del
        # training senza rischiare la VRAM, e ci mette molto meno.
        per_device_eval_batch_size=max(1, {batch_size} * 2),
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
        # Salvare a fine epoca sembra ragionevole finche' un'epoca non dura
        # 47.000 step: un run fermato prima non lascia nulla, e ore di GPU
        # spariscono. Si salva a intervalli di step, calcolati perche' i
        # checkpoint restino pochi ma non lontanissimi fra loro.
        save_strategy="steps",
        save_steps=SAVE_EVERY,
        save_total_limit=2,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

sigma("Inizio training LoRA...")
# Riavviare un job fermato deve riprendere da dove si era interrotto, non
# ributtare via le ore gia' fatte: se in output c'e' un checkpoint, si riparte
# da quello — stato dell'ottimizzatore e scheduler compresi.
def _last_checkpoint(folder):
    if not os.path.isdir(folder):
        return None
    found = [d for d in os.listdir(folder)
             if d.startswith("checkpoint-") and d.split("-")[-1].isdigit()]
    if not found:
        return None
    return os.path.join(folder, max(found, key=lambda d: int(d.split("-")[-1])))


RESUME_FROM = _last_checkpoint(r"{output_dir}")
if RESUME_FROM:
    sigma("Riprendo dal checkpoint %s" % os.path.basename(RESUME_FROM))
result = trainer.train(resume_from_checkpoint=RESUME_FROM)
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

    # ------------------------------------------------------- merge adapter
    # Fondere l'adapter nel modello base produce un modello autonomo, che
    # diventa il punto di partenza della fase successiva della catena. E' un
    # job come gli altri — ha il suo log, il suo esito e si puo' rifare — invece
    # di essere una coda opzionale del training, dove un fallimento passava
    # inosservato e lasciava la catena senza il suo anello.
    "merge_adapter": _PREAMBLE + '''
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
except ImportError as e:
    sigma("ERRORE dipendenza mancante: %s" % e)
    sigma("Installa con: pip install peft transformers")
    sys.exit(1)

ADAPTER = r"{resume_adapter}"
TARGET = r"{output_dir}" + "/merged_16bit"

if not ADAPTER or not os.path.isdir(ADAPTER):
    sigma("ERRORE: adapter non trovato in %s" % ADAPTER)
    sys.exit(1)

sigma("Base: {base_model}")
sigma("Adapter: %s" % ADAPTER)

# Il merge va fatto sui pesi a 16 bit, mai su una base quantizzata a 4: la
# quantizzazione e' servita per far stare il training in VRAM, ma fondere
# dentro pesi gia' degradati vi inchioderebbe la perdita per sempre.
model = AutoModelForCausalLM.from_pretrained(
    "{base_model}", dtype=DTYPE, device_map="cpu", low_cpu_mem_usage=True)
sigma("Modello base caricato in %s su CPU" % DTYPE)

model = PeftModel.from_pretrained(model, ADAPTER)
sigma("Adapter applicato, fusione in corso...")
model = model.merge_and_unload()

os.makedirs(TARGET, exist_ok=True)
model.save_pretrained(TARGET, safe_serialization=True)

try:
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER)
except Exception:
    tokenizer = AutoTokenizer.from_pretrained("{base_model}")
tokenizer.save_pretrained(TARGET)

total = sum(
    os.path.getsize(os.path.join(TARGET, f))
    for f in os.listdir(TARGET) if os.path.isfile(os.path.join(TARGET, f)))
sigma("Modello fuso salvato in %s (%.1f GB)" % (TARGET, total / 1024**3))
sigma("FATTO")
''',

    # ---------------------------------------------------------------- TRL SFT
    "trl_sft": _PREAMBLE + _DATASET_LOADER + '''
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import (LoraConfig, PeftModel, get_peft_model,
                      prepare_model_for_kbit_training)
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

RESUME_ADAPTER = r"{resume_adapter}"

if RESUME_ADAPTER:
    # Continuazione: `is_trainable` e' obbligatorio, altrimenti PEFT carica
    # l'adapter in sola inferenza e il run girerebbe senza aggiornare nulla.
    sigma("Riprendo l'adapter LoRA da: %s" % RESUME_ADAPTER)
    model = PeftModel.from_pretrained(model, RESUME_ADAPTER, is_trainable=True)
else:
    model = get_peft_model(model, LoraConfig(
        r={lora_r}, lora_alpha={lora_alpha}, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    ))
model.print_trainable_parameters()


# Ogni valutazione e' un passaggio completo sulla fetta di validation: a cadenza
# fissa, su un run lungo, diventa la voce di costo principale. Qui la cadenza si
# adatta perche' il numero di valutazioni resti circa costante — abbastanza da
# vedere la curva, non tante da rallentare il training.
TARGET_EVALS = 18


def eval_interval(n_examples):
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    return max({eval_steps}, int(steps / TARGET_EVALS) or {eval_steps})


def save_interval(n_examples):
    """Ogni quanti step lasciare un checkpoint da cui poter ripartire."""
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    # Almeno 20 punti di ripresa, mai piu' fitti di 100 step (scrivere un
    # checkpoint costa) e mai piu' radi di 2000 (perderne di piu' fa male).
    return int(min(2000, max(100, steps // 20)))

train_dataset, eval_dataset = load_train_and_eval()
EVAL_EVERY = eval_interval(len(train_dataset))
SAVE_EVERY = save_interval(len(train_dataset))
sigma("Checkpoint ogni %d step in %s" % (SAVE_EVERY, r"{output_dir}"))
if eval_dataset is not None:
    sigma("Validation ogni %d step su %d esempi tenuti da parte"
          % (EVAL_EVERY, len(eval_dataset)))

trainer = SFTTrainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    processing_class=tokenizer,
    args=SFTConfig(
        output_dir=r"{output_dir}",
        dataset_text_field="text",
        eval_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=EVAL_EVERY,
        # La valutazione non calcola gradienti: puo' usare batch piu' larghi del
        # training senza rischiare la VRAM, e ci mette molto meno.
        per_device_eval_batch_size=max(1, {batch_size} * 2),
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
        # Salvare a fine epoca sembra ragionevole finche' un'epoca non dura
        # 47.000 step: un run fermato prima non lascia nulla, e ore di GPU
        # spariscono. Si salva a intervalli di step, calcolati perche' i
        # checkpoint restino pochi ma non lontanissimi fra loro.
        save_strategy="steps",
        save_steps=SAVE_EVERY,
        save_total_limit=2,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

sigma("Inizio training SFT...")
# Riavviare un job fermato deve riprendere da dove si era interrotto, non
# ributtare via le ore gia' fatte: se in output c'e' un checkpoint, si riparte
# da quello — stato dell'ottimizzatore e scheduler compresi.
def _last_checkpoint(folder):
    if not os.path.isdir(folder):
        return None
    found = [d for d in os.listdir(folder)
             if d.startswith("checkpoint-") and d.split("-")[-1].isdigit()]
    if not found:
        return None
    return os.path.join(folder, max(found, key=lambda d: int(d.split("-")[-1])))


RESUME_FROM = _last_checkpoint(r"{output_dir}")
if RESUME_FROM:
    sigma("Riprendo dal checkpoint %s" % os.path.basename(RESUME_FROM))
result = trainer.train(resume_from_checkpoint=RESUME_FROM)
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

# Qui lo split va fatto sui blocchi, non sui testi grezzi: e' sui blocchi che
# il modello viene valutato, e sono loro l'unita' di misura della perplexity.
eval_dataset = None
train_blocks = lm_dataset
if VALIDATION_FRACTION > 0 and len(lm_dataset) >= 40:
    split = lm_dataset.train_test_split(test_size=VALIDATION_FRACTION, seed=42)
    train_blocks, eval_dataset = split["train"], split["test"]
    sigma("Split: %d blocchi di training, %d di validation" % (
        len(train_blocks), len(eval_dataset)))


# Ogni valutazione e' un passaggio completo sulla fetta di validation: a cadenza
# fissa, su un run lungo, diventa la voce di costo principale. Qui la cadenza si
# adatta perche' il numero di valutazioni resti circa costante — abbastanza da
# vedere la curva, non tante da rallentare il training.
TARGET_EVALS = 18


def eval_interval(n_examples):
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    return max({eval_steps}, int(steps / TARGET_EVALS) or {eval_steps})


def save_interval(n_examples):
    """Ogni quanti step lasciare un checkpoint da cui poter ripartire."""
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    # Almeno 20 punti di ripresa, mai piu' fitti di 100 step (scrivere un
    # checkpoint costa) e mai piu' radi di 2000 (perderne di piu' fa male).
    return int(min(2000, max(100, steps // 20)))

EVAL_EVERY = eval_interval(len(train_blocks))
SAVE_EVERY = save_interval(len(train_blocks))
sigma("Checkpoint ogni %d step in %s" % (SAVE_EVERY, r"{output_dir}"))
if eval_dataset is not None:
    sigma("Validation ogni %d step su %d blocchi tenuti da parte"
          % (EVAL_EVERY, len(eval_dataset)))

trainer = Trainer(
    model=model,
    train_dataset=train_blocks,
    eval_dataset=eval_dataset,
    data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    args=TrainingArguments(
        output_dir=r"{output_dir}",
        eval_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=EVAL_EVERY,
        # La valutazione non calcola gradienti: puo' usare batch piu' larghi del
        # training senza rischiare la VRAM, e ci mette molto meno.
        per_device_eval_batch_size=max(1, {batch_size} * 2),
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
        # Salvare a fine epoca sembra ragionevole finche' un'epoca non dura
        # 47.000 step: un run fermato prima non lascia nulla, e ore di GPU
        # spariscono. Si salva a intervalli di step, calcolati perche' i
        # checkpoint restino pochi ma non lontanissimi fra loro.
        save_strategy="steps",
        save_steps=SAVE_EVERY,
        save_total_limit=2,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

sigma("Inizio pre-training...")
# Riavviare un job fermato deve riprendere da dove si era interrotto, non
# ributtare via le ore gia' fatte: se in output c'e' un checkpoint, si riparte
# da quello — stato dell'ottimizzatore e scheduler compresi.
def _last_checkpoint(folder):
    if not os.path.isdir(folder):
        return None
    found = [d for d in os.listdir(folder)
             if d.startswith("checkpoint-") and d.split("-")[-1].isdigit()]
    if not found:
        return None
    return os.path.join(folder, max(found, key=lambda d: int(d.split("-")[-1])))


RESUME_FROM = _last_checkpoint(r"{output_dir}")
if RESUME_FROM:
    sigma("Riprendo dal checkpoint %s" % os.path.basename(RESUME_FROM))
result = trainer.train(resume_from_checkpoint=RESUME_FROM)
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
    """I job dal piu' recente al piu' vecchio.

    L'ordine non era mai stato imposto: la lista usciva nell'ordine di
    inserimento, cioe' dal piu' vecchio. La UI apriva quindi sul primo job mai
    creato invece che sull'ultimo, e il test che avrebbe dovuto accorgersene
    passava per caso — tre job creati nello stesso secondo hanno la stessa data,
    e qualunque ordine soddisfa il confronto.
    """
    jobs = _load_jobs()
    ordered = sorted(jobs.values(),
                     key=lambda j: (j.get("created_ts") or 0.0, j.get("created_at") or ""),
                     reverse=True)
    return {"success": True, "jobs": ordered, "total": len(ordered)}


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


def _default_eval_steps(hyper: dict) -> int:
    """How often to evaluate, when the user hasn't said.

    Ogni valutazione e' un passaggio completo sulla fetta di validation: troppo
    frequente e il run rallenta, troppo rara e l'overfitting si scopre quando e'
    gia' avvenuto. 50 step e' il compromesso che regge sia i run brevi sia
    quelli lunghi, e con 3 valutazioni la diagnosi comincia a essere affidabile.
    """
    return max(10, int(hyper.get("logging_steps", 1)) * 50)


def _build_script_values(data: dict, job_id: str, job_dir: Path) -> dict:
    """Every placeholder the script templates need, for a given job request.

    Shared by job creation and by the regeneration that extends an existing run,
    so an extended job gets exactly the script it would get if created now.
    """
    method = data.get("method", "lora_unsloth")
    model_base = resolve_base_model(
        data.get("base_model") or data.get("model_base", "unsloth/llama-3.2-3b-instruct"))
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
        "dataset_config": dataset.get("config", "") or "",
        "output_dir": str(output_dir).replace("\\", "/"),
        "num_epochs": num_epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "gradient_accumulation": grad_accum,
        "max_seq_length": seq_len,
        "lora_r": hyper.get("lora_r", 16),
        "lora_alpha": hyper.get("lora_alpha", 16),
        "resume_adapter": str(hyper.get("resume_adapter") or "").replace("\\", "/"),
        "validation_fraction": float(hyper.get("validation_fraction", 0.05)),
        "max_examples": int(hyper.get("max_examples") or 0),
        "eval_steps": int(hyper.get("eval_steps") or _default_eval_steps(hyper)),
        "text_field": hyper.get("text_field", "text"),
        "tune_json": json.dumps(tune, ensure_ascii=False),
        "legacy_datasets_json": json.dumps(LEGACY_HF_DATASETS, ensure_ascii=False),
        "dataset_configs_json": json.dumps(HF_DATASET_CONFIGS, ensure_ascii=False),
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
    dataset_id = data.get("dataset_id", "local_dataset")
    hyper = data.get("hyperparams") or data.get("config") or {}

    # Il modello base va validato prima di creare la cartella del job: un tag
    # Ollama non è addestrabile e l'utente deve saperlo adesso, non a training
    # avviato.
    try:
        model_base = resolve_base_model(
            data.get("base_model") or data.get("model_base", "unsloth/llama-3.2-3b-instruct"))
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    job_id = uuid.uuid4().hex[:8]
    job_dir = target_jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    values = _build_script_values(data, job_id, job_dir)
    tune = values["_tune"]
    visible_indices = values["_visible_indices"]
    dataset = values["_dataset"]
    batch_size, grad_accum = values["batch_size"], values["gradient_accumulation"]
    num_epochs, learning_rate = values["num_epochs"], values["learning_rate"]

    script_path = job_dir / "train_script.py"
    script_path.write_text(_render_script(method, values), encoding="utf-8")

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
        # `created_at` ha la granularita' del secondo: due job creati di fila
        # hanno la stessa stringa e l'ordinamento fra loro sarebbe arbitrario.
        # L'id non aiuta, e' un esadecimale casuale senza senso cronologico.
        "created_ts": time.time(),
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
    runs = job.get("runs") or []
    if runs and runs[-1].get("status") == "running":
        runs[-1].update({"status": final, "completed_at": job["completed_at"],
                         "final_loss": (state or job).get("last_loss"),
                         "steps": (state or job).get("current_step")})
    _save_jobs(jobs)
    log.info("Job %s terminato: %s (exit %s)", job_id, final, code)


def get_job_metrics(job_id: str) -> dict:
    """Metric series, aggregates and verdicts for one job."""
    job = _load_jobs().get(job_id)
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    from core.training.metrics import job_metrics
    return job_metrics(job)


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
        script_path.write_text(_render_script(data.get("method"), values), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Rigenerazione dello script fallita: {exc}"}

    log.info("Job %s: script rigenerato per %d step totali", job["id"], total_steps)
    return {"success": True, "regenerated": True}


# I due modi di proseguire un fine-tuning. Cambiano da dove ripartono i pesi,
# e quindi cosa il modello si porta dietro del giro precedente.
CONTINUATION_MODES = {
    "resume_adapter": {
        "label": "Riprendi lo stesso adapter LoRA",
        "detail": ("Il nuovo run continua ad addestrare l'adapter esistente: il "
                   "modello accumula quello che ha gia' imparato. Con un dataset "
                   "molto diverso puo' dimenticare il precedente."),
        "needs": "lora_model",
    },
    "fresh_adapter": {
        "label": "Nuovo adapter sul modello gia' fuso",
        "detail": ("Riparte da zero con un adapter pulito, ma sopra il modello in "
                   "cui il lavoro precedente e' gia' stato fuso. Ogni fase resta "
                   "separata e ispezionabile; serve il merge (~18 GB su disco)."),
        "needs": "merged_16bit",
    },
}


def _available_actions(job: dict, artifacts: dict) -> list[str]:
    """What can still be done to a stage, given what it produced."""
    status = job.get("status")
    method = job.get("method")
    actions = []
    if status in ("ready", "stopped", "failed"):
        actions.append("start")
        # I parametri si cambiano solo a run fermo: un processo sospeso
        # riprende con la configurazione che ha in memoria, non con quella nuova.
        if method not in ("merge_adapter", "script_custom"):
            actions.append("tune")
    if status == "running":
        return ["pause", "stop"]
    if status == "paused":
        return ["resume", "stop"]
    if status not in ("completed", "stopped"):
        return actions
    if method != "merge_adapter" and artifacts["adapter"]:
        actions += ["merge", "continue"]
    if method == "merge_adapter" and artifacts["merged"]:
        # Da una fase fusa si riparte solo con un adapter nuovo.
        actions.append("continue")
    if artifacts["merged"] or artifacts["adapter"] or artifacts["gguf"]:
        actions.append("export")
    if artifacts["merged"] or artifacts["gguf"]:
        actions.append("benchmark")
    actions.append("delete")
    return actions


def get_job_lineage(job_id: str) -> dict:
    """The whole chain a stage belongs to, from the first run to the last.

    Una catena di specializzazioni (LoRA, merge, LoRA, merge...) e' leggibile
    solo tutta insieme: serve a vedere se una fase ha davvero migliorato quella
    prima, e a sapere cosa si puo' ancora fare su ciascuna.
    """
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}

    # Si risale al capostipite e poi si ridiscende lungo i figli che stanno
    # sulla stessa linea, cosi' un ramo abbandonato non sporca la catena.
    root = job_id
    seen = set()
    while root not in seen:
        seen.add(root)
        parent = jobs.get(root, {}).get("parent_job_id")
        if not parent or parent not in jobs:
            break
        root = parent

    chain, cursor = [], root
    visited = set()
    while cursor and cursor in jobs and cursor not in visited:
        visited.add(cursor)
        chain.append(cursor)
        children = [c for c in jobs[cursor].get("children", []) if c in jobs]
        if not children:
            break
        # Se un ramo e' stato riprovato piu' volte si segue quello che porta al
        # job richiesto; in mancanza, l'ultimo creato.
        cursor = next((c for c in children if job_id in
                       ([c] + jobs[c].get("lineage", []) + jobs[c].get("children", []))),
                      children[-1])

    if job_id not in chain:
        chain.append(job_id)

    stages = []
    for index, jid in enumerate(chain):
        job = jobs[jid]
        artifacts = _stage_artifacts(job)
        stages.append({
            "index": index,
            "id": jid,
            "stage_name": job.get("stage_name") or "",
            "name": job.get("name") or jid,
            "kind": "merge" if job.get("method") == "merge_adapter" else "train",
            "method": job.get("method"),
            "method_label": job.get("method_label"),
            "base_model": job.get("base_model"),
            "dataset_name": job.get("dataset_name") or job.get("dataset_id") or "",
            "status": job.get("status"),
            "created_at": job.get("created_at"),
            "completed_at": job.get("completed_at"),
            "last_loss": job.get("last_loss"),
            "hyperparams": {k: v for k, v in (job.get("hyperparams") or {}).items()
                            if k in ("batch_size", "gradient_accumulation",
                                     "max_seq_length", "num_epochs", "learning_rate")},
            "artifacts": artifacts,
            "actions": _available_actions(job, artifacts),
            "is_current": jid == job_id,
        })

    return {"success": True, "job_id": job_id, "root": root, "stages": stages}


def _stage_artifacts(job: dict) -> dict:
    """Which artefacts a job actually produced, checked on disk."""
    output = Path(job.get("dir", "")) / "output"
    return {
        "adapter": (output / "lora_model").is_dir(),
        "merged": (output / "merged_16bit").is_dir(),
        "gguf": bool(list(output.glob("*.gguf"))) if output.is_dir() else False,
    }


def merge_job_adapter(job_id: str, data: dict | None = None) -> dict:
    """Fuse a job's LoRA adapter into its base model, as its own job.

    E' l'anello che rende una catena di specializzazioni percorribile: il
    modello fuso e' autonomo, si puo' valutare da solo e diventa la base della
    fase seguente. Girando come job separato ha log, stato ed esito propri, e
    puo' essere rifatto senza ripetere il training.
    """
    data = dict(data or {})
    parent = _load_jobs().get(job_id)
    if parent is None:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    if parent.get("status") == "running":
        return {"success": False,
                "error": f"Job '{job_id}' è in esecuzione: aspetta che finisca."}

    adapter = Path(parent.get("dir", "")) / "output" / "lora_model"
    if not adapter.is_dir():
        return {"success": False,
                "error": (f"Il job '{job_id}' non ha un adapter da fondere "
                          f"({adapter} non esiste). Il training è arrivato in fondo?")}

    stage_name = (data.get("stage_name") or "").strip()
    request = {
        "base_model": parent.get("base_model"),
        "method": "merge_adapter",
        "dataset_id": "",
        "name": stage_name or f"Merge di {parent.get('name', job_id)}",
        "output_name": data.get("output_name"),
        "hyperparams": {"resume_adapter": str(adapter)},
    }
    created = create_training_job(request)
    if not created.get("success"):
        return created

    jobs = _load_jobs()
    child = jobs[created["job_id"]]
    child["parent_job_id"] = job_id
    child["source_job_id"] = job_id
    child["stage_name"] = stage_name
    # Il metodo di training da usare quando questa fase verra' proseguita:
    # il merge non e' un metodo di addestramento, lo eredita da chi l'ha prodotto.
    child["train_method"] = parent.get("train_method") or parent.get("method")
    child["lineage"] = list(parent.get("lineage") or [])
    if job_id not in child["lineage"]:
        child["lineage"].append(job_id)
    jobs[job_id].setdefault("children", []).append(created["job_id"])
    _save_jobs(jobs)

    started = start_training_job(created["job_id"])
    if not started.get("success"):
        return {"success": False,
                "error": f"Job di merge creato ma non avviato: {started.get('error')}",
                "job_id": created["job_id"]}

    log.info("Job %s: merge dell'adapter di %s avviato", created["job_id"], job_id)
    return {"success": True, "job_id": created["job_id"], "job": jobs[created["job_id"]],
            "parent_job_id": job_id,
            "message": (f"Merge avviato ({created['job_id']}). Al termine il modello "
                        f"fuso sarà la base della fase successiva.")}


def continue_training_job(job_id: str, data: dict | None = None) -> dict:
    """Chain a new run onto a finished job, keeping what it learned.

    Non si riusa il job di partenza: il suo log, le sue metriche e i suoi
    checkpoint restano quello che sono stati, e il nuovo giro nasce come job a
    se' con un riferimento al padre. Cosi' la storia di una catena di training
    resta leggibile anche a distanza di settimane, invece di essere un unico
    job che si e' sovrascritto piu' volte.
    """
    data = dict(data or {})
    parent = _load_jobs().get(job_id)
    if parent is None:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    if parent.get("status") == "running":
        return {"success": False,
                "error": f"Job '{job_id}' è ancora in esecuzione: fermalo prima di continuarlo."}

    mode = data.get("mode") or "resume_adapter"
    method = parent.get("method")

    if method == "merge_adapter":
        # Da una fase fusa non c'e' un adapter da riprendere: quel lavoro e'
        # gia' dentro i pesi. Si riparte per forza con un adapter nuovo, e il
        # metodo di training lo si eredita da chi ha prodotto la fase.
        mode = "fresh_adapter"
        method = parent.get("train_method") or "lora_unsloth"
    elif method not in ("lora_unsloth", "trl_sft"):
        return {"success": False,
                "error": (f"La continuazione è prevista per i metodi LoRA e SFT; "
                          f"questo job usa '{method}'.")}

    if mode not in CONTINUATION_MODES:
        return {"success": False,
                "error": (f"Modalità '{mode}' sconosciuta. "
                          f"Disponibili: {', '.join(CONTINUATION_MODES)}.")}

    output = Path(parent.get("dir", "")) / "output"
    artifact = output / CONTINUATION_MODES[mode]["needs"]
    if not artifact.exists():
        missing = CONTINUATION_MODES[mode]["needs"]
        hint = ("Il merge a 16 bit non è stato prodotto: riprendi l'adapter, "
                "oppure rifai l'export dal job padre."
                if mode == "fresh_adapter" else
                "Il job non ha salvato un adapter: è arrivato in fondo al training?")
        return {"success": False,
                "error": f"Manca {missing}/ in {output}. {hint}"}

    # Gli iperparametri di partenza sono quelli del training, non quelli del
    # merge: un job di merge porta in `request` solo il percorso dell'adapter.
    source = parent
    if parent.get("method") == "merge_adapter":
        source = _load_jobs().get(parent.get("source_job_id") or "") or parent
    request = dict(source.get("request") or {})
    hyper = {**(request.get("hyperparams") or {}), **(data.get("hyperparams") or {})}
    if mode == "resume_adapter":
        hyper["resume_adapter"] = str(artifact)
        base_model = parent.get("base_model")
    else:
        # I pesi fusi sono gia' sul disco: il nuovo adapter parte da li'.
        hyper.pop("resume_adapter", None)
        base_model = str(artifact)

    child_request = {
        "base_model": base_model,
        "method": method,
        # Cambiare dataset e' il caso d'uso principale: se non ne arriva uno
        # nuovo si prosegue su quello di prima.
        "dataset_id": data.get("dataset_id") or parent.get("dataset_id", ""),
        "name": data.get("name") or f"{parent.get('name', job_id)} · continuazione",
        "output_name": data.get("output_name"),
        "hyperparams": hyper,
    }

    created = create_training_job(child_request)
    if not created.get("success"):
        return created

    jobs = _load_jobs()
    child = jobs[created["job_id"]]
    child["parent_job_id"] = job_id
    child["continuation_mode"] = mode
    child["stage_name"] = (data.get("stage_name") or "").strip()
    child["train_method"] = method
    child["lineage"] = list(parent.get("lineage") or [job_id])
    if job_id not in child["lineage"]:
        child["lineage"].append(job_id)
    jobs[job_id].setdefault("children", []).append(created["job_id"])
    _save_jobs(jobs)

    log.info("Job %s continua %s in modalità %s", created["job_id"], job_id, mode)
    return {"success": True, "job_id": created["job_id"], "job": child,
            "parent_job_id": job_id, "mode": mode,
            "message": (f"Nuovo job {created['job_id']} in coda a {job_id} "
                        f"({CONTINUATION_MODES[mode]['label'].lower()}).")}


def _sync_script_template(job: dict) -> bool:
    """Re-render the job script when it came from an older template version.

    Gli script sono file congelati su disco al momento della creazione: un job
    creato prima di una correzione al template la riavvia identica, e l'utente
    rivede lo stesso errore anche dopo aver aggiornato Sigma Studio. Il tag
    SIGMA_TEMPLATE in testa allo script dice da quale versione del template
    nasce; se non combacia con quella attuale lo script viene rigenerato dalla
    richiesta salvata. La cartella del run — e con essa i checkpoint — non viene
    toccata.

    `script_custom` resta escluso: quel template esiste proprio per essere
    modificato a mano, sovrascriverlo cancellerebbe il lavoro dell'utente.
    """
    method = job.get("method")
    request = job.get("request")
    script_path = Path(job.get("script_path", ""))
    if method == "script_custom" or method not in SCRIPT_TEMPLATES or not request:
        return False
    if not script_path.exists():
        return False

    try:
        source = script_path.read_text(encoding="utf-8")
    except Exception as exc:
        log.warning("Job %s: script illeggibile (%s)", job.get("id"), exc)
        return False

    tag = _TEMPLATE_TAG_RE.search(source)
    if tag and tag.group(1) == _template_fingerprint(method):
        return False

    data = dict(request)
    # Gli iperparametri salvati nel job includono quelli risolti alla creazione
    # (batch autotunato, step estesi di un run FWE) e devono avere la meglio.
    data["hyperparams"] = {**data.get("hyperparams", {}), **(job.get("hyperparams") or {})}
    try:
        values = _build_script_values(data, job["id"], Path(job["dir"]))
        script_path.write_text(_render_script(method, values), encoding="utf-8")
    except Exception as exc:
        # Meglio partire con lo script vecchio che non partire affatto.
        log.warning("Job %s: rigenerazione script fallita (%s), uso quello esistente",
                    job.get("id"), exc)
        return False

    log.info("Job %s: script rigenerato dal template aggiornato", job.get("id"))
    return True


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

    regenerated = _sync_script_template(job)

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
              + ("Script rigenerato dal template aggiornato.\n" if regenerated else "")
              + f"=====================================\n")
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
    # Storia delle esecuzioni: un job puo' essere avviato, fermato e ripreso
    # piu' volte, e a posteriori serve sapere con che dati e che iperparametri
    # e' stato addestrato in ciascun giro.
    job.setdefault("runs", []).append({
        "index": len(job.get("runs", [])) + 1,
        "started_at": job["started_at"],
        "dataset_id": job.get("dataset_id"),
        "dataset_name": job.get("dataset_name"),
        "base_model": job.get("base_model"),
        "method": job.get("method"),
        "hyperparams": dict(job.get("hyperparams") or {}),
        "script_regenerated": regenerated,
        "completed_at": None,
        "status": "running",
        "final_loss": None,
    })
    if total_steps:
        job.setdefault("hyperparams", {})["fwe_steps"] = int(total_steps)
        job["total_steps"] = int(total_steps)
    _save_jobs(jobs)
    return {"success": True, "message": f"Job '{job_id}' avviato.", "job": job, "pid": pid,
            "script_regenerated": regenerated}


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


def update_job_hyperparams(job_id: str, hyper: dict | None = None) -> dict:
    """Change a stopped job's settings and rewrite its script.

    Serve per il caso che capita davvero: un run parte con un batch che non
    entra in VRAM, lo si ferma, e lo si vuole riprendere piu' leggero senza
    ributtare via gli step gia' fatti. I checkpoint restano dove sono, quindi
    il prossimo avvio riparte da li'.

    Il numero di step totali dipende dal batch **effettivo** (batch x
    accumulation): finche' quel prodotto non cambia, il checkpoint continua a
    significare la stessa cosa e la ripresa e' esatta. Se cambia, il conto
    degli step cambia sotto i piedi dell'ottimizzatore, e la funzione lo dice.
    """
    hyper = {k: v for k, v in (hyper or {}).items() if v is not None}
    if not hyper:
        return {"success": False, "error": "Nessun iperparametro da aggiornare."}

    jobs = _load_jobs()
    job = jobs.get(job_id)
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    if job.get("status") in ("running", "paused"):
        return {"success": False,
                "error": ("Il job è ancora attivo. Fermalo prima di cambiarne i "
                          "parametri: un processo in pausa riprende con la "
                          "configurazione che ha in memoria, non con quella nuova.")}

    request = dict(job.get("request") or {})
    before = {**(request.get("hyperparams") or {})}
    after = {**before, **hyper}
    request["hyperparams"] = after
    job["request"] = request
    job["hyperparams"] = {**(job.get("hyperparams") or {}), **hyper}

    old_batch = int(before.get("batch_size") or 0) * int(before.get("gradient_accumulation") or 1)
    new_batch = int(after.get("batch_size") or 0) * int(after.get("gradient_accumulation") or 1)
    warning = ""
    if old_batch and new_batch and old_batch != new_batch:
        warning = (f" Attenzione: il batch effettivo passa da {old_batch} a {new_batch}, "
                   "quindi cambia il numero di step totali e i checkpoint esistenti "
                   "non corrispondono più allo stesso punto del training.")

    try:
        values = _build_script_values(dict(request), job_id, Path(job["dir"]))
        Path(job["script_path"]).write_text(
            _render_script(job.get("method"), values), encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Rigenerazione dello script fallita: {exc}"}

    _save_jobs(jobs)
    changed = ", ".join(f"{k}: {before.get(k, 'n/d')} -> {v}" for k, v in hyper.items())
    log.info("Job %s: parametri aggiornati (%s)", job_id, changed)
    return {"success": True, "job": job, "changed": changed,
            "effective_batch": new_batch,
            "message": f"Parametri aggiornati ({changed}).{warning}"}


def _job_process(job: dict):
    """Il processo di un job, anche se non l'ha avviato questa sessione."""
    proc = _ACTIVE_PROCESSES.get(job.get("id", ""))
    pid = getattr(proc, "pid", None) or job.get("pid")
    if not pid:
        return None
    try:
        import psutil
        process = psutil.Process(int(pid))
        return process if process.is_running() else None
    except Exception:
        return None


def pause_training_job(job_id: str) -> dict:
    """Freeze a running job without losing a single step.

    Il processo viene sospeso dal sistema operativo: si ferma esattamente dov'e'
    e riprende identico, senza ripartire da un checkpoint e senza perdere gli
    step fatti dall'ultimo salvataggio.

    Attenzione a cosa *non* fa: la VRAM resta allocata. Serve a lasciare la CPU
    e il disco a qualcos'altro, non a liberare la scheda per un benchmark — per
    quello va fermato.
    """
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    if job.get("status") != "running":
        return {"success": False,
                "error": f"Il job non è in esecuzione (stato: {job.get('status')})."}

    process = _job_process(job)
    if process is None:
        return {"success": False,
                "error": "Processo non raggiungibile: potrebbe essere già terminato."}
    try:
        process.suspend()
    except Exception as exc:
        return {"success": False, "error": f"Sospensione fallita: {exc}"}

    job["status"] = "paused"
    job["paused_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_jobs(jobs)
    log.info("Job %s sospeso (pid %s)", job_id, getattr(process, "pid", "?"))
    return {"success": True, "job": job,
            "message": (f"Job '{job_id}' in pausa. La VRAM resta occupata: "
                        "per liberare la GPU va fermato.")}


def resume_training_job(job_id: str) -> dict:
    """Let a paused job carry on from exactly where it was suspended."""
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if job is None:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    if job.get("status") != "paused":
        return {"success": False,
                "error": f"Il job non è in pausa (stato: {job.get('status')})."}

    process = _job_process(job)
    if process is None:
        # Il processo e' morto mentre era sospeso: lo stato va detto com'e',
        # altrimenti il job resterebbe "paused" per sempre.
        job["status"] = "stopped"
        _save_jobs(jobs)
        return {"success": False,
                "error": "Il processo non esiste più: il job è stato marcato come fermato."}
    try:
        process.resume()
    except Exception as exc:
        return {"success": False, "error": f"Ripresa fallita: {exc}"}

    job["status"] = "running"
    job.pop("paused_at", None)
    _save_jobs(jobs)
    log.info("Job %s ripreso (pid %s)", job_id, getattr(process, "pid", "?"))
    return {"success": True, "job": job, "message": f"Job '{job_id}' ripreso."}


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


# `ollama create` disegna la sua barra di avanzamento con sequenze ANSI e
# riscrive le righe in place: senza ripulirle il messaggio utile resta sepolto.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]")


def _ollama_failure_detail(res) -> str:
    """The readable reason an `ollama create` failed."""
    raw = (getattr(res, "stderr", "") or "") + (getattr(res, "stdout", "") or "")
    clean = _ANSI_RE.sub("", raw).replace("\r", "\n")
    lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
    errors = [ln for ln in lines if ln.lower().startswith("error")]
    if errors:
        return errors[-1]
    return " | ".join(lines[-3:])


def find_gguf_converter() -> Path | None:
    """llama.cpp's HF->GGUF converter, if this machine already has one.

    Unsloth ne installa una copia sotto ~/.unsloth/llama.cpp quando prepara i
    suoi export: e' esattamente quella che serve qui, quindi nel caso normale
    non c'e' niente da scaricare.
    """
    candidates = [Path.home() / ".unsloth" / "llama.cpp" / "convert_hf_to_gguf.py",
                  BASE_DIR / "llama.cpp" / "convert_hf_to_gguf.py"]
    env_dir = os.environ.get("LLAMA_CPP_DIR")
    if env_dir:
        candidates.insert(0, Path(env_dir) / "convert_hf_to_gguf.py")
    return next((p for p in candidates if p.exists()), None)


# Errori con cui il convertitore Go di Ollama dichiara di non saper leggere i
# pesi. Solo su questi vale la pena rifare il giro passando da llama.cpp: un
# fallimento di altro tipo (nome non valido, disco pieno) si ripeterebbe uguale.
_OLLAMA_CONVERT_MARKERS = ("improper type", "cannot unmarshal", "parse config.json",
                           "unsupported architecture", "unknown architecture",
                           "architecture is not supported")


def _declares_unbacked_mtp(model_dir: Path) -> bool:
    """True if the config announces MTP layers the weights don't actually carry.

    Qwen3.5 dichiara `mtp_num_hidden_layers` anche nei repo da cui la testa MTP
    e' stata rimossa. Il convertitore si fida della config ed estende
    block_count, poi llama.cpp cerca `blk.<N>.attn_norm.weight` e non lo trova:
    il modello si converte "con successo" e poi non si carica.
    """
    try:
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    hparams = config.get("text_config") or config
    if int(hparams.get("mtp_num_hidden_layers") or 0) <= 0:
        return False
    try:
        from safetensors import safe_open
        for shard in model_dir.glob("*.safetensors"):
            with safe_open(shard, "pt") as handle:
                if any(k.startswith(("mtp.", "model.mtp.")) for k in handle.keys()):
                    return False
    except Exception:
        return False
    return True


def _convert_to_gguf(model_dir: Path, out_dir: Path) -> dict:
    """Build a GGUF from HF weights with llama.cpp's converter.

    Il convertitore Go di Ollama copre solo le architetture che conosce: sui
    modelli recenti si ferma su un campo della config che non sa leggere.
    llama.cpp le supporta prima, e un .gguf Ollama lo carica cosi' com'e' —
    quindi la via d'uscita e' produrre il GGUF a parte.
    """
    converter = find_gguf_converter()
    if not converter:
        return {"success": False,
                "error": ("Ollama non sa convertire questi pesi e llama.cpp non e' "
                          "disponibile su questa macchina. Converti il modello in GGUF "
                          "con `convert_hf_to_gguf.py` e rilancia l'export: un .gguf "
                          "nella cartella output viene usato direttamente.")}

    target = out_dir / f"{model_dir.name}-f16.gguf"
    cmd = [sys.executable, str(converter), str(model_dir),
           "--outfile", str(target), "--outtype", "f16"]
    if _declares_unbacked_mtp(model_dir):
        cmd.append("--no-mtp")
        log.info("conversione GGUF: testa MTP dichiarata ma assente, uso --no-mtp")

    log.info("conversione GGUF di %s -> %s", model_dir, target)
    try:
        res = _get_subprocess_run()(cmd, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=3600)
    except Exception as exc:
        return {"success": False, "error": f"Conversione in GGUF fallita: {exc}"}

    if getattr(res, "returncode", 0) != 0 or not target.exists():
        detail = ((getattr(res, "stderr", "") or "") + (getattr(res, "stdout", "") or ""))
        lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
        return {"success": False,
                "error": f"Conversione in GGUF fallita: {' | '.join(lines[-3:])[:400]}"}
    return {"success": True, "gguf_path": target}


# Livelli che `ollama create -q` accetta, dal piu' fedele al piu' compresso.
# Il moltiplicatore stima la dimensione finale a partire dai pesi in 16 bit.
OLLAMA_QUANT_LEVELS = {
    "q8_0":   {"ratio": 0.53, "label": "Q8_0 — quasi identico al 16 bit"},
    "q6_K":   {"ratio": 0.41, "label": "Q6_K — perdita non percepibile"},
    "q5_K_M": {"ratio": 0.35, "label": "Q5_K_M — ottimo compromesso"},
    "q4_K_M": {"ratio": 0.30, "label": "Q4_K_M — lo standard di fatto"},
    "q4_K_S": {"ratio": 0.28, "label": "Q4_K_S — un filo piu' piccolo di Q4_K_M"},
    "q3_K_M": {"ratio": 0.24, "label": "Q3_K_M — degrado visibile"},
}


def export_to_ollama(job_id: str, model_name: str = "custom_model",
                     system_prompt: str = "", quantization: str = "") -> dict:
    """Register the trained model in Ollama via a generated Modelfile.

    `quantization` e' uno dei livelli di OLLAMA_QUANT_LEVELS: Ollama quantizza
    lui stesso durante `create`, partendo dai pesi a 16 bit. Vuoto = nessuna
    quantizzazione.
    """
    quantization = (quantization or "").strip()
    if quantization and quantization not in OLLAMA_QUANT_LEVELS:
        return {"success": False,
                "error": (f"Quantizzazione '{quantization}' non riconosciuta. "
                          f"Disponibili: {', '.join(OLLAMA_QUANT_LEVELS)}.")}

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

    # Un .gguf gia' pronto ha la precedenza: Ollama lo carica cosi' com'e',
    # senza far girare il proprio convertitore (che sulle architetture recenti
    # si ferma). Se ce n'e' piu' d'uno vince il piu' recente.
    ggufs = sorted(output.glob("*.gguf"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not (ggufs or merged.exists() or full_model.exists() or adapter.exists()):
        return {"success": False,
                "error": (f"Nessun artefatto esportabile nel job '{job_id}'. "
                          f"Cercati: *.gguf, {merged.name}/, {full_model.name}/, "
                          f"{adapter.name}/ sotto {output}.")}

    if ggufs:
        modelfile_content = (f"FROM {str(ggufs[0]).replace(chr(92), '/')}\n"
                             f"PARAMETER temperature 0.7\nPARAMETER top_p 0.9\n"
                             f'SYSTEM """{system_prompt}"""\n')
        source = "gguf"
    elif merged.exists():
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

    def write_modelfile(from_target: str) -> str:
        content = (f"FROM {str(from_target).replace(chr(92), '/')}\n"
                   f"PARAMETER temperature 0.7\nPARAMETER top_p 0.9\n"
                   f'SYSTEM """{system_prompt}"""\n')
        (job_dir / "Modelfile").write_text(content, encoding="utf-8")
        return content

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

    def run_create():
        cmd = [ollama_bin, "create", model_name, "-f", str(modelfile_path)]
        if quantization:
            cmd += ["--quantize", quantization]
        # encoding esplicito: `ollama create` scrive spinner e barre in UTF-8, e
        # con il codepage di default di Windows il thread che legge la pipe muore
        # su UnicodeDecodeError — lasciando l'errore vero senza alcun dettaglio.
        return sub_run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)

    try:
        res = run_create()
    except Exception as exc:
        return {"success": False, "error": f"Esecuzione di ollama create fallita: {exc}",
                "modelfile_path": str(modelfile_path)}

    returncode = getattr(res, "returncode", 0)
    detail = _ollama_failure_detail(res) if returncode != 0 else ""

    # Ollama non sa leggere questi pesi: si riprova passando da llama.cpp, che
    # copre le architetture recenti prima del convertitore Go.
    if (returncode != 0 and source in ("merged", "full")
            and any(m in detail.lower() for m in _OLLAMA_CONVERT_MARKERS)):
        log.info("ollama create non sa convertire %s (%s): passo da llama.cpp",
                 source, detail[:120])
        converted = _convert_to_gguf(merged if source == "merged" else full_model, output)
        if not converted.get("success"):
            return {"success": False,
                    "error": f"ollama create ha restituito {returncode}: {detail[:200]}. "
                             + converted["error"],
                    "model_name": model_name, "source": source,
                    "modelfile_path": str(modelfile_path), "modelfile": modelfile_content}
        modelfile_content = write_modelfile(str(converted["gguf_path"]))
        source = "gguf"
        try:
            res = run_create()
        except Exception as exc:
            return {"success": False, "error": f"Esecuzione di ollama create fallita: {exc}",
                    "modelfile_path": str(modelfile_path)}
        returncode = getattr(res, "returncode", 0)
        detail = _ollama_failure_detail(res) if returncode != 0 else ""

    if returncode != 0:
        return {
            "success": False,
            "error": f"ollama create ha restituito {returncode}: "
                     f"{detail[:400] or 'nessun dettaglio'}",
            "model_name": model_name,
            "source": source,
            "modelfile_path": str(modelfile_path),
            "modelfile": modelfile_content,
        }

    quant_note = f", quantizzato {quantization}" if quantization else ""
    return {
        "success": True,
        "message": (f"Modello Ollama '{model_name}' registrato "
                    f"(sorgente: {source}{quant_note})." + fp16_warning),
        "fp16_warning": fp16_warning or None,
        "model_name": model_name,
        "source": source,
        "quantization": quantization or None,
        "modelfile_path": str(modelfile_path),
        "modelfile": modelfile_content,
    }
