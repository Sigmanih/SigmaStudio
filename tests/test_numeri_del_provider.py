"""Il server dice quanto ha prefillato e quanto ha riusato: si legge.

Il riuso del prefisso e' la differenza fra un turno che costa dodicimila token
di attesa e uno che ne costa duecento, e finora quel numero arrivava solo dal
motore SigmaEngine. Da un server compatibile OpenAI (`usage` per OpenAI,
`timings` per llama.cpp) il campo non arrivava mai: in ogni sessione GGUF il
riuso risultava zero. Non era una misura di zero, era l'assenza di una misura,
ed e' la cosa peggiore perche' sembra un dato.

Qui si verifica che i conteggi vengono letti, che il calcolo del riuso non
dipende dall'ordine in cui i due pezzi arrivano, che un pezzo coi numeri esce
solo quando c'e' qualcosa da dichiarare, e che una richiesta a un server locale
chiede i conteggi senza perdere il run se quel server non li conosce.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from core.ai_providers import (
    _chunk_numeri,
    _endpoint_locale,
    _raccogli_numeri,
    call_openai_compatible_stream,
)


def _risposta(righe):
    """Una risposta in streaming finta, come la vedrebbe il client HTTP."""
    finta = MagicMock()
    finta.status_code = 200
    finta.text = ""
    finta.iter_lines.return_value = righe
    return finta


class TestILettoreDeiNumeri(unittest.TestCase):
    """`usage` e `timings`, letti per quello che dicono."""

    def test_llama_cpp_dice_quanto_ha_valutato_e_in_quanto_tempo(self):
        numeri = {}
        _raccogli_numeri({"timings": {"prompt_n": 1000, "prompt_ms": 2500.4,
                                      "predicted_n": 42}}, numeri)
        pezzo = _chunk_numeri(numeri)
        self.assertEqual(pezzo["prefill_ms"], 2500.4)
        self.assertEqual(pezzo["generated_tokens"], 42)
        self.assertTrue(pezzo["counters"])

    def test_il_riuso_non_dipende_dall_ordine_dei_pezzi(self):
        """`timings` puo' arrivare prima di `usage`: il conto si fa alla fine."""
        prima = {}
        _raccogli_numeri({"timings": {"prompt_n": 1000}}, prima)
        _raccogli_numeri({"usage": {"prompt_tokens": 10500}}, prima)
        self.assertEqual(_chunk_numeri(prima)["prefix_reused_tokens"], 9500)

        dopo = {}
        _raccogli_numeri({"usage": {"prompt_tokens": 10500}}, dopo)
        _raccogli_numeri({"timings": {"prompt_n": 1000}}, dopo)
        self.assertEqual(_chunk_numeri(dopo)["prefix_reused_tokens"], 9500)

    def test_se_il_server_conta_lui_la_cache_quello_e_il_numero(self):
        numeri = {}
        _raccogli_numeri({"usage": {"prompt_tokens": 10500},
                          "timings": {"cache_n": 9000, "prompt_n": 1500}}, numeri)
        self.assertEqual(_chunk_numeri(numeri)["prefix_reused_tokens"], 9000)

    def test_un_server_che_non_dice_niente_non_dichiara_zero(self):
        """La differenza fra un riuso mancato e un riuso non misurato."""
        self.assertIsNone(_chunk_numeri({}))

    def test_numeri_storti_non_fanno_esplodere_il_lettore(self):
        numeri = {}
        _raccogli_numeri({"usage": "molti", "timings": [1, 2, 3]}, numeri)
        _raccogli_numeri({"timings": {"prompt_n": "mille"}}, numeri)
        _raccogli_numeri(None, numeri)
        self.assertIsNone(_chunk_numeri(numeri))

    def test_il_prefill_non_diventa_mai_negativo(self):
        numeri = {}
        _raccogli_numeri({"timings": {"prompt_n": 20000},
                          "usage": {"prompt_tokens": 10500}}, numeri)
        self.assertEqual(_chunk_numeri(numeri)["prefix_reused_tokens"], 0)


