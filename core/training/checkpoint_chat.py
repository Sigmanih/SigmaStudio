# ==============================================================================
# core/training/checkpoint_chat.py — Chat di prova sui checkpoint in corso
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Interroga l'ultimo checkpoint mentre il training prosegue.

Vedere cosa sa produrre il modello a metà corsa è il modo più diretto per
capire se vale la pena continuare: la loss dice che sta imparando, il testo dice
*cosa* sta imparando.

Due accortezze perché la prova non disturbi il training:
  * il modello di prova gira sulla GPU **libera** (o su CPU), mai su quella che
    sta allenando;
  * il checkpoint viene tenuto in cache e ricaricato solo quando ne compare uno
    più recente, così una conversazione non ricarica pesi a ogni messaggio.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from core.logger import get_logger
from core.training import gpu as gpu_layer

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
JOBS_DIR = BASE_DIR / "training" / "jobs"

_CACHE: dict = {"path": None, "model": None, "tokenizer": None, "device": None}
_LOCK = threading.Lock()


def list_checkpoints(job_id: str) -> dict:
    """Checkpoint disponibili per un job, dal più recente."""
    job_dir = JOBS_DIR / job_id
    found = []

    for candidate in list((job_dir / "output" / "checkpoints").glob("step-*")) + \
                     [job_dir / "output" / "model", job_dir / "output" / "model_sft"]:
        marker = candidate / "sigma_step.json"
        config = candidate / "config.json"
        if not config.exists():
            continue
        step, final = None, candidate.name in ("model", "model_sft")
        if marker.exists():
            try:
                meta = json.loads(marker.read_text(encoding="utf-8"))
                step, final = meta.get("step"), meta.get("final", final)
            except Exception:
                pass
        found.append({
            "path": str(candidate),
            "name": candidate.name,
            "step": step,
            "final": final,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                        time.localtime(config.stat().st_mtime)),
            "mtime": config.stat().st_mtime,
        })

    found.sort(key=lambda c: (c["mtime"], c["step"] or 0), reverse=True)
    return {"success": True, "job_id": job_id, "checkpoints": found, "total": len(found)}


def pick_inference_device(training_indices=None, prefer: str = "cpu") -> str:
    """Dove far girare il modello di prova.

    Default **CPU**: il training è il carico da ottimizzare e usa entrambe le
    schede, quindi la prova non deve sottrarre né VRAM né SM. Un modello piccolo
    genera comunque qualche token al secondo su CPU, più che sufficiente per
    capire come sta parlando.

    Con `prefer="gpu"` si torna a usare una scheda libera (mai una che allena):
    utile quando nessun training è in corso.
    """
    if prefer == "cpu":
        return "cpu"

    try:
        report = gpu_layer.get_accelerator_report()
    except Exception:
        return "cpu"

    trainable = report.get("trainable_gpus") or []
    if not trainable:
        return "cpu"

    busy = set(training_indices or [])
    free = [g for g in trainable if g["index"] not in busy]
    if free:
        free.sort(key=lambda g: g.get("vram_used_mb", 0))
        return free[0].get("device_str", "cpu")
    return "cpu"


def _load(path: str, device: str):
    """Carica il checkpoint, riusando quello in cache se non è cambiato."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    with _LOCK:
        if _CACHE["path"] == path and _CACHE["device"] == device and _CACHE["model"] is not None:
            return _CACHE["model"], _CACHE["tokenizer"]

        log.info("Carico il checkpoint %s su %s", path, device)
        tokenizer = AutoTokenizer.from_pretrained(path)
        dtype = torch.float32 if device == "cpu" else torch.bfloat16
        model = AutoModelForCausalLM.from_pretrained(path, dtype=dtype).to(device).eval()

        previous = _CACHE.get("model")
        _CACHE.update({"path": path, "model": model, "tokenizer": tokenizer, "device": device})
        if previous is not None:
            del previous
            if device.startswith("cuda"):
                torch.cuda.empty_cache()
        return model, tokenizer


def chat(job_id: str = "", checkpoint: str = "", prompt: str = "",
         max_new_tokens: int = 120, temperature: float = 0.8,
         top_p: float = 0.9, training_gpus=None, device_preference: str = "cpu") -> dict:
    """Genera una risposta dal checkpoint indicato (o dall'ultimo disponibile)."""
    import torch

    if not prompt.strip():
        return {"success": False, "error": "Prompt vuoto."}

    path = checkpoint
    if not path:
        available = list_checkpoints(job_id)["checkpoints"]
        if not available:
            return {"success": False,
                    "error": ("Nessun checkpoint ancora disponibile: compare dopo i "
                              "primi salvataggi del training.")}
        path = available[0]["path"]

    if not (Path(path) / "config.json").exists():
        return {"success": False, "error": f"Checkpoint non valido: {path}"}

    device = pick_inference_device(training_gpus, device_preference)
    started = time.time()
    try:
        model, tokenizer = _load(path, device)
    except Exception as exc:
        return {"success": False, "error": f"Caricamento fallito: {exc}"}

    # Se il tokenizer ha un template di chat lo si usa: un modello dopo l'SFT
    # risponde molto meglio nel formato in cui è stato addestrato.
    text = prompt
    if getattr(tokenizer, "chat_template", None):
        try:
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True, tokenize=False)
        except Exception:
            text = prompt

    try:
        inputs = tokenizer(text, return_tensors="pt").to(device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=int(max_new_tokens),
                do_sample=temperature > 0,
                temperature=max(0.01, float(temperature)),
                top_p=float(top_p),
                repetition_penalty=1.1,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        generated = output[0][inputs["input_ids"].shape[1]:]
        reply = tokenizer.decode(generated, skip_special_tokens=True)
    except Exception as exc:
        return {"success": False, "error": f"Generazione fallita: {exc}"}

    step = None
    marker = Path(path) / "sigma_step.json"
    if marker.exists():
        try:
            step = json.loads(marker.read_text(encoding="utf-8")).get("step")
        except Exception:
            pass

    return {
        "success": True,
        "reply": reply,
        "checkpoint": path,
        "step": step,
        "device": device,
        "tokens": int(generated.shape[0]),
        "elapsed_s": round(time.time() - started, 2),
    }


def unload() -> dict:
    """Libera il modello di prova (utile se serve VRAM al training)."""
    import torch

    with _LOCK:
        had = _CACHE["model"] is not None
        _CACHE.update({"path": None, "model": None, "tokenizer": None, "device": None})
    if had:
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
    return {"success": True, "unloaded": had}
