"""L'identita' dipende dai pesi effettivi, non dal nome sigma."""

from types import SimpleNamespace

import pytest

from core.engine import checkpoint_identity as identity


def test_stesso_nome_con_pesi_diversi_non_e_lo_stesso_checkpoint(tmp_path):
    file = tmp_path / 'sigma.gguf'
    file.write_bytes(b'first-weights')
    first = identity.fingerprint_file(file)
    file.write_bytes(b'other-weights')
    second = identity.fingerprint_file(file)
    assert first['sha256'] != second['sha256']
    assert first['verified'] is True and second['verified'] is True


def test_budget_dimensioni_e_tempo(tmp_path, monkeypatch):
    file = tmp_path / 'sigma.gguf'
    file.write_bytes(b'weights')
    with pytest.raises(ValueError, match='budget'):
        identity.fingerprint_file(file, max_bytes=1)
    ticks = iter([0, 2])
    monkeypatch.setattr(identity, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError):
        identity.fingerprint_file(file, seconds=1)


def test_modello_composto_non_viene_certificato_per_ipotesi(tmp_path, monkeypatch):
    from core import model_paths

    monkeypatch.setattr(model_paths, 'resolve_model_dir', lambda name: str(tmp_path))
    engine = SimpleNamespace(has_resident_model=True, loaded_model_name='sigma')
    (tmp_path/'sigma.gguf').write_bytes(b'weights')
    assert identity.current_checkpoint_identity(engine)['verified'] is True
    (tmp_path/'adapter.gguf').write_bytes(b'adapter')
    assert identity.current_checkpoint_identity(engine)['verified'] is False
