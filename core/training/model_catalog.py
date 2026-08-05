# ==============================================================================
# core/training/model_catalog.py — i modelli tra cui scegliere
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Catalogo unificato dei modelli su cui il ciclo automatico può lavorare.

Un modello, qui dentro, ha **due identità** e confonderle costa un'ora:

* l'identità di **valutazione** è un tag Ollama, perché i benchmark passano da
  `/api/generate`;
* l'identità di **addestramento** è un repo HuggingFace o una cartella di pesi,
  perché LoRA non sa caricare un GGUF.

Questo modulo mette in fila tutto ciò che abbiamo — modelli installati in
Ollama, repo già scaricati nella cache HuggingFace, modelli prodotti dai nostri
job — e ciò che si può cercare su HuggingFace, e per ogni voce dice quale delle
due identità è disponibile. Chi sceglie dalla UI vede subito se un modello si
può solo misurare, solo addestrare, o entrambe le cose.
"""

import json
import os
import re
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.logger import get_logger

log = get_logger("training.model_catalog")

BASE_DIR = Path(__file__).parent.parent.parent
JOBS_DIR = BASE_DIR / "training" / "jobs"

HF_MODELS_API = "https://huggingface.co/api/models"

# I pesi che sappiamo addestrare. Un repo di soli GGUF si esegue e basta.
TRAINABLE_SUFFIXES = (".safetensors", ".bin", ".pt")

# Le cartelle di output di un job che contengono un modello intero. `lora_model`
# e' un adapter: da solo non e' un modello di partenza.
JOB_MODEL_DIRS = ("merged_16bit", "merged", "model")


# ==============================================================================
# ACCOPPIAMENTO DELLE DUE IDENTITÀ
# ==============================================================================

_NOT_ALNUM = re.compile(r"[^a-z0-9]+")


def _fingerprint(name: str) -> str:
    """Una chiave di confronto tra nomi scritti con convenzioni diverse.

    `qwen2.5:0.5b-instruct` (Ollama) e `Qwen/Qwen2.5-0.5B-Instruct` (HuggingFace)
    sono lo stesso modello scritto da due comunità che non si sono messe
    d'accordo. Togliendo namespace, separatori e maiuscole restano uguali:
    `qwen2505binstruct`.
    """
    name = (name or "").strip().lower()
    if "/" in name:
        name = name.rsplit("/", 1)[1]
    if name.endswith(":latest"):
        name = name[: -len(":latest")]
    return _NOT_ALNUM.sub("", name)


def _twin_of(indice: dict, nome: str) -> dict:
    """Il gemello Ollama di un modello, sotto uno qualunque dei suoi nomi.

    Due nomi da provare, non uno: il modello puo' essere installato con il
    nome originale, oppure essere stato importato da noi come `sigma-<nome>`.
    Cercarne uno solo faceva sembrare non accoppiato un modello che avevamo
    appena portato in casa.
    """
    for candidato in (nome, ollama_name_for(nome)):
        trovato = indice.get(_fingerprint(candidato))
        if trovato:
            return trovato
    return {}


def _ollama_index() -> dict:
    """Tag Ollama installati, indicizzati per impronta."""
    try:
        from core.training.benchmarks import get_available_models_for_benchmark
        return {_fingerprint(m["id"]): m for m in get_available_models_for_benchmark()}
    except Exception as err:
        log.debug("Elenco Ollama non disponibile: %s", err)
        return {}


# ==============================================================================
# MODELLI IN LOCALE
# ==============================================================================

def _hf_cache_dir() -> Path:
    """La cache di huggingface_hub, rispettando le variabili d'ambiente."""
    for var in ("HUGGINGFACE_HUB_CACHE", "HF_HUB_CACHE"):
        if os.environ.get(var):
            return Path(os.environ[var])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _dir_size_gb(path: Path) -> float:
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return round(total / (1024 ** 3), 2)
    except OSError:
        return 0.0


