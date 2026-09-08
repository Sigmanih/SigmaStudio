"""Tradurre un'interfaccia senza rompere il codice che ci sta dentro.

Dentro le stringhe di un'interfaccia ci sono pezzi che **non sono lingua**:
`{nome}` lo sostituisce il runtime, `%s` lo riempie Python, `<0>` e' un
elemento React che avvolge una parte del testo. Un modello che traduce
«Ciao {nome}» in «Hello {name}» ha prodotto una stringa che a runtime mostra
letteralmente `{name}`, e nessuno se ne accorge finche' qualcuno non apre
quella schermata.

I test qui sotto tengono ferme tre cose:

1. i segnaposto **sopravvivono** al giro di traduzione;
2. una traduzione che ne perde uno **viene scartata** — meglio l'originale, che
   almeno funziona;
3. un lotto disallineato **non viene indovinato**: metterebbe ogni traduzione
   sulla chiave sbagliata, ed e' l'errore piu' difficile da vedere, perche'
   ogni singola stringa sembra buona.
"""

import json

import pytest

from core.i18n import translator as T


class TestSegnaposto:
    @pytest.mark.parametrize("testo,quanti", [
        ("Ciao {nome}", 1),
        ("{count} file su {totale}", 2),
        ("Benvenuto %s", 1),
        ("Ciao %(nome)s, hai %(n)d messaggi", 2),
        ("Leggi <0>la guida</0> prima", 2),
        ("Sostituisci $1 con $2", 2),
        ("{{mustache}} e {singolo}", 2),
        ("Nessun segnaposto qui", 0),
    ])
    def test_li_riconosce(self, testo, quanti):
        assert len(T.find_placeholders(testo)) == quanti

    def test_mascherare_e_rimettere_non_cambia_niente(self):
        originale = "Ciao {nome}, hai %s messaggi in <0>posta</0>"
        mascherato, mappa = T.protect(originale)
        assert "{nome}" not in mascherato
        assert T.restore(mascherato, mappa) == originale

    def test_i_segni_non_somigliano_a_niente_di_traducibile(self):
        """`__0__` verrebbe riscritto come `_0_` o spaziato: questi no."""
        mascherato, _ = T.protect("Ciao {nome}")
        assert "⟦0⟧" in mascherato

    def test_le_doppie_graffe_non_vengono_spezzate(self):
        mascherato, mappa = T.protect("{{utente}} ha scritto")
        assert list(mappa.values()) == ["{{utente}}"]


class TestValidazione:
    def test_una_traduzione_intatta_passa(self):
        assert T.validate("Ciao {nome}", "Hello {nome}") == ""

    def test_un_segnaposto_perso_non_passa(self):
        """E' il difetto che questo modulo esiste per impedire."""
        motivo = T.validate("Ciao {nome}", "Hello")
        assert "mancano" in motivo and "{nome}" in motivo

    def test_un_segnaposto_tradotto_non_passa(self):
        motivo = T.validate("Ciao {nome}", "Hello {name}")
        assert "segnaposto alterati" in motivo

    def test_un_segnaposto_duplicato_non_passa(self):
        """Di solito significa che il modello ha ripetuto un pezzo di frase.

        Il confronto va fatto per conteggio, non per appartenenza: `{nome}` due
        volte e' presente in entrambi gli insiemi, e un confronto per
        appartenenza direbbe «alterati» senza saper dire cosa.
        """
        motivo = T.validate("Ciao {nome}", "Hello {nome} {nome}")
        assert "compaiono in piu'" in motivo
        assert "{nome}" in motivo

    def test_una_traduzione_vuota_non_passa(self):
        assert T.validate("Ciao", "   ") == "traduzione vuota"

    def test_i_segni_di_protezione_rimasti_non_passano(self):
        """Significa che il ripristino non ha funzionato: la stringa mostrerebbe
        caratteri incomprensibili."""
        assert "segni di protezione" in T.validate("Ciao", "Hello ⟦0⟧")


class TestGlossario:
    def test_i_termini_da_non_tradurre_devono_restare(self):
        assert T.check_glossary("Apri Sigma Studio", ["Sigma Studio"]) == ""

    def test_un_termine_tradotto_viene_segnalato(self):
        motivo = T.check_glossary("Open Sigma Workshop", ["Sigma Studio"])
        assert "Sigma Studio" in motivo


