"""Op con backward MANUALE (solo matmul/elementwise) + Adam manuale.

Convenzione: ogni layer salva nel forward cio' che serve al backward; backward(dy)
ritorna dx e memorizza i gradienti dei parametri. Nessun uso di autograd.

Percorsi CUDA
-------------
Le versioni originali evitano scatter/index op perche' DirectML le sospende: gli
scatter sono emulati con matmul one-hot (N x K). Su CUDA quella matrice e' sia
lenta sia enorme (N=8192, K=30000 -> ~1 GB), quindi qui esiste un percorso
alternativo con `index_add_`/`bincount`, selezionato a runtime dal device.
Il percorso DML/CPU originale resta invariato: stessa matematica, stesso risultato.
"""
from __future__ import annotations

import math
import torch


def is_cuda_tensor(t: torch.Tensor) -> bool:
    """True solo per device CUDA/ROCm reali (i tensori DML riportano 'privateuseone')."""
    return t.device.type == "cuda"


def silu(x):
    return x * torch.sigmoid(x)


def silu_grad(x):
    s = torch.sigmoid(x)
    return s * (1 + x * (1 - s))


class Linear:
    """y = x @ W^T + b  con  x:(N,in)  W:(out,in)  b:(out)"""

    def __init__(self, nin, nout, dev, seed=None):
        g = torch.Generator(device="cpu")
        if seed is not None:
            g.manual_seed(seed)
        k = 1.0 / math.sqrt(nin)
        self.W = ((torch.rand(nout, nin, generator=g) * 2 - 1) * k).to(dev)
        self.b = torch.zeros(nout, device=dev)
        self.dW = None
        self.db = None
        self._x = None

    def forward(self, x):
        # gestisce dimensioni arbitrarie (..., in): appiattisce le dim iniziali
        self._shape = x.shape
        x2 = x.reshape(-1, x.shape[-1])
        self._x = x2
        y = x2 @ self.W.t() + self.b
        return y.reshape(*self._shape[:-1], self.W.shape[0])

    def backward(self, dy):
        dy2 = dy.reshape(-1, dy.shape[-1])
        self.dW = dy2.t() @ self._x
        self.db = dy2.sum(dim=0)
        dx = dy2 @ self.W
        return dx.reshape(self._shape)

    def params(self):
        return [self.W, self.b]

    def grads(self):
        return [self.dW, self.db]


class Embedding:
    """Tabella di embedding con backward manuale (grad = one-hot^T @ dy, DML-safe)."""

    def __init__(self, num, dim, dev, std=0.02, seed=None):
        g = torch.Generator(device="cpu")
        if seed is not None:
            g.manual_seed(seed)
        self.W = (torch.randn(num, dim, generator=g) * std).to(dev)
        self.num = num
        self.dW = None
        self._idx = None

    def forward(self, idx):
        self._idx = idx
        return self.W[idx]

    def backward(self, dy):
        # dW[r] = somma dei dy le cui idx==r
        if is_cuda_tensor(dy):
            # CUDA: scatter-add nativo, O(N*d) invece della one-hot O(N*num)
            self.dW = torch.zeros_like(self.W)
            self.dW.index_add_(0, self._idx, dy)
        else:
            # DML/CPU: one-hot^T @ dy (nessuna index op, device-safe)
            oh = (self._idx[:, None] == torch.arange(self.num, device=dy.device)[None, :]).to(dy.dtype)
            self.dW = oh.t() @ dy
        return None  # nessun gradiente verso gli indici

    def params(self):
        return [self.W]

    def grads(self):
        return [self.dW]


