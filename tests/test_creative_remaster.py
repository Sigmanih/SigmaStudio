"""Prove rapide per cadenza, segmentazione e riparazione dei graffi verticali."""

import subprocess
import json

import numpy as np

from core.modules.sigma_creative_lab.video import remaster as M
from core.modules.sigma_creative_lab.video.clean_worker import Duster
from core.modules.sigma_creative_lab.video.production import ffmpeg_bin


def _write_3_2(path):
    width, height = 96, 72
    frames = []
    for i in range(72):
        a = np.full((height, width), 40 + i % 170, dtype=np.uint8)
        a[:, :i % width] = 220
        b = np.roll(a, 3, axis=1)
        c = np.roll(a, 7, axis=1)
        frames.extend((a, a, b, b, c))
    payload = b"".join(frame.tobytes() for frame in frames)
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s",
                    f"{width}x{height}", "-framerate", "30", "-i", "-", "-c:v", "libx264", "-qp", "0",
                    "-pix_fmt", "yuv420p", str(path)], input=payload, check=True)


def test_cadenza_3_2_rilevata_su_ciclo_non_uniforme(tmp_path):
    source = tmp_path / "telecine.mp4"
    _write_3_2(source)
    profile = M.cadence_profile(source)
    assert profile["cycle"] == 5
    assert profile["fps"] == 18
    assert len(profile["drop_phases"]) == 2


def test_espressione_ffmpeg_scarta_solo_le_due_fasi_duplicate():
    expr = M._select_expr({"drop_phases": [1, 3]})
    assert expr == r"not(eq(mod(n\,5)\,1)+eq(mod(n\,5)\,3))"


def test_segmenti_non_oltrepassano_i_tagli():
    assert M._segments([0, 50, 120], 36) == [(0, 36), (36, 50), (50, 86), (86, 120)]


def test_checkpoint_senza_identita_non_riutilizza_un_altro_film(tmp_path, monkeypatch):
    source = tmp_path / "film.mp4"
    source.write_bytes(b"sorgente")
    legacy = tmp_path / "remaster_legacy"
    legacy.mkdir()
    monkeypatch.setattr(M, "_valid_video", lambda *args, **kwargs: {"duration": 10})
    chosen = M._checkpoint_dir(tmp_path, source, 1080, {"duration": 10})
    assert chosen != legacy
    assert (chosen / "checkpoint.json").is_file()


def test_checkpoint_non_mescola_risoluzioni_diverse(tmp_path, monkeypatch):
    source = tmp_path / "film.mp4"
    source.write_bytes(b"sorgente")
    monkeypatch.setattr(M, "_valid_video", lambda *args, **kwargs: {"duration": 10})
    first = M._checkpoint_dir(tmp_path, source, 1080, {"duration": 10})
    second = M._checkpoint_dir(tmp_path, source, 2160, {"duration": 10})
    assert first != second
    assert M._checkpoint_dir(tmp_path, source, 1080, {"duration": 10}) == first


def test_checkpoint_parziale_si_ritrova_e_metadati_corrotti_si_conservano(tmp_path):
    source = tmp_path / "film.mp4"
    source.write_bytes(b"sorgente")
    first = M._checkpoint_dir(tmp_path, source, 1080, {"duration": 10})
    assert M._checkpoint_dir(tmp_path, source, 1080, {"duration": 10}) == first
    (first / "checkpoint.json").write_text("[]", encoding="utf-8")
    second = M._checkpoint_dir(tmp_path, source, 1080, {"duration": 10})
    assert second != first
    assert (first / "checkpoint.json").read_text() == "[]"


def test_master_con_audio_diverso_non_viene_riutilizzato(tmp_path, monkeypatch):
    import pytest
    source = tmp_path / "film.mp4"
    output = tmp_path / "master.mp4"
    source.write_bytes(b"sorgente")
    output.write_bytes(b"master")
    state = tmp_path / "checkpoint.json"
    state.write_text(json.dumps({"completed_stage": "master_video",
                                "final_recipe": M._final_recipe(output, None, True)}), encoding="utf-8")
    probe = lambda path: {"width": 320, "height": 240, "duration": 10, "frames": 240, "has_audio": True}
    monkeypatch.setattr(M, "_ff", lambda: (lambda: "ffmpeg", probe))
    monkeypatch.setattr(M, "_checkpoint_dir", lambda *args: tmp_path)
    monkeypatch.setattr(M, "cadence_profile", lambda *args: {"source_fps": 24})
    monkeypatch.setattr(M, "_valid_video", lambda path, *args, **kwargs: probe(path) if path == output else None)
    (tmp_path / "master_prima_dopo.jpg").write_bytes(b"anteprima")
    assert M.remaster_film(source, output, tmp_path, preserve_source_audio=True)["path"] == str(output)

    def interrupted(*args):
        raise RuntimeError("Il master deve essere ricostruito")

    monkeypatch.setattr(M, "normalize_cadence", interrupted)
    with pytest.raises(RuntimeError, match="deve essere ricostruito"):
        M.remaster_film(source, output, tmp_path, preserve_source_audio=False)


def test_risoluzione_finale_mantiene_il_rapporto_della_sorgente():
    assert M.output_dimensions(320, 240, 1080) == (1440, 1080)
    assert M.output_dimensions(320, 240, 1440) == (1920, 1440)
    assert M.output_dimensions(1920, 1080, 1080) == (1920, 1080)


def test_risoluzione_finale_rifiuta_valori_non_supportati():
    import pytest
    with pytest.raises(ValueError):
        M.output_dimensions(320, 240, 720)


def test_ripara_graffio_verticale_senza_modificare_immagine_pulita():
    clean = np.tile(np.linspace(50, 190, 96, dtype=np.uint8), (80, 1))
    restored, count = Duster._repair_vertical_scratches(clean)
    assert count == 0
    assert np.array_equal(restored, clean)

    damaged = clean.copy()
    damaged[:, 48] = 0
    restored, count = Duster._repair_vertical_scratches(damaged)
    assert count == 1
    assert np.abs(restored[:, 48].astype(np.int16) - clean[:, 48]).mean() < 2
