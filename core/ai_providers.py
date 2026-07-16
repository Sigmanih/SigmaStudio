# ==============================================================================
# core/ai_providers.py — AI Provider Abstraction Layer
# Sigma Studio v6 — Unified interface for calling different AI backends
# ==============================================================================
"""Unified interface for calling different AI backends (Ollama, OpenAI, Anthropic)."""

import json
import os
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
    "active_provider": "ollama",
    "active_model": "llama3.2",
    "providers": {
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
    "code": {
        "label": "Codice / Sviluppo",
        "temperature": 0.3,
        "max_tokens": 4096,
        "num_ctx": 8192,
        "top_p": 0.85,
        "top_k": 30,
        "repeat_penalty": 1.2,
        "description": "Preciso, deterministico, ideale per generare e modificare codice"
    },
    "mathematics": {
        "label": "Matematica / Ricerca",
        "temperature": 0.4,
        "max_tokens": 8192,
        "num_ctx": 16384,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "description": "Ragionamento logico, dimostrazioni, analisi formale"
    },
    "creative": {
        "label": "Creativo / Brainstorming",
        "temperature": 0.9,
        "max_tokens": 2048,
        "num_ctx": 4096,
        "top_p": 0.95,
        "top_k": 50,
        "repeat_penalty": 1.0,
        "description": "Creativo e divergente, ideale per brainstorming e scrittura"
    },
    "analysis": {
        "label": "Analisi Dati",
        "temperature": 0.2,
        "max_tokens": 4096,
        "num_ctx": 32768,
        "top_p": 0.8,
        "top_k": 25,
        "repeat_penalty": 1.3,
        "description": "Analitico, contesto ampio, preciso"
    },
    "conversation": {
        "label": "Conversazione / Chat",
        "temperature": 0.7,
        "max_tokens": 2048,
        "num_ctx": 4096,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "description": "Bilanciato per conversazione generale"
    },
    "web_search": {
        "label": "Ricerca Web",
        "temperature": 0.5,
        "max_tokens": 2048,
        "num_ctx": 4096,
        "top_p": 0.85,
        "top_k": 35,
        "repeat_penalty": 1.1,
        "description": "Bilanciato, sintetico, per ricerca informazioni"
    },
}


def detect_execution_profile(message: str, context: str = "") -> str:
    """Detect the most appropriate execution profile based on message content.

    Analyzes the user message for keywords to determine if the task is
    code-related, mathematical, creative, analytical, or general conversation.

    Returns:
        Profile key: 'code', 'mathematics', 'creative', 'analysis',
                    'conversation', or 'web_search'
    """
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
        'teorema', 'lemma', 'dimostrazione',
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

def resolve_provider_config(ai_cfg: dict, model_name: str):
    """Find the provider configuration that should handle the given model.

    Strategy:
    1. Exact match in any provider's models[] list
    2. Match against provider's default model
    3. Prefix match (e.g. 'deepseek-chat' starts with 'deepseek')
    4. Cloud providers have well-known prefixes → if matched, use that provider
    5. FALLBACK: anything unknown is Ollama (local), never route unknowns to cloud

    Returns:
        Tuple of (provider_key, provider_config). Always returns a valid tuple.
    """
    providers = ai_cfg.get("providers", {})
    best_match = None

    cloud_prefixes = {
        'deepseek': 'deepseek-',
        'gpt-': 'openai',
        'o1': 'openai',
        'o3-': 'openai',
        'claude-': 'anthropic',
        'llama-3.3': 'groq',
        'llama-3.1-8b': 'groq',
        'mixtral-8x7b': 'groq',
        'gemma2-9b': 'groq',
        'deepseek-r1-distill': 'groq',
        'openai/': 'openrouter',
        'anthropic/': 'openrouter',
        'google/': 'openrouter',
        'mistral/': 'openrouter',
        'gemini-': 'google',
        'gemma-3': 'google',
        'mistral-': 'mistral',
        'mistralai/': 'together',
        'codestral': 'mistral',
        'open-mistral': 'mistral',
        'grok-': 'xai',
        'sonar': 'perplexity',
        'meta-llama/': 'together',
        'deepseek-ai/': 'together',
        'Qwen/': 'together',
        'qwen-': 'qwen',
        'qwen2': 'qwen',
        'glm-': 'glm',
        'moonshot': 'moonshot',
        'yi-': 'yi',
    }

    for pk, pv in providers.items():
        model_list = pv.get("models", [])
        default_model = pv.get("model", "")

        if model_name in model_list:
            return pk, pv
        if model_name == default_model:
            best_match = (pk, pv)
        if not best_match:
            for known in model_list:
                if model_name.startswith(known.split("-")[0]) or known.startswith(
                    model_name.split("-")[0]
                ):
                    best_match = (pk, pv)
                    break

    if best_match:
        return best_match

    for prefix, provider_key in cloud_prefixes.items():
        if model_name.startswith(prefix):
            if provider_key in providers:
                return provider_key, providers[provider_key]
            return provider_key, providers.get(provider_key, {})

    # FALLBACK: unknown models are ALWAYS Ollama (local)
    return "ollama", providers.get("ollama", {})


