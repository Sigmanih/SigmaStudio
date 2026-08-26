# ==============================================================================
# core/engine/transformers_compat.py — Compatibility Layer for Novel/Unified Models
#
# Bridges newly released model architectures (e.g. Gemma 4, GLM-4, DeepSeek V3,
# Qwen 3, multimodal unified checkpoints) with the installed version of Hugging Face
# Transformers by registering aliases in CONFIG_MAPPING and resolving model classes.
# ==============================================================================
import os
import json
from typing import Optional, Any, Dict, Type

from core.logger import get_logger

log = get_logger(__name__)

_COMPAT_INITIALIZED = False


def ensure_transformers_compatibility():
    """
    Registers model type aliases and architecture mappings in Transformers AutoConfig.
    Ensures checkpoints with unified/novel model types (e.g. gemma4_unified) load seamlessly.
    """
    global _COMPAT_INITIALIZED
    if _COMPAT_INITIALIZED:
        return

    try:
        import transformers
        from transformers.models.auto.configuration_auto import CONFIG_MAPPING

        # `hasattr` is not safe on this object. Transformers exposes its model
        # classes through a lazy module, so reading an attribute triggers an
        # import -- and when that import fails for a reason other than a
        # missing name (a broken torch, a partially initialised submodule) it
        # raises ModuleNotFoundError, which `hasattr` does not swallow. One such
        # failure used to abort every registration below it, leaving the whole
        # alias table empty and a checkpoint that would have loaded reporting
        # "Transformers does not recognize this architecture".
        def has(name: str) -> bool:
            return _safe_getattr(transformers, name, None) is not None

        # 1. Gemma 4 family aliases
        if has("Gemma4Config"):
            for alias in ("gemma4_unified", "gemma4_it", "gemma_4", "gemma4_text"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.Gemma4Config)
                    except Exception as e:
                        log.debug(f"[TransformersCompat] Registration notice for {alias}: {e}")

        if has("Gemma4TextConfig") and "gemma4_unified_text" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("gemma4_unified_text", transformers.Gemma4TextConfig)
            except Exception:
                pass

        if has("Gemma4VisionConfig") and "gemma4_unified_vision" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("gemma4_unified_vision", transformers.Gemma4VisionConfig)
            except Exception:
                pass

        if has("Gemma4AudioConfig") and "gemma4_unified_audio" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("gemma4_unified_audio", transformers.Gemma4AudioConfig)
            except Exception:
                pass

        # 2. Gemma 3 family aliases
        if has("Gemma3Config"):
            for alias in ("gemma3_unified", "gemma_3"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.Gemma3Config)
                    except Exception:
                        pass

        # 3. Qwen family aliases
        if has("Qwen2Config"):
            for alias in ("qwen3", "qwen3_moe", "qwen2_5", "qwen2.5", "qwen_3"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.Qwen2Config)
                    except Exception:
                        pass

        # 4. GLM / ChatGLM aliases
        if has("ChatGLMConfig") and "glm4" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("glm4", transformers.ChatGLMConfig)
                CONFIG_MAPPING.register("glm4_unified", transformers.ChatGLMConfig)
            except Exception:
                pass

        # 5. DeepSeek aliases
        if has("DeepseekV2Config"):
            for alias in ("deepseek_v3", "deepseek_v2_5", "deepseekv3"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.DeepseekV2Config)
                    except Exception:
                        pass

        _COMPAT_INITIALIZED = True
        log.info("[TransformersCompat] Architecture compatibility mappings successfully registered.")
    except Exception as exc:
        log.warning(f"[TransformersCompat] Could not register architecture mappings: {exc}")


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Safely gets attribute from an object, guarding against LazyModule import errors."""
    try:
        val = getattr(obj, name, default)
        return val if val is not None else default
    except Exception:
        return default


def resolve_model_architecture_class(arch_name: str, is_multimodal: bool = False) -> Optional[Any]:
    """
    Finds the exact or closest matching PyTorch model class for a given architecture string.
    Handles unified naming differences like 'Gemma4UnifiedForConditionalGeneration' -> 'Gemma4ForConditionalGeneration'.
    """
    ensure_transformers_compatibility()
    try:
        import transformers

        # Direct lookup
        cls = _safe_getattr(transformers, arch_name, None)
        if cls is not None:
            return cls

        # Canonical normalization candidates
        candidates = []

        # Strip 'Unified' e.g. Gemma4UnifiedForConditionalGeneration -> Gemma4ForConditionalGeneration
        if "Unified" in arch_name:
            candidates.append(arch_name.replace("Unified", ""))

        # Check specific family aliases
        if "Gemma4" in arch_name:
            candidates.extend([
                "Gemma4ForConditionalGeneration",
                "Gemma4ForCausalLM",
                "Gemma4Model"
            ])
        elif "Gemma3" in arch_name:
            candidates.extend([
                "Gemma3ForConditionalGeneration",
                "Gemma3ForCausalLM",
                "Gemma3Model"
            ])
        elif "Qwen3" in arch_name:
            candidates.extend([
                "Qwen2ForCausalLM",
                "Qwen2MoeForCausalLM"
            ])
        elif "DeepseekV3" in arch_name:
            candidates.extend([
                "DeepseekV2ForCausalLM",
                "LlamaForCausalLM"
            ])
        elif "Glm" in arch_name or "GLM" in arch_name:
            candidates.extend([
                "ChatGLMForConditionalGeneration",
                "ChatGLMModel"
            ])

        if is_multimodal:
            candidates.extend([
                "AutoModelForImageTextToText",
                "AutoModelForVision2Seq",
                "AutoModelForConditionalGeneration"
            ])
        else:
            candidates.append("AutoModelForCausalLM")

        for cand in candidates:
            cand_cls = _safe_getattr(transformers, cand, None)
            if cand_cls is not None:
                log.info(f"[TransformersCompat] Resolved '{arch_name}' -> '{cand}'")
                return cand_cls

        return _safe_getattr(transformers, "AutoModelForCausalLM", None)
    except Exception as exc:
        log.warning(f"[TransformersCompat] Error resolving architecture class for '{arch_name}': {exc}")
        return None
