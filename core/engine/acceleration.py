"""Contratto di accelerazione indipendente dalla famiglia e dal formato dei pesi."""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Optional


@dataclass(frozen=True)
class RuntimeCapabilities:
    runtime: str
    execution_owner: str = "backend"
    parallel_slots: int = 1
    prefix_reuse: bool = False
    kv_checkpoint: bool = False
    exact_tokenizer: bool = False
    cancellation: bool = False
    logits_owner: str = "runtime"
    logits_processors: bool = False
    speculative_decoding: bool = False
    tensor_offload: bool = False
    evidence: str = "backend_contract"

    def __post_init__(self):
        if type(self.parallel_slots) is not int or not 1 <= self.parallel_slots <= 64:
            raise ValueError("Concorrenza del runtime fuori intervallo 1..64")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class CacheIdentity:
    """Revisioni esplicite: il solo nome della famiglia non identifica una cache KV."""
    checkpoint: str
    tokenizer: str
    template: str
    runtime: str
    adapters: str = "none"
    kv_layout: str = "runtime_default"
    positions: str = "checkpoint_default"
    modality: str = "text"
    scope: str = "local"

    def digest(self) -> str:
        if any(not isinstance(value, str) or not value for value in asdict(self).values()):
            raise ValueError("Identità cache incompleta")
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def acceleration_plan(capabilities: RuntimeCapabilities, *, model=None,
                      requested_parallelism: Optional[int] = None) -> dict:
    """Descrive strategie attuabili; non trasforma supporto dichiarato in guadagni misurati."""
    slots = capabilities.parallel_slots
    if requested_parallelism is not None:
        if type(requested_parallelism) is not int or requested_parallelism < 1:
            raise ValueError("Parallelismo richiesto non valido")
        slots = min(slots, requested_parallelism)
    features = {}
    for name, enabled, owner in (
        ("prefix_reuse", capabilities.prefix_reuse, capabilities.execution_owner),
        ("kv_checkpoint", capabilities.kv_checkpoint, capabilities.execution_owner),
        ("exact_tokenizer", capabilities.exact_tokenizer, capabilities.execution_owner),
        ("cancellation", capabilities.cancellation, capabilities.execution_owner),
        ("logits_processing", capabilities.logits_processors, capabilities.logits_owner),
        ("speculative_decoding", capabilities.speculative_decoding, capabilities.execution_owner),
        ("tensor_offload", capabilities.tensor_offload, capabilities.execution_owner),
    ):
        features[name] = {"supported": enabled, "owner": owner,
                          "state": "available" if enabled else "not_declared"}
    return {
        "schema": 1,
        "runtime": capabilities.to_dict(),
        "model": {"architecture": getattr(model, "model_type", "unknown"),
                  "weight_format": getattr(model, "weight_format", "unknown"),
                  "moe": bool(getattr(model, "is_moe", False)),
                  "multimodal": bool(getattr(model, "is_multimodal", False))},
        "effective_parallelism": slots,
        "batch_strategy": "runtime_slots" if slots > 1 else "serial",
        "features": features,
        "quality_policy": "preserve_sampling_and_precision",
        "measurement_required": True,
    }
