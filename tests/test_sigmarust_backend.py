# tests/test_sigmarust_backend.py — Test per SigmaRustBackend
import unittest
from unittest.mock import patch, MagicMock
import json

from core.engine.backends.sigmarust_backend import SigmaRustBackend, _is_rust_kernel_online
from core.engine.backends.registry import select_backend, all_backends
from core.engine.model_inspector import ModelFacts


class TestSigmaRustBackend(unittest.TestCase):
    def test_backend_in_registry(self):
        backends = all_backends()
        self.assertIn(SigmaRustBackend, backends)

    def test_supports_formats(self):
        facts_gguf = ModelFacts(path="/tmp/fake.gguf", name="test_model", weight_format="gguf")
        facts_safetensors = ModelFacts(path="/tmp/fake.st", name="test_st", weight_format="safetensors")
        facts_other = ModelFacts(path="/tmp/fake.bin", name="test_other", weight_format="pytorch_bin")

        self.assertTrue(SigmaRustBackend.supports(facts_gguf, {}))
        self.assertFalse(SigmaRustBackend.supports(facts_safetensors, {}))
        self.assertFalse(SigmaRustBackend.supports(facts_other, {}))

    def test_score_priority(self):
        facts = ModelFacts(path="/tmp/fake.gguf", name="test_model", weight_format="gguf")
        # Quando il kernel Rust è online: punteggio prioritario 125 che supera llama-server (110)
        with patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online", return_value=True):
            self.assertEqual(SigmaRustBackend.score(facts, {}), 125)

        # Quando il kernel Rust è offline: punteggio 0
        with patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online", return_value=False):
            self.assertEqual(SigmaRustBackend.score(facts, {}), 0)

    @patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online")
    def test_availability(self, mock_online):
        mock_online.return_value = True
        avail, reason = SigmaRustBackend.availability()
        self.assertTrue(avail)
        self.assertIn("attivo", reason)

        mock_online.return_value = False
        avail, reason = SigmaRustBackend.availability()
        self.assertFalse(avail)

    def test_select_backend_prefers_rust_when_online(self):
        facts = ModelFacts(path="/tmp/fake.gguf", name="qwen", weight_format="gguf")
        hardware = {"accelerators": []}

        # Quando è online vince per punteggio (125 vs 110/100)
        with patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online", return_value=True):
            with patch.object(SigmaRustBackend, "availability", return_value=(True, "Online")):
                chosen = select_backend(facts, hardware)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.name, "sigma_engine_rust")


class TestSenzaWorkerNonSiDichiaraCaricato(unittest.TestCase):
    """Il kernel e' un orchestratore: senza worker di calcolo non risponde.

    La rotta `/v1/chat/completions` del kernel restituisce 503 quando nessun
    upstream risponde, ed e' una scelta dichiarata (coda_inferenza.json: meglio
    un rifiuto che testo inventato -- il forward pass in Rust e' la voce i2, non
    ancora scritta). Quello che non deve succedere e' che il caricamento risulti
    riuscito lo stesso: la chat elencherebbe fra i modelli attivi uno che non
    produce un token, ed e' esattamente cio' che l'utente chiama "non funziona".
    """

    def _facts(self):
        return ModelFacts(path="/tmp/fake.gguf",
                          name="XHToken--Spark-X2.5-4B-GGUF",
                          weight_format="gguf")

    def _delegato(self, **configurazione):
        return patch("core.engine.backends.llamaserver_backend.LlamaServerBackend",
                     return_value=MagicMock(**configurazione))

    def test_un_worker_che_non_parte_fa_fallire_il_caricamento(self):
        esito = {
            "success": False, "stage": "runtime",
            "error": "La build di llama.cpp installata (b10682) non conosce "
                     "l'architettura 'spark2_5'.",
        }
        with self._delegato(load=MagicMock(return_value=esito)):
            backend = SigmaRustBackend()
            risultato = backend.load(self._facts(), {})

        self.assertFalse(risultato.get("success"))
        self.assertIn("non conosce l'architettura", risultato.get("error"))
        self.assertEqual(risultato.get("stage"), "runtime")
        self.assertFalse(backend.is_loaded)

    def test_un_worker_che_esplode_non_diventa_un_caricamento(self):
        with self._delegato(load=MagicMock(side_effect=RuntimeError("niente da fare"))):
            backend = SigmaRustBackend()
            risultato = backend.load(self._facts(), {})

        self.assertFalse(risultato.get("success"))
        self.assertIn("RuntimeError", risultato.get("error"))
        self.assertFalse(backend.is_loaded)

    def test_il_messaggio_non_consiglia_di_ridurre_il_contesto(self):
        """Un runtime che non conosce l'architettura non e' un problema di memoria."""
        from core.engine.unified_runtime import sigma_engine

        messaggio = sigma_engine._format_load_failure("XHToken--Spark-X2.5-4B-GGUF", {
            "success": False, "stage": "runtime",
            "error": "La build di llama.cpp installata (b10682) non conosce "
                     "l'architettura 'spark2_5'. Il file GGUF e' valido: aggiorna "
                     "il runtime dal pannello del motore e riprova.",
        })
        self.assertIn("non conosce l'architettura", messaggio)
        self.assertNotIn("riduci il contesto", messaggio)

    def test_con_il_worker_pronto_ma_il_kernel_irraggiungibile_si_usa_il_worker(self):
        """Il caso opposto: il calcolo c'e', il kernel e' caduto, e si prosegue."""
        finto = MagicMock()
        finto.load.return_value = {"success": True}
        finto.is_loaded = True

        with self._delegato(load=finto.load):
            with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen",
                       side_effect=OSError("kernel giu'")):
                risultato = SigmaRustBackend().load(self._facts(), {})

        self.assertTrue(risultato.get("success"))
        self.assertTrue(risultato.get("fallback"))


