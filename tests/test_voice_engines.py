"""Voci per personaggio col loro motore (Qwen3-TTS, VoxCPM2, Kokoro) e modello che scrive la storia."""

import json

from core.modules.sigma_creative_lab.video import production as P
from core.modules.sigma_creative_lab.voice import runtime as R
from core.modules.sigma_voice_studio import library


class FakeRuntime:
    def __init__(self, name):
        self.name, self.calls = name, []

    def installed(self):
        return True

    def synthesize(self, text, out, engine="", **opts):
        self.calls.append((engine, text, opts))
        out.write_bytes(b"RIFF")
        return {"path": str(out)}

    def transcribe(self, path, language="it"):
        return {"text": self.calls[-1][1] if self.calls else ""}

    def unload(self):
        pass


def _fake(monkeypatch, tmp_path):
    rts = {"qwen": FakeRuntime("qwen"), "voxcpm": FakeRuntime("voxcpm"), "voice": FakeRuntime("voice")}
    monkeypatch.setattr(R, "runtime_for", lambda e: rts["qwen" if e.startswith("qwen") else "voxcpm" if e.startswith("voxcpm") else "voice"])
    monkeypatch.setattr(library, "voices_dir", lambda: tmp_path / "voci")
    monkeypatch.setattr(library, "_runtimes", lambda: (rts["voice"], rts["qwen"]))
    return rts


def test_voce_da_tipo_parla_col_suo_motore(monkeypatch, tmp_path):
    rts = _fake(monkeypatch, tmp_path)
    v = library.create_from_type("Lia", "bambina", engine="qwen")
    assert v["engine"] == "qwen" and v["kind"] == "design" and "bambina" in v["description"]
    assert rts["qwen"].calls[0][0] == "qwen_design"
    library.speak(v["id"], "Ciao!", tmp_path / "a.wav", instruct="cheerful")
    engine, _text, opts = rts["qwen"].calls[-1]
    # Clonazione con la trascrizione del campione; il tono lo segue solo VoxCPM2.
    assert engine == "qwen_clone" and opts["ref_text"] == v["sample_text"] and "instruct" not in opts
    w = library.create_from_type("Tobia", "saggio", engine="voxcpm")
    assert "deep slow" in w["description"]                       # descrizione inglese per VoxCPM2
    library.speak(w["id"], "Si ricicla.", tmp_path / "b.wav", instruct="calm")
    assert rts["voxcpm"].calls[-1][0] == "voxcpm_clone" and rts["voxcpm"].calls[-1][2]["instruct"] == "calm"
    assert not rts["voice"].calls[1:]                            # niente Chatterbox: era l'accento straniero


def test_motore_sconosciuto(monkeypatch, tmp_path):
    _fake(monkeypatch, tmp_path)
    try:
        library.create_from_description("X", "voce", engine="elevenlabs")
    except ValueError as e:
        assert "sconosciuto" in str(e)
    else:
        raise AssertionError("motore sconosciuto accettato")


def test_scrittore_della_produzione(monkeypatch):
    seen = {}

    class Engine:
        def generate_stream(self, **kw):
            seen.update(kw)
            yield {"token": "", "notice": True, "model_status": "carico"}
            yield {"token": json.dumps({"ok": 1})}
    import core.engine as engine_pkg
    monkeypatch.setattr(engine_pkg, "sigma_engine", Engine(), raising=False)
    assert P.writer({}) is P._default_generate
    out = P.writer({"writer_model": "Qwen/Qwen3.8-27B-GGUF-Q4_K_M"})([{"role": "user", "content": "x"}], 50)
    assert seen["model_name"] == "Qwen/Qwen3.8-27B-GGUF-Q4_K_M" and out == '{"ok": 1}'


