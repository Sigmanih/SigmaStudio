"""Scoperta dei peer sulla rete locale via broadcast UDP.

La classe :class:`PeerDiscovery` emette periodicamente un annuncio JSON
sulla porta 47777 e ascolta gli annunci altrui per registrare i peer
scoperti nel :class:`~core.modules.sigma_network.registry.PeerRegistry`
in stato ``discovered``.

Un peer scoperto NON diventa mai automaticamente ``trusted``: la fiducia
e' una decisione esplicita dell'utente (vedi SPEC.md).
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import Any, Dict, List, Optional

from core.modules.sigma_network.peer_registry import PeerRegistry

logger = logging.getLogger(__name__)

#: Porta UDP convenzionale per la scoperta dei peer Sigma Network.
DISCOVERY_PORT: int = 47777

#: Intervallo di broadcast in secondi.
BROADCAST_INTERVAL: float = 15.0


class PeerDiscovery:
    """Scoperta peer-to-peer su rete locale tramite UDP broadcast.

    Parametri
    ---------
    registry:
        Registro dei peer dove registrare gli annunci ricevuti.
    peer_id:
        Identificativo univoco del peer locale (usato per ignorare il
        proprio annuncio).
    name:
        Nome amichevole del peer locale.
    port:
        Porta TCP del servizio inferenza locale (annunciata ai peer).
    models:
        Lista di modelli disponibili sul peer locale.
    version:
        Versione del software Sigma Network.
    """

    def __init__(
        self,
        registry: PeerRegistry,
        peer_id: str,
        name: str = "sigma-peer",
        port: int = 8000,
        models: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> None:
        self._registry = registry
        self._peer_id = peer_id
        self._name = name
        self._port = port
        self._models: List[str] = list(models) if models else []
        self._version = version

        self._broadcast_socket: Optional[socket.socket] = None
        self._listen_socket: Optional[socket.socket] = None
        self._broadcast_thread: Optional[threading.Thread] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Avvia i thread di broadcast e ascolto (idempotente)."""
        with self._lock:
            if self._running:
                return
            self._stop_event.clear()
            self._broadcast_socket = self._make_broadcast_socket()
            self._listen_socket = self._make_listen_socket()

            self._broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                name="sigma-discovery-broadcast",
                daemon=True,
            )
            self._listen_thread = threading.Thread(
                target=self._listen_loop,
                name="sigma-discovery-listen",
                daemon=True,
            )
            self._broadcast_thread.start()
            self._listen_thread.start()
            self._running = True
            logger.info("PeerDiscovery avviato (peer_id=%s)", self._peer_id)

    def stop(self) -> None:
        """Ferma i thread e chiude le socket (idempotente)."""
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()

            for thread in (self._broadcast_thread, self._listen_thread):
                if thread is not None and thread.is_alive():
                    thread.join(timeout=2.0)

            for sock in (self._broadcast_socket, self._listen_socket):
                if sock is not None:
                    try:
                        sock.close()
                    except OSError as exc:  # pragma: no cover - defensive
                        logger.debug("Errore chiusura socket: %s", exc)

            self._broadcast_socket = None
            self._listen_socket = None
            self._broadcast_thread = None
            self._listen_thread = None
            self._running = False
            logger.info("PeerDiscovery fermato")

    def is_running(self) -> bool:
        """Indica se la scoperta e' attiva."""
        return self._running

    def announce_now(self) -> None:
        """Forza l'emissione immediata di un annuncio UDP broadcast."""
        try:
            if self._broadcast_socket is None:
                self._broadcast_socket = self._make_broadcast_socket()
            payload = self._build_announcement()
            data = json.dumps(payload).encode("utf-8")
            self._broadcast_socket.sendto(data, ("<broadcast>", DISCOVERY_PORT))
            try:
                self._broadcast_socket.sendto(data, ("255.255.255.255", DISCOVERY_PORT))
            except OSError:
                pass
            logger.debug("Annuncio discovery immediato inviato (peer_id=%s)", self._peer_id)
        except Exception as exc:
            logger.debug("Errore emissione broadcast immediato: %s", exc)

    # ------------------------------------------------------------------
    # Costruzione socket
    # ------------------------------------------------------------------

    def _make_broadcast_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)
        return sock

    def _make_listen_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(0.5)
        return sock

    # ------------------------------------------------------------------
    # Loop di broadcast
    # ------------------------------------------------------------------

    def _broadcast_loop(self) -> None:
        """Emette l'annuncio ogni BROADCAST_INTERVAL secondi."""
        while not self._stop_event.is_set():
            try:
                if self._broadcast_socket is not None:
                    payload = self._build_announcement()
                    data = json.dumps(payload).encode("utf-8")
                    self._broadcast_socket.sendto(data, ("<broadcast>", DISCOVERY_PORT))
                    try:
                        self._broadcast_socket.sendto(data, ("255.255.255.255", DISCOVERY_PORT))
                    except OSError:
                        pass
            except OSError as exc:
                logger.debug("Errore broadcast: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Errore imprevisto nel broadcast: %s", exc)
            self._stop_event.wait(BROADCAST_INTERVAL)

    # ------------------------------------------------------------------
    # Loop di ascolto
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        """Riceve gli annunci altrui e li registra nel PeerRegistry."""
        while not self._stop_event.is_set():
            try:
                if self._listen_socket is None:
                    break
                data, addr = self._listen_socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError as exc:
                logger.debug("Errore ricezione: %s", exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Errore imprevisto nella ricezione: %s", exc)
                continue

            self._handle_announcement(data, addr)

    def _handle_announcement(self, data: bytes, addr: tuple) -> None:
        """Elabora un annuncio ricevuto: parsing, filtro, registrazione."""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Annuncio non UTF-8 da %s, ignorato", addr)
            return

        announcement = self.parse_announcement(text)
        if announcement is None:
            logger.debug("Annuncio malformato da %s, ignorato", addr)
            return

        peer_id = announcement.get("peer_id")
        if not peer_id or peer_id == self._peer_id:
            logger.debug("Proprio annuncio o peer_id mancante da %s, ignorato", addr)
            return

        try:
            self._registry.register(
                peer_id=peer_id,
                name=announcement.get("name", "unknown"),
                host=addr[0],
                port=int(announcement.get("port", 0)),
                models=list(announcement.get("models", [])),
                version=str(announcement.get("version", "")),
            )
        except (TypeError, ValueError) as exc:
            logger.debug("Annuncio con campi invalidi da %s: %s", addr, exc)
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Errore registrazione peer da %s: %s", addr, exc)
            return

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _build_announcement(self) -> Dict[str, Any]:
        """Costruisce il payload JSON dell'annuncio locale."""
        return {
            "peer_id": self._peer_id,
            "name": self._name,
            "port": self._port,
            "models": self._models,
            "version": self._version,
        }

    @staticmethod
    def parse_announcement(text: str) -> Optional[Dict[str, Any]]:
        """Parsa un annuncio JSON.

        Restituisce il dizionario se il testo e' un oggetto JSON valido con
        almeno la chiave ``peer_id``; altrimenti ``None``.
        """
        try:
            obj = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(obj, dict):
            return None
        if "peer_id" not in obj:
            return None
        return obj
