"""La musica difettosa non deve entrare automaticamente nei film successivi."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from core.modules.sigma_creative_lab.video.score_plan import plan_cues, MAX_CUE_SECONDS
from core.modules.sigma_creative_lab.video.score_quality import inspect_samples, source_music_filter


def test_film_diversi_non_condividono_il_seed_musicale_predefinito():
    from core.modules.sigma_creative_lab.video.score_plan import production_seed
    assert production_seed("film-a", 1922) == production_seed("film-a", 1922)
    assert production_seed("film-a", 1922) != production_seed("film-b", 1922)
    assert production_seed("film-a", 1922) != production_seed("film-a", 1923)


def test_rileva_loop_esatto_ma_accetta_audio_in_evoluzione():
    rng = np.random.default_rng(42)
    phrase = rng.normal(0, 0.1, 4000).astype(np.float32)
    loop = inspect_samples(np.tile(phrase, 25), 50)
    assert "loop_prolungato" in loop["issues"]
    assert inspect_samples(rng.normal(0, 0.1, 100000), 50)["ok"]


def test_non_scambia_una_breve_ripresa_del_tema_per_un_loop_prolungato():
    phrase = np.random.default_rng(3).normal(0, 0.1, 4000)
    assert inspect_samples(np.tile(phrase, 10), 20)["ok"]


def test_rifiuta_silenzi_durata_insufficiente_e_campioni_non_validi():
    report = inspect_samples(np.zeros(20000), 20)
    assert set(report["issues"]) == {"durata_insufficiente", "silenzi_prolungati"}
    with pytest.raises(ValueError):
        inspect_samples(np.array([np.nan]), 1)


def test_piano_copre_il_film_senza_buchi_e_varia_orchestrazione():
    cues = plan_cues([{"start": 0, "end": 240, "tags": "warm, strings"},
                      {"start": 240, "end": 473, "tags": "suspense, woodwinds"}])
    assert cues[0]["start"] == 0 and cues[-1]["end"] == 473
    assert all(a["end"] == b["start"] for a, b in zip(cues, cues[1:]))
    assert all(c["end"] - c["start"] <= MAX_CUE_SECONDS for c in cues)
    assert len({c["arrangement"] for c in cues}) == len(cues)
    with pytest.raises(ValueError):
        plan_cues([{"start": 0, "end": 10, "tags": "a"}, {"start": 11, "end": 20, "tags": "b"}])


def test_atmosfere_copiate_richiedono_rilettura_o_revisione(tmp_path, monkeypatch):
    from core.modules.sigma_creative_lab.video import restoration as r
    monkeypatch.setattr(r, "strip_jpeg", lambda *a: b"frames")
    prompts = []
    def ask(image, prompt):
        prompts.append(prompt)
        return "industrial, mechanical, rhythmic, brass"
    moods = r.describe_moods(tmp_path / "video.mp4", [[0, 60], [60, 120], [120, 180]], [], ask)
    assert len(prompts) == 4 and moods[-1]["needs_review"]
    with pytest.raises(ValueError, match="verificare"):
        plan_cues(moods)
    moods[-1]["edited"] = True
    assert plan_cues(moods)


def test_originale_soppresso_solo_dove_la_musica_di_restauro_e_udibile(tmp_path):
    audio = tmp_path / "music.flac"
    audio.write_bytes(b"audio")
    clip = {"src": str(audio), "start": 2, "src_in": 1, "src_out": 5,
            "meta": {"restoration_score": "shot"}}
    track = {"kind": "music", "clips": [clip, {**clip, "start": 5}]}
    assert source_music_filter([track]) == "volume=0:enable='between(t,2.000000,9.000000)'"
    assert source_music_filter([{**track, "mute": True}]) == "anull"
    assert source_music_filter([{**track, "clips": [{**clip, "meta": {}}]}]) == "anull"
    audio.unlink()
    assert source_music_filter([track]) == "anull"


def test_compose_rigenera_audio_scartato_e_verifica_la_cache(tmp_path, monkeypatch):
    from core.modules.sigma_creative_lab.video import restoration as r
    from core.modules.sigma_creative_lab.video import score_quality as q
    seen = []

    class Backend:
        async def run(self, payload, **kwargs):
            seen.append(payload["workflow"]["enc"]["inputs"])
            return b"audio", "audio.flac"

    def normalize(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"normalized")
        return SimpleNamespace(returncode=0)

    reports = iter([
        {"ok": False, "issues": ["loop_prolungato"], "fingerprint": "bad"},
        {"ok": True, "issues": [], "fingerprint": "good"},
        {"ok": True, "issues": [], "fingerprint": "good"},
    ])
    monkeypatch.setattr(r, "_ff", lambda: (lambda: "ffmpeg", None))
    monkeypatch.setattr(r.subprocess, "run", normalize)
    monkeypatch.setattr(q, "inspect_audio", lambda *args: next(reports))
    moods = [{"start": 0, "end": 40, "tags": "lyrical strings"}]
    first = asyncio.run(r.compose(moods, tmp_path, 0, backend=Backend()))
    second = asyncio.run(r.compose(moods, tmp_path, 0, backend=Backend()))
    assert len(seen) == 2
    assert seen[0]["seed"] != seen[1]["seed"]
    assert first == second
    assert Path(first[0]["path"]).with_suffix(".quality.json").is_file()


def test_compose_non_promuove_tentativi_difettosi(tmp_path, monkeypatch):
    from core.modules.sigma_creative_lab.video import restoration as r
    from core.modules.sigma_creative_lab.video import score_quality as q

    class Backend:
        async def run(self, *args, **kwargs):
            return b"audio", "audio.flac"

    def normalize(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"audio")

    monkeypatch.setattr(r, "_ff", lambda: (lambda: "ffmpeg", None))
    monkeypatch.setattr(r.subprocess, "run", normalize)
    monkeypatch.setattr(q, "inspect_audio", lambda *a: {"ok": False, "issues": ["loop_prolungato"], "fingerprint": "bad"})
    with pytest.raises(RuntimeError, match="Musica non valida"):
        asyncio.run(r.compose([{"start": 0, "end": 40, "tags": "strings"}], tmp_path, 0, backend=Backend()))
    assert not list(tmp_path.glob("cue_*_*.flac"))


def test_mix_elimina_la_sovrapposizione_senza_togliere_audio_fuori_dalla_musica(tmp_path):
    import shutil
    import subprocess
    from core.modules.sigma_creative_lab.video.audio_export import _audio_mix
    from core.modules.sigma_creative_lab.video.production import ffmpeg_bin
    ff = ffmpeg_bin()
    if not shutil.which(ff):
        pytest.skip("ffmpeg non disponibile")
    original, replacement, out = [tmp_path / name for name in ("original.wav", "replacement.wav", "mix.flac")]
    for path, hz, duration in ((original, 440, 6), (replacement, 880, 2)):
        subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={hz}:duration={duration}", str(path)],
                       check=True, capture_output=True)
    track = {"kind": "music", "clips": [{"src": str(replacement), "start": 2, "src_in": 0, "src_out": 2,
                                         "meta": {"restoration_score": "shot"}}]}
    _audio_mix([track], "en", out, 6, original)
    raw = subprocess.run([ff, "-v", "error", "-i", str(out), "-ar", "8000", "-ac", "1", "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    samples = np.frombuffer(raw, np.float32)
    def tone(start, hz):
        a = samples[int(start * 8000):int((start + 0.5) * 8000)]
        return abs(np.sum(a * np.exp(-2j * np.pi * hz * np.arange(len(a)) / 8000)))
    assert tone(0.5, 440) > 100 * tone(3, 440)
    assert tone(3, 880) > 100 * tone(3, 440)


def test_correzione_master_conserva_video_voci_e_sottotitoli(tmp_path):
    import json
    import shutil
    import subprocess
    from core.modules.sigma_creative_lab.video.production import ffmpeg_bin
    from core.modules.sigma_creative_lab.video.repair_score import repair_score
    ff, fp = ffmpeg_bin(), ffmpeg_bin("ffprobe")
    if not shutil.which(ff) or not shutil.which(fp):
        pytest.skip("ffmpeg non disponibile")
    voice = tmp_path / "voice.wav"
    subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(voice)],
                   check=True, capture_output=True)
    sub = tmp_path / "subtitle.srt"
    sub.write_text("1\n00:00:00,000 --> 00:00:02,000\nTesto conservato\n", encoding="utf-8")
    source, output = tmp_path / "source.mp4", tmp_path / "repaired.mp4"
    subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=32x32:r=24:d=3",
                    "-i", str(voice), "-i", str(sub), "-map", "0:v", "-map", "1:a", "-map", "2:s",
                    "-c:v", "libx264", "-c:a", "aac", "-c:s", "mov_text", "-metadata:s:a:0", "language=eng", str(source)],
                   check=True, capture_output=True)
    tl = {"audio": [{"id": "restore_voice_shot_en", "kind": "voice", "clips": [
        {"src": str(voice), "start": 0, "src_in": 0, "src_out": 3}]}]}
    original = json.dumps(tl).encode()
    (tmp_path / "timeline.json").write_bytes(original)

    class Backend:
        async def run(self, *args, **kwargs):
            return voice.read_bytes(), "music.wav"

    result = asyncio.run(repair_score(tmp_path, source, output,
                                     [{"start": 0, "end": 3, "tags": "lyrical strings"}], Backend()))
    assert result["languages"] == ["en"] and output.is_file() and source.is_file()
    assert (tmp_path / "timeline.json").read_bytes() == original
    def video_hash(path):
        return subprocess.run([ff, "-v", "error", "-i", str(path), "-map", "0:v", "-c", "copy",
                               "-f", "hash", "-hash", "sha256", "-"], capture_output=True, check=True).stdout
    assert video_hash(source) == video_hash(output)
    with pytest.raises(ValueError, match="nuovo file"):
        asyncio.run(repair_score(tmp_path, source, output, [], Backend()))


def test_soundtrack_generica_verifica_audio_cache_e_durata_delle_dissolvenze(tmp_path):
    import io
    import shutil
    import wave
    from core.modules.sigma_creative_lab.video.production import ffmpeg_bin, probe
    from core.modules.sigma_creative_lab.video.soundtrack import generate_soundtrack, scene_segments
    if not shutil.which(ffmpeg_bin()):
        pytest.skip("ffmpeg non disponibile")
    production = {"id": "film", "settings": {"fps": 24, "seed": 1}, "shots": [
        {"status": "done", "scene": "partenza", "frames": 36},
        {"status": "done", "scene": "ritorno", "frames": 48}]}
    calls = []
    class Backend:
        async def run(self, payload, **kw):
            inputs = payload["workflow"]["enc"]["inputs"]
            calls.append(inputs)
            hz = 220 + inputs["seed"] % 200
            samples = (4000 * np.sin(2 * np.pi * hz * np.arange(24000 * 4) / 24000)).astype("<i2")
            out = io.BytesIO()
            with wave.open(out, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(samples.tobytes())
            return out.getvalue(), "score.wav"
    out = asyncio.run(generate_soundtrack(production, tmp_path, Backend()))
    assert abs(probe(out)["duration"] - 3.5) < 0.03
    assert len(calls) == 2
    asyncio.run(generate_soundtrack(production, tmp_path, Backend()))
    assert len(calls) == 2
    production["settings"]["seed"] = 2
    asyncio.run(generate_soundtrack(production, tmp_path, Backend()))
    assert len(calls) == 4
    production["shots"] = [{"status": "done", "scene": "lunga", "frames": 24 * 500}]
    segments = scene_segments(production)
    assert sum(s["seconds"] for s in segments) == pytest.approx(500)
    assert max(s["seconds"] for s in segments) <= 96
