"""Una disconnessione non rilancia né interrompe il lavoro intestato alla chat."""
import asyncio
import json
import threading

import pytest

from core.harness.run_events import RunEvents


def test_replay_and_disk_spooling():
    run = RunEvents()
    try:
        run.append({'type': 'token', 'token': 'à' * 600000})
        run.append({'type': 'done'})
        assert run.read(1)[0]['type'] == 'done'
        assert run.read(0)[0]['token'] == 'à' * 600000
        assert run.read(0)[1]['event_id'] == 2
        with pytest.raises(ValueError):
            run.read(3)
    finally:
        run.close()


def test_transcript_limit_preserves_error():
    run = RunEvents(max_bytes=50)
    try:
        with pytest.raises(RuntimeError):
            run.append({'type': 'token', 'token': 'x' * 100})
        run.append({'type': 'error', 'error': 'Registro pieno'})
        assert run.read()[0]['type'] == 'error'
    finally:
        run.close()


def test_disconnect_replay_and_explicit_stop(monkeypatch):
    from core.modules.sigma_developer_lab import handlers
    release = threading.Event()
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        yield {'type': 'token', 'token': 'prima'}
        assert release.wait(5)
        yield {'type': 'pipeline_update', 'tasks': [{'id': 'cast', 'status': 'done'}]}
        yield {'type': 'done'}

    class Request:
        query_params = {}

        async def json(self):
            return {'session_id': 'reconnect-test', 'messages': [{'role': 'user', 'content': 'video'}]}

    monkeypatch.setattr(handlers, '_AGENT_STREAMS', {})
    monkeypatch.setattr(handlers, '_AGENT_RUNS', {})
    monkeypatch.setattr(handlers, 'stream_admin_agent_turn', generate)

    async def check():
        response = await handlers.handle_agent_chat(Request())
        run = handlers._AGENT_STREAMS['reconnect-test']
        iterator = response.body_iterator
        await anext(iterator)
        await iterator.aclose()
        assert not run.cancel.is_set()
        release.set()
        assert await asyncio.to_thread(run.finished.wait, 5)
        replay = ''.join([item async for item in handlers._agent_events_stream(run)])
        assert 'prima' in replay and 'pipeline_update' in replay and '[DONE]' in replay
        assert len(calls) == 1
        run.close()

    try:
        asyncio.run(check())
    finally:
        release.set()


def test_stop_only_targets_matching_run(monkeypatch):
    from core.modules.sigma_developer_lab import handlers
    run = RunEvents()
    monkeypatch.setattr(handlers, '_AGENT_STREAMS', {'session': run})

    class Request:
        async def json(self):
            return {'session_id': 'session', 'run_id': 'old'}

    response = asyncio.run(handlers.handle_agent_stop(Request()))
    assert not json.loads(response.body)['stopped']
    assert not run.cancel.is_set()
    run.close()
