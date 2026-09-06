"""Cosa deve stare in memoria, e cosa invece si legge a pagine.

Nasce da un incidente reale: un Q8_0 da 157 GB avviato su una macchina con
94 GB di RAM e 24 di VRAM. Il server non ha mai risposto, il timeout d'avvio
e' scattato dopo cinque minuti e nel frattempo la page cache aveva portato la
RAM all'86%; per fermarlo e' servito uccidere il processo a mano.

La tentazione era rifiutare i modelli piu' grandi della memoria. Sarebbe
sbagliato, e lo dimostra il fatto che quel modello **una volta era partito**:
e' un MoE mappato in memoria, i suoi esperti non sono residenti — si leggono a
pagine, e di cinquecento per layer un token ne accende dieci. Confrontare la
taglia del file con la RAM rifiuterebbe modelli che funzionano.

Il confronto giusto e' fra la memoria e cio' che deve starci davvero: la parte
densa piu' i tensori che llama.cpp tiene in RAM per forza. Questi test fissano
quel confine, e soprattutto che non si sposti dalla parte sbagliata.
"""

from types import SimpleNamespace

import pytest

from core.engine.gguf_planner import _CAPIENZA_MASSIMA, placement_is_impossible


def _macchina(vram_gb=24.4, ram_gb=93.7, ram_libera_gb=40.0):
    """La macchina dell'incidente: 5070 Ti piu' 5060, 94 GB di RAM."""
    return {
        "accelerators": [
            {"type": "NVIDIA_CUDA", "total_vram_gb": 16.3, "free_vram_gb": 14.7},
            {"type": "NVIDIA_CUDA", "total_vram_gb": 8.1, "free_vram_gb": 7.9},
        ],
        "ram": {"total_gb": ram_gb, "available_gb": ram_libera_gb},
    }


def _modello(nome="modello", gb=10.0, esperti_gb=0.0):
    """Un modello denso, oppure un MoE se si dichiara il peso degli esperti."""
    return SimpleNamespace(
        name=nome,
        total_bytes=int(gb * 2**30),
        expert_bytes=int(esperti_gb * 2**30),
        path="",
    )


class TestIlConfine:
    def test_un_moe_piu_grande_della_memoria_e_ammesso(self):
        """Il caso dell'incidente: gli esperti si leggono a pagine, non sono residenti."""
        assert placement_is_impossible(
            _modello("Flash-Next-Q8_0", 157.0, esperti_gb=140.0), _macchina()
        ) is None

    def test_lo_stesso_peso_ma_denso_viene_rifiutato(self):
        """Senza esperti da mappare, quei byte devono stare in memoria davvero."""
        motivo = placement_is_impossible(_modello("denso-enorme", 157.0), _macchina())
        assert motivo is not None
        assert "157" in motivo and "118" in motivo

    def test_un_moe_con_la_parte_densa_troppo_grande_viene_rifiutato(self):
        """Gli esperti si leggono a pagine; il resto no."""
        assert placement_is_impossible(
            _modello("moe-denso-enorme", 200.0, esperti_gb=50.0), _macchina()
        ) is not None

    def test_il_modello_che_gira_ogni_giorno_passa(self):
        """Il 27B Q4_K_S e' quello con cui l'harness lavora: rifiutarlo sarebbe un disastro."""
        assert placement_is_impossible(_modello("Qwen3.8-27B-Q4_K_S", 15.1), _macchina()) is None

    def test_un_modello_grande_ma_possibile_passa(self):
        """Lento non e' impossibile: un 70B Q4 sta in RAM e deve poter girare."""
        assert placement_is_impossible(_modello("70B-Q4", 40.0), _macchina()) is None

    def test_appena_sotto_la_soglia_passa(self):
        capienza = (24.4 + 93.7) * _CAPIENZA_MASSIMA
        assert placement_is_impossible(_modello("limite", capienza - 1), _macchina()) is None

    def test_appena_sopra_la_soglia_viene_rifiutato(self):
        capienza = (24.4 + 93.7) * _CAPIENZA_MASSIMA
        assert placement_is_impossible(_modello("limite", capienza + 1), _macchina()) is not None

    def test_la_soglia_lascia_margine_al_sistema(self):
        """Riempire l'ultimo byte non e' possibile: servono KV, buffer e il resto del sistema."""
        assert 0.5 < _CAPIENZA_MASSIMA < 1.0


class TestQuandoNonSiRifiuta:
    """Un rifiuto sbagliato costa piu' di un caricamento lento."""

    def test_senza_dati_hardware_non_si_rifiuta(self):
        assert placement_is_impossible(_modello("enorme", 999.0), {}) is None

    def test_senza_acceleratori_conta_la_sola_ram(self):
        solo_cpu = {"accelerators": [], "ram": {"total_gb": 8.0}}
        assert placement_is_impossible(_modello("piccolo", 3.0), solo_cpu) is None
        assert placement_is_impossible(_modello("grosso", 30.0), solo_cpu) is not None

    def test_un_modello_di_dimensione_ignota_non_si_rifiuta(self):
        assert placement_is_impossible(_modello("senza_taglia", 0.0), _macchina()) is None

    def test_la_ram_momentaneamente_occupata_non_conta(self):
        """Si guarda la RAM totale, non quella libera: la page cache si libera.

        Rifiutare in base alla RAM libera renderebbe il caricamento dipendente
        da cosa gira in quel momento — lo stesso modello ammesso alle otto e
        rifiutato alle nove, senza che nulla di rilevante sia cambiato.
        """
        occupata = _macchina(ram_libera_gb=2.0)
        assert placement_is_impossible(_modello("Qwen3.8-27B", 15.1), occupata) is None


