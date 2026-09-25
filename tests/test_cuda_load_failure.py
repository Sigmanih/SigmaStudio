# ==============================================================================
# tests/test_cuda_load_failure.py — Quando e' la scheda video a cedere
# ==============================================================================
"""Segnalazione reale, 25 settembre 2026, caricando `sigmanih--Qwen3.8-27B`:

    llama-server e' terminato (codice 3221226505).
    E CUDA error: unspecified launch failure
    E current device: 0, in function ggml_backend_cuda_buffer_set_tensor
    E cudaMemcpyAsync((char *) tensor->data + offset, data, size,
                      cudaMemcpyHostToDevice, stream)

L'utente ha ricevuto, sotto l'errore, il consiglio di **ridurre il contesto o
forzare una quantizzazione piu' aggressiva**. E' lo stesso consiglio sbagliato
che `runtime_probe` e' nato per togliere di mezzo nel caso dell'istruzione
illegale: il guasto e' una copia di memoria host->device, quindi avviene prima
che un contesto e una cache KV esistano. Nessuna quantita' di contesto cambia
una `cudaMemcpyAsync`.

Qui si tengono ferme tre cose:

- il guasto si riconosce dal **testo**, non dal solo codice d'uscita;
- il messaggio dice cosa e' successo e cosa fare, e zittisce il consiglio
  sbagliato (lo stage diventa `runtime`, come per l'istruzione illegale);
- il backend **riprova** abbassando l'offload, e ricorda cosa ha funzionato.
"""

import inspect

from core.engine import runtime_probe as RP
from core.engine.backends import llamaserver_backend as LS

#: L'uscita vera di llama.cpp in quel caso, riga per riga.
USCITA_CUDA = "\n".join([
    "0.12.011.558 E CUDA error: unspecified launch failure",
    "0.12.011.568 E current device: 0, in function "
    "ggml_backend_cuda_buffer_set_tensor at "
    "ggml/src/ggml-cuda/ggml-cuda.cu:790",
    "0.12.011.569 E cudaMemcpyAsync((char *) tensor->data + offset, data, "
    "size, cudaMemcpyHostToDevice, ((cudaStream_t)0x2))",
    "D:\\a\\llama.cpp\\llama.cpp\\ggml\\src\\ggml-cuda\\ggml-cuda.cu:107: "
    "CUDA error",
])

#: Il codice con cui Windows ha chiuso il processo (STATUS_STACK_BUFFER_OVERRUN).
CODICE = 3221226505


class TestRiconoscereLaSchedaCheCede:
    def test_il_caso_reale(self):
        assert RP.is_cuda_failure(returncode=CODICE, testo=USCITA_CUDA) is True

    def test_una_riga_cuda_basta_anche_senza_codice(self):
        assert RP.is_cuda_failure(testo="CUDA error: out of memory") is True
        assert RP.is_cuda_failure(
            testo="in function ggml_backend_cuda_buffer_set_tensor") is True

    def test_il_codice_basta_solo_se_il_processo_non_ha_detto_niente(self):
        """Un processo morto senza una riga di log, con quel codice, e' una
        scheda che si e' portata via il driver prima di poterlo raccontare."""
        assert RP.is_cuda_failure(returncode=CODICE, testo="") is True
        assert RP.is_cuda_failure(returncode=CODICE,
                                  testo="avvio fallito") is False

    def test_un_guasto_qualsiasi_non_diventa_un_guasto_di_gpu(self):
        assert RP.is_cuda_failure(returncode=1, testo="modello illeggibile") is False
        assert RP.is_cuda_failure() is False
        # Una pagina che non si legge e' un'altra diagnosi, e va tenuta distinta.
        assert RP.is_cuda_failure(
            returncode=3221225478, testo="STATUS_IN_PAGE_ERROR") is False


class TestIlMessaggioDiceLaVerita:
    def test_non_consiglia_di_ridurre_il_contesto(self):
        """E' la ragione per cui questo rapporto esiste."""
        rapporto = RP.cuda_failure_report(USCITA_CUDA)

        assert "cache KV" in rapporto
        assert "prima" in rapporto
        assert "Layer sulla GPU" in rapporto
        # Le tre cause, e ognuna col suo rimedio.
        assert "VRAM" in rapporto
        assert "driver" in rapporto
        assert "build CUDA" in rapporto

    def test_il_consiglio_generico_viene_zittito(self):
        """`unified_runtime` salta il suggerimento quando la causa e' gia'
        spiegata: se il rapporto non lo attiva, l'utente legge due volte."""
        from core.engine.unified_runtime import _causa_gia_spiegata

        assert _causa_gia_spiegata(RP.cuda_failure_report(USCITA_CUDA)) is True

    def test_lo_stage_e_runtime_come_per_l_istruzione_illegale(self):
        rapporto = RP.cuda_failure_report(USCITA_CUDA)
        assert LS._stage_del_motivo(rapporto) == "runtime"

    def test_il_rapporto_dice_anche_cosa_e_stato_gia_provato(self):
        rapporto = RP.cuda_failure_report(
            USCITA_CUDA, ["16 layer sulla GPU invece di 32",
                          "nessun layer sulla GPU (tutto in CPU)"])
        assert "16 layer sulla GPU invece di 32" in rapporto
        assert "tutto in CPU" in rapporto
        senza = RP.cuda_failure_report(USCITA_CUDA)
        assert "nessuna riduzione registrata" in senza

    def test_l_uscita_cruda_resta_allegata(self):
        """Senza il log, chi legge non puo' verificare la diagnosi."""
        rapporto = RP.cuda_failure_report(USCITA_CUDA)
        assert "unspecified launch failure" in rapporto
        assert "```" in rapporto


