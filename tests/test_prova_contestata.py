"""Una diagnosi senza il diritto di agirci sopra viene buttata.

Sul task `frontend` della Biblioteca il modello aveva capito tutto. Il registro
lo dimostra riga per riga: esegue la prova dichiarata e la shell la rifiuta,
riscrive il comando in una forma che PowerShell 5.1 accetta — la stessa che poi
e' finita in `adatta_alla_shell` — la esegue, ottiene zero, con il segno di
spunta di Vite nell'output.

Poi torna a sbattere sul comando dichiarato. Tre run, ventisei turni ciascuno.

Non era un difetto di ragionamento: il cancello era fuori dalla sua portata, e
il promemoria di verifica gli ripeteva ogni turno di eseguire proprio quello
rotto. Aveva ragione, il sistema gli ripeteva di avere torto, e il sistema
aveva l'ultima parola.

L'accettazione automatica e' stretta apposta, e sono due condizioni che una
macchina sa controllare: la prova dichiarata dev'essere stata **rifiutata dalla
shell**, e quella proposta dev'essere gia' stata **eseguita con successo** qui
dentro. Insieme coprono il caso che e' costato ottanta turni. Fuori di li' la
proposta si registra e si mostra: cambiarsi l'esame da soli e' come non darlo.
"""

import pytest

from core.harness.ledger import DevSessionLedger
from core.harness.loop import execute_admin_tool

DICHIARATO = "npm --prefix frontend install --no-audit --no-fund && npm --prefix frontend run build"
PROPOSTO = "cd frontend; npm install --no-audit --no-fund; if ($LASTEXITCODE -eq 0) { npm run build }"

RIFIUTO_SHELL = (
    "Il token '&&' non e' un separatore di istruzioni valido in questa versione.\n"
    "    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordException\n"
    "    + FullyQualifiedErrorId : InvalidEndOfLine"
)


def _ledger(tmp_path):
    L = DevSessionLedger(goal="fai il frontend", workspace_root=str(tmp_path))
    L.declare_verification(DICHIARATO)
    return L


def _la_shell_rifiuta(L):
    L.record_tool("terminal", {"command": DICHIARATO},
                  {"tool": "terminal", "success": False, "returncode": 1,
                   "command": DICHIARATO, "stderr": RIFIUTO_SHELL})


def _la_proposta_passa(L):
    L.record_tool("terminal", {"command": PROPOSTO},
                  {"tool": "terminal", "success": True, "returncode": 0,
                   "command": PROPOSTO, "stdout": "built in 801ms"})


class TestIlCasoCheECostatoOttantaTurni:
    def test_la_proposta_viene_accettata(self, tmp_path):
        L = _ledger(tmp_path)
        _la_shell_rifiuta(L)
        _la_proposta_passa(L)
        assert L.proponi_verifica(PROPOSTO, "PowerShell 5.1 non conosce &&")["accettata"]

    def test_e_da_quel_momento_e_lei_la_prova(self, tmp_path):
        """E' il punto: il cancello e il promemoria devono smettere di
        indicare il comando rotto."""
        L = _ledger(tmp_path)
        _la_shell_rifiuta(L)
        _la_proposta_passa(L)
        L.proponi_verifica(PROPOSTO, "il && non parte")
        assert L.counts_as_verification(PROPOSTO)

    def test_l_esito_dice_cosa_sostituisce(self, tmp_path):
        L = _ledger(tmp_path)
        _la_shell_rifiuta(L)
        _la_proposta_passa(L)
        esito = L.proponi_verifica(PROPOSTO, "il && non parte")
        assert DICHIARATO in esito["sostituisce"]


