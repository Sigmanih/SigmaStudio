"""Cosa significa «finito», e perche' non puo' deciderlo il modello.

Il cancello di completamento accettava «ho modificato un file e un comando e
uscito con zero». Su una richiesta con cinque cose dentro, questo vuol dire
che l'agente ne faceva una, lanciava i test e dichiarava finito — in perfetta
buona fede, perche' nessuno gli aveva mai detto cos'altro mancasse.

I criteri di accettazione spostano quel giudizio dal modello a un elenco
scritto prima di cominciare. Il vincolo che li rende utili invece che
decorativi e' la *prova ancorata*: un criterio si soddisfa solo citando un
file toccato o un comando eseguito in questa sessione. Senza quel vincolo,
spuntare un criterio sarebbe di nuovo la parola del modello, che e'
esattamente cio' che il ledger esiste per non dover credere.
"""

import pytest

from core.harness.ledger import (
    DevSessionLedger,
    Requirement,
    check_completion_allowed,
)

WS = "C:/progetto"


def _ledger(goal="Aggiungi la route /api/salute e i suoi test"):
    return DevSessionLedger(goal=goal, workspace_root=WS)


def _ha_modificato(ledger, path="core/api.py"):
    ledger.record_tool(
        "write_file",
        {"path": f"{WS}/{path}"},
        {"success": True, "path": f"{WS}/{path}", "lines_after": 30},
    )


def _ha_verificato(ledger, cmd="python -m pytest tests/ -q"):
    ledger.record_tool(
        "terminal", {"command": cmd},
        {"success": True, "returncode": 0, "command": cmd},
    )


class TestRegistrazione:
    def test_i_criteri_si_accettano_come_stringhe(self):
        led = _ledger()
        registrati = led.set_spec("Serve una route nuova", ["esiste la route", "i test passano"])
        assert [c["id"] for c in registrati] == ["1", "2"]
        assert led.has_spec()

    def test_i_criteri_si_accettano_come_oggetti(self):
        led = _ledger()
        led.set_spec("x", [{"id": "a", "text": "primo"}, {"id": "b", "text": "secondo"}])
        assert [r.id for r in led.requirements] == ["a", "b"]

    def test_i_criteri_vuoti_vengono_scartati(self):
        led = _ledger()
        led.set_spec("x", ["valido", "", "   ", {"text": ""}])
        assert len(led.requirements) == 1

    def test_una_specifica_nuova_sostituisce_la_precedente(self):
        """Riformulare l'obiettivo non deve lasciare in giro criteri orfani."""
        led = _ledger()
        led.set_spec("prima", ["a", "b", "c"])
        led.set_spec("poi", ["solo questo"])
        assert len(led.requirements) == 1
        assert led.requirements[0].text == "solo questo"


class TestProvaAncorata:
    """Il vincolo che rende i criteri qualcosa di piu' di una lista."""

    def test_una_prova_generica_viene_rifiutata(self):
        led = _ledger()
        led.set_spec("x", ["la route esiste"])
        esito = led.mark_requirement("1", "fatto tutto correttamente")
        assert esito["ok"] is False
        assert led.unmet_requirements()

    def test_una_prova_vuota_viene_rifiutata(self):
        led = _ledger()
        led.set_spec("x", ["la route esiste"])
        assert led.mark_requirement("1", "")["ok"] is False
        assert led.mark_requirement("1", "ok")["ok"] is False

    def test_una_prova_che_cita_un_file_toccato_regge(self):
        led = _ledger()
        led.set_spec("x", ["la route esiste"])
        _ha_modificato(led, "core/api.py")
        assert led.mark_requirement("1", "aggiunta in core/api.py alla riga 30")["ok"] is True
        assert not led.unmet_requirements()

    def test_basta_il_nome_del_file_senza_percorso(self):
        """Il modello abbrevia sempre: un falso negativo bloccherebbe un run corretto."""
        led = _ledger()
        led.set_spec("x", ["la route esiste"])
        _ha_modificato(led, "core/api.py")
        assert led.mark_requirement("1", "la funzione sta in api.py")["ok"] is True

    def test_una_prova_che_cita_un_comando_eseguito_regge(self):
        led = _ledger()
        led.set_spec("x", ["i test passano"])
        _ha_verificato(led)
        assert led.mark_requirement("1", "verificato con pytest, exit code 0")["ok"] is True

    def test_un_criterio_inesistente_viene_rifiutato(self):
        led = _ledger()
        led.set_spec("x", ["uno"])
        _ha_modificato(led)
        esito = led.mark_requirement("99", "core/api.py modificato")
        assert esito["ok"] is False
        assert "99" in esito["reason"]

    def test_un_file_mai_toccato_non_e_una_prova(self):
        """Il caso che conta: citare un file plausibile ma mai aperto."""
        led = _ledger()
        led.set_spec("x", ["la route esiste"])
        _ha_modificato(led, "core/api.py")
        assert led.mark_requirement("1", "vedi core/inesistente_mai_letto.py")["ok"] is False


