"""Stato reale dei modelli, in cinque livelli distinti.

Confondere "il file c'è" con "il backend può usarlo" produce interfacce che si
contraddicono: la cartella mostra `sd_xl_base_1.0.safetensors` mentre il pannello
dice «Checkpoint: 0», semplicemente perché ComfyUI non è in esecuzione.

Qui i livelli sono separati e ognuno ha una fonte di verità diversa:

    DISCOVERED   catalogo remoto (Hugging Face / Civitai) — non scaricato
        ↓
    INSTALLED    filesystem — il file esiste nella cartella del backend
        ↓
    AVAILABLE    runtime del backend — lo espone e sa caricarlo
        ↓
    LOADED       pesi in VRAM — il backend l'ha caricato per un job
        ↓
    ACTIVE       sta eseguendo un job in questo momento

Uno stato più alto implica quelli sotto; `state_reason` dice sempre perché ci si
è fermati a quel livello.
"""

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from core.logger import get_logger

log = get_logger("creative_model_state")


class ModelState(str, Enum):
    DISCOVERED = "discovered"
    INSTALLED = "installed"
    AVAILABLE = "available"
    LOADED = "loaded"
    ACTIVE = "active"


STATE_ORDER = (ModelState.DISCOVERED, ModelState.INSTALLED, ModelState.AVAILABLE,
               ModelState.LOADED, ModelState.ACTIVE)

# Capability implicite nella categoria; il registro modelli le raffina quando
# riconosce il file specifico.
CATEGORY_CAPABILITIES = {
    "checkpoint": ("text_to_image", "img_to_img", "inpaint"),
    "diffusion": ("text_to_image",),
    "lora": ("style_adapter",),
    "vae": ("decode",),
    "controlnet": ("structure_guidance",),
    "upscaler": ("upscale",),
    "embedding": ("prompt_concept",),
    "text_encoder": ("text_encoding",),
    "clip_vision": ("image_encoding",),
}

# Le liste che il runtime del backend restituisce, per categoria.
CATEGORY_RUNTIME_KEY = {
    "checkpoint": "checkpoints",
    "diffusion": "unets",
    "lora": "loras",
    "vae": "vaes",
    "controlnet": "controlnets",
    "upscaler": "upscale_models",
    "text_encoder": "clips",
}


@dataclass
class ModelRecord:
    name: str
    type: str                       # categoria (checkpoint, lora, vae, ...)
    path: str = ""
    size_gb: float = 0.0
    backend: str = "comfyui"
    installed: bool = False
    available: bool = False
    loaded: bool = False
    active: bool = False
    estimated_vram_gb: float = 0.0
    capabilities: list = field(default_factory=list)
    state: str = ModelState.DISCOVERED.value
    state_reason: str = ""
    registry_id: str = ""           # voce di model_registry, se riconosciuto

    def compute_state(self) -> None:
        """Deriva lo stato dai flag: un solo punto in cui la gerarchia è scritta."""
        if self.active:
            self.state = ModelState.ACTIVE.value
        elif self.loaded:
            self.state = ModelState.LOADED.value
        elif self.available:
            self.state = ModelState.AVAILABLE.value
        elif self.installed:
            self.state = ModelState.INSTALLED.value
        else:
            self.state = ModelState.DISCOVERED.value

    def to_dict(self):
        return asdict(self)


def estimate_vram_gb(size_gb: float, category: str) -> float:
    """VRAM indicativa per tenere in memoria questi pesi.

    Regola grossolana ma onesta: i pesi occupano quanto il file, più spazio per
    attivazioni e latenti. Gli upscaler lavorano a tile e costano molto meno.
    """
    if size_gb <= 0:
        return 0.0
    if category in ("upscaler", "vae", "embedding", "clip_vision"):
        return round(max(1.0, size_gb * 1.2), 1)
    if category == "lora":
        return round(max(0.2, size_gb), 1)
    return round(size_gb * 1.25 + 1.5, 1)


