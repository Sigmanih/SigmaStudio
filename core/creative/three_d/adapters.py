"""Adapter per la ricostruzione 3D (immagine → mesh).

Sigma non esegue i modelli 3D in proprio: instrada verso i servizi configurati e
riporta i bytes della mesh. Ogni adapter espone `image_to_3d(image_bytes, params)`
e, quando il servizio lo supporta, `multiview_to_3d(images, params)`.
"""

import asyncio
import base64

import aiohttp

from core.logger import get_logger

log = get_logger("creative_3d_adapters")


class StabilityFast3DAdapter:
    """Stability AI — Stable Fast 3D: singola immagine → GLB."""

    name = "stability"
    endpoint = "https://api.stability.ai/v2beta/3d/stable-fast-3d"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def image_to_3d(self, image_bytes: bytes, params: dict) -> tuple[bytes, str]:
        if not self.api_key:
            raise RuntimeError("API key Stability mancante")

        form = aiohttp.FormData()
        form.add_field('image', image_bytes, filename='input.png', content_type='image/png')
        form.add_field('texture_resolution', str(params.get('texture_resolution', 1024)))
        if params.get('foreground_ratio'):
            form.add_field('foreground_ratio', str(params['foreground_ratio']))

        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.endpoint, data=form, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Stability 3D error {resp.status}: {await resp.text()}")
                return await resp.read(), "glb"


class Fal3DAdapter:
    """fal.ai — modelli image-to-3d (TripoSR, Trellis, ...) via queue API."""

    name = "fal_ai"

    def __init__(self, api_key: str, model: str = "fal-ai/triposr", multiview_model: str = "fal-ai/trellis/multi"):
        self.api_key = api_key
        self.model = model
        self.multiview_model = multiview_model

    @property
    def _headers(self):
        return {"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _data_uri(image_bytes: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")

    async def _run_queue(self, model: str, payload: dict, timeout_s: int = 600) -> dict:
        """Accoda il job e attende il completamento (poll incrementale)."""
        if not self.api_key:
            raise RuntimeError("API key fal.ai mancante")

        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with aiohttp.ClientSession(headers=self._headers, timeout=timeout) as session:
            async with session.post(f"https://queue.fal.run/{model}", json=payload) as resp:
                if resp.status not in (200, 201, 202):
                    raise RuntimeError(f"fal.ai error {resp.status}: {await resp.text()}")
                queued = await resp.json()

            request_id = queued.get("request_id")
            if not request_id:
                return queued  # risposta sincrona

            status_url = f"https://queue.fal.run/{model}/requests/{request_id}/status"
            result_url = f"https://queue.fal.run/{model}/requests/{request_id}"
            delay, waited = 2, 0
            while waited < timeout_s:
                await asyncio.sleep(delay)
                waited += delay
                delay = min(delay * 1.5, 15)
                async with session.get(status_url) as sresp:
                    status = (await sresp.json()).get("status")
                if status == "COMPLETED":
                    async with session.get(result_url) as rresp:
                        return await rresp.json()
                if status in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"fal.ai job {status.lower()}")
            raise TimeoutError("fal.ai: timeout in attesa del modello 3D")

    @staticmethod
    def _extract_model_url(result: dict) -> str:
        for key in ("model_mesh", "model_glb", "mesh", "model"):
            node = result.get(key)
            if isinstance(node, dict) and node.get("url"):
                return node["url"]
            if isinstance(node, str) and node.startswith("http"):
                return node
        raise RuntimeError(f"Risposta fal.ai priva di mesh: {list(result.keys())}")

    async def _download(self, url: str) -> bytes:
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Download mesh fallito ({resp.status})")
                return await resp.read()

    async def image_to_3d(self, image_bytes: bytes, params: dict) -> tuple[bytes, str]:
        result = await self._run_queue(params.get("model") or self.model, {
            "image_url": self._data_uri(image_bytes),
            **{k: v for k, v in params.items() if k in ("do_remove_background", "foreground_ratio", "mc_resolution")}
        })
        url = self._extract_model_url(result)
        return await self._download(url), url.rsplit(".", 1)[-1].split("?")[0] or "glb"

    async def multiview_to_3d(self, images: list[bytes], params: dict) -> tuple[bytes, str]:
        result = await self._run_queue(params.get("model") or self.multiview_model, {
            "image_urls": [self._data_uri(b) for b in images],
        })
        url = self._extract_model_url(result)
        return await self._download(url), url.rsplit(".", 1)[-1].split("?")[0] or "glb"


def build_3d_adapter(backend_name: str, cfg: dict):
    """Istanzia l'adapter 3D per il backend richiesto (None se non supportato)."""
    if backend_name == "stability":
        return StabilityFast3DAdapter(api_key=cfg.get("api_key", ""))
    if backend_name == "fal_ai":
        return Fal3DAdapter(
            api_key=cfg.get("api_key", ""),
            model=cfg.get("model_3d", "fal-ai/triposr"),
            multiview_model=cfg.get("model_3d_multiview", "fal-ai/trellis/multi"),
        )
    return None
