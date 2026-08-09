import json
import asyncio
from urllib.parse import parse_qs, urlparse
from core.logger import get_logger
from core.creative import AssetGraph, ModelRouter
from core.creative.params import normalize_params
from core.creative.generators.image_generator import ImageGenerator
from core.creative.editors.image_editor import ImageEditor
from core.creative.three_d.model_generator import ModelGenerator3D
from core.creative.three_d.blender_bridge import BlenderBridge
from core.creative.three_d.render_service import SceneRenderer
from core.creative.mesh.mesh_processor import MeshProcessor
from core.creative.materials.texture_generator import TextureGenerator
from core.creative.materials.material_system import MaterialSystem
from core.creative.pipeline.creative_pipeline_engine import CreativePipelineEngine
from core.creative.video.video_generator import VideoGenerator
from core.creative.agents.creative_agents import CREATIVE_AGENTS, register_creative_agents
from core.creative.agents.vision_agent import VisionAgent
from core.creative.model_registry import catalog as model_catalog, available_vram_gb
from core.creative.generators.adapters.comfyui_adapter import ComfyUIAdapter
from core.creative import model_hub
from core.creative.backends import get_backend
from core.creative.model_state import build_inventory, runtime_tracker
from core.creative.workflow_registry import registry as workflow_registry
from core.creative.model_downloader import (
    CATALOG as DOWNLOAD_CATALOG, CATALOG_BY_ID, custom_asset, discover_models_root,
    disk_free_gb, download_manager, installed_by_category, installed_state,
)

log = get_logger("creative_router")

# Istanziamo i singleton per il router creativo
# Nota: andrebbe letto da config.json, qui semplifichiamo leggendolo direttamente se serve
def get_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        log.error(f"Errore salvataggio config: {e}")

_config = get_config()
asset_graph = AssetGraph()
model_router = ModelRouter(_config)
image_generator = ImageGenerator(model_router, asset_graph)
image_editor = ImageEditor(model_router, asset_graph, image_generator)
blender_bridge = BlenderBridge(_config.get("creative", {}).get("backends", {}).get("blender", {}).get("path", ""))
model_generator_3d = ModelGenerator3D(model_router, asset_graph, image_generator)
mesh_processor = MeshProcessor(asset_graph, blender_bridge)
texture_generator = TextureGenerator(model_router, asset_graph, image_generator)
material_system = MaterialSystem(asset_graph, blender_bridge)
scene_renderer = SceneRenderer(asset_graph, blender_bridge)
video_generator = VideoGenerator(model_router, asset_graph, image_generator)
vision_agent = VisionAgent(asset_graph, _config.get("creative", {}))
pipeline_engine = CreativePipelineEngine(asset_graph, model_router, blender_bridge)

# Gli agenti creativi devono comparire nel registro agenti come tutti gli altri.
register_creative_agents()


def _sse(self, payload: dict):
    """Invia un evento SSE se la richiesta è in streaming."""
    if hasattr(self, "sse_queue"):
        self.sse_queue.put(f"data: {json.dumps(payload)}\n\n")


def _fail(self, err: Exception, context: str, status: int = 500):
    """Log + risposta JSON + evento SSE con lo stesso messaggio d'errore."""
    log.error(f"Errore {context}: {err}")
    self.send_json_response({"success": False, "error": str(err)}, status)
    _sse(self, {"status": "error", "error": str(err)})


def handle_creative_assets(self):
    """GET /api/creative/assets"""
    try:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        type_filter = qs.get("type", [None])[0]
        tag_filter = qs.get("tag", [None])[0]
        limit = int(qs.get("limit", [50])[0])
        offset = int(qs.get("offset", [0])[0])
        
        assets = asset_graph.list_assets(type_filter=type_filter, tag_filter=tag_filter, limit=limit, offset=offset)
        self.send_json_response({"success": True, "assets": [a.to_dict() for a in assets]})
    except Exception as e:
        self.send_json_response({"success": False, "error": f"Errore recupero asset: {str(e)}"}, 500)


