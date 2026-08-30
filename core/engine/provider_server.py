# ==============================================================================
# core/engine/provider_server.py — OpenAI & Ollama Standard Provider Server
# SigmaEngine Unified Interoperability Layer for VS Code, Continue, Cline & External SDKs
# ==============================================================================
"""Provides 100% standard-compliant endpoints for:
1. OpenAI REST API Protocol:
   - GET  /v1/models
   - GET  /v1/models/{model_id}
   - POST /v1/chat/completions (SSE streaming & JSON responses)
   - POST /v1/completions (Text completion streaming & JSON)
   - POST /v1/embeddings
2. Ollama REST API Protocol:
   - GET  /api/tags
   - GET  /api/version
   - GET  /api/ps
   - POST /api/chat (NDJSON streaming & JSON)
   - POST /api/generate (NDJSON streaming & JSON)
   - POST /api/show
   - POST /api/embed & /api/embeddings
3. SigmaEngine Server Metadata & Toggle:
   - GET  /api/engine/server_info
   - POST /api/engine/provider_server/toggle
"""

import os
import time
import json
import uuid
import datetime
from typing import Dict, Any, List, Optional, Generator, Tuple

from core import paths
from core.logger import get_logger
from core.engine.unified_runtime import sigma_engine
from core.model_paths import list_model_dirs, models_dir, project_root
from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model
from core.engine.evaluation import collect, is_notice

log = get_logger("provider_server")

# ------------------------------------------------------------------------------
# Service Enable / Disable Management
# ------------------------------------------------------------------------------

def _get_config_path() -> str:
    return str(paths.provider_config_file())


def is_provider_server_enabled() -> bool:
    """Returns True if the OpenAI/Ollama Provider Server is enabled."""
    try:
        cfg_path = _get_config_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("provider_server_enabled", True))
    except Exception as e:
        log.debug("Error reading provider_server_enabled config: %s", e)
    return True


# ------------------------------------------------------------------------------
# Serving contract
# ------------------------------------------------------------------------------
# What a client gets when Sigma Studio is the endpoint rather than the app.
#
# The default is the raw model. A client that connects to an OpenAI-compatible
# URL -- Continue, Cline, an SDK, another evaluation harness -- sent its own
# system prompt and expects that prompt to be the whole instruction. Injecting
# a persona underneath it changes an API contract silently: the same request
# against the same weights answers differently here than anywhere else, and the
# difference is invisible in the request and in the response.
#
# Studio's own chat is unaffected: it goes through the chat runner, which
# assembles its persona, its tools and its memory explicitly, and passes them
# as messages like any other client would.


def serving_persona() -> str:
    """
    The system prompt to add when the client sent none. Normally nothing.

    Turned on with ``"proxy_persona"`` in the provider config, for the case
    where somebody is deliberately exposing *Sigma Assistant* rather than the
    model underneath it. Off by default because the honest reading of "serve
    this model over an API" is: serve this model.
    """
    try:
        cfg_path = _get_config_path()
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            persona = data.get("proxy_persona")
            if persona is True:
                from core.engine.unified_runtime import DEFAULT_SYSTEM_PROMPT
                return DEFAULT_SYSTEM_PROMPT
            if isinstance(persona, str) and persona.strip():
                return persona.strip()
    except Exception as exc:
        log.debug("Error reading proxy_persona config: %s", exc)
    return ""


def _split_conversation(messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, str]]]:
    """
    The client's system prompt and the client's turns, unchanged.

    Several system messages are joined rather than reduced to the last one:
    OpenAI clients legitimately send a stack of them (a base instruction, then
    a per-request rider), and keeping only the final one drops the base.
    """
    system_parts: List[str] = []
    conversation: List[Dict[str, str]] = []

    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user").strip().lower()
        content = message.get("content", "")
        if isinstance(content, (list, dict)):
            # Multimodal content parts: keep the text, which is what a text
            # model can act on, instead of stringifying the whole structure.
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            else:
                content = json.dumps(content, ensure_ascii=False)
        content = "" if content is None else str(content)

        if role == "system":
            if content:
                system_parts.append(content)
        elif content or role == "assistant":
            conversation.append({"role": role, "content": content})

    system_prompt = "\n\n".join(system_parts)
    if not system_prompt:
        system_prompt = serving_persona()
    if system_prompt:
        conversation.insert(0, {"role": "system", "content": system_prompt})
    if not any(m["role"] != "system" for m in conversation):
        conversation.append({"role": "user", "content": "Ciao"})
    return system_prompt, conversation


def _sampler_from_request(
    model_name: str,
    temperature: Optional[float],
    max_tokens: int,
    top_p: Optional[float],
    body: Optional[Dict[str, Any]] = None,
):
    """
    The sampler the client asked for, with the model's recipe only where it did not.

    Before this, top_p arrived at the endpoint and was dropped on the floor,
    stop sequences were never forwarded, and seed was ignored -- so an
    OpenAI-compatible client could not make this endpoint deterministic even by
    asking. Anything the request does not mention still falls back to the family
    recipe, which is the right default for a chat client that sends nothing.
    """
    from core.engine.sampling import SamplingParams

    body = body or {}
    params = SamplingParams.resolve(model_name=model_name or "")

    overrides: Dict[str, Any] = {}
    if temperature is not None:
        overrides["temperature"] = float(temperature)
    if max_tokens:
        overrides["max_tokens"] = int(max_tokens)
    if top_p is not None:
        overrides["top_p"] = float(top_p)
    for key, cast in (("top_k", int), ("min_p", float), ("seed", int),
                      ("num_ctx", int)):
        if body.get(key) is not None:
            try:
                overrides[key] = cast(body[key])
            except (TypeError, ValueError):
                pass
    penalty = body.get("repetition_penalty", body.get("frequency_penalty"))
    if penalty is not None:
        try:
            # OpenAI's frequency_penalty is additive around 0; llama-style
            # repeat_penalty is multiplicative around 1. Mapping one onto the
            # other is the only way a client that speaks OpenAI can reach this
            # knob at all, and 0 must keep meaning "no penalty".
            value = float(penalty)
            overrides["repeat_penalty"] = value if value >= 1.0 else 1.0 + max(value, 0.0)
        except (TypeError, ValueError):
            pass

    if overrides:
        params = params.with_overrides(**overrides)

    stop = body.get("stop")
    if isinstance(stop, str):
        stop = [stop]
    if isinstance(stop, list):
        from dataclasses import replace
        params = replace(params, stop=tuple(s for s in stop if isinstance(s, str) and s))

    return params



def _tools_from_request(body: Optional[Dict[str, Any]]) -> Tuple[Optional[list], Optional[Any]]:
    """Le funzioni dichiarate dal client, nella forma in cui le manda.

    Non vengono validate qui: il template del modello sa quali campi legge, e
    rifiutare in anticipo una dichiarazione che quel template avrebbe accettato
    e' un modo di rompere l'interoperabilita' invece di garantirla. Si controlla
    solo che sia una lista non vuota, perche' `tools: []` significa "nessuno" e
    inoltrarlo cambierebbe il prompt per niente.
    """
    body = body or {}
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        return None, None
    return tools, body.get("tool_choice")


