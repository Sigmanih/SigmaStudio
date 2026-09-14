# ==============================================================================
# core/harness/diagnostics.py — Fast Multi-Language Syntax Validator
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Provides fast, zero-external-dependency syntax validation for Python, JSON,
JavaScript, JSX, TypeScript, TSX, and CSS before and after edits.
"""

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger

log = get_logger("developer_diagnostics")


def _validate_brackets_and_quotes(code: str, language: str) -> Optional[str]:
    """Fast bracket & quotes balancer for JS, JSX, TS, TSX, CSS."""
    stack = []
    lines = code.splitlines()
    in_single_comment = False
    in_multi_comment = False
    in_string = None
    escape = False

    matching = {')': '(', '}': '{', ']': '['}

    for line_idx, line in enumerate(lines, 1):
        i = 0
        in_single_comment = False
        while i < len(line):
            c = line[i]
            nxt = line[i + 1] if i + 1 < len(line) else ""

            if escape:
                escape = False
                i += 1
                continue

            if in_string:
                if c == '\\':
                    escape = True
                elif c == in_string:
                    in_string = None
                i += 1
                continue

            if in_multi_comment:
                if c == '*' and nxt == '/':
                    in_multi_comment = False
                    i += 2
                    continue
                i += 1
                continue

            # Check comments
            if c == '/' and nxt == '/':
                in_single_comment = True
                break
            if c == '/' and nxt == '*':
                in_multi_comment = True
                i += 2
                continue

            # Strings
            if c in ("'", '"', '`'):
                in_string = c
                i += 1
                continue

            # Brackets
            if c in ('(', '{', '['):
                stack.append((c, line_idx, i + 1))
            elif c in (')', '}', ']'):
                if not stack:
                    return f"Parentesi chiusa non corrispondente '{c}' alla riga {line_idx}, colonna {i + 1}"
                top_char, top_line, top_col = stack.pop()
                expected = matching[c]
                if top_char != expected:
                    return (
                        f"Parentesi non corrispondente: aperta '{top_char}' alla riga {top_line} "
                        f"ma chiusa '{c}' alla riga {line_idx}"
                    )
            i += 1

    if in_string:
        return f"Stringa letterale con delimitatore {in_string} non chiusa."
    if in_multi_comment:
        return "Commento a blocchi /* ... */ non chiuso."
    if stack:
        top_char, top_line, top_col = stack[-1]
        return f"Parentesi aperta '{top_char}' alla riga {top_line}, colonna {top_col} non chiusa."

    return None


def _check_jsx_component_imports(content: str) -> Optional[str]:
    """Detects capitalized JSX components (<Component ...>) used without import or definition."""
    raw_tags = re.findall(r"<([A-Z][a-zA-Z0-9_]*)", content)
    if not raw_tags:
        return None

    unique_tags = set(raw_tags)
    builtins = {"Fragment", "React"}

    # Trova identificatori importati: import Foo from ... oppure import { Bar, Baz as B } from ...
    imported = set()
    for m in re.finditer(r"import\s+(?:(?:\*\s+as\s+([A-Za-z0-9_]+))|([A-Za-z0-9_]+)|(?:\{([^}]+)\}))", content):
        if m.group(1):
            imported.add(m.group(1).strip())
        if m.group(2):
            imported.add(m.group(2).strip())
        if m.group(3):
            for part in m.group(3).split(","):
                cleaned = part.strip().split(" as ")[-1].strip()
                if cleaned:
                    imported.add(cleaned)

    # Trova definizioni locali: function Foo, class Foo, const Foo = ...
    defined = set()
    for m in re.finditer(r"(?:function|class|const|let|var)\s+([A-Z][a-zA-Z0-9_]*)", content):
        defined.add(m.group(1).strip())

    missing = unique_tags - imported - defined - builtins
    if missing:
        missing_list = ", ".join(f"<{t}>" for t in sorted(missing))
        return (
            f"Componenti JSX utilizzati ma non importati né definiti: {missing_list}. "
            "Aggiungi l'import in testa al file o definisci il componente."
        )
    return None


def validate_code_syntax(file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """Validates syntax for Python, JSON, JavaScript/JSX/TypeScript, and CSS."""
    p = Path(file_path)
    ext = p.suffix.lower()

    if content is None:
        if not p.is_file():
            return {"valid": True, "language": "unknown", "error": None}
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as ex:
            return {"valid": False, "language": "unknown", "error": f"Impossibile leggere file: {ex}"}

    # 1. Python (.py)
    if ext == ".py":
        try:
            ast.parse(content, filename=str(p))
            return {"valid": True, "language": "python", "error": None}
        except SyntaxError as syn:
            return {
                "valid": False,
                "language": "python",
                "error": f"Errore di sintassi Python (riga {syn.lineno}): {syn.msg}",
                "line": syn.lineno,
            }

    # 2. JSON (.json)
    if ext in (".json", ".jsonc") and not ext == ".jsonc":
        try:
            json.loads(content)
            return {"valid": True, "language": "json", "error": None}
        except json.JSONDecodeError as jde:
            return {
                "valid": False,
                "language": "json",
                "error": f"Errore di formattazione JSON (riga {jde.lineno}): {jde.msg}",
                "line": jde.lineno,
            }

    # 3. JavaScript, JSX, TypeScript, TSX, CSS (.js, .jsx, .ts, .tsx, .css, .scss)
    if ext in (".js", ".jsx", ".ts", ".tsx", ".css", ".scss"):
        lang = "javascript" if ext in (".js", ".jsx") else ("typescript" if ext in (".ts", ".tsx") else "css")
        err = _validate_brackets_and_quotes(content, lang)
        if err:
            return {"valid": False, "language": lang, "error": err}
        
        # In JSX e TSX verifica componenti usati senza import
        if ext in (".jsx", ".tsx"):
            jsx_err = _check_jsx_component_imports(content)
            if jsx_err:
                return {"valid": False, "language": lang, "error": jsx_err}

        return {"valid": True, "language": lang, "error": None}

    return {"valid": True, "language": ext.lstrip("."), "error": None}
