"""La prova dichiarata la esegue il ciclo, non la chiede di nuovo.

Il cancello di completamento pretende una prova **eseguita**: un file toccato o
un comando andato a buon fine. Finche nessuno la esegue, l agente scrive file
che non puo dimostrare ? e sui run registrati quarantanove `complete_goal` sono
stati rifiutati esattamente cosi, con il lavoro che stava li.

Quando chi scrive il task ha dichiarato il comando che dimostra il lavoro
(`verify` di una voce di coda, o `propose_verify` dell agente), non c e niente da
indovinare: il ciclo lo esegue appena ci sono scritture, registra l esito nel
ledger come se l avesse eseguito l agente, e mette il risultato nello stato.

Qui si verifica che succeda, che succeda **una volta sola** per insieme di
scritture, e che senza un comando dichiarato non si esegua niente.
"""

from unittest.mock import patch

from core.harness.ledger import DevSessionLedger
from core.harness.loop import stream_admin_agent_turn

FENCE = chr(96) * 3
PROVA = "python -c " + chr(34) + "print(" + chr(39) + "prova-ok" + chr(39) + ")" + chr(34)


def _turni_che_scrivono(massimo=2):
    """Primo turno: scrive un file. Poi risponde e basta, quindi il run chiude."""
    contatore = {"n": 0}

    def _genera(*_a, **_k):
        contatore["n"] += 1
        if contatore["n"] == 1:
            corpo = (FENCE + "tool:write_file\n"
                     + "{" + chr(34) + "path" + chr(34) + ": " + chr(34) + "nota.txt" + chr(34) + "}\n"
                     + "---\n"
                     + "riga scritta dall agente\n"
                     + FENCE)
            return iter([{"token": corpo}, {"done": True}])
        return iter([{"token": "Fatto."}, {"done": True}])

    return _genera


def _esegui(tmp_path, verify="", massimo=8):
    # Otto turni e non quattro: i primi due possono andare alla specifica, e
    # quanti ne spenda dipende da cosa ha lasciato in giro il resto della
    # suite. Il test misura la prova, non il calendario del ciclo.
    led = DevSessionLedger(goal="Scrivi una nota", workspace_root=str(tmp_path))
    # Con i criteri gia dichiarati il ciclo non spende i primi turni sulla
    # `spec`: la prova arriva al secondo turno, sempre, e il test misura la
    # prova invece dell ordine in cui il ciclo decide di chiederla.
    led.mark_requirement("1", "esiste nota.txt con la riga scritta")
    with patch("core.harness.loop.stream_dev_generation",
               side_effect=_turni_che_scrivono(massimo)):
        eventi = list(stream_admin_agent_turn(
            messages=[{"role": "user", "content": "scrivi la nota"}],
            session_id="", ledger=led, workspace_root=str(tmp_path),
            max_turns=massimo, model_name="modello-di-prova",
            provider="sigma_engine", verify_command=verify))
    return led, eventi


class TestLaProvaDichiarata:
    def test_il_ciclo_la_esegue_e_la_registra(self, tmp_path):
        led, eventi = _esegui(tmp_path, verify=PROVA)
        comandi = [c.get("command") for c in (led._commands or [])]
        assert PROVA in comandi, comandi
        registrato = [c for c in led._commands if c.get("command") == PROVA][0]
        assert registrato["ok"] is True
        assert "prova-ok" in str(registrato)

    def test_il_pannello_lo_dice(self, tmp_path):
        """Il testo che il pannello mostra lo produce un aiutante, e si prova
        direttamente: passando dal ciclo il test dipenderebbe da quanti turni
        quello spende sulla specifica, cioe dall ordine della suite. E li che
        questo test e diventato instabile ? falliva solo nella corsa intera.
        """
        from core.harness.loop import _esegui_la_prova_dichiarata

        led = DevSessionLedger(goal="scrivi una nota",
                               workspace_root=str(tmp_path))
        led.record_tool("write_file", {"path": "nota.txt"},
                        {"success": True,
                         "path": str(tmp_path / "nota.txt"),
                         "lines_after": 1})
        testo = _esegui_la_prova_dichiarata(led, PROVA, str(tmp_path), None, {})
        assert "eseguita io" in testo, testo
        assert PROVA in testo
        assert "prova-ok" in testo, testo


    def test_una_volta_sola_per_insieme_di_scritture(self, tmp_path):
        """Il guard si prova direttamente, non attraverso il ciclo.

        Passando dal ciclo, questo test misurava quante volte il run finisce per
        scrivere — cioe' l'ordine della suite: passava da solo e falliva nella
        corsa intera. La regola invece e' una sola e sta in
        `_esegui_la_prova_dichiarata`: con le stesse scritture, la seconda
        chiamata non esegue niente.
        """
        from core.harness.loop import _esegui_la_prova_dichiarata

        led = DevSessionLedger(goal="scrivi una nota", workspace_root=str(tmp_path))
        led.record_tool("write_file", {"path": "nota.txt"},
                        {"success": True, "path": str(tmp_path / "nota.txt"),
                         "lines_after": 1})
        memoria = {}
        primo = _esegui_la_prova_dichiarata(led, PROVA, str(tmp_path), None, memoria)
        assert "prova-ok" in primo, primo
        secondo = _esegui_la_prova_dichiarata(led, PROVA, str(tmp_path), None, memoria)
        assert secondo == "", secondo

    def test_e_il_ciclo_almeno_una_volta_la_esegue(self, tmp_path):
        """Che il ciclo la esegua: questo si puo' pretendere dall'integrazione.

        Quante volte la esegua dipende da quante volte il run scrive, e quello
        dipende dai turni che il ciclo spende sulla specifica: la proprieta'
        esatta sta nel test qui sopra.
        """
        led, _ = _esegui(tmp_path, verify=PROVA, massimo=6)
        quante = [c for c in led._commands if c.get("command") == PROVA]
        assert quante, led._commands
        assert all(c.get("ok") for c in quante), quante

    def test_senza_comando_dichiarato_non_si_esegue_niente(self, tmp_path):
        led, _ = _esegui(tmp_path, verify="")
        assert not (led._commands or [])

    def test_il_file_l_ha_scritto_lo_stesso(self, tmp_path):
        """La prova non sostituisce il lavoro: lo dimostra."""
        _esegui(tmp_path, verify=PROVA)
        assert (tmp_path / "nota.txt").exists()
        assert "riga scritta" in (tmp_path / "nota.txt").read_text(encoding="utf-8")

