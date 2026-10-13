# ==============================================================================
# tests/test_video_agents_and_tools.py — Test Ruoli e Tool Video Studio
# ==============================================================================
from pathlib import Path

import pytest

from core.harness.roles import DEV_ROLES
from core.modules.sigma_creative_lab.video import tools as video_tools
from core.modules.sigma_creative_lab.video.roles import (
    ROLE_FILM_DIRECTOR,
    ROLE_CHARACTER_DESIGNER,
    ROLE_SCRIPT_SUPERVISOR,
    ROLE_CINEMATOGRAPHER,
    ROLE_VISUAL_QA,
)


@pytest.fixture(autouse=True)
def setup_video_tools(monkeypatch, tmp_path):
    """Registra i tool e sposta personaggi e produzioni in una cartella temporanea: i test non toccano data/."""
    from core.modules.sigma_creative_lab.video import character_library, production
    monkeypatch.setattr(character_library, "characters_dir", lambda: tmp_path / "characters")
    monkeypatch.setattr(production.manager, "store", production.ProductionStore(tmp_path / "productions"))
    video_tools.registra()


def test_video_roles_registered():
    """Verifica che tutti i ruoli cinematografici siano presenti in DEV_ROLES."""
    expected_roles = [
        "video_producer",
        "film_director",
        "character_designer",
        "script_supervisor",
        "cinematographer",
        "visual_qa",
    ]
    for r_id in expected_roles:
        assert r_id in DEV_ROLES, f"Ruolo {r_id} non registrato in DEV_ROLES"
        role = DEV_ROLES[r_id]
        assert role.name
        assert role.system_prompt
        assert role.tools


def test_video_character_lifecycle(tmp_path):
    """Verifica creazione, consultazione, prompt di vista e rimozione di un personaggio."""
    char_name = "Test Hero Marcus"
    char_desc = "35 years old warrior, short black hair, deep green eyes, steel armor with gold trim"
    
    # Crea personaggio
    res_create = video_tools.esegui("video_char_create", {
        "name": char_name,
        "description": char_desc,
        "genre": "realistic",
        "voice_id": "voice_123",
    })
    assert res_create["success"] is True
    char_id = res_create["char_id"]
    assert char_id

    # Lista personaggi
    res_list = video_tools.esegui("video_char_list")
    assert res_list["success"] is True
    assert any(c["id"] == char_id for c in res_list["characters"])

    # Leggi singolo personaggio
    res_get = video_tools.esegui("video_char_get", {"char_id": char_id})
    assert res_get["success"] is True
    assert res_get["character"]["name"] == char_name
    assert res_get["character"]["voice_id"] == "voice_123"

    # Aggiorna personaggio
    res_update = video_tools.esegui("video_char_update", {
        "char_id": char_id,
        "notes": "Parla con voce profonda e calma",
    })
    assert res_update["success"] is True
    assert res_update["character"]["notes"] == "Parla con voce profonda e calma"

    # Calcola prompt per vista del model sheet
    res_prompt = video_tools.esegui("video_char_view_prompt", {
        "char_id": char_id,
        "view": "profile",
    })
    assert res_prompt["success"] is True
    assert "profile" in res_prompt["prompt"].lower() or "strict side view" in res_prompt["prompt"].lower()



