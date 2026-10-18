"""Hub AiLo nativo: l'infrastruttura della rete AiLo dentro Sigma Studio.

Il coordinatore AiLo originale (ailo-network, Node.js) e' stato dismesso. Questo
modulo ne prende il posto: una qualsiasi istanza di Sigma Studio puo' fare da
hub e le altre vi si collegano con ``ailo_bridge`` esattamente come facevano col
vecchio server, perche' le route esposte sotto ``/api/sigma_network/ailo_hub``
riproducono le sue API (``/api/status``, ``/api/v1/rpc``, ``/api/login``,
``/api/transfer``, ``/api/inference/gpu``, ``/ws/gpu-inference``...).

Due parti:

- ``AiloLedger``: registro AiloCoin (ALC) su SQLite, con lo stesso schema
  ``users``/``transactions`` del vecchio server e lo stesso formato di hash
  scrypt delle password, cosi' un ``ailo.db`` esistente si importa senza
  chiedere a nessuno di reimpostare la password. Le regole sono quelle
  corrette in ailo-network: importi positivi, niente trasferimenti verso se
  stessi, commissione minima imposta dal server, ricompense con tetto orario.
- ``AiloNodeHub``: i nodi GPU collegati via WebSocket e l'instradamento delle
  richieste di inferenza verso il nodo libero usato meno di recente.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TOKEN_SCHEMA: Dict[str, Any] = {
    "name": "AiloCoin",
    "symbol": "ALC",
    "decimals": 8,
    "type": "Utility Token",
    "standard": "AiloNetwork-v1",
    "features": ["mining", "transfer", "inference"],
    "maxSupply": None,
    "network": "Sigma Network",
}

#: Ricompensa per richiesta servita, come nel coordinatore originale.
INFERENCE_REWARD = 0.05
#: Tetto di ricompense per wallet: chi interroga se stesso guadagna al massimo 1 ALC/ora.
REWARD_MAX_PER_HOUR = 20
#: Commissione minima su /api/ledger/transfer (bruciata, come nell'originale).
MIN_LEDGER_FEE = 0.01
#: Un nodo che tace da piu' di cosi' non riceve richieste.
NODE_STALE_SECONDS = 60.0
INFERENCE_TIMEOUT_SECONDS = 60.0

_SCRYPT = {"n": 16384, "r": 8, "p": 1, "dklen": 64, "maxmem": 64 * 1024 * 1024}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    wallet TEXT UNIQUE NOT NULL,
    balance REAL DEFAULT 0,
    contributions INTEGER DEFAULT 0,
    last_seen INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    from_wallet TEXT,
    to_wallet TEXT,
    amount REAL,
    timestamp INTEGER,
    metadata TEXT,
    status TEXT DEFAULT 'CONFIRMED',
    hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_wallet);
CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_wallet);
"""


