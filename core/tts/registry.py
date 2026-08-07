# ==============================================================================
# core/tts/registry.py — Voice Engine Registry
# ==============================================================================
"""Single place that knows which speech engines exist and which one to use.

`browser` is always present: it is the Web Speech API running in the client, so
it needs no Python dependency and acts as the guaranteed fallback when no neural
engine is installed.
"""

from core.logger import get_logger
from core.tts.kokoro_engine import KokoroEngine
from core.tts.xtts_engine import XttsEngine

log = get_logger(__name__)

BROWSER_ENGINE = {
    "id": "browser",
    "name": "Voce di sistema (Web Speech)",
    "description": "Voci installate nel sistema operativo. Nessun download, qualità limitata.",
    "license": "—",
    "installed": True,
    "loaded": True,
    "error": None,
    "install_hint": "",
    "sample_rate": 0,
    "default_voice": "",
    "voices": [],
}

# Ordered by preference: the first installed engine wins as default.
_ENGINES = {}
for engine_cls in (KokoroEngine, XttsEngine):
    instance = engine_cls()
    _ENGINES[instance.id] = instance


def get_engine(engine_id: str):
    """Return the engine instance, or None for unknown/browser ids."""
    return _ENGINES.get(engine_id)


def list_engines() -> list[dict]:
    """Status of every engine, browser fallback first."""
    return [BROWSER_ENGINE] + [engine.status() for engine in _ENGINES.values()]


def resolve_default() -> dict:
    """Pick the best engine available right now.

    Preference order matches `_ENGINES`: a locally installed neural voice always
    beats the system voices, and Kokoro beats XTTS because its licence is
    unrestricted and it does not need a GPU to keep up with the chat stream.
    """
    for engine in _ENGINES.values():
        try:
            if engine.is_installed():
                return {"engine": engine.id, "voice": engine.default_voice}
        except Exception as exc:
            log.debug("Default probe failed for '%s': %s", engine.id, exc)
    return {"engine": "browser", "voice": ""}


def prewarm() -> None:
    """Load the default engine's model ahead of the first sentence.

    Loading Kokoro costs ~7s while synthesis itself runs ~50x faster than
    realtime; paying that on the first sentence of an answer would be audible as
    a long silence. The client probes engines on page load, which is a good
    moment to absorb it.
    """
    default = resolve_default()
    engine = get_engine(default["engine"])
    if engine is None or engine._model is not None or engine._load_error:
        return
    try:
        engine.synthesize("Pronto.", default["voice"])
        log.info("TTS engine '%s' pre-warmed", engine.id)
    except Exception as exc:
        log.warning("TTS pre-warm for '%s' failed: %s", engine.id, exc)


def synthesize(engine_id: str, text: str, voice: str = "", speed: float = 1.0) -> bytes:
    """Render text to WAV with the requested engine."""
    engine = get_engine(engine_id)
    if engine is None:
        raise ValueError(f"Motore vocale '{engine_id}' non disponibile lato server.")
    if not engine.is_installed():
        raise RuntimeError(
            f"{engine.name} non è installato. Installalo con: {engine.install_hint}"
        )
    return engine.synthesize(text, voice, speed)
