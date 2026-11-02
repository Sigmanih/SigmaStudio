"""L'editor conserva i job senza riavviare automaticamente operazioni interrotte."""
import time
import pytest
import asyncio
import threading
from types import SimpleNamespace

from core.job_store import JobStore
from core.modules.sigma_creative_lab.video import editor_jobs as editor
from core.modules.sigma_creative_lab.video.production import ProductionStore


def test_editor_ripresa_esplicita_dei_checkpoint(tmp_path, monkeypatch):
    prods = ProductionStore(tmp_path / "productions")
    prod = prods.create("Film")
    state = tmp_path / "editor.db"
    old = JobStore(state, clock=lambda: 1)
    old.create({"id": "old_job", "scope": prod["id"], "kind": "restore_pipeline", "args": {"height": 1080},
                "created": 1, "status": "queued"})
    assert old.claim("old_job", "processo-terminato", lease_seconds=1)
    called = []
    monkeypatch.setitem(editor.HANDLERS, "restore_pipeline", lambda ctx, job: called.append(job["id"]))
    jobs = editor.EditorJobs(prods, SimpleNamespace(active=lambda: {"busy": True}), state_path=state)
    try:
        history = jobs.list(prod["id"])
        assert history[0]["status"] == "interrupted"
        assert history[0]["can_resume"]
        assert not called
        resumed = jobs.resume("old_job")
        assert resumed["args"] == {"height": 1080}
        assert resumed["retry_of"] == "old_job"
        assert "cancel_event" not in resumed
        assert jobs.busy()
        assert "In attesa" in jobs.list(prod["id"])[0]["message"]
        assert jobs.cancel(resumed["id"])
        assert jobs.list(prod["id"])[0]["status"] == "cancelled"
    finally:
        assert jobs.close()


def test_operazione_cpu_non_attende_la_gpu(tmp_path, monkeypatch):
    prods = ProductionStore(tmp_path / "productions")
    prod = prods.create("Titolo")
    monkeypatch.setitem(editor.HANDLERS, "title", lambda ctx, job: {"text": "Film"})
    jobs = editor.EditorJobs(prods, SimpleNamespace(active=lambda: {"busy": True}), state_path=tmp_path / "editor.db")
    try:
        job = jobs.submit(prod["id"], "title", {})
        end = time.monotonic() + 5
        while jobs._store.get(job["id"])["status"] != "done" and time.monotonic() < end:
            time.sleep(0.02)
        assert jobs._store.get(job["id"])["status"] == "done"
    finally:
        assert jobs.close()


def test_produzione_rispetta_la_prenotazione_e_la_libera_in_caso_di_errore(tmp_path, monkeypatch):
    from core.modules.sigma_creative_lab.video import production
    from core.modules.sigma_creative_lab.backends.resources import reserve_accelerator, accelerator_busy
    from core.resource_pool import ResourceBusy
    prods = ProductionStore(tmp_path / "productions")
    prod = prods.create("Film")
    manager = production.ProductionManager(prods)
    with reserve_accelerator("editor-in-esecuzione"):
        with pytest.raises(ResourceBusy):
            manager.start(prod["id"])

    class FailedRunner:
        def __init__(self, store, pid, **kwargs):
            self.pid = pid

        async def run(self):
            raise RuntimeError("Errore del generatore simulato")

    monkeypatch.setattr(production, "ProductionRunner", FailedRunner)
    manager.start(prod["id"])
    manager._thread.join(timeout=2)
    assert not manager._thread.is_alive()
    assert not accelerator_busy()
    assert prods.get(prod["id"])["status"] == "failed"


def test_ripresa_dopo_salvataggio_non_duplica_la_take(tmp_path, monkeypatch):
    from core.engine import gpu_lease
    from core.modules.sigma_creative_lab.video import production, remaster
    from core.modules.sigma_creative_lab.native import runtime
    from core.modules.sigma_creative_lab.video import timeline as T
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    store = ProductionStore(tmp_path / "productions")
    prod = store.create("Film", shots=[{"id": "shot_a", "status": "done", "origin": "import", "prompt": "film",
                                        "frames": 240, "clip_path": str(source), "take": "t1", "takes": [
                                            {"id": "t1", "kind": "import", "frames": 240, "clip_path": str(source)}]}])
    timeline = T.TimelineStore(store)
    timeline.apply(prod["id"], "insert_item", {"shot_id": "shot_a", "take_id": "t1", "index": 0})
    item = timeline.get(prod["id"])["video"][0]
    context = SimpleNamespace(prods=store, timelines=timeline, manager=SimpleNamespace(), _note=lambda *args: None)
    generated = []

    def generate(src, output, *args, **kwargs):
        generated.append(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"restored")
        return {"path": str(output)}

    monkeypatch.setattr(remaster, "remaster_film", generate)
    monkeypatch.setattr(runtime, "release_llm_vram", lambda: None)
    monkeypatch.setattr(gpu_lease, "leases", SimpleNamespace(acquire=lambda *a, **k: "lease", renew=lambda *a: True,
                                                           release=lambda *a: True))
    monkeypatch.setattr(production, "probe", lambda path: {"width": 1440, "height": 1080, "frames": 240})
    apply = timeline.apply
    attempts = []

    def fail_once(*args, **kwargs):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError("Interruzione prima del collegamento alla timeline")
        return apply(*args, **kwargs)

    monkeypatch.setattr(timeline, "apply", fail_once)
    job = {"id": "first", "operation_id": "same_operation", "production": prod["id"],
           "args": {"item_id": item["id"]}, "cancel_event": threading.Event()}
    with pytest.raises(RuntimeError, match="prima del collegamento"):
        asyncio.run(editor.job_remaster(context, job))
    result = asyncio.run(editor.job_remaster(context, {**job, "id": "retry"}))
    assert result["reused"]
    assert len(generated) == 1
    assert len(store.get(prod["id"])["shots"][0]["takes"]) == 2


@pytest.mark.parametrize("route", ["handle_editor_job", "handle_editor_job_cancel", "handle_editor_job_resume"])
def test_rotte_job_rifiutano_json_non_oggetto(route):
    from core.modules.sigma_creative_lab.video import editor_routes
    responses = []
    handler = SimpleNamespace(read_json_body=lambda: [],
                              send_json_response=lambda data, status=200: responses.append((status, data)))
    getattr(editor_routes, route)(handler)
    assert responses[0][0] == 400
