# ==============================================================================
# tests/test_canale_ragionamento.py — Dove finisce il pensiero, dove comincia
# la risposta
# ==============================================================================
"""La chat ragionava e non rispondeva. Non era il modello.

Segnalato dal vivo il 22 settembre 2026, in chat normale e in modalita'
sviluppo. Il ragionamento compariva, poi si interrompeva a meta' frase e
continuava dentro la bolla della risposta, con i backtick spaiati che
rompevano il markdown da li' in poi. La risposta vera non arrivava mai.

La causa: chi separava i due canali cercava i tag come **sottostringhe,
ovunque**. Quando il modello ragionava *sui* tag — cosa che fa ogni volta che
gli si chiede di diagnosticare un output rotto — scriveva nel proprio
ragionamento frasi come «il modello ha dimenticato di emettere </think>», e
quel tag citato veniva preso per un comando.

Tre effetti, tutti osservati:

1. il tag veniva **cancellato** dal testo, lasciando i backtick aperti;
2. il canale si **ribaltava** a meta' ragionamento;
3. se piu' avanti veniva nominato un tag di apertura, la **risposta finiva nel
   canale del pensiero** e l'utente non vedeva niente.

La regola nuova e' strutturale: un tag e' un comando solo se apre la sua riga,
o se e' attaccato al testo che lo precede. Un tag nominato in una frase ha uno
spazio o un backtick davanti, e resta testo — **dove si trova**, senza essere
cancellato.
"""
import unittest

from core.think_channel import RouterPensiero, separa


class TestIlCasoSegnalato(unittest.TestCase):
    """Il ragionamento che parla dei tag, riprodotto com'era."""

    def test_un_tag_di_chiusura_nominato_non_chiude_il_blocco(self):
        flusso = (
            "<think>\n"
            "Il modello ha dimenticato di emettere </think> e il testo si e' rotto.\n"
            "Devo spiegarlo a Diego con calma.\nProcedo.\n"
            "</think>\n"
            "Ciao Diego, ecco la diagnosi completa."
        )
        risposta, pensiero = separa(flusso)
        self.assertEqual(risposta.strip(), "Ciao Diego, ecco la diagnosi completa.")
        self.assertIn("Devo spiegarlo a Diego", pensiero)
        self.assertNotIn("Devo spiegarlo a Diego", risposta)

    def test_il_tag_nominato_resta_nel_testo(self):
        """Cancellarlo lasciava «ho visto tag `` sparsi»: due backtick vuoti,
        e il markdown rotto per tutto il resto del messaggio."""
        flusso = "<think>\nHo visto tag `<think>` sparsi nel mezzo.\n</think>\nCiao."
        _, pensiero = separa(flusso)
        self.assertIn("`<think>`", pensiero)
        self.assertNotIn("``", pensiero)

    def test_la_risposta_non_finisce_nel_canale_del_pensiero(self):
        """Il guasto peggiore: l'utente vede ragionare e non vede rispondere."""
        flusso = (
            "<think>\n"
            "Ricordo che </think> chiude il blocco e che <think> lo apre.\n"
            "Procedo.\n"
            "</think>\n"
            "Ciao Diego, questa e' la risposta che ti serve."
        )
        risposta, _ = separa(flusso)
        self.assertIn("questa e' la risposta che ti serve", risposta)


class TestICasiVeri(unittest.TestCase):
    """Le forme che i modelli emettono davvero devono continuare a funzionare."""

    def test_blocco_su_piu_righe(self):
        risposta, pensiero = separa("<think>\nRifletto.\n</think>\nEcco la risposta.")
        self.assertEqual(risposta.strip(), "Ecco la risposta.")
        self.assertEqual(pensiero.strip(), "Rifletto.")

    def test_blocco_compatto_su_una_riga_sola(self):
        """`<think>…</think>Risposta` senza a capo: se non si chiudesse, tutta
        la risposta resterebbe dentro il ragionamento."""
        risposta, pensiero = separa("<think>Rifletto.</think>Ecco la risposta.")
        self.assertEqual(risposta.strip(), "Ecco la risposta.")
        self.assertEqual(pensiero.strip(), "Rifletto.")

    def test_canale_alternativo(self):
        risposta, pensiero = separa(
            "<|channel>thought\nRifletto.\n<channel|>\nEcco la risposta.")
        self.assertEqual(risposta.strip(), "Ecco la risposta.")
        self.assertEqual(pensiero.strip(), "Rifletto.")

    def test_nessun_tag_e_tutta_risposta(self):
        risposta, pensiero = separa("Ecco la risposta, senza ragionamento.")
        self.assertEqual(risposta.strip(), "Ecco la risposta, senza ragionamento.")
        self.assertEqual(pensiero, "")

    def test_il_codice_nella_risposta_puo_contenere_i_tag(self):
        """Dopo la chiusura, un tag e' testo: una risposta che mostra un
        esempio di `<think>` non deve tornare nel canale del pensiero."""
        flusso = (
            "<think>\nOk.\n</think>\n"
            "Ecco il formato:\n```\n<think>esempio</think>\n```\nFine."
        )
        risposta, pensiero = separa(flusso)
        self.assertIn("<think>esempio</think>", risposta)
        self.assertIn("Fine.", risposta)
        self.assertEqual(pensiero.strip(), "Ok.")


