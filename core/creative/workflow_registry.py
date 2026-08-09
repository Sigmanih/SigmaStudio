"""Registro dei workflow: dati su disco, non codice.

Sigma non deve sapere *com'è costruito* un workflow. Deve sapere che genera
immagini e che richiede SDXL. Il resto è un grafo opaco che passa al backend.

Ogni workflow è un file in `data/creative/workflows/` con un manifest:

    {
      "id": "sdxl_txt2img",
      "name": "SDXL Text to Image",
      "backend": "comfyui",
      "capability": "text_to_image",
      "inputs": {"prompt": "{{prompt}}", "width": "{{width}}", ...},
      "requirements": {"checkpoint": "sdxl", "vram_gb": 8},
      "workflow": { ...grafo API del backend... }
    }

Il grafo può stare inline (`workflow`) o in un file affiancato (`workflow_file`),
così un export "Save (API format)" resta intatto e il manifest lo accompagna.
"""

import json
import random
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from core.logger import get_logger

log = get_logger("workflow_registry")

WORKFLOW_DIR = Path("data/creative/workflows")
MANIFEST_SUFFIX = ".manifest.json"

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@dataclass
class WorkflowManifest:
    id: str
    name: str
    capability: str
    backend: str = "comfyui"
    inputs: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    requirements: dict = field(default_factory=dict)
    description: str = ""
    source: str = "user"              # user | builtin
    path: str = ""
    workflow: dict = field(default_factory=dict, repr=False)

    @property
    def placeholders(self) -> set:
        """Nomi effettivamente usati nel grafo: la verità sui parametri attesi."""
        return set(PLACEHOLDER.findall(json.dumps(self.workflow))) if self.workflow else set()

    def to_dict(self, with_graph: bool = False) -> dict:
        data = asdict(self)
        data["placeholders"] = sorted(self.placeholders)
        data["node_count"] = len(self.workflow or {})
        if not with_graph:
            data.pop("workflow", None)
        return data


