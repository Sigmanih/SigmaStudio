"""Lo stato di lavoro sopravvive alla richiesta HTTP, o non serve a niente.

Il ledger nasceva e moriva dentro una richiesta: un refresh del browser e
l'agente rileggeva i file che aveva appena letto, rieseguiva le verifiche che
erano appena passate. Questi test coprono le due meta' del rimedio — la
serializzazione che non deve perdere pezzi, e il ripristino che non deve
riprendere lo stato sbagliato.

Il caso pericoloso e' il secondo: uno stato che parla dei file di un altro
progetto e' peggio di nessuno stato, perche' l'agente ci crede.
"""

import pytest

from core.developer_studio import session_store
from core.developer_studio.session_ledger import DevSessionLedger

WS = "C:/progetto"


@pytest.fixture
def store_isolato(tmp_path, monkeypatch):
    """Reindirizza lo store su una cartella temporanea."""
    cartella = tmp_path / "dev_sessions"
    monkeypatch.setattr(session_store, "dev_sessions_dir", lambda: cartella)
    monkeypatch.setattr(session_store, "SAVE_INTERVAL_S", 0.0)
    session_store._last_save.clear()
    return cartella


def _ledger_lavorato(goal="Correggi core/x.py", root=WS):
    """Un ledger con dentro un po' di lavoro vero."""
    ledger = DevSessionLedger(goal=goal, workspace_root=root)
    ledger.record_tool(
        "read_file",
        {"path": f"{root}/core/x.py"},
        {"success": True, "path": f"{root}/core/x.py", "offset": 1,
         "last_line": 40, "total_lines": 40,
         "content": "def somma(a, b):\n    return a + b\n"},
    )
    ledger.record_tool(
        "write_file",
        {"path": f"{root}/core/x.py"},
        {"success": True, "path": f"{root}/core/x.py", "lines_after": 42},
    )
    ledger.record_tool(
        "terminal",
        {"command": "python -m pytest tests/ -q"},
        {"success": True, "returncode": 0, "command": "python -m pytest tests/ -q"},
    )
    # Un file letto e non modificato: e' l'unico caso in cui lo stato
    # riporta la copertura della lettura, che e' cio' che va conservato.
    ledger.record_tool(
        "read_file",
        {"path": f"{root}/core/y.py"},
        {"success": True, "path": f"{root}/core/y.py", "offset": 1,
         "last_line": 12, "total_lines": 12, "content": "VALORE = 1"},
    )
    ledger.add_decision("Il file va corretto, non riscritto.")
    return ledger


class TestSerializzazione:
    def test_il_giro_completo_non_perde_lo_stato(self):
        originale = _ledger_lavorato()
        ripristinato = DevSessionLedger.restore(originale.serialize())

        assert ripristinato.goal == originale.goal
        assert ripristinato.workspace_root == originale.workspace_root
        assert ripristinato.modified_files == originale.modified_files
        assert ripristinato.read_files == originale.read_files
        assert ripristinato.successful_commands() == originale.successful_commands()

    def test_le_finestre_di_lettura_sopravvivono(self):
        """Sono cio' che distingue «letto integralmente» da «letto un pezzo».

        `snapshot()` non le contiene, ed e' la ragione per cui il ripristino
        non puo' passare di li': un ledger che ha dimenticato quanto aveva
        letto fa rileggere tutto da capo.
        """
        originale = _ledger_lavorato()
        ripristinato = DevSessionLedger.restore(originale.serialize())
        atteso = originale.render_state_block()
        assert "letto" in atteso
        assert ripristinato.render_state_block() == atteso

    def test_il_cancello_di_completamento_da_lo_stesso_esito(self):
        """La prova raccolta prima del riavvio deve valere anche dopo."""
        from core.developer_studio.session_ledger import check_completion_allowed
        originale = _ledger_lavorato()
        ripristinato = DevSessionLedger.restore(originale.serialize())
        assert (check_completion_allowed(ripristinato)["allowed"]
                == check_completion_allowed(originale)["allowed"])

    def test_uno_stato_vuoto_produce_un_ledger_vuoto(self):
        """Tollerante per costruzione: un formato vecchio non deve sollevare."""
        for stato in ({}, {"version": 99}, {"files": [{"senza": "percorso"}]}):
            ledger = DevSessionLedger.restore(stato)
            assert ledger.read_files == []

    def test_un_record_corrotto_non_porta_giu_gli_altri(self):
        stato = _ledger_lavorato().serialize()
        stato["files"].insert(0, {"path": "rotto", "lines_seen": "non-una-lista"})
        ripristinato = DevSessionLedger.restore(stato)
        assert ripristinato.modified_files  # gli altri sono passati


