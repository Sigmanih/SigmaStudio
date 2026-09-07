"""Nessuna capacita' dichiarata che nessuno puo' accendere.

Quattro volte, in questo progetto, una funzionalita' e' stata scritta, testata
e lasciata scollegata: `is_tool_allowed`, i profili operativi, il binding del
modello per ruolo, l'isolamento in worktree. Ogni volta i test del modulo erano
verdi, perche' chiamavano la funzione direttamente. Ogni volta il difetto era
altrove: **fra la funzione e l'utente non c'era una catena**.

Questo file non prova cosa fanno le funzionalita'. Prova che esistono dal punto
di vista di chi le userebbe: che ogni interruttore del ciclo dell'agente sia
raggiungibile da almeno un chiamante di produzione, e non solo da un test.

Se un parametro nuovo fa fallire questo file, la risposta non e' aggiungerlo
all'elenco delle eccezioni: e' collegarlo, oppure non dichiararlo finche' non
serve.
"""

import ast
import inspect
from pathlib import Path

import pytest

import core.harness.loop as modulo_loop

RADICE = Path(__file__).resolve().parents[1]

#: I parametri che descrivono *cosa* fare, non *come*: li passa per forza
#: chiunque chiami il ciclo, e verificarli non direbbe nulla.
STRUTTURALI = frozenset({"messages", "workspace_root", "model_name"})


def _parametri_del_ciclo():
    firma = inspect.signature(modulo_loop._stream_agent_turn_impl)
    return [
        nome for nome in firma.parameters
        if not nome.startswith("_") and nome not in STRUTTURALI
    ]


def _chiamanti_di_produzione():
    """I file che invocano il ciclo dell'agente, esclusi i test.

    Si guarda il sorgente e non i riferimenti a runtime perche' la domanda e'
    proprio se qualcuno *scrive* quel collegamento: una catena che nessuno ha
    scritto non si percorre nemmeno una volta.
    """
    file = []
    for percorso in (RADICE / "core").rglob("*.py"):
        if "__pycache__" in percorso.parts:
            continue
        try:
            testo = percorso.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "stream_admin_agent_turn(" in testo or "_stream_agent_turn_impl(" in testo:
            file.append((percorso, testo))
    return file


def _argomenti_passati(testo: str) -> set:
    """I nomi degli argomenti nominati in ogni chiamata al ciclo, nel sorgente."""
    passati = set()
    try:
        albero = ast.parse(testo)
    except SyntaxError:
        return passati
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.Call):
            continue
        funzione = nodo.func
        nome = getattr(funzione, "id", None) or getattr(funzione, "attr", None)
        if nome not in ("stream_admin_agent_turn", "_stream_agent_turn_impl"):
            continue
        for kw in nodo.keywords:
            if kw.arg:
                passati.add(kw.arg)
    return passati


@pytest.fixture(scope="module")
def argomenti_collegati():
    collegati = set()
    for percorso, testo in _chiamanti_di_produzione():
        if percorso.name == "loop.py":
            # L'involucro inoltra tutto con **kwargs: non e' un collegamento,
            # e' il condotto attraverso cui passano quelli veri.
            continue
        collegati |= _argomenti_passati(testo)
    return collegati


@pytest.mark.parametrize("parametro", _parametri_del_ciclo())
def test_ogni_interruttore_del_ciclo_ha_un_chiamante(parametro, argomenti_collegati):
    assert parametro in argomenti_collegati, (
        f"'{parametro}' e' dichiarato nel ciclo dell'agente e nessun chiamante "
        f"di produzione lo passa: e' una capacita' che l'utente non puo' "
        f"accendere. Collegala a un gestore HTTP, ai ruoli o alla CLI, oppure "
        f"toglila dalla firma finche' non serve davvero."
    )


def test_il_ciclo_ha_almeno_un_chiamante_di_produzione():
    """La guardia della guardia: se i chiamanti sparissero, il test sopra
    passerebbe a vuoto invece di fallire."""
    produzione = [p for p, _ in _chiamanti_di_produzione() if p.name != "loop.py"]
    assert produzione, "nessun chiamante di produzione trovato per il ciclo"


class TestLaGuardiaFunziona:
    """Il test sopra vale solo se sa davvero distinguere i due casi."""

    def test_un_parametro_inventato_non_risulta_collegato(self, argomenti_collegati):
        assert "parametro_che_non_esiste" not in argomenti_collegati

    def test_i_parametri_gia_collegati_risultano_tali(self, argomenti_collegati):
        # I quattro che sono stati collegati proprio per questo motivo.
        for atteso in ("review_writes", "isolate_worktree", "allowed_tools", "profile"):
            assert atteso in argomenti_collegati
