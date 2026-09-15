"""Un secondo tentativo che ricomincia da zero ripaga la stessa scoperta.

Il task `frontend` della Biblioteca e' stato tentato tre volte, ventisei turni
ciascuna. In tutte e tre il modello ha capito il problema e ha scritto da solo
la forma giusta del comando — la stessa che poi e' finita in
`adatta_alla_shell` — l'ha eseguita, ha ottenuto zero. Poi il run finiva, il
tentativo dopo partiva con la memoria vuota, e la scoperta veniva rifatta.
Ottanta turni per sapere tre volte la stessa cosa.

C'e' un secondo pezzo, ed e' quello che un umano fa senza accorgersene: se lo
stesso comando ha dato due esiti diversi, non e' il codice. Sulla Biblioteca
`node --test a.test.js b.test.js` dava zero e uno a giorni alterni, perche' i
due file giravano in processi paralleli sullo stesso archivio. Quel fatto era
gia' nel registro; nessuno calcolava la differenza.
"""

import pytest

from core.harness.lezioni import Lezione, estrai, incoerenze, racconta

COMANDO_ROTTO = "npm --prefix frontend install && npm --prefix frontend run build"
COMANDO_BUONO = "cd frontend; npm install; if ($LASTEXITCODE -eq 0) { npm run build }"
COMANDO_BALLERINO = "node --test index.test.js prestiti.test.js"


def _snapshot():
    return {
        "files": [{"path": "frontend/src/App.jsx", "writes": 1},
                  {"path": "backend/index.js", "reads": 3}],
        "commands": [
            {"command": COMANDO_ROTTO, "returncode": 1, "ok": False,
             "error": "build fallita"},
            {"command": COMANDO_BUONO, "returncode": 0, "ok": True},
            {"command": COMANDO_BALLERINO, "returncode": 0, "ok": True},
            {"command": COMANDO_BALLERINO, "returncode": 1, "ok": False,
             "error": "5 test falliti"},
        ],
        "requirements": [{"met": True}, {"met": True}, {"met": False}],
        "proposte_verifica": [{"accettata": True, "comando": COMANDO_BUONO}],
    }


class TestCosaSiTramanda:
    def test_i_comandi_che_hanno_funzionato(self):
        """E' la scoperta che e' stata rifatta tre volte."""
        l = estrai(1, _snapshot(), "non dimostrato", turni=26)
        assert COMANDO_BUONO in l.riusciti

    def test_i_comandi_falliti_col_loro_errore(self):
        l = estrai(1, _snapshot(), "", 26)
        assert any("build fallita" in f["errore"] for f in l.falliti)

    def test_i_file_gia_scritti_e_non_quelli_solo_letti(self):
        """«L'ho gia' scritto» e «l'ho guardato» portano a due mosse diverse."""
        l = estrai(1, _snapshot(), "", 26)
        assert "frontend/src/App.jsx" in l.file
        assert "backend/index.js" not in l.file

    def test_a_che_punto_erano_i_criteri(self):
        l = estrai(1, _snapshot(), "", 26)
        assert (l.criteri_ok, l.criteri_totali) == (2, 3)

    def test_la_prova_contestata(self):
        """Dice al tentativo dopo che il muro non era il lavoro, era il metro."""
        l = estrai(1, _snapshot(), "", 26)
        assert l.prova_sostituita == COMANDO_BUONO

    def test_uno_snapshot_vuoto_non_solleva(self):
        assert estrai(1, None, "", 0).file == []


class TestLoStessoComandoConEsitiDiversi:
    """Il ragionamento che un umano fa per primo e che nessuno qui faceva."""

    def test_viene_notato(self):
        note = incoerenze(_snapshot()["commands"])
        assert len(note) == 1
        assert COMANDO_BALLERINO in note[0]

    def test_dice_dove_NON_cercare(self):
        """Senza questa frase la nota e' un'osservazione; con, e' una diagnosi."""
        nota = incoerenze(_snapshot()["commands"])[0]
        assert "non sta nel codice" in nota

    def test_un_comando_sempre_uguale_a_se_stesso_non_e_una_nota(self):
        comandi = [{"command": "pytest", "returncode": 1, "ok": False},
                   {"command": "pytest", "returncode": 1, "ok": False}]
        assert incoerenze(comandi) == []

    def test_fallito_e_poi_riuscito_e_una_nota(self):
        """Puo' essere «l'ho riparato» ed e' il caso normale, ma puo' essere
        instabilita': merita una riga, non un allarme."""
        comandi = [{"command": "pytest", "returncode": 1, "ok": False},
                   {"command": "pytest", "returncode": 0, "ok": True}]
        assert len(incoerenze(comandi)) == 1

    def test_comandi_senza_testo_non_rompono_niente(self):
        assert incoerenze([{"returncode": 0}, {"command": "", "returncode": 1}]) == []


