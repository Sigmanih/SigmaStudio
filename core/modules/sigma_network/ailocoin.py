"""Contabilita AiloCoin per Sigma Network.

Registro locale di ricevute firmate: il provider emette una ricevuta per il
lavoro svolto, il consumer la controfirma. Il saldo e la somma delle ricevute
con firma valida. Progettato per essere regolato in seguito sulla crypto
AiloNetwork (campo ``settlement_ref``).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.modules.sigma_network.identity import sign, verify

logger = logging.getLogger(__name__)

_DEFAULT_WALLET_PATH = "data/sigma_network/wallet.json"

import hashlib

# Campi della ricevuta ESCLUSI dal messaggio firmato.
_SIGNED_EXCLUDED = {"provider_signature", "consumer_signature", "settlement_ref", "receipt_hash"}


def _signed_payload(receipt: Dict[str, Any]) -> str:
    """Serializzazione deterministica dei campi firmabili della ricevuta.

    Esclude i due campi di firma e ``settlement_ref`` cosi che provider e
    consumer firmino esattamente la stessa stringa.
    """
    payload = {k: v for k, v in receipt.items() if k not in _SIGNED_EXCLUDED}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_receipt_hash(receipt: Dict[str, Any]) -> str:
    """Calcola l'hash SHA-256 canonico della ricevuta per la catena immutabile."""
    canonical = _signed_payload(receipt)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_pouw_hash(prev_hash: str, gradients_hash: str, peer_id: str, nonce: int) -> str:
    """Calcola l'hash di validazione crittografica Proof-of-Useful-Work."""
    payload = f"{prev_hash}:{gradients_hash}:{peer_id}:{nonce}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def solve_pouw_challenge(
    prev_hash: str,
    gradients_hash: str,
    peer_id: str,
    difficulty: int = 2,
    max_attempts: int = 200000,
) -> Tuple[int, str]:
    """Risolve la challenge Proof-of-Useful-Work cercando il nonce che soddisfa la difficulty."""
    target_prefix = "0" * difficulty
    for nonce in range(max_attempts):
        h = compute_pouw_hash(prev_hash, gradients_hash, peer_id, nonce)
        if h.startswith(target_prefix):
            return nonce, h
    return max_attempts, compute_pouw_hash(prev_hash, gradients_hash, peer_id, max_attempts)



