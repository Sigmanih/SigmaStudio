# ==============================================================================
# tests/test_training_api_routes.py — Ogni rotta dichiarata deve avere un handler
# ==============================================================================
"""Sigma serve le richieste con due pipeline (http.server legacy e adapter
FastAPI). Quando gli handler erano duplicati nei due file, le copie sono
divergute: tutto il lato scrittura del Training Lab esisteva solo sul server
legacy e sul server FastAPI rispondeva 404 "Endpoint non trovato".

Questi test falliscono se una rotta viene dichiarata in api_router senza un
handler corrispondente, o se le due pipeline tornano a divergere.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.api_router import register_get_handlers, register_post_handlers
from core.training_api import HANDLERS, register_training_handlers


class _FakeHandler:
    """Classe minima su cui registrare gli handler."""


def _route_tables():
    register_get_handlers(_FakeHandler)
    register_post_handlers(_FakeHandler)
    return _FakeHandler._GET_HANDLERS, _FakeHandler._POST_HANDLERS


class TestRouteCoverage:

    def test_fastapi_pipeline_has_every_handler(self):
        from core.fastapi_app import FastAPIHandlerAdapter as adapter
        missing = [path for path, name in
                   list(adapter._GET_HANDLERS.items()) + list(adapter._POST_HANDLERS.items())
                   if not hasattr(adapter, name)]
        assert missing == [], f"rotte FastAPI senza handler: {missing}"

    def test_training_routes_exist_on_both_pipelines(self):
        """Le rotte del Training Lab devono essere servite da entrambe le pipeline."""
        from core.fastapi_app import FastAPIHandlerAdapter as fastapi_cls
        import sigma_server
        legacy_cls = sigma_server.SigmaAPIHandler

        get_map, post_map = _route_tables()
        training = {p: h for p, h in {**get_map, **post_map}.items()
                    if p.startswith("/api/training") or p.startswith("/api/hardware")}
        assert training, "nessuna rotta training trovata nel router"

        for path, name in training.items():
            assert hasattr(fastapi_cls, name), f"{path} manca sul server FastAPI"
            assert hasattr(legacy_cls, name), f"{path} manca sul server legacy"

    @pytest.mark.parametrize("path", [
        "/api/training/job/create",
        "/api/training/job/start",
        "/api/training/job/stop",
        "/api/training/job/delete",
        "/api/training/job/clear_logs",
        "/api/training/dataset/import",
        "/api/training/dataset/register_hf",
        "/api/training/dataset/delete",
        "/api/training/dependencies",
        "/api/training/export/ollama",
        "/api/training/fwe/selftest",
        "/api/config/hf_token",
    ])
    def test_write_endpoints_are_routed_and_implemented(self, path):
        """Il lato scrittura del Training Lab: la regressione che ha rotto Gradus."""
        from core.fastapi_app import FastAPIHandlerAdapter as adapter
        _get_map, post_map = _route_tables()
        assert path in post_map, f"{path} non dichiarata fra le rotte POST"
        assert hasattr(adapter, post_map[path]), f"{path} dichiarata ma non implementata"


class TestVerbsMatchTheFrontend:
    """Una rotta dichiarata sotto il verbo sbagliato risponde 404.

    E' successo con /export/quant_levels: registrata fra le POST mentre la UI la
    chiama in GET. Il test controlla il verbo effettivo servendo la richiesta,
    non solo la presenza della rotta in una delle due tabelle.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from core.fastapi_app import app
        return TestClient(app)

    @pytest.mark.parametrize("path", [
        "/api/training/export/quant_levels",
        "/api/training/job/continuation_modes",
        "/api/hardware/gpu/processes",
    ])
    def test_read_only_lookups_answer_on_get(self, client, path):
        response = client.get(path)
        assert response.status_code == 200, f"{path} non risponde in GET"
        assert response.json().get("success") is True

    def test_kill_senza_pid_non_e_un_404(self, client):
        """Chiudere un processo e' una scrittura: deve rispondere in POST.

        Il corpo vuoto deve far fallire l'operazione con un messaggio, non il
        routing con un 404 — la differenza fra "non hai detto quale processo" e
        "questa funzione non esiste".
        """
        response = client.post("/api/hardware/gpu/kill", json={})
        assert response.status_code == 400
        assert response.json()["success"] is False
        assert "pid" in response.json()["error"].lower()

    @pytest.mark.parametrize("path", [
        "/api/training/job/continue",
        "/api/training/export/ollama",
    ])
    def test_write_endpoints_answer_on_post(self, client, path):
        """Il corpo vuoto fa fallire l'operazione, non il routing."""
        response = client.post(path, json={})
        assert response.status_code == 200, f"{path} non risponde in POST"
        assert response.json().get("success") is False   # manca il job_id


