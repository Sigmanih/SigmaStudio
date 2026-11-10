"""Video lungo generato guidato solo dai tool della chat: impostazioni, scarto, revisione a lotti, montaggio.

Il motore video e i modelli di visione sono finti; ffmpeg e' vero, perche' le correzioni
di montaggio (dissolvenze, clip al contrario, volume) sono proprio comandi ffmpeg.
"""
import asyncio
from pathlib import Path

import pytest

from core.modules.sigma_creative_lab.video import finishing
from core.modules.sigma_creative_lab.video import generated_publication as gp
from core.modules.sigma_creative_lab.video import production as prod_mod
from core.modules.sigma_creative_lab.video import tools as video_tools
from core.modules.sigma_creative_lab.video import visual_integrity as vi
from core.modules.sigma_creative_lab.video.manual_review import fingerprint
from core.modules.sigma_creative_lab.video.production import (ClipEngine, ProductionManager, ProductionRunner,
                                                              ProductionStore)


def _ffmpeg_ok() -> bool:
    try:
        prod_mod.ffmpeg_bin()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _ffmpeg_ok(), reason="ffmpeg non disponibile")

CLIP_S = 2.0


class ClipFinte(ClipEngine):
    """Clip vere e piccole (testsrc con un tono), una per inquadratura; quelle in `rotte` falliscono."""
    name = "finto"

    def __init__(self, cartella: Path, rotte=()):
        self.cartella, self.rotte, self.chiamate = cartella, set(rotte), []

    async def render(self, prod, shot, request, progress=None):
        self.chiamate.append((shot["id"], request))
        if shot["id"] in self.rotte:
            raise RuntimeError("OOM simulato")
        out = Path(request["output_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        freq = 300 + 100 * len(self.chiamate)
        prod_mod._run([prod_mod.ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i",
                       f"testsrc=size=320x192:rate=24:duration={CLIP_S}", "-f", "lavfi", "-i",
                       f"sine=frequency={freq}:sample_rate=48000:duration={CLIP_S}", "-c:v", "libx264",
                       "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)])
        return {"clip_path": str(out), "last_frame": "", "frames": int(CLIP_S * 24), "timings": {"total_s": 1}}


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    store = ProductionStore(tmp_path / "prods")
    manager = ProductionManager(store)
    monkeypatch.setattr(prod_mod, "manager", manager)
    monkeypatch.setattr(prod_mod.paths, "creative_output_dir", lambda kind="image": tmp_path / "out")
    motore = ClipFinte(tmp_path / "clips", rotte={"rotta"})

    # Il render parte nello stesso thread: il test vede lo stato a giro finito.
    monkeypatch.setattr(video_tools, "_start_render",
                        lambda pid: asyncio.run(ProductionRunner(store, pid, engine=motore).run()))

    from core.modules.sigma_creative_lab.video import clip_judge
    from core.modules.sigma_creative_lab.video import postprocess as pp
    monkeypatch.setattr(clip_judge, "installed", lambda: True)
    monkeypatch.setattr(pp, "quality_check", lambda clip, *a, **k: [])
    monkeypatch.setattr(prod_mod, "resolve_judge_device", lambda s: "cpu")

    async def giudice(prod, shot, clip, intent, *a, **k):
        shot["judge"] = {"ok": True, "score": 0.9, "seen": "space probe drifting", "issues": []}
        return shot["judge"]
    monkeypatch.setattr(prod_mod, "judge_clip", giudice)
    monkeypatch.setattr(vi, "inspect_clip", lambda clip, device="cpu", evidence_dir=None: {
        "status": "pass", "version": vi.VERSION, "sha256": fingerprint(clip), "kind": "video", "frames": [],
        "evidence": [], "issues": [], "sampled_frames": 8})
    monkeypatch.setattr(gp, "create_package", lambda prod, directory, ask_text, progress=None: {
        "status": "ready", "publication_ready": True, "package_path": str(Path(directory) / "youtube_package.json"),
        "source": gp.source_identity(prod, prod["output_path"])})
    return store, motore


MOTIVO = "Provino guardato: sonda intera, nessun oggetto staccato, luce e continuita' coerenti."


def _decidi(store, pid, **extra_per_id):
    coda = video_tools.esegui("video_review_queue", {"prod_id": pid})
    assert coda["success"], coda
    for it in coda["items"]:
        assert Path(it["contact_sheet"]).is_file()
    decisioni = [{"shot_id": it["shot_id"], "verdict": "approve", "sha256": it["sha256"],
                  **extra_per_id.get(it["shot_id"], {})} for it in coda["items"]]
    return coda, video_tools.esegui("video_review_batch", {"prod_id": pid, "decisions": decisioni,
                                                           "reason": MOTIVO, "confirmed": True})


def test_video_lungo_dalla_chat_fino_alla_pubblicazione(ambiente):
    store, motore = ambiente
    creata = video_tools.esegui("video_prod_create", {
        "title": "Sonda nel cosmo", "treatment": "Una sonda attraversa galassie e comete.",
        "style": "photorealistic space documentary", "negative": "text, watermark",
        "settings": {"width": 448, "height": 256, "max_clip_seconds": 10}})
    assert creata["success"], creata
    pid = creata["prod_id"]

    bocciata = video_tools.esegui("video_prod_settings", {"prod_id": pid, "settings": {"warp_speed": 9}})
    assert not bocciata["success"] and "crossfade_s" in bocciata["accepted_keys"]
    assert not video_tools.esegui("video_prod_settings", {"prod_id": pid, "settings": {"output_height": 1234}})["success"]
    imp = video_tools.esegui("video_prod_settings", {"prod_id": pid, "settings": {
        "resolution": "448x256", "output_height": 720, "upscaler": "esrgan", "judge_mode": "advise", "seed": 42,
        "motion_guard": False, "crossfade_s": 0.5, "loudnorm_lufs": -16, "max_attempts": 1,
        "color_match": False}})
    assert imp["success"], imp
    assert imp["changed"]["width"] == 448 and imp["changed"]["crossfade_s"] == 0.5

    bib = video_tools.esegui("video_prod_bible", {"prod_id": pid, "negative": "text, watermark, people",
                                                  "audio_style": "ambient space drones"})
    assert bib["success"]

    for sid, transition in (("s0", "cut"), ("s1", "continue"), ("rotta", "cut"), ("s3", "cut")):
        r = video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": f"probe shot {sid}",
                                                       "seconds": CLIP_S, "transition": transition,
                                                       "start_frame_prompt": f"still frame of {sid}"})
        assert r["success"], r
        p = store.get(pid)
        p["shots"][-1]["id"] = sid           # id leggibili per il motore finto
        store.save(p)
    upd = video_tools.esegui("video_prod_update_shot", {"prod_id": pid, "shot_index": 3,
                                                        "start_frame_prompt": "probe above a comet, still"})
    assert upd["success"] and store.get(pid)["shots"][3]["start_frame_prompt"] == "probe above a comet, still"

    # Primo giro: le teste di ripresa aspettano la revisione, l'anello di catena aspetta la sua testa.
    assert video_tools.esegui("video_render", {"prod_id": pid})["success"]
    p = store.get(pid)
    assert p["status"] == "partial"
    assert [s["status"] for s in p["shots"]] == ["review_required", "pending", "failed", "review_required"]
    assert p["bible"]["negative"] == "text, watermark, people"
    assert motore.chiamate[0][1]["negative_prompt"] == "text, watermark, people"

    # Revisione a lotti: s3 era un'alba resa come tramonto, si monta al contrario.
    coda, esito = _decidi(store, pid, s3={"reverse": True})
    assert {it["shot_id"] for it in coda["items"]} == {"s0", "s3"}
    assert esito["success"] and esito["render_started"], esito
    p = store.get(pid)
    assert p["shots"][1]["status"] == "review_required"       # la catena e' ripartita da sola
    assert p["shots"][3]["reverse"] is True and p["shots"][3]["status"] == "done"
    s1_req = next(r for sid, r in motore.chiamate if sid == "s1")
    assert s1_req["continued"] and s1_req["init_image"].endswith(".last.png")

    # La clip rotta resterebbe failed per sempre: si scarta.
    skip = video_tools.esegui("video_prod_skip_shot", {"prod_id": pid, "shot_index": 2, "reason": "OOM ripetuto"})
    assert skip["success"] and skip["production"]["shots_skipped"] == 1

    _coda, esito = _decidi(store, pid)
    assert esito["success"], esito
    p = store.get(pid)
    assert p["status"] == "done", (p["status"], p.get("error"))
    assert p["publication"]["publication_ready"] is True
    assert p["loudness"]["target_lufs"] == -16
    film = Path(p["output_path"])
    info = prod_mod.probe(film)
    assert info["height"] == 720
    # Niente dissolvenza dentro la catena s0-s1, una fra s1 e s3; s1 perde il fotogramma doppio.
    atteso = CLIP_S + (CLIP_S - 1 / 24) + CLIP_S - 0.5
    assert abs(info["duration"] - atteso) < 0.15, info
    # La musica si compone su queste durate: la somma e' la lunghezza del film.
    assert abs(sum(sec for _sh, sec in finishing.montage_durations(p)) - atteso) < 0.05


def test_guadagno_notturno_taglia_solo_dopo_sette_secondi():
    fps = 24
    # Primo secondo a 46 (30 sopra il nero), poi discesa lineare fino a 16 in 12 secondi.
    luma = [46.0] * fps + [46.0 - 30.0 * k / (12 * fps) for k in range(12 * fps)]
    plan = finishing.night_gain_plan(luma, fps)
    assert plan["cut_s"] is not None and plan["cut_s"] >= finishing.NIGHT_MIN_SECONDS
    assert all(1.0 <= g <= finishing.NIGHT_GAIN_CAP for _t, g in plan["points"])
    # Una notte che si scurisce presto resta lunga almeno 7 s, col guadagno al tetto.
    presto = [46.0] * fps + [17.0] * (9 * fps)
    p2 = finishing.night_gain_plan(presto, fps)
    assert p2["cut_s"] >= finishing.NIGHT_MIN_SECONDS
    assert max(g for _t, g in p2["points"]) == finishing.NIGHT_GAIN_CAP
    assert "if(lt(t," in finishing.gain_expression(plan["points"])


def test_dissolvenze_mai_dentro_le_catene():
    shots = [{"transition": "cut"}, {"transition": "continue"}, {"transition": "cut"}, {"transition": "cut"}]
    assert finishing.fade_boundaries(shots, 1.0, [10, 10, 10, 1.2]) == [0.0, 1.0, 0.35, 0.0]
    # Un anello reso come taglio (precedente scartata) puo' sfumare.
    shots[1]["continued"] = False
    assert finishing.fade_boundaries(shots, 1.0, [10, 10, 10, 10])[0] == 1.0


def test_nome_del_modello_video_normalizzato(ambiente):
    # Collaudo della sonda: "LTX-2.5" passava e il runner rendeva con H3 (9 minuti per clip).
    creata = video_tools.esegui("video_prod_create", {"title": "Sonda", "treatment": "Spazio.",
                                                      "video_model": "LTX-2.5"})
    assert creata["success"] and creata["settings"]["video_model"] == "ltx25"
    assert not video_tools.esegui("video_prod_create", {"title": "X", "treatment": "Y",
                                                        "video_model": "sora"})["success"]
    imp = video_tools.esegui("video_prod_settings", {"prod_id": creata["prod_id"], "model": "MiniMax H3"})
    assert imp["success"] and imp["changed"]["video_model"] == "h3"
    # Un manifest vecchio col nome libero si legge col nome canonico.
    store, _ = ambiente
    p = store.get(creata["prod_id"])
    p["settings"]["video_model"] = "LTX-2.5"
    store.save(p)
    assert prod_mod.is_ltx(store.get(creata["prod_id"])["settings"])


def test_storyboard_lungo_troncato_recupera_le_scene():
    scene = [{"title": f"S{i}", "summary": f"scena {i}", "seconds": 45} for i in range(3)]
    import json
    troncato = "<think>conto le scene" + json.dumps(scene)[:-40]
    out = prod_mod.extract_json(troncato, list)
    assert [s["title"] for s in out] == ["S0", "S1"]
    budget = []

    def gen(messages, max_tokens):
        budget.append(max_tokens)
        if len(budget) == 1:
            return "<think>sto ancora ragionando senza fine"
        if "Dividi" in messages[0]["content"]:
            return json.dumps(scene)
        return json.dumps([{"prompt": "a probe drifts past a comet", "seconds": 8, "transition": "cut"}])
    shots = prod_mod.plan_storyboard("Una sonda nel cosmo.", 30, generate=gen, shot_seconds=(8.0, 10.0))
    assert budget[0] > 3000 and len(shots) == 3       # 40 scene per 30 minuti: budget alzato, secondo tentativo


def test_lotto_durante_il_render_rimanda_all_attesa(ambiente, monkeypatch):
    store, _ = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Lotto", "treatment": "T"})["prod_id"]
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "probe", "seconds": 2})
    p = store.get(pid)
    p["shots"][0]["status"] = "failed"
    store.save(p)
    monkeypatch.setattr(prod_mod.manager, "active", lambda: {"production": pid})
    esito = video_tools.esegui("video_review_batch", {"prod_id": pid, "confirmed": True, "reason": MOTIVO,
                                                      "decisions": [{"shot_index": 0, "verdict": "skip"}]})
    # Durante il render le GPU sono riservate: il lotto si rifiuta e rimanda all'attesa.
    assert not esito["success"] and "video_render_status" in esito["error"]
    assert store.get(pid)["shots"][0]["status"] == "failed"
    stato = video_tools.esegui("video_render_status", {"prod_id": pid})
    assert stato["running"] and "wait_s" in stato["hint"]


