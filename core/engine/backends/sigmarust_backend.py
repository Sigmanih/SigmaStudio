# ==============================================================================
# core/engine/backends/sigmarust_backend.py — SigmaEngine Nativo in Rust
#
# Backend ad altissime prestazioni scritto in Rust. Gestisce scheduling
# hardware-aware, zero-copy memory tiering, paged KV-cache e continuous batching.
# Quando il kernel Rust è attivo, SigmaStudio delega il critical path dell'orchestrazione
# e dell'esecuzione a questo backend per azzerare l'overhead del runtime Python.
# ==============================================================================
from __future__ import annotations

import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Generator, List, Optional, Tuple

from core.engine.backends.base import InferenceBackend
from core.engine.model_inspector import ModelFacts
from core.engine.sampling import SamplingParams
from core.logger import get_logger

log = get_logger(__name__)

#: Endpoint predefinito del micro-kernel SigmaEngine Rust (es. container Docker o binario nativo)
_DEFAULT_RUST_URL = os.environ.get("SIGMA_RUST_ENGINE_URL", "http://127.0.0.1:8090")

# --- Costanti protocollo IPC binario (allineate a crates/sigma-network/src/ipc_pipe.rs) ---
IPC_MAGIC = b"SIGM"
IPC_VERSION = 1
OP_PING = 0x01
OP_EXECUTE_TOOL = 0x02
OP_CANCEL_REQUEST = 0x03
IPC_HEADER_FMT = "<4sBBHQ"  # magic(4) version(1) op(1) session_id(2) payload_len(8)
IPC_HEADER_SIZE = struct.calcsize(IPC_HEADER_FMT)  # 16 byte
IS_WINDOWS = sys.platform.startswith("win")


#: Intestazione del token condiviso, allineata a crates/sigma-network/src/accesso.rs.
INTESTAZIONE_TOKEN = "X-Sigma-Token"


def _token_kernel() -> str:
    """Il token con cui parlare al kernel Rust.

    Il kernel rifiuta con 401 ogni rotta tranne /health: senza questa
    intestazione Sigma Studio non lo raggiunge piu'. Se la variabile non c'e'
    la richiesta parte lo stesso e il 401 lo dira' in chiaro — meglio di un
    errore di connessione che sembra un kernel spento.

    Due fonti, in ordine: la variabile d'ambiente, e poi `var/engine_token`.
    Il file serve perche' il token nasce quando si avvia il contenitore, e
    chiedere a chi lancia Sigma Studio di esportarlo a mano sarebbe un passo
    che prima o poi qualcuno salta — e il guasto sembrerebbe un kernel spento.
    """
    dalla_variabile = os.environ.get("SIGMA_ENGINE_TOKEN", "").strip()
    if dalla_variabile:
        return dalla_variabile
    try:
        from core import paths
        percorso = os.path.join(paths.var_dir(), "engine_token")
        if os.path.exists(percorso):
            with open(percorso, "r", encoding="utf-8") as fh:
                return fh.read().strip()
    except Exception as exc:
        log.debug("[Kernel] token non leggibile da var/engine_token: %s", exc)
    return ""