class TestLoStreamAPacchetti(unittest.TestCase):
    """In rete il testo arriva a pezzi, e i pezzi tagliano i tag a meta'."""

    def _a_pezzi(self, testo, dimensione):
        router = RouterPensiero()
        pezzi = []
        for i in range(0, len(testo), dimensione):
            pezzi.extend(router.feed(testo[i:i + dimensione]))
        pezzi.extend(router.flush())
        risposta = "".join(t for c, t in pezzi if c == "token")
        pensiero = "".join(t for c, t in pezzi if c == "thinking")
        return risposta, pensiero

    def test_un_tag_spezzato_fra_due_pacchetti_viene_riconosciuto(self):
        """Il filtro precedente confrontava un token alla volta: `</thi` +
        `nk>` non lo vedeva affatto, e il blocco non si chiudeva piu'."""
        flusso = "<think>\nRifletto.\n</think>\nEcco la risposta."
        for dimensione in (1, 2, 3, 5, 7, 13):
            with self.subTest(pacchetto=dimensione):
                risposta, pensiero = self._a_pezzi(flusso, dimensione)
                self.assertEqual(risposta.strip(), "Ecco la risposta.")
                self.assertEqual(pensiero.strip(), "Rifletto.")

    def test_niente_va_perso_fra_i_due_canali(self):
        flusso = "<think>\nUno due tre.\n</think>\nQuattro cinque sei."
        for dimensione in (1, 4, 9):
            with self.subTest(pacchetto=dimensione):
                risposta, pensiero = self._a_pezzi(flusso, dimensione)
                intero = (pensiero + risposta).replace("\n", " ").split()
                self.assertEqual(
                    intero,
                    ["Uno", "due", "tre.", "Quattro", "cinque", "sei."],
                    "ogni parola deve arrivare, in ordine, su un canale o sull'altro",
                )


