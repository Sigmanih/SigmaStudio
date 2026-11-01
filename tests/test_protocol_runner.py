# ==============================================================================
# tests/test_protocol_runner.py — Test del runner protocol_bench per Benchmark Lab
# ==============================================================================
import unittest
from unittest.mock import MagicMock, patch
import pytest

pytest.importorskip("core.modules.sigma_benchmark_lab.protocol_runner")


@pytest.fixture(autouse=True)
def storico_e_lavoratori_isolati(tmp_path, monkeypatch):
    from core.modules.sigma_benchmark_lab import protocol_runner as runner
    previous = set(runner._threads)
    monkeypatch.setattr(runner, "PROTOCOL_HISTORY_FILE", tmp_path / "history.json")
    yield
    for job_id, worker in list(runner._threads.items()):
        if job_id not in previous:
            runner.cancel_protocol_bench(job_id)
            worker.join(timeout=3)
            assert not worker.is_alive(), "Il benchmark ha lasciato un lavoratore attivo."

from core.modules.sigma_benchmark_lab.protocol_runner import (
    cancel_protocol_bench,
    get_protocol_scenarios,
    get_protocol_status,
    list_protocol_history,
    start_protocol_bench,
)


class TestProtocolRunner(unittest.TestCase):
    def test_get_protocol_scenarios(self):
        scenari = get_protocol_scenarios()
        self.assertIsInstance(scenari, list)
        self.assertGreaterEqual(len(scenari), 2)
        ids = [s["id"] for s in scenari]
        self.assertIn("file_nuovo", ids)
        self.assertIn("modifica_mirata", ids)
        for s in scenari:
            self.assertTrue(s["descrizione"])
            self.assertTrue(s["obiettivo"])
            self.assertGreater(s["tetto_turni"], 0)

    def test_get_protocol_status_idle(self):
        status = get_protocol_status("invalido_non_esistente_12345")
        self.assertIsInstance(status, dict)

    def test_list_protocol_history(self):
        history = list_protocol_history()
        self.assertIsInstance(history, list)

    @patch("core.modules.sigma_benchmark_lab.protocol.esegui")
    def test_start_and_status(self, mock_esegui):
        mock_esegui.return_value = {
            "model": "test-model",
            "punteggio": 100.0,
            "superate": 10,
            "totali": 10,
            "turni_totali": 5,
            "secondi": 12.0,
            "scenari": [],
            "non_misurati": [],
            "check_line": "SIGMA-CHECK {}",
        }

        res = start_protocol_bench(model_name="test-model", scenarios=["file_nuovo"])
        self.assertTrue(res["success"])
        job_id = res["job_id"]

        # Recupera stato: il modello non deve mai essere il placeholder 'test-model' o 'sigma'
        status = get_protocol_status(job_id)
        self.assertEqual(status["id"], job_id)
        self.assertNotEqual(status["model"], "test-model")
        self.assertTrue(len(status["model"]) > 0)

    @patch("core.modules.sigma_benchmark_lab.protocol.esegui")
    def test_delete_protocol_job(self, mock_esegui):
        import threading
        import time
        started = threading.Event()
        stopped = threading.Event()

        def work(**options):
            started.set()
            deadline = time.monotonic() + 2
            while not options["should_cancel"]() and time.monotonic() < deadline:
                time.sleep(0.01)
            if options["should_cancel"]():
                stopped.set()
            return {"punteggio": 0, "scenari": []}

        mock_esegui.side_effect = work
        from core.modules.sigma_benchmark_lab.protocol_runner import (
            start_protocol_bench,
            delete_protocol_job,
            get_protocol_status,
        )

        res = start_protocol_bench(model_name="dummy-delete", scenarios=["file_nuovo"])
        jid = res.get("job_id")
        self.assertTrue(jid)
        self.assertTrue(started.wait(timeout=1))

        ok = delete_protocol_job(jid)
        self.assertTrue(ok)
        self.assertTrue(stopped.wait(timeout=1), "La cancellazione deve restare visibile al lavoratore.")

        # Non deve piu essere presente come job attivo
        status = get_protocol_status(jid)
        self.assertNotEqual(status.get("id"), jid)


if __name__ == "__main__":
    unittest.main()

