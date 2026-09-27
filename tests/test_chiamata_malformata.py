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


# ==============================================================================
# Il confine opposto: cosa NON deve diventare una chiamata
#
# Il ripiego che accettava qualunque JSON in qualunque punto del testo prendeva
# un esempio citato nella prosa e lo eseguiva. Un parser che estrae azioni si
# giudica da entrambi i lati, e il lato che mancava era questo.
# ==============================================================================

from core.harness.loop import extract_tool_invocations


class TestLaProsaNonEUnaChiamata:

    def test_un_json_citato_nella_prosa_non_viene_eseguito(self):
        """Il caso che eseguiva `rm -rf build`."""
        testo = (
            "Per configurare il deploy, il file usa questo formato:\n\n"
            '{"command": "rm -rf build && npm run deploy", "shell": true}\n\n'
            "Non eseguirlo ora, e' solo un esempio."
        )
        assert extract_tool_invocations(testo) == []

    def test_un_recinto_a_due_backtick_dentro_una_frase_non_e_una_chiamata(self):
        testo = "Usa la variabile ``tool:read_file`` come riferimento nel testo."
        assert extract_tool_invocations(testo) == []

    def test_un_json_che_non_dichiara_il_tool_non_viene_indovinato(self):
        """Indovinare il tool dalle chiavi e' la parte pericolosa."""
        testo = 'Il manifest ha questa forma: {"path": "config/app.json"} e va letto a mano.'
        assert extract_tool_invocations(testo) == []

    def test_una_chiamata_vera_a_inizio_riga_passa_ancora(self):
        testo = '```tool:read_file\n{"path": "core/loop.py"}\n```'
        chiamate = extract_tool_invocations(testo)
        assert [(c["tool"], c["params"]["path"]) for c in chiamate] == [
            ("read_file", "core/loop.py")
        ]

    def test_due_backtick_a_inizio_riga_restano_accettati(self):
        """I modelli locali li emettono davvero: la stretta e' sulla posizione,
        non sul numero di backtick."""
        testo = '``tool:write_file\n{"path": "a.txt", "content": "ciao"}\n``'
        chiamate = extract_tool_invocations(testo)
        assert chiamate and chiamate[0]["tool"] == "write_file"

    def test_il_recinto_aperto_e_mai_chiuso_resta_recuperabile(self):
        """Era il problema vero che il ripiego voleva risolvere, e resta risolto."""
        testo = 'Procedo.\n\n```tool:read_file\n{"path": "core/loop.py"}'
        chiamate = extract_tool_invocations(testo)
        assert chiamate and chiamate[0]["tool"] == "read_file"

    def test_un_json_nudo_che_dichiara_il_tool_e_una_chiamata(self):
        """Se il modello dice quale tool vuole, e il JSON e' tutto il messaggio,
        l'intenzione c'e' ed e' esplicita."""
        chiamate = extract_tool_invocations('{"tool": "list_dir", "params": {"path": "core"}}')
        assert [(c["tool"], c["params"]["path"]) for c in chiamate] == [("list_dir", "core")]

    def test_chiamata_preceduta_da_tag_pensiero_riconosciuta(self):
        """Modelli con catena di pensiero nativa (es. Nex-N2.5, DeepSeek) che
        emettono il recinto tool attaccato a <think> o </think>."""
        testo1 = '<think>```tool:list_dir\n{"path": "."}\n```</think>'
        chiamate1 = extract_tool_invocations(testo1)
        assert [(c["tool"], c["params"]["path"]) for c in chiamate1] == [("list_dir", ".")]

        testo2 = '<think>Ragiono prima di agire</think>```tool:read_file\n{"path": "x.py"}\n```'
        chiamate2 = extract_tool_invocations(testo2)
        assert [(c["tool"], c["params"]["path"]) for c in chiamate2] == [("read_file", "x.py")]


class TestIlRiepilogoRifiutatoOttoVolte:
    """23 settembre 2026: un run ha emesso il proprio `complete_goal` otto volte
    di fila, identico, e ogni volta il cancello ha risposto «il corpo non e un
    oggetto JSON valido» mostrando l'esempio `{"path": "..."}` - cioe' dicendogli
    di togliere `summary`, l'unico campo che doveva riempire.

    Il corpo era scritto bene: aveva un a capo protetto e diciannove virgolette
    su venticinque protette. Le altre sei no, e una virgoletta non protetta
    dentro una stringa basta a invalidare tutto. Il modello, che non poteva
    saperlo, ha riprovato uguale. Il run e' finito con i turni esauriti.

    Si verifica: che l'esempio parli del campo giusto, che un corpo di prosa non
    venga buttato via, che la maglia non si allarghi agli altri tool, e che il
    nome con cui l'hub MCP chiama un tool valga anche qui.
    """

    def test_l_esempio_di_complete_goal_parla_di_summary(self):
        esempio = _esempio_di_chiamata("complete_goal")
        assert "summary" in esempio, esempio
        assert '"path"' not in esempio, "l'esempio chiedeva un campo che non serve"

    def test_il_corpo_di_prosa_non_si_butta(self):
        from core.harness.loop import normalize_tool_params

        corpo = '{"summary": "Ho verificato: sono ancora "DA FARE" i criteri 1 e 3."}'
        esito = normalize_tool_params(corpo, "complete_goal")
        assert esito.get("__malformed__") is not True, esito
        assert "DA FARE" in esito.get("summary", ""), esito
        assert len(esito.get("summary", "")) > 20

    def test_la_maglia_non_si_allarga(self):
        """La prosa si recupera per i riepiloghi, non per i file: li' un JSON
        rotto e' un contenuto che l'agente deve riscrivere, non indovinare."""
        from core.harness.loop import normalize_tool_params

        rotto = '{"path": "x.py", "content": Ho verificato il file: non e in json}'
        assert normalize_tool_params(rotto, "write_file").get("__malformed__") is True
        assert normalize_tool_params('{"summary": "ok"}', "complete_goal") == {"summary": "ok"}

    def test_il_messaggio_nomina_le_due_cause(self):
        errore = _errore("complete_goal", '{"summary": "a "b" c"}')
        assert "virgoletta" in errore, errore
        assert BARRA + "n" in errore, errore

    def test_il_nome_dell_hub_vale_anche_nel_ciclo(self):
        from core.harness.policy import canonical

        assert canonical("read_file_window") == "read_file"
        assert canonical("edit_file_exact") == "edit_file"
        assert canonical("read_file_slice") == "read_file"
