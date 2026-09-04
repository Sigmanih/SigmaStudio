"""Le convenzioni le detta il workspace, non l'harness.

Finche' le regole architetturali stavano nel system prompt Python, l'agente
puntato su un altro repository applicava le regole di Sigma Studio: vietava
`@mui` a un progetto costruito su `@mui`. Questi test fissano il
comportamento che rende l'harness portabile — leggere le regole dal progetto,
e non inventarne quando il progetto non ne dichiara.
"""

from core.developer_studio import project_rules


def _scrivi(radice, nome, testo):
    percorso = radice / nome
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(testo, encoding="utf-8")
    return percorso


class TestScoperta:
    def test_un_workspace_senza_regole_non_ne_produce(self, tmp_path):
        """Vuoto e' l'esito giusto: meglio nessuna regola che quelle di un altro."""
        project_rules.invalidate()
        assert project_rules.load_section(str(tmp_path)) == ""
        assert project_rules.discover(str(tmp_path)) == []

    def test_una_radice_inesistente_non_solleva(self, tmp_path):
        project_rules.invalidate()
        assert project_rules.load_section(str(tmp_path / "non_esiste")) == ""
        assert project_rules.load_section(None) == ""

    def test_agents_md_viene_letto(self, tmp_path):
        _scrivi(tmp_path, "AGENTS.md", "Usa solo tabulazioni.")
        project_rules.invalidate()
        sezione = project_rules.load_section(str(tmp_path))
        assert "Usa solo tabulazioni." in sezione
        assert "AGENTS.md" in sezione

    def test_le_forme_alternative_sono_riconosciute(self, tmp_path):
        _scrivi(tmp_path, ".sigma/rules.md", "Regola nativa.")
        _scrivi(tmp_path, "CLAUDE.md", "Regola compatibile.")
        project_rules.invalidate()
        sezione = project_rules.load_section(str(tmp_path))
        assert "Regola nativa." in sezione
        assert "Regola compatibile." in sezione

    def test_i_file_trovati_sono_elencabili(self, tmp_path):
        """La UI deve poter dire quali istruzioni l'agente sta applicando."""
        _scrivi(tmp_path, "AGENTS.md", "x")
        trovati = project_rules.discover(str(tmp_path))
        assert [f["rel"] for f in trovati] == ["AGENTS.md"]


class TestBudget:
    def test_un_file_enorme_viene_troncato(self, tmp_path):
        """Oltre una certa taglia non sono convenzioni, e' documentazione."""
        _scrivi(tmp_path, "AGENTS.md", "riga\n" * 20_000)
        project_rules.invalidate()
        sezione = project_rules.load_section(str(tmp_path))
        assert len(sezione) < project_rules.MAX_CHARS_TOTAL + 2_000
        assert "troncato" in sezione

    def test_la_somma_dei_file_resta_sotto_il_tetto(self, tmp_path):
        grande = "x" * (project_rules.MAX_CHARS_PER_FILE - 10)
        _scrivi(tmp_path, "AGENTS.md", grande)
        _scrivi(tmp_path, ".sigma/rules.md", grande)
        _scrivi(tmp_path, "CLAUDE.md", grande)
        project_rules.invalidate()
        sezione = project_rules.load_section(str(tmp_path))
        assert len(sezione) < project_rules.MAX_CHARS_TOTAL + 2_000


class TestMemorizzazione:
    def test_una_modifica_al_file_viene_rivista(self, tmp_path):
        """La sezione e' memorizzata per non rileggere il disco a ogni turno.

        Se pero' l'utente corregge le regole mentre lavora, deve valere la
        versione corretta: una cache che non si accorge del cambiamento
        farebbe seguire all'agente istruzioni che l'utente ha gia' cambiato.
        """
        percorso = _scrivi(tmp_path, "AGENTS.md", "Prima regola.")
        project_rules.invalidate()
        assert "Prima regola." in project_rules.load_section(str(tmp_path))

        import os
        import time
        percorso.write_text("Seconda regola.", encoding="utf-8")
        # La firma include mtime_ns e dimensione: il testo cambia entrambi,
        # ma su filesystem a bassa risoluzione conviene non fidarsi del solo
        # orologio.
        os.utime(percorso, (time.time() + 2, time.time() + 2))

        sezione = project_rules.load_section(str(tmp_path))
        assert "Seconda regola." in sezione
        assert "Prima regola." not in sezione

    def test_la_rimozione_del_file_svuota_la_sezione(self, tmp_path):
        percorso = _scrivi(tmp_path, "AGENTS.md", "Regola temporanea.")
        project_rules.invalidate()
        assert project_rules.load_section(str(tmp_path))
        percorso.unlink()
        assert project_rules.load_section(str(tmp_path)) == ""


class TestRegoleDiQuestoProgetto:
    """Sigma Studio dichiara le proprie regole come qualunque altro progetto."""

    def test_il_repository_ha_un_agents_md(self):
        from core.paths import project_root
        sezione = project_rules.load_section(str(project_root()))
        assert "AGENTS.md" in sezione
        # Le convenzioni che prima stavano incise nel prompt Python
        assert "lucide-react" in sezione
