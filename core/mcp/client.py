# ==============================================================================
# core/mcp/client.py — Client for third-party MCP servers (stdio & HTTP)
# ==============================================================================
"""Collega server MCP scritti da altri, con lo stesso trasporto dello standard.

Sigma Studio finora aveva solo server MCP interni: classi Python nel processo.
Qui c'è il lato client, quello che permette di aggiungere dalla tab un server
qualsiasi — Home Assistant ufficiale, GitHub, Playwright, filesystem, quello che
esce domani — senza scrivere una riga di codice.

Il protocollo è JSON-RPC 2.0 su due trasporti:

* **stdio** — il server è un processo figlio, i messaggi viaggiano su stdin e
  stdout delimitati da newline. È il trasporto della maggior parte dei server
  della community, lanciati con `npx` o `uvx`.
* **http** — il server è già in ascolto su un URL, e risponde in JSON o in SSE.

L'implementazione è sincrona e a thread perché il server di Sigma Studio lo è:
infilare un event loop asincrono qui dentro significherebbe farlo attraversare a
tutto il resto del programma per nessun guadagno.

I tool di un server esterno nascono SENSITIVE. Non sappiamo cosa faccia codice
che non abbiamo scritto, quindi la prima volta lo chiede; l'operatore può
dichiarare un server di sola lettura quando lo aggiunge.
"""

import json
import os
import queue
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE

log = get_logger(__name__)

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "SigmaStudio", "version": "8.0.0"}

HANDSHAKE_TIMEOUT = 25          # npx may download the package on first run
CALL_TIMEOUT = 60
SHUTDOWN_TIMEOUT = 5


class MCPTransportError(RuntimeError):
    """The server could not be reached, started, or understood."""


# --- stdio -------------------------------------------------------------------

