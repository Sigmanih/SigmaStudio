"""Editor video: timeline non distruttiva, versioni, cronologia annulla/ripeti."""

import copy

import pytest

from core.modules.sigma_creative_lab.video import timeline as tlm
from core.modules.sigma_creative_lab.video.timeline import FPS, TimelineError, TimelineStore


def _prod(n_shots=3, frames=96):
    # Le versioni hanno gia' i frame: nessuna chiamata a ffprobe.
    shots = []
    for i in range(n_shots):
        shots.append({"id": f"s{i}", "status": "done", "prompt": f"inquadratura {i}", "scene": "sc1",
                      "takes": [{"id": "t1", "clip_path": f"clip_{i}.mp4", "frames": frames}], "take": "t1"})
    return {"id": "p1", "shots": shots}


class _Store:
    """Sostituto minimo di ProductionStore: la timeline usa solo path/get/save."""

    def __init__(self, root, prod):
        self.root, self.prod = root, prod

    def path(self, pid):
        return self.root / pid

    def get(self, pid):
        return self.prod if pid == self.prod["id"] else None

    def save(self, prod):
        self.prod = prod


def test_costruzione_dalle_inquadrature_salta_quelle_dell_editor():
    prod = _prod()
    prod["shots"].append({"id": "e1", "status": "done", "origin": "edit",
                          "takes": [{"id": "t1", "clip_path": "x.mp4", "frames": 48}], "take": "t1"})
    tl = tlm.build_from_shots(prod)
    assert [it["shot_id"] for it in tl["video"]] == ["s0", "s1", "s2"]
    assert tlm.layout(tl, prod)["duration"] == pytest.approx(3 * 96 / FPS)


def test_continue_salta_il_frame_ripetuto():
    prod = _prod(2)
    prod["shots"][1]["transition"] = "continue"
    tl = tlm.build_from_shots(prod)
    assert tl["video"][0]["src_in"] == 0.0
    assert tl["video"][1]["src_in"] == pytest.approx(1 / FPS)


def test_dividi_al_fotogramma_e_rifiuta_i_bordi():
    prod = _prod()
    tl = tlm.build_from_shots(prod)
    res = tlm.op_split(tl, prod, 2.0101)          # cade fra due frame: si allinea
    assert len(tl["video"]) == 4
    left, right = tl["video"][0], tl["video"][1]
    assert left["id"] == res["left"] and right["id"] == res["right"]
    assert left["src_out"] == right["src_in"] == pytest.approx(round(2.0101 * FPS) / FPS)
    assert tlm.layout(tl, prod)["duration"] == pytest.approx(3 * 96 / FPS)
    with pytest.raises(TimelineError):
        tlm.op_split(tl, prod, 4.0)               # esattamente sul confine fra due elementi


def test_elimina_intervallo_a_cavallo_di_due_elementi():
    prod = _prod()
    tl = tlm.build_from_shots(prod)
    res = tlm.op_delete_range(tl, prod, 3.0, 5.0)
    assert res["removed"] == 2                    # coda del primo e testa del secondo
    lay = tlm.layout(tl, prod)
    assert lay["duration"] == pytest.approx(12.0 - 2.0)
    assert lay["items"][0]["end"] == pytest.approx(3.0)
    assert lay["items"][1]["src_in"] == pytest.approx(1.0)
    assert res["insert_at"] == 1


def test_accorcia_sposta_duplica_transizione():
    prod = _prod()
    tl = tlm.build_from_shots(prod)
    a, b, c = (it["id"] for it in tl["video"])
    tlm.op_trim(tl, prod, a, src_in=0.5, src_out=99)   # oltre la durata della versione: si ferma a 4 s
    assert (tl["video"][0]["src_in"], tl["video"][0]["src_out"]) == (0.5, 4.0)
    with pytest.raises(TimelineError):
        tlm.op_trim(tl, prod, a, src_in=3.99, src_out=4.0)
    tlm.op_move(tl, prod, c, 0)
    assert [it["id"] for it in tl["video"]] == [c, a, b]
    tlm.op_duplicate(tl, prod, a)
    assert len(tl["video"]) == 4 and tl["video"][2]["shot_id"] == "s0"
    tlm.op_transition(tl, prod, b, "fade", 5)
    assert tl["video"][-1]["transition"] == {"type": "fade", "duration": 2.0}
    with pytest.raises(TimelineError):
        tlm.op_transition(tl, prod, b, "wipe")


