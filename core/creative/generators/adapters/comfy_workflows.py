"""Template di workflow ComfyUI in formato API.

Due livelli:

1. **Template built-in** — coprono i grafi standard (SDXL, FLUX, inpaint, upscale).
2. **Override utente** — qualsiasi file in `data/creative/workflows/<nome>.json`
   (workflow esportato da ComfyUI con "Save (API format)") sostituisce il
   built-in omonimo. I placeholder `{{prompt}}`, `{{width}}`, `{{ckpt}}`, ...
   vengono rimpiazzati prima dell'invio.

Il secondo livello è il motivo per cui non serve toccare il codice per
aggiungere Qwen-Image, Hunyuan3D o Wan: basta esportare il workflow da ComfyUI.
"""

import json
import random
import re
from pathlib import Path

from core.logger import get_logger

log = get_logger("comfy_workflows")

WORKFLOW_DIR = Path("data/creative/workflows")

# Checkpoint di default per famiglia: sovrascrivibili da
# config.creative.backends.comfyui.checkpoints
DEFAULT_CHECKPOINTS = {
    "sdxl": "sd_xl_base_1.0.safetensors",
    "sd3": "sd3.5_large.safetensors",
    "flux": "flux1-dev-fp8.safetensors",
    "qwen": "qwen_image_fp8.safetensors",
    "upscaler": "RealESRGAN_x4plus.pth",
}


def _seed(params: dict):
    seed = params.get("seed", -1)
    # Un placeholder attraversa il builder intatto: serve a generare il manifest
    # del workflow senza eseguirlo.
    if isinstance(seed, str) and "{{" in seed:
        return seed
    return random.randint(0, 2**31 - 1) if seed in (None, -1, "") else int(seed)


# I nomi dei sampler differiscono fra ecosistemi: quelli in stile A1111/SD WebUI
# vengono rifiutati da ComfyUI con `value_not_in_list`.
SAMPLER_ALIASES = {
    "euler_a": "euler_ancestral",
    "euler a": "euler_ancestral",
    "dpm++ 2m": "dpmpp_2m",
    "dpm++ 2m karras": "dpmpp_2m",
    "dpm++ sde": "dpmpp_sde",
    "dpm++ 2m sde": "dpmpp_2m_sde",
    "dpm2": "dpm_2",
    "dpm2 a": "dpm_2_ancestral",
    "lms": "lms",
    "unipc": "uni_pc",
    "ddim": "ddim",
}


def _sampler(params: dict, default: str = "euler") -> str:
    name = str(params.get("sampler") or default).strip()
    return SAMPLER_ALIASES.get(name.lower(), name)


# ---------------------------------------------------------------------------
# Template built-in
# ---------------------------------------------------------------------------

def _sdxl_txt2img(p: dict) -> dict:
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": _seed(p), "steps": p.get("steps", 30), "cfg": p.get("cfg_scale", 7.0),
            "sampler_name": _sampler(p), "scheduler": p.get("scheduler", "normal"),
            "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": p["ckpt"]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {
            "batch_size": p.get("batch_size", 1),
            "width": p.get("width", 1024), "height": p.get("height", 1024)}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": p.get("prompt", ""), "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": p.get("negative_prompt", ""), "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "sigma", "images": ["8", 0]}},
    }


def _sdxl_img2img(p: dict) -> dict:
    wf = _sdxl_txt2img(p)
    wf["10"] = {"class_type": "LoadImage", "inputs": {"image": p["input_image"]}}
    wf["11"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["4", 2]}}
    wf["3"]["inputs"]["latent_image"] = ["11", 0]
    wf["3"]["inputs"]["denoise"] = p.get("strength", 0.7)
    wf.pop("5")
    return wf


def _sdxl_inpaint(p: dict) -> dict:
    wf = _sdxl_txt2img(p)
    wf["10"] = {"class_type": "LoadImage", "inputs": {"image": p["input_image"]}}
    wf["12"] = {"class_type": "LoadImageMask", "inputs": {"image": p["mask_image"], "channel": "red"}}
    wf["13"] = {"class_type": "VAEEncodeForInpaint", "inputs": {
        "pixels": ["10", 0], "vae": ["4", 2], "mask": ["12", 0],
        "grow_mask_by": p.get("mask_blur", 6)}}
    wf["3"]["inputs"]["latent_image"] = ["13", 0]
    wf["3"]["inputs"]["denoise"] = p.get("strength", 0.85)
    wf.pop("5")
    return wf


