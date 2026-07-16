# ==============================================================================
# core/chat/prompt_builder.py — System Prompt & Context Builder
# Extracted from core/chat_handler.py for Single Responsibility
# ==============================================================================
"""Build system prompts, collect context files, and resolve manifesti.

Responsibilities:
    - Load manifesto (Modelfile) content for an agent.
    - Resolve which manifesto matches the active model.
    - Build the filesystem structure context string.
    - Collect open-file contents for AI context.
    - Provide current date/time context string.
"""

import os
from core.logger import get_logger

log = get_logger(__name__)


def _get_time_context() -> str:
    """Return a short Italian date/time string for injection into prompts."""
    from datetime import datetime
    now = datetime.now()
    giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    mesi = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ]
    return (
        f"## 📅 Oggi è {giorni[now.weekday()]} {now.day} {mesi[now.month - 1]} "
        f"{now.year}, ore {now.strftime('%H:%M')}.\n"
    )


def _get_manifesto_content(manifesto_path: str) -> str:
    """Read and return the content of a manifesto Modelfile.

    Args:
        manifesto_path: Relative or absolute path to the ``.md`` manifesto.

    Returns:
        File content string, or empty string if the file cannot be read.
    """
    if not manifesto_path:
        return ""
    try:
        if os.path.exists(manifesto_path):
            with open(manifesto_path, "r", encoding="utf-8") as fh:
                return fh.read()
    except OSError as exc:
        log.warning("Cannot read manifesto %s: %s", manifesto_path, exc)
    return ""


def _resolve_manifesto_for_model(model_name: str) -> str:
    """Find the best matching manifesto for *model_name*.

    Search order:
    1. Exact filename matches in ``manifesti/``.
    2. Prefix match (model name starts with manifesto name).

    Returns:
        Path to the matching manifesto, or empty string if none found.
    """
    if not model_name:
        return ""

    base_name = model_name.replace(":latest", "").replace(":", "_")
    candidates = [
        f"manifesti/{model_name}.md",
        f"manifesti/{base_name}.md",
        f"manifesti/{model_name.split(':')[0]}.md",
    ]
    for candidate in candidates:
        candidate = candidate.replace(":", "_")
        if os.path.exists(candidate):
            return candidate

    manifesti_dir = "manifesti"
    if os.path.isdir(manifesti_dir):
        for fname in sorted(os.listdir(manifesti_dir)):
            if fname.endswith(".md"):
                fname_stem = fname[:-3].lower()
                mname = model_name.lower()
                if fname_stem in mname or mname.startswith(fname_stem):
                    return os.path.join(manifesti_dir, fname)
    return ""


def _build_filesystem_context() -> str:
    """Build a text representation of the ``data/`` knowledge-base structure.

    Returns:
        Multi-line string listing topics → modules → sections → files,
        or empty string if ``data/`` does not exist.
    """
    lines: list[str] = []
    data_dir = "data"
    if not os.path.isdir(data_dir):
        return ""

    for topic in sorted(os.listdir(data_dir)):
        topic_path = os.path.join(data_dir, topic)
        if not os.path.isdir(topic_path):
            continue
        lines.append(f"\n📂 {topic}/")
        for mod in sorted(os.listdir(topic_path)):
            mod_path = os.path.join(topic_path, mod)
            if not os.path.isdir(mod_path):
                continue
            mod_label = mod[3:] if mod[:2].isdigit() and len(mod) > 3 else mod
            lines.append(f"  📁 {mod} ({mod_label})")
            for section in ("teoria", "test", "viz", "docs"):
                sec_path = os.path.join(mod_path, section)
                if os.path.isdir(sec_path):
                    files = sorted(os.listdir(sec_path))
                    if files:
                        lines.append(f"    {section}/")
                        for fname in files:
                            fpath = os.path.join(sec_path, fname).replace("\\", "/")
                            lines.append(f"      {fname}  → {fpath}")

    return "\n".join(lines) if lines else ""


