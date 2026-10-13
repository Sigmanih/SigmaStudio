"""Identita crittografica del peer per Sigma Network.

Gestisce la generazione, il caricamento e la firma/verifica basati su
chiavi Ed25519 (libreria ``cryptography``).

Contratti:
    - La chiave privata non compare mai nei log ne viene restituita da
      funzioni che espongono l'identita pubblica.
    - ``peer_id`` = hex dei primi 16 byte dello SHA-256 della chiave pubblica.
    - ``sign``/``verify`` operano su stringhe base64 per la portabilita JSON.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

# Chiavi del dizionario identita. La chiave privata e presente SOLO nel file
# su disco; le funzioni pubbliche non la restituiscono mai.
_KEY_PRIVATE = "private_key"
_KEY_PUBLIC = "public_key"
_KEY_PEER_ID = "peer_id"


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value)


def peer_id_from_public_key(public_key_bytes: bytes) -> str:
    """Restituisce l'identita del peer.

    L'identita e il valore esadecimale dei primi 16 byte della digest
    SHA-256 calcolata sulla chiave pubblica in forma seriale (raw).

    Args:
        public_key_bytes: chiave pubblica Ed25519 in forma seriale (32 byte).

    Returns:
        Stringa hex di 32 caratteri (16 byte).
    """
    digest = hashlib.sha256(public_key_bytes).digest()
    return digest[:16].hex()


def _build_identity_dict(private_key: Ed25519PrivateKey) -> Dict[str, str]:
    """Costruisce il dizionario identita completo (con chiave privata).

    Questo dizionario e destinato ESCLUSIVAMENTE alla serializzazione su disco.
    Non va mai loggato ne restituito a chi esige l'identita pubblica.
    """
    public_key: Ed25519PublicKey = private_key.public_key()
    public_raw = public_key.public_bytes_raw()
    return {
        _KEY_PRIVATE: _b64encode(
            private_key.private_bytes_raw()
        ),
        _KEY_PUBLIC: _b64encode(public_raw),
        _KEY_PEER_ID: peer_id_from_public_key(public_raw),
    }


def generate_identity(path: str | os.PathLike[str]) -> Dict[str, str]:
    """Genera una nuova coppia di chiavi Ed25519 e la salva su disco.

    Il file in ``path`` viene (ri)scritto con il dizionario identita in JSON.
    La cartella genitore viene creata se assente.

    Args:
        path: percorso del file JSON dove persistere l'identita.

    Returns:
        Dizionario dell'identita completo (contiene la chiave privata in base64).
        Il chiamante e responsabile di non loggarlo.
    """
    private_key = Ed25519PrivateKey.generate()
    identity = _build_identity_dict(private_key)

    target = Path(path)
    try:
        if target.parent and str(target.parent) not in ("", "."):
            target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(identity, handle, indent=2)
    except OSError as exc:
        # La chiave privata non va mai nei log: si logga solo il percorso.
        logger.error(
            "Impossibile salvare l'identita in %s: %s", target, exc
        )
        raise

    logger.info("Identita generata e salvata in %s (peer_id=%s)", target, identity[_KEY_PEER_ID])
    return identity


def load_identity(path: str | os.PathLike[str]) -> Dict[str, str]:
    """Carica l'identita da disco; se il file non esiste la genera.

    Idempotente: due chiamate consecutive restituiscono lo stesso ``peer_id``.

    Args:
        path: percorso del file JSON dell'identita.

    Returns:
        Dizionario dell'identita completo (contiene la chiave privata in base64).
    """
    target = Path(path)
    if not target.exists():
        logger.info("Identita assente in %s: generazione nuova", target)
        return generate_identity(target)

    try:
        with target.open("r", encoding="utf-8") as handle:
            identity: Dict[str, Any] = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Impossibile leggere l'identita da %s: %s", target, exc)
        raise

    # Validazione minima dei campi obbligatori.
    for field in (_KEY_PRIVATE, _KEY_PUBLIC, _KEY_PEER_ID):
        if field not in identity or not isinstance(identity[field], str):
            logger.error(
                "Identita in %s malformata: campo '%s' mancante o non stringa",
                target,
                field,
            )
            raise ValueError(f"Identita malformata: campo '{field}' assente")

    return identity


def public_identity(identity: Dict[str, str]) -> Dict[str, str]:
    """Restituisce la sola identita pubblica (senza chiave privata).

    Utile per esporre l'identita in messaggi di rete o log senza mai
    rivelare il materiale segreto.

    Args:
        identity: dizionario identita completo.

    Returns:
        Dizionario con ``public_key`` e ``peer_id``.
    """
    return {
        _KEY_PUBLIC: identity[_KEY_PUBLIC],
        _KEY_PEER_ID: identity[_KEY_PEER_ID],
    }


def sign(private_key_bytes: bytes, message: str) -> str:
    """Firma ``message`` con la chiave privata Ed25519.

    Args:
        private_key_bytes: chiave privata in forma seriale (32 byte).
        message: messaggio da firmare (stringa UTF-8).

    Returns:
        Firma in base64.
    """
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except ValueError as exc:
        logger.error("Chiave privata non valida per la firma: %s", exc)
        raise

    signature = private_key.sign(message.encode("utf-8"))
    return _b64encode(signature)


def verify(public_key_b64: str, message: str, signature_b64: str) -> bool:
    """Verifica una firma Ed25519.

    Restituisce ``False`` (e non solleva eccezioni) se la firma e malformata,
    la chiave pubblica e invalida o la verifica fallisce.

    Args:
        public_key_b64: chiave pubblica in base64.
        message: messaggio originario (stringa UTF-8).
        signature_b64: firma da verificare, in base64.

    Returns:
        ``True`` se la firma e valida, altrimenti ``False``.
    """
    try:
        public_raw = _b64decode(public_key_b64)
        signature = _b64decode(signature_b64)
    except (ValueError, TypeError) as exc:
        logger.warning("Firma o chiave pubblica malformata: %s", exc)
        return False

    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_raw)
    except ValueError as exc:
        logger.warning("Chiave pubblica non valida: %s", exc)
        return False

    try:
        public_key.verify(signature, message.encode("utf-8"))
    except InvalidSignature:
        return False
    except Exception as exc:  # noqa: BLE001 - difensivo, mai far cadere il chiamante
        logger.warning("Errore imprevisto durante la verifica firma: %s", exc)
        return False

    return True
