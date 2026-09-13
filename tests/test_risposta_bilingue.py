"""L'inglese non e' sempre ragionamento: a volte e' la risposta.

Chiedendo «parlami del Sigma Studio, scrivimi una breve descrizione sia in
italiano che in inglese», l'utente vedeva arrivare **soltanto** la riga di
chiusura: «Fammi sapere se desideri altre modifiche!». Tutto il resto — la
descrizione italiana e quella inglese — finiva nel ragionamento.

La causa sta in due euristiche nate per un motivo buono: certi modelli lasciano
colare in chiaro il proprio ragionamento, quasi sempre in inglese, prima della
risposta in italiano. Da li' l'assunzione «inglese = ragionamento, italiano =
risposta», che regge quasi sempre e cade esattamente dove serve di piu': una
traduzione, una descrizione bilingue, un messaggio d'errore citato.

Due difese, e servono entrambe:

- se la domanda **chiede** inglese, quelle euristiche non girano;
- se comunque di una risposta sopravvive meno di un quarto, si rimette tutto.
  Un po' di ragionamento in chiaro si legge; una risposta che non c'e' non si
  recupera.
"""

import pytest

from core.chat.response_parser import _clean_all_tags, richiesta_ammette_inglese

DOMANDA_BILINGUE = ("ciao, parlami del sigma studio. scrivimi una breve "
                    "descrizione sia in italiano che in inglese.")

RISPOSTA_BILINGUE = """Plan: describe the studio in two languages.

Sigma Studio e' una postazione di lavoro AI locale che unisce chat e modelli.

Sigma Studio is a local AI workstation combining chat and models.

Fammi sapere se desideri altre modifiche su Sigma Studio!"""

RISPOSTA_QUASI_TUTTA_INGLESE = """Let's craft a bilingual description.

Sigma Studio is a local AI workstation that runs models on your own machine.
It brings chat, model management and a developer harness into one program.

Fammi sapere se desideri altre modifiche su Sigma Studio!"""


class TestIlBugRiprodotto:
    def test_la_descrizione_bilingue_arriva_intera(self):
        testo, _ = _clean_all_tags(RISPOSTA_BILINGUE, DOMANDA_BILINGUE)
        assert "postazione di lavoro AI locale" in testo, "manca l'italiano"
        assert "local AI workstation" in testo, "manca l'inglese"

    def test_non_resta_solo_la_riga_di_chiusura(self):
        """E' il sintomo esatto che l'utente ha visto."""
        testo, _ = _clean_all_tags(RISPOSTA_BILINGUE, DOMANDA_BILINGUE)
        assert testo.strip() != "Fammi sapere se desideri altre modifiche su Sigma Studio!"
        assert len(testo) > len(RISPOSTA_BILINGUE) * 0.5

    def test_vale_anche_per_una_risposta_quasi_tutta_inglese(self):
        testo, _ = _clean_all_tags(RISPOSTA_QUASI_TUTTA_INGLESE, DOMANDA_BILINGUE)
        assert "runs models on your own machine" in testo


class TestLaReteSottoVaSenzaLaDomanda:
    """Tre chiamanti su quattro non hanno la domanda a portata di mano. La
    seconda difesa non dipende da lei."""

    def test_senza_la_domanda_la_risposta_sopravvive_lo_stesso(self):
        testo, _ = _clean_all_tags(RISPOSTA_BILINGUE)
        assert "local AI workstation" in testo
        assert "postazione di lavoro" in testo

    def test_perdere_quasi_tutto_e_sempre_sbagliato(self):
        testo, pensiero = _clean_all_tags(RISPOSTA_QUASI_TUTTA_INGLESE)
        assert len(testo) >= len(RISPOSTA_QUASI_TUTTA_INGLESE) * 0.25
        assert pensiero is None, "non si estrae niente quando il conto non torna"


class TestCioCheDeveContinuareAFunzionare:
    def test_un_blocco_think_esplicito_viene_tolto_come_sempre(self):
        """Le euristiche di lingua hanno una rete; i tag espliciti no, perche'
        non c'e' niente da indovinare: il modello ha detto lui dov'era."""
        grezzo = ("<think>Devo rispondere in italiano, con calma.</think>\n\n"
                  "Sigma Studio e' una postazione di lavoro AI locale che "
                  "unisce chat, modelli e strumenti di sviluppo.")
        testo, pensiero = _clean_all_tags(grezzo, DOMANDA_BILINGUE)
        assert "<think>" not in testo
        assert "Devo rispondere" not in testo
        assert pensiero and "Devo rispondere" in pensiero
        assert "postazione di lavoro" in testo

    def test_un_preambolo_lungo_in_inglese_viene_ancora_tolto(self):
        """Il caso per cui l'euristica esiste: la risposta italiana e' lunga e
        sopravvive largamente, quindi la rete non scatta."""
        grezzo = (
            "We need to answer the user about the modules. The user speaks "
            "Italian, so I should respond in Italian. Let me structure a clear "
            "response about the architecture.\n\n"
            "Ciao! I moduli di Sigma Studio sono organizzati in un kernel e in "
            "moduli installabili. Il kernel contiene il motore di inferenza, "
            "la chat e l'harness dell'agente, mentre i moduli aggiungono "
            "funzioni specifiche come il Training Lab o il Creative Lab. "
            "Ognuno dichiara un manifest che ne descrive backend e frontend, "
            "e il caricatore li monta all'avvio senza che tu debba fare "
            "niente. Se vuoi posso entrare nel dettaglio di uno in "
            "particolare."
        )
        testo, pensiero = _clean_all_tags(grezzo)
        assert "We need to answer" not in testo
        assert pensiero and "We need to answer" in pensiero
        assert "I moduli di Sigma Studio" in testo


class TestIlRiconoscimentoDellaRichiesta:
    @pytest.mark.parametrize("domanda", [
        "scrivimi una descrizione in italiano e in inglese",
        "traduci questo paragrafo",
        "dammi la translation del readme",
        "voglio la versione bilingue",
        "write it in english please",
        "mostrami entrambe le lingue",
    ])
    def test_le_richieste_che_ammettono_inglese(self, domanda):
        assert richiesta_ammette_inglese(domanda) is True

    @pytest.mark.parametrize("domanda", [
        "parlami dei moduli di Sigma Studio",
        "come funziona l'harness?",
        "",
    ])
    def test_le_richieste_normali_non_disattivano_niente(self, domanda):
        assert richiesta_ammette_inglese(domanda) is False


def test_la_chat_passa_la_domanda():
    """Una difesa che nessuno attiva non e' una difesa."""
    import inspect

    from core.chat import chat_runner

    sorgente = inspect.getsource(chat_runner)
    assert "_clean_all_tags(full_text, message)" in sorgente
