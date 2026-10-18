"""Ponte nativo fra Sigma Network e la rete AiLo (AiloCoin + inferenza distribuita).

La rete AiLo (https://github.com/xxrickyxx/ailo-network) e' un server Node che
tiene il registro AiloCoin (ALC) e smista le richieste di chat ai nodi GPU
collegati via WebSocket. Questo modulo parla quel protocollo direttamente, cosi'
Sigma Studio entra nella rete come un miner ufficiale senza installare il
client CUDA separato:

- **consumer**: ``POST /api/inference/gpu`` e ``/api/inference/fused`` mandano
  un prompt alla rete e ricevono la risposta di un nodo remoto;
- **provider**: ``AiloInferenceNode`` si collega a ``/ws/gpu-inference``,
  si registra con il wallet ALC e risponde alle ``inference_request`` usando il
  motore locale di Sigma Studio;
- **wallet**: saldo, storico e trasferimenti ALC tramite le API REST e il
  JSON-RPC ``/api/v1/rpc`` (metodi ``alc_*``).

Sicurezza: la password dell'account AiLo serve solo per login e trasferimenti,
viaggia nella singola richiesta e non viene mai salvata ne' loggata. Il nodo
provider espone soltanto generazione di testo, con ``max_tokens`` limitato lato
nostro qualunque cosa chieda il server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

#: Path WebSocket su cui il server AiLo accetta i nodi di inferenza GPU.
GPU_INFERENCE_WS_PATH = "/ws/gpu-inference"

#: Il server considera morto un nodo che tace per 60 s: il battito va ben sotto.
HEARTBEAT_SECONDS = 25.0

DEFAULT_CONFIG: Dict[str, Any] = {
    # Vuoto di proposito: ailo.site oggi serve un'altra applicazione, e mandare
    # email e password a un host che non e' un nodo AiLo sarebbe un regalo.
    # L'utente sceglie il server e ``verify_server`` controlla che lo sia.
    "server_url": "",
    "wallet": "",
    "email": "",
    "node_enabled": False,
    "node_max_tokens": 512,
    "node_model": "",
    "gpu_label": "",
}

# Una risposta del server e' sempre un dato, mai un'istruzione: la tagliamo
# prima di mostrarla per non riempire la UI con pagine HTML di errore.
_MAX_ERROR_TEXT = 300


class AiloError(RuntimeError):
    """Errore restituito dalla rete AiLo o dal trasporto verso di essa."""


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class AiloConfig:
    """Configurazione persistente del collegamento AiLo (mai la password)."""

    _ALLOWED = set(DEFAULT_CONFIG)

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if self._path.is_file():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                self._data.update({k: v for k, v in loaded.items() if k in self._ALLOWED})
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Config AiLo illeggibile in %s: %s", self._path, exc)

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def update(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Aggiorna solo le chiavi note: un campo ``password`` non arriva mai su disco."""
        with self._lock:
            for key, value in changes.items():
                if key in self._ALLOWED and value is not None:
                    self._data[key] = value
            self._data["server_url"] = normalize_server_url(self._data.get("server_url", ""))
            self._data["node_max_tokens"] = max(1, min(int(self._data["node_max_tokens"]), 4096))
            _atomic_write(self._path, self._data)
            return dict(self._data)


def normalize_server_url(url: str) -> str:
    """``ailo.example`` -> ``https://ailo.example``; niente slash finale."""
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "https://" + url
    return url


def ws_url_for(server_url: str) -> str:
    """URL WebSocket dei nodi GPU derivato dall'URL HTTP del server."""
    base = normalize_server_url(server_url)
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base + GPU_INFERENCE_WS_PATH


