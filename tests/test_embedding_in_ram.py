"""L'embedding d'ingresso resta in RAM: non deve pesare sulla VRAM stimata, salvo se l'uscita lo riusa."""
import pytest

np = pytest.importorskip("numpy")
gguf = pytest.importorskip("gguf")

from core.engine.model_inspector import ModelInspector

pytestmark = pytest.mark.motore


def _modello(cartella, *, uscita_separata):
    cartella.mkdir()
    writer = gguf.GGUFWriter(str(cartella / "m.gguf"), "llama")
    writer.add_block_count(1)
    writer.add_embedding_length(64)
    writer.add_tensor("token_embd.weight", np.zeros((512, 64), dtype=np.float32))
    writer.add_tensor("blk.0.ffn_up.weight", np.zeros((128, 64), dtype=np.float32))
    if uscita_separata:
        writer.add_tensor("output.weight", np.zeros((512, 64), dtype=np.float32))
    writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()
    return ModelInspector.inspect(str(cartella))


def test_embedding_con_uscita_separata_resta_in_ram(tmp_path):
    facts = _modello(tmp_path / "separata", uscita_separata=True)
    assert facts.host_only_bytes >= 512 * 64 * 4


def test_embedding_condiviso_con_l_uscita_conta_come_vram(tmp_path):
    # Senza output.weight llama.cpp copia l'embedding sulla GPU per l'uscita.
    facts = _modello(tmp_path / "condivisa", uscita_separata=False)
    assert facts.host_only_bytes == 0
