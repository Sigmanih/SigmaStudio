"""Il conteggio reale deve distinguere compressione numerica e rimozione di pesi."""

import math
import struct

from core.engine.model_inspector import ModelFacts, ModelInspector


def write_gguf(path, tensors, tensor_type=0):
    entries = []
    offset = 0
    for name, shape in tensors:
        encoded = name.encode()
        entries.append(struct.pack("<Q", len(encoded)) + encoded
                       + struct.pack("<I", len(shape))
                       + struct.pack(f"<{len(shape)}Q", *shape)
                       + struct.pack("<IQ", tensor_type, offset))
        count = math.prod(shape)
        size = count * 4 if tensor_type == 0 else count // 32 * 18
        offset += (size + 31) // 32 * 32
    header = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), 0) + b"".join(entries)
    path.write_bytes(header + bytes((-len(header)) % 32) + bytes(offset))


def test_quantization_changes_bytes_but_not_parameter_count(tmp_path):
    tensors = [("token_embd.weight", (32, 8)), ("output.weight", (32, 4))]
    full = tmp_path / "full.gguf"
    quantized = tmp_path / "quantized.gguf"
    write_gguf(full, tensors)
    write_gguf(quantized, tensors, tensor_type=2)
    counts = []
    for path in (full, quantized):
        facts = ModelFacts(path=str(path), name=path.name)
        ModelInspector._read_gguf_tensor_sizes(facts, [str(path)])
        counts.append(facts.param_count)
    assert counts == [384, 384]
    assert quantized.stat().st_size < full.stat().st_size


def test_removed_tensor_reduces_count_and_shards_are_summed(tmp_path):
    trunk, mtp = tmp_path / "trunk.gguf", tmp_path / "mtp.gguf"
    write_gguf(trunk, [("blk.0.ffn.weight", (32, 8))])
    write_gguf(mtp, [("blk.1.nextn.weight", (32, 4))])
    facts = ModelFacts(path=str(tmp_path), name="with-mtp")
    ModelInspector._read_gguf_tensor_sizes(facts, [str(trunk), str(mtp)])
    assert facts.param_count == 384
    facts = ModelFacts(path=str(tmp_path), name="without-mtp")
    ModelInspector._read_gguf_tensor_sizes(facts, [str(trunk)])
    assert facts.param_count == 256


def test_bad_shard_does_not_produce_a_partial_count(tmp_path):
    valid, invalid = tmp_path / "valid.gguf", tmp_path / "invalid.gguf"
    write_gguf(valid, [("weight", (32, 8))])
    invalid.write_bytes(b"invalid")
    facts = ModelFacts(path=str(tmp_path), name="incomplete")
    ModelInspector._read_gguf_tensor_sizes(facts, [str(valid), str(invalid)])
    assert facts.param_count == 0
