"""La cartella di lavoro deve essere un confine, non un suggerimento.

`resolve_workspace_path` prometteva nel nome di risolvere i percorsi *dentro*
la radice di lavoro. Non lo faceva: un percorso assoluto veniva restituito tale
e quale, e un `..` in mezzo al percorso veniva risolto da `normpath` senza che
nessuno ricontrollasse il risultato. Con un run aperto su un progetto esterno
si arrivava a `config/config.json` di Sigma Studio, dove stanno le credenziali.

I tool di file avevano una staccionata bucata. Questi test la chiudono e
verificano che non abbia chiuso anche cio' che deve passare: un confine che
rifiuta il lavoro legittimo viene disattivato dopo due giorni.
"""

import os

import pytest

from core.harness.loop import (
    FuoriDalWorkspace,
    execute_admin_tool,
    resolve_workspace_path,
)


@pytest.fixture
def progetto(tmp_path):
    """Una radice di lavoro con dentro un file, e un segreto fuori."""
    radice = tmp_path / "progetto"
    (radice / "src").mkdir(parents=True)
    (radice / "src" / "app.py").write_text("print('ciao')\n", encoding="utf-8")
    fuori = tmp_path / "riservato"
    fuori.mkdir()
    (fuori / "config.json").write_text('{"hf_token": "non-si-legge"}', encoding="utf-8")
    return radice, fuori


class TestCioCheDeveEssereRifiutato:
    def test_un_percorso_assoluto_fuori_viene_rifiutato(self, progetto):
        radice, fuori = progetto
        with pytest.raises(FuoriDalWorkspace):
            resolve_workspace_path(str(fuori / "config.json"), str(radice))

    def test_il_punto_punto_in_mezzo_al_percorso_viene_rifiutato(self, progetto):
        """Era la via che `normpath` apriva: `^[./\\\\]+` toglie i punti solo
        in testa, e nessuno guardava dove il percorso finiva davvero."""
        radice, _ = progetto
        with pytest.raises(FuoriDalWorkspace):
            resolve_workspace_path("src/../../riservato/config.json", str(radice))

    def test_il_rifiuto_dice_quale_percorso_e_quale_radice(self, progetto):
        radice, fuori = progetto
        with pytest.raises(FuoriDalWorkspace) as exc:
            resolve_workspace_path(str(fuori / "config.json"), str(radice))
        assert "config.json" in str(exc.value)
        assert str(radice) in str(exc.value)

    @pytest.mark.skipif(not hasattr(os, "symlink"), reason="senza collegamenti")
    def test_un_collegamento_che_punta_fuori_non_e_una_scorciatoia(self, progetto):
        radice, fuori = progetto
        ponte = radice / "ponte"
        try:
            os.symlink(str(fuori), str(ponte), target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("questo sistema non lascia creare collegamenti")
        with pytest.raises(FuoriDalWorkspace):
            resolve_workspace_path("ponte/config.json", str(radice))


class TestCioCheDevePassare:
    def test_un_percorso_relativo_normale(self, progetto):
        radice, _ = progetto
        risolto = resolve_workspace_path("src/app.py", str(radice))
        assert risolto.endswith(os.path.join("src", "app.py"))

    def test_un_percorso_assoluto_dentro_la_radice(self, progetto):
        """Il modello li scrive spesso: rifiutarli sarebbe rifiutare lavoro buono."""
        radice, _ = progetto
        dentro = str(radice / "src" / "app.py")
        assert resolve_workspace_path(dentro, str(radice)) == os.path.abspath(dentro)

    def test_un_file_che_ancora_non_esiste(self, progetto):
        radice, _ = progetto
        risolto = resolve_workspace_path("src/nuovo.py", str(radice))
        assert risolto.endswith("nuovo.py")

    def test_la_radice_stessa(self, progetto):
        radice, _ = progetto
        assert resolve_workspace_path(".", str(radice)) == os.path.abspath(str(radice))

    def test_un_punto_punto_che_resta_dentro(self, progetto):
        radice, _ = progetto
        risolto = resolve_workspace_path("src/../src/app.py", str(radice))
        assert risolto.endswith(os.path.join("src", "app.py"))


class TestIlRifiutoArrivaAllAgente:
    def test_read_file_fuori_torna_un_errore_non_un_eccezione(self, progetto):
        """Un'eccezione qui ucciderebbe il turno: l'agente deve poter leggere
        il motivo e riprovare con un percorso buono."""
        radice, fuori = progetto
        esito = execute_admin_tool(
            "read_file", {"path": str(fuori / "config.json")}, str(radice))
        assert esito["success"] is False
        assert "fuori dalla cartella di lavoro" in esito["error"]
        assert "non-si-legge" not in str(esito)

    def test_write_file_fuori_non_scrive_niente(self, progetto):
        radice, fuori = progetto
        bersaglio = fuori / "intruso.py"
        esito = execute_admin_tool(
            "write_file", {"path": str(bersaglio), "content": "x"}, str(radice))
        assert esito["success"] is False
        assert not bersaglio.exists()

    def test_il_terminale_non_puo_spostare_la_cartella_di_lavoro_fuori(self, progetto):
        radice, fuori = progetto
        esito = execute_admin_tool(
            "terminal", {"command": "echo ciao", "cwd": str(fuori)}, str(radice))
        assert esito["success"] is False
        assert "fuori dalla cartella di lavoro" in esito["error"]

    def test_delete_fuori_non_cancella_niente(self, progetto):
        radice, fuori = progetto
        vittima = fuori / "config.json"
        esito = execute_admin_tool("delete", {"path": str(vittima)}, str(radice))
        assert esito["success"] is False
        assert vittima.exists()

    def test_un_percorso_buono_funziona_ancora(self, progetto):
        radice, _ = progetto
        esito = execute_admin_tool("read_file", {"path": "src/app.py"}, str(radice))
        assert esito["success"] is True


def test_la_modalita_non_stretta_serve_solo_per_le_etichette(progetto):
    """Due punti del ciclo usano il percorso come stringa da confrontare, non
    per aprire nulla. Li' il confine non si applica, e deve restare cosi':
    farli sollevare fermerebbe il run per una questione di etichette."""
    radice, fuori = progetto
    assert resolve_workspace_path(
        str(fuori / "config.json"), str(radice), strict=False)