class WorkflowRegistry:
    """Carica, valida e risolve i workflow disponibili."""

    def __init__(self, directory: Path = None):
        self.directory = Path(directory or WORKFLOW_DIR)
        self._cache: dict[str, WorkflowManifest] = {}
        self._mtime = 0.0

    # ------------------------------------------------------------------
    # Caricamento
    # ------------------------------------------------------------------

    def _dir_mtime(self) -> float:
        if not self.directory.is_dir():
            return 0.0
        return max((p.stat().st_mtime for p in self.directory.glob("*.json")), default=0.0)

    def load(self, force: bool = False) -> dict[str, WorkflowManifest]:
        """Rilegge la cartella se qualcosa è cambiato."""
        mtime = self._dir_mtime()
        if not force and self._cache and mtime == self._mtime:
            return self._cache

        found: dict[str, WorkflowManifest] = {}
        for entry in builtin_manifests():
            found[entry.id] = entry

        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.json")):
                if path.name.endswith(MANIFEST_SUFFIX):
                    continue          # letto insieme al grafo che descrive
                try:
                    manifest = self._load_file(path)
                except Exception as e:
                    log.warning(f"Workflow '{path.name}' ignorato: {e}")
                    continue
                if manifest:
                    found[manifest.id] = manifest   # l'utente sovrascrive il built-in

        self._cache, self._mtime = found, mtime
        return found

    def _load_file(self, path: Path) -> WorkflowManifest | None:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("il file non contiene un oggetto JSON")

        sidecar = path.with_suffix("").with_suffix(MANIFEST_SUFFIX) \
            if path.suffix == ".json" else None
        sidecar = self.directory / f"{path.stem}{MANIFEST_SUFFIX}"

        # Forma 1: manifest Sigma (inline o con workflow_file)
        if "capability" in doc:
            graph = doc.get("workflow")
            if not graph and doc.get("workflow_file"):
                graph_path = self.directory / doc["workflow_file"]
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
            return WorkflowManifest(
                id=doc.get("id") or path.stem,
                name=doc.get("name") or path.stem,
                capability=doc["capability"],
                backend=doc.get("backend", "comfyui"),
                inputs=doc.get("inputs") or {},
                defaults=doc.get("defaults") or {},
                requirements=doc.get("requirements") or {},
                description=doc.get("description", ""),
                source="user", path=str(path), workflow=graph or {},
            )

        # Forma 2: export grezzo del backend, con manifest affiancato se presente
        meta = {}
        if sidecar.exists():
            meta = json.loads(sidecar.read_text(encoding="utf-8"))

        return WorkflowManifest(
            id=meta.get("id") or path.stem,
            name=meta.get("name") or path.stem.replace("_", " ").title(),
            capability=meta.get("capability") or _guess_capability(path.stem),
            backend=meta.get("backend", "comfyui"),
            inputs=meta.get("inputs") or {},
            defaults=meta.get("defaults") or {},
            requirements=meta.get("requirements") or {},
            description=meta.get("description", ""),
            source="user", path=str(path), workflow=doc,
        )

    # ------------------------------------------------------------------
    # Interrogazione
    # ------------------------------------------------------------------

    def get(self, workflow_id: str) -> WorkflowManifest | None:
        return self.load().get(workflow_id)

    def for_capability(self, capability: str, backend: str = None) -> list[WorkflowManifest]:
        return [w for w in self.load().values()
                if w.capability == capability and (not backend or w.backend == backend)]

    def status(self, installed: dict = None, checkpoints: dict = None, vram_gb: float = 0.0) -> list[dict]:
        """Elenco con lo stato di prontezza rispetto a ciò che è installato.

        `installed` è l'inventario per categoria; `checkpoints` la mappa
        famiglia → file attesa dalla configurazione del backend.
        """
        out = []
        for workflow in sorted(self.load().values(), key=lambda w: (w.capability, w.id)):
            missing, notes = [], []
            req = workflow.requirements or {}

            wanted_family = req.get("checkpoint")
            if wanted_family:
                filename = (checkpoints or {}).get(wanted_family, "")
                present = _has_file(installed, filename) if filename else False
                if not present:
                    missing.append(f"checkpoint {wanted_family}"
                                   + (f" ({filename})" if filename else ""))

            for extra_key, category in (("upscale_model", "upscaler"), ("vae", "vae"),
                                        ("lora", "lora"), ("controlnet", "controlnet")):
                wanted = req.get(extra_key)
                if wanted and not _has_file(installed, wanted, category):
                    missing.append(f"{extra_key} {wanted}")

            needed_vram = float(req.get("vram_gb") or 0)
            if needed_vram and vram_gb and needed_vram > vram_gb:
                notes.append(f"richiede {needed_vram} GB di VRAM, ne risultano {vram_gb}")

            entry = workflow.to_dict()
            entry.update({"ready": not missing, "missing": missing, "notes": notes})
            out.append(entry)
        return out

    def resolve(self, workflow_id: str, params: dict) -> dict:
        """Grafo pronto per il backend, con i placeholder sostituiti.

        I default del workflow vengono applicati qui: con il grafo ridotto a dati
        non esiste più un builder che possa fornirli, e un `None` finirebbe dritto
        al backend come valore non valido.
        """
        workflow = self.get(workflow_id)
        if not workflow:
            raise KeyError(f"Workflow '{workflow_id}' non presente nel registro")
        if not workflow.workflow:
            raise ValueError(f"Workflow '{workflow_id}' non contiene un grafo eseguibile")

        values = finalize_params(workflow.defaults, params)
        missing = [p for p in workflow.placeholders if values.get(p) is None]
        if missing:
            raise ValueError(
                f"Workflow '{workflow_id}': parametri mancanti {', '.join(sorted(missing))}"
            )
        return substitute(workflow.workflow, values)

    # ------------------------------------------------------------------

    def save(self, manifest: dict, graph: dict) -> WorkflowManifest:
        """Registra un workflow fornito dall'utente."""
        workflow_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(manifest.get("id") or "")).strip("_")
        if not workflow_id:
            raise ValueError("Serve un id per il workflow")
        if not manifest.get("capability"):
            raise ValueError("Serve una capability (es. text_to_image)")
        if not isinstance(graph, dict) or not graph:
            raise ValueError("Il grafo del workflow è vuoto o non valido")

        self.directory.mkdir(parents=True, exist_ok=True)
        document = {
            "id": workflow_id,
            "name": manifest.get("name") or workflow_id,
            "backend": manifest.get("backend", "comfyui"),
            "capability": manifest["capability"],
            "description": manifest.get("description", ""),
            "inputs": manifest.get("inputs") or {},
            "defaults": manifest.get("defaults") or {},
            "requirements": manifest.get("requirements") or {},
            "workflow": graph,
        }
        path = self.directory / f"{workflow_id}.json"
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Workflow '{workflow_id}' salvato in {path}")

        self.load(force=True)
        return self.get(workflow_id)

    def delete(self, workflow_id: str) -> bool:
        workflow = self.get(workflow_id)
        if not workflow or workflow.source == "builtin" or not workflow.path:
            return False
        Path(workflow.path).unlink(missing_ok=True)
        (self.directory / f"{workflow_id}{MANIFEST_SUFFIX}").unlink(missing_ok=True)
        self.load(force=True)
        return True


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------

