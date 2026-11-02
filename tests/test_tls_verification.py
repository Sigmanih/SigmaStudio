"""Una CA non valida deve fallire senza un secondo tentativo non verificato."""
import ssl
import urllib.error

import pytest

from core.system import net_utils


def test_import_non_disabilita_tls():
    assert ssl._create_default_https_context is not ssl._create_unverified_context
    context = net_utils.get_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_certificato_non_valido_non_viene_aggirato(monkeypatch):
    attempts = []

    def fail(*args, **kwargs):
        attempts.append(kwargs["context"])
        raise urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))

    monkeypatch.setattr(net_utils.urllib.request, "urlopen", fail)
    with pytest.raises(urllib.error.URLError):
        net_utils.safe_urlopen("https://esempio.invalid")
    assert len(attempts) == 1
    assert attempts[0].verify_mode == ssl.CERT_REQUIRED
