"""Il codice non passa piu dentro una stringa JSON.

Dei trecentodieci fallimenti di tool registrati nelle sessioni, centoventinove
erano JSON malformato: il 42%. I due tool che falliscono di piu sono quelli che
scrivono codice ? `edit_file` sessantadue volte, `write_file` quarantanove ? e la
causa non e distrazione: mettere cento righe di Python dentro una stringa JSON
significa raddoppiare ogni virgoletta e scrivere ogni a capo come barra-rovesciata-n.

Con il corpo grezzo l intestazione resta JSON corto e il contenuto e testo
normale, dopo una riga di soli trattini. Qui si verifica che il contenuto arrivi
intatto ? virgolette, a capo, barre rovesciate ? che il file finisca davvero su
disco con quei byte, e che la forma vecchia continui a funzionare.
"""

from core.harness.loop import (
    ADMIN_DEVELOPER_SYSTEM_PROMPT,
    _separa_corpo_grezzo,
    execute_admin_tool,
    extract_tool_invocations,
)

FENCE = chr(96) * 3
CODICE = (
    "def saluta(nome):\n"
    "    percorso = \"C:\\\\cartella\\\\file.txt\"\n"
    "    return {\"ciao\": nome, \"percorso\": percorso}\n"
)


def _recinto(nome, intestazione, corpo=None):
    """Un blocco recintato come lo scrive il modello: il recinto di chiusura
    sta su una riga sua, quindi il corpo finisce con un solo a capo."""
    pezzi = [FENCE + "tool:" + nome, intestazione]
    if corpo is not None:
        pezzi += ["---", corpo]
    testo = "\n".join(pezzi)
    if not testo.endswith("\n"):
        testo += "\n"
    return testo + FENCE


def _params(testo):
    invocazioni = extract_tool_invocations(testo)
    assert len(invocazioni) == 1, invocazioni
    return invocazioni[0]["tool"], invocazioni[0]["params"]


class TestIlCorpoGrezzo:
    def test_le_virgolette_e_gli_a_capo_arrivano_intatti(self):
        nome, params = _params(_recinto(
            "write_file", '{"path": "core/modulo.py"}', CODICE))
        assert nome == "write_file"
        assert params["path"] == "core/modulo.py"
        assert params["content"] == CODICE

    def test_append_file_aggiunge_in_coda(self):
        _, params = _params(_recinto(
            "append_file", '{"path": "README.md"}', "## Nuova sezione\n"))
        assert params["path"] == "README.md"
        assert params["content"] == "## Nuova sezione\n"

    def test_edit_file_porta_il_testo_nuovo_nel_corpo(self):
        _, params = _params(_recinto(
            "edit_file",
            '{"path": "a.py", "old_string": "return 1"}',
            "return 2\n"))
        assert params["old_string"] == "return 1"
        assert params["new_string"] == "return 2\n"

    def test_un_tool_che_non_si_mappa_non_cambia_forma(self):
        """Uno strumento qualsiasi non deve guadagnare una chiave che non usa."""
        _, params = _params(_recinto(
            "read_file", '{"path": "a.py"}', "roba"))
        assert params == {"path": "a.py"}

    def test_la_forma_vecchia_continua_a_funzionare(self):
        testo = _recinto("write_file", '{"path": "b.py", "content": "x = 1\\n"}')
        _, params = _params(testo)
        assert params["content"] == "x = 1\n"

    def test_senza_separatore_non_si_inventa_niente(self):
        intestazione, corpo = _separa_corpo_grezzo('{"path": "a.py"}')
        assert corpo is None and intestazione == '{"path": "a.py"}'

    def test_il_separatore_deve_essere_una_riga_sua(self):
        """Dentro un JSON i trattini non contano: solo la riga da soli divide."""
        _, corpo = _separa_corpo_grezzo('{"path": "a---b.py"}')
        assert corpo is None


class TestIlFileFinisceSuDisco:
    def test_i_byte_scritti_sono_quelli_scritti(self, tmp_path):
        _, params = _params(_recinto(
            "write_file", '{"path": "core/modulo.py"}', CODICE))
        esito = execute_admin_tool("write_file", params, str(tmp_path))
        assert esito["success"] is True, esito
        scritto = (tmp_path / "core" / "modulo.py").read_text(encoding="utf-8")
        assert scritto == CODICE


class TestIlPromptLoInsegna:
    def test_la_forma_e_documentata(self):
        assert "il corpo fuori dal JSON" in ADMIN_DEVELOPER_SYSTEM_PROMPT
        assert "una\nriga di soli trattini" in ADMIN_DEVELOPER_SYSTEM_PROMPT
        assert chr(96) * 3 + "tool:write_file" in ADMIN_DEVELOPER_SYSTEM_PROMPT

