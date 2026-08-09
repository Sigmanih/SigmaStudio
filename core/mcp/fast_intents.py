# ==============================================================================
# core/mcp/fast_intents.py — Corsia veloce per i comandi diretti
# ==============================================================================
"""«Spegni le luci dell'ufficio» non merita un giro di ragionamento.

Un modello da 35 miliardi di parametri che macina qualche secondo per arrivare a
`{"state": "off", "area": "ufficio"}` è tempo speso male, e per giunta è il
punto in cui i modelli locali sbagliano di più: inventano identificativi,
dimenticano parametri obbligatori, o scrivono un manuale invece di agire.

Qui c'è un riconoscitore deterministico per il pugno di frasi che compongono la
quasi totalità dei comandi domestici. Quando riconosce con certezza, il comando
parte subito. Quando non riconosce — ed è progettato per arrendersi facilmente —
non fa nulla e la richiesta prosegue verso l'agente completo, che resta l'unico
a occuparsi di tutto ciò che richiede davvero di ragionare.

Tre proprietà che rendono sicuro anticipare l'LLM:

* si arrende al minimo dubbio: nessun bersaglio risolto, nessuna azione;
* non aggira niente — il comando passa dallo stesso cancello di governance, e
  uno strumento sensibile chiede conferma esattamente come prima;
* non inventa identificativi: il bersaglio si risolve sul registro vero, e se
  non c'è, la frase torna all'agente invece di diventare una chiamata a caso.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

# Oltre questa lunghezza non è più un comando: è una richiesta, e va all'agente.
MAX_COMMAND_CHARS = 90

_ON = r"accend\w*|attiv\w*|apri|alza"
_OFF = r"spegn\w*|disattiv\w*|chiudi|stacca"
_LIGHTS = r"luc[ei]|lampad\w*|illuminazione|abat.?jour|faretti?"
_SWITCHES = r"pres[ae]|interruttor[ei]|ciabatta"

# Parole che segnalano una domanda o una condizione: lì serve l'agente, non un
# comando secco. "spegni le luci se ho finito" non è un intento diretto.
_NEEDS_THINKING = re.compile(
    r"\b(se|quando|dopo|prima|perch\w*|come|potresti|dovresti|puoi|sapere|"
    r"spiegami|spiega|dimmi|cosa|quale|quali|oppure|altrimenti|ogni volta|"
    r"vorrei|farebbe|istruzioni|esempio)\b"
)

_COLORS = {
    "rosso": "red", "verde": "green", "blu": "blue", "giallo": "yellow",
    "arancione": "orange", "viola": "purple", "rosa": "pink", "bianco": "white",
    "azzurro": "cyan", "turchese": "turquoise", "magenta": "magenta",
}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def _normalize(text: str) -> str:
    return _strip_accents(str(text).lower()).strip()


def _tokens(text: str) -> str:
    """La frase ridotta a parole separate da spazi singoli.

    Serve a far combaciare "dell'ufficio" con l'area "Ufficio": analizzare le
    preposizioni italiane era fragile — l'elisione senza spazio, che è la forma
    più comune di tutte, sfuggiva mentre una domanda ci cascava dentro.
    """
    return " " + re.sub(r"[^a-z0-9]+", " ", _normalize(text)).strip() + " "


def _readable(entity_id: str) -> str:
    """`light.luce_ufficio_1` → `luce ufficio 1`, per il riepilogo in chat."""
    return entity_id.split(".", 1)[-1].replace("_", " ")


class HomeIntentMatcher:
    """Riconosce i comandi domestici diretti e li traduce in chiamate."""

    def __init__(self, server):
        self.server = server

    # --- risoluzione del bersaglio ------------------------------------------

    def _candidates(self, domain: str) -> List[Dict[str, Any]]:
        """Ogni nome con cui l'utente può indicare una stanza o un apparecchio."""
        found: List[Dict[str, Any]] = []

        try:
            for area in self.server._handle_list_areas(domain=domain).get("areas", []):
                if not area.get("entities"):
                    continue                     # una stanza senza luci non è un bersaglio
                for name in {area.get("name", ""), area.get("id", "")}:
                    if name:
                        found.append({"kind": "area", "name": name, "value": area["name"],
                                      "entities": set(area["entities"])})
        except Exception as exc:
            log.debug("Corsia veloce: aree non leggibili (%s)", exc)

        try:
            states = self.server._request("GET", "states")
            for entry in states if isinstance(states, list) else []:
                entity_id = entry.get("entity_id", "")
                if not entity_id.startswith(f"{domain}."):
                    continue
                names = {entity_id.split(".", 1)[1]}
                friendly = (entry.get("attributes") or {}).get("friendly_name")
                if friendly:
                    names.add(friendly)
                for name in names:
                    found.append({"kind": "entity", "name": name, "value": entity_id})
        except Exception as exc:
            log.debug("Corsia veloce: entità non leggibili (%s)", exc)

        return found

    @staticmethod
    def _matched_words(message_tokens: str, name: str) -> Optional[set]:
        """Le parole del nome, se compaiono TUTTE nel messaggio — anche sparse.

        Cercare il nome come sequenza contigua non bastava: "accendi luce 1 in
        ufficio" non contiene "luce ufficio 1" di fila, quindi combaciava solo
        l'area e partiva l'intera stanza. Chiedere che ci siano tutte le parole,
        ovunque, riconosce l'apparecchio senza dover indovinare l'ordine.
        """
        words = [w for w in _tokens(name).split() if w]
        if not words:
            return None
        if all(f" {w} " in message_tokens for w in words):
            return set(words)
        return None

    def _resolve(self, text: str, domain: str) -> Optional[Dict[str, Any]]:
        """Il bersaglio nominato nella frase: una stanza, uno o più apparecchi.

        Nominare un apparecchio è più specifico che nominare la stanza in cui
        sta, ma solo quando lo si è nominato *davvero*: le parole dell'entità
        devono aggiungere qualcosa a quelle dell'area. "luce 1 in ufficio" le
        aggiunge — "luci in cucina", dove la lampada si chiama come la stanza,
        no, e lì si intende tutta la stanza.
        """
        tokens = _tokens(text)
        areas: Dict[str, Dict[str, Any]] = {}
        entities: Dict[str, set] = {}

        for candidate in self._candidates(domain):
            matched = self._matched_words(tokens, candidate["name"])
            if not matched:
                continue
            if candidate["kind"] == "area":
                # Un'area compare due volte, col nome e con l'id: tiene la
                # corrispondenza più ricca delle due.
                known = areas.get(candidate["value"])
                if not known or len(matched) > len(known["matched"]):
                    areas[candidate["value"]] = {"matched": matched,
                                                 "entities": candidate["entities"]}
            else:
                if len(matched) > len(entities.get(candidate["value"], ())):
                    entities[candidate["value"]] = matched

        if len(areas) > 1:
            return None                          # due stanze nominate: decide l'agente
        area_name, area = next(iter(areas.items())) if areas else (None, None)

        if entities:
            chosen = dict(entities)
            if area:
                # Solo gli apparecchi di quella stanza, e solo se il loro nome
                # dice qualcosa in più del nome della stanza.
                chosen = {eid: words for eid, words in chosen.items()
                          if eid in area["entities"] and words > area["matched"]}
            if chosen:
                return {"kind": "entity", "value": sorted(chosen)}

        if area:
            return {"kind": "area", "value": area_name}
        return None

    # --- riconoscimento ------------------------------------------------------

    def match(self, message: str) -> Optional[Dict[str, Any]]:
        text = _normalize(message)
        if len(text) > MAX_COMMAND_CHARS or _NEEDS_THINKING.search(text):
            return None

        turning_on = bool(re.search(rf"\b(?:{_ON})\b", text))
        turning_off = bool(re.search(rf"\b(?:{_OFF})\b", text))
        if turning_on == turning_off:            # nessuno dei due, o entrambi
            return None

        is_light = bool(re.search(rf"\b(?:{_LIGHTS})\b", text))
        is_switch = bool(re.search(rf"\b(?:{_SWITCHES})\b", text))
        if is_light == is_switch:
            return None

        domain = "light" if is_light else "switch"
        tool = "ha_light_set" if is_light else "ha_switch_set"
        arguments: Dict[str, Any] = {"state": "on" if turning_on else "off"}

        target = self._resolve(text, domain)
        if not target:
            return None                          # bersaglio non risolto: decide l'agente

        verb = "Accendo" if turning_on else "Spengo"
        if target["kind"] == "area":
            arguments["area"] = target["value"]
            what = "le luci" if is_light else "le prese"
            summary = f"{verb} {what} di {target['value']}"
        else:
            arguments["entity_id"] = target["value"]
            names = [_readable(eid) for eid in target["value"]]
            summary = f"{verb} {', '.join(names)}"

        if is_light and turning_on:
            self._add_light_options(text, arguments)

        return {"tool": tool, "arguments": arguments, "summary": summary}

    @staticmethod
    def _add_light_options(text: str, arguments: Dict[str, Any]) -> None:
        percent = re.search(r"\b(\d{1,3})\s*(?:%|per\s*cento)", text)
        if percent:
            arguments["brightness_pct"] = max(0, min(100, int(percent.group(1))))

        for italian, english in _COLORS.items():
            if re.search(rf"\b{italian}\b", text):
                arguments["color_name"] = english
                break

        kelvin = re.search(r"\b(\d{4})\s*k\b", text)
        if kelvin:
            arguments["color_temp_kelvin"] = int(kelvin.group(1))
        elif "calda" in text or "caldo" in text:
            arguments["color_temp_kelvin"] = 2700
        elif "fredda" in text or "freddo" in text:
            arguments["color_temp_kelvin"] = 6000


def match_home_command(message: str) -> Optional[Dict[str, Any]]:
    """La chiamata pronta, o None se la frase va all'agente completo."""
    from core.mcp import mcp_hub

    server = mcp_hub.get_server("HomeAssistant MCP")
    if not server:
        return None
    try:
        if not server.is_configured():
            return None
    except Exception:
        return None

    try:
        return HomeIntentMatcher(server).match(message)
    except Exception as exc:
        # Un riconoscitore che esplode non deve rompere la chat: la frase
        # prosegue verso l'agente come se questo modulo non esistesse.
        log.warning("Corsia veloce non applicata: %s", exc)
        return None
