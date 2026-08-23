# ==============================================================================
# tests/test_model_specs_precision.py — Unit Tests for Real Model Size & Precision
# ==============================================================================
import pytest
from core.modules.sigma_model_hub.backend.hf_client import parse_model_specs


def test_q4_k_s_exact_quantization_and_used_storage():
    """Verify Q4_K_S precision detection and accurate file size calculations."""
    # 1. With usedStorage from Hugging Face API
    raw_item = {
        "usedStorage": 15825298656,
        "siblings": [
            {"rfilename": ".gitattributes"},
            {"rfilename": ".sigma_facts.json"},
            {"rfilename": "Qwen--Qwen3.8-27B.Q4_K_S.gguf"},
            {"rfilename": "README.md"}
        ],
        "gguf": {"total": 27320697856}
    }
    specs = parse_model_specs(
        model_id="sigmanih/Qwen3.8-27B-GGUF-Q4_K_S",
        name="Qwen3.8-27B-GGUF-Q4_K_S",
        tags=["gguf", "text-generation"],
        raw_item=raw_item
    )

    assert "Q4_K_S" in specs["precision"]
    assert specs["size_gb"] == 14.7
    assert specs["size_label"] == "~14.7 GB"
    assert specs["active_label"] == "27.32B"


def test_gguf_quant_fallback_multipliers():
    """Verify that different GGUF quantizations produce differentiated accurate sizes."""
    specs_q4_k_s = parse_model_specs("test/model-27b-q4_k_s-gguf", "model-27b-q4_k_s-gguf", ["gguf"])
    specs_q4_k_m = parse_model_specs("test/model-27b-q4_k_m-gguf", "model-27b-q4_k_m-gguf", ["gguf"])
    specs_q8_0 = parse_model_specs("test/model-27b-q8_0-gguf", "model-27b-q8_0-gguf", ["gguf"])
    specs_q3_k_s = parse_model_specs("test/model-27b-q3_k_s-gguf", "model-27b-q3_k_s-gguf", ["gguf"])

    assert "Q4_K_S" in specs_q4_k_s["precision"]
    assert "Q4_K_M" in specs_q4_k_m["precision"]
    assert "Q8_0" in specs_q8_0["precision"]
    assert "Q3_K_S" in specs_q3_k_s["precision"]

    # Q4_K_S should be smaller than Q4_K_M
    assert specs_q4_k_s["size_gb"] < specs_q4_k_m["size_gb"]
    # Q8_0 should be significantly larger than Q4_K_M
    assert specs_q8_0["size_gb"] > specs_q4_k_m["size_gb"]
    # Q3_K_S should be smaller than Q4_K_S
    assert specs_q3_k_s["size_gb"] < specs_q4_k_s["size_gb"]
