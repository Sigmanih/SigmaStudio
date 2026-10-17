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


class UPnPClient:
    """Client UPnP IGD (Internet Gateway Device) leggero in puro Python per auto-port forwarding su router."""

    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout
        self._control_url: Optional[str] = None
        self._service_type: Optional[str] = None

    def discover_control_url(self) -> Optional[Tuple[str, str]]:
        """Rileva l'URL di controllo del router tramite SSDP su 239.255.255.250:1900."""
        if self._control_url and self._service_type:
            return (self._control_url, self._service_type)

        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 2\r\n"
            "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n"
            "\r\n"
        ).encode("utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.sendto(msg, ("239.255.255.250", 1900))
            start_time = time.time()
            location = None
            while time.time() - start_time < self.timeout:
                try:
                    data, _ = sock.recvfrom(2048)
                    text = data.decode("utf-8", errors="ignore")
                    for line in text.splitlines():
                        if line.lower().startswith("location:"):
                            location = line.split(":", 1)[1].strip()
                            break
                    if location:
                        break
                except socket.timeout:
                    break

            if not location:
                return None

            import urllib.request
            import urllib.parse
            import xml.etree.ElementTree as ET

            req = urllib.request.Request(location, headers={"User-Agent": "SigmaStudio-P2P"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                xml_content = resp.read()

            root = ET.fromstring(xml_content)
            for service in root.iter():
                if "service" in service.tag:
                    st_elem = None
                    ctrl_elem = None
                    for child in service:
                        tag_lower = child.tag.lower()
                        if "servicetype" in tag_lower:
                            st_elem = child
                        elif "controlurl" in tag_lower:
                            ctrl_elem = child
                    if st_elem is not None and ctrl_elem is not None:
                        st_text = st_elem.text or ""
                        if "WANIPConnection" in st_text or "WANPPPConnection" in st_text:
                            ctrl_url = ctrl_elem.text or ""
                            full_url = urllib.parse.urljoin(location, ctrl_url)
                            self._control_url = full_url
                            self._service_type = st_text
                            return (full_url, st_text)

        except Exception as e:
            logger.debug("[UPnP] Errore durante la scoperta SSDP del router: %s", e)
        finally:
            sock.close()

        return None

    def add_port_mapping(
        self,
        internal_port: int,
        external_port: int,
        lan_ip: str,
        protocol: str = "TCP",
        description: str = "Sigma Studio P2P",
    ) -> bool:
        """Invia richiesta SOAP per mappare la porta esterna sull'IP LAN locale."""
        endpoint = self.discover_control_url()
        if not endpoint:
            return False

        control_url, service_type = endpoint
        import urllib.request

        soap_body = f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:AddPortMapping xmlns:u="{service_type}">
      <NewRemoteHost></NewRemoteHost>
      <NewExternalPort>{external_port}</NewExternalPort>
      <NewProtocol>{protocol.upper()}</NewProtocol>
      <NewInternalPort>{internal_port}</NewInternalPort>
      <NewInternalClient>{lan_ip}</NewInternalClient>
      <NewEnabled>1</NewEnabled>
      <NewPortMappingDescription>{description}</NewPortMappingDescription>
      <NewLeaseDuration>0</NewLeaseDuration>
    </u:AddPortMapping>
  </s:Body>
</s:Envelope>"""

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service_type}#AddPortMapping"',
            "User-Agent": "SigmaStudio-P2P",
        }

        try:
            req = urllib.request.Request(control_url, data=soap_body.encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    logger.info("[UPnP] Porta WAN %d mappata con successo su %s:%d (%s)", external_port, lan_ip, internal_port, protocol)
                    return True
        except Exception as e:
            logger.debug("[UPnP] Mappatura porta fallita: %s", e)

        return False

    def delete_port_mapping(self, external_port: int, protocol: str = "TCP") -> bool:
        """Rimuove la mappatura della porta dal router."""
        endpoint = self.discover_control_url()
        if not endpoint:
            return False

        control_url, service_type = endpoint
        import urllib.request

        soap_body = f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:DeletePortMapping xmlns:u="{service_type}">
      <NewRemoteHost></NewRemoteHost>
      <NewExternalPort>{external_port}</NewExternalPort>
      <NewProtocol>{protocol.upper()}</NewProtocol>
    </u:DeletePortMapping>
  </s:Body>
</s:Envelope>"""

        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service_type}#DeletePortMapping"',
            "User-Agent": "SigmaStudio-P2P",
        }

        try:
            req = urllib.request.Request(control_url, data=soap_body.encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status == 200
        except Exception:
            return False


def forward_port_upnp(
    internal_port: int = 8000,
    external_port: Optional[int] = None,
    protocol: str = "TCP"
) -> Dict[str, Any]:
    """Tenta automaticamente la mappatura della porta sul router UPnP IGD."""
    from core.ssl_manager import get_lan_ip
    lan_ip = get_lan_ip()
    ext_p = external_port or internal_port
    upnp = UPnPClient(timeout=2.0)
    success = upnp.add_port_mapping(internal_port, ext_p, lan_ip, protocol=protocol)
    return {
        "success": success,
        "internal_port": internal_port,
        "external_port": ext_p if success else None,
        "lan_ip": lan_ip,
        "protocol": protocol,
    }


def delete_port_upnp(external_port: int = 8000, protocol: str = "TCP") -> bool:
    """Rimuove la mappatura UPnP della porta esterna."""
    upnp = UPnPClient(timeout=2.0)
    return upnp.delete_port_mapping(external_port, protocol=protocol)


def detect_nat_info(local_service_port: int = 8000) -> Dict[str, Any]:
    """Restituisce informazioni complete sullo stato di rete, NAT Traversal e UPnP."""
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

    # Prova rapida presenza UPnP router
    upnp = UPnPClient(timeout=1.5)
    upnp_endpoint = upnp.discover_control_url()

    return {
        "lan_ip": lan_ip,
        "local_port": local_service_port,
        "wan_ip": wan_ip,
        "reflexive_port": reflexive_port,
        "is_behind_nat": is_behind_nat,
        "stun_available": wan_ip is not None,
        "upnp_available": upnp_endpoint is not None,
        "public_reachability": "direct" if not is_behind_nat else ("upnp_ready" if upnp_endpoint else "relay_required"),
    }