def _flux_txt2img(p: dict) -> dict:
    """FLUX usa doppio encoder (CLIP-L + T5) e guidance dedicata."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": p["ckpt"], "weight_dtype": p.get("weight_dtype", "fp8_e4m3fn")}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": p.get("clip_l", "clip_l.safetensors"),
            "clip_name2": p.get("clip_t5", "t5xxl_fp8_e4m3fn.safetensors"),
            "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": p.get("vae", "ae.safetensors")}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": p.get("prompt", ""), "clip": ["2", 0]}},
        "5": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["4", 0], "guidance": p.get("cfg_scale", 3.5)}},
        "6": {"class_type": "EmptySD3LatentImage", "inputs": {
            "batch_size": p.get("batch_size", 1),
            "width": p.get("width", 1024), "height": p.get("height", 1024)}},
        "7": {"class_type": "KSampler", "inputs": {
            "seed": _seed(p), "steps": p.get("steps", 20), "cfg": 1.0,
            "sampler_name": _sampler(p), "scheduler": p.get("scheduler", "simple"),
            "denoise": 1.0,
            "model": ["1", 0], "positive": ["5", 0], "negative": ["8", 0], "latent_image": ["6", 0]}},
        "8": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "sigma_flux", "images": ["9", 0]}},
    }


def _esrgan_upscale(p: dict) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": p["input_image"]}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": p.get("upscale_model", DEFAULT_CHECKPOINTS["upscaler"])}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "sigma_up", "images": ["3", 0]}},
    }


BUILTIN = {
    "sdxl_txt2img": _sdxl_txt2img,
    "sd3_txt2img": _sdxl_txt2img,      # SD3.5 usa lo stesso grafo checkpoint-based
    "sdxl_img2img": _sdxl_img2img,
    "sdxl_inpaint": _sdxl_inpaint,
    "flux_txt2img": _flux_txt2img,
    "qwen_txt2img": _flux_txt2img,     # stessa topologia dual-encoder
    "esrgan_upscale": _esrgan_upscale,
}

# Workflow che richiedono nodi custom (Hunyuan3D, TRELLIS, SAM2, Wan, SUPIR,
# Kontext...): non esistono built-in perché i nomi dei nodi dipendono
# dall'estensione installata. Vanno forniti come JSON esportato da ComfyUI.
CUSTOM_ONLY = (
    "qwen_edit", "flux_kontext", "supir_upscale", "sam2_segment",
    "hunyuan3d_image_to_3d", "trellis_image_to_3d", "instantmesh_image_to_3d",
    "triposr_image_to_3d", "wan_image_to_video", "ltx_image_to_video",
    "hunyuan_text_to_video",
)


class WorkflowNotAvailable(RuntimeError):
    """Il workflow richiesto non ha un built-in e non è stato fornito dall'utente."""


def user_workflow_path(name: str) -> Path:
    return WORKFLOW_DIR / f"{name}.json"


def list_workflows() -> dict:
    """Stato dei workflow secondo il registro, non secondo una lista fissa."""
    from core.creative.workflow_registry import registry

    entries = registry.load(force=True)
    provided = set(entries)
    return {
        "builtin": sorted(w.id for w in entries.values() if w.source == "builtin"),
        "user_provided": sorted(w.id for w in entries.values() if w.source == "user"),
        "custom_required": sorted(set(CUSTOM_ONLY) - provided),
        "directory": str(registry.directory),
    }


def _substitute(template: str, params: dict) -> str:
    """Sostituisce i placeholder `{{chiave}}` con i parametri (JSON-safe)."""
    def repl(match):
        key = match.group(1).strip()
        value = params.get(key, "")
        if isinstance(value, str):
            # Il placeholder è già dentro una stringa JSON: va solo escapato.
            return json.dumps(value)[1:-1]
        return str(value)
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, template)


def build(name: str, params: dict) -> dict:
    """Costruisce il workflow API-format, preferendo l'override utente."""
    params = dict(params)
    params.setdefault("seed", _seed(params))

    path = user_workflow_path(name)
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        try:
            workflow = json.loads(_substitute(raw, params))
        except json.JSONDecodeError as e:
            raise WorkflowNotAvailable(f"Workflow '{name}' non è JSON valido dopo la sostituzione: {e}")
        log.info(f"Workflow '{name}' caricato da {path}")
        return workflow

    builder = BUILTIN.get(name)
    if builder is None:
        raise WorkflowNotAvailable(
            f"Il workflow '{name}' richiede nodi custom di ComfyUI. Esportalo da ComfyUI "
            f"con «Save (API format)» e salvalo come {user_workflow_path(name)} "
            "usando i placeholder {{prompt}}, {{input_image}}, {{width}}, {{height}}, {{seed}}."
        )
    return builder(params)
