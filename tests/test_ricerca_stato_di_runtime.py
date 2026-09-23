"""Cosa la ricerca non deve trovare: la contabilita del programma stesso.

Il 23 settembre 2026 un run del Developer Studio ha speso i suoi ultimi dieci
turni a cercare `def stream_admin_agent_turn`, la funzione d ingresso del ciclo
alla quale il task chiedeva di aggiungere un parametro. Otto corrispondenze,
sette dentro `var/`: tre erano il log di quella stessa ricerca, scritto un turno
prima, e quattro erano copie morte di `loop.py` nei worktree di run finiti. Il
contatore cresceva di uno a ogni tentativo ? 6, 7, 8 ? perche la ricerca trovava
sempre un po di se stessa. L unica risposta vera era l ottava.

Il secondo difetto e l ordine: il tetto dei risultati si consuma camminando, e
`queue_id` lo esauriva sulle code scritte a mano nella radice e su `PIANO_*.md`,
senza arrivare mai a `core/harness/workqueue.py`, che e dove la risposta stava.

Qui si verificano le due correzioni: le cartelle di stato non entrano
nell albero cercato (tranne quando il percorso e chiesto esplicitamente), e le
cartelle del codice vengono prima.
"""

import inspect

import pytest

from core.harness.fs_manager import (
    SEARCH_FIRST_DIRS,
    SEARCH_IGNORE_DIRS,
    SEARCH_IGNORE_RUNTIME_DIRS,
    cartelle_di_stato_saltate,
    search_workspace_files,
)
from core.harness.loop import _cartelle_di_stato, _ricerca_a_vuoto, _riassunto_ricerca

TERMINE = "def catena_di_prova"


@pytest.fixture
def progetto(tmp_path):
    """Il codice da una parte, la contabilita del programma dall altra."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "loop.py").write_text(
        "%s(x):\n    return x\n" % TERMINE, encoding="utf-8")

    sessione = tmp_path / "var" / "dev_sessions"
    sessione.mkdir(parents=True)
    (sessione / "sessione.json").write_text(
        '{"searches": [{"query": "%s"}]}' % TERMINE, encoding="utf-8")

    # Una copia morta del file di codice, come nei worktree dei run finiti:
    # stessa definizione, stesso nome, cartella temporanea di un altro run.
    vecchio = tmp_path / "var" / "dev_worktrees" / "vecchio_run" / "core"
    vecchio.mkdir(parents=True)
    (vecchio / "loop.py").write_text(
        "%s(x):\n    return x\n" % TERMINE, encoding="utf-8")

    (tmp_path / "PIANO_TASK.md").write_text(
        "la voce parla di %s\n" % TERMINE, encoding="utf-8")
    return tmp_path


class TestLaContabilitaNonEntraNellAlbero:
    def test_il_codice_si_trova_e_lo_stato_no(self, progetto):
        esito = search_workspace_files(str(progetto), TERMINE)
        percorsi = [r["path"] for r in esito["results"]]
        assert len(percorsi) == 2, percorsi
        assert not [p for p in percorsi if "/var/" in p], percorsi

    def test_lo_dice_quali_cartelle_ha_saltato(self, progetto):
        esito = search_workspace_files(str(progetto), TERMINE)
        assert esito["ignored_runtime_dirs"] == ["var"]

    def test_chi_sa_dove_guardare_le_trova_lo_stesso(self, progetto):
        """Il divieto vale per la scansione, non per un percorso chiesto."""
        dentro = progetto / "var" / "dev_sessions"
        esito = search_workspace_files(str(dentro), TERMINE)
        assert len(esito["results"]) == 1

    def test_senza_cartelle_di_stato_non_si_annuncia_niente(self, tmp_path):
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "a.py").write_text(TERMINE, encoding="utf-8")
        esito = search_workspace_files(str(tmp_path), TERMINE)
        assert "ignored_runtime_dirs" not in esito
        assert cartelle_di_stato_saltate(str(tmp_path)) == []

    def test_le_cartelle_di_stato_sono_nel_divieto(self):
        for nome in ("var", "store", "logs"):
            assert nome in SEARCH_IGNORE_RUNTIME_DIRS
            assert nome in SEARCH_IGNORE_DIRS


class TestOrdineDiVisita:
    def test_il_codice_viene_prima_delle_note_della_radice(self, progetto):
        """Con un tetto di un solo risultato, vince `core/`."""
        esito = search_workspace_files(str(progetto), TERMINE, max_results=1)
        assert esito["results"][0]["path"].endswith("core/loop.py")
        assert esito["capped"] is True
        assert esito["stop_reason"] == "max_results"

    def test_le_cartelle_del_codice_sono_dichiarate(self):
        for nome in ("core", "tests", "tools"):
            assert nome in SEARCH_FIRST_DIRS

    def test_i_budget_restano_quelli(self, progetto):
        """Il tetto dei file esaminati non e cambiato per via dell ordine."""
        esito = search_workspace_files(str(progetto), TERMINE)
        assert esito["scanned_files"] == 2


class TestLaNotaArrivaAlModello:
    def test_la_ricerca_a_vuoto_dice_cosa_non_ha_guardato(self):
        riga = _ricerca_a_vuoto({
            "query": "x", "path": ".", "scanned_files": 10,
            "skipped_files": 0, "ignored_runtime_dirs": ["var", "store"]})
        assert "var/" in riga and "store/" in riga
        assert "`path`" in riga, "deve dire come cercarci dentro"

    def test_anche_una_ricerca_a_buon_fine_lo_dice(self):
        riga = _riassunto_ricerca({
            "query": "x", "results": [{"path": "a"}],
            "scanned_files": 3, "ignored_runtime_dirs": ["var"]})
        assert "Saltate 1 cartelle di stato (var)." in riga

    def test_senza_cartelle_saltate_la_nota_non_c_e(self):
        assert _cartelle_di_stato({"query": "x"}) == ""
        assert "Non ho guardato" not in _ricerca_a_vuoto(
            {"query": "x", "path": ".", "scanned_files": 10})

    def test_il_ciclo_usa_la_nota(self):
        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "_cartelle_di_stato(result)" in sorgente