def test_attesa_del_render_senza_turni(ambiente, monkeypatch):
    _store, _ = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Attesa", "treatment": "T"})["prod_id"]
    giri = iter([{"production": pid}, {"production": pid}, None, None])
    monkeypatch.setattr(prod_mod.manager, "active", lambda: next(giri, None))
    monkeypatch.setattr(video_tools, "RENDER_WAIT_POLL_S", 0.01)
    stato = video_tools.esegui("video_render_status", {"prod_id": pid, "wait_s": 30})
    assert stato["success"] and not stato["running"] and stato["waited_s"] < 5


def test_lotto_rifiutato_non_rilancia_e_spiega(ambiente, monkeypatch):
    # Prova Ornith: senza 'reason' il lotto falliva con error=None e rilanciava comunque il render.
    store, _ = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Rifiuto", "treatment": "T"})["prod_id"]
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "probe", "seconds": 2})
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "comet", "seconds": 2})
    p = store.get(pid)
    p["shots"][0]["status"] = "review_required"
    store.save(p)
    avvii = []
    monkeypatch.setattr(video_tools, "_start_render", lambda _pid: avvii.append(_pid))
    esito = video_tools.esegui("video_review_batch", {"prod_id": pid, "confirmed": True,
                                                      "decisions": [{"shot_index": 0, "verdict": "approve",
                                                                     "sha256": "0" * 64}]})
    assert not esito["success"] and esito["error"] and "reason" in esito["error"], esito
    assert not esito["render_started"] and avvii == []


