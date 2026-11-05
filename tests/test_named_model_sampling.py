"""Rinominare un checkpoint locale non deve cambiare il campionamento."""

from types import SimpleNamespace
from unittest.mock import Mock

from core.engine.sampling import SamplingParams


def test_sigma_conserva_il_profilo_qwen_dichiarato_nel_checkpoint(monkeypatch, tmp_path):
    import core.model_paths as model_paths
    from core.engine.model_inspector import ModelInspector

    monkeypatch.setattr(model_paths, "resolve_model_dir", lambda name: str(tmp_path / "sigma"))
    inspect = Mock(return_value=SimpleNamespace(model_type="qwen35"))
    monkeypatch.setattr(ModelInspector, "inspect", inspect)
    actual = SamplingParams.resolve("sigma:sigma")
    expected = SamplingParams.resolve("Qwen3.8-27B")
    assert actual.to_dict() == expected.to_dict()


def test_una_corrispondenza_approssimativa_non_sceglie_un_altro_modello(monkeypatch, tmp_path):
    import core.model_paths as model_paths
    from core.engine.model_inspector import ModelInspector

    monkeypatch.setattr(model_paths, "resolve_model_dir", lambda name: str(tmp_path / "altro"))
    inspect = Mock()
    monkeypatch.setattr(ModelInspector, "inspect", inspect)
    assert SamplingParams.resolve("sigma:inesistente").source == "family:generic"
    inspect.assert_not_called()


def test_un_modello_cloud_non_ispeziona_i_file_locali(monkeypatch):
    import core.model_paths as model_paths

    resolve = Mock(side_effect=AssertionError("accesso locale inatteso"))
    monkeypatch.setattr(model_paths, "resolve_model_dir", resolve)
    SamplingParams.resolve("provider/modello-cloud")
    resolve.assert_not_called()