class TestLaScalaDeiRipieghi:
    def test_da_trentadue_layer_si_scende_a_sedici_poi_alla_cpu(self):
        scalini = LS._scalini_cuda({"n_gpu_layers": 32, "flash_attn": True})
        assert [s[0]["n_gpu_layers"] for s in scalini] == [16, 0]
        assert all(s[0]["flash_attn"] is False for s in scalini)
        assert "16 layer" in scalini[0][1]
        assert "CPU" in scalini[1][1]

    def test_con_un_layer_solo_si_va_direttamente_alla_cpu(self):
        scalini = LS._scalini_cuda({"n_gpu_layers": 1})
        assert [s[0]["n_gpu_layers"] for s in scalini] == [0]

    def test_con_zero_layer_non_c_e_niente_da_ridurre(self):
        assert LS._scalini_cuda({"n_gpu_layers": 0}) == []
        assert LS._scalini_cuda({}) == []

    def test_non_si_aggiunge_mai_flash_attention(self):
        """Il piano decide: queste sono riduzioni, non impostazioni."""
        scalini = LS._scalini_cuda({"n_gpu_layers": 8, "flash_attn": False})
        assert all(s[0]["flash_attn"] is False for s in scalini)


class TestIlBackendLoUsaDavvero:
    def test_il_caricamento_classifica_e_riprova(self):
        sorgente = inspect.getsource(LS.LlamaServerBackend.load)
        assert "is_cuda_failure" in sorgente
        assert "_scalini_cuda" in sorgente
        assert "indice_tentativo += 1" in sorgente, (
            "con un while, un `continue` senza avanzare l'indice gira per sempre")

    def test_il_codice_d_uscita_si_legge_prima_di_staccare_il_processo(self):
        """`unload()` azzera il processo: letto dopo, il codice d'uscita non
        esiste piu' e un guasto della scheda diventa indistinguibile."""
        sorgente = inspect.getsource(LS.LlamaServerBackend.load)
        inizio = sorgente.index("codice_uscita = self._processo.poll()")
        fine = sorgente.index("ultima_uscita = uscita", inizio)
        blocco = sorgente[inizio:fine]
        assert "self.unload()" in blocco, (
            "il codice va letto prima dell'unload che sta in mezzo")

    def test_l_attesa_traduce_il_guasto_in_un_rapporto(self):
        sorgente = inspect.getsource(LS.LlamaServerBackend._attendi_pronto)
        assert "cuda_failure_report" in sorgente
        assert "is_cuda_failure" in sorgente

    def test_quello_che_ha_funzionato_viene_ricordato(self):
        """Un avvio fallito costa minuti: riprovarlo a ogni caricamento no."""
        sorgente = inspect.getsource(LS.LlamaServerBackend.load)
        assert "load_overrides.set_for" in sorgente
        assert '"n_gpu_layers"' in sorgente

    def test_le_riduzioni_provate_finiscono_nel_messaggio(self):
        sorgente = inspect.getsource(LS.LlamaServerBackend._attendi_pronto)
        assert "_riduzioni_gpu" in sorgente


class TestAncheIlPercorsoInProcess:
    """La stessa macchina puo' ricadere sul backend in-process: il messaggio
    dev'essere lo stesso, o lo stesso guasto riceve due spiegazioni diverse."""

    def test_la_diagnosi_riconosce_la_gpu_che_cede(self):
        from core.engine.backends import llamacpp_backend as LC

        messaggio = LC._diagnose_load_error(
            RuntimeError("CUDA error: unspecified launch failure"),
            USCITA_CUDA, {"architecture": "qwen3", "name": "prova"}, {})
        assert "scheda video ha smesso di rispondere" in messaggio
        assert "cache KV" in messaggio

    def test_un_out_of_memory_resta_un_problema_di_memoria(self):
        """Il ramo della memoria e' piu' preciso, e li' il contesto conta
        davvero: e' la ragione per cui il ramo nuovo sta dopo il suo."""
        from core.engine.backends import llamacpp_backend as LC

        messaggio = LC._diagnose_load_error(
            RuntimeError("CUDA error: out of memory"),
            "CUDA error: out of memory",
            {"architecture": "qwen3", "name": "prova"}, {})
        assert "Memoria" in messaggio
        assert "scheda video ha smesso di rispondere" not in messaggio
