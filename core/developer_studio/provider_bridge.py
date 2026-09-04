# ==============================================================================
# core/developer_studio/provider_bridge.py — Provider Routing for Dev Agent
# Sigma Studio v8 — Multi-Provider Support & SigmaEngine Acceleration
# ==============================================================================
"""Bridges the Developer Studio agent loop to multiple AI backends:
SigmaEngine (local with GBNF & prefix cache) or external cloud providers
(Claude, OpenAI, Gemini, DeepSeek, Ollama) via core.ai_providers.
"""

from typing import Any, Callable, Dict, Generator, List, Optional
from core.logger import get_logger
from core.ai_providers import load_ai_config, call_ai_model_stream
from core.engine.unified_runtime import sigma_engine

log = get_logger("dev_provider_bridge")


def stream_dev_generation(
    messages: List[Dict[str, str]],
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 16384,
    params: Any = None,
    thinking: Optional[bool] = False,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Streams inference tokens and status events from either SigmaEngine or an external provider.

    Yields dicts formatted with at least 'token' or 'status'/'thinking'/'error'.
    """
    ai_cfg = load_ai_config()
    active_prov = (provider or ai_cfg.get("active_provider") or "sigma_engine").lower().strip()

    # Normalise provider names
    if active_prov in ("sigma", "sigma_engine", "local", "sigmaengine", "native"):
        # Use native SigmaEngine with prefix caching and GBNF support
        try:
            for chunk in sigma_engine.generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name or ai_cfg.get("active_model", "sigmaengine"),
                messages=messages,
                params=params,
                thinking=thinking,
            ):
                yield chunk
        except Exception as ex:
            log.error("SigmaEngine generate_stream error: %s", ex)
            yield {"error": True, "message": f"Errore runtime SigmaEngine: {ex}"}
        return

    # External Provider Routing (OpenAI, Anthropic, Gemini, DeepSeek, Ollama, etc.)
    prov_cfg = ai_cfg.get("providers", {}).get(active_prov, {})
    eff_model = model_name or prov_cfg.get("model") or ai_cfg.get("active_model", "default")
    endpoint = prov_cfg.get("endpoint", "")
    api_url = prov_cfg.get("api_url", "")
    api_key = prov_cfg.get("api_key", "")
    top_p = prov_cfg.get("top_p", 0.9)
    req_timeout = prov_cfg.get("timeout", 180)

    # If system_prompt is passed separately, ensure it's at the start of messages
    formatted_messages = list(messages)
    if system_prompt and not any(m.get("role") == "system" for m in formatted_messages):
        formatted_messages.insert(0, {"role": "system", "content": system_prompt})

    class _CancelToken:
        def __init__(self, checker):
            self._checker = checker
        def is_set(self):
            return self._checker() if callable(self._checker) else False

    cancel_obj = _CancelToken(cancel_check) if cancel_check else None

    try:
        gen = call_ai_model_stream(
            messages=formatted_messages,
            ai_cfg=ai_cfg,
            model=eff_model,
            provider=active_prov,
            endpoint=endpoint,
            api_url=api_url,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            request_timeout=req_timeout,
            params=params,
            cancel=cancel_obj,
        )
        for chunk in gen:
            yield chunk
    except Exception as ex:
        log.error("Provider stream error for '%s': %s", active_prov, ex)
        yield {"error": True, "message": f"Errore provider '{active_prov}': {ex}"}
