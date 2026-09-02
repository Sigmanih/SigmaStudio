"""Verifica la PKI locale: la CA firma il certificato server e il browser puo' fidarsene."""
import datetime
import ipaddress
import socket
import ssl
import threading
import unittest

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding

from core import ssl_manager


class TestLocalCA(unittest.TestCase):
    def setUp(self):
        cert, key = ssl_manager.ensure_ssl_certificates()
        self.assertIsNotNone(cert)
        self.assertIsNotNone(key)
        self.cert_path = cert
        self.key_path = key
        self.leaf = x509.load_pem_x509_certificate(cert.read_bytes())
        self.ca = x509.load_pem_x509_certificate(ssl_manager.ca_cert_path().read_bytes())

    def test_certificate_is_signed_by_local_ca(self):
        """Il certificato non deve essere autofirmato: e' l'origine di ERR_CERT_AUTHORITY_INVALID."""
        self.assertNotEqual(self.leaf.issuer, self.leaf.subject)
        self.assertEqual(self.leaf.issuer, self.ca.subject)
        # La firma deve validare contro la chiave pubblica della CA.
        self.ca.public_key().verify(
            self.leaf.signature,
            self.leaf.tbs_certificate_bytes,
            padding.PKCS1v15(),
            self.leaf.signature_hash_algorithm,
        )

    def test_ca_has_ca_constraints_and_leaf_does_not(self):
        ca_bc = self.ca.extensions.get_extension_for_class(x509.BasicConstraints).value
        leaf_bc = self.leaf.extensions.get_extension_for_class(x509.BasicConstraints).value
        self.assertTrue(ca_bc.ca)
        self.assertFalse(leaf_bc.ca)

        ca_ku = self.ca.extensions.get_extension_for_class(x509.KeyUsage).value
        self.assertTrue(ca_ku.key_cert_sign)

        eku = self.leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        self.assertIn(x509.oid.ExtendedKeyUsageOID.SERVER_AUTH, list(eku))

    def test_leaf_validity_within_browser_limit(self):
        """Chrome e iOS rifiutano i certificati server oltre 398 giorni di validita'."""
        span = self.leaf.not_valid_after_utc - self.leaf.not_valid_before_utc
        self.assertLessEqual(span, datetime.timedelta(days=399))
        self.assertGreater(self.leaf.not_valid_after_utc, datetime.datetime.now(datetime.timezone.utc))

    def test_san_covers_localhost_and_all_local_ips(self):
        san = self.leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns = {n.value.lower() for n in san if isinstance(n, x509.DNSName)}
        ips = {str(n.value) for n in san if isinstance(n, x509.IPAddress)}

        self.assertIn("localhost", dns)
        self.assertIn("127.0.0.1", ips)
        self.assertIn("::1", ips)
        for ip in ssl_manager.get_all_local_ips():
            self.assertIn(ip, ips, f"IP locale {ip} assente dai SAN: HTTPS da LAN fallirebbe")

    def test_self_signed_certificate_is_regenerated(self):
        """Un vecchio certificato autofirmato deve essere sostituito da uno firmato dalla CA."""
        self.assertTrue(ssl_manager._server_cert_is_usable(self.cert_path))

        # Simula il certificato autofirmato prodotto dalle versioni precedenti.
        foreign_ca = x509.load_pem_x509_certificate(self.cert_path.read_bytes())
        self.assertNotEqual(foreign_ca.issuer, foreign_ca.subject)

        original = self.cert_path.read_bytes()
        try:
            # Un certificato emesso da un'altra CA non deve essere considerato utilizzabile.
            other_dir = self.cert_path.parent
            self.assertTrue(other_dir.exists())
            self.cert_path.write_bytes(ssl_manager.ca_cert_path().read_bytes())
            self.assertFalse(ssl_manager._server_cert_is_usable(self.cert_path))
        finally:
            self.cert_path.write_bytes(original)

        # ensure_ssl_certificates ricostruisce un certificato valido dopo la corruzione.
        self.cert_path.write_bytes(b"non un certificato")
        cert, key = ssl_manager.ensure_ssl_certificates()
        self.assertIsNotNone(cert)
        rebuilt = x509.load_pem_x509_certificate(cert.read_bytes())
        self.assertEqual(rebuilt.issuer, self.ca.subject)

    def test_tls_handshake_succeeds_with_ca_as_trust_anchor(self):
        """Con la sola CA come ancora di fiducia l'handshake deve riuscire: e' cio' che fa il browser."""
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(str(self.cert_path), str(self.key_path))

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        handshake_errors: list[Exception] = []

        def _accept_once():
            try:
                conn, _ = listener.accept()
                tls = server_ctx.wrap_socket(conn, server_side=True)
                # Il client attende questo byte: cosi' l'handshake si conclude su
                # entrambi i lati prima della chiusura, senza corse su TLS 1.3.
                tls.sendall(b"ok")
                tls.close()
            except Exception as exc:  # pragma: no cover - riportato dal thread principale
                handshake_errors.append(exc)

        thread = threading.Thread(target=_accept_once, daemon=True)
        thread.start()
        try:
            client_ctx = ssl.create_default_context(cafile=str(ssl_manager.ca_cert_path()))
            with socket.create_connection(("127.0.0.1", port), timeout=10) as raw:
                with client_ctx.wrap_socket(raw, server_hostname="localhost") as tls:
                    self.assertIsNotNone(tls.getpeercert())
                    self.assertTrue(tls.version().startswith("TLS"))
                    self.assertEqual(tls.recv(2), b"ok")
        finally:
            thread.join(timeout=5)
            listener.close()

        self.assertEqual(handshake_errors, [])

    def test_tls_handshake_succeeds_on_lan_ip(self):
        """L'accesso da smartphone usa l'IP: il certificato deve validare anche senza hostname."""
        lan_ip = ssl_manager.get_lan_ip()
        if lan_ip == "127.0.0.1":
            self.skipTest("Nessun IP LAN disponibile su questa macchina")

        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(str(self.cert_path), str(self.key_path))

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def _accept_once():
            try:
                conn, _ = listener.accept()
                tls = server_ctx.wrap_socket(conn, server_side=True)
                tls.sendall(b"ok")
                tls.close()
            except Exception:
                pass

        thread = threading.Thread(target=_accept_once, daemon=True)
        thread.start()
        try:
            client_ctx = ssl.create_default_context(cafile=str(ssl_manager.ca_cert_path()))
            # server_hostname con un IP verifica il SAN iPAddress, come fa il browser.
            ipaddress.ip_address(lan_ip)
            with socket.create_connection(("127.0.0.1", port), timeout=10) as raw:
                with client_ctx.wrap_socket(raw, server_hostname=lan_ip) as tls:
                    self.assertIsNotNone(tls.getpeercert())
                    self.assertEqual(tls.recv(2), b"ok")
        finally:
            thread.join(timeout=5)
            listener.close()

    def test_ssl_status_reports_ca(self):
        status = ssl_manager.ssl_status()
        self.assertTrue(status["ca_exists"])
        self.assertTrue(status["cert_exists"])
        self.assertEqual(len(status["ca_fingerprint"]), 40)
        self.assertIsInstance(status["ca_trusted"], bool)


if __name__ == "__main__":
    unittest.main()
