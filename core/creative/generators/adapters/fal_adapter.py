import aiohttp
from core.logger import get_logger

log = get_logger("fal_adapter")

class FalAIAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json"
        }

    async def text_to_image(self, prompt: str, params: dict) -> bytes:
        # Usa il modello fal-ai/flux/schnell di default
        model = params.get("model", "fal-ai/flux/schnell")
        payload = {
            "prompt": prompt,
            "image_size": f"{params.get('width', 1024)}x{params.get('height', 1024)}",
            "num_inference_steps": params.get("steps", 4),
            "guidance_scale": params.get("cfg_scale", 3.5),
            "num_images": 1
        }
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(f"https://queue.fal.run/{model}", json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Fal.ai Error: {await resp.text()}")
                
                data = await resp.json()
                image_url = data["images"][0]["url"]
                
                # Scarica l'immagine
                async with session.get(image_url) as img_resp:
                    return await img_resp.read()

    async def img_to_image(self, image_bytes: bytes, prompt: str, params: dict) -> bytes:
        raise NotImplementedError("Fal.ai img2img not fully implemented here")