class VQLatent:
    """Latent con CODEBOOK condiviso (Vector Quantization, stile VQ-VAE + STE).

    A deploy si salvano SOLO: codebook C (K×d) + un indice per blocco (log2 K bit).
    Se i blocchi sono ridondanti collassano sugli stessi atomi -> compressione reale.
    Training: latent libero z per blocco, quantizzato all'atomo piu' vicino; STE manda
    il gradiente a z come identita'; commitment loss su z; codebook loss su C.
    """

    def __init__(self, num_blocks, dim, K, dev, beta=0.25, std=0.02, seed=1,
                 ema=True, decay=0.99, eps=1e-5):
        self.z = Embedding(num_blocks, dim, dev, std=std, seed=seed)   # latent libero (training)
        g = torch.Generator(device="cpu"); g.manual_seed(seed + 100)
        self.C = (torch.randn(K, dim, generator=g) * std).to(dev)       # codebook
        self.K = K
        self.beta = beta
        self.ema = ema
        self.decay = decay
        self.eps = eps
        self.dC = None
        self._zb = self._zq = self._idx = None
        if ema:                                                        # statistiche EMA del codebook
            self.ema_count = torch.zeros(K, device=dev)
            self.ema_sum = self.C.clone()

    def _nearest(self, zb):
        # ||z||^2 - 2 z·C + ||C||^2 ; il primo termine e' costante per riga e non
        # cambia l'argmin, quindi su CUDA si risparmia con un solo addmm fuso.
        if is_cuda_tensor(zb):
            d2 = torch.addmm((self.C * self.C).sum(1), zb, self.C.t(), alpha=-2.0)
            return d2.argmin(1)
        d2 = (zb * zb).sum(1, keepdim=True) - 2 * zb @ self.C.t() + (self.C * self.C).sum(1)
        return d2.argmin(1)

    def forward(self, ids):
        zb = self.z.forward(ids)                                        # (B,d)
        idx = self._nearest(zb)
        zq = self.C[idx]                                               # (B,d)
        self._zb, self._zq, self._idx = zb, zq, idx
        return zq                                                       # il decoder vede l'atomo

    def backward(self, g):
        # STE: grad verso z = g (identita') + commitment 2*beta*(z - zq)
        self.z.backward(g + 2 * self.beta * (self._zb - self._zq))
        if not self.ema:
            dc = 2 * (self._zq - self._zb)
            if is_cuda_tensor(g):
                self.dC = torch.zeros_like(self.C)
                self.dC.index_add_(0, self._idx, dc)
            else:
                oh = (self._idx[:, None] == torch.arange(self.K, device=g.device)[None, :]).to(g.dtype)
                self.dC = oh.t() @ dc
        return None

    @torch.no_grad()
    def ema_update(self, ids):
        """Aggiorna il codebook con media mobile dei latent assegnati + reinit atomi morti."""
        if not self.ema:
            return
        n = torch.zeros(self.K, device=self.C.device)
        s = torch.zeros_like(self.ema_sum)
        cuda = is_cuda_tensor(self.C)
        chunk = 65536 if cuda else 8192                                # su CUDA niente one-hot: chunk piu' grandi
        for i in range(0, len(ids), chunk):
            zb_c = self.z.W[ids[i:i + chunk]]
            idx_c = self._nearest(zb_c)
            if cuda:
                n += torch.bincount(idx_c, minlength=self.K).to(n.dtype)
                s.index_add_(0, idx_c, zb_c)
            else:
                oh = (idx_c[:, None] == torch.arange(self.K, device=zb_c.device)[None, :]).to(zb_c.dtype)
                n += oh.sum(0)
                s += oh.t() @ zb_c
        self.ema_count = self.decay * self.ema_count + (1 - self.decay) * n
        self.ema_sum = self.decay * self.ema_sum + (1 - self.decay) * s
        total = self.ema_count.sum()
        cnt = (self.ema_count + self.eps) / (total + self.K * self.eps) * total
        self.C = self.ema_sum / cnt[:, None]
        # reinit atomi "morti" (poco usati) su latent casuali
        dead = self.ema_count < 1.0
        if bool(dead.any()):
            pick = ids[torch.randint(0, len(ids), (int(dead.sum()),), device=ids.device)]
            self.C[dead] = self.z.W[pick]

    def params(self):
        return [self.z.W] if self.ema else [self.z.W, self.C]

    def grads(self):
        return [self.z.dW] if self.ema else [self.z.dW, self.dC]