def handle_creative_asset_get(self):
    """GET /api/creative/assets/get?id=xxx"""
    try:
        qs = parse_qs(urlparse(self.path).query)
        asset_id = qs.get("id", [""])[0]
        if not asset_id:
            return self.send_json_response({"success": False, "error": "ID mancante"}, 400)
            
        asset = asset_graph.get_asset(asset_id)
        if not asset:
            return self.send_json_response({"success": False, "error": "Asset non trovato"}, 404)
            
        self.send_json_response({"success": True, "asset": asset.to_dict()})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_asset_lineage(self):
    """GET /api/creative/assets/lineage?id=xxx"""
    try:
        qs = parse_qs(urlparse(self.path).query)
        asset_id = qs.get("id", [""])[0]
        if not asset_id:
            return self.send_json_response({"success": False, "error": "ID mancante"}, 400)
            
        lineage = asset_graph.get_lineage(asset_id)
        self.send_json_response({"success": True, "lineage": lineage})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_asset_versions(self):
    """GET /api/creative/assets/versions?id=xxx"""
    try:
        qs = parse_qs(urlparse(self.path).query)
        asset_id = qs.get("id", [""])[0]
        if not asset_id:
            return self.send_json_response({"success": False, "error": "ID mancante"}, 400)
            
        versions = asset_graph.get_versions(asset_id)
        self.send_json_response({"success": True, "versions": versions})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_backends_status(self):
    """GET /api/creative/backends/status"""
    try:
        statuses = asyncio.run(model_router.get_available_backends(refresh=True))
        capabilities = {}
        for status in statuses:
            if status.available:
                for cap in status.capabilities:
                    capabilities.setdefault(cap, []).append(status.name)

        # Le capability "moderne" (instruct_edit, segment, video, vision) esistono
        # solo nel registro modelli: senza questo merge la UI le crederebbe assenti.
        available_names = asyncio.run(model_router.available_backend_names())
        ollama_models = asyncio.run(model_router.ollama_models())
        for entry in model_catalog(available_names, ollama_models):
            for backend in entry["available_via"]:
                for task in entry["tasks"]:
                    if backend not in capabilities.setdefault(task, []):
                        capabilities[task].append(backend)

        self.send_json_response({
            "success": True,
            "backends": [s.to_dict() for s in statuses],
            "capabilities": capabilities,
            "vram_free_gb": available_vram_gb(),
            "blender": {"available": blender_bridge.available, "path": blender_bridge.blender_path},
        })
    except Exception as e:
        log.error(f"Errore backends status: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_stats(self):
    """GET /api/creative/stats"""
    try:
        stats = asset_graph.get_stats()
        self.send_json_response({"success": True, "stats": stats})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_generate(self):
    """POST /api/creative/generate (SSE capable)"""
    data = self.read_json_body()
    task_type = data.get("task_type", "text_to_image")
    params = normalize_params(data.get("params", {}))
    backend = data.get("backend") or params.pop("backend", None)

    try:
        _sse(self, {"status": "starting", "progress": 5,
                    "message": f"Inizializzazione {task_type}...", "backend": backend})

        async def _run_generation():
            if task_type == "text_to_image":
                prompt = params.pop("prompt", "")
                return await image_generator.text_to_image(prompt, backend=backend, **params)
            elif task_type == "img_to_img":
                source_id = params.pop("source_asset_id", None) or params.pop("asset_id", None)
                prompt = params.pop("prompt", "")
                if not source_id:
                    raise ValueError("source_asset_id mancante per img_to_img")
                return await image_generator.image_to_image(source_id, prompt, backend=backend, **params)
            elif task_type == "upscale":
                source_id = params.pop("source_asset_id", None) or params.pop("asset_id", None)
                if not source_id:
                    raise ValueError("source_asset_id mancante per upscale")
                return await image_generator.upscale(source_id, backend=backend, **params)
            else:
                raise ValueError(f"Task type '{task_type}' non supportato (usa text_to_image, img_to_img, upscale)")

        asset = asyncio.run(_run_generation())

        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})

    except Exception as e:
        _fail(self, e, "generazione")


def handle_creative_asset_create(self):
    """POST /api/creative/assets/create"""
    data = self.read_json_body()
    try:
        asset = asset_graph.create_asset(
            type_val=data.get("type"),
            name=data.get("name"),
            metadata=data.get("metadata"),
            source_assets=data.get("source_assets"),
            tags=data.get("tags")
        )
        self.send_json_response({"success": True, "asset": asset.to_dict()})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_asset_update(self):
    """POST /api/creative/assets/update"""
    data = self.read_json_body()
    asset_id = data.get("asset_id")
    if not asset_id:
        return self.send_json_response({"success": False, "error": "asset_id mancante"}, 400)
        
    try:
        kwargs = {k: v for k, v in data.items() if k != "asset_id"}
        asset = asset_graph.update_asset(asset_id, **kwargs)
        self.send_json_response({"success": True, "asset": asset.to_dict()})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_asset_delete(self):
    """POST /api/creative/assets/delete"""
    data = self.read_json_body()
    asset_id = data.get("asset_id")
    if not asset_id:
        return self.send_json_response({"success": False, "error": "asset_id mancante"}, 400)
        
    try:
        success = asset_graph.delete_asset(asset_id)
        self.send_json_response({"success": success})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_backends_config(self):
    """POST /api/creative/backends/config"""
    data = self.read_json_body()
    try:
        # Aggiorna il config.json
        cfg = get_config()
        if "creative" not in cfg:
            cfg["creative"] = {}
        
        if "backends" in data:
            if "backends" not in cfg["creative"]:
                cfg["creative"]["backends"] = {}
            for backend_name, backend_cfg in data["backends"].items():
                if backend_name not in cfg["creative"]["backends"]:
                    cfg["creative"]["backends"][backend_name] = {}
                cfg["creative"]["backends"][backend_name].update(backend_cfg)
                
        for key in ("default_output_dir", "auto_route", "max_resolution", "default_format"):
            if key in data:
                cfg["creative"][key] = data[key]

        save_config(cfg)
        model_router.update_config(cfg["creative"])

        # Il bridge Blender tiene il path in memoria: senza questo refresh la nuova
        # configurazione ha effetto solo al riavvio del server.
        blender_path = cfg["creative"].get("backends", {}).get("blender", {}).get("path", "")
        blender_bridge.blender_path = blender_path or blender_bridge._find_blender()

        self.send_json_response({"success": True, "config": cfg["creative"]})
    except Exception as e:
        _fail(self, e, "config backend")


