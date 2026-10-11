"""Produzioni video lunghe: storyboard, dipendenze fra inquadrature, corsie, ripresa."""

import asyncio
import json

import pytest

from core.modules.sigma_creative_lab.video import production as prod_mod
from core.modules.sigma_creative_lab.video.production import (
    ClipEngine, ProductionRunner, ProductionStore, compose_prompt, extract_json, h3_frames,
    new_shot, plan_storyboard,
)


def test_frame_h3_sulla_griglia_17k_piu_5():
    for seconds in (0.1, 1, 2.33, 4, 5, 5.2, 10):
        n = h3_frames(seconds)
        assert (n - 5) % 17 == 0 and 5 <= n <= 124
    assert h3_frames(5.2) == 124
    assert h3_frames(10) == 124          # oltre il massimo si scende di 17 in 17


def test_estrazione_json_robusta():
    assert extract_json('Ecco:\n```json\n[{"a": 1}]\n```\nfine') == [{"a": 1}]
    assert extract_json('<think>ragiono [1]</think> risposta {"x": 2}') == {"x": 2}
    with pytest.raises(ValueError):
        extract_json("nessun json")


def test_storyboard_gerarchico_con_llm_finto():
    calls = []

    def fake(messages, max_tokens):
        calls.append(messages[0]["content"])
        if len(calls) == 1:
            return json.dumps([{"title": "Alba", "summary": "il gatto si sveglia", "seconds": 10},
                               {"title": "Onda", "summary": "il gatto surfa", "seconds": 10}])
        return json.dumps([
            {"prompt": "close-up of a kitten waking up", "audio": "birds", "seconds": 4,
             "transition": "continue", "characters": ["Micio"]},
            {"prompt": "kitten stretches", "seconds": 4, "transition": "continue", "characters": ["Altro"]},
        ])

    shots = plan_storyboard("Un gatto surfista", minutes=20 / 60, style="cinematic",
                            characters=[{"name": "Micio", "description": "silver tabby"}], generate=fake)
    assert len(calls) == 3                      # una richiesta per le scene, una per scena
    assert len(shots) == 4
    assert shots[0]["transition"] == "cut"      # ogni scena comincia con un taglio
    assert shots[1]["transition"] == "continue"
    assert shots[0]["refs"] == ["Micio"]        # personaggi sconosciuti scartati
    assert shots[1]["refs"] == []
    assert all(3.0 <= s["duration_s"] <= 5.0 for s in shots)


def test_prompt_composto_con_bibbia_e_riferimenti():
    prod = {"bible": {"style": "35mm film look", "audio_style": "ambient synth",
                      "characters": [{"name": "Ada", "description": "red coat", "ref_image": "ada.png"}]}}
    shot = new_shot("Ada walks in the rain", refs=["Ada"], audio="rain on asphalt")
    text = compose_prompt(prod, shot, use_refs=True)
    assert "35mm film look." in text and "<Picture 1>" in text and "red coat" in text
    assert text.endswith("Audio: ambient synth rain on asphalt")
    assert "<Picture" not in compose_prompt(prod, shot, use_refs=False)


class FakeEngine(ClipEngine):
    name = "fake"

    def __init__(self, tmp, fail_ids=(), delay=0.0):
        self.tmp, self.fail_ids, self.delay = tmp, set(fail_ids), delay
        self.calls = []

    async def render(self, prod, shot, request, progress=None):
        self.calls.append((shot["id"], request))
        await asyncio.sleep(self.delay)
        if shot["id"] in self.fail_ids:
            raise RuntimeError("OOM simulato")
        clip = self.tmp / f"{shot['id']}.mp4"
        clip.write_bytes(b"x")
        last = self.tmp / f"{shot['id']}.png"
        last.write_bytes(b"x")
        if progress:
            progress({"progress": 100})
        return {"clip_path": str(clip), "last_frame": str(last), "frames": request["frames"], "timings": {"total_s": 1}}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(prod_mod.paths, "creative_output_dir", lambda kind="image": tmp_path / "out")
    return ProductionStore(tmp_path / "prods")


