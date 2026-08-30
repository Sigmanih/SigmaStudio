"""Stato di lavoro dell'agente e cancello di completamento.

Il ledger e' il meccanismo che tiene insieme il loop autonomo: i fatti sul
workspace vivono qui invece che nel transcritto, cosi' che tagliare la
conversazione non faccia dimenticare all'agente cosa ha gia' letto o scritto.
Il cancello decide quando puo' dichiarare finito, e lo decide sulle prove
raccolte qui — non sulla parola del modello, perche' in un loop autonomo
nessuno controlla dietro di lui.

Questi test fissano le due decisioni che sbagliate costano di piu': quando un
obiettivo e' di sola analisi (e pretendere una modifica lo renderebbe
incompletabile) e quando un fallimento e' stato davvero superato.
"""

import unittest

from core.developer_studio.session_ledger import (
    DevSessionLedger,
    check_completion_allowed,
    looks_like_verification,
)

WS = "C:/progetto"


def _ledger(goal: str) -> DevSessionLedger:
    return DevSessionLedger(goal=goal, workspace_root=WS)


def _scrittura(path="core/x.py", ok=True):
    return {"success": ok, "path": f"{WS}/{path}", "lines_after": 10}


def _comando(cmd, ok=True, err=""):
    return {"success": True, "returncode": 0 if ok else 1, "command": cmd, "stderr": err}


class TestRiconoscimentoObiettivo(unittest.TestCase):
    """Un audit e un refactoring non si completano con le stesse prove."""

    def test_un_obiettivo_di_analisi_e_riconosciuto(self):
        for goal in (
            "Analizza il modulo di rete e dimmi come funziona",
            "Spiegami cosa fa core/engine/sampling.py",
            "Trova tutti i punti dove si legge la configurazione",
            "Fai un audit di sicurezza del provider",
        ):
            self.assertTrue(_ledger(goal).is_exploration_task(), goal)

    def test_un_obiettivo_di_sviluppo_non_lo_e(self):
        for goal in (
            "Crea il modulo sigma_network",
            "Correggi la funzione somma in scratch/probe.py",
            "Implementa le route p2p",
        ):
            self.assertFalse(_ledger(goal).is_exploration_task(), goal)

    def test_analizza_e_correggi_e_sviluppo(self):
        """Se c'e' anche una modifica da fare, le prove richieste sono quelle."""
        goal = "Analizza il modulo e correggi gli errori che trovi"
        self.assertFalse(_ledger(goal).is_exploration_task())


class TestCancelloAnalisi(unittest.TestCase):
    def test_un_audit_si_completa_avendo_letto(self):
        """Pretendere una modifica renderebbe un audit impossibile da chiudere."""
        led = _ledger("Analizza il modulo di rete")
        led.record_tool("read_file", {}, {
            "success": True, "path": f"{WS}/core/net.py",
            "offset": 1, "last_line": 40, "total_lines": 40, "content": "x = 1\n",
        })
        esito = check_completion_allowed(led)
        self.assertTrue(esito["allowed"])
        self.assertEqual(esito.get("mode"), "exploration")

    def test_un_audit_senza_letture_non_si_completa(self):
        """Un report non ancorato a file reali e' un'opinione, non un audit."""
        led = _ledger("Analizza il modulo di rete")
        esito = check_completion_allowed(led)
        self.assertFalse(esito["allowed"])
        self.assertIn("read_file", esito["reason"])


class TestCancelloSviluppo(unittest.TestCase):
    def test_senza_modifiche_non_si_completa(self):
        led = _ledger("Implementa il modulo sigma_network")
        self.assertFalse(check_completion_allowed(led)["allowed"])

    def test_modifiche_senza_verifica_non_bastano(self):
        led = _ledger("Implementa il modulo sigma_network")
        led.record_tool("write_file", {}, _scrittura())
        esito = check_completion_allowed(led)
        self.assertFalse(esito["allowed"])
        self.assertIn("VERIFICATO", esito["reason"])

    def test_modifica_piu_verifica_riuscita_completa(self):
        led = _ledger("Implementa il modulo sigma_network")
        led.record_tool("write_file", {}, _scrittura())
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))
        esito = check_completion_allowed(led)
        self.assertTrue(esito["allowed"])
        self.assertIn("core/x.py", esito["evidence"]["modified_files"])

    def test_una_verifica_fallita_blocca(self):
        led = _ledger("Implementa il modulo sigma_network")
        led.record_tool("write_file", {}, _scrittura())
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q", ok=False, err="1 failed"))
        self.assertFalse(check_completion_allowed(led)["allowed"])

    def test_un_fallimento_corretto_non_blocca_per_sempre(self):
        """Il giudizio e' sullo stato attuale, non sulla storia."""
        led = _ledger("Implementa il modulo sigma_network")
        led.record_tool("write_file", {}, _scrittura())
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q", ok=False, err="1 failed"))
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))
        self.assertTrue(check_completion_allowed(led)["allowed"])