def handle_creative_upload(self):
    """POST /api/creative/upload"""
    # Questo endpoint nella realtà richiederebbe parsing multipart form-data.
    # Assumiamo arrivi in base64 per semplicità nel POST JSON
    data = self.read_json_body()
    name = data.get("name", "upload")
    img_b64 = data.get("image")

    if not img_b64:
        return self.send_json_response({"success": False, "error": "image base64 mancante"}, 400)

    try:
        import base64
        # La UI invia una data URI (`data:image/png;base64,...`): il prefisso va tolto
        # o i bytes decodificati non sono un'immagine valida.
        payload = img_b64.split(",", 1)[-1] if str(img_b64).startswith("data:") else img_b64
        image_bytes = base64.b64decode(payload)

        asset = asset_graph.create_asset(
            type_val="image", name=name,
            metadata={"operation": "upload", "generator": "user"},
        )
        asset = asset_graph.attach_file(asset.asset_id, "image", "image.png", image_bytes)
        self.send_json_response({"success": True, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "upload")

def handle_creative_edit(self):
    """POST /api/creative/edit"""
    data = self.read_json_body()
    task_type = data.get("task_type")
    asset_id = data.get("asset_id")
    params = data.get("params", {})
    
    if not task_type or not asset_id:
        return self.send_json_response({"success": False, "error": "task_type o asset_id mancante"}, 400)

    params = normalize_params(params)
    try:
        _sse(self, {"status": "starting", "progress": 5, "message": f"Inizializzazione {task_type}..."})

        async def _run():
            if task_type == "inpaint":
                mask = params.pop("mask_data", "")
                prompt = params.pop("prompt", "")
                return await image_editor.inpaint(asset_id, mask, prompt, **params)
            elif task_type == "outpaint":
                direction = params.pop("direction", "all")
                pixels = params.pop("pixels", 128)
                prompt = params.pop("prompt", "")
                return await image_editor.outpaint(asset_id, direction, pixels, prompt, **params)
            elif task_type == "replace_object":
                mask = params.pop("mask_data", "")
                prompt = params.pop("prompt", "")
                return await image_editor.replace_object(asset_id, mask, prompt, **params)
            elif task_type == "style_transfer":
                style = params.pop("style_prompt", "") or params.pop("prompt", "")
                return await image_editor.style_transfer(asset_id, style, params.pop("strength", 0.7), **params)
            elif task_type == "relight":
                return await image_editor.relight(
                    asset_id, params.get("light_direction", "front"), params.get("intensity", 1.0)
                )
            elif task_type == "remove_background":
                return await image_editor.remove_background(asset_id)
            elif task_type == "replace_background":
                prompt = params.pop("prompt", "")
                return await image_editor.replace_background(asset_id, prompt, **params)
            elif task_type == "instruct_edit":
                instruction = params.pop("instruction", "") or params.pop("prompt", "")
                return await image_generator.instruct_edit(asset_id, instruction, **params)
            else:
                raise ValueError(
                    f"Task type '{task_type}' non supportato in edit (inpaint, outpaint, "
                    "replace_object, style_transfer, relight, remove_background, "
                    "replace_background, instruct_edit)"
                )

        asset = asyncio.run(_run())

        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})

    except Exception as e:
        _fail(self, e, "edit")


def handle_creative_remove_bg(self):
    """POST /api/creative/remove-bg"""
    data = self.read_json_body()
    asset_id = data.get("asset_id")
    if not asset_id:
        return self.send_json_response({"success": False, "error": "asset_id mancante"}, 400)
        
    try:
        asset = asyncio.run(image_editor.remove_background(asset_id))
        self.send_json_response({"success": True, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "remove_bg")


def handle_creative_3d(self):
    """POST /api/creative/3d"""
    data = self.read_json_body()
    task_type = data.get("task_type")
    params = data.get("params", {})
    
    if not task_type:
        return self.send_json_response({"success": False, "error": "task_type mancante"}, 400)

    params = normalize_params(params)
    try:
        _sse(self, {"status": "starting", "progress": 5, "message": f"Inizializzazione {task_type}..."})

        async def _run():
            if task_type == "image_to_3d":
                asset_id = params.pop("asset_id", None)
                if not asset_id:
                    raise ValueError("asset_id mancante per image_to_3d")
                return await model_generator_3d.image_to_3d(asset_id, **params)
            elif task_type == "multiview_to_3d":
                asset_ids = params.pop("asset_ids", [])
                return await model_generator_3d.multiview_to_3d(asset_ids, **params)
            elif task_type == "text_to_3d":
                prompt = params.pop("prompt", "")
                return await model_generator_3d.text_to_3d(prompt, **params)
            else:
                raise ValueError(
                    f"Task type '{task_type}' non supportato in 3d (image_to_3d, multiview_to_3d, text_to_3d)"
                )

        asset = asyncio.run(_run())

        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "3D")


