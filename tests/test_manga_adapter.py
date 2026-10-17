# ==============================================================================
# tests/test_manga_adapter.py — Trasposizione da fumetto: le parti deterministiche
# ==============================================================================
"""Cio' che decide la fedelta' di una trasposizione e si prova senza modelli:
l'ordine di lettura del manga, la ricomposizione dei testi, il riconoscimento
delle tavole a colori e la scelta dei nomi propri fra le parole dei balloon.

Ogni caso viene dal collaudo sul capitolo 1 di Mx0.
"""
import pytest

PIL = pytest.importorskip("PIL.Image")

from core.modules.sigma_creative_lab.video import manga, tools  # noqa: E402
from core.modules.sigma_creative_lab.video.manga import Vignetta  # noqa: E402


class TestOrdineManga:

    def test_colonna_a_destra_prima_della_sinistra(self):
        """Pagina 010: vignetta alta a tutta pagina a destra, colonna di quattro a sinistra."""
        destra = Vignetta(240, 36, 559, 899)
        sinistra = [Vignetta(24, 0, 234, 76), Vignetta(25, 85, 234, 356),
                    Vignetta(25, 335, 234, 465), Vignetta(25, 465, 234, 899)]
        ordine = manga.ordina_manga(sinistra[::-1] + [destra], 560, 900)
        assert ordine[0] == destra
        assert ordine[1:] == sinistra

    def test_righe_dall_alto_e_dentro_da_destra(self):
        """Pagina 020: la vignetta grande a destra sborda di poco nella riga di sotto."""
        boxes = [[16, 0, 239, 365], [251, 0, 562, 599], [19, 357, 224, 562],
                 [351, 603, 561, 899], [129, 573, 377, 899], [19, 562, 129, 899]]
        ordine = [v.box for v in manga.ordina_manga([Vignetta(*b) for b in boxes], 563, 900)]
        assert ordine == [[251, 0, 562, 599], [16, 0, 239, 365], [19, 357, 224, 562],
                          [351, 603, 561, 899], [129, 573, 377, 899], [19, 562, 129, 899]]


class TestTesti:

    def test_balloon_da_destra(self):
        """008_04: «devo liberarmi di questo peso» (destra) viene prima dell'altro pensiero."""
        testi = manga.ordina_testi([
            {"testo": "DEVO TROVARLA E DIRLE IL FATTO SUO.", "box": [437, 108, 692, 335]},
            {"testo": "DEVO LIBERARMI DI QUESTO PESO,", "box": [720, 87, 950, 300]},
        ])
        assert testi[0]["testo"].startswith("DEVO LIBERARMI")

    def test_parole_a_capo_ricomposte_onorifici_no(self):
        letto = manga._normalizza_lettura({"testi": [
            {"tipo": "battuta", "testo": "SEI SO-SPETTO! STA PARLANDO DI HIRAGI-SENSEI? AIKA-CHAN"}]})
        assert letto["testi"][0]["testo"] == "SEI SOSPETTO! STA PARLANDO DI HIRAGI-SENSEI? AIKA-CHAN"

    def test_tipo_sconosciuto_diventa_battuta(self):
        letto = manga._normalizza_lettura({"testi": [{"tipo": "urlo", "testo": "AAAH!"}]})
        assert letto["testi"][0]["tipo"] == "battuta"

    def test_balloon_sconfinato_tolto(self):
        """010: il margine del ritaglio prendeva «SEI SOSPETTO!» dalla vignetta accanto."""
        vv = [{"testi": [{"tipo": "battuta", "testo": "ALLORA PERCHE' STAI SCAVALCANDO"},
                         {"tipo": "battuta", "testo": "SEI SOSPETTO!"}]},
              {"testi": [{"tipo": "battuta", "testo": "SEI SOSPETTO! VIENI UN MOMENTO QUI!"}]}]
        assert manga.togli_sconfinati(vv) == 1
        assert [t["testo"] for t in vv[0]["testi"]] == ["ALLORA PERCHE' STAI SCAVALCANDO"]


class TestPagine:

    def test_colore_nera_bn(self, tmp_path):
        colore = tmp_path / "005.jpg"
        PIL.new("RGB", (60, 90), (220, 120, 40)).save(colore)
        nera = tmp_path / "004.jpg"
        PIL.new("RGB", (60, 90), (5, 5, 5)).save(nera)
        bn = tmp_path / "010.jpg"
        PIL.new("RGB", (60, 90), (200, 200, 200)).save(bn)
        assert manga.classifica_pagina(colore) == "colore"
        assert manga.classifica_pagina(nera) == "nera"
        assert manga.classifica_pagina(bn) == "bn"