class LedgerError(ValueError):
    """Operazione rifiutata dal registro; ``status`` e' il codice HTTP da restituire."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def hash_password(password: str) -> str:
    """Stesso formato del coordinatore Node: ``salt_hex:scrypt_hex`` (salt usato come stringa)."""
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), **_SCRYPT).hex()
    return f"{salt}:{digest}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored or not isinstance(password, str) or ":" not in stored:
        return False
    salt, expected = stored.split(":", 1)
    try:
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), **_SCRYPT).hex()
    except ValueError:
        return False
    return hmac.compare_digest(digest, expected)


def _new_wallet() -> str:
    return "0x" + secrets.token_hex(20)


def _tx_hash(tx_id: int, kind: str, frm: Optional[str], to: Optional[str], amount: float, ts: int) -> str:
    payload = json.dumps([tx_id, kind, frm, to, round(float(amount), 8), ts], separators=(",", ":"))
    return "0x" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _public_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {"email": row["email"], "wallet": row["wallet"],
            "balance": round(float(row["balance"] or 0), 8), "contributions": row["contributions"] or 0}


class AiloLedger:
    """Registro AiloCoin persistente. Ogni scrittura e' una transazione SQLite."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        self._reward_log: Dict[str, List[float]] = {}

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------ interni

    def _user_by_email(self, email: str) -> Optional[sqlite3.Row]:
        return self._db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    def _user_by_wallet(self, wallet: str) -> Optional[sqlite3.Row]:
        return self._db.execute("SELECT * FROM users WHERE wallet = ?", (wallet,)).fetchone()

    def _insert_tx(self, kind: str, frm: Optional[str], to: Optional[str], amount: float,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        ts = int(time.time() * 1000)
        cur = self._db.execute(
            "INSERT INTO transactions (type, from_wallet, to_wallet, amount, timestamp, metadata, status)"
            " VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED')",
            (kind, frm, to, float(amount), ts, json.dumps(metadata or {})),
        )
        tx_hash = _tx_hash(cur.lastrowid, kind, frm, to, amount, ts)
        self._db.execute("UPDATE transactions SET hash = ? WHERE id = ?", (tx_hash, cur.lastrowid))
        return tx_hash

    @staticmethod
    def _amount(value: Any) -> float:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            raise LedgerError("Invalid amount") from None
        if not (amount > 0) or amount == float("inf"):
            raise LedgerError("Invalid amount")
        return round(amount, 8)

    # ------------------------------------------------------------ account

    def register(self, email: str, password: str) -> Dict[str, Any]:
        email = (email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise LedgerError("Invalid email")
        if not isinstance(password, str) or len(password) < 8:
            raise LedgerError("Password must be at least 8 characters")
        with self._lock:
            if self._user_by_email(email):
                raise LedgerError("User already exists", 409)
            now = int(time.time() * 1000)
            self._db.execute(
                "INSERT INTO users (email, password, wallet, balance, contributions, last_seen, created_at)"
                " VALUES (?, ?, ?, 0, 0, ?, ?)",
                (email, hash_password(password), _new_wallet(), now, now),
            )
            return _public_user(self._user_by_email(email))

    def login(self, email: str, password: str) -> Dict[str, Any]:
        email = (email or "").strip().lower()
        with self._lock:
            row = self._user_by_email(email)
            if row is None:
                raise LedgerError("User not found", 404)
            if not verify_password(password, row["password"]):
                raise LedgerError("Invalid credentials", 401)
            self._db.execute("UPDATE users SET last_seen = ? WHERE email = ?", (int(time.time() * 1000), email))
            return _public_user(row)

    def balance(self, wallet: str) -> Dict[str, Any]:
        with self._lock:
            row = self._user_by_wallet(wallet)
        bal = round(float(row["balance"] or 0), 8) if row else 0.0
        # Il registro dell'hub e' definitivo: niente fondi "in attesa di conferme".
        return {"wallet": wallet, "balance": bal, "confirmedBalance": bal, "pendingBalance": 0,
                "contributions": (row["contributions"] or 0) if row else 0}

    # ------------------------------------------------------------ movimenti

    def transfer(self, sender_key: str, to_wallet: str, amount: Any, password: str,
                 fee: Any = 0.0, note: str = "") -> Dict[str, Any]:
        """Sposta ALC; ``sender_key`` e' email o wallet. Tutto o niente."""
        value = self._amount(amount)
        try:
            fee_value = max(float(fee or 0), 0.0)
        except (TypeError, ValueError):
            fee_value = 0.0
        with self._lock:
            sender = self._user_by_email((sender_key or "").strip().lower()) or self._user_by_wallet(sender_key or "")
            if sender is None:
                raise LedgerError("Sender not found", 404)
            if not verify_password(password, sender["password"]):
                raise LedgerError("Auth failed", 401)
            recipient = self._user_by_wallet(to_wallet or "") or self._user_by_email((to_wallet or "").strip().lower())
            if recipient is None:
                raise LedgerError("Recipient wallet not found", 404)
            if recipient["email"] == sender["email"]:
                raise LedgerError("Cannot transfer to your own wallet")
            total = round(value + fee_value, 8)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                # Il controllo del saldo sta nella stessa UPDATE: due invii
                # concorrenti non possono spendere la stessa moneta.
                cur = self._db.execute(
                    "UPDATE users SET balance = balance - ?, last_seen = ? WHERE email = ? AND balance >= ?",
                    (total, int(time.time() * 1000), sender["email"], total - 1e-9),
                )
                if cur.rowcount != 1:
                    raise LedgerError("Insufficient funds")
                self._db.execute("UPDATE users SET balance = balance + ? WHERE email = ?", (value, recipient["email"]))
                tx_hash = self._insert_tx("TRANSFER", sender["wallet"], recipient["wallet"], value,
                                          {"fee": fee_value, "note": str(note)[:200]})
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            new_balance = round(float(self._user_by_email(sender["email"])["balance"]), 8)
        return {"success": True, "hash": tx_hash, "from": sender["wallet"], "to": recipient["wallet"],
                "amount": value, "fee": fee_value, "newBalance": new_balance}

    def reward(self, wallet: str, amount: float = INFERENCE_REWARD, reason: str = "INFERENCE_REWARD",
               metadata: Optional[Dict[str, Any]] = None) -> Optional[float]:
        """Conia una ricompensa dalla rete. ``None`` se il wallet non esiste o ha raggiunto il tetto."""
        now = time.time()
        with self._lock:
            row = self._user_by_wallet(wallet)
            if row is None:
                return None
            recent = [t for t in self._reward_log.get(wallet, []) if now - t < 3600]
            if len(recent) >= REWARD_MAX_PER_HOUR:
                self._reward_log[wallet] = recent
                return None
            recent.append(now)
            self._reward_log[wallet] = recent
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("UPDATE users SET balance = balance + ?, contributions = contributions + 1"
                                 " WHERE wallet = ?", (amount, wallet))
                self._insert_tx(reason, "NETWORK", wallet, amount, metadata)
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            return round(float(self._user_by_wallet(wallet)["balance"]), 8)

    # ------------------------------------------------------------ lettura

    @staticmethod
    def _tx_out(row: sqlite3.Row) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}
        try:
            meta = json.loads(row["metadata"] or "{}")
        except (TypeError, ValueError):
            pass
        return {"id": row["id"], "hash": row["hash"], "type": row["type"], "from": row["from_wallet"],
                "to": row["to_wallet"], "amount": row["amount"], "timestamp": row["timestamp"],
                "status": row["status"], "metadata": meta}

    def transactions(self, wallet: str, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM transactions WHERE from_wallet = ? OR to_wallet = ? ORDER BY id DESC LIMIT ?",
                (wallet, wallet, limit)).fetchall()
        return [self._tx_out(r) for r in reversed(rows)]

    def transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._db.execute("SELECT * FROM transactions WHERE hash = ?", (tx_hash,)).fetchone()
        return self._tx_out(row) if row else None

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            count = self._db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            supply = self._db.execute("SELECT COALESCE(SUM(balance), 0) FROM users").fetchone()[0]
            users = self._db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            last = self._db.execute("SELECT MAX(timestamp) FROM transactions").fetchone()[0]
        return {"blockNumber": count, "totalSupply": round(float(supply), 8),
                "activeAddresses": users, "latestTimestamp": last}

    # ------------------------------------------------------------ migrazione

    def import_ailo_db(self, path: str | os.PathLike[str]) -> Dict[str, int]:
        """Importa account, saldi e storico da un ``ailo.db`` del vecchio coordinatore.

        Gli account gia' presenti (stessa email o stesso wallet) non vengono
        toccati: rieseguire l'import non raddoppia i saldi.
        """
        source = Path(path)
        if not source.is_file():
            raise LedgerError(f"File non trovato: {source}", 404)
        src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "users" not in tables:
                raise LedgerError("Il file non e' un database AiLo (manca la tabella users)")
            users = src.execute("SELECT * FROM users").fetchall()
            txs = src.execute("SELECT * FROM transactions ORDER BY id").fetchall() if "transactions" in tables else []
        finally:
            src.close()

        imported_users = 0
        imported_wallets = set()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                for u in users:
                    if self._user_by_email(u["email"]) or self._user_by_wallet(u["wallet"]):
                        continue
                    self._db.execute(
                        "INSERT INTO users (email, password, wallet, balance, contributions, last_seen, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (u["email"], u["password"], u["wallet"], float(u["balance"] or 0),
                         u["contributions"] or 0, u["last_seen"], u["created_at"]),
                    )
                    imported_users += 1
                    imported_wallets.add(u["wallet"])
                imported_txs = 0
                for t in txs:
                    # Solo lo storico che riguarda account appena importati.
                    if t["from_wallet"] not in imported_wallets and t["to_wallet"] not in imported_wallets:
                        continue
                    meta = dict(json.loads(t["metadata"] or "{}")) if t["metadata"] else {}
                    meta["imported_from"] = "ailo-network"
                    cur = self._db.execute(
                        "INSERT INTO transactions (type, from_wallet, to_wallet, amount, timestamp, metadata, status)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (t["type"], t["from_wallet"], t["to_wallet"], t["amount"], t["timestamp"],
                         json.dumps(meta), t["status"] or "CONFIRMED"),
                    )
                    self._db.execute("UPDATE transactions SET hash = ? WHERE id = ?", (
                        _tx_hash(cur.lastrowid, t["type"], t["from_wallet"], t["to_wallet"],
                                 t["amount"] or 0, t["timestamp"] or 0), cur.lastrowid))
                    imported_txs += 1
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        logger.info("Import AiLo: %d account, %d transazioni", imported_users, imported_txs)
        return {"users": imported_users, "transactions": imported_txs, "skipped_users": len(users) - imported_users}


