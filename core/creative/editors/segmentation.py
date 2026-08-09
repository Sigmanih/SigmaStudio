"""Segmentazione: produce maschere, non immagini finite.

Una maschera è il collante fra moduli: la stessa maschera alimenta rimozione
sfondo, inpainting e sostituzione oggetto. La catena di fallback è dichiarata,
e il metodo effettivamente usato finisce nel metadata dell'asset:

    SAM 2 (ComfyUI)  →  rembg (locale)  →  flood fill (Pillow)
"""

import io
import os

from core.creative.asset_graph import AssetGraph, AssetType
from core.logger import get_logger

log = get_logger("creative_segmentation")


class SegmentationService:
    def __init__(self, model_router, asset_graph: AssetGraph, image_generator=None):
        self.router = model_router
        self.graph = asset_graph
        self.generator = image_generator

    # ------------------------------------------------------------------

    async def _sam2_adapter(self):
        """Adapter ComfyUI se il workflow SAM 2 è stato fornito dall'utente."""
        from .segmentation_support import sam2_ready
        if not self.generator or not sam2_ready():
            return None
        backends = self.router.get_config().get("backends", {}) if self.router else {}
        if not backends.get("comfyui", {}).get("enabled"):
            return None
        adapter = self.generator._get_adapter("comfyui")
        return adapter if hasattr(adapter, "segment") else None

    async def mask_bytes(self, image_bytes: bytes, prompt: str = "") -> tuple[bytes, str]:
        """Maschera PNG (bianco = soggetto) + nome del metodo usato."""
        adapter = await self._sam2_adapter()
        if adapter is not None:
            try:
                mask = await adapter.segment(image_bytes, {"prompt": prompt})
                return mask, "sam2"
            except Exception as e:
                log.warning(f"SAM 2 non ha prodotto una maschera ({e}): passo ai fallback")

        try:
            import rembg
            cut = rembg.remove(image_bytes)
            return self._alpha_to_mask(cut), "rembg"
        except ImportError:
            pass
        except Exception as e:
            log.warning(f"rembg fallito ({e}): passo al flood fill")

        from .image_editor import ImageEditor
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as img:
            cut = ImageEditor._remove_background_heuristic(img.convert("RGBA"))
        buf = io.BytesIO()
        cut.save(buf, "PNG")
        return self._alpha_to_mask(buf.getvalue()), "flood_fill"

    @staticmethod
    def _alpha_to_mask(rgba_png: bytes) -> bytes:
        """Converte un PNG con alpha nella maschera L attesa dagli inpainter."""
        from PIL import Image
        with Image.open(io.BytesIO(rgba_png)) as img:
            alpha = img.convert("RGBA").getchannel("A")
        buf = io.BytesIO()
        alpha.point(lambda v: 255 if v > 8 else 0).convert("L").save(buf, "PNG")
        return buf.getvalue()

    # ------------------------------------------------------------------

    async def segment_asset(self, asset_id: str, prompt: str = "") -> tuple:
        """Crea un asset maschera derivato dall'immagine sorgente."""
        source = self.graph.get_asset(asset_id)
        if not source:
            raise ValueError(f"Asset non trovato: {asset_id}")
        path = source.files.get("image")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{source.name}' non ha un file immagine su disco")

        with open(path, "rb") as f:
            mask, method = await self.mask_bytes(f.read(), prompt)

        asset = self.graph.create_asset(
            type_val=AssetType.TEXTURE,
            name=f"{source.name}_mask",
            source_assets=[asset_id],
            metadata={"operation": "segment", "method": method, "prompt": prompt},
        )
        asset = self.graph.attach_file(asset.asset_id, "image", "image.png", mask)
        log.info(f"Maschera per {asset_id} generata con {method}")
        return asset, method
