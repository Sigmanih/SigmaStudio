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


def metodo_effettivo(method: str, hyper: dict) -> str:
    """Il metodo che il job usera' davvero, non quello chiesto.

    `lora_r = 0` significa "niente adapter, addestra i pesi": e' il regime
    sensato sotto il miliardo di parametri, dove un adapter da rank 16 vincola
    l'aggiornamento senza il vantaggio che su un modello grande lo giustifica.

    Solo `trl_sft` sa farlo. Chiederlo su Unsloth passerebbe `r=0` a PEFT, che
    e' un adapter di dimensione nulla: il run girerebbe fino in fondo senza
    aggiornare niente. La scelta va risolta qui e non nell'interfaccia, perche'
    l'autopilota e le API creano job senza passarci.
    """
    if method != "lora_unsloth":
        return method
    try:
        rank = int(hyper.get("lora_r", 16))
    except (TypeError, ValueError):
        return method
    if rank > 0:
        return method
    log.info("lora_r=0: passo da lora_unsloth a trl_sft, l'unico che addestra "
             "i pesi veri invece di un adapter")
    return "trl_sft"


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

    # Il taglio va fatto **prima** di formattare, non dopo. OpenMathInstruct-2
    # ha 13.972.791 righe: trasformarle tutte per tenerne 30.000 sono quattro
    # minuti di CPU e qualche giga di cache a ogni round, buttati. Il campione
    # e' mescolato con seme fisso, non i primi N: i dataset sono spesso
    # ordinati per categoria, e prendere la testa significherebbe addestrare
    # su una fetta sola del compito.
    if 0 < MAX_EXAMPLES < len(ds):
        ds = ds.shuffle(seed=42).select(range(MAX_EXAMPLES))
        sigma("Sottoinsieme: %d esempi estratti prima della formattazione (seed 42)"
              % len(ds))

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
            return {"text": coppia_a_testo(head, ex["output"])}
        sigma("Formato Alpaca rilevato: instruction/input/output -> text")
        return ds.map(to_text, remove_columns=ds.column_names)
    if {"prompt", "completion"} <= cols:
        sigma("Formato prompt/completion rilevato -> text")
        return ds.map(lambda ex: {"text": str(ex["prompt"]) + str(ex["completion"])},
                      remove_columns=ds.column_names)
    # OpenOrca e simili: system_prompt + domanda + risposta. Va prima del loop
    # Q/A generico perche' question+response matcherebbe e perderebbe il contesto.
    for sys_col, q, a in (("system_prompt", "question", "response"),):
        if {sys_col, q, a} <= cols:
            def orca_to_text(ex, sys_col=sys_col, q=q, a=a):
                system = ex.get(sys_col) or ""
                system = str(system)
                return {"text": coppia_a_testo(ex[q], ex[a], sistema=system)}
            sigma("Formato %s/%s/%s rilevato -> text" % (sys_col, q, a))
            return ds.map(orca_to_text, remove_columns=ds.column_names)
    # gsm8k, squad e simili. Senza questo ramo il fallback prenderebbe la prima
    # colonna stringa — la domanda — e si addestrerebbe senza mai la risposta.
    for q, a in (("question", "answer"), ("question", "answers"), ("question", "response"),
                 ("problem", "generated_solution"), ("query", "response"),
                 ("input", "output")):
        if {q, a} <= cols:
            sigma("Formato %s/%s rilevato -> text" % (q, a))
            return ds.map(
                lambda ex, q=q, a=a: {
                    "text": coppia_a_testo(ex[q], ex[a])},
                remove_columns=ds.column_names)
    if "messages" in cols or "conversations" in cols:
        key = "messages" if "messages" in cols else "conversations"
        def chat_to_text(ex):
            return {"text": turni_a_testo(ex[key])}
        sigma("Formato conversazionale rilevato -> text")
        return ds.map(chat_to_text, remove_columns=ds.column_names)

    str_cols = [c for c in ds.column_names if ds.features[c].dtype == "string"]
    if not str_cols:
        raise SystemExit("[ERRORE] Nessuna colonna di testo utilizzabile in %s" % ds.column_names)

    sample = ds.select(range(min(200, len(ds))))
    medie = {c: sum(len(str(v)) for v in sample[c]) / max(1, len(sample)) for c in str_cols}

    # Due o piu' colonne di testo corposo, e nessuno degli schemi noti le ha
    # riconosciute: quasi sempre e' una coppia domanda/risposta con nomi che
    # non abbiamo previsto. Prenderne una sola e' il caso peggiore, perche' non
    # somiglia a un errore: OpenMathInstruct-2 (`problem`/`generated_solution`)
    # cadeva qui e addestrava sulle sole domande, senza mai una risposta.
    # Fermarsi costa un minuto; non fermarsi costa un ciclo intero.
    # Una colonna conta come contenuto se e' abbastanza lunga **e** varia: un
    # `tag` o una `categoria` si ripetono, e non vanno scambiati per la
    # seconda meta' di una coppia. La soglia della secondaria e' piu' bassa
    # perche' le domande sono spesso molto piu' corte delle risposte.
    def e_contenuto(col, minimo):
        if medie[col] < minimo:
            return False
        valori = [str(v) for v in sample[col]]
        return len(set(valori)) / max(1, len(valori)) > 0.5

    corpose = sorted([c for c in str_cols if e_contenuto(c, 25)],
                     key=lambda c: medie[c], reverse=True)
    if corpose and medie[corpose[0]] < 50:
        corpose = []
    if len(corpose) >= 2:
        raise SystemExit(
            "[ERRORE] Nessun formato riconosciuto, ma ci sono %d colonne di testo "
            "corposo: %s. Sembra una coppia domanda/risposta con nomi non "
            "previsti: addestrarne una sola insegnerebbe meta' del compito. "
            "Indica la colonna giusta con l'iperparametro `text_field`, oppure "
            "aggiungi la coppia alla catena di riconoscimento."
            % (len(corpose), ", ".join("%s (%.0f car.)" % (c, medie[c]) for c in corpose)))

    fallback = max(str_cols, key=lambda c: medie[c])
    sigma("Uso la colonna testuale '%s' (media %.0f car.)" % (fallback, medie[fallback]))
    return ds.rename_column(fallback, "text") if fallback != "text" else ds


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

    # Controllo di sanita': se il testo medio e' troppo corto, probabilmente
    # e' stata presa la colonna sbagliata (id, source, tag...).
    sample = ds.select(range(min(200, len(ds))))
    avg_len = sum(len(str(v)) for v in sample["text"]) / max(1, len(sample))
    if avg_len < 20:
        raise SystemExit(
            "[ERRORE] Il testo di training ha una lunghezza media di %.0f caratteri: "
            "probabilmente e' stata selezionata la colonna sbagliata. "
            "Colonne disponibili nel dataset originale: controllare la formattazione." % avg_len)
    # Un testo lungo ma sempre uguale non e' contenuto, e' un'etichetta:
    # `type` di MetaMathQA vale "MATH_AnsAug" su meta' del dataset. La
    # lunghezza da sola non lo distingue da una risposta breve.
    distinti = len({str(v) for v in sample["text"]})
    if len(sample) >= 20 and distinti / len(sample) < 0.05:
        raise SystemExit(
            "[ERRORE] Il testo di training ha solo %d valori distinti su %d esempi: "
            "e' una colonna di categorie, non contenuto. Indica la colonna giusta "
            "con l'iperparametro `text_field`." % (distinti, len(sample)))
    sigma("Lunghezza media del testo: %.0f caratteri | %d valori distinti su %d"
          % (avg_len, distinti, len(sample)))
    for riga in composizione_del_dataset(sample["text"]):
        sigma(riga)
    # Mostra un esempio per debug rapido.
    esempio = str(sample["text"][0])[:300]
    sigma("Esempio testo[0]: %s%s" % (esempio, "..." if len(str(sample["text"][0])) > 300 else ""))

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

# Il formato con cui si addestra dev'essere quello con cui si interroga.
# Questa non e' una raffinatezza: e' il difetto che ha reso inservibili giorni
# di round. Il modello imparava a continuare "### Istruzione: ... ### Risposta:"
# e poi il benchmark lo interrogava con i marcatori di chat del suo tokenizer.
# Due lingue diverse, e le risposte diventavano illeggibili.
#
# Quando il modello ha un suo template lo si usa. Quando non ce l'ha — i modelli
# base, non istruiti — resta lo schema testuale, che per loro e' corretto.
_TEMPLATE_PROPRIO = [None]


def usa_template_del_modello(tokenizer):
    """Registra il tokenizer, se ha un formato di conversazione suo."""
    proprio = getattr(tokenizer, "chat_template", None)
    _TEMPLATE_PROPRIO[0] = tokenizer if proprio else None
    if proprio:
        sigma("Formato di addestramento: template di chat del modello")
    else:
        sigma("Il modello non ha un template di chat: uso lo schema istruzione/risposta")
    return bool(proprio)