class TestIlRouterEUnoSolo(unittest.TestCase):
    """Erano due implementazioni della stessa regola, e divergevano."""

    def test_la_chat_usa_il_router_condiviso(self):
        from core.chat.chat_runner import _ThinkTagRouter

        self.assertIs(_ThinkTagRouter, RouterPensiero)

    def test_il_ciclo_dellagente_usa_il_router_condiviso(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        self.assertIn("router_pensiero = RouterPensiero()", sorgente)
        self.assertIn("router_pensiero.feed(token)", sorgente)
        self.assertIn("router_pensiero.flush()", sorgente)

    def test_nessuna_uscita_dal_blocco_basata_sulla_lingua(self):
        """La via d'uscita era `"\\n\\nCiao"`: una risposta che non cominciava
        col saluto giusto restava invisibile."""
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        # Senza i commenti: il commento che sostituisce quel codice **nomina**
        # le stringhe tolte, per dire perche' non ci sono piu'. Cercarle li'
        # dentro farebbe fallire il test per la sua stessa documentazione.
        codice = "\n".join(
            riga for riga in inspect.getsource(_stream_agent_turn_impl).splitlines()
            if not riga.lstrip().startswith("#")
        )
        for spia in ('"\\n\\nCiao"', '"\\n\\n**Sigma"'):
            self.assertNotIn(spia, codice,
                             f"euristica sulla lingua ancora presente: {spia}")


class TestIlPrefill(unittest.TestCase):
    """Quando si inietta `<think>` come inizio del turno dell'assistente, il
    modello continua DENTRO il blocco e non emette nessun tag di apertura.

    Chi prefillava lo diceva al router scrivendogli dentro un attributo
    privato. Al primo cambio di nome quella riga ha smesso di fare qualcosa,
    in silenzio, e tutto il ragionamento sarebbe finito nella risposta: e' lo
    schema «scritto, testato, scollegato» applicato a una riga sola.
    """

    def test_il_router_puo_partire_gia_nel_pensiero(self):
        router = RouterPensiero()
        router.inizia_nel_pensiero()
        pezzi = router.feed("Sto ragionando.\n</think>\nEcco la risposta.")
        pezzi += router.flush()
        risposta = "".join(t for c, t in pezzi if c == "token").strip()
        pensiero = "".join(t for c, t in pezzi if c == "thinking").strip()
        self.assertEqual(risposta, "Ecco la risposta.")
        self.assertEqual(pensiero, "Sto ragionando.")

    def test_la_chat_usa_il_metodo_e_non_un_attributo_privato(self):
        import inspect

        from core.chat.chat_runner import _stream_chat_response

        sorgente = inspect.getsource(_stream_chat_response)
        self.assertIn("router.inizia_nel_pensiero()", sorgente)
        self.assertNotIn(
            "router._in_thinking",
            sorgente,
            "toccare un attributo privato si scollega al primo cambio di nome",
        )

    def test_ogni_router_creato_nel_giro_dei_tool_viene_riarmato(self):
        """Il router si ricrea a ogni giro del ciclo strumenti: se uno dei
        punti dimentica il prefill, il ragionamento di quel giro esce fuori."""
        import inspect

        from core.chat.chat_runner import _stream_chat_response

        sorgente = inspect.getsource(_stream_chat_response)
        creazioni = sorgente.count("_ThinkTagRouter()")
        riarmi = sorgente.count("inizia_nel_pensiero()")
        self.assertEqual(
            creazioni, riarmi,
            f"{creazioni} router creati ma {riarmi} riarmati: uno perde il prefill")


class TestIlProfiloArrivaAlModello(unittest.TestCase):
    """`thinking` esisteva fino in fondo e nessuno lo passava.

    `UnifiedRuntime.generate_stream` lo accetta da sempre, e il backend
    llama-server lo traduce in `chat_template_kwargs.enable_thinking`. Ma la
    catena si interrompeva a `call_ai_model_stream`, che non aveva il
    parametro: il template Qwen3 restava in modalita' ragionamento anche per i
    profili che chiedono una risposta diretta.

    L'effetto osservato: il modello ragionava lo stesso, **senza tag**, e
    quel monologo in inglese usciva nella bolla della risposta consumando il
    budget di token prima di arrivare a rispondere davvero. Nessun router puo'
    separare un ragionamento che non e' marcato: la correzione sta a monte.
    """

    def test_lo_strato_dei_provider_accetta_il_parametro(self):
        import inspect

        from core.ai_providers import call_ai_model_stream

        self.assertIn("thinking", inspect.signature(call_ai_model_stream).parameters)

    def test_lo_strato_dei_provider_lo_inoltra_al_motore(self):
        import inspect

        from core.ai_providers import call_ai_model_stream

        sorgente = inspect.getsource(call_ai_model_stream)
        self.assertIn("thinking=thinking", sorgente)

    def test_il_motore_lo_accetta(self):
        import inspect

        from core.engine.unified_runtime import UniversalSigmaEngine

        self.assertIn(
            "thinking",
            inspect.signature(UniversalSigmaEngine.generate_stream).parameters)

    def test_la_chat_lo_passa_dal_profilo(self):
        """Il pezzo che mancava: un chiamante di produzione che lo fornisca."""
        import inspect

        from core.chat.chat_runner import _stream_chat_response

        sorgente = inspect.getsource(_stream_chat_response)
        self.assertIn("thinking=wants_reasoning", sorgente)


class TestLaRispostaNonSpariceMai(unittest.TestCase):

    def test_il_router_dice_quando_la_risposta_e_vuota(self):
        """Chi chiama deve poter promuovere il ragionamento a risposta quando
        il modello non ha mai chiuso il blocco."""
        router = RouterPensiero()
        router.feed("<think>\nRagiono e mi dimentico di chiudere.")
        router.flush()
        self.assertTrue(router.risposta_vuota)

    def test_una_risposta_vera_non_risulta_vuota(self):
        router = RouterPensiero()
        router.feed("<think>\nOk.\n</think>\nEcco.")
        router.flush()
        self.assertFalse(router.risposta_vuota)

    def test_la_chat_promuove_il_ragionamento_quando_manca_la_risposta(self):
        import inspect

        from core.chat.chat_runner import _stream_chat_response

        sorgente = inspect.getsource(_stream_chat_response)
        self.assertIn("clean_text, thinking_out = thinking_out, \"\"", sorgente)


if __name__ == "__main__":
    unittest.main()


class TestIlCodiceNonVienePulito(unittest.TestCase):
    """La seconda passata cancellava ogni tag da tutta la risposta.

    `_clean_all_tags` finiva con una riga sola che toglieva qualunque tag XML
    dal testo intero, recinti di codice compresi. Per un assistente che scrive
    codice e' distruttivo: un esempio HTML arrivava senza i suoi elementi, e
    una spiegazione che nominava un tag lasciava due backtick vuoti — gli
    stessi che rompevano il markdown da li' in poi.

    E' il residuo visibile nella risposta del 22 settembre: «il tag di
    chiusura ``» con i backtick vuoti al posto del tag.
    """

    def _pulito(self, testo):
        from core.chat.response_parser import _clean_all_tags

        return _clean_all_tags(testo, "")[0]

    def test_un_tag_nominato_fra_backtick_resta(self):
        self.assertEqual(
            self._pulito("Il tag `</think>` chiude il blocco."),
            "Il tag `</think>` chiude il blocco.",
        )

    def test_un_esempio_html_in_un_recinto_resta_intero(self):
        testo = "Ecco:\n```html\n<div>\n  <span>ciao</span>\n</div>\n```\nFine."
        pulito = self._pulito(testo)
        self.assertIn("<div>", pulito)
        self.assertIn("<span>ciao</span>", pulito)

    def test_i_componenti_jsx_in_riga_restano(self):
        self.assertEqual(
            self._pulito("Usa `<Button>` dentro `<Form>` per il layout."),
            "Usa `<Button>` dentro `<Form>` per il layout.",
        )

    def test_un_involucro_nella_prosa_viene_ancora_tolto(self):
        """La pulizia serve ancora: alcuni modelli avvolgono la risposta."""
        self.assertEqual(
            self._pulito("<response>Ecco la risposta.</response>"),
            "Ecco la risposta.",
        )

    def test_il_testo_normale_non_viene_toccato(self):
        self.assertEqual(
            self._pulito("Nessun tag qui, solo testo."),
            "Nessun tag qui, solo testo.",
        )


class TestLaRegolaEUnaSolaOvunque(unittest.TestCase):
    """Il percorso NON in streaming aveva la sua copia, e il suo difetto.

    `parse_thinking_and_content` in core/ai_providers.py era la quarta
    implementazione della stessa separazione, con lo stesso errore delle
    altre tre: `re.search(r'<think>(.*?)</think>')` prende la prima chiusura
    che trova, ovunque sia. Serve `assistant_orchestrator` e `execute_loop`,
    che non passano dallo streaming: finche' la regola e' rimasta duplicata
    li', correggere il router non li copriva.

    Questa classe viene dal lavoro dell'agente sulla voce
    `v2_seconda_pipeline_chat`, esteso ai chiamanti che il task non aveva
    considerato.
    """

    def test_il_percorso_non_streaming_usa_il_router(self):
        from core.ai_providers import parse_thinking_and_content

        risposta, pensiero = parse_thinking_and_content(
            "<think>\nIl modello ha dimenticato </think> e si e' rotto.\n"
            "Procedo.\n</think>\nCiao, ecco la diagnosi."
        )
        self.assertEqual(risposta.strip(), "Ciao, ecco la diagnosi.")
        self.assertIn("</think>", pensiero)

    def test_il_percorso_non_streaming_regge_il_blocco_compatto(self):
        from core.ai_providers import parse_thinking_and_content

        risposta, pensiero = parse_thinking_and_content("<think>Rifletto.</think>Ecco.")
        self.assertEqual(risposta.strip(), "Ecco.")
        self.assertEqual((pensiero or "").strip(), "Rifletto.")

    def test_senza_tag_niente_viene_spostato(self):
        from core.ai_providers import parse_thinking_and_content

        testo = "Risposta diretta, senza ragionamento."
        risposta, pensiero = parse_thinking_and_content(testo)
        self.assertEqual(risposta.strip(), testo)
        self.assertFalse((pensiero or "").strip())


class TestLaSecondaPassataNonTogliePiuIlRagionamento(unittest.TestCase):
    """I due casi negativi scritti dall'agente, piu' quello che mancava.

    Tolto lo stadio 1, `_clean_all_tags` non deve toccare una risposta
    legittima che gli somiglia.
    """

    def _pulito(self, testo):
        from core.chat.response_parser import _clean_all_tags

        return _clean_all_tags(testo, "")

    def test_un_elenco_puntato_resta_intero(self):
        risposta = "- primo punto\n- secondo punto"
        pulita, pensiero = self._pulito(risposta)
        self.assertEqual(pulita, risposta)
        self.assertIsNone(pensiero)

    def test_una_risposta_in_inglese_resta_intera(self):
        risposta = ("The quick brown fox jumps over the lazy dog. "
                    "This is a simple explanation in English.")
        pulita, pensiero = self._pulito(risposta)
        self.assertEqual(pulita, risposta)
        self.assertIsNone(pensiero)

    def test_lo_stadio_uno_non_c_e_piu(self):
        """Se torna, torna anche la doppia estrazione."""
        import inspect

        from core.chat.response_parser import _clean_all_tags

        sorgente = inspect.getsource(_clean_all_tags)
        self.assertNotIn('_TAG_PATTERNS["thinking"]', sorgente)
