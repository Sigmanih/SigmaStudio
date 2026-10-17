"""Scoperta dei peer sulla rete locale via broadcast UDP.

La classe :class:`PeerDiscovery` emette periodicamente un annuncio JSON
sulla porta 47777 e ascolta gli annunci altrui per registrare i peer
scoperti nel :class:`~core.modules.sigma_network.registry.PeerRegistry`
in stato ``discovered``.

Un peer scoperto NON diventa mai automaticamente ``trusted``: la fiducia
e' una decisione esplicita dell'utente (vedi SPEC.md).
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import struct
import threading
import time
import urllib.request
import concurrent.futures
from typing import Any, Dict, List, Optional, Set, Tuple

from core.modules.sigma_network.peer_registry import PeerRegistry

logger = logging.getLogger(__name__)

#: Porta UDP convenzionale per la scoperta dei peer Sigma Network.
DISCOVERY_PORT: int = 47777

#: Gruppo Multicast locale per superare filtri di broadcast e switch/adapter multipli.
MULTICAST_GROUP: str = "239.255.42.99"

#: Intervallo di broadcast in secondi.
BROADCAST_INTERVAL: float = 12.0

#: Intervallo di sweep della subnet locale in secondi.
SWEEP_INTERVAL: float = 90.0


def get_active_interfaces_and_broadcasts() -> List[Tuple[str, str, str]]:
    """Rileva le interfacce IPv4 attive escludendo loopback e APIPA.

    Restituisce una lista di tuple: (nome_interfaccia, ip_locale, broadcast_ip).
    Funziona sia con psutil (se disponibile) sia con fallback su getaddrinfo.
    """
    interfaces: List[Tuple[str, str, str]] = []
    try:
        import psutil
        for iface_name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                # Famiglia 2 = AF_INET (IPv4)
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                        continue
                    netmask = addr.netmask or "255.255.255.0"
                    try:
                        net = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                        bcast = str(net.broadcast_address)
                        interfaces.append((iface_name, ip, bcast))
                    except Exception:
                        pass
    except Exception as exc:
        logger.debug("Rilevamento interfacce con psutil fallito: %s", exc)

    if not interfaces:
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                    # Stima /24 standard per LAN
                    parts = ip.split(".")
                    if len(parts) == 4:
                        bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                        interfaces.append(("default", ip, bcast))
        except Exception as exc:
            logger.debug("Fallback getaddrinfo per broadcast fallito: %s", exc)

    return interfaces


class PeerDiscovery:
    """Scoperta peer-to-peer su rete locale tramite UDP broadcast, multicast e sweep LAN.

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
        on_peer_found: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._peer_id = peer_id
        self._name = name
        self._port = port
        self._models: List[str] = list(models) if models else []
        self._version = version
        self._on_peer_found = on_peer_found

        self._broadcast_socket: Optional[socket.socket] = None
        self._listen_socket: Optional[socket.socket] = None
        self._broadcast_thread: Optional[threading.Thread] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._sweep_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Avvia i thread di broadcast, ascolto e sweep subnet (idempotente)."""
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
            self._sweep_thread = threading.Thread(
                target=self._subnet_sweep_loop,
                name="sigma-discovery-sweep",
                daemon=True,
            )
            self._broadcast_thread.start()
            self._listen_thread.start()
            self._sweep_thread.start()
            self._running = True
            logger.info("PeerDiscovery avviato (peer_id=%s, port=%d, multicast=%s)", self._peer_id, self._port, MULTICAST_GROUP)

    def stop(self) -> None:
        """Ferma i thread e chiude le socket (idempotente)."""
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()

            for thread in (self._broadcast_thread, self._listen_thread, self._sweep_thread):
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
            self._sweep_thread = None
            self._running = False
            logger.info("PeerDiscovery fermato")

    def is_running(self) -> bool:
        """Indica se la scoperta e' attiva."""
        return self._running

    def announce_now(self) -> None:
        """Forza l'emissione immediata di un annuncio su tutte le interfacce."""
        try:
            if self._broadcast_socket is None:
                self._broadcast_socket = self._make_broadcast_socket()
            self._send_announcement_all_targets()
            logger.debug("Annuncio discovery immediato inviato (peer_id=%s)", self._peer_id)
        except Exception as exc:
            logger.debug("Errore emissione broadcast immediato: %s", exc)

    def sweep_now(self) -> int:
        """Esegue una scansione immediata della subnet locale per scoprire peer collegati."""
        return self._perform_subnet_sweep()

    # ------------------------------------------------------------------
    # Costruzione socket
    # ------------------------------------------------------------------

    def _make_broadcast_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Abilita anche multicast TTL per la LAN
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        except OSError:
            pass
        sock.settimeout(1.0)
        return sock

    def _make_listen_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT"), 1)
        except OSError:
            pass

        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(0.5)

        # Iscrizione al gruppo multicast su tutte le interfacce per aggirare blocchi router
        try:
            mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            logger.debug("Iscrizione multicast %s riuscita", MULTICAST_GROUP)
        except OSError as exc:
            logger.debug("Iscrizione multicast non riuscita: %s", exc)

        return sock

    def _send_announcement_all_targets(self) -> None:
        """Invia l'annuncio su broadcast globale, multicast e tutti gli indirizzi di subnet."""
        if self._broadcast_socket is None:
            return
        payload = self._build_announcement()
        data = json.dumps(payload).encode("utf-8")

        # 1. Target standard broadcast
        targets: Set[str] = {"<broadcast>", "255.255.255.255", MULTICAST_GROUP}

        # 2. Target specifici per ogni scheda di rete (es. 192.168.1.255)
        for _, _, bcast in get_active_interfaces_and_broadcasts():
            if bcast:
                targets.add(bcast)

        for target in targets:
            try:
                self._broadcast_socket.sendto(data, (target, DISCOVERY_PORT))
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Loop di broadcast
    # ------------------------------------------------------------------

    def _broadcast_loop(self) -> None:
        """Emette l'annuncio ogni BROADCAST_INTERVAL secondi."""
        while not self._stop_event.is_set():
            try:
                self._send_announcement_all_targets()
            except OSError as exc:
                logger.debug("Errore broadcast: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Errore imprevisto nel broadcast: %s", exc)
            self._stop_event.wait(BROADCAST_INTERVAL)

    # ------------------------------------------------------------------
    # Loop di sweep della subnet locale (Zero-Config per Windows Firewall)
    # ------------------------------------------------------------------

    def _subnet_sweep_loop(self) -> None:
        """Esegue una prima scansione rapida della subnet LAN, poi periodicamente."""
        # Breve attesa iniziale per permettere l'avvio del server FastAPI
        time.sleep(2.0)
        while not self._stop_event.is_set():
            try:
                self._perform_subnet_sweep()
            except Exception as exc:
                logger.debug("Errore durante subnet sweep periodico: %s", exc)
            self._stop_event.wait(SWEEP_INTERVAL)

    def _perform_subnet_sweep(self) -> int:
        """Scansiona le subnet /24 delle interfacce attive alla ricerca di peer Sigma Studio."""
        interfaces = get_active_interfaces_and_broadcasts()
        discovered_count = 0
        candidate_ips: Set[str] = set()

        for _, local_ip, _ in interfaces:
            parts = local_ip.split(".")
            if len(parts) == 4:
                prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
                for host_num in range(1, 255):
                    ip = f"{prefix}{host_num}"
                    if ip != local_ip:
                        candidate_ips.add(ip)

        if not candidate_ips:
            return 0

        target_port = self._port

        def _probe_ip(ip: str) -> Optional[Dict[str, Any]]:
            url = f"http://{ip}:{target_port}/api/sigma_network/p2p/hello"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SigmaNetwork-ClusterSweeper"})
                with urllib.request.urlopen(req, timeout=0.20) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, dict) and data.get("peer_id"):
                            return {"host": ip, "data": data}
            except Exception:
                pass
            return None

        # Thread pool leggero per completare la scansione /24 in ~1 secondo
        with concurrent.futures.ThreadPoolExecutor(max_workers=35) as executor:
            future_to_ip = {executor.submit(_probe_ip, ip): ip for ip in candidate_ips}
            for future in concurrent.futures.as_completed(future_to_ip):
                if self._stop_event.is_set():
                    break
                try:
                    res = future.result()
                    if res:
                        peer_info = res["data"]
                        remote_peer_id = peer_info.get("peer_id")
                        if remote_peer_id and remote_peer_id != self._peer_id:
                            registered = self._registry.register(
                                peer_id=remote_peer_id,
                                name=peer_info.get("name", "Sigma Peer"),
                                host=res["host"],
                                port=target_port,
                                models=list(peer_info.get("models") or []),
                                version=str(peer_info.get("version") or "1.0.0"),
                            )
                            discovered_count += 1
                            logger.info(
                                "[ClusterSweeper] Peer rilevato automaticamente sulla LAN: %s (%s:%d)",
                                remote_peer_id, res["host"], target_port,
                            )
                            if self._on_peer_found and callable(self._on_peer_found):
                                try:
                                    self._on_peer_found(res["host"], target_port, peer_info)
                                except Exception as cb_err:
                                    logger.debug("Callback on_peer_found errore: %s", cb_err)
                except Exception as exc:
                    logger.debug("Errore valutazione probe IP: %s", exc)

        return discovered_count

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
            peer_host = addr[0]
            peer_port = int(announcement.get("port", 0))
            self._registry.register(
                peer_id=peer_id,
                name=announcement.get("name", "unknown"),
                host=peer_host,
                port=peer_port,
                models=list(announcement.get("models", [])),
                version=str(announcement.get("version", "")),
            )
            if self._on_peer_found and callable(self._on_peer_found):
                try:
                    self._on_peer_found(peer_host, peer_port, announcement)
                except Exception as cb_err:
                    logger.debug("Callback on_peer_found su annuncio fallito: %s", cb_err)
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
        known_peers = [
            {"peer_id": p.get("peer_id"), "host": p.get("host"), "port": p.get("port")}
            for p in self._registry.all_peers()
            if p.get("peer_id") != self._peer_id
        ][:8]

        return {
            "peer_id": self._peer_id,
            "name": self._name,
            "port": self._port,
            "models": self._models,
            "version": self._version,
            "peers": known_peers,
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
