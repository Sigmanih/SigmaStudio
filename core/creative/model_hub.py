"""Ricerca modelli su Hugging Face e Civitai.

Il catalogo curato di `model_downloader` copre l'essenziale; questo modulo apre
tutto il resto. Le due sorgenti hanno API, tassonomie e formati diversi: qui
vengono normalizzate in un unico risultato con la **categoria** — che è anche
ciò che determina in quale cartella di ComfyUI finisce il file.

La categoria non è un'etichetta cosmetica: è il contratto fra "cosa cerco" e
"dove deve stare perché funzioni".
"""

from dataclasses import dataclass, field

import requests

from core.logger import get_logger

log = get_logger("creative_model_hub")

TIMEOUT = 20
UA = {"User-Agent": "SigmaStudio/8.0 (+model-hub)"}

# Estensioni che ha senso scaricare come pesi.
WEIGHT_EXTS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx")


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    folder: str                  # sottocartella di ComfyUI models/
    hf_filters: tuple = ()       # tag/filtri Hugging Face
    hf_query_hint: str = ""      # termine aggiunto alla ricerca HF
    civitai_types: tuple = ()    # `types` dell'API Civitai
    description: str = ""


CATEGORIES: tuple[Category, ...] = (
    Category("checkpoint", "Checkpoint", "checkpoints",
             hf_filters=("text-to-image",), civitai_types=("Checkpoint",),
             description="Modelli completi di generazione immagini (SDXL, SD 1.5, Pony...)."),
    Category("diffusion", "Diffusion / UNET", "diffusion_models",
             hf_filters=("text-to-image",), hf_query_hint="unet",
             description="Modelli a componenti separate: FLUX, SD3, Qwen-Image."),
    Category("lora", "LoRA", "loras",
             hf_filters=("lora",), civitai_types=("LORA", "LoCon", "DoRA"),
             description="Adattatori di stile, personaggio o concetto."),
    Category("vae", "VAE", "vae",
             hf_query_hint="vae", civitai_types=("VAE",),
             description="Decoder latente: influisce su colori e dettaglio fine."),
    Category("controlnet", "ControlNet", "controlnet",
             hf_query_hint="controlnet", civitai_types=("Controlnet",),
             description="Guida strutturale: pose, bordi, profondità."),
    Category("upscaler", "Upscaler", "upscale_models",
             hf_query_hint="upscaler esrgan", civitai_types=("Upscaler",),
             description="Aumento risoluzione senza rigenerare l'immagine."),
    Category("embedding", "Embedding", "embeddings",
             hf_query_hint="textual inversion", civitai_types=("TextualInversion",),
             description="Textual inversion: concetti richiamabili dal prompt."),
    Category("text_encoder", "Text encoder", "text_encoders",
             hf_query_hint="clip t5 text encoder",
             description="CLIP e T5 richiesti dai modelli a componenti separate."),
    Category("clip_vision", "CLIP Vision", "clip_vision",
             hf_query_hint="clip vision",
             description="Encoder visivo per IP-Adapter e riferimenti immagine."),
)

CATEGORIES_BY_ID = {c.id: c for c in CATEGORIES}
ALLOWED_FOLDERS = {c.folder for c in CATEGORIES}


@dataclass
class SearchResult:
    id: str
    source: str                  # huggingface | civitai
    name: str
    author: str = ""
    category: str = ""
    folder: str = ""
    description: str = ""
    downloads: int = 0
    likes: int = 0
    url: str = ""                # pagina web del modello
    thumbnail: str = ""
    tags: list = field(default_factory=list)
    files: list = field(default_factory=list)   # [{filename, url, size_gb, format}]
    gated: bool = False
    license: str = ""

    def to_dict(self):
        return self.__dict__


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------

