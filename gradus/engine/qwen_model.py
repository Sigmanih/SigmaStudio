"""Qwen2 completo con forward/backward MANUALI (gira sul 6750).

Serve al task objective: iniettiamo i pesi generati in un Linear interno, facciamo
forward+backward manuale, e leggiamo il .dW di quel Linear = dL/dW_generato.
Niente autograd del framework -> niente TDR su DirectML.
"""
from __future__ import annotations

import torch

from .nn import Linear, Embedding
from .qwen_ops import RMSNorm, QwenLayer


def cross_entropy(logits, labels):
    """logits (B,T,V), labels (B,T). Shift (prevedi il token successivo)."""
    B, T, V = logits.shape
    lg = logits[:, :-1, :].reshape(-1, V)
    tgt = labels[:, 1:].reshape(-1)
    m = lg.max(-1, keepdim=True).values
    z = lg - m
    e = z.exp()
    sume = e.sum(-1, keepdim=True)
    p = e / sume
    logp = z - sume.log()
    oh = (tgt[:, None] == torch.arange(V, device=lg.device)[None, :]).to(p.dtype)
    N = lg.shape[0]
    loss = -(oh * logp).sum() / N
    dlg = (p - oh) / N
    dlogits = torch.cat([dlg.reshape(B, T - 1, V), torch.zeros(B, 1, V, device=logits.device)], dim=1)
    return loss, dlogits


class QwenModel:
    def __init__(self, hidden, n_layers, n_heads, n_kv, inter, vocab, dev,
                 eps=1e-6, theta=1e6):  # theta: vedi model_hparams() in modelio.py
        self.embed = Embedding(vocab, hidden, dev)     # tok_emb; lm_head legata a embed.W
        self.layers = [QwenLayer(hidden, n_heads, n_kv, inter, dev, eps, theta)
                       for _ in range(n_layers)]
        self.norm = RMSNorm(hidden, dev, eps)
        self.dev = dev

    # ---- caricamento pesi dal modello HF ----
    def load_hf(self, hf_model):
        sd = hf_model.state_dict()
        def cp(dst, key): dst.copy_(sd[key].to(dst.dtype).to(dst.device))
        cp(self.embed.W, "model.embed_tokens.weight")
        for i, L in enumerate(self.layers):
            p = f"model.layers.{i}."
            cp(L.ln1.g, p + "input_layernorm.weight")
            cp(L.attn.q.W, p + "self_attn.q_proj.weight"); cp(L.attn.q.b, p + "self_attn.q_proj.bias")
            cp(L.attn.k.W, p + "self_attn.k_proj.weight"); cp(L.attn.k.b, p + "self_attn.k_proj.bias")
            cp(L.attn.v.W, p + "self_attn.v_proj.weight"); cp(L.attn.v.b, p + "self_attn.v_proj.bias")
            cp(L.attn.o.W, p + "self_attn.o_proj.weight")
            cp(L.ln2.g, p + "post_attention_layernorm.weight")
            cp(L.mlp.gate.W, p + "mlp.gate_proj.weight")
            cp(L.mlp.up.W, p + "mlp.up_proj.weight")
            cp(L.mlp.down.W, p + "mlp.down_proj.weight")
        cp(self.norm.g, "model.norm.weight")
        return self

    def forward(self, input_ids, labels):
        x = self.embed.forward(input_ids)              # (B,T,H)
        for L in self.layers:
            x = L.forward(x)
        x = self.norm.forward(x)
        self._xf = x
        logits = x @ self.embed.W.t()                  # lm_head legata
        loss, self._dlogits = cross_entropy(logits, labels)
        return loss

    def backward(self):
        dx = self._dlogits @ self.embed.W              # lm_head bwd (embed.W congelata)
        dx = self.norm.backward(dx)
        for L in reversed(self.layers):
            dx = L.backward(dx)
        return dx                                       # (grad verso l'embedding, ignorato)
