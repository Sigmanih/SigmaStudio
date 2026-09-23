"""Una voce di coda deve dire come si dimostra, altrimenti e lavoro perso.

Il cancello di completamento pretende una prova **eseguita**: un file toccato o
un comando andato a buon fine. Chi scrive una voce aggiunge la sua `verify`
quando sa come si dimostra, e il ventaglio la passa al ciclo. Quando non c e,
chi lavora la voce non sa cosa gli verra chiesto ? e sui run registrati
quarantanove `complete_goal` sono stati rifiutati esattamente per questo, con il
lavoro che stava li.

Si avvisa e non si rifiuta: la prova a volte si scopre strada facendo, e una
coda che non accetta voci senza prova resta vuota. Ma l avviso arriva adesso, a
chi sta pianificando, che correggerlo gli costa una riga.
"""

import pytest

from core import paths
from core.harness.loop import execute_admin_tool


@pytest.fixture
def coda_isolata(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "var_dir", lambda: tmp_path)
    return tmp_path


def test_la_voce_senza_verify_viene_avvisata(coda_isolata):
    esito = execute_admin_tool(
        "queue_add",
        {"queue_id": "prova_verify",
         "items": [
             {"id": "senza", "title": "Una voce senza prova", "files": ["a.py"]},
             {"id": "con", "title": "Una voce con la prova",
              "verify": "python -m pytest tests/ -q", "files": ["b.py"]},
         ]},
        workspace_root=str(coda_isolata))
    assert esito["success"] is True, esito
    avvisi = esito.get("warnings") or []
    assert any("senza" in a and "verify" in a for a in avvisi), avvisi
    assert not any("con" in a and "non dichiara" in a for a in avvisi), avvisi


def test_una_prova_debole_resta_avvisata(coda_isolata):
    """Il controllo di prima non deve essersi perso per strada."""
    esito = execute_admin_tool(
        "queue_add",
        {"queue_id": "prova_debole",
         "items": [{"id": "debole", "title": "Guardare un file non e provare",
                    "verify": "grep -q demo src/App.jsx", "files": ["src/App.jsx"]}]},
        workspace_root=str(coda_isolata))
    avvisi = esito.get("warnings") or []
    assert any("si verifica con" in a for a in avvisi), avvisi

