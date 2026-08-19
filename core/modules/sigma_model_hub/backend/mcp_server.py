# ==============================================================================
# core/modules/sigma_model_hub/backend/mcp_server.py
# Model Hub & Hugging Face MCP Server for Autonomous AI Agents
# ==============================================================================
from __future__ import annotations
from typing import Dict, Any, List
from core.logger import get_logger
from .hf_client import search_hf_models, get_hf_model_details
from .downloader_engine import downloader_manager
from .model_inventory import scan_local_models, deploy_model_to_sigma_engine, unload_sigma_engine_model

log = get_logger(__name__)


class ModelHubMCPServer:
    """MCP Server exposing model hub, discovery and deployment tools to agents."""

    name = "model_hub"
    description = "Cerca, scarica modelli GGUF/Safetensors da Hugging Face e avviali direttamente in SigmaEngine."

    @staticmethod
    def get_tools() -> List[Dict[str, Any]]:
        return [
            {
                "name": "search_hf_models",
                "description": "Cerca modelli di intelligenza artificiale su Hugging Face (LLM, MoE, Code, Vision, Audio, Reasoning).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Termine di ricerca o architettura (es. 'DeepSeek-R1-Distill-Qwen', 'Qwen2.5-Coder', 'Llama-3.1')."},
                        "category": {"type": "string", "enum": ["all", "llm", "moe", "code", "vision", "audio", "reasoning"], "default": "all"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "download_hf_model",
                "description": "Avvia il download asincrono in streaming di un file modello (.gguf, .safetensors) da Hugging Face nella directory locale.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model_id": {"type": "string", "description": "ID del repository su Hugging Face (es. 'bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF')."},
                        "filename": {"type": "string", "description": "Nome del file specifico da scaricare (es. 'DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf')."}
                    },
                    "required": ["model_id", "filename"]
                }
            },
            {
                "name": "list_local_models",
                "description": "Elenca tutti i modelli scaricati in locale e pronti per essere utilizzati con SigmaEngine.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "deploy_to_sigma_engine",
                "description": "Carica e attiva un modello locale in SigmaEngine partizionandolo in modo ottimale su GPU e RAM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model_path": {"type": "string", "description": "Percorso assoluto del file modello locale."}
                    },
                    "required": ["model_path"]
                }
            }
        ]

    @staticmethod
    async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "search_hf_models":
            q = arguments.get("query", "")
            cat = arguments.get("category", "all")
            results = search_hf_models(query=q, category=cat)
            return {"success": True, "results": results}

        elif name == "download_hf_model":
            mid = arguments.get("model_id")
            fname = arguments.get("filename")
            task = downloader_manager.start_download(model_id=mid, filename=fname)
            return {"success": True, "task": task}

        elif name == "list_local_models":
            models = scan_local_models()
            return {"success": True, "models": models}

        elif name == "deploy_to_sigma_engine":
            path = arguments.get("model_path")
            res = deploy_model_to_sigma_engine(model_path=path)
            return res

        return {"success": False, "error": f"Tool sconosciuto: {name}"}
