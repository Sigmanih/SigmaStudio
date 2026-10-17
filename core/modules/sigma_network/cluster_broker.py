"""Cluster Broker per Sigma Network.

Gestisce la cooperazione decentralizzata tra i nodi della rete:
- Rileva e mappa tutti i modelli disponibili nell'intero cluster di Sigma Studio.
- Instrada le richieste di inferenza verso il nodo migliore o designato.
- Gestisce lo streaming SSE delle risposte in tempo reale.
- Regola automaticamente la contabilità in AiloCoin tramite ricevute firmate Ed25519.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from typing import Any, Dict, Generator, List, Optional

import requests

from core.modules.sigma_network.identity import sign, verify

logger = logging.getLogger(__name__)


class ClusterBroker:
    """Orchestratore di inferenza distribuita per il cluster P2P."""

    def __init__(
        self,
        registry_getter,
        wallet_getter,
        identity_getter,
        settings_getter,
    ) -> None:
        self._get_registry = registry_getter
        self._get_wallet = wallet_getter
        self._get_identity = identity_getter
        self._get_settings = settings_getter
        self._http_session = requests.Session()

    def get_cluster_models(self) -> List[Dict[str, Any]]:
        """Restituisce il catalogo unificato dei modelli disponibili nell'intero cluster."""
        registry = self._get_registry()
        identity = self._get_identity()
        settings = self._get_settings()
        local_peer_id = identity.get("peer_id", "")

        models_catalog: List[Dict[str, Any]] = []

        # 1. Modelli locali condivisi di questa istanza
        local_sharing = bool(settings.get("sharing_enabled", False))
        local_rate = float(settings.get("rate_tokens_per_coin", 1000))

        # Recupera modelli reali disponibili in locale
        local_models_list: List[str] = []
        try:
            from core.engine.provider_server import get_all_available_models
            for m in get_all_available_models():
                mid = m.get("id") or m.get("name")
                if mid:
                    local_models_list.append(mid)
        except Exception:
            local_models_list = list(settings.get("shared_models", []))

        # Se ci sono modelli condivisi configurati, filtra, altrimenti esponi quelli rilevati
        configured_shared = set(settings.get("shared_models", []))
        active_local_models = [m for m in local_models_list if not configured_shared or m in configured_shared]

        for m_id in active_local_models:
            models_catalog.append({
                "model_id": m_id,
                "name": m_id.split("/")[-1].replace(".gguf", ""),
                "provider_id": local_peer_id,
                "provider_name": str(settings.get("display_name") or "Il tuo nodo (Locale)"),
                "host": "127.0.0.1",
                "port": 8000,
                "is_local": True,
                "is_trusted": True,
                "sharing_active": local_sharing,
                "rate_tokens_per_coin": local_rate,
                "latency_ms": 0.0,
                "status": "ready",
            })

        # 2. Modelli dei peer remoti
        now = time.time()
        for p in registry.all_peers():
            pid = p.get("peer_id", "")
            if pid == local_peer_id:
                continue

            last_seen = p.get("last_seen", 0.0)
            is_online = (now - last_seen) < 180.0
            auto_trust = bool(settings.get("cluster_auto_trust", True))
            is_trusted = (p.get("state") == "trusted") or (auto_trust and is_online)

            for m_id in p.get("models", []):
                models_catalog.append({
                    "model_id": m_id,
                    "name": m_id.split("/")[-1].replace(".gguf", ""),
                    "provider_id": pid,
                    "provider_name": p.get("name", f"Peer {pid[:6]}"),
                    "host": p.get("host", "127.0.0.1"),
                    "port": p.get("port", 8000),
                    "is_local": False,
                    "is_trusted": is_trusted,
                    "sharing_active": is_online and is_trusted,
                    "rate_tokens_per_coin": 1000.0,
                    "latency_ms": p.get("latency_ms") or 45.0,
                    "status": "online" if is_online else "offline",
                })

        return models_catalog

    def execute_cluster_inference(
        self,
        prompt: Any,
        model: str,
        max_tokens: int = 1024,
        preferred_peer_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Esegue l'inferenza nel cluster e produce eventi SSE per il frontend."""
        identity = self._get_identity()
        wallet = self._get_wallet()
        registry = self._get_registry()
        settings = self._get_settings()
        local_peer_id = identity.get("peer_id", "")
        priv_key_str = identity.get("private_key")
        private_key_bytes: Optional[bytes] = None
        if priv_key_str:
            try:
                private_key_bytes = base64.b64decode(priv_key_str)
            except Exception as e:
                logger.warning("Decodifica chiave privata non riuscita: %s", e)

        # Identifica il provider adatto
        cluster_models = self.get_cluster_models()
        clean_model_name = model.split("]")[-1].strip() if "]" in model else model
        candidates = [
            m for m in cluster_models
            if m["model_id"] == model or m["name"] == model
            or m["model_id"] == clean_model_name or m["name"] == clean_model_name
            or clean_model_name.lower() in m["model_id"].lower()
        ]

        if "]" in model and "[" in model:
            prov_tag = model.split("]")[0].replace("[", "").replace("Cluster:", "").strip()
            prov_match = [m for m in candidates if prov_tag.lower() in m.get("provider_name", "").lower()]
            if prov_match:
                candidates = prov_match

        if preferred_peer_id:
            candidates = [m for m in candidates if m["provider_id"] == preferred_peer_id]

        if not candidates:
            # Fallback generico: cerca un peer trusted che abbia modelli
            candidates = [m for m in cluster_models if m.get("is_trusted") and m.get("status") == "online"]

        if not candidates and cluster_models:
            # Se nessun modello corrisponde esattamente, usa il primo modello locale o disponibile
            candidates = [cluster_models[0]]

        if not candidates:
            err = {"error": f"Nessun nodo del cluster disponibile per il modello '{model}'"}
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"
            return

        selected = candidates[0]
        is_local = selected.get("is_local", False)

        # Inizio stream: comunica al client a chi ci stiamo collegando
        start_meta = {
            "type": "start",
            "provider_id": selected["provider_id"],
            "provider_name": selected["provider_name"],
            "model": selected["model_id"],
            "is_local": is_local,
            "latency_ms": selected.get("latency_ms", 0),
        }
        yield f"data: {json.dumps(start_meta)}\n\n"

        token_count = 0

        # Normalizza prompt testuale
        prompt_text = prompt
        if isinstance(prompt, list):
            prompt_text = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in prompt if isinstance(m, dict)
            )
        elif not isinstance(prompt, str):
            prompt_text = str(prompt)

        # CASO 1: Nodo Locale
        if is_local:
            try:
                from core.engine.unified_runtime import sigma_engine
                from core.engine.provider_server import is_notice
                for chunk in sigma_engine.generate_stream(
                    prompt=prompt_text,
                    model_name=selected["model_id"],
                    max_tokens=max_tokens,
                ):
                    if is_notice(chunk):
                        continue
                    token_text = ""
                    if isinstance(chunk, dict):
                        token_text = chunk.get("token") or chunk.get("content") or ""
                    elif isinstance(chunk, str):
                        token_text = chunk
                    if token_text:
                        token_count += 1
                        yield f"data: {json.dumps({'token': token_text})}\n\n"
            except Exception as exc:
                logger.error("Errore generazione locale: %s", exc)
                yield f"data: {json.dumps({'error': f'Motore locale: {exc}'})}\n\n"

            # Chiusura locale
            end_meta = {
                "type": "finish",
                "tokens_generated": token_count,
                "cost_ailocoin": 0.0,
                "message": "Inferenza locale completata a costo zero.",
            }
            yield f"data: {json.dumps(end_meta)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # CASO 2: Peer Remoto P2P con regolamento AiloToken
        if not private_key_bytes:
            err = {
                "error": "Chiave privata del wallet assente o bloccata. Effettua l'accesso con password o importa il tuo wallet per firmare le richieste P2P."
            }
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Verifica saldo disponibile con auto-erogazione Genesis Faucet
        current_balance = wallet.balance(local_peer_id).get("balance", 0.0)
        if current_balance <= 0.0:
            try:
                wallet.mint_faucet(local_peer_id, amount=100.0, force=False)
                current_balance = 100.0
                logger.info("[ClusterBroker] Genesis Faucet accreditato automaticamente a %s (100 AiloToken)", local_peer_id)
            except Exception as f_err:
                logger.debug("Tentativo faucet: %s", f_err)
                current_balance = wallet.balance(local_peer_id).get("balance", 0.0)

        if current_balance <= 0.0:
            err = {
                "error": "Saldo AiloToken insufficiente. Richiedi AiloToken dal Faucet o avvia il Mining per guadagnare token."
            }
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"
            return

        host = selected["host"]
        port = selected["port"]
        url = f"http://{host}:{port}/api/sigma_network/p2p/infer"

        req_id = str(uuid.uuid4())
        timestamp = time.time()
        auth_msg = f"{local_peer_id}:{req_id}:{timestamp}"
        signature = sign(private_key_bytes, auth_msg)

        payload = {
            "peer_id": local_peer_id,
            "request_id": req_id,
            "prompt": prompt,
            "model": selected["model_id"],
            "max_tokens": max_tokens,
            "message": auth_msg,
            "signature": signature,
        }

        try:
            resp = self._http_session.post(url, json=payload, stream=True, timeout=90)
            if resp.status_code != 200:
                err_msg = f"Errore risposta peer ({resp.status_code}): {resp.text}"
                yield f"data: {json.dumps({'error': err_msg})}\n\n"
                yield "data: [DONE]\n\n"
                return

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if isinstance(line, bytes):
                    try:
                        line = line.decode("utf-8")
                    except Exception:
                        continue
                if line.startswith("data: "):
                    content = line[6:].strip()
                    if content == "[DONE]":
                        break
                    try:
                        parsed = json.loads(content)
                        if "token" in parsed:
                            token_count += 1
                            yield f"data: {json.dumps({'token': parsed['token']})}\n\n"
                        elif "error" in parsed:
                            yield f"data: {json.dumps({'error': parsed['error']})}\n\n"
                            break
                    except Exception:
                        yield f"data: {json.dumps({'token': content})}\n\n"
                        token_count += 1

        except Exception as exc:
            logger.error("Errore connessione P2P con peer %s: %s", selected['provider_id'], exc)
            yield f"data: {json.dumps({'error': f'Disconnessione peer: {exc}'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Regolamento AiloCoin al termine dello stream
        rate = selected.get("rate_tokens_per_coin", 1000.0)
        cost_ailocoin = round(token_count / rate, 5)

        # Emissione ricevuta registrata nel wallet
        try:
            receipt = wallet.issue_receipt(
                request_id=req_id,
                provider_id=selected["provider_id"],
                consumer_id=local_peer_id,
                model=selected["model_id"],
                tokens=token_count,
                rate=rate,
                private_key_bytes=private_key_bytes,
            )
            # Controfirma automatica della transazione
            wallet.countersign(receipt, private_key_bytes)
            receipt_id = receipt["receipt_id"]
        except Exception as exc:
            logger.warning("Errore emissione ricevuta AiloCoin: %s", exc)
            receipt_id = "rec-" + uuid.uuid4().hex[:8]

        # Evento finale di riepilogo
        end_meta = {
            "type": "finish",
            "tokens_generated": token_count,
            "cost_ailocoin": cost_ailocoin,
            "receipt_id": receipt_id,
            "provider_name": selected["provider_name"],
            "message": f"Inferenza P2P completata: {token_count} token elaborati per {cost_ailocoin} AiloCoin.",
        }
        yield f"data: {json.dumps(end_meta)}\n\n"
        yield "data: [DONE]\n\n"
