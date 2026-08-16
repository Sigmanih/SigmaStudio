# ==============================================================================
# core/ai_providers.py — AI Provider Abstraction Layer
# Sigma Studio v6 — Unified interface for calling different AI backends
# ==============================================================================
"""Unified interface for calling different AI backends (Ollama, OpenAI, Anthropic)."""

import json
import os
import re
import copy

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from core.logger import get_logger
log = get_logger(__name__)




# ---------------------------------------------------------------------------
# Config loading / saving
# ---------------------------------------------------------------------------

DEFAULT_AI_CONFIG = {
    "active_provider": "sigma_engine",
    "active_model": "sigma-native:latest",
    "providers": {
        "sigma_engine": {
            "label": "SigmaEngine (Nativo & Sharded)",
            "endpoint": "http://localhost:8000/api/engine",
            "model": "sigma-native:latest",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "models": [
                "sigma-native:latest",
                "sigma-minerva-1b-base-v1.0",
                "sigma-router:latest",
                "ailo-340m-v4",
                "llama4:16x17b (MoE Sharded)",
                "deepseek-r1:70b (Sigma Native)",
                "qwen2.5-coder:7b (Sigma Accelerated)"
            ],
        },
        "ailoflow": {
            "label": "AiloFlow (Flow Engine)",
            "endpoint": "http://localhost:5000/v1",
            "model": "ailo-flow-default",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "models": ["ailo-flow-default", "ailo-152m-router", "ailo-340m-v4"],
        },
        "ollama": {
            "label": "Ollama (Locale)",
            "endpoint": "http://localhost:11434/api/chat",
            "model": "llama3.2",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "models": [],
        },
        "deepseek": {
            "label": "DeepSeek",
            "api_url": "https://api.deepseek.com/v1/chat/completions",
            "api_key": "",
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
        },
        "google": {
            "label": "Google (Gemini)",
            "api_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "api_key": "",
            "model": "gemini-2.0-flash",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b"],
        },
        "mistral": {
            "label": "Mistral AI",
            "api_url": "https://api.mistral.ai/v1/chat/completions",
            "api_key": "",
            "model": "mistral-large-latest",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest", "mistral-medium-latest", "open-mistral-nemo"],
        },
        "xai": {
            "label": "xAI (Grok)",
            "api_url": "https://api.x.ai/v1/chat/completions",
            "api_key": "",
            "model": "grok-2",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["grok-2", "grok-2-mini", "grok-beta", "grok-2-vision"],
        },
        "perplexity": {
            "label": "Perplexity",
            "api_url": "https://api.perplexity.ai/chat/completions",
            "api_key": "",
            "model": "sonar-pro",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["sonar-pro", "sonar", "llama-3.1-sonar-small", "llama-3.1-sonar-large", "llama-3.1-sonar-huge"],
        },
        "together": {
            "label": "Together AI",
            "api_url": "https://api.together.xyz/v1/chat/completions",
            "api_key": "",
            "model": "mistralai/Mixtral-8x22B-Instruct-v0.1",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["mistralai/Mixtral-8x22B-Instruct-v0.1", "meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/deepseek-coder-v2-instruct", "Qwen/Qwen2.5-72B-Instruct-Turbo", "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo"],
        },
        "qwen": {
            "label": "Qwen (Alibaba Cloud)",
            "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "api_key": "",
            "model": "qwen-max",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-72b-instruct", "qwen2.5-32b-instruct", "qwen2.5-14b-instruct", "qwen2.5-7b-instruct", "qwen2.5-coder-32b-instruct", "qwen2.5-math-72b-instruct"],
        },
        "glm": {
            "label": "GLM (Zhipu AI)",
            "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            "api_key": "",
            "model": "glm-4-plus",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["glm-4-plus", "glm-4-0520", "glm-4-air", "glm-4-flash", "glm-4-long", "glm-4v-plus", "glm-4v"],
        },
        "moonshot": {
            "label": "Moonshot (Kimi)",
            "api_url": "https://api.moonshot.cn/v1/chat/completions",
            "api_key": "",
            "model": "moonshot-v1-8k",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "moonshot-v1-auto"],
        },
        "yi": {
            "label": "Yi (01.AI)",
            "api_url": "https://api.01.ai/v1/chat/completions",
            "api_key": "",
            "model": "yi-large",
            "temperature": 0.7,
            "max_tokens": 8192,
            "top_p": 0.9,
            "models": ["yi-large", "yi-medium", "yi-vision", "yi-large-rag", "yi-large-turbo", "yi-lightning", "yi-large-preview"],
        },
    },
}


