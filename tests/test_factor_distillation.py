"""Recupero di una componente perduta senza aggiornare il classificatore."""

import hashlib

import pytest

np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")

from core.modules.sigma_training_lab.factor_distillation import distill_decoder, load_frozen_head


def toy_data():
    rng = np.random.default_rng(42)
    head = torch.from_numpy(rng.normal(size=(8, 128)).astype(np.float32))
    gamma = torch.ones(128)
    encoder = np.eye(128, dtype=np.float32)[:2]
    cases = []
    for _ in range(4):
        y = np.zeros((12, 128), dtype=np.float32)
        y[:, :2] = rng.normal(size=(12, 2))
        y[:, 2] = .8*y[:, 0]
        h = y+rng.normal(scale=.03, size=y.shape).astype(np.float32)
        hidden = torch.from_numpy(h)
        logits = (hidden*torch.rsqrt(hidden.square().mean(dim=1, keepdim=True)+1e-6)) @ head.T
        p = torch.softmax(logits, dim=1)
        values, ids = p.topk(2, dim=1)
        cases.append({"tensors": {"ffn": {"features": y, "width": 128, "tokens": 12}},
                      "hidden": h, "decisions": {"first": ids[:, 0].numpy(), "second": ids[:, 1].numpy()},
                      "native_top_probabilities": values.numpy()})
    return cases, encoder, head, gamma


def test_decoder_recupera_fedelta_su_caso_senza_gradiente():
    cases, encoder, head, gamma = toy_data()
    before = head.clone()
    result = distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                             steps=40, learning_rate=.01, batch_size=8, validate_every=10)
    metrics = result["metrics"]
    assert metrics["best_validation_kl"] < .9*metrics["initial_validation_kl"]
    assert metrics["native_argmax_agreement"] == 1
    assert metrics["trainable_parameters"] == 256 and metrics["training_cases"] == 3
    assert torch.equal(before, head) and not head.requires_grad
    np.testing.assert_array_equal(result["encoder"], encoder)


def test_blocca_gradiente_sul_classificatore_e_validazione_non_separata():
    cases, encoder, head, gamma = toy_data()
    with pytest.raises(ValueError, match="validazioni"):
        distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[0, 1, 2, 3])
    head.requires_grad_(True)
    with pytest.raises(ValueError, match="congelato"):
        distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1])


def test_carica_classificatore_senza_modificare_gguf(tmp_path):
    gguf = pytest.importorskip("gguf")
    path = tmp_path / "head.gguf"
    writer = gguf.GGUFWriter(str(path), "qwen35")
    writer.add_layer_norm_rms_eps(1e-6)
    writer.add_tensor("output.weight", np.ones((8, 128), dtype=np.float32))
    writer.add_tensor("output_norm.weight", np.ones(128, dtype=np.float32))
    writer.write_header_to_file();writer.write_kv_data_to_file();writer.write_tensors_to_file();writer.close()
    before = hashlib.sha256(path.read_bytes()).digest()
    head, gamma, eps = load_frozen_head(path, max_working_mib=128)
    assert head.shape == (8, 128) and gamma.shape == (128,)
    assert eps == pytest.approx(1e-6) and not head.requires_grad
    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_decoder_aggiorna_senza_alterare_direzione_protetta():
    cases, encoder, head, gamma = toy_data()
    direction = np.eye(128, dtype=np.float32)[100:101]
    result = distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                             steps=20, learning_rate=.01, batch_size=8, validate_every=10,
                             protected_directions=direction)
    delta = result["decoder"]-encoder
    assert np.linalg.norm(delta) > 0
    np.testing.assert_allclose(delta @ direction.T, 0, atol=1e-8)
    assert result["metrics"]["protected_direction_rank"] == 1
    assert result["metrics"]["effective_free_parameters"] == 254


def test_supervisione_verificata_ottimizza_nll_e_rifiuta_etichette_non_certificate():
    cases, encoder, head, gamma = toy_data()
    for case in cases:
        case["reference_tokens"] = case["decisions"]["second"].copy()
    with pytest.raises(ValueError, match="non verificati"):
        distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1], reference_weight=2)
    for case in cases:
        case["reference_verified"] = True
    result = distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                             reference_weight=2, steps=40, learning_rate=.01, batch_size=8, validate_every=10)
    metrics = result["metrics"]
    assert metrics["selection_metric"] == "reference_nll"
    assert metrics["best_validation_reference_nll"] < metrics["initial_validation_reference_nll"]
    assert metrics["verified_reference_cases"] == 4
    assert not head.requires_grad


def test_vincolo_terminale_preserva_uscite_training_e_seleziona_senza_peggiorare_validazione():
    cases, encoder, head, gamma = toy_data()
    for case in cases:
        case["reference_tokens"] = case["decisions"]["second"].copy()
        case["reference_verified"] = True
    # Un solo vincolo indipendente lascia spazio per un aggiornamento misurabile.
    for case in cases:
        case["tensors"]["ffn"]["features"][-1] = cases[0]["tensors"]["ffn"]["features"][-1]
        hidden = torch.from_numpy(case["hidden"])
        logits = (hidden*torch.rsqrt(hidden.square().mean(dim=1, keepdim=True)+1e-6)) @ head.T
        values, ids = torch.softmax(logits, dim=1).topk(2, dim=1)
        case["decisions"] = {"first": ids[:, 0].numpy(), "second": ids[:, 1].numpy()}
        case["native_top_probabilities"] = values.numpy()
    result = distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                             reference_weight=2, steps=40, learning_rate=.01, batch_size=8,
                             validate_every=10, protect_training_ends=True, max_terminal_nll_increase=0,
                             protected_directions=np.eye(128, dtype=np.float32)[100:101])
    metrics = result["metrics"]
    assert metrics["protected_training_end_rank"] == 1
    assert metrics["effective_free_parameters"] == 127
    assert metrics["best_step"] > 0 and np.linalg.norm(result["decoder"]-encoder) > 0
    terminal_latent = cases[0]["tensors"]["ffn"]["features"][-1] @ encoder.T
    np.testing.assert_allclose(terminal_latent @ (result["decoder"]-encoder), 0, atol=1e-6)
    np.testing.assert_allclose((result["decoder"]-encoder)[:, 100], 0, atol=1e-8)
    assert all(b <= a for a, b in zip(metrics["initial_validation_terminal_reference_nll"],
                                      metrics["best_validation_terminal_reference_nll"]))


def test_vincoli_terminali_rifiutano_budget_non_finiti_e_rango_esaurito():
    cases, encoder, head, gamma = toy_data()
    with pytest.raises(ValueError, match="terminazione"):
        distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                         max_terminal_nll_increase=float('nan'))
    with pytest.raises(ValueError, match="verificati"):
        distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                         max_terminal_nll_increase=0)
    with pytest.raises(ValueError, match="esauriscono"):
        distill_decoder(cases, encoder, head, gamma, 1e-6, validation_indices=[1],
                         protect_training_ends=True)
