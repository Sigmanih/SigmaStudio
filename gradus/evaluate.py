"""Valutazione: fedeltà sui pesi (cosine/errore relativo) + perplexity a valle."""
from __future__ import annotations

import logging
from pathlib import Path

import torch

from .modelio import load_target_model
from .reconstruct import reconstruct_state


SAMPLE_TEXT = (
    "L'intelligenza artificiale moderna si basa su reti neurali profonde. "
    "I modelli linguistici imparano a prevedere la parola successiva a partire dal contesto. "
    "The quick brown fox jumps over the lazy dog. Gradus genera i pesi invece di memorizzarli."
)


def weight_fidelity(model_id: str, ckpt_path: Path, device="cpu",
                    logger: logging.Logger | None = None) -> dict:
    """Cosine ed errore relativo per ogni tensore coperto, originale vs ricostruito."""
    model, _tok, _dev = load_target_model(model_id, device, torch.float32)
    sd, plan = reconstruct_state(ckpt_path, device=device, logger=logger)
    params = dict(model.named_parameters())
    rows = []
    for name, w_rec in sd.items():
        w_orig = params[name].detach().float().cpu()
        a, b = w_orig.flatten(), w_rec.flatten()
        denom = a.norm() * b.norm()
        cos = (a @ b / denom).item() if denom > 0 else 0.0
        rel = ((a - b).norm() / a.norm().clamp_min(1e-8)).item()
        rows.append({"tensor": name, "cosine": round(cos, 4), "rel_err": round(rel, 4)})
    cos_mean = sum(r["cosine"] for r in rows) / max(1, len(rows))
    rel_mean = sum(r["rel_err"] for r in rows) / max(1, len(rows))
    return {"per_tensor": rows, "cosine_mean": round(cos_mean, 4), "rel_err_mean": round(rel_mean, 4)}


@torch.no_grad()
def perplexity(model, tok, text: str, device: str) -> float:
    enc = tok(text, return_tensors="pt").to(device)
    out = model(**enc, labels=enc["input_ids"])
    return float(torch.exp(out.loss).item())


def evaluate(model_id: str, ckpt_path: Path, device="auto",
             logger: logging.Logger | None = None) -> dict:
    from .config import pick_device, torch_device
    dev = pick_device(device)
    dev_obj = torch_device(dev)

    if logger:
        logger.info("Fedeltà pesi (originale vs ricostruito)...")
    fid = weight_fidelity(model_id, ckpt_path, device="cpu", logger=logger)
    if logger:
        logger.info("  cosine medio = %.4f | err. relativo medio = %.4f",
                    fid["cosine_mean"], fid["rel_err_mean"])

    # perplexity: originale
    model_o, tok, _ = load_target_model(model_id, dev, torch.float32)
    ppl_orig = perplexity(model_o, tok, SAMPLE_TEXT, dev_obj)
    del model_o
    # perplexity: ricostruito
    from .reconstruct import load_reconstructed_model
    model_r, tok_r, dev_r, _plan = load_reconstructed_model(
        model_id, ckpt_path, device=dev, logger=logger
    )
    ppl_rec = perplexity(model_r, tok_r, SAMPLE_TEXT, torch_device(dev_r))
    if logger:
        logger.info("Perplexity  originale=%.2f  ricostruito=%.2f  (più vicini = meglio)",
                    ppl_orig, ppl_rec)

    return {
        "cosine_mean": fid["cosine_mean"],
        "rel_err_mean": fid["rel_err_mean"],
        "ppl_original": round(ppl_orig, 3),
        "ppl_reconstructed": round(ppl_rec, 3),
        "per_tensor": fid["per_tensor"],
    }
