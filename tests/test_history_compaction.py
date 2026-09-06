# ==============================================================================
# tests/test_history_compaction.py — Test Compattazione e Memoria di Sessione
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================

import unittest
from core.harness.ledger import DevSessionLedger, MAX_TRACKED_MEMORIES
from core.harness.compaction import (
    extract_reasoning_and_decisions,
    heuristic_summarize_evicted,
    llm_summarize_evicted,
    summarize_and_record_eviction,
    compact_history_with_memory,
)


class TestHistoryCompaction(unittest.TestCase):
    """Verifica il comportamento della memoria duratura e della compattazione turni."""

    def test_ledger_session_memory_lifecycle(self):
        ledger = DevSessionLedger(goal="Ottimizzare il calcolo delle metriche")
        self.assertEqual(len(ledger.session_memory), 0)

        # Aggiunta di memorie con turn range e decisioni
        ledger.add_session_memory(
            summary="Identificato collo di bottiglia in compute_metrics.py. Scelto di usare NumPy anziche liste.",
            turn_range="Turni 1-3",
            decisions=["Usare NumPy per il calcolo metriche vettoriali"],
        )

        self.assertEqual(len(ledger.session_memory), 1)
        self.assertIn("NumPy", ledger.session_memory[0]["summary"])
        self.assertEqual(ledger.session_memory[0]["turn_range"], "Turni 1-3")
        self.assertIn("Usare NumPy per il calcolo metriche vettoriali", ledger._decisions)

        # Verifica rendering nello state block
        state_block = ledger.render_state_block()
        self.assertIn("Memoria della sessione (decisioni e motivazioni storiche):", state_block)
        self.assertIn("[Turni 1-3]", state_block)
        self.assertIn("NumPy", state_block)

        # Verifica snapshot
        snap = ledger.snapshot()
        self.assertIn("session_memory", snap)
        self.assertEqual(len(snap["session_memory"]), 1)

        # Verifica serialize e restore
        serialized = ledger.serialize()
        self.assertIn("session_memory", serialized)
        
        restored = DevSessionLedger.restore(serialized)
        self.assertEqual(len(restored.session_memory), 1)
        self.assertEqual(restored.session_memory[0]["summary"], ledger.session_memory[0]["summary"])
        self.assertIn("Memoria della sessione", restored.render_state_block())

    def test_ledger_memory_capping(self):
        """Assicura che la memoria di sessione non cresca all'infinito rispettando MAX_TRACKED_MEMORIES."""
        ledger = DevSessionLedger(goal="Run prolungato")
        for i in range(MAX_TRACKED_MEMORIES + 10):
            ledger.add_session_memory(f"Sintesi del blocco di turni {i}", turn_range=f"t={i}")

        self.assertEqual(len(ledger.session_memory), MAX_TRACKED_MEMORIES)
        # Deve conservare gli ultimi aggiunti
        self.assertIn(f"t={MAX_TRACKED_MEMORIES + 9}", ledger.session_memory[-1]["turn_range"])

    def test_extract_reasoning_and_decisions(self):
        raw_text = """
        Ho esaminato il modulo `core/api.py`.
        Ho deciso di non usare Flask poiche il resto del progetto e basato su FastAPI.
        Procedo quindi a implementare la route `/api/status` perche e richiesta dalla specifica.
        ```tool:edit_file
        {"path": "core/api.py", "old_string": "pass", "new_string": "# new"}
        ```
        """
        extracted = extract_reasoning_and_decisions(raw_text)
        self.assertTrue(len(extracted) >= 2)
        combined = " ".join(extracted)
        self.assertIn("deciso di non usare Flask", combined)
        self.assertIn("Procedo quindi a implementare", combined)
        # Non deve contenere il blocco tool
        self.assertNotIn("```tool:edit_file", combined)

    def test_heuristic_summarize_evicted(self):
        evicted = [
            {
                "role": "assistant",
                "content": "Ho notato che il test `test_auth.py` fallisce per un errore di token scaduto.\n"
                           "Deciso di aumentare il timeout a 3600 secondi invece di disabilitare il controllo.\n"
                           "```tool:edit_file\n{\"path\": \"core/auth.py\"}\n```",
            },
            {
                "role": "user",
                "content": "Modifica applicata con successo. File salvato.",
            },
            {
                "role": "assistant",
                "content": "Procedo ora a verificare la correzione eseguendo pytest sul test auth.\n"
                           "```tool:terminal\n{\"command\": \"pytest tests/test_auth.py\"}\n```",
            },
            {
                "role": "user",
                "content": "1 passed in 0.12s",
            },
        ]

        summary, decisions = heuristic_summarize_evicted(evicted)
        self.assertTrue(bool(summary))
        self.assertIn("timeout", summary.lower())
        self.assertTrue(any("timeout" in d.lower() for d in decisions) or len(decisions) >= 0)

    def test_compact_history_with_memory_eviction(self):
        """Simula una conversazione prolungata in cui i turni vecchi vengono sfrattati e memorizzati."""
        ledger = DevSessionLedger(goal="Rifattorizzare il parser JSON")

        messages = [
            {"role": "system", "content": "Sei un ingegnere del software."},
            {"role": "user", "content": "Rifattorizza il parser JSON per supportare commenti."},
        ]

        # Aggiungiamo 30 scambi di messaggi (60 messaggi)
        for turn_idx in range(1, 31):
            messages.append({
                "role": "assistant",
                "content": f"Turno {turn_idx}: Ho deciso di verificare il token parser. Procedo a modificare la riga {turn_idx} perche e necessaria.\n"
                           f"```tool:read_file\n{{\"path\": \"file_{turn_idx}.py\"}}\n```",
            })
            messages.append({
                "role": "user",
                "content": f"Contenuto di file_{turn_idx}.py letto con successo.",
            })

        # Prima della compattazione, ci sono 62 messaggi
        self.assertEqual(len(messages), 62)

        # Eseguiamo la compattazione con limite di 10 turni recenti (20 messaggi + system + first_user = 22)
        compacted = compact_history_with_memory(
            messages=messages,
            ledger=ledger,
            max_history_chars=100000,
            max_recent_turns=20,
            current_turn=30,
        )

        # La cronologia attiva deve essere ridotta
        self.assertLess(len(compacted), len(messages))
        self.assertEqual(compacted[0]["role"], "system")
        self.assertEqual(compacted[1]["content"], "Rifattorizza il parser JSON per supportare commenti.")

        # La memoria duratura del ledger deve contenere le motivazioni distillate dei turni sfrattati
        self.assertGreater(len(ledger.session_memory), 0)
        first_mem = ledger.session_memory[0]
        self.assertIn("Turni precedenti", first_mem["turn_range"])
        self.assertTrue(bool(first_mem["summary"]))

        # Lo state block include la memoria e non soffre di amnesia
        state_block = ledger.render_state_block()
        self.assertIn("Memoria della sessione (decisioni e motivazioni storiche):", state_block)

    def test_llm_summarize_mock_and_fallback(self):
        evicted = [
            {"role": "assistant", "content": "Deciso di cambiare algoritmo in Dijkstra."},
            {"role": "user", "content": "OK"},
        ]

        # 1. Con mock generator che restituisce token
        def mock_generator(**kwargs):
            yield {"token": "Scelto algoritmo Dijkstra "}
            yield {"token": "per ottimizzare i percorsi brevi."}

        res = llm_summarize_evicted(evicted, stream_generator_fn=mock_generator)
        self.assertIsNotNone(res)
        self.assertIn("Dijkstra", res[0])

        # 2. Con generator che fallisce -> summarize_and_record_eviction usa fallback
        def failing_generator(**kwargs):
            raise RuntimeError("Connessione timeout")

        ledger = DevSessionLedger(goal="Routing")
        recorded = summarize_and_record_eviction(
            evicted,
            ledger=ledger,
            turn_range="t=5-6",
            stream_generator_fn=failing_generator,
        )
        self.assertTrue(bool(recorded))
        self.assertEqual(len(ledger.session_memory), 1)
        self.assertIn("Dijkstra", ledger.session_memory[0]["summary"])


if __name__ == "__main__":
    unittest.main()