def handle_creative_mesh(self):
    """POST /api/creative/mesh"""
    data = self.read_json_body()
    task_type = data.get("task_type")
    asset_id = data.get("asset_id")
    params = data.get("params", {})
    
    if not task_type or not asset_id:
        return self.send_json_response({"success": False, "error": "task_type o asset_id mancante"}, 400)

    params = normalize_params(params)
    try:
        _sse(self, {"status": "starting", "progress": 5, "message": f"Elaborazione mesh: {task_type}..."})

        async def _run():
            if task_type == "cleanup":
                return await mesh_processor.cleanup(asset_id, params)
            elif task_type == "remesh":
                return await mesh_processor.remesh(asset_id, params)
            elif task_type == "decimate":
                return await mesh_processor.decimate(asset_id, params.get("ratio", 0.5))
            elif task_type == "uv_unwrap":
                return await mesh_processor.uv_unwrap(asset_id, params.get("method", "smart_project"))
            elif task_type == "fix_normals":
                return await mesh_processor.fix_normals(asset_id)
            elif task_type == "smooth":
                return await mesh_processor.smooth(asset_id, params.get("iterations", 2))
            elif task_type == "export":
                return await mesh_processor.export(asset_id, params.get("format", "glb"))
            else:
                raise ValueError(
                    f"Task type '{task_type}' non supportato in mesh "
                    "(cleanup, remesh, decimate, uv_unwrap, fix_normals, smooth, export)"
                )

        asset = asyncio.run(_run())

        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "mesh")


def handle_creative_mesh_info(self):
    """GET /api/creative/mesh/info?id=xxx"""
    try:
        qs = parse_qs(urlparse(self.path).query)
        asset_id = qs.get("id", [""])[0]
        if not asset_id:
            return self.send_json_response({"success": False, "error": "ID mancante"}, 400)
            
        info = asyncio.run(mesh_processor.get_mesh_info(asset_id))
        self.send_json_response({"success": True, "info": info})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_material(self):
    """POST /api/creative/material"""
    data = self.read_json_body()
    task_type = data.get("task_type")
    params = data.get("params", {})
    
    if not task_type:
        return self.send_json_response({"success": False, "error": "task_type mancante"}, 400)

    params = normalize_params(params)
    try:
        _sse(self, {"status": "starting", "progress": 5, "message": f"Materiali: {task_type}..."})

        async def _run():
            if task_type == "generate_pbr":
                prompt = params.pop("prompt", "")
                return await texture_generator.generate_pbr(prompt, **params)
            elif task_type == "generate_from_image":
                asset_id = params.pop("asset_id", None)
                if not asset_id:
                    raise ValueError("asset_id mancante per generate_from_image")
                return await texture_generator.generate_from_image(asset_id, **params)
            elif task_type == "make_tileable":
                return await texture_generator.make_tileable(params.get("asset_id"))
            elif task_type == "create_pbr_material":
                return await material_system.create_pbr_material(
                    params.get("textures", {}), params.get("name", "SigmaPBR")
                )
            elif task_type == "apply_to_mesh":
                return await material_system.apply_to_mesh(
                    params.get("mesh_asset_id"), params.get("material_asset_id")
                )
            else:
                raise ValueError(
                    f"Task type '{task_type}' non supportato in material "
                    "(generate_pbr, generate_from_image, make_tileable, create_pbr_material, apply_to_mesh)"
                )

        asset = asyncio.run(_run())

        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "material")


def handle_creative_render(self):
    """POST /api/creative/render"""
    data = self.read_json_body()
    asset_id = data.get("asset_id")
    params = data.get("params", {})
    
    if not asset_id:
        return self.send_json_response({"success": False, "error": "asset_id mancante"}, 400)

    try:
        _sse(self, {"status": "starting", "progress": 5, "message": "Render Blender in corso..."})

        asset = asyncio.run(scene_renderer.render(asset_id, normalize_params(params)))

        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "render")


def handle_creative_pipeline_execute(self):
    """POST /api/creative/pipeline/execute"""
    data = self.read_json_body()
    pipeline_def = data.get("pipeline_def")
    
    if not pipeline_def:
        return self.send_json_response({"success": False, "error": "pipeline_def mancante"}, 400)

    try:
        _sse(self, {"status": "starting", "progress": 0, "message": "Esecuzione pipeline..."})

        def progress_cb(progress_info):
            _sse(self, progress_info)

        async def _run():
            return await pipeline_engine.execute_pipeline(pipeline_def, progress_callback=progress_cb)

        results = asyncio.run(_run())

        serialized_results = [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]
        self.send_json_response({"success": True, "results": serialized_results})
        _sse(self, {"status": "complete", "progress": 100, "results": serialized_results})
    except Exception as e:
        _fail(self, e, "pipeline")