def test_bocciate_in_coda_rifatte_con_altro_seme(ambiente):
    # Prove Ornith e Nex: le bocciate dal giudice non comparivano in coda e, al rilancio,
    # tornavano con lo stesso seme: stessa clip, stessa bocciatura.
    store, motore = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Bocciate", "treatment": "T",
                                                   "settings": {"width": 448, "height": 256}})["prod_id"]
    for sid in ("a", "b"):
        video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": f"probe {sid}", "seconds": CLIP_S})
    p = store.get(pid)
    for s, sid in zip(p["shots"], ("a", "b")):
        s.update(id=sid, status="failed", seed=100, attempts=1, error="Clip non verificata: camera ferma",
                 judge={"ok": False, "prompt_fix": "the camera slowly dollies in"})
    store.save(p)
    coda = video_tools.esegui("video_review_queue", {"prod_id": pid})
    assert [f["shot_id"] for f in coda["failed"]] == ["a", "b"] and coda["failed_hint"]
    esito = video_tools.esegui("video_review_batch", {
        "prod_id": pid, "confirmed": True, "restart": False,
        "decisions": [{"shot_id": "a", "verdict": "redo", "fix": "the probe crosses the frame left to right"}]})
    assert esito["success"], esito
    a = store.get(pid)["shots"][0]
    assert a["status"] == "pending" and a["seed"] != 100
    assert "the probe crosses the frame left to right" in a.get("prompt_fixes", [])
    # Primo giro: solo la 'a'. Al giro dopo il runner rimette in coda la 'b', con un altro seme
    # e la correzione del giudice.
    video_tools.esegui("video_render", {"prod_id": pid})
    video_tools.esegui("video_render", {"prod_id": pid})
    semi = {sid: req["seed"] for sid, req in motore.chiamate}
    assert semi["a"] != 100 and semi["b"] != 100, semi
    assert "the camera slowly dollies in" in store.get(pid)["shots"][1].get("prompt_fixes", [])


