"""Brick 3: il generatore COMPLETO del motore (embedding+proiezione+blocchi+testa)
con backward manuale — gradient-check vs PyTorch e training su 6750."""
from __future__ import annotations

import logging
import torch

from ..config import pick_device, torch_device, setup_device
from ..logging_utils import section
from .nn import Adam, mse_loss
from .generator import ManualGenerator


def _rand_inputs(nb, ntypes, nlayers, B, dev):
    bid = torch.randint(0, nb, (B,), device=dev)
    tid = torch.randint(0, ntypes, (B,), device=dev)
    lid = torch.randint(0, nlayers, (B,), device=dev)
    cont = torch.rand(B, 5, device=dev)
    return bid, tid, lid, cont


def gradient_check(logger) -> float:
    section(logger, "Brick 3 — gradient-check generatore completo (CPU)")
    torch.manual_seed(0)
    dev = torch.device("cpu")
    nb, nt, nl, bs = 20, 4, 5, 8
    gen = ManualGenerator(nb, nt, nl, bs, dev, latent_dim=12, d_model=32,
                          n_layers=2, n_heads=4, inter=64, seq_len=3)
    bid, tid, lid, cont = _rand_inputs(nb, nt, nl, 16, dev)
    R = torch.randn_like(gen.forward(bid, tid, lid, cont))
    params = gen.params()

    for p in params:
        p.requires_grad_(True)
    (gen.forward(bid, tid, lid, cont) * R).sum().backward()
    ref = [p.grad.clone() for p in params]
    for p in params:
        p.grad = None
        p.requires_grad_(False)

    gen.forward(bid, tid, lid, cont)
    gen.backward(R)
    ours = gen.grads()

    md = max((o - r).abs().max().item() for o, r in zip(ours, ref))
    logger.info("Generatore completo: max|Δgrad| = %.2e  %s", md, "PASS" if md < 1e-3 else "FAIL")
    return md


@torch.no_grad()
def _cosine(gen, bid, tid, lid, cont, target):
    pred = gen.forward(bid, tid, lid, cont)
    a, b = pred.flatten(), target.flatten()
    return (a @ b / (a.norm() * b.norm() + 1e-9)).item()


def train_on_device(logger, device, steps=400) -> dict:
    label, dev = setup_device(device)
    section(logger, f"Brick 3 — training generatore completo su device='{label}'")
    nb, nt, nl, bs = 64, 6, 8, 16
    torch.manual_seed(1)
    gen = ManualGenerator(nb, nt, nl, bs, dev, latent_dim=64, d_model=128,
                          n_layers=4, n_heads=4, inter=256, seq_len=4)
    # input fissi per blocco + target casuali (prova che impara a generarli)
    all_bid = torch.arange(nb, device=dev)
    all_tid = torch.randint(0, nt, (nb,), device=dev)
    all_lid = torch.randint(0, nl, (nb,), device=dev)
    all_cont = torch.rand(nb, 5, device=dev)
    target = torch.randn(nb, bs * bs, device=dev)

    opt = Adam(gen.params(), lr=3e-3)
    first = None
    for step in range(1, steps + 1):
        idx = torch.randint(0, nb, (32,), device=dev)
        pred = gen.forward(all_bid[idx], all_tid[idx], all_lid[idx], all_cont[idx])
        loss, dpred = mse_loss(pred, target[idx])
        gen.backward(dpred)
        opt.step(gen.grads())
        if step == 1:
            first = loss.item()
        if step % max(1, steps // 6) == 0 or step == 1:
            cos = _cosine(gen, all_bid, all_tid, all_lid, all_cont, target)
            logger.info("step %4d/%d  loss=%.5f  cosine=%.4f", step, steps, loss.item(), cos)
    cos = _cosine(gen, all_bid, all_tid, all_lid, all_cont, target)
    logger.info("Loss %.5f -> %.5f | cosine finale %.4f (nessun TDR)", first, loss.item(), cos)
    return {"device": label, "loss_final": loss.item(), "cosine": cos}


def run(logger, device="auto", steps=400) -> dict:
    md = gradient_check(logger)
    res = train_on_device(logger, device, steps)
    res["grad_check_maxdiff"] = md
    section(logger, "Brick 3 — esito")
    logger.info("Backward generatore corretto: %s | GPU allena il generatore: cosine %.4f",
                "sì" if md < 1e-3 else "NO", res["cosine"])
    return res