class TestMemoriaDelLavoro(unittest.TestCase):
    def test_le_finestre_di_lettura_si_uniscono(self):
        """Due letture contigue coprono il file: rileggerlo sarebbe sprecato."""
        led = _ledger("Analizza core/net.py")
        for off, last in ((1, 200), (201, 400)):
            led.record_tool("read_file", {}, {
                "success": True, "path": f"{WS}/core/net.py",
                "offset": off, "last_line": last, "total_lines": 400, "content": "",
            })
        stato = led.snapshot()
        self.assertTrue(stato["files"][0]["fully_read"])

    def test_i_percorsi_sono_relativi_al_workspace(self):
        """Un percorso assoluto ripetuto per sessanta file e' solo tassa sul prompt."""
        led = _ledger("Analizza")
        led.record_tool("read_file", {}, {
            "success": True, "path": f"{WS}/core/net.py",
            "offset": 1, "last_line": 5, "total_lines": 5, "content": "",
        })
        self.assertEqual(led.read_files, ["core/net.py"])

    def test_lo_stato_nomina_i_file_toccati(self):
        led = _ledger("Implementa il modulo")
        led.record_tool("write_file", {}, _scrittura("core/nuovo.py"))
        blocco = led.render_state_block()
        self.assertIn("core/nuovo.py", blocco)

    def test_una_riscrittura_invalida_le_letture_precedenti(self):
        """Dopo un write_file il contenuto letto prima non descrive piu' il file."""
        led = _ledger("Implementa il modulo")
        led.record_tool("read_file", {}, {
            "success": True, "path": f"{WS}/core/x.py",
            "offset": 1, "last_line": 10, "total_lines": 10, "content": "",
        })
        led.record_tool("write_file", {}, _scrittura("core/x.py"))
        self.assertFalse(led.snapshot()["files"][0]["fully_read"])


class TestRiconoscimentoVerifica(unittest.TestCase):
    def test_i_comandi_che_dimostrano_qualcosa(self):
        for cmd in ("python -m pytest tests/ -q", "npm run build",
                    "python -m py_compile core/x.py", "ruff check ."):
            self.assertTrue(looks_like_verification(cmd), cmd)

    def test_guardare_non_e_verificare(self):
        for cmd in ("ls -la", "cat file.py", "git status", "echo ciao"):
            self.assertFalse(looks_like_verification(cmd), cmd)




class TestVerificheMultiple(unittest.TestCase):
    """Una verifica passata non risponde per quelle fallite prima di lei.

    Il caso reale: un task frontend ha eseguito `npm run build` (fallito, per
    una libreria assente dal progetto) e poi `pytest` (passato, perche' non
    tocca il frontend). Guardando solo l'ultima verifica il cancello concedeva
    il completamento su una prova che sul lavoro svolto non diceva nulla.
    """

    def test_una_verifica_fallita_non_viene_coperta_da_un_altra(self):
        led = _ledger("Implementa il frontend del modulo")
        led.record_tool("write_file", {}, _scrittura("src/a.jsx"))
        led.record_tool("terminal", {"command": "npm run build"},
                        _comando("npm run build", ok=False, err="Cannot resolve @mui/material"))
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))

        esito = check_completion_allowed(led)
        self.assertFalse(esito["allowed"])
        self.assertIn("npm run build", esito["reason"])

    def test_correggere_la_verifica_fallita_sblocca(self):
        led = _ledger("Implementa il frontend del modulo")
        led.record_tool("write_file", {}, _scrittura("src/a.jsx"))
        led.record_tool("terminal", {"command": "npm run build"},
                        _comando("npm run build", ok=False, err="errore"))
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))
        led.record_tool("terminal", {"command": "npm run build"},
                        _comando("npm run build"))

        self.assertTrue(check_completion_allowed(led)["allowed"])

    def test_i_comandi_non_di_verifica_non_contano(self):
        """Un `ls` fallito non dice nulla sulla consegnabilita' del codice."""
        led = _ledger("Implementa il modulo")
        led.record_tool("write_file", {}, _scrittura())
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))
        led.record_tool("terminal", {"command": "ls cartella_inesistente"},
                        _comando("ls cartella_inesistente", ok=False, err="not found"))

        self.assertTrue(check_completion_allowed(led)["allowed"])


if __name__ == "__main__":
    unittest.main()