class TestIlMessaggio:
    def test_dice_i_numeri_invece_di_dire_no(self):
        motivo = placement_is_impossible(_modello("denso-enorme", 157.0), _macchina())
        assert "di VRAM" in motivo
        assert "di RAM" in motivo
        assert "denso-enorme" in motivo

    def test_per_un_moe_distingue_il_residente_dal_file(self):
        """Chi legge il messaggio deve capire perche' 200 GB non sono 200 GB."""
        motivo = placement_is_impossible(
            _modello("moe", 200.0, esperti_gb=50.0), _macchina()
        )
        assert "residenti" in motivo and "esperti letti a pagine" in motivo

    def test_spiega_perche_non_e_solo_lentezza(self):
        """La distinzione che conta: l'utente altrimenti aspetta pensando sia lento."""
        motivo = placement_is_impossible(_modello("enorme", 500.0), _macchina())
        assert "non e' una questione di lentezza" in motivo.lower()

    def test_indica_una_via_d_uscita(self, monkeypatch):
        import core.engine.gguf_planner as planner
        monkeypatch.setattr(
            planner, "suggest_smaller_variant",
            lambda facts, hardware: {"name": "Flash-Next-Q4_K_M", "size_gb": 111.0},
        )
        motivo = placement_is_impossible(_modello("Flash-Next-Q8_0", 157.0), _macchina())
        assert "Flash-Next-Q4_K_M" in motivo

    def test_senza_alternative_suggerisce_comunque_cosa_fare(self, monkeypatch):
        import core.engine.gguf_planner as planner
        monkeypatch.setattr(planner, "suggest_smaller_variant", lambda f, h: None)
        motivo = placement_is_impossible(_modello("enorme", 500.0), _macchina())
        assert "quantizzazione" in motivo.lower()


class TestIlBackendRifiutaPrimaDiAvviare:
    """Il punto dell'intera correzione: il processo non deve partire."""

    def test_il_rifiuto_arriva_come_esito_di_load(self, monkeypatch):
        from core.engine.backends import llamaserver_backend as backend

        chiamate = {"spawn": 0}
        monkeypatch.setattr(
            backend.gguf_planner, "placement_is_impossible",
            lambda facts, hardware: "non ci sta",
        )
        monkeypatch.setattr(
            backend.gguf_planner, "_plan_settings",
            lambda *a, **k: chiamate.__setitem__("spawn", chiamate["spawn"] + 1) or {},
        )

        istanza = backend.LlamaServerBackend()
        monkeypatch.setattr(istanza, "_file_gguf", lambda facts: "modello.gguf")
        monkeypatch.setattr(
            "core.engine.llama_runtime.installed_server", lambda: "llama-server.exe"
        )

        esito = istanza.load(_modello("enorme", 500.0), _macchina(), context_tokens=8192)

        assert esito["success"] is False
        assert esito["stage"] == "capacity"
        assert "non ci sta" in esito["error"]
        # E soprattutto: non si e' nemmeno arrivati a pianificare.
        assert chiamate["spawn"] == 0


class TestTimeoutDiAvvio:
    """Trecento secondi fissi uccidono un caricamento che sta procedendo.

    E' l'altra meta' dell'incidente, e la piu' insidiosa: il modello non era
    impossibile — una volta era arrivato in fondo — ma la prima lettura di un
    file da 157 GB mappato in memoria non finisce in cinque minuti. Dall'esterno
    si vedeva solo «llama-server non ha risposto», che manda a cercare il
    problema ovunque tranne che nel timeout.
    """

    def test_i_modelli_ordinari_tengono_il_timeout_di_sempre(self):
        from core.engine.backends.llamaserver_backend import (
            _AVVIO_TIMEOUT_S, _timeout_avvio,
        )
        for gb in (0.5, 4, 15, 40):
            assert _timeout_avvio(gb) == _AVVIO_TIMEOUT_S, gb

    def test_un_modello_enorme_ottiene_piu_tempo(self):
        from core.engine.backends.llamaserver_backend import _timeout_avvio
        assert _timeout_avvio(157.0) > 600

    def test_il_tempo_cresce_con_la_taglia(self):
        from core.engine.backends.llamaserver_backend import _timeout_avvio
        assert _timeout_avvio(200.0) > _timeout_avvio(120.0) > _timeout_avvio(40.0)

    def test_esiste_comunque_un_tetto(self):
        """Oltre un certo punto non sta caricando: sta morendo piano."""
        from core.engine.backends.llamaserver_backend import (
            _AVVIO_TIMEOUT_MASSIMO_S, _timeout_avvio,
        )
        assert _timeout_avvio(100_000.0) == _AVVIO_TIMEOUT_MASSIMO_S

    def test_una_taglia_ignota_non_allunga_l_attesa(self):
        from core.engine.backends.llamaserver_backend import (
            _AVVIO_TIMEOUT_S, _timeout_avvio,
        )
        assert _timeout_avvio(0) == _AVVIO_TIMEOUT_S
        assert _timeout_avvio(-5) == _AVVIO_TIMEOUT_S
