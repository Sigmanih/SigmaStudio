"""Il saluto resta conversazione e il refresh non perde la risposta ordinaria."""
import asyncio
import io
import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from core.chat import chat_runner as chat
from core.chat import runs
from core.engine.cancellation import CancellationToken, cancellable_http_response, is_cancelled


@pytest.mark.parametrize('message', ['ciao come ti chiami? parlami di te', 'Ciao!', 'Chi sei?',
                                     'Ciao, cosa sai fare?', 'come stai?'])
def test_identity_is_conversation(message):
    assert chat._identity_conversation(message)


@pytest.mark.parametrize('message', ['ciao, genera un video', 'come ti chiami? crea un file',
                                     'presentati e avvia i test', 'elimina il file ciao.txt'])
def test_real_actions_are_not_misclassified(message):
    assert not chat._identity_conversation(message)


def test_identity_has_small_prompt_and_no_tool_catalogue(monkeypatch):
    from core.mcp import mcp_hub, agent_loop
    from core.harness import laya_router
    from core import scheda_progetto
    captured = {}
    monkeypatch.setattr(chat, 'load_ai_config', lambda: {'active_provider': 'ollama', 'model': 'fake',
                         'providers': {'ollama': {'model': 'fake'}}})
    monkeypatch.setattr(chat, '_determine_agent_by_request', lambda *a: '')
    monkeypatch.setattr(chat, '_get_manifesto_content', lambda *a: 'istruzioni operative ' * 15000)
    monkeypatch.setattr(chat, '_detect_hardware_note', lambda *a: '')
    monkeypatch.setattr(chat, '_build_filesystem_context', lambda: pytest.fail('Nessun albero necessario'))
    monkeypatch.setattr(agent_loop, 'build_tools_prompt', lambda *a: pytest.fail('Nessun catalogo strumenti'))
    monkeypatch.setattr(mcp_hub, 'get_server', lambda *a: None)
    monkeypatch.setattr(laya_router, 'triage_chat', lambda *a: pytest.fail('Nessun modello di triage necessario'))
    monkeypatch.setattr(scheda_progetto, 'scheda', lambda: 'Sigma Studio: kernel Python e moduli opzionali.')
    monkeypatch.setattr(chat, '_stream_chat_response', lambda *a, **kw: captured.update(messages=a[1], **kw))
    handler = SimpleNamespace(read_json_body=lambda: {'message': 'ciao come ti chiami? parlami di te',
                              'stream': True, 'allow_actions': True},
                              send_json_response=lambda *a: pytest.fail(str(a)))
    chat.handle_chat(handler)
    assert captured['allow_actions'] is False
    assert captured['wants_reasoning'] is False
    assert captured['sampling'].max_tokens <= 1024
    assert len(captured['messages'][0]['content']) < 5000


def test_disabled_actions_never_execute_model_tool_block(monkeypatch):
    import core.ai_providers as providers
    from core.mcp import agent_loop
    from core.engine.sampling import SamplingParams
    malicious = '```sigma-tool\n{"tool":"fake","arguments":{}}\n```'
    assert agent_loop.extract_tool_calls(malicious)
    monkeypatch.setattr(agent_loop, 'execute_calls', lambda *a: pytest.fail('Strumento eseguito'))
    monkeypatch.setattr(providers, 'call_ai_model_stream', lambda *a, **kw: iter([
        {'token': 'Sono Sigma. ' + malicious}, {'done': True}]))
    monkeypatch.setattr(chat, '_lookup_radix_prefix_cache', lambda *a: (0, 0, 0, [], None))
    handler = SimpleNamespace(wfile=io.BytesIO(), send_response=lambda *a: None,
                              send_header=lambda *a: None, end_headers=lambda: None)
    chat._stream_chat_response(handler, [{'role': 'user', 'content': 'chi sei?'}],
                              {}, 'fake', 'ollama', '', '', '', .7, 1024, .9, 5,
                              message='chi sei?', bot_name='Sigma', manifesto_path='',
                              allow_actions=False, wants_reasoning=False,
                              sampling=SamplingParams(max_tokens=1024))
    assert b'Sono Sigma' in handler.wfile.getvalue()
    assert b'tool_start' not in handler.wfile.getvalue()


def test_parent_cancellation_reaches_backend_protocol():
    stopped = threading.Event()
    token = CancellationToken(parent_event=stopped)
    assert not token.is_cancelled()
    stopped.set()
    assert token.is_cancelled() and is_cancelled(token)
    assert token.reason == 'client_disconnected'


def test_cancellable_transport_reads_http10_body():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header('Content-Length', '5')
            self.end_headers()
            self.wfile.write(b'Sigma')

        def log_message(self, *args):
            return None
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/', data=b'')
        with cancellable_http_response(request, 3, CancellationToken()) as response:
            assert response.read() == b'Sigma'
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize('send_headers', [False, True])
def test_cancel_http_before_first_token(send_headers):
    entered, release = threading.Event(), threading.Event()
    failures = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if send_headers:
                self.send_response(200)
                self.end_headers()
                self.wfile.flush()
            entered.set()
            release.wait(5)

        def log_message(self, *args):
            return None

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cancel = CancellationToken()
    def request():
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/', data=b'{}')
            with cancellable_http_response(req, 30, cancel) as response:
                response.readline()
        except Exception as exc:
            failures.append(exc)
    worker = threading.Thread(target=request, daemon=True)
    worker.start()
    try:
        assert entered.wait(2)
        start = time.monotonic()
        cancel.cancel()
        worker.join(2)
        assert not worker.is_alive(), 'Socket rimasto bloccato prima del primo token'
        assert time.monotonic() - start < 2
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        worker.join(2)


def test_normal_chat_replays_after_disconnect(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(runs, '_runs', {})
    handler = SimpleNamespace(client_gone=threading.Event(), _response_data=None)
    slots = threading.BoundedSemaphore(1)
    calls = []
    def produce():
        calls.append('once')
        handler.emit('data: {"token":"Sono "}\n\n')
        assert release.wait(3)
        handler.emit('data: {"token":"Sigma"}\n\n')
        handler.emit('data: [DONE]\n\n')
    async def check():
        response = runs.start(handler, produce, {'session_id': 'normal'}, slots)
        await anext(response.body_iterator)
        await response.body_iterator.aclose()
        run = runs._runs['normal']
        assert not run.cancel.is_set()
        release.set()
        assert await asyncio.to_thread(run.finished.wait, 3)
        replay = ''.join([frame async for frame in runs.events(run)])
        assert 'Sono ' in replay and 'Sigma' in replay and '[DONE]' in replay
        assert calls == ['once']
        assert slots.acquire(blocking=False)
        run.close()
    try:
        asyncio.run(check())
    finally:
        release.set()
