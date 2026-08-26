# ==============================================================================
# core/net_utils.py — Robust network utilities with automatic SSL resilience
#
# Resolves Windows certificate chain errors (e.g. "Missing Authority Key Identifier",
# missing root certificates, corporate proxies/antivirus TLS interception) by
# cascading from certifi -> default SSL context -> unverified fallback.
# ==============================================================================
from __future__ import annotations

import json
import logging
import os
import shutil
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

log = logging.getLogger(__name__)


def get_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Creates a robust SSL context.
    
    If verify is True, uses certifi CA bundle when available.
    If verify is False or if verification cannot be configured, returns an unverified context.
    """
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

    # 2. Try default system context
    try:
        return ssl.create_default_context()
    except Exception:
        pass

    # 3. Fallback to unverified context if system certificates are completely broken
    try:
        return ssl._create_unverified_context()
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def safe_urlopen(
    url_or_req: Union[str, urllib.request.Request],
    timeout: int = 30,
    **kwargs
) -> Any:
    """urllib.request.urlopen with automatic SSL certificate error recovery.
    
    If standard certificate verification fails (Missing Authority Key Identifier,
    self-signed proxy, outdated Windows CA store), it seamlessly falls back to
    an unverified context so operations never crash the application.
    """
    ctx = get_ssl_context(verify=True)
    try:
        return urllib.request.urlopen(url_or_req, timeout=timeout, context=ctx, **kwargs)
    except (ssl.SSLError, urllib.error.URLError, Exception) as exc:
        err_msg = str(exc).lower()
        if any(keyword in err_msg for keyword in ("ssl", "certificate", "verify failed", "authority key identifier", "handshake")):
            log.warning(
                "[NetUtils] SSL verification failed (%s). Retrying with fallback SSL context...",
                exc
            )
            unverified_ctx = get_ssl_context(verify=False)
            return urllib.request.urlopen(url_or_req, timeout=timeout, context=unverified_ctx, **kwargs)
        raise


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
