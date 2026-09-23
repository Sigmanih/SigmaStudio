"""Prima di chiedere una finestra, sapere dove guardare.

Il 23 settembre 2026 un agente ha cercato per dieci turni una funzione che
doveva modificare. Stava alla riga 2132 di `core/harness/loop.py`, un file di
4212 righe che aveva letto a pezzi (1-1200 e 2400-2899). Nessuno gli aveva
detto dove guardare, e le sue ricerche trovavano soprattutto il rumore delle
proprie tracce.

La mappa dei simboli esisteva gia: `find_symbol` la usa da mesi. Ma non era fra
i tool del ruolo Coder, e per i file citati nell obiettivo non entrava nello
stato del lavoro. Qui si verifica che entri, che costi poco (memo su mtime e
taglia) e che sparisca quando non serve piu: un file letto per intero non ha
niente da mappare.
"""

import pytest

from core.harness.ledger import DevSessionLedger
from core.harness.loop import _mappa_dei_file_citati, _mappa_di_un_file
from core.harness.role_registry import get_role
from core.harness.symbol_index import outline_of_file

RIGHE = 900
DEFINIZIONI = (100, 400, 800)
# Una riga per definizione, cosi il numero di riga e il numero nel nome
# coincidono e il test puo verificarli senza contare a mano.
CORPO = "\n".join(
    ("def funzione_%d(): return %d" % (r, r)) if r in DEFINIZIONI
    else ("x_%d = %d" % (r, r))
    for r in range(1, RIGHE + 1)
) + "\n"


def _progetto(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lungo.py").write_text(CORPO, encoding="utf-8")
    return tmp_path


def _percorso(tmp_path):
    return str(tmp_path / "src" / "lungo.py")


def _ledger(tmp_path, letto=None):
    led = DevSessionLedger(goal="Aggiungi un parametro in src/lungo.py",
                           workspace_root=str(tmp_path))
    if letto:
        led.record_tool(
            "read_file", {"path": _percorso(tmp_path)},
            {"success": True, "path": _percorso(tmp_path),
             "offset": letto[0], "last_line": letto[1],
             "total_lines": RIGHE, "content": "..."})
    return led


class TestLaMappa:
    def test_dice_cosa_definisce_e_a_che_riga(self, tmp_path):
        esito = outline_of_file(_percorso(_progetto(tmp_path)))
        assert esito["success"] is True
        assert esito["total_lines"] == RIGHE
        assert [(v["name"], v["line"]) for v in esito["symbols"]] == [
            ("funzione_100", 100), ("funzione_400", 400), ("funzione_800", 800)]

    def test_la_mappa_e_ordinate_per_riga(self, tmp_path):
        esito = outline_of_file(_percorso(_progetto(tmp_path)))
        righe = [v["line"] for v in esito["symbols"]]
        assert righe == sorted(righe)

    def test_un_file_che_non_esiste_non_si_mappa(self, tmp_path):
        esito = outline_of_file(str(tmp_path / "assente.py"))
        assert esito["success"] is False and esito["symbols"] == []

    def test_un_formato_senza_simboli_non_si_mappa(self, tmp_path):
        p = tmp_path / "x.bin"
        p.write_bytes(b"\x00\x01")
        assert outline_of_file(str(p))["success"] is False

    def test_il_tetto_delle_voci_e_rispettato(self, tmp_path):
        esito = outline_of_file(_percorso(_progetto(tmp_path)), limit=2)
        assert len(esito["symbols"]) == 2
        assert esito["count"] == 3


class TestLaMappaEntraNelloStato:
    def test_un_file_lungo_citato_viene_mappato(self, tmp_path):
        radice = _progetto(tmp_path)
        testo = _mappa_dei_file_citati(_ledger(radice), str(radice))
        assert "Mappa dei file citati" in testo
        assert "funzione_400" in testo and "400" in testo
        assert "manca" not in testo

    def test_un_file_letto_tutto_non_si_mappa_piu(self, tmp_path):
        radice = _progetto(tmp_path)
        letto = _ledger(radice, letto=(1, RIGHE))
        assert _mappa_dei_file_citati(letto, str(radice)) == ""

    def test_un_file_con_un_buco_resta_mappato(self, tmp_path):
        """E il caso del run vero: due finestre, un buco in mezzo."""
        radice = _progetto(tmp_path)
        letto = _ledger(radice, letto=(1, 300))
        assert "funzione_400" in _mappa_dei_file_citati(letto, str(radice))

    def test_un_file_corto_non_merita_una_mappa(self, tmp_path):
        (tmp_path / "corto.py").write_text("def x():\n    return 1\n", encoding="utf-8")
        led = DevSessionLedger(goal="Modifica corto.py", workspace_root=str(tmp_path))
        assert _mappa_dei_file_citati(led, str(tmp_path)) == ""

    def test_il_memo_si_aggiorna_quando_il_file_cambia(self, tmp_path):
        radice = _progetto(tmp_path)
        percorso = _percorso(radice)
        prima = _mappa_di_un_file(percorso)
        assert prima and "funzione_800" in prima
        with open(percorso, "a", encoding="utf-8") as f:
            f.write("def funzione_nuova():\n    return 1\n")
        dopo = _mappa_di_un_file(percorso)
        assert "funzione_nuova" in dopo, "il memo non deve nascondere una modifica"

    def test_il_ciclo_la_usa(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        assert "_mappa_dei_file_citati(ledger, workspace_root)" in inspect.getsource(
            _stream_agent_turn_impl)


def test_find_symbol_e_fra_i_tool_del_coder():
    coder = get_role("coder")
    assert coder is not None
    assert "find_symbol" in tuple(coder.tools)


def test_il_prompt_documenta_find_symbol():
    from core.harness.loop import ADMIN_DEVELOPER_SYSTEM_PROMPT
    assert "`find_symbol`" in ADMIN_DEVELOPER_SYSTEM_PROMPT

