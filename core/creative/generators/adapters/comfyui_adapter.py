"""Adapter ComfyUI — il percorso GPU locale di Sigma.

Accoda un workflow in formato API, attende il completamento (websocket quando
disponibile, altrimenti polling della history) e restituisce i byte del primo
output. Supporta immagini, mesh e video perché tutti finiscono nella history
come file scaricabili da `/view`.
"""

import asyncio
import json
import uuid

import aiohttp

from core.logger import get_logger
from .comfy_workflows import DEFAULT_CHECKPOINTS, build, list_workflows

log = get_logger("comfyui_adapter")

# Estensioni prodotte dai nodi di output, in ordine di preferenza per tipo.
IMAGE_KEYS = ("images", "gifs", "ui_images")
FILE_KEYS = ("images", "gifs", "videos", "result", "meshes", "3d", "model_file")


class ComfyUIAdapter:
    def __init__(self, base_url='http://127.0.0.1:8188', config: dict = None):
        self.base_url = base_url.rstrip('/')
        self.config = config or {}
        self.checkpoints = {**DEFAULT_CHECKPOINTS, **(self.config.get("checkpoints") or {})}
        self.timeout_s = int(self.config.get("timeout", 600))
        self.client_id = str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Primitive HTTP
    # ------------------------------------------------------------------

    async def _post_prompt(self, workflow: dict) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/prompt",
                                    json={"prompt": workflow, "client_id": self.client_id}) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"ComfyUI ha rifiutato il workflow ({resp.status}): {body[:400]}")
                return json.loads(body)["prompt_id"]

    async def _history(self, prompt_id: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/history/{prompt_id}") as resp:
                if resp.status != 200:
                    return {}
                return (await resp.json()).get(prompt_id, {})

    async def _view(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        params = {"filename": filename, "subfolder": subfolder or "", "type": folder_type or "output"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/view", params=params) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Download output ComfyUI fallito ({resp.status})")
                return await resp.read()

    async def upload_image(self, image_bytes: bytes, filename: str = None) -> str:
        """Carica un'immagine nella cartella input e ritorna il nome da usare in LoadImage."""
        filename = filename or f"sigma_{uuid.uuid4().hex[:12]}.png"
        form = aiohttp.FormData()
        form.add_field('image', image_bytes, filename=filename, content_type='image/png')
        form.add_field('overwrite', 'true')
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/upload/image", data=form) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Upload immagine su ComfyUI fallito ({resp.status})")
                data = await resp.json()
                name = data.get("name", filename)
                return f"{data['subfolder']}/{name}" if data.get("subfolder") else name

    # ------------------------------------------------------------------
    # Esecuzione
    # ------------------------------------------------------------------

    async def _wait_ws(self, prompt_id: str, progress_cb=None) -> bool:
        """Attende la fine dell'esecuzione via websocket. False se il ws non è usabile."""
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.ws_connect(f"{ws_url}/ws?clientId={self.client_id}") as ws:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        payload = json.loads(msg.data)
                        data = payload.get("data", {})
                        if payload.get("type") == "progress" and progress_cb:
                            value, total = data.get("value", 0), data.get("max", 1) or 1
                            progress_cb(int(value / total * 100))
                        # `node: None` sul nostro prompt = esecuzione conclusa
                        if payload.get("type") == "executing" and data.get("node") is None \
                                and data.get("prompt_id") == prompt_id:
                            return True
                        if payload.get("type") == "execution_error" and data.get("prompt_id") == prompt_id:
                            raise RuntimeError(f"ComfyUI: {data.get('exception_message', 'errore di esecuzione')}")
        except aiohttp.ClientError as e:
            log.debug(f"Websocket ComfyUI non disponibile ({e}): passo al polling")
            return False
        return False

    async def _wait_poll(self, prompt_id: str) -> None:
        waited, delay = 0.0, 1.0
        while waited < self.timeout_s:
            history = await self._history(prompt_id)
            if history.get("outputs"):
                return
            status = (history.get("status") or {}).get("status_str")
            if status == "error":
                raise RuntimeError("ComfyUI: esecuzione fallita (vedi log di ComfyUI)")
            await asyncio.sleep(delay)
            waited += delay
            delay = min(delay * 1.3, 5.0)
        raise TimeoutError(f"ComfyUI: timeout dopo {self.timeout_s}s")

    async def run_workflow(self, workflow: dict, progress_cb=None) -> bytes:
        """Esegue il workflow e ritorna i byte del primo file prodotto."""
        prompt_id = await self._post_prompt(workflow)
        log.info(f"Workflow accodato su ComfyUI: {prompt_id}")

        if not await self._wait_ws(prompt_id, progress_cb):
            await self._wait_poll(prompt_id)

        history = await self._history(prompt_id)
        outputs = history.get("outputs") or {}
        if not outputs:
            await self._wait_poll(prompt_id)
            outputs = (await self._history(prompt_id)).get("outputs") or {}

        for node_output in outputs.values():
            for key in FILE_KEYS:
                entries = node_output.get(key)
                if not entries:
                    continue
                entry = entries[0]
                if isinstance(entry, dict) and entry.get("filename"):
                    return await self._view(entry["filename"], entry.get("subfolder"), entry.get("type"))

        raise RuntimeError(f"Nessun file negli output di ComfyUI (nodi: {list(outputs)})")

    def _params(self, params: dict, family: str = "sdxl", **extra) -> dict:
        return {**params, "ckpt": params.get("ckpt") or self.checkpoints.get(family, DEFAULT_CHECKPOINTS["sdxl"]), **extra}

    # ------------------------------------------------------------------
    # Capability
    # ------------------------------------------------------------------

    async def text_to_image(self, prompt: str, params: dict) -> bytes:
        workflow_name = params.get("workflow") or "sdxl_txt2img"
        family = params.get("family", "sdxl")
        return await self.run_workflow(build(workflow_name, self._params(params, family, prompt=prompt)))

    async def img_to_image(self, image_bytes: bytes, prompt: str, params: dict) -> bytes:
        name = await self.upload_image(image_bytes)
        workflow_name = params.get("workflow") or "sdxl_img2img"
        family = params.get("family", "sdxl")
        return await self.run_workflow(build(workflow_name, self._params(
            params, family, prompt=prompt, input_image=name)))

    async def inpaint(self, image_bytes: bytes, mask_bytes: bytes, prompt: str, params: dict) -> bytes:
        image_name = await self.upload_image(image_bytes)
        mask_name = await self.upload_image(mask_bytes)
        workflow_name = params.get("workflow") or "sdxl_inpaint"
        family = params.get("family", "sdxl")
        return await self.run_workflow(build(workflow_name, self._params(
            params, family, prompt=prompt, input_image=image_name, mask_image=mask_name)))

    async def instruct_edit(self, image_bytes: bytes, instruction: str, params: dict) -> bytes:
        """Editing guidato da istruzione (Qwen-Image-Edit, FLUX Kontext)."""
        name = await self.upload_image(image_bytes)
        workflow_name = params.get("workflow") or "flux_kontext"
        family = params.get("family", "flux")
        return await self.run_workflow(build(workflow_name, self._params(
            params, family, prompt=instruction, instruction=instruction, input_image=name)))

    async def upscale(self, image_bytes: bytes, params: dict) -> bytes:
        name = await self.upload_image(image_bytes)
        workflow_name = params.get("workflow") or "esrgan_upscale"
        return await self.run_workflow(build(workflow_name, self._params(
            params, "sdxl", input_image=name,
            upscale_model=params.get("upscale_model", self.checkpoints["upscaler"]))))

    async def segment(self, image_bytes: bytes, params: dict) -> bytes:
        """Ritorna la maschera prodotta da SAM 2 (PNG)."""
        name = await self.upload_image(image_bytes)
        return await self.run_workflow(build(params.get("workflow") or "sam2_segment", self._params(
            params, "sdxl", input_image=name, prompt=params.get("prompt", ""))))

    async def image_to_3d(self, image_bytes: bytes, params: dict) -> tuple[bytes, str]:
        name = await self.upload_image(image_bytes)
        workflow_name = params.get("workflow") or "hunyuan3d_image_to_3d"
        data = await self.run_workflow(build(workflow_name, self._params(params, "sdxl", input_image=name)))
        return data, params.get("format", "glb")

    async def image_to_video(self, image_bytes: bytes, prompt: str, params: dict) -> tuple[bytes, str]:
        name = await self.upload_image(image_bytes)
        workflow_name = params.get("workflow") or "ltx_image_to_video"
        data = await self.run_workflow(build(workflow_name, self._params(
            params, "sdxl", prompt=prompt, input_image=name)))
        return data, params.get("format", "mp4")

    async def text_to_video(self, prompt: str, params: dict) -> tuple[bytes, str]:
        workflow_name = params.get("workflow") or "hunyuan_text_to_video"
        data = await self.run_workflow(build(workflow_name, self._params(params, "sdxl", prompt=prompt)))
        return data, params.get("format", "mp4")

    # ------------------------------------------------------------------
    # Introspezione
    # ------------------------------------------------------------------

    async def _object_info(self, session, class_type: str) -> dict:
        try:
            async with session.get(f"{self.base_url}/object_info/{class_type}") as resp:
                if resp.status != 200:
                    return {}
                return (await resp.json()).get(class_type, {})
        except Exception:
            return {}

    @staticmethod
    def _options(node_info: dict, field: str) -> list:
        """Valori ammessi per un input di un nodo, cioè i file presenti su disco.

        ComfyUI espone due schemi a seconda della versione:
          - storico:  `[[opzione, ...], {...}]`
          - 0.31+:    `["COMBO", {"options": [opzione, ...]}]`
        Leggerne uno solo significa non vedere i modelli installati.
        """
        for section in ("required", "optional"):
            spec = (node_info.get("input", {}).get(section) or {}).get(field)
            if not isinstance(spec, list) or not spec:
                continue
            if isinstance(spec[0], list):
                return [v for v in spec[0] if isinstance(v, str)]
            if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
                return [v for v in (spec[1].get("options") or []) if isinstance(v, str)]
        return []

    async def discover(self) -> dict:
        """Inventario di ciò che questa installazione ComfyUI può davvero caricare."""
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            classes = await asyncio.gather(*[
                self._object_info(session, c) for c in (
                    "CheckpointLoaderSimple", "UNETLoader", "VAELoader", "DualCLIPLoader",
                    "LoraLoader", "UpscaleModelLoader", "KSampler", "ControlNetLoader",
                )
            ])

        ckpt, unet, vae, clip, lora, upscaler, ksampler, controlnet = classes
        return {
            "checkpoints": self._options(ckpt, "ckpt_name"),
            "unets": self._options(unet, "unet_name"),
            "vaes": self._options(vae, "vae_name"),
            "clips": self._options(clip, "clip_name1"),
            "loras": self._options(lora, "lora_name"),
            "upscale_models": self._options(upscaler, "model_name"),
            "samplers": self._options(ksampler, "sampler_name"),
            "schedulers": self._options(ksampler, "scheduler"),
            "controlnets": self._options(controlnet, "control_net_name"),
        }

    async def get_models(self) -> list:
        async with aiohttp.ClientSession() as session:
            return self._options(await self._object_info(session, "CheckpointLoaderSimple"), "ckpt_name")

    async def get_samplers(self) -> list:
        async with aiohttp.ClientSession() as session:
            return self._options(await self._object_info(session, "KSampler"), "sampler_name")

    @staticmethod
    def workflow_status() -> dict:
        return list_workflows()
