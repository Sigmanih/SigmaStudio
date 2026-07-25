# ==============================================================================
# core/loop/verification.py — Autonomous Loop Context & Output Verification
# Sigma Studio v7 — Modular Loop Sub-package
# ==============================================================================
"""Context builder, filesystem status inspector, tasks state provider, and robust JSON
extractor for autonomous task-driven loops.
"""

import os
import json
import re
from core.logger import get_logger

log = get_logger(__name__)


def _build_loop_filesystem_context() -> str:
    """Build concise filesystem context for the loop."""
    lines = []
    data_dir = 'data'
    if not os.path.isdir(data_dir):
        return ""
    for topic in sorted(os.listdir(data_dir)):
        topic_path = os.path.join(data_dir, topic)
        if not os.path.isdir(topic_path):
            continue
        lines.append(f"\n📂 {topic}/")
        for mod in sorted(os.listdir(topic_path)):
            mod_path = os.path.join(topic_path, mod)
            if not os.path.isdir(mod_path) or not (mod[:2].isdigit()):
                continue
            mod_label = mod[3:] if len(mod) > 3 else mod
            lines.append(f"  📁 {mod} ({mod_label})")
            for section in ['teoria', 'scripts', 'viz', 'docs']:
                sec_path = os.path.join(mod_path, section)
                if os.path.isdir(sec_path):
                    files = sorted(os.listdir(sec_path))
                    if files:
                        lines.append(f"    {section}/")
                        for f_name in files:
                            f_path = os.path.join(sec_path, f_name).replace('\\', '/')
                            f_size = os.path.getsize(f_path) if os.path.isfile(f_path) else 0
                            lines.append(f"      {f_name} ({f_size}B)")
    return '\n'.join(lines)


def _get_tasks_context() -> str:
    """Get tasks.json as formatted string for context."""
    try:
        if os.path.exists('tasks.json'):
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            return json.dumps(tasks, indent=2)
    except Exception:
        pass
    return "[]"


def _extract_json_from_response(content: str):
    """Robust JSON extractor with balanced brace matcher."""
    if not content or not isinstance(content, str):
        return None
    idx = content.find('{')
    while idx >= 0:
        depth = 0
        start = idx
        for i in range(idx, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = content[start:i+1]
                    if '"response"' in candidate:
                        try:
                            json.loads(candidate)
                            class FakeMatch:
                                def group(self, n=0):
                                    return candidate
                            return FakeMatch()
                        except json.JSONDecodeError:
                            pass
                    break
            elif content[i] in ('"', "'"):
                quote = content[i]
                j = i + 1
                while j < len(content) and content[j] != quote:
                    if content[j] == '\\':
                        j += 1
                    j += 1
                i = j
        idx = content.find('{', idx + 1)
    return re.search(r'\{[\s\S]*"response"[\s\S]*("actions"|"tasks"|"self_reflection")[\s\S]*\}', content)