def load_ai_config(config_path: str = "config.json") -> dict:
    """Load AI config from config.json, returning a normalized multi-provider dict."""
    if not os.path.exists(config_path):
        return DEFAULT_AI_CONFIG

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        ai_cfg = cfg.get("ai", {})

        # Detect legacy flat format
        is_legacy = "providers" not in ai_cfg and (
            "provider" in ai_cfg or "endpoint" in ai_cfg
        )

        if is_legacy:
            provider_key = ai_cfg.get("provider", "ollama")
            defaults = DEFAULT_AI_CONFIG
            prov = defaults["providers"].get(
                provider_key, defaults["providers"]["ollama"]
            ).copy()
            prov.update({
                "endpoint": ai_cfg.get("endpoint", prov.get("endpoint", "")),
                "api_url": ai_cfg.get("api_url", prov.get("api_url", "")),
                "api_key": ai_cfg.get("api_key", prov.get("api_key", "")),
                "model": ai_cfg.get("model", prov.get("model", "llama3.2")),
                "temperature": ai_cfg.get("temperature", prov.get("temperature", 0.7)),
                "max_tokens": ai_cfg.get("max_tokens", prov.get("max_tokens", 4096)),
                "top_p": ai_cfg.get("top_p", prov.get("top_p", 0.9)),
            })
            ai_cfg = {
                "active_provider": provider_key,
                "active_model": prov["model"],
                "providers": defaults["providers"].copy(),
            }
            ai_cfg["providers"][provider_key] = prov
        else:
            # Ensure required keys exist
            ai_cfg.setdefault("active_provider", ai_cfg.get("provider", "ollama"))
            ai_cfg.setdefault("active_model", ai_cfg.get("model", "llama3.2"))
            if "providers" not in ai_cfg:
                ai_cfg["providers"] = DEFAULT_AI_CONFIG["providers"]
            else:
                for pk, pv in DEFAULT_AI_CONFIG["providers"].items():
                    ai_cfg["providers"].setdefault(pk, pv)

        return ai_cfg
    except Exception:
        return DEFAULT_AI_CONFIG


def save_ai_config(ai_config: dict, config_path: str = "config.json") -> None:
    """Persist the AI config back to config.json."""
    existing = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing["ai"] = ai_config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=4)


# ---------------------------------------------------------------------------
# Execution Profiles — parametri ottimizzati per contesto operativo
# ---------------------------------------------------------------------------

EXECUTION_PROFILES = {
    "fast_chat": {
        "label": "Chat Veloce / Sintetica",
        "temperature": 0.6,
        "max_tokens": 4096,
        "num_ctx": 32768,
        "top_p": 0.95,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "description": "Risposta veloce a bassissima latenza per saluti e richieste rapide, con memoria di contesto estesa (32K)"
    },
    "code": {
        "label": "Codice / Sviluppo Deep",
        "temperature": 0.2,
        "max_tokens": 32768,
        "num_ctx": 65536,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.05,
        "description": "Massima precisione e determinismo, ideale per generare e modificare codice completo senza troncamenti (65K ctx)"
    },
    "mathematics": {
        "label": "Matematica / Ricerca Deep",
        "temperature": 0.2,
        "max_tokens": 32768,
        "num_ctx": 65536,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.05,
        "description": "Ragionamento logico profondo, dimostrazioni formali e trattazioni complete (65K ctx)"
    },
    "creative": {
        "label": "Creativo / Brainstorming",
        "temperature": 0.85,
        "max_tokens": 16384,
        "num_ctx": 65536,
        "top_p": 0.95,
        "top_k": 50,
        "repeat_penalty": 1.05,
        "description": "Creativo e divergente, ideale per brainstorming e scrittura estesa (65K ctx)"
    },
    "analysis": {
        "label": "Analisi Dati",
        "temperature": 0.25,
        "max_tokens": 32768,
        "num_ctx": 65536,
        "top_p": 0.85,
        "top_k": 30,
        "repeat_penalty": 1.1,
        "description": "Analitico, contesto ultra-ampio (65K ctx), massima precisione di calcolo"
    },
    "conversation": {
        "label": "Conversazione Standard",
        "temperature": 0.7,
        "max_tokens": 16384,
        "num_ctx": 65536,
        "top_p": 0.95,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "description": "Bilanciato per conversazioni approfondite con finestra di memoria estesa (65K ctx)"
    },
    "web_search": {
        "label": "Ricerca Web",
        "temperature": 0.4,
        "max_tokens": 16384,
        "num_ctx": 65536,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "description": "Bilanciato, sintetico e strutturato per sintesi di informazioni web (65K ctx)"
    },
}