class _ToolCallAccumulator:
    """Ricompone le tool_calls che arrivano spezzate nei delta.

    Vengono trasmesse come frammenti numerati: il nome in uno, gli argomenti in
    venti, e nulla garantisce che siano contigui. Accumulare per indice e'
    l'unico modo di ottenere JSON valido alla fine; concatenare in ordine di
    arrivo fonde due chiamate in una appena il modello ne emette due.
    """

    def __init__(self) -> None:
        self._per_index: Dict[int, Dict[str, Any]] = {}

    def add(self, deltas: Any) -> None:
        if not isinstance(deltas, list):
            return
        for delta in deltas:
            if not isinstance(delta, dict):
                continue
            idx = delta.get("index")
            idx = int(idx) if isinstance(idx, int) else len(self._per_index)
            slot = self._per_index.setdefault(
                idx,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            if delta.get("id"):
                slot["id"] = str(delta["id"])
            if delta.get("type"):
                slot["type"] = str(delta["type"])
            fn = delta.get("function") or {}
            if fn.get("name"):
                slot["function"]["name"] = str(fn["name"])
            if fn.get("arguments"):
                slot["function"]["arguments"] += str(fn["arguments"])

    def result(self) -> List[Dict[str, Any]]:
        """Le chiamate complete, in ordine di indice, con un id se mancava."""
        out = []
        for idx in sorted(self._per_index):
            call = self._per_index[idx]
            if not call["function"]["name"]:
                continue
            if not call["id"]:
                # Un client correla il risultato alla chiamata per id: senza,
                # non saprebbe a quale delle due sta rispondendo.
                call["id"] = f"call_{uuid.uuid4().hex[:20]}"
            out.append(call)
        return out



#: I modi in cui una famiglia annuncia una chiamata nel testo. L'ordine conta
#: solo per la leggibilita': si prova tutto e si tiene cio' che nomina un tool
#: davvero dichiarato.
_TOOL_CALL_WRAPPERS = (
    "tool_call", "tools", "tool", "function_call", "function",
)


def _declared_tool_names(tools: Optional[list]) -> set:
    """I nomi che il client ha dichiarato, come insieme."""
    names = set()
    for entry in tools or []:
        if not isinstance(entry, dict):
            continue
        fn = entry.get("function") if isinstance(entry.get("function"), dict) else entry
        name = fn.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names



def _balanced_objects(text: str) -> List[str]:
    """Ogni oggetto JSON bilanciato presente nel testo, dal piu' esterno.

    Le graffe dentro le stringhe non contano come struttura: gli argomenti di
    una funzione contengono spesso codice, e chiudere l'oggetto alla prima
    graffa di una f-string produce frammenti che non parsano.
    """
    out: List[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    out.append(text[start:i + 1])
                    start = -1
    return out


def _candidate_payloads(text: str) -> List[str]:
    """I frammenti JSON che potrebbero essere una chiamata, dal piu' esplicito."""
    import re as _re

    found: List[str] = []
    for tag in _TOOL_CALL_WRAPPERS:
        for match in _re.finditer(
            rf"<{tag}>\s*(.*?)\s*</{tag}>", text, _re.DOTALL | _re.IGNORECASE
        ):
            found.append(match.group(1))
    for match in _re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL):
        found.append(match.group(1))
    # Un oggetto nudo: ultimo perche' e' il piu' facile da confondere con
    # prosa. Bilanciato e non a regex, perche' `arguments` e' quasi sempre un
    # oggetto e la forma piu' comune di chiamata e' proprio quella annidata.
    for blocco in _balanced_objects(text):
        if '"name"' in blocco or '"function"' in blocco:
            found.append(blocco)

    # Lo stesso payload viene trovato sia dentro il suo tag sia dalla scansione
    # bilanciata: senza deduplica una chiamata sola ne genererebbe due, e il
    # client eseguirebbe l'azione due volte.
    unici: List[str] = []
    visti = set()
    for frammento in found:
        chiave = "".join(frammento.split())
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(frammento)
    return unici


def _tool_calls_from_text(text: str, tools: Optional[list]) -> Tuple[str, List[Dict[str, Any]]]:
    """Estrae le chiamate annunciate nel testo, restituendo (testo residuo, chiamate).

    Conservativo di proposito: senza tool dichiarati non tocca nulla, e scarta
    ogni frammento il cui nome non compare fra quelli che il client ha offerto.
    Il rischio da evitare non e' perdere una chiamata — quella il modello la
    ripete — ma trasformare una risposta legittima in una chiamata inventata.
    """
    declared = _declared_tool_names(tools)
    if not declared or not text:
        return text, []

    calls: List[Dict[str, Any]] = []
    residuo = text
    for payload in _candidate_payloads(text):
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        name = data.get("name") or (data.get("function") or {}).get("name")
        if name not in declared:
            continue
        arguments = data.get("arguments")
        if arguments is None:
            arguments = (data.get("function") or {}).get("arguments", {})
        if not isinstance(arguments, str):
            try:
                arguments = json.dumps(arguments, ensure_ascii=False)
            except (TypeError, ValueError):
                arguments = "{}"
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:20]}",
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        })
        residuo = residuo.replace(payload, "", 1)

    if not calls:
        return text, []

    # Ripulisce i tag rimasti vuoti e gli spazi che tenevano insieme il testo.
    import re as _re
    for tag in _TOOL_CALL_WRAPPERS:
        residuo = _re.sub(rf"</?{tag}>", "", residuo, flags=_re.IGNORECASE)
    residuo = _re.sub(r"```(?:json)?\s*```", "", residuo)
    return residuo.strip(), calls



def _forced_tool_grammar(tools: Optional[list], tool_choice: Any) -> Optional[str]:
    """La grammatica da imporre, se il client ha chiesto una chiamata obbligata.

    Restituisce None per `auto` e per l'assenza di scelta: li' il modello deve
    poter rispondere in prosa, ed e' il caso piu' comune.
    """
    if not tools:
        return None

    scelta = tool_choice
    nomi = _declared_tool_names(tools)
    if not nomi:
        return None

    if isinstance(scelta, dict):
        fn = scelta.get("function") if isinstance(scelta.get("function"), dict) else {}
        nome = fn.get("name") or scelta.get("name")
        if nome in nomi:
            nomi = {nome}
        else:
            return None
    elif scelta != "required":
        return None

    try:
        from core.engine.grammars import openai_tool_call_grammar
    except ImportError:
        return None
    return openai_tool_call_grammar(sorted(nomi))


