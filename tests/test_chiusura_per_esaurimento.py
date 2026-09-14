"""Finire i turni non vuol dire non aver finito il lavoro.

Il task `prestiti_api` della Biblioteca ha soddisfatto **tutti e sette** i
criteri di accettazione, ha eseguito il proprio comando di verifica con esito
zero — due volte — e poi e' morto al turno trentaquattro senza chiamare
`complete_goal`. Il registro lo dice riga per riga:

    requisiti: 7 su 7 met=true
    rc=0 ok=True  cd backend && npm install ... && node --test index.test.js prestiti.test.js
    status: stopped, turns: 34

La coda l'ha segnato «lavoro prodotto ma non dimostrato» e l'ha rimesso in
lavorazione da capo. Era dimostrato: mancava la firma, non la prova.

Qui non si allenta il cancello. Si pone al cancello la stessa domanda che gli
porrebbe `complete_goal`, e in piu' si pretende che il comando dichiarato dalla
voce sia proprio uno di quelli riusciti. Le prove non diventano meno vere
perche' e' finito il contatore dei turni.
"""

import pytest

from core.harness.ledger import DevSessionLedger
from core.harness.loop import _chiusura_per_esaurimento

VERIFICA = "cd backend && npm install --no-audit --no-fund && node --test index.test.js"


def _ledger_che_ha_finito(tmp_path, comando=VERIFICA):
    """Un run che ha scritto, verificato e soddisfatto i propri criteri."""
    ledger = DevSessionLedger(goal="aggiungi i prestiti", workspace_root=str(tmp_path))
    ledger.declare_verification(comando)
    ledger.record_tool(
        "write_file", {"path": "backend/index.js"},
        {"tool": "write_file", "success": True, "path": "backend/index.js"})
    ledger.record_tool(
        "terminal", {"command": comando},
        {"tool": "terminal", "success": True, "returncode": 0,
         "command": comando, "stdout": "# pass 10 # fail 0"})
    return ledger


class TestQuandoSiPuoChiudere:
    def test_il_caso_vero(self, tmp_path):
        assert _chiusura_per_esaurimento(_ledger_che_ha_finito(tmp_path), VERIFICA) is not None

    def test_senza_un_comando_dichiarato_decide_il_cancello(self, tmp_path):
        assert _chiusura_per_esaurimento(_ledger_che_ha_finito(tmp_path), "") is not None


class TestQuandoNonSiPuo:
    def test_se_il_cancello_dice_no(self, tmp_path):
        """Scritture senza nessuna verifica: e' esattamente cio' che il
        cancello esiste per fermare, e i turni finiti non lo cambiano."""
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        ledger.record_tool(
            "write_file", {"path": "a.py"},
            {"tool": "write_file", "success": True, "path": "a.py"})
        assert _chiusura_per_esaurimento(ledger, VERIFICA) is None

    def test_se_e_passato_un_altro_comando(self, tmp_path):
        """«Qualcosa e' verde» non e' «la prova che avevo promesso e' verde».
        Il piano diceva come si dimostra questo lavoro: vale quella."""
        ledger = _ledger_che_ha_finito(tmp_path, comando="node --version")
        assert _chiusura_per_esaurimento(ledger, VERIFICA) is None

    def test_un_criterio_aperto_tiene_chiuso(self, tmp_path):
        ledger = _ledger_che_ha_finito(tmp_path)
        ledger.set_spec("aggiungi i prestiti",
                        ["le rotte rispondono 401 senza token"])
        assert _chiusura_per_esaurimento(ledger, VERIFICA) is None

    def test_un_ledger_rotto_non_fa_esplodere_la_chiusura(self):
        class Rotto:
            def __getattr__(self, nome):
                raise RuntimeError("registro illeggibile")

        assert _chiusura_per_esaurimento(Rotto(), VERIFICA) is None


class TestEDavveroCollegata:
    def test_il_ciclo_la_chiama_quando_i_turni_finiscono(self):
        import inspect

        from core.harness import loop

        sorgente = inspect.getsource(loop._stream_agent_turn_impl)
        assert "_chiusura_per_esaurimento(ledger, verify_command)" in sorgente
        i = sorgente.index("_chiusura_per_esaurimento(ledger, verify_command)")
        assert "current_turn >= max_turns" in sorgente[max(0, i - 400):i]

    def test_la_chiusura_si_vede(self):
        """Una chiusura d'ufficio che non si distingue da una normale
        toglierebbe il solo modo di accorgersi che i turni sono stretti."""
        import inspect

        from core.harness import loop

        sorgente = inspect.getsource(loop._stream_agent_turn_impl)
        i = sorgente.index("_chiusura_per_esaurimento(ledger, verify_command)")
        assert "per_esaurimento" in sorgente[i:i + 800]
