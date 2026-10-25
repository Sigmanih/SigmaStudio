# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/web_server.py — Web Research MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP Server per la ricerca web, consultazione documentazione tecnica e docs.rs.

Consente agli agenti di sviluppo di effettuare ricerche online, consultare pagine
web esterne, scaricare documentazione e ispezionare librerie dell'ecosistema Rust
(crates.io, docs.rs) e GitHub per non bloccarsi su librerie o errori non noti.
Tutti gli strumenti sono di sola lettura (SAFE).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE

log = get_logger(__name__)


def _clean_html_text(html: str) -> str:
    """Estrae testo leggibile da HTML rimuovendo script, style e tag superflui."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return "\n".join(chunk for chunk in chunks if chunk)
    except Exception:
        # Fallback regex se BeautifulSoup fallisce
        clean = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean


def _scrape_page(url: str, max_chars: int = 5000, timeout: int = 12) -> Dict[str, Any]:
    """Scarica ed estrae il contenuto testuale di una pagina web."""
    try:
        import urllib.request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it,en-US;q=0.7,en;q=0.3",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            encoding = response.headers.get_content_charset() or "utf-8"
            raw_html = response.read().decode(encoding, errors="replace")
            cleaned_text = _clean_html_text(raw_html)

            # Estrazione del titolo
            title_match = re.search(r"<title>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else url

            return {
                "success": True,
                "url": url,
                "title": title,
                "content": cleaned_text[:max_chars],
                "total_chars": len(cleaned_text),
                "truncated": len(cleaned_text) > max_chars,
            }
    except Exception as exc:
        log.debug("[WebMCPServer] Errore scraping %s: %s", url, exc)
        return {
            "success": False,
            "url": url,
            "error": f"Impossibile scaricare la pagina: {exc}",
        }


def _ddg_search(query: str, max_results: int = 5, timeout: int = 10) -> List[Dict[str, str]]:
    """Esegue una ricerca web tramite DuckDuckGo HTML scraper."""
    results: List[Dict[str, str]] = []
    try:
        from core.chat.web_search import _perform_web_search
        raw_items = _perform_web_search(query, max_results=max_results)
        for item in raw_items:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("body", ""),
                "url": item.get("href", ""),
            })
        if results:
            return results
    except Exception as exc:
        log.debug("[WebMCPServer] Fallback su chat web search: %s", exc)

    # Fallback diretto via DuckDuckGo lite
    try:
        import urllib.request
        clean_q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={clean_q}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
            links = re.findall(r'<a[^>]+class="result__snippet"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            for href, text in links[:max_results]:
                clean_text = re.sub(r"<[^>]+>", "", text).strip()
                results.append({
                    "title": query,
                    "snippet": clean_text,
                    "url": href,
                })
    except Exception as exc:
        log.warning("[WebMCPServer] Errore ricerca DDG: %s", exc)

    return results


class WebSearchMCPServer(BaseMCPServer):
    """Server MCP per la ricerca web e consultazione documentazione online."""

    def __init__(self):
        super().__init__(
            name="web_search_server",
            version="1.0.0",
            description="Ricerca web, scraping documentazione online e lookup librerie Rust/crates.io.",
        )

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "web_search",
                "description": "Cerca informazioni sul web (DuckDuckGo), documentazione tecnica, librerie e soluzioni di codice.",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query di ricerca."},
                        "num_results": {"type": "integer", "description": "Numero di risultati desiderati (default: 5).", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "fetch_web_page",
                "description": "Scarica e analizza il contenuto testuale di un URL (es. docs.rs, GitHub, documentazione di librerie).",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL completo da scaricare (es. https://docs.rs/tokio/latest/tokio/)."},
                        "max_chars": {"type": "integer", "description": "Numero massimo di caratteri da restituire (default: 4000).", "default": 4000},
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "docs_rust_search",
                "description": "Cerca informazioni e metadati su un crate Rust da crates.io (descrizione, versioni, dipendenze).",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "crate_name": {"type": "string", "description": "Nome del crate Rust (es. tokio, axum, memmap2, candle-core)."},
                    },
                    "required": ["crate_name"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "web_search":
            return self._tool_web_search(arguments)
        elif name == "fetch_web_page":
            return self._tool_fetch_web_page(arguments)
        elif name == "docs_rust_search":
            return self._tool_docs_rust_search(arguments)
        return {"success": False, "error": f"Tool sconosciuto: {name}"}

    def _tool_web_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"success": False, "error": "Parametro 'query' obbligatorio."}
        num = int(args.get("num_results", 5))
        results = _ddg_search(query, max_results=num)
        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results,
            "message": f"Trovati {len(results)} risultati per '{query}'.",
        }

    def _tool_fetch_web_page(self, args: Dict[str, Any]) -> Dict[str, Any]:
        url = str(args.get("url", "")).strip()
        if not url:
            return {"success": False, "error": "Parametro 'url' obbligatorio."}
        max_chars = int(args.get("max_chars", 4000))
        res = _scrape_page(url, max_chars=max_chars)
        return res

    def _tool_docs_rust_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        crate_name = str(args.get("crate_name", "")).strip().lower()
        if not crate_name:
            return {"success": False, "error": "Parametro 'crate_name' obbligatorio."}

        # Query all'API pubblica di crates.io
        try:
            import urllib.request
            api_url = f"https://crates.io/api/v1/crates/{urllib.parse.quote(crate_name)}"
            headers = {"User-Agent": "SigmaStudioAgent/8.0 (sigma-studio@local)"}
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                crate_info = data.get("crate", {})
                return {
                    "success": True,
                    "crate": crate_name,
                    "description": crate_info.get("description", ""),
                    "max_version": crate_info.get("max_version", ""),
                    "downloads": crate_info.get("downloads", 0),
                    "documentation": crate_info.get("documentation") or f"https://docs.rs/{crate_name}",
                    "repository": crate_info.get("repository", ""),
                    "message": f"Crate '{crate_name}' trovato: v{crate_info.get('max_version', '')}",
                }
        except Exception as exc:
            # Fallback a documentazione stimata docs.rs
            return {
                "success": True,
                "crate": crate_name,
                "documentation": f"https://docs.rs/{crate_name}",
                "repository": f"https://github.com/{crate_name}",
                "note": f"Lookup API crates.io non disponibile ({exc}), usa https://docs.rs/{crate_name}",
            }