def coppia_a_testo(domanda, risposta, sistema=""):
    """Un esempio nel formato che il modello si aspetta di ricevere."""
    tokenizer = _TEMPLATE_PROPRIO[0]
    if tokenizer is not None:
        messaggi = ([{"role": "system", "content": str(sistema)}] if sistema else [])
        messaggi += [{"role": "user", "content": str(domanda)},
                     {"role": "assistant", "content": str(risposta)}]
        try:
            return tokenizer.apply_chat_template(messaggi, tokenize=False)
        except Exception as exc:
            sigma("Template del modello non applicabile (%s): uso lo schema testuale"
                  % str(exc)[:90])
            _TEMPLATE_PROPRIO[0] = None
    testa = (str(sistema) + "\\n\\n" if sistema else "") + str(domanda)
    return "### Istruzione:\\n" + testa + "\\n\\n### Risposta:\\n" + str(risposta)


def turni_a_testo(turni):
    """Una conversazione nel formato del modello."""
    tokenizer = _TEMPLATE_PROPRIO[0]
    normalizzati = []
    for t in turni or []:
        ruolo = t.get("role") or t.get("from") or "user"
        ruolo = {"human": "user", "gpt": "assistant", "system": "system"}.get(ruolo, ruolo)
        normalizzati.append({"role": ruolo,
                             "content": str(t.get("content") or t.get("value") or "")})
    if tokenizer is not None and normalizzati:
        try:
            return tokenizer.apply_chat_template(normalizzati, tokenize=False)
        except Exception:
            _TEMPLATE_PROPRIO[0] = None
    return "\\n".join(m["role"] + ": " + m["content"] for m in normalizzati)

#: Indizi per riconoscere di cosa parla un esempio. Non e' un classificatore:
#: e' un conteggio di parole spia, che basta a dire se un dataset copre la
#: competenza che stiamo cercando di migliorare. Oggi il ciclo lo assume — e
#: quando l'assunzione era sbagliata (OpenOrca per la matematica) se ne
#: accorgeva solo dopo un round intero.
INDIZI_DOMINIO = {
    "matematica": ("\frac", "equation", "solve for", "theorem", "integral",
                   "derivative", "equazione", "teorema", "calcola", "somma"),
    "codice": ("def ", "class ", "import ", "function", "return ", "```python",
               "```js", "SELECT ", "for (", "public static"),
    "ragionamento": ("therefore", "because", "step by step", "reasoning",
                     "quindi", "perche'", "ne segue", "passo dopo passo"),
    "dialogo": ("<|user|>", "<|im_start|>", "user:", "assistant:", "human:"),
}


def composizione_del_dataset(testi):
    """Di cosa parla questo dataset, in righe pronte per il log.

    Un esempio puo' contare in piu' domini: un problema di matematica spiegato
    passo per passo e' matematica *e* ragionamento, e fingere che sia una cosa
    sola darebbe percentuali piu' pulite e piu' false.
    """
    conteggi = dict.fromkeys(INDIZI_DOMINIO, 0)
    for testo in testi:
        minuscolo = str(testo).lower()
        for dominio, indizi in INDIZI_DOMINIO.items():
            if any(i.lower() in minuscolo for i in indizi):
                conteggi[dominio] += 1
    totale = max(1, len(testi))
    presenti = [(d, n) for d, n in conteggi.items() if n]
    if not presenti:
        return ["Composizione: nessun dominio riconosciuto sul campione"]
    presenti.sort(key=lambda x: -x[1])
    parti = ", ".join("%s %d%%" % (d, round(100 * n / totale)) for d, n in presenti)
    return ["Composizione del campione (%d esempi): %s" % (len(testi), parti)]