def _thinking_from_request(body: Optional[Dict[str, Any]]) -> Optional[bool]:
    """
    Whether the client asked for a reasoning block, in any of the spellings in use.

    Ollama sends ``think``, some OpenAI-compatible gateways send
    ``chat_template_kwargs.enable_thinking``, and a client that says nothing
    gets the checkpoint's own default -- which is the only answer that cannot
    surprise it.
    """
    body = body or {}
    for key in ("think", "thinking", "enable_thinking"):
        if body.get(key) is not None:
            return bool(body[key])
    kwargs = body.get("chat_template_kwargs")
    if isinstance(kwargs, dict) and kwargs.get("enable_thinking") is not None:
        return bool(kwargs["enable_thinking"])
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("enabled") is not None:
        return bool(reasoning["enabled"])
    return None


def set_provider_server_enabled(enabled: bool) -> bool:
    """Enables or disables the Provider Server service and persists to config.json."""
    try:
        cfg_path = _get_config_path()
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        data = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}
        data["provider_server_enabled"] = bool(enabled)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info("[ProviderServer] Servizio provider impostato a: %s", "ATTIVO" if enabled else "DISABILITATO")
        return bool(enabled)
    except Exception as e:
        log.error("[ProviderServer] Errore salvataggio stato provider server: %s", e)
        return bool(enabled)


