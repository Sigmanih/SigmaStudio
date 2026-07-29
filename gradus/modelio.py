"""I/O modello target + 'blockify': spezzettare le matrici in blocchi quadrati
e tenere un indice globale dei blocchi (il dataset per il generatore)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import torch

from .config import GradusConfig, pick_device, torch_device


_LAYER_RE = re.compile(r"layers?\.(\d+)\.")


def load_hf_dataset(name: str, *args, **kwargs):
    """load_dataset() tollerante agli id 'canonici' ritirati da HuggingFace.

    Gli id senza namespace ('wikitext', 'imdb', ...) non sono piu' risolvibili:
    huggingface_hub pretende 'namespace/name'. I dataset sono stati spostati
    sotto l'organizzazione che li mantiene ('Salesforce/wikitext'). Qui si prova
    prima il nome dato e poi l'alias noto, cosi' funziona su entrambe le
    generazioni della libreria `datasets`.
    """
    from datasets import load_dataset

    aliases = {
        "wikitext": "Salesforce/wikitext",
        "openwebtext": "Skylion007/openwebtext",
        "tiny_shakespeare": "karpathy/tiny_shakespeare",
    }
    try:
        return load_dataset(name, *args, **kwargs)
    except Exception:
        alt = aliases.get(name)
        if not alt:
            raise
        return load_dataset(alt, *args, **kwargs)


def config_get(cfg, name: str, default=None):
    """Legge un iperparametro dalla config HF, indipendentemente dalla versione.

    transformers 5.x ha raggruppato i parametri RoPE in `rope_parameters`
    ({'rope_type': ..., 'rope_theta': ...}); in 4.x erano attributi piatti
    (`rope_theta`). Qui si prova prima l'attributo diretto e poi i contenitori
    noti, cosi' lo stesso codice gira su entrambe le versioni.
    """
    value = getattr(cfg, name, None)
    if value is not None:
        return value
    for container in ("rope_parameters", "rope_scaling", "text_config"):
        holder = getattr(cfg, container, None)
        if isinstance(holder, dict) and holder.get(name) is not None:
            return holder[name]
        if holder is not None and not isinstance(holder, dict):
            nested = getattr(holder, name, None)
            if nested is not None:
                return nested
    return default


def model_hparams(cfg) -> dict:
    """Iperparametri architetturali del modello target, normalizzati.

    Serve al motore manuale (QwenModel), che deve ricostruire l'architettura a
    mano e quindi non puo' affidarsi al modello HF per questi valori.
    """
    return {
        "hidden": config_get(cfg, "hidden_size"),
        "n_layers": config_get(cfg, "num_hidden_layers"),
        "n_heads": config_get(cfg, "num_attention_heads"),
        "n_kv": config_get(cfg, "num_key_value_heads") or config_get(cfg, "num_attention_heads"),
        "inter": config_get(cfg, "intermediate_size"),
        "vocab": config_get(cfg, "vocab_size"),
        "eps": config_get(cfg, "rms_norm_eps", 1e-6),
        "theta": float(config_get(cfg, "rope_theta", 1e6)),
    }

# Tipi semantici di tensore: danno al generatore il "contesto" (q/k/v/o/gate/up/down...).
# L'indice 0 e' "other"; l'ordine definisce gli id usati dall'embedding del generatore.
TENSOR_TYPES = [
    "other", "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj", "embed", "lm_head",
]
_TYPE_INDEX = {t: i for i, t in enumerate(TENSOR_TYPES)}


def tensor_type_id(name: str) -> int:
    n = name.lower()
    for t in TENSOR_TYPES[1:]:
        if t in n:
            return _TYPE_INDEX[t]
    if "embed_tokens" in n or "wte" in n:
        return _TYPE_INDEX["embed"]
    return 0


def load_target_model(model_id: str, device: str = "auto", dtype=torch.float32):
    """Carica un causal LM HF + tokenizer. Gira su CPU, CUDA, MPS o DirectML (AMD)."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    label = pick_device(device)
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype)
    model.to(torch_device(label))
    model.eval()
    return model, tok, label


def _layer_index(name: str) -> int:
    m = _LAYER_RE.search(name)
    return int(m.group(1)) if m else -1


@dataclass
class TensorEntry:
    name: str
    rows: int
    cols: int
    layer: int
    grid_r: int
    grid_c: int
    block_start: int   # indice del primo blocco di questo tensore nell'indice globale
    ttype: int = 0     # tipo semantico (vedi TENSOR_TYPES)


