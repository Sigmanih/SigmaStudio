# ==============================================================================
# core/ssl_manager.py — Gestione e Generazione Certificati SSL/TLS per HTTPS Locale
# ==============================================================================
from __future__ import annotations

import datetime
import ipaddress
import socket
from pathlib import Path
from typing import Optional, Tuple

from core.logger import get_logger
from core.paths import certs_dir

log = get_logger(__name__)


def get_lan_ip() -> str:
    """Recupera l'indirizzo IPv4 locale principale per accesso da LAN / Wi-Fi."""
    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Non invia traffico reale, interroga la tabella di routing del sistema operativo
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return lan_ip


def get_all_local_ips() -> list[str]:
    """Restituisce tutti gli IP locali della macchina noti."""
    ips = {"127.0.0.1", get_lan_ip()}
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(list(ips))


def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    extra_hosts: Optional[list[str]] = None,
    valid_days: int = 3650
) -> bool:
    """Genera una chiave privata e un certificato X.509 autofirmato valido per localhost e LAN."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        cert_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Genera chiave privata RSA 2048-bit
        log.info("[SSL] Generazione nuova chiave privata RSA per HTTPS...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # 2. Costruisci Subject e Issuer
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Italy"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Sigma"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sigma Studio Local"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Sigma Studio LAN Server"),
        ])

        # 3. Costruisci i Subject Alternative Names (SAN)
        san_list: list[x509.GeneralName] = [
            x509.DNSName("localhost"),
            x509.DNSName("sigma.local"),
            x509.DNSName("sigmastudio.local"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            x509.IPAddress(ipaddress.IPv6Address("::1")),
        ]

        # Aggiungi tutti gli IP della LAN locale
        for ip_str in get_all_local_ips():
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                san_list.append(x509.IPAddress(ip_obj))
            except ValueError:
                san_list.append(x509.DNSName(ip_str))

        if extra_hosts:
            for host in extra_hosts:
                try:
                    ip_obj = ipaddress.ip_address(host)
                    san_list.append(x509.IPAddress(ip_obj))
                except ValueError:
                    san_list.append(x509.DNSName(host))

        # 4. Crea il certificato
        now = datetime.datetime.now(datetime.timezone.utc)
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=valid_days))
            .add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
        )

        certificate = builder.sign(
            private_key=private_key,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )

        # 5. Salva i file .pem
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(cert_path, "wb") as f:
            f.write(certificate.public_bytes(serialization.Encoding.PEM))

        log.info("[SSL] Certificato SSL generato con successo in %s", cert_path)
        return True

    except Exception as exc:
        log.error("[SSL] Errore durante la generazione del certificato SSL: %s", exc)
        return False


def ensure_ssl_certificates(
    custom_certfile: Optional[str] = None,
    custom_keyfile: Optional[str] = None
) -> Tuple[Optional[Path], Optional[Path]]:
    """Garantisce la presenza di certificato e chiave SSL, generandoli se mancanti."""
    if custom_certfile and custom_keyfile:
        cp = Path(custom_certfile)
        kp = Path(custom_keyfile)
        if cp.exists() and kp.exists():
            return cp, kp

    target_dir = certs_dir()
    default_cert = target_dir / "cert.pem"
    default_key = target_dir / "key.pem"

    if default_cert.exists() and default_key.exists():
        return default_cert, default_key

    # Genera automaticamente
    ok = generate_self_signed_cert(default_cert, default_key)
    if ok and default_cert.exists() and default_key.exists():
        return default_cert, default_key

    return None, None
