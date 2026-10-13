"""Storyboard e montaggio dopo la prova dei samurai: alias, lingua, durate, stop, scene rifatte, stile, montaggi paralleli."""

import json
import subprocess
import threading
from pathlib import Path

import pytest

from core.modules.sigma_creative_lab.video import genres, image_gen
from core.modules.sigma_creative_lab.video import production as P

MIMOKI = {"name": "Mimoki", "description": "young shogun, red armor", "aliases": ["shonen", "shogun"]}


def test_ruoli_diventano_il_personaggio():
    # Caso reale: "shonen and Mimoki" erano due persone identiche nella stessa inquadratura.
    assert P.apply_aliases("Medium shot of shonen and Mimoki standing triumphant.", [MIMOKI]) == \
        "Medium shot of Mimoki standing triumphant."
    assert P.apply_aliases("The shonen, though wounded, raises his hand.", [MIMOKI]).startswith("Mimoki, though")
    assert P.apply_aliases("A samurai bows to the shogunate envoy", [MIMOKI]) == "A samurai bows to the shogunate envoy"


def test_lingua_e_durate():
    assert P.looks_italian("Camera segue Mimoki mentre esegue una serie di calci rapidi")
    assert not P.looks_italian("A samurai is in the garden with a lamp held in his right hand")
    assert P.shot_bounds({"video_model": "ltx25", "max_clip_seconds": 10}) == (4.0, 10.0)
    assert P.shot_bounds({"video_model": "h3"}) == (3.0, 5.2)


def _fake_llm(scenes, shots_by_scene, translations=None):
    calls = []

    def gen(messages, max_tokens):
        text = messages[-1]["content"]
        calls.append(text)
        if "Dividi questo soggetto" in text:
            return json.dumps(scenes)
        if "Translate these" in text:
            return json.dumps(translations or [])
        return json.dumps(shots_by_scene.pop(0))
    return gen, calls


def test_storyboard_alias_inglese_e_salvataggio_parziale():
    scenes = [{"title": "Il villaggio", "summary": "lo shonen difende la casa", "seconds": 12},
              {"title": "La battaglia", "summary": "combatte", "seconds": 12}]
    shots = [[{"prompt": "Close-up of the shonen looking at the hills.", "seconds": 6, "characters": ["shonen"]},
              {"prompt": "Inquadratura ravvicinata sullo Mimoki mentre i suoi occhi guardano", "seconds": 6}],
             [{"prompt": "Mimoki draws his sword.", "seconds": 6, "characters": ["Mimoki"]}]]
    gen, calls = _fake_llm(scenes, shots, translations=["Close-up of Mimoki as his eyes look ahead"])
    saved = []
    out = P.plan_storyboard("lo shonen difende la casa", 0.4, characters=[MIMOKI], generate=gen,
                            shot_seconds=(4.0, 10.0), on_scene=lambda s: saved.append(len(s)))
    assert out[0]["prompt"] == "Close-up of Mimoki looking at the hills." and out[0]["refs"] == ["Mimoki"]
    assert out[1]["prompt"] == "Close-up of Mimoki as his eyes look ahead"        # tradotto
    assert all(s["duration_s"] >= 4.0 for s in out)
    assert saved == [2, 3]                                                        # una scena alla volta
    assert "shonen" in calls[1] and "SEMPRE in inglese" in calls[1]


def test_storyboard_si_ferma_e_tiene_le_scene_fatte():
    scenes = [{"title": f"S{k}", "summary": "x", "seconds": 10} for k in range(3)]
    stop = threading.Event()
    saved = []

    def gen(messages, max_tokens):
        if "Dividi questo soggetto" in messages[-1]["content"]:
            return json.dumps(scenes)
        stop.set()                                    # l'utente preme "Ferma" durante la prima scena
        return json.dumps([{"prompt": "Mimoki walks.", "seconds": 5}])
    with pytest.raises(P.PlanningCancelled):
        P.plan_storyboard("x", 0.5, characters=[MIMOKI], generate=gen, cancel=stop,
                          on_scene=lambda s: saved.append(len(s)))
    assert saved == [1]


