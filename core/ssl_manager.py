# ==============================================================================
# core/ssl_manager.py — Gestione e Generazione Certificati SSL/TLS per HTTPS Locale
# ==============================================================================
"""PKI locale a due livelli per HTTPS su localhost e LAN.

Un certificato autofirmato viene sempre rifiutato dal browser con
ERR_CERT_AUTHORITY_INVALID, perche' nessuno lo ha firmato. Qui viene invece
generata una piccola Certificate Authority locale ("Sigma Studio Local CA"),
che firma il certificato del server. Installando UNA sola volta la CA nel
trust store del sistema (o del telefono), tutti i certificati emessi in
seguito diventano attendibili senza altri avvisi.
"""
from __future__ import annotations

import datetime
import ipaddress
import platform
import socket
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from core.logger import get_logger
from core.paths import certs_dir

log = get_logger(__name__)

CA_CERT_NAME = "sigma-ca.pem"
CA_KEY_NAME = "sigma-ca-key.pem"
SERVER_CERT_NAME = "cert.pem"
SERVER_KEY_NAME = "key.pem"

CA_VALID_DAYS = 3650          # La CA locale dura 10 anni: si installa una volta sola.
LEAF_VALID_DAYS = 397         # Limite accettato da Chrome/Safari/iOS per i certificati server.
RENEW_BEFORE_DAYS = 30        # Rigenerazione automatica prima della scadenza.

CA_COMMON_NAME = "Sigma Studio Local CA"


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


def ca_cert_path() -> Path:
    """Percorso del certificato pubblico della CA locale (da installare sui dispositivi)."""
    return certs_dir() / CA_CERT_NAME


def ca_key_path() -> Path:
    """Percorso della chiave privata della CA locale (non esce mai da questa macchina)."""
    return certs_dir() / CA_KEY_NAME


def server_cert_path() -> Path:
    """Percorso del certificato del server usato da uvicorn."""
    return certs_dir() / SERVER_CERT_NAME


def server_key_path() -> Path:
    """Percorso della chiave privata del server usata da uvicorn."""
    return certs_dir() / SERVER_KEY_NAME


def _build_san_list(extra_hosts: Optional[list[str]] = None):
    """Costruisce i Subject Alternative Names per localhost, hostname e tutti gli IP locali."""
    from cryptography import x509

    dns_names = ["localhost", "sigma.local", "sigmastudio.local"]
    try:
        hostname = socket.gethostname()
        if hostname:
            dns_names.append(hostname)
            dns_names.append(f"{hostname}.local")
    except Exception:
        pass

    san_list: list[x509.GeneralName] = [
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv6Address("::1")),
    ]

    seen_ips = {"127.0.0.1", "::1"}
    for ip_str in get_all_local_ips():
        if ip_str in seen_ips:
            continue
        seen_ips.add(ip_str)
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            dns_names.append(ip_str)

    if extra_hosts:
        for host in extra_hosts:
            host = str(host).strip()
            if not host or host in seen_ips or host in dns_names:
                continue
            try:
                san_list.append(x509.IPAddress(ipaddress.ip_address(host)))
                seen_ips.add(host)
            except ValueError:
                dns_names.append(host)

    seen_dns = set()
    for name in dns_names:
        low = name.lower()
        if low in seen_dns:
            continue
        seen_dns.add(low)
        san_list.append(x509.DNSName(name))

    return san_list


def _write_pem(path: Path, data: bytes, private: bool = False) -> None:
    """Scrive un file PEM creando la cartella e restringendo i permessi delle chiavi private."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if private:
        try:
            path.chmod(0o600)
        except Exception:
            pass


def generate_local_ca(cert_path: Optional[Path] = None, key_path: Optional[Path] = None) -> bool:
    """Genera la Certificate Authority locale che firmera' i certificati del server."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        cert_path = cert_path or ca_cert_path()
        key_path = key_path or ca_key_path()

        log.info("[SSL] Generazione Certificate Authority locale Sigma Studio...")
        ca_key = rsa.generate_private_key(
            public_exponent=65537, key_size=4096, backend=default_backend()
        )

        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sigma Studio"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Local Development CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, CA_COMMON_NAME),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=CA_VALID_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False, key_cert_sign=True,
                    crl_sign=True, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
            .sign(private_key=ca_key, algorithm=hashes.SHA256(), backend=default_backend())
        )

        _write_pem(key_path, ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ), private=True)
        _write_pem(cert_path, ca_cert.public_bytes(serialization.Encoding.PEM))

        log.info("[SSL] CA locale creata in %s (installala una volta sola nel sistema).", cert_path)
        return True

    except Exception as exc:
        log.error("[SSL] Errore durante la generazione della CA locale: %s", exc)
        return False