class StdioTransport:
    """A child process speaking newline-delimited JSON-RPC on stdin/stdout."""

    def __init__(self, command: str, args: List[str] = None,
                 env: Dict[str, str] = None, cwd: str = ""):
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})
        self.cwd = cwd or None
        self._process: Optional[subprocess.Popen] = None
        self._pending: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self._stderr_tail: List[str] = []

    def start(self) -> None:
        if self._process and self._process.poll() is None:
            return

        environment = {**os.environ, **self.env}
        try:
            self._process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment, cwd=self.cwd, text=True, encoding="utf-8",
                errors="replace", bufsize=1,
                # Keeps a console window from flashing up on Windows for every server.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as exc:
            raise MCPTransportError(
                f"Comando '{self.command}' non trovato. Se il server usa npx, serve Node.js installato."
            ) from exc
        except OSError as exc:
            raise MCPTransportError(f"Avvio del server fallito: {exc}") from exc

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _read_loop(self) -> None:
        """Hand each reply to whoever is waiting on its id."""
        stream = self._process.stdout
        while True:
            line = stream.readline()
            if not line:
                break                                  # process ended
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                # Servers routinely print banners on stdout before speaking JSON.
                log.debug("[mcp] riga non JSON ignorata: %s", line[:120])
                continue

            message_id = message.get("id")
            if message_id is None:
                continue                               # a notification: nothing waits for it
            with self._lock:
                waiter = self._pending.pop(str(message_id), None)
            if waiter:
                waiter.put(message)

    def _drain_stderr(self) -> None:
        """Keep the last stderr lines: they are the only clue when a server dies."""
        for line in self._process.stderr:
            text = line.rstrip()
            if text:
                self._stderr_tail.append(text)
                del self._stderr_tail[:-15]
                log.debug("[mcp:%s] %s", self.command, text[:200])

    def _write(self, payload: Dict[str, Any]) -> None:
        if not self._process or self._process.poll() is not None:
            raise MCPTransportError(self._death_reason())
        try:
            self._process.stdin.write(json.dumps(payload) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise MCPTransportError(f"Server MCP non più in ascolto: {exc}") from exc

    def _death_reason(self) -> str:
        tail = " | ".join(self._stderr_tail[-3:])
        code = self._process.poll() if self._process else "mai avviato"
        return f"Il processo del server MCP è terminato (codice {code})" + (f": {tail}" if tail else "")

    def request(self, method: str, params: Dict[str, Any] = None,
                timeout: float = CALL_TIMEOUT) -> Dict[str, Any]:
        request_id = uuid.uuid4().hex[:12]
        waiter: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[request_id] = waiter

        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})

        try:
            message = waiter.get(timeout=timeout)
        except queue.Empty:
            with self._lock:
                self._pending.pop(request_id, None)
            if self._process and self._process.poll() is not None:
                raise MCPTransportError(self._death_reason())
            raise MCPTransportError(f"Nessuna risposta a '{method}' entro {timeout:.0f}s")

        if "error" in message:
            error = message["error"]
            raise MCPTransportError(f"{error.get('message', 'errore sconosciuto')} (code {error.get('code')})")
        return message.get("result", {})

    def notify(self, method: str, params: Dict[str, Any] = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def stop(self) -> None:
        if not self._process:
            return
        try:
            self._process.stdin.close()
        except Exception:
            pass
        try:
            self._process.wait(timeout=SHUTDOWN_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None

    def is_alive(self) -> bool:
        return bool(self._process and self._process.poll() is None)


# --- http --------------------------------------------------------------------

class HttpTransport:
    """A server already listening on a URL, answering in JSON or SSE."""

    def __init__(self, url: str, headers: Dict[str, str] = None):
        self.url = url
        self.headers = dict(headers or {})
        self.session_id = ""

    def start(self) -> None:
        return                                          # nothing to launch

    def is_alive(self) -> bool:
        return True

    def stop(self) -> None:
        return

    def _post(self, payload: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        try:
            response = requests.post(self.url, json=payload, headers=headers,
                                     timeout=timeout, stream=True)
        except Exception as exc:
            raise MCPTransportError(f"Server MCP irraggiungibile su {self.url}: {exc}") from exc

        if response.status_code >= 400:
            raise MCPTransportError(f"Il server ha risposto {response.status_code}: {response.text[:200]}")

        # The session id is handed out on initialize and required afterwards.
        new_session = response.headers.get("Mcp-Session-Id")
        if new_session:
            self.session_id = new_session

        if payload.get("id") is None:
            return None                                 # a notification has no reply

        content_type = response.headers.get("Content-Type", "")
        if "text/event-stream" in content_type:
            return self._read_sse(response)
        try:
            return response.json()
        except ValueError as exc:
            raise MCPTransportError(f"Risposta non JSON dal server MCP: {response.text[:200]}") from exc

    @staticmethod
    def _read_sse(response) -> Dict[str, Any]:
        """First `data:` frame carrying a JSON-RPC reply."""
        for raw in response.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            chunk = raw[5:].strip()
            if not chunk:
                continue
            try:
                message = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if "result" in message or "error" in message:
                return message
        raise MCPTransportError("Stream SSE terminato senza una risposta")

    def request(self, method: str, params: Dict[str, Any] = None,
                timeout: float = CALL_TIMEOUT) -> Dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": uuid.uuid4().hex[:12], "method": method, "params": params or {}}
        message = self._post(payload, timeout) or {}
        if "error" in message:
            error = message["error"]
            raise MCPTransportError(f"{error.get('message', 'errore sconosciuto')} (code {error.get('code')})")
        return message.get("result", {})

    def notify(self, method: str, params: Dict[str, Any] = None) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params or {}}, CALL_TIMEOUT)


# --- the server facade -------------------------------------------------------

class ExternalMCPServer(BaseMCPServer):
    """A third-party MCP server, presented to the hub like any internal one.

    Connection is lazy: the tab lists servers without launching every child
    process, and a server that fails to start reports why instead of taking the
    hub down with it.
    """

    def __init__(self, spec: Dict[str, Any]):
        self.spec = dict(spec)
        self.server_id = spec.get("id") or uuid.uuid4().hex[:8]
        self.transport_kind = spec.get("transport", "stdio")
        self.default_safety = SAFE if spec.get("read_only") else SENSITIVE

        super().__init__(
            name=spec.get("name") or f"MCP {self.server_id}",
            version="external",
            description=spec.get("description") or "Server MCP esterno",
        )

        self._transport = None
        self._connected = False
        self._connect_error = ""
        self._connected_at = 0.0
        self._lock = threading.Lock()

    # --- connection ----------------------------------------------------------

    def _build_transport(self):
        if self.transport_kind == "http":
            url = self.spec.get("url", "")
            if not url:
                raise MCPTransportError("Manca l'URL del server MCP.")
            return HttpTransport(url, self.spec.get("headers"))

        command = self.spec.get("command", "")
        if not command:
            raise MCPTransportError("Manca il comando da eseguire per il server MCP.")
        return StdioTransport(command, self.spec.get("args"), self.spec.get("env"), self.spec.get("cwd"))

    def connect(self, force: bool = False) -> Dict[str, Any]:
        """Handshake, then import the server's tools into this facade."""
        with self._lock:
            if self._connected and not force and (not self._transport or self._transport.is_alive()):
                return {"connected": True, "tools": len(self._tools)}

            if force and self._transport:
                try:
                    self._transport.stop()
                except Exception:
                    pass
                self._connected = False

            self._connect_error = ""
            try:
                self._transport = self._build_transport()
                self._transport.start()

                self._transport.request("initialize", {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}, "resources": {}},
                    "clientInfo": CLIENT_INFO,
                }, timeout=HANDSHAKE_TIMEOUT)
                self._transport.notify("notifications/initialized")

                self._import_tools()
                self._connected = True
                self._connected_at = time.time()
                log.info("Server MCP esterno '%s' collegato: %d tool", self.name, len(self._tools))
                return {"connected": True, "tools": len(self._tools)}

            except MCPTransportError as exc:
                self._connect_error = str(exc)
                self._connected = False
                log.warning("Server MCP esterno '%s' non collegabile: %s", self.name, exc)
                return {"connected": False, "error": self._connect_error}
            except Exception as exc:
                self._connect_error = f"Errore inatteso: {exc}"
                self._connected = False
                log.error("Server MCP '%s': %s", self.name, exc, exc_info=True)
                return {"connected": False, "error": self._connect_error}

    def _import_tools(self) -> None:
        """Mirror the remote tool list as local registrations."""
        self._tools.clear()
        self._tool_handlers.clear()

        result = self._transport.request("tools/list", timeout=HANDSHAKE_TIMEOUT)
        for tool in result.get("tools", []):
            name = tool.get("name")
            if not name:
                continue
            self.register_tool(
                name=name,
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema") or {"type": "object", "properties": {}},
                handler=self._make_handler(name),
                safety=self.default_safety,
                category="external",
            )

        try:
            resources = self._transport.request("resources/list", timeout=HANDSHAKE_TIMEOUT)
            for res in resources.get("resources", []):
                uri = res.get("uri")
                if uri:
                    self.register_resource(
                        uri=uri, name=res.get("name", uri),
                        description=res.get("description", ""),
                        mime_type=res.get("mimeType", "text/plain"),
                        handler=self._make_resource_handler(uri),
                    )
        except MCPTransportError:
            pass                                       # resources are optional in MCP

    def _make_handler(self, tool_name: str):
        def handler(**arguments):
            state = self.connect()                     # reconnect if the child died
            if not state.get("connected"):
                raise RuntimeError(f"Server MCP '{self.name}' non collegato: {self._connect_error}")
            return self._transport.request("tools/call", {"name": tool_name, "arguments": arguments})
        return handler

    def _make_resource_handler(self, uri: str):
        def handler(_uri: str):
            self.connect()
            return self._transport.request("resources/read", {"uri": uri})
        return handler

    def disconnect(self) -> None:
        with self._lock:
            if self._transport:
                try:
                    self._transport.stop()
                except Exception:
                    pass
            self._connected = False

    # --- reporting -----------------------------------------------------------

    def is_configured(self) -> bool:
        return self._connected

    def connection_status(self) -> Dict[str, Any]:
        return {
            "id": self.server_id,
            "transport": self.transport_kind,
            "connected": self._connected,
            "error": self._connect_error,
            "tools": len(self._tools),
            "read_only": self.default_safety == SAFE,
            "connected_at": self._connected_at,
        }
