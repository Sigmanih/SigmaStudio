"""Registro dei modelli creativi.

Sigma non esegue i modelli: li orchestra. Questo registro è la mappa che permette
agli agenti di scegliere *quale* modello usare per *quale* task, in base a:

  - backend disponibili (ComfyUI locale, SD WebUI, fal.ai, Stability, Ollama...)
  - capacità VRAM reale della macchina
  - priorità richiesta (`quality` | `speed` | `balanced`)
  - punti di forza del modello (testo nell'immagine, editing semantico, ecosistema...)

Aggiungere un modello significa aggiungere una riga qui: il router, la UI e gli
agenti lo vedono automaticamente.
"""

from dataclasses import dataclass, field, asdict

from core.logger import get_logger

log = get_logger("creative_model_registry")


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    family: str
    tasks: tuple                      # capability coperte dal modello
    backends: tuple                   # backend che sanno eseguirlo
    vram_gb: float = 0.0              # VRAM minima consigliata per l'esecuzione locale
    quality: int = 3                  # 1..5 — qualità percepita dell'output
    speed: int = 3                    # 1..5 — velocità relativa
    strengths: tuple = ()
    workflow: str = ""                # template ComfyUI (vedi comfy_workflows.py)
    ckpt_key: str = ""                # chiave in creative.backends.comfyui.checkpoints
    remote_ids: dict = field(default_factory=dict)   # backend -> id remoto
    notes: str = ""

    @property
    def checkpoint_key(self) -> str:
        """Chiave con cui si risolve il file di pesi per questo modello."""
        return self.ckpt_key or self.family

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

