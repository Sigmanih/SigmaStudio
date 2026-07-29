# ==============================================================================
# core/training/fwe.py — Gradus Functional Weight Engine integration
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Bridge between the Training Lab and the vendored Gradus FWE engine.

Gradus does not fine-tune a model: it replaces its weight tables with a
*generator* (a frozen AILO decoder driven by a VQ codebook), so the per-model
payload collapses to the codebook plus one index per block. See gradus/NOTICE.md.

This module exposes what the UI needs — availability, sane per-GPU defaults, the
list of runs with their checkpoints, and the engine self-test (gradient checks).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from core.logger import get_logger
from core.training import gpu as gpu_layer

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
GRADUS_DIR = BASE_DIR / "gradus"
JOBS_DIR = BASE_DIR / "training" / "jobs"

# Tensor families the generator can compress, in increasing order of coverage.
FWE_TARGETS = [
    {"id": "layers.0.self_attn.q_proj", "label": "Un solo tensore (smoke test)",
     "desc": "q_proj del primo layer: verifica il flusso in pochi minuti"},
    {"id": "self_attn", "label": "Tutta l'attenzione",
     "desc": "q/k/v/o di tutti i layer"},
    {"id": "mlp", "label": "Tutti gli MLP",
     "desc": "gate/up/down di tutti i layer"},
    {"id": "_proj", "label": "Copertura completa",
     "desc": "attenzione + MLP: il run del paper, ore o giorni"},
]

FWE_DATASETS = [
    {"id": "", "label": "Corpus interno", "desc": "Poche frasi, per validare il flusso"},
    {"id": "wikitext", "label": "WikiText-2", "desc": "Perplexity su testo held-out reale"},
]


def fwe_available() -> dict:
    """Is the engine importable, and what does it need?"""
    missing = []
    try:
        import torch  # noqa: F401
    except Exception:
        missing.append("torch")
    try:
        import transformers  # noqa: F401
    except Exception:
        missing.append("transformers")

    engine_ok = (GRADUS_DIR / "engine" / "fwe.py").exists()
    if not engine_ok:
        missing.append("gradus")

    # Il decoder AILO non e' un requisito bloccante: se manca viene scaricato e
    # convertito automaticamente al primo run (una volta sola, ~600 MB).
    try:
        sys.path.insert(0, str(BASE_DIR))
        from gradus.backbone import backbone_status
        backbone = backbone_status()
    except Exception as exc:                                    # pragma: no cover
        log.warning("backbone_status: %s", exc)
        backbone = {"ready": False, "path": "", "size_mb": 0.0, "repo_id": ""}

    return {
        "available": engine_ok and not missing,
        "engine_path": str(GRADUS_DIR),
        "missing": missing,
        "install_command": f"pip install {' '.join(m for m in missing if m != 'gradus')}"
                           if [m for m in missing if m != "gradus"] else "",
        "backbone": backbone,
    }


