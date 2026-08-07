# ==============================================================================
# core/tts_handler.py — Voice Synthesis Endpoints
# ==============================================================================
"""REST surface for the neural TTS engines.

Audio comes back base64-encoded inside JSON rather than as a binary body: the
client speaks one sentence at a time while the answer is still streaming, so
each payload is short-lived and small, and this keeps the endpoint on the same
dispatch path as every other handler.
"""

import base64
import threading

from core.logger import get_logger
from core.tts import list_engines, prewarm, resolve_default, synthesize

log = get_logger(__name__)

# Guards against a runaway request pinning the GPU for minutes.
MAX_TEXT_CHARS = 1200

_prewarm_started = threading.Event()


def handle_tts_engines(self):
    """GET /api/tts/engines — Engines, voices and install status."""
    try:
        payload = {
            "success": True,
            "engines": list_engines(),
            "default": resolve_default(),
        }
        # The client calls this on page load: a good moment to absorb the
        # one-off model load in the background, off the request thread.
        if not _prewarm_started.is_set():
            _prewarm_started.set()
            threading.Thread(target=prewarm, daemon=True).start()
        return self.send_json_response(payload)
    except Exception as exc:
        log.error("handle_tts_engines error: %s", exc, exc_info=True)
        return self.send_json_response({"error": str(exc)}, 500)


def handle_tts_speak(self):
    """POST /api/tts/speak — Synthesize one chunk of text to WAV audio."""
    try:
        req = self.read_json_body()
        text = (req.get("text") or "").strip()
        if not text:
            return self.send_json_response({"error": "Testo vuoto"}, 400)
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]

        engine_id = req.get("engine") or resolve_default()["engine"]
        voice = req.get("voice") or ""
        try:
            speed = float(req.get("speed") or 1.0)
        except (TypeError, ValueError):
            speed = 1.0
        speed = max(0.5, min(2.0, speed))

        if engine_id == "browser":
            return self.send_json_response(
                {"error": "Il motore 'browser' viene sintetizzato dal client."}, 400
            )

        audio = synthesize(engine_id, text, voice, speed)
        if not audio:
            return self.send_json_response({"error": "Nessun audio generato"}, 500)

        return self.send_json_response({
            "success": True,
            "engine": engine_id,
            "voice": voice,
            "format": "wav",
            "audio": base64.b64encode(audio).decode("ascii"),
        })
    except (ValueError, RuntimeError) as exc:
        # Missing dependency or unknown engine: actionable, not a server fault.
        return self.send_json_response({"error": str(exc)}, 503)
    except Exception as exc:
        log.error("handle_tts_speak error: %s", exc, exc_info=True)
        return self.send_json_response({"error": str(exc)}, 500)
