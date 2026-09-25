# ==============================================================================
# tests/test_cache_dei_tool.py — La cache dei risultati di sola lettura
# ==============================================================================
"""La stessa lettura due volte deve costare una sola apertura di file.

La proprieta' che conta non e' «la cache risponde»: e' «la cache risponde **solo
quando la risposta e' ancora quella giusta**». Servire un file vecchio a un
agente che l'ha appena scritto e' il modo piu' rapido di fargli disfare il
proprio lavoro, e un test che si limitasse a contare gli hit non se ne
accorgerebbe.
"""
from pathlib import Path

from core.harness.tool_cache import ToolResultCache


def _scrivi(percorso: Path, testo: str) -> None:
    percorso.write_text(testo, encoding="utf-8")


class TestValidita:
    def test_il_file_riscritto_non_e_piu_quello(self, tmp_path):
        f = tmp_path / "a.txt"
        _scrivi(f, "prima versione")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": True, "content": "prima versione"})

        assert c.get("read_file", {"path": str(f)})["content"] == "prima versione"

        # Contenuto di lunghezza diversa: cambia anche la dimensione, quindi
        # l'impronta cambia anche se l'orologio del filesystem non ha battuto.
        _scrivi(f, "seconda versione, piu lunga")
        assert c.get("read_file", {"path": str(f)}) is None, (
            "la cache ha servito un file che nel frattempo era cambiato"
        )

    def test_il_file_sparito_non_e_piu_quello(self, tmp_path):
        f = tmp_path / "b.txt"
        _scrivi(f, "contenuto")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": True})
        f.unlink()
        assert c.get("read_file", {"path": str(f)}) is None

    def test_un_file_mai_visto_non_e_cacheabile(self, tmp_path):
        c = ToolResultCache()
        c.put("read_file", {"path": str(tmp_path / "inesistente.txt")},
              {"success": True})
        assert c.stats()["voci"] == 0
        assert c.stats()["rifiutate"] == 1


class TestInvalidazione:
    def test_una_scrittura_invalida_gli_elenchi_ma_non_le_letture(self, tmp_path):
        f = tmp_path / "c.txt"
        _scrivi(f, "contenuto stabile")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": True, "content": "x"})
        c.put("list_dir", {"path": str(tmp_path)}, {"success": True, "entries": ["c.txt"]})

        c.invalida()

        assert c.get("list_dir", {"path": str(tmp_path)}) is None, (
            "un elenco sopravvive a una scrittura: descrive un albero che non "
            "c'e' piu'"
        )
        assert c.get("read_file", {"path": str(f)}) is not None, (
            "la lettura di un file non toccato e' stata buttata: il ciclo "
            "modifica-poi-rileggi e' proprio quello in cui la cache serve"
        )

    def test_svuota_non_lascia_niente(self, tmp_path):
        f = tmp_path / "d.txt"
        _scrivi(f, "contenuto")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": True})
        c.svuota()
        assert c.get("read_file", {"path": str(f)}) is None

    def test_invalidare_un_percorso_butta_solo_quel_file(self, tmp_path):
        """Chi scrive conosce il file: le sue voci non hanno scuse per restare.

        E' il caso che l'impronta non copre per forza — due scritture della
        stessa lunghezza nello stesso battito dell'orologio — e l'unico in cui
        la cache puo' servire con sicurezza una risposta sbagliata.
        """
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        _scrivi(a, "contenuto a")
        _scrivi(b, "contenuto b")
        c = ToolResultCache()
        c.put("read_file", {"path": str(a)}, {"success": True, "content": "A"})
        c.put("read_file", {"path": str(b)}, {"success": True, "content": "B"})

        c.invalida(str(a))

        assert c.get("read_file", {"path": str(a)}) is None
        assert c.get("read_file", {"path": str(b)})["content"] == "B", (
            "ha buttato anche le voci di un file che nessuno ha toccato"
        )

    def test_invalidare_con_percorso_relativo_trova_la_voce(self, tmp_path, monkeypatch):
        """Il modello scrive a volte `core/x.py`, a volte il percorso intero."""
        monkeypatch.chdir(tmp_path)
        rel = Path("rel.txt")
        rel.write_text("contenuto", encoding="utf-8")
        c = ToolResultCache()
        c.put("read_file", {"path": str(tmp_path / "rel.txt")},
              {"success": True, "content": "contenuto"})
        c.invalida("rel.txt")
        assert c.get("read_file", {"path": str(tmp_path / "rel.txt")}) is None


