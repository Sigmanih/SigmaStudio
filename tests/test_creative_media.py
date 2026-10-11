"""Editor per presentazioni e generi: media importati, testi sovrapposti, fotogrammi chiave."""

import pytest

from core.modules.sigma_creative_lab.video import genres, media_import as mi, timeline as T
from core.modules.sigma_creative_lab.video import production as prod_mod
from core.modules.sigma_creative_lab.video.timeline import TimelineError


# --- caricamento a pezzi ------------------------------------------------------

def test_tipi_di_file():
    from pathlib import Path
    assert mi.kind_of(Path("demo.MP4")) == "video"
    assert mi.kind_of(Path("logo.png")) == "image"
    assert mi.kind_of(Path("voce.m4a")) == "audio"
    with pytest.raises(ValueError):
        mi.kind_of(Path("documento.pdf"))
    assert mi.safe_name("Registrazione schermo (1).mp4") == "Registrazione_schermo_1.mp4"


def test_pezzi_in_ordine_e_ripresa(tmp_path):
    up = tmp_path / ".uploads"
    assert mi.append_chunk(up, "abcd1234", 0, b"x" * 10) == 10
    assert mi.append_chunk(up, "abcd1234", 10, b"y" * 5) == 15
    with pytest.raises(ValueError):
        mi.append_chunk(up, "abcd1234", 10, b"z")          # pezzo ripetuto: il client riparte dall'offset giusto
    with pytest.raises(ValueError):
        mi.append_chunk(up, "../escape", 0, b"z")           # identificativo che esce dalla cartella
    path = mi.finish_upload(up, "abcd1234", "Demo finale.mp4", tmp_path / "imports")
    assert path.read_bytes() == b"x" * 10 + b"y" * 5 and path.suffix == ".mp4"


def test_testo_impaginato_trasparente():
    img = mi.render_text((640, 360), "Titolo molto lungo che deve andare a capo su piu' righe", "sotto", "title")
    assert img.size == (640, 360) and img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0                     # angolo trasparente: il video resta visibile


# --- testi sovrapposti nella timeline ----------------------------------------

def _prod():
    return {"id": "p1", "shots": [{"id": "s0", "status": "done",
                                   "takes": [{"id": "t1", "clip_path": "c.mp4", "frames": 240}], "take": "t1"}]}


def test_testi_sovrapposti():
    prod = _prod()
    tl = T.build_from_shots(prod)
    assert tl["overlays"] == []
    ov = T.op_overlay_add(tl, prod, "Il guardiano", 2.0, 5.0, sub="1952", style="lower")["overlay"]
    T.op_overlay_add(tl, prod, "Prima", 0.5, 1.5, style="caption")
    assert [o["text"] for o in tl["overlays"]] == ["Prima", "Il guardiano"]      # ordinati per inizio
    T.op_overlay_update(tl, prod, ov, start=6.0, end=8.0)
    assert tl["overlays"][-1]["start"] == 6.0
    with pytest.raises(TimelineError):
        T.op_overlay_update(tl, prod, ov, style="lampeggiante")
    with pytest.raises(TimelineError):
        T.op_overlay_add(tl, prod, "  ", 0, 2)
    T.op_overlay_delete(tl, prod, ov)
    assert len(tl["overlays"]) == 1


def test_dissolvenze_audio_limitate(tmp_path):
    prod = _prod()
    tl = T.build_from_shots(prod)
    wav = tmp_path / "m.wav"
    wav.write_bytes(b"RIFF")
    cid = T.op_audio_add(tl, prod, "music", str(wav), 0, src_out=4.0)["clip"]
    T.op_audio_update(tl, prod, cid, fade_in=10, fade_out=1.5)
    _, _, clip = T._find_audio_clip(tl, cid)
    assert clip["fade_in"] == 2.0 and clip["fade_out"] == 1.5           # non oltre meta' clip ciascuna


def test_media_importati_fuori_da_ricostruzione_e_riepilogo():
    prod = _prod()
    prod["shots"] += [{"id": "imp", "status": "done", "origin": "import",
                       "takes": [{"id": "t1", "clip_path": "i.mp4", "frames": 48}], "take": "t1"},
                      {"id": "tit", "status": "done", "origin": "title",
                       "takes": [{"id": "t1", "clip_path": "t.mp4", "frames": 48}], "take": "t1"}]
    assert [it["shot_id"] for it in T.build_from_shots(prod)["video"]] == ["s0"]
    assert prod_mod.summary(prod)["shots"] == 1


# --- generi e fotogrammi chiave ----------------------------------------------

def test_prompt_anime_a_tag_senza_nomi():
    prod = {"bible": {"genre": "anime", "characters": [{"name": "Mira", "description": "1girl, silver hair, yellow raincoat"}]}}
    shot = {"prompt": "Mira walks along the pier, the oil lamp held in her right hand. The camera follows from behind.",
            "refs": ["Mira"]}
    text = genres.keyframe_prompt(prod, shot)
    assert text.startswith("1girl, silver hair, yellow raincoat, solo, from behind")
    assert "holding oil lamp" in text and "Mira:" not in text and "wide shot" not in text


def test_prompt_realistico_con_descrizione_dei_personaggi():
    prod = {"bible": {"genre": "realistic", "characters": [{"name": "Ada", "description": "red coat"}]}}
    assert "Ada: red coat." in genres.keyframe_prompt(prod, {"prompt": "Ada opens the door", "refs": ["Ada"]})


def test_fotogramma_chiave_diventa_il_primo_fotogramma(tmp_path):
    store = prod_mod.ProductionStore(tmp_path)
    key = tmp_path / "k.png"
    key.write_bytes(b"x")
    prod = store.create("t", settings={"keyframes": True},
                        bible={"characters": [{"name": "Ada", "description": "red coat", "ref_image": str(key)}]})
    prod["shots"] = [prod_mod.new_shot("Ada walks", 4.0, refs=["Ada"]), prod_mod.new_shot("she keeps walking", 4.0, "continue")]
    prod["shots"][0]["keyframe"] = str(key)
    runner = prod_mod.ProductionRunner(store, prod["id"], engine=prod_mod.ClipEngine())
    req = runner.build_request(prod, 0)
    assert req["init_image"] == str(key) and req["ref_images"] == []
    assert prod_mod.keyframe_targets(prod) == [0]                    # la continue parte dal clip precedente
    prod["settings"]["keyframes"] = False
    assert runner.build_request(prod, 0)["init_image"] == ""          # senza la modalita' resta il riferimento


def test_generi_completi():
    for gid, g in genres.GENRES.items():
        assert g["image_model"] in ("zimage", "animagine"), gid
        assert "{description}" in g["portrait"] and "{prompt}" in g["keyframe"], gid
