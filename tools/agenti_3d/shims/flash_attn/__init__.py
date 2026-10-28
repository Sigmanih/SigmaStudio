"""Sostituto di flash_attn sopra la SDPA di torch, solo per TRELLIS.

Su Windows con Blackwell (sm_120) non ci sono ruote di flash-attn e quelle di
xformers per cu128 arrivano senza kernel CUDA: la SDPA di torch invece usa gia'
i kernel efficienti della scheda. Le varianti "varlen" raggruppano i segmenti
di pari lunghezza in un unico batch, perche' le finestre degli attention
sparsi sono migliaia e una chiamata per finestra sarebbe troppo lenta.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def _sdpa(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    # flash_attn lavora in [B, N, H, C], la SDPA in [B, H, N, C]
    out = F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2))
    return out.transpose(1, 2)


def flash_attn_func(q, k, v, *args, **kwargs):
    return _sdpa(q, k, v)


def flash_attn_qkvpacked_func(qkv, *args, **kwargs):
    q, k, v = qkv.unbind(dim=2)
    return _sdpa(q, k, v)


def flash_attn_kvpacked_func(q, kv, *args, **kwargs):
    k, v = kv.unbind(dim=2)
    return _sdpa(q, k, v)


def _bounds(cu_seqlens: torch.Tensor) -> list[tuple[int, int]]:
    cu = cu_seqlens.tolist()
    return list(zip(cu[:-1], cu[1:]))


def flash_attn_varlen_func(q, k, v, cu_seqlens_q, cu_seqlens_k, *args, **kwargs):
    q_bounds = _bounds(cu_seqlens_q)
    k_bounds = _bounds(cu_seqlens_k)
    out = torch.empty(q.shape[0], q.shape[1], v.shape[2], dtype=q.dtype, device=q.device)

    groups: dict[tuple[int, int], list[int]] = {}
    for i, ((qs, qe), (ks, ke)) in enumerate(zip(q_bounds, k_bounds)):
        groups.setdefault((qe - qs, ke - ks), []).append(i)

    for (q_len, k_len), members in groups.items():
        q_idx = torch.cat([torch.arange(q_bounds[i][0], q_bounds[i][1], device=q.device) for i in members])
        k_idx = torch.cat([torch.arange(k_bounds[i][0], k_bounds[i][1], device=q.device) for i in members])
        n = len(members)
        qb = q[q_idx].view(n, q_len, *q.shape[1:])
        kb = k[k_idx].view(n, k_len, *k.shape[1:])
        vb = v[k_idx].view(n, k_len, *v.shape[1:])
        out[q_idx] = _sdpa(qb, kb, vb).reshape(n * q_len, *out.shape[1:])
    return out


def flash_attn_varlen_qkvpacked_func(qkv, cu_seqlens, *args, **kwargs):
    q, k, v = qkv.unbind(dim=1)
    return flash_attn_varlen_func(q, k, v, cu_seqlens, cu_seqlens)


def flash_attn_varlen_kvpacked_func(q, kv, cu_seqlens_q, cu_seqlens_k, *args, **kwargs):
    k, v = kv.unbind(dim=1)
    return flash_attn_varlen_func(q, k, v, cu_seqlens_q, cu_seqlens_k)