class RuntimeTracker:
    """Traccia cosa il backend ha caricato e cosa sta eseguendo.

    ComfyUI non espone quali pesi siano residenti in VRAM. Sigma però *sa* cosa
    ha chiesto: registrando i file usati a ogni submit si ottiene un'inferenza
    corretta e dichiarata come tale, invece di un dato inventato.
    """

    TTL = 900.0     # dopo un quarto d'ora senza usi non si può più dare per caricato

    def __init__(self):
        self._loaded: dict[tuple, float] = {}    # (backend, filename) -> timestamp
        self._active: set[tuple] = set()

    def mark_submitted(self, backend: str, filenames) -> None:
        now = time.monotonic()
        for name in filter(None, filenames):
            self._loaded[(backend, name)] = now
            self._active.add((backend, name))

    def mark_finished(self, backend: str, filenames) -> None:
        for name in filter(None, filenames):
            self._active.discard((backend, name))

    def clear_backend(self, backend: str) -> None:
        """Il backend è caduto: nulla di suo può essere considerato caricato."""
        self._loaded = {k: v for k, v in self._loaded.items() if k[0] != backend}
        self._active = {k for k in self._active if k[0] != backend}

    def is_loaded(self, backend: str, filename: str) -> bool:
        ts = self._loaded.get((backend, filename))
        return bool(ts) and (time.monotonic() - ts) < self.TTL

    def is_active(self, backend: str, filename: str) -> bool:
        return (backend, filename) in self._active


runtime_tracker = RuntimeTracker()


def build_inventory(filesystem: dict, runtime: dict | None, backend: str = "comfyui",
                    runtime_reachable: bool = False, tracker: RuntimeTracker = None) -> dict:
    """Unisce filesystem, runtime del backend e tracker in un unico inventario.

    `filesystem` è l'uscita di `installed_by_category`, `runtime` quella di
    `discover()` del backend. Quando il backend non risponde i file restano
    INSTALLED: è la distinzione che mancava.
    """
    tracker = tracker or runtime_tracker
    from core.creative.model_registry import MODELS

    # filename dichiarato dal registro -> voce del registro
    by_filename = {}
    for model in MODELS:
        for spec_name in (model.id,):
            by_filename.setdefault(spec_name, model)

    categories = {}
    totals = {state.value: 0 for state in STATE_ORDER}

    for category_id, data in (filesystem or {}).items():
        runtime_names = set()
        if runtime_reachable and runtime:
            runtime_names = set(runtime.get(CATEGORY_RUNTIME_KEY.get(category_id, ""), []) or [])

        records = []
        for file_info in data.get("files", []):
            name = file_info["filename"]
            record = ModelRecord(
                name=Path(name).stem,
                type=category_id,
                path=file_info.get("path", ""),
                size_gb=file_info.get("size_gb", 0.0),
                backend=backend,
                installed=True,
                available=name in runtime_names,
                loaded=tracker.is_loaded(backend, name),
                active=tracker.is_active(backend, name),
                estimated_vram_gb=estimate_vram_gb(file_info.get("size_gb", 0.0), category_id),
                capabilities=list(CATEGORY_CAPABILITIES.get(category_id, ())),
            )
            # L'ordine segue la gerarchia degli stati: la motivazione deve
            # spiegare il livello raggiunto, non uno inferiore.
            if record.active:
                record.state_reason = "In uso da un job in corso."
            elif record.loaded:
                record.state_reason = "Usato di recente: verosimilmente ancora in VRAM."
            elif record.available:
                record.state_reason = "Pronto: il backend può caricarlo su richiesta."
            elif not runtime_reachable:
                record.state_reason = ("Backend non in esecuzione: il file è installato "
                                       "ma nessun runtime lo espone.")
            else:
                record.state_reason = ("Presente su disco ma non indicizzato dal backend: "
                                       "riavvia il backend per rilevarlo.")

            record.compute_state()
            totals[record.state] += 1
            records.append(record.to_dict())

        # File esposti dal runtime ma non trovati su disco: cartelle extra o link.
        for orphan in sorted(runtime_names - {f["filename"] for f in data.get("files", [])}):
            record = ModelRecord(
                name=Path(orphan).stem, type=category_id, backend=backend,
                installed=False, available=True,
                capabilities=list(CATEGORY_CAPABILITIES.get(category_id, ())),
                state_reason="Esposto dal backend da un percorso fuori dalla cartella nota.",
            )
            record.compute_state()
            totals[record.state] += 1
            records.append(record.to_dict())

        categories[category_id] = {
            "label": data.get("label", category_id),
            "folder": data.get("folder", ""),
            "description": data.get("description", ""),
            "models": records,
            "counts": {
                "installed": sum(1 for r in records if r["installed"]),
                "available": sum(1 for r in records if r["available"]),
                "loaded": sum(1 for r in records if r["loaded"]),
            },
        }

    return {
        "backend": backend,
        "runtime_reachable": runtime_reachable,
        "states": [s.value for s in STATE_ORDER],
        "totals": totals,
        "categories": categories,
    }
