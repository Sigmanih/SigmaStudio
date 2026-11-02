"""Controlli sugli asset localizzati della sigla per il restauro multilingua."""

import pytest

from core.modules.sigma_creative_lab.video import audio_export


def test_validazione_sigla_rileva_video_e_voci_per_lingua(tmp_path, monkeypatch):
    (tmp_path / "intro.mp4").write_bytes(b"intro")
    (tmp_path / "outro.mp4").write_bytes(b"outro")
    for name in ("intro_en.wav", "outro_en.wav", "intro_it.wav", "outro_it.wav"):
        (tmp_path / name).write_bytes(b"audio")

    def fake_probe(path):
        path = path if hasattr(path, "name") else tmp_path / str(path)
        if path.suffix == ".mp4":
            return {"width": 1280, "height": 720,
                    "duration": 6.0 if path.name == "intro.mp4" else 4.0}
        return {"has_audio": True, "audio_duration": 6.0 if path.name.startswith("intro_") else 4.0}

    monkeypatch.setattr("core.modules.sigma_creative_lab.video.production.probe", fake_probe)
    assets = audio_export.validate_sigla_assets(tmp_path, ["en", "it"])

    assert assets["intro_duration"] == 6.0
    assert assets["outro_duration"] == 4.0
    assert assets["voices"]["it"][0].name == "intro_it.wav"


def test_validazione_sigla_ferma_la_pipeline_se_manca_una_voce(tmp_path):
    (tmp_path / "intro.mp4").write_bytes(b"intro")
    (tmp_path / "outro.mp4").write_bytes(b"outro")

    with pytest.raises(ValueError, match="Asset della sigla mancanti"):
        audio_export.validate_sigla_assets(tmp_path, ["en"])


def test_logo_sigla_viene_ritagliato_con_maschera_circolare(tmp_path):
    from PIL import Image
    frame = tmp_path / "logo_frame.png"
    Image.new("RGB", (320, 240), (220, 30, 90)).save(frame)

    logo, button = audio_export._sigla_overlays(640, 480, tmp_path, "it", frame)

    assert logo.is_file() and button.is_file()
    mask = Image.open(logo).getchannel("A")
    assert mask.getpixel((0, 0)) == 0
    assert mask.getpixel((mask.width // 2, mask.height // 2)) == 255
    assert Image.open(button).getbbox() is not None
