# ==============================================================================
# tests/test_structured_verification.py — Verifica strutturata delle prove
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Test della verifica strutturata dei comandi eseguiti dall'agente.

Dimostra che il sistema non accetta piu' una finta verifica solo perche' il
processo e' terminato con exit code 0, e che i veri test eseguiti vengono
contati e documentati come prova oggettiva di correttezza.
"""

from core.harness.verification import parse_verification
from core.harness.ledger import DevSessionLedger, check_completion_allowed


class TestParsingPytest:
    def test_pytest_con_test_passati_e_valido(self):
        output = (
            "============================= test session starts =============================\n"
            "tests/test_mod.py ...                                                    [100%]\n"
            "3 passed, 1 warning in 0.12s\n"
        )
        report = parse_verification("python -m pytest tests/test_mod.py -q", 0, stdout=output)
        assert report.is_valid is True
        assert report.passed == 3
        assert report.failed == 0
        assert "3 passati" in report.summary

    def test_pytest_senza_test_raccolti_e_respinto(self):
        """Un comando uscito con zero che non ha eseguito nulla NON e' una verifica."""
        output = (
            "============================= test session starts =============================\n"
            "collected 0 items\n"
            "============================ no tests ran in 0.01s =============================\n"
        )
        report = parse_verification("pytest tests/test_inesistente.py", 0, stdout=output)
        assert report.is_valid is False
        assert report.passed == 0
        assert "Nessun test" in report.summary

    def test_pytest_con_fallimenti_e_non_valido(self):
        output = (
            "FAILED tests/test_mod.py::test_uno - AssertionError: 1 != 2\n"
            "1 failed, 2 passed in 0.25s\n"
        )
        report = parse_verification("pytest tests/", 1, stdout=output)
        assert report.is_valid is False
        assert report.passed == 2
        assert report.failed == 1
        assert "falliti" in report.summary


class TestParsingUnittest:
    def test_unittest_successo(self):
        output = (
            ".....\n"
            "----------------------------------------------------------------------\n"
            "Ran 5 tests in 0.003s\n\n"
            "OK\n"
        )
        report = parse_verification("python -m unittest tests/test_a.py", 0, stdout=output)
        assert report.is_valid is True
        assert report.passed == 5
        assert "5 test superati" in report.summary

    def test_unittest_zero_test_rifiutato(self):
        output = (
            "----------------------------------------------------------------------\n"
            "Ran 0 tests in 0.000s\n\n"
            "OK\n"
        )
        report = parse_verification("python -m unittest tests/test_vuoto.py", 0, stdout=output)
        assert report.is_valid is False
        assert "Nessun test" in report.summary


class TestParsingLinterEBuild:
    def test_eslint_senza_errori(self):
        report = parse_verification("npm run lint:undef", 0, stdout="")
        assert report.is_valid is True
        assert "pulito" in report.summary

    def test_eslint_con_errori(self):
        output = "✖ 2 problems (2 errors, 0 warnings)\n"
        report = parse_verification("npm run lint:undef", 1, stdout=output)
        assert report.is_valid is False
        assert report.failed == 2

    def test_vite_build_completato(self):
        output = "✓ built in 822ms\n"
        report = parse_verification("npm run build", 0, stdout=output)
        assert report.is_valid is True
        assert "completata" in report.summary


class TestIntegrazioneNelLedger:
    def test_falso_positivo_bloccato_dal_cancello(self, tmp_path):
        """Un pytest a vuoto non sblocca la chiusura per codice modificato."""
        ledger = DevSessionLedger(goal="Implementa il modulo note", workspace_root=str(tmp_path))
        # Simuliamo la creazione di un file di codice
        ledger.record_tool("write_file", {"path": "modulo.py", "content": "X = 1\n"}, {"success": True, "path": "modulo.py"})

        # L'agente esegue un test che non raccoglie nulla ma esce con 0
        ledger.record_tool(
            "terminal",
            {"command": "python -m pytest tests/test_inesistente.py"},
            {"success": True, "returncode": 0, "stdout": "collected 0 items\nno tests ran"},
        )

        esito = check_completion_allowed(ledger)
        assert esito["allowed"] is False
        # Il ledger registra che c'e' una verifica ancora fallita/invalida
        assert ledger.failed_verifications()

    def test_verifica_reale_sblocca_con_dettaglio_strutturato(self, tmp_path):
        """Un pytest con test passati sblocca e riporta la prova esatta."""
        ledger = DevSessionLedger(goal="Implementa il modulo note", workspace_root=str(tmp_path))
        ledger.record_tool("write_file", {"path": "modulo.py", "content": "X = 1\n"}, {"success": True, "path": "modulo.py"})

        # Prima prova fallita
        ledger.record_tool(
            "terminal",
            {"command": "python -m pytest tests/test_modulo.py"},
            {"success": True, "returncode": 1, "stdout": "1 failed in 0.1s"},
        )
        assert check_completion_allowed(ledger)["allowed"] is False

        # Correzione e seconda prova superata con 4 test verdi
        ledger.record_tool(
            "terminal",
            {"command": "python -m pytest tests/test_modulo.py"},
            {"success": True, "returncode": 0, "stdout": "4 passed in 0.15s"},
        )

        esito = check_completion_allowed(ledger)
        assert esito["allowed"] is True
        assert "verified_by" in esito["evidence"]
        # La prova deve citare il riepilogo strutturato estratto dall'output
        assert "4 passati" in esito["evidence"]["verified_by"]
