"""Generazione texture PBR.

L'albedo arriva dal generatore di immagini (backend instradato dal ModelRouter);
le mappe derivate — normal, roughness, height, AO, metallic — sono calcolate
localmente dall'albedo. È l'approccio standard dei tool di texturing: una sola
inferenza, mappe coerenti tra loro.
"""

import io
import os

from core.creative.asset_graph import AssetGraph, Asset, AssetType
from core.creative.model_router import ModelRouter
from core.creative.params import normalize_params
from core.logger import get_logger

log = get_logger("texture_generator")

PBR_MAPS = ("albedo", "normal", "roughness", "metallic", "height", "ao")


class TextureGenerator:
    def __init__(self, model_router: ModelRouter, asset_graph: AssetGraph, image_generator=None):
        self.model_router = model_router
        self.asset_graph = asset_graph
        if image_generator is None:
            from core.creative.generators.image_generator import ImageGenerator
            image_generator = ImageGenerator(model_router, asset_graph)
        self.image_generator = image_generator

    # ------------------------------------------------------------------
    # Derivazione mappe
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_maps(albedo_bytes: bytes, resolution: int = 1024) -> dict:
        """Calcola normal/roughness/height/AO/metallic a partire dall'albedo."""
        import numpy as np
        from PIL import Image, ImageFilter, ImageOps

        with Image.open(io.BytesIO(albedo_bytes)) as img:
            albedo = img.convert("RGB").resize((resolution, resolution), Image.LANCZOS)

        gray = ImageOps.autocontrast(albedo.convert("L"))
        height = gray.filter(ImageFilter.GaussianBlur(radius=1))

        h = np.asarray(height, dtype=np.float32) / 255.0
        # Gradiente Sobel → normal map in tangent space
        gx = np.zeros_like(h)
        gy = np.zeros_like(h)
        gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
        gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
        strength = 4.0
        nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(h)
        norm = np.sqrt(nx * nx + ny * ny + nz * nz)
        normal = np.stack([(nx / norm + 1) * 0.5, (ny / norm + 1) * 0.5, (nz / norm + 1) * 0.5], axis=-1)
        normal_img = Image.fromarray((normal * 255).astype(np.uint8))

        # Roughness: superfici chiare e piatte → più lucide; dettaglio alto → più ruvide
        detail = np.abs(gx) + np.abs(gy)
        detail = detail / (detail.max() or 1.0)
        roughness = np.clip(0.45 + 0.5 * detail - 0.15 * (h - 0.5), 0, 1)
        roughness_img = Image.fromarray((roughness * 255).astype(np.uint8))

        # AO approssimata: cavità = zone più basse rispetto all'intorno
        blurred = np.asarray(height.filter(ImageFilter.GaussianBlur(radius=resolution // 64 or 4)), dtype=np.float32) / 255.0
        ao = np.clip(1.0 - (blurred - h) * 3.0, 0, 1)
        ao_img = Image.fromarray((ao * 255).astype(np.uint8))

        # Metallic: non inferibile dall'albedo, si parte da dielettrico (0)
        metallic_img = Image.new("L", (resolution, resolution), 0)

        def encode(image, mode="PNG"):
            buf = io.BytesIO()
            image.save(buf, mode)
            return buf.getvalue()

        return {
            "albedo": encode(albedo),
            "normal": encode(normal_img),
            "roughness": encode(roughness_img),
            "height": encode(height),
            "ao": encode(ao_img),
            "metallic": encode(metallic_img),
        }

    def _store_material(self, name: str, maps: dict, metadata: dict, sources: list = None) -> Asset:
        asset = self.asset_graph.create_asset(
            type_val=AssetType.MATERIAL,
            name=name,
            source_assets=sources or [],
            metadata=metadata,
        )
        files = {}
        for role, data in maps.items():
            files[role] = self.asset_graph.save_file(asset.asset_id, f"{role}.png", data)
        asset = self.asset_graph.update_asset(asset.asset_id, files=files)
        if "albedo" in files:
            self.asset_graph.generate_thumbnail(asset.asset_id, files["albedo"])
            asset = self.asset_graph.get_asset(asset.asset_id)
        return asset

    # ------------------------------------------------------------------
    # Operazioni
    # ------------------------------------------------------------------

    async def generate_pbr(self, prompt: str, **params) -> Asset:
        """Genera un set PBR completo a partire da un prompt materiale."""
        if not prompt or not str(prompt).strip():
            raise ValueError("Il prompt è obbligatorio per generare un materiale PBR")

        params = normalize_params(params)
        params.pop("prompt", None)
        resolution = int(params.pop("resolution", 1024))

        log.info(f"Generating PBR textures for prompt: '{prompt}'")
        texture_prompt = (
            f"{prompt}, seamless tileable texture, top-down flat view, "
            "uniform lighting, no shadows, high detail material scan"
        )
        albedo_asset = await self.image_generator.text_to_image(
            texture_prompt,
            width=params.get("width", resolution),
            height=params.get("height", resolution),
            seed=params.get("seed", -1),
        )
        with open(albedo_asset.files["image"], "rb") as f:
            albedo_bytes = f.read()

        maps = self._derive_maps(albedo_bytes, resolution)
        return self._store_material(f"pbr_{prompt[:20].strip()}", maps, {
            "operation": "generate_pbr", "prompt": prompt,
            "generator": albedo_asset.metadata.get("generator"),
            "maps": list(maps.keys()), "resolution": resolution,
        }, [albedo_asset.asset_id])

    async def generate_from_image(self, asset_id: str, **params) -> Asset:
        """Deriva un set PBR da un'immagine già presente nel vault."""
        source_asset = self.asset_graph.get_asset(asset_id)
        if not source_asset:
            raise ValueError(f"Asset source non trovato: {asset_id}")
        path = source_asset.files.get("image")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{source_asset.name}' non ha un file immagine su disco")

        params = normalize_params(params)
        resolution = int(params.get("resolution", 1024))
        with open(path, "rb") as f:
            maps = self._derive_maps(f.read(), resolution)

        log.info(f"Generating PBR from image {asset_id}")
        return self._store_material(f"{source_asset.name}_pbr", maps, {
            "operation": "generate_from_image", "resolution": resolution,
            "maps": list(maps.keys()),
        }, [asset_id])

    async def make_tileable(self, asset_id: str) -> Asset:
        """Rende una texture seamless con offset + blending dei bordi."""
        import numpy as np
        from PIL import Image

        source_asset = self.asset_graph.get_asset(asset_id)
        if not source_asset:
            raise ValueError(f"Asset source non trovato: {asset_id}")
        path = source_asset.files.get("image") or source_asset.files.get("albedo")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{source_asset.name}' non ha un file immagine su disco")

        with Image.open(path) as img:
            src = img.convert("RGB")
        arr = np.asarray(src, dtype=np.float32)
        h, w, _ = arr.shape

        # Offset di mezza immagine: le cuciture finiscono al centro, dove si sfumano.
        rolled = np.roll(np.roll(arr, w // 2, axis=1), h // 2, axis=0)
        blend_w = max(4, w // 16)
        ramp_x = np.clip(np.abs(np.arange(w) - w / 2) / blend_w, 0, 1)[None, :, None]
        ramp_y = np.clip(np.abs(np.arange(h) - h / 2) / blend_w, 0, 1)[:, None, None]
        weight = np.minimum(ramp_x, ramp_y)
        blended = rolled * weight + np.roll(np.roll(rolled, w // 2, axis=1), h // 2, axis=0) * (1 - weight)

        out = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))
        buf = io.BytesIO()
        out.save(buf, "PNG")

        log.info(f"Making texture {asset_id} tileable")
        new_asset = self.asset_graph.create_asset(
            type_val=AssetType.TEXTURE,
            name=f"{source_asset.name}_tileable",
            source_assets=[asset_id],
            metadata={"operation": "make_tileable", "method": "offset_blend"},
        )
        return self.asset_graph.attach_file(new_asset.asset_id, "image", "image.png", buf.getvalue())
