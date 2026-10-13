try:
    from core.engine.hardware_probe import UniversalHardwareProbe
except Exception:
    UniversalHardwareProbe = None

try:
    from core.engine.model_inspector import ModelInspector, ModelFacts
except Exception:
    ModelInspector, ModelFacts = None, None

try:
    from core.engine.memory_planner import MemoryPlanner, PlacementPlan
except Exception:
    MemoryPlanner, PlacementPlan = None, None

try:
    from core.engine.sampling import SamplingParams, FAMILY_RECIPES
except Exception:
    SamplingParams, FAMILY_RECIPES = None, None

try:
    from core.engine.cancellation import CancellationToken, is_cancelled
except Exception:
    CancellationToken, is_cancelled = None, None

try:
    from core.engine.prefix_cache import PrefixKVCache
except Exception:
    PrefixKVCache = None

try:
    from core.engine.grammars import (
        tool_call_grammar, json_object_grammar, grammar_for_available_tools,
    )
except Exception:
    tool_call_grammar, json_object_grammar, grammar_for_available_tools = None, None, None

try:
    from core.engine.unified_runtime import UniversalSigmaEngine, sigma_engine
except Exception:
    UniversalSigmaEngine, sigma_engine = None, None

try:
    from core.engine.engine_router import (
        handle_engine_status,
        handle_engine_profile,
        handle_engine_overrides_get,
        handle_engine_overrides_set,
        handle_engine_overrides_clear,
        handle_engine_runtime_check,
        handle_engine_rust_metrics,
        handle_engine_rust_stream,
        handle_engine_bitnet_status,
        handle_engine_partition,
        handle_engine_hf_import,
        handle_engine_models,
        handle_engine_optimize,
        handle_engine_plan,
        handle_engine_unload,
        handle_engine_benchmark,
    )
except Exception:
    handle_engine_status = handle_engine_profile = handle_engine_overrides_get = None
    handle_engine_overrides_set = handle_engine_overrides_clear = handle_engine_runtime_check = None
    handle_engine_rust_metrics = handle_engine_rust_stream = handle_engine_bitnet_status = None
    handle_engine_partition = handle_engine_hf_import = handle_engine_models = None
    handle_engine_optimize = handle_engine_plan = handle_engine_unload = handle_engine_benchmark = None

try:
    from core.engine.provider_server import (
        handle_v1_models,
        handle_v1_model_retrieve,
        handle_v1_embeddings,
        handle_ollama_tags,
        handle_ollama_version,
        handle_ollama_ps,
        handle_ollama_show,
        handle_engine_server_info,
        handle_provider_server_toggle,
        is_provider_server_enabled,
        set_provider_server_enabled,
        resolve_target_model,
        stream_openai_chat_generator,
        execute_openai_chat_non_stream,
        stream_ollama_chat_generator,
        execute_ollama_chat_non_stream,
        stream_ollama_generate_generator,
        execute_ollama_generate_non_stream,
        get_all_available_models,
    )
except Exception:
    handle_v1_models = handle_v1_model_retrieve = handle_v1_embeddings = None
    handle_ollama_tags = handle_ollama_version = handle_ollama_ps = handle_ollama_show = None
    handle_engine_server_info = handle_provider_server_toggle = is_provider_server_enabled = None
    set_provider_server_enabled = resolve_target_model = stream_openai_chat_generator = None
    execute_openai_chat_non_stream = stream_ollama_chat_generator = execute_ollama_chat_non_stream = None
    stream_ollama_generate_generator = execute_ollama_generate_non_stream = get_all_available_models = None


__all__ = [
    "UniversalHardwareProbe",
    "ModelInspector",
    "ModelFacts",
    "MemoryPlanner",
    "PlacementPlan",
    "SamplingParams",
    "FAMILY_RECIPES",
    "CancellationToken",
    "is_cancelled",
    "PrefixKVCache",
    "tool_call_grammar",
    "json_object_grammar",
    "grammar_for_available_tools",
    "UniversalSigmaEngine",
    "sigma_engine",
    "handle_engine_status",
    "handle_engine_profile",
    "handle_engine_overrides_get",
    "handle_engine_overrides_set",
    "handle_engine_overrides_clear",
    "handle_engine_runtime_check",
    "handle_engine_rust_metrics",
    "handle_engine_rust_stream",
    "handle_engine_bitnet_status",
    "handle_engine_partition",
    "handle_engine_hf_import",
    "handle_engine_models",
    "handle_engine_optimize",
    "handle_engine_plan",
    "handle_engine_unload",
    "handle_engine_benchmark",
    "handle_v1_models",
    "handle_v1_model_retrieve",
    "handle_v1_embeddings",
    "handle_ollama_tags",
    "handle_ollama_version",
    "handle_ollama_ps",
    "handle_ollama_show",
    "handle_engine_server_info",
    "stream_openai_chat_generator",
    "execute_openai_chat_non_stream",
    "stream_ollama_chat_generator",
    "execute_ollama_chat_non_stream",
    "stream_ollama_generate_generator",
    "execute_ollama_generate_non_stream",
    "get_all_available_models",
]