def make(store, shots, **settings):
    # Il motore finto non produce video veri: QA, colore e giudice hanno test propri.
    settings = {"qa": False, "color_match": False, "judge": False, **settings}
    return store.create("Prova", settings=settings, shots=[new_shot(**s) for s in shots])


def test_continue_usa_ultimo_frame_e_catena_limitata(store, tmp_path):
    prod = make(store, [{"prompt": "a", "id": "s0"}] + [{"prompt": f"c{i}", "transition": "continue", "id": f"s{i}"}
                                                       for i in range(1, 4)], max_chain=2)
    engine = FakeEngine(tmp_path)
    runner = ProductionRunner(store, prod["id"], engine=engine)
    result = asyncio.run(runner.run(assemble_at_end=False))
    assert result["status"] == "rendered"
    req = {sid: r for sid, r in engine.calls}
    assert req["s0"]["init_image"] == ""
    assert req["s1"]["init_image"].endswith("s0.png") and req["s1"]["continued"]
    assert req["s2"]["init_image"].endswith("s1.png")
    # Terza continuazione oltre max_chain=2: diventa un taglio, la deriva non si accumula.
    assert req["s3"]["init_image"] == "" and not req["s3"]["continued"]


def test_fallimento_e_ripresa(store, tmp_path):
    prod = make(store, [{"prompt": "a", "id": "s0"}, {"prompt": "b", "id": "s1"}], max_attempts=1)
    result = asyncio.run(ProductionRunner(store, prod["id"], engine=FakeEngine(tmp_path, fail_ids={"s1"})).run(False))
    assert result["status"] == "partial"
    assert [s["status"] for s in result["shots"]] == ["done", "failed"]
    # Ripresa: il clip gia' fatto non si rigenera.
    fixed = store.get(prod["id"])
    fixed["shots"][1]["status"] = "pending"
    store.save(fixed)
    engine = FakeEngine(tmp_path)
    result = asyncio.run(ProductionRunner(store, prod["id"], engine=engine).run(False))
    assert result["status"] == "rendered"
    assert [sid for sid, _ in engine.calls] == ["s1"]


def test_due_corsie_in_parallelo_rispettano_le_catene(store, tmp_path):
    shots = [{"prompt": "a", "id": "a0"}, {"prompt": "a1", "transition": "continue", "id": "a1"},
             {"prompt": "b", "id": "b0"}, {"prompt": "c", "id": "c0"}]
    prod = make(store, shots)
    fast, slow = FakeEngine(tmp_path, delay=0.02), FakeEngine(tmp_path, delay=0.05)
    runner = ProductionRunner(store, prod["id"])
    runner.lanes = lambda p: [{"engine": fast, "label": "fast", "devices": []},
                              {"engine": slow, "label": "slow", "devices": []}]
    result = asyncio.run(runner.run(assemble_at_end=False))
    assert result["status"] == "rendered"
    done_by = {s["id"]: s["lane"] for s in result["shots"]}
    assert set(done_by.values()) == {"fast", "slow"}
    # a0 apre una catena: la corsia lenta non la prende.
    assert done_by["a0"] == "fast"
    a1 = next(r for sid, r in fast.calls + slow.calls if sid == "a1")
    assert a1["continued"] and a1["init_image"].endswith("a0.png")


def test_inquadratura_rimasta_in_render_si_riprende(store, tmp_path):
    prod = make(store, [{"prompt": "a", "id": "s0"}])
    prod["shots"][0]["status"] = "rendering"          # come dopo un crash
    store.save(prod)
    result = asyncio.run(ProductionRunner(store, prod["id"], engine=FakeEngine(tmp_path)).run(False))
    assert result["shots"][0]["status"] == "done"


def test_id_produzione_validato(store):
    with pytest.raises(ValueError):
        store.get("../../config")


class BrokenEngine(ClipEngine):
    """Motore che si guasta sempre (avvio fallito, istanza bloccata)."""
    name = "broken"

    def __init__(self):
        self.calls = 0

    async def render(self, prod, shot, request, progress=None):
        self.calls += 1
        raise prod_mod.EngineError("ComfyUI non disponibile")


