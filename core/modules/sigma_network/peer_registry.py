"""Registro dei peer per Sigma Network.

Mantiene lo stato dei peer noti (scoperti, fidati, bloccati) con persistenza
atomica su JSON. Lo stato e protetto da un RLock perche' il registro viene
letto dalle route HTTP e scritto dai thread di discovery in parallelo.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_STATES: tuple[str, ...] = ("discovered", "trusted", "blocked")

DEFAULT_PERSIST_PATH = "data/sigma_network/peers.json"


class PeerRegistry:
    """Registro thread-safe dei peer con persistenza JSON atomica.

    Il registro e la fonte di verita' per lo stato di ogni peer. Le route
    HTTP lo leggono per servire la UI; i thread di discovery lo aggiornano
    quando un peer risponde a un heartbeat. Un RLock (reentrante) copre
    tutte le mutazioni e le letture composite.
    """

    def __init__(self, persist_path: str = DEFAULT_PERSIST_PATH) -> None:
        self._persist_path: str = persist_path
        self._lock = threading.RLock()
        # peer_id -> dict conforme al contratto Peer in SPEC.md sezione 3
        self._peers: Dict[str, Dict[str, Any]] = {}
        self.load()

    # ------------------------------------------------------------------
    # Mutazioni
    # ------------------------------------------------------------------

    def add_peer(
        self,
        host: str,
        port: int,
        peer_id: str,
        public_key: str,
        name: str,
        models: Optional[List[str]] = None,
        version: str = "",
    ) -> Dict[str, Any]:
        """Inserisce o aggiorna un peer in stato ``discovered``.

        Se il peer esiste gia' vengono aggiornati i campi di rete e i modelli;
        lo stato non viene toccato per non degradare accidentalmente un peer
        gia' fidato.
        """
        with self._lock:
            existing = self._peers.get(peer_id)
            now = time.time()
            if existing is not None:
                existing["host"] = host
                existing["port"] = port
                if public_key:
                    existing["public_key"] = public_key
                existing["name"] = name
                existing["models"] = list(models) if models else []
                if version:
                    existing["version"] = version
                existing["last_seen"] = now
            else:
                peer: Dict[str, Any] = {
                    "peer_id": peer_id,
                    "name": name,
                    "host": host,
                    "port": port,
                    "public_key": public_key or "",
                    "state": "discovered",
                    "models": list(models) if models else [],
                    "version": version or "1.0.0",
                    "accepting": True,
                    "last_seen": now,
                    "latency_ms": None,
                }
                self._peers[peer_id] = peer
            return dict(self._peers[peer_id])

    def register(
        self,
        peer_id: str,
        name: str,
        host: str,
        port: int,
        models: Optional[List[str]] = None,
        version: str = "",
    ) -> Dict[str, Any]:
        """Metodo invocato dal discovery per registrare un annuncio UDP ricevuto."""
        with self._lock:
            existing = self._peers.get(peer_id)
            pub_key = existing.get("public_key", "") if existing else ""
            return self.add_peer(
                host=host,
                port=port,
                peer_id=peer_id,
                public_key=pub_key,
                name=name,
                models=models,
                version=version,
            )

    def set_state(self, peer_id: str, state: str) -> Dict[str, Any]:
        """Cambia lo stato di un peer tra ``discovered``, ``trusted``, ``blocked``.

        Rifiuta con ``ValueError`` stati non validi e con ``KeyError`` peer
        sconosciuti, perche' il chiamante (route HTTP) deve poter mappare
        l'errore su una risposta 400/404 senza ambiguita'.
        """
        if state not in VALID_STATES:
            raise ValueError(
                f"Stato non valido: {state!r}. Stati ammessi: {VALID_STATES}"
            )
        with self._lock:
            peer = self._peers.get(peer_id)
            if peer is None:
                raise KeyError(f"Peer sconosciuto: {peer_id}")
            peer["state"] = state
            return dict(peer)

    def touch(self, peer_id: str, latency_ms: Optional[float] = None) -> None:
        """Aggiorna ``last_seen`` e la latenza osservata di un peer.

        Chiamato dal thread di discovery a ogni heartbeat riuscito. Se il
        peer non esiste nel registro l'operazione e' un no-op: la scoperta
        vera e propria passa per ``add_peer``.
        """
        with self._lock:
            peer = self._peers.get(peer_id)
            if peer is None:
                return
            peer["last_seen"] = time.time()
            if latency_ms is not None:
                peer["latency_ms"] = latency_ms

    def remove(self, peer_id: str) -> bool:
        """Rimuove un peer dal registro. Ritorna ``True`` se era presente."""
        with self._lock:
            return self._peers.pop(peer_id, None) is not None

    # ------------------------------------------------------------------
    # Letture
    # ------------------------------------------------------------------

    def get(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Ritorna una copia del peer o ``None`` se non esiste."""
        with self._lock:
            peer = self._peers.get(peer_id)
            return dict(peer) if peer is not None else None

    def all_peers(self) -> List[Dict[str, Any]]:
        """Ritorna copie di tutti i peer, ordinati per ``last_seen`` decrescente."""
        with self._lock:
            peers = [dict(p) for p in self._peers.values()]
        peers.sort(key=lambda p: p.get("last_seen") or 0.0, reverse=True)
        return peers

    def trusted_peers(self) -> List[Dict[str, Any]]:
        """Ritorna solo i peer in stato ``trusted``.

        Il provider di inferenza usa questa lista per decidere a chi servire:
        un peer ``discovered`` o ``blocked`` non deve mai ricevere lavoro.
        """
        with self._lock:
            return [dict(p) for p in self._peers.values() if p["state"] == "trusted"]

    # ------------------------------------------------------------------
    # Persistenza
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persiste il registro su disco con scrittura atomica.

        Usa un file temporaneo nella stessa directory + ``os.replace`` perche'
        un crash a meta' scrittura non deve lasciare un JSON parzialmente
        valido che poi ``load`` non saprebbe interpretare.
        """
        with self._lock:
            payload = {peer_id: dict(p) for peer_id, p in self._peers.items()}
            directory = os.path.dirname(self._persist_path) or "."
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=directory, prefix=".peers_", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, self._persist_path)
            except Exception:
                # Pulizia del temporaneo se la sostituzione e' fallita
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def load(self) -> None:
        """Carica il registro dal disco, tollerando file assente o corrotto.

        Un file mancante e' il caso normale alla prima esecuzione: si parte da
        un registro vuoto senza log. Un file presente ma non parsabile e'
        un errore di stato: si logga un warning e si riparte da vuoto, perche'
        perdere i peer e' meno grave di bloccare l'avvio del server.
        """
        with self._lock:
            if not os.path.exists(self._persist_path):
                self._peers = {}
                return
            try:
                with open(self._persist_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    raise ValueError("payload non e' un dizionario")
                self._peers = {
                    str(pid): dict(p) for pid, p in data.items() if isinstance(p, dict)
                }
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                logger.warning(
                    "Registro peer non caricabile da %s (%s); si riparte da vuoto.",
                    self._persist_path,
                    exc,
                )
                self._peers = {}

    def get_network_map(self, local_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Restituisce la topologia completa della rete per il radar e la mappa dei peer."""
        now = time.time()
        local_info = local_info or {}
        local_peer_id = local_info.get("peer_id", "local")

        with self._lock:
            peer_list = [dict(p) for p in self._peers.values()]

        mapped_peers = []
        all_models = set(local_info.get("models", []))
        online_count = 1  # il nodo locale è sempre online

        for p in peer_list:
            if p.get("peer_id") == local_peer_id:
                continue

            last_seen = p.get("last_seen") or 0.0
            is_online = (now - last_seen) < 120.0  # online se visto negli ultimi 2 minuti
            latency = p.get("latency_ms")
            if is_online and latency is None:
                latency = 28.0  # stima default se non ancora pingato

            if is_online:
                online_count += 1
                for m in p.get("models", []):
                    all_models.add(m)

            # Angolo fisso deterministico basato sull'hash del peer_id (0-360)
            pid_hash = hash(p.get("peer_id", ""))
            angle = abs(pid_hash) % 360

            # Distanza dal centro basata su latenza (0.2 - 0.95)
            effective_latency = latency if latency is not None else 150.0
            distance_factor = min(0.95, max(0.25, effective_latency / 250.0))

            mapped_peers.append({
                "peer_id": p.get("peer_id"),
                "name": p.get("name", "Peer"),
                "host": p.get("host", "127.0.0.1"),
                "port": p.get("port", 8000),
                "state": p.get("state", "discovered"),
                "models": p.get("models", []),
                "version": p.get("version", "1.0.0"),
                "accepting": p.get("accepting", True),
                "last_seen": last_seen,
                "latency_ms": latency,
                "is_online": is_online,
                "radar_angle": angle,
                "radar_distance": distance_factor,
            })

        # Ordina per stato (trusted prima) e poi per online
        mapped_peers.sort(key=lambda x: (x["state"] == "trusted", x["is_online"]), reverse=True)

        return {
            "local_node": {
                "peer_id": local_peer_id,
                "name": local_info.get("name", "Sigma Studio"),
                "models": local_info.get("models", []),
                "version": local_info.get("version", "0.1.0"),
                "is_online": True,
                "radar_angle": 0,
                "radar_distance": 0.0,
            },
            "peers": mapped_peers,
            "summary": {
                "total_known": len(mapped_peers),
                "online_count": online_count,
                "trusted_count": sum(1 for p in mapped_peers if p["state"] == "trusted"),
                "cluster_models_count": len(all_models),
                "unique_models": sorted(list(all_models)),
                "cluster_status": "active" if online_count > 1 else "solo",
            },
        }