def fwe_defaults(base_model: str = "qwen0.5b-instruct") -> dict:
    """Recommended FWE settings for the accelerator actually installed.

    The engine holds the whole target model plus the generator in VRAM in fp32
    (no autograd, no quantisation), so the knobs that matter are the block size,
    the codebook and how many tensors are covered.
    """
    report = gpu_layer.get_accelerator_report()
    caps = report["capabilities"]
    vram = caps.get("max_vram_gb", 0.0)
    backend = report["backend"]

    if vram >= 15:      # una scheda "16 GB" ne riporta ~15.9
        include, steps, batch, vq, latent = "_proj", 600, 8, 512, 64
        note = f"{vram:g} GB: copertura completa dei proiettori, codebook K=512."
    elif vram >= 8:
        include, steps, batch, vq, latent = "self_attn", 400, 4, 256, 64
        note = f"{vram:g} GB: solo attenzione, codebook K=256."
    elif vram > 0:
        include, steps, batch, vq, latent = "layers.0.self_attn.q_proj", 200, 2, 128, 48
        note = f"{vram:g} GB: un solo tensore, per validare il flusso."
    else:
        include, steps, batch, vq, latent = "layers.0.self_attn.q_proj", 100, 2, 128, 48
        note = "Nessuna GPU: il motore gira su CPU, molto lentamente."

    # Lo sharding del generatore (94% del tempo, indipendente per blocco) rende
    # su GPU eterogenee dove DDP non sarebbe applicabile: le fette sono
    # proporzionali alla throughput misurata di ogni scheda.
    trainable = report["trainable_gpus"]
    multi_gpu = len(trainable) > 1 and backend in ("cuda", "rocm")
    if multi_gpu:
        note += (f" Sharding su {len(trainable)} GPU "
                 f"({', '.join(g['name'] for g in trainable)}).")

    return {
        "success": True,
        "base_model": base_model,
        "device": "auto",
        "fwe_devices": "all" if multi_gpu else "",
        "multi_gpu_available": multi_gpu,
        "gpu_names": [g["name"] for g in trainable],
        "backend": backend,
        "fwe_include": include,
        "fwe_block_size": 32,
        "fwe_latent_dim": latent,
        "fwe_steps": steps,
        "fwe_vq": vq,
        "fwe_max_layers": -1,
        "fwe_dataset": "wikitext",
        "fwe_save_every": 25,
        "batch_size": batch,
        "learning_rate": 2e-4,
        "targets": FWE_TARGETS,
        "datasets": FWE_DATASETS,
        "note": note,
        "gpu": caps.get("arch"),
    }


def list_fwe_runs() -> dict:
    """Every FWE run produced by the Training Lab, with its latest checkpoint."""
    runs = []
    if JOBS_DIR.exists():
        for ckpt in JOBS_DIR.glob("*/output/fwe_run/engine_ckpt.pt"):
            run_dir = ckpt.parent
            job_id = run_dir.parent.parent.name
            step = None
            try:
                import torch
                meta = torch.load(ckpt, map_location="cpu", weights_only=False)
                step = int(meta.get("step", 0))
                cfg = meta.get("cfg", {})
            except Exception:
                cfg = {}
            stat = ckpt.stat()
            runs.append({
                "job_id": job_id,
                "run_dir": str(run_dir),
                "checkpoint": str(ckpt),
                "step": step,
                "config": cfg,
                "size_mb": round(stat.st_size / (1024 ** 2), 2),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                            time.localtime(stat.st_mtime)),
            })
    runs.sort(key=lambda r: r["updated_at"], reverse=True)
    return {"success": True, "runs": runs, "total": len(runs)}


def run_engine_selftest(brick: int = 1, device: str = "auto", steps: int = 200,
                        timeout: int = 900) -> dict:
    """Run the engine gradient checks (manual backward vs PyTorch autograd).

    brick 1 = Linear/MLP/Adam, 2 = AILO block ops, 3 = full generator.
    """
    cmd = [sys.executable, "-m", "gradus", "engine-test",
           "--brick", str(int(brick)), "--device", device, "--steps", str(int(steps))]
    started = time.time()
    try:
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True,
                             timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Self-test oltre {timeout}s", "brick": brick}
    except Exception as exc:
        return {"success": False, "error": str(exc), "brick": brick}

    output = (res.stdout or "") + (res.stderr or "")
    lines = [l for l in output.splitlines() if l.strip()]
    passed = "PASS" in output or "corrett" in output.lower()
    return {
        "success": res.returncode == 0,
        "brick": brick,
        "device": device,
        "passed": passed,
        "elapsed_s": round(time.time() - started, 1),
        "lines": lines,
        "output": output,
    }


def fwe_status() -> dict:
    """Everything the FWE panel needs in one call."""
    avail = fwe_available()
    return {
        "success": True,
        "engine": avail,
        "defaults": fwe_defaults(),
        "runs": list_fwe_runs()["runs"],
        "targets": FWE_TARGETS,
        "datasets": FWE_DATASETS,
    }
