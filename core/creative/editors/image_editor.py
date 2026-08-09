"""Editing di immagini sugli asset del Creative Studio.

Ogni operazione produce un file reale nella directory dell'asset e un nuovo nodo
nell'asset graph collegato alla sorgente. Quando il backend configurato espone
l'operazione nativa (es. inpaint di SD WebUI) viene usato quello; altrimenti si
ricade su una composizione locale con Pillow, dichiarata nel metadata `method`.
"""

import base64
import io
import os

from core.creative.asset_graph import AssetGraph, Asset, AssetType
from core.creative.model_router import ModelRouter, CreativeTask
from core.creative.params import normalize_params
from core.logger import get_logger

log = get_logger("image_editor")

DIRECTIONS = ("all", "top", "bottom", "left", "right")


def _require_pil():
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError as e:
        raise RuntimeError("Editing immagini non disponibile: Pillow non installato") from e


class ImageEditor:
    def __init__(self, model_router: ModelRouter, asset_graph: AssetGraph, image_generator=None):
        self.model_router = model_router
        self.asset_graph = asset_graph
        if image_generator is None:
            from core.creative.generators.image_generator import ImageGenerator
            image_generator = ImageGenerator(model_router, asset_graph)
        self.generator = image_generator

        from .segmentation import SegmentationService
        self.segmentation = SegmentationService(model_router, asset_graph, image_generator)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load(self, asset_id: str):
        """Ritorna (asset, PIL.Image RGBA) validando l'esistenza del file."""
        _require_pil()
        from PIL import Image

        asset = self.asset_graph.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset source non trovato: {asset_id}")
        path = asset.files.get("image")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{asset.name}' non ha un file immagine su disco")
        with Image.open(path) as img:
            return asset, img.convert("RGBA")

    @staticmethod
    def _to_bytes(img) -> bytes:
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def _decode_mask(self, mask_data: str, size):
        """Converte la maschera base64 della UI in una maschera L (255 = da editare)."""
        _require_pil()
        from PIL import Image

        if not mask_data:
            return None
        payload = mask_data.split(",", 1)[-1] if mask_data.startswith("data:") else mask_data
        try:
            raw = base64.b64decode(payload)
        except Exception as e:
            raise ValueError(f"Maschera non decodificabile: {e}")

        with Image.open(io.BytesIO(raw)) as m:
            m = m.convert("RGBA")
            # Il pennello della UI disegna in rosso semitrasparente: l'alpha è il
            # segnale affidabile; se la maschera è opaca si usa la luminanza.
            alpha = m.getchannel("A")
            mask = alpha if alpha.getextrema()[1] > 0 else m.convert("L")
            if mask.size != size:
                mask = mask.resize(size, Image.LANCZOS)
            return mask.point(lambda v: 255 if v > 8 else 0)

    def _save_result(self, source_asset: Asset, img, suffix: str, metadata: dict,
                     extra_sources: list = None) -> Asset:
        sources = [source_asset.asset_id] if source_asset else []
        sources += extra_sources or []
        asset = self.asset_graph.create_asset(
            type_val=AssetType.IMAGE,
            name=f"{source_asset.name}_{suffix}" if source_asset else suffix,
            source_assets=sources,
            metadata=metadata,
        )
        return self.asset_graph.attach_file(asset.asset_id, "image", "image.png", self._to_bytes(img))

    def _adapter_for(self, capability: str):
        """Adapter del backend attivo se supporta la capability, altrimenti None."""
        backends = self.model_router.get_config().get("backends", {})
        for name, cfg in backends.items():
            if not cfg.get("enabled"):
                continue
            adapter = self.generator._get_adapter(name)
            if hasattr(adapter, capability):
                return name, adapter
        return None, None

    async def _generate_patch(self, prompt: str, size, params: dict):
        """Genera un'immagine dal prompt, ritagliata alle dimensioni richieste."""
        from PIL import Image

        task = CreativeTask('text_to_image', normalize_params({
            "prompt": prompt, "width": size[0], "height": size[1], **(params or {})
        }))
        backend = await self.model_router.route(task)
        patch_bytes, _ = await self.generator._call_with_fallback(
            backend, "text_to_image", prompt, task.params
        )
        with Image.open(io.BytesIO(patch_bytes)) as patch:
            return patch.convert("RGBA").resize(size, Image.LANCZOS)

    # ------------------------------------------------------------------
    # Operazioni
    # ------------------------------------------------------------------

    async def inpaint(self, asset_id: str, mask_data: str, prompt: str, **params) -> Asset:
        """Rigenera l'area mascherata a partire dal prompt."""
        from PIL import Image, ImageFilter

        source_asset, img = self._load(asset_id)
        mask = self._decode_mask(mask_data, img.size)
        if mask is None:
            raise ValueError("Maschera mancante: disegna l'area da rigenerare prima di applicare l'inpaint")

        params = normalize_params(params)
        backend_name, adapter = self._adapter_for("inpaint")
        if adapter is not None:
            try:
                result_bytes = await adapter.inpaint(
                    self._to_bytes(img), self._to_bytes(mask.convert("RGB")), prompt, params
                )
                with Image.open(io.BytesIO(result_bytes)) as res:
                    out = res.convert("RGBA")
                method = f"backend:{backend_name}"
            except Exception as e:
                log.warning(f"Inpaint nativo su {backend_name} fallito ({e}): composizione locale")
                adapter = None

        if adapter is None:
            patch = await self._generate_patch(prompt, img.size, params)
            soft_mask = mask.filter(ImageFilter.GaussianBlur(radius=max(2, min(img.size) // 128)))
            out = Image.composite(patch, img, soft_mask)
            method = "local_composite"

        log.info(f"Inpaint di {asset_id} completato ({method})")
        return self._save_result(source_asset, out, "inpainted", {
            "operation": "inpaint", "prompt": prompt, "method": method, "params": params
        })

    async def outpaint(self, asset_id: str, direction: str, pixels: int, prompt: str, **params) -> Asset:
        """Estende la tela e riempie la parte nuova con contenuto generato."""
        from PIL import Image, ImageFilter

        source_asset, img = self._load(asset_id)
        direction = (direction or "all").lower()
        if direction not in DIRECTIONS:
            raise ValueError(f"Direzione '{direction}' non valida (usa: {', '.join(DIRECTIONS)})")
        pixels = max(1, int(pixels or 128))

        left = pixels if direction in ("all", "left") else 0
        right = pixels if direction in ("all", "right") else 0
        top = pixels if direction in ("all", "top") else 0
        bottom = pixels if direction in ("all", "bottom") else 0

        new_size = (img.width + left + right, img.height + top + bottom)
        canvas = Image.new("RGBA", new_size, (0, 0, 0, 0))
        canvas.paste(img, (left, top))

        # Maschera = tutto ciò che non è l'immagine originale
        mask = Image.new("L", new_size, 255)
        mask.paste(0, (left, top, left + img.width, top + img.height))

        params = normalize_params(params)
        fill_prompt = prompt or f"seamless continuation of {source_asset.name}"
        patch = await self._generate_patch(fill_prompt, new_size, params)
        soft_mask = mask.filter(ImageFilter.GaussianBlur(radius=max(2, pixels // 8)))
        out = Image.composite(patch, canvas.convert("RGBA"), soft_mask)

        log.info(f"Outpaint di {asset_id} verso {direction} (+{pixels}px)")
        return self._save_result(source_asset, out, f"outpainted_{direction}", {
            "operation": "outpaint", "prompt": fill_prompt, "direction": direction,
            "pixels": pixels, "method": "local_composite", "params": params
        })

    async def remove_background(self, asset_id: str) -> Asset:
        """Rimuove lo sfondo producendo un PNG RGBA (SAM 2 → rembg → flood fill)."""
        from PIL import Image

        source_asset, img = self._load(asset_id)
        mask_bytes, method = await self.segmentation.mask_bytes(self._to_bytes(img))

        with Image.open(io.BytesIO(mask_bytes)) as m:
            mask = m.convert("L").resize(img.size, Image.LANCZOS)
        out = img.copy()
        out.putalpha(mask)

        log.info(f"Background rimosso da {asset_id} ({method})")
        return self._save_result(source_asset, out, "nobg", {
            "operation": "remove_background", "method": method
        })

    async def replace_background(self, asset_id: str, prompt: str, **params) -> Asset:
        """Scontorna il soggetto e rigenera lo sfondo dal prompt.

        È la richiesta tipica dell'e-commerce ("stesso prodotto, ambiente diverso"):
        il soggetto resta pixel-identico, cambia solo ciò che gli sta dietro.
        """
        from PIL import Image, ImageFilter

        if not prompt or not str(prompt).strip():
            raise ValueError("Serve un prompt che descriva il nuovo sfondo")

        source_asset, img = self._load(asset_id)
        mask_bytes, method = await self.segmentation.mask_bytes(self._to_bytes(img), prompt="soggetto principale")
        with Image.open(io.BytesIO(mask_bytes)) as m:
            subject = m.convert("L").resize(img.size, Image.LANCZOS)

        background = await self._generate_patch(prompt, img.size, normalize_params(params))
        # Bordo ammorbidito: un taglio netto sul soggetto tradisce il montaggio.
        soft = subject.filter(ImageFilter.GaussianBlur(radius=max(1, min(img.size) // 400)))
        out = Image.composite(img, background, soft)

        log.info(f"Sfondo di {asset_id} sostituito ({method})")
        return self._save_result(source_asset, out, "newbg", {
            "operation": "replace_background", "prompt": prompt,
            "method": f"{method}+generate", "params": normalize_params(params),
        })

    async def segment(self, asset_id: str, prompt: str = "") -> Asset:
        """Produce un asset maschera riutilizzabile dagli altri moduli."""
        asset, _method = await self.segmentation.segment_asset(asset_id, prompt)
        return asset

    @staticmethod
    def _remove_background_heuristic(img, tolerance: int = 32):
        """Fallback senza modelli: flood fill dai bordi sui colori uniformi.

        Funziona bene su sfondi piatti (packshot, render); su foto complesse
        serve `rembg`, segnalato nel metadata dell'asset.
        """
        from PIL import Image, ImageDraw

        rgb = img.convert("RGB")
        work = rgb.copy()
        w, h = work.size
        drawer = ImageDraw.floodfill
        seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
                 (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
        marker = (1, 254, 3)
        for seed in seeds:
            try:
                drawer(work, seed, marker, thresh=tolerance)
            except Exception:
                continue

        alpha = Image.new("L", (w, h), 255)
        work_px = work.load()
        alpha_px = alpha.load()
        for y in range(h):
            for x in range(w):
                if work_px[x, y] == marker:
                    alpha_px[x, y] = 0

        out = img.copy()
        out.putalpha(alpha)
        return out

    async def replace_object(self, asset_id: str, mask_data: str, prompt: str, **params) -> Asset:
        """Sostituisce il contenuto dell'area mascherata (inpaint mirato)."""
        asset = await self.inpaint(asset_id, mask_data, prompt, **params)
        return self.asset_graph.update_asset(
            asset.asset_id,
            name=asset.name.replace("_inpainted", "_replaced"),
            metadata={**asset.metadata, "operation": "replace_object"},
        )

    async def style_transfer(self, asset_id: str, style_prompt: str, strength: float = 0.7, **params) -> Asset:
        """Riapplica l'immagine attraverso img2img con un prompt di stile."""
        if not style_prompt:
            raise ValueError("style_prompt obbligatorio per lo style transfer")
        asset = await self.generator.image_to_image(
            asset_id, style_prompt, strength=float(strength), **normalize_params(params)
        )
        source = self.asset_graph.get_asset(asset_id)
        return self.asset_graph.update_asset(
            asset.asset_id,
            name=f"{source.name}_styled" if source else asset.name,
            metadata={**asset.metadata, "operation": "style_transfer", "style_prompt": style_prompt},
        )

    async def relight(self, asset_id: str, light_direction: str = "front", intensity: float = 1.0) -> Asset:
        """Rilluminazione locale: gradiente direzionale + guadagno di esposizione."""
        from PIL import Image, ImageEnhance

        source_asset, img = self._load(asset_id)
        intensity = max(0.0, min(3.0, float(intensity)))
        w, h = img.size

        gradient = Image.new("L", (w, h), 128)
        px = gradient.load()
        direction = (light_direction or "front").lower()
        for y in range(h):
            for x in range(w):
                if direction == "left":
                    v = 255 - int(255 * x / max(1, w - 1))
                elif direction == "right":
                    v = int(255 * x / max(1, w - 1))
                elif direction == "top":
                    v = 255 - int(255 * y / max(1, h - 1))
                elif direction == "bottom":
                    v = int(255 * y / max(1, h - 1))
                else:  # front: illuminazione uniforme
                    v = 200
                px[x, y] = v

        light = Image.merge("RGBA", (gradient, gradient, gradient, Image.new("L", (w, h), 255)))
        blended = Image.blend(img, light, alpha=min(0.45, 0.25 * intensity))
        out = ImageEnhance.Brightness(blended).enhance(0.85 + 0.25 * intensity)
        out = ImageEnhance.Contrast(out).enhance(1.0 + 0.15 * intensity)
        out.putalpha(img.getchannel("A"))

        log.info(f"Relight di {asset_id}: {direction} @ {intensity}")
        return self._save_result(source_asset, out, "relit", {
            "operation": "relight", "light_direction": direction,
            "intensity": intensity, "method": "local_gradient"
        })