class TestStreamingRustConRipiegoLocale(unittest.TestCase):
    def test_registrazione_fallita_non_usa_un_vecchio_upstream(self):
        backend=SigmaRustBackend(endpoint_url="http://kernel.test")
        backend._proxy_registration_failed=True
        backend._compute_delegate=MagicMock()
        backend._compute_delegate.is_loaded=True
        backend._compute_delegate.generate_stream.return_value=iter([{"token":"dal modello corretto"}])
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen") as proxy:
            result=list(backend.generate_stream("ciao"))
        proxy.assert_not_called()
        self.assertEqual(result,[{"token":"dal modello corretto"}])
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen") as proxy:
            with self.assertRaises(RuntimeError):
                backend.tokenize("ciao")
            self.assertFalse(backend.slot_checkpoint("erase",0)["success"])
        proxy.assert_not_called()

    def _backend(self):
        backend = SigmaRustBackend(endpoint_url="http://kernel.test")
        backend._loaded_model_id = "qwen-test"
        backend._compute_delegate = MagicMock()
        backend._compute_delegate.is_loaded = True
        return backend

    def test_prova_il_proxy_rust_prima_del_worker_locale(self):
        class Risposta:
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "dal kernel"}}]}).encode()

        backend = self._backend()
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen",
                   return_value=Risposta()):
            risultato = list(backend.generate_stream("ciao"))

        self.assertEqual(risultato[0]["token"], "dal kernel")
        backend._compute_delegate.generate_stream.assert_not_called()

    def test_se_il_proxy_fallisce_usa_il_worker_sigma_locale(self):
        backend = self._backend()
        backend._compute_delegate.generate_stream.return_value = iter([{"token": "dal runtime locale"}])
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen",
                   side_effect=OSError("kernel spento")):
            risultato = list(backend.generate_stream("ciao"))

        self.assertEqual(risultato, [{"token": "dal runtime locale"}])
        backend._compute_delegate.generate_stream.assert_called_once()