def handle_creative_pipeline_nodes(self):
    """GET /api/creative/pipeline/nodes — tipi di nodo eseguibili e loro porte."""
    try:
        self.send_json_response({
            "success": True,
            "node_types": pipeline_engine.node_types,
            "catalog": NODE_CATALOG,
        })
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_agents_list(self):
    """GET /api/creative/agents"""
    try:
        self.send_json_response({"success": True, "agents": CREATIVE_AGENTS})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_models(self):
    """GET /api/creative/models — registro modelli annotato con la disponibilità."""
    try:
        available = asyncio.run(model_router.available_backend_names())
        ollama_models = asyncio.run(model_router.ollama_models())
        self.send_json_response({
            "success": True,
            "models": model_catalog(available, ollama_models),
            "available_backends": sorted(available),
            "vram_free_gb": available_vram_gb(),
            "workflows": ComfyUIAdapter.workflow_status(),
        })
    except Exception as e:
        log.error(f"Errore catalogo modelli: {e}")
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_creative_discover(self):
    """GET /api/creative/backends/discover — inventario reale dei backend locali.

    Elenca checkpoint, LoRA, VAE, sampler e scheduler realmente installati, così
    la UI può proporre solo ciò che esiste davvero su questa macchina.
    """
    try:
        cfg = model_router.get_config().get("backends", {}).get("comfyui", {})
        url = cfg.get("url") or ""
        detected = asyncio.run(model_router.probe_backend("comfyui"))
        target = url if (cfg.get("enabled") and url) else detected

        if not target:
            return self.send_json_response({
                "success": True, "comfyui": {"reachable": False},
                "message": "ComfyUI non raggiungibile su 127.0.0.1:8188. Avvia ComfyUI Desktop e riprova.",
            })

        inventory = asyncio.run(ComfyUIAdapter(base_url=target, config=cfg).discover())
        self.send_json_response({
            "success": True,
            "comfyui": {
                "reachable": True, "url": target,
                "enabled": bool(cfg.get("enabled")),
                **inventory,
            },
            "workflows": ComfyUIAdapter.workflow_status(),
        })
    except Exception as e:
        _fail(self, e, "discover")


def _models_root() -> str:
    """Cartella models/ di ComfyUI verso cui scaricare."""
    cfg = model_router.get_config().get("backends", {}).get("comfyui", {})
    url = cfg.get("url") or asyncio.run(model_router.probe_backend("comfyui"))
    return discover_models_root(comfy_url=url, configured=cfg.get("models_dir", ""))


def handle_creative_downloads(self):
    """GET /api/creative/downloads — catalogo scaricabile, stato e job in corso."""
    try:
        root = _models_root()
        state = installed_state(root)
        self.send_json_response({
            "success": True,
            "models_root": root,
            "disk_free_gb": disk_free_gb(root) if root else 0,
            "has_token": bool(model_router.get_config().get("hf_token")),
            "catalog": [{**a.to_dict(), **state.get(a.id, {})} for a in DOWNLOAD_CATALOG],
            "jobs": download_manager.list_jobs(),
        })
    except Exception as e:
        _fail(self, e, "downloads")


def _comfy_backend():
    cfg = model_router.get_config().get("backends", {}).get("comfyui", {})
    url = cfg.get("url") or asyncio.run(model_router.probe_backend("comfyui"))
    return get_backend("comfyui", {**cfg, "url": url or "http://127.0.0.1:8188"})


def handle_creative_model_inventory(self):
    """GET /api/creative/models/inventory — i cinque stati dei modelli.

    Separa esplicitamente "il file c'è" da "il backend lo espone": senza questa
    distinzione la stessa schermata mostrava un checkpoint sul disco e zero
    checkpoint disponibili.
    """
    try:
        root = _models_root()
        filesystem = installed_by_category(root) if root else {}

        backend = _comfy_backend()
        reachable = asyncio.run(backend.is_available()) if backend else False
        runtime = asyncio.run(backend.discover_models()) if reachable else None
        if not reachable:
            runtime_tracker.clear_backend("comfyui")

        inventory = build_inventory(filesystem, runtime, "comfyui", reachable)
        stats = asyncio.run(backend.get_system_stats()) if reachable else {}

        self.send_json_response({
            "success": True,
            "models_root": root,
            "disk_free_gb": disk_free_gb(root) if root else 0,
            "backend_stats": stats,
            **inventory,
        })
    except Exception as e:
        _fail(self, e, "inventario modelli")


