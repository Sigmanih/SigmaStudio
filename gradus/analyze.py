"""Analisi statistica dei pesi del modello target (per capire cosa stiamo comprimendo)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import torch

from .config import GradusConfig
from .modelio import load_target_model


@torch.no_grad()
def _effective_rank(w: torch.Tensor, max_dim: int = 1024) -> float:
    """Rank effettivo (entropia degli autovalori normalizzati). Caro: solo su un sotto-blocco."""
    m = w.float()
    if m.shape[0] > max_dim:
        m = m[:max_dim]
    if m.shape[1] > max_dim:
        m = m[:, :max_dim]
    try:
        s = torch.linalg.svdvals(m)
    except Exception:
        return float("nan")
    s = s[s > 0]
    if s.numel() == 0:
        return 0.0
    p = s / s.sum()
    ent = -(p * p.log()).sum()
    return float(torch.exp(ent).item())


def analyze(cfg: GradusConfig, run_dir: Path, logger: logging.Logger, rank_samples: int = 6) -> dict:
    # analisi (incluse SVD) sempre su CPU: alcune op non sono supportate su DirectML
    model, _tok, dev = load_target_model(cfg.model, "cpu", torch.float32)
    logger.info("Analizzo i pesi 2D di %s", cfg.model)
    rows = []
    total = 0
    rank_done = 0
    for name, p in model.named_parameters():
        if p.ndim != 2 or p.numel() < cfg.block.min_tensor_numel:
            continue
        w = p.detach().float().cpu()
        total += w.numel()
        entry = {
            "tensor": name,
            "shape": list(w.shape),
            "mean": round(w.mean().item(), 5),
            "std": round(w.std().item(), 5),
            "absmax": round(w.abs().max().item(), 5),
        }
        if rank_done < rank_samples:
            er = _effective_rank(w)
            entry["eff_rank"] = round(er, 1)
            entry["full_rank"] = min(w.shape)
            entry["rank_ratio"] = round(er / min(w.shape), 3)
            rank_done += 1
        rows.append(entry)

    summary = {
        "model": cfg.model,
        "n_tensors_2d": len(rows),
        "params_2d_M": round(total / 1e6, 2),
    }
    logger.info("Tensori 2D: %d | parametri 2D: %.2fM", len(rows), total / 1e6)
    sampled = [r for r in rows if "eff_rank" in r]
    if sampled:
        avg_ratio = sum(r["rank_ratio"] for r in sampled) / len(sampled)
        logger.info("Rank ratio medio (campione %d tensori): %.3f  "
                    "(vicino a 1 = quasi pieno rango = low-rank inutile)",
                    len(sampled), avg_ratio)
        summary["rank_ratio_sampled"] = round(avg_ratio, 3)

    report = {"summary": summary, "tensors": rows}
    out = run_dir / "analysis.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Report: %s", out)
    return summary
