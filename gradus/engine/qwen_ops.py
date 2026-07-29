"""Op dell'architettura Qwen2 con forward E backward manuali (DML-safe, bmm 3D).

Differenze da AILO: RMSNorm (no centratura), GQA (num_kv_heads < num_heads),
bias su q/k/v, RoPE theta=1e6. MLP SwiGLU = SwiGLU di ailo_ops (gate=w1, up=w3, down=w2).
"""
from __future__ import annotations

import torch

from .nn import Linear, silu, silu_grad
from .ailo_ops import softmax_lastdim, softmax_backward, _rotate_half, _rope_base, causal_bias


# --------------------------------------------------------------------------- RMSNorm
class RMSNorm:
    def __init__(self, dim, dev, eps=1e-6):
        self.g = torch.ones(dim, device=dev)
        self.eps = eps
        self.dg = None

    def forward(self, x):
        self._rms = (x.pow(2).mean(-1, keepdim=True) + self.eps).rsqrt()
        self._xhat = x * self._rms
        return self._xhat * self.g

    def backward(self, dy):
        D = dy.shape[-1]
        self.dg = (dy * self._xhat).reshape(-1, D).sum(0)
        dxhat = dy * self.g
        m = (dxhat * self._xhat).mean(-1, keepdim=True)
        return self._rms * (dxhat - self._xhat * m)

    def params(self):
        return [self.g]

    def grads(self):
        return [self.dg]


def rope_tables4(T, head_dim, dev, base=1e6):
    return _rope_base(T, head_dim, dev, base, ndim=2)     # (1,1,T,hd), cached


def rope_fwd(x, cos, sin):
    return x * cos + _rotate_half(x) * sin


def rope_bwd(g, cos, sin):
    return g * cos - _rotate_half(g * sin)


# --------------------------------------------------------------------------- Attention (GQA)
class QwenAttention:
    def __init__(self, hidden, n_heads, n_kv, dev, theta=1e6):
        self.nh = n_heads
        self.nkv = n_kv
        self.rep = n_heads // n_kv
        self.hd = hidden // n_heads
        self.scale = self.hd ** -0.5
        self.theta = theta
        self.q = Linear(hidden, n_heads * self.hd, dev, seed=31)      # con bias
        self.k = Linear(hidden, n_kv * self.hd, dev, seed=32)
        self.v = Linear(hidden, n_kv * self.hd, dev, seed=33)
        self.o = Linear(n_heads * self.hd, hidden, dev, seed=34)      # senza bias (b=0)

    def _causal_bias(self, T, dev):
        return causal_bias(T, dev)

    def forward(self, x):
        B, T, C = x.shape
        self._BT = (B, T)
        hd, nh, nkv, rep = self.hd, self.nh, self.nkv, self.rep
        q = self.q.forward(x).reshape(B, T, nh, hd).permute(0, 2, 1, 3)      # (B,nh,T,hd)
        k = self.k.forward(x).reshape(B, T, nkv, hd).permute(0, 2, 1, 3)     # (B,nkv,T,hd)
        v = self.v.forward(x).reshape(B, T, nkv, hd).permute(0, 2, 1, 3)
        cos, sin = rope_tables4(T, hd, x.device, self.theta)
        self._cos, self._sin = cos, sin
        q = rope_fwd(q, cos, sin)
        k = rope_fwd(k, cos, sin)
        # GQA: ripeti le teste kv (expand+reshape, DML-safe)
        kr = k[:, :, None, :, :].expand(B, nkv, rep, T, hd).reshape(B, nh, T, hd).contiguous()
        vr = v[:, :, None, :, :].expand(B, nkv, rep, T, hd).reshape(B, nh, T, hd).contiguous()
        q3 = q.reshape(B * nh, T, hd); k3 = kr.reshape(B * nh, T, hd); v3 = vr.reshape(B * nh, T, hd)
        scores = torch.baddbmm(self._causal_bias(T, x.device), q3, k3.transpose(1, 2),
                               beta=1.0, alpha=self.scale)
        p = softmax_lastdim(scores)
        self._p, self._q3, self._k3, self._v3 = p, q3, k3, v3
        ctx = torch.bmm(p, v3).reshape(B, nh, T, hd).permute(0, 2, 1, 3).reshape(B, T, nh * hd).contiguous()
        return self.o.forward(ctx)

    def backward(self, d_out):
        B, T = self._BT
        hd, nh, nkv, rep = self.hd, self.nh, self.nkv, self.rep
        d_ctx = self.o.backward(d_out).reshape(B, T, nh, hd).permute(0, 2, 1, 3).reshape(B * nh, T, hd).contiguous()
        dp = torch.bmm(d_ctx, self._v3.transpose(1, 2))
        dv3 = torch.bmm(self._p.transpose(1, 2), d_ctx)
        dscores = softmax_backward(self._p, dp) * self.scale
        dq3 = torch.bmm(dscores, self._k3)
        dk3 = torch.bmm(dscores.transpose(1, 2), self._q3)
        # de-ripeti GQA: somma sui gruppi
        dq = dq3.reshape(B, nh, T, hd)
        dk = dk3.reshape(B, nkv, rep, T, hd).sum(2)
        dv = dv3.reshape(B, nkv, rep, T, hd).sum(2)
        dq = rope_bwd(dq, self._cos, self._sin)
        dk = rope_bwd(dk, self._cos, self._sin)
        dxq = self.q.backward(dq.permute(0, 2, 1, 3).reshape(B, T, nh * hd).contiguous())
        dxk = self.k.backward(dk.permute(0, 2, 1, 3).reshape(B, T, nkv * hd).contiguous())
        dxv = self.v.backward(dv.permute(0, 2, 1, 3).reshape(B, T, nkv * hd).contiguous())
        return dxq + dxk + dxv

    def params(self):
        return self.q.params() + self.k.params() + self.v.params() + self.o.params()

    def grads(self):
        return self.q.grads() + self.k.grads() + self.v.grads() + self.o.grads()