def test_oggetti_in_fila_senza_array():
    # Ornith risponde alla riscrittura per LTX con {..},{..} senza parentesi quadre.
    fila = '{\n "index": 0, "prompt": "a"\n},\n{\n "index": 1, "prompt": "b"\n}'
    assert prod_mod.extract_json(fila, list) == [{"index": 0, "prompt": "a"}, {"index": 1, "prompt": "b"}]
    assert prod_mod.extract_json('{"index": 0, "prompt": "a"},\n{"index": 1, "pro', list) == [
        {"index": 0, "prompt": "a"}]
    assert prod_mod.extract_json('{"title": "x"}') == {"title": "x"}      # senza want resta un oggetto


def test_lotto_senza_sha_vale_se_la_coda_ha_mostrato_la_clip(ambiente):
    # Prova del 27B: decisioni giuste ma senza sha256, e l'errore parlava di clip cambiata.
    store, _ = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Sha", "treatment": "T",
                                                   "settings": {"width": 448, "height": 256}})["prod_id"]
    for k in range(2):
        video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": f"probe {k}", "seconds": CLIP_S})
    assert video_tools.esegui("video_render", {"prod_id": pid})["success"]
    decisione = {"prod_id": pid, "confirmed": True, "reason": MOTIVO, "restart": False,
                 "decisions": [{"shot_index": 0, "verdict": "approve"}]}
    senza_coda = video_tools.esegui("video_review_batch", decisione)
    assert not senza_coda["success"] and "manca sha256" in senza_coda["error"]
    assert video_tools.esegui("video_review_queue", {"prod_id": pid})["success"]
    esito = video_tools.esegui("video_review_batch", decisione)
    assert esito["success"], esito
    assert store.get(pid)["shots"][0]["status"] == "done"


