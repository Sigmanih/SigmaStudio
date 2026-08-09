"""Mesh Lab: operazioni di cleanup/ottimizzazione geometria.

Le operazioni sono eseguite da Blender headless tramite BlenderBridge. Senza
Blender configurato l'operazione fallisce con un messaggio esplicito invece di
creare asset vuoti: un nodo mesh senza file è indistinguibile da un successo.
"""

import json
import os
import shutil
import struct
from pathlib import Path

from core.creative.asset_graph import AssetGraph, Asset, AssetType, MODEL_FILE_ROLES
from core.creative.three_d.blender_bridge import BlenderBridge
from core.logger import get_logger

log = get_logger("mesh_processor")

BLENDER_REQUIRED = (
    "Blender non è disponibile. Configura il percorso in Impostazioni → Creative → "
    "backends.blender.path per abilitare le operazioni mesh."
)


class MeshProcessor:
    def __init__(self, asset_graph: AssetGraph, blender_bridge: BlenderBridge):
        self.asset_graph = asset_graph
        self.blender_bridge = blender_bridge

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _source_model(self, asset_id: str):
        asset = self.asset_graph.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset source non trovato: {asset_id}")
        for role in MODEL_FILE_ROLES:
            path = asset.files.get(role)
            if path and os.path.exists(path):
                return asset, path
        raise ValueError(f"L'asset '{asset.name}' non contiene un file mesh su disco")

    async def _run_op(self, asset_id: str, suffix: str, metadata: dict, runner) -> Asset:
        """Esegue un'operazione Blender producendo un nuovo asset mesh derivato."""
        source_asset, input_path = self._source_model(asset_id)
        if not self.blender_bridge.available:
            raise RuntimeError(BLENDER_REQUIRED)

        new_asset = self.asset_graph.create_asset(
            type_val=AssetType.MESH,
            name=f"{source_asset.name}_{suffix}",
            source_assets=[asset_id],
            metadata=metadata,
        )
        output_path = self.asset_graph.asset_dir(new_asset.asset_id) / "model.glb"

        result = await runner(input_path, str(output_path))
        if isinstance(result, dict) and result.get("status") == "error":
            self.asset_graph.delete_asset(new_asset.asset_id)
            raise RuntimeError(f"Blender: {result.get('error', 'operazione fallita')}")
        if not output_path.exists():
            self.asset_graph.delete_asset(new_asset.asset_id)
            raise RuntimeError("Blender non ha prodotto alcun file di output")

        return self.asset_graph.update_asset(
            new_asset.asset_id,
            files={"model": output_path.as_posix()},
            metadata={**metadata, "blender_result": result},
        )

    # ------------------------------------------------------------------
    # Operazioni
    # ------------------------------------------------------------------

    async def cleanup(self, asset_id: str, params: dict = None) -> Asset:
        """Rimuove duplicati, ricalcola le normali, merge by distance."""
        params = params or {}
        log.info(f"Cleanup mesh per {asset_id}")
        return await self._run_op(
            asset_id, "cleaned", {"operation": "cleanup", **params},
            lambda i, o: self.blender_bridge.clean_mesh(i, o, params),
        )

    async def remesh(self, asset_id: str, params: dict = None) -> Asset:
        """Remesh voxel/quadriflow (via cleanup + decimate controllato)."""
        params = params or {}
        log.info(f"Remesh per {asset_id}")
        return await self._run_op(
            asset_id, "remeshed", {"operation": "remesh", **params},
            lambda i, o: self.blender_bridge.remesh(i, o, params),
        )

    async def decimate(self, asset_id: str, ratio: float = 0.5) -> Asset:
        """Riduzione poligoni preservando la silhouette."""
        ratio = max(0.01, min(1.0, float(ratio)))
        log.info(f"Decimate per {asset_id} con ratio {ratio}")
        return await self._run_op(
            asset_id, "decimated", {"operation": "decimate", "ratio": ratio},
            lambda i, o: self.blender_bridge.decimate(i, o, ratio),
        )

    async def uv_unwrap(self, asset_id: str, method: str = 'smart_project') -> Asset:
        log.info(f"UV unwrap per {asset_id} con metodo {method}")
        return await self._run_op(
            asset_id, "uv", {"operation": "uv_unwrap", "method": method},
            lambda i, o: self.blender_bridge.uv_unwrap(i, o, method),
        )

    async def fix_normals(self, asset_id: str) -> Asset:
        log.info(f"Fix normals per {asset_id}")
        return await self._run_op(
            asset_id, "normals", {"operation": "fix_normals"},
            lambda i, o: self.blender_bridge.clean_mesh(i, o, {"merge_distance": 0.0}),
        )

    async def smooth(self, asset_id: str, iterations: int = 2) -> Asset:
        iterations = max(1, min(20, int(iterations)))
        log.info(f"Smooth per {asset_id} ({iterations} iterazioni)")
        return await self._run_op(
            asset_id, "smoothed", {"operation": "smooth", "iterations": iterations},
            lambda i, o: self.blender_bridge.smooth(i, o, iterations),
        )

    async def export(self, asset_id: str, fmt: str = 'glb') -> Asset:
        """Riesporta la mesh in un altro formato (glb/fbx/obj/stl)."""
        fmt = (fmt or 'glb').lower()
        source_asset, input_path = self._source_model(asset_id)
        if not self.blender_bridge.available:
            raise RuntimeError(BLENDER_REQUIRED)

        new_asset = self.asset_graph.create_asset(
            type_val=AssetType.MESH,
            name=f"{source_asset.name}.{fmt}",
            source_assets=[asset_id],
            metadata={"operation": "export", "format": fmt},
        )
        output_path = self.asset_graph.asset_dir(new_asset.asset_id) / f"model.{fmt}"
        result = await self.blender_bridge.export(input_path, str(output_path), fmt)
        if not output_path.exists():
            self.asset_graph.delete_asset(new_asset.asset_id)
            raise RuntimeError(f"Export fallito: {result.get('error', 'nessun output')}")
        return self.asset_graph.update_asset(new_asset.asset_id, files={"model": output_path.as_posix()})

    # ------------------------------------------------------------------
    # Statistiche
    # ------------------------------------------------------------------

    async def get_mesh_info(self, asset_id: str) -> dict:
        """Statistiche reali della mesh: parsing GLB locale, Blender come fallback."""
        asset, path = self._source_model(asset_id)

        if path.lower().endswith(('.glb', '.gltf')):
            info = self._inspect_gltf(path)
            if info:
                info.update({"status": "ok", "source": "gltf_parser", "file": Path(path).name})
                return info

        if self.blender_bridge.available:
            fmt = Path(path).suffix.lstrip('.').lower() or 'glb'
            result = await self.blender_bridge.import_mesh(path, fmt)
            objects = {k: v for k, v in result.items() if isinstance(v, dict)}
            if objects:
                return {
                    "vertices": sum(o.get("vertices", 0) for o in objects.values()),
                    "faces": sum(o.get("faces", 0) for o in objects.values()),
                    "edges": sum(o.get("edges", 0) for o in objects.values()),
                    "objects": len(objects),
                    "status": "ok",
                    "source": "blender",
                    "file": Path(path).name,
                }

        return {
            "status": "unknown",
            "file": Path(path).name,
            "size_bytes": os.path.getsize(path),
            "message": "Statistiche non disponibili per questo formato senza Blender",
        }

    @staticmethod
    def _inspect_gltf(path: str) -> dict | None:
        """Legge il chunk JSON di un .glb (o il .gltf) e somma gli accessor.

        Nessuna dipendenza esterna: il conteggio arriva dagli accessor POSITION
        e dagli indici delle primitive.
        """
        try:
            if path.lower().endswith('.gltf'):
                with open(path, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
            else:
                with open(path, 'rb') as f:
                    magic, _version, _length = struct.unpack('<III', f.read(12))
                    if magic != 0x46546C67:  # 'glTF'
                        return None
                    chunk_len, chunk_type = struct.unpack('<II', f.read(8))
                    if chunk_type != 0x4E4F534A:  # 'JSON'
                        return None
                    doc = json.loads(f.read(chunk_len).decode('utf-8'))

            accessors = doc.get('accessors', [])
            vertices = faces = 0
            primitives = 0
            for mesh in doc.get('meshes', []):
                for prim in mesh.get('primitives', []):
                    primitives += 1
                    pos = prim.get('attributes', {}).get('POSITION')
                    if pos is not None and pos < len(accessors):
                        vertices += accessors[pos].get('count', 0)
                    idx = prim.get('indices')
                    if idx is not None and idx < len(accessors):
                        faces += accessors[idx].get('count', 0) // 3
            return {
                "vertices": vertices,
                "faces": faces,
                "edges": faces * 3 // 2 if faces else 0,
                "objects": len(doc.get('meshes', [])),
                "primitives": primitives,
                "materials": len(doc.get('materials', [])),
                "has_uv": any(
                    'TEXCOORD_0' in prim.get('attributes', {})
                    for mesh in doc.get('meshes', []) for prim in mesh.get('primitives', [])
                ),
            }
        except Exception as e:
            log.warning(f"Parsing glTF fallito per {path}: {e}")
            return None