def _is_causal_lm(config: Path) -> bool:
    """Un modello di linguaggio, non un diffusore o un encoder di immagini.

    La cache HuggingFace raccoglie tutto quello che è passato di lì: Stable
    Diffusion, CLIP, Hunyuan3D. Proporli come base di un ciclo di training
    testuale sarebbe solo rumore in cui perdere quelli buoni.
    """
    try:
        data = json.loads(config.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return False
    archs = data.get("architectures") or []
    # `ForConditionalGeneration` non e' un dettaglio: e' come si dichiara
    # Qwythos, cioe' proprio il modello da cui partiamo.
    if any(a.endswith(("ForCausalLM", "LMHeadModel", "ForConditionalGeneration"))
           for a in archs):
        return True
    # I modelli che dichiarano solo il testo senza architettura esplicita.
    return not archs and bool(data.get("vocab_size")) and bool(data.get("model_type"))


def _wants_custom_code(config: Path) -> bool:
    """Il modello si carica solo eseguendo il codice del suo repo?

    `auto_map` rimanda a moduli Python che stanno nel repo: transformers li
    scarica e li importa, e senza `trust_remote_code=True` si rifiuta di
    farlo. E' una decisione da prendere prima di lanciare il job, non da
    scoprire dal traceback un minuto dopo.
    """
    try:
        data = json.loads(config.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return False
    return bool(data.get("auto_map"))


def _snapshot_of(repo_dir: Path) -> Path | None:
    """L'istantanea scaricata di un repo in cache, se contiene un modello."""
    snapshots = repo_dir / "snapshots"
    if not snapshots.is_dir():
        return None
    for snap in sorted(snapshots.iterdir(), reverse=True):
        if (snap / "config.json").exists():
            return snap
    return None


def _cached_models(ollama: dict) -> list:
    """I repo HuggingFace già scaricati: pronti ad addestrare, zero download."""
    out = []
    cache = _hf_cache_dir()
    if not cache.is_dir():
        return out
    for repo_dir in sorted(cache.glob("models--*")):
        snap = _snapshot_of(repo_dir)
        if snap is None or not _is_causal_lm(snap / "config.json"):
            continue
        # Senza pesi addestrabili è un repo di configurazione o di soli GGUF.
        if not any(f.suffix in TRAINABLE_SUFFIXES for f in snap.iterdir() if f.is_file()):
            continue
        repo_id = repo_dir.name[len("models--"):].replace("--", "/")
        twin = _twin_of(ollama, repo_id)
        out.append(_entry(
            source="cache",
            label=repo_id,
            train_model=repo_id,
            eval_model=(twin or {}).get("id", ""),
            size_gb=_dir_size_gb(repo_dir / "blobs"),
            detail="già in cache locale",
            custom_code=_wants_custom_code(snap / "config.json"),
        ))
    return out


def _job_models(ollama: dict) -> list:
    """I modelli che abbiamo prodotto noi: il punto di partenza più naturale."""
    out = []
    try:
        from core.training.jobs import list_training_jobs
        jobs = list_training_jobs().get("jobs", [])
    except Exception as err:
        log.debug("Elenco job non disponibile: %s", err)
        return out
    for job in jobs:
        job_id = job.get("id") or ""
        for folder in JOB_MODEL_DIRS:
            path = JOBS_DIR / job_id / "output" / folder
            if not (path / "config.json").exists():
                continue
            name = job.get("name") or job_id
            twin = _twin_of(ollama, name)
            out.append(_entry(
                source="job",
                label=name,
                train_model=str(path).replace("\\", "/"),
                eval_model=(twin or {}).get("id", ""),
                size_gb=_dir_size_gb(path),
                detail=f"prodotto dal job {job_id}",
            ))
            break
    return out


def _ollama_models(ollama: dict, taken: set) -> list:
    """I modelli installati in Ollama non già coperti da una voce con i pesi."""
    out = []
    for fp, m in ollama.items():
        if fp in taken:
            continue
        out.append(_entry(
            source="ollama",
            label=m["id"],
            train_model="",
            eval_model=m["id"],
            size_gb=m.get("size_gb") or 0.0,
            params=m.get("parameter_size") or "",
            detail=f"installato in Ollama · {m.get('quantization') or 'quantizzazione ignota'}",
        ))
    return out


def _entry(source, label, train_model, eval_model, size_gb=0.0,
           params="", detail="", downloads=0, likes=0, gguf=False,
           custom_code=False):
    """Una voce del catalogo, con scritto in chiaro cosa ci si può fare."""
    can_train = bool(train_model)
    can_eval = bool(eval_model)
    if can_train and can_eval:
        missing = ""
    elif can_eval:
        missing = ("Pesi non individuati: si può misurare ma non specializzare "
                   "finché non indichi il repo HuggingFace corrispondente.")
    elif can_train:
        # L'import non e' piu' un compito dell'utente: lo fa il ciclo al primo
        # avvio. Resta scritto perche' costa tempo e va saputo prima.
        missing = ("Non è in Ollama: lo importa il ciclo prima di profilarlo"
                   + (" (il repo ha un GGUF, si scarica e basta)." if gguf
                      else " (scarico dei pesi e conversione, qualche minuto)."))
    else:
        missing = ("Non è in Ollama e non ha pesi addestrabili: "
                   "questo modello non si può né misurare né specializzare.")
    return {
        "key": f"{source}:{label}",
        # Un'architettura propria si carica solo eseguendo il codice Python
        # del repo. Dirlo prima evita di scoprirlo dal traceback di un job.
        "custom_code": custom_code,
        "source": source,
        "label": label,
        "eval_model": eval_model,
        "train_model": train_model,
        "size_gb": size_gb,
        "params": params,
        "detail": detail,
        "downloads": downloads,
        "likes": likes,
        "gguf": gguf,
        "can_train": can_train,
        "can_eval": can_eval,
        "ready": can_train and can_eval,
        "missing": missing,
    }


def local_models() -> dict:
    """Tutto ciò che è già su questa macchina, senza toccare la rete."""
    ollama = _ollama_index()
    cached = _cached_models(ollama)
    produced = _job_models(ollama)
    taken = set()
    for e in cached + produced:
        taken.add(_fingerprint(e["label"]))
        taken.add(_fingerprint(ollama_name_for(e["label"])))
    raw_models = produced + cached + _ollama_models(ollama, taken)

    # Fetch autopilot cycle history and benchmark scores for accuracy & timestamps
    cycles_map = {}
    try:
        from core.training.autopilot import known_cycles
        for c in known_cycles():
            fp = _fingerprint(c["model"])
            if fp:
                cycles_map[fp] = c
    except Exception as err:
        log.debug("Known cycles error: %s", err)

    # Benchmark results map
    bench_map = {}
    bench_file = BASE_DIR / "training_lab" / "official_benchmark_results.json"
    if bench_file.exists():
        try:
            b_data = json.loads(bench_file.read_text(encoding="utf-8"))
            if isinstance(b_data, list):
                for res in b_data:
                    m_name = res.get("model") or ""
                    metrics = res.get("metrics") or {}
                    acc = metrics.get("accuracy_pct") or metrics.get("overall_score")
                    if m_name and acc is not None:
                        fp = _fingerprint(m_name)
                        if fp not in bench_map or (res.get("updated_at") or "") > (bench_map[fp].get("updated_at") or ""):
                            bench_map[fp] = {"accuracy_pct": round(float(acc), 1), "updated_at": res.get("updated_at")}
        except Exception:
            pass

    # Deduplicate models by fingerprint
    merged_models = {}
    for m in raw_models:
        fp = _fingerprint(m.get("label") or m.get("eval_model") or m.get("train_model") or "")
        if not fp:
            fp = m.get("key", "")

        if fp not in merged_models:
            item = dict(m)
            item["sources"] = [m["source"]]
            merged_models[fp] = item
        else:
            item = merged_models[fp]
            if m["source"] not in item["sources"]:
                item["sources"].append(m["source"])
            if not item.get("eval_model") and m.get("eval_model"):
                item["eval_model"] = m["eval_model"]
            if not item.get("train_model") and m.get("train_model"):
                item["train_model"] = m["train_model"]
            if m.get("can_train"):
                item["can_train"] = True
            if m.get("can_eval"):
                item["can_eval"] = True
            if m.get("custom_code"):
                item["custom_code"] = True
            item["size_gb"] = max(item.get("size_gb") or 0.0, m.get("size_gb") or 0.0)

    # Finalize attributes for each merged model
    final_list = []
    for fp, item in merged_models.items():
        item["ready"] = bool(item.get("can_train") and item.get("can_eval"))
        if item["ready"]:
            item["missing"] = ""
        elif item.get("can_eval"):
            item["missing"] = ("Pesi non individuati: si può misurare ma non specializzare "
                               "finché non indichi il repo HuggingFace corrispondente.")
        elif item.get("can_train"):
            item["missing"] = "Non è in Ollama: lo importa il ciclo prima di profilarlo."
        else:
            item["missing"] = "Non è in Ollama e non ha pesi addestrabili."

        cycle_info = cycles_map.get(fp) or {}
        bench_info = bench_map.get(fp) or {}

        item["accuracy_pct"] = cycle_info.get("accuracy_pct") or bench_info.get("accuracy_pct")
        item["last_run_at"] = cycle_info.get("last_run_at") or cycle_info.get("updated_at") or ""
        final_list.append(item)

    final_list.sort(key=lambda m: (not m["ready"], not m["can_train"], m["label"].lower()))
    return {"success": True, "models": final_list, "total": len(final_list),
            "ollama_count": len(ollama)}


# ==============================================================================
# RICERCA SU HUGGINGFACE
# ==============================================================================

def _urlopen():
    """L'indirezione che permette ai test di rispondere al posto della rete."""
    th = sys.modules.get("core.training_handler")
    if th and hasattr(th, "urlopen"):
        return th.urlopen
    return urlopen


def search_hf_models(query: str, limit: int = 25) -> dict:
    """I modelli generativi su HuggingFace, i più scaricati per primi."""
    ollama = _ollama_index()
    cache = _hf_cache_dir()
    try:
        params = urlencode({
            "search": (query or "").strip(),
            "limit": max(1, min(int(limit), 50)),
            "filter": "text-generation",
            "sort": "downloads",
            "direction": -1,
            "full": "true",
            # Senza questo la risposta non porta `auto_map`, e i modelli con
            # architettura propria sembrerebbero normali finche' il job non
            # fallisce sul caricamento.
            "config": "true",
        })
        req = Request(f"{HF_MODELS_API}?{params}",
                      headers={"User-Agent": "SigmaStudio/7.0"})
        with _urlopen()(req, timeout=12) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        return {"success": False, "error": f"Connessione HuggingFace fallita: {e}",
                "models": []}
    except Exception as e:
        return {"success": False, "error": str(e), "models": []}

    models = []
    for m in raw:
        repo_id = m.get("id") or ""
        if not repo_id or m.get("private"):
            continue
        files = [s.get("rfilename", "") for s in (m.get("siblings") or [])]
        trainable = any(f.endswith(TRAINABLE_SUFFIXES) for f in files)
        custom = bool((m.get("config") or {}).get("auto_map"))
        gguf = any(f.endswith(".gguf") for f in files)
        twin = _twin_of(ollama, repo_id)
        cached = (cache / f"models--{repo_id.replace('/', '--')}").is_dir()
        entry = _entry(
            source="hf",
            label=repo_id,
            train_model=repo_id if trainable else "",
            eval_model=(twin or {}).get("id", ""),
            params=(m.get("library_name") or ""),
            # I download li mostra gia' la riga: ripeterli qui li faceva
            # leggere due volte, con due formati diversi.
            detail=("già in cache locale" if cached else
                    "solo GGUF: si esegue, non si addestra" if gguf and not trainable else
                    "GGUF disponibile" if gguf else
                    (m.get("library_name") or "")),
            downloads=m.get("downloads", 0),
            likes=m.get("likes", 0),
            gguf=gguf,
            custom_code=custom,
        )
        entry["gated"] = bool(m.get("gated"))
        entry["cached"] = cached
        models.append(entry)
    return {"success": True, "models": models, "total": len(models)}


# ==============================================================================
# PORTARE UN MODELLO IN OLLAMA
# ==============================================================================
# Scegliere un modello da HuggingFace serve a poco se poi non lo si può
# misurare. Per i repo che pubblicano un GGUF, Ollama sa scaricarli da solo:
# qui c'e' l'avvio in background e lo stato da mostrare mentre lavora.

_pull_lock = threading.Lock()
_pull_state = {"running": False, "model": "", "status": "", "percent": 0.0,
               "error": "", "done": False}


def pull_status() -> dict:
    with _pull_lock:
        return {"success": True, "pull": dict(_pull_state)}


def _pull_worker(model: str, ollama_url: str):
    try:
        import requests
        with requests.post(f"{ollama_url}/api/pull", json={"model": model},
                           stream=True, timeout=(10, 3600)) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama ha risposto {resp.status_code}: {resp.text[:200]}")
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    ev = json.loads(line.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if ev.get("error"):
                    raise RuntimeError(ev["error"])
                total, done = ev.get("total") or 0, ev.get("completed") or 0
                with _pull_lock:
                    _pull_state["status"] = ev.get("status", "")
                    _pull_state["percent"] = round(done / total * 100, 1) if total else 0.0
        with _pull_lock:
            _pull_state.update(status="completato", percent=100.0, done=True)
    except Exception as err:
        with _pull_lock:
            _pull_state.update(error=str(err), status="fallito")
        log.warning("Pull di %s fallito: %s", model, err)
    finally:
        with _pull_lock:
            _pull_state["running"] = False


def pull_to_ollama(model: str) -> dict:
    """Avvia il download di un modello in Ollama e torna subito.

    Un pull può durare mezz'ora: bloccare la richiesta HTTP significherebbe
    lasciare la UI in attesa senza poter dire a che punto siamo.
    """
    model = (model or "").strip()
    if not model:
        return {"success": False, "error": "Nessun modello indicato."}
    # Un repo HuggingFace va nominato come tale, altrimenti Ollama lo cerca
    # nella propria libreria e risponde "not found".
    if "/" in model and not model.startswith("hf.co/"):
        model = f"hf.co/{model}"
    with _pull_lock:
        if _pull_state["running"]:
            return {"success": False,
                    "error": f"C'è già un download in corso ({_pull_state['model']})."}
        _pull_state.update(running=True, model=model, status="avvio",
                           percent=0.0, error="", done=False)
    from core.training.benchmarks import OLLAMA_URL
    threading.Thread(target=_pull_worker, args=(model, OLLAMA_URL),
                     daemon=True, name="ollama-pull").start()
    return {"success": True, "message": f"Download di {model} avviato.", "model": model}


# ==============================================================================
# IMPORTARE UN MODELLO HUGGINGFACE COMPLETO
# ==============================================================================
# Scaricare i pesi e registrarli in Ollama sono due gesti separati che
# l'utente non ha ragione di conoscere: se ha scelto un modello, vuole poterlo
# usare. Qui i due gesti diventano uno solo, e il percorso si sceglie da se':
# un repo con GGUF si scarica direttamente da Ollama, uno con soli safetensors
# passa dal convertitore.

def ollama_name_for(repo_id: str) -> str:
    """Il nome con cui un repo HuggingFace vive in Ollama.

    Ollama non accetta le maiuscole nei nomi e tratta lo slash come namespace:
    `sapienzanlp/Minerva-1B-base-v1.0` diventa `sigma-minerva-1b-base-v1.0`. Il
    prefisso dice a colpo d'occhio quali modelli ha portato in casa Sigma.
    """
    nome = (repo_id or "").strip().rsplit("/", 1)[-1].lower()
    nome = re.sub(r"[^a-z0-9._-]+", "-", nome).strip("-.")
    return f"sigma-{nome}" if nome else ""


def _has_gguf(repo_id: str) -> bool:
    """Un repo con GGUF si porta in casa senza convertire niente."""
    try:
        req = Request(f"{HF_MODELS_API}/{repo_id}",
                      headers={"User-Agent": "SigmaStudio/7.0"})
        with _urlopen()(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return False
    return any((s.get("rfilename") or "").endswith(".gguf")
               for s in (data.get("siblings") or []))


def _cached_weights(repo_id: str) -> str | None:
    """Il percorso dei pesi già scaricati, se sono completi."""
    snap = _snapshot_of(_hf_cache_dir() / f"models--{repo_id.replace('/', '--')}")
    if snap is None:
        return None
    # Un config.json senza pesi accanto e' uno scaricamento a meta': meglio
    # rifarlo che passarlo al convertitore e vederlo fallire.
    if not any(f.suffix in TRAINABLE_SUFFIXES for f in snap.iterdir() if f.is_file()):
        return None
    return str(snap)


def _flatten(snapshot: Path, repo_id: str) -> Path:
    """Una copia della cartella con file veri al posto dei collegamenti.

    Nella cache di HuggingFace ogni file e' un link a `../../blobs/<sha>`, e
    `ollama create` li rifiuta: *insecure path*, perche' il percorso esce dalla
    cartella del modello. Gli hardlink risolvono senza occupare spazio — sono
    lo stesso contenuto su disco, con un secondo nome.
    """
    dest = BASE_DIR / "training" / "imports" / repo_id.replace("/", "--")
    dest.mkdir(parents=True, exist_ok=True)
    for src in snapshot.iterdir():
        if not src.is_file():
            continue
        target, reale = dest / src.name, src.resolve()
        if target.exists():
            continue
        try:
            os.link(reale, target)
        except OSError:
            # Volumi diversi o filesystem senza hardlink: si copia.
            import shutil
            shutil.copy2(reale, target)
    return dest


def _scarta_intermedi(cartella: Path, repo_id: str) -> float:
    """Butta il GGUF a 16 bit prodotto per la conversione, a import riuscito.

    `ollama create` copia il file nel proprio archivio: la nostra copia da
    qualche giga non serve piu' a nessuno, e il ciclo automatico si ferma
    quando lo spazio libero scende sotto la soglia. I pesi in hardlink invece
    restano — non occupano niente e rendono immediato un reimport.
    """
    liberati = 0.0
    for gguf in cartella.glob(f"{repo_id.replace('/', '--')}*.gguf"):
        try:
            liberati += gguf.stat().st_size / (1024 ** 3)
            gguf.unlink()
        except OSError as err:
            log.debug("GGUF intermedio non rimosso: %s", err)
    if liberati:
        log.info("liberati %.1f GB di GGUF intermedio dopo l'import di %s",
                 liberati, repo_id)
    return round(liberati, 2)


# ==============================================================================
# REPO INCOMPLETI
# ==============================================================================

#: Basta uno di questi perche' transformers sappia costruire il tokenizer.
_TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json",
                    "tokenizer.model", "spiece.model")


@lru_cache(maxsize=256)
def _repo_files(repo_id: str) -> tuple:
    """L'elenco dei file di un repo, chiesto una volta sola per processo.

    Senza memoria questa chiamata parte a ogni creazione di job — e la suite
    di test e' passata da 28 a 86 secondi per interrogare sempre gli stessi
    quattro repo.
    """
    try:
        req = Request(f"{HF_MODELS_API}/{repo_id}",
                      headers={"User-Agent": "SigmaStudio/7.0"})
        with _urlopen()(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ()
    return tuple(s.get("rfilename", "") for s in (data.get("siblings") or []))


def _build_bpe_tokenizer(vocab: Path, merges: Path, config: dict):
    """Un tokenizer BPE byte-level da `vocab.json` + `merges.txt`.

    E' il formato di GPT-2, e diversi modelli piccoli pubblicano quei due file
    senza il `tokenizer_config.json` che dice a transformers cosa farne. Il
    percorso classico (`GPT2Tokenizer(vocab_file=..., merges_file=...)`) in
    transformers 5.5 restituisce un tokenizer con vocabolario **vuoto**, senza
    sollevare niente: costruirlo con la libreria `tokenizers` e' l'unica via
    che produce davvero i token giusti.
    """
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast

    grezzo = Tokenizer(models.BPE.from_file(str(vocab), str(merges)))
    grezzo.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    grezzo.decoder = decoders.ByteLevel()

    speciale = grezzo.id_to_token(config.get("eos_token_id", 0)) or "<|endoftext|>"

    # Il riempimento vuole un token **diverso** dalla fine sequenza, altrimenti
    # nelle etichette non si distingue "qui finisce" da "qui non c'e' niente" —
    # e Unsloth si rifiuta di partire. Aggiungerne uno nuovo allargherebbe il
    # vocabolario, e un adapter addestrato su un modello allargato non si
    # rifonde piu' sull'originale. Serve quindi un token che esiste gia' e che
    # il testo non produce: nel BPE byte-level `Ā` e' il byte NUL, e in un
    # testo vero non compare mai.
    riempimento = grezzo.id_to_token(config.get("pad_token_id", -1))
    if not riempimento or riempimento == speciale:
        riempimento = "Ā" if grezzo.token_to_id("Ā") is not None else speciale

    return PreTrainedTokenizerFast(
        tokenizer_object=grezzo,
        bos_token=grezzo.id_to_token(config.get("bos_token_id", 0)) or speciale,
        eos_token=speciale,
        # Un byte-level BPE non ha davvero token sconosciuti: qualunque byte si
        # scrive. `unk` serve solo perche' i caricatori se lo aspettano.
        unk_token=riempimento,
        pad_token=riempimento,
    )


def prepare_trainable_weights(repo_id: str) -> str:
    """I pesi pronti da addestrare, completando il repo se gli manca qualcosa.

    Un repo senza tokenizer non e' addestrabile: transformers si ferma con
    *Couldn't instantiate the backend tokenizer*, e il messaggio suggerisce di
    installare sentencepiece anche quando e' gia' installato — perche' il
    problema non e' quello. Se ci sono `vocab.json` e `merges.txt` il tokenizer
    si puo' ricostruire, e conviene farlo qui una volta invece di scoprirlo a
    ogni job.

    Torna il repo cosi' com'e' quando non c'e' niente da sistemare: e' il caso
    normale, e non deve costare nulla.
    """
    repo_id = (repo_id or "").strip()
    if not repo_id or Path(repo_id).is_dir():
        return repo_id

    files = _repo_files(repo_id)
    if not files or any(f in _TOKENIZER_FILES for f in files):
        return repo_id
    if not ("vocab.json" in files and "merges.txt" in files):
        # Manca il tokenizer e non c'e' da cosa ricostruirlo: meglio lasciare
        # che il job fallisca dicendo la verita' che inventarsi un vocabolario.
        return repo_id

    from huggingface_hub import snapshot_download

    snap = Path(_cached_weights(repo_id) or
                snapshot_download(repo_id, ignore_patterns=["*.gguf", "*.onnx"]))
    dest = _flatten(snap, repo_id)
    if not any((dest / f).exists() for f in _TOKENIZER_FILES):
        config = json.loads((dest / "config.json").read_text(encoding="utf-8"))
        tok = _build_bpe_tokenizer(dest / "vocab.json", dest / "merges.txt", config)
        tok.save_pretrained(str(dest))
        log.info("tokenizer ricostruito per %s in %s", repo_id, dest)
    return str(dest).replace("\\", "/")


def _import_worker(repo_id: str, model_name: str, quantization: str):
    from core.training.benchmarks import OLLAMA_URL
    from core.training.jobs import register_ollama_model

    try:
        if _has_gguf(repo_id):
            # La via corta: nessuna conversione, nessuno spazio doppio su disco.
            _pull_worker(f"hf.co/{repo_id}", OLLAMA_URL)
            return

        # Se i pesi ci sono gia', non si riscarica niente. Non e' solo
        # velocita': `snapshot_download` ricontatta comunque l'hub, e il
        # backend Xet risponde 404 su certi repo storici (gpt2) facendo
        # fallire un import che avrebbe potuto non toccare la rete.
        percorso = _cached_weights(repo_id)
        if percorso is None:
            from huggingface_hub import snapshot_download
            with _pull_lock:
                _pull_state.update(status="scarico i pesi da HuggingFace", percent=0.0)
            percorso = snapshot_download(repo_id, ignore_patterns=["*.gguf", "*.onnx"])

        with _pull_lock:
            _pull_state.update(status="registro in Ollama", percent=50.0)
        pesi = _flatten(Path(percorso), repo_id)
        esito = register_ollama_model(pesi, model_name,
                                      quantization=quantization,
                                      workdir=pesi.parent)
        if not esito.get("success"):
            raise RuntimeError(esito.get("error", "registrazione fallita"))
        _scarta_intermedi(pesi.parent, repo_id)
        with _pull_lock:
            _pull_state.update(status="completato", percent=100.0, done=True)
    except Exception as err:
        with _pull_lock:
            _pull_state.update(error=str(err)[:400], status="fallito")
        log.warning("Import di %s fallito: %s", repo_id, err)
    finally:
        with _pull_lock:
            _pull_state["running"] = False


def import_hf_model(repo_id: str, model_name: str = "",
                    quantization: str = "q4_K_M") -> dict:
    """Porta un modello da HuggingFace fino a essere eseguibile in Ollama."""
    repo_id = (repo_id or "").strip()
    if not repo_id:
        return {"success": False, "error": "Nessun modello indicato."}
    model_name = (model_name or ollama_name_for(repo_id)).strip()
    if not model_name:
        return {"success": False, "error": f"Da '{repo_id}' non ricavo un nome Ollama valido."}
    with _pull_lock:
        if _pull_state["running"]:
            return {"success": False,
                    "error": f"C'è già un import in corso ({_pull_state['model']})."}
        _pull_state.update(running=True, model=repo_id, status="avvio",
                           percent=0.0, error="", done=False)
    threading.Thread(target=_import_worker, args=(repo_id, model_name, quantization),
                     daemon=True, name="hf-import").start()
    return {"success": True, "model": repo_id, "ollama_name": model_name,
            "message": f"Import di {repo_id} avviato come '{model_name}'."}


def ensure_ollama_identity(repo_id: str, quantization: str = "q4_K_M",
                           timeout: float = 7200.0) -> dict:
    """Come `import_hf_model`, ma aspetta la fine. Per chi gira gia' in un thread.

    Il ciclo automatico non ha una UI da non bloccare: ha bisogno del nome
    Ollama *prima* di poter profilare il modello, quindi qui si aspetta.
    """
    # Due nomi da cercare, non uno: il repo puo' essere gia' installato con il
    # suo nome originale, oppure essere stato importato da noi come
    # `sigma-<nome>`. Cercarne uno solo farebbe riscaricare dieci giga a ogni
    # ripresa del ciclo.
    esistente = _twin_of(_ollama_index(), repo_id)
    if esistente:
        return {"success": True, "model_name": esistente["id"], "already": True}

    avviato = import_hf_model(repo_id, quantization=quantization)
    if not avviato.get("success"):
        return avviato
    scadenza = time.monotonic() + timeout
    while time.monotonic() < scadenza:
        time.sleep(3)
        with _pull_lock:
            stato = dict(_pull_state)
        if stato["error"]:
            return {"success": False, "error": stato["error"]}
        if stato["done"] and not stato["running"]:
            return {"success": True, "model_name": avviato["ollama_name"]}
        if not stato["running"] and not stato["done"]:
            return {"success": False, "error": "import terminato senza esito"}
    return {"success": False, "error": "import non concluso entro il tempo massimo"}
