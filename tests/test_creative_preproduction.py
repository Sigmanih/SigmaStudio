"""Pre-produzione e sincronia delle voci, dopo "Il seme di Lia".

Storia piatta, vaso disegnato ogni volta diverso, voci che a fine film anticipavano le labbra di 6 s.
"""

import json
import subprocess
from pathlib import Path

from core.modules.sigma_creative_lab.video import genres, image_gen
from core.modules.sigma_creative_lab.video import preproduction as PP
from core.modules.sigma_creative_lab.video import production as P

LIA = {"name": "Lia", "description": "little girl, brown bob, green overalls"}
POT = {"name": "terracotta pot", "description": "a plain round terracotta pot with no spout and no handle",
       "states": "only soil -> tiny sprout"}
GARDEN = {"name": "Lia's garden", "description": "a small sunny garden with a stone path and a wooden fence"}


def _gen(answers, calls=None):
    def gen(messages, max_tokens):
        text = messages[-1]["content"]
        if calls is not None:
            calls.append(text)
        for key, answer in answers:
            if key in text:
                return json.dumps(answer) if not isinstance(answer, str) else answer
        raise AssertionError(f"richiesta inattesa: {text[:80]}")
    return gen


def test_storia_sviluppata_e_durate_riportate():
    story = {"title": "Il seme", "logline": "Lia vuole un fiore", "message": "la pazienza",
             "scenes": [{"title": "Semina", "location": "Lia's garden", "summary": "Lia pianta il seme.", "seconds": 10},
                        {"title": "Attesa", "location": "Lia's garden", "summary": "Non cresce nulla.", "seconds": 10},
                        {"title": "vuota", "summary": ""}]}
    out = PP.develop_story("A girl plants a seed", 1.0, [LIA], generate=_gen([("sceneggiatore", story)]))
    assert [s["title"] for s in out["scenes"]] == ["Semina", "Attesa"]
    assert sum(s["seconds"] for s in out["scenes"]) == 60          # 20 dichiarati -> 60 chiesti
    assert out["message"] == "la pazienza"


def test_mondo_descritto_in_inglese_e_luoghi_mancanti():
    story = {"scenes": [{"title": "Semina", "location": "Lia's garden", "summary": "x"},
                        {"title": "Notte", "location": "la cameretta", "summary": "y"}]}
    design = {"locations": [{"name": "Lia's garden", "description": "un piccolo giardino soleggiato con un sentiero di pietra"}],
              "props": [POT]}
    out = PP.design_world(story, [LIA], generate=_gen([("production designer", design),
                                                       ("Translate", ["a small sunny garden with a stone path"])]))
    assert out["locations"][0]["description"] == "a small sunny garden with a stone path"
    assert out["locations"][1] == {"name": "la cameretta", "description": ""}     # da completare a mano
    assert out["props"][0]["name"] == "terracotta pot"


def test_lingua_indifferente():
    assert PP.needs_english("Lia annaffia il vaso con cura")
    assert PP.needs_english("Lia arrose le pot avec soin dans le jardin")
    assert not PP.needs_english("Lia waters the pot carefully in the garden")
    assert not PP.needs_english("Close-up")


def test_luogo_oggetti_ed_espressioni_nei_prompt(monkeypatch, tmp_path):
    prod = {"settings": {"video_model": "ltx25"},
            "bible": {"style": "3D cartoon", "characters": [LIA],
                      "pre": {"scenes": [{"title": "Semina", "location": "Lia's garden"}], "locations": [GARDEN],
                              "props": [POT, {"name": "watering can", "description": "a small blue metal watering can"}]}}}
    shot = {"prompt": "Lia kneels by the terracotta pot.", "scene": "Semina", "refs": ["Lia"],
            "expressions": {"Lia": "wide-eyed wonder"}}
    text = P.compose_prompt(prod, shot, use_refs=False)
    assert "Setting, Lia's garden: a small sunny garden" in text
    assert "no spout and no handle" in text and "watering can" not in text      # solo gli oggetti in scena
    assert "Lia: wide-eyed wonder" in text
    monkeypatch.setattr(image_gen, "installed", lambda model: True)
    _model, kprompt, _refs = genres.keyframe_plan(prod, shot)
    assert "no spout" in kprompt and "Setting" in kprompt


def test_dialogo_inquadrato_per_il_labiale():
    prod = {"settings": {"video_model": "ltx25"}, "bible": {"characters": [LIA, {"name": "Pepe"}]}}
    shot = {"prompt": "Lia talks to Pepe.", "refs": ["Lia", "Pepe"], "dialogue": {"character": "Lia", "text": "Ciao!"}}
    text = P.compose_prompt(prod, shot, use_refs=False)
    assert "Medium close-up of Lia, face toward the camera, mouth clearly visible" in text
    assert "Pepe listens in silence" in text


