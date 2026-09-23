# ==============================================================================
# core/harness/symbol_index.py — Workspace AST & Symbol Indexer
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Indexes functions, classes, and exported components across Python, JavaScript,
and TypeScript files in the workspace for instantaneous symbol resolution.
"""

import ast
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from core.harness.fs_manager import (
    SEARCH_IGNORE_DIRS,
    SEARCH_IGNORE_EXTENSIONS,
    get_default_workspace_root,
)

log = get_logger("developer_symbol_index")

_INDEX_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def _extract_py_symbols(code: str, rel_path: str) -> List[Dict[str, Any]]:
    """Extracts classes, functions, and async functions from Python code via AST."""
    symbols = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return symbols

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append({
                "name": node.name,
                "kind": "class",
                "path": rel_path,
                "line": node.lineno,
                "signature": f"class {node.name}",
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            symbols.append({
                "name": node.name,
                "kind": "function",
                "path": rel_path,
                "line": node.lineno,
                "signature": f"{prefix}{node.name}(...)",
            })
    return symbols


_JS_SYMBOL_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\("
    r"|^(?:export\s+)?class\s+([A-Za-z0-9_$]+)"
    r"|^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:(?:\([^\)]*\)|[A-Za-z0-9_$]+)\s*=>|function)",
    re.MULTILINE
)


def _extract_js_symbols(code: str, rel_path: str) -> List[Dict[str, Any]]:
    """Extracts exported functions, components, and classes from JS/TS/JSX."""
    symbols = []
    lines = code.splitlines()
    for line_idx, line in enumerate(lines, 1):
        s_line = line.strip()
        m = _JS_SYMBOL_RE.search(s_line)
        if m:
            name = m.group(1) or m.group(2) or m.group(3)
            if name:
                kind = "class" if "class " in s_line else ("component" if name[0].isupper() else "function")
                symbols.append({
                    "name": name,
                    "kind": kind,
                    "path": rel_path,
                    "line": line_idx,
                    "signature": s_line[:80],
                })
    return symbols


def find_symbol_definitions(
    query: str,
    root_path: Optional[str] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    """Finds definitions of classes, functions, and components across the workspace."""
    root = Path(root_path or get_default_workspace_root()).resolve()
    if not root.exists() or not query.strip():
        return {"success": True, "query": query, "symbols": [], "count": 0}

    query_clean = query.strip().lower()
    symbols: List[Dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            d for d in dirnames
            if d not in SEARCH_IGNORE_DIRS and not d.startswith(".")
        ]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".py", ".js", ".jsx", ".ts", ".tsx"):
                continue

            full_path = Path(dirpath) / fname
            try:
                rel_path = str(full_path.relative_to(root)).replace("\\", "/")
                code = full_path.read_text(encoding="utf-8", errors="replace")
                
                if ext == ".py":
                    file_syms = _extract_py_symbols(code, rel_path)
                else:
                    file_syms = _extract_js_symbols(code, rel_path)

                for sym in file_syms:
                    if query_clean in sym["name"].lower():
                        symbols.append(sym)
                        if len(symbols) >= limit:
                            break
            except Exception:
                continue

        if len(symbols) >= limit:
            break

    # Exact matches first
    symbols.sort(key=lambda s: (0 if s["name"].lower() == query_clean else 1, s["name"]))
    return {
        "success": True,
        "query": query,
        "count": len(symbols),
        "symbols": symbols[:limit],
        "message": f"Trovate {len(symbols)} definizioni per '{query}'."
    }


def outline_of_file(file_path: str, limit: int = 40) -> Dict[str, Any]:
    """La mappa di un file: cosa definisce, e a che riga.

    Leggere un file di quattromila righe a finestre e un modo per non trovarlo:
    il 23 settembre 2026 un agente ha letto `core/harness/loop.py` (4212 righe)
    nelle finestre 1-1200 e 2400-2899, e ha cercato per dieci turni una funzione
    che stava alla riga 2132. Una mappa di quaranta righe, con i nomi e i numeri
    di riga, dice dove guardare prima di chiedere una finestra.
    """
    p = Path(file_path)
    esito: Dict[str, Any] = {
        "success": False, "path": str(p).replace("\\", "/"),
        "symbols": [], "count": 0, "total_lines": 0,
    }
    if not p.is_file():
        esito["error"] = f"File non trovato: {file_path}"
        return esito
    estensione = p.suffix.lower()
    if estensione not in (".py", ".js", ".jsx", ".ts", ".tsx"):
        esito["error"] = f"Mappa non disponibile per i file con estensione {estensione}."
        return esito
    try:
        codice = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        esito["error"] = f"File non leggibile: {exc}"
        return esito

    if estensione == ".py":
        simboli = _extract_py_symbols(codice, p.name)
    else:
        simboli = _extract_js_symbols(codice, p.name)
    simboli.sort(key=lambda voce: int(voce.get("line") or 0))
    esito.update({
        "success": True,
        "symbols": simboli[: max(1, int(limit))],
        "count": len(simboli),
        "total_lines": len(codice.splitlines()),
    })
    return esito
