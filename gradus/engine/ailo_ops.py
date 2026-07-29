"""Op del blocco AILO con forward E backward scritti a mano (solo matmul/elementwise).

Replica la matematica di modeling_ailo.py (LayerNorm bias=False, attention causale
con RoPE, SwiGLU) ma senza autograd: ogni layer salva nel forward cio' che serve e
calcola i gradienti a mano. Cosi' gira sulla 6750 via DirectML.
"""
from __future__ import annotations

import math
import torch

from .nn import Linear, silu, silu_grad


# --------------------------------------------------------------------------- LayerNorm
class LayerNorm:
    """LayerNorm sull'ultima dim, affine SENZA bias (come AILO)."""

    def __init__(self, dim, dev, eps=1e-5):
        self.g = torch.ones(dim, device=dev)
        self.eps = eps
        self.dg = None

    def forward(self, x):
        self._mu = x.mean(-1, keepdim=True)
        xc = x - self._mu
        self._var = (xc * xc).mean(-1, keepdim=True)
        self._rstd = (self._var + self.eps).rsqrt()
        self._xhat = xc * self._rstd
        return self._xhat * self.g

    def backward(self, dy):
        D = dy.shape[-1]
        self.dg = (dy * self._xhat).reshape(-1, D).sum(0)
        dxhat = dy * self.g
        m1 = dxhat.mean(-1, keepdim=True)
        m2 = (dxhat * self._xhat).mean(-1, keepdim=True)
        return self._rstd * (dxhat - m1 - self._xhat * m2)

    def params(self):
        return [self.g]

    def grads(self):
        return [self.dg]


# --------------------------------------------------------------------------- softmax
def softmax_lastdim(x):
    return torch.softmax(x, dim=-1)


def softmax_backward(p, dp):
    # p = softmax(x); dx = p*(dp - sum(dp*p))
    return p * (dp - (dp * p).sum(-1, keepdim=True))


# --------------------------------------------------------------------------- cache
# RoPE e maschera causale dipendono solo da (T, head_dim, base, device): ricostruirle
# a ogni forward di ogni layer costava migliaia di allocazioni per run. Sono costanti,
# quindi vengono calcolate una volta e riusate (chiave: forma + device).
_ROPE_CACHE: dict = {}
_MASK_CACHE: dict = {}


def _rope_base(T, head_dim, dev, base, ndim):
    key = (T, head_dim, float(base), str(dev), ndim)
    hit = _ROPE_CACHE.get(key)
    if hit is not None:
        return hit
    inv = 1.0 / (base ** (torch.arange(0, head_dim, 2, device=dev).float() / head_dim))
    t = torch.arange(T, device=dev).float()
    freqs = t[:, None] * inv[None, :]         # (T, hd/2)  -- broadcasting, DML-safe
    emb = torch.cat((freqs, freqs), dim=-1)   # (T, hd)
    cos, sin = emb.cos(), emb.sin()
    for _ in range(ndim):                      # (T,hd) -> (1,T,hd) oppure (1,1,T,hd)
        cos, sin = cos[None], sin[None]
    _ROPE_CACHE[key] = (cos, sin)
    return cos, sin


def causal_bias(T, dev, dtype=torch.float32):
    """Maschera causale additiva (T,T), cache per (T, device, dtype)."""
    key = (T, str(dev), str(dtype))
    hit = _MASK_CACHE.get(key)
    if hit is not None:
        return hit
    idx = torch.arange(T, device=dev)
    bias = (idx[None, :] > idx[:, None]).to(dtype) * (-1e9)   # niente triu (DML-safe)
    _MASK_CACHE[key] = bias
    return bias


def clear_op_caches():
    """Libera le cache RoPE/maschera (es. cambio device o fine run)."""
    _ROPE_CACHE.clear()
    _MASK_CACHE.clear()


# --------------------------------------------------------------------------- RoPE
def rope_tables(T, head_dim, dev, base=10000.0):
    return _rope_base(T, head_dim, dev, base, ndim=1)   # (1,T,hd) -> broadcast su (B*h,T,hd)


def _rotate_half(x):
    h = x.shape[-1] // 2
    x1, x2 = x[..., :h], x[..., h:]
    return torch.cat((-x2, x1), dim=-1)


def rope_fwd(x, cos, sin):
    return x * cos + _rotate_half(x) * sin


def rope_bwd(g, cos, sin):
    # trasposto: d/dx [x*cos + rotate_half(x)*sin] = g*cos - rotate_half(g*sin)
    return g * cos - _rotate_half(g * sin)