class TestFileNonCompilabili(unittest.TestCase):
    """Un file che non compila rende irrilevante ogni altra prova.

    La validazione AST dopo la scrittura segnala l'errore nel momento in cui
    nasce, invece di farlo scoprire venti turni dopo dentro l'output di pytest.
    Ma senza un cancello resterebbe un avviso: la scrittura torna comunque
    riuscita, e un test che non tocca quel file passa lo stesso.
    """

    @staticmethod
    def _scrittura_rotta(path="core/rotto.py"):
        return {
            "success": True, "path": f"{WS}/{path}", "lines_after": 3,
            "ast_valid": False,
            "ast_error": "Errore di sintassi Python (riga 1): invalid syntax",
        }

    def test_un_file_rotto_blocca_anche_con_i_test_verdi(self):
        led = _ledger("Implementa il modulo")
        led.record_tool("write_file", {}, self._scrittura_rotta())
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))

        esito = check_completion_allowed(led)
        self.assertFalse(esito["allowed"])
        self.assertIn("core/rotto.py", esito["reason"])

    def test_riscrivere_correttamente_sblocca(self):
        """Si giudica lo stato attuale del file, non la storia delle scritture."""
        led = _ledger("Implementa il modulo")
        led.record_tool("write_file", {}, self._scrittura_rotta())
        led.record_tool("write_file", {}, {
            "success": True, "path": f"{WS}/core/rotto.py",
            "lines_after": 3, "ast_valid": True,
        })
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        _comando("python -m pytest -q"))

        self.assertTrue(check_completion_allowed(led)["allowed"])

    def test_un_file_non_python_non_viene_giudicato(self):
        """`ast_valid` e' assente per jsx e css: assente non significa rotto."""
        led = _ledger("Implementa il frontend")
        led.record_tool("write_file", {}, {
            "success": True, "path": f"{WS}/src/a.jsx", "lines_after": 10,
        })
        led.record_tool("terminal", {"command": "npm run build"},
                        _comando("npm run build"))

        self.assertTrue(check_completion_allowed(led)["allowed"])

    def test_lo_stato_del_lavoro_segnala_il_file_rotto(self):
        led = _ledger("Implementa il modulo")
        led.record_tool("write_file", {}, self._scrittura_rotta())
        self.assertIn("NON COMPILA", led.render_state_block())


class TestGuardiaSvuotamento(unittest.TestCase):
    """Svuotare un file non e' una modifica: e' quasi sempre un incidente.

    Durante l'audit finale l'agente ha riscritto un `__init__.py` con contenuto
    vuoto. Nessuna guardia se n'e' accorta — un file vuoto e' Python valido,
    quindi la validazione di sintassi passa — e il difetto e' emerso solo come
    ImportError nella suite, su un modulo che un minuto prima funzionava.
    """

    def test_una_riscrittura_che_azzera_viene_riconosciuta(self):
        from core.developer_studio.fs_tools import would_truncate

        precedente = "# " + "x" * 400 + "\ndef f():\n    return 1\n"
        self.assertTrue(would_truncate(precedente, ""))
        self.assertTrue(would_truncate(precedente, "# nota\n"))

    def test_una_riscrittura_di_pari_dimensione_passa(self):
        from core.developer_studio.fs_tools import would_truncate

        precedente = "# " + "x" * 400 + "\ndef f():\n    return 1\n"
        nuova = "# " + "y" * 400 + "\ndef f():\n    return 2\n"
        self.assertFalse(would_truncate(precedente, nuova))

    def test_i_file_piccoli_non_sono_sorvegliati(self):
        """Sotto una certa soglia qualunque riscrittura e' plausibile."""
        from core.developer_studio.fs_tools import would_truncate

        self.assertFalse(would_truncate("x = 1\n", ""))


class TestProvaVisiva(unittest.TestCase):
    """Una schermata e' l'unica prova che risponde alle domande giuste.

    Il modulo Sigma Network ha superato ogni controllo automatico — nessuna
    dipendenza vietata, tema gestito, stati presenti, build verde, test verdi —
    ed era graficamente inaccettabile. Nessuna verifica testuale guardava il
    risultato.
    """

    def test_una_schermata_non_vuota_e_una_prova(self):
        led = _ledger("Implementa il frontend")
        led.record_tool("screenshot", {"url": "http://127.0.0.1:8000"}, {
            "success": True, "path": "/tmp/a.png", "bytes": 500_000,
            "likely_blank": False,
        })
        self.assertTrue(led.has_visual_proof())
        self.assertEqual(len(led.snapshot()["screenshots"]), 1)

    def test_una_pagina_bianca_non_e_una_prova(self):
        """Accettarla renderebbe il cancello sempre soddisfatto."""
        led = _ledger("Implementa il frontend")
        led.record_tool("screenshot", {}, {
            "success": True, "path": "/tmp/vuota.png", "bytes": 2_000,
            "likely_blank": True,
        })
        self.assertFalse(led.has_visual_proof())

    def test_uno_scatto_fallito_non_e_una_prova(self):
        led = _ledger("Implementa il frontend")
        led.record_tool("screenshot", {}, {
            "success": False, "error": "nessun browser trovato",
        })
        self.assertFalse(led.has_visual_proof())