def test_la_dissolvenza_sovrappone_i_due_lati():
    prod = _prod(2)
    tl = tlm.build_from_shots(prod)
    tlm.op_transition(tl, prod, tl["video"][1]["id"], "fade", 1.0)
    lay = tlm.layout(tl, prod)
    assert lay["items"][1]["start"] == pytest.approx(3.0)
    assert lay["duration"] == pytest.approx(7.0)


def test_cambio_versione():
    prod = _prod()
    tlm.add_take(prod["shots"][1], "clip_1_v2.mp4", frames=48)
    tl = tlm.build_from_shots(prod)
    item = tl["video"][1]
    assert item["take_id"] == "t2"
    tlm.op_set_take(tl, prod, item["id"], "t1")
    assert item["take_id"] == "t1"
    with pytest.raises(TimelineError):
        tlm.op_set_take(tl, prod, item["id"], "t9")


def test_clip_audio_e_tracce(tmp_path):
    prod = _prod()
    tl = tlm.build_from_shots(prod)
    wav = tmp_path / "voce.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(TimelineError):
        tlm.op_audio_add(tl, prod, "clip", str(wav), 0, src_out=2)
    with pytest.raises(TimelineError):
        tlm.op_audio_add(tl, prod, "voice", str(tmp_path / "manca.wav"), 0, src_out=2)
    cid = tlm.op_audio_add(tl, prod, "voice", str(wav), 1.5, src_out=2.0, label="Narratore")["clip"]
    tlm.op_audio_update(tl, prod, cid, start=-3, gain_db=-2)
    track, _, clip = tlm._find_audio_clip(tl, cid)
    assert track["kind"] == "voice" and clip["start"] == 0.0 and clip["gain_db"] == -2.0
    tlm.op_track(tl, prod, track["id"], gain_db=40, mute=True)
    assert track["gain_db"] == 12.0 and track["mute"] is True
    tlm.op_audio_delete(tl, prod, cid)
    assert not track["clips"]


def test_marcatori_ordinati():
    prod = _prod()
    tl = tlm.build_from_shots(prod)
    tlm.op_marker(tl, prod, 5.0, "b")
    tlm.op_marker(tl, prod, 1.0, "a")
    assert [m["label"] for m in tl["markers"]] == ["a", "b"]
    tlm.op_marker_delete(tl, prod, tl["markers"][0]["id"])
    assert [m["label"] for m in tl["markers"]] == ["b"]


def test_store_annulla_ripeti_e_ricostruisci(tmp_path):
    prod = _prod()
    store = TimelineStore(_Store(tmp_path, prod))
    start = copy.deepcopy(store.get("p1"))
    assert (tmp_path / "p1" / "timeline.json").is_file()

    tl, _ = store.apply("p1", "split", {"t": 2.0})
    assert len(tl["video"]) == 4
    tl, _ = store.apply("p1", "delete", {"item_id": tl["video"][0]["id"]})
    assert len(tl["video"]) == 3
    assert store.history_depth("p1") == {"undo": 2, "redo": 0}

    assert len(store.undo("p1")["video"]) == 4
    assert len(store.undo("p1")["video"]) == 3
    assert [it["id"] for it in store.get("p1")["video"]] == [it["id"] for it in start["video"]]
    with pytest.raises(TimelineError):
        store.undo("p1")
    assert len(store.undo("p1", redo=True)["video"]) == 4

    # Una nuova modifica cancella i "ripeti" rimasti.
    store.apply("p1", "marker", {"t": 1.0})
    assert store.history_depth("p1")["redo"] == 0

    rebuilt = store.rebuild("p1")
    assert len(rebuilt["video"]) == 3 and not rebuilt["markers"]
    assert len(store.undo("p1")["markers"]) == 1     # anche la ricostruzione si annulla

    with pytest.raises(TimelineError):
        store.apply("p1", "nonesiste", {})
    with pytest.raises(TimelineError):
        store.get("altra")