MODELS: tuple[ModelSpec, ...] = (
    # ----------------------------------------------------------- generazione
    ModelSpec(
        id="flux.1-dev", ckpt_key="flux", label="FLUX.1 dev", family="flux",
        tasks=("text_to_image",), backends=("comfyui", "fal_ai"),
        vram_gb=12.0, quality=5, speed=2,
        strengths=("composizione", "testo_nelle_immagini", "prompt_adherence"),
        workflow="flux_txt2img",
        remote_ids={"fal_ai": "fal-ai/flux/dev"},
        notes="Qualità di riferimento. In fp8/GGUF gira su 12-16 GB.",
    ),
    ModelSpec(
        id="flux.1-schnell", ckpt_key="flux", label="FLUX.1 schnell", family="flux",
        tasks=("text_to_image",), backends=("comfyui", "fal_ai"),
        vram_gb=8.0, quality=4, speed=5,
        strengths=("velocità", "composizione"),
        workflow="flux_txt2img",
        remote_ids={"fal_ai": "fal-ai/flux/schnell"},
        notes="4-8 step: ideale per iterazione rapida e anteprime di pipeline.",
    ),
    ModelSpec(
        id="qwen-image", ckpt_key="qwen", label="Qwen-Image", family="qwen",
        tasks=("text_to_image",), backends=("comfyui", "fal_ai"),
        vram_gb=16.0, quality=5, speed=2,
        strengths=("testo_nelle_immagini", "poster", "mockup", "immagini_prodotto"),
        workflow="qwen_txt2img",
        remote_ids={"fal_ai": "fal-ai/qwen-image"},
        notes="Il migliore quando il testo dentro l'immagine deve essere corretto.",
    ),
    ModelSpec(
        id="sdxl", ckpt_key="sdxl", label="SDXL 1.0", family="sd",
        tasks=("text_to_image", "img_to_img", "inpaint"),
        backends=("comfyui", "sd_webui"),
        vram_gb=8.0, quality=3, speed=4,
        strengths=("ecosistema", "lora", "controlnet", "ip_adapter", "inpaint"),
        workflow="sdxl_txt2img",
        notes="Non il migliore in assoluto, ma l'ecosistema (LoRA/ControlNet) è insostituibile.",
    ),
    ModelSpec(
        id="sd3.5-large", ckpt_key="sd3", label="Stable Diffusion 3.5 Large", family="sd",
        tasks=("text_to_image",), backends=("comfyui", "stability"),
        vram_gb=12.0, quality=4, speed=3,
        strengths=("fotorealismo", "ecosistema"),
        workflow="sd3_txt2img",
        remote_ids={"stability": "sd3.5-large"},
    ),

    ModelSpec(
        id="pollinations", label="Pollinations (zero-setup)", family="pollinations",
        tasks=("text_to_image", "img_to_img", "upscale"), backends=("pollinations",),
        vram_gb=0.0, quality=2, speed=4,
        strengths=("zero_setup", "nessuna_configurazione"),
        notes="Fallback pubblico senza setup né GPU: qualità e controllo limitati, "
              "ma garantisce che la pipeline sia sempre percorribile.",
    ),

    # ---------------------------------------------------------------- editing
    ModelSpec(
        id="qwen-image-edit", ckpt_key="qwen", label="Qwen-Image-Edit", family="qwen",
        tasks=("instruct_edit", "inpaint", "img_to_img"),
        backends=("comfyui", "fal_ai"),
        vram_gb=16.0, quality=5, speed=2,
        strengths=("editing_semantico", "istruzioni_naturali", "testo"),
        workflow="qwen_edit",
        remote_ids={"fal_ai": "fal-ai/qwen-image-edit"},
        notes="Editor generalista guidato da istruzioni ('cambia lo sfondo in...').",
    ),
    ModelSpec(
        id="flux-kontext", ckpt_key="flux", label="FLUX.1 Kontext", family="flux",
        tasks=("instruct_edit", "img_to_img"),
        backends=("comfyui", "fal_ai"),
        vram_gb=12.0, quality=5, speed=3,
        strengths=("coerenza_soggetto", "editing_semantico", "relight"),
        workflow="flux_kontext",
        remote_ids={"fal_ai": "fal-ai/flux-pro/kontext"},
        notes="Modifiche guidate dal linguaggio preservando l'identità del soggetto.",
    ),
    ModelSpec(
        id="sdxl-inpaint", ckpt_key="sdxl", label="SDXL Inpainting", family="sd",
        tasks=("inpaint", "outpaint"), backends=("comfyui", "sd_webui"),
        vram_gb=8.0, quality=3, speed=4,
        strengths=("inpaint", "outpaint", "controllo_maschera"),
        workflow="sdxl_inpaint",
    ),

    # -------------------------------------------------------------- upscaling
    ModelSpec(
        id="real-esrgan", ckpt_key="upscaler", label="Real-ESRGAN x4", family="esrgan",
        tasks=("upscale",), backends=("comfyui", "sd_webui"),
        vram_gb=2.0, quality=3, speed=5,
        strengths=("veloce", "affidabile", "nessuna_allucinazione"),
        workflow="esrgan_upscale",
        notes="Default per immagini già pulite: ingrandisce senza inventare dettagli.",
    ),
    ModelSpec(
        id="supir", label="SUPIR", family="supir",
        tasks=("upscale", "restore"), backends=("comfyui",),
        vram_gb=16.0, quality=5, speed=1,
        strengths=("ricostruzione_dettagli", "restauro", "foto_degradate"),
        workflow="supir_upscale",
        notes="Ricostruzione generativa: da usare su sorgenti degradate, non su render puliti.",
    ),
    ModelSpec(
        id="swinir", ckpt_key="upscaler", label="SwinIR", family="swinir",
        tasks=("upscale",), backends=("comfyui",),
        vram_gb=4.0, quality=4, speed=3,
        strengths=("texture", "dettaglio_fine"),
        workflow="esrgan_upscale",
    ),

    # ----------------------------------------------------------------- vision
    ModelSpec(
        id="qwen2.5-vl", label="Qwen2.5-VL", family="qwen",
        tasks=("vision_describe", "vision_qa", "quality_score", "ocr"),
        backends=("ollama",),
        vram_gb=8.0, quality=5, speed=3,
        strengths=("descrizione", "ocr", "controllo_qualità", "confronto"),
        remote_ids={"ollama": "qwen2.5vl:7b"},
        notes="Gli occhi di Sigma: analisi, QA e scoring degli output creativi.",
    ),
    ModelSpec(
        id="llava", label="LLaVA", family="llava",
        tasks=("vision_describe", "vision_qa"), backends=("ollama",),
        vram_gb=6.0, quality=3, speed=4,
        strengths=("descrizione",),
        remote_ids={"ollama": "llava:7b"},
    ),

    # ----------------------------------------------------------- segmentation
    ModelSpec(
        id="sam2", label="Segment Anything 2", family="sam",
        tasks=("segment", "remove_background"), backends=("comfyui",),
        vram_gb=4.0, quality=5, speed=4,
        strengths=("maschere_precise", "prompt_punti", "video"),
        workflow="sam2_segment",
        notes="Produce la maschera; l'inpainting/sostituzione sfondo la consuma.",
    ),
    ModelSpec(
        id="rembg", label="rembg (U2-Net)", family="rembg",
        tasks=("remove_background",), backends=("local",),
        vram_gb=1.0, quality=3, speed=5,
        strengths=("zero_setup", "veloce"),
        notes="Fallback locale se SAM 2 non è disponibile.",
    ),

    # ------------------------------------------------------------------- 3D
    ModelSpec(
        id="hunyuan3d-2", label="Hunyuan3D 2.x", family="hunyuan3d",
        tasks=("image_to_3d", "texture_3d"), backends=("comfyui", "fal_ai"),
        vram_gb=12.0, quality=5, speed=2,
        strengths=("geometria", "texture", "asset_prodotto"),
        workflow="hunyuan3d_image_to_3d",
        remote_ids={"fal_ai": "fal-ai/hunyuan3d/v2"},
        notes="Prima scelta per asset 3D texturizzati di qualità.",
    ),
    ModelSpec(
        id="trellis", label="TRELLIS", family="trellis",
        tasks=("image_to_3d", "multiview_to_3d"), backends=("comfyui", "fal_ai"),
        vram_gb=16.0, quality=5, speed=2,
        strengths=("geometria", "multi_vista", "concept_to_3d"),
        workflow="trellis_image_to_3d",
        remote_ids={"fal_ai": "fal-ai/trellis"},
    ),
    ModelSpec(
        id="instantmesh", label="InstantMesh", family="instantmesh",
        tasks=("image_to_3d",), backends=("comfyui", "fal_ai"),
        vram_gb=10.0, quality=4, speed=4,
        strengths=("velocità", "mesh_pulita"),
        workflow="instantmesh_image_to_3d",
        remote_ids={"fal_ai": "fal-ai/instant-mesh"},
    ),
    ModelSpec(
        id="triposr", label="TripoSR", family="triposr",
        tasks=("image_to_3d",), backends=("comfyui", "fal_ai"),
        vram_gb=6.0, quality=2, speed=5,
        strengths=("velocità", "vram_bassa", "anteprima"),
        workflow="triposr_image_to_3d",
        remote_ids={"fal_ai": "fal-ai/triposr"},
        notes="Anteprima rapida: utile per validare l'inquadratura prima di un modello pesante.",
    ),
    ModelSpec(
        id="stable-fast-3d", label="Stable Fast 3D", family="stability",
        tasks=("image_to_3d",), backends=("stability",),
        vram_gb=0.0, quality=3, speed=5,
        strengths=("api", "nessun_setup_locale"),
        remote_ids={"stability": "stable-fast-3d"},
    ),

    # -------------------------------------------------------------- materiali
    ModelSpec(
        id="pbr-derive", label="PBR derivate (locale)", family="local",
        tasks=("texture_pbr",), backends=("local",),
        vram_gb=0.0, quality=3, speed=5,
        strengths=("coerenza_mappe", "zero_setup"),
        notes="Albedo dal modello immagine, mappe derivate localmente in numpy.",
    ),

    # ------------------------------------------------------------------ video
    ModelSpec(
        id="wan2.2", label="Wan 2.2", family="wan",
        tasks=("text_to_video", "image_to_video"), backends=("comfyui", "fal_ai"),
        vram_gb=16.0, quality=5, speed=2,
        strengths=("movimento", "coerenza_temporale", "i2v"),
        workflow="wan_image_to_video",
        remote_ids={"fal_ai": "fal-ai/wan-i2v"},
    ),
    ModelSpec(
        id="ltx-video", label="LTX-Video", family="ltx",
        tasks=("text_to_video", "image_to_video"), backends=("comfyui", "fal_ai"),
        vram_gb=12.0, quality=3, speed=5,
        strengths=("leggerezza", "realtime", "vram_bassa"),
        workflow="ltx_image_to_video",
        remote_ids={"fal_ai": "fal-ai/ltx-video"},
        notes="Il più gestibile in locale: prima scelta sotto i 16 GB liberi.",
    ),
    ModelSpec(
        id="hunyuan-video", label="HunyuanVideo", family="hunyuan",
        tasks=("text_to_video",), backends=("comfyui", "fal_ai"),
        vram_gb=24.0, quality=5, speed=1,
        strengths=("qualità", "cinematografico"),
        workflow="hunyuan_text_to_video",
        remote_ids={"fal_ai": "fal-ai/hunyuan-video"},
        notes="Molto pesante: sensato solo su GPU grandi o via API.",
    ),
)

