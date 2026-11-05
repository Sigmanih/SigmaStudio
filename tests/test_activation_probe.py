"""Il protocollo rifiuta catture incomplete e non confonde campioni e canali."""

import struct

import pytest

np = pytest.importorskip("numpy")

from core.engine.activation_probe import (
    decode_gguf_tokens, fit_output_basis, read_capture, read_generation, read_token_scores,
    summarize_capture, summarize_token_scores,
    write_channel_mask, write_channel_plan, write_channel_reconstruction,
    write_lowrank_map, write_projection_basis, write_replay,
)


def test_maschera_canali_valida_prima_di_scrivere_e_supporta_identita(tmp_path):
    path = tmp_path / 'channels.bin'
    for rows in [[[3, 3]], [[4, 2]], [[128]], [[1], []]]:
        with pytest.raises(ValueError):
            write_channel_mask(path, rows, width=128)
        assert not path.exists()
    write_channel_mask(path, [[], []], width=128)
    assert path.read_bytes() == b'SGCM0001'+struct.pack('<III', 2, 128, 0)
    with pytest.raises(FileExistsError):
        write_channel_mask(path, [[], []], width=128)


def test_piano_ingressi_rifiuta_canali_duplicati_e_campioni_vuoti(tmp_path):
    path = tmp_path / 'plan.bin'
    for rows in [[[]], [[1, 1]], [[3, 2]]]:
        with pytest.raises(ValueError):
            write_channel_plan(path, rows, width=128)
        assert not path.exists()
    write_channel_plan(path, [[1, 4]], width=128)
    assert path.read_bytes() == b'SGCP0001'+struct.pack('<IIIII', 1, 128, 2, 1, 4)


def test_cattura_ingressi_supporta_canali_selezionati(tmp_path):
    path = tmp_path / 'input.bin'
    channels = np.array([1, 4], dtype='<u4')
    values = np.array([[1., 2.], [3., 4.]], dtype='<f4')
    sums, sums2 = np.zeros(128, dtype='<f8'), np.zeros(128, dtype='<f8')
    sums[channels] = values.sum(axis=0)
    sums2[channels] = (values**2).sum(axis=0)
    name = b'blk.0.ffn_down.weight'
    path.write_bytes(b'SGAO0005'+struct.pack('<IIIII', 1, 1, 2, 1, len(name))+name
                     +struct.pack('<III', 128, 2, 2)+channels.tobytes()+sums.tobytes()
                     +sums2.tobytes()+values.tobytes())
    item = read_capture(path)[0]['tensors'][name.decode()]
    np.testing.assert_array_equal(item['features'], values)


def test_mappa_compensazione_valida_indici_e_non_richiede_canali_rimossi(tmp_path):
    path = tmp_path / 'reconstruction.bin'
    with pytest.raises(ValueError, match='sovrapposti'):
        write_channel_reconstruction(path, [[1]], [[1]], [[[1.]]], width=128)
    assert not path.exists()
    write_channel_reconstruction(path, [[1]], [[4]], [[[2.]]], width=128)
    assert path.read_bytes() == (b'SGCR0001'+struct.pack('<IIII', 1, 128, 1, 1)
                                 +struct.pack('<IIf', 1, 4, 2.))


def test_compensazione_si_puo_assorbire_nei_pesi_conservati():
    rng = np.random.default_rng(19)
    weights = rng.normal(size=(32, 128))
    x = rng.normal(size=(128, 5))
    removed, anchors = np.array([0, 7]), np.array([1, 4, 6])
    coefficients = rng.normal(size=(2, 3))
    recovered = x.copy()
    recovered[removed] = coefficients @ x[anchors]
    keep = np.setdiff1d(np.arange(128), removed)
    folded = weights[:, keep].copy()
    folded[:, np.searchsorted(keep, anchors)] += weights[:, removed] @ coefficients
    np.testing.assert_allclose(weights @ recovered, folded @ x[keep], atol=1e-12, rtol=1e-12)