class TestDoveSiChiedonoIConteggi(unittest.TestCase):
    """I conteggi si chiedono in locale, non a un servizio remoto."""

    def test_riconosce_gli_endpoint_locali(self):
        for url in ("http://127.0.0.1:8080/v1/chat/completions",
                    "http://localhost:11434/v1/chat/completions",
                    "http://[::1]:8080/v1/chat/completions"):
            self.assertTrue(_endpoint_locale(url), url)

    def test_non_chiede_niente_a_un_servizio_remoto(self):
        for url in ("https://api.deepseek.com/chat/completions",
                    "https://api.openai.com/v1/chat/completions",
                    "non-e-un-url", ""):
            self.assertFalse(_endpoint_locale(url), url)

    @patch("core.ai_providers.requests.post")
    def test_a_un_server_locale_i_conteggi_si_chiedono(self, mock_post):
        mock_post.return_value = _risposta([
            'data: {"choices": [{"delta": {"content": "ciao"}}]}',
            'data: {"choices": [{"finish_reason": "stop", "delta": {}}], '
            '"timings": {"prompt_n": 2000, "prompt_ms": 800.0, "cache_n": 8000}}',
            'data: [DONE]',
        ])

        eventi = list(call_openai_compatible_stream(
            messages=[{"role": "user", "content": "ciao"}],
            model="qwen3-27b", api_url="http://127.0.0.1:8080/v1/chat/completions",
            api_key="", temperature=0.2, max_tokens=64, top_p=0.9, timeout=60,
        ))

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload.get("stream_options"), {"include_usage": True})
        # Il riuso non basta aspettarlo: a llama.cpp va chiesto.
        self.assertTrue(payload.get("cache_prompt"))
        conteggi = [e for e in eventi if e.get("counters")]
        self.assertEqual(len(conteggi), 1)
        self.assertEqual(conteggi[0]["prefix_reused_tokens"], 8000)
        self.assertEqual(conteggi[0]["prefill_ms"], 800.0)
        self.assertEqual([e.get("token") for e in eventi if e.get("token")],
                         ["ciao"])

    @patch("core.ai_providers.requests.post")
    def test_a_un_servizio_remoto_non_si_manda_stream_options(self, mock_post):
        mock_post.return_value = _risposta([
            'data: {"choices": [{"delta": {"content": "ciao"}}]}',
            'data: {"choices": [{"finish_reason": "stop", "delta": {}}]}',
            'data: [DONE]',
        ])
        list(call_openai_compatible_stream(
            messages=[{"role": "user", "content": "ciao"}],
            model="deepseek-coder", api_url="https://api.deepseek.com/chat/completions",
            api_key="sk-test", temperature=0.2, max_tokens=64, top_p=0.9, timeout=60,
        ))
        payload = mock_post.call_args.kwargs["json"]
        self.assertNotIn("stream_options", payload)
        self.assertNotIn("cache_prompt", payload)

    @patch("core.ai_providers.requests.post")
    def test_un_server_che_rifiuta_i_conteggi_non_perde_il_run(self, mock_post):
        """Un `400` sui conteggi non e' un motivo per non rispondere."""
        rifiuto = MagicMock()
        rifiuto.status_code = 400
        rifiuto.text = '{"error":"unknown field stream_options"}'
        mock_post.side_effect = [rifiuto, _risposta([
            'data: {"choices": [{"delta": {"content": "ciao"}}]}',
            'data: {"choices": [{"finish_reason": "stop", "delta": {}}]}',
            'data: [DONE]',
        ])]

        eventi = list(call_openai_compatible_stream(
            messages=[{"role": "user", "content": "ciao"}],
            model="qwen3-27b", api_url="http://127.0.0.1:8080/v1/chat/completions",
            api_key="", temperature=0.2, max_tokens=64, top_p=0.9, timeout=60,
        ))

        self.assertEqual(mock_post.call_count, 2)
        secondo = mock_post.call_args.kwargs["json"]
        self.assertNotIn("stream_options", secondo)
        self.assertNotIn("cache_prompt", secondo)
        self.assertEqual([e.get("token") for e in eventi if e.get("token")],
                         ["ciao"])
        # Senza conteggi non si inventa niente: nessun pezzo `counters`.
        self.assertEqual([e for e in eventi if e.get("counters")], [])


if __name__ == "__main__":
    unittest.main()