class AiloNodeHub:
    """Nodi di inferenza collegati via WebSocket e instradamento delle richieste.

    Vive nell'event loop del server ASGI: ``dispatch`` va atteso da una route
    ``async``, nello stesso loop dei WebSocket dei nodi.
    """

    def __init__(self, ledger: AiloLedger) -> None:
        self._ledger = ledger
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, asyncio.Future] = {}

    # ------------------------------------------------------------ nodi

    def connect(self, ws: Any) -> str:
        node_id = f"gpu_inf_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        self._nodes[node_id] = {"ws": ws, "wallet": None, "email": None, "gpu": None, "vram": 0,
                                "last_seen": time.time(), "busy": False, "last_used": 0.0, "inferences": 0}
        return node_id

    def disconnect(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)

    def nodes(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [{"nodeId": nid, "wallet": n["wallet"], "gpu": n["gpu"], "busy": n["busy"],
                 "inferences": n["inferences"], "lastSeen": round(now - n["last_seen"], 1)}
                for nid, n in self._nodes.items() if n["wallet"]]

    async def handle_message(self, node_id: str, raw: str) -> None:
        node = self._nodes.get(node_id)
        if node is None:
            return
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            return
        node["last_seen"] = time.time()
        kind = msg.get("type")
        if kind == "register_inference":
            wallet = str(msg.get("wallet") or "")
            node.update(wallet=wallet or None, email=msg.get("email"), gpu=msg.get("gpu"), vram=msg.get("vram") or 0)
            await node["ws"].send_text(json.dumps({"type": "registered", "nodeId": node_id,
                                                   "message": "Ready to receive inference requests"}))
            logger.info("Nodo AiLo registrato %s (%s)", node_id, (wallet or "?")[:12])
        elif kind == "inference_response":
            future = self._pending.pop(str(msg.get("request_id") or ""), None)
            if future is not None and not future.done() and future.node_id == node_id:  # type: ignore[attr-defined]
                future.set_result({"response": msg.get("response", ""), "tokens_generated": msg.get("tokens_generated", 0),
                                   "model_epoch": msg.get("model_epoch", 0), "processed_by": node["wallet"]})
                node["inferences"] += 1
        elif kind == "inference_error":
            future = self._pending.pop(str(msg.get("request_id") or ""), None)
            if future is not None and not future.done() and future.node_id == node_id:  # type: ignore[attr-defined]
                future.set_exception(RuntimeError(str(msg.get("error") or "inference error")))
        elif kind == "ping":
            await node["ws"].send_text(json.dumps({"type": "pong"}))

    # ------------------------------------------------------------ inferenza

    def _pick(self) -> Optional[str]:
        now = time.time()
        idle = [(n["last_used"], nid) for nid, n in self._nodes.items()
                if n["wallet"] and not n["busy"] and now - n["last_seen"] < NODE_STALE_SECONDS]
        return min(idle)[1] if idle else None

    async def dispatch(self, prompt: str, max_tokens: int, temperature: float,
                       timeout: float = INFERENCE_TIMEOUT_SECONDS) -> Dict[str, Any]:
        node_id = self._pick()
        if node_id is None:
            return {"success": False, "error": "No GPU inference nodes available", "fallback": True,
                    "response": "[No GPU nodes connected] Connect a GPU node to enable AI chat.",
                    "gpuNodesCount": len(self._nodes)}
        node = self._nodes[node_id]
        request_id = f"inf_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        future = asyncio.get_running_loop().create_future()
        future.node_id = node_id  # type: ignore[attr-defined]  # solo quel nodo puo' rispondere
        self._pending[request_id] = future
        node["busy"] = True
        try:
            await node["ws"].send_text(json.dumps({"type": "inference_request", "request_id": request_id,
                                                   "prompt": prompt, "max_tokens": int(max_tokens),
                                                   "temperature": float(temperature)}))
            result = await asyncio.wait_for(future, timeout)
        except Exception as exc:  # noqa: BLE001 - l'errore torna al chiamante come risposta
            self._pending.pop(request_id, None)
            return {"success": False, "error": str(exc) or type(exc).__name__, "fallback": True,
                    "response": f"[GPU Error: {exc}] Inference failed."}
        finally:
            node["busy"] = False
            node["last_used"] = time.time()

        reward = None
        if result.get("processed_by"):
            reward = self._ledger.reward(result["processed_by"], INFERENCE_REWARD, "INFERENCE_REWARD",
                                         {"request_id": request_id, "tokens": result.get("tokens_generated", 0)})
        wallet = result.get("processed_by") or ""
        return {"success": True, "prompt": prompt, "response": result["response"],
                "tokens_generated": result["tokens_generated"], "processed_by": wallet[:12] + "...",
                "model_epoch": result["model_epoch"], "gpu_accelerated": True,
                "reward": INFERENCE_REWARD if reward is not None else 0}