def handle_creative_workflows(self):
    """GET /api/creative/workflows — registro workflow con stato di prontezza."""
    try:
        root = _models_root()
        cfg = model_router.get_config().get("backends", {}).get("comfyui", {})
        from core.creative.generators.adapters.comfy_workflows import DEFAULT_CHECKPOINTS
        checkpoints = {**DEFAULT_CHECKPOINTS, **(cfg.get("checkpoints") or {})}

        entries = workflow_registry.status(
            installed=installed_by_category(root) if root else {},
            checkpoints=checkpoints,
            vram_gb=available_vram_gb(),
        )
        self.send_json_response({
            "success": True,
            "directory": str(workflow_registry.directory),
            "checkpoints": checkpoints,
            "workflows": entries,
            "capabilities": sorted({w["capability"] for w in entries}),
        })
    except Exception as e:
        _fail(self, e, "registro workflow")


def handle_creative_workflow_save(self):
    """POST /api/creative/workflows/save — registra un workflow dell'utente."""
    data = self.read_json_body()
    try:
        graph = data.get("workflow")
        if isinstance(graph, str):
            graph = json.loads(graph)
        saved = workflow_registry.save(data.get("manifest") or data, graph)
        self.send_json_response({"success": True, "workflow": saved.to_dict()})
    except Exception as e:
        _fail(self, e, "salvataggio workflow", 400)


def handle_creative_workflow_delete(self):
    """POST /api/creative/workflows/delete — rimuove un workflow dell'utente."""
    data = self.read_json_body()
    workflow_id = data.get("id", "")
    removed = workflow_registry.delete(workflow_id)
    self.send_json_response(
        {"success": removed,
         "error": "" if removed else "Workflow non trovato o fornito da Sigma (non rimovibile)"},
        200 if removed else 400)


def handle_creative_model_search(self):
    """GET /api/creative/models/search — cerca su Hugging Face e Civitai.

    `category` decide sia i filtri di ricerca sia la cartella di destinazione:
    è ciò che rende un risultato immediatamente scaricabile e utilizzabile.
    """
    try:
        qs = parse_qs(urlparse(self.path).query)
        query = qs.get("q", [""])[0]
        category = qs.get("category", [""])[0]
        limit = max(1, min(40, int(qs.get("limit", [15])[0])))
        sources = tuple(s for s in qs.get("source", ["huggingface,civitai"])[0].split(",") if s)

        cfg = model_router.get_config()
        result = model_hub.search(
            query=query, category_id=category, sources=sources, limit=limit,
            hf_token=cfg.get("hf_token", ""), civitai_token=cfg.get("civitai_token", ""),
        )

        root = _models_root()
        installed = {f["filename"] for cat in installed_by_category(root).values() for f in cat["files"]} if root else set()
        for item in result["results"]:
            for f in item["files"]:
                f["installed"] = f["filename"] in installed

        self.send_json_response({"success": True, **result, "models_root": root})
    except Exception as e:
        _fail(self, e, "ricerca modelli")


def handle_creative_model_categories(self):
    """GET /api/creative/models/categories — categorie e modelli già installati."""
    try:
        root = _models_root()
        self.send_json_response({
            "success": True,
            "models_root": root,
            "disk_free_gb": disk_free_gb(root) if root else 0,
            "categories": [
                {"id": c.id, "label": c.label, "folder": c.folder,
                 "description": c.description,
                 "sources": [s for s, ok in (("huggingface", True), ("civitai", bool(c.civitai_types))) if ok]}
                for c in model_hub.CATEGORIES
            ],
            "installed": installed_by_category(root) if root else {},
            "has_hf_token": bool(model_router.get_config().get("hf_token")),
            "has_civitai_token": bool(model_router.get_config().get("civitai_token")),
        })
    except Exception as e:
        _fail(self, e, "categorie modelli")


def handle_creative_download_start(self):
    """POST /api/creative/downloads/start — catalogo curato o risultato di ricerca."""
    data = self.read_json_body()

    # Download diretto da una ricerca: la voce non sta nel catalogo curato.
    if data.get("file"):
        try:
            root = _models_root()
            if not root:
                raise RuntimeError("Cartella modelli di ComfyUI non trovata.")
            asset = custom_asset(data["file"])
            token = model_router.get_config().get(
                "civitai_token" if data["file"].get("source") == "civitai" else "hf_token", "")
            # Civitai autentica via query string, già inclusa nell'URL di ricerca.
            job = download_manager.start(asset, root, "" if data["file"].get("source") == "civitai" else token)
            return self.send_json_response({"success": True, "jobs": [job.to_dict()], "models_root": root})
        except Exception as e:
            return _fail(self, e, "download start", 400 if isinstance(e, ValueError) else 500)

    asset_id = data.get("asset_id")
    asset = CATALOG_BY_ID.get(asset_id)
    if not asset:
        return self.send_json_response(
            {"success": False, "error": f"Voce '{asset_id}' non presente nel catalogo"}, 400)

    try:
        root = _models_root()
        if not root:
            raise RuntimeError(
                "Cartella modelli di ComfyUI non trovata. Avvia ComfyUI oppure imposta "
                "backends.comfyui.models_dir in Impostazioni → Creative."
            )

        # Le dipendenze (text encoder, VAE) partono insieme al modello: senza,
        # il workflow fallirebbe comunque al primo caricamento.
        started = []
        token = model_router.get_config().get("hf_token", "")
        for dep_id in (*asset.requires, asset.id) if data.get("with_dependencies", True) else (asset.id,):
            dep = CATALOG_BY_ID.get(dep_id)
            if not dep:
                continue
            if installed_state(root).get(dep_id, {}).get("installed") and dep_id != asset.id:
                continue
            started.append(download_manager.start(dep, root, token).to_dict())

        self.send_json_response({"success": True, "jobs": started, "models_root": root})
    except Exception as e:
        _fail(self, e, "download start")