def detect_execution_profile(message: str, context: str = "") -> str:
    """Detect the most appropriate execution profile based on message content.

    Analyzes prompt complexity to return fast_chat for quick queries,
    or deep generation profiles for math, code, analysis, etc.
    """
    msg_strip = message.strip().lower()
    words = msg_strip.split()
    
    # Fast chat check for short greetings or trivial questions
    greetings = {'ciao', 'buongiorno', 'buonasera', 'salve', 'chi sei', 'come stai', 'grazie', 'ok', 'perfetto', 'test'}
    if len(words) <= 4 and (msg_strip in greetings or any(w in greetings for w in words)):
        return "fast_chat"

    msg_lower = (message + " " + context).lower()

    code_keywords = [
        'create_file', 'edit_file', 'run_test', 'run_terminal',
        'def ', 'class ', 'import ', 'function', 'codice', 'programma',
        'script', 'api', 'endpoint', 'bug', 'debug', 'refactor', 'test',
        'python', 'javascript', 'react', 'html', 'css', 'jsx',
        '.py', '.js', '.jsx', '.html', '.css', '.json',
    ]
    code_score = sum(1 for kw in code_keywords if kw in msg_lower)

    math_keywords = [
        'dimostra', 'teorema', 'lemma', 'congettura', 'matematica',
        'equazione', 'formula', 'numeri', 'primi', 'fattori',
        'dimostrazione', 'prova che', 'verifica che', 'calcolo',
        'modulo', 'distribuzione', 'pattern', 'sequenza',
        'analisi', 'limiti', 'derivate', 'integrali', 'funzioni',
    ]
    math_score = sum(1 for kw in math_keywords if kw in msg_lower)

    analysis_keywords = [
        'analizza', 'analisi', 'confronta', 'statistica', 'dati',
        'tendenza', 'media', 'mediana', 'deviazione', 'correlazione',
        'grafico', 'chart', 'plot', 'distribuzione',
    ]
    analysis_score = sum(1 for kw in analysis_keywords if kw in msg_lower)

    web_keywords = [
        'cerca', 'search', 'ricerca web', 'wikipedia', 'internet',
        'notizie', 'ultime', 'aggiornamento', 'web',
    ]
    web_score = sum(1 for kw in web_keywords if kw in msg_lower)

    creative_keywords = [
        'crea', 'inventa', 'immagina', 'storia', 'poesia',
        'racconto', 'canzone', 'idea', 'brainstorming',
    ]
    creative_score = sum(1 for kw in creative_keywords if kw in msg_lower)

    scores = {
        'code': code_score,
        'mathematics': math_score,
        'analysis': analysis_score,
        'web_search': web_score,
        'creative': creative_score,
    }

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best

    return "conversation"


def apply_execution_profile(profile: str, config: dict) -> dict:
    """Apply an execution profile to a config dict, overriding relevant params."""
    profile_cfg = EXECUTION_PROFILES.get(profile)
    if not profile_cfg:
        return config

    updated = config.copy()
    updated["temperature"] = profile_cfg["temperature"]
    updated["max_tokens"] = profile_cfg["max_tokens"]
    updated["top_p"] = profile_cfg["top_p"]
    if "num_ctx" in profile_cfg:
        updated["num_ctx"] = profile_cfg["num_ctx"]
    if "top_k" in profile_cfg:
        updated["top_k"] = profile_cfg["top_k"]
    if "repeat_penalty" in profile_cfg:
        updated["repeat_penalty"] = profile_cfg["repeat_penalty"]

    return updated


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------

