"""Chi ha scritto il codice, davanti a un test rosso, corregge il codice.

È naturale, ed è spesso la mossa sbagliata. Stanotte le cause vere sono state,
in ordine: la shell che non sapeva leggere `&&`, il protocollo delle chiamate,
una porta occupata, due file di test che giravano in parallelo sullo stesso
archivio. **Il codice quasi mai.**

Il sistema però, quando le regole non sapevano rispondere, mandava un Coder —
cioè qualcuno il cui mestiere è rimettere mano al sorgente. Il Diagnosta non ha
scritto niente e non può scrivere: non ha investito nell'ipotesi, ed è l'unica
ragione per cui vede i livelli che un autore non guarda.

Le regole restano davanti a lui. I casi netti costano zero, un modello costa un
minuto: lo si paga solo dove nessuna regola ha saputo rispondere.
"""

import pytest

from core.harness.roles import DEV_ROLES


@pytest.fixture
def diagnosta():
    return DEV_ROLES["diagnosta"]


class TestCosaPuoFare:
    def test_esiste_ed_e_registrato(self, diagnosta):
        assert diagnosta.id == "diagnosta"

    def test_non_puo_scrivere_niente(self, diagnosta):
        """È tutto il senso del ruolo: chi può riparare ripara, e riparando
        smette di cercare la causa."""
        vietati = {"write_file", "edit_file", "append_file", "delete", "restore_file"}
        assert not (set(diagnosta.tools) & vietati)

    def test_ma_puo_eseguire(self, diagnosta):
        """Un guasto che non hai visto accadere è una congettura. Senza
        `terminal` si può solo congetturare."""
        assert "terminal" in diagnosta.tools

    def test_e_puo_leggere_e_cercare(self, diagnosta):
        assert {"read_file", "search_code"} <= set(diagnosta.tools)

    def test_e_puo_chiudere(self, diagnosta):
        assert "complete_goal" in diagnosta.tools


class TestCosaGliEStatoInsegnato:
    def test_i_cinque_livelli_ci_sono_tutti(self, diagnosta):
        p = diagnosta.system_prompt
        for livello in ("LA PROVA", "L'AMBIENTE", "IL TEST", "IL CODICE", "IL COMPITO"):
            assert livello in p

    def test_il_codice_non_e_la_prima_ipotesi(self, diagnosta):
        """È l'errore che il ruolo esiste per evitare."""
        p = diagnosta.system_prompt
        assert p.index("**LA PROVA**") < p.index("**IL CODICE**")
        assert "ultima ipotesi, non la prima" in p

    def test_sa_riconoscere_un_guasto_che_non_sta_nel_codice(self, diagnosta):
        """Stesso comando, esiti diversi: è la firma che stanotte nessuno
        leggeva, ed è quella che avrebbe smascherato i test paralleli."""
        p = diagnosta.system_prompt
        assert "esiti diversi" in p
        assert "non è lì" in p

    def test_gli_e_permesso_non_sapere(self, diagnosta):
        """Una causa inventata costa più di un «non lo so»: ha la forma di una
        diagnosi e il contenuto di un'immaginazione."""
        assert "Non lo so" in diagnosta.system_prompt

    def test_non_deve_progettare_la_riparazione(self, diagnosta):
        assert "Chi ripara decide come" in diagnosta.system_prompt

    def test_la_temperatura_e_bassa(self, diagnosta):
        """Da un diagnosta si vuole la stessa risposta due volte."""
        assert diagnosta.temperature <= 0.2


class TestIlSuoCompletamentoNonVieneRifiutato:
    """Non modificare niente è il suo mestiere: se il cancello lo trattasse
    come un Coder che non ha scritto, non potrebbe mai chiudere."""

    def test_un_obiettivo_di_diagnosi_conta_come_analisi(self):
        from core.harness.ledger import DevSessionLedger

        ledger = DevSessionLedger(
            goal="Diagnosi del task «prestiti_api»: di' a che livello sta il guasto")
        assert ledger.is_exploration_task() is True

    def test_e_lo_stesso_per_la_parola_diagnostica(self):
        from core.harness.ledger import DevSessionLedger

        assert DevSessionLedger(goal="diagnostica il fallimento").is_exploration_task()

    def test_un_compito_di_scrittura_resta_un_compito_di_scrittura(self):
        """La parola in più non deve aprire una scorciatoia a chi deve produrre."""
        from core.harness.ledger import DevSessionLedger

        ledger = DevSessionLedger(goal="diagnostica il guasto e correggi index.js")
        assert ledger.is_exploration_task() is False


class TestQuandoVieneChiamato:
    """Un ruolo che nessuno invoca è una capacità scritta e mai raggiunta —
    il difetto ricorrente di questo progetto."""

    def _diagnosi_senza_causa(self):
        from core.harness.autocorrezione import Bilancio, diagnostica

        class Task:
            id = "t1"
            title = "fai una cosa"
            files = ["a.js"]
            error = "fallito"

        snapshot = {
            "files": [{"path": "a.js", "writes": 1}],
            "commands": [{"command": "npm test", "returncode": 1, "ok": False}],
        }
        return diagnostica(Task(), snapshot, Bilancio())

    def test_il_cassetto_senza_causa_chiama_il_diagnosta(self):
        """È dove finiva il caso `&&`, e da lì partiva un Coder a rimettere
        mano a del codice che stava bene."""
        assert self._diagnosi_senza_causa().ruolo == "diagnosta"

    def test_e_gli_dice_di_non_riparare(self):
        assert "Non riparare" in self._diagnosi_senza_causa().istruzione

    def test_e_gli_indica_la_pista_giusta(self):
        assert "esiti diversi" in self._diagnosi_senza_causa().istruzione

    def test_le_regole_restano_davanti(self):
        """Un file scritto in questa sessione che non compila ha una causa
        netta: si sa il file, si sa l'errore, e chiamare un modello per
        saperlo sarebbe pagare un minuto per niente."""
        from core.harness.autocorrezione import Bilancio, diagnostica

        class Task:
            id = "t1"
            title = "fai una cosa"
            files = ["a.py"]
            error = "fallito"

        snapshot = {
            "files": [{"path": "a.py", "writes": 1,
                       "syntax_error": "SyntaxError: invalid syntax (riga 12)"}],
            "commands": [],
        }
        assert diagnostica(Task(), snapshot, Bilancio()).ruolo != "diagnosta"
