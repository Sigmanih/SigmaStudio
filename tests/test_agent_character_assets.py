"""Le revisioni degli asset devono arrivare alla Home senza GLB obsoleti in cache."""
import os

import pytest

from core.handlers.data_handler import _parse_manifesto_file


@pytest.fixture
def role_files(tmp_path, monkeypatch):
    import core.manifests_catalog as catalog
    monkeypatch.setattr(catalog, "get_catalog", lambda: [])
    manifesto = tmp_path / "test_cyborg.md"
    manifesto.write_text('FROM sigma\n# Image: /ruoli/test_cyborg/immagine.png?v=4\nSYSTEM """Assistente."""', encoding="utf-8")
    assets = tmp_path / manifesto.stem
    assets.mkdir()
    return manifesto, assets


def test_missing_character_has_no_url(role_files):
    manifesto, _ = role_files
    result = _parse_manifesto_file(str(manifesto), manifesto.name, {}, {})
    assert result["character3d"] is None
    assert result["image"] == "/ruoli/test_cyborg/immagine.png?v=4"


def test_regeneration_invalidates_character_cache(role_files):
    manifesto, assets = role_files
    character = assets / "personaggio.glb"
    character.write_bytes(b"glTF")
    first = _parse_manifesto_file(str(manifesto), manifesto.name, {}, {})["character3d"]["url"]
    modified = character.stat().st_mtime_ns + 2_000_000_000
    os.utime(character, ns=(modified, modified))
    second = _parse_manifesto_file(str(manifesto), manifesto.name, {}, {})["character3d"]["url"]
    assert first != second
    assert second.startswith("/ruoli/test_cyborg/personaggio.glb?v=")
