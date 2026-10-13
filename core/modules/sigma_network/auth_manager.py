"""Ailo Network — Gestione Autenticazione Utente & Custodia Wallet Crittografico.

Implementa:
- Creazione account utente con derivazione Ed25519 deterministica
- Generazione e ripristino tramite Mnemonic Seed Phrase (12 parole)
- Cifratura delle chiavi private a riposo con PBKDF2-HMAC-SHA256 e AES-256-GCM
- Gestione sessioni e token di autorizzazione crittografici
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519

from core.logger import get_logger

log = get_logger(__name__)

# Wordlist ridotta standard BIP-39 (256 parole canoniche per generazione seed 12 parole)
_BIP39_SAMPLE_WORDS = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
    "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
    "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
    "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album",
    "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone",
    "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among",
    "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle", "angry",
    "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique",
    "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april",
    "arch", "arctic", "area", "arena", "argue", "arm", "armed", "armor",
    "army", "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact",
    "artist", "artwork", "ask", "aspect", "assault", "asset", "assist", "assume",
    "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction",
    "audit", "august", "aunt", "author", "auto", "autumn", "average", "avocado",
    "avoid", "awake", "aware", "away", "awesome", "awful", "awkward", "axis",
    "baby", "bachelor", "bacon", "badge", "bag", "balance", "balcony", "ball",
    "bamboo", "banana", "banner", "bar", "barely", "bargain", "barrel", "base",
    "basic", "basket", "battle", "beach", "bean", "beauty", "because", "become",
    "beef", "before", "begin", "behave", "behind", "believe", "below", "belt",
    "bench", "benefit", "best", "betray", "better", "between", "beyond", "bicycle",
    "bid", "bike", "bind", "biology", "bird", "birth", "bitter", "black",
    "blade", "blame", "blanket", "blast", "bleak", "bless", "blind", "blood",
    "blossom", "blouse", "blue", "blur", "blush", "board", "boat", "body",
    "boil", "bomb", "bone", "bonus", "book", "boost", "border", "boring",
    "borrow", "boss", "bottom", "bounce", "box", "boy", "bracket", "brain",
    "brand", "brass", "brave", "bread", "breeze", "brick", "bridge", "brief",
    "bright", "bring", "brisk", "broccoli", "broken", "bronze", "broom", "brother"
]


def generate_mnemonic(words_count: int = 12) -> str:
    """Genera una sequenza mnemonica casuale di 12 parole."""
    chosen = [secrets.choice(_BIP39_SAMPLE_WORDS) for _ in range(words_count)]
    return " ".join(chosen)


def seed_from_mnemonic(mnemonic: str, passphrase: str = "") -> bytes:
    """Deriva una chiave seed deterministica di 32 byte dalla frase mnemonica."""
    normalized = " ".join(mnemonic.strip().lower().split())
    salt = ("ailo_network_mnemonic" + passphrase).encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(normalized.encode("utf-8"))


def derive_ed25519_keypair(seed_bytes: bytes) -> Tuple[bytes, bytes, str, str]:
    """Deriva la coppia di chiavi Ed25519 e l'indirizzo publico/peer_id."""
    priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)
    pub_key = priv_key.public_key()

    priv_raw = priv_key.private_bytes_raw()
    pub_raw = pub_key.public_bytes_raw()

    peer_id = hashlib.sha256(pub_raw).hexdigest()[:32]
    pub_b64 = base64.b64encode(pub_raw).decode("ascii")
    priv_b64 = base64.b64encode(priv_raw).decode("ascii")

    return priv_raw, pub_raw, peer_id, pub_b64


def encrypt_private_key(private_key_bytes: bytes, password: str) -> Dict[str, str]:
    """Cifra la chiave privata a riposo usando AES-256-GCM con PBKDF2."""
    salt = secrets.token_bytes(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=120000,
    )
    derived_key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(derived_key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, private_key_bytes, None)

    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_private_key(enc_dict: Dict[str, str], password: str) -> bytes:
    """Decifra la chiave privata cifrata."""
    salt = base64.b64decode(enc_dict["salt"])
    nonce = base64.b64decode(enc_dict["nonce"])
    ciphertext = base64.b64decode(enc_dict["ciphertext"])

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=120000,
    )
    derived_key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(derived_key)
    return aesgcm.decrypt(nonce, ciphertext, None)


