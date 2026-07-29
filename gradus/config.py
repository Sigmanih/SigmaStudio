"""Configurazioni e preset del progetto Gradus."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional
import json
from pathlib import Path

import torch

# Preset di modelli target supportati per prototipare.
MODEL_PRESETS = {
    "qwen0.5b": "Qwen/Qwen2.5-0.5B",
    "qwen0.5b-instruct": "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen1.5b": "Qwen/Qwen2.5-1.5B",
    "gemma2b": "google/gemma-2-2b",
}

# Generatore di default: il backbone AILO come decoder condiviso.
AILO_BACKBONE = "xxrickyxx/ailo-152m"


def resolve_model(name: str) -> str:
    """Accetta sia un preset ('qwen0.5b') sia un id HF / path locale."""
    return MODEL_PRESETS.get(name.lower(), name)


def _directml_available() -> bool:
    try:
        import torch_directml  # noqa: F401
        return torch_directml.is_available()
    except Exception:
        return False


def _xpu_available() -> bool:
    xpu = getattr(torch, "xpu", None)
    try:
        return xpu is not None and xpu.is_available()
    except Exception:
        return False


def pick_device(device: str = "auto") -> str:
    """Etichetta device: 'cuda' | 'xpu' | 'mps' | 'dml' | 'cpu'.

    Ordine CUDA-first: su una macchina NVIDIA il motore gira sui tensor core,
    DirectML resta il fallback per le GPU AMD/Intel su Windows.
    Accetta anche 'cuda:1' per scegliere una scheda specifica.
    """
    if device != "auto":
        return device
    if torch.cuda.is_available():          # NVIDIA CUDA e AMD ROCm
        return "cuda"
    if _xpu_available():                   # Intel Arc / Data Center GPU
        return "xpu"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    if _directml_available():              # AMD/Intel su Windows via DirectX 12
        return "dml"
    return "cpu"


def torch_device(label: str):
    """Mappa l'etichetta in un torch.device. 'dml' richiede torch-directml."""
    if label.startswith("dml"):
        import torch_directml
        _, _, idx = label.partition(":")
        return torch_directml.device(int(idx)) if idx else torch_directml.device()
    return torch.device(label)


def is_cuda(label: str) -> bool:
    return str(label).startswith("cuda")


def setup_device(label: str = "auto", deterministic: bool = False) -> tuple:
    """Sceglie il device, applica le ottimizzazioni CUDA e ritorna (label, device).

    Su CUDA abilita TF32 (matmul ~3x sui tensor core Ampere+ senza perdita
    pratica di precisione per questo carico) e cudnn.benchmark.
    """
    label = pick_device(label)
    dev = torch_device(label)
    if is_cuda(label):
        try:
            major = torch.cuda.get_device_capability(dev if isinstance(dev, torch.device) else 0)[0]
            if major >= 8:                                  # Ampere e successive
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                torch.set_float32_matmul_precision("high")
            torch.backends.cudnn.benchmark = not deterministic
            torch.backends.cudnn.deterministic = deterministic
        except Exception:
            pass
    return label, dev


def device_summary(label: str) -> str:
    """Riga descrittiva del device per i log del Training Lab."""
    if is_cuda(label):
        try:
            idx = int(label.partition(":")[2] or 0)
            props = torch.cuda.get_device_properties(idx)
            vram = props.total_memory / (1024 ** 3)
            return (f"{props.name} | sm_{props.major}{props.minor} | {vram:.1f} GB | "
                    f"torch {torch.__version__} cuda {torch.version.cuda}")
        except Exception:
            return f"cuda | torch {torch.__version__}"
    return f"{label} | torch {torch.__version__}"


@dataclass
class BlockConfig:
    """Come spezzettiamo ogni matrice 2D in blocchi quadrati."""
    block_size: int = 64          # BS x BS per blocco
    min_tensor_numel: int = 4096  # ignora tensori troppo piccoli (es. norm 1D già esclusi)


@dataclass
class GeneratorConfig:
    kind: str = "ailo"            # "ailo" | "mlp" (baseline coordinate-INR)
    backbone: str = AILO_BACKBONE
    latent_dim: int = 48
    seq_len: int = 4             # quanti "token" virtuali diamo in pasto al backbone
    head_hidden: int = 0          # 0 = testa lineare; >0 = MLP a 2 layer
    freeze_backbone: bool = False  # se True allena solo latent + proiezioni + testa
    # solo per kind="mlp" baseline:
    mlp_hidden: int = 512


@dataclass
class TrainConfig:
    steps: int = 2000
    batch_blocks: int = 256
    lr: float = 1e-3
    weight_decay: float = 0.0
    eval_every: int = 200
    seed: int = 0
    # filtri per limitare l'ambito (smoke test):
    max_layers: int = -1          # -1 = tutti i layer
    include: str = ""            # substring da includere nei nomi tensore ("" = tutti)
    # obiettivo: "weight" = copia i pesi (MSE) | "task" = mantieni la perplexity (LM loss)
    objective: str = "weight"
    text_len: int = 64            # lunghezza sequenze testo per objective=task
    dataset: str = ""            # "" = corpus interno; "wikitext" = HF wikitext-2 (se installato)


@dataclass
class GradusConfig:
    model: str = "Qwen/Qwen2.5-0.5B"
    device: str = "auto"
    dtype: str = "float32"
    block: BlockConfig = field(default_factory=BlockConfig)
    generator: GeneratorConfig = field(default_factory=GeneratorConfig)
    train: TrainConfig = field(default_factory=TrainConfig)

    def torch_dtype(self):
        return {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }.get(self.dtype, torch.float32)

    def to_json(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def from_json(path: Path) -> "GradusConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = GradusConfig(
            model=raw["model"], device=raw["device"], dtype=raw["dtype"],
            block=BlockConfig(**raw["block"]),
            generator=GeneratorConfig(**raw["generator"]),
            train=TrainConfig(**raw["train"]),
        )
        return cfg