def test_video_production_lifecycle():
    """Verifica creazione produzione, aggiunta inquadrature e aggiornamento shot."""
    prod_title = "La Notte delle Lanterne"
    prod_treatment = "Due viaggiatori attraversano una foresta nebbiosa cercando un antico tempio."

    # Crea produzione
    res_create = video_tools.esegui("video_prod_create", {
        "title": prod_title,
        "treatment": prod_treatment,
        "style": "Cinematic dark fantasy, misty atmosphere",
        "video_model": "ltx25",
    })
    assert res_create["success"] is True
    prod_id = res_create["prod_id"]
    assert prod_id

    # Lista produzioni
    res_list = video_tools.esegui("video_prod_list")
    assert res_list["success"] is True
    assert any(p["id"] == prod_id for p in res_list["productions"])

    # Leggi produzione
    res_get = video_tools.esegui("video_prod_get", {"prod_id": prod_id})
    assert res_get["success"] is True
    assert res_get["production"]["title"] == prod_title

    # Aggiungi inquadratura (Cut)
    res_shot1 = video_tools.esegui("video_prod_add_shot", {
        "prod_id": prod_id,
        "prompt": "Wide establishing shot of the foggy forest at dusk. Two travelers walk with a glowing brass lantern.",
        "seconds": 5.0,
        "transition": "cut",
        "scene": "Atto 1: La Foresta",
        "props": ["brass lantern"],
        "characters": ["Traveler 1", "Traveler 2"],
    })
    assert res_shot1["success"] is True
    assert res_shot1["shot_index"] == 0

    # Aggiorna inquadratura con correzione di continuity
    res_update_shot = video_tools.esegui("video_prod_update_shot", {
        "prod_id": prod_id,
        "shot_index": 0,
        "prompt": "Wide establishing shot. The brass lantern emits a steady warm yellow light without smoke.",
        "seconds": 6.0,
        "props": ["brass lantern with warm yellow light"],
    })
    assert res_update_shot["success"] is True
    assert res_update_shot["shot"]["duration_s"] == 6.0

    # Ispezione shot
    res_inspect = video_tools.esegui("video_inspect_shot", {
        "prod_id": prod_id,
        "shot_index": 0,
    })
    assert res_inspect["success"] is True
    assert res_inspect["shot"]["duration_s"] == 6.0

    # Timeline get
    res_tl = video_tools.esegui("video_timeline_get", {"prod_id": prod_id})
    assert res_tl["success"] is True
    assert "timeline" in res_tl



def test_video_tools_error_handling():
    """Verifica gestione errori per parametri non validi o risorse mancanti."""
    # Personaggio inesistente
    res_bad_char = video_tools.esegui("video_char_get", {"char_id": "non_existent_char_12345"})
    assert res_bad_char["success"] is False
    assert "non trovato" in res_bad_char["error"].lower()

    # Produzione inesistente
    res_bad_prod = video_tools.esegui("video_prod_get", {"prod_id": "non_existent_prod_12345"})
    assert res_bad_prod["success"] is False
    assert "non trovata" in res_bad_prod["error"].lower()

    # Tool inesistente
    res_bad_tool = video_tools.esegui("unknown_video_tool", {})
    assert res_bad_tool["success"] is False
    assert "sconosciuto" in res_bad_tool["error"].lower()


def test_creative_mcp_server_video_tools():
    """Verifica che CreativeMCPServer registri tutti i tool video tra i propri tool disponibili."""
    from core.modules.sigma_creative_lab.mcp_server import CreativeMCPServer
    server = CreativeMCPServer()
    tool_names = {t["name"] for t in server.list_tools()}
    assert "video_char_create" in tool_names
    assert "video_prod_create" in tool_names
    assert "video_judge_clip" in tool_names
    assert "video_timeline_get" in tool_names


# --- coerenza fra ruoli, schemi ed esecutori --------------------------------------

def test_ogni_tool_ha_schema_esecutore_e_permesso():
    import re
    from core.modules.sigma_creative_lab.video.roles import VIDEO_ROLES
    from core.modules.sigma_creative_lab.video.tool_schemas import SCHEMI
    schemi = {x["function"]["name"] for x in SCHEMI}
    assert schemi == set(video_tools.ESECUTORI)
    assert set(video_tools.ESECUTORI) == video_tools.READ_TOOLS | video_tools.WRITE_TOOLS
    kernel = set(re.findall(r'_f\("([a-z_]+)"', Path("core/harness/tool_schema.py").read_text(encoding="utf-8")))
    for role in VIDEO_ROLES:
        # Un ruolo che concede un tool senza schema lo fa promettere al modello senza darglielo.
        assert not [t for t in role.tools if t not in schemi and t not in kernel], role.id


# --- difetti corretti -------------------------------------------------------------

def _prod():
    return video_tools.esegui("video_prod_create", {"title": "Prova agenti", "treatment": "un faro"})["prod_id"]