def substitute(graph: dict, params: dict) -> dict:
    """Sostituisce `{{chiave}}` nel grafo preservando i tipi JSON."""
    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            match = PLACEHOLDER.fullmatch(node.strip())
            if match:
                # Placeholder isolato: conserva il tipo del valore (int, float, bool).
                return params.get(match.group(1))
            return PLACEHOLDER.sub(lambda m: str(params.get(m.group(1), "")), node)
        return node
    return walk(graph)


def finalize_params(defaults: dict, params: dict) -> dict:
    """Unisce default e parametri, poi applica le regole del dominio.

    Due normalizzazioni non possono vivere nel grafo, che è dati puri: il seed
    casuale (`-1`) e i nomi di sampler in stile A1111, che ComfyUI rifiuta.
    """
    from core.creative.generators.adapters.comfy_workflows import SAMPLER_ALIASES

    values = dict(defaults or {})
    values.update({k: v for k, v in (params or {}).items() if v is not None})

    seed = values.get("seed", -1)
    if not isinstance(seed, str) and seed in (None, -1, ""):
        values["seed"] = random.randint(0, 2 ** 31 - 1)

    sampler = values.get("sampler")
    if sampler:
        values["sampler"] = SAMPLER_ALIASES.get(str(sampler).strip().lower(), sampler)

    return values


def _has_file(installed: dict, filename: str, category: str = None) -> bool:
    if not installed or not filename:
        return False
    for cat_id, data in installed.items():
        if category and cat_id != category:
            continue
        for f in data.get("files", []):
            if f.get("filename") == filename:
                return True
    return False


_CAPABILITY_HINTS = (
    ("txt2img", "text_to_image"), ("text_to_image", "text_to_image"),
    ("img2img", "img_to_img"), ("image_to_image", "img_to_img"),
    ("inpaint", "inpaint"), ("outpaint", "outpaint"),
    ("kontext", "instruct_edit"), ("edit", "instruct_edit"),
    ("upscale", "upscale"), ("segment", "segment"), ("sam", "segment"),
    ("image_to_3d", "image_to_3d"), ("3d", "image_to_3d"),
    ("image_to_video", "image_to_video"), ("text_to_video", "text_to_video"),
    ("video", "text_to_video"),
)