def test_scena_riscritta_con_le_indicazioni():
    prod = {"settings": {"video_model": "ltx25"}, "bible": {"characters": [MIMOKI], "style": ""},
            "shots": [P.new_shot("A", 5, scene="Uno"), P.new_shot("B", 5, scene="Due"), P.new_shot("C", 5, scene="Due"),
                      P.new_shot("D", 5, scene="Tre")]}
    seen = []

    def gen(messages, max_tokens):
        seen.append(messages[-1]["content"])
        return json.dumps([{"prompt": "Mimoki fights three samurai alone.", "seconds": 8, "characters": ["Mimoki"]}])
    new = P.replan_scene(prod, "Due", "Mimoki combatte da solo contro tre samurai", gen)
    assert [s["prompt"] for s in prod["shots"]] == ["A", "Mimoki fights three samurai alone.", "D"]
    assert new[0]["scene"] == "Due" and "PREVALGONO" in seen[0] and seen[0].index("Mimoki combatte") < seen[0].index("Versione precedente")
    with pytest.raises(ValueError):
        P.replan_scene(prod, "Inesistente", "x", gen)


def test_stile_unico_con_klein(monkeypatch, tmp_path):
    # Prova dei samurai: le inquadrature senza personaggi uscivano da un altro modello, con un altro stile.
    monkeypatch.setattr(image_gen, "installed", lambda model: True)
    ref, style = tmp_path / "mimoki.png", tmp_path / "stile.png"
    ref.write_bytes(b"x")
    style.write_bytes(b"x")
    prod = {"bible": {"genre": "illustration", "characters": [{**MIMOKI, "ref_image": str(ref)}]}}
    model, _prompt, refs = genres.keyframe_plan(prod, {"prompt": "Samurai run down the hill", "refs": []})
    assert model == "klein" and refs == []                    # anche senza personaggi: klein, non Z-Image
    prod["bible"]["style_image"] = str(style)
    model, prompt, refs = genres.keyframe_plan(prod, {"prompt": "Mimoki waits", "refs": ["Mimoki"]})
    assert refs == [str(ref), str(style)] and "art style" in prompt and "image 2" in prompt


def _clip(path: Path, color: str) -> None:
    ff = P.ffmpeg_bin()
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=128x72:d=1:r=24",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True, capture_output=True)


def test_montaggi_paralleli_non_si_pestano(tmp_path):
    clips = []
    for k, color in enumerate(("red", "green", "blue")):
        c = tmp_path / f"c{k}.mp4"
        _clip(c, color)
        clips.append({"id": f"s{k}", "status": "done", "clip_path": str(c), "transition": "cut"})
    prod = {"id": "prova_montaggio", "shots": clips}
    out = tmp_path / "video" / "finale.mp4"
    errors = []

    def run():
        try:
            P.assemble(prod, out)
        except RuntimeError as e:
            errors.append(str(e))
    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Uno monta, l'altro viene rifiutato con un messaggio chiaro: nessun "Impossible to open".
    assert out.is_file() and P.probe(out)["duration"] > 2.5
    assert all("gia' in corso" in e for e in errors)
    assert not [p for p in out.parent.iterdir() if p.name.startswith(".")]     # niente cartelle di lavoro lasciate


