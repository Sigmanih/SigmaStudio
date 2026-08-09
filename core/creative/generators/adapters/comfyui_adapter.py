"""Adapter ComfyUI: traduce capability creative in workflow eseguibili.

Tre livelli separati, ognuno con una responsabilità sola:

    ImageGenerator / ModelGenerator3D / ...   « cosa voglio ottenere »
                    ↓
    ComfyUIAdapter (questo file)              « quale workflow e con quali input »
                    ↓
    WorkflowRegistry                          « il grafo, che sta su disco »
                    ↓
    ComfyUIBackend                            « il protocollo del motore »

L'adapter non conosce né le API di ComfyUI né la forma dei grafi: chiede al
registro un workflow risolto e lo consegna al backend.
"""

from core.creative.backends.comfyui_backend import ComfyUIBackend
from core.creative.model_state import runtime_tracker
from core.creative.workflow_registry import registry as workflow_registry
from core.logger import get_logger

from .comfy_workflows import DEFAULT_CHECKPOINTS, WorkflowNotAvailable, list_workflows

log = get_logger("comfyui_adapter")

# Workflow usato quando la capability non ne indica uno esplicito.
DEFAULT_WORKFLOWS = {
    "text_to_image": "sdxl_txt2img",
    "img_to_image": "sdxl_img2img",
    "inpaint": "sdxl_inpaint",
    "instruct_edit": "flux_kontext",
    "upscale": "esrgan_upscale",
    "segment": "sam2_segment",
    "image_to_3d": "hunyuan3d_image_to_3d",
    "image_to_video": "ltx_image_to_video",
    "text_to_video": "hunyuan_text_to_video",
}


class ComfyUIAdapter:
    def __init__(self, base_url='http://127.0.0.1:8188', config: dict = None):
        self.config = config or {}
        self.backend = ComfyUIBackend(base_url=base_url, config=self.config)
        self.checkpoints = {**DEFAULT_CHECKPOINTS, **(self.config.get("checkpoints") or {})}

    @property
    def base_url(self) -> str:
        return self.backend.base_url

    # ------------------------------------------------------------------
    # Preparazione ed esecuzione
    # ------------------------------------------------------------------

    def _resolve(self, capability: str, params: dict, **extra) -> tuple[dict, str]:
        """Grafo pronto per il backend + nome del checkpoint richiesto."""
        workflow_id = params.get("workflow") or DEFAULT_WORKFLOWS.get(capability)
        if not workflow_id:
            raise WorkflowNotAvailable(f"Nessun workflow associato alla capability '{capability}'")

        family = params.get("family", "sdxl")
        ckpt = params.get("ckpt") or self.checkpoints.get(family, DEFAULT_CHECKPOINTS["sdxl"])

        values = {
            **params,
            "ckpt": ckpt,
            "upscale_model": params.get("upscale_model", self.checkpoints.get("upscaler", "")),
            **extra,
        }
        return workflow_registry.resolve(workflow_id, values), ckpt

    async def run_workflow(self, graph: dict, ckpt: str = "", progress_cb=None) -> bytes:
        """Esegue il grafo tenendo traccia di cosa il backend sta caricando."""
        runtime_tracker.mark_submitted(self.backend.id, [ckpt])
        try:
            data, _filename = await self.backend.run({"workflow": graph}, progress_cb=progress_cb)
            return data
        finally:
            runtime_tracker.mark_finished(self.backend.id, [ckpt])

    async def _execute(self, capability: str, params: dict, **extra) -> bytes:
        graph, ckpt = self._resolve(capability, params, **extra)
        return await self.run_workflow(graph, ckpt)

    async def upload_image(self, image_bytes: bytes, filename: str = None) -> str:
        return await self.backend.upload_image(image_bytes, filename)

    # ------------------------------------------------------------------
    # Capability
    # ------------------------------------------------------------------

    async def text_to_image(self, prompt: str, params: dict) -> bytes:
        return await self._execute("text_to_image", params, prompt=prompt)

    async def img_to_image(self, image_bytes: bytes, prompt: str, params: dict) -> bytes:
        name = await self.upload_image(image_bytes)
        return await self._execute("img_to_image", params, prompt=prompt, input_image=name)

    async def inpaint(self, image_bytes: bytes, mask_bytes: bytes, prompt: str, params: dict) -> bytes:
        image_name = await self.upload_image(image_bytes)
        mask_name = await self.upload_image(mask_bytes)
        return await self._execute("inpaint", params, prompt=prompt,
                                   input_image=image_name, mask_image=mask_name)

    async def instruct_edit(self, image_bytes: bytes, instruction: str, params: dict) -> bytes:
        name = await self.upload_image(image_bytes)
        return await self._execute("instruct_edit", params, prompt=instruction,
                                   instruction=instruction, input_image=name)

    async def upscale(self, image_bytes: bytes, params: dict) -> bytes:
        name = await self.upload_image(image_bytes)
        return await self._execute("upscale", params, input_image=name)

    async def segment(self, image_bytes: bytes, params: dict) -> bytes:
        name = await self.upload_image(image_bytes)
        return await self._execute("segment", params, input_image=name,
                                   prompt=params.get("prompt", ""))

    async def image_to_3d(self, image_bytes: bytes, params: dict) -> tuple[bytes, str]:
        name = await self.upload_image(image_bytes)
        data = await self._execute("image_to_3d", params, input_image=name)
        return data, params.get("format", "glb")

    async def image_to_video(self, image_bytes: bytes, prompt: str, params: dict) -> tuple[bytes, str]:
        name = await self.upload_image(image_bytes)
        data = await self._execute("image_to_video", params, prompt=prompt, input_image=name)
        return data, params.get("format", "mp4")

    async def text_to_video(self, prompt: str, params: dict) -> tuple[bytes, str]:
        data = await self._execute("text_to_video", params, prompt=prompt)
        return data, params.get("format", "mp4")

    # ------------------------------------------------------------------
    # Introspezione (delegata al backend)
    # ------------------------------------------------------------------

    async def discover(self) -> dict:
        return await self.backend.discover_models()

    async def get_models(self) -> list:
        return (await self.backend.discover_models()).get("checkpoints", [])

    async def get_samplers(self) -> list:
        return (await self.backend.discover_models()).get("samplers", [])

    async def get_queue(self) -> dict:
        return await self.backend.get_queue()

    @staticmethod
    def _options(node_info: dict, field: str) -> list:
        """Mantenuto per compatibilità: la logica vive nel backend."""
        return ComfyUIBackend._options(node_info, field)

    @staticmethod
    def workflow_status() -> dict:
        return list_workflows()
