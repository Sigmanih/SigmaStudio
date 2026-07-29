"""Brick 2: verifica che i backward manuali del blocco AILO siano CORRETTI
(gradient-check vs autograd PyTorch su CPU) e che il blocco si alleni sulla 6750
(forward + backward manuale, niente autograd del framework)."""
from __future__ import annotations

import logging
import torch

from ..config import pick_device, torch_device, setup_device
from ..logging_utils import section
from .nn import Adam, mse_loss
from .ailo_ops import LayerNorm, Attention, SwiGLU, AILOBlock


def _check(name, module, x, logger) -> float:
    """Confronta i gradienti manuali del modulo con autograd PyTorch.
    Loss = (out * R).sum()  =>  dout = R (passato a backward)."""
    R = torch.randn_like(module.forward(x))
    params = module.params()

    # riferimento: autograd
    for p in params:
        p.requires_grad_(True)
    xr = x.clone().requires_grad_(True)
    (module.forward(xr) * R).sum().backward()
    ref = [p.grad.clone() for p in params] + [xr.grad.clone()]
    for p in params:
        p.grad = None
        p.requires_grad_(False)

    # manuale
    module.forward(x.clone())
    dx = module.backward(R)
    ours = module.grads() + [dx]

    md = max((o - r).abs().max().item() for o, r in zip(ours, ref))
    logger.info("  %-12s gradient-check max|Δ| = %.2e  %s", name, md,
                "PASS" if md < 1e-3 else "FAIL")
    return md


def gradient_check(logger) -> float:
    section(logger, "Brick 2 — gradient-check op del blocco AILO (CPU)")
    torch.manual_seed(0)
    dev = torch.device("cpu")
    B, T, D, H, I = 4, 6, 32, 4, 64
    x = torch.randn(B, T, D)
    diffs = [
        _check("LayerNorm", LayerNorm(D, dev), x, logger),
        _check("Attention", Attention(D, H, dev), x, logger),
        _check("SwiGLU", SwiGLU(D, I, dev), x, logger),
        _check("AILOBlock", AILOBlock(D, H, I, dev), x, logger),
    ]
    worst = max(diffs)
    logger.info("Peggior scarto: %.2e  => %s", worst,
                "tutti i backward corretti" if worst < 1e-3 else "ERRORE nei backward")
    return worst


def train_block_on_device(logger, device, steps=300) -> dict:
    label, dev = setup_device(device)
    section(logger, f"Brick 2 — training blocco AILO su device='{label}'")
    B, T, D, H, I, N = 8, 8, 64, 8, 128, 256
    torch.manual_seed(1)
    teacher = AILOBlock(D, H, I, dev)        # blocco fisso = genera i target
    X = torch.randn(N, T, D, device=dev)
    with torch.no_grad():
        Y = teacher.forward(X)

    student = AILOBlock(D, H, I, dev)
    with torch.no_grad():                     # parti lontano dal teacher
        for p in student.params():
            p.add_(torch.randn_like(p) * 0.3)
    opt = Adam(student.params(), lr=3e-3)
    first = None
    for step in range(1, steps + 1):
        idx = torch.randint(0, N, (B,), device=dev)
        pred = student.forward(X[idx])
        loss, dpred = mse_loss(pred, Y[idx])
        student.backward(dpred)
        opt.step(student.grads())
        if step == 1:
            first = loss.item()
        if step % max(1, steps // 6) == 0 or step == 1:
            logger.info("step %4d/%d  loss=%.6f", step, steps, loss.item())
    final = loss.item()
    logger.info("Loss %.5f -> %.5f  (riduzione %.1fx, nessun TDR)", first, final, first / max(final, 1e-9))
    return {"device": label, "loss_start": first, "loss_final": final}


def run(logger, device="auto", steps=300) -> dict:
    worst = gradient_check(logger)
    res = train_block_on_device(logger, device, steps)
    res["grad_check_maxdiff"] = worst
    section(logger, "Brick 2 — esito")
    logger.info("Backward blocco AILO corretti: %s | GPU allena il blocco: %.5f->%.5f",
                "sì" if worst < 1e-3 else "NO", res["loss_start"], res["loss_final"])
    return res