def resolve_provider_config(ai_cfg_or_model, model_name: str = "") -> tuple[str, dict]:
    """
    Resolve which AI provider to use based on model name and configuration.
    Returns (provider_name, provider_config).
    Defaults to native SigmaEngine for all local models.
    """
    if isinstance(ai_cfg_or_model, dict):
        ai_cfg = ai_cfg_or_model
    else:
        ai_cfg = load_ai_config()
        if not model_name and isinstance(ai_cfg_or_model, str):
            model_name = ai_cfg_or_model

    providers = (ai_cfg or {}).get("providers", {})
    if not model_name:
        model_name = (ai_cfg or {}).get("active_model", "sigma-native:latest")

    lower = (model_name or "").lower()

    # Rule 0: SigmaEngine native models or downloaded Hugging Face models in data/models/
    clean_folder = model_name.replace("/", "--")
    if os.path.exists(os.path.join(os.getcwd(), "data", "models", clean_folder)) or \
       os.path.exists(os.path.join(os.getcwd(), "data", "models", model_name)) or \
       lower.startswith("sigma") or lower.startswith("ailo") or "sharded" in lower or "native" in lower or "minerva" in lower:
        return "sigma_engine", providers.get("sigma_engine", {"label": "SigmaEngine (Nativo)", "endpoint": "http://localhost:8000/api/engine"})

    # Rule 1: Exact model match in configured cloud providers list
    for pk, pv in providers.items():
        if pk == "ollama" or pk == "sigma_engine":
            continue
        configured_models = pv.get("models", [])
        if model_name in configured_models or pv.get("model") == model_name:
            if pv.get("api_key", "").strip() or pv.get("endpoint") or pv.get("api_url"):
                return pk, pv

    # Rule 2: Strict Cloud-only prefix matching (prevent false positives)
    cloud_prefixes = {
        'openai': ('gpt-', 'o1-', 'o1', 'o3-', 'chatgpt-'),
        'anthropic': ('claude-',),
        'google': ('gemini-',),
        'deepseek': ('deepseek-chat', 'deepseek-reasoner', 'deepseek-coder'),
        'xai': ('grok-', 'grok-2', 'grok-beta'),
        'perplexity': ('sonar',),
        'mistral': ('mistral-large', 'mistral-small', 'codestral-', 'open-mistral'),
        'groq': ('llama-3.3-70b', 'llama-3.1-8b', 'mixtral-8x7b', 'gemma2-9b', 'deepseek-r1-distill'),
        'openrouter': ('openai/', 'anthropic/', 'google/', 'meta-llama/', 'mistralai/', 'deepseek/'),
        'qwen': ('qwen-plus', 'qwen-max', 'qwen-turbo'),
        'glm': ('glm-4',),
        'moonshot': ('moonshot-v1',),
        'yi': ('yi-large', 'yi-medium'),
    }
    for pk, prefixes in cloud_prefixes.items():
        if any(model_name.lower().startswith(pfx) for pfx in prefixes):
            pv = providers.get(pk, {})
            if pv.get("api_key", "").strip():
                return pk, pv

    # Rule 3: Optional external Ollama (ONLY if explicitly configured and enabled)
    ollama_pv = providers.get("ollama", {})
    if ollama_pv.get("enabled") is True and ollama_pv.get("endpoint"):
        return "ollama", ollama_pv

    # Default: Native SigmaEngine
    return "sigma_engine", providers.get("sigma_engine", {"label": "SigmaEngine (Nativo)", "endpoint": "http://localhost:8000/api/engine"})


# ---------------------------------------------------------------------------
# AI Call implementations
# ---------------------------------------------------------------------------

