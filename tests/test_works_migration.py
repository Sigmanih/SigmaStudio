"""Trasloco delle creazioni da data/ a works/: copia senza cancellare e percorsi riscritti."""

import json
import sqlite3

import pytest

from core import paths, works_migration as W


@pytest.fixture
def radice(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    return tmp_path


def _produzione(radice):
    prod = radice / "data" / "creative" / "productions" / "faro_123456"
    prod.mkdir(parents=True)
    clip = prod / "clips" / "a.mp4"
    clip.parent.mkdir()
    clip.write_bytes(b"x")
    (prod / "production.json").write_text(json.dumps({
        "id": "faro_123456", "output_path": str(radice / "data" / "creative" / "video" / "faro.mp4"),
        "shots": [{"clip_path": str(clip), "prompt": "metadata/creative stays as it is"}],
        "bible": {"characters": [{"voice_sample": str(radice / "data" / "voices" / "nonno" / "sample.wav")}]},
    }), encoding="utf-8")
    return prod


def test_prima_del_trasloco_si_legge_la_cartella_storica(radice):
    (radice / "data" / "creative").mkdir(parents=True)
    assert paths.creative_dir() == radice / "data" / "creative"
    assert paths.works_area("voci", legacy="voices") == radice / "works" / "voci"   # nessuna storica: nuova
    assert paths.public_url(radice / "works" / "voci" / "a.wav") == "/works/voci/a.wav"
    assert paths.public_url(radice / "config" / "x.json") == ""


def test_trasloco_copia_e_riscrive(radice):
    _produzione(radice)
    (radice / "data" / "voices" / "nonno").mkdir(parents=True)
    (radice / "data" / "voices" / "nonno" / "sample.wav").write_bytes(b"w")
    db = radice / "data" / "creative" / "creative_assets.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE assets (asset_id TEXT, files TEXT, thumbnail TEXT)")
        conn.execute("INSERT INTO assets VALUES ('a', ?, 'data/creative/assets/a/thumb.png')",
                     (json.dumps({"image": "data\\creative\\assets\\a\\image.png"}),))
    assert [v["fatto"] for v in W.piano()] == [False, False]
    W.esegui()
    nuovo = radice / "works" / "creative" / "productions" / "faro_123456" / "production.json"
    prod = json.loads(nuovo.read_text(encoding="utf-8"))
    assert prod["shots"][0]["clip_path"].startswith(str(radice / "works" / "creative"))
    assert prod["output_path"] == str(radice / "works" / "creative" / "video" / "faro.mp4")
    assert prod["bible"]["characters"][0]["voice_sample"] == str(radice / "works" / "voci" / "nonno" / "sample.wav")
    assert prod["shots"][0]["prompt"] == "metadata/creative stays as it is"        # solo prefissi interi
    with sqlite3.connect(radice / "works" / "creative" / "creative_assets.db") as conn:
        files, thumb = conn.execute("SELECT files, thumbnail FROM assets").fetchone()
    assert json.loads(files)["image"] == "works\\creative\\assets\\a\\image.png"
    assert thumb == "works/creative/assets/a/thumb.png"
    # Gli originali restano: in data/ non si cancella niente.
    assert (radice / "data" / "creative" / "productions" / "faro_123456" / "production.json").is_file()
    assert paths.creative_dir() == radice / "works" / "creative"


def test_secondo_trasloco_non_sovrascrive(radice):
    _produzione(radice)
    W.esegui()
    marker = radice / "works" / "creative" / "nuovo.txt"
    marker.write_text("lavoro fatto dopo il trasloco", encoding="utf-8")
    esito = W.esegui()
    assert str(radice / "works" / "creative") in esito["saltate"] and marker.is_file()