def test_annullare_up_equivale_a_rimuovere_gate_up_e_colonne_down():
    rng = np.random.default_rng(123)
    gate, up, down = rng.normal(size=(256, 128)), rng.normal(size=(256, 128)), rng.normal(size=(128, 256))
    x = rng.normal(scale=.1, size=(128, 3))
    removed = np.array([0, 7, 60, 255])
    kept = np.setdiff1d(np.arange(256), removed)
    g = gate @ x
    u = up @ x
    u[removed] = 0
    masked = down @ ((g/(1+np.exp(-g)))*u)
    g_small = gate[kept] @ x
    reduced = down[:, kept] @ ((g_small/(1+np.exp(-g_small)))*(up[kept] @ x))
    np.testing.assert_allclose(masked, reduced, rtol=1e-12, atol=1e-12)


def test_generazione_multilayer_accetta_callback_limitate_e_rifiuta_contatori_eccessivi(tmp_path):
    path = tmp_path / 'generation.bin'
    header = b'SGAG0001'+struct.pack('<I', 1)
    path.write_bytes(header+struct.pack('<IIId', 1, 1, 64*512, 1.0)+struct.pack('<i', 7))
    assert read_generation(path)[0]['intervention_calls'] == 64*512
    path.write_bytes(header+struct.pack('<IIId', 1, 1, 2**18+1, 1.0)+struct.pack('<i', 7))
    with pytest.raises(ValueError, match='non valide'):
        read_generation(path)


def capture_bytes(features, full_output=False):
    features = np.asarray(features, dtype="<f4")
    tokens, width = features.shape
    name = b"blk.0.ffn_gate.weight"
    sampled = width if full_output else 128
    return b"".join([
        b"SGAO0002" if full_output else b"SGAO0001", struct.pack("<I", 1), struct.pack("<III", tokens, tokens, 1),
        struct.pack("<I", len(name)), name, struct.pack("<III", width, tokens, sampled),
        np.arange(sampled, dtype="<u4").tobytes(),
        features.sum(axis=0, dtype=np.float64).astype("<f8").tobytes(),
        np.square(features.astype(np.float64)).sum(axis=0).astype("<f8").tobytes(),
        features.tobytes(),
    ])


def test_replay_valida_prima_di_scrivere_e_non_sovrascrive(tmp_path):
    path = tmp_path / "replay.bin"
    with pytest.raises(ValueError, match="budget"):
        write_replay(path, [{"prefix_tokens": [1], "answer_tokens": [2]*513}])
    assert not path.exists()
    case = {"prefix_tokens": [1, 2], "answer_tokens": [3, 4]}
    write_replay(path, [case])
    assert path.read_bytes() == b"SGAP0001" + struct.pack("<III4i", 1, 2, 2, 1, 2, 3, 4)
    with pytest.raises(FileExistsError):
        write_replay(path, [case])


def test_cattura_controlla_somme_e_ricostruisce_campioni(tmp_path):
    features = np.random.default_rng(42).normal(size=(16, 128)).astype(np.float32)
    path = tmp_path / "capture.bin"
    path.write_bytes(capture_bytes(features))
    cases = read_capture(path)
    item = cases[0]["tensors"]["blk.0.ffn_gate.weight"]
    np.testing.assert_array_equal(item["features"], features)
    assert cases[0]["greedy_matches"] == 16
    corrupted = bytearray(path.read_bytes())
    corrupted[-4:] = struct.pack("<f", 100)
    path.write_bytes(corrupted)
    with pytest.raises(ValueError, match="coerenti"):
        read_capture(path)


@pytest.mark.parametrize("suffix", [b"", b"extra"])
def test_cattura_rifiuta_troncamenti_o_appendici(tmp_path, suffix):
    data = capture_bytes(np.ones((4, 128)))
    path = tmp_path / "capture.bin"
    path.write_bytes(data[:-1] if not suffix else data+suffix)
    with pytest.raises(ValueError, match="troncata|eccesso"):
        read_capture(path)


def test_covarianza_riconosce_un_sottospazio_unidimensionale(tmp_path):
    direction = np.arange(1, 129, dtype=np.float32)
    features = np.arange(16, dtype=np.float32)[:, None]*direction
    path = tmp_path / "capture.bin"
    path.write_bytes(capture_bytes(features))
    case = read_capture(path)[0]
    result = summarize_capture([case, case], [True, False])
    groups = result["tensors"][0]["groups"]
    assert groups["passed"]["sample_rank95_median"] == 1
    assert groups["failed"]["sample_participation_rank_median"] == pytest.approx(1)
    with pytest.raises(ValueError, match="riusciti e falliti"):
        summarize_capture([case], [True])


