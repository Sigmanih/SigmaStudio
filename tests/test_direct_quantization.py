"""La prova diretta deve mantenere fisse le altre variabili della quantizzazione."""

import pytest

np = pytest.importorskip('numpy')
gguf = pytest.importorskip('gguf')

from core.modules.sigma_training_lab.direct_quantization import conversion_plan, write_tensor_types, validate_candidate


def write(path, *, columns=128, token='b', norm=1., template='baseline', nextn=None):
    writer = gguf.GGUFWriter(str(path), 'llama')
    writer.add_name('sigma')
    writer.add_basename('sigma')
    writer.add_block_count(1)
    writer.add_embedding_length(128)
    if nextn is not None:
        writer.add_uint32('llama.nextn_predict_layers', nextn)
    writer.add_tokenizer_model('gpt2')
    writer.add_token_list(['a', token])
    writer.add_chat_template(template)
    writer.add_tensor('blk.0.ffn_up.weight', np.ones((256, columns), dtype=np.float32))
    writer.add_tensor('output_norm.weight', np.full(128, norm, dtype=np.float32))
    writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()


def test_preserva_template_e_tipi_senza_sovrascrivere_il_piano(tmp_path):
    reference, floating = tmp_path/'reference.gguf', tmp_path/'float.gguf'
    write(reference); write(floating, template='different')
    plan = conversion_plan(reference, floating)
    assert plan['tensors'] == 2 and plan['f32_tensors_checked'] == 2
    assert 'tokenizer.chat_template=str:baseline' in plan['metadata_overrides']
    path = tmp_path/'types.txt'; write_tensor_types(path, plan)
    assert '^blk\\.0\\.ffn_up\\.weight$=f32' in path.read_text()
    with pytest.raises(FileExistsError): write_tensor_types(path, plan)
    with pytest.raises(ValueError, match='Metadati'): validate_candidate(reference, floating)
    candidate = tmp_path/'candidate.gguf'; write(candidate)
    assert validate_candidate(reference, candidate)['public_name'] == 'sigma'


@pytest.mark.parametrize('change,match', [({'columns':64}, 'Forma'), ({'token':'c'}, 'tokenizer'), ({'norm':2.}, 'F32')])
def test_rifiuta_confronti_che_cambiano_altre_variabili(tmp_path, change, match):
    reference, floating = tmp_path/'reference.gguf', tmp_path/'float.gguf'
    write(reference); write(floating, **change)
    with pytest.raises(ValueError, match=match): conversion_plan(reference, floating)


def test_normalizza_solo_assenza_di_mtp_disabilitato(tmp_path):
    reference, floating = tmp_path/'reference.gguf', tmp_path/'float.gguf'
    write(reference, nextn=0); write(floating)
    plan = conversion_plan(reference, floating)
    assert plan['normalized_metadata_keys'] == ['llama.nextn_predict_layers']
    assert 'llama.nextn_predict_layers=int:0' in plan['metadata_overrides']
    different = tmp_path/'mtp.gguf'; write(different, nextn=1)
    with pytest.raises(ValueError, match='nextn_predict_layers'):
        conversion_plan(reference, different)
