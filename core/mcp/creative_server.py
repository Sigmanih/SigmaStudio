# ==============================================================================
# core/mcp/creative_server.py — Creative Studio MCP Server
# Generazione immagini, editing, 3D, materiali, video e pipeline per gli agenti
# ==============================================================================
"""Espone il Creative Studio come strumenti MCP.

Gli agenti della chat non parlano con i modelli: parlano con Sigma. Chiedono
«genera un'immagine di X» e il router sceglie backend e modello, l'asset finisce
nel vault con la sua provenienza, e la risposta contiene l'URL già visualizzabile
in chat.

Tutti i tool sono SAFE: producono asset dentro `data/creative/`, non toccano
nulla fuori da Sigma Studio e non spendono denaro se non sono configurate API a
pagamento — l'unico caso in cui l'utente ha già espresso il consenso mettendo la
propria chiave in configurazione.
"""

import asyncio

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE

log = get_logger(__name__)


def _run(coro):
    """Esegue una coroutine da un handler sincrono MCP.

    L'hub invoca i tool in un thread senza event loop: `asyncio.run` è corretto
    qui e sbagliato dentro il loop di FastAPI, dove i router usano to_thread.
    """
    return asyncio.run(coro)


class CreativeMCPServer(BaseMCPServer):
    integration_key = "creative"

    def __init__(self):
        super().__init__(
            name="Creative MCP",
            version="1.0.0",
            description="Generazione immagini, editing, 3D, materiali, video e pipeline creative",
        )
        self._init_tools()
        self._init_resources()

    # ------------------------------------------------------------------
    # Accesso pigro ai singleton del Creative Studio
    # ------------------------------------------------------------------

    @property
    def _cs(self):
        # Import differito: il modulo apre il DB degli asset, non deve farlo
        # all'avvio dell'hub se nessuno usa gli strumenti creativi.
        import core.creative.creative_router as router
        return router

    @staticmethod
    def _asset_payload(asset, extra: dict = None) -> dict:
        data = asset.to_dict()
        payload = {
            "success": True,
            "asset_id": data["asset_id"],
            "name": data["name"],
            "type": data["type"],
            "url": data["url"],
            "model": data.get("model"),
            "generator": data.get("generator"),
        }
        if data.get("model_url"):
            payload["model_url"] = data["model_url"]
        if data.get("video_url"):
            payload["video_url"] = data["video_url"]
        payload.update(extra or {})
        return payload

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def _init_tools(self):
        self.register_tool(
            name="generate_image",
            description=(
                "Genera un'immagine da un prompt testuale. Sigma sceglie il modello migliore "
                "(FLUX, SDXL, Qwen-Image...) in base ai backend attivi e alla VRAM, salvo indicazione "
                "esplicita. Ritorna l'URL dell'immagine e l'asset_id da usare negli altri strumenti."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Descrizione di cosa generare"},
                    "negative_prompt": {"type": "string", "description": "Cosa evitare", "default": ""},
                    "width": {"type": "integer", "description": "Larghezza in px", "default": 1024},
                    "height": {"type": "integer", "description": "Altezza in px", "default": 1024},
                    "steps": {"type": "integer", "default": 30},
                    "cfg_scale": {"type": "number", "default": 7.0},
                    "seed": {"type": "integer", "description": "-1 per casuale", "default": -1},
                    "model_id": {"type": "string", "description": "Forza un modello del registro (es. 'flux.1-dev')"},
                    "priority": {"type": "string", "enum": ["quality", "balanced", "speed"], "default": "balanced"},
                },
                "required": ["prompt"],
            },
            handler=self._handle_generate_image,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="edit_image",
            description=(
                "Modifica un'immagine del vault: rimozione sfondo, sostituzione sfondo, outpaint, "
                "relight, style transfer o istruzione in linguaggio naturale (instruct_edit)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "Asset immagine da modificare"},
                    "operation": {
                        "type": "string",
                        "enum": ["remove_background", "replace_background", "outpaint",
                                 "relight", "style_transfer", "instruct_edit"],
                    },
                    "prompt": {"type": "string", "description": "Istruzione o descrizione, secondo l'operazione"},
                    "direction": {"type": "string", "description": "Solo outpaint: all|top|bottom|left|right"},
                    "pixels": {"type": "integer", "description": "Solo outpaint: px da aggiungere", "default": 128},
                },
                "required": ["asset_id", "operation"],
            },
            handler=self._handle_edit_image,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="upscale_image",
            description="Aumenta la risoluzione di un'immagine. Con restore=true usa un modello di "
                        "ricostruzione generativa (SUPIR) invece di un interpolatore.",
            input_schema={
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "scale": {"type": "integer", "default": 2},
                    "restore": {"type": "boolean", "description": "Sorgente degradata", "default": False},
                },
                "required": ["asset_id"],
            },
            handler=self._handle_upscale_image,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="analyze_image",
            description="Analizza un'immagine con il modello vision locale: soggetto, stile, difetti, "
                        "punteggio di qualità. Con intent valuta quanto l'immagine rispetta la richiesta.",
            input_schema={
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "question": {"type": "string", "description": "Domanda specifica sull'immagine"},
                    "intent": {"type": "string", "description": "Cosa doveva rappresentare, per il punteggio"},
                },
                "required": ["asset_id"],
            },
            handler=self._handle_analyze_image,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="generate_3d",
            description="Crea un modello 3D da un'immagine del vault o da un prompt testuale. "
                        "Ritorna l'URL del file GLB.",
            input_schema={
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "Immagine sorgente (image→3D)"},
                    "prompt": {"type": "string", "description": "Descrizione (text→3D, genera prima la vista)"},
                },
            },
            handler=self._handle_generate_3d,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="generate_material",
            description="Genera un materiale PBR completo (albedo, normal, roughness, metallic, height, AO) "
                        "da un prompt o da un'immagine esistente.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Descrizione del materiale"},
                    "asset_id": {"type": "string", "description": "Immagine da cui derivare le mappe"},
                    "resolution": {"type": "integer", "default": 1024},
                },
            },
            handler=self._handle_generate_material,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="generate_video",
            description="Genera un video da un prompt o animando un'immagine del vault.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "asset_id": {"type": "string", "description": "Immagine di partenza (image→video)"},
                    "num_frames": {"type": "integer", "default": 97},
                    "fps": {"type": "integer", "default": 24},
                },
            },
            handler=self._handle_generate_video,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="render_3d",
            description="Renderizza un asset 3D con Blender (Cycles/Eevee) e ritorna l'immagine.",
            input_schema={
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "engine": {"type": "string", "enum": ["cycles", "eevee"], "default": "cycles"},
                    "width": {"type": "integer", "default": 1280},
                    "height": {"type": "integer", "default": 720},
                    "samples": {"type": "integer", "default": 96},
                },
                "required": ["asset_id"],
            },
            handler=self._handle_render_3d,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="run_creative_pipeline",
            description=(
                "Esegue una pipeline creativa a nodi (DAG). Usalo per catene multi-passo: "
                "prompt → immagine → scontorno → 3D → render. Consulta list_creative_capabilities "
                "per i tipi di nodo e le loro porte."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "description": "[{node_id, node_type, params}]",
                        "items": {"type": "object"},
                    },
                    "connections": {
                        "type": "array",
                        "description": "[{from_node, from_port, to_node, to_port}]",
                        "items": {"type": "object"},
                    },
                },
                "required": ["nodes"],
            },
            handler=self._handle_run_pipeline,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="list_creative_assets",
            description="Elenca gli asset del vault creativo, opzionalmente filtrati per tipo.",
            input_schema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "image|model_3d|mesh|material|video|texture"},
                    "limit": {"type": "integer", "default": 20},
                    "query": {"type": "string", "description": "Ricerca testuale su nome e metadata"},
                },
            },
            handler=self._handle_list_assets,
            safety=SAFE, category="creative",
        )

        self.register_tool(
            name="list_creative_capabilities",
            description="Cosa può fare il Creative Studio ora: backend attivi, modelli disponibili, "
                        "tipi di nodo della pipeline. Consultalo prima di promettere una capacità all'utente.",
            input_schema={"type": "object", "properties": {}},
            handler=self._handle_capabilities,
            safety=SAFE, category="creative",
        )

    def _init_resources(self):
        self.register_resource(
            uri="creative://assets",
            name="Creative Asset Vault",
            description="Asset generati: immagini, mesh, materiali, video, con provenienza",
            mime_type="application/json",
            handler=lambda: self._handle_list_assets(limit=50),
        )
        self.register_resource(
            uri="creative://models",
            name="Registro modelli creativi",
            description="Modelli disponibili per generazione, editing, 3D e video",
            mime_type="application/json",
            handler=lambda: self._handle_capabilities(),
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_generate_image(self, prompt: str, **kwargs):
        try:
            cs = self._cs
            params = {k: v for k, v in kwargs.items() if v is not None}
            asset = _run(cs.image_generator.text_to_image(prompt, **params))
            return self._asset_payload(asset, {"prompt": prompt})
        except Exception as e:
            log.error(f"generate_image fallita: {e}")
            return {"success": False, "error": str(e)}

    def _handle_edit_image(self, asset_id: str, operation: str, **kwargs):
        try:
            cs = self._cs
            prompt = kwargs.get("prompt", "")
            if operation == "remove_background":
                asset = _run(cs.image_editor.remove_background(asset_id))
            elif operation == "replace_background":
                asset = _run(cs.image_editor.replace_background(asset_id, prompt))
            elif operation == "outpaint":
                asset = _run(cs.image_editor.outpaint(
                    asset_id, kwargs.get("direction", "all"), kwargs.get("pixels", 128), prompt))
            elif operation == "relight":
                asset = _run(cs.image_editor.relight(asset_id, kwargs.get("direction", "front")))
            elif operation == "style_transfer":
                asset = _run(cs.image_editor.style_transfer(asset_id, prompt))
            elif operation == "instruct_edit":
                asset = _run(cs.image_generator.instruct_edit(asset_id, prompt))
            else:
                return {"success": False, "error": f"Operazione '{operation}' non supportata"}
            return self._asset_payload(asset, {"operation": operation})
        except Exception as e:
            log.error(f"edit_image fallita: {e}")
            return {"success": False, "error": str(e)}

    def _handle_upscale_image(self, asset_id: str, scale: int = 2, restore: bool = False):
        try:
            asset = _run(self._cs.image_generator.upscale(asset_id, scale=scale, restore=restore))
            return self._asset_payload(asset, {"scale": scale, "restore": restore})
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_analyze_image(self, asset_id: str, question: str = "", intent: str = ""):
        try:
            agent = self._cs.vision_agent
            if not _run(agent.available()):
                return {"success": False,
                        "error": f"Modello vision non disponibile. Esegui: ollama pull {agent.model}"}
            if intent:
                result = _run(agent.score(asset_id, intent))
            elif question:
                result = _run(agent.describe(asset_id, question))
            else:
                result = _run(agent.analyze(asset_id))
            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_generate_3d(self, asset_id: str = "", prompt: str = ""):
        try:
            cs = self._cs
            if asset_id:
                asset = _run(cs.model_generator_3d.image_to_3d(asset_id))
            elif prompt:
                asset = _run(cs.model_generator_3d.text_to_3d(prompt))
            else:
                return {"success": False, "error": "Serve asset_id (immagine) oppure prompt"}
            return self._asset_payload(asset)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_generate_material(self, prompt: str = "", asset_id: str = "", resolution: int = 1024):
        try:
            cs = self._cs
            if asset_id:
                asset = _run(cs.texture_generator.generate_from_image(asset_id, resolution=resolution))
            elif prompt:
                asset = _run(cs.texture_generator.generate_pbr(prompt, resolution=resolution))
            else:
                return {"success": False, "error": "Serve prompt oppure asset_id"}
            return self._asset_payload(asset, {"maps": list(asset.files.keys())})
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_generate_video(self, prompt: str = "", asset_id: str = "", **kwargs):
        try:
            cs = self._cs
            params = {k: v for k, v in kwargs.items() if v is not None}
            if asset_id:
                asset = _run(cs.video_generator.image_to_video(asset_id, prompt, **params))
            elif prompt:
                asset = _run(cs.video_generator.text_to_video(prompt, **params))
            else:
                return {"success": False, "error": "Serve prompt oppure asset_id"}
            return self._asset_payload(asset)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_render_3d(self, asset_id: str, **kwargs):
        try:
            params = {k: v for k, v in kwargs.items() if v is not None}
            asset = _run(self._cs.scene_renderer.render(asset_id, params))
            return self._asset_payload(asset)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_run_pipeline(self, nodes: list, connections: list = None):
        try:
            steps = []
            results = _run(self._cs.pipeline_engine.execute_pipeline(
                {"nodes": nodes, "connections": connections or []},
                progress_callback=lambda info: steps.append(info),
            ))
            return {
                "success": True,
                "outputs": [self._asset_payload(a) for a in results],
                "steps": [s for s in steps if s.get("status") == "node_complete"],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_list_assets(self, type: str = None, limit: int = 20, query: str = ""):
        try:
            graph = self._cs.asset_graph
            assets = graph.search_assets(query) if query else graph.list_assets(type_filter=type, limit=limit)
            return {
                "success": True,
                "count": len(assets),
                "assets": [{
                    "asset_id": a.asset_id, "name": a.name, "type": a.type.value,
                    "url": a.to_dict()["url"], "created_at": a.created_at,
                    "sources": a.source_assets,
                } for a in assets[:limit]],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_capabilities(self):
        try:
            cs = self._cs
            from core.creative.model_registry import available_vram_gb, catalog
            backends = _run(cs.model_router.available_backend_names())
            ollama = _run(cs.model_router.ollama_models())
            models = catalog(backends, ollama)
            usable = [m for m in models if m["available"]]
            tasks = sorted({t for m in usable for t in m["tasks"]})
            return {
                "success": True,
                "backends": sorted(backends),
                "vram_free_gb": available_vram_gb(),
                "supported_tasks": tasks,
                "models": [{"id": m["id"], "label": m["label"], "tasks": m["tasks"],
                            "via": m["available_via"]} for m in usable],
                "pipeline_node_types": cs.pipeline_engine.node_types,
                "blender": cs.blender_bridge.available,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
