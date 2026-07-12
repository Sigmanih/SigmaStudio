# ==============================================================================
# tests/test_store.py — Unit tests for core/store.py
# ==============================================================================
"""Verify thread-safe JsonStore: read/write/update + atomic rename."""

import os
import sys
import json
import threading
import tempfile
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.store import JsonStore


@pytest.fixture
def tmp_store(tmp_path):
    """Return a fresh JsonStore backed by a temp file."""
    path = str(tmp_path / "test.json")
    return JsonStore(path, default=[])


class TestJsonStoreBasic:
    def test_load_default_when_missing(self, tmp_store):
        assert tmp_store.load() == []

    def test_save_and_load(self, tmp_store):
        tmp_store.save(["a", "b"])
        assert tmp_store.load() == ["a", "b"]

    def test_update_returns_new_value(self, tmp_store):
        tmp_store.save([1, 2])
        result = tmp_store.update(lambda items: items + [3])
        assert result == [1, 2, 3]
        assert tmp_store.load() == [1, 2, 3]

    def test_corrupted_file_resets_to_default(self, tmp_store):
        # Write garbage to the backing file
        with open(tmp_store._path, "w") as fh:
            fh.write("NOT VALID JSON {{{{")
        result = tmp_store.load()
        assert result == []

    def test_empty_file_returns_default(self, tmp_store):
        with open(tmp_store._path, "w") as fh:
            fh.write("")
        assert tmp_store.load() == []

    def test_nested_dict_store(self, tmp_path):
        store = JsonStore(str(tmp_path / "meta.json"), default={"topics": {}, "modules": {}})
        store.save({"topics": {"t1": {}}, "modules": {"01": "Base"}})
        data = store.load()
        assert data["topics"]["t1"] == {}
        assert data["modules"]["01"] == "Base"


class TestJsonStoreConcurrency:
    def test_concurrent_updates_no_corruption(self, tmp_store):
        """100 threads each append one item — final count must be exactly 100."""
        tmp_store.save([])
        errors = []

        def _append(i):
            try:
                tmp_store.update(lambda items: items + [i])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_append, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent update: {errors}"
        final = tmp_store.load()
        assert len(final) == 100, f"Expected 100 items, got {len(final)}"

    def test_atomic_write_no_partial_read(self, tmp_store):
        """Readers never see a half-written file."""
        tmp_store.save([])
        stop = threading.Event()
        corrupt_reads = []

        def _writer():
            while not stop.is_set():
                tmp_store.save(list(range(50)))
                time.sleep(0.001)

        def _reader():
            while not stop.is_set():
                data = tmp_store.load()
                if not isinstance(data, list):
                    corrupt_reads.append(data)
                time.sleep(0.0005)

        wt = threading.Thread(target=_writer, daemon=True)
        rt = threading.Thread(target=_reader, daemon=True)
        wt.start(); rt.start()
        time.sleep(0.5)
        stop.set()
        wt.join(); rt.join()

        assert not corrupt_reads, f"Corrupted reads detected: {corrupt_reads}"
