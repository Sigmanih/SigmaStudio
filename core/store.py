# ==============================================================================
# core/store.py — Thread-Safe JSON File Store
# Sigma Studio v6 — Centralized, lock-protected access to JSON state files
# ==============================================================================
"""Thread-safe read/write helpers for the project's JSON state files.

Every file has a dedicated ``threading.RLock`` so concurrent HTTP threads
(spawned by ``ThreadingMixIn``) never corrupt data.

Provided stores:
    tasks_store       → tasks.json
    modules_store     → modules_meta.json

Usage:
    from core.store import tasks_store, modules_store

    # Read
    tasks = tasks_store.load()

    # Atomic write
    tasks.append(new_task)
    tasks_store.save(tasks)

    # Atomic update (read-modify-write in one lock)
    def add_task(task: dict) -> list:
        tasks = tasks_store.load()
        tasks.append(task)
        return tasks
    tasks_store.update(add_task)
"""

import json
import os
import threading
from typing import Any, Callable
from core.logger import get_logger

log = get_logger(__name__)


class JsonStore:
    """Atomic, thread-safe JSON file store backed by a ``threading.RLock``.

    Args:
        path:    Relative path to the JSON file (e.g. ``"tasks.json"``).
        default: Default value returned / written when the file is missing
                 or corrupted.  Typically ``[]`` or ``{}``.
    """

    def __init__(self, path: str, default: Any = None) -> None:
        self._path = path
        self._default = default if default is not None else {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> Any:
        """Return the current contents of the JSON file.

        Returns *default* if the file does not exist or contains invalid JSON.
        Always called inside the lock so the caller sees a consistent snapshot.
        """
        with self._lock:
            return self._read()

    def save(self, data: Any) -> None:
        """Atomically overwrite the JSON file with *data*.

        Writes to a temp file first, then renames to avoid partial writes.
        """
        with self._lock:
            self._write(data)

    def update(self, fn: Callable[[Any], Any]) -> Any:
        """Atomically read → transform → write in a single lock acquisition.

        Args:
            fn: A callable that receives the current data and returns the
                new data to persist.

        Returns:
            The value returned by *fn*.
        """
        with self._lock:
            current = self._read()
            updated = fn(current)
            self._write(updated)
            return updated

    # ------------------------------------------------------------------
    # Internal helpers (must be called with lock held)
    # ------------------------------------------------------------------

    def _read(self) -> Any:
        if not os.path.exists(self._path):
            return self._default_copy()
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
            if not content:
                return self._default_copy()
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Corrupted JSON in %s: %s — resetting to default", self._path, exc)
            self._write(self._default_copy())
            return self._default_copy()

    def _write(self, data: Any) -> None:
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=4, ensure_ascii=False)
            # Atomic replace (works on Windows too)
            if os.path.exists(self._path):
                os.replace(tmp, self._path)
            else:
                os.rename(tmp, self._path)
        except OSError as exc:
            log.error("Failed to write %s: %s", self._path, exc)
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            raise

    def _default_copy(self) -> Any:
        """Return a fresh copy of the default value (avoids shared-reference bugs)."""
        import copy
        return copy.deepcopy(self._default)


# ---------------------------------------------------------------------------
# Singleton stores — import these everywhere instead of open() calls
# ---------------------------------------------------------------------------

#: Global store for ``tasks.json`` — default is an empty list.
tasks_store = JsonStore("tasks.json", default=[])

#: Global store for ``modules_meta.json`` — default is an empty dict.
modules_store = JsonStore("modules_meta.json", default={"topics": {}, "modules": {}})
