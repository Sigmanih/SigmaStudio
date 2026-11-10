"""Soggetti ricorrenti che non sono persone: la sonda del video lungo cambiava a ogni clip."""
from pathlib import Path

import pytest

from core.modules.sigma_creative_lab.video import character_library as lib
from core.modules.sigma_creative_lab.video import genres


@pytest.fixture
def libreria(tmp_path, monkeypatch):
    monkeypatch.setattr(lib, "characters_dir", lambda: tmp_path / "personaggi")
    return tmp_path


def test_oggetto_ha_viste_e_prompt_da_oggetto(libreria):
    sonda = lib.create("Sonda", "gold-foil hexagonal space probe with one white dish antenna", kind="object")
    assert sonda["kind"] == "object" and set(lib.views_for(sonda)) == set(lib.OBJECT_VIEWS)
    testo = lib.view_prompt(sonda, "side", with_reference=True)
    assert "object in image 1" in testo and "face" not in testo
    persona = lib.create("Lia", "young woman with red hair")
    assert lib.kind_of(persona) == "person" and "face" in lib.view_prompt(persona, "profile", with_reference=True)
    with pytest.raises(ValueError):
        lib.create("X", "y", kind="animale")


def test_fotogramma_chiave_chiede_lo_stesso_oggetto(libreria, monkeypatch, tmp_path):
    from core.modules.sigma_creative_lab.video import image_gen
    monkeypatch.setattr(image_gen, "installed", lambda model: model == "klein")
    ref = tmp_path / "sonda.png"
    ref.write_bytes(b"png")
    prod = {"bible": {"genre": "realistic", "style": "photoreal space",
                      "characters": [{"name": "Sonda", "description": "gold probe", "ref_image": str(ref),
                                      "kind": "object"}]},
            "settings": {}}
    shot = {"prompt": "Sonda drifts past a comet", "refs": ["Sonda"]}
    model, prompt, refs = genres.keyframe_plan(prod, shot)
    assert model == "klein" and refs == [str(ref)]
    assert "Sonda is the object in image 1" in prompt and "same face" not in prompt
