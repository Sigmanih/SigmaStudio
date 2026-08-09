"""Generazione 3D: immagine/testo/multi-vista → mesh.

L'orchestrazione è di Sigma, l'esecuzione dei modelli è dei backend configurati.
Se nessun backend 3D è attivo l'operazione fallisce con un messaggio azionabile
invece di produrre un asset senza geometria.
"""

import os

from core.creative.asset_graph import AssetGraph, Asset, AssetType
from core.creative.model_router import ModelRouter, CreativeTask
from core.creative.params import normalize_params
from core.creative.three_d.adapters import build_3d_adapter
from core.logger import get_logger

log = get_logger("model_generator_3d")

NO_3D_BACKEND = (
    "Nessun backend 3D configurato. Opzioni: ComfyUI con Hunyuan3D/TRELLIS/InstantMesh "
    "(serve il workflow esportato in data/creative/workflows/), oppure fal.ai / Stability "
    "con la relativa API key in Impostazioni → Creative."
)


class ModelGenerator3D:
    def __init__(self, model_router: ModelRouter, asset_graph: AssetGraph, image_generator=None):
        self.model_router = model_router
        self.asset_graph = asset_graph
        if image_generator is None:
            from core.creative.generators.image_generator import ImageGenerator
            image_generator = ImageGenerator(model_router, asset_graph)
        self.image_generator = image_generator

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _adapter_for_backend(self, backend: str, capability: str):
        """Adapter concreto per il backend, se espone la capability richiesta."""
        cfg = self.model_router.get_config().get("backends", {}).get(backend, {})
        if backend == "comfyui":
            adapter = self.image_generator._get_adapter("comfyui")
        else:
            adapter = build_3d_adapter(backend, cfg)
        return adapter if adapter is not None and hasattr(adapter, capability) else None

    async def _plan(self, task: CreativeTask, capability: str = "image_to_3d"):
        """3D Agent: sceglie il modello 3D migliore fra quelli davvero eseguibili.

        Prova i candidati in ordine di punteggio: un modello vince solo se il suo
        backend è raggiungibile *e* sa eseguire la capability (per ComfyUI questo
        significa avere il workflow custom installato).
        """
        model, backend = await self.model_router.select(task)
        if model and backend:
            adapter = self._adapter_for_backend(backend, capability)
            if adapter is not None:
                task.params = self.model_router.apply_model(task.params, model, backend)
                return model, backend, adapter

        # Il primo candidato non è utilizzabile: scendi la lista dei backend attivi.
        for name, cfg in self.model_router.get_config().get("backends", {}).items():
            if not cfg.get("enabled"):
                continue
            adapter = self._adapter_for_backend(name, capability)
            if adapter is not None:
                log.info(f"3D: ripiego sul backend {name} per {capability}")
                return None, name, adapter
        return None, None, None

    def _pick_adapter(self, capability: str = "image_to_3d"):
        """Selezione senza registro (compat): primo backend abilitato utilizzabile."""
        for name, cfg in self.model_router.get_config().get("backends", {}).items():
            if not cfg.get("enabled"):
                continue
            adapter = self._adapter_for_backend(name, capability)
            if adapter is not None:
                return name, adapter
        return None, None

    def _read_image(self, asset_id: str) -> tuple[Asset, bytes]:
        asset = self.asset_graph.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset source non trovato: {asset_id}")
        path = asset.files.get("image")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{asset.name}' non ha un file immagine su disco")
        with open(path, "rb") as f:
            return asset, f.read()

    def _store_mesh(self, mesh_bytes: bytes, ext: str, name: str, metadata: dict, sources: list) -> Asset:
        ext = (ext or "glb").lower()
        if ext not in ("glb", "gltf", "obj", "fbx", "ply", "stl"):
            ext = "glb"
        asset = self.asset_graph.create_asset(
            type_val=AssetType.MODEL_3D,
            name=name,
            source_assets=sources,
            metadata=metadata,
        )
        path = self.asset_graph.save_file(asset.asset_id, f"model.{ext}", mesh_bytes)
        return self.asset_graph.update_asset(asset.asset_id, files={"model": path})

    # ------------------------------------------------------------------
    # Operazioni
    # ------------------------------------------------------------------

    async def image_to_3d(self, asset_id: str, priority: str = "quality", **params) -> Asset:
        """Converte una singola immagine in modello 3D."""
        params = normalize_params(params)
        params.pop("asset_id", None)
        source_asset, image_bytes = self._read_image(asset_id)

        task = CreativeTask('image_to_3d', params, priority=priority)
        spec, backend_name, adapter = await self._plan(task, "image_to_3d")
        if adapter is None:
            raise RuntimeError(NO_3D_BACKEND)

        log.info(f"Image to 3D di {asset_id} via {backend_name}" + (f" / {spec.id}" if spec else ""))
        mesh_bytes, ext = await adapter.image_to_3d(image_bytes, task.params)

        return self._store_mesh(mesh_bytes, ext, f"{source_asset.name}_3d", {
            "operation": "image_to_3d", "generator": backend_name,
            "model": spec.id if spec else None, "params": task.params
        }, [asset_id])

    async def multiview_to_3d(self, asset_ids: list, **params) -> Asset:
        """Ricostruzione 3D da più viste dello stesso soggetto."""
        params = normalize_params(params)
        params.pop("asset_ids", None)
        if not asset_ids:
            raise ValueError("Servono almeno due immagini per la ricostruzione multi-vista")

        images = [self._read_image(aid)[1] for aid in asset_ids]

        task = CreativeTask('multiview_to_3d', params, priority="quality")
        spec, backend_name, adapter = await self._plan(task, "multiview_to_3d")
        note = None
        if adapter is None:
            # Nessun backend multi-vista: ripiego sulla prima vista, dichiarandolo.
            single = CreativeTask('image_to_3d', params, priority="quality")
            spec, backend_name, adapter = await self._plan(single, "image_to_3d")
            if adapter is None:
                raise RuntimeError(NO_3D_BACKEND)
            note = "Backend multi-vista non disponibile: ricostruzione dalla prima immagine"
            log.warning(note)
            mesh_bytes, ext = await adapter.image_to_3d(images[0], single.params)
        else:
            log.info(f"Multiview to 3D ({len(images)} viste) via {backend_name}")
            mesh_bytes, ext = await adapter.multiview_to_3d(images, task.params)

        return self._store_mesh(mesh_bytes, ext, "multiview_reconstruction", {
            "operation": "multiview_to_3d", "generator": backend_name,
            "model": spec.id if spec else None,
            "views": len(images), "note": note, "params": params
        }, list(asset_ids))

    async def text_to_3d(self, prompt: str, **params) -> Asset:
        """Testo → 3D orchestrando generazione immagine + ricostruzione."""
        if not prompt or not str(prompt).strip():
            raise ValueError("Il prompt è obbligatorio per text_to_3d")
        params = normalize_params(params)
        params.pop("prompt", None)

        # Una vista frontale su fondo neutro è ciò che i ricostruttori gestiscono meglio.
        concept_prompt = f"{prompt}, single object, centered, front view, plain white background, studio lighting"
        log.info(f"Text to 3D: genero la vista di concept per '{prompt}'")
        concept = await self.image_generator.text_to_image(
            concept_prompt,
            width=params.get("width", 1024),
            height=params.get("height", 1024),
            seed=params.get("seed", -1),
        )

        asset = await self.image_to_3d(concept.asset_id, **params)
        return self.asset_graph.update_asset(asset.asset_id, name=f"text_to_3d_{prompt[:20].strip()}", metadata={
            **asset.metadata, "operation": "text_to_3d", "prompt": prompt,
            "concept_asset_id": concept.asset_id,
        })
