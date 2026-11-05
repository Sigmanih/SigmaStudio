"""Proiezioni spettrali controllate su matrici con spettro noto."""

import pytest

np = pytest.importorskip("numpy")

from core.engine.weight_spectrum import full_gram_spectrum, streamed_spectrum


def test_spettro_noto_ed_effetto_della_ponderazione():
    matrix = np.zeros((24, 16), dtype=np.float32)
    matrix[0, 0], matrix[1, 1] = 4, 3
    moment = np.ones(16)
    moment[0] = 9
    calls = []

    def read(start, stop):
        calls.append((start, stop))
        return matrix[start:stop]

    result = streamed_spectrum(matrix.shape, read, ranks=(1, 2, 4),
                              second_moment=moment, block_rows=5)
    raw, weighted = (result["modes"][key] for key in ("unweighted", "diagonal_weighted"))
    assert raw["energy"] == pytest.approx(25)
    assert raw["curves"][0]["retained_energy"] == pytest.approx(16/25, abs=1e-6)
    assert raw["curves"][1]["retained_energy"] == pytest.approx(1, abs=1e-6)
    assert weighted["curves"][0]["retained_energy"] == pytest.approx(144/153, abs=1e-6)
    assert len(calls) == 10 and all(stop-start <= 5 for start, stop in calls)


def test_matrice_non_comprimibile_non_appare_di_rango_basso():
    matrix = np.eye(16, dtype=np.float32)
    result = streamed_spectrum(matrix.shape, lambda a, b: matrix[a:b], ranks=(2, 4))
    assert result["modes"]["unweighted"]["curves"][1]["retained_energy"] == pytest.approx(0.25, abs=1e-6)


def test_matrice_nulla_non_suggerisce_una_compressione_verificata():
    matrix = np.zeros((8, 8), dtype=np.float32)
    result = streamed_spectrum(matrix.shape, lambda a, b: matrix[a:b], ranks=(2,))
    assert result["modes"]["unweighted"]["curves"][0]["retained_energy"] is None


def test_budget_memoria_rifiuta_prima_di_leggere():
    def forbidden(*args):
        raise AssertionError("lettura non prevista")

    with pytest.raises(ValueError, match="memoria"):
        streamed_spectrum((17000, 5000), forbidden, ranks=(256,), max_working_mib=16)


def test_dimensione_errata_del_blocco_non_e_accettata():
    with pytest.raises(ValueError, match="Blocco"):
        streamed_spectrum((16, 16), lambda a, b: np.ones((2, 2)), ranks=(2,))


@pytest.mark.parametrize("transpose", [False, True])
def test_gram_completo_coincide_con_la_svd_diretta(transpose):
    matrix = np.random.default_rng(42).normal(size=(16, 8)).astype(np.float32)
    matrix = matrix.T.copy() if transpose else matrix
    moment = np.linspace(0.1, 2, matrix.shape[1])
    result = full_gram_spectrum(matrix.shape, lambda a, b: matrix[a:b],
                                ranks=(1, 4, 8), second_moment=moment)
    for key, value in [("unweighted", matrix), ("diagonal_weighted", matrix*np.sqrt(moment))]:
        expected = np.linalg.svd(value.astype(np.float64), compute_uv=False)
        actual = result["modes"][key]
        np.testing.assert_allclose(actual["projected_singular_values"], expected, rtol=1e-5)
        assert actual["numerically_reliable"]
        assert actual["curves"][-1]["retained_energy"] == pytest.approx(1, abs=1e-6)


def test_mappa_gguf_non_modifica_i_pesi_e_segnala_tensori_mancanti(tmp_path):
    import hashlib
    gguf = pytest.importorskip("gguf")
    from core.engine.weight_spectrum import map_gguf_spectra

    name = "blk.0.ffn_up.weight"
    matrix = np.random.default_rng(42).normal(size=(16, 8)).astype(np.float32)

    def write(path, tensors):
        writer = gguf.GGUFWriter(str(path), "llama")
        for key, array in tensors.items():
            writer.add_tensor(key, np.asarray(array, dtype=np.float32))
        writer.write_header_to_file()
        writer.write_kv_data_to_file()
        writer.write_tensors_to_file()
        writer.close()

    weights, stats = tmp_path / "weights.gguf", tmp_path / "stats.gguf"
    write(weights, {name: matrix})
    write(stats, {name + ".in_sum2": np.ones(8)*8, name + ".counts": [8]})
    before = hashlib.sha256(weights.read_bytes()).digest()
    result = map_gguf_spectra(weights, stats, [name], ranks=(1, 4, 8), method="gram")
    assert result["complete"] and len(result["entries"]) == 1
    assert result["entries"][0]["modes"]["unweighted"]["energy"] == pytest.approx(float(np.sum(matrix.astype(np.float64)**2)))
    assert hashlib.sha256(weights.read_bytes()).digest() == before
    missing = map_gguf_spectra(weights, stats, ["absent"], ranks=(1,))
    assert not missing["complete"] and missing["skipped"][0]["name"] == "absent"