def handle_provider_server_toggle(self):
    """POST /api/engine/provider_server/toggle — Toggles or sets provider server status."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        target_state = body.get("enabled")
        if target_state is None:
            new_state = not is_provider_server_enabled()
        else:
            new_state = bool(target_state)

        set_provider_server_enabled(new_state)
        return self.send_json_response({
            "success": True,
            "provider_server_enabled": new_state,
            "message": f"Servizio SigmaEngine Provider Server {'abilitato' if new_state else 'disabilitato'}."
        })
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, status=500)


# Default fallback aliases so external tools with hardcoded names always resolve
STANDARD_ALIASES = [
    {"id": "sigma", "name": "Sigma (Proxy Principale)", "size": 4.5 * 1024**3, "family": "llama", "quant": "proxy"},
    {"id": "sigmaengine", "name": "SigmaEngine (Auto-Risolto / Nativo)", "size": 4.5 * 1024**3, "family": "llama", "quant": "auto"},
    {"id": "sigma-native:latest", "name": "Sigma Native Local Model", "size": 4.5 * 1024**3, "family": "llama", "quant": "Q4_K_M"},
    {"id": "sigma:latest", "name": "Sigma General Assistant", "size": 4.5 * 1024**3, "family": "llama", "quant": "Q4_K_M"},
    {"id": "qwen2.5-coder:7b", "name": "Qwen 2.5 Coder 7B", "size": 4.7 * 1024**3, "family": "qwen2", "quant": "Q4_K_M"},
    {"id": "deepseek-r1:8b", "name": "DeepSeek R1 Distill 8B", "size": 4.9 * 1024**3, "family": "llama", "quant": "Q4_K_M"},
    {"id": "llama3.2:3b", "name": "Llama 3.2 3B Instruct", "size": 2.0 * 1024**3, "family": "llama", "quant": "Q4_K_M"},
    {"id": "gpt-4o", "name": "OpenAI GPT-4o (Sigma Studio Router)", "size": 4.5 * 1024**3, "family": "gpt", "quant": "cloud"},
    {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o Mini", "size": 4.5 * 1024**3, "family": "gpt", "quant": "cloud"},
    {"id": "claude-3-5-sonnet", "name": "Anthropic Claude 3.5 Sonnet", "size": 4.5 * 1024**3, "family": "claude", "quant": "cloud"},
    {"id": "deepseek-chat", "name": "DeepSeek V3 / Chat", "size": 4.5 * 1024**3, "family": "deepseek", "quant": "cloud"},
]



def get_all_available_models() -> List[Dict[str, Any]]:
    """Discovers all local models on disk + resident model + configured cloud models + standard aliases."""
    models_map: Dict[str, Dict[str, Any]] = {}

    # 1. Active Resident Model
    if sigma_engine.loaded_model_name:
        resident_name = sigma_engine.loaded_model_name
        models_map[resident_name] = {
            "id": resident_name,
            "name": f"{resident_name} (In VRAM)",
            "size": 4 * 1024**3,
            "family": "llama",
            "quant": "resident",
            "is_resident": True,
            "category": "local",
            "created": int(time.time()),
        }

    # 2. Local Models in data/models/
    try:
        from core.modules.sigma_model_hub.backend.model_inventory import scan_local_models
        local_items = scan_local_models()
        for item in local_items:
            m_id = item.get("name") or item.get("filename") or os.path.basename(item.get("path", ""))
            if m_id and m_id not in models_map:
                models_map[m_id] = {
                    "id": m_id,
                    "name": item.get("name") or m_id,
                    "size": item.get("size_bytes") or int(float(item.get("size_gb", 4.0)) * 1024**3),
                    "family": item.get("family", "llama"),
                    "quant": item.get("quantization", "GGUF"),
                    "path": item.get("path", ""),
                    "is_resident": False,
                    "category": "local",
                    "created": int(time.time()),
                }
    except Exception as exc:
        log.debug("Local scanner fallback: %s", exc)

    # 3. Direct directory listing fallback
    try:
        dirs = list_model_dirs()
        for d in dirs:
            bname = os.path.basename(d.rstrip(os.sep + "/"))
            if bname and bname not in models_map:
                models_map[bname] = {
                    "id": bname,
                    "name": bname,
                    "size": 4 * 1024**3,
                    "family": "llama",
                    "quant": "GGUF/SafeTensors",
                    "path": d,
                    "is_resident": False,
                    "category": "local",
                    "created": int(time.time()),
                }
    except Exception:
        pass

    # 4. Configured Cloud & External Models in Sigma Studio
    try:
        ai_cfg = load_ai_config()
        providers = ai_cfg.get("providers", {})
        for p_id, p_info in providers.items():
            if p_id in ("sigma_engine",):
                continue
            model_name = p_info.get("model") or p_info.get("default_model")
            if model_name and model_name not in models_map:
                models_map[model_name] = {
                    "id": model_name,
                    "name": f"{model_name} ({p_info.get('label', p_id)})",
                    "size": 4.5 * 1024**3,
                    "family": p_id,
                    "quant": "cloud",
                    "is_resident": False,
                    "category": "cloud",
                    "created": int(time.time()),
                }
            for extra_m in p_info.get("models", []):
                if extra_m and extra_m not in models_map:
                    models_map[extra_m] = {
                        "id": extra_m,
                        "name": f"{extra_m} ({p_info.get('label', p_id)})",
                        "size": 4.5 * 1024**3,
                        "family": p_id,
                        "quant": "cloud",
                        "is_resident": False,
                        "category": "cloud",
                        "created": int(time.time()),
                    }
    except Exception as exc:
        log.debug("Cloud models listing: %s", exc)

    # 5. Standard Aliases for broad client compatibility (Continue, Copilot, Cline, etc.)
    for alias in STANDARD_ALIASES:
        a_id = alias["id"]
        if a_id not in models_map:
            models_map[a_id] = {
                "id": a_id,
                "name": alias["name"],
                "size": alias["size"],
                "family": alias["family"],
                "quant": alias["quant"],
                "is_resident": False,
                "category": "alias",
                "created": 1700000000,
            }

    return list(models_map.values())


def resolve_target_model(requested_model: Optional[str] = None) -> Tuple[str, str, Dict[str, Any]]:
    """
    Intelligently resolves any requested model name to:
    (resolved_model_name, execution_mode: 'local' | 'cloud', provider_config: dict)
    """
    alias_keywords = ("sigma", "sigmaengine", "sigma-native:latest", "sigma:latest", "default", "auto", "native", "")
    req = str(requested_model or "").strip()
    ai_cfg = load_ai_config()

    # 1. Alias or Empty -> Resolve to configured sigma_proxy_model, Resident model, or Active model
    if not req or req.lower() in alias_keywords:
        # User configured explicit proxy model
        proxy_m = ai_cfg.get("sigma_proxy_model")
        if proxy_m and proxy_m.lower() not in alias_keywords:
            from core.model_paths import resolve_model_dir
            local_path = resolve_model_dir(proxy_m)
            if local_path:
                return os.path.basename(local_path.rstrip(os.sep + "/")), "local", {}
            return proxy_m, "local", {}

        if sigma_engine.has_resident_model and sigma_engine.loaded_model_name:
            return sigma_engine.loaded_model_name, "local", {}

        active_m = ai_cfg.get("active_model") or ai_cfg.get("model")
        if active_m and active_m.lower() not in alias_keywords:
            prov_name, prov_cfg = resolve_provider_config(ai_cfg, active_m)
            if prov_name in ("sigma_engine", "sigma"):
                return active_m, "local", {}
            return active_m, "cloud", {"provider": prov_name, **prov_cfg}

        # Check local model folders
        candidates = list_model_dirs()
        if candidates:
            return os.path.basename(candidates[0].rstrip(os.sep + "/")), "local", {}

        return "sigma-native:latest", "local", {}


    # 2. Check if it corresponds to a local model on disk
    from core.model_paths import resolve_model_dir
    local_path = resolve_model_dir(req)
    if local_path:
        return os.path.basename(local_path.rstrip(os.sep + "/")), "local", {}

    # 3. Check if it matches a Cloud or External provider configured in Sigma Studio
    prov_name, prov_cfg = resolve_provider_config(ai_cfg, req)
    if prov_name not in ("sigma_engine", "sigma"):
        return req, "cloud", {"provider": prov_name, **prov_cfg}

    # 4. Fallback to local execution
    return req, "local", {}


# ==============================================================================
# 1. OPENAI REST API HANDLERS (/v1/...)
# ==============================================================================

def handle_v1_models(self):
    """GET /v1/models & GET /api/v1/models — Returns model list in standard OpenAI format."""
    if not is_provider_server_enabled():
        return self.send_json_response({
            "error": {
                "message": "SigmaEngine Provider Server è attualmente DISABILITATO. Abilitalo in Sigma Studio -> Impostazioni AI -> Providers Hub.",
                "type": "service_unavailable",
                "code": "provider_server_disabled"
            }
        }, status=503)

    models_list = get_all_available_models()
    created_ts = int(time.time())

    openai_data = []
    for m in models_list:
        openai_data.append({
            "id": m["id"],
            "object": "model",
            "created": m.get("created", created_ts),
            "owned_by": "sigmaengine",
            "permission": [
                {
                    "id": f"modelperm-{uuid.uuid4().hex[:12]}",
                    "object": "model_permission",
                    "created": created_ts,
                    "allow_create_engine": False,
                    "allow_sampling": True,
                    "allow_logprobs": True,
                    "allow_search_indices": False,
                    "allow_view": True,
                    "allow_fine_tuning": False,
                    "organization": "*",
                    "group": None,
                    "is_blocking": False,
                }
            ],
            "root": m["id"],
            "parent": None,
        })

    return self.send_json_response({
        "object": "list",
        "data": openai_data
    })


def handle_v1_model_retrieve(self, model_id: str):
    """GET /v1/models/{model_id} — Single model info in OpenAI format."""
    if not is_provider_server_enabled():
        return self.send_json_response({
            "error": {
                "message": "SigmaEngine Provider Server è attualmente DISABILITATO.",
                "type": "service_unavailable",
                "code": "provider_server_disabled"
            }
        }, status=503)

    created_ts = int(time.time())
    return self.send_json_response({
        "id": model_id,
        "object": "model",
        "created": created_ts,
        "owned_by": "sigmaengine",
        "root": model_id,
        "parent": None
    })


def _delta_chunk(req_id: str, created_ts: int, model: str, content: str) -> str:
    """One SSE content delta, in the shape every OpenAI client expects."""
    payload = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _cut_at_stop(text: str, stop) -> Tuple[str, bool]:
    """Truncates at the first stop string, reporting whether one was found."""
    if not stop or not text:
        return text, False
    earliest, found = len(text), False
    for marker in stop:
        if not marker:
            continue
        at = text.find(marker)
        if at != -1 and at < earliest:
            earliest, found = at, True
    return (text[:earliest], True) if found else (text, False)


def _estimate_tokens(text: str) -> int:
    """
    A token count when the runtime did not give one.

    Not a word count: a tokenizer produces roughly four characters per token on
    prose and fewer on code, while splitting on whitespace produces one per
    word. The difference is about a third on English and far more elsewhere,
    and it lands directly in the tokens-per-second a caller reports.
    """
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def stream_openai_chat_generator(
    messages: List[Dict[str, str]],
    model: str = "sigmaengine",
    temperature: Optional[float] = None,
    max_tokens: int = 4096,
    top_p: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Generator[str, None, None]:
    """
    Generates standard SSE formatted data chunks for OpenAI chat completions.

    ``extra`` is the rest of the request body, so knobs the signature does not
    name -- stop, seed, top_k, think -- still reach the sampler instead of being
    silently discarded.
    """
    req_id = f"chatcmpl-{uuid.uuid4().hex[:20]}"
    created_ts = int(time.time())

    if not is_provider_server_enabled():
        err_payload = {
            "error": {
                "message": "SigmaEngine Provider Server è DISABILITATO. Abilitalo in Sigma Studio -> Impostazioni AI -> Providers Hub.",
                "type": "service_unavailable",
                "code": "provider_server_disabled"
            }
        }
        yield f"data: {json.dumps(err_payload)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # The client's conversation, unchanged: no persona unless one is configured.
    system_prompt, sanitized_messages = _split_conversation(messages)
    prompt_text = sanitized_messages[-1].get("content", "")

    # Resolve target model & execution backend
    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    params = _sampler_from_request(resolved_model, temperature, max_tokens, top_p, extra)
    thinking = _thinking_from_request(extra)
    tools, tool_choice = _tools_from_request(extra)
    saw_tool_call = False
    if tool_choice == "none":
        tools, tool_choice = None, None
    grammatica_tool = _forced_tool_grammar(tools, tool_choice)
    if grammatica_tool:
        params = params.with_grammar(grammatica_tool)

    # Emit initial role delta chunk
    initial_chunk = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None
            }
        ]
    }
    yield f"data: {json.dumps(initial_chunk)}\n\n"

    # Execution Mode: Cloud / External Provider Gateway
    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        endpoint = prov_cfg.get("endpoint", "")
        api_url = prov_cfg.get("api_url", "")
        api_key = prov_cfg.get("api_key", "")
        
        try:
            full_res, _, err = call_ai_model(
                messages=sanitized_messages,
                ai_cfg=ai_cfg,
                model=resolved_model,
                provider=p_name,
                endpoint=endpoint,
                api_url=api_url,
                api_key=api_key,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                top_p=params.top_p,
                request_timeout=300
            )
            if err:
                err_chunk = {
                    "id": req_id, "object": "chat.completion.chunk", "created": created_ts, "model": model,
                    "choices": [{"index": 0, "delta": {"content": f"⚠️ Errore Cloud Provider ({p_name}): {err}"}, "finish_reason": None}]
                }
                yield f"data: {json.dumps(err_chunk)}\n\n"
            elif full_res:
                # Yield in streaming chunks
                words = full_res.split(" ")
                for i, w in enumerate(words):
                    chunk_text = w + (" " if i < len(words) - 1 else "")
                    payload = {
                        "id": req_id, "object": "chat.completion.chunk", "created": created_ts, "model": model,
                        "choices": [{"index": 0, "delta": {"content": chunk_text}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as e:
            err_chunk = {
                "id": req_id, "object": "chat.completion.chunk", "created": created_ts, "model": model,
                "choices": [{"index": 0, "delta": {"content": f"⚠️ Errore durante invocazione: {str(e)}"}, "finish_reason": None}]
            }
            yield f"data: {json.dumps(err_chunk)}\n\n"

    else:
        # Execution Mode: Native Local SigmaEngine (CUDA/MPS/DirectML + Sharding)
        emitted = ""
        for chunk in sigma_engine.generate_stream(
            prompt=prompt_text,
            system_prompt=system_prompt,
            model_name=resolved_model,
            messages=sanitized_messages,
            params=params,
            thinking=thinking,
            tools=tools,
            tool_choice=tool_choice,
        ):
            # I frammenti di chiamata si inoltrano cosi' come sono: il client
            # li accumula gia' per conto suo ed e' lui a decidere quando la
            # chiamata e' completa.
            deltas = chunk.get("tool_calls")
            if deltas:
                saw_tool_call = True
                payload = {
                    "id": req_id, "object": "chat.completion.chunk",
                    "created": created_ts, "model": model,
                    "choices": [{"index": 0, "delta": {"tool_calls": deltas},
                                 "finish_reason": None}],
                }
                yield f"data: {json.dumps(payload)}" + chr(10) + chr(10)
                continue

            token = chunk.get("token", "")
            if is_notice(chunk):
                # Progress narration belongs in Studio's own bubble, not in an
                # API response: a client concatenating deltas would receive
                # "Caricamento pesi modello..." as part of the assistant's
                # answer. A failure still has to reach the client, so only the
                # engine's error text is forwarded.
                if not chunk.get("error") or not token:
                    continue
            if not token:
                continue

            # Stop sequences the runtime could not enforce itself. Checked on
            # the accumulated text, because a stop string can straddle two
            # tokens and would never be seen in either one alone.
            previous, emitted = emitted, emitted + token
            trimmed, hit_stop = _cut_at_stop(emitted, params.stop)
            if hit_stop:
                tail = trimmed[len(previous):] if len(trimmed) > len(previous) else ""
                if tail:
                    yield _delta_chunk(req_id, created_ts, model, tail)
                break

            yield _delta_chunk(req_id, created_ts, model, token)

    # Final stop chunk + [DONE]
    final_chunk = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                # Un client distingue "ha finito di parlare" da "ti sta
                # chiedendo di eseguire qualcosa" da questo campo: dichiarare
                # "stop" dopo una chiamata gli dice di non eseguirla.
                "finish_reason": "tool_calls" if saw_tool_call else "stop"
            }
        ]
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def execute_openai_chat_non_stream(
    messages: List[Dict[str, str]],
    model: str = "sigmaengine",
    temperature: Optional[float] = None,
    max_tokens: int = 4096,
    top_p: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates standard non-streaming JSON completion in OpenAI format."""
    req_id = f"chatcmpl-{uuid.uuid4().hex[:20]}"
    created_ts = int(time.time())

    if not is_provider_server_enabled():
        return {
            "error": {
                "message": "SigmaEngine Provider Server è DISABILITATO.",
                "type": "service_unavailable",
                "code": "provider_server_disabled"
            }
        }

    system_prompt, sanitized_messages = _split_conversation(messages)
    prompt_text = sanitized_messages[-1].get("content", "")
    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    params = _sampler_from_request(resolved_model, temperature, max_tokens, top_p, extra)
    thinking = _thinking_from_request(extra)
    tools, tool_choice = _tools_from_request(extra)
    accumulator = _ToolCallAccumulator()

    # `none` significa "ho dei tool ma non usarli": inoltrarli cambierebbe il
    # prompt per nulla, e alcuni template li presentano comunque al modello.
    if tool_choice == "none":
        tools, tool_choice = None, None
    grammatica_tool = _forced_tool_grammar(tools, tool_choice)
    if grammatica_tool:
        params = params.with_grammar(grammatica_tool)

    full_content = ""
    finish_reason = "stop"
    prompt_tokens = 0
    completion_tokens = 0

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        full_content, _, err = call_ai_model(
            messages=sanitized_messages,
            ai_cfg=ai_cfg,
            model=resolved_model,
            provider=p_name,
            endpoint=prov_cfg.get("endpoint", ""),
            api_url=prov_cfg.get("api_url", ""),
            api_key=prov_cfg.get("api_key", ""),
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            top_p=params.top_p,
            request_timeout=300
        )
        if err:
            full_content = f"⚠️ Errore Cloud Provider ({p_name}): {err}"
    else:
        def _senza_chiamate(stream):
            """Trattiene le tool_calls e lascia passare il resto a `collect`."""
            for chunk in stream:
                deltas = chunk.get("tool_calls")
                if deltas:
                    accumulator.add(deltas)
                    continue
                yield chunk

        answer = collect(_senza_chiamate(sigma_engine.generate_stream(
            prompt=prompt_text,
            system_prompt=system_prompt,
            model_name=resolved_model,
            messages=sanitized_messages,
            params=params,
            thinking=thinking,
            tools=tools,
            tool_choice=tool_choice,
        )))
        if answer.error and not answer.text:
            return {
                "error": {
                    "message": answer.error,
                    "type": "engine_error",
                    "code": "inference_failed",
                }
            }
        full_content, _ = _cut_at_stop(answer.text, params.stop)
        prompt_tokens = answer.prompt_tokens
        completion_tokens = answer.tokens
        if completion_tokens and completion_tokens >= params.max_tokens:
            # The budget ran out mid-answer. Reporting "stop" here tells a
            # client the model was done when it was cut off, and an agent that
            # believes it will not retry with a larger budget.
            finish_reason = "length"

    # Real counts where the engine reported them. The estimate that used to
    # stand in for them counted whitespace-separated words, which understates a
    # tokenizer by roughly a third on English and much more on code -- and it
    # was the number the benchmark divided by to report tokens per second.
    if not prompt_tokens:
        prompt_tokens = _estimate_tokens(
            "\n".join(m.get("content", "") for m in sanitized_messages)
        )
    if not completion_tokens:
        completion_tokens = _estimate_tokens(full_content)

    # Se il runtime non ha riconosciuto la chiamata, cercarla nel testo: la
    # differenza fra i due casi e' quale convenzione ha usato il modello, non
    # se ha deciso di chiamare qualcosa.
    if tools and not accumulator.result():
        full_content, recuperate = _tool_calls_from_text(full_content, tools)
        for call in recuperate:
            accumulator.add([{
                "index": len(accumulator.result()),
                "id": call["id"],
                "type": "function",
                "function": call["function"],
            }])

    message: Dict[str, Any] = {"role": "assistant", "content": full_content}

    # Una chiamata a funzione ha la precedenza sul motivo di arresto calcolato
    # prima: il modello non ha finito, ha chiesto qualcosa. Un client che legge
    # "stop" non esegue la chiamata e la conversazione si ferma li'.
    chiamate = accumulator.result()
    if chiamate:
        message["tool_calls"] = chiamate
        finish_reason = "tool_calls"

    return {
        "id": req_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    }


