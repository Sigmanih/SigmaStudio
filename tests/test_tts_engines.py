# ==============================================================================
# tests/test_tts_engines.py — Test Suite for Neural Voice Synthesis
# Sigma Studio v8.2 — Kokoro & XTTS v2 Integration
# ==============================================================================
"""Tests for the TTS engine registry, the WAV encoder and the /api/tts endpoints.

The neural models themselves are optional and usually absent: these tests cover
the contract around them — graceful degradation, install hints, engine
selection — plus synthesis against a stub engine.
"""

import base64
import io
import threading
import time
import wave

import pytest
from fastapi.testclient import TestClient

from core.fastapi_app import app
from core.tts import registry
from core.tts.base import TTSEngine, pcm_to_wav
from core.tts.kokoro_engine import KokoroEngine
from core.tts.xtts_engine import XttsEngine


class _StubEngine(TTSEngine):
    """Engine that pretends to be installed and emits a short ramp."""

    id = "stub"
    name = "Stub Engine"
    install_hint = "pip install nothing"
    sample_rate = 8000
    default_voice = "stub_voice"

    def __init__(self, installed=True):
        super().__init__()
        self._installed = installed
        self.loads = 0
        self.last_call = None

    def is_installed(self):
        return self._installed

    def list_voices(self):
        return [{"id": "stub_voice", "name": "Stub", "lang": "it-IT", "gender": "female"}]

    def _load(self):
        self.loads += 1
        return object()

    def _synthesize(self, text, voice, speed):
        self.last_call = (text, voice, speed)
        return [0.0, 0.5, -0.5, 1.0]


class TestWavEncoding:
    def test_produces_a_readable_mono_16bit_wav(self):
        data = pcm_to_wav([0.0, 0.5, -0.5], 24000)
        with wave.open(io.BytesIO(data), "rb") as handle:
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getframerate() == 24000
            assert handle.getnframes() == 3

    def test_clips_instead_of_wrapping_around(self):
        """A sample above 1.0 must saturate, not wrap to a loud negative click."""
        data = pcm_to_wav([5.0, -5.0], 8000)
        with wave.open(io.BytesIO(data), "rb") as handle:
            frames = handle.readframes(2)
        assert frames == b"\xff\x7f\x01\x80"  # +32767, -32767


