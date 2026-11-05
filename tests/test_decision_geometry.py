"""Vincoli sui margini: validita' algebrica e letture limitate dei pesi."""

import hashlib

import pytest

np = pytest.importorskip("numpy")

from core.engine.activation_probe import fit_output_basis
from core.engine.decision_geometry import compare_outcomes, read_head_directions, select_margin_pairs


def test_selezione_prioritaria_estremi_e_margini_minimi():
    case = {"decisions": {"first": np.array([5, 2, 8, 4, 9]),
                          "second": np.array([6, 3, 7, 5, 10]),
                          "margins": np.array([1, .2, .01, .3, 2])}}
    assert select_margin_pairs([case], 3) == [(5, 6), (9, 10), (7, 8)]
    case["decisions"]["margins"][2] = -1
    with pytest.raises(ValueError, match="Decisioni"):
        select_margin_pairs([case])


def test_lettura_direzioni_include_gamma_e_non_modifica_gguf(tmp_path):
    gguf = pytest.importorskip("gguf")
    head = np.random.default_rng(42).normal(size=(3, 128)).astype(np.float32)
    gamma = np.linspace(.1, 2, 128).astype(np.float32)
    path = tmp_path / "head.gguf"
    writer = gguf.GGUFWriter(str(path), "qwen35")
    writer.add_tensor("output.weight", head)
    writer.add_tensor("output_norm.weight", gamma)
    writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()
    before = hashlib.sha256(path.read_bytes()).digest()
    direction = read_head_directions(path, [(0, 1)])[0]
    expected = (head[0].astype(np.float64)-head[1])*gamma
    np.testing.assert_allclose(direction, expected/np.linalg.norm(expected), atol=1e-12)
    assert hashlib.sha256(path.read_bytes()).digest() == before
    with pytest.raises(ValueError, match="budget"):
        read_head_directions(path, [(0, 3)])


def test_vincolo_preserva_margine_lineare_anche_su_stati_non_calibrati():
    rng = np.random.default_rng(42)
    width = 128
    training = rng.normal(size=(20, width)).astype(np.float32)
    direction = rng.normal(size=(1, width))
    case = {"tensors": {"y": {"features": training, "width": width, "tokens": 20,
                              "channels": np.arange(width)}}}
    basis, stats = fit_output_basis([case], "y", 4, protected_directions=direction)
    assert stats["protected_state_rank"] == 1
    y, residual = rng.normal(size=(30, width)), rng.normal(size=(30, width))
    projected = y @ basis.T @ basis
    before, after = (y+residual) @ direction.T, (projected+residual) @ direction.T
    np.testing.assert_allclose(before, after, atol=1e-5)
    # RMSNorm cambia il denominatore positivo: il segno della differenza resta invariato.
    before /= np.sqrt(np.mean(np.square(y+residual), axis=1, keepdims=True)+1e-6)
    after /= np.sqrt(np.mean(np.square(projected+residual), axis=1, keepdims=True)+1e-6)
    np.testing.assert_array_equal(np.sign(before), np.sign(after))
    with pytest.raises(ValueError, match="nulle"):
        fit_output_basis([case], "y", 4, protected_directions=np.zeros((1, width)))


def test_confronto_appaiato_allinea_id_e_non_nasconde_regressioni():
    base = [{"id": str(i), "passed": i<2, "ended": True} for i in range(4)]
    candidate = [{"id": str(i), "passed": i!=1, "ended": i!=3} for i in reversed(range(4))]
    result = compare_outcomes(base, candidate)
    assert result["candidate_passed"] == 3
    assert result["wins"] == ["2", "3"] and result["regressions"] == ["1"]
    assert result["new_length_limits"] == ["3"] and not result["observed_nonregression"]
    with pytest.raises(ValueError, match="duplicati"):
        compare_outcomes(base, candidate+candidate[:1])


def test_significativita_appaiata_e_limiti_del_piccolo_campione():
    base = [{"id": str(i), "passed": i>=6, "ended": True} for i in range(8)]
    candidate = [{**x, "passed": True} for x in base]
    result = compare_outcomes(base, candidate)
    assert result["mcnemar_exact_two_sided_p"] == pytest.approx(.03125)
    assert result["candidate_wilson95"][0] < .9
    assert compare_outcomes(candidate, candidate)["mcnemar_exact_two_sided_p"] == 1
