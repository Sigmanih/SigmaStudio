# ==============================================================================
# core/tts/xtts_engine.py — Coqui XTTS v2 Neural TTS
# ==============================================================================
"""XTTS v2 produces the most expressive Italian voices available offline and can
clone a speaker from a few seconds of reference audio.

Two caveats are surfaced to the UI rather than hidden:
  · the model is released under the Coqui Public Model License — **non
    commercial**, which conflicts with the commercial half of this project's
    dual licence;
  · `coqui-tts` pins a narrow `transformers` range and installing it in the same
    environment can disturb the Training Lab stack.
"""

import importlib.util
import os

from core.tts.base import TTSEngine

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

# XTTS v2 ships these studio speakers; any of them can read Italian.
VOICES = [
    {"id": "Claribel Dervla", "name": "Claribel", "lang": "it-IT", "gender": "female"},
    {"id": "Daisy Studious", "name": "Daisy", "lang": "it-IT", "gender": "female"},
    {"id": "Gracie Wise", "name": "Gracie", "lang": "it-IT", "gender": "female"},
    {"id": "Damien Black", "name": "Damien", "lang": "it-IT", "gender": "male"},
    {"id": "Viktor Menelaos", "name": "Viktor", "lang": "it-IT", "gender": "male"},
]


class XttsEngine(TTSEngine):
    id = "xtts"
    name = "XTTS v2"
    description = "Voce neurale espressiva con clonazione del parlante. Richiede GPU per essere fluida."
    license = "Coqui Public Model License — solo uso non commerciale"
    install_hint = "pip install coqui-tts  (attenzione: fissa una versione di transformers, può interferire con il Training Lab)"
    sample_rate = 24000
    default_voice = "Claribel Dervla"

    def is_installed(self) -> bool:
        return importlib.util.find_spec("TTS") is not None

    def list_voices(self) -> list[dict]:
        return list(VOICES)

    def _load(self):
        # Accepts the model licence non-interactively; without it the loader
        # blocks on a stdin prompt that never arrives in a server process.
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        from TTS.api import TTS

        gpu = False
        try:
            import torch
            gpu = torch.cuda.is_available()
        except Exception:
            pass
        return TTS(MODEL_NAME, gpu=gpu)

    def _synthesize(self, text: str, voice: str, speed: float):
        known = {v["id"] for v in VOICES}
        if voice not in known:
            voice = self.default_voice
        return self._model.tts(text=text, speaker=voice, language="it", speed=speed)