class TestNomi:

    @pytest.mark.parametrize("parola,atteso", [
        ("AIKA", True), ("KUZUMI", True), ("TAIGA", True), ("HIRAGI", True),
        ("ANDARE", True), ("SCAVALCARE", False), ("COSA", False),
    ])
    def test_forma_giapponese(self, parola, atteso):
        assert tools._e_romaji(parola) is atteso

    def test_cast_dalle_battute(self, monkeypatch):
        """Nomi veri si', parole comuni con la stessa forma no."""
        stato = {"pagine": [{"pagina": "025.jpg", "vignette": [
            {"id": "025_02", "testi": [{"tipo": "battuta", "testo": "AIKA! ASPETTACI!"}]},
            {"id": "025_03", "testi": [{"tipo": "battuta", "testo": "SEI STRANA, AIKA."}]},
            {"id": "032_07", "testi": [{"tipo": "battuta", "testo": "KUZUMI TAIGA!!"}]},
            {"id": "051_02", "testi": [{"tipo": "battuta", "testo": "E' OPERA DI KUZUMI TAIGA"}]},
            {"id": "011_04", "testi": [{"tipo": "battuta", "testo": "LA MAGIA ESISTE. UNA MAGIA VERA."}]},
            {"id": "016_01", "testi": [{"tipo": "battuta", "testo": "LA MAGIA? SEI UNA MATRICOLA?"}]},
            {"id": "020_06", "testi": [{"tipo": "battuta", "testo": "STA PARLANDO DI HIRAGI-SENSEI?"}]},
            {"id": "005_01", "testi": [{"tipo": "didascalia", "testo": "MI ARRAMPICAI SU PER IL PENDIO"}]},
        ]}]}
        monkeypatch.setattr(tools, "_vignette", lambda pid: (stato, None))
        r = tools.video_manga_cast("prova_manga_cast")
        nomi = {c["name"] for c in r["candidates"]}
        assert {"AIKA", "KUZUMI", "TAIGA", "HIRAGI-SENSEI"} <= nomi
        assert not nomi & {"MAGIA", "UNA"}
        assert r["narrator_hint"]


class TestVoci:

    def test_riattribuisce_col_copione(self, tmp_path):
        """010_01: la vista dava «STA VOLANDO!!!» a Hiragi-sensei, che e' in scena; la dice Taiga."""
        import json
        stato = {"pagine": [{"pagina": "010.jpg", "vignette": [{
            "id": "010_01", "testi": [{"tipo": "battuta", "testo": "STA VOLANDO!!!", "chi": "fuori campo"},
                                      {"tipo": "onomatopea", "testo": "FUUU"}],
            "regia": {"presenti": ["Hiragi-sensei"], "shot_en": "low angle on Hiragi-sensei above the gate",
                      "voci": {"0": {"chi": "Hiragi-sensei", "fuori_campo": False}}}}]}]}
        (tmp_path / "vignette.json").write_text(json.dumps(stato), encoding="utf-8")
        visti = []

        def genera(messaggi, _max):
            visti.append(messaggi[0]["content"])
            return '{"lines": [{"id": "L1", "who": "Kuzumi Taiga", "off_screen": true}]}'

        esito = manga.rivedi_voci(tmp_path, ["Kuzumi Taiga", "Hiragi-sensei", "Comparsa"], "Kuzumi Taiga",
                                  "Comparsa", genera)
        assert esito == {"lines": 1, "changed": 1}
        assert "FUUU" not in visti[0]          # le onomatopee non si attribuiscono
        voce = json.loads((tmp_path / "vignette.json").read_text(encoding="utf-8"))["pagine"][0]["vignette"][0]
        assert voce["regia"]["voci"]["0"] == {"chi": "Kuzumi Taiga", "fuori_campo": True}
        assert voce["regia"]["voci_riviste"] is True

    def test_nome_inventato_ignorato(self, tmp_path):
        import json
        stato = {"pagine": [{"pagina": "020.jpg", "vignette": [{
            "id": "020_01", "testi": [{"tipo": "battuta", "testo": "E TU CHI SEI?"}],
            "regia": {"presenti": [], "voci": {"0": {"chi": "Aika", "fuori_campo": False}}}}]}]}
        (tmp_path / "vignette.json").write_text(json.dumps(stato), encoding="utf-8")
        esito = manga.rivedi_voci(tmp_path, ["Aika"], "Aika", "Comparsa",
                                  lambda m, n: '{"lines": [{"id": "L1", "who": "Mister X"}]}')
        assert esito["changed"] == 0


class TestStoryboard:

    def test_piu_pagine_con_didascalie_ed_esclusioni(self, tmp_path):
        """Una didascalia (fuori campo) seguita da un'altra pagina: il nome «fuori» serviva
        a due cose e la seconda pagina faceva esplodere il controllo delle esclusioni."""
        import json
        vignetta = lambda vid, testi: {"id": vid, "ritaglio": f"vignette/{vid}.png", "inquadratura": "campo lungo",
                                       "testi": testi, "regia": {"presenti": ["Taiga"], "voci": {}}}
        stato = {"pagine": [
            {"pagina": "004.jpg", "vignette": [vignetta("004_01", [])]},
            {"pagina": "005.jpg", "vignette": [vignetta("005_01", [{"tipo": "didascalia", "testo": "APRILE"}])]},
            {"pagina": "008.jpg", "vignette": [vignetta("008_01", [{"tipo": "battuta", "testo": "CIAO"}])]},
        ]}
        (tmp_path / "vignette.json").write_text(json.dumps(stato), encoding="utf-8")
        shots = manga.storyboard(tmp_path, "Taiga", "Comparsa", ["004"])
        assert [s["panel_id"] for s in shots] == ["005_01", "008_01"]
        assert shots[0]["dialogue"]["off_screen"] is True
        assert shots[0]["dialogue"]["character"] == "Taiga"


