"""Il successo dell'agente non coincide con la media delle prove di protocollo."""

from pathlib import Path

import pytest

from core.harness.protocol import engine
from core.harness.protocol.evaluator import EsitoScenario, Prova
from core.harness.protocol.scenarios import Scenario


def test_telemetria_rust_espone_la_configurazione_del_compute_delegate():
    from unittest.mock import Mock
    from core.engine.backends.sigmarust_backend import SigmaRustBackend

    backend = SigmaRustBackend()
    misure = dict(main_gpu=0, forced_single_gpu=True, n_ctx=8192)
    backend._compute_delegate = Mock(is_loaded=True)
    backend._compute_delegate.telemetry.return_value = misure
    assert backend.telemetry() == misure
    assert backend.telemetry() is not misure


def _esito(**kwargs):
    valori = dict(scenario="x", model="m", obiettivo_raggiunto=True,
                  turni=2, secondi=1.0, tetto_turni=3, tetto_secondi=10.0,
                  prove=[Prova("risultato_giusto", "", True),
                         Prova("rispetto_sandbox", "", True)])
    valori.update(kwargs)
    return EsitoScenario(**valori)


def test_il_risultato_sbagliato_prevale_sulla_chiusura_del_modello():
    esito = _esito()
    esito.prove[0].superata = False
    assert esito.compito_riuscito is False


def test_un_difetto_di_protocollo_non_annulla_un_risultato_verificato():
    esito = _esito()
    esito.prove.append(Prova("spec_per_prima", "", False))
    assert esito.punteggio < 100
    assert esito.to_dict()["compito_riuscito"] is True


@pytest.mark.parametrize("modifiche", [
    {"errore": "motore guasto"}, {"scaduto": True}, {"annullato": True},
    {"turni": 4}, {"turni": 0}, {"secondi": 11.0},
    {"obiettivo_raggiunto": False},
])
def test_risultato_corretto_fuori_contratto_non_e_successo(modifiche):
    assert _esito(**modifiche).compito_riuscito is False


def test_senza_verificatore_il_risultato_resta_non_verificato():
    assert _esito(prove=[]).compito_riuscito is None


@pytest.mark.parametrize("prova", ["rispetto_sandbox", "non_riscrive_la_prova", "file_protetti_invariati"])
def test_violazione_integrita_non_puo_diventare_successo(prova):
    esito = _esito()
    esito.prove.append(Prova(prova, "", False))
    assert esito.compito_riuscito is False


def test_errori_e_mancati_avvii_non_scompaiono_dal_denominatore(monkeypatch):
    scenari = [Scenario(id=str(i), descrizione="", file={}, obiettivo="",
                       criteri=[]) for i in range(3)]
    esiti = iter([_esito(), _esito(errore="guasto"), _esito(prove=[])])
    monkeypatch.setattr(engine, "SCENARI", scenari)
    monkeypatch.setattr(engine, "esegui_scenario", lambda *a: next(esiti))
    rapporto = engine.esegui("m")["completamento_compiti"]
    assert rapporto == dict(versione=1, riusciti=1, totali=3,
                            non_verificati=1, percentuale=33.3)


def test_verificatore_guasto_non_interrompe_la_suite(monkeypatch):
    import core.harness.loop as loop

    def eventi(**kwargs):
        yield {"type": "token", "text": "fatto"}
        yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

    def guasto(radice):
        raise ValueError("file non valido")

    monkeypatch.setattr(loop, "stream_admin_agent_turn", eventi)
    scenario = Scenario(id="verificatore_guasto", descrizione="", file={},
                        obiettivo="x", criteri=[], controllo=guasto)
    esito = engine.esegui_scenario(scenario, "m")
    try:
        assert esito.compito_riuscito is False
        assert "Verificatore esterno fallito" in esito.prove[-1].dettaglio
        assert esito.tetto_turni == scenario.tetto_turni
    finally:
        if esito.sandbox:
            engine.pulisci(Path(esito.sandbox))
