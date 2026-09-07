"""Un controllo scritto per il progetto vale come prova, se dice cosa ha esaminato.

Il cancello di completamento pretende prove ancorate a fatti, e finora le sapeva
riconoscere solo in una suite di test. Ci sono lavori la cui prova non e' una
suite: che ogni chiave di traduzione esista in ogni lingua e che non resti
nessun letterale non tradotto non lo dimostra pytest. Senza un modo di credere a
quel controllo, l'agente dichiarerebbe finito un lavoro che nessuno ha misurato.

Il contratto e' una riga sola:

    SIGMA-CHECK {"check": "i18n", "checked": 214, "problems": 0}

`checked` non e' decorazione, ed e' il punto di tutto il file: un controllo che
non ha esaminato niente esce con codice zero esattamente come uno che ha
esaminato tutto senza trovare nulla. E' la stessa regola per cui una suite con
zero test raccolti qui non passa — la differenza fra una prova e un'illusione.
"""

import pytest

from core.harness.ledger import looks_like_verification
from core.harness.verification import parse_verification


def _rapporto(**campi):
    import json
    return "SIGMA-CHECK " + json.dumps(campi)


class TestIlControlloVieneLetto:
    def test_un_controllo_pulito_e_una_prova(self):
        r = parse_verification(
            "python tools/check_i18n.py", 0,
            _rapporto(check="i18n", checked=214, problems=0),
        )
        assert r.kind == "project_check"
        assert r.is_valid is True
        assert r.collected == 214
        assert r.passed == 214
        assert "214" in r.summary

    def test_i_problemi_trovati_lo_rendono_non_valido(self):
        r = parse_verification(
            "python tools/check_i18n.py", 1,
            _rapporto(check="i18n", checked=214, problems=7),
        )
        assert r.is_valid is False
        assert r.failed == 7
        assert "7 problemi" in r.summary

    def test_problemi_con_codice_zero_restano_problemi(self):
        """Un controllo che trova guai e poi esce con zero e' un controllo
        scritto male, non un successo."""
        r = parse_verification(
            "python tools/check.py", 0,
            _rapporto(check="i18n", checked=10, problems=3),
        )
        assert r.is_valid is False

    def test_il_rapporto_puo_stare_in_mezzo_all_output(self):
        testo = (
            "Analizzo 214 file...\n"
            "  sigma_network/index.jsx: 12 stringhe\n"
            + _rapporto(check="i18n", checked=214, problems=0) + "\n"
            "Fatto.\n"
        )
        assert parse_verification("python check.py", 0, testo).is_valid is True

    def test_vale_l_ultimo_rapporto_emesso(self):
        """Un comando che ne stampa piu' d'uno sta riportando fasi diverse:
        quella che conta e' l'ultima."""
        testo = (
            _rapporto(check="parziale", checked=10, problems=4) + "\n"
            + _rapporto(check="i18n", checked=214, problems=0)
        )
        r = parse_verification("python check.py", 0, testo)
        assert r.is_valid is True
        assert r.collected == 214


class TestUnControlloAVuotoNonDimostraNiente:
    """Il difetto che questo parser esiste per impedire."""

    def test_zero_elementi_esaminati_non_e_una_prova(self):
        r = parse_verification(
            "python tools/check_i18n.py", 0,
            _rapporto(check="i18n", checked=0, problems=0),
        )
        assert r.is_valid is False
        assert "non ha esaminato nulla" in r.summary

    def test_un_controllo_senza_rapporto_non_viene_creduto(self):
        """Uscire con zero e stampare «tutto ok» non e' una misura."""
        r = parse_verification("python tools/check_i18n.py", 0, "tutto ok!")
        assert r.is_valid is False
        assert "SIGMA-CHECK" in r.summary

    def test_un_rapporto_malformato_non_viene_creduto(self):
        r = parse_verification("python check.py", 0, "SIGMA-CHECK {non json}")
        assert r.is_valid is False
        assert "JSON" in r.summary


class TestIlCancelloLoRiconosce:
    """Il parser serve a poco se il ledger non conta quel comando fra le
    verifiche: sarebbe un rapporto letto da nessuno."""

    @pytest.mark.parametrize("comando", [
        "python tools/check_i18n.py",
        "python tools/check.py --strict",
        "npm run check",
        "python -m tools.verifica_lingue",
    ])
    def test_un_controllo_conta_come_verifica(self, comando):
        assert looks_like_verification(comando) is True

    def test_un_comando_che_scrive_non_conta_neanche_se_si_chiama_check(self):
        """La regola che aveva gia' bruciato dieci turni su un run vero: un
        comando che modifica il workspace non ne e' una verifica."""
        assert looks_like_verification(
            'python -c "import pathlib; pathlib.Path(\'check.py\').write_text(x)"'
        ) is False


class TestIlLedgerRegistraIlRapporto:
    def test_un_controllo_verde_sblocca_il_cancello(self, tmp_path):
        from core.harness.ledger import DevSessionLedger, check_completion_allowed

        led = DevSessionLedger(goal="tradurre l'interfaccia", workspace_root=str(tmp_path))
        led.set_spec("i18n", ["ogni chiave esiste in ogni lingua"])
        led.record_tool("write_file", {"path": "a.jsx"},
                        {"success": True, "path": str(tmp_path / "a.jsx")})
        led.record_tool(
            "terminal", {"command": "python tools/check_i18n.py"},
            {"success": True, "returncode": 0, "command": "python tools/check_i18n.py",
             "stdout": _rapporto(check="i18n", checked=214, problems=0), "stderr": ""},
        )

        ultima = led.last_verification()
        assert ultima is not None, "il controllo non e' stato registrato come verifica"
        assert ultima["ok"] is True
        assert (ultima.get("verification") or {}).get("kind") == "project_check"

    def test_un_controllo_a_vuoto_non_sblocca_il_cancello(self, tmp_path):
        from core.harness.ledger import DevSessionLedger

        led = DevSessionLedger(goal="tradurre l'interfaccia", workspace_root=str(tmp_path))
        led.record_tool("write_file", {"path": "a.jsx"},
                        {"success": True, "path": str(tmp_path / "a.jsx")})
        led.record_tool(
            "terminal", {"command": "python tools/check_i18n.py"},
            {"success": True, "returncode": 0, "command": "python tools/check_i18n.py",
             "stdout": _rapporto(check="i18n", checked=0, problems=0), "stderr": ""},
        )

        ultima = led.last_verification()
        assert ultima is not None
        assert ultima["ok"] is False, "un controllo a vuoto non deve valere come prova"