class TestCancelloDiCompletamento:
    def test_i_criteri_aperti_bloccano_il_completamento(self):
        led = _ledger()
        led.set_spec("x", ["la route esiste", "i test passano"])
        _ha_modificato(led)
        _ha_verificato(led)
        esito = check_completion_allowed(led)
        assert esito["allowed"] is False
        assert len(esito["unmet"]) == 2

    def test_soddisfare_tutti_i_criteri_sblocca(self):
        led = _ledger()
        led.set_spec("x", ["la route esiste", "i test passano"])
        _ha_modificato(led, "core/api.py")
        _ha_verificato(led)
        assert led.mark_requirement("1", "scritta in core/api.py")["ok"]
        assert led.mark_requirement("2", "python -m pytest tests/ -q verde")["ok"]
        assert check_completion_allowed(led)["allowed"] is True

    def test_soddisfarne_solo_una_parte_non_basta(self):
        """Il difetto originale, in una riga: un task su due non e' finito."""
        led = _ledger()
        led.set_spec("x", ["primo pezzo", "secondo pezzo"])
        _ha_modificato(led, "core/api.py")
        _ha_verificato(led)
        led.mark_requirement("1", "core/api.py")
        assert check_completion_allowed(led)["allowed"] is False

    def test_un_piano_con_task_aperti_blocca(self):
        led = _ledger()
        led.set_pipeline([
            {"id": "1", "title": "Scrivi la route", "status": "done"},
            {"id": "2", "title": "Scrivi i test", "status": "in_progress"},
        ])
        _ha_modificato(led)
        _ha_verificato(led)
        esito = check_completion_allowed(led)
        assert esito["allowed"] is False
        assert "Scrivi i test" in esito["reason"]

    def test_un_task_saltato_esplicitamente_non_blocca(self):
        """Rinunciare a un task e' una decisione legittima; dimenticarlo no."""
        led = _ledger()
        led.set_pipeline([
            {"id": "1", "title": "Scrivi la route", "status": "done"},
            {"id": "2", "title": "Migrazione dati", "status": "skipped"},
        ])
        _ha_modificato(led)
        _ha_verificato(led)
        assert check_completion_allowed(led)["allowed"] is True

    def test_senza_specifica_valgono_le_regole_di_prima(self):
        """Chi non dichiara criteri non deve restare bloccato: audit, domande brevi."""
        led = _ledger()
        _ha_modificato(led)
        _ha_verificato(led)
        assert check_completion_allowed(led)["allowed"] is True

    def test_i_criteri_vengono_prima_della_verifica(self):
        """Un criterio aperto blocca anche se non c'e' nulla di rotto."""
        led = _ledger("Analizza e correggi il modulo di rete")
        led.set_spec("x", ["il bug e corretto"])
        esito = check_completion_allowed(led)
        assert esito["allowed"] is False
        assert "Criteri di accettazione" in esito["reason"]


class TestStatoDelLavoro:
    def test_lo_stato_elenca_i_criteri_e_il_loro_esito(self):
        led = _ledger()
        led.set_spec("Serve la route /api/salute", ["la route esiste", "i test passano"])
        _ha_modificato(led, "core/api.py")
        led.mark_requirement("1", "aggiunta in core/api.py")

        stato = led.render_state_block()
        assert "Serve la route /api/salute" in stato
        assert "[OK] #1" in stato
        assert "[DA FARE] #2" in stato

    def test_senza_specifica_lo_stato_non_ne_parla(self):
        assert "Criteri di accettazione" not in _ledger().render_state_block()


class TestPersistenza:
    def test_i_criteri_sopravvivono_al_giro_di_serializzazione(self):
        led = _ledger()
        led.set_spec("Serve la route", ["la route esiste", "i test passano"])
        _ha_modificato(led, "core/api.py")
        led.mark_requirement("1", "aggiunta in core/api.py")

        ripristinato = DevSessionLedger.restore(led.serialize())

        assert [r.to_dict() for r in ripristinato.requirements] == [
            r.to_dict() for r in led.requirements
        ]
        assert ripristinato.render_state_block() == led.render_state_block()

    def test_il_cancello_da_lo_stesso_esito_dopo_un_riavvio(self):
        """Una sessione ripresa non deve poter chiudere cio' che era aperto."""
        led = _ledger()
        led.set_spec("x", ["primo", "secondo"])
        _ha_modificato(led)
        _ha_verificato(led)
        led.mark_requirement("1", "core/api.py")

        ripristinato = DevSessionLedger.restore(led.serialize())
        assert check_completion_allowed(ripristinato)["allowed"] is False
        assert len(ripristinato.unmet_requirements()) == 1

    def test_uno_stato_senza_criteri_si_ripristina_lo_stesso(self):
        vecchio = {"goal": "x", "workspace_root": WS, "files": [], "commands": []}
        assert DevSessionLedger.restore(vecchio).requirements == []