def test_traduzione_nella_scrittura_sbagliata_si_rifa(tmp_path):
    # Prova della sonda: la descrizione "araba" era in cinese e la pubblicazione si fermava.
    from core.modules.sigma_creative_lab.video import publishing as pub
    risposte = iter(['{"title": "T", "description": "探测器孤独地漂浮"}',
                     '{"title": "T", "description": "مسبار يطفو في الفضاء"}'])
    chieste = []

    def ask(prompt, n):
        chieste.append(prompt)
        return next(risposte)
    out = pub.localizations({"title": "Probe", "description": "A probe drifts."}, ["en", "ar"], ask,
                            tmp_path / "t.json", lambda *a: None, lambda: None)
    assert out[pub.LOCALES.get("ar", "ar")]["description"].startswith("مسبار")
    assert len(chieste) == 2 and "script" in chieste[-1]


def test_soggettiva_il_veicolo_diventa_la_camera(ambiente, monkeypatch):
    # Prova della sonda in soggettiva: "onboard camera of a space probe" portava oblo', scafo e un equipaggio.
    store, motore = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Sonda POV", "treatment": "T", "negative": "text",
                                                   "settings": {"width": 448, "height": 256, "pov": True}})["prod_id"]
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "seconds": CLIP_S, "prompt":
        "First-person view from the onboard camera of a space probe flying over a comet. The probe banks gently."})
    p = store.get(pid)
    req = ProductionRunner(store, pid, engine=motore).build_request(p, 0)
    testo = req["prompt"].lower()
    assert "probe" not in testo and "onboard" not in testo and "people move forward" not in testo
    assert "no people" in testo and "first-person camera" in testo
    assert req["negative_prompt"].startswith("text") and "cockpit" in req["negative_prompt"]
    # Il fotogramma chiave e il giudice ricevono la stessa soggettiva.
    from core.modules.sigma_creative_lab.video import genres, image_gen
    monkeypatch.setattr(image_gen, "installed", lambda model: model == "klein")
    _m, chiave, _r = genres.keyframe_plan(p, p["shots"][0])
    assert "probe" not in chiave.lower() and "no crew" in chiave.lower()


