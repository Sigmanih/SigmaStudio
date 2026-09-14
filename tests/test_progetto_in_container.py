"""Un progetto nuovo nasce dentro il contenitore, non sulla macchina di chi lo crea.

`crea_progetto` faceva solo la cartella. Senza `sandbox.json` dentro,
l'esecutore ricade sulla configurazione generale — che dice `host` — e un
progetto nato per essere isolato lavora invece sull'host. Nessuno lo sceglie:
succede perche' il file non c'era, ed e' il modo piu' silenzioso di perdere
una garanzia che si crede di avere.

La domanda era esattamente questa: «se apro un altro task e avvio un progetto
nuovo, lo assegna direttamente al container?». Prima la risposta era no.
"""

import json

import pytest

from core import progetti


@pytest.fixture
def radice(tmp_path, monkeypatch):
    monkeypatch.setattr(progetti, "radice_progetti", lambda: tmp_path)
    return tmp_path


class TestIlProgettoNasceIsolato:
    def test_la_cartella_c_e(self, radice):
        cartella = progetti.crea_progetto("libreria")
        assert cartella.is_dir()

    def test_e_dentro_c_e_la_sandbox(self, radice):
        """Il file e' la differenza fra «isolato» e «si credeva isolato»."""
        cartella = progetti.crea_progetto("libreria")
        assert (cartella / "sandbox.json").is_file()

    def test_la_modalita_e_contenitore(self, radice):
        dati = json.loads((progetti.crea_progetto("x") / "sandbox.json").read_text(encoding="utf-8"))
        assert dati["mode"] == "container"

    def test_l_immagine_ha_node_e_python(self, radice):
        """All'inizio non si sa cosa sara': un frontend Vite dentro
        `python:3.12-slim` non ha `npm`, e la prima verifica fallisce per una
        ragione che non c'entra niente con il lavoro."""
        dati = json.loads((progetti.crea_progetto("x") / "sandbox.json").read_text(encoding="utf-8"))
        assert "nodejs" in dati["image"] and "python" in dati["image"]

    def test_la_nota_dice_il_limite_prima_che_lo_si_incontri(self, radice):
        """`docker compose up` da dentro un contenitore non vede il Docker
        dell'host. Scoprirlo a meta' di un run costa il run."""
        dati = json.loads((progetti.crea_progetto("x") / "sandbox.json").read_text(encoding="utf-8"))
        assert "docker compose" in dati["_nota"]
        assert "host" in dati["_nota"]


class TestCosaSiPuoCambiare:
    def test_si_puo_chiedere_altro(self, radice):
        cartella = progetti.crea_progetto("y", sandbox={"image": "node:22-slim"})
        dati = json.loads((cartella / "sandbox.json").read_text(encoding="utf-8"))
        assert dati["image"] == "node:22-slim"
        assert dati["mode"] == "container", "cio' che non si chiede resta il predefinito"

    def test_si_puo_non_volerla(self, radice):
        cartella = progetti.crea_progetto("z", con_sandbox=False)
        assert not (cartella / "sandbox.json").exists()

    def test_una_sandbox_gia_scritta_non_viene_sovrascritta(self, radice):
        """Riaprire un progetto non deve cancellare la scelta di chi lo conosce:
        BibliotecaDigitale sta su `host` con la ragione scritta dentro."""
        cartella = radice / "esistente"
        cartella.mkdir()
        (cartella / "sandbox.json").write_text(
            json.dumps({"mode": "host", "_nota": "deve pubblicare lo stack"}),
            encoding="utf-8")
        progetti.crea_progetto("esistente")
        dati = json.loads((cartella / "sandbox.json").read_text(encoding="utf-8"))
        assert dati["mode"] == "host"


class TestLEsecutoreLaLeggeDavvero:
    """Scrivere il file e non farlo leggere sarebbe la solita capacita' mai
    raggiunta: qui si controlla l'anello intero."""

    def test_l_esecutore_scelto_e_il_contenitore(self, radice):
        from core.harness.esecutori import scegli_esecutore

        cartella = progetti.crea_progetto("prova_container")
        esecutore = scegli_esecutore(radice=str(cartella))
        assert type(esecutore).__name__ == "EsecutoreContenitore"

    def test_e_usa_l_immagine_del_progetto(self, radice):
        from core.harness.esecutori import scegli_esecutore

        cartella = progetti.crea_progetto("prova2", sandbox={"image": "node:22-slim"})
        esecutore = scegli_esecutore(radice=str(cartella))
        assert esecutore.immagine == "node:22-slim"

    def test_senza_sandbox_resta_com_era(self, radice):
        """La modifica non deve cambiare il comportamento di chi non l'ha chiesta."""
        from core.harness.esecutori import scegli_esecutore

        cartella = progetti.crea_progetto("nuda", con_sandbox=False)
        esecutore = scegli_esecutore(radice=str(cartella))
        assert type(esecutore).__name__ == "EsecutoreHost"


def test_la_rotta_che_crea_i_progetti_passa_di_qui():
    """Il pannello chiama la rotta, non la funzione: se la rotta scrivesse la
    cartella per conto proprio, la sandbox non arriverebbe mai."""
    import inspect

    from core.modules.sigma_developer_lab import handlers

    sorgente = inspect.getsource(handlers.handle_project_create)
    assert "crea_progetto(" in sorgente


class TestUnaPortaOccupataNonFermaLaSandbox:
    """Il primo progetto creato con la sandbox non e' partito affatto:

        Bind for 0.0.0.0:3000 failed: port is already allocated

    Sulla 3000 c'era il backend della Biblioteca, acceso e legittimo. Docker
    rifiuta di avviare il contenitore se una porta da inoltrare e' presa, e il
    messaggio parla di un'altra applicazione mentre ferma questa. Partire senza
    quell'inoltro e' sempre meglio che non partire.
    """

    def test_la_porta_presa_non_viene_inoltrata(self, monkeypatch):
        from core.harness import esecutori

        monkeypatch.setattr(esecutori, "_porta_occupata", lambda p: p == "3000")
        es = esecutori.EsecutoreContenitore(
            immagine="node:22-slim", rete=True, ports=["3000:3000", "5173:5173"])
        argv = es.argv("npm test", cwd=".")
        assert "5173:5173" in argv, "le altre porte restano"
        assert "3000:3000" not in argv

    def test_quando_sono_tutte_libere_non_cambia_niente(self, monkeypatch):
        from core.harness import esecutori

        monkeypatch.setattr(esecutori, "_porta_occupata", lambda p: False)
        es = esecutori.EsecutoreContenitore(
            immagine="node:22-slim", rete=True, ports=["3000:3000", "5173:5173"])
        argv = es.argv("npm test", cwd=".")
        assert "3000:3000" in argv and "5173:5173" in argv

    def test_la_domanda_non_occupa_la_porta_a_sua_volta(self):
        """Una verifica che si mette in ascolto per sapere se qualcuno ascolta
        renderebbe occupata ogni porta che controlla."""
        from core.harness.esecutori import _porta_occupata

        assert _porta_occupata("54321") is False
        assert _porta_occupata("54321") is False

    def test_un_valore_storto_non_solleva(self):
        from core.harness.esecutori import _porta_occupata

        assert _porta_occupata("") is False
        assert _porta_occupata("abc") is False