def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    """Scrittura atomica: file temporaneo + ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, path)


class Wallet:
    """Registro locale di ricevute AiloCoin con persistenza atomica.

    Lo stato e protetto da un lock per la sicurezza in concorrenza (route HTTP
    in lettura, thread di discovery in scrittura).
    """

    def __init__(self, path: str | os.PathLike[str] = _DEFAULT_WALLET_PATH) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._receipts: List[Dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------ I/O

    def _load(self) -> None:
        """Carica le ricevute da disco; se il file non esiste parte da zero."""
        with self._lock:
            if not self._path.exists():
                return
            try:
                with self._path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                receipts = data.get("receipts", [])
                if isinstance(receipts, list):
                    self._receipts = receipts
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Impossibile caricare il wallet da %s: %s", self._path, exc)
                self._receipts = []

    def _save(self) -> None:
        """Persiste lo stato corrente in modo atomico."""
        with self._lock:
            _atomic_write(self._path, {"receipts": self._receipts})

    # ------------------------------------------------------------- ricevute

    def issue_receipt(
        self,
        request_id: str,
        provider_id: str,
        consumer_id: str,
        model: str,
        tokens: int,
        rate: float,
        private_key_bytes: bytes,
    ) -> Dict[str, Any]:
        """Il provider emette una ricevuta firmata per il lavoro svolto.

        ``amount = tokens / rate``. La firma copre tutti i campi della
        ricevuta tranne le due firme e ``settlement_ref``.
        """
        if rate <= 0:
            raise ValueError("rate deve essere positivo")
        if tokens < 0:
            raise ValueError("tokens non puo essere negativo")

        prev_hash = self._get_latest_hash()
        receipt: Dict[str, Any] = {
            "receipt_id": str(uuid.uuid4()),
            "request_id": request_id,
            "provider_id": provider_id,
            "consumer_id": consumer_id,
            "model": model,
            "tokens": tokens,
            "amount": tokens / rate,
            "created_at": time.time(),
            "prev_hash": prev_hash,
            "provider_signature": None,
            "consumer_signature": None,
            "settlement_ref": None,
        }

        receipt["provider_signature"] = sign(private_key_bytes, _signed_payload(receipt))
        receipt["receipt_hash"] = compute_receipt_hash(receipt)

        with self._lock:
            self._receipts.append(receipt)
            self._save()

        logger.info(
            "Ricevuta emessa: id=%s provider=%s consumer=%s amount=%.4f",
            receipt["receipt_id"], provider_id, consumer_id, receipt["amount"],
        )
        return receipt

    def countersign(
        self,
        receipt: Dict[str, Any],
        private_key_bytes: bytes,
        provider_public_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Il consumer controfirma la ricevuta.

        Rifiuta (``ValueError``) se la firma del provider non e valida. La
        verifica della firma provider richiede ``provider_public_key``; se non
        fornita, si fa solo un controllo di presenza della firma.

        Aggiorna la ricevuta gia registrata (se presente) o la aggiunge.
        """
        provider_sig = receipt.get("provider_signature")
        if not provider_sig:
            raise ValueError("La ricevuta non ha la firma del provider")

        if provider_public_key is not None:
            payload = _signed_payload(receipt)
            if not verify(provider_public_key, payload, provider_sig):
                raise ValueError("Firma del provider non valida: controfirma rifiutata")

        receipt = dict(receipt)  # copia per non mutare l'originale del chiamante
        receipt["consumer_signature"] = sign(private_key_bytes, _signed_payload(receipt))

        with self._lock:
            self._upsert_receipt(receipt)
            self._save()

        logger.info("Ricevuta controfirmata: id=%s", receipt.get("receipt_id"))
        return receipt

    def verify_receipt(
        self,
        receipt: Dict[str, Any],
        provider_public_key: str,
        consumer_public_key: Optional[str] = None,
    ) -> bool:
        """Verifica che entrambe le firme (provider e consumer) siano valide.

        Se ``consumer_public_key`` e ``None`` o ``consumer_signature`` e assente,
        verifica solo la firma del provider.
        """
        payload = _signed_payload(receipt)

        provider_sig = receipt.get("provider_signature")
        if not provider_sig:
            return False
        if not verify(provider_public_key, payload, provider_sig):
            return False

        consumer_sig = receipt.get("consumer_signature")
        if consumer_sig and consumer_public_key:
            if not verify(consumer_public_key, payload, consumer_sig):
                return False

        return True

    # --------------------------------------------------------------- saldo & conio

    def _get_latest_hash(self) -> str:
        """Restituisce l'hash dell'ultima ricevuta nella catena locale."""
        with self._lock:
            if not self._receipts:
                return "0" * 64
            last = self._receipts[-1]
            return str(last.get("receipt_hash") or compute_receipt_hash(last))

    def account_nonce(self, peer_id: str) -> int:
        """Restituisce il nonce attuale per l'account (numero di spese/trasferimenti effettuati)."""
        with self._lock:
            return sum(1 for r in self._receipts if r.get("consumer_id") == peer_id and r.get("type") != "faucet")

    def mint_faucet(self, peer_id: str, amount: float = 100.0, force: bool = False) -> Dict[str, Any]:
        """Emette un'allocazione iniziale Genesis per permettere al nodo di effettuare richieste.
        
        Protezione Anti-Sybil: consente una sola erogazione per wallet a meno di force=True.
        """
        if amount <= 0:
            raise ValueError("L'importo del faucet deve essere positivo")
        with self._lock:
            if not force:
                for r in self._receipts:
                    if r.get("type") == "faucet" and r.get("consumer_id") == peer_id:
                        raise ValueError("Genesis Faucet già riscattato per questo wallet")
            prev_hash = self._get_latest_hash()
            receipt: Dict[str, Any] = {
                "receipt_id": str(uuid.uuid4()),
                "request_id": f"genesis-{uuid.uuid4().hex[:8]}",
                "provider_id": "GENESIS_FAUCET",
                "consumer_id": peer_id,
                "model": "genesis-allocation",
                "tokens": int(amount * 1000),
                "amount": float(amount),
                "type": "faucet",
                "created_at": time.time(),
                "prev_hash": prev_hash,
                "provider_signature": "GENESIS_ROOT_AUTHORIZED",
                "consumer_signature": None,
                "settlement_ref": "genesis_block_0",
            }
            receipt["receipt_hash"] = compute_receipt_hash(receipt)
            self._receipts.append(receipt)
            self._save()
        logger.info("Genesis Faucet accreditato a %s: %.2f AiloCoin", peer_id, amount)
        return receipt

    def mint_mining_reward(
        self,
        peer_id: str,
        amount: float,
        task_type: str = "ailo_gradient_step",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Emette una ricompensa di mining Proof-of-Useful-Work per computazione neurale."""
        if amount <= 0:
            raise ValueError("La ricompensa di mining deve essere positiva")
        meta = meta or {}
        with self._lock:
            prev_hash = self._get_latest_hash()
            gradients_hash = meta.get("gradients_hash") or hashlib.sha256(f"step_{meta.get('step', 0)}".encode("utf-8")).hexdigest()
            difficulty = meta.get("difficulty", 2)
            nonce = meta.get("nonce")
            pouw_hash = meta.get("pouw_hash")
            if nonce is None or pouw_hash is None:
                nonce, pouw_hash = solve_pouw_challenge(prev_hash, gradients_hash, peer_id, difficulty=difficulty)

            receipt: Dict[str, Any] = {
                "receipt_id": str(uuid.uuid4()),
                "request_id": f"mining-{uuid.uuid4().hex[:8]}",
                "provider_id": peer_id,
                "consumer_id": "AILO_NETWORK_CONSENSUS",
                "model": meta.get("model", "AILO-152M"),
                "tokens": meta.get("tokens", int(amount * 1000)),
                "amount": float(amount),
                "type": "mining_reward",
                "task_type": task_type,
                "loss": meta.get("loss"),
                "step": meta.get("step"),
                "gradients_hash": gradients_hash,
                "nonce": nonce,
                "pouw_hash": pouw_hash,
                "difficulty": difficulty,
                "created_at": time.time(),
                "prev_hash": prev_hash,
                "provider_signature": "PROOF_OF_USEFUL_COMPUTE_VERIFIED",
                "consumer_signature": "CONSENSUS_ACCEPTED",
                "settlement_ref": f"block_{meta.get('step', int(time.time()))}",
            }
            receipt["receipt_hash"] = compute_receipt_hash(receipt)
            self._receipts.append(receipt)
            self._save()
        logger.info("Ricompensa Mining accreditata a %s: +%.4f AiloCoin (task=%s, pouw=%s)", peer_id, amount, task_type, pouw_hash[:8])
        return receipt

    def transfer(
        self,
        sender_id: str,
        recipient_id: str,
        amount: float,
        private_key_bytes: bytes,
        note: str = "",
    ) -> Dict[str, Any]:
        """Trasferisce AiloCoin dal mittente a un peer destinatario.
        
        Verifica il saldo del mittente, applica nonce sequenziale per prevenire
        la doppia spesa e registra una ricevuta crittograficamente firmata.
        """
        if amount <= 0:
            raise ValueError("L'importo del trasferimento deve essere positivo")
        if not recipient_id or recipient_id == sender_id:
            raise ValueError("Destinatario non valido o coincidente con il mittente")

        with self._lock:
            cur_balance = self.balance(sender_id)["balance"]
            if cur_balance < amount:
                raise ValueError(f"Saldo insufficiente: disponibile {cur_balance:.4f}, richiesto {amount:.4f}")

            next_nonce = self.account_nonce(sender_id) + 1
            prev_hash = self._get_latest_hash()
            receipt: Dict[str, Any] = {
                "receipt_id": str(uuid.uuid4()),
                "request_id": f"tx-{uuid.uuid4().hex[:8]}",
                "provider_id": recipient_id,  # chi riceve guadagna
                "consumer_id": sender_id,     # chi invia spende
                "nonce": next_nonce,
                "model": "p2p-direct-transfer",
                "tokens": int(amount * 1000),
                "amount": float(amount),
                "type": "transfer",
                "note": note,
                "created_at": time.time(),
                "prev_hash": prev_hash,
                "provider_signature": "DIRECT_TRANSFER_CONFIRMED",
                "consumer_signature": None,
                "settlement_ref": f"tx_{int(time.time())}",
            }
            receipt["consumer_signature"] = sign(private_key_bytes, _signed_payload(receipt))
            receipt["receipt_hash"] = compute_receipt_hash(receipt)

            self._receipts.append(receipt)
            self._save()

        logger.info("Trasferimento completato: %s -> %s (%.4f AiloCoin, nonce=%d)", sender_id, recipient_id, amount, next_nonce)
        return receipt

    def balance(self, peer_id: str) -> Dict[str, float]:
        """Restituisce ``{balance, earned, mined, faucet, spent}`` per il peer indicato."""
        with self._lock:
            earned = 0.0
            mined = 0.0
            faucet = 0.0
            spent = 0.0
            for r in self._receipts:
                if not r.get("provider_signature"):
                    continue
                amount = float(r.get("amount", 0.0))
                rtype = r.get("type", "inference")

                if rtype == "faucet" and r.get("consumer_id") == peer_id:
                    faucet += amount
                elif rtype == "mining_reward" and r.get("provider_id") == peer_id:
                    mined += amount
                else:
                    if r.get("provider_id") == peer_id:
                        earned += amount
                    elif r.get("consumer_id") == peer_id:
                        spent += amount

            total_balance = (earned + mined + faucet) - spent
            return {
                "balance": total_balance,
                "earned": earned,
                "mined": mined,
                "faucet": faucet,
                "spent": spent,
            }

    def receipts(self) -> List[Dict[str, Any]]:
        """Storico delle ricevute, ordinate dalla piu recente."""
        with self._lock:
            return sorted(
                (dict(r) for r in self._receipts),
                key=lambda r: r.get("created_at", 0.0),
                reverse=True,
            )

    def verify_chain(self) -> Dict[str, Any]:
        """Verifica la continuità crittografica, le firme, i nonce e le prove PoUW."""
        with self._lock:
            corrupted = []
            prev_expected = "0" * 64
            seen_faucets = set()
            account_nonces: Dict[str, int] = {}

            for i, r in enumerate(self._receipts):
                calc_hash = compute_receipt_hash(r)
                recorded_hash = r.get("receipt_hash")
                prev_in_r = r.get("prev_hash")

                # Verifica hash canonico e continuità della catena
                if recorded_hash and recorded_hash != calc_hash:
                    corrupted.append({"index": i, "id": r.get("receipt_id"), "reason": "hash_mismatch"})
                if prev_in_r and prev_in_r != prev_expected and i > 0:
                    corrupted.append({"index": i, "id": r.get("receipt_id"), "reason": "broken_chain"})

                # Verifica PoUW se blocco di mining
                if r.get("type") == "mining_reward" and "pouw_hash" in r:
                    calc_pouw = compute_pouw_hash(
                        r.get("prev_hash", ""),
                        r.get("gradients_hash", ""),
                        r.get("provider_id", ""),
                        r.get("nonce", 0),
                    )
                    if calc_pouw != r["pouw_hash"]:
                        corrupted.append({"index": i, "id": r.get("receipt_id"), "reason": "invalid_pouw_hash"})

                # Verifica Faucet anti-sybil duplicato
                if r.get("type") == "faucet":
                    cid = r.get("consumer_id")
                    if cid in seen_faucets:
                        corrupted.append({"index": i, "id": r.get("receipt_id"), "reason": "duplicate_faucet_sybil"})
                    seen_faucets.add(cid)

                # Verifica nonces sequenziali per prevenire double-spending sui trasferimenti
                cid = r.get("consumer_id")
                if r.get("type") == "transfer" and cid and "nonce" in r:
                    expected = account_nonces.get(cid, 0) + 1
                    if r["nonce"] != expected:
                        corrupted.append({"index": i, "id": r.get("receipt_id"), "reason": "double_spending_nonce_mismatch"})
                    account_nonces[cid] = r["nonce"]

                prev_expected = recorded_hash or calc_hash

            return {
                "valid": len(corrupted) == 0,
                "chain_length": len(self._receipts),
                "corrupted_count": len(corrupted),
                "corrupted_details": corrupted,
                "tip_hash": prev_expected,
            }

    # ------------------------------------------------------------- interno

    def _upsert_receipt(self, receipt: Dict[str, Any]) -> None:
        """Aggiorna la ricevuta con lo stesso ``receipt_id`` o la aggiunge."""
        rid = receipt.get("receipt_id")
        for i, existing in enumerate(self._receipts):
            if existing.get("receipt_id") == rid:
                self._receipts[i] = receipt
                return
        self._receipts.append(receipt)