class TensorPlan:
    """Catalogo dei tensori 2D da comprimere e mappa verso i blocchi globali."""

    def __init__(self, block_size: int):
        self.block_size = block_size
        self.entries: list[TensorEntry] = []
        # per ogni blocco globale: (tensor_idx, block_row, block_col)
        self.block_index: list[tuple[int, int, int]] = []

    @property
    def num_blocks(self) -> int:
        return len(self.block_index)

    @property
    def num_tensors(self) -> int:
        return len(self.entries)

    @property
    def num_layers(self) -> int:
        # +1 per il caso layer == -1 (tensori fuori dai blocchi, es. embed/lm_head)
        return max((e.layer for e in self.entries), default=0) + 2

    def add(self, name: str, rows: int, cols: int) -> None:
        bs = self.block_size
        grid_r = (rows + bs - 1) // bs
        grid_c = (cols + bs - 1) // bs
        start = len(self.block_index)
        ti = len(self.entries)
        self.entries.append(
            TensorEntry(name, rows, cols, _layer_index(name), grid_r, grid_c, start,
                        ttype=tensor_type_id(name))
        )
        for br in range(grid_r):
            for bc in range(grid_c):
                self.block_index.append((ti, br, bc))

    def features(self) -> dict:
        """Contesto per ogni blocco (l'idea 'piu' contesto al generatore'):
          type_id  (num_blocks,)  long  -> q/k/v/o/gate/up/down/embed ...
          layer_id (num_blocks,)  long  -> indice del layer (clamp >=0)
          cont     (num_blocks,5) float -> [br_norm, bc_norm, br_abs, bc_abs, aspect]
        cosi' AILO puo' imparare regolarita' TRA layer e TRA tipi, non una sola matrice.
        """
        n = self.num_blocks
        type_id = torch.zeros(n, dtype=torch.long)
        layer_id = torch.zeros(n, dtype=torch.long)
        cont = torch.zeros(n, 5, dtype=torch.float32)
        for gi, (ti, br, bc) in enumerate(self.block_index):
            e = self.entries[ti]
            type_id[gi] = e.ttype
            layer_id[gi] = e.layer + 1 if e.layer >= 0 else 0
            cont[gi, 0] = br / max(1, e.grid_r)
            cont[gi, 1] = bc / max(1, e.grid_c)
            cont[gi, 2] = (br * self.block_size) / max(1, e.rows)
            cont[gi, 3] = (bc * self.block_size) / max(1, e.cols)
            cont[gi, 4] = e.rows / (e.rows + e.cols)
        return {"type_id": type_id, "layer_id": layer_id, "cont": cont}

    def block_ids(self) -> torch.Tensor:
        return torch.arange(self.num_blocks, dtype=torch.long)

    def valid_dims(self) -> tuple[torch.Tensor, torch.Tensor]:
        """Per ogni blocco le dimensioni valide (non-pad): (num_blocks,), (num_blocks,)."""
        bs = self.block_size
        vr = torch.zeros(self.num_blocks, dtype=torch.long)
        vc = torch.zeros(self.num_blocks, dtype=torch.long)
        for gi, (ti, br, bc) in enumerate(self.block_index):
            e = self.entries[ti]
            vr[gi] = min(bs, e.rows - br * bs)
            vc[gi] = min(bs, e.cols - bc * bs)
        return vr, vc

    def to_dict(self) -> dict:
        return {
            "block_size": self.block_size,
            "entries": [
                {"name": e.name, "rows": e.rows, "cols": e.cols} for e in self.entries
            ],
        }

    @staticmethod
    def from_dict(d: dict) -> "TensorPlan":
        plan = TensorPlan(d["block_size"])
        for e in d["entries"]:
            plan.add(e["name"], e["rows"], e["cols"])
        return plan


def build_plan(model, cfg: GradusConfig) -> TensorPlan:
    """Costruisce il piano dei blocchi dai parametri 2D del modello."""
    plan = TensorPlan(cfg.block.block_size)
    inc = cfg.train.include
    max_layers = cfg.train.max_layers
    for name, p in model.named_parameters():
        if p.ndim != 2:
            continue
        if p.numel() < cfg.block.min_tensor_numel:
            continue
        if inc and inc not in name:
            continue
        if max_layers >= 0:
            li = _layer_index(name)
            if li >= 0 and li >= max_layers:
                continue
        rows, cols = p.shape
        plan.add(name, rows, cols)
    return plan


def materialize_targets(model, plan: TensorPlan) -> torch.Tensor:
    """Estrae i blocchi target (padded a BS×BS) in un tensore (num_blocks, BS, BS)."""
    bs = plan.block_size
    targets = torch.zeros(plan.num_blocks, bs, bs, dtype=torch.float32)
    params = dict(model.named_parameters())
    for ti, e in enumerate(plan.entries):
        w = params[e.name].detach().to(torch.float32).cpu()
        for br in range(e.grid_r):
            for bc in range(e.grid_c):
                gi = e.block_start + br * e.grid_c + bc
                r0, c0 = br * bs, bc * bs
                blk = w[r0:r0 + bs, c0:c0 + bs]
                targets[gi, : blk.shape[0], : blk.shape[1]] = blk
    return targets


def reconstruct_state_dict(plan: TensorPlan, blocks: torch.Tensor) -> dict[str, torch.Tensor]:
    """Da (num_blocks, BS, BS) ricostruisce i tensori originali (croppati)."""
    bs = plan.block_size
    out: dict[str, torch.Tensor] = {}
    for e in plan.entries:
        w = torch.zeros(e.rows, e.cols, dtype=torch.float32)
        for br in range(e.grid_r):
            for bc in range(e.grid_c):
                gi = e.block_start + br * e.grid_c + bc
                r0, c0 = br * bs, bc * bs
                r1, c1 = min(r0 + bs, e.rows), min(c0 + bs, e.cols)
                w[r0:r1, c0:c1] = blocks[gi, : r1 - r0, : c1 - c0]
        out[e.name] = w
    return out


def plan_summary(plan: TensorPlan) -> dict:
    total_params = sum(e.rows * e.cols for e in plan.entries)
    return {
        "tensors": plan.num_tensors,
        "blocks": plan.num_blocks,
        "block_size": plan.block_size,
        "params_covered": total_params,
        "params_covered_M": round(total_params / 1e6, 2),
    }
