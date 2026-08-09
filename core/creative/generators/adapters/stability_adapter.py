import aiohttp
from core.logger import get_logger

log = get_logger("stability_adapter")

class StabilityAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "image/*"
        }

    async def text_to_image(self, prompt: str, params: dict) -> bytes:
        payload = aiohttp.FormData()
        payload.add_field('prompt', prompt)
        payload.add_field('output_format', 'png')
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post("https://api.stability.ai/v2beta/stable-image/generate/sd3", data=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Stability Error: {await resp.text()}")
                
                return await resp.read()