class TestEngineLifecycle:
    def test_model_is_loaded_once_and_only_on_first_use(self):
        engine = _StubEngine()
        assert engine.loads == 0
        engine.synthesize("ciao", "stub_voice")
        engine.synthesize("ancora", "stub_voice")
        assert engine.loads == 1

    def test_empty_text_never_loads_the_model(self):
        engine = _StubEngine()
        assert engine.synthesize("   ") == b""
        assert engine.loads == 0

    def test_load_failure_is_remembered_and_not_retried(self, monkeypatch):
        engine = _StubEngine()
        monkeypatch.setattr(engine, "_load", lambda: (_ for _ in ()).throw(OSError("modello mancante")))

        with pytest.raises(RuntimeError, match="modello mancante"):
            engine.synthesize("ciao")
        with pytest.raises(RuntimeError, match="modello mancante"):
            engine.synthesize("ciao")

    def test_concurrent_first_calls_load_the_model_exactly_once(self):
        """The pre-warm thread and the first sentence race on the same engine.

        Two loads meant one of them failing, the engine being flagged broken, and
        the client falling back to the system voice while neural clips were still
        playing — two voices at once.
        """
        engine = _StubEngine()
        slow_load = engine._load

        def _slow():
            time.sleep(0.05)
            return slow_load()

        engine._load = _slow

        threads = [threading.Thread(target=engine.synthesize, args=("ciao",)) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert engine.loads == 1
        assert engine._load_error is None

    def test_speed_and_voice_reach_the_backend(self):
        engine = _StubEngine()
        engine.synthesize("prova", "altra_voce", 1.4)
        assert engine.last_call == ("prova", "altra_voce", 1.4)

    def test_status_reports_install_hint_when_missing(self):
        engine = _StubEngine(installed=False)
        status = engine.status()
        assert status["installed"] is False
        assert status["install_hint"] == "pip install nothing"
        assert status["voices"] == []


class TestRegistry:
    def test_browser_engine_is_always_offered(self):
        ids = [e["id"] for e in registry.list_engines()]
        assert ids[0] == "browser"
        assert {"kokoro", "xtts"} <= set(ids)

    def test_missing_engines_report_how_to_install_them(self):
        for entry in registry.list_engines():
            if entry["id"] != "browser" and not entry["installed"]:
                assert entry["install_hint"]

    def test_default_falls_back_to_browser_when_nothing_is_installed(self, monkeypatch):
        for engine in registry._ENGINES.values():
            monkeypatch.setattr(engine, "is_installed", lambda: False)
        assert registry.resolve_default() == {"engine": "browser", "voice": ""}

    def test_kokoro_wins_over_xtts_when_both_are_installed(self, monkeypatch):
        for engine in registry._ENGINES.values():
            monkeypatch.setattr(engine, "is_installed", lambda: True)
        assert registry.resolve_default() == {"engine": "kokoro", "voice": "if_sara"}

    def test_synthesize_on_a_missing_engine_explains_the_fix(self, monkeypatch):
        kokoro = registry.get_engine("kokoro")
        monkeypatch.setattr(kokoro, "is_installed", lambda: False)
        with pytest.raises(RuntimeError, match="pip install kokoro"):
            registry.synthesize("kokoro", "ciao")

    def test_unknown_engine_is_rejected(self):
        with pytest.raises(ValueError):
            registry.synthesize("inesistente", "ciao")

    def test_prewarm_loads_the_default_engine(self, monkeypatch):
        stub = _StubEngine()
        monkeypatch.setitem(registry._ENGINES, "stub", stub)
        monkeypatch.setattr(registry, "resolve_default",
                            lambda: {"engine": "stub", "voice": "stub_voice"})
        registry.prewarm()
        assert stub.loads == 1

    def test_prewarm_never_raises_when_nothing_is_installed(self, monkeypatch):
        for engine in registry._ENGINES.values():
            monkeypatch.setattr(engine, "is_installed", lambda: False)
        registry.prewarm()  # resolves to 'browser', which has no model to load


class TestEngineMetadata:
    def test_kokoro_offers_italian_voices(self):
        voices = KokoroEngine().list_voices()
        assert {v["id"] for v in voices} == {"if_sara", "im_nicola"}
        assert all(v["lang"] == "it-IT" for v in voices)

    def test_xtts_licence_restriction_is_visible(self):
        """The non-commercial licence must reach the UI, not stay in a comment."""
        assert "non commerciale" in XttsEngine().license.lower()

    def test_kokoro_licence_allows_commercial_use(self):
        assert "apache" in KokoroEngine().license.lower()


class TestTtsEndpoints:
    def test_engines_endpoint_lists_status_and_default(self):
        response = TestClient(app).get("/api/tts/engines")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert [e["id"] for e in data["engines"]][0] == "browser"
        assert "engine" in data["default"]

    def test_speak_returns_playable_base64_audio(self, monkeypatch):
        stub = _StubEngine()
        monkeypatch.setitem(registry._ENGINES, "stub", stub)

        response = TestClient(app).post("/api/tts/speak", json={
            "text": "ciao mondo", "engine": "stub", "voice": "stub_voice",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "wav"

        with wave.open(io.BytesIO(base64.b64decode(data["audio"])), "rb") as handle:
            assert handle.getframerate() == 8000
            assert handle.getnframes() == 4

    def test_speak_rejects_empty_text(self):
        response = TestClient(app).post("/api/tts/speak", json={"text": "  "})
        assert response.status_code == 400

    def test_speak_refuses_the_browser_engine(self):
        response = TestClient(app).post("/api/tts/speak", json={
            "text": "ciao", "engine": "browser",
        })
        assert response.status_code == 400

    def test_missing_engine_answers_503_with_the_install_command(self, monkeypatch):
        kokoro = registry.get_engine("kokoro")
        monkeypatch.setattr(kokoro, "is_installed", lambda: False)

        response = TestClient(app).post("/api/tts/speak", json={
            "text": "ciao", "engine": "kokoro",
        })
        assert response.status_code == 503
        assert "pip install kokoro" in response.json()["error"]

    def test_overlong_text_is_truncated_not_rejected(self, monkeypatch):
        stub = _StubEngine()
        monkeypatch.setitem(registry._ENGINES, "stub", stub)

        TestClient(app).post("/api/tts/speak", json={
            "text": "a" * 5000, "engine": "stub",
        })
        assert len(stub.last_call[0]) == 1200

    def test_speed_is_clamped_to_a_sane_range(self, monkeypatch):
        stub = _StubEngine()
        monkeypatch.setitem(registry._ENGINES, "stub", stub)

        TestClient(app).post("/api/tts/speak", json={
            "text": "ciao", "engine": "stub", "speed": 99,
        })
        assert stub.last_call[2] == 2.0
