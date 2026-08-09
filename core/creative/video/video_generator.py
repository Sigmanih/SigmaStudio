"""Generazione video: text→video e image→video.

Stessa filosofia del resto del Creative Studio: Sigma sceglie il modello in base
a VRAM e priorità (LTX-Video sotto i 16 GB, Wan per la qualità, HunyuanVideo solo
su GPU grandi o via API) e delega l'esecuzione al backend.
"""

import os

from core.creative.asset_graph import AssetGraph, Asset, AssetType
from core.creative.model_router import ModelRouter, CreativeTask
from core.creative.params import normalize_params
from core.creative.three_d.adapters import Fal3DAdapter
from core.logger import get_logger

log = get_logger("creative_video")

NO_VIDEO_BACKEND = (
    "Nessun backend video disponibile. Opzioni: ComfyUI con il workflow Wan/LTX "
    "esportato in data/creative/workflows/, oppure una API key fal.ai."
)

VIDEO_EXTS = ("mp4", "webm", "gif")


class FalVideoAdapter(Fal3DAdapter):
    """Riusa la coda fal.ai: cambiano solo il modello e la chiave di output."""

    @staticmethod
    def _extract_model_url(result: dict) -> str:
        for key in ("video", "videos", "output"):
            node = result.get(key)
            if isinstance(node, list) and node:
                node = node[0]
            if isinstance(node, dict) and node.get("url"):
                return node["url"]
            if isinstance(node, str) and node.startswith("http"):
                return node
        raise RuntimeError(f"Risposta fal.ai priva di video: {list(result.keys())}")

    async def image_to_video(self, image_bytes: bytes, prompt: str, params: dict) -> tuple[bytes, str]:
        result = await self._run_queue(params.get("model") or "fal-ai/ltx-video", {
            "image_url": self._data_uri(image_bytes),
            "prompt": prompt,
            **{k: v for k, v in params.items() if k in ("num_frames", "fps", "seed")},
        }, timeout_s=int(params.get("timeout", 900)))
        url = self._extract_model_url(result)
        return await self._download(url), url.rsplit(".", 1)[-1].split("?")[0] or "mp4"

    async def text_to_video(self, prompt: str, params: dict) -> tuple[bytes, str]:
        result = await self._run_queue(params.get("model") or "fal-ai/ltx-video", {
            "prompt": prompt,
            **{k: v for k, v in params.items() if k in ("num_frames", "fps", "seed", "aspect_ratio")},
        }, timeout_s=int(params.get("timeout", 900)))
        url = self._extract_model_url(result)
        return await self._download(url), url.rsplit(".", 1)[-1].split("?")[0] or "mp4"


class VideoGenerator:
    def __init__(self, model_router: ModelRouter, asset_graph: AssetGraph, image_generator=None):
        self.router = model_router
        self.graph = asset_graph
        if image_generator is None:
            from core.creative.generators.image_generator import ImageGenerator
            image_generator = ImageGenerator(model_router, asset_graph)
        self.image_generator = image_generator

    # ------------------------------------------------------------------

    def _adapter_for(self, backend: str, capability: str):
        cfg = self.router.get_config().get("backends", {}).get(backend, {})
        if backend == "comfyui":
            adapter = self.image_generator._get_adapter("comfyui")
        elif backend == "fal_ai":
            adapter = FalVideoAdapter(api_key=cfg.get("api_key", ""))
        else:
            return None
        return adapter if hasattr(adapter, capability) else None

    async def _plan(self, task: CreativeTask, capability: str):
        model, backend = await self.router.select(task)
        if model and backend:
            adapter = self._adapter_for(backend, capability)
            if adapter is not None:
                task.params = self.router.apply_model(task.params, model, backend)
                return model, backend, adapter

        for name, cfg in self.router.get_config().get("backends", {}).items():
            if not cfg.get("enabled"):
                continue
            adapter = self._adapter_for(name, capability)
            if adapter is not None:
                return None, name, adapter
        return None, None, None

    def _store(self, data: bytes, ext: str, name: str, metadata: dict, sources: list) -> Asset:
        ext = (ext or "mp4").lower()
        if ext not in VIDEO_EXTS:
            ext = "mp4"
        asset = self.graph.create_asset(
            type_val=AssetType.VIDEO, name=name, source_assets=sources, metadata=metadata,
        )
        path = self.graph.save_file(asset.asset_id, f"video.{ext}", data)
        return self.graph.update_asset(asset.asset_id, files={"video": path})

    # ------------------------------------------------------------------

    async def text_to_video(self, prompt: str, priority: str = "balanced", **params) -> Asset:
        if not prompt or not str(prompt).strip():
            raise ValueError("Il prompt è obbligatorio per text_to_video")
        params = normalize_params(params)
        params.pop("prompt", None)

        task = CreativeTask('text_to_video', params, priority=priority)
        spec, backend, adapter = await self._plan(task, "text_to_video")
        if adapter is None:
            raise RuntimeError(NO_VIDEO_BACKEND)

        log.info(f"Text to video via {backend}" + (f" / {spec.id}" if spec else ""))
        data, ext = await adapter.text_to_video(prompt, task.params)
        return self._store(data, ext, f"video_{prompt[:20].strip()}", {
            "operation": "text_to_video", "prompt": prompt, "generator": backend,
            "model": spec.id if spec else None, "params": task.params,
        }, [])

    async def image_to_video(self, asset_id: str, prompt: str = "", priority: str = "balanced", **params) -> Asset:
        source = self.graph.get_asset(asset_id)
        if not source:
            raise ValueError(f"Asset non trovato: {asset_id}")
        path = source.files.get("image")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{source.name}' non ha un file immagine su disco")
        with open(path, "rb") as f:
            image_bytes = f.read()

        params = normalize_params(params)
        task = CreativeTask('image_to_video', params, priority=priority)
        spec, backend, adapter = await self._plan(task, "image_to_video")
        if adapter is None:
            raise RuntimeError(NO_VIDEO_BACKEND)

        log.info(f"Image to video di {asset_id} via {backend}" + (f" / {spec.id}" if spec else ""))
        data, ext = await adapter.image_to_video(image_bytes, prompt, task.params)
        return self._store(data, ext, f"{source.name}_video", {
            "operation": "image_to_video", "prompt": prompt, "generator": backend,
            "model": spec.id if spec else None, "params": task.params,
        }, [asset_id])
