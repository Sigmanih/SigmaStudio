# ==============================================================================
# tests/test_civitai_red.py — Test Supporto Civitai.red e Civitai.com
# ==============================================================================
import pytest

from core.modules.sigma_creative_lab import civitai_import as C
from core.modules.sigma_creative_lab.model_downloader import custom_asset


def test_parse_link_civitai_red_models():
    """Verifica che i link di modelli da civitai.red vengano riconosciuti correttamente."""
    link = C.parse_link("https://civitai.red/models/123456")
    assert link["kind"] == "model"
    assert link["id"] == 123456
    assert link["domain"] == "civitai.red"


def test_parse_link_civitai_red_version():
    """Verifica link con modelVersionId da civitai.red."""
    link = C.parse_link("https://civitai.red/models/123456?modelVersionId=7890")
    assert link["kind"] == "version"
    assert link["id"] == 7890
    assert link["domain"] == "civitai.red"

    link_direct_ver = C.parse_link("https://civitai.red/model-versions/7890")
    assert link_direct_ver["kind"] == "version"
    assert link_direct_ver["id"] == 7890
    assert link_direct_ver["domain"] == "civitai.red"


def test_parse_link_civitai_red_images():
    """Verifica link immagine da civitai.red."""
    link = C.parse_link("https://civitai.red/images/54321")
    assert link["kind"] == "image"
    assert link["id"] == 54321
    assert link["domain"] == "civitai.red"


def test_parse_link_civitai_com_backward_compatible():
    """Verifica che i link tradizionali civitai.com continuino a funzionare."""
    link = C.parse_link("https://civitai.com/models/123456")
    assert link["kind"] == "model"
    assert link["id"] == 123456
    assert link["domain"] == "civitai.com"


def test_model_downloader_allows_civitai_red():
    """Verifica che model_downloader consenta URL di download da civitai.red."""
    asset = custom_asset({
        "url": "https://civitai.red/api/download/models/12345?token=abc",
        "filename": "model_test.safetensors",
        "folder": "loras",
        "size_gb": 0.15,
    })
    assert asset.url.startswith("https://civitai.red/")
    assert asset.filename == "model_test.safetensors"
    assert asset.folder == "loras"


def test_invalid_domains_rejected():
    """Verifica che domini non autorizzati siano respinti."""
    with pytest.raises(ValueError, match="non e' un link Civitai"):
        C.parse_link("https://malicious-site.org/models/123")
