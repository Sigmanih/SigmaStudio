"""Ogni turno lascia la sua riga: quale turno costa, e quanto contesto e riuso.

La media su trenta turni non serve a decidere: nasconde il turno da dodicimila
token di contesto e quello da duecento. E il modello mancava nel 67% delle
sessioni salvate, `generated_tokens` era zero nel 17%, e il riuso del prefisso
non era registrato da nessuna parte: senza questi numeri ogni ottimizzazione e
una scommessa.

Qui si verifica che un turno vero ? con un provider finto, senza modello ?
lasci la sua riga: prompt in ingresso, token generati, tps, ttft, durata, i tool
del turno e il riuso dichiarato dal motore.
"""

from unittest.mock import patch

from core.harness.ledger import DevSessionLedger
from core.harness.loop import stream_admin_agent_turn

CHIAVI_DELLA_RIGA = ("turn", "prompt_tokens", "generated_tokens", "tps",
                     "ttft_ms", "duration_s", "tool_calls", "tool_failures",
                     "reuse_tokens", "state_chars")


def _turno(destinazione, max_turns=1, riuso=None, con_tool=False,
           prompt_vero=None):
    """Un run finto. Senza una chiamata nel primo turno il ciclo chiude al
    primo: il modello ha risposto, e un run che risponde e finito."""
    chiamate = {"n": 0}

    def _genera(*_a, **_k):
        chiamate["n"] += 1
        pezzi = []
        if con_tool and chiamate["n"] == 1:
            pezzi.append({"token": 'Guardo la cartella.\n```tool:list_dir\n'
                                  + '{"path": "."}\n```'})
        else:
            pezzi.append({"token": 'Ciao'})
            pezzi.append({"token": ' mondo'})
        if riuso is not None:
            pezzi.append({"prefix_reused_tokens": riuso})
        if prompt_vero is not None:
            pezzi.append({"prompt_tokens": prompt_vero, "prefill_ms": 1200.0})
        pezzi.append({"done": True})
        return iter(pezzi)

    with patch('core.harness.loop.stream_dev_generation', side_effect=_genera):
        return list(stream_admin_agent_turn(
            messages=[{"role": "user", "content": "saluta"}],
            session_id="",
            ledger=DevSessionLedger(goal="Ciao", workspace_root=str(destinazione)),
            workspace_root=str(destinazione),
            max_turns=max_turns,
            model_name="modello-di-prova",
            provider="sigma_engine",
        ))


def _consuntivo(eventi):
    finali = [e for e in eventi if e.get("type") == "run_metrics"]
    assert finali, "il run deve dichiarare il suo consuntivo"
    return finali[-1]


def _costi(eventi):
    """L'evento `metrics` del run: quello con i numeri del costo.

    Non va confuso con il `metrics` di ogni turno, che porta tps e ttft del
    turno appena finito e nessun consuntivo.
    """
    finali = [e for e in eventi
              if e.get("type") == "metrics" and isinstance(e.get("metrics"), dict)]
    assert finali, "il run deve dichiarare quanto e' costato"
    return finali[-1]["metrics"]


class TestLaRigaDelTurno:
    def test_ogni_turno_ha_la_sua_riga(self, tmp_path):
        metrica = _consuntivo(_turno(tmp_path))
        righe = metrica["turns_detail"]
        assert len(righe) == 1
        for chiave in CHIAVI_DELLA_RIGA:
            assert chiave in righe[0], chiave
        assert righe[0]["turn"] == 1
        assert righe[0]["generated_tokens"] == 2
        assert righe[0]["prompt_tokens"] > 0

    def test_il_contesto_in_ingresso_si_accumula(self, tmp_path):
        """Due turni veri: il primo chiama un tool, il secondo risponde."""
        metrica = _consuntivo(_turno(tmp_path, max_turns=2, con_tool=True))
        assert [r["turn"] for r in metrica["turns_detail"]] == [1, 2]
        assert metrica["turns_detail"][0]["tool_calls"] == 1
        assert metrica["turns_detail"][1]["tool_calls"] == 0
        assert metrica["prompt_tokens"] >= sum(r["prompt_tokens"]
                                                 for r in metrica["turns_detail"])

    def test_il_riuso_del_prefisso_non_e_piu_una_dichiarazione(self, tmp_path):
        metrica = _consuntivo(_turno(tmp_path, riuso=9500))
        assert metrica["reuse_tokens"] == 9500
        assert metrica["turns_detail"][0]["reuse_tokens"] == 9500

    def test_senza_riuso_il_contatore_resta_a_zero(self, tmp_path):
        assert _consuntivo(_turno(tmp_path))["reuse_tokens"] == 0

    def test_il_modello_finisce_nel_consuntivo(self, tmp_path):
        metrica = _consuntivo(_turno(tmp_path))
        assert metrica["model"] == "modello-di-prova"
        assert metrica["provider"] == "sigma_engine"

    def test_il_conteggio_vero_del_server_batte_la_stima(self, tmp_path):
        """Quando il server dice quanti token ha ricevuto, quello e' il numero."""
        riga = _consuntivo(_turno(tmp_path, prompt_vero=9500))["turns_detail"][0]
        assert riga["prompt_tokens"] == 9500
        assert riga["prompt_tokens_estimated"] is False
        assert riga["prefill_ms"] == 1200.0

    def test_senza_il_conteggio_la_stima_si_dichiara_tale(self, tmp_path):
        riga = _consuntivo(_turno(tmp_path))["turns_detail"][0]
        assert riga["prompt_tokens"] > 0
        assert riga["prompt_tokens_estimated"] is True

    def test_il_costo_del_run_si_vede_senza_aprire_il_json(self, tmp_path):
        metrica = _costi(_turno(tmp_path, riuso=9500, prompt_vero=9500))
        assert metrica["reuse_tokens"] == 9500
        assert metrica["prefill_ms"] == 1200.0
        assert metrica["prompt_tokens_estimated_pct"] == 0

    def test_senza_conteggi_la_quota_di_stime_lo_dichiara(self, tmp_path):
        metrica = _costi(_turno(tmp_path))
        assert metrica["reuse_tokens"] == 0
        assert metrica["prompt_tokens_estimated_pct"] == 100


class TestLaTelemetriaLive:
    """Il tempo al primo token deve arrivare all'interfaccia, non stare muto.

    La prima stesura lo calcolava da `turn_first_token_time`, che viene
    azzerata all'inizio di ogni turno: la condizione era sempre falsa e ogni
    evento `context_telemetry` portava `ttft_ms: null`. Il numero c'era nel
    consuntivo e nessuno lo vedeva mentre il run girava.
    """

    def test_al_secondo_turno_il_tempo_del_primo_si_vede(self, tmp_path):
        eventi = _turno(tmp_path, max_turns=2, con_tool=True)
        telemetrie = [e for e in eventi if e.get("type") == "context_telemetry"]
        assert len(telemetrie) == 2
        assert telemetrie[0]["ttft_ms"] is None
        assert telemetrie[0]["generated_tokens_last_turn"] == 0
        assert telemetrie[1]["ttft_ms"] is not None
        assert telemetrie[1]["tps"] is not None
        assert telemetrie[1]["generated_tokens_last_turn"] >= 1

