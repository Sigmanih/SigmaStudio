"""Vision Agent — gli occhi di Sigma sugli asset creativi.

Usa un modello multimodale locale via Ollama (Qwen2.5-VL di default) per:

  - descrivere un'immagine (input per i prompt a valle)
  - rispondere a domande sull'immagine / estrarre testo
  - valutare la qualità di un output rispetto all'intento (Quality Agent)
  - confrontare input e output di una modifica

Il punteggio prodotto finisce in `asset.metadata['quality_score']`, che l'asset
graph già espone: è il segnale che permette a una pipeline di decidere se
rigenerare invece di proseguire.
"""

import base64
import json
import os
import re

import aiohttp

from core.creative.asset_graph import AssetGraph
from core.logger import get_logger

log = get_logger("creative_vision_agent")

DEFAULT_MODEL = "qwen2.5vl:7b"
DEFAULT_ENDPOINT = "http://localhost:11434"

ANALYZE_PROMPT = """Analizza questa immagine e rispondi SOLO con JSON valido, senza testo attorno:
{
  "subject": "soggetto principale in poche parole",
  "style": "stile visivo",
  "composition": "note su inquadratura e composizione",
  "colors": ["colore1", "colore2"],
  "text_in_image": "testo leggibile nell'immagine, o stringa vuota",
  "issues": ["difetti evidenti: artefatti, mani deformi, testo illeggibile, ..."],
  "quality_score": 0.0
}
quality_score va da 0.0 (inutilizzabile) a 1.0 (pronta per la produzione)."""

SCORE_PROMPT = """L'immagine doveva rappresentare: "{intent}".
Rispondi SOLO con JSON valido:
{{
  "matches_intent": true,
  "quality_score": 0.0,
  "issues": ["..."],
  "suggested_prompt_fix": "come riformulare il prompt per migliorare, o stringa vuota"
}}"""


def _extract_json(text: str) -> dict | None:
    """Estrae il primo oggetto JSON dalla risposta del modello.

    I VLM aggiungono spesso prosa o fence markdown attorno al JSON richiesto.
    """
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end > start else None
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


class VisionAgent:
    def __init__(self, asset_graph: AssetGraph, config: dict = None):
        config = config or {}
        self.asset_graph = asset_graph
        self.endpoint = (config.get("ollama_url") or DEFAULT_ENDPOINT).rstrip("/")
        self.model = config.get("vision_model") or DEFAULT_MODEL
        self.timeout = int(config.get("vision_timeout", 180))

    # ------------------------------------------------------------------

    def _image_b64(self, asset_id: str) -> tuple[str, str]:
        asset = self.asset_graph.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset non trovato: {asset_id}")
        path = asset.files.get("image") or asset.files.get("albedo")
        if not path or not os.path.exists(path):
            raise ValueError(f"L'asset '{asset.name}' non ha un'immagine analizzabile")
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8"), asset.name

    async def available(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.endpoint}/api/tags", timeout=3) as resp:
                    if resp.status != 200:
                        return False
                    names = [m.get("name", "") for m in (await resp.json()).get("models", [])]
                    return any(n.split(":")[0] == self.model.split(":")[0] for n in names)
        except Exception:
            return False

    async def _ask(self, image_b64: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.endpoint}/api/generate", json=payload) as resp:
                if resp.status == 404:
                    raise RuntimeError(
                        f"Modello vision '{self.model}' non installato. Esegui: ollama pull {self.model}"
                    )
                if resp.status != 200:
                    raise RuntimeError(f"Ollama vision error {resp.status}: {(await resp.text())[:300]}")
                return (await resp.json()).get("response", "")

    # ------------------------------------------------------------------
    # Capability
    # ------------------------------------------------------------------

    async def describe(self, asset_id: str, question: str = None) -> dict:
        """Descrizione in linguaggio naturale (o risposta a una domanda)."""
        image_b64, name = self._image_b64(asset_id)
        prompt = question or "Descrivi questa immagine in modo dettagliato e oggettivo, in italiano."
        text = await self._ask(image_b64, prompt)
        log.info(f"Vision describe su {asset_id} ({len(text)} caratteri)")
        return {"asset_id": asset_id, "asset": name, "model": self.model,
                "question": question, "description": text.strip()}

    async def analyze(self, asset_id: str) -> dict:
        """Analisi strutturata; il quality_score viene persistito sull'asset."""
        image_b64, _ = self._image_b64(asset_id)
        raw = await self._ask(image_b64, ANALYZE_PROMPT)
        data = _extract_json(raw)
        if data is None:
            # Il modello non ha rispettato il formato: la descrizione resta utile.
            return {"asset_id": asset_id, "model": self.model, "raw": raw.strip(), "parsed": False}

        data["asset_id"] = asset_id
        data["model"] = self.model
        data["parsed"] = True
        self._persist_analysis(asset_id, data)
        return data

    async def score(self, asset_id: str, intent: str) -> dict:
        """Quality Agent: quanto l'output rispetta l'intento richiesto."""
        image_b64, _ = self._image_b64(asset_id)
        raw = await self._ask(image_b64, SCORE_PROMPT.format(intent=intent))
        data = _extract_json(raw) or {"quality_score": None, "raw": raw.strip(), "parsed": False}
        data.update({"asset_id": asset_id, "intent": intent, "model": self.model})
        if data.get("quality_score") is not None:
            self._persist_analysis(asset_id, data)
        return data

    async def compare(self, asset_a: str, asset_b: str, criteria: str = "") -> dict:
        """Confronto A/B fra due versioni dello stesso asset."""
        a_b64, a_name = self._image_b64(asset_a)
        b_b64, b_name = self._image_b64(asset_b)
        # Ollama accetta più immagini in un solo turno: la valutazione resta contestuale.
        payload_prompt = (
            "Ti mostro due immagini: la prima è l'originale, la seconda la versione modificata.\n"
            f"Criterio di valutazione: {criteria or 'qualità complessiva e coerenza'}.\n"
            'Rispondi SOLO con JSON: {"winner": "a"|"b", "reason": "...", '
            '"regression_risk": ["..."]}'
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        payload = {"model": self.model, "prompt": payload_prompt,
                   "images": [a_b64, b_b64], "stream": False, "options": {"temperature": 0.1}}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.endpoint}/api/generate", json=payload) as resp:
                raw = (await resp.json()).get("response", "") if resp.status == 200 else ""

        data = _extract_json(raw) or {"raw": raw.strip(), "parsed": False}
        data.update({"a": {"asset_id": asset_a, "name": a_name},
                     "b": {"asset_id": asset_b, "name": b_name}, "model": self.model})
        return data

    async def extract_text(self, asset_id: str) -> dict:
        """OCR: utile per validare poster/mockup generati con testo."""
        image_b64, _ = self._image_b64(asset_id)
        raw = await self._ask(image_b64, "Trascrivi ESATTAMENTE tutto il testo leggibile "
                                         "nell'immagine. Se non c'è testo rispondi con una stringa vuota.")
        return {"asset_id": asset_id, "text": raw.strip(), "model": self.model}

    # ------------------------------------------------------------------

    def _persist_analysis(self, asset_id: str, data: dict) -> None:
        asset = self.asset_graph.get_asset(asset_id)
        if not asset:
            return
        metadata = dict(asset.metadata)
        metadata["vision"] = {k: v for k, v in data.items() if k not in ("asset_id", "parsed")}
        if data.get("quality_score") is not None:
            try:
                metadata["quality_score"] = round(float(data["quality_score"]), 3)
            except (TypeError, ValueError):
                pass
        self.asset_graph.update_asset(asset_id, metadata=metadata)