class TestToolSpec:
    """La forma della chiamata, come la produce un modello locale."""

    def test_il_tool_normalizza_una_lista_di_stringhe(self):
        from core.harness.loop import execute_admin_tool
        res = execute_admin_tool(
            "spec",
            {"understanding": "Serve X", "criteria": ["uno", "due"]},
            WS,
        )
        assert res["success"] is True
        assert res["criteria"] == ["uno", "due"]

    def test_il_tool_accetta_un_elenco_scritto_a_righe(self):
        """I modelli piccoli scrivono elenchi puntati anche dentro il JSON."""
        from core.harness.loop import execute_admin_tool
        res = execute_admin_tool(
            "spec",
            {"understanding": "Serve X", "criteria": "- uno\n- due\n"},
            WS,
        )
        assert res["criteria"] == ["uno", "due"]

    def test_una_specifica_senza_criteri_viene_rifiutata_con_la_forma_giusta(self):
        from core.harness.loop import execute_admin_tool
        res = execute_admin_tool("spec", {"understanding": "Serve X"}, WS)
        assert res["success"] is False
        assert "criteria" in res["error"]

    def test_complete_goal_trasporta_le_prove(self):
        from core.harness.loop import execute_admin_tool
        res = execute_admin_tool(
            "complete_goal",
            {"summary": "fatto", "criteria": [{"id": "1", "evidence": "core/api.py"}]},
            WS,
        )
        assert res["criteria"] == [{"id": "1", "evidence": "core/api.py"}]


class TestPolicy:
    def test_spec_e_un_tool_di_controllo(self):
        """Vietarlo a un ruolo lo renderebbe incapace di dichiarare cosa fara."""
        from core.harness.policy import CONTROL_TOOLS, ToolPolicy, canonical
        assert "spec" in CONTROL_TOOLS
        assert canonical("requirements") == "spec"
        assert ToolPolicy.of(("read_file",)).permits("spec")


class TestChiusuraRespintaNonSiRipete:
    """Una `complete_goal` rifiutata dal cancello deve contare come fallita.

    Emerso da un run reale di pipeline: il nodo con ruolo architect ha chiamato
    `complete_goal` otto volte di fila, identica, e il cancello l'ha respinta
    ogni volta. Quarantacinque secondi su sessantadue spesi a ripetere la
    stessa mossa.

    La causa e' un ordine: il cancello riscrive l'esito della chiamata *dopo*
    il punto in cui il ciclo memorizza le chiamate fallite, quindi quella
    chiusura non risultava mai fallita e la guardia contro le ripetizioni
    identiche non la vedeva.
    """

    def test_il_ciclo_registra_la_firma_prima_di_riscrivere_l_esito(self):
        """L'ordine nel sorgente e' la cosa che si e' rotta: si verifica quello."""
        import inspect
        from core.harness.loop import stream_admin_agent_turn

        sorgente = inspect.getsource(stream_admin_agent_turn)
        rifiuto = sorgente.index('"error": f"Completamento rifiutato.')
        blocco = sorgente[max(0, rifiuto - 900):rifiuto]
        assert "failed_call_signatures.add(" in blocco, (
            "la firma della chiusura respinta non viene registrata"
        )

    def test_una_chiusura_senza_prove_viene_respinta(self):
        """Il motivo per cui veniva respinta, che resta giusto."""
        led = _ledger()
        led.set_spec("x", ["il prefisso e documentato"])
        _ha_modificato(led)
        _ha_verificato(led)
        esito = check_completion_allowed(led)
        assert esito["allowed"] is False
        assert esito["unmet"]

    def test_dopo_aver_fornito_le_prove_la_chiusura_passa(self):
        """La ripetizione va bloccata, non il secondo tentativo informato."""
        led = _ledger()
        led.set_spec("x", ["il prefisso e documentato"])
        _ha_modificato(led, "core/api.py")
        _ha_verificato(led)
        assert led.mark_requirement("1", "scritto in core/api.py")["ok"]
        assert check_completion_allowed(led)["allowed"] is True
