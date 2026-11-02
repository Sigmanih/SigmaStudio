"""Prenotazioni atomiche di risorse nel processo, indipendenti dai moduli."""
from __future__ import annotations

import threading
import time


class ResourceBusy(RuntimeError):
    """La risorsa appartiene già a un'altra esecuzione."""


class Reservation:
    def __init__(self, pool, keys: tuple[str, ...], owner: str):
        self.pool, self.keys, self.owner = pool, keys, owner
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        with self.pool._lock:
            if not self.closed:
                for key in self.keys:
                    self.pool._active.pop(key, None)
                self.closed = True


class ResourcePool:
    def __init__(self):
        self._lock = threading.Lock()
        self._active = {}

    def reserve(self, keys, owner: str) -> Reservation:
        if isinstance(keys, (str, bytes)):
            raise ValueError("Le risorse devono essere una sequenza di nomi")
        keys = tuple(keys)
        if not keys or not isinstance(owner, str) or not owner or any(not isinstance(key, str) or not key for key in keys):
            raise ValueError("Risorse e proprietario richiesti")
        keys = tuple(sorted(set(keys)))
        with self._lock:
            if any(key in self._active for key in keys):
                raise ResourceBusy("Una risorsa richiesta è già occupata")
            for key in keys:
                self._active[key] = {"owner": owner, "since": time.monotonic()}
        return Reservation(self, keys, owner)

    def occupied(self, key: str) -> bool:
        with self._lock:
            return key in self._active

    def snapshot(self) -> dict:
        with self._lock:
            return {key: {"owner": value["owner"], "elapsed_seconds": max(0, time.monotonic() - value["since"])}
                    for key, value in self._active.items()}


resource_pool = ResourcePool()