class TestContrattoProxySigma(unittest.TestCase):
    def test_annullamento_inoltrato_anche_senza_token_in_arrivo(self):
        import threading
        cancelled=threading.Event();forwarded=threading.Event()
        backend=SigmaRustBackend(endpoint_url="http://kernel.test")
        response=MagicMock();response.__enter__.return_value=response
        response.headers={"Content-Type":"text/event-stream"}
        def stream():
            cancelled.set()
            if not forwarded.wait(1):raise AssertionError("Annullamento non inoltrato durante lo stallo")
            yield b"data: [DONE]\n\n"
        response.__iter__.side_effect=stream
        def cancel_request(**kwargs):
            forwarded.set();return {"cancelled":True}
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen",return_value=response), \
             patch.object(backend,"cancel_request",side_effect=cancel_request):
            list(backend.generate_stream("ciao",cancel=cancelled.is_set))
        self.assertTrue(forwarded.is_set())
    def _richiesta(self, **opzioni):
        backend = SigmaRustBackend(endpoint_url="http://kernel.test")
        backend._loaded_model_id = "sigma"
        risposta = MagicMock()
        risposta.__enter__.return_value = risposta
        risposta.headers = {"Content-Type": "application/json"}
        risposta.read.return_value = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen", return_value=risposta) as invio:
            list(backend.generate_stream("ciao", **opzioni))
        return json.loads(invio.call_args.args[0].data)

    def test_parametri_identici_al_worker_diretto(self):
        from core.engine.sampling import SamplingParams
        from core.engine.backends.llamaserver_backend import LlamaServerBackend
        params = SamplingParams(temperature=0.0, top_p=0.8, top_k=12, min_p=0.04,
                                repeat_penalty=1.08, max_tokens=32, seed=123,
                                stop=("FINE",), thinking_budget=64)
        atteso = LlamaServerBackend()._corpo_richiesta("ciao", "", None, params, False)
        corpo = self._richiesta(params=params, thinking=False)
        for campo, valore in atteso.items():
            with self.subTest(campo=campo):
                self.assertEqual(corpo.get(campo), valore)

    def test_tool_nativi_preservati_senza_grammatica_inventata(self):
        tools = [{"type": "function", "function": {"name": "leggi", "parameters": {"type": "object"}}}]
        corpo = self._richiesta(tools=tools, tool_choice="auto")
        self.assertEqual(corpo.get("tools"), tools)
        self.assertEqual(corpo.get("tool_choice"), "auto")
        self.assertNotIn("grammar", corpo)

    def test_telemetria_offline_non_inventa_latenze(self):
        backend = SigmaRustBackend(endpoint_url="http://kernel.test")
        with patch.object(backend, "get_status", return_value={"status": "error"}), \
             patch("core.engine.backends.sigma_ffi.is_ffi_available", return_value=False):
            telemetria = backend.telemetry()
        self.assertIsNone(telemetria["latency_breakdown"]["decode_us"])
        self.assertFalse(telemetria.get("measured", True))

    def test_cronologia_con_tool_id_preservata(self):
        messages = [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "call-1", "type": "function", "function": {"name": "leggi", "arguments": "{}"}}]},
            {"role": "tool", "content": "risultato", "tool_call_id": "call-1"}]
        corpo = self._richiesta(messages=messages)
        self.assertEqual(corpo["messages"][0]["tool_calls"], messages[0]["tool_calls"])
        self.assertEqual(corpo["messages"][1]["tool_call_id"], "call-1")

    def test_stream_tool_e_ragionamento_non_attiva_ripiego(self):
        backend = SigmaRustBackend(endpoint_url="http://kernel.test")
        delegate = MagicMock()
        delegate.is_loaded = True
        backend._compute_delegate = delegate
        calls = [{"index": 0, "function": {"name": "leggi", "arguments": "{}"}}]
        events = [{"choices": [{"delta": {"reasoning_content": "ragiono"}}], "usage": None},
                  {"choices": [{"delta": {"tool_calls": calls}, "finish_reason": "tool_calls"}]}]
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {"Content-Type": "text/event-stream"}
        response.__iter__.return_value = iter([("data: " + json.dumps(event) + "\n\n").encode() for event in events]
                                             + [b"data: [DONE]\n\n"])
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen", return_value=response):
            results = list(backend.generate_stream("ciao"))
        self.assertEqual(next(item["reasoning_content"] for item in results if "reasoning_content" in item), "ragiono")
        self.assertEqual(next(item["tool_calls"] for item in results if "tool_calls" in item), calls)
        self.assertEqual("".join(item.get("token", "") for item in results), "<think>ragiono</think>")
        delegate.generate_stream.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class TestCollocazioneDelWorker(unittest.TestCase):
    """Il piano del kernel non deve nascondere i layer effettivamente caricati dal worker."""

    def test_full_offload_letto_dal_worker_non_dal_piano(self):
        backend = SigmaRustBackend()
        backend._placement_info = {"mode": "plan_only", "vram_layers": 10}
        delegate = MagicMock(is_loaded=True)
        delegate.describe_placement.return_value = {"fully_offloaded": True, "layers_on_cpu": 0}
        backend._compute_delegate = delegate
        placement = backend.describe_placement()
        self.assertTrue(placement["fully_offloaded"])
        self.assertEqual(placement["rust_tiering_plan"]["mode"], "plan_only")

    def test_senza_worker_resta_il_piano(self):
        backend = SigmaRustBackend()
        backend._placement_info = {"mode": "plan_only"}
        self.assertEqual(backend.describe_placement(), {"mode": "plan_only"})


class TestConteggioTokenDelProxy(unittest.TestCase):
    """Il kernel manda il conteggio in un evento senza choices: va propagato, non sostituito dalle parole."""

    def test_usage_finale_diventa_total_tokens(self):
        backend = SigmaRustBackend(endpoint_url="http://kernel.test")
        events = [{"choices": [{"delta": {"content": "uno, due, tre"}}]},
                  {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                  {"choices": [], "usage": {"completion_tokens": 7, "prompt_tokens": 3}},
                  {"sigma_telemetry": {"completion_tokens": 7}}]
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {"Content-Type": "text/event-stream"}
        response.__iter__.return_value = iter([("data: " + json.dumps(e) + "\n\n").encode() for e in events]
                                             + [b"data: [DONE]\n\n"])
        with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen", return_value=response):
            results = list(backend.generate_stream("conta"))
        final = results[-1]
        self.assertTrue(final["done"])
        self.assertEqual(final["total_tokens"], 7)
        self.assertEqual("".join(r.get("token", "") for r in results), "uno, due, tre")