def test_storyboard_dalla_preproduzione():
    pre = {"scenes": [{"title": "Semina", "location": "Lia's garden", "time": "morning", "mood": "hope",
                       "summary": "Lia pianta il seme.", "seconds": 10}],
           "locations": [GARDEN], "props": [POT], "message": "la pazienza"}
    calls = []
    shots = [{"prompt": "Medium shot: Lia kneels by the terracotta pot, pressing a seed into the soil.", "seconds": 5,
              "characters": ["Lia"], "expressions": {"lia": "focused, tongue out"}}]
    out = P.plan_storyboard("x", 10 / 60, characters=[LIA], shot_seconds=(4, 8), pre=pre,
                            generate=_gen([("Scomponi la scena", shots)], calls))
    assert len(calls) == 1 and "Dividi questo soggetto" not in calls[0]          # le scene sono quelle approvate
    assert "no spout and no handle" in calls[0] and "Lia's garden" in calls[0]
    assert out[0]["location"] == "Lia's garden" and out[0]["expressions"] == {"Lia": "focused, tongue out"}


def _clip(path: Path, seconds: float, audio_seconds: float) -> None:
    subprocess.run([P.ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=red:s=128x72:d={seconds}:r=24",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={audio_seconds}:sample_rate=48000",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True, capture_output=True)


def test_montaggio_audio_allineato_al_video(tmp_path):
    # Clip con battuta: video 3 s, audio 1 s. Concatenando senza riempire, l'audio dopo anticipava.
    shots = []
    for k in range(4):
        c = tmp_path / f"c{k}.mp4"
        _clip(c, 3.0, 1.0)
        shots.append({"id": f"s{k}", "status": "done", "clip_path": str(c), "transition": "cut"})
    out = P.assemble({"id": "sync", "shots": shots}, tmp_path / "film.mp4")
    info = P.probe(out)
    assert abs(info["audio_duration"] - info["duration"]) < 0.08


def test_battuta_allungata_fino_a_fine_clip(tmp_path):
    line = tmp_path / "line.wav"
    subprocess.run([P.ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1:sample_rate=24000",
                    str(line)], check=True, capture_output=True)
    padded = tmp_path / "padded.wav"
    padded.write_bytes(P._padded_line(line, 4.0))
    assert abs(P.probe(padded)["audio_duration"] - 4.0) < 0.05


def test_miglior_tentativo_solo_della_ripresa_attuale():
    shot = {"prompt": "Pepe waves", "dialogue": {"text": "Ciao", "source": "voce_vecchia"}}
    shot["judge_history"] = [{"clip_path": "vecchia.mp4", "score": 0.9, "take": P.take_key(shot)}]
    shot["dialogue"]["source"] = "voce_nuova"
    shot["judge_history"].append({"clip_path": "nuova.mp4", "score": 0.5, "take": P.take_key(shot)})
    assert P.best_judged(shot)["clip_path"] == "nuova.mp4"


def test_revisione_della_storia_e_arco():
    draft = {"title": "Bozza", "scenes": [{"title": "A", "location": "il prato", "summary": "la bottiglia diventa un vaso per magia", "seconds": 30}]}
    better = {"title": "Il picnic", "message": "si separa la plastica",
              "arc": {"want": "Pepe vuole giocare subito", "failed_attempt": "lascia la bottiglia sull'erba"},
              "scenes": [{"title": "A", "location": "il prato", "summary": "Pepe porta la bottiglia al bidone giallo", "seconds": 30}]}
    calls = []
    out = PP.develop_story("picnic", 0.5, [], generate=_gen([("story editor", better), ("sceneggiatore", draft)], calls))
    assert len(calls) == 2 and "per magia" in calls[1]                 # la revisione legge la stesura
    assert out["title"] == "Il picnic" and out["arc"]["want"] == "Pepe vuole giocare subito"
    assert out["arc"]["resolution"] == ""


def test_nomi_e_stati_degli_oggetti():
    assert PP.prop_name("PlasticBottle") == "plastic bottle"
    assert PP._states("['soil', 'sprout']") == "soil -> sprout"
    story = {"scenes": [{"title": "A", "location": "il prato", "summary": "x"}]}
    calls = []
    design = {"locations": [{"name": "il prato", "description": "a green meadow"}],
              "props": [{"name": "PlasticBottle", "description": "a clear bottle", "states": ["full", "empty"]}]}
    out = PP.design_world(story, [], generate=_gen([("production designer", design)], calls))
    assert "exactly these, with these exact names: il prato" in calls[0]
    assert out["props"][0] == {"name": "plastic bottle", "description": "a clear bottle", "states": "full -> empty"}


def test_sottotitoli_e_anteprima(tmp_path):
    frame = tmp_path / "k.png"
    subprocess.run([P.ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x176", "-frames:v", "1",
                    str(frame)], check=True, capture_output=True)
    line = tmp_path / "line.wav"
    subprocess.run([P.ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=2:sample_rate=24000",
                    str(line)], check=True, capture_output=True)
    prod = {"settings": {"video_model": "ltx25"}, "shots": [
        {"id": "a", "keyframe": str(frame), "duration_s": 3.0, "status": "pending"},
        {"id": "b", "keyframe": str(frame), "duration_s": 2.0, "status": "pending",
         "dialogue": {"character": "Lia", "text": "Ciao nonno!", "audio": str(line), "seconds": 2.0}}]}
    out = P.animatic(prod, tmp_path / "anteprima.mp4", width=320)
    info = P.probe(out)
    assert abs(info["duration"] - 5.6) < 0.1 and abs(info["audio_duration"] - info["duration"]) < 0.1   # 3 + 2.6
    srt = out.with_suffix(".srt").read_text(encoding="utf-8")
    assert "00:00:03,250 --> 00:00:05,000" in srt and "Ciao nonno!" in srt
    assert out.with_suffix(".vtt").read_text(encoding="utf-8").startswith("WEBVTT")


def test_inquadratura_ricopiata_tolta_e_luogo_della_scena():
    old = [{"prompt": "Wide shot of the meadow under the oak tree, with the picnic towel laid flat. Pepe reappears from the "
                      "right and runs toward the flower field. The camera remains static."}]
    items = [{"prompt": "Wide shot of the meadow under the oak tree, with the picnic towel laid flat; Pepe reappears from "
                        "the right and runs toward the flower field. The camera stays static.", "seconds": 5,
              "location": "the meadow"},
             {"prompt": "Close-up of Tobia emerging from the pond.", "seconds": 5, "location": "the pond"}]
    shots = P._normalize_shots(items, 10, (4, 8), [], "Due", location="il prato")
    kept = P._drop_repeats(shots, old)
    assert [s["prompt"][:8] for s in kept] == ["Close-up"]
    assert kept[0]["location"] == "il prato"


def test_battute_perse_rimesse_al_loro_posto():
    shots = [{"prompt": "a", "refs": ["Lia"]}, {"prompt": "b", "refs": ["Pepe"], "dialogue": {"character": "Pepe", "text": "Ciao Lia!"}},
             {"prompt": "c", "refs": ["Lia"]}, {"prompt": "d", "refs": [], "transition": "continue"}]
    lines = [{"character": "Pepe", "line": "Ciao, Lia!"}, {"character": "Lia", "line": "Andiamo al bidone"},
             {"character": "Tobia", "line": "Bravi"}, {"character": "Lia", "line": "Non c'e' piu' posto"}]
    assert PP.place_lines(shots, lines) == 2
    assert shots[2]["dialogue"] == {"character": "Lia", "text": "Andiamo al bidone"}          # dopo Pepe, Lia in scena
    assert shots[3]["dialogue"]["character"] == "Tobia" and "Tobia" in shots[3]["refs"]
    assert shots[3]["transition"] == "cut" and "dialogue" not in shots[0]


def test_battute_della_storia_solo_dei_personaggi():
    story = {"scenes": [{"title": "A", "summary": "x", "seconds": 10,
                         "lines": [{"character": "Lia", "line": "Ciao!"}, {"character": "Un passante", "line": "Ehi"}]}]}
    out = PP.develop_story("x", 10 / 60, [LIA], generate=_gen([("sceneggiatore", story)]), revise=False)
    assert out["scenes"][0]["lines"] == [{"character": "Lia", "line": "Ciao!"}]
    assert 'Lia: "Ciao!"' in PP.scene_brief({"scenes": out["scenes"]}, out["scenes"][0])


def test_personaggi_contati_per_tipo(monkeypatch, tmp_path):
    from core.modules.sigma_creative_lab.video import clip_judge
    prod = {"bible": {"characters": [LIA, {"name": "Tobia", "description": "a cute old cartoon tortoise, green cap"},
                                     {"name": "Nonno Beppe", "description": "elderly Italian man, white beard"}]}}
    assert P.character_kind(prod["bible"]["characters"][1]) == "cute old cartoon tortoise"
    seen = {}

    def count(image, kinds, device):
        seen["kinds"] = kinds
        return [2, 0, 1]                    # due Lia, Tobia sparita, il nonno c'e'
    monkeypatch.setattr(clip_judge.judge, "count_kinds", count)
    shot = {"prompt": "Lia and Tobia by the pond, Nonno Beppe behind", "refs": ["Lia", "Tobia", "Nonno Beppe"]}
    errors = P._cast_errors(prod, shot, tmp_path / "k.png", "cpu")
    assert seen["kinds"] == ["little girl", "cute old cartoon tortoise", "elderly Italian man"]
    assert errors == ["Lia: 2 nell'immagine invece di 1", "Tobia: 0 nell'immagine invece di 1"]
