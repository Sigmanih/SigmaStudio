# ==============================================================================
# core/mcp/calendar_server.py — Calendar MCP Server (CalDAV)
# ==============================================================================
"""Calendario per gli agenti, via CalDAV.

CalDAV invece dell'API di Google perché è lo stesso protocollo per Google,
Nextcloud, iCloud, Fastmail e Radicale, e si autentica con una password per app
invece che con un giro di OAuth e un browser che si apre da solo — cosa che su
un server che gira in locale è più un ostacolo che una comodità.

La libreria `caldav` è opzionale, come i motori vocali: se manca, gli strumenti
restano visibili ma dichiarano come installarla, invece di far esplodere l'hub
all'avvio.
"""

import importlib.util
from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE, get_integration_config

log = get_logger(__name__)

MAX_EVENTS = 50


class CalendarMCPServer(BaseMCPServer):
    integration_key = "calendar"
    config_fields = [
        {"key": "url", "label": "URL CalDAV", "placeholder": "https://caldav.icloud.com/", "type": "text",
         "help": "Google: https://apidata.googleusercontent.com/caldav/v2/TUA_EMAIL/events — Nextcloud: https://tuoserver/remote.php/dav"},
        {"key": "username", "label": "Utente", "placeholder": "tu@esempio.it", "type": "text"},
        {"key": "password", "label": "Password", "placeholder": "password per app", "type": "secret",
         "help": "Password per app del provider, non quella dell'account."},
        {"key": "calendar_name", "label": "Nome calendario", "placeholder": "(il primo disponibile)",
         "type": "text", "help": "Lascia vuoto per usare il calendario predefinito."},
    ]

    def __init__(self):
        super().__init__(
            name="Calendar MCP",
            version="1.0.0",
            description="Lettura e creazione eventi su calendari CalDAV (Google, Nextcloud, iCloud, Fastmail)",
        )
        self._init_tools()

    def is_configured(self) -> bool:
        cfg = get_integration_config(self.integration_key)
        return bool(cfg.get("url") and cfg.get("username") and cfg.get("password"))

    def missing_dependency(self):
        if importlib.util.find_spec("caldav") is None:
            return "pip install caldav"
        return None

    def _calendar(self):
        """Connect and pick the calendar named in the settings, else the first."""
        if importlib.util.find_spec("caldav") is None:
            raise RuntimeError("Libreria CalDAV mancante. Installala con: pip install caldav")

        import caldav

        cfg = get_integration_config(self.integration_key)
        if not (cfg.get("url") and cfg.get("username") and cfg.get("password")):
            raise RuntimeError("Calendario non configurato: imposta URL, utente e password nella tab MCP Tools.")

        try:
            client = caldav.DAVClient(
                url=cfg["url"], username=cfg["username"], password=cfg["password"])
            calendars = client.principal().calendars()
        except Exception as exc:
            raise RuntimeError(f"Connessione CalDAV fallita su {cfg['url']}: {exc}") from exc

        if not calendars:
            raise RuntimeError("Nessun calendario trovato per queste credenziali.")

        wanted = (cfg.get("calendar_name") or "").strip().lower()
        if wanted:
            for calendar in calendars:
                if wanted in str(calendar.name or "").lower():
                    return calendar
            raise RuntimeError(
                f"Calendario '{cfg['calendar_name']}' non trovato. Disponibili: "
                + ", ".join(str(c.name) for c in calendars)
            )
        return calendars[0]

    # --- tools ---------------------------------------------------------------

    def _init_tools(self):
        self.register_tool(
            name="calendar_list_events",
            description=("Elenca gli eventi del calendario in una finestra temporale, per default i prossimi "
                         "7 giorni a partire da adesso."),
            input_schema={
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Giorni da coprire da oggi", "default": 7},
                    "days_back": {"type": "integer", "description": "Giorni all'indietro da includere", "default": 0},
                    "limit": {"type": "integer", "description": "Numero massimo di eventi", "default": 20},
                },
            },
            handler=self._handle_list_events,
            safety=SAFE,
            category="calendar",
        )

        self.register_tool(
            name="calendar_create_event",
            description=("Crea un evento nel calendario. Le date vanno in formato ISO 8601, "
                         "es. 2026-03-14T15:00:00."),
            input_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Titolo dell'evento"},
                    "start": {"type": "string", "description": "Inizio in ISO 8601, es. 2026-03-14T15:00:00"},
                    "end": {"type": "string", "description": "Fine in ISO 8601; se assente dura un'ora"},
                    "description": {"type": "string", "description": "Note dell'evento"},
                    "location": {"type": "string", "description": "Luogo"},
                },
                "required": ["summary", "start"],
            },
            handler=self._handle_create_event,
            safety=SENSITIVE,
            category="calendar",
        )

        self.register_tool(
            name="calendar_list_calendars",
            description="Elenca i calendari disponibili per le credenziali configurate.",
            input_schema={"type": "object", "properties": {}},
            handler=self._handle_list_calendars,
            safety=SAFE,
            category="calendar",
        )

    # --- handlers ------------------------------------------------------------

    def _handle_list_calendars(self, **kwargs):
        if importlib.util.find_spec("caldav") is None:
            raise RuntimeError("Libreria CalDAV mancante. Installala con: pip install caldav")

        import caldav

        cfg = get_integration_config(self.integration_key)
        client = caldav.DAVClient(url=cfg.get("url", ""), username=cfg.get("username", ""),
                                  password=cfg.get("password", ""))
        calendars = client.principal().calendars()
        return {"success": True, "calendars": [str(c.name) for c in calendars]}

    def _handle_list_events(self, days_ahead: int = 7, days_back: int = 0, limit: int = 20, **kwargs):
        calendar = self._calendar()
        start = datetime.now() - timedelta(days=max(0, int(days_back or 0)))
        end = datetime.now() + timedelta(days=max(1, int(days_ahead or 7)))

        try:
            found = calendar.search(start=start, end=end, event=True, expand=True)
        except Exception as exc:
            raise RuntimeError(f"Ricerca eventi fallita: {exc}") from exc

        capped = max(1, min(int(limit or 20), MAX_EVENTS))
        events: List[Dict[str, Any]] = []
        for item in found[:capped]:
            events.append(self._describe_event(item))

        return {"success": True, "calendar": str(calendar.name),
                "window": {"from": start.isoformat(), "to": end.isoformat()},
                "total": len(found), "events": events}

    @staticmethod
    def _describe_event(item) -> Dict[str, Any]:
        """Pull the fields an agent cares about out of a VEVENT."""
        try:
            component = item.icalendar_component
            def value(field):
                raw = component.get(field)
                if raw is None:
                    return None
                dt = getattr(raw, "dt", None)
                return dt.isoformat() if hasattr(dt, "isoformat") else str(raw)

            return {
                "summary": str(component.get("summary", "(senza titolo)")),
                "start": value("dtstart"),
                "end": value("dtend"),
                "location": str(component.get("location", "") or ""),
                "description": str(component.get("description", "") or "")[:500],
            }
        except Exception as exc:
            return {"summary": "(evento illeggibile)", "error": str(exc)}

    def _handle_create_event(self, summary: str = "", start: str = "", end: str = "",
                             description: str = "", location: str = "", **kwargs):
        calendar = self._calendar()
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            return {"success": False,
                    "error": f"Data di inizio non valida: '{start}'. Usa il formato 2026-03-14T15:00:00."}

        if end:
            try:
                end_dt = datetime.fromisoformat(end)
            except ValueError:
                return {"success": False, "error": f"Data di fine non valida: '{end}'."}
        else:
            end_dt = start_dt + timedelta(hours=1)

        if end_dt <= start_dt:
            return {"success": False, "error": "La fine dell'evento precede l'inizio."}

        try:
            calendar.save_event(
                dtstart=start_dt, dtend=end_dt, summary=summary,
                description=description or None, location=location or None,
            )
        except Exception as exc:
            raise RuntimeError(f"Creazione evento fallita: {exc}") from exc

        log.info("Evento '%s' creato su %s", summary[:60], calendar.name)
        return {"success": True, "calendar": str(calendar.name), "summary": summary,
                "start": start_dt.isoformat(), "end": end_dt.isoformat()}
