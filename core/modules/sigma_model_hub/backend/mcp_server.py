# ==============================================================================
# core/modules/sigma_model_hub/backend/mcp_server.py
# Model Hub & Hugging Face MCP Server for Autonomous AI Agents
# ==============================================================================
from __future__ import annotations
from typing import Dict, Any, List, Optional
from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from .hf_client import search_hf_models, get_hf_model_details
from .downloader_engine import downloader_manager
from .model_inventory import scan_local_models, deploy_model_to_sigma_engine, unload_sigma_engine_model

log = get_logger(__name__)


class ModelHubMCPServer(BaseMCPServer):
    """MCP Server exposing model hub, discovery and deployment tools to agents."""

    def __init__(self):
        super().__init__(
            name="Model Hub",
            version="1.0.0",
            description="Cerca, scarica modelli GGUF/Safetensors da Hugging Face e avviali direttamente in SigmaEngine."
        )
        self.register_tool(
            name="search_hf_models",
            description="Cerca modelli di intelligenza artificiale su Hugging Face (LLM, MoE, Code, Vision, Audio, Reasoning).",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termine di ricerca o architettura (es. 'DeepSeek-R1-Distill-Qwen', 'Qwen2.5-Coder', 'Llama-3.1')."},
                    "category": {"type": "string", "enum": ["all", "llm", "moe", "code", "vision", "audio", "reasoning"], "default": "all"}
                },
                "required": ["query"]
            },
            handler=self._tool_search_hf,
            safety=SAFE,
            category="models"
        )
        self.register_tool(
            name="download_hf_model",
            description="Avvia il download asincrono in streaming di un file modello (.gguf, .safetensors) da Hugging Face nella directory locale.",
            input_schema={
                "type": "object",
                "properties": {
                    "model_id": {"type": "string", "description": "ID del repository su Hugging Face (es. 'Qwen/Qwen2.5-Coder-14B-Instruct-GGUF' o 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B')."},
                    "filename": {"type": "string", "description": "Nome del file specifico da scaricare (es. 'qwen2.5-coder-14b-instruct-q4_k_m.gguf')."}
                },
                "required": ["model_id", "filename"]
            },
            handler=self._tool_download_hf,
            safety=SENSITIVE,
            category="models"
        )
        self.register_tool(
            name="list_local_models",
            description="Elenca tutti i modelli scaricati in locale e pronti per essere utilizzati con SigmaEngine.",
            input_schema={"type": "object", "properties": {}},
            handler=self._tool_list_local,
            safety=SAFE,
            category="models"
        )
        self.register_tool(
            name="deploy_to_sigma_engine",
            description="Carica e attiva un modello locale in SigmaEngine partizionandolo in modo ottimale su GPU e RAM.",
            input_schema={
                "type": "object",
                "properties": {
                    "model_path": {"type": "string", "description": "Percorso assoluto del file modello locale."}
                },
                "required": ["model_path"]
            },
            handler=self._tool_deploy,
            safety=SENSITIVE,
            category="models"
        )

    def _tool_search_hf(self, query: str = "", category: str = "all", **kwargs) -> Dict[str, Any]:
        results = search_hf_models(query=query, category=category)
        return {"success": True, "results": results}

    def _tool_download_hf(self, model_id: str = "", filename: str = "", **kwargs) -> Dict[str, Any]:
        task = downloader_manager.start_download(model_id=model_id, filename=filename)
        return {"success": True, "task": task}

    def _tool_list_local(self, **kwargs) -> Dict[str, Any]:
        models = scan_local_models()
        return {"success": True, "models": models}

    def _tool_deploy(self, model_path: str = "", **kwargs) -> Dict[str, Any]:
        return deploy_model_to_sigma_engine(model_path=model_path)

    # Legacy compatibility methods
    @staticmethod
    def get_tools() -> List[Dict[str, Any]]:
        server = ModelHubMCPServer()
        return server.list_tools()

    @staticmethod
    async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        server = ModelHubMCPServer()
        return server.call_tool(name, arguments)