class TestTraduzioneDelCatalogo:
    def _traduttore(self, prefisso="EN:"):
        def t(testi, lingua):
            return [f"{prefisso}{x}" for x in testi]
        return t

    def test_traduce_tutto_il_catalogo(self):
        esito = T.translate_catalog(
            {"a": "Ciao", "b": "Arrivederci"}, "inglese", self._traduttore())

        assert esito.ok is True
        assert esito.checked == 2
        assert esito.translations["a"] == "EN:Ciao"

    def test_i_segnaposto_arrivano_dall_altra_parte(self):
        esito = T.translate_catalog(
            {"saluto": "Ciao {nome}, hai %s messaggi"}, "inglese", self._traduttore())

        assert esito.ok is True
        assert "{nome}" in esito.translations["saluto"]
        assert "%s" in esito.translations["saluto"]

    def test_una_traduzione_che_rompe_viene_scartata(self):
        """Meglio l'originale, che almeno funziona."""
        def rovina(testi, lingua):
            return ["Hello, no placeholders here" for _ in testi]

        esito = T.translate_catalog({"saluto": "Ciao {nome}"}, "inglese", rovina)

        assert esito.ok is False
        assert "saluto" in esito.problems
        assert esito.translations["saluto"] == "Ciao {nome}"

    def test_un_lotto_disallineato_non_viene_indovinato(self):
        """Metterebbe ogni traduzione sulla chiave sbagliata."""
        def corto(testi, lingua):
            return ["solo una"]

        esito = T.translate_catalog(
            {"a": "uno", "b": "due", "c": "tre"}, "inglese", corto)

        assert len(esito.problems) == 3
        assert all("disallineata" in m for m in esito.problems.values())

    def test_un_traduttore_che_esplode_non_ferma_il_lavoro(self):
        chiamate = {"n": 0}

        def a_tratti(testi, lingua):
            chiamate["n"] += 1
            if chiamate["n"] == 1:
                raise RuntimeError("modello non raggiungibile")
            return [f"EN:{x}" for x in testi]

        catalogo = {f"k{i}": f"testo {i}" for i in range(4)}
        esito = T.translate_catalog(catalogo, "inglese", a_tratti, lotto=2)

        assert len(esito.problems) == 2
        assert len([v for v in esito.translations.values()
                    if v.startswith("EN:")]) == 2

    def test_cio_che_e_gia_tradotto_non_si_ritraduce(self):
        """Su duemila voci e' la differenza fra un aggiornamento e una
        traduzione da capo."""
        visti = []

        def t(testi, lingua):
            visti.extend(testi)
            return [f"EN:{x}" for x in testi]

        esito = T.translate_catalog({"a": "uno", "b": "due"}, "inglese", t,
                                    gia_tradotto={"a": "One"})

        assert visti == ["due"]
        assert esito.translations["a"] == "One"
        assert esito.checked == 1

    def test_le_stringhe_vuote_non_si_traducono(self):
        esito = T.translate_catalog({"a": "  ", "b": "Ciao"}, "inglese",
                                    self._traduttore())
        assert esito.checked == 1
        assert "a" not in esito.translations

    def test_il_glossario_vale_solo_dove_il_termine_c_era(self):
        """Pretendere «GGUF» in una frase che non lo conteneva sarebbe assurdo."""
        def t(testi, lingua):
            return ["Hello world" for _ in testi]

        esito = T.translate_catalog({"a": "Ciao mondo"}, "inglese", t,
                                    glossario=["GGUF"])
        assert esito.ok is True

    def test_un_termine_del_glossario_perso_viene_segnalato(self):
        def t(testi, lingua):
            return ["Open Sigma Workshop"]

        esito = T.translate_catalog({"a": "Apri Sigma Studio"}, "inglese", t,
                                    glossario=["Sigma Studio"])
        assert "a" in esito.problems


class TestIlRapportoPerIlCancello:
    def test_dice_quanti_ne_ha_esaminati(self):
        riga = T.Esito(checked=214).check_line()
        assert riga.startswith("SIGMA-CHECK ")
        dati = json.loads(riga.split(" ", 1)[1])
        assert dati["checked"] == 214
        assert dati["problems"] == 0

    def test_l_harness_lo_riconosce_come_prova(self):
        """Il giro completo: il rapporto scritto qui deve valere di la'."""
        from core.harness.verification import parse_verification

        rapporto = parse_verification(
            "python tools/traduci.py", 0, T.Esito(checked=214).check_line())
        assert rapporto.is_valid is True
        assert rapporto.collected == 214

    def test_una_traduzione_a_vuoto_non_vale_come_prova(self):
        from core.harness.verification import parse_verification

        assert parse_verification(
            "python tools/traduci.py", 0,
            T.Esito(checked=0).check_line()).is_valid is False


class TestIlDialogoColModello:
    def test_il_prompt_chiede_json_e_spiega_i_segnaposto(self):
        """Un elenco numerato in testo libero si sfalsa alla prima stringa con
        un a capo, e ogni traduzione finisce sulla chiave sbagliata."""
        prompt = T.build_prompt(["Ciao ⟦0⟧"], "inglese", ["Sigma Studio"])
        assert "array JSON" in prompt
        assert "⟦0⟧" in prompt
        assert "Sigma Studio" in prompt

    def test_la_risposta_viene_estratta_anche_col_contorno(self):
        risposta = 'Ecco le traduzioni:\n```json\n["Hello", "Bye"]\n```\n'
        assert T.parse_response(risposta, 2) == ["Hello", "Bye"]

    def test_una_risposta_di_lunghezza_sbagliata_viene_rifiutata(self):
        assert T.parse_response('["solo una"]', 3) == []

    def test_una_risposta_non_json_viene_rifiutata(self):
        assert T.parse_response("Hello, Bye", 2) == []

    def test_il_traduttore_a_modello_solleva_se_la_risposta_non_serve(self):
        traduttore = T.make_model_translator(lambda prompt: "boh")
        with pytest.raises(ValueError):
            traduttore(["Ciao"], "inglese")

    def test_il_traduttore_a_modello_funziona_con_una_risposta_buona(self):
        traduttore = T.make_model_translator(lambda prompt: '["Hello"]')
        assert traduttore(["Ciao"], "inglese") == ["Hello"]
