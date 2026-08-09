import os
from pathlib import Path
from core.logger import get_logger
from core.creative.model_router import ModelRouter, CreativeTask
from core.creative.asset_graph import AssetGraph, Asset, AssetType
from core.creative.params import normalize_params
from .adapters.comfyui_adapter import ComfyUIAdapter
from .adapters.sd_webui_adapter import SDWebUIAdapter
from .adapters.fal_adapter import FalAIAdapter
from .adapters.stability_adapter import StabilityAdapter
from .adapters.pollinations_adapter import PollinationsAdapter

log = get_logger("creative_image_generator")

FALLBACK_BACKEND = "pollinations"


class ImageGenerator:
    def __init__(self, model_router: ModelRouter, asset_graph: AssetGraph):
        self.router = model_router
        self.graph = asset_graph

    def _get_adapter(self, backend_name: str):
        backends = self.router.get_config().get("backends", {})
        cfg = backends.get(backend_name, {})

        if backend_name == "comfyui":
            return ComfyUIAdapter(base_url=cfg.get("url", "http://127.0.0.1:8188"), config=cfg)
        elif backend_name == "sd_webui":
            return SDWebUIAdapter(base_url=cfg.get("url", "http://127.0.0.1:7860"))
        elif backend_name == "fal_ai":
            return FalAIAdapter(api_key=cfg.get("api_key", ""))
        elif backend_name == "stability":
            return StabilityAdapter(api_key=cfg.get("api_key", ""))
        else:
            return PollinationsAdapter()

    async def _call_with_fallback(self, backend: str, method: str, *args) -> tuple[bytes, str]:
        """Invoca l'adapter del backend scelto; se fallisce ripiega sul default.

        Ritorna (bytes, backend_effettivamente_usato) così che il metadata
        dell'asset registri il generatore reale e non quello richiesto.
        """
        adapter = self._get_adapter(backend)
        fn = getattr(adapter, method, None)
        if fn is not None:
            try:
                return await fn(*args), backend
            except Exception as e:
                if backend == FALLBACK_BACKEND:
                    raise
                log.warning(f"Backend '{backend}' fallito su {method} ({e}); fallback su {FALLBACK_BACKEND}")
        else:
            log.warning(f"Backend '{backend}' non implementa {method}; fallback su {FALLBACK_BACKEND}")

        fallback = self._get_adapter(FALLBACK_BACKEND)
        fallback_fn = getattr(fallback, method, None)
        if fallback_fn is None:
            raise RuntimeError(f"Nessun backend disponibile per l'operazione '{method}'")
        return await fallback_fn(*args), FALLBACK_BACKEND

    async def _plan(self, task: CreativeTask, backend: str = None):
        """Decide modello e backend e arricchisce i params di conseguenza.

        Con `backend` forzato dalla UI si rispetta la scelta dell'utente ma si
        continua a selezionare il modello migliore *dentro* quel backend.
        """
        model, selected = await self.router.select(task)
        if backend:
            selected = backend
            if model and backend not in model.backends:
                model = None
        task.params = self.router.apply_model(task.params, model, selected or backend)
        return model, (selected or backend or FALLBACK_BACKEND)

    def _save_image_asset(self, image_bytes: bytes, name: str, metadata: dict, source_assets: list = None) -> Asset:
        asset = self.graph.create_asset(
            type_val=AssetType.IMAGE,
            name=name,
            metadata=metadata,
            source_assets=source_assets
        )
        return self.graph.attach_file(asset.asset_id, "image", "image.png", image_bytes)

    def _read_source_image(self, asset_id: str) -> tuple[Asset, bytes]:
        source_asset = self.graph.get_asset(asset_id)
        if not source_asset:
            raise ValueError(f"Asset sorgente {asset_id} non trovato")

        file_path = source_asset.files.get("image")
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"L'asset '{source_asset.name}' non ha un file immagine su disco")

        with open(file_path, "rb") as f:
            return source_asset, f.read()

    async def text_to_image(self, prompt: str, negative_prompt: str = '', width: int = 1024, height: int = 1024,
                            steps: int = 30, cfg_scale: float = 7.0, sampler: str = None, seed: int = -1,
                            model: str = None, backend: str = None, priority: str = 'balanced', **extra) -> Asset:
        if not prompt or not str(prompt).strip():
            raise ValueError("Il prompt è obbligatorio per la generazione text_to_image")

        task = CreativeTask('text_to_image', normalize_params({
            "prompt": prompt, "negative_prompt": negative_prompt, "width": width, "height": height,
            "steps": steps, "cfg_scale": cfg_scale, "sampler": sampler, "seed": seed, "model": model,
            **extra
        }), priority=priority)

        spec, selected_backend = await self._plan(task, backend)
        log.info(f"Esecuzione text_to_image con {selected_backend}" + (f" / {spec.id}" if spec else ""))
        image_bytes, used_backend = await self._call_with_fallback(
            selected_backend, "text_to_image", prompt, task.params
        )

        return self._save_image_asset(
            image_bytes,
            name=f"txt2img_{str(prompt)[:20].strip()}",
            metadata={"generator": used_backend, "model": spec.id if spec else None,
                      "operation": "text_to_image", "params": task.params}
        )

    async def image_to_image(self, source_asset_id: str, prompt: str, strength: float = 0.7,
                             backend: str = None, **kwargs) -> Asset:
        source_asset, image_bytes = self._read_source_image(source_asset_id)

        task = CreativeTask('img_to_img', normalize_params({"prompt": prompt, "strength": strength, **kwargs}))
        spec, selected_backend = await self._plan(task, backend)
        log.info(f"Esecuzione img_to_img con {selected_backend}" + (f" / {spec.id}" if spec else ""))
        new_image_bytes, used_backend = await self._call_with_fallback(
            selected_backend, "img_to_image", image_bytes, prompt, task.params
        )

        return self._save_image_asset(
            new_image_bytes,
            name=f"img2img_{str(prompt)[:20].strip()}",
            metadata={"generator": used_backend, "model": spec.id if spec else None,
                      "operation": "img_to_img", "params": task.params},
            source_assets=[source_asset_id]
        )

    async def instruct_edit(self, source_asset_id: str, instruction: str, backend: str = None, **kwargs) -> Asset:
        """Editing guidato dal linguaggio (FLUX Kontext / Qwen-Image-Edit).

        A differenza di img2img non serve una maschera: il modello interpreta
        l'istruzione mantenendo il resto dell'immagine coerente.
        """
        if not instruction or not str(instruction).strip():
            raise ValueError("L'istruzione è obbligatoria per instruct_edit")
        source_asset, image_bytes = self._read_source_image(source_asset_id)

        task = CreativeTask('instruct_edit', normalize_params({"prompt": instruction, **kwargs}),
                            priority=kwargs.get("priority", "quality"))
        spec, selected_backend = await self._plan(task, backend)
        if spec is None and selected_backend in (None, FALLBACK_BACKEND):
            raise RuntimeError(
                "Nessun modello di instruct-editing disponibile. Serve ComfyUI con FLUX Kontext "
                "o Qwen-Image-Edit, oppure una API key fal.ai."
            )

        log.info(f"Instruct edit di {source_asset_id} con {selected_backend} / {spec.id if spec else '?'}")
        new_bytes, used_backend = await self._call_with_fallback(
            selected_backend, "instruct_edit", image_bytes, instruction, task.params
        )

        return self._save_image_asset(
            new_bytes,
            name=f"{source_asset.name}_edit",
            metadata={"generator": used_backend, "model": spec.id if spec else None,
                      "operation": "instruct_edit", "instruction": instruction, "params": task.params},
            source_assets=[source_asset_id]
        )

    async def upscale(self, asset_id: str, scale: int = 2, model: str = None,
                      backend: str = None, restore: bool = False, **kwargs) -> Asset:
        """Upscale: Real-ESRGAN per immagini pulite, SUPIR quando serve restauro.

        `restore=True` dichiara che la sorgente è degradata: l'agente preferisce
        allora un modello di ricostruzione generativa invece di un interpolatore.
        """
        source_asset, image_bytes = self._read_source_image(asset_id)

        params = normalize_params({"scale": scale, **kwargs})
        if model:
            params["model"] = model
        task = CreativeTask(
            'upscale', params,
            priority=kwargs.get("priority", "quality" if restore else "balanced"),
        )
        task.params["prefer"] = ("ricostruzione_dettagli", "restauro") if restore else ("veloce", "affidabile")

        spec, selected_backend = await self._plan(task, backend)
        task.params.pop("prefer", None)
        new_image_bytes, used_backend = await self._call_with_fallback(
            selected_backend, "upscale", image_bytes, task.params
        )

        return self._save_image_asset(
            new_image_bytes,
            name=f"upscale_{source_asset.name}",
            metadata={"generator": used_backend, "model": spec.id if spec else None,
                      "operation": "upscale", "restore": bool(restore), "params": task.params},
            source_assets=[asset_id]
        )
