"""La compensazione deve generalizzare a stati esclusi dal sistema lineare."""

import pytest

np = pytest.importorskip('numpy')

from core.modules.sigma_training_lab.channel_reconstruction import fit_reconstruction


def samples():
    rng = np.random.default_rng(7)
    cases = []
    for _ in range(4):
        x = rng.normal(size=(32, 2))
        y = x @ np.array([[2., -1.], [.5, 3.]])
        values = np.concatenate([x, y], axis=1).astype(np.float32)
        cases.append({'tensors': {'blk.0.ffn_down.weight': {
            'width': 128, 'tokens': 32, 'channels': np.arange(4), 'features': values}}})
    return cases, np.array([[2, 3]]), np.array([[0, 1]]), np.ones((1, 128))


def test_ricostruisce_correlazioni_e_non_usa_validazione_per_il_sistema_lineare():
    cases, removed, anchors, energy = samples()
    first = fit_reconstruction(cases, removed, anchors, energy, validation_indices=[3], ridge_values=(1e-5,))
    assert first['metrics'][0]['validation_diagonal_error_ratio'] < 1e-8
    np.testing.assert_allclose(first['coefficients'][0], [[2., .5], [-1., 3.]], atol=1e-4)
    cases[3]['tensors']['blk.0.ffn_down.weight']['features'] *= 7
    second = fit_reconstruction(cases, removed, anchors, energy, validation_indices=[3], ridge_values=(1e-5,))
    np.testing.assert_array_equal(first['coefficients'], second['coefficients'])


def test_rifiuta_sovrapposizioni_catture_incoerenti_e_validazione_totale():
    cases, removed, anchors, energy = samples()
    with pytest.raises(ValueError, match='rimossi'):
        fit_reconstruction(cases, removed, removed, energy, validation_indices=[3])
    with pytest.raises(ValueError, match='separata'):
        fit_reconstruction(cases, removed, anchors, energy, validation_indices=[0, 1, 2, 3])
    cases[0]['tensors']['blk.0.ffn_down.weight']['features'][0, 0] = np.nan
    with pytest.raises(ValueError, match='Campioni'):
        fit_reconstruction(cases, removed, anchors, energy, validation_indices=[3])
