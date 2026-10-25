# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/screenshot_server.py — Screenshot MCP
# Sigma Studio v8 — Developer Studio AI-Native IDE
# =============================================================================
"""MCP server per la verifica visiva tramite screenshot.

Il tool `screenshot_page` cattura uno screenshot di una pagina web locale o
remota e lo salva in un file PNG. Non modifica nulla: solo legge e riporta.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE
from core.harness.fs_manager import get_default_workspace_root

log = get_logger(__name__)


def _capture_screenshot(url: str, output_path: Path, width: int = 1280, height: int = 720) -> Dict[str, Any]:
    """Cattura uno screenshot di una pagina web usando Playwright o fallback."""
    
    # Verifica che il percorso di output sia valido
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Prova con Playwright se disponibile
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()
        
        return {
            "success": True,
            "method": "playwright",
            "url": url,
            "output_path": str(output_path),
            "width": width,
            "height": height,
            "size_bytes": output_path.stat().st_size if output_path.exists() else 0,
        }
    except ImportError:
        log.info("Playwright non disponibile, provo con fallback")
    except Exception as exc:
        log.warning("Errore con Playwright: %s", exc)
    
    # Fallback: usa wkhtmltoimage se disponibile
    try:
        result = subprocess.run(
            ["wkhtmltoimage", "--width", str(width), "--height", str(height), url, str(output_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and output_path.exists():
            return {
                "success": True,
                "method": "wkhtmltoimage",
                "url": url,
                "output_path": str(output_path),
                "width": width,
                "height": height,
                "size_bytes": output_path.stat().st_size,
            }
        else:
            return {
                "success": False,
                "method": "wkhtmltoimage",
                "error": result.stderr or "Screenshot fallito",
            }
    except FileNotFoundError:
        log.info("wkhtmltoimage non disponibile")
    except Exception as exc:
        return {
            "success": False,
            "method": "fallback",
            "error": f"Errore durante la cattura screenshot: {exc}",
        }
    
    # Nessun metodo disponibile
    return {
        "success": False,
        "error": "Nessun tool per screenshot disponibile. Installa Playwright (pip install playwright) o wkhtmltoimage.",
    }


class ScreenshotMCPServer(BaseMCPServer):
    """MCP server per la verifica visiva tramite screenshot."""
    
    def __init__(self):
        super().__init__(
            name="screenshot",
            version="1.0.0",
            description="Cattura screenshot di pagine web per verifica visiva",
        )
        self.register_tool(
            name="screenshot_page",
            description="Cattura uno screenshot di una pagina web e lo salva in un file PNG",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL della pagina da catturare (es. http://localhost:8000)"},
                    "output_path": {"type": "string", "description": "Percorso del file PNG di output (opzionale, default: var/screenshots/screenshot_<timestamp>.png)"},
                    "width": {"type": "integer", "description": "Larghezza viewport in pixel (default: 1280)"},
                    "height": {"type": "integer", "description": "Altezza viewport in pixel (default: 720)"},
                },
                "required": ["url"],
            },
            handler=self._handle_screenshot_page,
            safety=SAFE,
        )

    def missing_dependency(self) -> Optional[str]:
        try:
            import playwright  # noqa: F401
            return None
        except ImportError:
            return "pip install playwright && python -m playwright install chromium"

    def _handle_screenshot_page(self, **kwargs) -> Dict[str, Any]:
        url = kwargs.get("url")
        if not url:
            return {"success": False, "error": "Parametro 'url' mancante"}

        output_path_str = kwargs.get("output_path")
        if output_path_str:
            output_path = Path(output_path_str)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(get_default_workspace_root()) / "var" / "screenshots" / f"screenshot_{timestamp}.png"
        
        width = kwargs.get("width", 1280)
        height = kwargs.get("height", 720)
        
        return _capture_screenshot(url, output_path, width, height)
