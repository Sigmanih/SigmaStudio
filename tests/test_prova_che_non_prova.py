"""Cercare una parola in un sorgente dice che la parola c'e', e nient'altro.

Lasciati liberi di pianificare, gli agenti si sono scritti da soli una voce
«aggiungi l'accesso demo» con questa prova:

    cd frontend && npm run build && grep -q 'demo' src/App.jsx

E mentre lavoravano, `App.jsx` conteneva una funzione `inviaDemo` che nessun
bottone chiamava. Codice morto, e il `grep` sarebbe passato lo stesso.

Il cancello di completamento pretende una verifica riuscita, ma non sapeva
distinguere una verifica che **esegue** da una che **guarda**. E una prova
dichiarata nella voce valeva per definizione: chi scrive la voce puo'
sbagliarsi, e dichiarare come si dimostra una cosa non rende dimostrabile cio'
che non lo e'.

Tre difese, e la terza e' quella che tiene in piedi il sistema: l'avviso
arriva a chi pianifica prima che si lavori; una prova debole non conta piu';
e chi si trova con una prova debole gia' scritta ha una via d'uscita — la
propone, e se quella nuova esegue davvero ed e' passata, vale.
"""

import tempfile

import pytest

from core.harness.ledger import DevSessionLedger, prova_debole
from core.harness.loop import execute_admin_tool

DEBOLE = "grep -q 'demo' src/App.jsx"
FORTE = "cd frontend && npm run build"


class TestCosaGuardaEcosaEsegue:
    @pytest.mark.parametrize("comando", [
        "grep -q 'demo' src/App.jsx",
        "findstr /C:demo src\\App.jsx",
        "test -d dist",
        "test -f backend/index.js",
        "ls frontend/src",
        "cat package.json",
        "echo fatto",
        "grep -c token src/App.jsx | wc -l",
        "cd backend; grep -q x index.js",
    ])
    def test_queste_guardano_e_basta(self, comando):
        assert prova_debole(comando)

    @pytest.mark.parametrize("comando", [
        "cd frontend && npm run build",
        "node --test backend/index.test.js",
        "pytest tests/",
        "docker compose up -d && curl -s http://localhost:8080",
        # Una catena dove UN pezzo esegue e' una catena che esegue: il `grep`
        # in coda e' un dettaglio in piu', non il cuore della prova.
        "cd frontend && npm run build && grep -q 'demo' src/App.jsx",
    ])
    def test_queste_mettono_in_moto_qualcosa(self, comando):
        assert prova_debole(comando) == ""

    def test_il_motivo_spiega_il_difetto(self):
        """Un rifiuto senza il perche' si ripete identico."""
        motivo = prova_debole(DEBOLE)
        assert "invece di eseguire" in motivo
        assert "mai chiamato" in motivo

    def test_un_comando_vuoto_non_e_una_prova(self):
        assert prova_debole("")


class TestIlCancelloNonLaAccettaPiu:
    def test_nemmeno_se_e_dichiarata(self, tmp_path):
        """Chi scrive la voce puo' sbagliarsi. Dichiarare come si dimostra una
        cosa non rende dimostrabile cio' che non lo e'."""
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        ledger.declare_verification(DEBOLE)
        assert ledger.counts_as_verification(DEBOLE) is False

    def test_mentre_una_prova_vera_dichiarata_vale(self, tmp_path):
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        ledger.declare_verification(FORTE)
        assert ledger.counts_as_verification(FORTE) is True


