# ==============================================================================
# tests/test_chat_streaming.py — Test Suite for /api/chat Token Streaming
# Sigma Studio v8.2 — Real-time SSE Chat Delivery
# ==============================================================================
"""Tests for token-by-token SSE delivery on /api/chat and for the SSE endpoint
whitelist that drives the FastAPI dispatcher.

Regression guard: before this suite, /api/chat resolved the whole completion with a
blocking provider call and published a single SSE event at the end, and
/api/chat/orchestrate was missing from the whitelist entirely — its events were
written into a queue nobody drained, so the client received an empty 200.
"""

import json

import pytest
from fastapi.testclient import TestClient

from core.fastapi_app import app, SSE_ENDPOINTS
from core.chat import chat_runner


class _FakeHandler:
    """Minimal stand-in for the HTTP handler: records everything written on wfile."""

    def __init__(self):
        self.chunks = []
        self.status = None
        self.headers_sent = {}
        self.wfile = self

    # --- wfile surface ---
    def write(self, b):
        self.chunks.append(b.decode("utf-8"))

    def flush(self):
        pass

    # --- handler surface ---
    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers_sent[key] = value

    def end_headers(self):
        pass

    # --- assertions helper ---
    def events(self):
        """Parse the recorded stream into decoded SSE payloads (excluding [DONE])."""
        raw = "".join(self.chunks)
        out = []
        for block in raw.split("\n\n"):
            line = block.strip()
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                continue
            out.append(json.loads(payload))
        return out


def _fake_stream(*args, **kwargs):
    yield {"token": "Ciao"}
    yield {"token": " mondo"}
    yield {"done": True, "done_reason": "stop", "truncated": False}


def _run_stream(handler, allow_actions=False):
    return chat_runner._stream_chat_response(
        handler,
        messages=[{"role": "user", "content": "ciao"}],
        ai_cfg={"providers": {"ollama": {}}},
        model="test-model",
        provider="ollama",
        endpoint="http://localhost:11434/api/chat",
        api_url="",
        api_key="",
        temperature=0.7,
        max_tokens=512,
        top_p=0.9,
        timeout=30,
        message="ciao",
        bot_name="Sigma Assistant",
        manifesto_path="manifesti/sigma_assistant.md",
        allow_actions=allow_actions,
    )


class TestSSEEndpointWhitelist:
    """The dispatcher only streams paths listed in SSE_ENDPOINTS."""

    def test_orchestrate_is_streamed(self):
        assert "/api/chat/orchestrate" in SSE_ENDPOINTS

    def test_chat_is_streamed(self):
        assert "/api/chat" in SSE_ENDPOINTS

    def test_orchestrate_events_reach_the_client(self, monkeypatch):
        """Progress events written on wfile must be delivered, not swallowed.

        The orchestrator itself is stubbed: this asserts the transport, which is
        what was broken — real events were queued and the client got an empty 200.
        """
        from core.fastapi_app import FastAPIHandlerAdapter

        def _fake_orchestrate(handler):
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.end_headers()
            for event in ({"type": "orchestrate_start"},
                          {"type": "orchestrate_plan", "total_subtasks": 2},
                          {"type": "orchestrate_done"}):
                handler.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
            handler.wfile.write(b"data: [DONE]\n\n")

        monkeypatch.setattr(FastAPIHandlerAdapter, "handle_chat_orchestrate",
                            _fake_orchestrate, raising=True)

        response = TestClient(app).post("/api/chat/orchestrate", json={"message": "goal"})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        types = [
            json.loads(line[len("data: "):])["type"]
            for line in response.text.split("\n\n")
            if line.strip().startswith("data: ") and line.strip() != "data: [DONE]"
        ]
        assert types == ["orchestrate_start", "orchestrate_plan", "orchestrate_done"]