'''



# Blocco condiviso: completa una classe di modello scritta a mano a cui manca
# quello che i caricatori danno per scontato.
_ARCH_SHIM = """
def completa_architettura(modello_id):
    '''Alcuni repo con architettura propria non implementano
    `get_input_embeddings`, e transformers 5 non lo indovina piu' da solo:
    il caricamento muore con *not auto-handled for <Classe>*.

    Qui si guarda la classe **prima** di istanziarla e, se ha una sola
    `nn.Embedding` fra i suoi figli diretti, la si dichiara. Una sola: con
    zero o con due non si tira a indovinare, si lascia fallire il job con il
    suo errore, che e' meno peggio di addestrare la matrice sbagliata.
    '''
    import torch.nn as nn
    from transformers import AutoConfig
    from transformers.dynamic_module_utils import get_class_from_dynamic_module

    try:
        cfg = AutoConfig.from_pretrained(modello_id, trust_remote_code=True)
        riferimento = (getattr(cfg, "auto_map", None) or {}).get("AutoModelForCausalLM")
        if not riferimento:
            return True
        cls = get_class_from_dynamic_module(riferimento, modello_id)
    except Exception as exc:
        sigma("Architettura non ispezionabile (%s): proseguo" % exc)
        return True

    # "Lo implementa l'autore" vuol dire: in una classe sua, non in una di
    # transformers. Escludere il solo `PreTrainedModel` non bastava — in
    # transformers 5 il metodo sta in `EmbeddingAccessMixin`, e il controllo
    # lo scambiava per un'implementazione vera lasciando il modello rotto.
    def suo(nome):
        return any(nome in c.__dict__ for c in cls.__mro__
                   if not c.__module__.startswith("transformers."))

    def get_input_embeddings(self):
        trovate = [(n, m) for n, m in self.named_children() if isinstance(m, nn.Embedding)]
        if len(trovate) != 1:
            raise NotImplementedError(
                "%s non dichiara get_input_embeddings e ha %d embedding fra i "
                "figli diretti: non e' deducibile quale sia quella dei token."
                % (cls.__name__, len(trovate)))
        return trovate[0][1]

    def set_input_embeddings(self, nuove):
        trovate = [n for n, m in self.named_children() if isinstance(m, nn.Embedding)]
        if len(trovate) != 1:
            raise NotImplementedError("%s: embedding dei token non deducibile" % cls.__name__)
        setattr(self, trovate[0], nuove)

    def get_output_embeddings(self):
        '''La testa che produce i logit. Il predefinito di transformers torna
        `None`, e chi la usa poi muore su `NoneType has no attribute weight`.'''
        vocab = getattr(self.config, "vocab_size", None)
        trovate = [m for _, m in self.named_children()
                   if isinstance(m, nn.Linear) and m.out_features == vocab]
        if len(trovate) != 1:
            raise NotImplementedError(
                "%s non dichiara get_output_embeddings e ha %d strati lineari "
                "larghi quanto il vocabolario: non e' deducibile quale sia la "
                "testa." % (cls.__name__, len(trovate)))
        return trovate[0]

    def set_output_embeddings(self, nuove):
        vocab = getattr(self.config, "vocab_size", None)
        trovate = [n for n, m in self.named_children()
                   if isinstance(m, nn.Linear) and m.out_features == vocab]
        if len(trovate) != 1:
            raise NotImplementedError("%s: testa non deducibile" % cls.__name__)
        setattr(self, trovate[0], nuove)

    aggiunte = []
    for nome, funzione in (("get_input_embeddings", get_input_embeddings),
                           ("set_input_embeddings", set_input_embeddings),
                           ("get_output_embeddings", get_output_embeddings),
                           ("set_output_embeddings", set_output_embeddings)):
        if not suo(nome):
            setattr(cls, nome, funzione)
            aggiunte.append(nome)
    if aggiunte:
        sigma("Architettura %s completata: %s dedotte"
              % (cls.__name__, ", ".join(aggiunte)))

    supporta = bool(getattr(cls, "supports_gradient_checkpointing", True))
    if not supporta:
        sigma("%s non supporta il gradient checkpointing: disattivato ovunque"
              % cls.__name__)
    return supporta

def ripara_frequenze_rotative(model):
    '''Ricalcola le frequenze RoPE se il checkpoint non le conteneva.

    `inv_freq` di solito e' un buffer **non** persistente: si ricalcola a ogni
    costruzione e nessuno lo salva. Chi lo registra con il valore predefinito
    (`register_buffer("inv_freq", ...)`, persistente) si aspetta invece di
    ritrovarlo nel checkpoint — e se non c'e', transformers lo materializza a
    zero, perche' il modello nasce su `meta` e i valori calcolati in `__init__`
    non sopravvivono.

    Con frequenze nulle la rotazione posizionale diventa l'identita': il
    modello smette di distinguere l'ordine dei token. Non da' nessun errore,
    da' una loss di 130 dove il caso puro ne farebbe 10,8 — misurato su
    Ailo340m-v4, che in GGUF funziona perche' llama.cpp le calcola per conto
    suo invece di leggerle dal file.

    Il controllo e' esatto, non una stima: la prima frequenza di RoPE vale
    sempre 1 (base elevato a zero). Se non e' 1, quel buffer non e' stato
    inizializzato.
    '''
    import torch

    base = float(getattr(model.config, "rope_theta", 0) or 10000.0)
    riparati = []
    for nome, modulo in model.named_modules():
        buf = getattr(modulo, "inv_freq", None)
        if not isinstance(buf, torch.Tensor) or buf.numel() == 0:
            continue
        if abs(float(buf.reshape(-1)[0]) - 1.0) < 1e-6:
            continue
        dim = buf.numel() * 2
        corrette = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim))
        with torch.no_grad():
            buf.copy_(corrette.to(dtype=buf.dtype, device=buf.device))
        riparati.append(nome)
    if riparati:
        sigma("Frequenze rotative ricalcolate su %d moduli (base %g): il "
              "checkpoint non le conteneva e valevano zero" % (len(riparati), base))
    return len(riparati)


def funziona_in(model, dtype):
    '''Il modello sopravvive a un forward nella precisione scelta?

    Costa un token e mezzo secondo, e distingue un modello utilizzabile da uno
    che produrra' numeri senza senso per ore senza sollevare nulla.
    '''
    import torch

    try:
        with torch.no_grad():
            uno = torch.ones((1, 8), dtype=torch.long, device=model.device)
            uscita = model(input_ids=uno, labels=uno)
        perdita = float(uscita.loss)
        if not (perdita == perdita) or perdita in (float("inf"), float("-inf")):
            sigma("Prova in %s: loss non finita" % dtype)
            return False
        return True
    except Exception as exc:
        sigma("Prova in %s fallita: %s" % (dtype, str(exc)[:160]))
        return False



def proiezioni_lora(model, preferite):
    '''I moduli su cui attaccare la LoRA, presi dal modello.

    La lista canonica (`q_proj`, `o_proj`, `gate_proj`...) e' quella di Llama e
    Qwen, e su chi non segue quella convenzione copre solo la parte che per caso
    ha lo stesso nome. Misurato su Ailo340m-v4, che chiama le sue
    `out_proj, w1, w2, w3`: adattatore su 2,36M parametri invece che sui 7M
    attesi — due terzi del modello restavano fermi senza che niente lo dicesse.

    Se i nomi canonici ci sono si usano quelli, per non cambiare il
    comportamento su tutto il resto.
    '''
    import torch.nn as nn

    presenti = {nome.rsplit(".", 1)[-1] for nome, modulo in model.named_modules()
                if isinstance(modulo, nn.Linear)}
    canoniche = [n for n in preferite if n in presenti]
    if len(canoniche) >= 4:
        return canoniche
    # La testa che produce i logit non e' una proiezione interna: adattarla
    # significa toccare il vocabolario, che non e' quello che si vuole da LoRA.
    teste = {nome.rsplit(".", 1)[-1] for nome, modulo in model.named_modules()
             if isinstance(modulo, nn.Linear)
             and modulo.out_features == getattr(model.config, "vocab_size", -1)}
    dedotte = sorted(presenti - teste)
    sigma("Nomi non canonici: LoRA su %s (canoniche trovate: %s)"
          % (", ".join(dedotte) or "nessuna", ", ".join(canoniche) or "nessuna"))
    return dedotte or canoniche


def normalizza_la_perdita(trainer):
    '''Chi divide la loss per l'accumulo: il modello o il Trainer?

    Dalla 4.46 il Trainer non divide piu' la loss per il numero di passi di
    accumulo. Passa invece `num_items_in_batch` al forward e si aspetta che sia
    il modello a normalizzare sul conteggio vero dei token — cosi' l'ultimo
    micro-batch, che spesso e' piu' corto, non pesa quanto uno pieno.

    Decide chi fa cosa guardando **solo** se il forward ha un `**kwargs`
    (`trainer.py`, `model_accepts_loss_kwargs`). I modelli di transformers ce
    l'hanno e onorano il conteggio; un'architettura scritta a mano ce l'ha
    quasi sempre per comodita' e il conteggio lo butta via, restituendo una
    media. Allora nessuno dei due divide, e la loss riportata esce
    moltiplicata per l'accumulo — con i gradienti, che e' la parte che fa
    danno: 16 volte troppo grandi, tosati dal clipping a ogni passo, quindi
    ogni aggiornamento ha la stessa lunghezza a prescindere dalla pendenza.

    Misurato su Ailo340m-v4: loss riportata 63 dove quella vera era 3,97, con
    accumulo 16. Nessun errore, nessun avviso — solo un numero sei volte sopra
    il tetto del caso puro, che sembra un modello che non impara.

    Il controllo e' esatto: si chiede la stessa loss con due conteggi diversi.
    Se il numero non cambia, quel parametro il modello non lo guarda.
    '''
    import torch

    model = trainer.model
    try:
        device = next(model.parameters()).device
    except StopIteration:
        return True
    ids = torch.tensor([[1, 2, 3, 4]], device=device)
    # Con il dropout attivo due chiamate identiche danno numeri diversi e la
    # sonda leggerebbe rumore come se fosse normalizzazione.
    era_in_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            poco = model(input_ids=ids, labels=ids, num_items_in_batch=3).loss
            tanto = model(input_ids=ids, labels=ids, num_items_in_batch=300).loss
        onora = abs(float(poco) - float(tanto)) > 1e-6
    except Exception as exc:
        sigma("Non ho potuto verificare la normalizzazione della loss (%s): "
              "la divido io, che e' il comportamento prudente" % exc)
        onora = False
    finally:
        model.train(era_in_training)

    if not onora:
        # Il Trainer torna a dividere per l'accumulo: non e' la normalizzazione
        # sul conteggio dei token, ma e' quella giusta come ordine di grandezza
        # ed e' quella che tutti hanno usato fino alla 4.46.
        trainer.model_accepts_loss_kwargs = False
        sigma("Il modello ignora num_items_in_batch: normalizzo la loss "
              "sull'accumulo (senza, loss e gradienti sarebbero %dx)"
              % trainer.args.gradient_accumulation_steps)
    return onora

"""


_SIGMA_CALLBACK = '''
# Oltre questa frazione della VRAM della scheda si sta gia' paginando: il 5%
# di margine copre la contabilita' imprecisa dell'allocatore senza lasciar
# passare uno sforamento vero.
VRAM_LIMITE = 1.05
# Oltre questa percentuale di RAM occupata Windows comincia a non rispondere.
# Non e' una soglia di comodo: e' il punto oltre il quale l'unica via d'uscita
# diventa il tasto di reset, e con esso si perde tutto il lavoro del run.
RAM_LIMITE_PCT = 92.0
MAX_SEQ_LENGTH = {max_seq_length}

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
        # Quante letture di fila hanno trovato la memoria sforata. Una sola
        # puo' essere il picco di un'allocazione transitoria; tre no.
        self.sforata = 0
        self.ram_scarsa = 0
        self.strozzato = 0
        self.ultima_vram = 0.0

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
            # `max_memory_allocated` conta i tensori vivi, non quanto
            # l'allocatore tiene occupato dal driver: misurati 9,4 GB
            # dichiarati mentre la scheda ne aveva 15,4 su 16,3. La guardia
            # dormiva proprio mentre la memoria finiva. `mem_get_info` chiede
            # al driver, e vede anche cio' che occupano gli altri processi.
            libera, totale = torch.cuda.mem_get_info()
            total_gb = totale / 1024**3
            used_gb = (totale - libera) / 1024**3
            tensori_gb = torch.cuda.memory_allocated() / 1024**3
            vram = " | VRAM %.1f/%.1f GB (tensori %.1f)" % (used_gb, total_gb, tensori_gb)
        # Sforare la VRAM su Windows non produce un errore: il driver pagina in
        # RAM di sistema e il run continua, quattrocento volte piu' lento. Un
        # ciclo automatico ci resta dentro per giorni senza che nessuno se ne
        # accorga — misurato: 47 GB su una scheda da 15,9, 346 s/step contro
        # 0,72, ETA cinque giorni per un'epoca. Fallire subito e' l'unica
        # risposta utile: dice cosa cambiare mentre c'e' ancora tempo.
        # La RAM di sistema e' l'altra meta' del problema, e la piu' grave: con
        # l'offload dei gradienti Unsloth sposta i tensori nella memoria
        # dell'host, e Windows non la protegge. Non arriva nessun errore —
        # arriva che la macchina si pianta e va riavviata, perdendo tutto.
        ram_libera = None
        try:
            import psutil
            ram = psutil.virtual_memory()
            ram_libera = ram.available / 1024**3
            if ram.percent > RAM_LIMITE_PCT:
                self.ram_scarsa += 1
                if self.ram_scarsa >= 3:
                    raise RuntimeError(
                        "RAM di sistema quasi esaurita: %.0f%% occupata, restano "
                        "%.1f GB. Fermo il run prima che la macchina si blocchi. "
                        "Di solito e' l'offload dei gradienti verso la CPU: "
                        "riduci batch_size (ora %d) o disattiva il gradient "
                        "checkpointing sull'adapter."
                        % (ram.percent, ram_libera, args.per_device_train_batch_size))
            else:
                self.ram_scarsa = 0
        except ImportError:
            pass

        self.ultima_vram = (used_gb / total_gb) if (used_gb and total_gb) else 0.0
        if used_gb and total_gb and used_gb > total_gb * VRAM_LIMITE:
            self.sforata += 1
            if self.sforata >= 3:
                raise RuntimeError(
                    "VRAM sforata: %.1f GB allocati su %.1f GB di scheda. Su Windows "
                    "non e' un errore, e' paginazione in RAM di sistema: il run "
                    "prosegue centinaia di volte piu' lento. Riduci batch_size "
                    "(ora %d) o max_seq_length (ora %d), oppure attiva il gradient "
                    "checkpointing." % (used_gb, total_gb,
                                        args.per_device_train_batch_size,
                                        MAX_SEQ_LENGTH))
        else:
            self.sforata = 0

        # La VRAM va nella serie, non solo nel testo: e' l'unico modo perche' il
        # Monitor possa accorgersi da solo che la scheda e' satura.
        sigma_metric(step=state.global_step, epoch=logs.get("epoch", state.epoch),
                     loss=logs.get("loss"),
                     learning_rate=logs.get("learning_rate"),
                     grad_norm=logs.get("grad_norm"),
                     vram_gb=round(used_gb, 2) if used_gb else None,
                     ram_libera_gb=round(ram_libera, 1) if ram_libera else None,
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
            # E se rallenta *mentre* la scheda e' quasi piena, non e' un caso:
            # e' l'allocatore che non trova piu' blocchi contigui e comincia a
            # sfogare in RAM di sistema. Misurato: 18 s/step iniziali diventati
            # 83 con la VRAM al 94%, e una stima di diciotto ore per un'epoca
            # che ne prometteva quattro. Da li' non si riprende da solo.
            piena = self.ultima_vram and self.ultima_vram > 0.90
            if per_step > lifetime * 3 and piena and self.seen > 20:
                self.strozzato += 1
                if self.strozzato >= 3:
                    raise RuntimeError(
                        "Il run sta rallentando su una scheda piena: %.0f s/step "
                        "contro %.0f iniziali, VRAM al %.0f%%. L'allocatore non "
                        "trova piu' blocchi e sfoga in RAM di sistema; da qui non "
                        "si riprende. Riduci batch_size (ora %d) alzando il "
                        "gradient accumulation, oppure max_seq_length (ora %d)."
                        % (per_step, lifetime, self.ultima_vram * 100,
                           args.per_device_train_batch_size, MAX_SEQ_LENGTH))
            else:
                self.strozzato = 0
        sigma("Epoch %d/%d step %d/%d (%.1f%%) - loss: %.4f | lr: %.2e%s%s" % (
            min(int(epoch) + 1, int(total)), int(total), state.global_step,
            state.max_steps, pct, logs["loss"], logs.get("learning_rate", 0.0), vram, eta))
'''


SCRIPT_TEMPLATES = {

    # ---------------------------------------------------------------- LoRA
    "lora_unsloth": _PREAMBLE + _DATASET_LOADER + _ARCH_SHIM + '''
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
TRUST_REMOTE_CODE = {trust_remote_code}
if TRUST_REMOTE_CODE:
    sigma("ATTENZIONE: trust_remote_code attivo — eseguo il codice del repo del modello")

# Il gradient checkpointing su Unsloth va lasciato in pace. Misurato tre volte
# sullo stesso lavoro (Qwen2.5-0.5B, batch 8, seq 1024):
#
#   configurazione                                   VRAM      s/step
#   non passarlo a from_pretrained (come da sempre)   1,1 GB    0,72
#   passarlo esplicitamente = False                   47 GB     346
#   passarlo esplicitamente = "unsloth"               23 GB     non parte
#
# Unsloth decide da se' al caricamento, e decide bene; dirglielo — con
# qualunque valore — peggiora le cose. L'unico caso in cui va detto e'
# un'architettura che il checkpointing non lo supporta affatto: li' va
# spento ovunque, altrimenti il run si ferma al primo passo.
SUPPORTA_CHECKPOINTING = True
if TRUST_REMOTE_CODE:
    SUPPORTA_CHECKPOINTING = completa_architettura(RESUME_ADAPTER or "{base_model}")

CARICAMENTO = {} if SUPPORTA_CHECKPOINTING else {"use_gradient_checkpointing": False}
# Sull'adapter comanda l'autotune: li' "unsloth" significa offload dei
# gradienti verso la RAM di sistema, che su un modello piccolo e' costo puro.
CHECKPOINTING = ("unsloth" if TUNE.get("gradient_checkpointing")
                 and SUPPORTA_CHECKPOINTING else False)

# Un'architettura che non regge il checkpointing e' quasi sempre scritta a
# mano, e chi la scrive a mano di solito scrive anche l'attenzione a mano:
# `softmax(q @ k.T)` materializza una matrice (batch x teste x T x T) per
# **ogni livello**, e senza checkpointing restano tutte in memoria fino al
# backward. Misurato su Ailo340m-v4 — 32 livelli, 12 teste, contesto 1024 —
# con batch 8 fa 53 GB su una scheda da 15,9 e va in OutOfMemory; con batch 2
# sta in un paio di GB. L'autotune non puo' saperlo: guarda i parametri (340M,
# "ci sta comodo") e non come sono implementati. Il batch efficace resta lo
# stesso, ridistribuito sull'accumulo.
BATCH = {batch_size}
ACCUM = {gradient_accumulation}
if not SUPPORTA_CHECKPOINTING and BATCH > 2:
    ACCUM = max(1, ACCUM * (BATCH // 2))
    BATCH = 2
    sigma("Attenzione non ottimizzata e niente checkpointing: batch %d->2, "
          "accumulo %d->%d (batch efficace invariato)"
          % ({batch_size}, {gradient_accumulation}, ACCUM))

def carica(dtype):
    return FastLanguageModel.from_pretrained(
        model_name=RESUME_ADAPTER or "{base_model}",
        max_seq_length={max_seq_length},
        dtype=dtype,
        load_in_4bit=bool(TUNE.get("load_in_4bit")),
        trust_remote_code=TRUST_REMOTE_CODE,
        **CARICAMENTO,
    )


model, tokenizer = carica(DTYPE)
sigma("Modello caricato (4-bit=%s)" % TUNE.get("load_in_4bit"))
usa_template_del_modello(tokenizer)
ripara_frequenze_rotative(model)

# Una moltiplicazione di prova prima di impegnare ore di GPU. I modelli scritti
# a mano mescolano spesso float32 e mezza precisione dentro l'attenzione: in
# bf16 il forward si rompe, o peggio passa e restituisce numeri senza senso.
# Non e' un'ipotesi: verificato su Ailo340m-v4, che in bf16 solleva "expected
# scalar type Float but found BFloat16" e in float32 da' una loss di 2,4 dove
# il caso puro ne farebbe 10,8.
if not funziona_in(model, DTYPE) and str(DTYPE) != "torch.float32":
    sigma("Il modello non regge %s: ricarico in float32" % DTYPE)
    del model
    torch.cuda.empty_cache()
    DTYPE = torch.float32
    TUNE["bf16"], TUNE["fp16"] = False, False
    model, tokenizer = carica(DTYPE)
    ripara_frequenze_rotative(model)

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
        target_modules=proiezioni_lora(model, ["q_proj", "k_proj", "v_proj", "o_proj",
                                              "gate_proj", "up_proj", "down_proj"]),
        use_gradient_checkpointing=CHECKPOINTING,
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


def save_interval(n_examples, ogni_valutazione):
    """Ogni quanti step lasciare un checkpoint da cui poter ripartire.

    Deve essere un **multiplo** della cadenza di validazione: con
    `load_best_model_at_end` il Trainer deve poter far coincidere il
    checkpoint migliore con una misura, e se i due passi non si allineano si
    rifiuta di partire — "found 100, which is not a round multiple of 52",
    che ha fatto fallire due round di fila.
    """
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    # Almeno 20 punti di ripresa, mai piu' fitti di 100 step (scrivere un
    # checkpoint costa) e mai piu' radi di 2000 (perderne di piu' fa male).
    voluto = int(min(2000, max(100, steps // 20)))
    ogni_valutazione = max(1, int(ogni_valutazione))
    return ogni_valutazione * max(1, round(voluto / ogni_valutazione))

train_dataset, eval_dataset = load_train_and_eval()
EVAL_EVERY = eval_interval(len(train_dataset))
SAVE_EVERY = save_interval(len(train_dataset), EVAL_EVERY)
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
        per_device_eval_batch_size=max(1, BATCH * 2),
        max_length={max_seq_length},
        per_device_train_batch_size=BATCH,
        gradient_accumulation_steps=ACCUM,
        # Terzo punto che decide la stessa cosa: la SFTConfig di Unsloth ha
        # `gradient_checkpointing=True` come predefinito, e il Trainer lo
        # accende all'inizio di `train()` a prescindere da come e' stato
        # caricato il modello. Senza questa riga la scelta dell'autotune
        # veniva ignorata: le architetture che non lo supportano si
        # fermavano, e tutte le altre pagavano il rallentamento.
        gradient_checkpointing=SUPPORTA_CHECKPOINTING,
        num_train_epochs={num_epochs},
        learning_rate={learning_rate},
        warmup_ratio=0.05,
        lr_scheduler_type="linear",
        weight_decay=0.01,
        optim=TUNE.get("optim", "adamw_8bit"),
        bf16=bool(TUNE.get("bf16")),
        fp16=bool(TUNE.get("fp16")),
        logging_steps=1,
        # Su un dataset a lunghezza variabile la maggior parte dei token
        # elaborati e' riempimento: misurato su competition_math con batch 8,
        # il 56,7% erano padding, contro il 2% ordinando per lunghezza. Il
        # rimedio ovvio, `group_by_length=True`, qui non si puo' usare: TRL
        # 0.24 con transformers 5.0 l'ha tolto da SFTConfig, e passarlo fa
        # fallire ogni job con un TypeError. L'equivalente moderno e'
        # `packing=True`, ma impacchetta piu' esempi nella stessa sequenza e
        # senza flash-attention si contaminano a vicenda: con attn=sdpa non
        # e' una sostituzione, e' un cambio di semantica. Resta da fare.
        # Salvare a fine epoca sembra ragionevole finche' un'epoca non dura
        # 47.000 step: un run fermato prima non lascia nulla, e ore di GPU
        # spariscono. Si salva a intervalli di step, calcolati perche' i
        # checkpoint restino pochi ma non lontanissimi fra loro.
        save_strategy="steps",
        save_steps=SAVE_EVERY,
        save_total_limit=2,
        # Con `save_total_limit` da solo restano gli ultimi due checkpoint, che
        # non sono i migliori: se la validation ha toccato il minimo a meta' run
        # e poi e' risalita, quel punto e' gia' stato cancellato. Qui il minimo
        # viene tenuto e ricaricato alla fine, cosi' l'adapter salvato e' il
        # migliore prodotto dal run, non l'ultimo.
        load_best_model_at_end=eval_dataset is not None,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

normalizza_la_perdita(trainer)

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
TRUST_REMOTE_CODE = {trust_remote_code}
model = AutoModelForCausalLM.from_pretrained(
    "{base_model}", dtype=DTYPE, device_map="cpu", low_cpu_mem_usage=True,
    trust_remote_code=TRUST_REMOTE_CODE)
sigma("Modello base caricato in %s su CPU" % DTYPE)

model = PeftModel.from_pretrained(model, ADAPTER)
sigma("Adapter applicato, fusione in corso...")
model = model.merge_and_unload()

os.makedirs(TARGET, exist_ok=True)
model.save_pretrained(TARGET, safe_serialization=True)

try:
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER, trust_remote_code=TRUST_REMOTE_CODE)
except Exception:
    tokenizer = AutoTokenizer.from_pretrained("{base_model}", trust_remote_code=TRUST_REMOTE_CODE)
tokenizer.save_pretrained(TARGET)

total = sum(
    os.path.getsize(os.path.join(TARGET, f))
    for f in os.listdir(TARGET) if os.path.isfile(os.path.join(TARGET, f)))
sigma("Modello fuso salvato in %s (%.1f GB)" % (TARGET, total / 1024**3))
sigma("FATTO")
''',

    # ---------------------------------------------------------------- TRL SFT
    "trl_sft": _PREAMBLE + _DATASET_LOADER + _ARCH_SHIM + '''
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
TRUST_REMOTE_CODE = {trust_remote_code}
if TRUST_REMOTE_CODE:
    sigma("ATTENZIONE: trust_remote_code attivo — eseguo il codice del repo del modello")

if TRUST_REMOTE_CODE:
    completa_architettura("{base_model}")

tokenizer = AutoTokenizer.from_pretrained("{base_model}", trust_remote_code=TRUST_REMOTE_CODE)
usa_template_del_modello(tokenizer)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

load_kwargs = dict(dtype=DTYPE, device_map=TUNE.get("device_map") or {"": 0},
                   trust_remote_code=TRUST_REMOTE_CODE)
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

# rank 0 = niente LoRA, si toccano i pesi veri.
#
# LoRA nasce per i modelli grandi: la conoscenza c'e' gia' e la si sposta di
# poco, spendendo l'1% dei parametri. Sotto il miliardo la premessa cade — il
# modello e' poco addestrato, non c'e' molto da spostare di poco, e vincolare
# l'aggiornamento a rank 16 su un decimo dei moduli e' una gabbia senza il
# vantaggio che la giustifica. Un modello da 340M in float32 costa 1,5 GB di
# pesi, altri 1,5 di gradienti e 3 di stati Adam: sei GB, che ci stanno.
ADDESTRAMENTO_COMPLETO = int({lora_r}) <= 0

PASSO = float({learning_rate})

if ADDESTRAMENTO_COMPLETO:
    intero = sum(p.numel() for p in model.parameters())
    for p in model.parameters():
        p.requires_grad_(True)
    sigma("Addestramento completo: tutti i %.2fM parametri sono allenabili "
          "(niente LoRA)" % (intero / 1e6))
    # Un passo tarato su LoRA e' da una a due decadi troppo lungo per i pesi
    # veri: LoRA aggiorna una matrice piccola partendo da zero e sopporta
    # 2e-4, mentre qui si muovono pesi gia' addestrati, dove lo stesso passo
    # cancella quello che c'era. Il tetto e' dichiarato nel log, non applicato
    # di nascosto.
    TETTO = 5e-5
    if PASSO > TETTO:
        sigma("Passo %.1e troppo lungo per l'addestramento completo: sceso a "
              "%.1e (con LoRA sarebbe stato corretto)" % (PASSO, TETTO))
        PASSO = TETTO
elif RESUME_ADAPTER:
    # Continuazione: `is_trainable` e' obbligatorio, altrimenti PEFT carica
    # l'adapter in sola inferenza e il run girerebbe senza aggiornare nulla.
    sigma("Riprendo l'adapter LoRA da: %s" % RESUME_ADAPTER)
    model = PeftModel.from_pretrained(model, RESUME_ADAPTER, is_trainable=True)
    model.print_trainable_parameters()
else:
    model = get_peft_model(model, LoraConfig(
        r={lora_r}, lora_alpha={lora_alpha}, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=proiezioni_lora(model, ["q_proj", "k_proj", "v_proj", "o_proj",
                                               "gate_proj", "up_proj", "down_proj"]),
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


def save_interval(n_examples, ogni_valutazione):
    """Ogni quanti step lasciare un checkpoint da cui poter ripartire.

    Deve essere un **multiplo** della cadenza di validazione: con
    `load_best_model_at_end` il Trainer deve poter far coincidere il
    checkpoint migliore con una misura, e se i due passi non si allineano si
    rifiuta di partire — "found 100, which is not a round multiple of 52",
    che ha fatto fallire due round di fila.
    """
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    # Almeno 20 punti di ripresa, mai piu' fitti di 100 step (scrivere un
    # checkpoint costa) e mai piu' radi di 2000 (perderne di piu' fa male).
    voluto = int(min(2000, max(100, steps // 20)))
    ogni_valutazione = max(1, int(ogni_valutazione))
    return ogni_valutazione * max(1, round(voluto / ogni_valutazione))

train_dataset, eval_dataset = load_train_and_eval()
EVAL_EVERY = eval_interval(len(train_dataset))
SAVE_EVERY = save_interval(len(train_dataset), EVAL_EVERY)
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
        learning_rate=PASSO,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        weight_decay=0.01,
        optim=TUNE.get("optim", "adamw_torch_fused"),
        bf16=bool(TUNE.get("bf16")),
        fp16=bool(TUNE.get("fp16")),
        gradient_checkpointing=bool(TUNE.get("gradient_checkpointing")),
        logging_steps=1,
        # Su un dataset a lunghezza variabile la maggior parte dei token
        # elaborati e' riempimento: misurato su competition_math con batch 8,
        # il 56,7% erano padding, contro il 2% ordinando per lunghezza. Il
        # rimedio ovvio, `group_by_length=True`, qui non si puo' usare: TRL
        # 0.24 con transformers 5.0 l'ha tolto da SFTConfig, e passarlo fa
        # fallire ogni job con un TypeError. L'equivalente moderno e'
        # `packing=True`, ma impacchetta piu' esempi nella stessa sequenza e
        # senza flash-attention si contaminano a vicenda: con attn=sdpa non
        # e' una sostituzione, e' un cambio di semantica. Resta da fare.
        # Salvare a fine epoca sembra ragionevole finche' un'epoca non dura
        # 47.000 step: un run fermato prima non lascia nulla, e ore di GPU
        # spariscono. Si salva a intervalli di step, calcolati perche' i
        # checkpoint restino pochi ma non lontanissimi fra loro.
        save_strategy="steps",
        save_steps=SAVE_EVERY,
        save_total_limit=2,
        # Con `save_total_limit` da solo restano gli ultimi due checkpoint, che
        # non sono i migliori: se la validation ha toccato il minimo a meta' run
        # e poi e' risalita, quel punto e' gia' stato cancellato. Qui il minimo
        # viene tenuto e ricaricato alla fine, cosi' l'adapter salvato e' il
        # migliore prodotto dal run, non l'ultimo.
        load_best_model_at_end=eval_dataset is not None,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=42,
        disable_tqdm=True,
        report_to="none",
    ),
    callbacks=[SigmaProgress()],
)

normalizza_la_perdita(trainer)

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

# Un adapter va in "lora_model" e chiede il merge prima di poter essere usato;
# un modello addestrato per intero e' gia' autonomo e va in "model", che
# l'export riconosce come sorgente completa e manda a Ollama senza altri passi.
out = r"{output_dir}" + ("/model" if ADDESTRAMENTO_COMPLETO else "/lora_model")
trainer.model.save_pretrained(out)
tokenizer.save_pretrained(out)
sigma("%s salvato in: %s" % ("Modello" if ADDESTRAMENTO_COMPLETO else "Adapter", out))
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


def save_interval(n_examples, ogni_valutazione):
    """Ogni quanti step lasciare un checkpoint da cui poter ripartire.

    Deve essere un **multiplo** della cadenza di validazione: con
    `load_best_model_at_end` il Trainer deve poter far coincidere il
    checkpoint migliore con una misura, e se i due passi non si allineano si
    rifiuta di partire — "found 100, which is not a round multiple of 52",
    che ha fatto fallire due round di fila.
    """
    steps = max(1, (n_examples * {num_epochs}) // max(1, {batch_size} * {gradient_accumulation}))
    # Almeno 20 punti di ripresa, mai piu' fitti di 100 step (scrivere un
    # checkpoint costa) e mai piu' radi di 2000 (perderne di piu' fa male).
    voluto = int(min(2000, max(100, steps // 20)))
    ogni_valutazione = max(1, int(ogni_valutazione))
    return ogni_valutazione * max(1, round(voluto / ogni_valutazione))

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
        warmup_ratio=0.05,
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
        # Con `save_total_limit` da solo restano gli ultimi due checkpoint, che
        # non sono i migliori: se la validation ha toccato il minimo a meta' run
        # e poi e' risalita, quel punto e' gia' stato cancellato. Qui il minimo
        # viene tenuto e ricaricato alla fine, cosi' l'adapter salvato e' il
        # migliore prodotto dal run, non l'ultimo.
        load_best_model_at_end=eval_dataset is not None,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
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
    # Un job il cui processo muore mentre Sigma e' acceso — ucciso da fuori,
    # OOM, riavvio del driver — restava "running" nell'interfaccia fino al
    # riavvio successivo, perche' la riconciliazione girava solo all'avvio.
    # Farla anche qui costa una lettura di psutil per job in corso, che sono
    # zero o uno quasi sempre, e chiude il caso in cui l'utente vede un run
    # attivo che non esiste piu'.
    try:
        reconcile_jobs()
    except Exception as exc:
        log.debug("riconciliazione durante la lista: %s", exc)

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
    method = metodo_effettivo(data.get("method", "lora_unsloth"),
                              data.get("hyperparams") or data.get("config") or {})
    model_base = resolve_base_model(
        data.get("base_model") or data.get("model_base", "unsloth/llama-3.2-3b-instruct"))
    # Un repo puo' essere pubblicato senza tokenizer: in quel caso si prepara
    # una copia locale completa e si addestra da li'. Per i repo a posto —
    # cioe' quasi tutti — questa riga non fa niente e non costa niente.
    try:
        from core.training.model_catalog import prepare_trainable_weights
        model_base = prepare_trainable_weights(model_base) or model_base
    except Exception as exc:
        log.warning("preparazione dei pesi di %s non riuscita: %s", model_base, exc)
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
        # Caricare un modello con architettura propria significa eseguire il
        # codice Python che sta nel suo repo. E' una scelta di chi lancia il
        # job, non un default: qui resta spento finche' non lo si accende.
        "trust_remote_code": bool(hyper.get("trust_remote_code")),
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

    dataset_id = data.get("dataset_id", "local_dataset")
    hyper = data.get("hyperparams") or data.get("config") or {}
    method = metodo_effettivo(data.get("method", "lora_unsloth"), hyper)

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


def _termina_albero(pid: int, attesa: float = 12.0) -> int:
    """Ferma un processo **e i suoi figli**, e torna quanti ne ha chiusi.

    Non e' un dettaglio di robustezza: il `python.exe` del venv e' un
    lanciatore che genera l'interprete vero come figlio, ed e' il figlio a
    tenere i tensori. Terminando solo il padre il training resta vivo,
    orfano, con decine di GB in mano — misurati 41 GB su due job "fermati"
    con successo. Bastano tre stop per mandare la macchina al riavvio.
    """
    try:
        import psutil
    except ImportError:
        return 0
    try:
        radice = psutil.Process(int(pid))
    except Exception:
        return 0

    famiglia = []
    try:
        famiglia = radice.children(recursive=True)
    except Exception:
        pass
    famiglia.append(radice)

    for proc in famiglia:
        try:
            proc.terminate()
        except Exception:
            pass
    _, vivi = psutil.wait_procs(famiglia, timeout=attesa)
    # Chi non se ne va con le buone: su Windows un processo dentro una kernel
    # call CUDA ignora il terminate.
    for proc in vivi:
        try:
            proc.kill()
        except Exception:
            pass
    if vivi:
        psutil.wait_procs(vivi, timeout=5)
    return len(famiglia)


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
        _termina_albero(self.pid)

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


def _catena_di_processi(pid: int) -> list[int]:
    """Il pid e tutti i suoi antenati, dal piu' vicino al piu' lontano.

    Serve perche' il pid che il driver vede sulla GPU quasi mai e' quello che
    Sigma ha registrato: il `python.exe` del venv e' un lanciatore, ed e' il
    **figlio** a prendere il contesto CUDA. Cercare il job partendo dal figlio
    e risalendo e' l'unico modo per collegare i due numeri.
    """
    try:
        import psutil
    except ImportError:
        return [int(pid)]
    catena = [int(pid)]
    try:
        proc = psutil.Process(int(pid))
        for antenato in proc.parents():
            catena.append(antenato.pid)
    except Exception:
        pass
    return catena


def _job_del_processo(pid: int, cmdline: str, jobs: dict) -> dict | None:
    """Il job di Sigma a cui appartiene un processo sulla GPU, se c'e'."""
    catena = set(_catena_di_processi(pid))
    for job_id, job in jobs.items():
        registrato = job.get("pid")
        if registrato and int(registrato) in catena:
            return {"id": job_id, "job": job, "match": "pid"}
    # Nessun pid combacia: puo' essere un job avviato da una sessione in cui il
    # numero non e' stato salvato, o un record sovrascritto da un riavvio. Lo
    # script pero' e' in una cartella che porta l'id del job, e quello resta.
    if cmdline:
        for job_id, job in jobs.items():
            script = job.get("script_path") or ""
            if script and script.replace("\\", "/") in cmdline.replace("\\", "/"):
                return {"id": job_id, "job": job, "match": "script"}
    return None


#: Processi di Windows che compaiono fra quelli con un contesto sulla GPU e che
#: non vanno mai offerti come chiudibili. `dwm.exe` e' il compositore del
#: desktop: e' comparso davvero nella lista, con accanto un pulsante «Termina»
#: che avrebbe spento l'interfaccia grafica dell'utente. Gli altri sono peggio —
#: `csrss`, `lsass`, `winlogon` e compagnia terminano la sessione o la macchina.
#: Nessuno di questi sara' mai un training, quindi escluderli non costa niente.
_PROCESSI_DI_SISTEMA = frozenset({
    "dwm.exe", "csrss.exe", "winlogon.exe", "wininit.exe", "smss.exe",
    "services.exe", "lsass.exe", "explorer.exe", "system", "registry",
    "sihost.exe", "fontdrvhost.exe", "logonui.exe",
})


def _e_processo_di_sistema(nome: str) -> bool:
    return (nome or "").strip().lower() in _PROCESSI_DI_SISTEMA


def _unisci_per_pid(processi: list[dict]) -> list[dict]:
    """Una riga per processo, non una per coppia (processo, scheda).

    `nvidia-smi` elenca un processo una volta per ogni GPU su cui ha aperto un
    contesto: Sigma stesso compariva due volte, identico, perche' interroga
    entrambe le schede. Due righe per la stessa cosa sono solo confusione — e
    due pulsanti «Termina» che fanno la stessa identica cosa.
    """
    unito: dict[int, dict] = {}
    for voce in processi:
        pid = voce["pid"]
        scheda = {"index": voce.get("gpu_index", -1), "name": voce.get("gpu_name", ""),
                  "vram_mb": voce.get("vram_mb"), "vram_gb": voce.get("vram_gb")}
        if pid not in unito:
            primo = dict(voce)
            primo["gpus"] = [scheda]
            unito[pid] = primo
            continue
        gia = unito[pid]
        gia["gpus"].append(scheda)
        # La VRAM totale del processo e' la somma su tutte le schede; resta
        # `None` se nessuna delle due era misurabile (il caso di Windows WDDM).
        misurate = [g["vram_mb"] for g in gia["gpus"] if g["vram_mb"] is not None]
        gia["vram_mb"] = round(sum(misurate), 1) if misurate else None
        gia["vram_gb"] = round(sum(misurate) / 1024, 2) if misurate else None
    return list(unito.values())


def gpu_process_inventory() -> dict:
    """I processi che occupano la GPU, con il job di Sigma a cui appartengono.

    E' la risposta alla domanda che la scheda Hardware non sapeva rispondere:
    *cosa* tiene occupata la GPU, e posso chiuderlo da qui. Fino a ieri quella
    scheda offriva un solo pulsante — «Pulisci VRAM» — che scarica i modelli di
    Ollama e non tocca il training: premuto su un run appeso non fa niente, e
    non lo dice.

    Ogni processo esce classificato, perche' la lista del driver mette sullo
    stesso piano il training e il browser (vedi `probe_gpu_processes`) e un
    pulsante «Termina» indifferenziato sarebbe piu' pericoloso del problema che
    risolve:

      training — appartiene a un job di Sigma: e' cio' che si vuole poter chiudere
      sigma    — Sigma Studio stesso: mai chiudibile da qui
      sistema  — processi di Windows senza cui la sessione non sta in piedi
      esterno  — tutto il resto: mostrato perche' occupa la scheda, ma non e'
                 roba nostra e va trattato come tale
    """
    processi = _unisci_per_pid(gpu_layer.probe_gpu_processes())
    if not processi:
        return {"success": True, "processes": [], "total": 0, "orfani": 0}

    jobs = _load_jobs()
    protetti = set(_catena_di_processi(os.getpid()))

    orfani = 0
    for voce in processi:
        collegato = _job_del_processo(voce["pid"], voce.get("cmdline", ""), jobs)
        if collegato:
            job = collegato["job"]
            # Un processo che il driver mostra vivo mentre il registro da' il
            # job per finito e' esattamente l'orfano da cui nasce il problema:
            # nessuna schermata lo elencava, e il job non aveva piu' un tasto
            # Stop da premere.
            orfano = job.get("status") != "running"
            orfani += int(orfano)
            voce.update({
                "job_id": collegato["id"],
                "job_status": job.get("status"),
                "job_label": job.get("method_label") or job.get("method"),
                "base_model": job.get("base_model"),
                "orphan": orfano,
                "attribution": collegato["match"],
            })
        else:
            voce.update({"job_id": None, "job_status": None, "job_label": None,
                         "base_model": None, "orphan": False, "attribution": None})

        if voce["pid"] in protetti:
            voce["kind"] = "sigma"
        elif collegato:
            voce["kind"] = "training"
        elif _e_processo_di_sistema(voce.get("name", "")):
            voce["kind"] = "sistema"
        else:
            voce["kind"] = "esterno"
        voce["protected"] = voce["kind"] in ("sigma", "sistema")
        voce["killable"] = not voce["protected"]

    # I job di Sigma per primi: sono l'unica cosa per cui questa lista esiste.
    ordine = {"training": 0, "esterno": 1, "sigma": 2, "sistema": 3}
    processi.sort(key=lambda p: ordine[p["kind"]])
    return {"success": True, "processes": processi, "total": len(processi),
            "orfani": orfani}


def terminate_gpu_process(pid: int | str) -> dict:
    """Chiude un processo che occupa la GPU, con l'albero dei suoi figli.

    Se appartiene a un job di Sigma passa da `stop_training_job`, cosi' il
    registro resta coerente con la realta'; altrimenti termina l'albero e
    basta. In entrambi i casi verifica che il processo sia davvero sparito:
    dire "fermato" quando non lo e' e' il difetto che ha reso questa scheda
    inutile.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {"success": False, "error": f"PID non valido: {pid!r}"}
    if pid <= 0:
        return {"success": False, "error": f"PID non valido: {pid}"}

    if pid in set(_catena_di_processi(os.getpid())):
        return {"success": False,
                "error": (f"Il processo {pid} è Sigma Studio stesso (o il suo "
                          "lanciatore): chiuderlo da qui spegnerebbe anche "
                          "l'interfaccia che te lo sta chiedendo.")}

    if not _pid_alive(pid):
        return {"success": False, "error": f"Il processo {pid} non esiste più."}

    jobs = _load_jobs()
    nome, cmdline = "", ""
    try:
        import psutil
        proc = psutil.Process(pid)
        nome, cmdline = proc.name(), " ".join(proc.cmdline())
    except Exception:
        pass

    # Il controllo sta anche qui, non solo nell'inventario: l'endpoint accetta
    # un pid qualunque, e un pulsante nascosto non e' una protezione.
    if _e_processo_di_sistema(nome):
        return {"success": False,
                "error": (f"'{nome}' (PID {pid}) è un processo di Windows, non un "
                          "training: chiuderlo comprometterebbe la sessione. "
                          "Se occupa la GPU è perché disegna il desktop.")}

    collegato = _job_del_processo(pid, cmdline, jobs)

    if collegato:
        job_id = collegato["id"]
        esito = stop_training_job(job_id)
        # `stop_training_job` parte dal pid *registrato*. Se quello era gia'
        # morto — record vecchio, riavvio di mezzo — l'albero vero non e' stato
        # toccato e il processo sulla GPU e' ancora li'.
        if _pid_alive(pid):
            chiusi = _termina_albero(pid)
            esito = {"success": not _pid_alive(pid),
                     "message": (f"Job '{job_id}' fermato dal processo sulla GPU "
                                 f"({chiusi} processi chiusi)."),
                     "job_id": job_id, "processi_chiusi": chiusi}
            if not esito["success"]:
                esito["error"] = (f"Il processo {pid} non si è chiuso: continua a "
                                  "occupare la GPU.")
        esito.setdefault("job_id", job_id)
        esito["pid"] = pid
        return esito

    chiusi = _termina_albero(pid)
    if _pid_alive(pid):
        return {"success": False, "pid": pid,
                "error": (f"Il processo {pid} non si è chiuso. Su Windows un "
                          "processo dentro una chiamata CUDA può ignorare il "
                          "terminate: riprova, o chiudilo dal Task Manager.")}
    log.info("Processo GPU %s terminato a mano (%d processi chiusi)", pid, chiusi)
    return {"success": True, "pid": pid, "processi_chiusi": chiusi,
            "message": f"Processo {pid} terminato ({chiusi} processi chiusi)."}


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

    # Il pid registrato basta: `_termina_albero` scende ai figli, ed e' li'
    # che vive il training vero.
    proc = _ACTIVE_PROCESSES.pop(job_id, None)
    pid = getattr(proc, "pid", None) or job.get("pid")
    chiusi = _termina_albero(pid) if pid else 0
    if pid and _pid_alive(pid):
        log.warning("job %s: il processo %s non si e' chiuso", job_id, pid)
        return {"success": False,
                "error": (f"Il processo {pid} del job '{job_id}' non si e' chiuso. "
                          "Chiudilo a mano prima di avviarne altri: continua a "
                          "occupare memoria.")}
    return {"success": True,
            "message": f"Job '{job_id}' fermato ({chiusi} processi chiusi).",
            "job": job, "processi_chiusi": chiusi}


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


def formato_chat_di(modello_ollama: str) -> str:
    """Il TEMPLATE e i token di stop di un modello gia' installato in Ollama.

    Senza questo blocco, un modello esportato riceve il predefinito di Ollama —
    `TEMPLATE {{ .Prompt }}`, cioe' il prompt passato nudo. Su un modello
    istruito significa togliergli il formato con cui e' stato addestrato: al
    posto di una risposta produce una continuazione, e il benchmark la conta
    come illeggibile. Misurato su qwen2.5:0.5b-instruct — base 79 risposte
    valide su 300, ogni candidato esportato 0 su 300 con 276 illeggibili, gli
    stessi numeri a ogni round qualunque fosse l'addestramento.

    Si copia da chi ce l'ha gia' giusto invece di tradurre il template Jinja
    del tokenizer nel dialetto Go di Ollama: sarebbe una conversione fragile
    per riottenere qualcosa che e' gia' li'.
    """
    binario = shutil.which("ollama")
    if not binario or not modello_ollama:
        return ""
    try:
        esito = _get_subprocess_run()([binario, "show", "--modelfile", modello_ollama],
                                      capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=60)
    except Exception as exc:
        log.warning("template di %s non leggibile: %s", modello_ollama, exc)
        return ""
    if getattr(esito, "returncode", 1) != 0:
        return ""

    righe, tenute, dentro = (getattr(esito, "stdout", "") or "").splitlines(), [], False
    for riga in righe:
        if dentro:
            tenute.append(riga)
            if riga.rstrip().endswith('"""'):
                dentro = False
            continue
        if riga.startswith("TEMPLATE "):
            # Un template banale non vale la pena di copiarlo: e' proprio il
            # predefinito da cui stiamo scappando.
            if riga.strip() in ('TEMPLATE {{ .Prompt }}', 'TEMPLATE """{{ .Prompt }}"""'):
                continue
            tenute.append(riga)
            dentro = riga.count('"""') == 1
        elif riga.startswith("PARAMETER stop"):
            tenute.append(riga)
    return ("\n".join(tenute) + "\n") if tenute else ""


def register_ollama_model(source: Path, model_name: str, system_prompt: str | None = None,
                          quantization: str = "", workdir: Path | None = None,
                          adapter_base: str = "", source_label: str = "",
                          template_from: str = "") -> dict:
    """Registra in Ollama dei pesi che stanno gia' su disco.

    `source` e' una cartella di pesi in formato HuggingFace oppure un `.gguf`
    gia' pronto. Se il convertitore interno di Ollama non sa leggere quei pesi
    — succede regolarmente sulle architetture uscite da poco — si passa da
    llama.cpp e si riprova, che e' la sola via che funziona su Qwen3.5.

    Vive qui, fuori da `export_to_ollama`, perche' serve identica anche a chi
    non ha un job: un repo scaricato da HuggingFace va registrato allo stesso
    modo di un modello che abbiamo addestrato noi.
    """
    if system_prompt is None:
        from core.training.identity import default_system_prompt
        system_prompt = default_system_prompt()
    quantization = (quantization or "").strip()
    if quantization and quantization not in OLLAMA_QUANT_LEVELS:
        return {"success": False,
                "error": (f"Quantizzazione '{quantization}' non riconosciuta. "
                          f"Disponibili: {', '.join(OLLAMA_QUANT_LEVELS)}.")}
    source = Path(source)
    if not source.exists():
        return {"success": False, "error": f"Pesi non trovati in {source}."}

    workdir = Path(workdir) if workdir else (source if source.is_dir() else source.parent)
    workdir.mkdir(parents=True, exist_ok=True)
    modelfile_path = workdir / "Modelfile"

    # Il formato di conversazione va portato dietro: e' cio' che distingue una
    # risposta da una continuazione. Senza, Ollama mette il suo predefinito —
    # il prompt passato nudo — e un modello istruito smette di rispondere.
    formato = formato_chat_di(template_from)
    if formato:
        log.info("template di chat ereditato da %s", template_from)

    def write_modelfile(from_target) -> str:
        content = (f"FROM {str(from_target).replace(chr(92), '/')}\n"
                   + formato
                   + "PARAMETER temperature 0.7\nPARAMETER top_p 0.9\n"
                   + f'SYSTEM """{system_prompt}"""\n')
        modelfile_path.write_text(content, encoding="utf-8")
        return content

    def write_adapter_modelfile() -> str:
        # Un adapter non e' un modello: da solo Ollama non saprebbe da dove
        # partire, e va montato sopra la base con cui e' stato addestrato.
        content = (f"FROM {adapter_base}" + chr(10)
                   + f"ADAPTER {str(source).replace(chr(92), '/')}" + chr(10)
                   + "PARAMETER temperature 0.7" + chr(10)
                   + "PARAMETER top_p 0.9" + chr(10)
                   + f'SYSTEM """{system_prompt}"""' + chr(10))
        modelfile_path.write_text(content, encoding="utf-8")
        return content

    kind = source_label or ("gguf" if source.suffix == ".gguf" else "weights")

    # Il convertitore di Ollama ha sbagliato tre volte su tre in questa
    # sessione: si ferma sulle architetture recenti (Qwen3.5, AILO) e — molto
    # peggio — su un modello con embedding legate riesce, ma produce uno strato
    # di uscita rotto. Misurato sugli stessi pesi: da Ollama "@@@@@@@@@@",
    # da llama.cpp una risposta vera. Un guasto che non solleva niente e' il
    # motivo per cui il ripiego "solo se fallisce" non e' mai scattato.
    #
    # Quindi: se llama.cpp c'e', converte lui. Ollama resta la via di scorta.
    if source.is_dir() and not adapter_base and find_gguf_converter():
        convertito = _convert_to_gguf(source, workdir)
        if convertito.get("success"):
            source = Path(convertito["gguf_path"])
            kind = "gguf"
        else:
            log.warning("llama.cpp non ha convertito %s (%s): provo con Ollama",
                        source, convertito.get("error", "")[:120])

    modelfile_content = (write_adapter_modelfile() if adapter_base
                         else write_modelfile(source))

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return {"success": False,
                "error": ("Ollama non trovato nel PATH. Il Modelfile e' comunque pronto: "
                          f"esegui `ollama create {model_name} -f \"{modelfile_path}\"`."),
                "modelfile_path": str(modelfile_path), "modelfile": modelfile_content}

    sub_run = _get_subprocess_run()

    def run_create():
        cmd = [ollama_bin, "create", model_name, "-f", str(modelfile_path)]
        if quantization:
            cmd += ["--quantize", quantization]
        return sub_run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=3600)

    try:
        res = run_create()
    except Exception as exc:
        return {"success": False, "error": f"Esecuzione di ollama create fallita: {exc}",
                "modelfile_path": str(modelfile_path)}

    returncode = getattr(res, "returncode", 0)
    detail = _ollama_failure_detail(res) if returncode != 0 else ""

    if (returncode != 0 and source.is_dir() and not adapter_base
            and any(m in detail.lower() for m in _OLLAMA_CONVERT_MARKERS)):
        log.info("ollama create non sa convertire %s (%s): passo da llama.cpp",
                 source, detail[:120])
        converted = _convert_to_gguf(source, workdir)
        if not converted.get("success"):
            return {"success": False,
                    "error": f"ollama create ha restituito {returncode}: {detail[:200]}. "
                             + converted["error"],
                    "model_name": model_name, "source": kind,
                    "modelfile_path": str(modelfile_path), "modelfile": modelfile_content}
        modelfile_content = write_modelfile(converted["gguf_path"])
        kind = "gguf"
        try:
            res = run_create()
        except Exception as exc:
            return {"success": False, "error": f"Esecuzione di ollama create fallita: {exc}",
                    "modelfile_path": str(modelfile_path)}
        returncode = getattr(res, "returncode", 0)
        detail = _ollama_failure_detail(res) if returncode != 0 else ""

    if returncode != 0:
        return {"success": False,
                "error": (f"ollama create ha restituito {returncode}: "
                          f"{detail[:400] or 'nessun dettaglio'}"),
                "model_name": model_name, "source": kind,
                "modelfile_path": str(modelfile_path), "modelfile": modelfile_content}

    quant_note = f", quantizzato {quantization}" if quantization else ""
    return {"success": True,
            "message": f"Modello Ollama '{model_name}' registrato (sorgente: {kind}{quant_note}).",
            "model_name": model_name, "source": kind,
            "quantization": quantization or None,
            "modelfile_path": str(modelfile_path), "modelfile": modelfile_content}


def export_to_ollama(job_id: str, model_name: str = "custom_model",
                     system_prompt: str | None = None, quantization: str = "",
                     template_from: str = "") -> dict:
    """Register the trained model in Ollama via a generated Modelfile.

    `quantization` e' uno dei livelli di OLLAMA_QUANT_LEVELS: Ollama quantizza
    lui stesso durante `create`, partendo dai pesi a 16 bit. Vuoto = nessuna
    quantizzazione.
    """
    # `None` significa "non specificato" e prende l'identita' di Sigma; una
    # stringa vuota significa "nessun system prompt", ed e' una scelta diversa.
    if system_prompt is None:
        from core.training.identity import default_system_prompt
        system_prompt = default_system_prompt()
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
        target, source = ggufs[0], "gguf"
    elif merged.exists():
        target, source = merged, "merged"
    elif full_model.exists():
        target, source = full_model, "full"
    else:
        target, source = adapter, "adapter"

    # La registrazione vera — Modelfile, `ollama create`, ripiego su llama.cpp
    # quando il convertitore interno non sa leggere i pesi — sta in un posto
    # solo: la usa anche chi importa un modello preso da HuggingFace, e una
    # correzione qui non deve poter mancare l'altra meta'.
    result = register_ollama_model(
        target, model_name, system_prompt, quantization,
        workdir=job_dir, source_label=source, template_from=template_from,
        adapter_base=(job.get("base_model", "llama3") if source == "adapter" else ""))

    if not result.get("success"):
        return result
    result["message"] += fp16_warning
    result["fp16_warning"] = fp16_warning or None
    return result
