"""Download dei modelli dentro Sigma Studio.

Sigma sa già *quali* modelli servono (model_registry) e *cosa manca* su questa
macchina (discovery ComfyUI). Questo modulo chiude il cerchio: scarica i pesi
nella cartella giusta di ComfyUI, così che dopo il download il registro li veda
e il router possa sceglierli — senza uscire dall'applicazione.

Le destinazioni non sono indovinate: si leggono dalla configurazione che ComfyUI
stesso dichiara nei propri argomenti di avvio.
"""

import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

import requests

from core.logger import get_logger

log = get_logger("creative_downloader")

CHUNK = 1024 * 512
USER_AGENT = "SigmaStudio/8.0 (+model-downloader)"


# ---------------------------------------------------------------------------
# Catalogo scaricabile
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DownloadableAsset:
    id: str
    label: str
    folder: str                 # sottocartella models/ di ComfyUI
    filename: str
    url: str
    size_gb: float = 0.0
    model_id: str = ""          # voce corrispondente in model_registry
    kind: str = "checkpoint"    # checkpoint | diffusion | text_encoder | vae | upscaler | lora
    requires_token: bool = False
    license: str = ""
    notes: str = ""
    requires: tuple = ()        # altri asset necessari perché il modello funzioni

    def to_dict(self):
        return {**asdict(self), "requires": list(self.requires)}


HF = "https://huggingface.co"

CATALOG: tuple[DownloadableAsset, ...] = (
    # ------------------------------------------------------------- SDXL
    DownloadableAsset(
        id="sdxl-base", label="SDXL 1.0 base", model_id="sdxl",
        folder="checkpoints", filename="sd_xl_base_1.0.safetensors",
        url=f"{HF}/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        size_gb=6.9, kind="checkpoint", license="CreativeML Open RAIL++-M",
        notes="Il punto di partenza: ecosistema enorme di LoRA, ControlNet e workflow.",
    ),
    DownloadableAsset(
        id="sdxl-vae", label="SDXL VAE (fp16 fix)", model_id="sdxl",
        folder="vae", filename="sdxl_vae.safetensors",
        url=f"{HF}/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors",
        size_gb=0.33, kind="vae", license="MIT",
        notes="Evita artefatti e colori slavati in fp16.",
    ),

    # ------------------------------------------------------------- FLUX
    DownloadableAsset(
        id="flux-schnell", label="FLUX.1 schnell (fp8)", model_id="flux.1-schnell",
        folder="diffusion_models", filename="flux1-schnell-fp8.safetensors",
        url=f"{HF}/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors",
        size_gb=17.2, kind="diffusion", license="Apache 2.0",
        notes="Licenza permissiva, 4-8 step. Il FLUX da cui partire.",
        requires=("flux-clip-l", "flux-t5", "flux-vae"),
    ),
    DownloadableAsset(
        id="flux-dev", label="FLUX.1 dev (fp8)", model_id="flux.1-dev",
        folder="diffusion_models", filename="flux1-dev-fp8.safetensors",
        url=f"{HF}/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors",
        size_gb=17.2, kind="diffusion", requires_token=True,
        license="FLUX.1-dev Non-Commercial",
        notes="Qualità superiore a schnell. Repo gated: serve un token Hugging Face "
              "e l'accettazione della licenza sul sito.",
        requires=("flux-clip-l", "flux-t5", "flux-vae"),
    ),
    DownloadableAsset(
        id="flux-clip-l", label="CLIP-L (text encoder FLUX)", model_id="flux.1-schnell",
        folder="text_encoders", filename="clip_l.safetensors",
        url=f"{HF}/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        size_gb=0.25, kind="text_encoder", license="MIT",
    ),
    DownloadableAsset(
        id="flux-t5", label="T5-XXL fp8 (text encoder FLUX)", model_id="flux.1-schnell",
        folder="text_encoders", filename="t5xxl_fp8_e4m3fn.safetensors",
        url=f"{HF}/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
        size_gb=4.9, kind="text_encoder", license="Apache 2.0",
    ),
    DownloadableAsset(
        id="flux-vae", label="VAE FLUX (ae.safetensors)", model_id="flux.1-schnell",
        folder="vae", filename="ae.safetensors",
        url=f"{HF}/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors",
        size_gb=0.33, kind="vae", license="Apache 2.0",
    ),

    # -------------------------------------------------------- upscaling
    DownloadableAsset(
        id="realesrgan-x4", label="Real-ESRGAN x4 plus", model_id="real-esrgan",
        folder="upscale_models", filename="RealESRGAN_x4plus.pth",
        url=f"{HF}/lllyasviel/Annotators/resolve/main/RealESRGAN_x4plus.pth",
        size_gb=0.07, kind="upscaler", license="BSD-3",
        notes="Upscale affidabile che non inventa dettagli: il default sensato.",
    ),
    DownloadableAsset(
        id="ultrasharp", label="4x UltraSharp", model_id="swinir",
        folder="upscale_models", filename="4x-UltraSharp.pth",
        url=f"{HF}/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth",
        size_gb=0.07, kind="upscaler", license="Open",
        notes="Più nitido di Real-ESRGAN su texture e dettaglio fine.",
    ),

    # ---------------------------------------------------------- scontorno
    DownloadableAsset(
        id="rmbg-14", label="RMBG-1.4 (rimozione sfondo)", model_id="rembg",
        folder="background_removal", filename="RMBG-1.4.pth",
        url=f"{HF}/briaai/RMBG-1.4/resolve/main/model.pth",
        size_gb=0.18, kind="checkpoint", license="Non-commercial",
        notes="Scontorno di qualità superiore al flood fill locale.",
    ),
)