def test_motore_wan_per_inquadratura(monkeypatch):
    monkeypatch.setattr(P, "wan_installed", lambda mode: True)
    req_voce = {"init_image": "k.png", "audio": "l.wav"}
    req_azione = {"init_image": "k.png"}
    assert P.wan_mode({}, {}, req_voce) == ""                                    # predefinito: LTX
    assert P.wan_mode({"dialogue_engine": "wan_s2v"}, {}, req_voce) == "s2v"
    assert P.wan_mode({"dialogue_engine": "wan_s2v"}, {"engine": "ltx"}, req_voce) == ""   # la scelta per inquadratura vince
    assert P.wan_mode({}, {"engine": "wan_i2v"}, req_azione) == "i2v"
    assert P.wan_mode({"motion_engine": "wan_i2v"}, {}, {"audio": "l.wav"}) == ""        # Wan parte sempre da un fotogramma
    monkeypatch.setattr(P, "wan_installed", lambda mode: False)
    assert P.wan_mode({}, {"engine": "wan_i2v"}, req_azione) == ""                # non installato: si resta su LTX


def test_grafi_wan_e_seedvr2():
    from core.modules.sigma_creative_lab.generators.adapters import comfy_seedvr, comfy_wan
    g = comfy_wan.build_wan_s2v({"prompt": "Lia talks", "image": "a.png", "audio": "a.wav", "seconds": 6.5})
    assert g["trim"]["inputs"]["length"] == comfy_wan.wan_frames(6.5) and "ext1" in g      # battuta lunga: due blocchi
    assert g["s2v"]["inputs"]["length"] == comfy_wan.S2V_CHUNK
    i = comfy_wan.build_wan_i2v({"prompt": "Pepe digs", "image": "a.png", "seconds": 5})
    assert i["high"]["inputs"]["end_at_step"] == 2 and i["low"]["inputs"]["start_at_step"] == 2
    s = comfy_seedvr.build_seedvr2({"video": "c.mp4", "multiplier": 1.534})
    assert s["resize"]["inputs"]["resize_type.multiplier"] == 1.534
    assert s["chunk"]["inputs"]["chunking_mode"] == "manual" and s["post"]["inputs"]["color_correction_method"] == "lab"


def test_ambiente_sotto_le_battute(tmp_path):
    import subprocess
    ff = P.ffmpeg_bin()
    clip = tmp_path / "c.mp4"
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=128x72:d=3:r=24", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(clip)], check=True, capture_output=True)
    amb = tmp_path / "prato.wav"
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=10:c=pink:a=0.1:r=48000", str(amb)],
                   check=True, capture_output=True)
    prod = {"id": "amb", "settings": {}, "ambience": {"il prato": str(amb)},
            "shots": [{"id": "a", "status": "done", "clip_path": str(clip), "transition": "cut", "location": "il prato",
                       "dialogue": {"character": "Lia", "text": "Ciao"}}]}
    out = P.assemble(prod, tmp_path / "f.mp4")
    r = subprocess.run([ff, "-v", "info", "-i", str(out), "-ss", "2", "-t", "0.8", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    # Dopo la battuta (1 s) non c'e' piu' silenzio: si sente il prato.
    mean = float(r.stderr.split("mean_volume:")[1].split("dB")[0])
    assert mean > -60 and abs(P.probe(out)["audio_duration"] - P.probe(out)["duration"]) < 0.08


def test_pulizia_tiene_cio_che_e_citato(tmp_path):
    store = P.ProductionStore(tmp_path / "prods")
    prod = store.create("Prova pulizia")
    clips = store.path(prod["id"]) / "clips"
    clips.mkdir(parents=True)
    for name in ("0001_a.mp4", "0001_a.scrub.mp4", "0001_a.mp4.peaks.json", "0001_a_a2.mp4", "vecchia.png"):
        (clips / name).write_bytes(b"x")
    prod["shots"] = [{"id": "a", "clip_path": str(clips / "0001_a.mp4")}]
    store.save(prod)
    (store.path(prod["id"]) / "timeline.json").write_text(json.dumps({"items": [str(clips / "vecchia.png")]}))
    r = P.prune_production(store, prod["id"])
    assert r["removed"] == 1 and sorted(f.name for f in clips.iterdir()) == \
        ["0001_a.mp4", "0001_a.mp4.peaks.json", "0001_a.scrub.mp4", "vecchia.png"]      # tolto solo il tentativo
