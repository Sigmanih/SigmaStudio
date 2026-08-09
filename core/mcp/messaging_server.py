# ==============================================================================
# core/mcp/messaging_server.py — Telegram & Slack MCP Server
# ==============================================================================
"""Notifiche push dagli agenti verso Telegram e Slack.

È il canale con cui un lavoro lungo avvisa che è finito senza tenere l'operatore
davanti allo schermo: training completato, benchmark sopra soglia, task chiuso.

Ogni invio è SENSITIVE — arriva a una persona, con il nome dell'operatore sopra.
"""

from typing import Any, Dict

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE, get_integration_config

log = get_logger(__name__)

TIMEOUT = 12
# Telegram taglia a 4096 caratteri: meglio troncare noi e dirlo.
TELEGRAM_LIMIT = 4000


class MessagingMCPServer(BaseMCPServer):
    integration_key = "messaging"
    config_fields = [
        {"key": "telegram_bot_token", "label": "Token bot Telegram", "placeholder": "123456:ABC-DEF...",
         "type": "secret", "help": "Crea un bot con @BotFather e incolla qui il token."},
        {"key": "telegram_chat_id", "label": "Chat ID Telegram", "placeholder": "123456789", "type": "text",
         "help": "Scrivi al bot e leggi il chat id, oppure usa lo strumento telegram_get_chat_id."},
        {"key": "slack_webhook_url", "label": "Webhook Slack", "placeholder": "https://hooks.slack.com/services/...",
         "type": "secret", "help": "Slack → Incoming Webhooks → aggiungi al canale."},
    ]

    def __init__(self):
        super().__init__(
            name="Messaging MCP",
            version="1.0.0",
            description="Notifiche e messaggi verso Telegram e Slack",
        )
        self._init_tools()

    def is_configured(self) -> bool:
        cfg = get_integration_config(self.integration_key)
        return bool((cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"))
                    or cfg.get("slack_webhook_url"))

    def missing_dependency(self):
        try:
            import requests  # noqa: F401
        except ImportError:
            return "pip install requests"
        return None

    # --- tools ---------------------------------------------------------------

    def _init_tools(self):
        self.register_tool(
            name="telegram_send_message",
            description=("Invia un messaggio Telegram alla chat configurata. Adatto a notificare la fine di un "
                         "lavoro lungo o il superamento di una soglia."),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Testo del messaggio"},
                    "chat_id": {"type": "string", "description": "Chat alternativa a quella configurata"},
                    "silent": {"type": "boolean", "description": "Notifica senza suono", "default": False},
                },
                "required": ["text"],
            },
            handler=self._handle_telegram_send,
            safety=SENSITIVE,
            category="messaging",
        )

        self.register_tool(
            name="telegram_get_chat_id",
            description=("Legge gli aggiornamenti recenti del bot per scoprire il chat id da configurare. "
                         "Scrivi un messaggio qualsiasi al bot, poi chiama questo strumento."),
            input_schema={"type": "object", "properties": {}},
            handler=self._handle_telegram_chat_id,
            safety=SAFE,
            category="messaging",
        )

        self.register_tool(
            name="slack_post_message",
            description="Pubblica un messaggio sul canale Slack collegato al webhook configurato.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Testo del messaggio"},
                    "username": {"type": "string", "description": "Nome mostrato come mittente"},
                },
                "required": ["text"],
            },
            handler=self._handle_slack_post,
            safety=SENSITIVE,
            category="messaging",
        )

    # --- handlers ------------------------------------------------------------

    def _handle_telegram_send(self, text: str = "", chat_id: str = "", silent: bool = False, **kwargs):
        import requests

        cfg = get_integration_config(self.integration_key)
        token = cfg.get("telegram_bot_token")
        target = chat_id or cfg.get("telegram_chat_id")
        if not token or not target:
            raise RuntimeError("Telegram non configurato: servono token del bot e chat id nella tab MCP Tools.")

        truncated = len(text) > TELEGRAM_LIMIT
        payload = {
            "chat_id": target,
            "text": text[:TELEGRAM_LIMIT] + ("\n[…messaggio troncato]" if truncated else ""),
            "disable_notification": bool(silent),
        }
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Telegram irraggiungibile: {exc}") from exc

        if response.status_code == 401:
            raise RuntimeError("Token del bot Telegram rifiutato.")
        if response.status_code >= 400:
            raise RuntimeError(f"Telegram ha risposto {response.status_code}: {response.text[:200]}")

        log.info("Messaggio Telegram inviato alla chat %s", target)
        return {"success": True, "chat_id": target, "truncated": truncated}

    def _handle_telegram_chat_id(self, **kwargs):
        import requests

        cfg = get_integration_config(self.integration_key)
        token = cfg.get("telegram_bot_token")
        if not token:
            raise RuntimeError("Manca il token del bot Telegram.")

        try:
            response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=TIMEOUT)
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Lettura aggiornamenti Telegram fallita: {exc}") from exc

        chats = []
        for update in data.get("result", []):
            chat = (update.get("message") or update.get("channel_post") or {}).get("chat") or {}
            if chat.get("id") and not any(c["chat_id"] == str(chat["id"]) for c in chats):
                chats.append({
                    "chat_id": str(chat["id"]),
                    "type": chat.get("type"),
                    "name": chat.get("title") or chat.get("username") or chat.get("first_name", ""),
                })

        if not chats:
            return {"success": True, "chats": [],
                    "hint": "Nessuna chat trovata: scrivi un messaggio al bot e riprova."}
        return {"success": True, "chats": chats}

    def _handle_slack_post(self, text: str = "", username: str = "", **kwargs):
        import requests

        cfg = get_integration_config(self.integration_key)
        webhook = cfg.get("slack_webhook_url")
        if not webhook:
            raise RuntimeError("Slack non configurato: manca l'URL del webhook nella tab MCP Tools.")

        payload: Dict[str, Any] = {"text": text}
        if username:
            payload["username"] = username
        try:
            response = requests.post(webhook, json=payload, timeout=TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Slack irraggiungibile: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(f"Slack ha risposto {response.status_code}: {response.text[:200]}")
        return {"success": True, "channel": "webhook"}