class TestSharedRegistration:

    def test_registration_attaches_all_handlers(self):
        class Target:
            pass

        registered = register_training_handlers(Target)
        assert registered, "nessun handler registrato"
        for name in registered:
            assert callable(getattr(Target, name))

    def test_handler_set_covers_job_lifecycle(self):
        expected = {
            "handle_training_job_create", "handle_training_job_start",
            "handle_training_job_stop", "handle_training_job_delete",
            "handle_training_job_status", "handle_training_job_logs",
            "handle_training_list_jobs", "handle_training_clear_logs",
            "handle_training_export_ollama", "handle_training_dependencies",
            "handle_training_fwe_status", "handle_training_fwe_selftest",
            "handle_training_gpu_capabilities", "handle_training_gpu_autotune",
        }
        assert expected <= set(HANDLERS)


class TestEndToEndOverHttp:
    """Chiamate reali attraverso l'app FastAPI, come le fa la tab."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from core.fastapi_app import app
        return TestClient(app)

    def test_gradus_job_lifecycle(self, client, tmp_path):
        import core.training_handler as th
        saved = {n: getattr(th, n) for n in ("TRAINING_DIR", "JOBS_DIR", "JOBS_FILE", "SCRIPTS_DIR")}
        th.TRAINING_DIR = tmp_path / "training"
        th.JOBS_DIR = th.TRAINING_DIR / "jobs"
        th.JOBS_FILE = th.TRAINING_DIR / "training_jobs.json"
        th.SCRIPTS_DIR = th.TRAINING_DIR / "scripts"
        for d in (th.TRAINING_DIR, th.JOBS_DIR, th.SCRIPTS_DIR):
            d.mkdir(parents=True, exist_ok=True)
        try:
            res = client.post("/api/training/job/create", json={
                "base_model": "qwen0.5b-instruct", "dataset_id": "", "method": "fwe_gradus",
                "output_name": "test_fwe",
                "hyperparams": {"fwe_include": "_proj", "fwe_vq": 512, "fwe_steps": 100,
                                "batch_size": 4, "learning_rate": 2e-4},
            })
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["success"] is True
            job_id = body["job_id"]
            assert body["job"]["method"] == "fwe_gradus"
            assert Path(body["job"]["script_path"]).exists()

            status = client.get(f"/api/training/job/status?job_id={job_id}")
            assert status.status_code == 200
            assert status.json()["job"]["id"] == job_id

            logs = client.get(f"/api/training/job/logs?job_id={job_id}&offset=0")
            assert logs.status_code == 200 and logs.json()["success"] is True

            deleted = client.post("/api/training/job/delete", json={"job_id": job_id})
            assert deleted.status_code == 200 and deleted.json()["success"] is True
        finally:
            for name, value in saved.items():
                setattr(th, name, value)

    def test_dependencies_endpoint_answers(self, client):
        res = client.post("/api/training/dependencies", json={"method": "fwe_gradus"})
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True and body["method"] == "fwe_gradus"

    def test_unknown_job_is_a_clean_error_not_a_404(self, client):
        res = client.post("/api/training/job/start", json={"job_id": "inesistente"})
        assert res.status_code == 200
        assert res.json()["success"] is False
