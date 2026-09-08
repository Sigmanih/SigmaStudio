"""Chi fa quello che gli e' stato chiesto deve poter riprovare.

Difetto trovato su un run vero, guardando ogni singolo tool. La sequenza era
questa, ed e' impeccabile da parte dell'agente:

1. `spec`, `pipeline`, `write_file` — il file viene creato;
2. `terminal` — la verifica gira e passa;
3. `complete_goal` — il cancello risponde «nel piano ci sono ancora task non
   chiusi: chiudili, o segnali saltati e spiega perche'»;
4. `pipeline` — l'agente **fa esattamente questo**;
5. `complete_goal` — **rifiutato dalla guardia anti-ripetizione**, perche' la
   chiamata e' identica alla precedente.

Aveva fatto precisamente cio' che il sistema gli aveva chiesto, e il sistema
gliel'ha rinfacciato. Quattordici turni per un file scritto al terzo, e la voce
contata come fallita.

La guardia e' giusta e serve — un `complete_goal` ripetuto identico otto volte
di fila e' successo davvero. Ma vale finche' **il mondo non cambia**, e un
aggiornamento del piano cambia esattamente cio' che il cancello guarda.
"""

import inspect

from core.harness.loop import GATE_INPUT_TOOLS, _stream_agent_turn_impl


class TestCosaRiapreUnaChiusuraRifiutata:
    def test_il_piano_e_la_specifica_sono_ingressi_del_cancello(self):
        assert "pipeline" in GATE_INPUT_TOOLS
        assert "spec" in GATE_INPUT_TOOLS

    def test_una_scrittura_azzera_le_firme_fallite(self):
        """Il caso gia' noto: il workspace e' cambiato."""
        sorgente = inspect.getsource(_stream_agent_turn_impl)
        blocco = sorgente[sorgente.index("t_name in PRODUCTIVE_TOOLS"):][:600]
        assert "failed_call_signatures.clear()" in blocco

    def test_anche_un_aggiornamento_del_piano_le_azzera(self):
        """Il caso nuovo, e quello che bloccava i run."""
        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "canonical(t_name) in GATE_INPUT_TOOLS" in sorgente
        blocco = sorgente[sorgente.index("GATE_INPUT_TOOLS"):][:900]
        assert "failed_call_signatures.clear()" in blocco

    def test_un_tool_qualunque_non_le_azzera(self):
        """La guardia deve restare: un `complete_goal` ripetuto identico otto
        volte di fila e' successo davvero, ed e' costato 45 secondi su 62."""
        assert "read_file" not in GATE_INPUT_TOOLS
        assert "list_dir" not in GATE_INPUT_TOOLS
        assert "screenshot" not in GATE_INPUT_TOOLS


class TestIlGiroCompleto:
    """La sequenza vera, riprodotta: scrivi, verifica, chiudi, ti dicono di
    sistemare il piano, lo sistemi, richiudi."""

    def test_dopo_aver_sistemato_il_piano_la_chiusura_passa(self, tmp_path, monkeypatch):
        from core.harness import loop as modulo_loop

        risposte = [
            '```tool:spec\n{"goal": "creare nota.py", "criteria": ["il file esiste"]}\n```',
            '```tool:pipeline\n{"tasks": [{"title": "creare il file", "status": "pending"}]}\n```',
            '```tool:write_file\n{"path": "nota.py", "content": "X = 1\n"}\n```',
            '```tool:terminal\n{"command": "python -c \\"import ast; ast.parse(open(\'nota.py\').read())\\""}\n```',
            '```tool:complete_goal\n{"summary": "fatto", "evidence": {"il file esiste": "nota.py scritto e verificato"}}\n```',
            '```tool:pipeline\n{"tasks": [{"title": "creare il file", "status": "done"}]}\n```',
            '```tool:complete_goal\n{"summary": "fatto", "evidence": {"il file esiste": "nota.py scritto e verificato"}}\n```',
            "Concluso.",
        ]
        stato = {"i": 0}

        def finto(**kw):
            i = min(stato["i"], len(risposte) - 1)
            stato["i"] += 1
            yield {"token": risposte[i]}

        monkeypatch.setattr(modulo_loop, "stream_dev_generation", finto)

        eventi = list(modulo_loop.stream_admin_agent_turn(
            messages=[{"role": "user", "content": "crea nota.py"}],
            workspace_root=str(tmp_path), model_name="finto", max_turns=10,
        ))

        rifiuti_per_ripetizione = [
            e for e in eventi
            if e.get("type") == "tool_result"
            and "identica chiamata" in str((e.get("result") or {}).get("error") or "")
        ]
        assert not rifiuti_per_ripetizione, (
            "la seconda chiusura e' stata bloccata dalla guardia anti-ripetizione "
            "anche se il piano era cambiato"
        )