def test_soggettiva_spiegata_al_giudice(monkeypatch):
    from core.modules.sigma_creative_lab.video import clip_judge
    intenti = []

    def giudice(clip, intent, *a, **k):
        intenti.append(intent)
        return {"ok": True, "score": 1.0, "seen": "camera flies over a comet", "issues": [], "prompt_fix": ""}
    monkeypatch.setattr(clip_judge, "installed", lambda: True)
    monkeypatch.setattr(clip_judge.judge, "judge", giudice)
    monkeypatch.setattr(prod_mod, "resolve_judge_device", lambda s: "cpu")
    prod = {"settings": {"pov": True, "judge": True}, "shots": []}
    shot = {"id": "s0", "prompt": "First-person view from the onboard camera of a space probe over a comet."}
    asyncio.run(prod_mod.judge_clip(prod, shot, Path("x.mp4"), shot["prompt"]))
    assert intenti and "first-person camera flight" in intenti[0] and "probe" not in intenti[0].lower()


def test_lotto_accetta_decision_al_posto_di_verdict(ambiente):
    store, _ = ambiente
    pid = video_tools.esegui("video_prod_create", {"title": "Alias", "treatment": "T",
                                                   "settings": {"width": 448, "height": 256}})["prod_id"]
    video_tools.esegui("video_prod_add_shot", {"prod_id": pid, "prompt": "probe", "seconds": CLIP_S})
    video_tools.esegui("video_render", {"prod_id": pid})
    video_tools.esegui("video_review_queue", {"prod_id": pid})
    esito = video_tools.esegui("video_review_batch", {"prod_id": pid, "confirmed": True, "reason": MOTIVO,
                                                      "restart": False,
                                                      "decisions": [{"index": 0, "decision": "approve"}]})
    assert esito["success"], esito
    assert store.get(pid)["shots"][0]["status"] == "done"
