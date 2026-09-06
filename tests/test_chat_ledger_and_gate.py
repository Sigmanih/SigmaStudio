# ==============================================================================
# tests/test_chat_ledger_and_gate.py — Test per il cancello e il ledger della Chat
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Test per la protezione da mutazioni indesiderate e il ledger nella chat.

Dimostra che:
1. Una domanda informativa o conversazionale NON crea file sul disco, neanche
   se la risposta del modello include percorsi "Path: data/..." o blocchi di codice.
2. Solo richieste esplicite e intenzionali di creazione/salvataggio file sono
   autorizzate dal cancello.
3. Il ChatLedger traccia in modo trasparente file letti, scritti e rifiuti.
"""

import os
import shutil
import pytest

from core.chat.ledger import (
    is_mutation_permitted,
    get_chat_ledger,
    release_chat_ledger,
)
from core.chat.file_extractor import _extract_and_create_files_from_text


@pytest.fixture(autouse=True)
def pulisci_cartella_test():
    test_dir = "data/test_chat_gate"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)
    yield
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)


class TestCancelloMutazioneChat:
    def test_domande_informative_vengono_respinte(self):
        """Domande che hanno causato la creazione di 6 file markdown nell'audit."""
        query_informative = [
            "Spiegami come migliorare l'efficienza dell'agente",
            "Parlami del codice di Sigma Studio",
            "Come funziona il modulo di rete?",
            "Quali sono le differenze tra architect e coder?",
            "Descrivi il pattern di completamento",
            "Analizza questo codice e dimmi cosa fa",
            "Riassumi le funzionalita dell'harness",
            "Come posso ottimizzare la memoria?",
        ]
        for q in query_informative:
            permesso, motivo = is_mutation_permitted(q)
            assert permesso is False, f"La query '{q}' non deve autorizzare scritture!"
            assert "non autorizzata" in motivo or "Nessuna richiesta esplicita" in motivo

    def test_richieste_esplicite_vengono_autorizzate(self):
        query_esplicite = [
            "Crea un file data/test_chat_gate/note.md",
            "Salva in un file il codice per la rotte",
            "Generami un file markdown con gli appunti",
            "Salvalo in data/test_chat_gate/script.py",
            "Scrivimi un file di configurazione",
        ]
        for q in query_esplicite:
            permesso, motivo = is_mutation_permitted(q)
            assert permesso is True, f"La query '{q}' doveva essere autorizzata!"

    def test_force_save_supera_sempre_il_cancello(self):
        permesso, _ = is_mutation_permitted("spiegami i limiti", force_save=True)
        assert permesso is True


class TestEstrazioneFileBloccataDaCancello:
    def test_modello_che_suggerisce_file_non_scrive_senza_richiesta(self):
        """Simula il bug storico: il modello illustra un file con 'Path: data/...'
        ma l'utente ha solo chiesto una spiegazione."""
        risposta_modello = (
            "Certamente! Ecco come puoi strutturare la tua ricerca:\n\n"
            "Path: data/test_chat_gate/ricerca.md\n"
            "```markdown\n"
            "# Ricerca su Efficienza\n"
            "Punti chiave da analizzare...\n"
            "```\n"
        )
        prompt_utente = "Come posso migliorare l'efficienza dell'agente?"

        created, actions = _extract_and_create_files_from_text(
            clean_response=risposta_modello,
            prompt_topic=prompt_utente,
            force_save=False,
            session_id="sess_informativa",
        )

        # NESSUN file deve essere stato creato
        assert len(created) == 0
        assert len(actions) == 0
        assert not os.path.exists("data/test_chat_gate/ricerca.md")

        # Il ChatLedger deve aver annotato il rifiuto
        ledger = get_chat_ledger("sess_informativa")
        assert ledger.snapshot()["rejected_attempts_count"] > 0
        release_chat_ledger("sess_informativa")

    def test_richiesta_esplicita_scrive_e_registra_nel_ledger(self):
        risposta_modello = (
            "Ecco il file richiesto:\n\n"
            "Path: data/test_chat_gate/modulo.py\n"
            "```python\n"
            "def test_fn():\n"
            "    return True\n"
            "```\n"
        )
        prompt_utente = "Crea il file data/test_chat_gate/modulo.py"

        created, actions = _extract_and_create_files_from_text(
            clean_response=risposta_modello,
            prompt_topic=prompt_utente,
            force_save=False,
            session_id="sess_esplicita",
        )

        assert len(created) == 1
        assert os.path.exists("data/test_chat_gate/modulo.py")

        ledger = get_chat_ledger("sess_esplicita")
        snap = ledger.snapshot()
        assert snap["writes_count"] == 1
        assert "data/test_chat_gate/modulo.py" in snap["written_files"][0]["path"]
        release_chat_ledger("sess_esplicita")
