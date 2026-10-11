"""Giudice visivo delle clip: punteggio, correzioni del prompt, scelta del tentativo migliore."""

import asyncio

from core.modules.sigma_creative_lab.video import clip_judge
from core.modules.sigma_creative_lab.video import production as prod_mod
from core.modules.sigma_creative_lab.video.clip_judge import _extract_json, verdict_from
from core.modules.sigma_creative_lab.video.production import (
    MOTION_GUARD, add_prompt_fix, best_judged, compose_prompt, judge_clip,
)


def test_conta_l_anello_piu_debole():
    v = verdict_from({"intent_match": 1.0, "motion_natural": 0.2, "anatomy_ok": True, "issues": ["walks backwards"]})
    assert v["score"] == 0.2 and not v["ok"]
    v = verdict_from({"intent_match": 0.9, "motion_natural": 0.8, "anatomy_ok": False})
    assert v["score"] == round(0.8 * 0.7, 3) and not v["ok"]
    assert verdict_from({"intent_match": 0.9, "motion_natural": 0.8})["ok"]


def test_valori_sporchi_non_rompono_il_verdetto():
    v = verdict_from({"intent_match": "abc", "motion_natural": 7, "issues": ["", " ", "x"]})
    assert v["intent_match"] == 0.0 and v["motion_natural"] == 1.0
    assert v["issues"] == ["x"]


def test_json_fra_ragionamento_e_prosa():
    assert _extract_json('<think>{"no": 1}</think> Ecco: {"questions": ["a"]} fine') == {"questions": ["a"]}


def test_correzioni_del_prompt_senza_doppioni_e_limitate():
    shot = {}
    for fix in ("Face the steps.", "Face the steps.", "Hold the lamp.", "Step upward."):
        add_prompt_fix(shot, {"prompt_fix": fix})
    assert shot["prompt_fixes"] == ["Hold the lamp.", "Step upward."]
    add_prompt_fix(shot, {"prompt_fix": ""})
    assert len(shot["prompt_fixes"]) == 2


def test_il_prompt_porta_correzioni_e_guardia_del_movimento():
    prod = {"bible": {"style": "woodcut"}, "settings": {"motion_guard": True}}
    shot = {"prompt": "The keeper climbs the stairs", "prompt_fixes": ["He faces the steps"]}
    text = compose_prompt(prod, shot, False)
    assert "He faces the steps." in text and MOTION_GUARD in text
    assert text.index("The keeper climbs") < text.index("He faces the steps")
    prod["settings"]["motion_guard"] = False
    assert MOTION_GUARD not in compose_prompt(prod, shot, False)


def test_migliore_tentativo():
    shot = {"judge_history": [{"clip_path": "a", "score": 0.3}, {"clip_path": "b", "score": 0.55},
                              {"clip_path": "c", "score": None}]}
    assert best_judged(shot)["clip_path"] == "b"
    assert best_judged({}) is None


def test_giudice_spento_o_assente_non_blocca(monkeypatch, tmp_path):
    shot = {"id": "s1"}
    prod = {"settings": {"judge": False}}
    assert asyncio.run(judge_clip(prod, shot, tmp_path / "x.mp4", "azione")) is None
    monkeypatch.setattr(clip_judge, "installed", lambda: False)
    prod["settings"]["judge"] = True
    assert asyncio.run(judge_clip(prod, shot, tmp_path / "x.mp4", "azione")) is None
    assert "judge_history" not in shot


def test_giudizio_registrato_nella_storia(monkeypatch, tmp_path):
    monkeypatch.setattr(clip_judge, "installed", lambda: True)
    monkeypatch.setattr(clip_judge.judge, "judge", lambda *a, **k: verdict_from(
        {"intent_match": 0.1, "motion_natural": 0.1, "seen": "walks away", "prompt_fix": "walk toward"}))
    shot = {"id": "s1", "seed": 5}
    v = asyncio.run(judge_clip({"settings": {}}, shot, tmp_path / "x.mp4", "walks toward the door"))
    assert not v["ok"]
    assert shot["judge_history"][0]["clip_path"] == str(tmp_path / "x.mp4")
    assert shot["judge_history"][0]["seed"] == 5


