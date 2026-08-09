"""Materiali PBR e applicazione alla geometria via Blender."""

import os
import shutil

from core.creative.asset_graph import AssetGraph, Asset, AssetType, MODEL_FILE_ROLES
from core.creative.three_d.blender_bridge import BlenderBridge
from core.logger import get_logger

log = get_logger("material_system")

PBR_ROLES = ("albedo", "normal", "roughness", "metallic", "height", "ao")


class MaterialSystem:
    def __init__(self, asset_graph: AssetGraph, blender_bridge: BlenderBridge):
        self.asset_graph = asset_graph
        self.blender_bridge = blender_bridge

    def _resolve_texture(self, value) -> str | None:
        """Accetta sia un path su disco sia un asset_id di texture/immagine."""
        if not value:
            return None
        if os.path.exists(str(value)):
            return str(value)
        asset = self.asset_graph.get_asset(str(value))
        if not asset:
            return None
        for role in ("image", "albedo"):
            path = asset.files.get(role)
            if path and os.path.exists(path):
                return path
        return None

    async def create_pbr_material(self, textures: dict, name: str = 'SigmaPBR') -> Asset:
        """Raccoglie un set di texture in un asset materiale con file propri."""
        if not textures:
            raise ValueError("Nessuna texture fornita per il materiale")

        log.info(f"Creating PBR material {name}")
        sources = [str(v) for v in textures.values() if self.asset_graph.get_asset(str(v))]
        asset = self.asset_graph.create_asset(
            type_val=AssetType.MATERIAL,
            name=name,
            source_assets=sources,
            metadata={"operation": "create_pbr_material", "roles": list(textures.keys())},
        )

        files = {}
        missing = []
        for role, value in textures.items():
            resolved = self._resolve_texture(value)
            if not resolved:
                missing.append(role)
                continue
            target = self.asset_graph.asset_dir(asset.asset_id) / f"{role}.png"
            shutil.copyfile(resolved, target)
            files[role] = target.as_posix()

        if not files:
            self.asset_graph.delete_asset(asset.asset_id)
            raise ValueError("Nessuna delle texture indicate è risolvibile su disco")
        if missing:
            log.warning(f"Texture non risolte per il materiale {name}: {missing}")

        asset = self.asset_graph.update_asset(asset.asset_id, files=files)
        if "albedo" in files:
            self.asset_graph.generate_thumbnail(asset.asset_id, files["albedo"])
            asset = self.asset_graph.get_asset(asset.asset_id)
        return asset

    async def apply_to_mesh(self, mesh_asset_id: str, material_asset_id: str) -> Asset:
        """Applica il materiale alla mesh producendo un GLB texturizzato."""
        mesh_asset = self.asset_graph.get_asset(mesh_asset_id)
        if not mesh_asset:
            raise ValueError(f"Mesh asset non trovato: {mesh_asset_id}")

        mat_asset = self.asset_graph.get_asset(material_asset_id)
        if not mat_asset:
            raise ValueError(f"Material asset non trovato: {material_asset_id}")

        mesh_path = next((mesh_asset.files[r] for r in MODEL_FILE_ROLES
                          if mesh_asset.files.get(r) and os.path.exists(mesh_asset.files[r])), None)
        if not mesh_path:
            raise ValueError(f"L'asset '{mesh_asset.name}' non contiene un file mesh su disco")

        if not self.blender_bridge.available:
            raise RuntimeError(
                "Blender non è disponibile: impossibile applicare il materiale alla mesh. "
                "Configura backends.blender.path in Impostazioni → Creative."
            )

        textures = {role: os.path.abspath(mat_asset.files[role])
                    for role in PBR_ROLES if mat_asset.files.get(role)}

        log.info(f"Applying material {material_asset_id} to mesh {mesh_asset_id}")
        new_asset = self.asset_graph.create_asset(
            type_val=AssetType.MODEL_3D,
            name=f"{mesh_asset.name}_textured",
            source_assets=[mesh_asset_id, material_asset_id],
            metadata={"operation": "apply_material", "material": material_asset_id},
        )
        output_path = self.asset_graph.asset_dir(new_asset.asset_id) / "model.glb"

        result = await self.blender_bridge.apply_material(mesh_path, str(output_path), textures)
        if not output_path.exists():
            self.asset_graph.delete_asset(new_asset.asset_id)
            raise RuntimeError(f"Blender: {result.get('error', 'materiale non applicato')}")

        return self.asset_graph.update_asset(
            new_asset.asset_id,
            files={"model": output_path.as_posix()},
            metadata={"operation": "apply_material", "material": material_asset_id, "blender_result": result},
        )
