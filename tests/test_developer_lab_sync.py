"""Il modulo installato deve corrispondere al sorgente su cui girano i test.

Il Developer Studio vive in due posti: `core/developer_studio/` e' il sorgente
tracciato, `core/modules/sigma_developer_lab/` e' la copia installata che il
module loader importa davvero. Finche' la copia si faceva a mano, una modifica
poteva passare tutti i test e non arrivare mai al server — i test giravano sul
file giusto, l'applicazione eseguiva l'altro.

Questo test rende quel disallineamento rumoroso. Se fallisce:

    python scripts/sync_developer_lab.py
"""

import importlib.util
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
MODULO = RADICE / "core" / "modules" / "sigma_developer_lab"
SCRIPT = RADICE / "scripts" / "sync_developer_lab.py"


def _carica_script():
    spec = importlib.util.spec_from_file_location("sync_developer_lab", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def sync():
    if not SCRIPT.is_file():
        pytest.skip("script di sincronizzazione assente")
    return _carica_script()


@pytest.mark.skipif(
    not MODULO.is_dir(),
    reason="modulo sigma_developer_lab non installato su questa macchina",
)
def test_il_modulo_installato_e_allineato_al_sorgente(sync):
    esito = sync.sincronizza(controlla_soltanto=True)
    assert esito == 0, (
        "Il modulo installato non corrisponde al sorgente. "
        "Esegui: python scripts/sync_developer_lab.py"
    )


@pytest.mark.skipif(
    not MODULO.is_dir(),
    reason="modulo sigma_developer_lab non installato su questa macchina",
)
def test_le_rotte_registrate_vengono_dalla_tabella_del_sorgente():
    """Una rotta aggiunta al sorgente deve esistere anche nel modulo.

    Era il secondo modo di divergere: l'elenco delle rotte stava scritto due
    volte, e quella nuova finiva solo nella copia che non registra nulla.
    """
    from core.developer_studio.handlers import ROUTES as sorgente
    from core.modules.sigma_developer_lab.handlers import ROUTES as installato

    percorsi_sorgente = {(p, tuple(m)) for p, _, m in sorgente}
    percorsi_installato = {(p, tuple(m)) for p, _, m in installato}
    assert percorsi_sorgente == percorsi_installato


def test_le_rotte_delle_sessioni_esistono():
    """Il minimo perche' una sessione sia ripristinabile da un client."""
    from core.developer_studio.handlers import ROUTES
    percorsi = {p for p, _, _ in ROUTES}
    assert "/api/developer/sessions" in percorsi
    assert "/api/developer/session" in percorsi
    assert "/api/developer/project/rules" in percorsi


def test_nessuna_rotta_e_registrata_due_volte():
    from core.developer_studio.handlers import ROUTES
    coppie = [(p, tuple(m)) for p, _, m in ROUTES]
    assert len(coppie) == len(set(coppie))
