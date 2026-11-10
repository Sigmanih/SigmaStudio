"""Piccolo LLaMA numerico per verificare i collegamenti HTTP e C-ABI."""
import struct


def tiny_llama() -> bytes:
    tensors=[("token_embd.weight",[2,3],[1.,0.,0.,1.,1.,1.]),
        ("blk.0.attn_norm.weight",[2],[1.,1.]),
        *[(f"blk.0.{name}.weight",[2,2],[1.,0.,0.,1.]) for name in
          ("attn_q","attn_k","attn_v","attn_output")],
        ("blk.0.ffn_norm.weight",[2],[1.,1.]),
        *[(f"blk.0.{name}.weight",[2,2],[1.,0.,0.,1.]) for name in
          ("ffn_gate","ffn_up","ffn_down")],
        ("output_norm.weight",[2],[1.,1.]),
        ("output.weight",[2,3],[1.,0.,0.,1.,.5,.5])]
    out=bytearray(b"GGUF"+struct.pack("<IQQ",3,len(tensors),10))
    def string(value):
        raw=value.encode();out.extend(struct.pack("<Q",len(raw)));out.extend(raw)
    string("general.architecture");out.extend(struct.pack("<I",8));string("llama")
    for key,value in [("general.alignment",32),("llama.embedding_length",2),("llama.block_count",1),
        ("llama.attention.head_count",1),("llama.attention.head_count_kv",1),
        ("llama.feed_forward_length",2),("llama.context_length",8)]:
        string(key);out.extend(struct.pack("<II",4,value))
    for key,value in [("llama.attention.layer_norm_rms_epsilon",1e-5),("llama.rope.freq_base",10000.)]:
        string(key);out.extend(struct.pack("<If",6,value))
    offset=0;offsets=[]
    for name,shape,values in tensors:
        offset=(offset+31)&~31;offsets.append(offset)
        string(name);out.extend(struct.pack("<I",len(shape)))
        out.extend(struct.pack("<"+"Q"*len(shape),*shape));out.extend(struct.pack("<IQ",0,offset))
        offset+=len(values)*4
    while len(out)%32:out.append(0)
    start=len(out)
    for (_,_,values),offset in zip(tensors,offsets):
        out.extend(bytes(start+offset-len(out)));out.extend(struct.pack("<"+"f"*len(values),*values))
    return bytes(out)