CATALOG_BY_ID = {a.id: a for a in CATALOG}


# ---------------------------------------------------------------------------
# Destinazioni
# ---------------------------------------------------------------------------

def _parse_extra_model_paths(yaml_path: str) -> str:
    """base_path dichiarato nel file extra_model_paths di ComfyUI."""
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for entry in doc.values():
            if isinstance(entry, dict) and entry.get("base_path"):
                return str(entry["base_path"])
    except Exception as e:
        log.debug(f"extra_model_paths non leggibile ({yaml_path}): {e}")
    return ""


def discover_models_root(comfy_url: str = "", configured: str = "") -> str:
    """Cartella `models/` di ComfyUI, chiedendola a ComfyUI stesso.

    Ordine: valore in config → argomenti di avvio dell'istanza in esecuzione →
    percorsi tipici delle installazioni desktop/portable.
    """
    if configured and Path(configured).is_dir():
        return str(Path(configured))

    if comfy_url:
        try:
            stats = requests.get(f"{comfy_url.rstrip('/')}/system_stats", timeout=4).json()
            argv = stats.get("system", {}).get("argv", []) or []
            if "--extra-model-paths-config" in argv:
                yaml_path = argv[argv.index("--extra-model-paths-config") + 1]
                base = _parse_extra_model_paths(yaml_path)
                if base and Path(base).is_dir():
                    return base
            # Fallback: le cartelle input/output stanno accanto a models/
            for flag in ("--output-directory", "--input-directory"):
                if flag in argv:
                    sibling = Path(argv[argv.index(flag) + 1]).parent / "models"
                    if sibling.is_dir():
                        return str(sibling)
        except Exception as e:
            log.debug(f"system_stats non interrogabile: {e}")

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Comfy-Desktop" / "ComfyUI-Shared" / "models",
        Path.home() / "Documents" / "ComfyUI" / "models",
        Path("C:/ComfyUI/models"),
        Path.home() / "ComfyUI" / "models",
    ]
    for c in candidates:
        if c.is_dir():
            return str(c)
    return ""


def target_path(root: str, asset: DownloadableAsset) -> Path:
    return Path(root) / asset.folder / asset.filename


def installed_by_category(root: str) -> dict:
    """File di pesi presenti, raggruppati per cartella di ComfyUI."""
    from core.creative.model_hub import CATEGORIES

    out = {}
    for category in CATEGORIES:
        folder = Path(root) / category.folder if root else None
        files = []
        if folder and folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if path.is_file() and path.suffix.lower() in (
                        ".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"):
                    files.append({
                        "filename": path.name,
                        "size_gb": round(path.stat().st_size / 1024 ** 3, 2),
                        "path": str(path),
                    })
        out[category.id] = {
            "label": category.label,
            "folder": category.folder,
            "description": category.description,
            "files": files,
        }
    return out


def custom_asset(spec: dict) -> DownloadableAsset:
    """Costruisce una voce scaricabile da un risultato di ricerca.

    Cartella e nome file sono validati: arrivano da una API esterna e finirebbero
    altrimenti in un percorso arbitrario del disco.
    """
    from core.creative.model_hub import ALLOWED_FOLDERS

    folder = str(spec.get("folder", "")).strip().strip("/\\")
    if folder not in ALLOWED_FOLDERS:
        raise ValueError(f"Cartella '{folder}' non ammessa per i modelli")

    filename = Path(str(spec.get("filename", ""))).name   # elimina qualsiasi percorso
    if not filename or filename.startswith("."):
        raise ValueError("Nome file non valido")

    url = str(spec.get("url", ""))
    if not url.startswith(("https://huggingface.co/", "https://civitai.com/")):
        raise ValueError("Sono ammessi solo download da Hugging Face o Civitai")

    return DownloadableAsset(
        id=f"{spec.get('source', 'custom')}:{spec.get('model_id', '')}:{filename}",
        label=spec.get("label") or filename,
        folder=folder, filename=filename, url=url,
        size_gb=float(spec.get("size_gb") or 0),
        kind=spec.get("kind", "checkpoint"),
        license=spec.get("license", ""),
        notes=spec.get("notes", ""),
    )


def installed_state(root: str) -> dict:
    """Per ogni voce del catalogo: presente su disco e con che dimensione."""
    state = {}
    for asset in CATALOG:
        path = target_path(root, asset) if root else None
        exists = bool(path and path.exists())
        state[asset.id] = {
            "installed": exists,
            "path": str(path) if path else "",
            "size_bytes": path.stat().st_size if exists else 0,
        }
    return state