# --------------------------------------------------------------------------- Attention
class Attention:
    """Multi-head causale con RoPE, backward manuale."""

    def __init__(self, dim, n_heads, dev):
        self.h = n_heads
        self.hd = dim // n_heads
        self.scale = self.hd ** -0.5
        self.q = Linear(dim, dim, dev, seed=11)
        self.k = Linear(dim, dim, dev, seed=12)
        self.v = Linear(dim, dim, dev, seed=13)
        self.o = Linear(dim, dim, dev, seed=14)

    def _split(self, x, B, T):
        # (B,T,C) -> (B*h, T, hd), contiguo (DML-safe per le bmm 3D)
        return x.reshape(B, T, self.h, self.hd).permute(0, 2, 1, 3).reshape(B * self.h, T, self.hd).contiguous()

    def _merge(self, x, B, T):
        # (B*h, T, hd) -> (B, T, C)
        return x.reshape(B, self.h, T, self.hd).permute(0, 2, 1, 3).reshape(B, T, self.h * self.hd).contiguous()

    def _causal_bias(self, T, dev):
        return causal_bias(T, dev)

    def forward(self, x):
        B, T, C = x.shape
        self._BT = (B, T)
        cos, sin = rope_tables(T, self.hd, x.device)
        self._cos, self._sin = cos, sin
        qr = rope_fwd(self._split(self.q.forward(x), B, T), cos, sin)   # (B*h,T,hd)
        kr = rope_fwd(self._split(self.k.forward(x), B, T), cos, sin)
        v = self._split(self.v.forward(x), B, T)
        self._qr, self._kr, self._v = qr, kr, v
        # baddbmm fonde scores = bias + scale * (q @ k^T) in un solo kernel
        scores = torch.baddbmm(self._causal_bias(T, x.device), qr, kr.transpose(1, 2),
                               beta=1.0, alpha=self.scale)              # (B*h,T,T)
        p = softmax_lastdim(scores)
        self._p = p
        ctx = torch.bmm(p, v)                                           # (B*h,T,hd)
        return self.o.forward(self._merge(ctx, B, T))

    def backward(self, d_out):
        B, T = self._BT
        d_ctx = self._split(self.o.backward(d_out), B, T)               # (B*h,T,hd)
        dp = torch.bmm(d_ctx, self._v.transpose(1, 2))                  # (B*h,T,T)
        dv = torch.bmm(self._p.transpose(1, 2), d_ctx)                  # (B*h,T,hd)
        dscores = softmax_backward(self._p, dp) * self.scale
        dqr = torch.bmm(dscores, self._kr)                             # (B*h,T,hd)
        dkr = torch.bmm(dscores.transpose(1, 2), self._qr)
        dq = rope_bwd(dqr, self._cos, self._sin)
        dk = rope_bwd(dkr, self._cos, self._sin)
        dx = self.q.backward(self._merge(dq, B, T))
        dx = dx + self.k.backward(self._merge(dk, B, T))
        dx = dx + self.v.backward(self._merge(dv, B, T))
        return dx

    def params(self):
        return self.q.params() + self.k.params() + self.v.params() + self.o.params()

    def grads(self):
        return self.q.grads() + self.k.grads() + self.v.grads() + self.o.grads()


# --------------------------------------------------------------------------- SwiGLU
class SwiGLU:
    """w2( silu(w1(x)) * w3(x) ), backward manuale."""

    def __init__(self, dim, inter, dev):
        self.w1 = Linear(dim, inter, dev, seed=21)
        self.w2 = Linear(inter, dim, dev, seed=22)
        self.w3 = Linear(dim, inter, dev, seed=23)

    def forward(self, x):
        self._a = self.w1.forward(x)
        self._b = self.w3.forward(x)
        self._s = silu(self._a)
        return self.w2.forward(self._s * self._b)

    def backward(self, dy):
        dh = self.w2.backward(dy)
        ds = dh * self._b
        db = dh * self._s
        da = ds * silu_grad(self._a)
        dx = self.w1.backward(da) + self.w3.backward(db)
        return dx

    def params(self):
        return self.w1.params() + self.w2.params() + self.w3.params()

    def grads(self):
        return self.w1.grads() + self.w2.grads() + self.w3.grads()


# --------------------------------------------------------------------------- Block
class AILOBlock:
    """x + attn(ln1(x))  poi  x + ff(ln2(x)), backward manuale."""

    def __init__(self, dim, n_heads, inter, dev):
        self.ln1 = LayerNorm(dim, dev)
        self.attn = Attention(dim, n_heads, dev)
        self.ln2 = LayerNorm(dim, dev)
        self.ff = SwiGLU(dim, inter, dev)

    def forward(self, x):
        x_mid = x + self.attn.forward(self.ln1.forward(x))
        x_out = x_mid + self.ff.forward(self.ln2.forward(x_mid))
        return x_out

    def backward(self, dy):
        d_xmid = dy + self.ln2.backward(self.ff.backward(dy))
        d_xin = d_xmid + self.ln1.backward(self.attn.backward(d_xmid))
        return d_xin

    def params(self):
        return self.ln1.params() + self.attn.params() + self.ln2.params() + self.ff.params()

    def grads(self):
        return self.ln1.grads() + self.attn.grads() + self.ln2.grads() + self.ff.grads()