def test_guasto_del_motore_non_consuma_tentativi_e_la_corsia_si_ritira(store, tmp_path, monkeypatch):
    # Pause fra un guasto e l'altro azzerate: il test misura la logica, non l'attesa.
    real_sleep = asyncio.sleep
    monkeypatch.setattr(prod_mod.asyncio, "sleep", lambda s, *a, **k: real_sleep(0))
    prod = make(store, [{"prompt": f"s{i}", "id": f"s{i}"} for i in range(4)], max_attempts=1)
    good, broken = FakeEngine(tmp_path, delay=0.01), BrokenEngine()
    runner = ProductionRunner(store, prod["id"])
    # La corsia guasta e' la piu' veloce: prende lavoro subito e deve cederlo.
    runner.lanes = lambda p: [{"engine": broken, "label": "guasta", "devices": []},
                              {"engine": good, "label": "sana", "devices": [], "assumed_ratio": 1.0}]
    result = asyncio.run(runner.run(assemble_at_end=False))
    assert result["status"] == "rendered"
    assert broken.calls == prod_mod.MAX_LANE_FAILURES
    assert all(s["status"] == "done" and s["lane"] == "sana" for s in result["shots"])
    # Con max_attempts=1 un tentativo consumato dal guasto avrebbe fatto fallire l'inquadratura.
    assert all(s["attempts"] == 1 for s in result["shots"])


# --- storyboard: correzioni a cio' che un LLM vero sbaglia ---------------------

def test_stile_ripetuto_tolto_dal_prompt():
    from core.modules.sigma_creative_lab.video.production import _strip_style
    style = "Black and white woodcut-style illustration"
    assert _strip_style("A wide shot of the sea, black and white woodcut-style illustration", style) == \
        "A wide shot of the sea"
    assert _strip_style("He waves. Black and white woodcut-style illustration with high contrast.", style) == "He waves."
    assert _strip_style("No style here.", style) == "No style here."


def test_continue_declassato_se_cambia_ripresa():
    from core.modules.sigma_creative_lab.video.production import _normalize_shots
    chars = [{"name": "Keeper"}, {"name": "Fisher"}]
    shots = _normalize_shots([
        {"prompt": "Keeper walks up the stairs", "seconds": 4, "characters": ["keeper"]},
        {"prompt": "He keeps climbing", "seconds": 4, "transition": "continue", "characters": ["Keeper"]},
        {"prompt": "A close-up of his hands", "seconds": 4, "transition": "continue", "characters": ["Keeper"]},
        {"prompt": "The fishermen wave", "seconds": 4, "transition": "continue", "characters": ["Fisher"]},
    ], 16, (3.0, 5.0), chars, "s")
    assert shots[0]["refs"] == ["Keeper"]                 # nome canonico della bibbia
    assert [s["transition"] for s in shots] == ["cut", "continue", "cut", "cut"]


def test_scena_troppo_lunga_accorciata():
    from core.modules.sigma_creative_lab.video.production import _normalize_shots
    items = [{"prompt": f"azione {i}", "seconds": 5} for i in range(6)]          # 30 s per una scena da 12
    shots = _normalize_shots(items, 12, (3.0, 5.0), [], "s")
    assert sum(s["duration_s"] for s in shots) <= 12 * 1.15
    assert all(s["duration_s"] >= 3.0 for s in shots)


def test_corsia_lenta_aiuta_se_la_veloce_e_gia_occupata(store):
    # Caso reale (prova del 2026-10-11): 5070 Ti su s0, s1 e s2 in coda, 5060 ferma.
    prod = make(store, [{"prompt": "a", "id": "s0"}, {"prompt": "b", "id": "s1", "transition": "continue"},
                        {"prompt": "c", "id": "s2"}])
    fast = {"label": "veloce"}
    slow = {"label": "lenta", "assumed_ratio": 2.0}
    prod["shots"][0].update(status="rendering", lane="veloce")
    runner = ProductionRunner(store, prod["id"], engine=FakeEngine(None))
    assert runner._pick(prod, slow, fast) == 2           # prende il taglio, non apre la catena di s0
    prod["shots"][0].update(status="done", lane="veloce")
    prod["shots"][1].update(status="done")
    assert runner._pick(prod, slow, fast) is None        # resta un solo clip: lo chiude prima la veloce