# --------------------------------------------------------------------------- MLP (SwiGLU)
class QwenMLP:
    def __init__(self, hidden, inter, dev):
        self.gate = Linear(hidden, inter, dev, seed=41)   # w1
        self.up = Linear(hidden, inter, dev, seed=42)     # w3
        self.down = Linear(inter, hidden, dev, seed=43)   # w2

    def forward(self, x):
        self._g = self.gate.forward(x)
        self._u = self.up.forward(x)
        self._s = silu(self._g)
        return self.down.forward(self._s * self._u)

    def backward(self, dy):
        dh = self.down.backward(dy)
        ds = dh * self._u
        du = dh * self._s
        dg = ds * silu_grad(self._g)
        return self.gate.backward(dg) + self.up.backward(du)

    def params(self):
        return self.gate.params() + self.up.params() + self.down.params()

    def grads(self):
        return self.gate.grads() + self.up.grads() + self.down.grads()


# --------------------------------------------------------------------------- Layer
class QwenLayer:
    def __init__(self, hidden, n_heads, n_kv, inter, dev, eps=1e-6, theta=1e6):
        self.ln1 = RMSNorm(hidden, dev, eps)
        self.attn = QwenAttention(hidden, n_heads, n_kv, dev, theta)
        self.ln2 = RMSNorm(hidden, dev, eps)
        self.mlp = QwenMLP(hidden, inter, dev)

    def forward(self, x):
        x = x + self.attn.forward(self.ln1.forward(x))
        x = x + self.mlp.forward(self.ln2.forward(x))
        return x

    def backward(self, dy):
        d_mid = dy + self.ln2.backward(self.mlp.backward(dy))
        d_in = d_mid + self.ln1.backward(self.attn.backward(d_mid))
        return d_in

    def params(self):
        return self.ln1.params() + self.attn.params() + self.ln2.params() + self.mlp.params()

    def grads(self):
        return self.ln1.grads() + self.attn.grads() + self.ln2.grads() + self.mlp.grads()