def _load_ca():
    """Carica certificato e chiave della CA locale, oppure (None, None) se assenti o illeggibili."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        cp, kp = ca_cert_path(), ca_key_path()
        if not (cp.exists() and kp.exists()):
            return None, None
        cert = x509.load_pem_x509_certificate(cp.read_bytes())
        key = serialization.load_pem_private_key(kp.read_bytes(), password=None)
        if cert.not_valid_after_utc <= datetime.datetime.now(datetime.timezone.utc):
            log.warning("[SSL] La CA locale e' scaduta: verra' rigenerata.")
            return None, None
        return cert, key
    except Exception as exc:
        log.warning("[SSL] CA locale non caricabile (%s): verra' rigenerata.", exc)
        return None, None


def ensure_local_ca() -> Tuple[Optional[Path], Optional[Path]]:
    """Garantisce l'esistenza della CA locale, generandola se mancante o scaduta."""
    cert, _key = _load_ca()
    if cert is not None:
        return ca_cert_path(), ca_key_path()
    if generate_local_ca():
        return ca_cert_path(), ca_key_path()
    return None, None


def generate_server_cert(
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
    extra_hosts: Optional[list[str]] = None,
    valid_days: int = LEAF_VALID_DAYS,
) -> bool:
    """Genera il certificato del server firmato dalla CA locale, valido per localhost e LAN."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

        cert_path = cert_path or server_cert_path()
        key_path = key_path or server_key_path()

        ca_cert, ca_key = _load_ca()
        if ca_cert is None or ca_key is None:
            if not generate_local_ca():
                return False
            ca_cert, ca_key = _load_ca()
        if ca_cert is None or ca_key is None:
            return False

        log.info("[SSL] Generazione certificato server firmato dalla CA locale...")
        key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sigma Studio"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=valid_days))
            .add_extension(x509.SubjectAlternativeName(_build_san_list(extra_hosts)), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, content_commitment=False, key_encipherment=True,
                    data_encipherment=False, key_agreement=False, key_cert_sign=False,
                    crl_sign=False, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=False,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
                critical=False,
            )
            .sign(private_key=ca_key, algorithm=hashes.SHA256(), backend=default_backend())
        )

        _write_pem(key_path, key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ), private=True)
        # Il file contiene anche la CA: alcuni client (curl, requests) richiedono la catena completa.
        _write_pem(
            cert_path,
            cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM),
        )

        log.info("[SSL] Certificato server generato con successo in %s", cert_path)
        return True

    except Exception as exc:
        log.error("[SSL] Errore durante la generazione del certificato server: %s", exc)
        return False


# Alias storico mantenuto per compatibilita' con il codice e i test esistenti.
def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    extra_hosts: Optional[list[str]] = None,
    valid_days: int = LEAF_VALID_DAYS,
) -> bool:
    """Compatibilita': genera il certificato server tramite la CA locale."""
    return generate_server_cert(cert_path, key_path, extra_hosts, valid_days)


def _server_cert_is_usable(cert_path: Path) -> bool:
    """Verifica che il certificato sia emesso dalla CA attuale, non scaduto e con i SAN aggiornati."""
    try:
        from cryptography import x509

        ca_cert, _ = _load_ca()
        if ca_cert is None:
            return False

        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())

        # Emesso dalla CA locale corrente? Un vecchio certificato autofirmato fallisce qui.
        if cert.issuer != ca_cert.subject:
            log.info("[SSL] Certificato non emesso dalla CA locale: rigenerazione.")
            return False

        now = datetime.datetime.now(datetime.timezone.utc)
        if cert.not_valid_after_utc <= now + datetime.timedelta(days=RENEW_BEFORE_DAYS):
            log.info("[SSL] Certificato in scadenza: rinnovo automatico.")
            return False

        san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san_ips = {str(n.value) for n in san_ext.value if isinstance(n, x509.IPAddress)}
        if not set(get_all_local_ips()).issubset(san_ips):
            log.info("[SSL] Nuovo indirizzo IP locale rilevato: rigenerazione del certificato.")
            return False

        return True
    except Exception:
        return False


def ensure_ssl_certificates(
    custom_certfile: Optional[str] = None,
    custom_keyfile: Optional[str] = None
) -> Tuple[Optional[Path], Optional[Path]]:
    """Garantisce certificato e chiave SSL validi, rigenerandoli se mancanti, scaduti o con IP cambiato."""
    if custom_certfile and custom_keyfile:
        cp = Path(custom_certfile)
        kp = Path(custom_keyfile)
        if cp.exists() and kp.exists():
            return cp, kp

    default_cert = server_cert_path()
    default_key = server_key_path()

    if default_cert.exists() and default_key.exists() and _server_cert_is_usable(default_cert):
        return default_cert, default_key

    if generate_server_cert(default_cert, default_key) and default_cert.exists() and default_key.exists():
        return default_cert, default_key

    return None, None


