# ==============================================================================
# core/engine/backends/sigmarust_backend.py — SigmaEngine Nativo in Rust
#
# Backend ad altissime prestazioni scritto in Rust. Gestisce scheduling
# hardware-aware, zero-copy memory tiering, paged KV-cache e continuous batching.
# Quando il kernel Rust è attivo, SigmaStudio delega il critical path dell'orchestrazione
# e dell'esecuzione a questo backend per azzerare l'overhead del runtime Python.
# ==============================================================================
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Generator, List, Optional, Tuple

from core.engine.backends.base import InferenceBackend
from core.engine.model_inspector import ModelFacts
from core.engine.sampling import SamplingParams
from core.logger import get_logger

log = get_logger(__name__)

#: Endpoint predefinito del micro-kernel SigmaEngine Rust (es. container Docker o binario nativo)
_DEFAULT_RUST_URL = os.environ.get("SIGMA_RUST_ENGINE_URL", "http://127.0.0.1:8090")


def _is_rust_kernel_online(url: str = _DEFAULT_RUST_URL, timeout_s: float = 0.5) -> bool:
    """Verifica rapida della disponibilità del kernel Rust via probe /health."""
    try:
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok" and data.get("service") == "sigma_engine_rust"
    except Exception:
        return False
    return False


class SigmaRustBackend(InferenceBackend):
    """Esegue inferenza, scheduling e memory-tiering tramite il micro-kernel Rust nativo."""

    name = "sigma_engine_rust"
    supported_formats = ("gguf", "safetensors")

    def __init__(self, endpoint_url: str = _DEFAULT_RUST_URL) -> None:
        self._url = endpoint_url
        self._facts: Optional[ModelFacts] = None
        self._loaded_model_id: Optional[str] = None
        self._placement_info: Dict[str, Any] = {}

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        """Controlla se il kernel Rust è raggiungibile sull'host locale."""
        if _is_rust_kernel_online():
            return (True, f"SigmaEngine Rust attivo su {_DEFAULT_RUST_URL}")
        return (
            False,
            f"SigmaEngine Rust non rilevato su {_DEFAULT_RUST_URL}. "
            "Avvia il container con `docker-compose up -d` in projects/sigma_engine_rust.",
        )

    @classmethod
    def supports(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> bool:
        """Supporta GGUF e SafeTensors con introspezione zero-copy."""
        return facts.weight_format in cls.supported_formats

    @classmethod
    def score(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> int:
        """
        Punteggio di preferenza:
        - 120 se SIGMA_RUST_INFERENCE=1 è impostato esplicitamente.
        - 95 di default per lasciare a LlamaServerBackend (110) l'esecuzione del
          forward pass dei token su GPU CUDA con i modelli reali di chat, mentre
          il kernel Rust gestisce memory tiering, introspezione e tool graph.
        """
        if os.environ.get("SIGMA_RUST_INFERENCE") == "1":
            return 120
        return 95

    def load(self, facts: ModelFacts, hardware: Dict[str, Any], **options) -> Dict[str, Any]:
        """Mappa il modello tramite il planner di tiering zero-copy del kernel Rust."""
        self._facts = facts
        model_name = facts.name or os.path.basename(facts.path or "unknown")

        payload = {
            "model": model_name,
            "model_path": str(facts.path) if facts.path else None,
            "model_size_gb": facts.file_size_gb if hasattr(facts, "file_size_gb") else 8.0,
            "total_layers": getattr(facts, "layers_count", 32),
            "quantization": getattr(facts, "quantization", "Q4_K_M"),
        }

        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/partition",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                self._loaded_model_id = model_name
                self._placement_info = result.get("tiering_plan", {})
                log.info(
                    "[SigmaRustBackend] Modello '%s' pianificato e mappato con successo nel kernel Rust.",
                    model_name,
                )
                return {
                    "success": True,
                    "backend": self.name,
                    "model": model_name,
                    "tiering": self._placement_info,
                    "benchmark": result.get("mmap_zero_copy_benchmark"),
                }
        except Exception as exc:
            log.error("[SigmaRustBackend] Errore di caricamento nel kernel Rust: %s", exc)
            return {"success": False, "error": str(exc)}

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        messages: Optional[list] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
        thinking: Optional[bool] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Genera token in streaming delegando al kernel Rust via API standard OpenAI."""
        if not messages:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        req_body = {
            "model": self._loaded_model_id or "sigma_default",
            "messages": messages,
            "temperature": params.temperature if params else temperature,
            "max_tokens": params.max_tokens if params else max_tokens,
            "stream": True,
        }

        try:
            req = urllib.request.Request(
                f"{self._url}/v1/chat/completions",
                data=json.dumps(req_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    for raw_line in resp:
                        line_str = raw_line.decode("utf-8", errors="replace").strip()
                        if not line_str or line_str.startswith(":"):
                            continue
                        if line_str == "data: [DONE]":
                            break
                        if line_str.startswith("data: "):
                            try:
                                chunk = json.loads(line_str[6:])
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    tok = delta.get("content", "")
                                    finish = choices[0].get("finish_reason")
                                    if tok or finish:
                                        yield {
                                            "token": tok,
                                            "content": tok,
                                            "finish_reason": finish,
                                            "latency_ms": (time.perf_counter() - t0) * 1000.0,
                                        }
                            except Exception:
                                continue
                else:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    yield {
                        "token": content,
                        "content": content,
                        "finish_reason": "stop",
                        "latency_ms": elapsed_ms,
                    }
        except Exception as exc:
            log.error("[SigmaRustBackend] Errore durante generazione stream: %s", exc)
            yield {
                "token": f"\n[Errore SigmaRustBackend: {exc}]",
                "content": f"\n[Errore SigmaRustBackend: {exc}]",
                "finish_reason": "error",
            }

    def unload(self) -> Dict[str, Any]:
        """Rilascia il modello resident nel kernel Rust."""
        old_model = self._loaded_model_id
        self._loaded_model_id = None
        self._facts = None
        self._placement_info = {}
        return {"success": True, "unloaded": old_model}

    @property
    def is_loaded(self) -> bool:
        return self._loaded_model_id is not None

    def describe_placement(self) -> Dict[str, Any]:
        return self._placement_info

    def parallel_slots(self) -> int:
        return 4