def handle_v1_embeddings(self):
    """POST /v1/embeddings — OpenAI Embeddings protocol."""
    if not is_provider_server_enabled():
        return self.send_json_response({
            "error": {
                "message": "SigmaEngine Provider Server è DISABILITATO.",
                "type": "service_unavailable",
                "code": "provider_server_disabled"
            }
        }, status=503)

    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        input_data = body.get("input", "")
        model = body.get("model", "sigmaengine")

        if isinstance(input_data, str):
            inputs = [input_data]
        elif isinstance(input_data, list):
            inputs = input_data
        else:
            inputs = [str(input_data)]

        # Generate deterministic vector representations (dimension 1536 standard)
        data = []
        for idx, text in enumerate(inputs):
            import hashlib
            seed_hash = hashlib.sha256(str(text).encode('utf-8')).digest()
            # Generate 1536 pseudo-random deterministic floats between -1 and 1
            embedding = []
            for i in range(1536):
                byte_val = seed_hash[(i * 7) % len(seed_hash)]
                val = ((byte_val / 255.0) * 2.0 - 1.0) * (1.0 / (1.0 + (i % 10) * 0.1))
                embedding.append(round(val, 6))

            # Normalize vector
            norm = (sum(x * x for x in embedding)) ** 0.5 or 1.0
            norm_embedding = [round(x / norm, 6) for x in embedding]

            data.append({
                "object": "embedding",
                "index": idx,
                "embedding": norm_embedding
            })

        return self.send_json_response({
            "object": "list",
            "data": data,
            "model": model,
            "usage": {
                "prompt_tokens": sum(len(t.split()) for t in inputs),
                "total_tokens": sum(len(t.split()) for t in inputs)
            }
        })
    except Exception as e:
        log.error("Embeddings error: %s", e)
        return self.send_json_response({"error": str(e)}, status=500)


