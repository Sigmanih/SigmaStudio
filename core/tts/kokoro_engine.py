# ==============================================================================
# core/tts/kokoro_engine.py — Kokoro 82M Neural TTS
# ==============================================================================
"""Kokoro is a small (82M parameter) Apache-2.0 TTS model.

It is the recommended default: the weights are ~330 MB, it runs comfortably on
CPU, and — unlike XTTS v2 — its licence puts no restriction on commercial use,
which matters for a dual-licensed project.
"""

import importlib.util

from core.tts.base import TTSEngine

# lang_code 'i' selects the Italian frontend inside Kokoro's phonemiser.
KOKORO_LANG = "i"
KOKORO_REPO = "hexgrad/Kokoro-82M"

VOICES = [
    {"id": "if_sara", "name": "Sara", "lang": "it-IT", "gender": "female"},
    {"id": "im_nicola", "name": "Nicola", "lang": "it-IT", "gender": "male"},
]


class KokoroEngine(TTSEngine):
    id = "kokoro"
    name = "Kokoro 82M"
    description = "Voce neurale leggera, gira su CPU. Voci italiane Sara e Nicola."
    license = "Apache-2.0 (uso commerciale consentito)"
    install_hint = "pip install kokoro soundfile misaki[it]"
    sample_rate = 24000
    default_voice = "if_sara"

    def is_installed(self) -> bool:
        return importlib.util.find_spec("kokoro") is not None

    def list_voices(self) -> list[dict]:
        return list(VOICES)

    def _load(self):
        from kokoro import KPipeline
        return KPipeline(lang_code=KOKORO_LANG, repo_id=KOKORO_REPO)

    def _synthesize(self, text: str, voice: str, speed: float):
        known = {v["id"] for v in VOICES}
        if voice not in known:
            voice = self.default_voice

        samples = []
        for _graphemes, _phonemes, audio in self._model(text, voice=voice, speed=speed):
            if audio is None:
                continue
            # torch tensor / numpy array / plain sequence, depending on version
            samples.extend(audio.tolist() if hasattr(audio, "tolist") else list(audio))
        return samples
