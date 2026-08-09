import io

import pytest

from core.creative.asset_graph import AssetGraph
from core.creative.model_router import ModelRouter
from core.creative.three_d.blender_bridge import BlenderBridge


def make_png(size=(64, 64), color=(120, 60, 200)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


class FakeImageAdapter:
    """Adapter deterministico: nessuna chiamata di rete nei test."""

    def __init__(self, payload: bytes = None):
        self.payload = payload or make_png()
        self.calls = []

    async def text_to_image(self, prompt, params):
        self.calls.append(("text_to_image", prompt, params))
        return self.payload

    async def img_to_image(self, image_bytes, prompt, params):
        self.calls.append(("img_to_image", prompt, params))
        return self.payload

    async def upscale(self, image_bytes, params):
        self.calls.append(("upscale", params))
        from core.creative.generators.adapters.pollinations_adapter import PollinationsAdapter
        return await PollinationsAdapter().upscale(image_bytes, params)


@pytest.fixture
def graph(tmp_path):
    ag = AssetGraph(db_path=str(tmp_path / "creative.db"))
    ag.assets_dir = tmp_path / "assets"
    ag.assets_dir.mkdir(parents=True, exist_ok=True)
    return ag


@pytest.fixture
def router():
    return ModelRouter({"creative": {"backends": {}}})


@pytest.fixture
def fake_adapter():
    return FakeImageAdapter()


@pytest.fixture
def generator(graph, router, fake_adapter):
    from core.creative.generators.image_generator import ImageGenerator
    gen = ImageGenerator(router, graph)
    gen._get_adapter = lambda name: fake_adapter
    return gen


@pytest.fixture
def blender_off():
    """BlenderBridge senza eseguibile: verifica i percorsi di errore."""
    return BlenderBridge("/percorso/inesistente/blender")


@pytest.fixture
def image_asset(graph, generator):
    """Un asset immagine reale su disco, pronto per gli editor."""
    import asyncio
    return asyncio.run(generator.text_to_image("test subject", width=64, height=64))
