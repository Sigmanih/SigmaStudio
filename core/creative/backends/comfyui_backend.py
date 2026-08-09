"""Backend ComfyUI: traduce il contratto Sigma nelle sue API HTTP/websocket."""

import asyncio
import json
import uuid

import aiohttp

from core.creative.backends.base import BackendJob, BackendUnavailable, GenerationBackend
from core.logger import get_logger

log = get_logger("comfyui_backend")

# Chiavi con cui i nodi di output dichiarano i file prodotti.
OUTPUT_KEYS = ("images", "gifs", "videos", "result", "meshes", "3d", "model_file", "audio")


class ComfyUIBackend(GenerationBackend):
    id = "comfyui"
    label = "ComfyUI"

    def __init__(self, base_url: str = "http://127.0.0.1:8188", config: dict = None):
        self.base_url = (base_url or "http://127.0.0.1:8188").rstrip("/")
        self.config = config or {}
        self.timeout_s = int(self.config.get("timeout", 600))
        self.client_id = str(uuid.uuid4())

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict = None, raw: bool = False):
        timeout = aiohttp.ClientTimeout(total=60)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}{path}", params=params) as resp:
                    if resp.status != 200:
                        return None
                    return await (resp.read() if raw else resp.json())
        except aiohttp.ClientError as e:
            raise BackendUnavailable(f"ComfyUI non raggiungibile: {e}")

    async def _post(self, path: str, payload: dict) -> dict:
        timeout = aiohttp.ClientTimeout(total=60)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{self.base_url}{path}", json=payload) as resp:
                    body = await resp.text()
                    if resp.status != 200:
                        raise RuntimeError(f"ComfyUI ha rifiutato la richiesta ({resp.status}): {body[:400]}")
                    return json.loads(body) if body else {}
        except aiohttp.ClientError as e:
            raise BackendUnavailable(f"ComfyUI non raggiungibile: {e}")

    # ------------------------------------------------------------------
    # Stato
    # ------------------------------------------------------------------

    async def is_available(self) -> bool:
        try:
            return await self._get("/system_stats") is not None
        except BackendUnavailable:
            return False

    async def get_system_stats(self) -> dict:
        stats = await self._get("/system_stats") or {}
        system = stats.get("system", {})
        devices = stats.get("devices", []) or []
        return {
            "backend": self.id,
            "version": system.get("comfyui_version", ""),
            "python": system.get("python_version", "").split(" ")[0],
            "torch": system.get("pytorch_version", ""),
            "ram_free_gb": round((system.get("ram_free") or 0) / 1024 ** 3, 1),
            "devices": [{
                "name": d.get("name", ""),
                "vram_total_gb": round((d.get("vram_total") or 0) / 1024 ** 3, 1),
                "vram_free_gb": round((d.get("vram_free") or 0) / 1024 ** 3, 1),
                "torch_vram_used_gb": round(
                    ((d.get("torch_vram_total") or 0) - (d.get("torch_vram_free") or 0)) / 1024 ** 3, 1),
            } for d in devices],
            "argv": system.get("argv", []),
        }

    @staticmethod
    def _options(node_info: dict, field: str) -> list:
        """Valori ammessi per un input: due schemi a seconda della versione."""
        for section in ("required", "optional"):
            spec = (node_info.get("input", {}).get(section) or {}).get(field)
            if not isinstance(spec, list) or not spec:
                continue
            if isinstance(spec[0], list):
                return [v for v in spec[0] if isinstance(v, str)]
            if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
                return [v for v in (spec[1].get("options") or []) if isinstance(v, str)]
        return []

    async def _object_info(self, class_type: str) -> dict:
        data = await self._get(f"/object_info/{class_type}")
        return (data or {}).get(class_type, {})

    async def discover_models(self) -> dict:
        classes = await asyncio.gather(*[
            self._object_info(c) for c in (
                "CheckpointLoaderSimple", "UNETLoader", "VAELoader", "DualCLIPLoader",
                "LoraLoader", "UpscaleModelLoader", "KSampler", "ControlNetLoader",
            )
        ], return_exceptions=True)
        classes = [c if isinstance(c, dict) else {} for c in classes]
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

    # ------------------------------------------------------------------
    # Esecuzione
    # ------------------------------------------------------------------

    async def get_queue(self) -> dict:
        data = await self._get("/queue") or {}
        running = data.get("queue_running", []) or []
        pending = data.get("queue_pending", []) or []
        return {
            "running": [q[1] for q in running if len(q) > 1],
            "pending": [q[1] for q in pending if len(q) > 1],
            "running_count": len(running),
            "pending_count": len(pending),
        }

    async def submit(self, payload: dict) -> str:
        workflow = payload.get("workflow", payload)
        data = await self._post("/prompt", {"prompt": workflow, "client_id": self.client_id})
        job_id = data.get("prompt_id")
        if not job_id:
            raise RuntimeError(f"ComfyUI non ha restituito un prompt_id: {data}")
        log.info(f"Job accodato su ComfyUI: {job_id}")
        return job_id

    async def get_job_status(self, job_id: str) -> BackendJob:
        history = (await self._get(f"/history/{job_id}") or {}).get(job_id, {})
        if history:
            status = (history.get("status") or {})
            if status.get("status_str") == "error":
                messages = status.get("messages") or []
                detail = next((json.dumps(m[1])[:300] for m in messages
                               if isinstance(m, list) and m and m[0] == "execution_error"), "")
                return BackendJob(job_id, "error", 100.0, error=detail or "Esecuzione fallita")
            if history.get("outputs"):
                return BackendJob(job_id, "done", 100.0, outputs=self._collect_outputs(history))

        queue = await self.get_queue()
        if any(q == job_id for q in queue["running"]):
            return BackendJob(job_id, "running", 50.0)
        if any(q == job_id for q in queue["pending"]):
            return BackendJob(job_id, "pending", 0.0)
        return BackendJob(job_id, "running" if not history else "done", 0.0 if not history else 100.0)

    async def cancel_job(self, job_id: str) -> bool:
        try:
            # Un job in coda si rimuove, uno in esecuzione si interrompe.
            await self._post("/queue", {"delete": [job_id]})
            queue = await self.get_queue()
            if job_id in queue["running"]:
                await self._post("/interrupt", {})
            return True
        except Exception as e:
            log.warning(f"Annullamento job {job_id} fallito: {e}")
            return False

    async def get_history(self, job_id: str) -> dict:
        return (await self._get(f"/history/{job_id}") or {}).get(job_id, {})

    @staticmethod
    def _collect_outputs(history: dict) -> list:
        outputs = []
        for node_id, node_output in (history.get("outputs") or {}).items():
            for key in OUTPUT_KEYS:
                for entry in (node_output.get(key) or []):
                    if isinstance(entry, dict) and entry.get("filename"):
                        outputs.append({
                            "filename": entry["filename"],
                            "subfolder": entry.get("subfolder", ""),
                            "kind": entry.get("type", "output"),
                            "node": node_id,
                        })
        return outputs

    async def get_outputs(self, job_id: str) -> list[tuple[bytes, str]]:
        history = await self.get_history(job_id)
        files = []
        for meta in self._collect_outputs(history):
            data = await self._get("/view", params={
                "filename": meta["filename"], "subfolder": meta["subfolder"], "type": meta["kind"],
            }, raw=True)
            if data:
                files.append((data, meta["filename"]))
        return files

    # ------------------------------------------------------------------

    async def upload_image(self, image_bytes: bytes, filename: str = None) -> str:
        """Carica un'immagine nella cartella input e ritorna il nome per LoadImage."""
        filename = filename or f"sigma_{uuid.uuid4().hex[:12]}.png"
        form = aiohttp.FormData()
        form.add_field("image", image_bytes, filename=filename, content_type="image/png")
        form.add_field("overwrite", "true")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(f"{self.base_url}/upload/image", data=form) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"Upload immagine fallito ({resp.status})")
                    data = await resp.json()
                    name = data.get("name", filename)
                    return f"{data['subfolder']}/{name}" if data.get("subfolder") else name
        except aiohttp.ClientError as e:
            raise BackendUnavailable(f"ComfyUI non raggiungibile: {e}")

    async def run(self, payload: dict, progress_cb=None, timeout_s: int = None) -> tuple[bytes, str]:
        """Esecuzione con attesa via websocket, polling come rete di sicurezza."""
        timeout_s = timeout_s or self.timeout_s
        job_id = await self.submit(payload)

        if not await self._wait_ws(job_id, progress_cb, timeout_s):
            await self._wait_poll(job_id, progress_cb, timeout_s)

        outputs = await self.get_outputs(job_id)
        if not outputs:
            raise RuntimeError("ComfyUI non ha prodotto alcun file")
        return outputs[0]

    async def _wait_ws(self, job_id: str, progress_cb, timeout_s: int) -> bool:
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_s)) as session:
                async with session.ws_connect(f"{ws_url}/ws?clientId={self.client_id}") as ws:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        payload = json.loads(msg.data)
                        data = payload.get("data", {})
                        kind = payload.get("type")

                        if kind == "progress" and progress_cb:
                            total = data.get("max", 1) or 1
                            progress_cb({"job_id": job_id, "status": "running",
                                         "progress": round(data.get("value", 0) / total * 100, 1)})
                        elif kind == "executing" and data.get("node") is None \
                                and data.get("prompt_id") == job_id:
                            return True
                        elif kind == "execution_error" and data.get("prompt_id") == job_id:
                            raise RuntimeError(f"ComfyUI: {data.get('exception_message', 'errore di esecuzione')}")
        except aiohttp.ClientError as e:
            log.debug(f"Websocket non disponibile ({e}): passo al polling")
            return False
        return False

    async def _wait_poll(self, job_id: str, progress_cb, timeout_s: int) -> None:
        waited, delay = 0.0, 1.0
        while waited < timeout_s:
            job = await self.get_job_status(job_id)
            if progress_cb:
                progress_cb(job.to_dict())
            if job.status == "error":
                raise RuntimeError(job.error)
            if job.status == "done":
                return
            await asyncio.sleep(delay)
            waited += delay
            delay = min(delay * 1.3, 5.0)
        raise TimeoutError(f"ComfyUI: timeout dopo {timeout_s}s")
