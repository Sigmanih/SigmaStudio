# ==============================================================================
# Utilità di rete: una CA non valida deve produrre un errore verificabile,
# senza disabilitare implicitamente la verifica TLS dell'intero processo.
# ==============================================================================
from __future__ import annotations

import json
import os
import shutil
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
from core.logger import get_logger

log = get_logger(__name__)


def setup_resilient_ssl() -> None:
    """Usa le CA disponibili senza indebolire la verifica TLS del processo."""
    try:
        import certifi
        ca = certifi.where()
        if ca and os.path.exists(ca):
            os.environ.setdefault("SSL_CERT_FILE", ca)
            os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
    except Exception:
        pass


# Auto-configure resilient SSL immediately on import
setup_resilient_ssl()


def get_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Verifica TLS attiva, salvo richiesta esplicita del chiamante."""
    if not verify:
        try:
            return ssl._create_unverified_context()
        except Exception:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

    # 1. Try certifi bundle
    try:
        import certifi
        cafile = certifi.where()
        if cafile and os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    except Exception:
        pass

    # Una CA mancante deve emergere: ripiegare su CERT_NONE nasconde un attacco.
    return ssl.create_default_context()


def safe_urlopen(
    url_or_req: Union[str, urllib.request.Request],
    timeout: int = 30,
    verify: bool = True,
    **kwargs
) -> Any:
    """Propaga gli errori TLS al chiamante senza tentativi non verificati."""
    ctx = get_ssl_context(verify=verify)
    return urllib.request.urlopen(url_or_req, timeout=timeout, context=ctx, **kwargs)


def fetch_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15
) -> Optional[Any]:
    """Fetches and parses a JSON endpoint safely."""
    req_headers = {"User-Agent": "SigmaStudio", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with safe_urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content)
    except Exception as exc:
        log.warning("[NetUtils] Failed to fetch JSON from %s: %s", url, exc)
        return None


def download_file(
    url: str,
    destination: Union[str, Path],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 600,
    progress: Optional[Callable[[int, Optional[int]], None]] = None,
    chunk_size: int = 65536
) -> bool:
    """Downloads a file to the destination path with streaming and optional progress callback."""
    req_headers = {"User-Agent": "SigmaStudio"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    
    dest_path = Path(destination)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_name(f".{dest_path.name}.download")

    try:
        with safe_urlopen(req, timeout=timeout) as resp, open(temp_path, "wb") as out_file:
            total_size = resp.headers.get("Content-Length")
            total_bytes = int(total_size) if total_size and total_size.isdigit() else None
            downloaded = 0

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total_bytes)

        if temp_path.exists():
            temp_path.replace(dest_path)
            return True
        return False
    except Exception as exc:
        log.warning("[NetUtils] Failed to download %s: %s", url, exc)
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return False