def test_battute_dello_storyboard():
    lia = {"name": "Lia", "description": "girl, 7", "aliases": ["the girl"]}
    items = [{"prompt": "Lia looks at Nonno Beppe and smiles.", "seconds": 5, "characters": [],
              "dialogue": {"character": "the girl", "line": "Nonno, perche' le stelle brillano?"}},
             {"prompt": "A cat sleeps.", "seconds": 5, "dialogue": {"character": "Gatto misterioso", "line": "Miao"}}]
    shots = P._normalize_shots(items, 10, (4.0, 10.0), [lia], "Sera")
    assert shots[0]["dialogue"] == {"character": "Lia", "text": "Nonno, perche' le stelle brillano?"}
    assert "Lia" in shots[0]["refs"]                                  # chi parla e' in scena
    assert "dialogue" not in shots[1]                                 # personaggio fuori dalla bibbia: niente voce
    prod = {"settings": {"video_model": "ltx25"}, "bible": {"characters": [lia]}}
    prompt = P.compose_prompt(prod, shots[0], False)
    assert "saying: \"Nonno, perche' le stelle brillano?\"" in prompt and "lips move" in prompt


def test_nomi_doppi_uniti():
    chars = [{"name": "Pepe", "aliases": ["the little hedgehog"]}, {"name": "Lia", "aliases": []}]
    assert P.apply_aliases("Pepe Pepe emerges from a bush", chars) == "Pepe emerges from a bush"
    assert P.apply_aliases("The little hedgehog Pepe waves", chars) == "Pepe waves"
    assert P.apply_aliases("Pepe and Lia walk", chars) == "Pepe and Lia walk"


def test_giudice_consiglia_e_rifa_solo_i_gravi():
    lieve = {"ok": False, "severe": False, "issues": ["the water is not visible"]}
    grave = {"ok": False, "severe": True, "issues": ["the girl walks backwards"]}
    shot = {"attempts": 1}
    assert P._judge_retries({"judge_mode": "severe"}, shot, grave)
    assert not P._judge_retries({"judge_mode": "severe"}, shot, lieve)        # decide l'utente
    assert not P._judge_retries({"judge_mode": "severe"}, {"attempts": 2}, grave)   # una volta sola
    assert not P._judge_retries({"judge_mode": "advise"}, shot, grave)
    assert P._judge_retries({"judge_mode": "strict", "max_attempts": 3}, {"attempts": 2}, lieve)


def test_correzione_dell_utente_resta_nell_inquadratura():
    prod = {"settings": {"video_model": "ltx25"}, "bible": {}, "shots": [{"id": "a1", "prompt": "Lia waters the pot.", "refs": ["Lia"]}]}
    rewritten = "The terracotta pot is a plain round pot with no spout; only the watering can has a spout."
    answers = iter([json.dumps({"literal": "the pot has a spout like the watering can", "instruction": rewritten}), "yes"])
    shot = P.user_fix(prod, "a1", "il vaso ha un becco come l'annaffiatoio", lambda m, n: next(answers))
    assert shot["fixes"] == [{"problem": "il vaso ha un becco come l'annaffiatoio", "text": rewritten}]
    assert rewritten.rstrip(".") in P.compose_prompt(prod, shot, False)
    model, prompt, _refs = genres.keyframe_plan({"bible": {}}, shot) if image_gen.installed("klein") else ("", rewritten, [])
    assert "no spout" in prompt
    with pytest.raises(ValueError):
        P.user_fix(prod, "a1", "   ", lambda m, n: "x")


def test_chi_parla_e_chi_ascolta():
    prod = {"settings": {"video_model": "ltx25"}, "bible": {}}
    shot = {"prompt": "Lia looks at Nonno.", "refs": ["Lia", "Nonno Beppe"], "dialogue": {"character": "Lia", "text": "Ciao!"}}
    prompt = P.compose_prompt(prod, shot, False)
    assert "Only Lia's lips move" in prompt and "Nonno Beppe listens in silence" in prompt



def test_correzione_ribaltata_viene_scartata():
    # Caso reale: "Lia non tiene niente in mano, nessun girasole" -> "Lia holds a sunflower".
    answers = iter([json.dumps({"literal": "Lia holds nothing in her hands, no sunflower",
                                "instruction": "Lia holds a sunflower clearly visible in her hand"}), "no"])
    assert P.rewrite_fix("Lia non tiene niente in mano, nessun girasole", "Lia runs", lambda m, n: next(answers)) ==         "Lia holds nothing in her hands, no sunflower"
