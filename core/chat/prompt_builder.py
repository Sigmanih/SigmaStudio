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
    """Read and concatenate the content of up to 5 open context files.

    Args:
        handler:    The HTTP handler instance (provides ``_is_path_allowed``).
        open_files: List of file paths sent by the frontend.

    Returns:
        Concatenated file contents as a string (max 5 000 chars per file).
    """
    context_str = ""
    if not open_files:
        return context_str

    for file_path in open_files[:5]:
        if handler._is_path_allowed(file_path) and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                context_str += f"\n--- FILE: {file_path} ---\n{content[:5000]}\n"
            except OSError as exc:
                log.warning("Cannot read context file %s: %s", file_path, exc)
    return context_str