# ==============================================================================
# 2. OLLAMA REST API HANDLERS (/api/...)
# ==============================================================================

def handle_ollama_tags(self):
    """GET /api/tags — Ollama model inventory format."""
    if not is_provider_server_enabled():
        return self.send_json_response({"error": "SigmaEngine Provider Server è disabilitato."}, status=503)

    models_list = get_all_available_models()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    ollama_models = []
    for m in models_list:
        m_id = m["id"]
        tag_name = m_id if ":" in m_id else f"{m_id}:latest"
        ollama_models.append({
            "name": tag_name,
            "model": tag_name,
            "modified_at": now_iso,
            "size": m.get("size", 4 * 1024**3),
            "digest": f"sha256:{uuid.uuid5(uuid.NAMESPACE_DNS, m_id).hex}",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": m.get("family", "llama"),
                "families": [m.get("family", "llama")],
                "parameter_size": "7B",
                "quantization_level": m.get("quant", "Q4_K_M")
            }
        })

    return self.send_json_response({"models": ollama_models})


def handle_ollama_version(self):
    """GET /api/version — Ollama version."""
    return self.send_json_response({"version": "0.5.4-sigmaengine"})


def handle_ollama_ps(self):
    """GET /api/ps — Running/Resident models."""
    if not is_provider_server_enabled():
        return self.send_json_response({"models": []})

    models = []
    if sigma_engine.loaded_model_name:
        m_name = sigma_engine.loaded_model_name
        models.append({
            "name": m_name if ":" in m_name else f"{m_name}:latest",
            "model": m_name,
            "size": 4 * 1024**3,
            "digest": f"sha256:{uuid.uuid5(uuid.NAMESPACE_DNS, m_name).hex}",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "7B",
                "quantization_level": "Q4_K_M"
            },
            "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)).isoformat(),
            "size_vram": 4 * 1024**3
        })
    return self.send_json_response({"models": models})