MODELS_BY_ID = {m.id: m for m in MODELS}

# Task per cui una VRAM insufficiente non è un ostacolo se il backend è remoto.
REMOTE_BACKENDS = frozenset({"fal_ai", "stability", "replicate", "pollinations"})


def models_for_task(task: str) -> list[ModelSpec]:
    return [m for m in MODELS if task in m.tasks]


def get_model(model_id: str) -> ModelSpec | None:
    return MODELS_BY_ID.get(model_id)


def available_vram_gb() -> float:
    """VRAM *totale* della GPU più capiente (0.0 se non rilevabile).

    Deliberatamente non è la memoria libera: un backend che tiene i pesi in
    cache la fa scendere, e useremmo il successo di ComfyUI come motivo per
    smettere di sceglierlo. La capacità della scheda è il vincolo reale.
    """
    try:
        from core.training import gpu as gpu_layer
        report = gpu_layer.get_accelerator_report(refresh=False)
        gpus = report.get("gpus") or []
        return max((g.get("vram_total_gb") or 0.0) for g in gpus) if gpus else 0.0
    except Exception as e:
        log.debug(f"VRAM non rilevabile: {e}")
        return 0.0


def free_vram_gb() -> float:
    """VRAM libera adesso — solo per la UI, non per le decisioni di routing."""
    try:
        from core.training import gpu as gpu_layer
        report = gpu_layer.get_accelerator_report(refresh=True)
        gpus = report.get("gpus") or []
        return max((g.get("vram_free_gb") or 0.0) for g in gpus) if gpus else 0.0
    except Exception:
        return 0.0