def call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout):
    """Unified AI model caller used by agent_orchestrator, execute_loop, loop_handler."""
    if provider in ('sigma_engine', 'sigma'):
        from core.engine import sigma_engine
        prompt_text = messages[-1].get("content", "") if messages else ""
        sys_text = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
        tokens = list(sigma_engine.generate_stream(prompt_text, system_prompt=sys_text, temperature=temperature, max_tokens=max_tokens, model_name=model))
        full_res = "".join([t["token"] for t in tokens])
        return full_res, "Esecuzione nativa diretta su hardware completata tramite SigmaEngine (CUDA/MPS/DirectML + Multi-Tier Sharding).", None

    route_provider = provider
    if route_provider in ('deepseek', 'openai'):
        route_provider = 'api'
    elif route_provider not in ('ollama', 'api', 'anthropic'):
        route_provider = 'api'
    ac = ai_cfg.get("providers", {}).get(provider, {})
    try:
        if route_provider == "ollama":
            return call_ollama(messages, model, endpoint, temperature, max_tokens, top_p,
                ac.get("top_k", 40), ac.get("repeat_penalty", 1.1), ac.get("num_ctx", 8192), ac.get("seed", 0), request_timeout)
        elif route_provider == "api":
            return call_openai_compatible(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
        elif route_provider == "anthropic":
            r = call_anthropic(messages, model, api_url, api_key, temperature, max_tokens, top_p)
            return r[0], None, r[1] if len(r) > 1 else None
    except Exception as e:
        return None, None, str(e)
    return None, None, "Provider sconosciuto"

def parse_thinking_and_content(raw_text: str, provider_thinking: str = None) -> tuple:
    """
    Robustly separates thinking/reasoning blocks from user-facing Markdown content.
    Handles XML <think>...</think> tags and meta-cognitive reasoning headers
    (e.g., 'Analyze User Input:', 'Draft Construction:', 'Check System Prompt').
    """
    if not raw_text:
        return "", provider_thinking
        
    thinking = provider_thinking or ""
    content = str(raw_text).strip()
    
    # 1. XML <think>...</think> tags
    think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL | re.IGNORECASE)
    if think_match:
        extracted = think_match.group(1).strip()
        thinking = f"{thinking}\n{extracted}".strip() if thinking else extracted
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
        
    # 2. Heuristic reasoning headers (Analyze User Input, Identify Intent, Persona Check, Draft, etc.)
    reasoning_keywords = [
        'Analyze User Input', 'Identify Key Concepts', 'Structure the Response',
        'Draft Construction', 'Draft the Content', 'Self-Correction', 'Check System Prompt',
        'Determine Response Strategy', 'Mental Refinement', 'Final Polish',
        'The user is asking', 'The user said', 'Identify Intent:', 'Determine Response Mode:',
        'Persona Check:', 'Response Plan:', 'Drafting the response:', 'Refining tone:', 'Plan:'
    ]
    if any(kw in content for kw in reasoning_keywords):
        end_match = re.search(r'(?:Output matches[^\n]*✅?|✅|\bProceed\.|\bFinal Polish:.*?\n|\bThis fits perfectly[^\n]*\n|\bThis sounds professional[^\n]*\n|\bUse this approach\.[^\n]*\n|\bProceed with this response\.[^\n]*\n)', content, re.IGNORECASE)
        if end_match:
            split_pos = end_match.end()
            extracted_think = content[:split_pos].strip()
            thinking = f"{thinking}\n{extracted_think}".strip() if thinking else extracted_think
            content = content[split_pos:].strip()
            content = re.sub(r'^[🤖✅\s]+', '', content).strip()
        else:
            parts = re.split(r'\n(?=Le\s|I\s|Un\s|Una\s|Il\s|La\s|#|\*\*|Ciao|Salute|Benvenuto|Ecco|Certamente|Sicuramente)', content, maxsplit=1)
            if len(parts) == 2:
                thinking = parts[0].strip()
                content = parts[1].strip()
                
    return content, thinking


def check_ollama_vram_status(model_name: str, endpoint: str = "http://localhost:11434/api/chat") -> dict:
    """Check if model is currently loaded in Ollama VRAM/RAM or needs cold load."""
    if not REQUESTS_AVAILABLE:
        return {"loaded": False, "status_message": f"⏳ Avvio inferenza con {model_name}..."}
    try:
        base_url = endpoint.rsplit('/', 1)[0]
        ps_url = f"{base_url}/ps"
        resp = requests.get(ps_url, timeout=2)
        if resp.status_code == 200:
            loaded_models = [m.get("name", "") for m in resp.json().get("models", [])]
            if any(model_name in m or m in model_name for m in loaded_models):
                return {"loaded": True, "status_message": f"⚡ Modello `{model_name}` pronto in VRAM GPU (Warm Cache)"}
    except Exception:
        pass
    return {"loaded": False, "status_message": f"⏳ Caricamento del modello `{model_name}` in VRAM GPU (Cold Start)..."}


def select_best_available_model(requested_model: str = "", available_models: list[str] = None) -> str | None:
    """
    Selects the best model using the following strict priority:
    1. First model from configured favorite_models that is available.
    2. The configured favorite_model / active_model if available.
    3. First lightweight/quantized model available in Ollama (avoiding 50GB+ FP16 models).
    4. Returns None if no models are available.
    """
    if not available_models:
        return None
        
    cfg = load_ai_config()
    fav_models = cfg.get("favorite_models", [])
    if isinstance(fav_models, str):
        fav_models = [fav_models]
    single_fav = cfg.get("favorite_model", "")
    if single_fav and single_fav not in fav_models:
        fav_models.append(single_fav)

    # 1. Check favorites
    for fav in fav_models:
        if fav in available_models:
            return fav
        clean_fav = fav.lower().replace("/", "--").replace(":", "-")
        for av in available_models:
            av_clean = av.lower().replace("/", "--").replace(":", "-")
            if clean_fav in av_clean or av_clean in clean_fav:
                return av

    # 2. Check active/configured model
    active_m = cfg.get("active_model", "")
    if active_m in available_models:
        return active_m

    # 3. Prioritize fast quantized models over heavy 50GB+ FP16 models
    quant_priority = ["qwen3.6-raw", "qwen3.6:27b", "qwen3.6:35b", "deepseek-r1:14b", "deepseek-r1:70b", "llama4", "glm-4", "qwen2.5"]
    for q_cand in quant_priority:
        for av in available_models:
            if q_cand in av.lower() and "f16" not in av.lower():
                return av

    # 4. Filter out unquantized 50GB+ if smaller models exist
    smaller_models = [m for m in available_models if "3.8:27b" not in m.lower()]
    if smaller_models:
        return smaller_models[0]

    return available_models[0]


