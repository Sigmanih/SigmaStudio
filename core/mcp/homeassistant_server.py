# ==============================================================================
# core/mcp/homeassistant_server.py — Home Assistant MCP Server
# Lights, switches, climate and sensors over the Home Assistant REST API
# ==============================================================================
"""Domotica for Sigma Studio agents, through Home Assistant.

Home Assistant is the right seam for this. It already speaks Zigbee, Z-Wave,
Matter, Thread and Bluetooth LE, and it already solved pairing, reconnection and
device naming — so one HTTP integration here buys every device the operator has
already onboarded there, instead of a Bluetooth stack we would have to babysit.

Anything that changes the state of the house is SENSITIVE: an agent that
mis-parses a sentence should not be able to unlock a door on its own.
"""

import json
from typing import Any, Dict, List

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE, get_integration_config

log = get_logger(__name__)

REQUEST_TIMEOUT = 12
# A whole-house dump is tens of thousands of tokens; agents get a slice.
MAX_ENTITIES = 60
# Some LED strips advertise hundreds of effects: the list alone would cost more
# context than the answer it is meant to inform.
MAX_EFFECTS = 25


def _normalize(text: str) -> str:
    """Confronto tollerante fra i modi in cui un nome può essere scritto."""
    return "".join(c for c in str(text).lower().strip() if c.isalnum())