def handle_creative_download_cancel(self):
    """POST /api/creative/downloads/cancel — annulla un job e ripulisce il parziale."""
    data = self.read_json_body()
    job_id = data.get("job_id")
    try:
        cancelled = download_manager.cancel(job_id)
        if data.get("discard_partial"):
            job = download_manager.jobs.get(job_id)
            asset = CATALOG_BY_ID.get(job.asset_id) if job else None
            if asset:
                download_manager.cleanup_partial(asset, _models_root())
        self.send_json_response({"success": cancelled,
                                 "error": "" if cancelled else "Job non attivo"})
    except Exception as e:
        _fail(self, e, "download cancel")


def handle_creative_vision(self):
    """POST /api/creative/vision — describe | analyze | score | compare | ocr."""
    data = self.read_json_body()
    task_type = data.get("task_type", "analyze")
    params = data.get("params", {})
    asset_id = data.get("asset_id") or params.get("asset_id")

    try:
        async def _run():
            if not await vision_agent.available():
                raise RuntimeError(
                    f"Modello vision non disponibile. Avvia Ollama e installa il modello: "
                    f"ollama pull {vision_agent.model}"
                )
            if task_type == "describe":
                return await vision_agent.describe(asset_id, params.get("question"))
            if task_type == "analyze":
                return await vision_agent.analyze(asset_id)
            if task_type == "score":
                return await vision_agent.score(asset_id, params.get("intent", ""))
            if task_type == "ocr":
                return await vision_agent.extract_text(asset_id)
            if task_type == "compare":
                return await vision_agent.compare(params.get("asset_a"), params.get("asset_b"),
                                                 params.get("criteria", ""))
            raise ValueError(f"Task type '{task_type}' non supportato (describe, analyze, score, ocr, compare)")

        if task_type != "compare" and not asset_id:
            return self.send_json_response({"success": False, "error": "asset_id mancante"}, 400)

        result = asyncio.run(_run())
        self.send_json_response({"success": True, "result": result})
    except Exception as e:
        _fail(self, e, "vision")