def test_errore_del_giudice_non_ferma_la_produzione(monkeypatch, tmp_path):
    monkeypatch.setattr(clip_judge, "installed", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("llama-server morto")
    monkeypatch.setattr(clip_judge.judge, "judge", boom)
    assert asyncio.run(judge_clip({"settings": {}}, {"id": "s"}, tmp_path / "x.mp4", "azione")) is None


def test_tentativi_su_file_distinti(tmp_path):
    store = prod_mod.ProductionStore(tmp_path)
    prod = store.create("t", settings={})
    prod["shots"] = [prod_mod.new_shot("a man walks", 4.0)]
    runner = prod_mod.ProductionRunner(store, prod["id"], engine=prod_mod.ClipEngine())
    first = runner.build_request(prod, 0)["output_path"]
    prod["shots"][0]["attempts"] = 1
    second = runner.build_request(prod, 0)["output_path"]
    assert first != second and second.endswith("_a2.mp4")


# --- upscale: il montaggio non deve mai fallire per colpa di Real-ESRGAN ------

def test_upscale_lanczos_o_non_installato_usa_l_originale(monkeypatch, tmp_path):
    from core.modules.sigma_creative_lab.video import postprocess as pp
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    monkeypatch.setattr(pp, "esrgan_ready", lambda: True)
    assert pp.upscaled_source(clip, 1080, {"upscaler": "lanczos"}) == clip
    assert pp.upscaled_source(clip, 0, {}) == clip
    monkeypatch.setattr(pp, "esrgan_ready", lambda: False)
    assert pp.upscaled_source(clip, 1080, {}) == clip


def test_upscale_in_errore_ripiega_sull_originale(monkeypatch, tmp_path):
    from core.modules.sigma_creative_lab.video import postprocess as pp
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    monkeypatch.setattr(pp, "esrgan_ready", lambda: True)
    monkeypatch.setattr(pp, "_ff", lambda: (None, None, lambda p: {"height": 480}))

    def boom(*a, **k):
        raise RuntimeError("CUDA out of memory")
    monkeypatch.setattr(pp, "upscale_esrgan", boom)
    assert pp.upscaled_source(clip, 1080, {}) == clip
    # Gia' alla misura richiesta: nessun upscale.
    assert pp.upscaled_source(clip, 480, {}) == clip


def test_regole_si_no_decidono_la_bocciatura():
    # Azione assente: bocciata anche con quality alta.
    assert not verdict_from({"main_action_happens": False, "quality": 0.95})["ok"]
    # Direzione sbagliata o fisica impossibile: bocciata.
    assert verdict_from({"main_action_happens": True, "wrong_direction": True, "quality": 0.9})["score"] <= 0.2
    assert not verdict_from({"main_action_happens": True, "physically_impossible": "true"})["ok"]
    # Solo la camera diversa dal richiesto: passa, anche se quality e' bassa.
    v = verdict_from({"main_action_happens": True, "camera_as_requested": False, "quality": 0.2})
    assert v["ok"] and not v["camera_ok"]
    # Anatomia deformata con il resto giusto: non scatta il minimo garantito.
    assert verdict_from({"main_action_happens": True, "anatomy_ok": False, "quality": 0.7})["score"] < 0.6


# --- giudizio in parallelo ai render -------------------------------------------

def test_la_corsia_non_aspetta_il_giudice(monkeypatch, tmp_path):
    """Mentre il giudice guarda s0, la corsia rende s1; s0 bocciata torna in coda e si rifa'."""
    from core.modules.sigma_creative_lab.video.production import ClipEngine, ProductionRunner, ProductionStore, new_shot

    class Engine(ClipEngine):
        name = "fake"

        def __init__(self):
            self.calls = []

        async def render(self, prod, shot, request, progress=None):
            self.calls.append(shot["id"])
            await asyncio.sleep(0.01)
            clip = tmp_path / f"{shot['id']}_{len(self.calls)}.mp4"
            clip.write_bytes(b"x")
            return {"clip_path": str(clip), "frames": request["frames"]}

    judged = []

    async def fake_judge(prod, shot, clip, intent, *a, **k):
        judged.append(shot["id"])
        await asyncio.sleep(0.2)                    # il giudice e' lento: la corsia intanto lavora
        ok = not (shot["id"] == "s0" and judged.count("s0") == 1)
        return {"ok": ok, "score": 0.9 if ok else 0.2, "issues": [] if ok else ["walks backwards"],
                "seen": "", "prompt_fix": "" if ok else "walk forward, facing the steps"}

    monkeypatch.setattr(prod_mod, "judge_clip", fake_judge)
    monkeypatch.setattr(clip_judge, "installed", lambda: True)
    monkeypatch.setattr(prod_mod, "extract_last_frame", lambda clip: None)
    store = ProductionStore(tmp_path / "prods")
    prod = store.create("Prova", settings={"qa": False, "color_match": False, "judge": True, "max_attempts": 3},
                        shots=[new_shot("a", id="s0"), new_shot("b", id="s1")])
    engine = Engine()
    result = asyncio.run(ProductionRunner(store, prod["id"], engine=engine).run(False))
    assert engine.calls[:2] == ["s0", "s1"]          # s1 parte senza aspettare il giudizio di s0
    assert engine.calls.count("s0") == 2
    assert all(s["status"] == "done" for s in result["shots"])
    assert result["shots"][0]["prompt_fixes"] == ["walk forward, facing the steps"]


def test_oggetti_tenuti_in_mano_dal_prompt():
    from core.modules.sigma_creative_lab.video.clip_judge import held_objects
    assert held_objects("He keeps climbing, the oil lamp held in his right hand.") == ["oil lamp"]
    # Il caso che la prima regola sbagliava: l'oggetto viene dopo un'altra azione.
    assert held_objects("The keeper walks up, his left hand sliding along the railing and the oil lamp "
                        "held in his right hand.") == ["oil lamp"]
    assert held_objects("The keeper climbs the staircase holding an oil lamp") == ["oil lamp"]
    assert held_objects("He wipes the lens, holding a cloth in his left hand") == ["cloth"]
    assert held_objects("A lighthouse on a cliff at night") == []


def test_giudice_su_gpu_preferisce_l_8b(monkeypatch, tmp_path):
    for folder, model, mmproj in clip_judge.MODELS:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / model).write_bytes(b"x")
        (tmp_path / folder / mmproj).write_bytes(b"x")
    monkeypatch.setattr(clip_judge.paths, "models_dir", lambda: tmp_path)
    assert "8B" in clip_judge.model_files("gpu:1")[0].name
    assert "30B" in clip_judge.model_files("cpu")[0].name