def test_base_su_uscita_completa_preserva_sottospazio_noto(tmp_path):
    rng = np.random.default_rng(42)
    features = rng.normal(size=(20, 2)) @ rng.normal(size=(2, 256))
    path = tmp_path / "capture.bin"
    path.write_bytes(capture_bytes(features, full_output=True))
    cases = read_capture(path)
    basis, stats = fit_output_basis(cases, "blk.0.ffn_gate.weight", 2)
    assert basis.shape == (2, 256)
    assert stats["training_retained_energy"] == pytest.approx(1, abs=1e-6)
    np.testing.assert_allclose(features @ basis.T @ basis, features, atol=2e-6)
    write_projection_basis(tmp_path / "basis.bin", basis)
    with pytest.raises(ValueError, match="ortonormale"):
        write_projection_basis(tmp_path / "bad.bin", basis*2)
    cases[0]["tensors"]["blk.0.ffn_gate.weight"]["channels"] = np.arange(128)
    with pytest.raises(ValueError, match="complete"):
        fit_output_basis(cases, "blk.0.ffn_gate.weight", 2)


def test_proiezione_uscita_equivale_alla_fattorizzazione_del_peso():
    rng = np.random.default_rng(42)
    weight, x = rng.normal(size=(24, 16)), rng.normal(size=(16, 8))
    u, _ = np.linalg.qr(rng.normal(size=(24, 4)))
    projected = u @ (u.T @ (weight @ x))
    factored = u @ (u.T @ weight) @ x
    np.testing.assert_allclose(projected, factored, atol=1e-12)


def test_generazione_libera_non_accetta_controllo_non_eseguito(tmp_path):
    path = tmp_path / "generation.bin"
    header = b"SGAG0001" + struct.pack("<I", 1)
    path.write_bytes(header + struct.pack("<IIId2i", 2, 1, 3, .5, 10, 20))
    item = read_generation(path)[0]
    assert item["tokens"] == [10, 20] and item["ended"]
    path.write_bytes(header + struct.pack("<IIId2i", 2, 1, 0, .5, 10, 20))
    with pytest.raises(ValueError, match="non valide"):
        read_generation(path)


def test_decoder_byte_bpe_ricompone_spazi_e_utf8_spezzato(tmp_path):
    import hashlib
    gguf = pytest.importorskip("gguf")
    path = tmp_path / "vocab.gguf"
    writer = gguf.GGUFWriter(str(path), "llama")
    writer.add_tokenizer_model("gpt2")
    writer.add_token_list(["hello", "Ġ", "world", "Ċ", "Ã", "©"])
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    before = hashlib.sha256(path.read_bytes()).digest()
    assert decode_gguf_tokens(path, [[0, 1, 2, 3, 4, 5]]) == ["hello world\né"]
    assert hashlib.sha256(path.read_bytes()).digest() == before
    with pytest.raises(ValueError, match="vocabolario"):
        decode_gguf_tokens(path, [[6]])


@pytest.mark.parametrize("protect_first", [False, True])
def test_vincolo_preserva_stati_rari_a_bassa_energia(tmp_path, protect_first):
    cases = []
    for index in range(2):
        features = np.zeros((20, 256), dtype=np.float32)
        features[:, 0] = 10
        boundary = 0 if protect_first else -1
        features[boundary] = 0
        features[boundary, 254+index] = .001
        path = tmp_path / f"capture{index}.bin"
        path.write_bytes(capture_bytes(features, full_output=True))
        cases.extend(read_capture(path))
    name = "blk.0.ffn_gate.weight"
    ordinary, _ = fit_output_basis(cases, name, 1)
    protected, stats = fit_output_basis(cases, name, 2, protect_last=not protect_first, protect_first=protect_first)
    last = np.stack([x["tensors"][name]["features"][boundary] for x in cases])
    np.testing.assert_allclose(last @ protected.T @ protected, last, atol=1e-9)
    assert np.linalg.norm(last @ ordinary.T @ ordinary-last) > .001
    assert stats["protected_state_rank"] == 2
    with pytest.raises(ValueError, match="stati protetti"):
        fit_output_basis(cases, name, 1, protect_last=not protect_first, protect_first=protect_first)


