# ==============================================================================
# core/chat/file_extractor.py — Extraction, Validation & Auto-saving of Files
# Sigma Studio v7 — Modular Chat Sub-package
# ==============================================================================
"""Extracts code blocks, markdown documents, and scripts from LLM responses,
performs AST syntax validation on Python files, creates automatic backups,
computes diffs, and writes to disk inside sandbox boundaries.
"""

import os
import re
import ast
from core.logger import get_logger
from core.data_handler import rebuild_modules_meta
from core.backup_manager import create_backup
from core.task_handler import _compute_diff

log = get_logger(__name__)


def _normalize_data_path(raw_path: str) -> str:
    """Normalize extracted raw path ensuring it starts with data/."""
    clean = raw_path.strip().strip("`'\"").replace("\\", "/")
    clean = re.sub(r"^\.?/+", "", clean)
    clean = re.sub(r"^(?:📄\s*)", "", clean).strip()
    if not clean.startswith("data/"):
        clean = f"data/{clean}"
    return clean


def _ensure_module_subfolders(file_path: str) -> None:
    """Ensure the target directory for file_path exists dynamically."""
    parent_dir = os.path.dirname(os.path.abspath(file_path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def _determine_default_module_path(topic_slug: str, folder: str, fname: str) -> str:
    """Determine clean dynamic path for a topic file."""
    return f"data/{topic_slug}/{fname}"


def is_explicit_file_creation_request(prompt: str) -> bool:
    """Determine if user explicitly requested creating or saving a file on disk."""
    if not prompt or not isinstance(prompt, str):
        return False
    
    text = prompt.strip().lower()
    
    # 1. Informational or conversational queries are NEVER file creation requests
    conversational_patterns = [
        r'^\s*(?:parlami|spiegami|raccontami|dimmi|mostrami|elenca|descrivi|analizza|riassumi|illustrami|introduci)\b',
        r'^\s*(?:chi sei|cosa sei|come ti chiami|cosa puoi fare|cosa sai fare|quali sono|che cosa sono|cosa fa|come funziona)\b',
        r'\b(?:parlami in chat|parlami del|parlami dei|parlami delle|parlami di)\b',
        r'^\s*(?:ciao|buongiorno|buonasera|salve|hey|ehi|help|aiuto)\b',
    ]
    for cp in conversational_patterns:
        if re.search(cp, text, re.IGNORECASE):
            if not re.search(r'\b(?:salva(?:lo|li)?\s+(?:su|in|come)\s+file|crea(?:mi)?\s+(?:un|il|lo|la|i|gli|le)\s+file|scrivi(?:mi)?\s+(?:un|il)\s+file)\b', text, re.IGNORECASE):
                return False

    # 2. Positive explicit file creation triggers:
    positive_patterns = [
        r'\b(?:crea|creami|genera|generami|scrivi|scrivimi|salva|salvalo|salvali|esporta|esportami|sviluppa|sviluppami)\s+(?:un|uno|una|il|lo|la|i|gli|le)?\s*(?:nuovo\s+)?(?:file|documento|script|codice|modulo|progetto|dataset|scheda)\b',
        r'\b(?:salva(?:lo|li)?\s+(?:su|in|come|nel)\s+(?:file|disco|disco fisso|data/|./data/))\b',
        r'\b(?:crea(?:mi)?\s+(?:la\s+cartella|la\s+directory|il\s+file))\b',
        r'\b(?:create_file|write_file|save_to_file)\b',
    ]
    for pp in positive_patterns:
        if re.search(pp, text, re.IGNORECASE):
            return True
            
    return False


def _generate_files_summary(created_paths: list[str], full_response: str) -> str:
    """Generate an elegant markdown summary description of the created files."""
    if not created_paths:
        return ""
    
    summary_parts = []
    intro_match = re.search(r'^(?:#\s+[^\n]+\n+)?([\s\S]{30,300}?)(?=\n##|\n```|\Z)', full_response)
    if intro_match and len(full_response) > 350:
        clean_intro = intro_match.group(1).strip()
        summary_parts.append(f"### 📋 Sintesi dei Contenuti Generati\n{clean_intro}\n")

    summary_parts.append("📁 **File creati e salvati su disco:**")
    
    for path in created_paths:
        file_desc = ""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                h_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
                title = h_match.group(1).strip() if h_match else os.path.basename(path)
                
                para_match = re.search(r'^(?:#+\s+[^\n]+\n+)+([\s\S]{20,120}?)(?=\n#|\Z)', content)
                short_text = para_match.group(1).replace('\n', ' ').strip() if para_match else ""
                if short_text:
                    file_desc = f" — *{short_text[:100]}...*"
                summary_parts.append(f"- **{title}**: `{path}`{file_desc}")
            except Exception:
                summary_parts.append(f"- `{path}`")
        else:
            summary_parts.append(f"- `{path}`")
            
    return "\n\n" + "\n".join(summary_parts)


def _format_file_creation_summary(ai_response, created_paths) -> str:
    """Preserves conversational clean text without injecting duplicate file logs into text.
    The created_files and actions_log metadata are rendered by the dedicated UI component.
    """
    if isinstance(ai_response, list) and isinstance(created_paths, str):
        ai_response, created_paths = created_paths, ai_response
    
    if not isinstance(ai_response, str):
        ai_response = str(ai_response or "")

    return ai_response.strip()


_format_conversational_summary = _format_file_creation_summary


def _strip_reasoning_monologue(text: str) -> str:
    """Strip AI thinking monologues (e.g. 'Here's a thinking process:', '<think>', 'Analyze User Input:')
    so file extraction operates on the final generated response text.
    """
    if not text:
        return ""
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    if re.search(r'^(?:Here\'s\s+a\s+thinking\s+process|Analyze\s+User\s+Input|Identify\s+Key\s+Constraints)', text.strip(), re.IGNORECASE):
        markers = [
            r'Final\s+Output\s+Generation:[^\n]*\n(?:[✅\s]*\n)*Path:\s*',
            r'Final\s+Output\s+Generation:[^\n]*',
            r'Proceeds\.?',
            r'Final\s+Polish:[^\n]*',
            r'✅\s*\n\s*Path:\s*',
            r'Path:\s*`?(?:📄\s*)?(?:data/|\./data/)',
            r'File:\s*`?(?:📄\s*)?(?:data/|\./data/)',
            r'📄\s*data/'
        ]
        for m in markers:
            match = re.search(m, text, re.IGNORECASE)
            if match:
                all_matches = list(re.finditer(m, text, re.IGNORECASE))
                if all_matches:
                    last_match = all_matches[-1]
                    return text[last_match.start():].strip()
    return text.strip()


def _extract_and_create_files_from_text(clean_response: str, prompt_topic: str = "", force_save: bool = False) -> tuple[list[str], list[dict]]:
    """Extract multiple files from markdown text response, save them with backup, AST validation, and diff tracking.
    
    Returns:
        tuple of (created_paths, actions_log) where each action contains backup_id and diff.
    """
    clean_response = _strip_reasoning_monologue(clean_response)
    created_paths = []
    actions_log = []

    def _save_file_with_backup(clean_path: str, file_content: str):
        if not clean_path or not file_content.strip():
            return
        
        clean_path = _normalize_data_path(clean_path)
        filename = os.path.basename(clean_path)
        
        # Strict validation: reject placeholders, dot-only extensions, double slashes
        if (
            '<' in clean_path or '>' in clean_path
            or filename.startswith('.')
            or len(filename.split('.')[0]) < 1
            or clean_path.endswith('/.md')
            or clean_path.endswith('/.py')
            or clean_path.endswith('/.html')
            or '01_...' in clean_path
            or clean_path in created_paths
        ):
            log.warning("Rejected invalid/placeholder file path extraction: %s", clean_path)
            return

        # AST syntax check for Python files to avoid saving corrupt code
        if clean_path.endswith('.py'):
            try:
                ast.parse(file_content.strip(), filename=clean_path)
            except SyntaxError as syn_err:
                log.warning("Rejected Python file with SyntaxError (%s): %s", syn_err, clean_path)
                return

        backup_id = create_backup(clean_path, "chat_save")
        old_content = ""
        if os.path.exists(clean_path):
            try:
                with open(clean_path, "r", encoding="utf-8") as fh:
                    old_content = fh.read()
            except Exception:
                pass
        
        dir_name = os.path.dirname(clean_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        _ensure_module_subfolders(clean_path)
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(file_content.strip())
        
        file_diff = _compute_diff(old_content, file_content.strip(), os.path.basename(clean_path))
        created_paths.append(clean_path)
        actions_log.append({
            "type": "edit_file" if old_content else "create_file",
            "success": True,
            "path": clean_path,
            "message": f"File {'modificato' if old_content else 'creato'}: {clean_path}",
            "backup_id": backup_id,
            "diff": file_diff
        })

        # Developer MCP Verification for Python files
        if clean_path.endswith('.py'):
            try:
                from core.mcp import mcp_hub
                dev_mcp = mcp_hub.get_server("Developer MCP")
                if dev_mcp:
                    test_res = dev_mcp.call_tool("run_pytest", {"test_path": clean_path})
                    actions_log.append({
                        "type": "mcp_tool_call",
                        "server": "Developer MCP",
                        "tool": "run_pytest",
                        "success": test_res.get("isError", False) is False,
                        "message": f"🛠️ Developer MCP Pytest: {clean_path}"
                    })
            except Exception as mcp_err:
                log.debug("Developer MCP validation skipped: %s", mcp_err)

        log.info("Auto-extracted & backed-up file: %s (%d chars)", clean_path, len(file_content))

    _creation_keywords_re = re.compile(r'\b(crea|scrivi|genera|salva|fammi|modifica|aggiorna|sviluppa|aggiungi|create|write|generate|save|file|documento|modulo|teoria|script|codice)\b', re.IGNORECASE)
    user_wants_file_creation = force_save or bool(_creation_keywords_re.search(prompt_topic))

    raw_prompt = prompt_topic.lower() if prompt_topic else ""
    raw_prompt = re.sub(r'^(?:crea(?:mi)?|scrivi(?:mi)?|genera|sviluppa)\s+(?:un|l[\'\"]|il|lo|la|i|gli|le)?\s*(?:argomento|modulo|documento|file|teoria)?\s*(?:su(?:gli)?|di|per)?\s*', '', raw_prompt).strip()
    topic_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_prompt).strip('_') if raw_prompt else ""
    if not topic_slug or len(topic_slug) < 2 or topic_slug in ('ciao', 'ok', 'test', 'analyze_user_input'):
        t_match = re.search(r'^#\s+(.+)', clean_response, re.MULTILINE)
        if t_match:
            topic_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', t_match.group(1).lower()).strip('_')
    if not topic_slug or topic_slug in ('ciao', 'ok', 'test', 'analyze_user_input'):
        topic_slug = "matematica"

    # Pattern 0: Pseudo-code command create_file path="..." content="..."
    pseudo_matches = re.findall(
        r"create_file\s+path=[\"']?(?:📄\s*)?([^\s\"']+)[\"']?\s+content=[\"']([\s\S]*?)(?:[\"']\s*(?:create_file|\Z))",
        clean_response,
        re.IGNORECASE
    )
    if pseudo_matches:
        for path_str, file_content in pseudo_matches:
            clean_path = _normalize_data_path(path_str)
            _save_file_with_backup(clean_path, file_content)

    # Pattern 0.1: Direct explicit file path mention (📁 📄 data/... or Path: data/...) with plain text document
    direct_path_matches = re.findall(
        r"(?:📁|📄|Path|Percorso|File|salvare\s+in|salva\s+in|salvalo\s+in)[:\s]*[`'\"📁📄\s]*((?:data/|\./data/)[^\s`'\":,\)]+\.[a-zA-Z0-9]+)",
        clean_response,
        re.IGNORECASE
    )
    if direct_path_matches:
        for path_str in direct_path_matches:
            clean_path = _normalize_data_path(path_str)
            if clean_path and clean_path not in created_paths:
                lines = clean_response.split("\n")
                raw_lines = []
                found_path = False
                for line in lines:
                    if not found_path:
                        if path_str in line:
                            found_path = True
                            continue
                    else:
                        line_strip = line.strip()
                        if (
                            line_strip.startswith('💡')
                            or line_strip.startswith('**Istruzioni')
                            or line_strip.startswith('Istruzioni:')
                            or 'Copia il contenuto sopra' in line_strip
                            or 'Fammi sapere se' in line_strip
                            or 'Spero che questo' in line_strip
                        ):
                            break
                        raw_lines.append(line)
                
                # Find start of actual document content (skipping intro sentences)
                start_idx = 0
                for idx, line in enumerate(raw_lines):
                    ls = line.strip()
                    if (
                        ls.startswith('# ')
                        or ls.startswith('## ')
                        or ls.startswith('---')
                        or ls.startswith('import ')
                        or ls.startswith('def ')
                        or ls.startswith('class ')
                        or ls.startswith('<html')
                        or ls.startswith('<!DOCTYPE')
                        or ls.startswith('📌')
                        or ls.startswith('1. ')
                    ):
                        start_idx = idx
                        break

                clean_lines = raw_lines[start_idx:] if raw_lines else []
                raw_file_content = "\n".join(clean_lines).strip()
                if raw_file_content:
                    _save_file_with_backup(clean_path, raw_file_content)

    # Pattern 0.3: Path specified inside codeblock header comment (e.g. # File: data/... or # Path: data/...)
    comment_path_matches = re.findall(
        r"```[a-zA-Z0-9]*\n\s*(?:#|//|<!--)\s*(?:File|Path|Percorso)[:\s]+`?((?:data/|\./data/)[^\s`'\n]+\.[a-zA-Z0-9]+)`?[^\n]*\n([\s\S]*?)\n```",
        clean_response,
        re.IGNORECASE
    )
    if comment_path_matches:
        for path_str, file_content in comment_path_matches:
            clean_path = _normalize_data_path(path_str)
            if clean_path and clean_path not in created_paths:
                _save_file_with_backup(clean_path, file_content)

    # Pattern 0.5: math_researcher manifesto format — Path: `data/...` followed by ```markdown block
    backtick_path_matches = re.findall(
        r"(?:Path|Percorso|File)[:\s]+`((?:data/|\./data/)[^`]+\.[a-zA-Z0-9]+)`[^\n]*\n+```[a-zA-Z0-9]*\n([\s\S]*?)\n```",
        clean_response,
        re.IGNORECASE
    )
    if backtick_path_matches:
        for path_str, file_content in backtick_path_matches:
            clean_path = _normalize_data_path(path_str)
            if clean_path and clean_path not in created_paths:
                _save_file_with_backup(clean_path, file_content)

    # Pattern 1: Explicit Path markers + codeblock (supports 📄, ./data/, backticks, quotes)
    file_matches = re.findall(
        r"(?:Path|Percorso|File|Salva\s+in|###|##|\*\*|-|\*|\b)?\s*[`'\"]?(?:📄\s*)?((?:data/|\./data/)[^\s`'\"]+\.[a-zA-Z0-9]+)[`'\"]?[\s\S]*?```[a-zA-Z0-9]*\n([\s\S]*?)\n```",
        clean_response,
        re.IGNORECASE
    )
    if file_matches:
        for path_str, file_content in file_matches:
            clean_path = _normalize_data_path(path_str)
            if clean_path and clean_path not in created_paths:
                _save_file_with_backup(clean_path, file_content)

    # Pattern 2: Standalone Codeblocks paired with preceding filenames (requires explicit file creation intent)
    if not created_paths and user_wants_file_creation:
        codeblocks = re.findall(r"(?:###|##|\*\*|[a-zA-Z0-9_\-\./]+)?\s*([a-zA-Z0-9_\-\./]+\.(?:md|py|html|js|css|json))?[^\n]*\n```([a-zA-Z0-9]*)\n([\s\S]*?)\n```", clean_response, re.IGNORECASE)
        if codeblocks:
            for idx, (filename_hint, lang, file_content) in enumerate(codeblocks, start=1):
                if file_content.strip():
                    if filename_hint and (filename_hint.endswith('.md') or filename_hint.endswith('.py') or filename_hint.endswith('.html')):
                        fname = os.path.basename(filename_hint)
                    else:
                        fname = f"modulo_{idx}.{'py' if lang == 'python' else ('html' if lang == 'html' else 'md')}"
                    
                    folder = "scripts" if lang == "python" else ("viz" if lang == "html" else "teoria")
                    clean_path = _determine_default_module_path(topic_slug, folder, fname)
                    _save_file_with_backup(clean_path, file_content)

    # Pattern 4: Fallback — save entire response as a structured topic file (requires explicit creation intent)
    is_reasoning_only = clean_response.strip().startswith("Analyze User Input:") or clean_response.strip().startswith("Identify Constraints")
    is_admin_action = any(w in prompt_topic.lower() for w in ('rinomina', 'elimina', 'cancella', 'rimuovi', 'cambia nome'))
    should_fallback = not is_reasoning_only and not is_admin_action and (
        force_save or (len(clean_response) > 50 and user_wants_file_creation)
    )
    if not created_paths and should_fallback:
        title_match = re.search(r'^#\s+(.+)', clean_response, re.MULTILINE)
        raw_title = title_match.group(1).strip() if title_match else raw_prompt or topic_slug
        file_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_title.lower()).strip('_')[:40] or topic_slug
        if file_slug in ('analyze_user_input', 'identify_constraints', 'documento'):
            file_slug = topic_slug
        
        clean_path = _determine_default_module_path(topic_slug, "teoria", f"{file_slug}.md")
        _save_file_with_backup(clean_path, clean_response)

    if created_paths:
        try:
            rebuild_modules_meta()
        except Exception as exc:
            log.warning("Non-fatal: rebuild_modules_meta failed after file extraction: %s", exc)

    return created_paths, actions_log