class TestCosaNonEntra:
    def test_un_comando_non_si_mette_in_cache(self):
        c = ToolResultCache()
        c.put("terminal", {"command": "pytest -q"}, {"success": True, "stdout": "ok"})
        assert c.get("terminal", {"command": "pytest -q"}) is None
        assert c.stats()["voci"] == 0

    def test_un_fallimento_non_si_mette_in_cache(self, tmp_path):
        f = tmp_path / "e.txt"
        _scrivi(f, "contenuto")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": False, "error": "permesso negato"})
        assert c.get("read_file", {"path": str(f)}) is None, (
            "un errore servito dal passato dice all'agente che cio' che ha "
            "appena sistemato e' ancora rotto"
        )

    def test_un_risultato_enorme_non_si_mette_in_cache(self, tmp_path):
        f = tmp_path / "f.txt"
        _scrivi(f, "x")
        c = ToolResultCache()
        c.put("search_code", {"pattern": "x"},
              {"success": True, "matches": ["x" * 600_000]})
        assert c.stats()["voci"] == 0
        assert c.stats()["rifiutate"] == 1


class TestIsolamento:
    def test_chi_riceve_un_hit_non_avvelena_la_voce(self, tmp_path):
        f = tmp_path / "g.txt"
        _scrivi(f, "contenuto")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": True, "content": "vero"})

        primo = c.get("read_file", {"path": str(f)})
        primo["content"] = "manomesso"
        secondo = c.get("read_file", {"path": str(f)})
        assert secondo["content"] == "vero", (
            "l'annotazione di un hit e' finita dentro la voce e quindi in tutti "
            "gli hit successivi"
        )


class TestLimite:
    def test_oltre_il_limite_esce_la_voce_piu_vecchia(self, tmp_path):
        c = ToolResultCache(max_voci=3)
        for i in range(5):
            f = tmp_path / f"n{i}.txt"
            _scrivi(f, "contenuto")
            c.put("read_file", {"path": str(f)}, {"success": True, "n": i})
        assert c.stats()["voci"] == 3, "la cache e' cresciuta oltre il suo tetto"
        assert c.get("read_file", {"path": str(tmp_path / "n0.txt")}) is None
        assert c.get("read_file", {"path": str(tmp_path / "n4.txt")})["n"] == 4

    def test_il_conteggio_dice_il_vero(self, tmp_path):
        f = tmp_path / "h.txt"
        _scrivi(f, "contenuto")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)}, {"success": True})
        c.get("read_file", {"path": str(f)})
        c.get("read_file", {"path": str(f)})
        c.get("read_file", {"path": str(tmp_path / "assente.txt")})
        s = c.stats()
        assert (s["hits"], s["misses"]) == (2, 1), s
        assert s["hit_rate_percent"] == 66.7, s


class TestIlCicloModificaRileggi:
    def test_dopo_una_scrittura_la_risposta_e_quella_nuova(self, tmp_path):
        """La sequenza che conta: leggo, scrivo, rileggo. Il rileggi e' nuovo."""
        f = tmp_path / "i.txt"
        _scrivi(f, "versione uno\n")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f)},
              {"success": True, "content": "versione uno\n"})

        _scrivi(f, "versione due\n")
        c.invalida()

        assert c.get("read_file", {"path": str(f)}) is None
        c.put("read_file", {"path": str(f)},
              {"success": True, "content": "versione due\n"})
        assert c.get("read_file", {"path": str(f)})["content"] == "versione due\n"

    def test_letture_diverse_dello_stesso_file_sono_voci_diverse(self, tmp_path):
        """Due finestre dello stesso file non sono la stessa risposta."""
        f = tmp_path / "l.txt"
        _scrivi(f, "riga uno\nriga due\nriga tre\n")
        c = ToolResultCache()
        c.put("read_file", {"path": str(f), "offset": 1, "limit": 1},
              {"success": True, "content": "riga uno"})
        c.put("read_file", {"path": str(f), "offset": 3, "limit": 1},
              {"success": True, "content": "riga tre"})
        assert c.stats()["voci"] == 2, (
            "le due finestre sono collassate in una: l'agente riceverebbe la "
            "riga sbagliata"
        )
        assert c.get("read_file", {"path": str(f), "offset": 3, "limit": 1})["content"] == "riga tre"