# ---------------------------------------------------------------------------
# Job di download
# ---------------------------------------------------------------------------

@dataclass
class DownloadJob:
    job_id: str
    asset_id: str
    label: str
    target: str
    status: str = "queued"       # queued | downloading | done | error | cancelled
    downloaded: int = 0
    total: int = 0
    speed_bps: float = 0.0
    error: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    @property
    def progress(self) -> float:
        return round(self.downloaded / self.total * 100, 1) if self.total else 0.0

    def to_dict(self):
        data = asdict(self)
        data["progress"] = self.progress
        data["eta_s"] = int((self.total - self.downloaded) / self.speed_bps) if self.speed_bps > 0 and self.total else None
        return data


class DownloadManager:
    """Scarica su thread separati, con cancellazione e ripresa parziale."""

    def __init__(self):
        self.jobs: dict[str, DownloadJob] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    # -- introspezione ---------------------------------------------------

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [j.to_dict() for j in sorted(self.jobs.values(), key=lambda j: -j.started_at)]

    def active_for(self, asset_id: str) -> DownloadJob | None:
        with self._lock:
            for job in self.jobs.values():
                if job.asset_id == asset_id and job.status in ("queued", "downloading"):
                    return job
        return None

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancel.get(job_id)
        if not event:
            return False
        event.set()
        return True

    # -- esecuzione ------------------------------------------------------

    def start(self, asset: DownloadableAsset, root: str, token: str = "") -> DownloadJob:
        existing = self.active_for(asset.id)
        if existing:
            return existing

        destination = target_path(root, asset)
        destination.parent.mkdir(parents=True, exist_ok=True)

        job = DownloadJob(job_id=str(uuid.uuid4())[:8], asset_id=asset.id,
                          label=asset.label, target=str(destination))
        cancel = threading.Event()
        with self._lock:
            self.jobs[job.job_id] = job
            self._cancel[job.job_id] = cancel

        thread = threading.Thread(target=self._run, args=(job, asset, destination, token, cancel), daemon=True)
        thread.start()
        return job

    def _run(self, job: DownloadJob, asset: DownloadableAsset, destination: Path,
             token: str, cancel: threading.Event):
        part = destination.with_suffix(destination.suffix + ".part")
        headers = {"User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Ripresa: se esiste un .part si riparte da dove si era arrivati.
        resume_from = part.stat().st_size if part.exists() else 0
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"

        job.status = "downloading"
        job.downloaded = resume_from
        log.info(f"Download {asset.id} → {destination}" + (f" (ripresa da {resume_from} byte)" if resume_from else ""))

        try:
            with requests.get(asset.url, headers=headers, stream=True, timeout=60, allow_redirects=True) as resp:
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        "Accesso negato: il repository è gated. Accetta la licenza su Hugging Face "
                        "e imposta un token in Impostazioni → Creative (hf_token)."
                    )
                if resp.status_code == 416:      # già completo
                    resume_from = 0
                    part.replace(destination)
                    job.status, job.finished_at = "done", time.time()
                    return
                resp.raise_for_status()

                total = int(resp.headers.get("Content-Length", 0))
                job.total = total + resume_from if resume_from and resp.status_code == 206 else total

                mode = "ab" if resume_from and resp.status_code == 206 else "wb"
                if mode == "wb":
                    job.downloaded = 0

                last_t, last_b = time.time(), job.downloaded
                with open(part, mode) as f:
                    for chunk in resp.iter_content(CHUNK):
                        if cancel.is_set():
                            job.status = "cancelled"
                            log.info(f"Download {asset.id} annullato")
                            return
                        if not chunk:
                            continue
                        f.write(chunk)
                        job.downloaded += len(chunk)

                        now = time.time()
                        if now - last_t >= 1.0:
                            job.speed_bps = (job.downloaded - last_b) / (now - last_t)
                            last_t, last_b = now, job.downloaded

            if job.total and job.downloaded < job.total:
                raise RuntimeError(f"Download incompleto: {job.downloaded}/{job.total} byte")

            part.replace(destination)
            job.status, job.finished_at = "done", time.time()
            log.info(f"Download {asset.id} completato ({job.downloaded} byte)")

        except Exception as e:
            job.status, job.error, job.finished_at = "error", str(e), time.time()
            log.error(f"Download {asset.id} fallito: {e}")
        finally:
            with self._lock:
                self._cancel.pop(job.job_id, None)

    def cleanup_partial(self, asset: DownloadableAsset, root: str) -> bool:
        """Rimuove il file parziale di un download annullato."""
        part = target_path(root, asset).with_suffix(target_path(root, asset).suffix + ".part")
        if part.exists():
            part.unlink()
            return True
        return False


download_manager = DownloadManager()


def disk_free_gb(root: str) -> float:
    try:
        return round(shutil.disk_usage(root).free / 1024 ** 3, 1)
    except Exception:
        return 0.0
