import asyncio
import io
import urllib.parse
import aiohttp
from core.logger import get_logger

log = get_logger("creative_pollinations_adapter")

class PollinationsAdapter:
    """Zero-setup public text-to-image generator powered by Pollinations AI.

    È il backend di fallback: non richiede né GPU né API key. Le operazioni che
    l'endpoint pubblico non espone (upscale) sono risolte localmente con Pillow,
    così la pipeline resta percorribile anche senza backend configurati.
    """

    def __init__(self, base_url: str = "https://image.pollinations.ai"):
        self.base_url = base_url

    async def text_to_image(self, prompt: str, params: dict) -> bytes:
        width = params.get("width", 1024)
        height = params.get("height", 1024)
        seed = params.get("seed", -1)

        negative = params.get("negative_prompt")
        if negative:
            prompt = f"{prompt} | avoid: {negative}"

        encoded_prompt = urllib.parse.quote(prompt)
        url = f"{self.base_url}/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
        if seed is not None and seed != -1:
            url += f"&seed={seed}"
            
        log.info(f"Generating image via Pollinations AI: {url}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    raise RuntimeError(f"Pollinations AI HTTP error {resp.status}")

    async def img_to_image(self, image_bytes: bytes, prompt: str, params: dict) -> bytes:
        # L'endpoint pubblico non accetta immagini di input: la sorgente serve solo
        # a ereditare le dimensioni, il risultato è guidato dal solo prompt.
        log.warning("Pollinations non supporta img2img reale: rigenerazione dal solo prompt")
        params = dict(params)
        params.setdefault("width", 1024)
        params.setdefault("height", 1024)
        try:
            from PIL import Image
            with Image.open(io.BytesIO(image_bytes)) as img:
                params["width"], params["height"] = img.size
        except Exception:
            pass
        return await self.text_to_image(prompt, params)

    async def upscale(self, image_bytes: bytes, params: dict) -> bytes:
        """Upscale locale Lanczos — nessun dettaglio inventato, solo risoluzione."""
        scale = float(params.get("scale", 2) or 2)
        return await asyncio.to_thread(self._resize_sync, image_bytes, scale)

    @staticmethod
    def _resize_sync(image_bytes: bytes, scale: float) -> bytes:
        try:
            from PIL import Image
        except ImportError as e:
            raise RuntimeError("Upscale locale non disponibile: Pillow non installato") from e

        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGBA")
            target = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            resized = img.resize(target, Image.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, "PNG")
            return buf.getvalue()