def call_ollama(
    messages: list,
    model: str,
    endpoint: str,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    top_p: float = 0.95,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
    num_ctx: int = 32768,
    seed: int = 0,
    timeout: int = 300,
) -> tuple:
    if not REQUESTS_AVAILABLE:
        return None, None, "requests library not available. Install with: pip install requests"
    try:
        options = {
            "temperature": temperature,
            "num_predict": max(max_tokens or 16384, 16384), # Generous token limit to prevent truncation during long code & reasoning
            "top_p": top_p if top_p is not None else 0.95,
            "top_k": top_k or 40,
            "repeat_penalty": repeat_penalty or 1.1,
            "num_ctx": max(num_ctx or 32768, 65536),       # Expanded context window up to 65K
            "num_thread": 12,                              # Use 12 physical CPU threads for prompt prefill
            "use_mmap": True,                              # Memory-mapped weights for high memory bandwidth
        }
        if seed:
            options["seed"] = seed
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        if resp.status_code == 404 and "not found" in resp.text:
            try:
                base_url = endpoint.rsplit('/', 1)[0]
                tags_url = f"{base_url}/tags"
                tags_resp = requests.get(tags_url, timeout=5)
                available_models = []
                if tags_resp.status_code == 200:
                    models_data = tags_resp.json()
                    available_models = [m.get("name") for m in models_data.get("models", []) if m.get("name")]
                fallback_model = select_best_available_model(model, available_models)
                if fallback_model and fallback_model != model:
                    log.warning("Model '%s' not found in Ollama. Falling back to favorite/available '%s'", model, fallback_model)
                    payload["model"] = fallback_model
                    resp = requests.post(endpoint, json=payload, timeout=timeout)
                elif not fallback_model:
                    error_msg = (
                        "⚠️ **Nessun modello AI locale attivo o pronto all'uso.**\n\n"
                        "Per iniziare a chattare:\n"
                        "1. Apri il tab **Model Hub** (dalla barra laterale) e scarica o avvia un modello raccomandato (es. *Qwen 3.6 27B Q4_K_M* o *DeepSeek-R1 14B*).\n"
                        "2. Oppure apri **Impostazioni AI** (icona ⚙️) e inserisci la tua API Key per provider cloud (DeepSeek, OpenAI, Anthropic, Gemini, Groq)."
                    )
                    log.error("No models available in Ollama.")
                    return None, None, error_msg
                if resp.status_code != 200:
                    error_msg = f"Modello '{model}' non trovato in Ollama. Modelli disponibili: {', '.join(available_models[:10]) if available_models else 'nessuno'}"
                    log.error(error_msg)
                    return None, None, error_msg
            except Exception as ex:
                log.error("Failed to query Ollama tags: %s", ex)
                return None, None, f"Modello '{model}' non trovato in Ollama."

        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("message", {})
            content = msg.get("content", "")
            thinking = msg.get("thinking", msg.get("reasoning_content", None))
            content, thinking = parse_thinking_and_content(content, thinking)
            if not content and thinking:
                content = thinking
                thinking = None
            return content, thinking, None
        return None, None, f"Ollama error {resp.status_code}: {resp.text}"
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        log.warning("[Ollama] Daemon non raggiungibile (%s). Fallback su SigmaEngine Nativo...", e)
        try:
            from core.engine import sigma_engine
            prompt_text = messages[-1].get("content", "") if messages else ""
            sys_text = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
            tokens = list(sigma_engine.generate_stream(prompt_text, system_prompt=sys_text, temperature=temperature, max_tokens=max_tokens))
            full_res = "".join([t["token"] for t in tokens])
            return full_res, None, None
        except Exception as ex:
            return None, None, f"Errore connessione Ollama / SigmaEngine: {e} | {ex}"
    except Exception as e:
        return None, None, str(e)