def test_aggiunta_inquadratura_rispetta_la_durata():
    pid = _prod()
    r = video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "Mira walks", "seconds": 8.0,
                                                   "props": ["brass oil lamp"]})
    assert r["shot"]["duration_s"] == 8.0 and r["shot"]["props"] == ["brass oil lamp"]
    bad = video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "x", "transition": "dissolve"})
    assert bad["success"] is False


def test_props_entrano_nel_prompt_del_video():
    from core.modules.sigma_creative_lab.video.production import compose_prompt
    prompt = compose_prompt({"bible": {}, "settings": {}}, {"prompt": "Mira walks.", "props": ["brass oil lamp"]}, False)
    assert "brass oil lamp" in prompt


def test_render_avvia_davvero_il_runner(monkeypatch):
    from core.modules.sigma_creative_lab.video import production
    started = []
    monkeypatch.setattr(production.manager, "start", lambda pid, config=None: started.append(pid) or {"started": pid})
    monkeypatch.setattr(production.manager, "active", lambda: None)
    pid = _prod()
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "Mira walks"})
    r = video_tools.esegui("video_render_shot", {"prod_id": pid, "shot_index": 0})
    assert r["success"] and r["status"] == "started" and started == [pid]
    monkeypatch.setattr(production.manager, "active", lambda: {"production": pid})
    assert video_tools.esegui("video_render_shot", {"prod_id": pid, "shot_index": 0})["success"] is False


def test_giudice_usa_soglia_e_dispositivo_della_produzione(monkeypatch, tmp_path):
    from core.modules.sigma_creative_lab.video import clip_judge, production
    seen = {}

    def fake_judge(clip, intent, device="cpu", threshold=0.6, **_):
        seen.update(device=device, threshold=threshold, intent=intent)
        return {"ok": False, "score": 0.5, "issues": ["lamp floats"]}
    monkeypatch.setattr(clip_judge.judge, "judge", fake_judge)
    monkeypatch.setattr(production, "resolve_judge_device", lambda settings: "gpu:1")
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    pid = _prod()
    r = video_tools.esegui("video_judge_clip", {"clip_path": str(clip), "intent": "Mira walks", "camera": "dolly in",
                                                "prod_id": pid})
    assert r["passed"] is False and r["threshold"] == 0.6
    assert seen["device"] == "gpu:1" and "dolly in" in seen["intent"]


def test_correzione_del_qa_rimette_in_coda():
    pid = _prod()
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "Mira walks"})
    r = video_tools.esegui("video_shot_fix", {"prod_id": pid, "shot_index": 0, "fix": "the lamp stays in her hand"})
    assert r["shot"]["prompt_fixes"] == ["the lamp stays in her hand"] and r["shot"]["status"] == "pending"


def test_riepilogo_compatto_della_produzione():
    pid = _prod()
    for k in range(3):
        video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "x" * 2000})
    r = video_tools.esegui("video_prod_get", {"prod_id": pid})
    shots = r["production"]["shots"]
    assert len(shots) == 3 and all(len(sh["prompt"]) <= 300 for sh in shots) and "takes" not in shots[0]


def test_personaggio_dalla_libreria_alla_produzione(tmp_path):
    from PIL import Image
    from core.modules.sigma_creative_lab.video import character_library
    c = video_tools.esegui("video_char_create", {"name": "Beppe", "description": "old man"})["character"]
    no_ref = video_tools.esegui("video_char_to_production", {"char_id": c["id"], "prod_id": _prod()})
    assert no_ref["success"] is False                      # senza riferimento non serve a niente
    Image.new("RGB", (8, 8)).save(character_library._folder(c["id"]) / "front.png")
    char = character_library.get(c["id"])
    char["front"] = "front.png"
    character_library._write(char)
    pid = _prod()
    r = video_tools.esegui("video_char_to_production", {"char_id": c["id"], "prod_id": pid})
    assert r["success"] and r["name"] == "Beppe"
    chars = video_tools.esegui("video_prod_get", {"prod_id": pid})["production"]["bible"]["characters"]
    assert chars == [{"name": "Beppe", "description": "old man", "has_reference": True, "has_voice": False}]