class TestQuandoNonSiAccetta:
    def test_se_la_prova_dichiarata_gira_e_fallisce(self, tmp_path):
        """E' il caso da NON coprire: un comando che parte e fallisce sta
        dicendo che il lavoro non e' finito, e va ascoltato."""
        L = _ledger(tmp_path)
        L.record_tool("terminal", {"command": DICHIARATO},
                      {"tool": "terminal", "success": False, "returncode": 1,
                       "command": DICHIARATO,
                       "stdout": "src/App.jsx:12 ERROR: Expected \")\""})
        _la_proposta_passa(L)
        esito = L.proponi_verifica(PROPOSTO, "non mi piace")
        assert esito["accettata"] is False
        assert "rifiutata dalla shell" in esito["perche"]

    def test_se_la_proposta_non_e_mai_stata_eseguita(self, tmp_path):
        """Altrimenti basterebbe proporre `echo ok`."""
        L = _ledger(tmp_path)
        _la_shell_rifiuta(L)
        esito = L.proponi_verifica("echo ok", "cosi' passa")
        assert esito["accettata"] is False
        assert "non e' ancora stato eseguito" in esito["perche"]

    def test_se_la_proposta_e_stata_eseguita_e_fallita(self, tmp_path):
        L = _ledger(tmp_path)
        _la_shell_rifiuta(L)
        L.record_tool("terminal", {"command": PROPOSTO},
                      {"tool": "terminal", "success": False, "returncode": 1,
                       "command": PROPOSTO, "error": "build fallita"})
        assert L.proponi_verifica(PROPOSTO, "x")["accettata"] is False

    def test_senza_comando_non_succede_niente(self, tmp_path):
        assert _ledger(tmp_path).proponi_verifica("", "x")["accettata"] is False


class TestRestaTracciaComunque:
    def test_anche_una_proposta_respinta_si_vede(self, tmp_path):
        """E' il segnale che l'agente credeva che il metro fosse sbagliato:
        se ha torto e' comunque cio' che serve sapere per capire il run."""
        L = _ledger(tmp_path)
        L.proponi_verifica("echo ok", "secondo me e' rotto")
        proposte = L.proposte_di_verifica()
        assert len(proposte) == 1 and proposte[0]["accettata"] is False

    def test_arrivano_nello_snapshot(self, tmp_path):
        """Da li' le raccoglie la lezione per il tentativo dopo."""
        L = _ledger(tmp_path)
        _la_shell_rifiuta(L)
        _la_proposta_passa(L)
        L.proponi_verifica(PROPOSTO, "il && non parte")
        assert L.snapshot()["proposte_verifica"][0]["accettata"] is True

    def test_non_crescono_senza_fine(self, tmp_path):
        L = _ledger(tmp_path)
        for n in range(9):
            L.proponi_verifica(f"comando {n}", "x")
        assert len(L.proposte_di_verifica()) <= 5


class TestIlToolERaggiungibile:
    def test_e_nel_catalogo(self):
        from core.harness.tool_schema import TOOL_SCHEMAS

        assert "propose_verify" in [s["function"]["name"] for s in TOOL_SCHEMAS]

    def test_normalizza_e_non_tocca_il_workspace(self, tmp_path):
        esito = execute_admin_tool(
            "propose_verify", {"command": PROPOSTO, "reason": "il && non parte"},
            str(tmp_path))
        assert esito["success"] is True
        assert esito["command"] == PROPOSTO

    def test_senza_motivo_viene_rifiutato(self, tmp_path):
        """Una prova sostituita senza il perche' e' una prova annacquata."""
        esito = execute_admin_tool(
            "propose_verify", {"command": PROPOSTO}, str(tmp_path))
        assert esito["success"] is False
        assert "reason" in esito["error"]

    def test_il_ciclo_lo_applica_al_registro(self):
        import inspect

        from core.harness import loop

        sorgente = inspect.getsource(loop._stream_agent_turn_impl)
        assert "ledger.proponi_verifica(" in sorgente

    def test_e_aggiorna_il_comando_del_promemoria(self):
        """Senza questa riga il promemoria continuerebbe a indicare il comando
        rotto, che e' esattamente cio' che rimandava l'agente contro il muro."""
        import inspect

        from core.harness import loop

        sorgente = inspect.getsource(loop._stream_agent_turn_impl)
        i = sorgente.index("ledger.proponi_verifica(")
        assert "verify_command = esito[" in sorgente[i:i + 600]

    def test_la_voce_della_coda_lo_insegna(self):
        """Un tool che nessuno sa di avere non viene usato."""
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout._prompt_voce)
        assert "propose_verify" in sorgente