class TestStreamChatResponse:
    """Unit coverage for the SSE writer used by /api/chat."""

    def test_emits_meta_before_any_token(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        events = handler.events()
        assert "meta" in events[0]
        assert events[0]["meta"]["agent_id"] == "sigma_assistant"
        assert events[0]["meta"]["agent_name"] == "Sigma Assistant"

    def test_tokens_are_sent_individually_as_deltas(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        tokens = [e["token"] for e in handler.events() if "token" in e]
        assert tokens == ["Ciao", " mondo"]

    def test_stream_terminates_with_done_sentinel(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        assert "".join(handler.chunks).endswith("data: [DONE]\n\n")

    def test_final_content_carries_formatted_answer(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        finals = [e for e in handler.events() if "final_content" in e]
        assert len(finals) == 1
        assert "Ciao mondo" in finals[0]["final_content"]
        assert finals[0]["created_files"] == []

    def test_event_stream_headers_are_set(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        assert handler.status == 200
        assert handler.headers_sent["Content-Type"] == "text/event-stream"

    def test_truncation_flag_is_forwarded(self, monkeypatch):
        def _truncated_stream(*args, **kwargs):
            yield {"token": "meta risposta"}
            yield {"done": True, "done_reason": "length", "truncated": True}

        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _truncated_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        assert any(e.get("truncated") for e in handler.events())

    def test_provider_error_reaches_the_client(self, monkeypatch):
        def _failing_stream(*args, **kwargs):
            yield {"error": True, "message": "Ollama non raggiungibile"}

        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _failing_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        events = handler.events()
        assert any(e.get("error") == "Ollama non raggiungibile" for e in events)
        assert not any("final_content" in e for e in events)
        assert "".join(handler.chunks).endswith("data: [DONE]\n\n")

    def test_created_files_are_reported_when_actions_allowed(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        monkeypatch.setattr(
            chat_runner, "_extract_and_create_files_from_text",
            lambda text, prompt_topic="": (
                ["data/test/nota.md"],
                [{"type": "create_file", "success": True, "path": "data/test/nota.md"}],
            ),
        )
        handler = _FakeHandler()
        _run_stream(handler, allow_actions=True)

        finals = [e for e in handler.events() if "final_content" in e]
        assert finals[0]["created_files"] == ["data/test/nota.md"]
        assert finals[0]["actions_log"][0]["type"] == "create_file"


class TestThinkTagRouter:
    """Reasoning wrapped in <think> tags must never reach the answer channel."""

    def test_splits_inline_reasoning_from_answer(self):
        router = chat_runner._ThinkTagRouter()
        out = router.feed("<think>rifletto un attimo</think>Ecco la risposta.")
        out += router.flush()

        thinking = "".join(t for c, t in out if c == "thinking")
        answer = "".join(t for c, t in out if c == "token")
        assert thinking == "rifletto un attimo"
        assert answer == "Ecco la risposta."

    def test_tag_split_across_chunks_is_not_leaked(self):
        """The tag arrives one character at a time, as a real token stream does."""
        router = chat_runner._ThinkTagRouter()
        out = []
        for piece in ["<th", "ink>seg", "reto</thi", "nk>Ciao", " a tutti."]:
            out += router.feed(piece)
        out += router.flush()

        answer = "".join(t for c, t in out if c == "token")
        thinking = "".join(t for c, t in out if c == "thinking")
        assert answer == "Ciao a tutti."
        assert thinking == "segreto"
        assert "<" not in answer

    def test_plain_text_passes_through_unchanged(self):
        router = chat_runner._ThinkTagRouter()
        out = router.feed("Nessun tag qui, solo testo.") + router.flush()
        assert "".join(t for c, t in out if c == "token") == "Nessun tag qui, solo testo."

    def test_unclosed_reasoning_block_stays_on_thinking_channel(self):
        router = chat_runner._ThinkTagRouter()
        out = router.feed("<think>mi hanno interrotto a meta") + router.flush()
        assert not [t for c, t in out if c == "token"]
        assert "".join(t for c, t in out if c == "thinking") == "mi hanno interrotto a meta"


class TestThinkingSeparation:
    """End-to-end separation of the two channels inside the SSE writer."""

    def test_inline_think_block_never_hits_the_token_channel(self, monkeypatch):
        def _reasoning_stream(*args, **kwargs):
            yield {"token": "<think>Devo contare"}
            yield {"token": " fino a tre</think>Uno, due, tre."}
            yield {"done": True, "done_reason": "stop"}

        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _reasoning_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        events = handler.events()
        tokens = "".join(e["token"] for e in events if "token" in e)
        thinking = "".join(e["thinking"] for e in events if "thinking" in e)
        final = [e for e in events if "final_content" in e][0]

        assert tokens == "Uno, due, tre."
        assert "Devo contare fino a tre" in thinking
        assert "Devo contare" not in final["final_content"]
        assert "Devo contare fino a tre" in final["final_thinking"]

    def test_native_reasoning_channel_stays_separate(self, monkeypatch):
        def _native_stream(*args, **kwargs):
            yield {"thinking": "ragiono in silenzio"}
            yield {"token": "Risposta finale."}
            yield {"done": True, "done_reason": "stop"}

        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _native_stream)
        handler = _FakeHandler()
        _run_stream(handler)

        events = handler.events()
        final = [e for e in events if "final_content" in e][0]
        assert "".join(e["token"] for e in events if "token" in e) == "Risposta finale."
        assert final["final_thinking"] == "ragiono in silenzio"
        assert "ragiono" not in final["final_content"]

    def test_reasoning_only_answer_does_not_leave_an_empty_bubble(self, monkeypatch):
        def _thinking_only(*args, **kwargs):
            yield {"thinking": "il risultato e' 42"}
            yield {"done": True, "done_reason": "stop"}

        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _thinking_only)
        handler = _FakeHandler()
        _run_stream(handler)

        final = [e for e in handler.events() if "final_content" in e][0]
        assert "42" in final["final_content"]
        assert not final["final_thinking"]


class TestOllamaStreamChannels:
    """Regression guard on the provider that used to merge the two channels."""

    def test_thinking_is_not_yielded_as_token(self, monkeypatch):
        import core.ai_providers as ai

        class _FakeResponse:
            status_code = 200

            def iter_lines(self, chunk_size=1, decode_unicode=True):
                yield json.dumps({"message": {"thinking": "sto ragionando"}})
                yield json.dumps({"message": {"content": "Ciao!"}})
                yield json.dumps({"message": {}, "done": True, "done_reason": "stop"})

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _FakeResponse())

        chunks = list(ai.call_ollama_stream([], "m", "http://x"))
        assert {"thinking": "sto ragionando"} in chunks
        assert {"token": "Ciao!"} in chunks
        assert not any(c.get("token") == "sto ragionando" for c in chunks)


class TestChatEndpointStreaming:
    """End-to-end: POST /api/chat with stream:true must deliver progressive SSE."""

    def test_chat_endpoint_streams_multiple_events(self, monkeypatch):
        monkeypatch.setattr("core.ai_providers.call_ai_model_stream", _fake_stream)
        client = TestClient(app)

        response = client.post("/api/chat", json={
            "message": "ciao",
            "stream": True,
            "allow_actions": False,
            "model": "test-model",
        })

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        payloads = [
            line[len("data: "):]
            for line in response.text.split("\n\n")
            if line.strip().startswith("data: ")
        ]
        assert payloads[-1] == "[DONE]"

        decoded = [json.loads(p) for p in payloads if p != "[DONE]"]
        # More than one event is the whole point: the old path emitted exactly one.
        assert len(decoded) > 1
        assert "meta" in decoded[0]
        assert [e["token"] for e in decoded if "token" in e] == ["Ciao", " mondo"]
