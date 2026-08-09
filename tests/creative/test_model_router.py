import pytest
import asyncio
from core.creative.model_router import ModelRouter, CreativeTask

@pytest.fixture
def config():
    return {
        "creative": {
            "backends": {
                "comfyui": {"enabled": True, "url": "http://localhost:8188"},
                "sd_webui": {"enabled": True, "url": "http://localhost:7860"},
                "fal_ai": {"enabled": True, "api_key": "test_key"},
                "replicate": {"enabled": False},
                "blender": {"enabled": True, "path": "/fake/path/blender.exe"}
            }
        }
    }

@pytest.fixture
def router(config):
    return ModelRouter(config)

def test_get_available_backends(router, monkeypatch):
    async def mock_ping_comfy(url): return True
    async def mock_ping_sd(url): return False
    monkeypatch.setattr(router, "_ping_comfyui", mock_ping_comfy)
    monkeypatch.setattr(router, "_ping_sd_webui", mock_ping_sd)
    
    backends = asyncio.run(router.get_available_backends())
    
    comfy = next(b for b in backends if b.name == "comfyui")
    assert comfy.available == True
    assert "text_to_image" in comfy.capabilities
    
    sd = next(b for b in backends if b.name == "sd_webui")
    assert sd.available == False
    
    fal = next(b for b in backends if b.name == "fal_ai")
    assert fal.available == True
    
    rep = next(b for b in backends if b.name == "replicate")
    assert rep.available == False

    poll = next(b for b in backends if b.name == "pollinations")
    assert poll.available == True

def test_route(router, monkeypatch):
    async def mock_ping_comfy(url): return True
    monkeypatch.setattr(router, "_ping_comfyui", mock_ping_comfy)
    
    task = CreativeTask("text_to_image", {})
    backend = asyncio.run(router.route(task))
    # The order of keys is not guaranteed, but comfyui should handle it
    assert backend in ["comfyui", "fal_ai"]
    
    # Force no backends available
    router.backends["comfyui"]["enabled"] = False
    router.backends["fal_ai"]["enabled"] = False
    
    backend_fallback = asyncio.run(router.route(task))
    assert backend_fallback == "pollinations"
