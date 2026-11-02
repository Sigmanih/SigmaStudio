"""Capacita' opzionali registrate dai moduli, senza dipendenze inverse."""
import threading
from typing import Any

_lock = threading.RLock()
_services: dict[str, tuple[str, Any]] = {}


def register(name: str, value: Any, *, owner: str) -> None:
    if not name or not owner or value is None:
        raise ValueError("Servizio e proprietario devono essere dichiarati.")
    with _lock:
        previous = _services.get(name)
        if previous and previous[0] != owner:
            raise ValueError(f"Capacita' '{name}' gia' registrata da '{previous[0]}'.")
        _services[name] = (owner, value)


def get(name: str, default: Any = None) -> Any:
    with _lock:
        return _services.get(name, ("", default))[1]


def require(name: str) -> Any:
    value = get(name)
    if value is None:
        raise RuntimeError(f"Capacita' '{name}' non disponibile: attiva il laboratorio che la fornisce.")
    return value


def unregister_owner(owner: str) -> None:
    with _lock:
        for name in [name for name, entry in _services.items() if entry[0] == owner]:
            _services.pop(name)


def snapshot() -> dict:
    with _lock:
        return dict(_services)


def restore(state: dict) -> None:
    with _lock:
        _services.clear()
        _services.update(state)


def remove_changes(before: dict, after: dict) -> None:
    with _lock:
        for name, entry in after.items():
            if before.get(name) != entry and _services.get(name) == entry:
                _services.pop(name, None)
                if name in before:
                    _services[name] = before[name]
