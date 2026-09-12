# ==============================================================================
# tests/test_orchestrator_live_5phases.py — Test End-to-End Orchestratore 5 Fasi
# ==============================================================================
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil

import pytest

pytest.importorskip(
    "core.modules.sigma_developer_lab.orchestrator",
    reason="modulo sigma_developer_lab non installato",
)

from core.modules.sigma_developer_lab.orchestrator import (
    DevOrchestrator,
    ExecutionMode,
    PHASES,
)
from core.harness.pipeline import TaskNode, TaskPipeline


class TestOrchestratorLive5Phases(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sigma_orch_test_")
        self.workspace_root = str(Path(self.temp_dir).resolve()).replace("\\", "/")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_autonomous_5phases_pipeline_execution(self):
        """Esegue l'intero flusso delle 5 fasi in modalità autonoma con Architect, DevOps, Coder, Tester, Reviewer."""
        orch = DevOrchestrator(workspace_root=self.workspace_root, session_id="test_live_session")
        goal = "Aggiungi modulo calcolo sconti in pricing.py con test"

        # Mock del motore ruoli per simulare l'output di ciascun ruolo in sequenza
        def fake_generate_with_role(role_id, prompt, context="", model_name=None, should_cancel=None,
                                    workspace_root=None, ledger=None, session_id=None, **kwargs):
            yield {"type": "role_switch", "role_id": role_id, "role_name": role_id.title()}
            
            if role_id == "architect":
                yield {"type": "token", "token": "Ho analizzato il workspace. Creo la pipeline di task."}
                # Architect definisce i task tramite tool pipeline
                tasks = [
                    {"id": "t1", "title": "Crea pricing.py", "role": "coder", "description": "Scrivi modulo pricing.py"},
                    {"id": "t2", "title": "Scrivi test_pricing.py", "role": "coder", "description": "Scrivi test in tests/test_pricing.py", "depends_on": ["t1"]}
                ]
                yield {"type": "pipeline_update", "tasks": tasks}
                if ledger:
                    ledger.record_tool("pipeline", {}, {"tasks": tasks, "success": True})

            elif role_id == "devops" and "branch" in prompt.lower():
                yield {"type": "token", "token": "Creo branch feat/discounts"}
                yield {"type": "tool_result", "result": {"tool": "git_branch_create", "message": "creato branch 'feat/discounts'"}}

            elif role_id == "coder":
                yield {"type": "token", "token": "Implemento il codice."}
                yield {
                    "type": "tool_result",
                    "result": {
                        "tool": "write_file",
                        "path": "pricing.py",
                        "full_path": f"{workspace_root}/pricing.py",
                        "success": True,
                    }
                }
                if ledger:
                    ledger.record_tool("write_file", {"path": "pricing.py"}, {"success": True, "path": "pricing.py"})

            elif role_id == "tester":
                yield {"type": "token", "token": "Eseguo i test con pytest."}
                stdout_success = "test_pricing.py . [100%]\n2 passed in 0.05s"
                yield {
                    "type": "tool_result",
                    "result": {
                        "tool": "terminal",
                        "command": "python -m pytest tests/test_pricing.py",
                        "returncode": 0,
                        "stdout": stdout_success,
                        "stderr": "",
                        "success": True,
                    }
                }
                if ledger:
                    ledger.record_tool("terminal", {"command": "python -m pytest tests/test_pricing.py"}, {
                        "returncode": 0, "stdout": stdout_success, "stderr": "", "success": True
                    })

            elif role_id == "reviewer":
                yield {"type": "token", "token": "Codice revisionato: conforme e ben strutturato."}

            elif role_id == "devops" and "commit" in prompt.lower():
                yield {"type": "token", "token": "Commit completato con Conventional Commits."}

        orch.role_engine.generate_with_role = fake_generate_with_role

        # Esecuzione del flusso
        events = list(orch.execute_goal(goal, mode=ExecutionMode.AUTONOMOUS))
        event_types = [e.get("type") for e in events]

        # 1. Verifica avvio e ordine delle fasi
        self.assertIn("orchestrator_start", event_types)
        phase_starts = [e.get("phase") for e in events if e.get("type") == "phase_start"]
        self.assertEqual(phase_starts, ["analyze", "setup", "implement", "verify", "deliver"])

        # 2. Verifica che i task dell'Architect siano stati creati ed eseguiti
        task_starts = [e.get("task_id") for e in events if e.get("type") == "task_start"]
        task_dones = [e.get("task_id") for e in events if e.get("type") == "task_done"]
        self.assertEqual(task_starts, ["t1", "t2"])
        self.assertEqual(task_dones, ["t1", "t2"])

        # 3. Verifica sincronizzazione ledger e file tracciati
        self.assertIsNotNone(orch.ledger)
        self.assertIn("pricing.py", orch.ledger.modified_files)
        self.assertTrue(orch.ledger.has_modifications())

        # 4. Verifica evento di chiusura e report
        self.assertIn("orchestrator_done", event_types)
        done_event = next(e for e in events if e.get("type") == "orchestrator_done")
        self.assertIn("pricing.py", str(done_event.get("files_modified", [])))

    def test_interactive_mode_requires_approval_and_respects_rejection(self):
        """In modalità interattiva, una fase rifiutata viene saltata e non eseguita."""
        orch = DevOrchestrator(workspace_root=self.workspace_root)
        goal = "Refactoring del database"

        # Pre-approva analyze, ma rifiuta setup
        orch.approve("analyze", "approved")
        orch.approve("setup", "rejected")
        orch.approve("implement", "approved")
        orch.approve("verify", "approved")
        orch.approve("deliver", "approved")

        def fake_generate(role_id, *args, **kwargs):
            yield {"type": "token", "token": f"Esecuzione ruolo {role_id}"}

        orch.role_engine.generate_with_role = fake_generate

        events = list(orch.execute_goal(goal, mode=ExecutionMode.INTERACTIVE))
        event_types = [e.get("type") for e in events]

        # approval_required deve essere stato emesso
        self.assertIn("approval_required", event_types)

        # setup deve risultare phase_skipped
        skipped_phases = [e.get("phase") for e in events if e.get("type") == "phase_skipped"]
        self.assertIn("setup", skipped_phases)

    def test_feedback_loop_triggers_when_test_fails(self):
        """Test rossi -> il ciclo di correzione parte, corregge, e si ferma
        quando la verifica torna verde.

        Prima questo test riconosceva la chiamata al Coder cercando «feedback
        del tester» dentro il prompt. Era esattamente la cosa da togliere: al
        Coder non si passa piu' il racconto del Tester — la prosa di un modello
        — ma l'istruzione costruita sui fatti che il ledger ha registrato.
        """
        orch = DevOrchestrator(workspace_root=self.workspace_root)
        orch.mode = ExecutionMode.AUTONOMOUS
        goal = "Correggi bug di divisione per zero"

        runs = {"tester_calls": 0, "coder_calls": 0}
        istruzioni_al_coder = []

        def fake_generate(role_id, prompt, *args, **kwargs):
            if role_id == "tester":
                runs["tester_calls"] += 1
                if runs["tester_calls"] == 1:
                    yield {
                        "type": "tool_result",
                        "result": {"tool": "terminal", "command": "pytest",
                                   "returncode": 1, "stderr": "ZeroDivisionError"},
                    }
                else:
                    yield {
                        "type": "tool_result",
                        "result": {"tool": "terminal", "command": "pytest",
                                   "returncode": 0, "stdout": "1 passed"},
                    }
            elif role_id == "coder":
                runs["coder_calls"] += 1
                istruzioni_al_coder.append(prompt)
                yield {"type": "token", "token": "Bug corretto con try/except."}
            elif role_id == "reviewer":
                yield {"type": "token", "token": "Ok"}
            else:
                yield {"type": "token", "token": "Ok"}

        orch.role_engine.generate_with_role = fake_generate

        events = list(orch._run_phase("verify", goal))
        status_texts = [e.get("text", "") for e in events if e.get("type") == "status"]

        self.assertTrue(any("avvio ciclo di correzione" in s for s in status_texts))
        self.assertTrue(any("Verifica superata" in s for s in status_texts))
        self.assertEqual(runs["coder_calls"], 1,
                         "una correzione sola: poi la verifica e' tornata verde")
        self.assertEqual(runs["tester_calls"], 2)

        # La diagnosi deve essere passata dall'autocorrezione, ed essere
        # visibile a chi guarda.
        diagnosi = [e for e in events if e.get("type") == "self_correction"]
        self.assertTrue(diagnosi, "la mossa scelta deve essere dichiarata")
        self.assertIn("budget", diagnosi[0])

        # E l'istruzione al Coder non deve essere il testo di un modello.
        self.assertTrue(istruzioni_al_coder)
        self.assertNotIn("feedback del tester", istruzioni_al_coder[0].lower())

    def test_il_bilancio_ferma_il_ciclo_di_correzione(self):
        """Un sistema che riprova per sempre non e' autonomo, e' bloccato."""
        from core.harness import autocorrezione

        orch = DevOrchestrator(workspace_root=self.workspace_root)
        orch.mode = ExecutionMode.AUTONOMOUS
        orch.bilancio = autocorrezione.Bilancio(correzioni=0)

        chiamate = {"n": 0}

        def fake_generate(role_id, prompt, *args, **kwargs):
            chiamate["n"] += 1
            yield {"type": "token", "token": "ok"}

        orch.role_engine.generate_with_role = fake_generate
        eventi = list(orch._feedback_loop("obiettivo", None, max_retries=2))

        self.assertEqual(chiamate["n"], 0, "non deve chiamare nessun ruolo")
        testi = [e.get("text", "") for e in eventi if e.get("type") == "status"]
        self.assertTrue(any("esaurito" in t for t in testi))


if __name__ == "__main__":
    unittest.main()