class AuthManager:
    """Gestore degli account utente e delle sessioni del wallet locale."""

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self._path = Path(storage_path or Path.home() / ".sigma_studio" / "network_accounts.json")
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._accounts = data.get("accounts", {})
            except Exception as e:
                log.warning("Impossibile caricare accounts.json: %s", e)
                self._accounts = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"accounts": self._accounts}
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register_user(self, username: str, password: str) -> Dict[str, Any]:
        """Crea un nuovo account con Mnemonic Seed Phrase a 12 parole e wallet Ed25519."""
        username = username.strip()
        if not username:
            raise ValueError("Username obbligatorio")
        if len(password) < 6:
            raise ValueError("La password deve contenere almeno 6 caratteri")

        with self._lock:
            if username in self._accounts:
                raise ValueError(f"L'utente '{username}' esiste già")

            mnemonic = generate_mnemonic(12)
            seed = seed_from_mnemonic(mnemonic, passphrase="")
            priv_raw, pub_raw, peer_id, pub_b64 = derive_ed25519_keypair(seed)

            enc_key = encrypt_private_key(priv_raw, password)

            account_data = {
                "username": username,
                "peer_id": peer_id,
                "public_key": pub_b64,
                "encrypted_key": enc_key,
                "created_at": time.time(),
            }
            self._accounts[username] = account_data
            self._save()

            # Crea sessione automatica
            session_token = self._create_session(account_data, priv_raw)

            return {
                "status": "success",
                "username": username,
                "peer_id": peer_id,
                "public_key": pub_b64,
                "mnemonic_seed": mnemonic,  # Mostrata una sola volta all'utente per backup
                "session_token": session_token,
            }

    def import_wallet(self, username: str, password: str, mnemonic_or_privkey: str) -> Dict[str, Any]:
        """Ripristina un account tramite 12 parole seed o chiave privata in base64."""
        username = username.strip()
        if not username:
            raise ValueError("Username obbligatorio")
        if len(password) < 6:
            raise ValueError("La password deve contenere almeno 6 caratteri")

        text = mnemonic_or_privkey.strip()
        words = text.split()

        if len(words) == 12:
            seed = seed_from_mnemonic(text)
            priv_raw, pub_raw, peer_id, pub_b64 = derive_ed25519_keypair(seed)
        else:
            try:
                priv_raw = base64.b64decode(text)
                if len(priv_raw) != 32:
                    raise ValueError("Lunghezza chiave non valida")
                priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_raw)
                pub_raw = priv_key.public_key().public_bytes_raw()
                peer_id = hashlib.sha256(pub_raw).hexdigest()[:32]
                pub_b64 = base64.b64encode(pub_raw).decode("ascii")
            except Exception:
                raise ValueError("Formato seed phrase o chiave privata non valido")

        with self._lock:
            enc_key = encrypt_private_key(priv_raw, password)
            account_data = {
                "username": username,
                "peer_id": peer_id,
                "public_key": pub_b64,
                "encrypted_key": enc_key,
                "created_at": time.time(),
            }
            self._accounts[username] = account_data
            self._save()

            session_token = self._create_session(account_data, priv_raw)
            return {
                "status": "success",
                "username": username,
                "peer_id": peer_id,
                "public_key": pub_b64,
                "session_token": session_token,
            }

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Autentica l'utente decifrando la chiave privata Ed25519."""
        username = username.strip()
        with self._lock:
            account = self._accounts.get(username)
            if not account:
                raise ValueError("Credenziali non valide o utente inesistente")

            try:
                priv_raw = decrypt_private_key(account["encrypted_key"], password)
            except Exception:
                raise ValueError("Password errata: impossibile decifrare il wallet")

            session_token = self._create_session(account, priv_raw)
            return {
                "status": "success",
                "username": username,
                "peer_id": account["peer_id"],
                "public_key": account["public_key"],
                "session_token": session_token,
            }

    def _create_session(self, account: Dict[str, Any], priv_raw: bytes) -> str:
        token = secrets.token_hex(24)
        self._sessions[token] = {
            "username": account["username"],
            "peer_id": account["peer_id"],
            "public_key": account["public_key"],
            "private_key_b64": base64.b64encode(priv_raw).decode("ascii"),
            "created_at": time.time(),
        }
        return token

    def get_session(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self._lock:
            sess = self._sessions.get(token)
            if not sess:
                return None
            return dict(sess)

    def logout(self, token: Optional[str]) -> bool:
        if not token:
            return False
        with self._lock:
            if token in self._sessions:
                del self._sessions[token]
                return True
            return False

    def list_local_accounts(self) -> List[Dict[str, str]]:
        with self._lock:
            return [
                {
                    "username": acc["username"],
                    "peer_id": acc["peer_id"],
                    "public_key": acc["public_key"],
                }
                for acc in self._accounts.values()
            ]
