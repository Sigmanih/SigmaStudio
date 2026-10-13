"""Libreria dei personaggi: schede, scelta del riferimento, model sheet col giudice, passaggio alle produzioni."""

import asyncio
from pathlib import Path

import pytest
from PIL import Image

from core.modules.sigma_creative_lab.video import character_library as L


@pytest.fixture
def lib(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "characters_dir", lambda: tmp_path / "characters")
    monkeypatch.setattr(L, "_gpu_busy", lambda: False)
    return tmp_path


def _fake_generate(calls):
    async def generate(model, prompt, out, width=1024, height=1024, seed=None, gpu=0, **_):
        calls.append(prompt)
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 96), "white").save(out)
        return {"path": str(out)}
    return generate


def test_scheda_e_percorsi_sicuri(lib):
    c = L.create("Nonno Beppe", "old man, flat cap", "cartoon3d")
    assert c["id"].startswith("nonno_beppe_") and L.get(c["id"])["genre"] == "cartoon3d"
    assert L.get("../config") is None                          # niente percorsi fuori dalla libreria
    assert L.file_path(c, "../../config/x.png") is None
    with pytest.raises(ValueError):
        L.create("   ")
    assert L.update(c["id"], name="Beppe")["name"] == "Beppe"
    assert L.delete(c["id"]) and L.list_characters() == []


def test_proposte_scelta_e_model_sheet(lib, monkeypatch):
    from core.modules.sigma_creative_lab.video import clip_judge, image_gen
    calls = []
    monkeypatch.setattr(image_gen, "generate", _fake_generate(calls))
    monkeypatch.setattr(image_gen, "installed", lambda model: True)
    verdicts = iter([{"ok": False, "score": 0.5, "differences": ["red cap instead of brown"], "fix": "brown cap"},
                     {"ok": True, "score": 1.0, "differences": []}])
    monkeypatch.setattr(clip_judge, "installed", lambda: True)
    monkeypatch.setattr(clip_judge.judge, "same_character", lambda *a, **k: next(verdicts))
    c = L.create("Beppe", "old man, brown flat cap", "cartoon3d")
    c = asyncio.run(L.candidates(c["id"], 2))
    assert len(c["candidates"]) == 2
    c = L.pick(c["id"], c["candidates"][1]["file"])
    assert c["front"] == "front.png" and c["seed"] == c["candidates"][1]["seed"]
    c = asyncio.run(L.sheet(c["id"], ["back"]))
    # La vista che ha cambiato persona viene rifatta col suggerimento del giudice.
    assert c["sheet"]["back"]["score"] == 1.0 and calls[-1].endswith("brown cap")
    assert calls[-1].lower().startswith("rear view")               # inquadratura in testa al prompt


def test_proposte_senza_descrizione(lib):
    c = L.create("Senza volto")
    with pytest.raises(ValueError):
        asyncio.run(L.candidates(c["id"]))


def test_immagine_caricata(lib):
    import io
    c = L.create("Disegno", "girl with red scarf")
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buf, "PNG")
    c = L.import_image(c["id"], buf.getvalue(), "mio.png", describe=False)
    assert c["front"] == "front.png" and L.file_path(c, "front.png")
    with pytest.raises(ValueError):
        L.import_image(c["id"], b"x", "virus.exe")


def test_passaggio_alla_produzione_e_ritorno(lib, monkeypatch):
    from core.modules.sigma_creative_lab.video import production as P
    store = P.ProductionStore(lib / "productions")
    monkeypatch.setattr(P.manager, "store", store)
    monkeypatch.setattr(L.paths, "workspace_dir", lambda: lib)
    prod = store.create("Storia")
    c = L.create("Mira", "girl, yellow raincoat", "anime")
    with pytest.raises(ValueError):
        L.to_production(c["id"], prod["id"])                   # senza riferimento non si aggiunge
    Image.new("RGB", (8, 8)).save(L._folder(c["id"]) / "front.png")
    L.update(c["id"])
    c = L.get(c["id"]); c["front"] = "front.png"; L._write(c)
    entry = L.to_production(c["id"], prod["id"])
    bible = store.get(prod["id"])["bible"]["characters"]
    assert [x["name"] for x in bible] == ["Mira"] and Path(entry["ref_image"]).is_file()
    # Dalla bozza non ancora salvata della produzione alla libreria.
    back = L.from_production(prod["id"], "Lia", {"name": "Lia", "description": "boy", "ref_image": entry["ref_image"]})
    assert back["front"] == "front.png"
    outside = L.from_production(prod["id"], "X", {"name": "X", "ref_image": str(Path(__file__).resolve())})
    assert outside["front"] == ""                              # file fuori dallo spazio di lavoro: ignorato


def test_grafo_klein_con_piu_riferimenti():
    from core.modules.sigma_creative_lab.video import image_gen
    g = image_gen.build_graph("klein", "two friends on a pier", width=1344, height=768, refs=["a.png", "b.png"])
    # Ogni riferimento si aggancia in catena sia al positivo sia al negativo.
    assert g["pos2"]["inputs"]["conditioning"] == ["pos1", 0] and g["neg2"]["inputs"]["conditioning"] == ["neg1", 0]
    assert g["guider"]["inputs"]["positive"] == ["pos2", 0]
    assert g["sigmas"]["inputs"] == {"steps": 4, "width": 1344, "height": 768}
    many = image_gen.build_graph("klein", "crowd", refs=[f"{k}.png" for k in range(9)])
    assert sum(1 for n in many.values() if n["class_type"] == "LoadImage") == image_gen.MAX_REFS


def test_fotogramma_chiave_dai_riferimenti(monkeypatch, tmp_path):
    from core.modules.sigma_creative_lab.video import genres, image_gen
    ref = tmp_path / "mira.png"
    Image.new("RGB", (8, 8)).save(ref)
    prod = {"bible": {"genre": "anime", "characters": [{"name": "Mira", "description": "girl", "ref_image": str(ref)},
                                                         {"name": "Ada", "description": "woman"}]}}
    shot = {"prompt": "Mira walks on the pier", "refs": []}
    monkeypatch.setattr(image_gen, "installed", lambda model: True)
    model, prompt, refs = genres.keyframe_plan(prod, shot)
    assert model == "klein" and refs == [str(ref)] and "Mira is the character in image 1" in prompt
    # Senza klein, o senza immagini dei personaggi in scena, resta il modello del genere.
    monkeypatch.setattr(image_gen, "installed", lambda model: model != "klein")
    assert genres.keyframe_plan(prod, shot)[0] == "animagine"
    monkeypatch.setattr(image_gen, "installed", lambda model: True)
    assert genres.keyframe_plan(prod, {"prompt": "Ada reads", "refs": []}) [2] == []