# ---------------------------------------------------------------------------
# AI Call implementations
# ---------------------------------------------------------------------------

# Centralized AI model caller — eliminates 3x duplication across codebase
def call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout):
    """Unified AI model caller used by agent_orchestrator, execute_loop, loop_handler.
    Eliminates 3x code duplication."""
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

def call_ollama(
    messages: list,
    model: str,
    endpoint: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
    num_ctx: int = 8192,
    seed: int = 0,
    timeout: int = 300,
) -> tuple:
    if not REQUESTS_AVAILABLE:
        return None, None, "requests library not available. Install with: pip install requests"
    try:
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "repeat_penalty": repeat_penalty,
            "num_ctx": num_ctx,
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
                if tags_resp.status_code == 200:
                    models_data = tags_resp.json()
                    models_list = [m.get("name") for m in models_data.get("models", [])]
                    if models_list:
                        fallback_model = models_list[0]
                        log.warning("Ollama model '%s' not found. Falling back to first available model: '%s'", model, fallback_model)
                        payload["model"] = fallback_model
                        resp = requests.post(endpoint, json=payload, timeout=timeout)
            except Exception as ex:
                log.error("Failed to query Ollama tags for fallback: %s", ex)

        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("message", {})
            content = msg.get("content", "")
            thinking = msg.get("thinking", msg.get("reasoning_content", None))
            if not content and thinking:
                content = thinking
                thinking = None
            return content, thinking, None
        return None, None, f"Ollama error {resp.status_code}: {resp.text}"
    except requests.exceptions.ConnectionError:
        return None, None, f"Impossibile connettersi a Ollama su {endpoint}."
    except requests.exceptions.Timeout:
        return None, None, f"Timeout ({timeout}s) nel contattare Ollama."
    except Exception as e:
        return None, None, str(e)


def call_ollama_stream(
    messages: list,
    model: str,
    endpoint: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
    num_ctx: int = 8192,
    seed: int = 0,
    timeout: int = 300,
):
    if not REQUESTS_AVAILABLE:
        yield {"error": True, "message": "requests library not available"}
        return
    try:
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "repeat_penalty": repeat_penalty,
            "num_ctx": num_ctx,
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
                result = {}
                if not content and thinking:
                    result["token"] = thinking
                else:
                    if content:
                        result["token"] = content
                    if thinking:
                        result["thinking"] = thinking
                if result:
                    yield result
                if data.get("done", False):
                    yield {"done": True}
                    break
            except json.JSONDecodeError:
                continue
    except requests.exceptions.Timeout:
        yield {"error": True, "message": f"Timeout ({timeout}s) - il modello sta impiegando troppo tempo."}
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
            if not thinking:
                thinking = data.get("reasoning_content", data.get("thinking", None))
            return content or data.get("response", ""), thinking, None
        return None, None, f"API error {resp.status_code}: {resp.text}"
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
                if choice.get("finish_reason"):
                    yield {"done": True}
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
    """Unified generator yielding chunks of tokens in the format {'token': '...', 'thinking': '...'} or {'done': True} or {'error': True, 'message': '...'}"""
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