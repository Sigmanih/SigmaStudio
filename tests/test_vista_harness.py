# ==============================================================================
# tests/test_vista_harness.py — view_image visto dall'harness
# ==============================================================================
"""L'agente puo' guardare un'immagine solo se il tool esiste in tutti i punti
in cui l'harness lo cerca: schema, policy, ruoli e smistamento. Un tool
concesso da un ruolo ma senza schema non esiste per il modello, e niente lo
segnala: e' il motivo per cui il catalogo si controlla qui.

Il modello di visione non si avvia: `occhio.guarda` e' sostituito, cosi' si
prova che cosa gli arriva (ritaglio, riduzione, domanda) senza caricare 6 GB.
La prova col modello vero sta in `TestModelloVero`, che gira solo se Qwen3-VL
e' installato ed e' marcata lenta.
"""
import io

import pytest

from core.harness import policy, vista
from core.harness.roles import DEV_ROLES
from core.harness.tool_schema import TOOL_SCHEMAS, schemas_for

PIL = pytest.importorskip("PIL.Image")


@pytest.fixture
def pagina(tmp_path):
    """Una pagina 2000x1000 con la meta' destra rossa: abbastanza per vedere ritaglio e riduzione."""
    img = PIL.new("RGB", (2000, 1000), "white")
    img.paste((255, 0, 0), (1000, 0, 2000, 1000))
    percorso = tmp_path / "pagina.png"
    img.save(percorso)
    return percorso


@pytest.fixture
def occhio_finto(monkeypatch):
    visti = []

    def guarda(dati, domanda):
        visti.append({"img": PIL.open(io.BytesIO(dati)), "domanda": domanda})
        return "Una pagina bianca e rossa.", "qwen3vl-finto"

    monkeypatch.setattr(vista.occhio, "guarda", guarda)
    return visti


class TestCatalogo:

    def test_dichiarato_ed_eseguibile(self):
        dichiarati = {s["function"]["name"] for s in TOOL_SCHEMAS}
        assert set(vista.ESECUTORI) <= dichiarati

    def test_policy(self):
        assert "view_image" in policy.ALIASES
        assert policy.canonical("guarda_immagine") == "view_image"
        assert "view_image" in policy.READ_ONLY_TOOLS

    def test_ogni_ruolo_che_lo_concede_lo_vede(self):
        """Il controllo che smaschera una registrazione mancante."""
        concessori = [r for r in DEV_ROLES.values() if "view_image" in r.tools]
        assert concessori, "nessun ruolo puo' guardare un'immagine"
        for ruolo in concessori:
            nomi = {s["function"]["name"] for s in schemas_for(ruolo.tools)}
            assert "view_image" in nomi

    def test_ignora_gli_altri_tool(self):
        assert vista.esegui("read_file", {"path": "x"}) is None


class TestEsecuzione:

    def test_descrive_e_ridimensiona(self, pagina, occhio_finto):
        esito = vista.esegui("view_image", {"path": str(pagina)})
        assert esito["success"], esito
        assert esito["description"] == "Una pagina bianca e rossa."
        assert (esito["width"], esito["height"]) == (2000, 1000)
        visto = occhio_finto[0]["img"]
        assert max(visto.size) == vista.LATO_MASSIMO
        assert "Non inventare" in occhio_finto[0]["domanda"]

    def test_regione_in_frazioni(self, pagina, occhio_finto):
        esito = vista.esegui("view_image", {"path": str(pagina), "region": [0.5, 0, 1, 1]})
        assert esito["region"] == [1000, 0, 2000, 1000]
        visto = occhio_finto[0]["img"].convert("RGB")
        r, g, b = visto.getpixel((visto.width // 2, visto.height // 2))
        assert r > 200 and g < 60 and b < 60

    def test_sinonimi_e_domanda(self, pagina, occhio_finto):
        esito = vista.esegui("view_image", {"file_path": str(pagina), "prompt": "Che colore c'e'?"})
        assert esito["success"]
        assert occhio_finto[0]["domanda"].endswith("Che colore c'e'?")

    def test_percorso_relativo_al_workspace(self, pagina, occhio_finto):
        esito = vista.esegui("view_image", {"path": pagina.name}, radice=str(pagina.parent))
        assert esito["success"], esito

    def test_errori_leggibili(self, tmp_path, occhio_finto):
        assert "non trovata" in vista.esegui("view_image", {"path": "manca.png"})["error"]
        testo = tmp_path / "note.txt"
        testo.write_text("x", encoding="utf-8")
        assert "non e' un'immagine" in vista.esegui("view_image", {"path": str(testo)})["error"]
        assert "Accettati" in vista.esegui("view_image", {"path": "x.png", "colore": 1})["error"]
        assert not occhio_finto

    def test_estensione_sbagliata_suggerisce_il_file(self, pagina, occhio_finto):
        """Collaudo Mx0: l'agente chiedeva 005.png, la scansione era 005.jpg."""
        errore = vista.esegui("view_image", {"path": str(pagina.with_suffix(".jpg"))})["error"]
        assert "pagina.png" in errore

    def test_osservazione_per_l_agente(self, pagina, occhio_finto):
        testo = vista.descrivi(vista.esegui("view_image", {"path": str(pagina)}))
        assert "Una pagina bianca e rossa." in testo
        assert "2000x1000" in testo
        assert not testo.lstrip().startswith("{")


@pytest.mark.skipif(vista.file_modello() is None, reason="Qwen3-VL non installato")
class TestModelloVero:

    def test_legge_un_testo(self, tmp_path):
        from PIL import ImageDraw, ImageFont
        img = PIL.new("RGB", (900, 300), "white")
        try:
            font = ImageFont.truetype("arial.ttf", 64)
        except OSError:
            font = ImageFont.load_default()
        ImageDraw.Draw(img).text((40, 100), "CIAO SIGMA", fill="black", font=font)
        percorso = tmp_path / "scritta.png"
        img.save(percorso)
        try:
            esito = vista.view_image(str(percorso), "Trascrivi il testo dell'immagine.")
        finally:
            vista.occhio.ferma()
        assert esito["success"], esito
        assert "CIAO SIGMA" in esito["description"].upper()
