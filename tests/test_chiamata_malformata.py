"""Un rifiuto che non insegna niente si ripete.

Il task `compose` della Biblioteca Digitale e' finito con ventinove turni, tre
file scritti, **zero comandi eseguiti** e sei chiamate malformate. Il
promemoria di verifica scattava e diceva in chiaro «ESEGUI ORA `docker compose
up -d --build`»: il modello non ci e' mai arrivato, perche' restava impigliato
sulle chiamate a `write_file`.

A ogni inciampo leggeva sempre la stessa riga:

    Riemetti il blocco nel formato esatto, per esempio:
    ```tool:write_file
    {"path": "core/api_router.py"}
    ```

Due cose non andavano, e sono la stessa cosa detta due volte: `core/api_router.py`
e' un file di Sigma Studio, non del progetto su cui si stava lavorando; e per
`write_file` l'esempio **ometteva `content`**, cioe' l'unico campo difficile —
quello dove va infilato un file intero, a capo compresi, dentro una stringa
JSON. Sei volte un esempio che non riguardava il suo problema.

Il secondo pezzo e' lo strumento che mancava per capirlo: il registro teneva il
messaggio del rifiuto e buttava via cio' che il modello aveva emesso. Sei volte
lo stesso testo generico, e nessun modo di sapere cosa ci fosse di storto. Ora
il corpo rifiutato resta: nel registro per chi indaga dopo, e nel blocco di
stato davanti a chi l'ha scritto — che e' il modo piu' diretto di farlo
correggere.
"""

import pytest

from core.harness.loop import _esempio_di_chiamata, execute_admin_tool

BARRA = chr(92)


def _errore(tool: str, raw: str = "services:") -> str:
    esito = execute_admin_tool(tool, {"__malformed__": True, "raw": raw}, ".")
    assert esito["success"] is False
    return esito["error"]


class TestLEsempioRiguardaIlTool:
    def test_write_file_mostra_content(self):
        """Era il campo mancante, ed era l'unico difficile."""
        assert '"content"' in _esempio_di_chiamata("write_file")

    def test_edit_file_mostra_old_e_new(self):
        esempio = _esempio_di_chiamata("edit_file")
        assert '"old"' in esempio and '"new"' in esempio

    def test_terminal_mostra_command(self):
        esempio = _esempio_di_chiamata("terminal")
        assert '"command"' in esempio
        assert '"path"' not in esempio, "il tool non prende un percorso"

    def test_nessun_esempio_nomina_file_di_sigma_studio(self):
        """Chi legge lavora su un altro progetto: un percorso di qui e' rumore,
        e su un run vero il modello ha provato ad aprirlo."""
        for tool in ("write_file", "append_file", "edit_file", "terminal",
                     "read_file", "search_code", "list_dir"):
            assert "core/api_router.py" not in _esempio_di_chiamata(tool)

    def test_un_tool_sconosciuto_non_fa_esplodere_niente(self):
        assert "```tool:boh" in _esempio_di_chiamata("boh")


class TestSiDiceDoveSiRompeDavvero:
    def test_l_avviso_sugli_a_capo_c_e_dove_serve(self):
        avviso = _esempio_di_chiamata("write_file")
        assert BARRA + "n" in avviso
        assert "una sola riga" in avviso

    def test_e_non_c_e_dove_non_serve(self):
        """Un avviso ovunque e' rumore ovunque: `terminal` non porta file."""
        assert "una sola riga" not in _esempio_di_chiamata("terminal")

    def test_il_rifiuto_vero_porta_l_esempio_giusto(self):
        assert '"content"' in _errore("write_file")


class TestIlCorpoRifiutatoNonSiPerde:
    def test_il_risultato_riporta_cio_che_e_arrivato(self):
        esito = execute_admin_tool(
            "write_file", {"__malformed__": True, "raw": "services:" + chr(10) + "  web:"}, ".")
        assert "services:" in esito["received"]

    def test_il_registro_lo_conserva(self):
        """Senza, un run fallito su sei chiamate malformate non e' spiegabile."""
        from core.harness.ledger import DevSessionLedger

        ledger = DevSessionLedger(goal="x", workspace_root=".")
        ledger.record_tool(
            "write_file", {"path": "docker-compose.yml"},
            {"tool": "write_file", "success": False,
             "error": "il corpo non e un oggetto JSON valido",
             "received": "services:" + chr(10) + "  web:" + chr(10) + "    build: ."},
        )
        stato = ledger.render_state_block()
        assert "hai emesso" in stato
        assert "services:" in stato, "il modello non rivede cio' che ha scritto"

    def test_un_fallimento_senza_corpo_resta_una_riga_sola(self):
        from core.harness.ledger import DevSessionLedger

        ledger = DevSessionLedger(goal="x", workspace_root=".")
        ledger.record_tool(
            "terminal", {"command": "npm test"},
            {"tool": "terminal", "success": False, "error": "uscito con codice 1"},
        )
        assert "hai emesso" not in ledger.render_state_block()
