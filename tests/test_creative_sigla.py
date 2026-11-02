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


def test_intro_corta_e_video_centrale_conservato(tmp_path, monkeypatch):
    import shutil
    import subprocess
    from core.modules.sigma_creative_lab.video import postprocess
    from core.modules.sigma_creative_lab.video.production import ffmpeg_bin, probe

    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg non installato')
    ff = ffmpeg_bin()
    monkeypatch.setattr(postprocess, 'video_encoder_args', lambda *args: ['-c:v', 'libx264', '-crf', '18'])
    def run(args):
        return subprocess.run([ff, '-v', 'error', '-y', *args], capture_output=True, check=True)
    for name, duration in [('intro', 4), ('outro', 5)]:
        run(['-f', 'lavfi', '-i', f'color=c=black:s=64x48:r=24:d={duration}', '-c:v', 'libx264', str(tmp_path / f'{name}.mp4')])
        voice_duration = duration - 0.25 if name == 'intro' else duration
        run(['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', str(voice_duration), str(tmp_path / f'{name}_en.wav')])
    subtitle = tmp_path / 'sub.srt'
    subtitle.write_text('1\n00:00:00,500 --> 00:00:01,500\nFilm\n', encoding='utf-8')
    source, output = tmp_path / 'film.mp4', tmp_path / 'finale.mp4'
    run(['-f', 'lavfi', '-i', 'color=c=blue:s=64x48:r=24:d=2', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
         '-i', str(subtitle), '-map', '0:v', '-map', '1:a', '-map', '2:s', '-t', '2', '-c:v', 'libx264',
         '-c:a', 'aac', '-c:s', 'mov_text', str(source)])
    import hashlib
    from core.store import JsonStore
    JsonStore(tmp_path / 'sigla_template.json').save({'layout': 'sigma-logo-title-v1',
        **{kind + '_sha256': hashlib.sha256((tmp_path / f'{kind}.mp4').read_bytes()).hexdigest() for kind in ('intro', 'outro')}})
    result = audio_export.add_sigla_to_master(source, output, tmp_path, ['en'], film_title='Film', film_year='1926')
    assert result['identity_title'] == 'Film'
    assert result['film_video_copied']
    assert abs(probe(output)['duration'] - 11) < 0.1
    assert abs(probe(output)['audio_duration'] - 11) < 0.1
    hashes = [run(['-ss', str(t), '-i', str(path), '-map', '0:v:0', '-frames:v', '1', '-f', 'hash', '-hash', 'sha256', '-']).stdout
              for path, t in [(source, 0), (output, 4)]]
    assert hashes[0] == hashes[1]