class HomeAssistantMCPServer(BaseMCPServer):
    integration_key = "home_assistant"
    config_fields = [
        {"key": "base_url", "label": "URL istanza", "placeholder": "http://homeassistant.local:8123",
         "type": "text", "help": "Indirizzo della tua istanza Home Assistant."},
        {"key": "token", "label": "Token di accesso", "placeholder": "eyJhbGciOi...",
         "type": "secret", "help": "Profilo utente → Token di accesso a lunga durata → Crea token."},
    ]

    def __init__(self):
        super().__init__(
            name="HomeAssistant MCP",
            version="1.0.0",
            description="Luci, prese, termostati e sensori via Home Assistant (include Zigbee, Matter e Bluetooth già integrati)",
        )
        self._init_tools()
        self._init_resources()

    # --- configuration -------------------------------------------------------

    def is_configured(self) -> bool:
        cfg = get_integration_config(self.integration_key)
        return bool(cfg.get("base_url") and cfg.get("token"))

    def missing_dependency(self):
        try:
            import requests  # noqa: F401
        except ImportError:
            return "pip install requests"
        return None

    def _request(self, method: str, path: str, payload: Dict[str, Any] = None, raw: bool = False) -> Any:
        """One call to the Home Assistant API, with the failures named in Italian."""
        cfg = get_integration_config(self.integration_key)
        base = (cfg.get("base_url") or "").rstrip("/")
        token = cfg.get("token") or ""
        if not base or not token:
            raise RuntimeError(
                "Home Assistant non è configurato: imposta URL e token nella tab MCP Tools."
            )

        import requests

        try:
            response = requests.request(
                method,
                f"{base}/api/{path.lstrip('/')}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Home Assistant irraggiungibile su {base}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f"Home Assistant non ha risposto entro {REQUEST_TIMEOUT}s") from exc

        if response.status_code == 401:
            raise RuntimeError("Token Home Assistant rifiutato: creane uno nuovo e riconfiguralo.")
        if response.status_code == 404:
            raise RuntimeError(f"Endpoint Home Assistant inesistente: {path}")
        if response.status_code >= 400:
            raise RuntimeError(f"Home Assistant ha risposto {response.status_code}: {response.text[:200]}")

        if raw:
            return response.text
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text[:500]}

    # --- targeting -----------------------------------------------------------

    def _render_template(self, template: str) -> Any:
        """Ask Home Assistant to evaluate a Jinja template and give back JSON.

        The REST API has no endpoint for the area registry, but the template
        engine can reach it. It is the only way to turn "ufficio" into the
        entities that actually live there.
        """
        text = self._request("POST", "template", {"template": template}, raw=True)
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            raise RuntimeError(f"Home Assistant ha risposto in modo inatteso: {str(text)[:200]}")

    def _entities_in_area(self, area: str, domain: str = "") -> List[str]:
        entities = self._render_template("{{ area_entities('%s') | tojson }}" % area.replace("'", "\\'"))
        if not isinstance(entities, list):
            return []
        return [e for e in entities if not domain or str(e).startswith(f"{domain}.")]

    def _entity_index(self, domain: str) -> Dict[str, str]:
        """Mappa dei nomi conosciuti → entity_id, per un dominio.

        Contiene l'id, l'id senza prefisso e il nome amichevole normalizzato:
        sono le tre forme con cui un modello può nominare la stessa lampada.
        """
        states = self._request("GET", "states")
        index: Dict[str, str] = {}
        for entry in states if isinstance(states, list) else []:
            entity_id = entry.get("entity_id", "")
            if domain and not entity_id.startswith(f"{domain}."):
                continue
            index[_normalize(entity_id)] = entity_id
            index.setdefault(_normalize(entity_id.split(".", 1)[-1]), entity_id)
            friendly = (entry.get("attributes") or {}).get("friendly_name")
            if friendly:
                index.setdefault(_normalize(friendly), entity_id)
        return index

    def _service_outcome(self, targets: List[str], response: Any, action: str) -> Dict[str, Any]:
        """Traduce la risposta di un servizio in un esito verificabile.

        Home Assistant restituisce l'elenco delle entità che hanno *davvero*
        cambiato stato. Una lista vuota con HTTP 200 significa che il comando è
        stato accettato ma non ha toccato nulla — tipicamente perché l'entità è
        `unavailable`: l'integrazione che la forniva non è più attiva e HA ne
        conserva solo il ricordo. Dichiarare successo in quel caso manda
        l'operatore a cercare il guasto nel posto sbagliato.
        """
        changed = [s.get("entity_id") for s in response
                   if isinstance(s, dict) and s.get("entity_id")] if isinstance(response, list) else []
        untouched = [t for t in targets if t not in changed]

        result: Dict[str, Any] = {
            "success": True, "count": len(targets), "entities": targets,
            "changed": len(changed), "changed_entities": changed,
        }
        if not untouched:
            return result

        # Solo sul percorso anomalo si paga una lettura in più per dire perché.
        unavailable = []
        for entity in untouched[:10]:
            try:
                state = self._request("GET", f"states/{entity}")
                if isinstance(state, dict) and state.get("state") in ("unavailable", "unknown"):
                    unavailable.append(entity)
            except Exception:
                continue

        if unavailable:
            result["success"] = False
            result["unavailable"] = unavailable
            result["error"] = (
                f"{action} non applicato: {', '.join(unavailable[:3])} "
                f"{'è' if len(unavailable) == 1 else 'sono'} in stato 'unavailable' su Home Assistant. "
                "Il comando è stato accettato ma nessun dispositivo risponde: "
                "controlla in Home Assistant che l'integrazione che fornisce queste luci sia attiva."
            )
        elif not changed:
            result["warning"] = (f"{action} accettato ma nessuna entità ha cambiato stato "
                                 "(erano già nella condizione richiesta).")
        return result

    def _resolve_targets(self, entity_id, area: str, domain: str) -> List[str]:
        """Turn whatever the agent named into a concrete list of entity ids.

        Accepts one entity, several, an area, or a combination. Home Assistant
        applies a service to a whole list in a single call, so "spegni le luci
        dell'ufficio" is one command and one confirmation — not one per lamp.

        Every name is checked against the live registry first. A model that
        invents an id — and they do, `ufficio_luce_1234567890` came out of one —
        would otherwise poison the whole batch: Home Assistant rejects the
        request as a unit, so the lamps that *did* exist stay untouched and the
        agent gets back nothing more useful than "400 Bad Request".
        """
        requested: List[str] = []
        if isinstance(entity_id, str) and entity_id.strip():
            requested = [e.strip() for e in entity_id.split(",") if e.strip()]
        elif isinstance(entity_id, (list, tuple)):
            requested = [str(e).strip() for e in entity_id if str(e).strip()]

        targets: List[str] = []
        if requested:
            index = self._entity_index(domain)
            unknown = []
            for name in requested:
                resolved = index.get(_normalize(name))
                if resolved:
                    if resolved not in targets:
                        targets.append(resolved)
                else:
                    unknown.append(name)
            if unknown:
                catalogue = sorted(set(index.values()))
                raise RuntimeError(
                    f"Entità inesistenti: {', '.join(unknown)}. "
                    f"Quelle vere sono: {', '.join(catalogue[:20]) or 'nessuna'}"
                    + (f" (e altre {len(catalogue) - 20})" if len(catalogue) > 20 else "")
                    + ". Usa esattamente uno di questi id, oppure il parametro 'area'."
                )

        if area:
            found = self._entities_in_area(area, domain)
            if not found and not targets:
                known = self._handle_list_areas().get("areas", [])
                names = ", ".join(a["name"] for a in known) or "nessuna"
                raise RuntimeError(
                    f"Nessuna entità '{domain}' nell'area '{area}'. Aree disponibili: {names}")
            targets.extend(e for e in found if e not in targets)

        if not targets:
            raise RuntimeError("Serve almeno entity_id oppure area.")
        return targets

    # --- tools ---------------------------------------------------------------

    def _init_tools(self):
        self.register_tool(
            name="ha_list_entities",
            description=("Elenca le entità Home Assistant con il loro stato. Filtra con 'domain' "
                         "(light, switch, sensor, climate). Per le luci riporta anche effetti e "
                         "modalità colore supportati."),
            input_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Dominio da filtrare, es. light, switch, sensor, climate"},
                    "search": {"type": "string", "description": "Filtro sul nome dell'entità"},
                    "limit": {"type": "integer", "description": "Numero massimo di entità", "default": 30},
                },
            },
            handler=self._handle_list_entities,
            safety=SAFE,
            category="smart_home",
        )

        self.register_tool(
            name="ha_entity_state",
            description="Legge lo stato e gli attributi di una singola entità Home Assistant.",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "ID entità, es. light.studio_desk"},
                },
                "required": ["entity_id"],
            },
            handler=self._handle_entity_state,
            safety=SAFE,
            category="smart_home",
        )

        self.register_tool(
            name="ha_light_set",
            # Descrizione corta di proposito: una lunga viene recitata come
            # documentazione invece di essere eseguita. I dettagli stanno nei
            # singoli parametri, dove servono al momento di compilarli.
            description=("Comanda luci: acceso/spento, luminosità, colore, effetti. "
                         "Usa 'area' per tutte le luci di una stanza in una chiamata sola."),
            input_schema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "description": "Una entità o un elenco, es. 'light.scrivania' oppure ['light.a','light.b']",
                        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
                    },
                    "area": {"type": "string", "description": "Nome della stanza: comanda tutte le sue luci"},
                    "state": {"type": "string", "enum": ["on", "off"], "description": "Stato desiderato"},
                    "brightness": {"type": "integer", "description": "Luminosità 0-255"},
                    "brightness_pct": {"type": "number", "description": "Luminosità in percentuale 0-100"},
                    "color_temp_kelvin": {"type": "integer", "description": "Temperatura colore in kelvin, es. 2700 caldo, 6500 freddo"},
                    "rgb_color": {
                        "type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3,
                        "description": "Colore RGB, es. [255, 120, 0]",
                    },
                    "color_name": {"type": "string", "description": "Nome colore riconosciuto da Home Assistant, es. red, warmwhite"},
                    "effect": {"type": "string", "description": "Effetto della lampada, dev'essere uno di quelli che dichiara"},
                    "transition": {"type": "number", "description": "Durata della dissolvenza in secondi"},
                    "flash": {"type": "string", "enum": ["short", "long"], "description": "Lampeggio di segnalazione"},
                },
                "required": ["state"],
            },
            handler=self._handle_light_set,
            safety=SENSITIVE,
            category="smart_home",
        )

        self.register_tool(
            name="ha_switch_set",
            description=("Accende o spegne prese e interruttori intelligenti. Accetta una entità, un elenco "
                         "o un'intera area."),
            input_schema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "description": "Una entità o un elenco, es. 'switch.stampante_3d'",
                        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
                    },
                    "area": {"type": "string", "description": "Nome della stanza: comanda tutte le sue prese"},
                    "state": {"type": "string", "enum": ["on", "off"], "description": "Stato desiderato"},
                },
                "required": ["state"],
            },
            handler=self._handle_switch_set,
            safety=SENSITIVE,
            category="smart_home",
        )

        self.register_tool(
            name="ha_list_areas",
            description=("Elenca le stanze configurate in Home Assistant con le entità di ciascuna. "
                         "Serve a sapere quale nome passare al parametro 'area' degli altri strumenti."),
            input_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Mostra solo le entità di questo dominio, es. light"},
                },
            },
            handler=self._handle_list_areas,
            safety=SAFE,
            category="smart_home",
        )

        self.register_tool(
            name="ha_climate_set",
            description="Imposta la temperatura obiettivo e la modalità di un termostato o climatizzatore.",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "ID entità clima, es. climate.soggiorno"},
                    "temperature": {"type": "number", "description": "Temperatura obiettivo in gradi"},
                    "hvac_mode": {
                        "type": "string",
                        "enum": ["off", "heat", "cool", "auto", "dry", "fan_only"],
                        "description": "Modalità di funzionamento",
                    },
                },
                "required": ["entity_id"],
            },
            handler=self._handle_climate_set,
            safety=SENSITIVE,
            category="smart_home",
        )

        self.register_tool(
            name="ha_call_service",
            description=("Chiama un servizio Home Assistant qualsiasi, per i dispositivi non coperti dagli altri "
                         "strumenti. Esempio: domain='media_player', service='volume_set'."),
            input_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Dominio del servizio, es. light, cover, media_player"},
                    "service": {"type": "string", "description": "Nome del servizio, es. turn_on, open_cover"},
                    "entity_id": {"type": "string", "description": "Entità bersaglio"},
                    "data": {"type": "object", "description": "Parametri aggiuntivi del servizio"},
                },
                "required": ["domain", "service"],
            },
            handler=self._handle_call_service,
            safety=SENSITIVE,
            category="smart_home",
        )

    def _init_resources(self):
        self.register_resource(
            uri="homeassistant://entities",
            name="Entità Home Assistant",
            description="Stato corrente delle entità della casa",
            mime_type="application/json",
            handler=lambda uri: self._handle_list_entities(limit=MAX_ENTITIES),
        )

    # --- handlers ------------------------------------------------------------

    def _handle_list_entities(self, domain: str = "", search: str = "", limit: int = 30, **kwargs):
        states = self._request("GET", "states")
        if not isinstance(states, list):
            return {"success": False, "error": "Risposta inattesa da Home Assistant"}

        entities: List[Dict[str, Any]] = []
        for entry in states:
            entity_id = entry.get("entity_id", "")
            if domain and not entity_id.startswith(f"{domain}."):
                continue
            attrs = entry.get("attributes", {})
            name = attrs.get("friendly_name", entity_id)
            if search and search.lower() not in f"{entity_id} {name}".lower():
                continue
            item = {
                "entity_id": entity_id,
                "name": name,
                "state": entry.get("state"),
                "unit": attrs.get("unit_of_measurement"),
            }
            if entity_id.startswith("light."):
                item["capabilities"] = self._light_capabilities(attrs)
            entities.append(item)

        capped = min(int(limit or 30), MAX_ENTITIES)
        return {
            "success": True,
            "total_found": len(entities),
            "showing": min(len(entities), capped),
            "entities": entities[:capped],
        }

    @staticmethod
    def _light_capabilities(attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cosa sa fare davvero questa lampada.

        Senza questo l'agente tira a indovinare: prova un effetto che il modello
        non ha, o manda un colore a una lampada che fa solo bianco, e si prende
        un errore che poteva evitare leggendo.
        """
        effects = attrs.get("effect_list") or []
        capabilities: Dict[str, Any] = {
            "color_modes": attrs.get("supported_color_modes") or [],
            "current_mode": attrs.get("color_mode"),
        }
        if attrs.get("brightness") is not None:
            capabilities["brightness"] = attrs["brightness"]
        if attrs.get("min_color_temp_kelvin"):
            capabilities["kelvin_range"] = [attrs.get("min_color_temp_kelvin"),
                                            attrs.get("max_color_temp_kelvin")]
        if attrs.get("rgb_color"):
            capabilities["rgb_color"] = attrs["rgb_color"]
        if effects:
            # Certe lampade dichiarano centinaia di effetti: l'elenco intero
            # costerebbe più contesto di tutto il resto della risposta.
            capabilities["effects"] = list(effects[:MAX_EFFECTS])
            if len(effects) > MAX_EFFECTS:
                capabilities["effects_total"] = len(effects)
            capabilities["current_effect"] = attrs.get("effect")
        return capabilities

    def _handle_entity_state(self, entity_id: str = "", **kwargs):
        if not entity_id:
            return {"success": False, "error": "entity_id è obbligatorio"}
        entry = self._request("GET", f"states/{entity_id}")
        return {"success": True, "entity": entry}

    def _handle_list_areas(self, domain: str = "", **kwargs):
        areas = self._render_template(
            "[{% for a in areas() %}"
            '{"id": {{ a | tojson }}, "name": {{ area_name(a) | tojson }}, '
            '"entities": {{ area_entities(a) | tojson }}}'
            "{% if not loop.last %},{% endif %}{% endfor %}]"
        )
        if domain:
            for area in areas:
                area["entities"] = [e for e in area["entities"] if str(e).startswith(f"{domain}.")]
        return {"success": True, "areas": areas}

    def _handle_light_set(self, entity_id=None, area: str = "", state: str = "on",
                          brightness: int = None, brightness_pct: float = None,
                          color_temp_kelvin: int = None, rgb_color=None, color_name: str = "",
                          effect: str = "", transition: float = None, flash: str = "", **kwargs):
        targets = self._resolve_targets(entity_id, area, "light")
        data: Dict[str, Any] = {"entity_id": targets}

        # A fade applies to going dark just as much as to lighting up.
        if transition is not None:
            data["transition"] = max(0, float(transition))
        if flash:
            data["flash"] = flash

        if state == "on":
            if brightness_pct is not None:
                data["brightness_pct"] = max(0, min(100, float(brightness_pct)))
            elif brightness is not None:
                data["brightness"] = max(0, min(255, int(brightness)))

            # Colour, colour name and white temperature are three ways of saying
            # the same thing to the lamp; sending two makes the last one win in a
            # way nobody can predict, so only the most specific goes out.
            if rgb_color:
                data["rgb_color"] = [max(0, min(255, int(c))) for c in list(rgb_color)[:3]]
            elif color_name:
                data["color_name"] = color_name
            elif color_temp_kelvin is not None:
                data["color_temp_kelvin"] = int(color_temp_kelvin)

            if effect:
                data["effect"] = effect

        service = "turn_on" if state == "on" else "turn_off"
        response = self._request("POST", f"services/light/{service}", data)
        outcome = self._service_outcome(targets, response, f"Comando luci '{state}'")
        log.info("Luci %s: %s (%d richieste, %d cambiate)", state,
                 ", ".join(targets[:5]), len(targets), outcome["changed"])
        return {**outcome, "state": state, "applied": data}

    def _handle_switch_set(self, entity_id=None, area: str = "", state: str = "on", **kwargs):
        targets = self._resolve_targets(entity_id, area, "switch")
        service = "turn_on" if state == "on" else "turn_off"
        response = self._request("POST", f"services/switch/{service}", {"entity_id": targets})
        outcome = self._service_outcome(targets, response, f"Comando prese '{state}'")
        return {**outcome, "state": state}

    def _handle_climate_set(self, entity_id: str = "", temperature: float = None,
                            hvac_mode: str = "", **kwargs):
        applied = {}
        if hvac_mode:
            self._request("POST", "services/climate/set_hvac_mode",
                          {"entity_id": entity_id, "hvac_mode": hvac_mode})
            applied["hvac_mode"] = hvac_mode
        if temperature is not None:
            self._request("POST", "services/climate/set_temperature",
                          {"entity_id": entity_id, "temperature": float(temperature)})
            applied["temperature"] = float(temperature)
        if not applied:
            return {"success": False, "error": "Serve almeno temperature o hvac_mode"}
        return {"success": True, "entity_id": entity_id, "applied": applied}

    def _handle_call_service(self, domain: str = "", service: str = "",
                             entity_id: str = "", data: Dict[str, Any] = None, **kwargs):
        payload = dict(data or {})
        if entity_id:
            payload["entity_id"] = entity_id
        result = self._request("POST", f"services/{domain}/{service}", payload)
        targets = [entity_id] if entity_id else []
        outcome = self._service_outcome(targets, result, f"Servizio {domain}.{service}") if targets             else {"success": True, "changed": len(result) if isinstance(result, list) else 0}
        return {**outcome, "domain": domain, "service": service, "result": result}
