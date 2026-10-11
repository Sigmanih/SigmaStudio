"""Scene didattiche (blocchi e HTML libero) e libreria delle voci personali."""

import json

import pytest

from core.modules.sigma_creative_lab.video import scene_author, scene_kit


# --- scene a blocchi -----------------------------------------------------------

SPEC = {"title": "Proiettile", "duration": 8, "params": {"g": 9.8, "v0": 20, "theta": 0.785},
        "blocks": [{"type": "formula", "tex": r"y = x\tan\theta", "start": 0},
                   {"type": "trajectory", "start": 2, "draw": 5, "t": [0, 3], "x": [0, 45], "y": [0, 12],
                    "xt": "v0*cos(theta)*t", "yt": "v0*sin(theta)*t - g*t^2/2"}]}


def test_spec_valida():
    assert scene_kit.validate(SPEC) == []


def test_espressioni_con_nomi_o_caratteri_non_ammessi():
    assert scene_kit.check_expr("x*tan(theta)", {"theta": 1}) is None
    assert "sconosciuti" in scene_kit.check_expr("x*alpha", {})
    assert "caratteri" in scene_kit.check_expr("alert`1`", {})       # niente codice dentro le espressioni
    bad = json.loads(json.dumps(SPEC))
    bad["blocks"][1]["xt"] = "document.cookie"
    assert any("xt" in p for p in scene_kit.validate(bad))


def test_intervalli_e_tipi():
    bad = json.loads(json.dumps(SPEC))
    bad["blocks"][1]["x"] = [10, 0]
    bad["blocks"].append({"type": "video"})
    problems = scene_kit.validate(bad)
    assert any("[min, max]" in p for p in problems) and any("type must be" in p for p in problems)


def test_spec_nel_html_non_chiude_lo_script():
    spec = {**SPEC, "title": "</script><script>alert(1)</script>"}
    html = scene_kit.to_html(spec)
    assert "</script><script>alert(1)" not in html and "window.seek" in html


def test_json_dalla_risposta_del_modello():
    assert scene_kit.json_from('Ecco:\n```json\n{"a": 1}\n```')["a"] == 1
    with pytest.raises(ValueError):
        scene_kit.json_from("nessun json")


# --- HTML libero --------------------------------------------------------------

def test_contratto_html():
    assert scene_author.check_contract("<script>window.seek = t => 0</script>") == []
    problems = scene_author.check_contract("<script>setInterval(() => 0, 10)</script>")
    assert any("seek" in p for p in problems) and any("setInterval" in p for p in problems)
    assert scene_author.extract_html("```html\n<div>x</div>\n```") == "<div>x</div>"


def test_autore_a_blocchi_corregge_dopo_un_errore(monkeypatch, tmp_path):
    answers = [json.dumps({"title": "x", "blocks": [{"type": "plot", "curves": [{"expr": "x*k"}]}]}),
               json.dumps(SPEC)]
    seen = []

    def gen(messages, max_tokens):
        seen.append(messages[-1]["content"])
        return answers.pop(0)
    rendered = {}

    def fake_render(html, out, seconds, *a, **k):
        rendered["html"] = html
        return {"clip_path": str(out), "frames": int(seconds * 24), "seconds": seconds, "errors": []}
    monkeypatch.setattr("core.modules.sigma_creative_lab.video.html_scene.render_scene", fake_render)
    r = scene_author.author_kit_scene("proiettile", tmp_path / "s.mp4", 8, generate=gen)
    assert r["attempts"] == 2 and "sconosciuti" in seen[-1]          # l'errore torna al modello
    assert "window.SPEC" in rendered["html"]


# --- libreria voci ------------------------------------------------------------

def test_libreria_voci(monkeypatch, tmp_path):
    from core.modules.sigma_voice_studio import library
    monkeypatch.setattr(library, "voices_dir", lambda: tmp_path)
    folder = tmp_path / "narratrice_abc123"
    folder.mkdir()
    (folder / "sample.wav").write_bytes(b"RIFF")
    (folder / "voice.json").write_text(json.dumps({"id": "narratrice_abc123", "name": "Narratrice", "kind": "design",
                                                   "created": 1}), encoding="utf-8")
    (tmp_path / "rotta").mkdir()                                     # cartella senza campione: ignorata
    assert [v["id"] for v in library.list_voices()] == ["narratrice_abc123"]
    assert library.get("../config") is None                          # niente percorsi fuori dalla libreria
    assert library.rename("narratrice_abc123", "Voce calda")["name"] == "Voce calda"
    with pytest.raises(ValueError):
        library.create_from_sample("x", b"data", "voce.exe")
    assert library.delete("narratrice_abc123") and library.list_voices() == []


