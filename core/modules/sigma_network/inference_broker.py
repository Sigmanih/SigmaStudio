"""Sigma Network — Inference Broker.

Instrada una richiesta di inferenza verso un peer remoto e produce i token
ricevuti in streaming.

Usa `requests` con stream=True. Ogni errore di rete diventa un evento di
errore, mai un'eccezione che sfugge al chiamante.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Generator, Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT_S = 120


class InferenceBroker:
    """Client lato richiedente: invia richieste di inferenza a peer remoti."""

    def __init__(self) -> None:
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # request_inference
    # ------------------------------------------------------------------
    def request_inference(
        self,
        peer: Dict[str, Any],
        prompt: str,
        model: str,
        max_tokens: int,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Generatore che firma la richiesta, la invia al peer remoto e
        produce i token ricevuti in streaming.

        Ogni errore di rete produce un evento ``{"type": "error", ...}``;
        non solleva eccezioni al chiamante.
        """
        host = peer.get("host", "127.0.0.1")
        port = int(peer.get("port", 8080))
        url = f"http://{host}:{port}/api/sigma_network/p2p/infer"

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "max_tokens": max_tokens,
            "timestamp": time.time(),
        }
        if identity:
            payload["identity"] = identity

        try:
            resp = self._session.post(
                url,
                json=payload,
                stream=True,
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            yield {"type": "error", "error": f"connection_error: {exc}", "reason": f"connection_error: {exc}"}
            return
        except requests.exceptions.Timeout as exc:
            yield {"type": "error", "error": f"timeout: {exc}", "reason": f"timeout: {exc}"}
            return
        except requests.exceptions.HTTPError as exc:
            yield {"type": "error", "error": f"http_error: {exc}", "reason": f"http_error: {exc}"}
            return
        except requests.exceptions.RequestException as exc:
            yield {"type": "error", "error": f"request_error: {exc}", "reason": f"request_error: {exc}"}
            return

        # Stream dei token
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # Ogni riga e un token (o una riga JSON con campo "token")
                if line.startswith("{"):
                    import json as _json
                    try:
                        obj = _json.loads(line)
                        if obj.get("type") == "error":
                            yield {"type": "error", "reason": obj.get("reason", "unknown")}
                            return
                        token = obj.get("token", "")
                    except ValueError:
                        token = line
                else:
                    token = line
                if token:
                    yield {"type": "token", "text": token}
        except requests.exceptions.ChunkedEncodingError as exc:
            yield {"type": "error", "reason": f"stream_error: {exc}"}
        except requests.exceptions.RequestException as exc:
            yield {"type": "error", "reason": f"stream_error: {exc}"}

    # ------------------------------------------------------------------
    # hello
    # ------------------------------------------------------------------
    def hello(self, peer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Chiama GET /p2p/hello sul peer remoto e restituisce le capacita,
        o None se il peer e irraggiungibile."""
        host = peer.get("host", "127.0.0.1")
        port = int(peer.get("port", 8080))
        url = f"http://{host}:{port}/api/sigma_network/p2p/hello"

        try:
            resp = self._session.get(url, timeout=_TIMEOUT_S)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException:
            logger.debug("Peer %s:%s irraggiungibile su /hello", host, port)
            return None
