"""Riserva esclusiva delle GPU fra i carichi che le condividono.

Un render video di ore e l'LLM della chat non possono stare sulla stessa
scheda: il modello video occupa quasi tutta la VRAM e un LLM ricaricato a
meta' render (basta aprire la chat) lo manda in out-of-memory. Chi avvia un
carico lungo prende un lease sui device che usa; chi carica un LLM chiede
quali device sono liberi e si sposta su quelli, o sulla CPU se non ne resta
nessuno. Il lease scade da solo se il proprietario smette di rinnovarlo, cosi'
un processo morto non blocca la GPU per sempre.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from core.logger import get_logger

log = get_logger("gpu_lease")

DEFAULT_TTL_S = 15 * 60


@dataclass
class Lease:
    id: str
    owner: str
    devices: tuple
    reason: str = ""
    acquired: float = field(default_factory=time.time)
    expires: float = 0.0

    def to_dict(self) -> dict:
        return {"id": self.id, "owner": self.owner, "devices": list(self.devices), "reason": self.reason,
                "acquired": self.acquired, "expires_in_s": round(max(0.0, self.expires - time.time()))}


class GpuLeases:
    def __init__(self):
        self._leases: dict[str, Lease] = {}
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.time()
        for lid in [lid for lid, l in self._leases.items() if l.expires and l.expires < now]:
            log.warning(f"lease GPU scaduto senza rilascio: {self._leases[lid].owner}")
            del self._leases[lid]

    def acquire(self, owner: str, devices, reason: str = "", ttl_s: float = DEFAULT_TTL_S) -> str:
        devices = tuple(sorted({int(d) for d in devices}))
        with self._lock:
            self._purge()
            for other in self._leases.values():
                clash = set(other.devices) & set(devices)
                if clash and other.owner != owner:
                    raise RuntimeError(f"GPU {sorted(clash)} gia' riservate da {other.owner} ({other.reason})")
            lease = Lease(id=uuid.uuid4().hex[:12], owner=owner, devices=devices, reason=reason,
                          expires=time.time() + ttl_s if ttl_s else 0.0)
            self._leases[lease.id] = lease
        log.info(f"GPU {list(devices)} riservate a {owner}: {reason}")
        return lease.id

    def renew(self, lease_id: str, ttl_s: float = DEFAULT_TTL_S) -> bool:
        with self._lock:
            lease = self._leases.get(lease_id)
            if not lease:
                return False
            lease.expires = time.time() + ttl_s if ttl_s else 0.0
            return True

    def release(self, lease_id: str) -> bool:
        with self._lock:
            lease = self._leases.pop(lease_id, None)
        if lease:
            log.info(f"GPU {list(lease.devices)} rilasciate da {lease.owner}")
        return lease is not None

    def reserved(self) -> set[int]:
        with self._lock:
            self._purge()
            return {d for l in self._leases.values() for d in l.devices}

    def snapshot(self) -> list[dict]:
        with self._lock:
            self._purge()
            return [l.to_dict() for l in self._leases.values()]


leases = GpuLeases()


def apply_to_llama_command(env: dict, command: list, gpu_count: int, reserved: set[int] | None = None) -> str:
    """Sposta un avvio di llama-server fuori dalle GPU riservate.

    Modifica `env` e `command` sul posto e ritorna una descrizione della scelta
    (vuota se non serviva nulla). Gli indici di `-mg` e `-ts` si riferiscono ai
    device visibili, quindi vanno riscritti dopo aver ristretto la visibilita'.
    """
    reserved = leases.reserved() if reserved is None else reserved
    if not reserved:
        return ""
    current = env.get("CUDA_VISIBLE_DEVICES")
    if current not in (None, ""):
        visible = [int(x) for x in current.split(",") if x.strip().lstrip("-").isdigit() and int(x) >= 0]
    else:
        visible = list(range(gpu_count))
    allowed = [d for d in visible if d not in reserved]
    if allowed == visible:
        return ""

    def drop_flag(flag: str) -> None:
        if flag in command:
            i = command.index(flag)
            del command[i:i + 2]

    def set_flag(flag: str, value: str) -> None:
        if flag in command:
            command[command.index(flag) + 1] = value
        else:
            command.extend([flag, value])

    drop_flag("-ts")
    if allowed:
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(d) for d in allowed)
        if "-mg" in command:
            set_flag("-mg", "0")
        if len(allowed) == 1:
            set_flag("-sm", "none")
        return f"GPU {sorted(reserved)} riservate: LLM sulle GPU {allowed}"
    # Nessuna GPU libera: l'LLM resta usabile, piu' lento, sulla CPU.
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    set_flag("-ngl", "0")
    drop_flag("-mg")
    return f"GPU {sorted(reserved)} riservate: LLM su CPU"
