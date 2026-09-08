"""La prova che il sistema chiede deve essere quella che il sistema riconosce.

Difetto trovato dal vivo, e il piu' insidioso di questa sessione perche' era
il sistema a contraddirsi. La sequenza:

1. la voce della coda dice «esegui `python -m json.tool locales/it.json`»;
2. il prompt la riporta all'agente come VERIFICA RICHIESTA;
3. l'agente scrive il file e esegue quel comando, che esce con codice 0;
4. il cancello di completamento risponde «hai modificato dei file ma non hai
   ancora VERIFICATO nulla».

`looks_like_verification` cerca indizi noti — pytest, eslint, py_compile — e
`json.tool` non e' fra quelli. Il sistema chiedeva una prova, indicava quale, e
poi non la riconosceva. Quattordici turni per un file scritto al secondo.

Allargare l'elenco a indovinare sarebbe il rimedio sbagliato: non esiste un
elenco di tutti i modi legittimi di dimostrare qualcosa, e ogni allargamento
avvicina il punto in cui un comando qualunque passa per verifica. Chi assegna
il lavoro invece **sa** come si dimostra, e ora puo' dirlo.
"""

import inspect

import pytest

from core.harness.ledger import DevSessionLedger


@pytest.fixture
def ledger(tmp_path):
    return DevSessionLedger(goal="creare i file di lingua", workspace_root=str(tmp_path))


class TestUnaProvaDichiarata:
    def test_un_comando_non_riconosciuto_non_vale_da_solo(self, ledger):
        assert ledger.counts_as_verification("python -m json.tool locales/it.json") is False

    def test_dichiararlo_lo_rende_una_prova(self, ledger):
        ledger.declare_verification("python -m json.tool locales/it.json")
        assert ledger.counts_as_verification("python -m json.tool locales/it.json") is True

    def test_vale_anche_se_il_comando_ha_qualcosa_intorno(self, ledger):
        """L'agente lo riscrive a modo suo: con `cd`, con le virgolette, con un
        percorso assoluto. Pretendere l'uguaglianza esatta lo farebbe fallire
        per un dettaglio che non cambia cosa il comando dimostra."""
        ledger.declare_verification("python -m json.tool locales/it.json")
        assert ledger.counts_as_verification(
            'cd progetto && python -m json.tool locales/it.json') is True

    def test_dichiararne_una_non_fa_passare_tutto(self, ledger):
        """Se bastasse dichiararne una per accettare qualsiasi cosa, il cancello
        non servirebbe piu' a niente."""
        ledger.declare_verification("python -m json.tool locales/it.json")
        assert ledger.counts_as_verification("echo fatto") is False
        assert ledger.counts_as_verification("git push") is False

    def test_le_verifiche_di_sempre_continuano_a_valere(self, ledger):
        for comando in ("python -m pytest", "npm run build", "npm run lint:undef"):
            assert ledger.counts_as_verification(comando) is True

    def test_una_dichiarazione_vuota_non_apre_niente(self, ledger):
        ledger.declare_verification("   ")
        assert ledger.counts_as_verification("qualunque cosa") is False


class TestIlGiroCompleto:
    def test_il_comando_dichiarato_sblocca_il_cancello(self, tmp_path):
        """Il caso vero: scrivo un file, eseguo la prova dichiarata, chiudo."""
        ledger = DevSessionLedger(goal="creare locales/it.json",
                                  workspace_root=str(tmp_path))
        ledger.declare_verification("python -m json.tool locales/it.json")
        ledger.set_spec("creare il file", ["il file esiste ed e' JSON valido"])
        ledger.record_tool("write_file", {"path": "locales/it.json"},
                           {"success": True, "path": str(tmp_path / "locales/it.json")})
        ledger.record_tool(
            "terminal", {"command": "python -m json.tool locales/it.json"},
            {"success": True, "returncode": 0,
             "command": "python -m json.tool locales/it.json",
             "stdout": '{\n    "titolo": "Ciao"\n}', "stderr": ""},
        )

        ultima = ledger.last_verification()
        assert ultima is not None, "la prova dichiarata non e' stata registrata"
        assert ultima["ok"] is True

    def test_senza_dichiararla_resta_non_riconosciuta(self, tmp_path):
        """Il difetto, riprodotto: e' la stessa sequenza senza la dichiarazione."""
        ledger = DevSessionLedger(goal="creare locales/it.json",
                                  workspace_root=str(tmp_path))
        ledger.record_tool("write_file", {"path": "locales/it.json"},
                           {"success": True, "path": str(tmp_path / "locales/it.json")})
        ledger.record_tool(
            "terminal", {"command": "python -m json.tool locales/it.json"},
            {"success": True, "returncode": 0,
             "command": "python -m json.tool locales/it.json",
             "stdout": "{}", "stderr": ""},
        )
        assert ledger.last_verification() is None


class TestRaggiungibilita:
    """Il difetto ricorrente: scritto, testato, scollegato."""

    def test_il_ciclo_registra_la_prova_del_run(self):
        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "ledger.declare_verification(verify_command)" in sorgente

    def test_il_ventaglio_passa_la_prova_della_voce(self):
        from core.harness import fanout

        sorgente = inspect.getsource(fanout._esegui_voce)
        assert "verify_command=verifica" in sorgente

    def test_anche_i_ruoli_la_passano(self):
        from core.harness.roles import RoleEngine

        parametri = inspect.signature(RoleEngine.generate_with_role).parameters
        assert "verify_command" in parametri
        assert "verify_command=verify_command" in inspect.getsource(
            RoleEngine.generate_with_role)
