import aiohttp
import base64
from core.logger import get_logger

log = get_logger("sd_webui_adapter")

class SDWebUIAdapter:
    def __init__(self, base_url='http://127.0.0.1:7860'):
        self.base_url = base_url

    async def text_to_image(self, prompt: str, params: dict) -> bytes:
        payload = {
            "prompt": prompt,
            "negative_prompt": params.get("negative_prompt", ""),
            "steps": params.get("steps", 30),
            "cfg_scale": params.get("cfg_scale", 7.0),
            "width": params.get("width", 1024),
            "height": params.get("height", 1024),
            "sampler_name": params.get("sampler", "Euler a"),
            "seed": params.get("seed", -1)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"SD WebUI Error: {await resp.text()}")
                
                data = await resp.json()
                img_b64 = data["images"][0]
                return base64.b64decode(img_b64)

    async def img_to_image(self, image_bytes: bytes, prompt: str, params: dict) -> bytes:
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            "init_images": [img_b64],
            "prompt": prompt,
            "negative_prompt": params.get("negative_prompt", ""),
            "steps": params.get("steps", 30),
            "cfg_scale": params.get("cfg_scale", 7.0),
            "denoising_strength": params.get("strength", 0.7),
            "width": params.get("width", 1024),
            "height": params.get("height", 1024),
            "sampler_name": params.get("sampler", "Euler a")
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/sdapi/v1/img2img", json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"SD WebUI Error: {await resp.text()}")
                
                data = await resp.json()
                return base64.b64decode(data["images"][0])

    async def inpaint(self, image_bytes: bytes, mask_bytes: bytes, prompt: str, params: dict) -> bytes:
        """Inpaint nativo via img2img con maschera (bianco = area da rigenerare)."""
        payload = {
            "init_images": [base64.b64encode(image_bytes).decode('utf-8')],
            "mask": base64.b64encode(mask_bytes).decode('utf-8'),
            "prompt": prompt,
            "negative_prompt": params.get("negative_prompt", ""),
            "steps": params.get("steps", 30),
            "cfg_scale": params.get("cfg_scale", 7.0),
            "denoising_strength": params.get("strength", 0.75),
            "inpainting_fill": params.get("inpainting_fill", 1),
            "inpaint_full_res": params.get("inpaint_full_res", True),
            "mask_blur": params.get("mask_blur", 4),
            "sampler_name": params.get("sampler", "Euler a"),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/sdapi/v1/img2img", json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"SD WebUI Error: {await resp.text()}")

                data = await resp.json()
                return base64.b64decode(data["images"][0])

    async def upscale(self, image_bytes: bytes, params: dict) -> bytes:
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            "resize_mode": 0,
            "show_extras_results": True,
            "gfpgan_visibility": 0,
            "codeformer_visibility": 0,
            "upscaling_resize": params.get("scale", 2),
            "upscaler_1": params.get("model", "R-ESRGAN 4x+"),
            "image": img_b64
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/sdapi/v1/extra-single-image", json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"SD WebUI Error: {await resp.text()}")
                
                data = await resp.json()
                return base64.b64decode(data["image"])

    async def get_models(self) -> list:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/sdapi/v1/sd-models") as resp:
                data = await resp.json()
                return [model["title"] for model in data]