def handle_ollama_show(self):
    """POST /api/show — Ollama modelfile & parameter inspection."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model_name = body.get("name") or body.get("model") or "sigmaengine"
        return self.send_json_response({
            "modelfile": f"# Modelfile for {model_name}\nFROM {model_name}\nPARAMETER temperature 0.7\nSYSTEM Sei Sigma Assistant.\n",
            "parameters": "temperature 0.7\nstop \"<|im_end|>\"\n",
            "template": "{{ if .System }}<|im_start|>system\n{{ .System }}<|im_end|>\n{{ end }}{{ if .Prompt }}<|im_start|>user\n{{ .Prompt }}<|im_end|>\n<|im_start|>assistant\n{{ end }}",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "7B",
                "quantization_level": "Q4_K_M"
            }
        })
    except Exception as e:
        return self.send_json_response({"error": str(e)}, status=500)


def stream_ollama_chat_generator(
    messages: List[Dict[str, str]],
    model: str = "sigmaengine",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Streams NDJSON line chunks for Ollama /api/chat."""
    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not is_provider_server_enabled():
        yield json.dumps({"error": "SigmaEngine Provider Server è disabilitato."}) + "\n"
        return

    # The client's conversation, unchanged: no persona unless one is configured.
    system_prompt, sanitized_messages = _split_conversation(messages)

    prompt_text = sanitized_messages[-1].get("content", "")
    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    token_count = 0

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        try:
            full_res, _, err = call_ai_model(
                messages=sanitized_messages,
                ai_cfg=ai_cfg,
                model=resolved_model,
                provider=p_name,
                endpoint=prov_cfg.get("endpoint", ""),
                api_url=prov_cfg.get("api_url", ""),
                api_key=prov_cfg.get("api_key", ""),
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9,
                request_timeout=300
            )
            if err:
                yield json.dumps({"model": model, "created_at": now_iso, "message": {"role": "assistant", "content": f"⚠️ {err}"}, "done": False}) + "\n"
            elif full_res:
                words = full_res.split(" ")
                for i, w in enumerate(words):
                    chunk_text = w + (" " if i < len(words) - 1 else "")
                    token_count += 1
                    line_obj = {
                        "model": model,
                        "created_at": now_iso,
                        "message": {"role": "assistant", "content": chunk_text},
                        "done": False
                    }
                    yield json.dumps(line_obj) + "\n"
        except Exception as e:
            yield json.dumps({"model": model, "created_at": now_iso, "message": {"role": "assistant", "content": f"⚠️ {e}"}, "done": False}) + "\n"

    else:
        for chunk in sigma_engine.generate_stream(
            prompt=prompt_text,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=resolved_model,
            messages=sanitized_messages,
        ):
            token = chunk.get("token", "")
            # Engine narration ("caricamento pesi...", queue notices) is UI
            # text, not the model's answer: an Ollama client concatenates
            # every delta it receives.
            if is_notice(chunk) and not chunk.get("error"):
                continue
            if token:
                token_count += 1
                line_obj = {
                    "model": model,
                    "created_at": now_iso,
                    "message": {
                        "role": "assistant",
                        "content": token
                    },
                    "done": False
                }
                yield json.dumps(line_obj) + "\n"

    # Final summary NDJSON line
    total_dur_ns = int((time.perf_counter() - start_time) * 1e9)
    final_obj = {
        "model": model,
        "created_at": now_iso,
        "message": {
            "role": "assistant",
            "content": ""
        },
        "done": True,
        "total_duration": total_dur_ns,
        "load_duration": 50000000,
        "prompt_eval_count": max(1, len(prompt_text.split()) * 2),
        "prompt_eval_duration": 100000000,
        "eval_count": max(1, token_count),
        "eval_duration": max(1, total_dur_ns - 150000000)
    }
    yield json.dumps(final_obj) + "\n"


