"""Un errore di installazione conserva la versione utilizzabile precedente."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from core import module_loader as module
from core.mcp.base_server import BaseMCPServer
from core.mcp.mcp_hub import mcp_hub


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "studio"
    backend = root / "core/modules"
    frontend = root / "sigma_studio/src/modules"
    for name, value in (("_ROOT", root), ("_CORE_MODULES_DIR", backend),
                        ("_FRONTEND_MODULES_DIR", frontend), ("_FRONTEND_DIR", root / "sigma_studio"),
                        ("_STATE_FILE", root / "installed.json")):
        monkeypatch.setattr(module, name, str(value))
    source = tmp_path / "SigmaStudio-Moduli/modules/demo"
    for side in ("backend", "frontend"):
        (source / side).mkdir(parents=True)
        (source / side / "version.txt").write_text("nuovo", encoding="utf-8")
    for directory in (backend / "demo", frontend / "demo", root / "sigma_studio/dist"):
        directory.mkdir(parents=True)
        (directory / "version.txt").write_text("precedente", encoding="utf-8")
    state = root / "installed.json"
    state.write_text(json.dumps({"demo": True}), encoding="utf-8")
    loader = module.ModuleLoader()
    monkeypatch.setattr(loader, "_install_python_dependencies", lambda *args: None)
    monkeypatch.setattr(loader, "_rebuild_frontend", lambda: None)
    monkeypatch.setattr(loader, "_load_module", lambda *args: True)
    return loader, root, backend, frontend


@pytest.mark.parametrize("step", ["_install_python_dependencies", "_rebuild_frontend", "_load_module"])
def test_errore_ripristina_codice_build_e_stato(setup, monkeypatch, step):
    loader, root, backend, frontend = setup

    def fail(*args):
        raise RuntimeError("errore controllato")

    monkeypatch.setattr(loader, step, fail)
    with pytest.raises(RuntimeError):
        loader.install("demo", app=FastAPI())
    for directory in (backend / "demo", frontend / "demo", root / "sigma_studio/dist"):
        assert (directory / "version.txt").read_text(encoding="utf-8") == "precedente"
    assert json.loads((root / "installed.json").read_text()) == {"demo": True}


def test_caricamento_falso_non_diventa_successo(setup, monkeypatch):
    loader, root, _, _ = setup
    monkeypatch.setattr(loader, "_load_module", lambda *args: False)
    with pytest.raises(RuntimeError, match="registrazione"):
        loader.install("demo", app=FastAPI())


@pytest.mark.parametrize("name", ["../esterno", "", "/tmp/esterno", "C:\\esterno", "demo/../../esterno"])
def test_identificativo_non_puo_uscire_dal_modulo(setup, name):
    loader, _, _, _ = setup
    with pytest.raises(ValueError):
        loader.uninstall(name)


def test_disinstallazione_fallita_conserva_il_modulo(setup, monkeypatch):
    loader, _, backend, _ = setup

    def fail():
        raise RuntimeError("build fallita")

    monkeypatch.setattr(loader, "_rebuild_frontend", fail)
    with pytest.raises(RuntimeError):
        loader.uninstall("demo")
    assert (backend / "demo/version.txt").read_text() == "precedente"


def test_disinstallazione_rimuove_route_e_server_di_proprieta(setup, monkeypatch):
    loader, _, _, _ = setup
    app = FastAPI()
    original_import = module.importlib.import_module

    def routes(app):
        app.add_api_route("/demo", lambda: {"ok": True})

    server = BaseMCPServer("nome-diverso-dal-modulo")
    extension = SimpleNamespace(register_routes=routes, register_mcp=lambda hub: hub.register_server(server))

    def import_module(name, *args):
        return extension if name == "core.modules.demo.handlers" else original_import(name, *args)

    monkeypatch.setattr(module.importlib, "import_module", import_module)
    assert module.ModuleLoader._load_module(loader, "demo", app)
    assert any(route.path == "/demo" for route in app.routes)
    loader._unregister_module("demo")
    assert all(route.path != "/demo" for route in app.routes)
    assert server.name not in mcp_hub.servers


@pytest.mark.parametrize("invalid", [[], None, "demo", 42])
def test_stato_json_non_valido_non_interrompe_il_boot(setup, invalid):
    loader, root, _, _ = setup
    (root / "installed.json").write_text(json.dumps(invalid), encoding="utf-8")
    assert loader._enabled_module_ids() == []


@pytest.mark.parametrize("requirements", [
    {"min_kernel_version": "99.0.0"}, {"kernel_api": 99}, {"kernel_api": True},
    {"required_kernel_features": ["funzione_inesistente"]}, {"required_kernel_features": "persistent_jobs"},
    {"id": "altro_modulo"}, {"min_kernel_version": "non-valida"},
])
def test_pacchetto_incompatibile_non_sostituisce_la_versione_precedente(setup, requirements):
    loader, root, backend, _ = setup
    source = root.parent / "SigmaStudio-Moduli/modules/demo"
    (source / "manifest.json").write_text(json.dumps({"id": "demo", **requirements}), encoding="utf-8")
    with pytest.raises(ValueError):
        loader.install("demo", app=FastAPI())
    assert (backend / "demo/version.txt").read_text() == "precedente"


def test_manifest_compatibile_con_le_funzioni_del_kernel(tmp_path):
    from core.module_contract import validate_manifest
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"id": "demo", "kernel_api": 1, "min_kernel_version": "0.9.1",
                               "required_kernel_features": ["persistent_jobs"]}), encoding="utf-8")
    assert validate_manifest(path, "demo")["id"] == "demo"


def test_versione_del_kernel_coerente_con_i_pacchetti_frontend():
    from core.version import VERSION
    root = Path(__file__).resolve().parents[1]
    for relative in ("package.json", "sigma_studio/package.json", "sigma_studio/package-lock.json"):
        assert json.loads((root / relative).read_text(encoding="utf-8"))["version"] == VERSION