class TestLaViaDUscita:
    """Chiudere la porta senza aprirne un'altra bloccherebbe una voce che
    l'agente non ha scritto e non puo' cambiare."""

    def _con_prova_debole(self, tmp_path):
        ledger = DevSessionLedger(goal="accesso demo", workspace_root=str(tmp_path))
        ledger.declare_verification(DEBOLE)
        ledger.record_tool("terminal", {"command": DEBOLE},
                           {"tool": "terminal", "success": True, "returncode": 0,
                            "command": DEBOLE})
        return ledger

    def test_una_prova_vera_gia_passata_prende_il_posto(self, tmp_path):
        ledger = self._con_prova_debole(tmp_path)
        ledger.record_tool("terminal", {"command": FORTE},
                           {"tool": "terminal", "success": True, "returncode": 0,
                            "command": FORTE})
        esito = ledger.proponi_verifica(FORTE, "il grep passa anche su codice morto")
        assert esito["accettata"] is True
        assert "guardava un file" in esito["perche"]
        assert ledger.counts_as_verification(FORTE) is True

    def test_ma_non_una_prova_debole_al_posto_di_un_altra(self, tmp_path):
        ledger = self._con_prova_debole(tmp_path)
        ledger.record_tool("terminal", {"command": "echo ok"},
                           {"tool": "terminal", "success": True, "returncode": 0,
                            "command": "echo ok"})
        esito = ledger.proponi_verifica("echo ok", "cosi' passa")
        assert esito["accettata"] is False

    def test_e_non_una_che_nessuno_ha_visto_girare(self, tmp_path):
        ledger = self._con_prova_debole(tmp_path)
        assert ledger.proponi_verifica(FORTE, "questa e' meglio")["accettata"] is False


class TestChiPianificaLoSaSubito:
    """Correggere la prova mentre si pianifica costa una riga. Scoprirlo a
    valle costa un run."""

    def _avvisi(self, verify):
        from unittest import mock

        from core import paths
        from core.harness import workqueue

        with tempfile.TemporaryDirectory() as t:
            with mock.patch.object(paths, "var_dir", lambda: t):
                workqueue.forget_queue("prova_avvisi")
                esito = execute_admin_tool("queue_add", {
                    "queue_id": "prova_avvisi",
                    "items": [{"id": "a", "title": "fai una cosa", "verify": verify}],
                }, t)
                return esito.get("warnings") or []

    def test_una_prova_debole_viene_segnalata(self):
        avvisi = self._avvisi(DEBOLE)
        assert avvisi and "invece di eseguire" in avvisi[0]

    def test_e_si_dice_cosa_metterci(self):
        """Segnalare senza indicare l'alternativa lascia il problema intero."""
        avvisi = self._avvisi(DEBOLE)
        assert "un test, una build" in avvisi[0]

    def test_una_prova_vera_non_produce_rumore(self):
        assert self._avvisi(FORTE) == []

    def test_una_voce_senza_prova_non_viene_segnalata_qui(self):
        """Chi non dichiara la verifica la deve trovare da se': lo dice gia'
        il prompt della voce, e ripeterlo qui sarebbe rumore."""
        assert self._avvisi("") == []


class TestQuandoUnLavoroEsisteGia:
    """Il pianificatore vede i file, non la storia.

    Gli agenti si sono scritti una voce «scrivi backend/test.js» mentre nella
    stessa cartella c'erano gia' `index.test.js`, `prestiti.test.js` e
    `dati.test.js` con tredici test verdi. Ne sono nati sei file di test dove
    ce n'erano tre, e uno — `models.test.js` — con dentro zero test.
    """

    def _avvisi(self, files, presenti=("index.test.js", "prestiti.test.js", "dati.test.js")):
        import os
        from unittest import mock

        from core import paths
        from core.harness import workqueue

        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "backend"))
            for nome in presenti:
                open(os.path.join(t, "backend", nome), "w").write("//")
            with mock.patch.object(paths, "var_dir", lambda: t):
                workqueue.forget_queue("prova_doppioni")
                esito = execute_admin_tool("queue_add", {
                    "queue_id": "prova_doppioni",
                    "items": [{"id": "a", "title": "fai una cosa", "files": list(files)}],
                }, t)
                return esito.get("warnings") or []

    def test_un_file_nuovo_fra_fratelli_viene_segnalato(self):
        avvisi = self._avvisi(["backend/test.js"])
        assert avvisi and "index.test.js" in avvisi[0]

    def test_e_si_dice_cosa_farne(self):
        avvisi = self._avvisi(["backend/test.js"])
        assert "Guardali prima" in avvisi[0]

    def test_modificare_un_file_che_esiste_non_e_lavoro_doppio(self):
        assert self._avvisi(["backend/index.test.js"]) == []

    def test_un_file_senza_fratelli_non_produce_rumore(self):
        assert self._avvisi(["backend/cache.js"]) == []

    def test_una_cartella_che_non_esiste_non_solleva(self):
        assert self._avvisi(["servizi/nuovo/roba.js"]) == []

    def test_una_voce_senza_file_non_solleva(self):
        assert self._avvisi([]) == []