def ca_fingerprint() -> Optional[str]:
    """Impronta SHA-1 della CA locale, nel formato usato dagli store di certificati."""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes

        cp = ca_cert_path()
        if not cp.exists():
            return None
        cert = x509.load_pem_x509_certificate(cp.read_bytes())
        return cert.fingerprint(hashes.SHA1()).hex().upper()
    except Exception:
        return None


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Esegue un comando di sistema senza aprire finestre di console su Windows."""
    kwargs: dict = {"capture_output": True, "text": True, "timeout": timeout}
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(cmd, **kwargs)


def is_ca_trusted() -> bool:
    """Verifica se la CA locale risulta gia' installata nel trust store del sistema."""
    fp = ca_fingerprint()
    if not fp:
        return False
    try:
        system = platform.system()
        if system == "Windows":
            for args in (["certutil", "-user", "-store", "ROOT", fp],
                         ["certutil", "-store", "ROOT", fp]):
                try:
                    if _run(args).returncode == 0:
                        return True
                except Exception:
                    continue
            return False
        if system == "Darwin":
            return _run(["security", "verify-cert", "-c", str(ca_cert_path())]).returncode == 0
        # Linux: la CA e' considerata installata se presente fra le ancore di sistema.
        for anchor in (Path("/usr/local/share/ca-certificates/sigma-studio-ca.crt"),
                       Path("/etc/pki/ca-trust/source/anchors/sigma-studio-ca.crt")):
            if anchor.exists():
                return True
        return False
    except Exception:
        return False


def install_ca_into_trust_store() -> Tuple[bool, str]:
    """Installa la CA locale nel trust store dell'utente/sistema. Richiede conferma o privilegi."""
    cp, _ = ensure_local_ca()
    if not cp or not cp.exists():
        return False, "CA locale non disponibile: impossibile procedere."

    system = platform.system()
    try:
        if system == "Windows":
            # Lo store ROOT dell'utente corrente basta a Chrome ed Edge e non richiede privilegi admin.
            res = _run(["certutil", "-user", "-addstore", "-f", "ROOT", str(cp)], timeout=120)
            if res.returncode == 0:
                return True, "CA installata fra le Autorita' di certificazione radice attendibili dell'utente."
            return False, (res.stderr or res.stdout or "certutil ha restituito un errore").strip()

        if system == "Darwin":
            res = _run([
                "security", "add-trusted-cert", "-d", "-r", "trustRoot",
                "-k", str(Path.home() / "Library/Keychains/login.keychain-db"), str(cp)
            ], timeout=120)
            if res.returncode == 0:
                return True, "CA installata nel portachiavi di login."
            return False, (res.stderr or res.stdout or "security ha restituito un errore").strip()

        # Linux: copia fra le ancore di sistema e aggiorna il bundle (richiede sudo).
        target_dir = Path("/usr/local/share/ca-certificates")
        update_cmd = ["sudo", "update-ca-certificates"]
        if not target_dir.exists():
            target_dir = Path("/etc/pki/ca-trust/source/anchors")
            update_cmd = ["sudo", "update-ca-trust", "extract"]
        if not target_dir.exists():
            return False, "Trust store di sistema non individuato su questa distribuzione."
        target = target_dir / "sigma-studio-ca.crt"
        res = _run(["sudo", "cp", str(cp), str(target)], timeout=120)
        if res.returncode != 0:
            return False, (res.stderr or "copia nella cartella delle ancore non riuscita").strip()
        res = _run(update_cmd, timeout=120)
        if res.returncode == 0:
            return True, f"CA installata in {target} e trust store aggiornato."
        return False, (res.stderr or "aggiornamento del trust store non riuscito").strip()

    except FileNotFoundError as exc:
        return False, f"Strumento di sistema non trovato: {exc}"
    except Exception as exc:
        return False, f"Installazione della CA non riuscita: {exc}"


def ssl_status() -> dict:
    """Riepilogo dello stato TLS per le API e l'interfaccia."""
    cp = ca_cert_path()
    return {
        "ca_path": str(cp),
        "ca_exists": cp.exists(),
        "ca_fingerprint": ca_fingerprint(),
        "ca_trusted": is_ca_trusted(),
        "cert_exists": server_cert_path().exists() and server_key_path().exists(),
        "cert_path": str(server_cert_path()),
        "ca_download_url": "/ssl/ca.crt",
        "platform": platform.system(),
    }
