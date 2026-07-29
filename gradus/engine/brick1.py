"""Brick 1 del motore: dimostra che (a) i nostri gradienti manuali sono CORRETTI
(gradient-check vs PyTorch su CPU) e (b) la GPU allena sotto il NOSTRO motore
(training su device, solo forward-op, niente autograd del framework)."""
from __future__ import annotations

import logging

import torch

from ..config import pick_device, torch_device, setup_device
from ..logging_utils import section
from .nn import MLP, Adam, mse_loss, silu


def gradient_check(logger: logging.Logger) -> float:
    """Confronta i gradienti manuali della MLP con quelli di autograd PyTorch (CPU)."""
    torch.manual_seed(0)
    dev = torch.device("cpu")
    N, din, dh, dout = 32, 16, 24, 8
    x = torch.randn(N, din)
    y = torch.randn(N, dout)

    net = MLP([din, dh, dout], dev, seed=3)
    pred = net.forward(x)
    loss, dpred = mse_loss(pred, y)
    net.backward(dpred)
    ours = [g.clone() for g in net.grads()]

    # riferimento: stessa rete con autograd
    W1 = net.l1.W.clone().requires_grad_(True)
    b1 = net.l1.b.clone().requires_grad_(True)
    W2 = net.l2.W.clone().requires_grad_(True)
    b2 = net.l2.b.clone().requires_grad_(True)
    a1 = silu(x @ W1.t() + b1)
    pred_ref = a1 @ W2.t() + b2
    loss_ref = ((pred_ref - y) ** 2).mean()
    loss_ref.backward()
    ref = [W1.grad, b1.grad, W2.grad, b2.grad]

    max_diff = max((o - r).abs().max().item() for o, r in zip(ours, ref))
    logger.info("Gradient-check: loss manuale=%.6f  autograd=%.6f  max|Δgrad|=%.2e",
                loss.item(), loss_ref.item(), max_diff)
    ok = max_diff < 1e-4
    logger.info("Gradient-check: %s", "PASS (i nostri gradienti sono corretti)" if ok
                else "FAIL (gradienti errati!)")
    return max_diff


def train_on_device(logger: logging.Logger, device: str, steps: int = 400) -> dict:
    """Allena la MLP (motore manuale) su un device a imitare un teacher casuale."""
    label, dev = setup_device(device)
    section(logger, f"Training motore manuale su device='{label}'")

    din, dh, dout, N = 64, 128, 32, 512
    torch.manual_seed(1)
    # teacher fisso (genera i target) — usa solo forward, niente grad
    tw1 = (torch.randn(dh, din) * 0.3).to(dev)
    tw2 = (torch.randn(dout, dh) * 0.3).to(dev)
    X = torch.randn(N, din, device=dev)
    with torch.no_grad():
        Y = silu(X @ tw1.t()) @ tw2.t()

    net = MLP([din, dh, dout], dev, seed=7)
    opt = Adam(net.params(), lr=5e-3)

    first = None
    for step in range(1, steps + 1):
        idx = torch.randint(0, N, (128,), device=dev)
        xb, yb = X[idx], Y[idx]
        pred = net.forward(xb)
        loss, dpred = mse_loss(pred, yb)
        net.backward(dpred)
        opt.step(net.grads())
        if step == 1:
            first = loss.item()
        if step % max(1, steps // 8) == 0 or step == 1:
            logger.info("step %4d/%d  loss=%.6f", step, steps, loss.item())
    final = loss.item()
    logger.info("Loss %.5f -> %.5f  (riduzione %.1fx)", first, final, first / max(final, 1e-9))
    return {"device": label, "loss_start": first, "loss_final": final}


def run(logger: logging.Logger, device: str = "auto", steps: int = 400) -> dict:
    section(logger, "Brick 1 — gradient-check (CPU)")
    diff = gradient_check(logger)
    res = train_on_device(logger, device, steps)
    res["grad_check_maxdiff"] = diff
    section(logger, "Brick 1 — esito")
    logger.info("Gradienti corretti: %s | GPU allena: loss %.5f->%.5f",
                "sì" if diff < 1e-4 else "NO", res["loss_start"], res["loss_final"])
    return res
