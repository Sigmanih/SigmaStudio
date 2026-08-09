# ==============================================================================
# core/mcp/email_server.py — Email MCP Server (SMTP send, IMAP read)
# ==============================================================================
"""Posta elettronica per gli agenti, sopra smtplib e imaplib.

Nessuna dipendenza esterna: la libreria standard copre SMTP e IMAP, e ogni
provider che accetta una password per app (Gmail, Fastmail, iCloud, un server
aziendale) funziona senza OAuth.

Leggere la posta è SAFE, spedirla è SENSITIVE: un messaggio parte a nome
dell'operatore e non si richiama indietro.
"""

import email
import imaplib
import smtplib
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage
from typing import Any, Dict, List

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE, get_integration_config

log = get_logger(__name__)

TIMEOUT = 20
MAX_FETCH = 25
# Un corpo intero manda in saturazione il contesto; l'agente ne vede l'inizio.
BODY_PREVIEW_CHARS = 1500


class EmailMCPServer(BaseMCPServer):
    integration_key = "email"
    config_fields = [
        {"key": "address", "label": "Indirizzo email", "placeholder": "tu@esempio.it", "type": "text",
         "help": "Mittente delle email e utente per la lettura."},
        {"key": "password", "label": "Password", "placeholder": "password per app", "type": "secret",
         "help": "Con Gmail serve una password per app, non quella dell'account."},
        {"key": "smtp_host", "label": "Server SMTP", "placeholder": "smtp.gmail.com", "type": "text"},
        {"key": "smtp_port", "label": "Porta SMTP", "placeholder": "587", "type": "number",
         "help": "587 per STARTTLS, 465 per SSL diretto."},
        {"key": "imap_host", "label": "Server IMAP", "placeholder": "imap.gmail.com", "type": "text",
         "help": "Lascia vuoto se non ti serve leggere la posta."},
        {"key": "imap_port", "label": "Porta IMAP", "placeholder": "993", "type": "number"},
    ]

    def __init__(self):
        super().__init__(
            name="Email MCP",
            version="1.0.0",
            description="Invio di report e notifiche via SMTP, lettura e sintesi della posta via IMAP",
        )
        self._init_tools()

    def is_configured(self) -> bool:
        cfg = get_integration_config(self.integration_key)
        return bool(cfg.get("address") and cfg.get("password") and cfg.get("smtp_host"))

    def _config(self) -> Dict[str, Any]:
        cfg = get_integration_config(self.integration_key)
        if not cfg.get("address") or not cfg.get("password"):
            raise RuntimeError("Email non configurata: imposta indirizzo e password nella tab MCP Tools.")
        return cfg

    # --- tools ---------------------------------------------------------------

    def _init_tools(self):
        self.register_tool(
            name="send_email",
            description=("Spedisce una email di testo o HTML. Usala per report, notifiche di fine lavorazione "
                         "e risposte. Il mittente è l'indirizzo configurato in Sigma Studio."),
            input_schema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Destinatario, o più destinatari separati da virgola"},
                    "subject": {"type": "string", "description": "Oggetto del messaggio"},
                    "body": {"type": "string", "description": "Corpo del messaggio"},
                    "html": {"type": "boolean", "description": "true se il corpo è HTML", "default": False},
                    "cc": {"type": "string", "description": "Destinatari in copia, separati da virgola"},
                },
                "required": ["to", "subject", "body"],
            },
            handler=self._handle_send_email,
            safety=SENSITIVE,
            category="email",
        )

        self.register_tool(
            name="read_inbox",
            description=("Legge le email più recenti della casella, con anteprima del corpo. "
                         "Usa unread_only per vedere solo i messaggi non letti."),
            input_schema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Cartella IMAP", "default": "INBOX"},
                    "unread_only": {"type": "boolean", "description": "Solo messaggi non letti", "default": False},
                    "limit": {"type": "integer", "description": "Numero massimo di messaggi", "default": 5},
                },
            },
            handler=self._handle_read_inbox,
            safety=SAFE,
            category="email",
        )

        self.register_tool(
            name="search_email",
            description="Cerca messaggi per mittente o per parole nell'oggetto.",
            input_schema={
                "type": "object",
                "properties": {
                    "sender": {"type": "string", "description": "Indirizzo o frammento del mittente"},
                    "subject": {"type": "string", "description": "Testo da cercare nell'oggetto"},
                    "limit": {"type": "integer", "description": "Numero massimo di risultati", "default": 10},
                },
            },
            handler=self._handle_search_email,
            safety=SAFE,
            category="email",
        )

    # --- send ----------------------------------------------------------------

    def _handle_send_email(self, to: str = "", subject: str = "", body: str = "",
                           html: bool = False, cc: str = "", **kwargs):
        cfg = self._config()
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
        cc_list = [addr.strip() for addr in (cc or "").split(",") if addr.strip()]
        if not recipients:
            return {"success": False, "error": "Nessun destinatario valido"}

        message = EmailMessage()
        message["From"] = cfg["address"]
        message["To"] = ", ".join(recipients)
        if cc_list:
            message["Cc"] = ", ".join(cc_list)
        message["Subject"] = subject
        if html:
            message.set_content("Questo messaggio richiede un client che supporti l'HTML.")
            message.add_alternative(body, subtype="html")
        else:
            message.set_content(body)

        host = cfg.get("smtp_host") or ""
        port = int(cfg.get("smtp_port") or 587)
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT,
                                      context=ssl.create_default_context()) as server:
                    server.login(cfg["address"], cfg["password"])
                    server.send_message(message, to_addrs=recipients + cc_list)
            else:
                with smtplib.SMTP(host, port, timeout=TIMEOUT) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(cfg["address"], cfg["password"])
                    server.send_message(message, to_addrs=recipients + cc_list)
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError(
                "Credenziali SMTP rifiutate. Con Gmail serve una password per app, non quella dell'account."
            )
        except (smtplib.SMTPException, OSError) as exc:
            raise RuntimeError(f"Invio fallito su {host}:{port} — {exc}") from exc

        log.info("Email inviata a %s (oggetto: %s)", recipients, subject[:60])
        return {"success": True, "to": recipients, "cc": cc_list, "subject": subject}

    # --- read ----------------------------------------------------------------

    def _imap_connect(self):
        cfg = self._config()
        host = cfg.get("imap_host")
        if not host:
            raise RuntimeError("Lettura posta non configurata: manca il server IMAP.")
        port = int(cfg.get("imap_port") or 993)
        try:
            client = imaplib.IMAP4_SSL(host, port, timeout=TIMEOUT)
            client.login(cfg["address"], cfg["password"])
            return client
        except imaplib.IMAP4.error as exc:
            raise RuntimeError(f"Accesso IMAP rifiutato su {host}: {exc}") from exc
        except OSError as exc:
            raise RuntimeError(f"Server IMAP {host}:{port} irraggiungibile — {exc}") from exc

    @staticmethod
    def _decode(value: str) -> str:
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    def _fetch_messages(self, client, ids: List[bytes], limit: int) -> List[Dict[str, Any]]:
        messages = []
        for msg_id in reversed(ids[-limit:]):          # newest first
            status, data = client.fetch(msg_id, "(RFC822)")
            if status != "OK" or not data or not isinstance(data[0], tuple):
                continue
            parsed = email.message_from_bytes(data[0][1])
            messages.append({
                "id": msg_id.decode(errors="replace"),
                "from": self._decode(parsed.get("From", "")),
                "to": self._decode(parsed.get("To", "")),
                "subject": self._decode(parsed.get("Subject", "")),
                "date": parsed.get("Date", ""),
                "preview": self._body_preview(parsed),
            })
        return messages

    @staticmethod
    def _body_preview(parsed) -> str:
        """First readable text of a message, HTML parts skipped when possible."""
        try:
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain" and "attachment" not in str(
                            part.get("Content-Disposition", "")):
                        payload = part.get_payload(decode=True) or b""
                        return payload.decode(part.get_content_charset() or "utf-8",
                                              errors="replace")[:BODY_PREVIEW_CHARS]
                return "(nessuna parte testuale)"
            payload = parsed.get_payload(decode=True) or b""
            return payload.decode(parsed.get_content_charset() or "utf-8",
                                  errors="replace")[:BODY_PREVIEW_CHARS]
        except Exception as exc:
            return f"(corpo illeggibile: {exc})"

    def _handle_read_inbox(self, folder: str = "INBOX", unread_only: bool = False,
                           limit: int = 5, **kwargs):
        limit = max(1, min(int(limit or 5), MAX_FETCH))
        client = self._imap_connect()
        try:
            client.select(folder, readonly=True)       # readonly: reading must not mark as read
            status, data = client.search(None, "UNSEEN" if unread_only else "ALL")
            if status != "OK":
                return {"success": False, "error": f"Ricerca IMAP fallita in '{folder}'"}
            ids = data[0].split()
            return {
                "success": True,
                "folder": folder,
                "total": len(ids),
                "messages": self._fetch_messages(client, ids, limit),
            }
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _handle_search_email(self, sender: str = "", subject: str = "", limit: int = 10, **kwargs):
        limit = max(1, min(int(limit or 10), MAX_FETCH))
        criteria = []
        if sender:
            criteria += ["FROM", f'"{sender}"']
        if subject:
            criteria += ["SUBJECT", f'"{subject}"']
        if not criteria:
            return {"success": False, "error": "Serve almeno sender o subject"}

        client = self._imap_connect()
        try:
            client.select("INBOX", readonly=True)
            status, data = client.search(None, *criteria)
            if status != "OK":
                return {"success": False, "error": "Ricerca IMAP fallita"}
            ids = data[0].split()
            return {
                "success": True,
                "criteria": {"sender": sender, "subject": subject},
                "total": len(ids),
                "messages": self._fetch_messages(client, ids, limit),
            }
        finally:
            try:
                client.logout()
            except Exception:
                pass
