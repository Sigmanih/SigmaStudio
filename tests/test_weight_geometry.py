"""Controlli numerici e invarianti per gli esperimenti geometrici sui pesi."""

import pytest

np = pytest.importorskip("numpy")

from core.engine.weight_geometry import audit_gguf, permute_swiglu_sample, reconstruction_error


def test_i_momenti_delle_attivazioni_cambiano_la_priorita_dell_errore():
    ref = np.ones((1, 2))
    first = reconstruction_error(ref, ref + [[1.0, 0]], [1, 1000])
    second = reconstruction_error(ref, ref + [[0, 0.1]], [1, 1000])
    assert first["relative_mse"] > second["relative_mse"]
    assert first["relative_weighted_mse"] < second["relative_weighted_mse"]
    assert second["weighted_error_energy"] == pytest.approx(10)


def test_riferimento_nullo_non_produce_rapporti_fuorvianti():
    result = reconstruction_error([[0, 0]], [[1, 0]], [1, 1])
    assert result["relative_weighted_mse"] is None
    assert result["weighted_error_energy"] == 1


def test_intervallo_bootstrap_per_una_distorsione_uniforme():
    ref = np.ones((32, 2))
    result = reconstruction_error(ref, ref * 0.5, [1, 2], bootstrap=200)
    assert result["row_bootstrap_ci95"] == pytest.approx([0.25, 0.25])
    with pytest.raises(ValueError, match="budget di memoria"):
        reconstruction_error(np.ones((3000, 1)), np.ones((3000, 1)), [1], bootstrap=1000)


@pytest.mark.parametrize("moment", [[-1, 1], [1], [float("nan"), 1]])
def test_momenti_non_validi_sono_rifiutati(moment):
    with pytest.raises(ValueError):
        reconstruction_error([[1, 1]], [[1, 1]], moment)


def test_permutazione_coordinata_preserva_swiglu_ma_una_sola_matrice_no():
    rng = np.random.default_rng(42)
    gate, up, down = rng.normal(size=(4, 3)), rng.normal(size=(4, 3)), rng.normal(size=(2, 4))
    value = rng.normal(size=(3, 8))
    order = [2, 0, 3, 1]

    def forward(g, u, d):
        z = g @ value
        return d @ ((z / (1 + np.exp(-z))) * (u @ value))

    before = forward(gate, up, down)
    transformed = permute_swiglu_sample(gate, up, down, order)
    np.testing.assert_allclose(forward(*transformed), before, atol=1e-12)
    assert not np.allclose(forward(gate, up, transformed[2]), before)
    with pytest.raises(ValueError):
        permute_swiglu_sample(gate, up, down, [0, 0, 1, 2])


def test_audit_legge_gguf_e_rispetta_il_budget(tmp_path):
    gguf = pytest.importorskip("gguf")
    name = "blk.0.ffn_up.weight"

    def write(path, tensors):
        writer = gguf.GGUFWriter(str(path), "llama")
        for key, array in tensors.items():
            writer.add_tensor(key, np.asarray(array, dtype=np.float32))
        writer.write_header_to_file()
        writer.write_kv_data_to_file()
        writer.write_tensors_to_file()
        writer.close()

    reference, candidate, stats = (tmp_path / n for n in ("ref.gguf", "cand.gguf", "stats.gguf"))
    write(reference, {name: np.ones((2, 32))})
    write(candidate, {name: np.full((2, 32), 0.5)})
    write(stats, {name + ".in_sum2": np.ones(32) * 8, name + ".counts": [8]})
    result = audit_gguf(candidate, reference, stats, [name])
    assert result["complete"]
    assert result["entries"][0]["relative_weighted_mse"] == pytest.approx(0.25)
    result = audit_gguf(candidate, reference, stats, [name], max_values=1)
    assert not result["complete"] and result["stop_reason"] == "value_budget"