class TestComeSiLegge:
    def test_senza_lezioni_non_si_dice_niente(self):
        """Il primo tentativo non deve pagare il prezzo del prompt."""
        assert racconta([]) == ""
        assert racconta(None) == ""

    def test_dice_subito_di_non_ricominciare(self):
        testo = racconta([estrai(1, _snapshot(), "non dimostrato", 26)])
        assert "GIA' STATA TENTATA" in testo
        assert "Non ricominciare da zero" in testo

    def test_porta_dentro_il_comando_buono(self):
        testo = racconta([estrai(1, _snapshot(), "", 26)])
        assert COMANDO_BUONO in testo

    def test_porta_dentro_l_avviso_sull_instabilita(self):
        testo = racconta([estrai(1, _snapshot(), "", 26)])
        assert "ATTENZIONE" in testo

    def test_regge_i_dizionari_oltre_agli_oggetti(self):
        """Dalla coda tornano dizionari: sono passati da un file JSON."""
        grezza = estrai(1, _snapshot(), "", 26).to_dict()
        assert COMANDO_BUONO in racconta([grezza])

    def test_non_cresce_senza_fine(self):
        molte = [estrai(n, _snapshot(), "", 26) for n in range(1, 9)]
        testo = racconta(molte)
        assert testo.count("— Tentativo") <= 3


class TestLaCodaLeConserva:
    def test_si_annotano_e_si_rileggono(self, tmp_path, monkeypatch):
        from core.harness import workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        coda = workqueue.WorkQueue("prova_lezioni", goal="x")
        coda.add(title="fai una cosa", item_id="v1")
        coda.annota_lezione("v1", estrai(1, _snapshot(), "non dimostrato", 26))
        voce = [v for v in coda.items() if v.id == "v1"][0]
        assert voce.lezioni and voce.lezioni[0]["riusciti"]

    def test_sopravvivono_al_salvataggio(self, tmp_path, monkeypatch):
        """Il tentativo dopo puo' essere in un altro processo: se la lezione
        non passa dal disco, non passa affatto."""
        from core.harness import workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        coda = workqueue.WorkQueue("prova_lezioni2", goal="x")
        coda.add(title="fai una cosa", item_id="v1")
        coda.annota_lezione("v1", estrai(1, _snapshot(), "non dimostrato", 26))

        riletta = workqueue.WorkQueue("prova_lezioni2", goal="x")
        voce = [v for v in riletta.items() if v.id == "v1"][0]
        assert voce.lezioni[0]["prova_sostituita"] == COMANDO_BUONO

    def test_una_voce_che_non_esiste_non_solleva(self, tmp_path, monkeypatch):
        from core.harness import workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        coda = workqueue.WorkQueue("prova_lezioni3", goal="x")
        assert coda.annota_lezione("inesistente", Lezione(tentativo=1)) is False


class TestEDavveroCollegato:
    """Il difetto ricorrente di questo progetto e' la capacita' scritta e mai
    raggiunta."""

    def test_il_prompt_della_voce_le_legge(self):
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout._prompt_voce)
        assert "racconta(" in sorgente

    def test_stanno_in_cima_dove_si_leggono(self, tmp_path, monkeypatch):
        from core.harness import fanout, workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        coda = workqueue.WorkQueue("prova_prompt", goal="obiettivo generale")
        coda.add(title="IL COMPITO", item_id="v1", payload={"verify": "pytest"})
        coda.annota_lezione("v1", estrai(1, _snapshot(), "non dimostrato", 26))
        voce = [v for v in coda.items() if v.id == "v1"][0]

        testo = fanout._prompt_voce(voce, "obiettivo generale", "prova_prompt")
        assert "GIA' STATA TENTATA" in testo
        assert testo.index("GIA' STATA TENTATA") < testo.index("VERIFICA RICHIESTA")

    def test_la_lezione_si_scrive_prima_che_la_voce_torni_in_coda(self):
        """Dopo `fail` la voce e' di nuovo disponibile e un altro lavoratore
        puo' averla presa: la lezione arriverebbe tardi."""
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout._esegui_voce)
        assert sorgente.index("_tramanda(coda, voce, esito, ultimo_stato)") < sorgente.index(
            "coda.fail(voce.id, esito.error)\n    return esito")


class TestSiVedeAncheDurante:
    """Accorgersene al tentativo dopo salva il tentativo dopo. Accorgersene
    adesso salva questo."""

    def _ledger_ballerino(self, tmp_path):
        from core.harness.ledger import DevSessionLedger

        L = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        for rc, ok in ((0, True), (1, False)):
            L.record_tool("terminal", {"command": COMANDO_BALLERINO},
                          {"tool": "terminal", "success": ok, "returncode": rc,
                           "command": COMANDO_BALLERINO,
                           "error": "" if ok else "5 test falliti"})
        return L

    def test_il_blocco_di_stato_lo_dice(self, tmp_path):
        stato = self._ledger_ballerino(tmp_path).render_state_block()
        assert "esiti diversi" in stato

    def test_e_dice_dove_non_cercare(self, tmp_path):
        stato = self._ledger_ballerino(tmp_path).render_state_block()
        assert "non sta nel codice" in stato

    def test_un_run_regolare_non_paga_niente(self, tmp_path):
        from core.harness.ledger import DevSessionLedger

        L = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        L.record_tool("terminal", {"command": "pytest"},
                      {"tool": "terminal", "success": True, "returncode": 0,
                       "command": "pytest"})
        assert "esiti diversi" not in L.render_state_block()