class TestPersistenza:
    def test_salva_e_rilegge(self, store_isolato):
        ledger = _ledger_lavorato()
        assert session_store.save("s1", ledger, model="qwen", force=True)

        ripreso = session_store.load_ledger("s1", ledger.goal, WS)
        assert ripreso is not None
        assert ripreso.modified_files == ledger.modified_files

    def test_una_sessione_ignota_non_esiste(self, store_isolato):
        assert session_store.load("mai_vista") is None
        assert session_store.load_ledger("mai_vista", "x", WS) is None

    def test_un_workspace_diverso_non_viene_ripreso(self, store_isolato):
        """Il caso pericoloso: lo stato di un altro progetto, creduto vero."""
        session_store.save("s1", _ledger_lavorato(), force=True)
        assert session_store.load_ledger("s1", "obiettivo", "D:/altro_progetto") is None

    def test_un_obiettivo_nuovo_riprende_lo_stesso_stato(self, store_isolato):
        """Domande di seguito nella stessa sessione: i file letti restano validi."""
        session_store.save("s1", _ledger_lavorato(), force=True)
        ripreso = session_store.load_ledger("s1", "Ora aggiungi i test", WS)
        assert ripreso is not None
        assert ripreso.goal == "Ora aggiungi i test"
        assert ripreso.read_files  # il lavoro precedente e' ancora li'

    def test_un_identificativo_ostile_non_esce_dalla_cartella(self, store_isolato):
        """Un id finisce in un nome di file: non deve poter risalire l'albero."""
        session_store.save("../../fuga", _ledger_lavorato(), force=True)
        scritti = list(store_isolato.glob("**/*.json"))
        assert len(scritti) == 1
        assert scritti[0].parent == store_isolato

    def test_il_salvataggio_e_limitato_nel_ritmo(self, store_isolato, monkeypatch):
        """Il ledger cambia a ogni tool: scriverlo ogni volta e' spreco."""
        monkeypatch.setattr(session_store, "SAVE_INTERVAL_S", 3600.0)
        session_store._last_save.clear()
        ledger = _ledger_lavorato()
        assert session_store.save("s2", ledger) is True
        assert session_store.save("s2", ledger) is False
        assert session_store.save("s2", ledger, force=True) is True

    def test_un_disco_non_scrivibile_non_ferma_il_run(self, store_isolato, monkeypatch):
        def esplodi(*_a, **_k):
            raise OSError("disco pieno")
        monkeypatch.setattr(session_store.Path, "write_text", esplodi)
        assert session_store.save("s3", _ledger_lavorato(), force=True) is False


class TestElencoEPulizia:
    def test_le_sessioni_si_elencano_dalla_piu_recente(self, store_isolato):
        session_store.save("vecchia", _ledger_lavorato(goal="prima"), force=True)
        session_store.save("nuova", _ledger_lavorato(goal="seconda"), force=True)
        elenco = session_store.list_sessions()
        assert [v["session_id"] for v in elenco][:2] == ["nuova", "vecchia"]
        assert elenco[0]["files_touched"] >= 1

    def test_la_sessione_si_elimina(self, store_isolato):
        session_store.save("s1", _ledger_lavorato(), force=True)
        assert session_store.delete("s1")
        assert session_store.load("s1") is None

    def test_le_sessioni_in_eccesso_vengono_potate(self, store_isolato):
        for i in range(6):
            session_store.save(f"s{i}", _ledger_lavorato(), force=True)
        assert session_store.prune(keep=2) == 4
        assert len(session_store.list_sessions()) == 2
