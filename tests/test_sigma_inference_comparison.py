"""Le misure Sigma usano token del worker e confrontano gli stessi input."""
import json
from unittest.mock import MagicMock, patch

import pytest

from tools.benchmarks.sigma_inference_comparison import misura, confronta


def response(events):
    reply = MagicMock()
    reply.__enter__.return_value = reply
    reply.__iter__.return_value = iter(
        [("data: " + json.dumps(event) + "\n\n").encode() for event in events]
        + [b"data: [DONE]\n\n"])
    return reply


def test_metriche_usano_token_del_worker_e_non_numero_eventi():
    events = [{"choices": [{"delta": {"role": "assistant"}}]},
              {"choices": [{"delta": {"content": "Un evento con molti token"}}]},
              {"usage": {"completion_tokens": 7}, "timings": {"predicted_per_second": 20.5}}]
    with patch("tools.benchmarks.sigma_inference_comparison.urllib.request.urlopen", return_value=response(events)):
        report = misura("http://worker.test", {})
    assert report["completion_tokens"] == 7
    assert report["worker_decode_tokens_per_second"] == 20.5
    assert report["ttft_ms"] >= 0
    assert report["output"] == "Un evento con molti token"


def test_senza_usage_non_si_stima_il_numero_di_token():
    with patch("tools.benchmarks.sigma_inference_comparison.urllib.request.urlopen",
               return_value=response([{"choices": [{"delta": {"content": "ciao"}}]}])):
        report = misura("http://worker.test", {})
    assert report["completion_tokens"] is None
    assert report["e2e_tokens_per_second"] is None


def test_confronto_alterna_ordine_e_mantiene_identici_gli_input():
    measured = {"ttft_ms": 10, "elapsed_ms": 100, "e2e_tokens_per_second": 20,
                "worker_decode_tokens_per_second": 21, "output_sha256": "uguale"}
    with patch("tools.benchmarks.sigma_inference_comparison.misura", return_value=measured) as run:
        report = confronta("http://worker.test", "http://rust.test", "token", "sigma", 2, 32)
    calls = run.call_args_list[2:]
    assert [call.args[0] for call in calls] == ["http://worker.test", "http://rust.test",
                                               "http://rust.test", "http://worker.test"]
    assert all(call.args[1] == calls[0].args[1] for call in calls)
    assert report["outputs_match"] is True
    assert report["request"]["cache_prompt"] is False


def test_errore_inferenza_non_diventa_una_misura_valida():
    with patch("tools.benchmarks.sigma_inference_comparison.urllib.request.urlopen",
               return_value=response([{"error": {"message": "worker assente"}}])):
        with pytest.raises(RuntimeError, match="worker assente"):
            misura("http://worker.test", {})