def _hf_headers(token: str = "") -> dict:
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _hf_files(repo_id: str, token: str = "", limit: int = 12) -> list:
    """File di pesi presenti nel repo, con URL diretto di download."""
    try:
        resp = requests.get(f"https://huggingface.co/api/models/{repo_id}/tree/main",
                            params={"recursive": "true"}, headers=_hf_headers(token), timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        entries = resp.json()
    except Exception as e:
        log.debug(f"Tree HF non leggibile per {repo_id}: {e}")
        return []

    files = []
    for entry in entries:
        path = entry.get("path", "")
        if entry.get("type") != "file" or not path.lower().endswith(WEIGHT_EXTS):
            continue
        size = entry.get("size") or (entry.get("lfs") or {}).get("size") or 0
        files.append({
            "filename": path.split("/")[-1],
            "path": path,
            "url": f"https://huggingface.co/{repo_id}/resolve/main/{path}",
            "size_gb": round(size / 1024 ** 3, 2) if size else 0.0,
            "format": path.split(".")[-1],
        })
    # I file più grandi sono quasi sempre i pesi principali.
    files.sort(key=lambda f: -f["size_gb"])
    return files[:limit]


def search_huggingface(query: str, category: Category = None, limit: int = 15,
                       token: str = "", with_files: bool = True) -> list[SearchResult]:
    params = {
        "search": " ".join(filter(None, [query, category.hf_query_hint if category else ""])).strip(),
        "sort": "downloads", "direction": -1, "limit": limit,
        "full": "true",
    }
    if category and category.hf_filters:
        params["filter"] = category.hf_filters[0]

    try:
        resp = requests.get("https://huggingface.co/api/models", params=params,
                            headers=_hf_headers(token), timeout=TIMEOUT)
        resp.raise_for_status()
        items = resp.json()
    except Exception as e:
        log.warning(f"Ricerca Hugging Face fallita: {e}")
        raise RuntimeError(f"Hugging Face non raggiungibile: {e}")

    results = []
    for item in items:
        repo_id = item.get("id", "")
        card = item.get("cardData") or {}
        results.append(SearchResult(
            id=repo_id, source="huggingface",
            name=repo_id.split("/")[-1], author=repo_id.split("/")[0] if "/" in repo_id else "",
            category=category.id if category else "",
            folder=category.folder if category else "",
            description=(card.get("summary") or item.get("pipeline_tag") or "")[:220],
            downloads=item.get("downloads", 0), likes=item.get("likes", 0),
            url=f"https://huggingface.co/{repo_id}",
            tags=[t for t in (item.get("tags") or []) if not t.startswith(("license:", "region:"))][:8],
            gated=bool(item.get("gated")),
            license=next((t.split(":", 1)[1] for t in (item.get("tags") or []) if t.startswith("license:")), ""),
            files=_hf_files(repo_id, token) if with_files else [],
        ))
    return results


# ---------------------------------------------------------------------------
# Civitai
# ---------------------------------------------------------------------------

def search_civitai(query: str, category: Category = None, limit: int = 15,
                   token: str = "", nsfw: bool = False) -> list[SearchResult]:
    params = {"limit": min(limit, 100), "sort": "Highest Rated", "period": "AllTime"}
    if query:
        params["query"] = query
    if category and category.civitai_types:
        params["types"] = list(category.civitai_types)
    if not nsfw:
        params["nsfw"] = "false"

    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get("https://civitai.com/api/v1/models", params=params,
                            headers=headers, timeout=TIMEOUT)
        if resp.status_code == 401:
            raise RuntimeError("Civitai richiede una API key: impostala come civitai_token in Impostazioni → Creative.")
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except RuntimeError:
        raise
    except Exception as e:
        log.warning(f"Ricerca Civitai fallita: {e}")
        raise RuntimeError(f"Civitai non raggiungibile: {e}")

    results = []
    for item in items:
        versions = item.get("modelVersions") or []
        latest = versions[0] if versions else {}
        files = []
        for f in (latest.get("files") or []):
            url = f.get("downloadUrl")
            name = f.get("name", "")
            if not url or not name.lower().endswith(WEIGHT_EXTS):
                continue
            meta = f.get("metadata") or {}
            files.append({
                "filename": name,
                "path": name,
                # Il token va nell'URL: Civitai non accetta l'header su /download.
                "url": f"{url}?token={token}" if token else url,
                "size_gb": round((f.get("sizeKB") or 0) / 1024 ** 2, 2),
                "format": (meta.get("format") or name.split(".")[-1]),
                "precision": meta.get("fp") or "",
            })

        images = latest.get("images") or []
        stats = item.get("stats") or {}
        results.append(SearchResult(
            id=str(item.get("id")), source="civitai",
            name=item.get("name", ""),
            author=(item.get("creator") or {}).get("username", ""),
            category=category.id if category else _civitai_category(item.get("type", "")),
            folder=(category.folder if category
                    else CATEGORIES_BY_ID.get(_civitai_category(item.get("type", "")), CATEGORIES[0]).folder),
            description=(item.get("description") or "").replace("<p>", "").replace("</p>", "")[:220],
            downloads=stats.get("downloadCount", 0), likes=stats.get("thumbsUpCount", 0),
            url=f"https://civitai.com/models/{item.get('id')}",
            thumbnail=next((i.get("url") for i in images if i.get("type") == "image"), ""),
            tags=(item.get("tags") or [])[:8],
            license="; ".join(filter(None, [
                "commerciale" if item.get("allowCommercialUse") else "",
                "no credit" if item.get("allowNoCredit") else "",
            ])),
            files=files[:6],
        ))
    return results


_CIVITAI_TYPE_MAP = {
    "Checkpoint": "checkpoint", "LORA": "lora", "LoCon": "lora", "DoRA": "lora",
    "VAE": "vae", "Controlnet": "controlnet", "Upscaler": "upscaler",
    "TextualInversion": "embedding",
}


def _civitai_category(civitai_type: str) -> str:
    return _CIVITAI_TYPE_MAP.get(civitai_type, "checkpoint")


# ---------------------------------------------------------------------------

def search(query: str = "", category_id: str = "", sources: tuple = ("huggingface", "civitai"),
           limit: int = 15, hf_token: str = "", civitai_token: str = "") -> dict:
    """Ricerca unificata. Le sorgenti non raggiungibili non bloccano le altre."""
    category = CATEGORIES_BY_ID.get(category_id)
    results, errors = [], {}

    if "huggingface" in sources:
        try:
            results += search_huggingface(query, category, limit, hf_token)
        except Exception as e:
            errors["huggingface"] = str(e)

    if "civitai" in sources:
        try:
            results += search_civitai(query, category, limit, civitai_token)
        except Exception as e:
            errors["civitai"] = str(e)

    # Senza file scaricabili un risultato non è azionabile: va in fondo.
    results.sort(key=lambda r: (bool(r.files), r.downloads), reverse=True)
    return {
        "results": [r.to_dict() for r in results],
        "errors": errors,
        "category": category.id if category else "",
    }
