"""Il launcher prepara i servizi senza HTTP e non confonde una coda con un modello."""
from types import SimpleNamespace

from core import service_registry
from core.module_loader import ModuleLoader
from core.system import first_run


def test_bootstrap_registra_solo_servizi(tmp_path, monkeypatch):
    import core.module_loader as loader_module
    monkeypatch.setattr(loader_module, "_CORE_MODULES_DIR", str(tmp_path / "modules"))
    loader = ModuleLoader()
    monkeypatch.setattr(loader, "_enabled_module_ids", lambda: ["esempio"])
    calls = []
    backend = SimpleNamespace(register_services=lambda registry: calls.append("servizi"),
                              register_routes=lambda app: calls.append("http"))
    monkeypatch.setattr(loader, "_import_backend", lambda name: (backend, "backend"))
    loader.load_services()
    assert calls == ["servizi"]


def test_download_accodato_non_segna_il_modello_pronto(monkeypatch):
    from core import model_paths
    monkeypatch.setattr(model_paths, "list_model_dirs", lambda: [])
    monkeypatch.setattr(first_run, "modello_predefinito", lambda: {"repo": "prova/modello", "dimensione_mb": 1})
    manager = SimpleNamespace(start_repo_download=lambda repo: {"success": True, "status": "queued"})
    monkeypatch.setattr(service_registry, "require", lambda name: manager)
    result = first_run._modello_pronto(lambda message: None, scarica=True)
    assert result["ok"] is False
    assert result["motivo"] == "download_in_corso"
