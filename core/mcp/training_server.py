# ==============================================================================
# core/mcp/training_server.py — Training MCP Server
# Datasets, Tokenizers, LoRA Training Jobs & Checkpoints Export
# ==============================================================================
import os
import json
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from core.logger import get_logger

log = get_logger(__name__)


class TrainingMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="Training MCP",
            version="1.0.0",
            description="Dataset import, tokenization, LoRA fine-tuning training jobs, and checkpoint exports"
        )
        self._init_tools()
        self._init_resources()

    def _init_tools(self):
        self.register_tool(
            name="import_dataset",
            description="Import and validate a training dataset (JSONL or HuggingFace format).",
            input_schema={
                "type": "object",
                "properties": {
                    "dataset_name": {"type": "string", "description": "Dataset identifier"},
                    "data_path": {"type": "string", "description": "Local path or HuggingFace repo ID"}
                },
                "required": ["dataset_name", "data_path"]
            },
            handler=self._handle_import_dataset,
            safety=SENSITIVE,
            category="training",
        )

        self.register_tool(
            name="start_lora_training",
            description="Initialize and start a LoRA / QLoRA fine-tuning job.",
            input_schema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "base_model": {"type": "string", "description": "Base model identifier"},
                    "dataset_id": {"type": "string", "description": "Dataset ID to train on"},
                    "epochs": {"type": "integer", "default": 3}
                },
                "required": ["job_name", "base_model", "dataset_id"]
            },
            handler=self._handle_start_lora_training,
            safety=SENSITIVE,
            category="training",
        )

        self.register_tool(
            name="export_ollama_model",
            description="Export trained model checkpoint to Modelfile for local Ollama inference.",
            input_schema={
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string", "description": "Training checkpoint ID"},
                    "target_model_name": {"type": "string", "description": "Target Ollama model name"}
                },
                "required": ["checkpoint_id", "target_model_name"]
            },
            handler=self._handle_export_ollama_model,
            safety=SENSITIVE,
            category="training",
        )

    def _init_resources(self):
        self.register_resource(
            uri="training://datasets/list",
            name="Imported Datasets List",
            description="List of all registered fine-tuning datasets",
            mime_type="application/json",
            handler=self._read_datasets_list
        )
        self.register_resource(
            uri="training://jobs/active",
            name="Active Fine-Tuning Jobs",
            description="Status of active and past training jobs",
            mime_type="application/json",
            handler=self._read_active_jobs
        )

    def _handle_import_dataset(self, dataset_name: str = "sample_dataset", data_path: str = "training/datasets/sample.jsonl", **kwargs):
        try:
            from core.training.datasets import import_dataset_from_path
            name = dataset_name or "sample_dataset"
            path = data_path or kwargs.get("query") or "training/datasets/sample.jsonl"
            res = import_dataset_from_path(name, path)
            return {"success": True, "dataset": res}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_start_lora_training(self, job_name: str = "job_sample", base_model: str = "llama3.2", dataset_id: str = "sample_dataset", epochs: int = 3, **kwargs):
        try:
            from core.training.jobs import create_training_job, start_training_job
            j_name = job_name or "job_sample"
            b_model = base_model or "llama3.2"
            d_id = dataset_id or "sample_dataset"
            job = create_training_job(j_name, b_model, d_id, epochs)
            start_training_job(job["id"])
            return {"success": True, "job_id": job["id"], "status": "started"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_export_ollama_model(self, checkpoint_id: str = "ckpt_sample", target_model_name: str = "sigma-lora", **kwargs):
        try:
            from core.training.jobs import export_to_ollama
            ckpt = checkpoint_id or "ckpt_sample"
            target = target_model_name or kwargs.get("query") or "sigma-lora"
            res = export_to_ollama(ckpt, target)
            return {"success": True, "result": res}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _read_datasets_list(self, uri: str):
        try:
            from core.training.datasets import list_imported_datasets
            return list_imported_datasets()
        except Exception as exc:
            return {"datasets": [], "error": str(exc)}

    def _read_active_jobs(self, uri: str):
        try:
            from core.training.jobs import list_training_jobs
            return list_training_jobs()
        except Exception as exc:
            return {"jobs": [], "error": str(exc)}