class TestRevisione:

    def test_correzione_passa_allo_storyboard_e_resta(self, tmp_path):
        """La battuta corretta cambia voce nell'inquadratura gia' resa, che torna da rifare;
        la regia automatica non la sovrascrive piu'."""
        import json
        stato = {"pagine": [{"pagina": "010.jpg", "vignette": [{
            "id": "010_01", "ritaglio": "vignette/010_01.png", "inquadratura": "figura intera",
            "testi": [{"tipo": "battuta", "testo": "STA VOLANDO!!!"}],
            "regia": {"presenti": ["Hiragi-sensei"], "firma": "x",
                      "voci": {"0": {"chi": "Hiragi-sensei", "fuori_campo": False}}}}]}]}
        (tmp_path / "vignette.json").write_text(json.dumps(stato), encoding="utf-8")
        prod = {"shots": [{"id": "010_01_1", "panel_id": "010_01", "status": "done", "refs": ["Hiragi-sensei"],
                           "dialogue": {"character": "Hiragi-sensei", "text": "STA VOLANDO!!!", "audio": "a.wav"}}]}
        manga.correggi_vignetta(tmp_path, "010_01", None, {"0": {"chi": "Kuzumi Taiga", "fuori_campo": True}})
        assert manga.applica_allo_storyboard(prod, tmp_path, "010_01", "Kuzumi Taiga", "Comparsa") == 1
        shot = prod["shots"][0]
        assert shot["dialogue"]["character"] == "Kuzumi Taiga" and shot["dialogue"]["off_screen"] is True
        assert "audio" not in shot["dialogue"] and shot["status"] == "pending"
        # La regia rifatta con una bibbia diversa salta la vignetta rivista.
        manga.regia_capitolo(tmp_path, [{"name": "Kuzumi Taiga", "description": "nuova"}])
        v = json.loads((tmp_path / "vignette.json").read_text(encoding="utf-8"))["pagine"][0]["vignette"][0]
        assert v["regia"]["voci"]["0"]["chi"] == "Kuzumi Taiga" and v["regia"]["revisione_umana"] is True
        assert manga.elenco_revisione(tmp_path)[0]["rivista"] is True


class TestFotogrammiDaVignetta:

    def test_riferimento_solo_colori_comparsa_esclusa(self, tmp_path):
        """005_03: la comparsa entrava come ragazza inventata, il foglio di Kuzumi come doppione."""
        from core.modules.sigma_creative_lab.video import genres
        ref = tmp_path / "k.png"
        ref.write_bytes(b"x")
        prod = {"bible": {"characters": [{"name": "Kuzumi Taiga", "ref_image": str(ref)},
                                         {"name": "Comparsa Generica", "ref_image": str(ref)}]}}
        shot = {"refs": ["Kuzumi Taiga", "Comparsa Generica"], "prompt": ""}
        bn = tmp_path / "bn.png"
        PIL.new("RGB", (60, 90), (200, 200, 200)).save(bn)
        prompt, refs = genres.panel_keyframe(prod, shot, str(bn))
        assert refs == [str(bn), str(ref)]
        assert "only a color reference for Kuzumi Taiga" in prompt and "do not copy its figure" in prompt
        assert "is the character in image" not in prompt and "Comparsa" not in prompt
        # A colori la vignetta basta: niente foglio da incollare.
        colore = tmp_path / "c.png"
        PIL.new("RGB", (60, 90), (240, 120, 60)).save(colore)
        assert genres.panel_keyframe(prod, shot, str(colore))[1] == [str(colore)]

    def test_correzione_rifa_il_fotogramma(self, monkeypatch):
        """La correzione del QA vale anche per il fotogramma: LTX parte da li'."""
        from core.modules.sigma_creative_lab.video import production
        prod = {"shots": [{"prompt": "p", "keyframe": "k.png", "keyframe_check": {}, "status": "done"}]}

        class Store:
            def get(self, pid):
                return prod

            def save(self, p):
                pass
        monkeypatch.setattr(production.manager, "store", Store())
        out = tools.video_shot_fix("x", 0, "Kuzumi alone, no duplicate")
        shot = prod["shots"][0]
        assert out["success"] and "keyframe" not in shot and shot["status"] == "pending"
        assert shot["keyframe_fixes"] == ["Kuzumi alone, no duplicate"]
        assert shot["prompt_fixes"] == ["Kuzumi alone, no duplicate"]
