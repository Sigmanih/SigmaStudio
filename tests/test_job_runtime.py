"""Persistenza, concorrenza e cancellazione senza modelli o acceleratori."""
import asyncio
import time
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.job_store import JobStore
from core.job_worker import JobCancelled, PersistentJobWorker


def record(key="job_a", **extra):
    return {"id": key, "scope": "film", "kind": "restore", "args": {},
            "status": "queued", "created": time.time(), "message": "In coda", **extra}


def wait_for(predicate, seconds=5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    pytest.fail("Lo stato atteso non è arrivato entro il limite")


def test_claim_atomico_e_limite_globale_fra_esecutori(tmp_path):
    path = tmp_path / "jobs.db"
    stores = [JobStore(path), JobStore(path)]
    stores[0].create(record())
    stores[0].create(record("job_b"))
    with ThreadPoolExecutor(2) as pool:
        acquired = list(pool.map(lambda i: stores[i].claim("job_a", str(i)), range(2)))
    assert sum(acquired) == 1
    assert not stores[0].claim("job_b", "altro")
    owner = str(acquired.index(True))
    assert stores[0].save(record(status="done"), owner)
    assert stores[1].claim("job_b", "altro")


def test_lease_scaduta_non_puo_pubblicare_un_successo(tmp_path):
    now = [100.0]
    store = JobStore(tmp_path / "jobs.db", clock=lambda: now[0])
    store.create(record())
    assert store.claim("job_a", "worker", lease_seconds=2)
    now[0] += 3
    assert not store.heartbeat("job_a", "worker")
    assert not store.save(record(status="done"), "worker")
    assert store.recover() == 1
    assert store.get("job_a")["status"] == "interrupted"
    assert not store.claim("job_a", "nuovo")


def test_coda_limitata_e_riprese_non_duplicate(tmp_path):
    store = JobStore(tmp_path / "jobs.db", max_pending=1)
    store.create(record())
    with pytest.raises(ValueError, match="Coda piena"):
        store.create(record("job_b"))
    assert store.cancel("job_a")
    store.create(record("retry_a", retry_of="job_a"))
    assert store.claim("retry_a", "worker")
    store.max_pending = 3
    with pytest.raises(ValueError, match="già in coda"):
        store.create(record("retry_b", retry_of="job_a"))
    assert store.get("job_a")["status"] == "cancelled"


def test_coda_sopravvive_al_riavvio_senza_duplicare_i_lavori(tmp_path):
    path = tmp_path / "jobs.db"
    called = []
    first = PersistentJobWorker(JobStore(path), {"restore": lambda ctx, job: called.append(job["id"])}, None,
                                blocked=lambda job: "Risorsa occupata")
    job = first.submit("film", "restore", {"param": 1})
    assert first.close()
    assert not called
    second = PersistentJobWorker(JobStore(path), {"restore": lambda ctx, job: called.append(job["id"])}, None)
    try:
        wait_for(lambda: second.store.get(job["id"])["status"] == "done")
        assert called == [job["id"]]
    finally:
        assert second.close()


def test_cancellazione_cooperativa_e_parametri_conservati(tmp_path):
    async def handler(ctx, job):
        while not job["cancel_event"].is_set():
            await asyncio.sleep(0.01)
        raise JobCancelled("Richiesta ricevuta")

    worker = PersistentJobWorker(JobStore(tmp_path / "jobs.db"), {"restore": handler}, None)
    try:
        job = worker.submit("film", "restore", {"source": "film.mp4"})
        wait_for(lambda: worker.store.get(job["id"])["status"] == "running")
        assert worker.cancel(job["id"])
        wait_for(lambda: worker.store.get(job["id"])["status"] == "cancelled")
        assert worker.store.get(job["id"])["args"] == {"source": "film.mp4"}
        resumed = worker.retry(job["id"], {"restore"})
        assert resumed["retry_of"] == job["id"]
        assert worker.cancel(resumed["id"])
    finally:
        assert worker.close()


def test_risultato_non_serializzabile_diventa_errore_visibile(tmp_path):
    worker = PersistentJobWorker(JobStore(tmp_path / "jobs.db"), {"restore": lambda ctx, job: object()}, None)
    try:
        job = worker.submit("film", "restore", {})
        wait_for(lambda: worker.store.get(job["id"])["status"] == "error")
        assert worker.store.get(job["id"])["error"]
    finally:
        assert worker.close()


def test_prenotazione_multi_risorsa_atomica_e_rilascio_idempotente():
    from core.resource_pool import ResourceBusy, ResourcePool
    pool = ResourcePool()
    with pool.reserve(["gpu:0"], "restauro"):
        with pytest.raises(ResourceBusy):
            pool.reserve(["gpu:0", "gpu:1"], "chat")
        assert not pool.occupied("gpu:1")
        assert pool.snapshot()["gpu:0"]["owner"] == "restauro"
    lease = pool.reserve(["gpu:0"], "editor")
    lease.close()
    with pool.reserve(["gpu:0"], "altro"):
        lease.close()
        assert pool.occupied("gpu:0")
    assert not pool.snapshot()


def test_job_attende_la_prenotazione_e_poi_parte(tmp_path):
    from core.resource_pool import ResourcePool
    pool = ResourcePool()
    reservation = pool.reserve(["gpu:0"], "restauro")
    worker = PersistentJobWorker(JobStore(tmp_path / "jobs.db"), {"restore": lambda ctx, job: {}}, None,
                                 reserve=lambda job: pool.reserve(["gpu:0"], job["id"]))
    try:
        job = worker.submit("film", "restore", {})
        time.sleep(0.1)
        assert worker.store.get(job["id"])["status"] == "queued"
        reservation.close()
        wait_for(lambda: worker.store.get(job["id"])["status"] == "done")
        wait_for(lambda: not pool.snapshot())
    finally:
        reservation.close()
        assert worker.close()


def test_il_job_conserva_la_traccia_della_richiesta(tmp_path):
    from core.request_context import get_request_id, request_scope
    worker = PersistentJobWorker(JobStore(tmp_path / "jobs.db"), {"restore": lambda ctx, job: get_request_id()}, None)
    try:
        with request_scope("richiesta-di-prova"):
            job = worker.submit("film", "restore", {})
        wait_for(lambda: worker.store.get(job["id"])["status"] == "done")
        completed = worker.store.get(job["id"])
        assert completed["request_id"] == completed["result"] == "richiesta-di-prova"
        assert get_request_id() == "-"
    finally:
        assert worker.close()


def test_monitor_non_pubblica_un_esito_che_sta_ancora_terminando():
    job = record(status="running", cancel_event=threading.Event())
    saved = []

    def heartbeat(*args):
        job["status"] = "done"
        return True

    worker = object.__new__(PersistentJobWorker)
    worker.owner = "owner"
    worker._stop = threading.Event()
    worker.store = SimpleNamespace(get=lambda key: {"cancel_requested": False}, heartbeat=heartbeat,
                                   save=lambda payload, owner: saved.append(payload) or True)
    worker._monitor(job, SimpleNamespace(wait=Mock(side_effect=[False, True])))
    assert saved[0]["status"] == "running"