def score_model(model: ModelSpec, backend: str, priority: str, vram_gb: float,
                prefer: tuple = ()) -> float:
    """Punteggio di idoneità: più alto = scelta migliore.

    Il peso tra qualità e velocità dipende dalla priorità richiesta; i modelli
    locali che non entrano nella VRAM libera vengono penalizzati pesantemente
    invece di essere esclusi, così restano utilizzabili se non c'è alternativa.
    """
    if priority == "speed":
        base = model.speed * 2.0 + model.quality * 0.6
    elif priority == "quality":
        base = model.quality * 2.0 + model.speed * 0.4
    else:
        base = model.quality * 1.3 + model.speed * 1.0

    if prefer:
        base += 1.5 * len(set(prefer) & set(model.strengths))

    is_remote = backend in REMOTE_BACKENDS
    if not is_remote and model.vram_gb:
        if vram_gb <= 0:
            base -= 1.0            # VRAM sconosciuta: leggera cautela
        elif model.vram_gb > vram_gb:
            # Penalità proporzionale allo sforamento: un modello che chiede il
            # doppio della VRAM disponibile deve perdere contro uno che sfora di poco.
            overflow = model.vram_gb / vram_gb - 1.0
            base -= min(12.0, 3.0 + 5.0 * overflow)
        elif model.vram_gb > vram_gb * 0.85:
            base -= 1.0            # ci sta appena
    if is_remote:
        base -= 0.3                # a parità, il locale non ha costi né latenza di rete

    return base


def select_model(task: str, available_backends: set, priority: str = "balanced",
                 vram_gb: float | None = None, prefer: tuple = (),
                 forced_model: str = "") -> tuple[ModelSpec, str] | tuple[None, None]:
    """Sceglie (modello, backend) per il task fra ciò che è realmente disponibile."""
    vram_gb = available_vram_gb() if vram_gb is None else vram_gb

    candidates = []
    pool = [MODELS_BY_ID[forced_model]] if forced_model in MODELS_BY_ID else models_for_task(task)
    for model in pool:
        for backend in model.backends:
            if backend not in available_backends:
                continue
            if backend == "comfyui" and _comfy_workflow_missing(model):
                continue   # nodi custom non installati: sceglierlo sarebbe un errore certo
            candidates.append((score_model(model, backend, priority, vram_gb, prefer), model, backend))

    if not candidates:
        return None, None

    candidates.sort(key=lambda c: c[0], reverse=True)
    score, model, backend = candidates[0]
    log.info(f"Modello scelto per '{task}': {model.id} via {backend} (score {score:.1f}, VRAM libera {vram_gb} GB)")
    return model, backend


