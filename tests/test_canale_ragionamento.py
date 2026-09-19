# ==============================================================================
# tests/test_canale_ragionamento.py — Test per il canale del ragionamento
# Sigma Studio — Task k08
# ==============================================================================
import pytest
from core.chat.chat_runner import _ThinkTagRouter


def test_flusso_senza_tag():
    """Un modello che non apre nessun tag emette tutto nel canale 'token'."""
    router = _ThinkTagRouter()
    chunks = ["Ciao ", "mondo! ", "Ecco la ", "risposta completa."]
    emitted = []
    for c in chunks:
        emitted.extend(router.feed(c))
    emitted.extend(router.flush())

    channels = [ch for ch, _ in emitted]
    text = "".join(t for _, t in emitted)

    assert all(ch == "token" for ch in channels)
    assert text == "Ciao mondo! Ecco la risposta completa."


def test_blocco_think_regolare():
    """Un blocco <think>...</think> viene instradato correttamente in 'thinking' e poi in 'token'."""
    router = _ThinkTagRouter()
    chunks = [
        "<think>\nSto riflettendo sul problema.\n",
        "Passo 1: analisi.\n</think>\n",
        "Ecco la soluzione:",
        " x = 42",
    ]
    emitted = []
    for c in chunks:
        emitted.extend(router.feed(c))
    emitted.extend(router.flush())

    thinking_text = "".join(t for ch, t in emitted if ch == "thinking")
    token_text = "".join(t for ch, t in emitted if ch == "token")

    assert "Sto riflettendo sul problema." in thinking_text
    assert "Passo 1: analisi." in thinking_text
    assert "Ecco la soluzione: x = 42" in token_text
    assert "<think>" not in thinking_text
    assert "</think>" not in token_text


def test_spezzettamento_tag_in_chunk():
    """Un tag spezzato tra più chunk (es. '<th' poi 'ink>') viene gestito senza perdite."""
    router = _ThinkTagRouter()
    chunks = ["Prima <th", "ink>Pensiero intermedio</thi", "nk> e poi risposta."]
    emitted = []
    for c in chunks:
        emitted.extend(router.feed(c))
    emitted.extend(router.flush())

    thinking_text = "".join(t for ch, t in emitted if ch == "thinking")
    token_text = "".join(t for ch, t in emitted if ch == "token")

    assert thinking_text.strip() == "Pensiero intermedio"
    assert token_text.strip() == "Prima  e poi risposta."


def test_tag_canale_alternativo():
    """Supporto per tag channel di Qwen/DeepSeek (<|channel>thought...<channel|>)."""
    router = _ThinkTagRouter()
    stream = "<|channel>thought\nRagionamento matematico.\n<channel|>\nRisultato finale: 100."
    emitted = router.feed(stream) + router.flush()

    thinking_text = "".join(t for ch, t in emitted if ch == "thinking")
    token_text = "".join(t for ch, t in emitted if ch == "token")

    assert "Ragionamento matematico." in thinking_text
    assert "Risultato finale: 100." in token_text


def test_saluto_italiano_non_spezza_il_pensiero():
    """Un saluto o 'Ciao' dentro il pensiero NON deve causare una transizione forzata prematura."""
    router = _ThinkTagRouter()
    stream = (
        "<think>\nL'utente mi ha detto Ciao!\n"
        "Devo rispondere: Ciao utente, come stai?\n"
        "Analizzo la richiesta.\n</think>\n"
        "Ciao utente! Come posso aiutarti oggi?"
    )
    emitted = router.feed(stream) + router.flush()

    thinking_text = "".join(t for ch, t in emitted if ch == "thinking")
    token_text = "".join(t for ch, t in emitted if ch == "token")

    assert "L'utente mi ha detto Ciao!" in thinking_text
    assert "Devo rispondere: Ciao utente" in thinking_text
    assert token_text.strip() == "Ciao utente! Come posso aiutarti oggi?"


def test_tag_aperto_mai_chiuso_non_perde_dati():
    """Se il modello apre <think> e non lo chiude mai, il buffer non va perso a fine stream."""
    router = _ThinkTagRouter()
    stream = "<think>\nHo pensato solo a questo e non ho chiuso il tag."
    emitted = router.feed(stream) + router.flush()

    thinking_text = "".join(t for ch, t in emitted if ch == "thinking")
    assert "Ho pensato solo a questo e non ho chiuso il tag." in thinking_text