def _collect_context_files(handler, open_files: list[str]) -> str:
    """Read and concatenate the content of open context files with enhanced limits and style context.

    Args:
        handler:    The HTTP handler instance (provides ``_is_path_allowed``).
        open_files: List of file paths sent by the frontend.

    Returns:
        Concatenated file contents as a string (max 25,000 chars per file + related styles/scripts).
    """
    context_str = ""
    if not open_files:
        return context_str

    loaded_paths = set()

    for file_path in open_files[:6]:
        if not file_path or not isinstance(file_path, str):
            continue
        file_path = file_path.replace("\\", "/")
        if file_path in loaded_paths:
            continue
        if handler._is_path_allowed(file_path) and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                context_str += f"\n--- FILE CONTESTO APERTO: {file_path} ---\n{content[:25000]}\n"
                loaded_paths.add(file_path)

                # Automatic related files injection for visualizers, styling or scripts
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ('.html', '.js', '.css'):
                    dir_name = os.path.dirname(file_path)
                    if os.path.isdir(dir_name):
                        for sibling in os.listdir(dir_name):
                            sibling_ext = os.path.splitext(sibling)[1].lower()
                            if sibling_ext in ('.css', '.js', '.html') and sibling_ext != ext:
                                sib_path = os.path.join(dir_name, sibling).replace("\\", "/")
                                if sib_path not in loaded_paths and handler._is_path_allowed(sib_path):
                                    try:
                                        with open(sib_path, "r", encoding="utf-8", errors="replace") as sfh:
                                            s_content = sfh.read()
                                        context_str += f"\n--- FILE CORRELATO NELLA STESSA DIRECTORY: {sib_path} ---\n{s_content[:15000]}\n"
                                        loaded_paths.add(sib_path)
                                    except Exception:
                                        pass
            except OSError as exc:
                log.warning("Cannot read context file %s: %s", file_path, exc)
    return context_str


def _determine_agent_by_request(message: str, ai_cfg: dict, model_override: str) -> str:
    """Query the AI coordinator to decide which manifesto/role is best suited for the user prompt."""
    import re
    import json
    from core.orchestration.agent_config import load_agent_config
    from core.agent_registry import SIGMA_ARCHITECT_ID, get_all_agents
    from core.ai_providers import call_ai_model

    # Use default coordinator credentials
    main_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)
        
    agents = get_all_agents()
    active_agents = [a for a in agents if a.get("status") == "active"]
    
    agents_info = "\n".join([f"- {a['id']}: {a['name']} (Specializzazione: {a.get('specialization', a.get('role', ''))})" for a in active_agents])
    
    system_prompt = f"""Sei Sigma AI Architect. Il tuo unico scopo è instradare la richiesta dell'utente all'agente specializzato più efficiente.
    
### AGENTI DISPONIBILI:
{agents_info}

### REGOLA FONDAMENTALE:
Rispondi SOLO ed ESCLUSIVAMENTE con l'id esatto dell'agente prescelto.
Non aggiungere introduzioni, non spiegare il motivo, non scrivere nient'altro. Solo l'id dell'agente prescelto (es: math1 o code_architect).
Se non sei sicuro o se la richiesta riguarda la pianificazione generale del progetto o la gestione della roadmap, rispondi: sigma_architect
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Richiesta utente: {message}"}
    ]
    
    try:
        response, _, error = call_ai_model(
            messages, ai_cfg, main_model, provider, endpoint, api_url, api_key,
            0.1, 1000, top_p, timeout
        )
        if not error and response:
            chosen = response.strip().lower()
            # Clean eventual quotes or formatting
            chosen = re.sub(r'[^a-z0-9_-]', '', chosen)
            for a in active_agents:
                if a['id'].lower() == chosen:
                    path = f"manifesti/{a['id']}.md"
                    log.info("Auto-routing to agent: %s (%s)", a['id'], path)
                    return path
    except Exception as e:
        log.error("Error in automatic agent routing: %s", e)
        
    return "manifesti/sigma_architect.md"

