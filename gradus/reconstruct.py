"""Ricostruzione: dal generatore allenato ai pesi, e iniezione nel modello."""
from __future__ import annotations

import logging
from pathlib import Path

import torch

from .config import GeneratorConfig, torch_device
from .generator import build_generator
from .modelio import TENSOR_TYPES, TensorPlan, load_target_model, reconstruct_state_dict


def load_checkpoint(ckpt_path: Path, device: str = "cpu"):
    dev = torch_device(device)
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    plan = TensorPlan.from_dict(ckpt["plan"])
    gcfg = GeneratorConfig(**ckpt["generator_cfg"])
    gen = build_generator(ckpt["kind"], plan.num_blocks, plan.block_size,
                          len(TENSOR_TYPES), plan.num_layers, gcfg)
    gen.load_state_dict(ckpt["generator_state"])
    gen.to(dev).eval()
    return gen, plan, ckpt["mean"], ckpt["std"], dev


@torch.no_grad()
def generate_blocks(gen, plan: TensorPlan, mean, std, dev, batch=512) -> torch.Tensor:
    """Genera tutti i blocchi (denormalizzati) -> (num_blocks, BS, BS) su CPU."""
    feats = plan.features()
    ids = plan.block_ids()
    bs = plan.block_size
    out = torch.zeros(plan.num_blocks, bs, bs)
    for i in range(0, plan.num_blocks, batch):
        j = min(i + batch, plan.num_blocks)
        pred = gen(ids[i:j].to(dev), feats["type_id"][i:j].to(dev),
                   feats["layer_id"][i:j].to(dev), feats["cont"][i:j].to(dev)).cpu()
        pred = pred * std[i:j][:, None, None] + mean[i:j][:, None, None]
        out[i:j] = pred
    return out


def reconstruct_state(ckpt_path: Path, device="cpu", logger: logging.Logger | None = None):
    gen, plan, mean, std, dev = load_checkpoint(ckpt_path, device)
    if logger:
        logger.info("Genero %d blocchi...", plan.num_blocks)
    blocks = generate_blocks(gen, plan, mean, std, dev)
    sd = reconstruct_state_dict(plan, blocks)
    return sd, plan


def load_reconstructed_model(model_id: str, ckpt_path: Path, device="auto", dtype=torch.float32,
                             logger: logging.Logger | None = None):
    """Carica il modello target e sostituisce i tensori coperti con quelli generati."""
    model, tok, dev = load_target_model(model_id, device, dtype)
    sd, plan = reconstruct_state(ckpt_path, device="cpu", logger=logger)
    params = dict(model.named_parameters())
    replaced = 0
    with torch.no_grad():
        for name, w in sd.items():
            if name in params and tuple(params[name].shape) == tuple(w.shape):
                params[name].data.copy_(w.to(params[name].dtype).to(params[name].device))
                replaced += 1
    if logger:
        logger.info("Tensori sostituiti: %d/%d", replaced, plan.num_tensors)
    return model, tok, dev, plan