def test_probabilita_richiedono_decisione_di_arresto_e_valori_finiti(tmp_path):
    path = tmp_path / "scores.bin"
    header = b"SGAS0001" + struct.pack("<II", 1, 2)
    normal = struct.pack("<iiiI8d", 5, 5, 5, 0, .1, .2, .3, .4, .1, .2, -2, -1)
    terminal = struct.pack("<iiiI8d", 9, 9, 7, 1, .2, .3, .4, .5, .8, .2, 2, -1)
    trailer = struct.pack("<IId", 2, 2, .5)
    path.write_bytes(header+normal+terminal+trailer)
    rows = read_token_scores(path)[0]["rows"]
    assert len(rows) == 2 and rows["candidate_top"][-1] == 7
    assert rows["kl"][0] == pytest.approx(.1)
    short = rows[-1:].copy()
    short["kl"] = .1
    long = np.repeat(rows[-1:], 3)
    long["terminal"][:-1] = 0
    summary = summarize_token_scores([{"rows": short}, {"rows": long}])
    assert summary["equal_case_mean_kl"] == pytest.approx(.15)
    assert summary["terminal_stop_lost_count"] == 2
    path.write_bytes(header+normal+normal+trailer)
    with pytest.raises(ValueError, match="non valide"):
        read_token_scores(path)
    invalid = struct.pack("<iiiI8d", 9, 9, 7, 1, float("nan"), .3, .4, .5, .8, .2, 2, -1)
    path.write_bytes(header+normal+invalid+trailer)
    with pytest.raises(ValueError, match="non valide"):
        read_token_scores(path)


def test_cattura_decisioni_top_due_con_margini(tmp_path):
    path = tmp_path / "capture.bin"
    base = capture_bytes(np.ones((2, 128)), full_output=True)
    choices = np.array([5, 6, 7, 8], dtype="<i4").tobytes()
    gaps = np.array([.1, .2], dtype="<f4").tobytes()
    path.write_bytes(b"SGAO0003"+base[8:]+choices+gaps)
    case = read_capture(path)[0]
    assert case["decisions"]["first"].tolist() == [5, 6]
    np.testing.assert_allclose(case["decisions"]["margins"], [.1, .2])
    invalid = np.array([5, 6, 5, 8], dtype="<i4").tobytes()
    path.write_bytes(b"SGAO0003"+base[8:]+invalid+gaps)
    with pytest.raises(ValueError, match="Decisioni"):
        read_capture(path)


def test_stato_pre_norm_e_probabilita_native(tmp_path):
    path = tmp_path / "capture.bin"
    base = capture_bytes(np.ones((2, 128)), full_output=True)
    decisions = np.array([5, 6, 7, 8], dtype="<i4").tobytes()+np.array([.1, .2], dtype="<f4").tobytes()
    hidden = np.full((2, 128), 2, dtype="<f4")
    probabilities = np.array([.7, .8, .2, .1], dtype="<f4").tobytes()
    path.write_bytes(b"SGAO0004"+base[8:]+decisions+hidden.tobytes()+probabilities)
    case = read_capture(path)[0]
    np.testing.assert_array_equal(case["hidden"], hidden)
    np.testing.assert_allclose(case["native_top_probabilities"], [[.7, .2], [.8, .1]])
    hidden[0, 0] = float("nan")
    path.write_bytes(b"SGAO0004"+base[8:]+decisions+hidden.tobytes()+probabilities)
    with pytest.raises(ValueError, match="non validi"):
        read_capture(path)


def test_fattori_indipendenti_non_richiedono_simmetria(tmp_path):
    encoder = np.eye(128, dtype=np.float32)[:2]
    decoder = encoder*2
    path = tmp_path / "factors.bin"
    write_lowrank_map(path, encoder, decoder)
    assert path.read_bytes()[:16] == b"SGAF0001"+struct.pack("<II", 128, 2)
    recovered = np.frombuffer(path.read_bytes()[16:], dtype="<f4").reshape(2, 2, 128)
    np.testing.assert_array_equal(recovered[0], encoder)
    np.testing.assert_array_equal(recovered[1], decoder)