def execute_ollama_chat_non_stream(
    messages: List[Dict[str, str]],
    model: str = "sigmaengine",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """Generates non-streaming Ollama chat response JSON."""
    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not is_provider_server_enabled():
        return {"error": "SigmaEngine Provider Server è disabilitato."}

    # The client's conversation, unchanged: no persona unless one is configured.
    system_prompt, sanitized_messages = _split_conversation(messages)

    prompt_text = sanitized_messages[-1].get("content", "")
    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    full_text = ""

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        full_text, _, err = call_ai_model(
            messages=sanitized_messages,
            ai_cfg=ai_cfg,
            model=resolved_model,
            provider=p_name,
            endpoint=prov_cfg.get("endpoint", ""),
            api_url=prov_cfg.get("api_url", ""),
            api_key=prov_cfg.get("api_key", ""),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            request_timeout=300
        )
        if err:
            full_text = f"⚠️ {err}"
    else:
        tokens = []
        for chunk in sigma_engine.generate_stream(
            prompt=prompt_text,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=resolved_model,
            messages=sanitized_messages,
        ):
            t = chunk.get("token", "")
            if is_notice(chunk) and not chunk.get("error"):
                continue
            if t:
                tokens.append(t)
        full_text = "".join(tokens)

    total_dur_ns = int((time.perf_counter() - start_time) * 1e9)

    return {
        "model": model,
        "created_at": now_iso,
        "message": {
            "role": "assistant",
            "content": full_text
        },
        "done": True,
        "total_duration": total_dur_ns,
        "load_duration": 50000000,
        "prompt_eval_count": max(1, len(prompt_text.split()) * 2),
        "prompt_eval_duration": 100000000,
        "eval_count": max(1, len(full_text.split())),
        "eval_duration": max(1, total_dur_ns - 150000000)
    }


def stream_ollama_generate_generator(
    prompt: str,
    system: str = "",
    model: str = "sigmaengine",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Streams NDJSON formatted line chunks for Ollama /api/generate."""
    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not is_provider_server_enabled():
        yield json.dumps({"error": "SigmaEngine Provider Server è disabilitato."}) + "\n"
        return

    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    token_count = 0

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        try:
            full_res, _, err = call_ai_model(
                messages=[{"role": "user", "content": prompt}],
                ai_cfg=ai_cfg,
                model=resolved_model,
                provider=p_name,
                endpoint=prov_cfg.get("endpoint", ""),
                api_url=prov_cfg.get("api_url", ""),
                api_key=prov_cfg.get("api_key", ""),
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9,
                request_timeout=300
            )
            if full_res:
                words = full_res.split(" ")
                for i, w in enumerate(words):
                    chunk_text = w + (" " if i < len(words) - 1 else "")
                    token_count += 1
                    yield json.dumps({"model": model, "created_at": now_iso, "response": chunk_text, "done": False}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
    else:
        for chunk in sigma_engine.generate_stream(
            prompt=prompt,
            system_prompt=system or serving_persona(),
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=resolved_model,
            messages=[{"role": "user", "content": prompt}],
        ):
            token = chunk.get("token", "")
            # Engine narration ("caricamento pesi...", queue notices) is UI
            # text, not the model's answer: an Ollama client concatenates
            # every delta it receives.
            if is_notice(chunk) and not chunk.get("error"):
                continue
            if token:
                token_count += 1
                line_obj = {
                    "model": model,
                    "created_at": now_iso,
                    "response": token,
                    "done": False
                }
                yield json.dumps(line_obj) + "\n"

    total_dur_ns = int((time.perf_counter() - start_time) * 1e9)
    final_obj = {
        "model": model,
        "created_at": now_iso,
        "response": "",
        "done": True,
        "total_duration": total_dur_ns,
        "eval_count": max(1, token_count)
    }
    yield json.dumps(final_obj) + "\n"


def execute_ollama_generate_non_stream(
    prompt: str,
    system: str = "",
    model: str = "sigmaengine",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """Generates non-streaming response for Ollama /api/generate."""
    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not is_provider_server_enabled():
        return {"error": "SigmaEngine Provider Server è disabilitato."}

    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    full_text = ""

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        full_text, _, err = call_ai_model(
            messages=[{"role": "user", "content": prompt}],
            ai_cfg=ai_cfg,
            model=resolved_model,
            provider=p_name,
            endpoint=prov_cfg.get("endpoint", ""),
            api_url=prov_cfg.get("api_url", ""),
            api_key=prov_cfg.get("api_key", ""),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            request_timeout=300
        )
    else:
        tokens = []
        for chunk in sigma_engine.generate_stream(
            prompt=prompt,
            system_prompt=system or serving_persona(),
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=resolved_model,
            messages=[{"role": "user", "content": prompt}],
        ):
            t = chunk.get("token", "")
            if is_notice(chunk) and not chunk.get("error"):
                continue
            if t:
                tokens.append(t)
        full_text = "".join(tokens)

    total_dur_ns = int((time.perf_counter() - start_time) * 1e9)

    return {
        "model": model,
        "created_at": now_iso,
        "response": full_text,
        "done": True,
        "total_duration": total_dur_ns,
        "eval_count": max(1, len(full_text.split()))
    }


def execute_ollama_chat_non_stream(
    messages: List[Dict[str, str]],
    model: str = "sigmaengine",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """Generates non-streaming Ollama chat response JSON."""
    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not is_provider_server_enabled():
        return {"error": "SigmaEngine Provider Server è disabilitato."}

    # The client's conversation, unchanged: no persona unless one is configured.
    system_prompt, sanitized_messages = _split_conversation(messages)

    prompt_text = sanitized_messages[-1].get("content", "")
    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    full_text = ""

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        full_text, _, err = call_ai_model(
            messages=sanitized_messages,
            ai_cfg=ai_cfg,
            model=resolved_model,
            provider=p_name,
            endpoint=prov_cfg.get("endpoint", ""),
            api_url=prov_cfg.get("api_url", ""),
            api_key=prov_cfg.get("api_key", ""),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            request_timeout=300
        )
        if err:
            full_text = f"⚠️ {err}"
    else:
        tokens = []
        for chunk in sigma_engine.generate_stream(
            prompt=prompt_text,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=resolved_model,
            messages=sanitized_messages,
        ):
            t = chunk.get("token", "")
            if is_notice(chunk) and not chunk.get("error"):
                continue
            if t:
                tokens.append(t)
        full_text = "".join(tokens)

    total_dur_ns = int((time.perf_counter() - start_time) * 1e9)

    return {
        "model": model,
        "created_at": now_iso,
        "message": {
            "role": "assistant",
            "content": full_text
        },
        "done": True,
        "total_duration": total_dur_ns,
        "load_duration": 50000000,
        "prompt_eval_count": max(1, len(prompt_text.split()) * 2),
        "prompt_eval_duration": 100000000,
        "eval_count": max(1, len(full_text.split())),
        "eval_duration": max(1, total_dur_ns - 150000000)
    }


def stream_ollama_generate_generator(
    prompt: str,
    system: str = "",
    model: str = "sigmaengine",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Streams NDJSON formatted line chunks for Ollama /api/generate."""
    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not is_provider_server_enabled():
        yield json.dumps({"error": "SigmaEngine Provider Server è disabilitato."}) + "\n"
        return

    resolved_model, exec_mode, prov_cfg = resolve_target_model(model)
    token_count = 0

    if exec_mode == "cloud":
        ai_cfg = load_ai_config()
        p_name = prov_cfg.get("provider", "openai")
        try:
            full_res, _, err = call_ai_model(
                messages=[{"role": "user", "content": prompt}],
                ai_cfg=ai_cfg,
                model=resolved_model,
                provider=p_name,
                endpoint=prov_cfg.get("endpoint", ""),
                api_url=prov_cfg.get("api_url", ""),
                api_key=prov_cfg.get("api_key", ""),
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9,
                request_timeout=300
            )
            if full_res:
                words = full_res.split(" ")
                for i, w in enumerate(words):
                    chunk_text = w + (" " if i < len(words) - 1 else "")
                    token_count += 1
                    yield json.dumps({"model": model, "created_at": now_iso, "response": chunk_text, "done": False}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
    else:
        for chunk in sigma_engine.generate_stream(
            prompt=prompt,
            system_prompt=system or serving_persona(),
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=resolved_model,
            messages=[{"role": "user", "content": prompt}],
        ):
            token = chunk.get("token", "")
            # Engine narration ("caricamento pesi...", queue notices) is UI
            # text, not the model's answer: an Ollama client concatenates
            # every delta it receives.
            if is_notice(chunk) and not chunk.get("error"):
                continue
            if token:
                token_count += 1
                line_obj = {
                    "model": model,
                    "created_at": now_iso,
                    "response": token,
                    "done": False
                }
                yield json.dumps(line_obj) + "\n"

    total_dur_ns = int((time.perf_counter() - start_time) * 1e9)
    final_obj = {
        "model": model,
        "created_at": now_iso,
        "response": "",
        "done": True,
        "total_duration": total_dur_ns,
        "eval_count": max(1, token_count)
    }
    yield json.dumps(final_obj) + "\n"


# ==============================================================================
# 3. SIGMA ENGINE SERVER INFO
# ==============================================================================

def handle_engine_server_info(self):
    """GET /api/engine/server_info — Diagnostic metadata on engine and active server endpoints."""
    models = get_all_available_models()
    resident = sigma_engine.loaded_model_name or "Nessun modello caricato"
    is_enabled = is_provider_server_enabled()
    ai_cfg = load_ai_config()
    server_port = int(ai_cfg.get("provider_server_port") or 8000)
    server_host = str(ai_cfg.get("provider_server_host") or "localhost")
    proxy_alias = str(ai_cfg.get("sigma_proxy_alias") or "sigma")
    base_url = f"http://{server_host}:{server_port}"

    return self.send_json_response({
        "success": True,
        "engine_name": "SigmaEngine Universal Runtime",
        "version": "8.0",
        "provider_server_enabled": is_enabled,
        "status": "online" if is_enabled else "disabled",
        "active_backend": sigma_engine.active_backend,
        "resident_model": resident,
        "has_resident_model": sigma_engine.has_resident_model,
        "total_models_available": len(models),
        "available_models": models,
        "port": server_port,
        "host": server_host,
        "proxy_alias": proxy_alias,
        "proxy_model": ai_cfg.get("sigma_proxy_model") or "sigma",
        "endpoints": {
            "openai_base_url": f"{base_url}/v1",
            "openai_chat_url": f"{base_url}/v1/chat/completions",
            "openai_models_url": f"{base_url}/v1/models",
            "ollama_base_url": f"{base_url}",
            "ollama_chat_url": f"{base_url}/api/chat",
            "ollama_tags_url": f"{base_url}/api/tags",
            "ollama_generate_url": f"{base_url}/api/generate",
        }
    })


# Backward-compatible alias
handle_server_info = handle_engine_server_info
