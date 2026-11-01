"""Un import storico e quello canonico devono condividere cache e singleton."""
import importlib

import pytest


@pytest.mark.parametrize("alias,canonical", [
    ("core.data_handler", "core.handlers.data_handler"),
    ("core.sandbox", "core.security.sandbox"),
    ("core.runtime_env", "core.system.runtime_env"),
])
def test_alias_condivide_modulo_e_spec(alias, canonical):
    legacy = importlib.import_module(alias)
    actual = importlib.import_module(canonical)
    assert legacy is actual
    assert actual.__spec__.name == canonical


def test_cache_condivisa_fra_alias_e_modulo_canonico(monkeypatch):
    legacy = importlib.import_module("core.data_handler")
    actual = importlib.import_module("core.handlers.data_handler")
    cached = {"cache": "condivisa"}
    monkeypatch.setitem(legacy._MODULES_META, "dati", cached)
    assert actual._MODULES_META["dati"] is cached
