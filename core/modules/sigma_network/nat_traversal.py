"""NAT Traversal & STUN Client per Sigma Network (RFC 5389).

Fornisce la risoluzione dell'indirizzo IP pubblico e della porta mappata
(reflexive address) tramite server STUN pubblici (Google, Cloudflare) senza
dipendenze esterne oltre alle librerie standard di Python (socket, struct, os).
"""

from __future__ import annotations

import logging
import os
import socket
import struct
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Server STUN pubblici standard ad alta disponibilita'
DEFAULT_STUN_SERVERS: List[Tuple[str, int]] = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
    ("stun.services.mozilla.com", 3478),
]

# Costanti STUN RFC 5389
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101
STUN_MAGIC_COOKIE = 0x2112A442

ATTR_MAPPED_ADDRESS = 0x0001
ATTR_XOR_MAPPED_ADDRESS = 0x0020


class STUNClient:
    """Client STUN leggero per NAT Traversal su socket UDP."""

    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout

    def get_public_address(
        self,
        local_port: int = 0,
        servers: Optional[List[Tuple[str, int]]] = None,
    ) -> Optional[Tuple[str, int]]:
        """Interroga i server STUN per ottenere la coppia (public_ip, public_port)."""
        target_servers = servers or DEFAULT_STUN_SERVERS

        for host, port in target_servers:
            try:
                res = self._query_stun(host, port, local_port)
                if res:
                    logger.info("[STUN] IP pubblico riflesso rilevato: %s:%d (via %s)", res[0], res[1], host)
                    return res
            except Exception as exc:
                logger.debug("[STUN] Fallito probe su %s:%d: %s", host, port, exc)

        return None

    def _query_stun(self, host: str, port: int, local_port: int) -> Optional[Tuple[str, int]]:
        # Genera un transaction ID univoco di 12 byte (96 bit)
        transaction_id = os.urandom(12)

        # Header STUN: Message Type (2B), Message Length (2B), Magic Cookie (4B), Transaction ID (12B)
        header = struct.pack(
            "!HHI12s",
            STUN_BINDING_REQUEST,
            0,  # Nessun attributo nel body per Binding Request
            STUN_MAGIC_COOKIE,
            transaction_id,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            if local_port > 0:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("", local_port))
                except OSError:
                    # Se la porta locale è già vincolata, lascia scegliere al SO
                    pass

            sock.sendto(header, (host, port))
            response, _ = sock.recvfrom(2048)

            if len(response) < 20:
                return None

            msg_type, msg_len, magic, resp_tx_id = struct.unpack("!HHI12s", response[:20])

            if msg_type != STUN_BINDING_RESPONSE or resp_tx_id != transaction_id:
                return None

            # Parsing degli attributi nel body della risposta
            offset = 20
            end = 20 + msg_len
            while offset + 4 <= end and offset + 4 <= len(response):
                attr_type, attr_len = struct.unpack("!HH", response[offset : offset + 4])
                val_offset = offset + 4
                attr_val = response[val_offset : val_offset + attr_len]

                if attr_type == ATTR_XOR_MAPPED_ADDRESS and len(attr_val) >= 8:
                    family = attr_val[1]
                    xport = struct.unpack("!H", attr_val[2:4])[0]
                    real_port = xport ^ (STUN_MAGIC_COOKIE >> 16)

                    if family == 0x01:  # IPv4
                        xip = struct.unpack("!I", attr_val[4:8])[0]
                        real_ip_int = xip ^ STUN_MAGIC_COOKIE
                        real_ip = socket.inet_ntoa(struct.pack("!I", real_ip_int))
                        return (real_ip, real_port)

                elif attr_type == ATTR_MAPPED_ADDRESS and len(attr_val) >= 8:
                    family = attr_val[1]
                    real_port = struct.unpack("!H", attr_val[2:4])[0]
                    if family == 0x01:  # IPv4
                        real_ip = socket.inet_ntoa(attr_val[4:8])
                        return (real_ip, real_port)

                # Allineamento a 4 byte per attributi successivi
                padded_len = (attr_len + 3) & ~3
                offset += 4 + padded_len

        finally:
            sock.close()

        return None


def detect_nat_info(local_service_port: int = 8000) -> Dict[str, Any]:
    """Restituisce informazioni complete sullo stato di rete e NAT Traversal."""
    from core.ssl_manager import get_lan_ip

    lan_ip = get_lan_ip()
    client = STUNClient(timeout=2.0)
    public_res = client.get_public_address(local_port=0)

    if public_res:
        wan_ip, reflexive_port = public_res
        is_behind_nat = (lan_ip != wan_ip) and not wan_ip.startswith("127.")
    else:
        wan_ip = None
        reflexive_port = None
        is_behind_nat = False

    return {
        "lan_ip": lan_ip,
        "local_port": local_service_port,
        "wan_ip": wan_ip,
        "reflexive_port": reflexive_port,
        "is_behind_nat": is_behind_nat,
        "stun_available": wan_ip is not None,
    }