def call_ollama_stream(
    messages: list,
    model: str,
    endpoint: str,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    top_p: float = 0.95,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
    num_ctx: int = 32768,
    seed: int = 0,
    timeout: int = 300,
):
    if not REQUESTS_AVAILABLE:
        yield {"error": True, "message": "requests library not available"}
        return
    try:
        options = {
            "temperature": temperature,
            "num_predict": max(max_tokens or 16384, 16384), # Generous token limit to prevent truncation during long code & reasoning
            "top_p": top_p if top_p is not None else 0.95,
            "top_k": top_k or 40,
            "repeat_penalty": repeat_penalty or 1.1,
            "num_ctx": max(num_ctx or 32768, 65536),       # Expanded context window up to 65K
            "num_thread": 12,                              # Use 12 physical CPU threads for prompt prefill
            "use_mmap": True,                              # Memory-mapped weights for high memory bandwidth
        }
        if seed:
            options["seed"] = seed
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        resp = requests.post(endpoint, json=payload, stream=True, timeout=int(timeout or 300))
        if resp.status_code == 404 and "not found" in resp.text:
            try:
                base_url = endpoint.rsplit('/', 1)[0]
                tags_resp = requests.get(f"{base_url}/tags", timeout=5)
                available_models = []
                if tags_resp.status_code == 200:
                    available_models = [m.get("name") for m in tags_resp.json().get("models", []) if m.get("name")]
                fallback_model = select_best_available_model(model, available_models)
                if fallback_model and fallback_model != model:
                    log.warning("[Ollama Stream] Model '%s' not found. Falling back to favorite/available '%s'", model, fallback_model)
                    payload["model"] = fallback_model
                    resp = requests.post(endpoint, json=payload, stream=True, timeout=int(timeout or 300))
                elif not fallback_model:
                    yield {
                        "error": True,
                        "no_model_available": True,
                        "token": (
                            "⚠️ **Nessun modello AI locale attivo o pronto all'uso.**\n\n"
                            "Per iniziare a chattare:\n"
                            "1. Apri il tab **Model Hub** (dalla barra laterale) e scarica o avvia un modello raccomandato (es. *Qwen 3.6 27B Q4_K_M* o *DeepSeek-R1 14B*).\n"
                            "2. Oppure apri **Impostazioni AI** (icona ⚙️) e inserisci la tua API Key per provider cloud (DeepSeek, OpenAI, Anthropic, Gemini, Groq)."
                        )
                    }
                    return
            except Exception as ex:
                log.error("[Ollama Stream] Failed to resolve fallback model: %s", ex)
        if resp.status_code != 200:
            yield {"error": True, "message": f"Ollama error {resp.status_code}: {resp.text[:200]}"}
            return
        for line in resp.iter_lines(chunk_size=1, decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                msg = data.get("message", {})
                content = msg.get("content", "")
                thinking = msg.get("thinking", msg.get("reasoning_content", ""))
                # Reasoning stays on its own channel: routing it into "token"
                # dumps the whole chain-of-thought into the answer bubble.
                # Consumers fall back to thinking when no content ever arrives.
                result = {}
                if content:
                    result["token"] = content
                if thinking:
                    result["thinking"] = thinking
                if result:
                    yield result
                if data.get("done", False):
                    done_reason = data.get("done_reason", "stop")
                    eval_count = data.get("eval_count")
                    eval_duration = data.get("eval_duration")
                    load_duration = data.get("load_duration")
                    prompt_eval_duration = data.get("prompt_eval_duration")
                    tps = None
                    if eval_count and eval_duration and eval_duration > 0:
                        tps = round(eval_count / (eval_duration / 1e9), 1)
                    yield {
                        "done": True,
                        "done_reason": done_reason,
                        "truncated": done_reason == "length",
                        "eval_count": eval_count,
                        "eval_duration": eval_duration,
                        "load_duration": load_duration,
                        "prompt_eval_duration": prompt_eval_duration,
                        "tokens_per_second": tps
                    }
                    break
            except json.JSONDecodeError:
                continue
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        log.warning("[Ollama Stream] Daemon non raggiungibile (%s). Fallback automatico su SigmaEngine Nativo...", e)
        try:
            from core.engine import sigma_engine
            prompt_text = messages[-1].get("content", "") if messages else ""
            sys_text = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
            for token_chunk in sigma_engine.generate_stream(prompt_text, system_prompt=sys_text, temperature=temperature, max_tokens=max_tokens, model_name=model):
                yield token_chunk
            return
        except Exception as fallback_err:
            yield {"error": True, "message": f"Ollama non raggiungibile su {endpoint} ({e})"}
    except Exception as e:
        yield {"error": True, "message": str(e)}

def call_openai_compatible(
    messages: list,
    model: str,
    api_url: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
    timeout: int = 120,
) -> tuple:
    if not REQUESTS_AVAILABLE:
        return None, None, "requests library not available."
    if not api_url:
        return None, None, "API URL non configurata."
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            thinking = msg.get("reasoning_content", msg.get("reasoning", None))
            content, thinking = parse_thinking_and_content(content, thinking)
            if not content and thinking:
                content = thinking
                thinking = None
            return content, thinking, None
        return None, None, f"API error {resp.status_code}: {resp.text}"
    except requests.exceptions.Timeout:
        return None, None, f"Timeout ({timeout}s) nel contattare l'API."
    except Exception as e:
        return None, None, str(e)


def call_openai_compatible_stream(
    messages: list,
    model: str,
    api_url: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
    timeout: int = 120,
):
    if not REQUESTS_AVAILABLE:
        yield {"error": True, "message": "requests library not available"}
        return
    if not api_url:
        yield {"error": True, "message": "API URL non configurata."}
        return
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
        }
        resp = requests.post(api_url, json=payload, headers=headers, stream=True, timeout=int(timeout or 120))
        if resp.status_code != 200:
            yield {"error": True, "message": f"API error {resp.status_code}: {resp.text[:200]}"}
            return
        for line in resp.iter_lines(chunk_size=1, decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                yield {"done": True}
                break
            try:
                data = json.loads(data_str)
                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                thinking = delta.get("reasoning_content", delta.get("reasoning", ""))
                result = {}
                if content:
                    result["token"] = content
                if thinking:
                    result["thinking"] = thinking
                if result:
                    yield result
                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    yield {"done": True, "done_reason": finish_reason, "truncated": finish_reason == "length"}
                    break
            except json.JSONDecodeError:
                continue
    except requests.exceptions.Timeout:
        yield {"error": True, "message": f"Timeout ({timeout}s) nella connessione API."}
    except Exception as e:
        yield {"error": True, "message": str(e)}


def call_anthropic(
    messages: list,
    model: str,
    api_url: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
) -> tuple:
    if not REQUESTS_AVAILABLE:
        return None, "requests library not available."
    if not api_url:
        return None, "API URL non configurata."
    try:
        system_msg = ""
        anthropic_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg += m["content"] + "\n"
            elif m["role"] in ("user", "assistant"):
                anthropic_msgs.append({"role": m["role"], "content": m["content"]})

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "messages": anthropic_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg.strip():
            payload["system"] = system_msg.strip()

        resp = requests.post(api_url, json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("content", [{}])[0].get("text", ""), None

        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            detail = resp.text
        return None, f"Anthropic error {resp.status_code}: {detail}"
    except Exception as e:
        return None, str(e)


def call_ai_model_stream(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout):
    # Unified generator yielding chunks of tokens
    if provider in ('sigma_engine', 'sigma'):
        from core.engine import sigma_engine
        prompt_text = messages[-1].get("content", "") if messages else ""
        sys_text = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
        return sigma_engine.generate_stream(prompt_text, system_prompt=sys_text, temperature=temperature, max_tokens=max_tokens)

    route_provider = provider
    if route_provider in ('deepseek', 'openai'):
        route_provider = 'api'
    elif route_provider not in ('ollama', 'api', 'anthropic'):
        route_provider = 'api'
    ac = ai_cfg.get("providers", {}).get(provider, {})
    try:
        if route_provider == "ollama":
            return call_ollama_stream(messages, model, endpoint, temperature, max_tokens, top_p,
                ac.get("top_k", 40), ac.get("repeat_penalty", 1.1), ac.get("num_ctx", 8192), ac.get("seed", 0), request_timeout)
        elif route_provider == "api":
            return call_openai_compatible_stream(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
        elif route_provider == "anthropic":
            # Anthropic fallback to non-stream, yielding the entire text as a single token
            content, thinking = call_anthropic(messages, model, api_url, api_key, temperature, max_tokens, top_p)
            def _single_gen():
                if content: yield {"token": content}
                if thinking: yield {"thinking": thinking}
                yield {"done": True}
            return _single_gen()
    except Exception as e:
        def _exc_gen(): yield {"error": True, "message": str(e)}
        return _exc_gen()
    
    def _unk_gen(): yield {"error": True, "message": "Provider sconosciuto"}
    return _unk_gen()