def _guess_capability(stem: str) -> str:
    """Capability dedotta dal nome file, per gli export senza manifest."""
    lowered = stem.lower()
    for hint, capability in _CAPABILITY_HINTS:
        if hint in lowered:
            return capability
    return "text_to_image"


def builtin_manifests() -> list[WorkflowManifest]:
    """Workflow forniti da Sigma, esposti come voci normali del registro."""
    from core.creative.generators.adapters import comfy_workflows as cw

    common = {
        "negative_prompt": "", "width": 1024, "height": 1024, "steps": 30,
        "cfg_scale": 7.0, "seed": -1, "sampler": "euler", "scheduler": "normal",
        "batch_size": 1, "strength": 0.7, "mask_blur": 6,
    }
    flux_defaults = {**common, "steps": 20, "cfg_scale": 3.5, "scheduler": "simple",
                     "weight_dtype": "fp8_e4m3fn", "clip_l": "clip_l.safetensors",
                     "clip_t5": "t5xxl_fp8_e4m3fn.safetensors", "vae": "ae.safetensors"}

    specs = [
        ("sdxl_txt2img", "SDXL Text to Image", "text_to_image",
         {"checkpoint": "sdxl", "vram_gb": 8},
         "Grafo checkpoint standard: KSampler + CLIP doppio prompt."),
        ("sdxl_img2img", "SDXL Image to Image", "img_to_img",
         {"checkpoint": "sdxl", "vram_gb": 8},
         "Come txt2img ma partendo da un latente codificato dall'immagine."),
        ("sdxl_inpaint", "SDXL Inpainting", "inpaint",
         {"checkpoint": "sdxl", "vram_gb": 8},
         "Rigenera solo l'area mascherata con VAEEncodeForInpaint."),
        ("sd3_txt2img", "SD 3.5 Text to Image", "text_to_image",
         {"checkpoint": "sd3", "vram_gb": 12}, "Stesso grafo checkpoint-based di SDXL."),
        ("flux_txt2img", "FLUX Text to Image", "text_to_image",
         {"checkpoint": "flux", "vram_gb": 12},
         "Doppio encoder CLIP-L + T5 con FluxGuidance."),
        ("qwen_txt2img", "Qwen-Image Text to Image", "text_to_image",
         {"checkpoint": "qwen", "vram_gb": 16}, "Topologia dual-encoder come FLUX."),
        ("esrgan_upscale", "Real-ESRGAN Upscale", "upscale",
         {"upscale_model": "RealESRGAN_x4plus.pth", "vram_gb": 2},
         "Upscale con modello dedicato, nessuna rigenerazione."),
    ]

    manifests = []
    for wf_id, name, capability, requirements, description in specs:
        builder = cw.BUILTIN.get(wf_id)
        if not builder:
            continue
        # Il grafo si costruisce con placeholder, così il manifest mostra
        # esattamente i parametri che il workflow consuma.
        sample = {k: f"{{{{{k}}}}}" for k in
                  ("prompt", "negative_prompt", "width", "height", "steps",
                   "cfg_scale", "seed", "sampler", "scheduler", "ckpt",
                   "input_image", "mask_image", "upscale_model", "strength")}
        try:
            graph = builder({**sample, "ckpt": "{{ckpt}}"})
        except Exception as e:
            log.debug(f"Built-in '{wf_id}' non serializzabile: {e}")
            continue

        used = sorted(set(PLACEHOLDER.findall(json.dumps(graph))))
        base = flux_defaults if wf_id in ("flux_txt2img", "qwen_txt2img") else common
        manifests.append(WorkflowManifest(
            id=wf_id, name=name, capability=capability, backend="comfyui",
            inputs={k: f"{{{{{k}}}}}" for k in used},
            defaults={k: v for k, v in base.items() if k in used},
            requirements=requirements, description=description,
            source="builtin", path="", workflow=graph,
        ))
    return manifests


registry = WorkflowRegistry()