class AiloNetworkClient:
    """Client HTTP per le API pubbliche di un server AiLo."""

    def __init__(
        self,
        server_url: str,
        timeout: float = 20.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.server_url = normalize_server_url(server_url)
        if not self.server_url:
            raise AiloError("Server AiLo non configurato")
        self.timeout = timeout
        self._http = session or requests.Session()
        self._rpc_id = 0

    # ------------------------------------------------------------ trasporto

    def _request(self, method: str, path: str, *, timeout: Optional[float] = None, **kwargs: Any) -> Any:
        url = self.server_url + path
        try:
            resp = self._http.request(method, url, timeout=timeout or self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise AiloError(f"Server AiLo irraggiungibile: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise AiloError(
                f"Risposta non JSON da {path} (HTTP {resp.status_code}): {resp.text[:_MAX_ERROR_TEXT]}"
            ) from None
        if resp.status_code >= 400:
            message = data.get("error") if isinstance(data, dict) else None
            raise AiloError(str(message or f"HTTP {resp.status_code}")[:_MAX_ERROR_TEXT])
        return data

    def rpc(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """JSON-RPC 2.0 su ``/api/v1/rpc`` (metodi ``alc_*`` dell'AiloCoin SDK)."""
        self._rpc_id += 1
        data = self._request("POST", "/api/v1/rpc", json={
            "jsonrpc": "2.0", "method": method, "params": params or [], "id": self._rpc_id,
        })
        if not isinstance(data, dict):
            raise AiloError("Risposta RPC malformata")
        if data.get("error"):
            err = data["error"]
            raise AiloError(f"RPC {err.get('code')}: {err.get('message')}")
        return data.get("result")

    # ------------------------------------------------------------ rete

    def verify_server(self) -> Dict[str, Any]:
        """Controlla che dall'altra parte ci sia davvero un nodo AiLo.

        Si fida solo se il token dichiarato e' AiloCoin/ALC e lo stato espone i
        campi del coordinatore: senza questo controllo un URL sbagliato
        riceverebbe le credenziali dell'utente al primo login.
        """
        token = self.rpc("alc_getTokenInfo")
        if not isinstance(token, dict) or token.get("symbol") != "ALC":
            raise AiloError("Il server non dichiara il token AiloCoin (ALC): non e' un nodo AiLo")
        status = self._request("GET", "/api/status")
        if not isinstance(status, dict) or "globalModelVersion" not in status:
            raise AiloError("Il server non espone lo stato del coordinatore AiLo")
        return {"token": token, "status": status}

    def status(self) -> Dict[str, Any]:
        return self._request("GET", "/api/status")

    def network_stats(self) -> Dict[str, Any]:
        return self._request("GET", "/api/network-stats")

    def token_info(self) -> Dict[str, Any]:
        return self.rpc("alc_getTokenInfo")

    def chain_stats(self) -> Dict[str, Any]:
        return self.rpc("alc_getNetworkStats")

    # ------------------------------------------------------------ wallet

    def balance(self, wallet: str) -> Dict[str, Any]:
        """Saldo con quota confermata (spendibile dopo 10 conferme) e pendente."""
        if not wallet:
            raise AiloError("Wallet AiLo non impostato")
        return self._request("GET", f"/api/balance/{requests.utils.quote(wallet, safe='')}")

    def transactions(self, wallet: str, limit: int = 50) -> List[Dict[str, Any]]:
        result = self.rpc("alc_getTransactionsByAddress", [wallet, int(limit)])
        return result if isinstance(result, list) else []

    def login(self, email: str, password: str) -> Dict[str, Any]:
        data = self._request("POST", "/api/login", json={"email": email, "password": password})
        user = data.get("user") if isinstance(data, dict) else None
        if not user or not user.get("wallet"):
            raise AiloError("Login AiLo senza wallet nella risposta")
        return user

    def register(self, email: str, password: str) -> Dict[str, Any]:
        data = self._request("POST", "/api/register", json={"email": email, "password": password})
        user = data.get("user") if isinstance(data, dict) else None
        if not user or not user.get("wallet"):
            raise AiloError("Registrazione AiLo senza wallet nella risposta")
        return user

    def transfer(self, from_email: str, to_wallet: str, amount: float, password: str) -> Dict[str, Any]:
        """Trasferimento autenticato da password (``/api/transfer``).

        Si usa questo e non ``/api/ledger/transfer`` perche' quest'ultimo, nel
        server attuale, non verifica chi sta spendendo.
        """
        if amount <= 0:
            raise AiloError("Importo non valido")
        return self._request("POST", "/api/transfer", json={
            "fromEmail": from_email, "toWallet": to_wallet,
            "amount": float(amount), "password": password,
        })

    # ------------------------------------------------------------ inferenza

    def infer(
        self,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.8,
        backend: str = "gpu",
    ) -> Dict[str, Any]:
        """Inferenza distribuita: il server la passa a un nodo GPU della rete.

        ``backend='gpu'`` usa i miner collegati, ``'fused'`` il modello AILO
        allenato con FedAvg. Il server attende il nodo fino a 60 s.
        """
        if backend not in ("gpu", "fused"):
            raise AiloError("backend deve essere 'gpu' o 'fused'")
        data = self._request(
            "POST", f"/api/inference/{backend}", timeout=max(self.timeout, 90.0),
            json={"prompt": prompt, "max_tokens": int(max_tokens), "temperature": float(temperature)},
        )
        if not isinstance(data, dict):
            raise AiloError("Risposta di inferenza malformata")
        return data


GenerateFn = Callable[[str, int, float], Tuple[str, int]]
GateFn = Callable[[], Tuple[bool, str]]


class AiloInferenceNode:
    """Nodo provider: serve le richieste di inferenza della rete AiLo.

    Gira in un thread daemon con un proprio event loop, perche' le route
    FastAPI del modulo sono sincrone e il nodo deve sopravvivere alla singola
    richiesta che lo ha avviato. Si riconnette da solo con backoff.
    """

    def __init__(
        self,
        server_url: str,
        wallet: str,
        email: str,
        generate_fn: GenerateFn,
        gate_fn: Optional[GateFn] = None,
        max_tokens: int = 512,
        gpu_label: str = "",
        connect: Optional[Callable[..., Any]] = None,
    ) -> None:
        if not wallet:
            raise AiloError("Serve un wallet AiLo per ricevere le ricompense del nodo")
        self.ws_url = ws_url_for(server_url)
        self.wallet = wallet
        self.email = email
        self._generate = generate_fn
        self._gate = gate_fn or (lambda: (True, ""))
        self.max_tokens = max(1, min(int(max_tokens), 4096))
        self.gpu_label = gpu_label or "Sigma Studio"
        self._connect = connect
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop = threading.Event()
        self._state: Dict[str, Any] = {
            "running": False, "connected": False, "node_id": None,
            "inferences": 0, "tokens_generated": 0, "rejected": 0,
            "last_error": None, "connected_since": None, "history": [],
        }

    # ------------------------------------------------------------ ciclo vita

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._state["running"] = True
            self._thread = threading.Thread(target=self._run_thread, name="ailo-node", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(lambda: None)
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        with self._lock:
            self._state["running"] = False
            self._state["connected"] = False

    def status(self) -> Dict[str, Any]:
        with self._lock:
            out = dict(self._state)
            out["history"] = list(self._state["history"][-20:])
        out.update({"ws_url": self.ws_url, "wallet": self.wallet, "max_tokens": self.max_tokens})
        return out

    def _set(self, **changes: Any) -> None:
        with self._lock:
            self._state.update(changes)

    def _run_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._run())
        except Exception as exc:  # noqa: BLE001 - il thread non deve morire in silenzio
            logger.error("Nodo AiLo terminato per errore: %s", exc)
            self._set(last_error=str(exc))
        finally:
            self._loop.close()
            self._loop = None
            self._set(running=False, connected=False)

    async def _run(self) -> None:
        backoff = 2.0
        while not self._stop.is_set():
            try:
                await self._session()
                backoff = 2.0
            except Exception as exc:  # noqa: BLE001 - ogni caduta va ritentata
                logger.warning("Connessione al nodo AiLo persa: %s", exc)
                self._set(connected=False, last_error=str(exc)[:_MAX_ERROR_TEXT])
            if self._stop.is_set():
                break
            await self._sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    async def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < end:
            await asyncio.sleep(0.2)

    async def _session(self) -> None:
        connect = self._connect
        if connect is None:
            import websockets

            connect = websockets.connect
        async with connect(self.ws_url, ping_interval=30, ping_timeout=10, max_size=2**22) as ws:
            await ws.send(json.dumps({
                "type": "register_inference",
                "wallet": self.wallet,
                "email": self.email,
                "gpu": self.gpu_label,
                "vram": 0,
            }))
            self._set(connected=True, connected_since=time.time(), last_error=None)
            last_beat = time.monotonic()
            while not self._stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    raw = None
                if raw is not None:
                    await self._handle(ws, raw)
                if time.monotonic() - last_beat >= HEARTBEAT_SECONDS:
                    with self._lock:
                        count = self._state["inferences"]
                    await ws.send(json.dumps({"type": "heartbeat", "wallet": self.wallet, "inferences": count}))
                    last_beat = time.monotonic()

    # ------------------------------------------------------------ messaggi

    async def _handle(self, ws: Any, raw: Any) -> None:
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Messaggio non JSON dal server AiLo ignorato")
            return
        kind = msg.get("type")
        if kind == "registered":
            self._set(node_id=msg.get("nodeId"))
            logger.info("Nodo AiLo registrato: %s", msg.get("nodeId"))
        elif kind == "ping":
            await ws.send(json.dumps({"type": "pong"}))
        elif kind == "inference_request":
            await self._serve(ws, msg)

    async def _serve(self, ws: Any, msg: Dict[str, Any]) -> None:
        request_id = str(msg.get("request_id") or "")
        ok, reason = self._gate()
        if not ok:
            with self._lock:
                self._state["rejected"] += 1
            await ws.send(json.dumps({"type": "inference_error", "request_id": request_id, "error": reason}))
            return

        prompt = str(msg.get("prompt") or "")
        try:
            requested = int(msg.get("max_tokens") or self.max_tokens)
        except (TypeError, ValueError):
            requested = self.max_tokens
        max_tokens = max(1, min(requested, self.max_tokens))
        try:
            temperature = float(msg.get("temperature", 0.8))
        except (TypeError, ValueError):
            temperature = 0.8

        started = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            text, tokens = await loop.run_in_executor(None, self._generate, prompt, max_tokens, temperature)
        except Exception as exc:  # noqa: BLE001 - l'errore va restituito al server
            logger.warning("Inferenza AiLo %s fallita: %s", request_id, exc)
            await ws.send(json.dumps({"type": "inference_error", "request_id": request_id, "error": str(exc)}))
            self._set(last_error=str(exc)[:_MAX_ERROR_TEXT])
            return

        await ws.send(json.dumps({
            "type": "inference_response",
            "request_id": request_id,
            "wallet": self.wallet,
            "response": text,
            "tokens_generated": int(tokens),
            "model_epoch": 0,
        }))
        with self._lock:
            self._state["inferences"] += 1
            self._state["tokens_generated"] += int(tokens)
            self._state["history"].append({
                "request_id": request_id, "tokens": int(tokens),
                "latency_ms": int((time.monotonic() - started) * 1000), "at": time.time(),
            })
            del self._state["history"][:-50]
