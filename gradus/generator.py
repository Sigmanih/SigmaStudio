"""Il generatore di pesi.

Idea: per ogni blocco un *latent* piccolo; un *decoder condiviso* (il backbone AILO)
mappa (latent + CONTESTO) -> blocco di pesi BS×BS. Il contesto = tipo (q/k/v/o/gate/
up/down...), layer, posizione del blocco. Cosi' il decoder puo' imparare regolarita'
condivise TRA layer e TRA tipi, avvicinandosi a una vera "funzione dei pesi".

Due varianti:
  - AILOWeightGenerator : i transformer block di AILO come decoder condiviso.
  - MLPWeightGenerator  : baseline coordinate-INR (per confronto onesto).
"""
from __future__ import annotations

import torch
import torch.nn as nn

from .config import GeneratorConfig


def fourier_features(coords: torch.Tensor, num_freqs: int = 6) -> torch.Tensor:
    """coords (B, C) -> (B, C + C*2*num_freqs) con encoding sin/cos."""
    feats = [coords]
    for k in range(num_freqs):
        freq = (2.0 ** k) * torch.pi
        feats.append(torch.sin(freq * coords))
        feats.append(torch.cos(freq * coords))
    return torch.cat(feats, dim=-1)


def _make_head(in_dim: int, out_dim: int, hidden: int) -> nn.Module:
    if hidden and hidden > 0:
        return nn.Sequential(
            nn.Linear(in_dim, hidden), nn.GELU(), nn.Linear(hidden, out_dim)
        )
    return nn.Linear(in_dim, out_dim)


class _BaseGenerator(nn.Module):
    def __init__(self, num_blocks, block_size, num_types, num_layers,
                 cfg: GeneratorConfig, num_freqs: int = 6):
        super().__init__()
        self.block_size = block_size
        self.out_dim = block_size * block_size
        self.num_freqs = num_freqs
        self.cont_dim = 5  # vedi TensorPlan.features()['cont']
        type_emb_dim = 16
        layer_emb_dim = 16
        # latent_dim == 0  =>  FUNZIONE PURA: nessun latent libero per blocco, il peso
        # dipende SOLO dalle coordinate (layer/tipo/posizione). E' il "sogno 500B":
        # memoria = solo il generatore. latent_dim > 0 => versione con latent appresi.
        self.use_latent = cfg.latent_dim > 0
        if self.use_latent:
            self.latent = nn.Embedding(num_blocks, cfg.latent_dim)
            nn.init.normal_(self.latent.weight, std=0.02)
        latent_dim = cfg.latent_dim if self.use_latent else 0
        self.type_emb = nn.Embedding(max(1, num_types), type_emb_dim)
        self.layer_emb = nn.Embedding(max(1, num_layers), layer_emb_dim)
        nn.init.normal_(self.type_emb.weight, std=0.02)
        nn.init.normal_(self.layer_emb.weight, std=0.02)
        # dimensione del vettore di input al decoder
        self.in_features = (
            latent_dim + type_emb_dim + layer_emb_dim
            + self.cont_dim + self.cont_dim * 2 * num_freqs
        )

    def _context(self, block_ids, type_ids, layer_ids, cont) -> torch.Tensor:
        te = self.type_emb(type_ids)
        le = self.layer_emb(layer_ids)
        cf = fourier_features(cont, self.num_freqs)
        parts = [te, le, cf]
        if self.use_latent:
            parts.insert(0, self.latent(block_ids))
        return torch.cat(parts, dim=-1)

    def _emit(self, vec: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError

    def forward(self, block_ids, type_ids, layer_ids, cont) -> torch.Tensor:
        vec = self._context(block_ids, type_ids, layer_ids, cont)
        out = self._emit(vec)
        return out.view(-1, self.block_size, self.block_size)


class MLPWeightGenerator(_BaseGenerator):
    """Baseline: (latent + contesto) -> MLP -> blocco. Nessun AILO."""

    def __init__(self, num_blocks, block_size, num_types, num_layers, cfg: GeneratorConfig):
        super().__init__(num_blocks, block_size, num_types, num_layers, cfg)
        h = cfg.mlp_hidden
        self.net = nn.Sequential(
            nn.Linear(self.in_features, h), nn.GELU(),
            nn.Linear(h, h), nn.GELU(),
            nn.Linear(h, self.out_dim),
        )

    def _emit(self, vec):
        return self.net(vec)


class AILOWeightGenerator(_BaseGenerator):
    """Decoder condiviso = i transformer block di AILO (architettura custom).

    AILO non e' Llama-standard: espone `tok_emb, blocks, ln_f, head` e ogni block fa
    x -> x + attn(ln1(x)) + ff(ln2(x))  prendendo solo x (B,T,C). Riusiamo `blocks` +
    `ln_f` come stack condiviso, sostituendo tok_emb/head con una proiezione
    (latent+contesto) -> seq di 'token' e una testa -> blocco di pesi.
    """

    def __init__(self, num_blocks, block_size, num_types, num_layers, cfg: GeneratorConfig):
        super().__init__(num_blocks, block_size, num_types, num_layers, cfg)
        from pathlib import Path
        from transformers import AutoModelForCausalLM
        from .config import AILO_BACKBONE

        # preferisci la copia locale in safetensors (necessaria con torch<2.6 / DirectML,
        # dove transformers rifiuta il torch.load dei .bin). Vedi README / setup GPU.
        backbone = cfg.backbone
        if backbone == AILO_BACKBONE and Path("ailo_backbone/model.safetensors").exists():
            backbone = "ailo_backbone"
        causal = AutoModelForCausalLM.from_pretrained(backbone, trust_remote_code=True)
        d_model = causal.config.hidden_size
        self.d_model = d_model
        self.seq_len = max(1, cfg.seq_len)

        # aggancia SOLO lo stack transformer + norm finale (scarta tok_emb/head testuali)
        self.blocks = causal.blocks
        self.ln_f = causal.ln_f

        if cfg.freeze_backbone:
            for p in self.blocks.parameters():
                p.requires_grad_(False)
            for p in self.ln_f.parameters():
                p.requires_grad_(False)

        self.in_proj = nn.Linear(self.in_features, self.seq_len * d_model)
        self.head = _make_head(d_model, self.out_dim, cfg.head_hidden)

    def _emit(self, vec):
        b = vec.shape[0]
        x = self.in_proj(vec).view(b, self.seq_len, self.d_model)
        for block in self.blocks:
            x = block(x)
        x = self.ln_f(x)
        h = x.mean(dim=1)                                # pooling (B, d_model)
        return self.head(h)


def build_generator(kind, num_blocks, block_size, num_types, num_layers,
                    cfg: GeneratorConfig) -> nn.Module:
    if kind == "ailo":
        return AILOWeightGenerator(num_blocks, block_size, num_types, num_layers, cfg)
    if kind == "mlp":
        return MLPWeightGenerator(num_blocks, block_size, num_types, num_layers, cfg)
    raise ValueError(f"Generatore sconosciuto: {kind!r} (usa 'ailo' o 'mlp')")


def count_params(module: nn.Module, trainable_only: bool = False) -> int:
    return sum(p.numel() for p in module.parameters() if (p.requires_grad or not trainable_only))