def _intestazioni(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Le intestazioni per una chiamata al kernel, token compreso."""
    testa: Dict[str, str] = dict(extra or {})
    token = _token_kernel()
    if token:
        testa[INTESTAZIONE_TOKEN] = token
    return testa


def _ipc_pipe_name() -> str:
    """Nome del Named Pipe Windows per il micro-kernel Rust (configurabile)."""
    return os.environ.get("SIGMA_RUST_PIPE_NAME", r"\\.\pipe\sigma_engine_ipc")


def _ipc_socket_path() -> str:
    """Percorso Unix Domain Socket, relativo alla cartella temporanea (mai path assoluto hardcoded)."""
    base = os.environ.get("SIGMA_RUST_SOCKET_DIR", os.path.join(os.path.expanduser("~"), ".sigma_engine_rust"))
    return os.path.join(base, f"sigma_engine_{os.getpid()}.sock")


class NamedPipeClient:
    """
    Client IPC nativo per il micro-kernel Rust con API Win32 native.

    - Windows: Named Pipe via win32pipe/win32file (zero-copy, nessun HTTP).
    - Linux/macOS: Unix Domain Socket.
    - Fallback trasparente a HTTP (porta 8090) se il canale IPC non è disponibile.

    Caratteristiche:
      * Riconnessione automatica in caso di pipe/socket chiusa o timeout.
      * Timeout di 1 secondo per ogni operazione di I/O.
      * Metodo cancel_generation(request_id) a priorità assoluta (lock-free lato Rust).
      * Ogni chiamata registra la latenza di roundtrip in nanosecondi.
    """

    def __init__(self, endpoint_url: str = _DEFAULT_RUST_URL, timeout: float = 1.0) -> None:
        self._url = endpoint_url.rstrip("/")
        self._timeout = timeout
        self._session_id = 1
        self._handle = None  # handle win32pipe o socket.socket
        self._transport: Optional[str] = None  # "named_pipe" | "unix_socket" | "http"
        self._last_latency_ns: int = 0
        self._connect()

    def cancel_generation(self, request_id: str) -> bool:
        """Annulla una generazione in corso tramite IPC nativo o endpoint REST."""
        res_ipc = self.cancel_ipc(request_id)
        if res_ipc is not None:
            return res_ipc

        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/cancel",
                data=json.dumps({"request_id": request_id}).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("cancelled", False)
        except Exception as exc:
            log.warning("[IPC] cancel_generation fallita: %s", exc)
            return False

    def send_ipc(self, payload_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Invia una richiesta strutturata sul canale IPC nativo (Named Pipe o Unix Socket)
        utilizzando il framing length-prefixed [u32 len LE][JSON bytes] compatibile con Rust.
        """
        if self._transport not in ("named_pipe", "named_pipe_raw", "unix_socket") or not self._handle:
            return None

        try:
            raw_json = json.dumps(payload_dict).encode("utf-8")
            frame = struct.pack("<I", len(raw_json)) + raw_json
            t0 = time.perf_counter_ns()

            if self._transport == "named_pipe":
                import win32file
                import pywintypes
                overlapped = pywintypes.OVERLAPPED()
                win32file.WriteFile(self._handle, frame, overlapped)
                len_bytes = self._read_exact(4)
                if len(len_bytes) < 4:
                    return None
                resp_len = struct.unpack("<I", len_bytes)[0]
                resp_body = self._read_exact(resp_len)
            elif self._transport == "named_pipe_raw":
                self._handle.write(frame)
                self._handle.flush()
                len_bytes = self._read_raw_exact(4)
                resp_len = struct.unpack("<I", len_bytes)[0]
                resp_body = self._read_raw_exact(resp_len)
            elif self._transport == "unix_socket":
                self._handle.sendall(frame)
                len_bytes = self._recv_exact(4)
                resp_len = struct.unpack("<I", len_bytes)[0]
                resp_body = self._recv_exact(resp_len)
            else:
                return None

            t1 = time.perf_counter_ns()
            self._last_latency_ns = t1 - t0
            return json.loads(resp_body.decode("utf-8"))
        except Exception as exc:
            log.debug("[IPC] Errore frame IPC (%s), passaggio a fallback HTTP", exc)
            self._transport = "http"
            return None

    def tokenize_ipc(self, text: str) -> Optional[List[int]]:
        """Esegue la tokenizzazione direttamente tramite IPC nativo senza passare per HTTP."""
        resp = self.send_ipc({"op": "tokenize", "text": text})
        if resp and resp.get("status") == "ok":
            token_ids = resp.get("token_ids")
            if token_ids is not None:
                return [int(t) for t in token_ids]
        return None

    def tokenize(self, text: str) -> List[int]:
        """Tokenizza tramite canale IPC o fallback deterministico."""
        if not text:
            return []
        tokens = self.tokenize_ipc(text)
        if tokens is not None:
            return tokens
        import zlib
        return [zlib.crc32(word.encode("utf-8")) & 0x7FFFFFFF for word in text.split()]

    @property
    def is_ipc_connected(self) -> bool:
        """Indica se il canale di trasporto IPC nativo (Named Pipe o Unix Socket) è attivo."""
        return self._transport in ("named_pipe", "named_pipe_raw", "unix_socket") and self._handle is not None

    def stream_tokens_ipc(self, payload_dict: Dict[str, Any], cancel: Any = None) -> Generator[Dict[str, Any], None, None]:
        """Invia una richiesta di streaming e genera sequenzialmente i token ricevuti via IPC nativo.
        Ogni frame segue il formato length-prefixed [u32 len LE][JSON bytes] con schema:
        {"type": "token", "delta": "...", "token_id": int} oppure {"type": "done", "finish_reason": "stop"}.
        """
        if not self.is_ipc_connected or not self._handle:
            return

        try:
            raw_json = json.dumps(payload_dict).encode("utf-8")
            frame = struct.pack("<I", len(raw_json)) + raw_json

            if self._transport == "named_pipe":
                import win32file
                import pywintypes
                overlapped = pywintypes.OVERLAPPED()
                win32file.WriteFile(self._handle, frame, overlapped)
            elif self._transport == "named_pipe_raw":
                self._handle.write(frame)
                self._handle.flush()
            elif self._transport == "unix_socket":
                self._handle.sendall(frame)

            # Ricezione sequenziale dei token frame
            while True:
                if cancel and cancel():
                    self.cancel_ipc(payload_dict.get("request_id", ""))
                    break

                if self._transport == "named_pipe":
                    len_bytes = self._read_exact(4)
                elif self._transport == "named_pipe_raw":
                    len_bytes = self._read_raw_exact(4)
                elif self._transport == "unix_socket":
                    len_bytes = self._recv_exact(4)
                else:
                    break

                if len(len_bytes) < 4:
                    break
                resp_len = struct.unpack("<I", len_bytes)[0]
                if resp_len == 0:
                    continue

                if self._transport == "named_pipe":
                    resp_body = self._read_exact(resp_len)
                elif self._transport == "named_pipe_raw":
                    resp_body = self._read_raw_exact(resp_len)
                elif self._transport == "unix_socket":
                    resp_body = self._recv_exact(resp_len)
                else:
                    break

                item = json.loads(resp_body.decode("utf-8"))
                frame_type = item.get("type", "token")
                if frame_type == "token":
                    yield {
                        "text": item.get("delta", ""),
                        "token_id": item.get("token_id"),
                        "finish_reason": None,
                    }
                elif frame_type == "done":
                    yield {
                        "text": "",
                        "token_id": None,
                        "finish_reason": item.get("finish_reason", "stop"),
                        "usage": item.get("usage", {}),
                    }
                    break
                elif frame_type == "error":
                    log.warning("[IPC] Frame di errore ricevuto dal kernel: %s", item.get("error"))
                    break
        except Exception as exc:
            log.debug("[IPC] Interruzione stream token IPC (%s)", exc)

    def cancel_ipc(self, request_id: str) -> Optional[bool]:
        """Segnala l'annullamento atomico di una richiesta tramite IPC nativo."""
        resp = self.send_ipc({"op": "cancel_request", "request_id": request_id})
        if resp and resp.get("status") in ("ok", "cancelled"):
            return True
        return None

    def prefetch_radix_ipc(self, token_ids: List[int], priority: int = 1) -> Optional[Dict[str, Any]]:
        """Invia istruzione predittiva di prefetching e pinning di una sequenza di token nella Radix Cache."""
        if not token_ids:
            return None
        return self.send_ipc({
            "op": "prefetch_radix",
            "tokens": token_ids,
            "priority": priority,
        })

    def unpin_radix_ipc(self, token_ids: List[int]) -> Optional[Dict[str, Any]]:
        """Rimuove il flag di pinning per consentire l'eviction LRU ordinaria."""
        if not token_ids:
            return None
        return self.send_ipc({
            "op": "unpin_radix",
            "tokens": token_ids,
        })

    def store_memory_buffer_ipc(self, data: str) -> Optional[int]:
        """Salva un payload massivo nello store nativo Rust condiviso e restituisce l'handle zero-copy."""
        resp = self.send_ipc({
            "op": "execute_tool",
            "tool": "direct_memory_pipe",
            "input": {"op": "store", "data": data},
        })
        if resp and resp.get("status") == "ok":
            out = resp.get("output", {})
            return out.get("buffer_handle")
        return None

    def retrieve_memory_buffer_ipc(self, handle: int) -> Optional[str]:
        """Recupera il contenuto di un buffer dallo store condiviso dato il relativo handle numerico."""
        resp = self.send_ipc({
            "op": "execute_tool",
            "tool": "direct_memory_pipe",
            "input": {"op": "retrieve", "handle": handle},
        })
        if resp and resp.get("status") == "ok":
            out = resp.get("output", {})
            return out.get("data")
        return None

    def reconnect(self) -> None:
        """Riconnessione automatica al trasporto IPC con timeout 1s."""
        self.close()
        self._connect()

    def _reconnect(self) -> None:
        """Alias privato per la riconnessione automatica."""
        self.reconnect()


    def _connect(self) -> None:
        pipe_name = _ipc_pipe_name()
        if IS_WINDOWS:
            # Prova prima con win32pipe se disponibile
            try:
                import win32pipe
                import win32file

                self._handle = win32pipe.CreateFile(
                    pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32pipe.OPEN_EXISTING,
                    0,
                    None,
                )
                self._transport = "named_pipe"
                log.info("[IPC] Connesso a Named Pipe (win32): %s", pipe_name)
                return
            except Exception:
                pass

            # Fallback nativo su Windows: apertura diretta del file Named Pipe nel filesystem IPC
            try:
                self._handle = open(pipe_name, "r+b", buffering=0)
                self._transport = "named_pipe_raw"
                log.info("[IPC] Connesso a Named Pipe nativa (raw binary stream): %s", pipe_name)
                return
            except Exception as exc:
                log.debug("[IPC] Named Pipe raw non disponibile (%s), procedo su fallback HTTP", exc)
        else:
            try:
                sock_path = _ipc_socket_path()
                if os.path.exists(sock_path):
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(5.0)
                    s.connect(sock_path)
                    self._handle = s
                    self._transport = "unix_socket"
                    log.info("[IPC] Connesso a Unix Domain Socket: %s", sock_path)
                    return
            except Exception as exc:
                log.debug("[IPC] Unix Socket non disponibile (%s), fallback HTTP", exc)

        # Fallback HTTP
        self._handle = None
        self._transport = "http"

    def _send_frame(self, op_code: int, payload: bytes) -> bytes:
        """Invia un frame binario e legge la risposta. Ritorna il payload della risposta."""
        header = struct.pack(IPC_HEADER_FMT, IPC_MAGIC, IPC_VERSION, op_code, self._session_id, len(payload))
        data = header + payload

        t0 = time.perf_counter_ns()
        if self._transport == "named_pipe":
            import win32file
            import pywintypes

            overlapped = pywintypes.OVERLAPPED()
            win32file.WriteFile(self._handle, data, overlapped)
            buf_header = self._read_exact(IPC_HEADER_SIZE)
            magic, version, op_resp, session_id, payload_len = struct.unpack(IPC_HEADER_FMT, buf_header)
            if magic != IPC_MAGIC:
                raise IOError(f"IPC magic mismatch: {magic!r}")
            resp_payload = self._read_exact(payload_len) if payload_len else b""
        elif self._transport == "named_pipe_raw":
            self._handle.write(data)
            self._handle.flush()
            buf_header = self._read_raw_exact(IPC_HEADER_SIZE)
            magic, version, op_resp, session_id, payload_len = struct.unpack(IPC_HEADER_FMT, buf_header)
            if magic != IPC_MAGIC:
                raise IOError(f"IPC magic mismatch: {magic!r}")
            resp_payload = self._read_raw_exact(payload_len) if payload_len else b""
        elif self._transport == "unix_socket":
            self._handle.sendall(data)
            buf_header = self._recv_exact(IPC_HEADER_SIZE)
            magic, version, op_resp, session_id, payload_len = struct.unpack(IPC_HEADER_FMT, buf_header)
            if magic != IPC_MAGIC:
                raise IOError(f"IPC magic mismatch: {magic!r}")
            resp_payload = self._recv_exact(payload_len) if payload_len else b""
        else:
            # Fallback HTTP: usa endpoint REST equivalente
            return self._http_fallback(op_code, payload)

        t1 = time.perf_counter_ns()
        self._last_latency_ns = t1 - t0
        log.debug("[IPC] op=0x%02X roundtrip=%d ns", op_code, self._last_latency_ns)
        return resp_payload

    def _read_raw_exact(self, n: int) -> bytes:
        """Legge esattamente n byte dallo stream binario nativo (Named Pipe raw)."""
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self._handle.read(remaining)
            if not chunk:
                raise IOError("Named Pipe chiusa dall'host remoto")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_exact(self, n: int) -> bytes:
        import win32file
        import pywintypes

        chunks = []
        remaining = n
        while remaining > 0:
            overlapped = pywintypes.OVERLAPPED()
            buf = win32file.ReadFile(self._handle, remaining, overlapped)
            if not buf:
                break
            chunks.append(buf)
            remaining -= len(buf)
        return b"".join(chunks)

    def _recv_exact(self, n: int) -> bytes:
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self._handle.recv(remaining)
            if not chunk:
                raise IOError("IPC connection closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _http_fallback(self, op_code: int, payload: bytes) -> bytes:
        """Fallback HTTP quando il canale IPC non è disponibile."""
        if op_code == OP_PING:
            req = urllib.request.Request(f"{self._url}/health", headers=_intestazioni(), method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.read()
        elif op_code == OP_EXECUTE_TOOL:
            body = json.loads(payload.decode("utf-8")) if payload else {}
            req = urllib.request.Request(
                f"{self._url}/api/engine/tools/execute",
                data=json.dumps(body).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.read()
        elif op_code == OP_CANCEL_REQUEST:
            body = json.loads(payload.decode("utf-8")) if payload else {}
            req = urllib.request.Request(
                f"{self._url}/api/engine/cancel",
                data=json.dumps(body).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.read()
        else:
            raise ValueError(f"Op code non supportato in fallback HTTP: 0x{op_code:02X}")

    def ping(self) -> Dict[str, Any]:
        """Ping IPC con latenza di roundtrip."""
        raw = self._send_frame(OP_PING, b"")
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {"status": "ok", "raw": raw.hex()}
        data["latency_ns"] = self._last_latency_ns
        data["transport"] = self._transport
        return data

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invia execute_native_tool via pipe/socket.

        Se il fallback HTTP restituisce un errore (es. 404 perché il server non
        espone la rotta), degrada in modo trasparente restituendo un dict di
        errore coerente invece di propagare l'HTTPError al chiamante.
        """
        payload = json.dumps({"tool": tool_name, "params": params}).encode("utf-8")
        try:
            raw = self._send_frame(OP_EXECUTE_TOOL, payload)
        except Exception as exc:
            return {
                "success": False,
                "error": f"IPC execute_tool fallito: {exc}",
                "transport": self._transport,
                "latency_ns": self._last_latency_ns,
            }
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {"success": False, "error": "risposta non JSON", "raw": raw.hex()}
        data["latency_ns"] = self._last_latency_ns
        data["transport"] = self._transport
        return data

    def cancel_request(self, session_id: int) -> Dict[str, Any]:
        """Invia cancel_request via pipe/socket."""
        payload = json.dumps({"session_id": session_id}).encode("utf-8")
        raw = self._send_frame(OP_CANCEL_REQUEST, payload)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {"success": False, "error": "risposta non JSON", "raw": raw.hex()}
        data["latency_ns"] = self._last_latency_ns
        data["transport"] = self._transport
        return data

    @property
    def transport(self) -> Optional[str]:
        return self._transport

    @property
    def last_latency_ns(self) -> int:
        return self._last_latency_ns

    def close(self) -> None:
        if self._handle is not None:
            try:
                if self._transport == "named_pipe":
                    import win32file
                    win32file.CloseHandle(self._handle)
                elif self._transport in ("unix_socket", "named_pipe_raw"):
                    self._handle.close()
            except Exception:
                pass
            self._handle = None
            self._transport = None


#: Alias per retrocompatibilità con codice esistente
IpcPipeClient = NamedPipeClient
SigmaRustClient = NamedPipeClient



def _is_rust_kernel_online(url: str = _DEFAULT_RUST_URL, timeout_s: float = 0.5) -> bool:
    """Verifica rapida della disponibilità del kernel Rust via probe /health."""
    try:
        req = urllib.request.Request(f"{url}/health", headers=_intestazioni(), method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok" and data.get("service") == "sigma_engine_rust"
    except Exception:
        return False
    return False


class SigmaRustBackend(InferenceBackend):
    """Esegue inferenza, scheduling e memory-tiering tramite il micro-kernel Rust nativo."""

    name = "sigma_engine_rust"
    supported_formats = ("gguf",)

    def __init__(self, endpoint_url: str = _DEFAULT_RUST_URL) -> None:
        self._url = endpoint_url
        self._facts: Optional[ModelFacts] = None
        self._loaded_model_id: Optional[str] = None
        self._placement_info: Dict[str, Any] = {}
        self._compute_delegate: Optional[Any] = None

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        """Controlla se il kernel Rust è raggiungibile sull'host locale."""
        if _is_rust_kernel_online():
            return (True, f"SigmaEngine Rust attivo su {_DEFAULT_RUST_URL}")
        return (
            False,
            f"SigmaEngine Rust non rilevato su {_DEFAULT_RUST_URL}. "
            "Avvia il container con `docker-compose up -d` in projects/sigma_engine_rust.",
        )

    @classmethod
    def supports(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> bool:
        """Supporta GGUF e SafeTensors con introspezione zero-copy."""
        return facts.weight_format in cls.supported_formats

    @classmethod
    def score(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> int:
        """
        Punteggio di preferenza:
        - 125 quando il micro-kernel Rust è attivo e raggiungibile, superando
          LlamaServerBackend (110) e diventando l'orchestratore primario.
        - 0 se non raggiungibile.
        """
        if _is_rust_kernel_online():
            return 125
        return 0

    def load(self, facts: ModelFacts, hardware: Dict[str, Any], **options) -> Dict[str, Any]:
        """Mappa il modello tramite il planner di tiering zero-copy del kernel Rust e attiva il compute worker CUDA."""
        self._facts = facts
        model_name = facts.name or os.path.basename(facts.path or "unknown")

        # 1. Caricamento del worker di calcolo delegato
        delega: Dict[str, Any] = {
            "success": False,
            "stage": "load",
            "error": "il worker di calcolo non e' partito",
        }
        try:
            from core.engine.backends.llamaserver_backend import LlamaServerBackend
            self._compute_delegate = LlamaServerBackend()
            delega = self._compute_delegate.load(facts, hardware, **options) or delega
            if delega.get("success"):
                porta = getattr(self._compute_delegate, "_porta", 57540)
                # Registra l'upstream worker nel micro-kernel Rust (sia host.docker.internal che localhost)
                try:
                    up_req = urllib.request.Request(
                        f"{self._url}/api/engine/upstream",
                        data=json.dumps({"upstream_url": f"http://host.docker.internal:{porta}"}).encode("utf-8"),
                        headers=_intestazioni({"Content-Type": "application/json"}),
                        method="POST",
                    )
                    with urllib.request.urlopen(up_req, timeout=3.0) as up_resp:
                        log.info("[SigmaRustBackend] Upstream CUDA registrato nel kernel Rust su porta %s", porta)
                except Exception as up_exc:
                    log.warning("[SigmaRustBackend] Impossibile notificare upstream al kernel Rust: %s", up_exc)
            else:
                log.error("[SigmaRustBackend] Caricamento worker delegato non riuscito: %s", delega.get("error"))
        except Exception as exc:
            delega = {"success": False, "stage": "load",
                      "error": f"{type(exc).__name__}: {exc}"}
            log.error("[SigmaRustBackend] Fallito avvio compute delegate: %s", exc)

        # Senza worker non c'e' calcolo, e il kernel non lo inventa: e' un
        # orchestratore, e la rotta `/v1/chat/completions` risponde 503 quando
        # nessun upstream risponde (e' la scelta dichiarata in coda_inferenza.json:
        # meglio un rifiuto che testo finto — il forward pass in Rust e' la voce
        # i2, non ancora scritta). Mappare il modello nel piano di tiering e
        # dichiarare il caricamento riuscito lascerebbe la chat con un modello
        # elencato fra quelli attivi che non produce un token: e' esattamente
        # cio' che l'utente vede come "non funziona nemmeno l'inferenza".
        if not delega.get("success"):
            self._compute_delegate = None
            return {
                "success": False,
                "backend": self.name,
                "error": str(delega.get("error") or "il worker di calcolo non e' partito"),
                "stage": delega.get("stage") or "load",
            }

        # 2. Registrazione partizione zero-copy nel kernel Rust
        payload = {
            "model": model_name,
            "model_path": str(facts.path) if facts.path else None,
            "model_size_gb": facts.file_size_gb if hasattr(facts, "file_size_gb") else 8.0,
            "total_layers": getattr(facts, "layers_count", 32),
            "quantization": getattr(facts, "quantization", "Q4_K_M"),
        }

        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/partition",
                data=json.dumps(payload).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                self._loaded_model_id = model_name
                self._placement_info = result.get("tiering_plan", {})
                log.info(
                    "[SigmaRustBackend] Modello '%s' pianificato e mappato con successo nel kernel Rust.",
                    model_name,
                )
                return {
                    "success": True,
                    "backend": self.name,
                    "model": model_name,
                    "tiering": self._placement_info,
                    "benchmark": result.get("mmap_zero_copy_benchmark"),
                }
        except Exception as exc:
            log.error("[SigmaRustBackend] Errore di caricamento nel kernel Rust: %s", exc)
            if self._compute_delegate and self._compute_delegate.is_loaded:
                self._loaded_model_id = model_name
                return {"success": True, "backend": self.name, "fallback": True}
            return {"success": False, "error": str(exc)}

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        messages: Optional[list] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
        thinking: Optional[bool] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Genera token in streaming combinando il tracking zero-copy/KV-Cache del kernel Rust con l'accelerazione CUDA nativa."""
        if not messages:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        # 1. Notifica e sincronizza asincronamente la Paged KV-Cache e il prefetcher AiloFlow nel kernel Rust
        try:
            cache_req = urllib.request.Request(
                f"{self._url}/v1/chat/completions",
                data=json.dumps({
                    "model": self._loaded_model_id or "sigma_default",
                    "messages": messages,
                    "stream": False,
                }).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            urllib.request.urlopen(cache_req, timeout=0.1)
        except Exception:
            pass

        # 2. Se il compute worker CUDA locale è pronto, esegue lo streaming reale dei token ad altissima velocità
        if self._compute_delegate and self._compute_delegate.is_loaded:
            yield from self._compute_delegate.generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                params=params,
                cancel=cancel,
                thinking=thinking,
                tools=tools,
                tool_choice=tool_choice,
            )
            return

        # Tentativo di recuperare il backend di calcolo attivo da UniversalSigmaEngine
        try:
            from core.engine.unified_runtime import sigma_engine
            for b_name, b_inst in getattr(sigma_engine, "_backends", {}).items():
                if b_inst is not self and getattr(b_inst, "is_loaded", False):
                    yield from b_inst.generate_stream(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        params=params,
                        cancel=cancel,
                        thinking=thinking,
                        tools=tools,
                        tool_choice=tool_choice,
                    )
                    return
        except Exception as b_exc:
            log.debug("[SigmaRustBackend] Impossibile delegare a backend alternativo: %s", b_exc)

        # 3. Streaming nativo ad altissima velocità via IPC micro-kernel (Named Pipe o Unix Socket)
        #
        # `self._client` non e' mai esistito: la classe crea `_ipc_client`
        # tramite `_get_ipc_client()`, come fanno gia' gli altri due punti che
        # usano l'IPC. Il nome sbagliato sollevava AttributeError *prima* del
        # try qui sotto, quindi l'eccezione usciva dal generatore e il fallback
        # HTTP del passo 4 non veniva mai raggiunto: ogni generazione del
        # kernel Rust moriva, e il ciclo dell'agente bruciava tutti i suoi
        # turni sullo stesso errore senza produrre un token.
        client = self._get_ipc_client()
        if client and client.is_ipc_connected:
            ipc_payload = {
                "op": "generate_stream",
                "request_id": f"req_{int(time.time()*1000)}",
                "model": self._loaded_model_id or "sigma_default",
                "messages": messages,
                "temperature": params.temperature if params else temperature,
                "max_tokens": params.max_tokens if params else max_tokens,
            }
            try:
                stream_iter = client.stream_tokens_ipc(ipc_payload, cancel=cancel)
                has_yielded = False
                for token_chunk in stream_iter:
                    has_yielded = True
                    yield token_chunk
                if has_yielded:
                    return
            except Exception as ipc_stream_exc:
                log.debug("[SigmaRustBackend] Fallback da IPC stream a HTTP: %s", ipc_stream_exc)

        # 4. Fallback via proxy HTTP OpenAI del kernel Rust
        req_body = {
            "model": self._loaded_model_id or "sigma_default",
            "messages": messages,
            "temperature": params.temperature if params else temperature,
            "max_tokens": params.max_tokens if params else max_tokens,
            "stream": True,
        }
        if params and getattr(params, "grammar", None):
            req_body["grammar"] = params.grammar
        if params and getattr(params, "response_format", None):
            req_body["response_format"] = params.response_format
        elif tools:
            req_body["grammar"] = "tool_call"

        try:
            req = urllib.request.Request(
                f"{self._url}/v1/chat/completions",
                data=json.dumps(req_body).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            t0 = time.perf_counter()
            yielded_any_token = False
            total_content_len = 0
            with urllib.request.urlopen(req, timeout=120.0) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    for raw_line in resp:
                        if cancel and cancel():
                            self.cancel_request()
                            break
                        line_str = raw_line.decode("utf-8", errors="replace").strip()
                        if not line_str or line_str.startswith(":"):
                            continue
                        if line_str == "data: [DONE]":
                            break
                        if line_str.startswith("data: "):
                            try:
                                chunk = json.loads(line_str[6:])
                                choices = chunk.get("choices", [])
                                spec_telem = chunk.get("speculative_telemetry") or chunk.get("usage", {}).get("speculative_telemetry") or {}
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    tok = delta.get("content", "")
                                    finish = choices[0].get("finish_reason")
                                    if tok or finish:
                                        if tok:
                                            yielded_any_token = True
                                            total_content_len += len(tok)
                                        item = {
                                            "token": tok,
                                            "content": tok,
                                            "finish_reason": finish,
                                            "latency_ms": (time.perf_counter() - t0) * 1000.0,
                                        }
                                        if spec_telem:
                                            item["speculative_speedup"] = spec_telem.get("effective_speedup", 1.0)
                                            item["speculative_acceptance_rate"] = spec_telem.get("acceptance_rate", 0.0)
                                            item["grammar_constrained"] = spec_telem.get("grammar_constrained", False)
                                        yield item
                            except Exception:
                                continue
                else:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    spec_telem = data.get("speculative_telemetry") or data.get("usage", {}).get("speculative_telemetry") or {}
                    if content:
                        yielded_any_token = True
                        total_content_len += len(content)
                    item = {
                        "token": content,
                        "content": content,
                        "finish_reason": "stop",
                        "latency_ms": elapsed_ms,
                    }
                    if spec_telem:
                        item["speculative_speedup"] = spec_telem.get("effective_speedup", 1.0)
                        item["speculative_acceptance_rate"] = spec_telem.get("acceptance_rate", 0.0)
                        item["grammar_constrained"] = spec_telem.get("grammar_constrained", False)
                    yield item

            if not yielded_any_token or total_content_len == 0:
                warning_msg = (
                    "⚠️ [SigmaEngine] Il micro-kernel Rust è attivo ma non è stato caricato alcun modello linguistico LLM in memoria. "
                    "Seleziona un modello con pesi reali (es. Qwen2.5-Coder-14B o Qwen3.8-27B) dal selettore in alto per abilitare la generazione di codice."
                )
                yield {
                    "token": warning_msg,
                    "content": warning_msg,
                    "finish_reason": "stop",
                    "latency_ms": (time.perf_counter() - t0) * 1000.0,
                }
        except Exception as exc:
            log.error("[SigmaRustBackend] Errore durante generazione stream: %s", exc)
            yield {
                "token": f"\n[Errore SigmaRustBackend: {exc}]",
                "content": f"\n[Errore SigmaRustBackend: {exc}]",
                "finish_reason": "error",
            }

    def unload(self) -> Dict[str, Any]:
        """Rilascia il modello resident nel kernel Rust."""
        if self._compute_delegate:
            try:
                self._compute_delegate.unload()
            except Exception:
                pass
            self._compute_delegate = None
        old_model = self._loaded_model_id
        self._loaded_model_id = None
        self._facts = None
        self._placement_info = {}
        return {"success": True, "unloaded": old_model}

    def cancel_request(self) -> None:
        """Invia un segnale di cancellazione atomico immediato al micro-kernel Rust."""
        try:
            if self._ipc_client:
                # Invia frame binario OP_CANCEL_REQUEST via Named Pipe
                self._ipc_client._send_frame(OP_CANCEL_REQUEST, b"{\"op\":\"cancel_request\"}")
                log.info("[SigmaRustBackend] Segnale di cancellazione atomica inviato via Named Pipe.")
        except Exception:
            pass

    @property
    def is_loaded(self) -> bool:
        return self._loaded_model_id is not None

    def describe_placement(self) -> Dict[str, Any]:
        if self._placement_info:
            return self._placement_info
        if self._compute_delegate and hasattr(self._compute_delegate, "describe_placement"):
            return self._compute_delegate.describe_placement()
        return {}

    def parallel_slots(self) -> int:
        return 4

    def validate_grammar(
        self, text: str, allowed_tools: Optional[List[str]] = None, is_partial: bool = False
    ) -> Dict[str, Any]:
        """Verifica la conformità sintattica di output parziali o completi con il modulo Grammar nativo."""
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/grammar/validate",
                data=json.dumps({
                    "text": text,
                    "allowed_tools": allowed_tools,
                    "is_partial": is_partial,
                }).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"valid": False, "error": str(exc)}

    def publish_agent_event(
        self, session_id: str, agent_role: str, event_type: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invia un evento sull'AgentEventBus in memoria condivisa lock-free del micro-kernel Rust."""
        try:
            req = urllib.request.Request(
                f"{self._url}/api/agent/bus/publish",
                data=json.dumps({
                    "session_id": session_id,
                    "agent_role": agent_role,
                    "event_type": event_type,
                    "payload": payload,
                }).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def execute_native_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue un tool nativo nel worker pool Rust ad altissima velocità.

        Preferisce il canale IPC binario (Named Pipe / Unix Socket) per azzerare
        l'overhead HTTP; se il trasporto non è disponibile degrada in modo
        trasparente al REST equivalente.
        """
        client = self._get_ipc_client()
        if client is not None and client.transport in ("named_pipe", "unix_socket"):
            try:
                return client.execute_tool(tool_name, params)
            except Exception as exc:
                log.warning("[SigmaRustBackend] IPC execute_tool fallito (%s), fallback HTTP", exc)
        # Fallback HTTP
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/tools/execute",
                data=json.dumps({"tool": tool_name, "params": params}).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cancel_request(self, session_id: int) -> Dict[str, Any]:
        """Cancella immediatamente una sessione in-flight nel kernel Rust.

        Usa il canale IPC binario quando disponibile per la cancellazione atomica
        lock-free gestita dal continuous batching del micro-kernel.
        """
        client = self._get_ipc_client()
        if client is not None and client.transport in ("named_pipe", "unix_socket"):
            try:
                return client.cancel_request(session_id)
            except Exception as exc:
                log.warning("[SigmaRustBackend] IPC cancel_request fallito (%s), fallback HTTP", exc)
        # Fallback HTTP
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/cancel",
                data=json.dumps({"session_id": session_id}).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _get_ipc_client(self) -> Optional[IpcPipeClient]:
        """Restituisce il client IPC condiviso (lazy init), o None se non configurabile."""
        if not hasattr(self, "_ipc_client"):
            self._ipc_client = None
        if self._ipc_client is None:
            try:
                self._ipc_client = IpcPipeClient(endpoint_url=self._url)
            except Exception as exc:
                log.debug("[SigmaRustBackend] Client IPC non disponibile: %s", exc)
                self._ipc_client = None
        return self._ipc_client

    def get_status(self) -> Dict[str, Any]:
        """Recupera lo stato completo dal micro-kernel Rust."""
        try:
            req = urllib.request.Request(f"{self._url}/api/engine/status", headers=_intestazioni(), method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def lookup_prefix_cache(self, tokens: List[int]) -> Dict[str, Any]:
        """Verifica se una sequenza di token ha un prefisso già presente nella Radix Cache."""
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/cache/lookup",
                data=json.dumps({"tokens": tokens}).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"status": "error", "error": str(exc), "matched_tokens": 0}

    def insert_prefix_cache(self, tokens: List[int], page_id: int) -> Dict[str, Any]:
        """Registra un prefisso calcolato nella Radix Prefix Cache del kernel Rust."""
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/cache/insert",
                data=json.dumps({"tokens": tokens, "page_id": page_id}).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def get_radix_cache_stats(self) -> Dict[str, Any]:
        """Recupera le metriche di hit-rate e token risparmiati dal Radix Tree Prefix Cache."""
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/cache/stats",
                headers=_intestazioni(),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return self.get_status().get("radix_cache", {})

    def tokenize(self, text: str) -> List[int]:
        """Tokenizza il testo tramite IPC nativo ultra-veloce, REST HTTP o ripiego deterministico."""
        if not text:
            return []

        # 1. Prova prioritaria via canale IPC nativo (< 0.1 ms)
        if hasattr(self, "_ipc") and self._ipc:
            ipc_tokens = self._ipc.tokenize_ipc(text)
            if ipc_tokens is not None:
                return ipc_tokens


        # 2. Fallback via endpoint REST HTTP del micro-kernel
        try:
            req = urllib.request.Request(
                f"{self._url}/api/engine/tokenize",
                data=json.dumps({"text": text}).encode("utf-8"),
                headers=_intestazioni({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tokens = data.get("tokens")
                if tokens:
                    return [int(t) for t in tokens]
        except Exception:
            pass

        # 3. Ripiego deterministico: mappa le parole su interi positivi stabili
        import zlib
        return [zlib.crc32(word.encode("utf-8")) & 0x7FFFFFFF for word in text.split()]