def mse_loss(pred, target):
    """loss media su tutti gli elementi; ritorna (loss_scalar, dpred)."""
    diff = pred - target
    n = pred.numel()
    loss = (diff * diff).sum() / n
    dpred = (2.0 / n) * diff
    return loss, dpred


class MLP:
    """Linear -> SiLU -> Linear, tutto con backward manuale."""

    def __init__(self, sizes, dev, seed=0):
        self.l1 = Linear(sizes[0], sizes[1], dev, seed=seed)
        self.l2 = Linear(sizes[1], sizes[2], dev, seed=seed + 1)
        self._z1 = None

    def forward(self, x):
        self._z1 = self.l1.forward(x)
        a1 = silu(self._z1)
        return self.l2.forward(a1)

    def backward(self, dy):
        da1 = self.l2.backward(dy)
        dz1 = da1 * silu_grad(self._z1)
        return self.l1.backward(dz1)

    def params(self):
        return self.l1.params() + self.l2.params()

    def grads(self):
        return self.l1.grads() + self.l2.grads()


class Adam:
    """Adam manuale, aggiornamento in-place (solo elementwise). Con gradient clipping
    (clip della norma globale) per evitare la divergenza.

    Su CUDA usa i kernel `torch._foreach_*`: un solo kernel fuso per l'intera lista
    di parametri invece di ~6 kernel per parametro, e la norma per il clipping resta
    sul device (nessuna sincronizzazione host a ogni step).
    """

    def __init__(self, params, lr=1e-3, betas=(0.9, 0.999), eps=1e-8, clip_norm=1.0):
        self.params = params
        self.lr = lr
        self.b1, self.b2 = betas
        self.eps = eps
        self.clip_norm = clip_norm
        self.m = [torch.zeros_like(p) for p in params]
        self.v = [torch.zeros_like(p) for p in params]
        self.t = 0
        self._fused = bool(params) and is_cuda_tensor(params[0])

    def step(self, grads):
        self.t += 1
        bc1 = 1 - self.b1 ** self.t
        bc2 = 1 - self.b2 ** self.t
        if self._fused:
            self._step_foreach(grads, bc1, bc2)
        else:
            self._step_loop(grads, bc1, bc2)

    # -- percorso CUDA ------------------------------------------------------
    def _step_foreach(self, grads, bc1, bc2):
        if self.clip_norm and self.clip_norm > 0:
            total = torch.linalg.vector_norm(torch.stack(torch._foreach_norm(grads)))
            # clamp <= 1: se la norma e' sotto soglia il fattore vale 1 (no-op),
            # esattamente come il ramo `if total > clip_norm` originale.
            scale = (self.clip_norm / (total + 1e-6)).clamp(max=1.0)
            grads = torch._foreach_mul(grads, scale)

        # m = b1*m + (1-b1)*g
        torch._foreach_lerp_(self.m, grads, 1 - self.b1)
        # v = b2*v + (1-b2)*g^2
        torch._foreach_mul_(self.v, self.b2)
        torch._foreach_addcmul_(self.v, grads, grads, value=1 - self.b2)
        # p -= (lr/bc1) * m / (sqrt(v)/sqrt(bc2) + eps)
        denom = torch._foreach_sqrt(self.v)
        torch._foreach_div_(denom, math.sqrt(bc2))
        torch._foreach_add_(denom, self.eps)
        torch._foreach_addcdiv_(self.params, self.m, denom, value=-self.lr / bc1)

    # -- percorso DML/CPU (invariato) ---------------------------------------
    def _step_loop(self, grads, bc1, bc2):
        if self.clip_norm and self.clip_norm > 0:
            total = sum((g * g).sum() for g in grads).sqrt()
            if float(total) > self.clip_norm:
                scale = self.clip_norm / (float(total) + 1e-6)
                grads = [g * scale for g in grads]
        for i, (p, g) in enumerate(zip(self.params, grads)):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * (g * g)
            mhat = self.m[i] / bc1
            vhat = self.v[i] / bc2
            p -= self.lr * mhat / (vhat.sqrt() + self.eps)