def handle_creative_segment(self):
    """POST /api/creative/segment — maschera SAM 2 (o fallback) come asset."""
    data = self.read_json_body()
    asset_id = data.get("asset_id")
    if not asset_id:
        return self.send_json_response({"success": False, "error": "asset_id mancante"}, 400)

    try:
        asset = asyncio.run(image_editor.segment(asset_id, (data.get("params") or {}).get("prompt", "")))
        self.send_json_response({"success": True, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "segment")


def handle_creative_video(self):
    """POST /api/creative/video — text_to_video | image_to_video."""
    data = self.read_json_body()
    task_type = data.get("task_type", "image_to_video")
    params = normalize_params(data.get("params", {}))

    try:
        _sse(self, {"status": "starting", "progress": 3, "message": f"Video: {task_type}..."})

        async def _run():
            if task_type == "text_to_video":
                prompt = params.pop("prompt", "")
                return await video_generator.text_to_video(prompt, **params)
            if task_type == "image_to_video":
                asset_id = params.pop("asset_id", None)
                if not asset_id:
                    raise ValueError("asset_id mancante per image_to_video")
                prompt = params.pop("prompt", "")
                return await video_generator.image_to_video(asset_id, prompt, **params)
            raise ValueError(f"Task type '{task_type}' non supportato (text_to_video, image_to_video)")

        asset = asyncio.run(_run())
        self.send_json_response({"success": True, "asset": asset.to_dict()})
        _sse(self, {"status": "complete", "progress": 100, "asset": asset.to_dict()})
    except Exception as e:
        _fail(self, e, "video")


# Descrizione dei nodi per la palette del node editor: porte e parametri devono
# combaciare con gli executor di CreativePipelineEngine.
NODE_CATALOG = [
    {"type": "prompt", "label": "Prompt", "category": "Input", "color": "#7c8cff",
     "inputs": [], "outputs": ["text"], "params": {"prompt": ""}},
    {"type": "asset_input", "label": "Asset dal Vault", "category": "Input", "color": "#7c8cff",
     "inputs": [], "outputs": ["image", "mesh"], "params": {"asset_id": ""}},
    {"type": "image_generate", "label": "Image Generate", "category": "Generate", "color": "#00d2ff",
     "inputs": ["prompt"], "outputs": ["image"],
     "params": {"negative_prompt": "", "width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7, "seed": -1}},
    {"type": "image_to_image", "label": "Image to Image", "category": "Generate", "color": "#00d2ff",
     "inputs": ["image", "prompt"], "outputs": ["image"], "params": {"strength": 0.7}},
    {"type": "upscale", "label": "Upscale", "category": "Generate", "color": "#00d2ff",
     "inputs": ["image"], "outputs": ["image"], "params": {"scale": 2}},
    {"type": "image_edit", "label": "Image Edit", "category": "Edit", "color": "#ff9f43",
     "inputs": ["image", "prompt"], "outputs": ["image"],
     "params": {"operation": "outpaint", "direction": "all", "pixels": 128}},
    {"type": "instruct_edit", "label": "Instruct Edit (Kontext/Qwen)", "category": "Edit", "color": "#ff9f43",
     "inputs": ["image", "instruction"], "outputs": ["image"],
     "params": {"instruction": "", "strength": 0.8}},
    {"type": "bg_remove", "label": "Background Remove", "category": "Edit", "color": "#ff9f43",
     "inputs": ["image"], "outputs": ["image"], "params": {}},
    {"type": "bg_replace", "label": "Background Replace", "category": "Edit", "color": "#ff9f43",
     "inputs": ["image", "prompt"], "outputs": ["image"], "params": {"prompt": ""}},
    {"type": "segment", "label": "Segment (SAM 2)", "category": "Edit", "color": "#ff9f43",
     "inputs": ["image"], "outputs": ["mask"], "params": {"prompt": ""}},
    {"type": "relight", "label": "Relight", "category": "Edit", "color": "#ff9f43",
     "inputs": ["image"], "outputs": ["image"], "params": {"light_direction": "front", "intensity": 1.0}},
    {"type": "vision_analyze", "label": "Vision Analyze", "category": "Agents", "color": "#5ef2c1",
     "inputs": ["image"], "outputs": ["image", "text"], "params": {}},
    {"type": "quality_gate", "label": "Quality Gate", "category": "Agents", "color": "#5ef2c1",
     "inputs": ["image", "intent"], "outputs": ["image"],
     "params": {"intent": "", "threshold": 0.6, "strict": True}},
    {"type": "image_to_3d", "label": "Image to 3D", "category": "3D", "color": "#a06bff",
     "inputs": ["image"], "outputs": ["mesh"], "params": {}},
    {"type": "text_to_3d", "label": "Text to 3D", "category": "3D", "color": "#a06bff",
     "inputs": ["prompt"], "outputs": ["mesh"], "params": {}},
    {"type": "multiview_to_3d", "label": "Multi-view to 3D", "category": "3D", "color": "#a06bff",
     "inputs": ["view_1", "view_2", "view_3", "view_4"], "outputs": ["mesh"], "params": {}},
    {"type": "mesh_cleanup", "label": "Mesh Cleanup", "category": "Mesh", "color": "#3fb950",
     "inputs": ["mesh"], "outputs": ["mesh"], "params": {"merge_distance": 0.001}},
    {"type": "decimate", "label": "Decimate", "category": "Mesh", "color": "#3fb950",
     "inputs": ["mesh"], "outputs": ["mesh"], "params": {"ratio": 0.5}},
    {"type": "uv_unwrap", "label": "UV Unwrap", "category": "Mesh", "color": "#3fb950",
     "inputs": ["mesh"], "outputs": ["mesh"], "params": {"method": "smart_project"}},
    {"type": "texture_gen", "label": "Texture PBR", "category": "Materials", "color": "#ffd166",
     "inputs": ["prompt", "image"], "outputs": ["material"], "params": {"resolution": 1024}},
    {"type": "material", "label": "Apply Material", "category": "Materials", "color": "#ffd166",
     "inputs": ["mesh", "material"], "outputs": ["mesh"], "params": {}},
    {"type": "text_to_video", "label": "Text to Video", "category": "Video", "color": "#f472b6",
     "inputs": ["prompt"], "outputs": ["video"],
     "params": {"num_frames": 97, "fps": 24}},
    {"type": "image_to_video", "label": "Image to Video", "category": "Video", "color": "#f472b6",
     "inputs": ["image", "prompt"], "outputs": ["video"],
     "params": {"num_frames": 97, "fps": 24}},
    {"type": "render", "label": "Render", "category": "Output", "color": "#ff6b6b",
     "inputs": ["scene"], "outputs": ["image"],
     "params": {"engine": "cycles", "width": 1920, "height": 1080, "samples": 128}},
    {"type": "export", "label": "Export", "category": "Output", "color": "#ff6b6b",
     "inputs": ["asset"], "outputs": [], "params": {"format": "keep"}},
]