# --- narrazione: simboli detti a parole ---------------------------------------

def test_simboli_matematici_a_parole():
    from core.modules.sigma_creative_lab.video.speech_text import plausible_duration, to_spoken
    assert to_spoken("c² = a² + b²") == "c al quadrato uguale a a al quadrato più b al quadrato"
    assert to_spoken("c = √25 = 5") == "c uguale a radice quadrata di 25 uguale a 5"
    assert to_spoken("v = s / t") == "v uguale a s fratto t"
    assert to_spoken("Un tram - quello rosso - passa") == "Un tram - quello rosso - passa"   # l'inciso resta
    # 18 parole in 25 s: la voce ha inventato parlato (caso reale della prima lezione).
    assert not plausible_duration(" ".join(["parola"] * 18), 25.4)
    assert plausible_duration(" ".join(["parola"] * 18), 7.0)


def test_figure_geometriche():
    spec = {"title": "Pitagora", "blocks": [{"type": "shapes", "x": [-4, 8], "y": [-5, 8], "items": [
        {"kind": "polygon", "points": [[0, 0], [4, 0], [0, 3]]},
        {"kind": "square_on", "from": [0, 0], "to": [4, 0], "side": -1, "label": "16"}]}]}
    assert scene_kit.validate(spec) == []
    spec["blocks"][0]["items"].append({"kind": "star", "points": [[0, 0]]})
    spec["blocks"][0]["items"].append({"kind": "segment", "from": [0, "a"], "to": [1, 1]})
    problems = scene_kit.validate(spec)
    assert any("kind must be" in p for p in problems) and any("coordinates" in p for p in problems)


def test_quadrati_sempre_esterni_e_dentro_gli_assi():
    # Caso reale: il modello aveva messo tutti i quadrati sopra il triangolo e assi troppo stretti.
    spec = {"title": "Pitagora", "blocks": [{"type": "shapes", "x": [0, 5], "y": [0, 5], "items": [
        {"kind": "polygon", "points": [[0, 0], [4, 0], [0, 3]]},
        {"kind": "square_on", "from": [0, 0], "to": [4, 0], "side": 1},
        {"kind": "square_on", "from": [0, 0], "to": [0, 3], "side": -1},
        {"kind": "square_on", "from": [4, 0], "to": [0, 3], "side": 1}]}]}
    b = scene_kit.normalize(spec)["blocks"][0]
    assert [it.get("side") for it in b["items"][1:]] == [-1, 1, -1]
    assert b["x"][0] <= -3 and b["x"][1] >= 7 and b["y"][0] <= -4 and b["y"][1] >= 7


def test_vecchie_lezioni_con_scena_oggetto(tmp_path):
    # "scene" e' il nome della scena: un oggetto li' mandava in errore l'interfaccia (React #31).
    from core.modules.sigma_creative_lab.video.production import ProductionStore
    store = ProductionStore(tmp_path)
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "production.json").write_text(json.dumps({"id": "p", "shots": [
        {"id": "a", "scene": {"description": "triangolo", "narration": "ciao"}}, {"id": "b", "scene": "Faro"}]}),
        encoding="utf-8")
    shots = store.get("p")["shots"]
    assert shots[0]["scene"] == "Lezione" and shots[0]["teaching"]["narration"] == "ciao"
    assert shots[1]["scene"] == "Faro" and "teaching" not in shots[1]


def test_quadrati_senza_triangolo_e_scritte_sole():
    spec = {"title": "P", "blocks": [
        {"type": "shapes", "items": [{"kind": "square_on", "from": [0, 0], "to": [3, 0], "side": 1},
                                     {"kind": "square_on", "from": [0, 0], "to": [0, 4], "side": -1},
                                     {"kind": "square_on", "from": [3, 0], "to": [0, 4], "side": 1}]},
        {"type": "shapes", "items": [{"kind": "label", "at": [3, 5], "text": "9 + 16 = 25"}]}]}
    out = scene_kit.normalize(spec)
    assert out["blocks"][0]["items"][0]["kind"] == "polygon"                # triangolo ricavato dai quadrati
    assert [it["side"] for it in out["blocks"][0]["items"][1:]] == [-1, 1, -1]
    assert out["blocks"][1] == {"type": "bullets", "start": 0, "items": ["9 + 16 = 25"]}
    assert scene_kit.validate(out) == []