# Inventario dell'installazione ComfyUI corrente (impostato dal ModelRouter).
# None = sconosciuto: in quel caso non si assume nulla.
_COMFY_INVENTORY: dict | None = None

# Task che per girare su ComfyUI richiedono un modello di diffusione caricabile.
_DIFFUSION_TASKS = frozenset({
    "text_to_image", "img_to_img", "inpaint", "outpaint", "instruct_edit",
    "text_to_video", "image_to_video",
})


def set_comfy_inventory(inventory: dict | None) -> None:
    """Registra cosa è installato su ComfyUI, per evitare scelte impossibili."""
    global _COMFY_INVENTORY
    _COMFY_INVENTORY = inventory


def _comfy_can_load(model: ModelSpec) -> bool:
    """True se ComfyUI ha su disco il file di pesi che questo modello caricherebbe.

    Un ComfyUI appena installato risponde ai ping ma non ha pesi, e avere *un*
    checkpoint qualsiasi non basta: il workflow di FLUX chiede proprio il file
    FLUX. Selezionarlo comunque significherebbe fallire e ripiegare, sprecando
    un round-trip e confondendo l'utente con un errore evitabile.
    """
    if _COMFY_INVENTORY is None:
        return True

    # Gli upscaler vivono in una cartella propria: senza modelli lì, nessun
    # workflow di upscale può partire.
    if model.checkpoint_key == "upscaler":
        return bool(_COMFY_INVENTORY.get("upscale_models"))

    if not (set(model.tasks) & _DIFFUSION_TASKS):
        return True

    # I workflow forniti dall'utente referenziano i propri file al loro interno:
    # non tocca a noi indovinare quali pesi caricano.
    from core.creative.workflow_registry import registry
    entry = registry.get(model.workflow)
    if entry is not None and entry.source == "user":
        # I workflow dell'utente referenziano i propri file: non tocca a noi
        # indovinare quali pesi caricano.
        return True

    loadable = set(_COMFY_INVENTORY.get("checkpoints") or ()) | set(_COMFY_INVENTORY.get("unets") or ())
    wanted = (_COMFY_INVENTORY.get("configured_checkpoints") or {}).get(model.checkpoint_key)
    return bool(wanted) and wanted in loadable


def _comfy_workflow_missing(model: ModelSpec) -> bool:
    """True se il modello su ComfyUI richiede un workflow custom non ancora fornito.

    Senza questo controllo la UI mostrerebbe come disponibili modelli che poi
    falliscono al primo click con «esporta il workflow».
    """
    if not model.workflow:
        return False
    try:
        from core.creative.workflow_registry import registry
    except Exception:
        return False
    # Il registro è l'unica fonte di verità su quali workflow esistono davvero.
    if registry.get(model.workflow) is None:
        return True
    # Il workflow c'è ma mancano i pesi: per ComfyUI equivale a non averlo.
    return not _comfy_can_load(model)


def _ollama_installed(model: ModelSpec, installed: set | None) -> bool:
    """Un modello Ollama è usabile solo se il tag è stato scaricato."""
    if installed is None:
        return True
    tag = model.remote_ids.get("ollama", model.id)
    base = tag.split(":")[0]
    return any(name.split(":")[0] == base for name in installed)


def catalog(available_backends: set = frozenset(), ollama_models: set | None = None) -> list[dict]:
    """Catalogo serializzabile per la UI, annotato con la disponibilità corrente."""
    vram = available_vram_gb()
    workflow_missing = {m.id: _comfy_workflow_missing(m) for m in MODELS}
    out = []
    for model in MODELS:
        usable = sorted(set(model.backends) & set(available_backends))
        if workflow_missing[model.id] and "comfyui" in usable:
            usable.remove("comfyui")
        if "ollama" in usable and not _ollama_installed(model, ollama_models):
            usable.remove("ollama")
        out.append({
            "workflow_missing": workflow_missing[model.id],
            **model.to_dict(),
            "tasks": list(model.tasks),
            "backends": list(model.backends),
            "strengths": list(model.strengths),
            "available_via": usable,
            "available": bool(usable),
            "fits_vram": (not model.vram_gb) or vram <= 0 or model.vram_gb <= vram,
        })
    return out
