# ==============================================================================
# core/tts/base.py — Neural TTS Engine Contract
# Sigma Studio v8 — Voice Synthesis Sub-package
# ==============================================================================
"""Base class and WAV helpers shared by every speech synthesis engine.

Engines are optional: their heavy dependencies (torch pipelines, model weights)
are imported lazily inside ``_load`` so that a missing package degrades into
``available: false`` plus an install hint, never into an import error at boot.
"""

import io
import struct
import threading
import wave

from core.logger import get_logger

log = get_logger(__name__)


def pcm_to_wav(samples, sample_rate: int) -> bytes:
    """Encode float samples in [-1, 1] (or int16) as a mono 16-bit WAV."""
    frames = bytearray()
    for value in samples:
        if isinstance(value, int):
            clipped = max(-32768, min(32767, value))
        else:
            clipped = int(max(-1.0, min(1.0, float(value))) * 32767)
        frames += struct.pack("<h", clipped)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


class TTSEngine:
    """A speech synthesis backend that turns text into WAV audio."""

    id = "base"
    name = "Base Engine"
    description = ""
    license = ""
    install_hint = ""
    sample_rate = 24000
    default_voice = ""

    def __init__(self):
        self._model = None
        self._load_error = None
        # The pre-warm thread and the first sentence of an answer can arrive at
        # the same moment. Without this both would download and build the model
        # concurrently; one of them loses the race, marks the engine broken, and
        # every later sentence silently degrades to the system voice.
        self._lock = threading.Lock()

    # --- capability probing ---

    def is_installed(self) -> bool:
        """True when the Python dependencies are importable."""
        raise NotImplementedError

    def list_voices(self) -> list[dict]:
        """Return [{id, name, lang, gender}, …] — cheap, no model load."""
        return []

    # --- synthesis ---

    def _load(self):
        """Instantiate the underlying model. Called once, lazily."""
        raise NotImplementedError

    def _synthesize(self, text: str, voice: str, speed: float):
        """Return an iterable of samples for `text`. Model is already loaded."""
        raise NotImplementedError

    def synthesize(self, text: str, voice: str = "", speed: float = 1.0) -> bytes:
        """Render `text` to WAV bytes, loading the model on first use."""
        if not text or not text.strip():
            return b""

        # Held across inference too: the underlying torch pipelines are not
        # thread-safe, and at ~50x realtime serialising costs nothing.
        with self._lock:
            if self._model is None:
                if self._load_error:
                    raise RuntimeError(self._load_error)
                try:
                    self._model = self._load()
                except Exception as exc:
                    # Remembered so a broken install fails fast instead of retrying
                    # a multi-second import on every sentence.
                    self._load_error = f"{self.name}: {exc}"
                    log.error("TTS engine '%s' failed to load: %s", self.id, exc, exc_info=True)
                    raise RuntimeError(self._load_error) from exc

            samples = self._synthesize(text, voice or self.default_voice, speed)

        return pcm_to_wav(samples, self.sample_rate)

    # --- reporting ---

    def status(self) -> dict:
        installed = False
        try:
            installed = self.is_installed()
        except Exception as exc:
            log.debug("Availability probe failed for '%s': %s", self.id, exc)

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "installed": installed,
            "loaded": self._model is not None,
            "error": self._load_error,
            "install_hint": self.install_hint,
            "sample_rate": self.sample_rate,
            "default_voice": self.default_voice,
            "voices": self.list_voices() if installed else [],
        }
