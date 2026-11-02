"""Le richieste chunked e un lettore lento rispettano budget finiti."""
import asyncio
import threading

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from core.security.request_limits import RequestLimitMiddleware
from core.sse import ClientGone


async def echo(request):
    return Response(await request.body())


def client():
    app = Starlette(routes=[Route("/", echo, methods=["POST"])])
    app.add_middleware(RequestLimitMiddleware, max_bytes=8)
    return TestClient(app)


def test_body_dichiarato_oltre_limite():
    assert client().post("/", content=b"012345678").status_code == 413
    assert client().post("/", content=b"01234567").content == b"01234567"


def test_body_chunked_oltre_limite():
    assert client().post("/", content=iter([b"01234", b"56789"])).status_code == 413


def test_lunghezza_non_valida():
    assert client().post("/", content=b"x", headers={"Content-Length": "errato"}).status_code == 400


@pytest.mark.asyncio
async def test_coda_limitata_rallenta_il_produttore_senza_perdere_eventi(monkeypatch):
    from core import fastapi_app
    monkeypatch.setattr(fastapi_app, "_SSE_QUEUE_SIZE", 2)
    adapter = fastapi_app.FastAPIHandlerAdapter("/", {}, b"")
    queue = adapter.attach_stream(asyncio.get_running_loop())

    def produce():
        for value in ("uno", "due", "tre", None):
            adapter.emit(value)

    producer = asyncio.create_task(asyncio.to_thread(produce))
    for _ in range(100):
        if queue.qsize() == 2:
            break
        await asyncio.sleep(0.01)
    assert queue.qsize() == 2
    assert not producer.done()
    values = [await asyncio.wait_for(queue.get(), timeout=2) for _ in range(4)]
    await asyncio.wait_for(producer, timeout=2)
    assert values == ["uno", "due", "tre", None]


@pytest.mark.asyncio
async def test_disconnessione_sblocca_il_produttore(monkeypatch):
    from core import fastapi_app
    monkeypatch.setattr(fastapi_app, "_SSE_QUEUE_SIZE", 1)
    adapter = fastapi_app.FastAPIHandlerAdapter("/", {}, b"")
    queue = adapter.attach_stream(asyncio.get_running_loop())
    queue.put_nowait("occupato")
    producer = asyncio.create_task(asyncio.to_thread(adapter.emit, "in attesa"))
    await asyncio.sleep(0.05)
    adapter.client_gone.set()
    with pytest.raises(ClientGone):
        await asyncio.wait_for(producer, timeout=2)


@pytest.mark.asyncio
async def test_stream_nativo_rispetta_backpressure_e_chiude_la_sorgente(monkeypatch):
    from core import fastapi_app
    monkeypatch.setattr(fastapi_app, "_SSE_QUEUE_SIZE", 1)
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(fastapi_app, "_stream_slots", slots)
    produced = []
    closed = threading.Event()

    def source():
        try:
            for value in range(100):
                produced.append(value)
                yield value
        finally:
            closed.set()

    stream = fastapi_app._aiter_blocking(source)
    assert await asyncio.wait_for(anext(stream), timeout=2) == 0
    await asyncio.sleep(0.15)
    assert len(produced) <= 3
    assert not slots.acquire(blocking=False)
    await stream.aclose()
    assert await asyncio.to_thread(closed.wait, 2)
    for _ in range(100):
        if slots.acquire(blocking=False):
            slots.release()
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Il produttore non ha liberato il posto dopo la disconnessione")


@pytest.mark.asyncio
async def test_stream_nativo_non_accoda_lavoro_oltre_il_budget(monkeypatch):
    from core import fastapi_app
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(fastapi_app, "_stream_slots", slots)
    called = threading.Event()

    def source():
        called.set()
        return iter([1])

    with pytest.raises(RuntimeError, match="Troppi stream"):
        await anext(fastapi_app._aiter_blocking(source))
    assert not called.is_set()
    slots.release()


@pytest.mark.asyncio
async def test_stream_nativo_propaga_errore_e_restituisce_il_posto(monkeypatch):
    from core import fastapi_app
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(fastapi_app, "_stream_slots", slots)

    def source():
        raise ValueError("generazione fallita")

    with pytest.raises(ValueError, match="generazione fallita"):
        async for _ in fastapi_app._aiter_blocking(source):
            pytest.fail("Non deve produrre dati dopo l'errore")
    for _ in range(100):
        if slots.acquire(blocking=False):
            slots.release()
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Il produttore non ha liberato il posto dopo l'errore")


@pytest.mark.asyncio
async def test_stream_nativo_consegna_tutti_gli_eventi_in_ordine(monkeypatch):
    from core import fastapi_app
    monkeypatch.setattr(fastapi_app, "_SSE_QUEUE_SIZE", 2)
    received = [item async for item in fastapi_app._aiter_blocking(lambda: iter(range(100)))]
    assert received == list(range(100))


@pytest.mark.asyncio
async def test_stream_nativo_restituisce_il_posto_se_executor_chiuso(monkeypatch):
    from core import fastapi_app
    from concurrent.futures import ThreadPoolExecutor
    slots = threading.BoundedSemaphore(1)
    executor = ThreadPoolExecutor(max_workers=1)
    executor.shutdown()
    monkeypatch.setattr(fastapi_app, "_stream_slots", slots)
    monkeypatch.setattr(fastapi_app, "_stream_executor", executor)
    with pytest.raises(RuntimeError, match="shutdown"):
        await anext(fastapi_app._aiter_blocking(lambda: iter([1])))
    assert slots.acquire(blocking=False)
    slots.release()
