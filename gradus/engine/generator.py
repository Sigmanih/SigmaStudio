"""Generatore di pesi del motore manuale: stessa architettura del PyTorch
AILOWeightGenerator, ma con forward E backward scritti a mano (gira sulla 6750).

  (latent[blocco] + type + layer + fourier(coord)) -> in_proj -> seq di token
  -> stack di blocchi AILO -> ln_f -> mean-pool -> head -> blocco BS×BS
"""
from __future__ import annotations

import math
import torch

from .nn import Linear, Embedding, VQLatent
from .ailo_ops import AILOBlock, LayerNorm


def fourier(cont, num_freqs=6):
    feats = [cont]
    for k in range(num_freqs):
        f = (2.0 ** k) * math.pi
        feats.append(torch.sin(f * cont))
        feats.append(torch.cos(f * cont))
    return torch.cat(feats, dim=-1)


class ManualGenerator:
    def __init__(self, num_blocks, num_types, num_layers, bs, dev,
                 latent_dim=48, type_dim=16, layer_dim=16, num_freqs=6,
                 seq_len=4, d_model=128, n_layers=4, n_heads=4, inter=256, vq_k=0):
        self.dev = dev
        self.bs = bs
        self.num_freqs = num_freqs
        self.seq_len = seq_len
        self.d_model = d_model
        self.cont_dim = 5
        self.use_latent = latent_dim > 0
        self.vq_k = vq_k
        if self.use_latent:
            self.latent = (VQLatent(num_blocks, latent_dim, vq_k, dev, seed=1)
                           if vq_k > 0 else Embedding(num_blocks, latent_dim, dev, seed=1))
        self.type_emb = Embedding(num_types, type_dim, dev, seed=2)
        self.layer_emb = Embedding(num_layers, layer_dim, dev, seed=3)
        ld = latent_dim if self.use_latent else 0
        in_features = ld + type_dim + layer_dim + self.cont_dim + self.cont_dim * 2 * num_freqs
        self._ld, self._td, self._yd = ld, type_dim, layer_dim
        self.in_proj = Linear(in_features, seq_len * d_model, dev, seed=4)
        self.blocks = [AILOBlock(d_model, n_heads, inter, dev) for _ in range(n_layers)]
        self.ln_f = LayerNorm(d_model, dev)
        self.head = Linear(d_model, bs * bs, dev, seed=5)

    def forward(self, block_ids, type_ids, layer_ids, cont):
        parts = [self.type_emb.forward(type_ids), self.layer_emb.forward(layer_ids),
                 fourier(cont, self.num_freqs)]
        if self.use_latent:
            parts.insert(0, self.latent.forward(block_ids))
        vec = torch.cat(parts, dim=-1)
        B = vec.shape[0]
        x = self.in_proj.forward(vec).reshape(B, self.seq_len, self.d_model)
        for b in self.blocks:
            x = b.forward(x)
        x = self.ln_f.forward(x)
        self._B = B
        h = x.mean(dim=1)                       # mean-pool (B, d_model)
        return self.head.forward(h)             # (B, bs*bs)

    def backward(self, dout):
        dh = self.head.backward(dout)           # (B, d_model)
        # backward del mean-pool: ogni posizione riceve dh/seq_len
        dx = (dh / self.seq_len).unsqueeze(1).expand(self._B, self.seq_len, self.d_model).contiguous()
        dx = self.ln_f.backward(dx)
        for b in reversed(self.blocks):
            dx = b.backward(dx)
        dvec = self.in_proj.backward(dx.reshape(self._B, self.seq_len * self.d_model))
        off = 0
        if self.use_latent:
            self.latent.backward(dvec[:, off:off + self._ld]); off += self._ld
        self.type_emb.backward(dvec[:, off:off + self._td]); off += self._td
        self.layer_emb.backward(dvec[:, off:off + self._yd]); off += self._yd
        # il resto (fourier) e' funzione di coord costanti: nessun gradiente
        return None

    def _modules(self):
        mods = [self.type_emb, self.layer_emb, self.in_proj, *self.blocks, self.ln_f, self.head]
        if self.use_latent:
            mods = [self.latent] + mods
        return mods

    def params(self):
        ps = []
        for m in self._modules():
            ps += m.params()
        return ps

    def grads(self):
        gs = []
        for m in self._modules():
            gs += m.grads()
        return gs

    def _adapter_modules(self):
        # tutto tranne il decoder (blocchi + ln_f): latent/type/layer + in_proj + head
        mods = [self.type_emb, self.layer_emb, self.in_proj, self.head]
        if self.use_latent:
            mods = [self.latent] + mods
        return mods

    def adapter_params(self):
        ps = []
        for m in self._adapter_modules():
            ps += m.params()
        return ps

    def adapter_grads(self):
        gs = []
        for m in self._adapter_modules():
            gs += m.grads()
        return gs


def build_ailo_generator(plan, num_types, bs, dev, latent_dim=48, seq_len=4,
                         backbone="ailo_backbone", vq_k=0, logger=None):
    """Costruisce il generatore con il DECODER = AILO pretrained (pesi caricati).

    Il backbone viene risolto (e se serve scaricato) da `gradus.backbone`: il
    path non dipende piu' dalla directory di lavoro, cosi' funziona anche quando
    il job del Training Lab gira nella propria cartella.
    """
    import json
    from pathlib import Path
    from safetensors.torch import load_file

    from ..backbone import ensure_ailo_backbone

    backbone = Path(ensure_ailo_backbone(backbone, logger=logger))
    cfg = json.loads((backbone / "config.json").read_text(encoding="utf-8"))
    d_model = cfg["hidden_size"]; n_layers = cfg["num_hidden_layers"]
    n_heads = cfg["num_attention_heads"]; inter = cfg["intermediate_size"]
    gen = ManualGenerator(plan.num_blocks, num_types, plan.num_layers, bs, dev,
                          latent_dim=latent_dim, d_model=d_model, n_layers=n_layers,
                          n_heads=n_heads, inter=inter, seq_len=seq_len, vq_k=vq_k)
    sd = load_file(str(backbone / "model.safetensors"))

    def cp(dst, key):
        dst.copy_(sd[key].to(dst.dtype).to(dst.device))

    for i, blk in enumerate(gen.blocks):
        p = f"blocks.{i}."
        cp(blk.ln1.g, p + "ln1.weight")
        cp(blk.attn.q.W, p + "attn.q_proj.weight")
        cp(blk.attn.k.W, p + "attn.k_proj.weight")
        cp(blk.attn.v.W, p + "attn.v_proj.weight")
        cp(blk.attn.o.W, p + "attn.out_proj.weight")
        cp(blk.ln2.g, p + "ln2.weight")
        cp(blk.ff.w1.W, p + "ff.w1.weight")
        cp(blk.ff.w2.W, p + "ff.w2.weight")
        cp(blk.ff.w3.W, p + "ff.w3.weight")
    cp(gen.ln_f.g, "ln_f.weight")
    return gen
