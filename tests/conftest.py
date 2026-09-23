"""Il registro delle attivita' non viene sporcato dalla suite.

`stream_admin_agent_turn` scrive in `var/attivita.json` a ogni run, ed e' cio'
che permette all'interfaccia di dire cosa sta girando. Fa la stessa cosa quando
a chiamarlo e' un test: dopo una suite completa il registro conteneva quattro
voci di run finti, l'API rispondeva `busy: true`, e la chat cominciava ad
avvertire l'utente che «il Developer Studio sta lavorando» su un banco di prova
chiuso da un pezzo.

Il difetto non era grave e la sua forma si': **un test che lascia tracce nello
stato vero**. Qui il registro viene dirottato in una cartella temporanea per
tutta la sessione di prova. Chi vuole verificarne il contenuto ridirotta a sua
volta con `monkeypatch`, e continua a funzionare.

Non si dirotta `var_dir()` in blocco: troppi moduli lo usano per cose diverse,
e spostarli tutti insieme cambierebbe il significato di parecchi test senza che
nessuno l'abbia chiesto. Si sposta solo questo, che e' l'unico che scrive per
il solo fatto di essere passati di li'.
"""

import pytest


@pytest.fixture(autouse=True, scope="session")
def registro_attivita_isolato(tmp_path_factory):
    from core.harness import attivita

    cartella = tmp_path_factory.mktemp("attivita")
    originale = attivita.paths.var_dir
    attivita.paths.var_dir = lambda: cartella
    try:
        yield cartella
    finally:
        attivita.paths.var_dir = originale


def pytest_configure(config):
    """Registra i lotti come marcatori, da un posto solo.

    L'elenco dei lotti sta in `tests/lotti.py` e non si ripete qui: due copie
    della stessa lista divergono sempre, e la seconda a divergere e' quella che
    nessuno aggiorna. Registrandoli da li', `pytest -m harness` funziona senza
    che nessuno debba ricordarsi di toccare due file.
    """
    from tests.lotti import LOTTI

    config.addinivalue_line(
        "markers", "lento: avvia un modello o un server vero (fuori dalla corsa veloce)")
    for lotto in LOTTI:
        config.addinivalue_line(
            "markers", "%s: il lotto %s della suite" % (lotto, lotto))


def pytest_collection_modifyitems(config, items):
    """Ogni prova porta il lotto del suo file, e le lente portano `lento`."""
    from tests.lotti import e_lento, lotto_di

    for item in items:
        percorso = getattr(item, "fspath", None) or getattr(item, "path", "")
        lotto = lotto_di(percorso)
        if lotto:
            item.add_marker(getattr(pytest.mark, lotto))
        if e_lento(item.nodeid):
            item.add_marker(pytest.mark.lento)

