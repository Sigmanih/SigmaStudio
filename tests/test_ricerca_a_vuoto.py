"""Una ricerca che non trova niente deve dire quanto ha guardato.

Nel pannello comparivano schede «AZIONE: SEARCH_CODE — ✓ Completato» con dentro
il vuoto: la ricerca era andata a buon fine e non si vedeva ne' cosa cercasse
ne' cosa avesse trovato. Per il modello era anche peggio dell'interfaccia —
leggeva «Nessuna corrispondenza» e ripeteva la stessa ricerca con un sinonimo,
perche' quella riga non distingue due situazioni opposte:

- quattrocento file esaminati e il termine non c'e' — **una risposta**, su cui
  si puo' contare per decidere il passo successivo;
- zero file esaminati perche' il percorso e' sbagliato — **nessuna risposta**,
  e cercare un'altra parola dara' di nuovo zero.

Il dato c'era gia' nel risultato (`scanned_files`) e non arrivava a nessuno dei
due. E' la stessa idea della riga SIGMA-CHECK: un controllo che non ha
esaminato niente non dimostra niente.
"""

import pytest

from core.harness.loop import (
    _ricerca_a_vuoto,
    _riassunto_ricerca,
    execute_admin_tool,
)


@pytest.fixture
def progetto(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def carica_modello(nome):\n    return nome\n", encoding="utf-8")
    (tmp_path / "src" / "util.py").write_text("VALORE = 1\n", encoding="utf-8")
    return tmp_path


class TestLOsservazioneDistingueIDueCasi:
    def test_termine_assente_ma_file_esaminati_e_una_risposta(self, progetto):
        esito = execute_admin_tool(
            "search_code", {"query": "inesistente_xyz", "path": "src"},
            workspace_root=str(progetto))
        riga = _ricerca_a_vuoto(esito)
        assert "2 file" in riga, "deve dire quanti ne ha guardati"
        assert "affidabile" in riga, "e che ci si puo' contare sopra"

    def test_zero_file_esaminati_non_e_una_risposta(self, progetto):
        esito = execute_admin_tool(
            "search_code", {"query": "qualcosa", "path": "cartella_assente"},
            workspace_root=str(progetto))
        riga = _ricerca_a_vuoto(esito)
        assert "ESAMINATI 0 FILE" in riga
        assert "list_dir" in riga, "deve dire cosa fare invece di ricercare"
        assert "dara' di nuovo zero" in riga

    def test_i_file_saltati_vengono_detti(self):
        riga = _ricerca_a_vuoto({"query": "x", "path": "s",
                                 "scanned_files": 10, "skipped_files": 4})
        assert "4 saltati" in riga

    def test_il_ciclo_la_usa(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "_ricerca_a_vuoto(result)" in sorgente


class TestIlRisultatoSiDescriveDaSolo:
    def test_una_ricerca_riuscita_dice_quante_e_su_quanti(self, progetto):
        esito = execute_admin_tool(
            "search_code", {"query": "carica_modello", "path": "src"},
            workspace_root=str(progetto))
        assert esito["message"]
        assert "carica_modello" in esito["message"]
        assert "file esaminati" in esito["message"]

    def test_una_ricerca_a_vuoto_non_lascia_la_scheda_muta(self, progetto):
        """E' il difetto che si vedeva nel pannello."""
        esito = execute_admin_tool(
            "search_code", {"query": "inesistente_xyz", "path": "src"},
            workspace_root=str(progetto))
        assert esito["success"] is True
        assert esito["message"], "un successo senza racconto e' una scatola vuota"
        assert "Nessuna corrispondenza" in esito["message"]

    def test_un_percorso_sbagliato_lo_dice_nel_messaggio(self, progetto):
        esito = execute_admin_tool(
            "search_code", {"query": "x", "path": "non_esiste"},
            workspace_root=str(progetto))
        assert "Nessun file esaminato" in esito["message"]

    def test_un_elenco_troncato_lo_dichiara(self):
        riga = _riassunto_ricerca({
            "query": "def", "results": [{"path": "a"}] * 25,
            "scanned_files": 300, "capped": True, "stop_reason": "max_results"})
        assert "troncato" in riga and "max_results" in riga

    def test_un_errore_non_viene_coperto_da_un_riassunto(self, progetto):
        """Con un messaggio sopra, un errore vero smetterebbe di vedersi."""
        esito = execute_admin_tool(
            "search_code", {"query": "", "path": "src"},
            workspace_root=str(progetto))
        assert esito["success"] is False
        assert "message" not in esito


def test_il_pannello_mostra_il_termine_cercato():
    """Una scheda che dice «RICERCA NEL CODICE» e non dice di cosa e' meta'
    informazione."""
    import pathlib

    percorso = pathlib.Path(
        "sigma_studio/src/modules/sigma_developer_lab/AdminAgentChat.jsx")
    testo = percorso.read_text(encoding="utf-8")
    assert "RICERCA NEL CODICE" in testo
    assert "t.params?.query" in testo
