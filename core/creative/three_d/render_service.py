"""Rendering di asset 3D via Blender headless."""

import os

from core.creative.asset_graph import AssetGraph, Asset, AssetType, MODEL_FILE_ROLES
from core.creative.three_d.blender_bridge import BlenderBridge
from core.logger import get_logger

log = get_logger("creative_render")

ENGINES = {"cycles": "CYCLES", "eevee": "BLENDER_EEVEE_NEXT", "eevee_legacy": "BLENDER_EEVEE"}


class SceneRenderer:
    def __init__(self, asset_graph: AssetGraph, blender_bridge: BlenderBridge):
        self.asset_graph = asset_graph
        self.blender_bridge = blender_bridge

    async def render(self, asset_id: str, params: dict = None) -> Asset:
        params = params or {}
        source = self.asset_graph.get_asset(asset_id)
        if not source:
            raise ValueError(f"Asset non trovato: {asset_id}")

        mesh_path = next((source.files[r] for r in MODEL_FILE_ROLES
                          if source.files.get(r) and os.path.exists(source.files[r])), None)
        if not mesh_path:
            raise ValueError(f"L'asset '{source.name}' non contiene geometria da renderizzare")

        if not self.blender_bridge.available:
            raise RuntimeError(
                "Blender non è disponibile: il render richiede backends.blender.path "
                "configurato in Impostazioni → Creative."
            )

        engine = ENGINES.get(str(params.get("engine", "cycles")).lower(), "CYCLES")
        width = int(params.get("width", 1920))
        height = int(params.get("height", 1080))
        samples = int(params.get("samples", 128))

        new_asset = self.asset_graph.create_asset(
            type_val=AssetType.RENDER,
            name=f"{source.name}_render",
            source_assets=[asset_id],
            metadata={"operation": "render", "engine": engine,
                      "resolution": [width, height], "samples": samples},
        )
        output_path = self.asset_graph.asset_dir(new_asset.asset_id) / "render.png"

        log.info(f"Render di {asset_id} con {engine} @ {width}x{height} ({samples} samples)")
        result = await self.blender_bridge.render(
            mesh_path, str(output_path), engine=engine,
            resolution=(width, height), samples=samples,
            transparent=bool(params.get("transparent", False)),
        )

        if not output_path.exists():
            self.asset_graph.delete_asset(new_asset.asset_id)
            raise RuntimeError(f"Render fallito: {result.get('error', 'nessuna immagine prodotta')}")

        asset = self.asset_graph.update_asset(
            new_asset.asset_id,
            files={"image": output_path.as_posix()},
            metadata={"operation": "render", "engine": engine, "resolution": [width, height],
                      "samples": samples, "blender_result": result},
        )
        self.asset_graph.generate_thumbnail(asset.asset_id, output_path.as_posix())
        return self.asset_graph.get_asset(asset.asset_id)
