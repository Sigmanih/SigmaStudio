# ==============================================================================
# core/training/gguf_export.py — Conversione HuggingFace -> GGUF (architettura Llama)
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Esporta un modello Llama-like in GGUF senza dipendere da llama.cpp.

Il convertitore ufficiale (`convert_hf_to_gguf.py`) vive nel repository di
llama.cpp e va scaricato e mantenuto a parte. Qui si scrive direttamente il
file con il pacchetto `gguf`, che è già una dipendenza: nessun download,
funziona offline, e il comportamento è sotto il nostro controllo.

Il punto delicato è la **permutazione di Q e K**. HuggingFace memorizza le due
metà della rotazione RoPE affiancate, llama.cpp le vuole interlacciate: senza
questa trasformazione il modello si converte "con successo" e poi in inferenza
produce testo degenere — un errore che non dà alcun segnale finché non lo si
prova davvero.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

# Nome GGUF <- nome HuggingFace, per i tensori non ripetuti per layer
_TOP_LEVEL = {
    "token_embd.weight": "model.embed_tokens.weight",
    "output_norm.weight": "model.norm.weight",
    "output.weight": "lm_head.weight",
}

# Suffisso GGUF <- suffisso HuggingFace, dentro ogni blocco
_PER_LAYER = {
    "attn_norm.weight": "input_layernorm.weight",
    "attn_q.weight": "self_attn.q_proj.weight",
    "attn_k.weight": "self_attn.k_proj.weight",
    "attn_v.weight": "self_attn.v_proj.weight",
    "attn_output.weight": "self_attn.o_proj.weight",
    "ffn_norm.weight": "post_attention_layernorm.weight",
    "ffn_gate.weight": "mlp.gate_proj.weight",
    "ffn_up.weight": "mlp.up_proj.weight",
    "ffn_down.weight": "mlp.down_proj.weight",
}

# Tipi che il pacchetto `gguf` sa davvero *scrivere*. Q4_K/Q6_K esistono nel
# formato ma in Python sono di sola lettura: offrirli produrrebbe file F32
# etichettati come quantizzati, cioè più grandi dell'F16 invece che più piccoli.
QUANT_TYPES = {"f32": "F32", "f16": "F16", "q8_0": "Q8_0",
               "q4_0": "Q4_0", "q4_1": "Q4_1", "q5_0": "Q5_0"}

# Dimensione del blocco di quantizzazione: una matrice va quantizzata solo se
# l'ultima dimensione è un multiplo esatto.
_QUANT_BLOCK = 32


def permute_rope(weight, n_head: int, n_head_kv: int | None = None):
    """Riordina Q/K dal layout HuggingFace a quello atteso da llama.cpp.

    HF applica RoPE su due metà contigue del vettore testa; llama.cpp la applica
    a coppie interlacciate. Le matrici vanno quindi rimescolate una volta sola,
    in fase di conversione.
    """
    if n_head_kv is not None and n_head != n_head_kv:
        n_head = n_head_kv
    shape = weight.shape
    if shape[0] % (n_head * 2):
        raise ValueError(
            f"Forma {shape} incompatibile con {n_head} teste: le righe devono essere "
            f"un multiplo di {n_head * 2} (una coppia RoPE per testa)")
    return (weight.reshape(n_head, 2, shape[0] // n_head // 2, *shape[1:])
            .swapaxes(1, 2)
            .reshape(shape))


def _bpe_merges(model_dir: Path) -> list[str]:
    """Regole di merge del BPE, nel formato "a b" atteso da llama.cpp.

    Senza di queste llama.cpp rifiuta il file ("cannot find tokenizer merges"):
    il vocabolario da solo non basta a ricostruire la tokenizzazione.
    """
    tokenizer_file = model_dir / "tokenizer.json"
    if not tokenizer_file.exists():
        return []
    try:
        data = json.loads(tokenizer_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    merges = []
    for entry in (data.get("model") or {}).get("merges", []) or []:
        if isinstance(entry, str):
            merges.append(entry)
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            merges.append(f"{entry[0]} {entry[1]}")   # formato tokenizers >= 0.20
    return merges


def _load_tokenizer_vocab(model_dir: Path, config: dict):
    """Vocabolario, punteggi e tipi di token nel formato che GGUF si aspetta."""
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=False)
    vocab_size = int(config.get("vocab_size") or tok.vocab_size)

    lookup = tok.get_vocab()
    by_id = {index: token for token, index in lookup.items()}

    tokens, scores, types = [], [], []
    special = set(tok.all_special_ids or [])
    for index in range(vocab_size):
        token = by_id.get(index)
        if token is None:                       # buchi di padding nel vocabolario
            tokens.append(f"[PAD{index}]")
            scores.append(-1000.0)
            types.append(3)                     # USER_DEFINED
            continue
        tokens.append(token)
        scores.append(0.0)
        types.append(4 if index in special else 1)   # CONTROL : NORMAL
    return tok, tokens, scores, types


def export_gguf(model_dir, out_path, quantization: str = "f16",
                logger=None) -> dict:
    """Scrive `out_path` in GGUF a partire da un modello HF Llama-like."""
    import numpy as np
    import gguf
    from safetensors.torch import load_file

    def emit(message, *args):
        if logger:
            logger.info(message, *args)
        else:
            print("[GGUF] " + (message % args if args else message), flush=True)

    model_dir, out_path = Path(model_dir), Path(out_path)
    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))

    architecture = (config.get("architectures") or ["LlamaForCausalLM"])[0]
    if "Llama" not in architecture and "Mistral" not in architecture:
        return {"success": False,
                "error": (f"Architettura '{architecture}' non supportata da questo "
                          "convertitore: gestisce modelli Llama-like (quelli forgiati "
                          "da Sigma lo sono).")}

    n_layer = int(config["num_hidden_layers"])
    n_head = int(config["num_attention_heads"])
    n_head_kv = int(config.get("num_key_value_heads") or n_head)
    n_embd = int(config["hidden_size"])

    # pesi: safetensors singolo o shardato
    state: dict = {}
    index_file = model_dir / "model.safetensors.index.json"
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding="utf-8"))
        for shard in sorted(set(index["weight_map"].values())):
            state.update(load_file(str(model_dir / shard)))
    else:
        state.update(load_file(str(model_dir / "model.safetensors")))

    tok, tokens, scores, types = _load_tokenizer_vocab(model_dir, config)
    emit("Vocabolario: %d token | %d layer | hidden %d | teste %d (kv %d)",
         len(tokens), n_layer, n_embd, n_head, n_head_kv)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = gguf.GGUFWriter(str(out_path), "llama")

    writer.add_name(out_path.stem)
    writer.add_context_length(int(config.get("max_position_embeddings", 2048)))
    writer.add_embedding_length(n_embd)
    writer.add_block_count(n_layer)
    writer.add_feed_forward_length(int(config["intermediate_size"]))
    writer.add_rope_dimension_count(n_embd // n_head)
    writer.add_head_count(n_head)
    writer.add_head_count_kv(n_head_kv)
    writer.add_layer_norm_rms_eps(float(config.get("rms_norm_eps", 1e-5)))
    writer.add_rope_freq_base(float(config.get("rope_theta", 10000.0)))
    writer.add_file_type(getattr(gguf.LlamaFileType,
                                 f"MOSTLY_{QUANT_TYPES.get(quantization, 'F16')}",
                                 gguf.LlamaFileType.MOSTLY_F16))
    if quantization not in QUANT_TYPES:
        emit("Quantizzazione '%s' non scrivibile da Python: uso F16", quantization)

    is_bpe = _is_bpe(model_dir)
    writer.add_tokenizer_model("gpt2" if is_bpe else "llama")
    writer.add_tokenizer_pre("default")
    writer.add_token_list(tokens)
    writer.add_token_scores(scores)
    writer.add_token_types(types)
    if is_bpe:
        merges = _bpe_merges(model_dir)
        if not merges:
            writer.close()
            return {"success": False,
                    "error": ("Tokenizer BPE senza regole di merge in tokenizer.json: "
                              "llama.cpp non può ricostruire la tokenizzazione.")}
        writer.add_token_merges(merges)
        emit("Merge BPE incluse: %d regole", len(merges))
    for setter, value in (
        (writer.add_bos_token_id, tok.bos_token_id),
        (writer.add_eos_token_id, tok.eos_token_id),
        (writer.add_pad_token_id, tok.pad_token_id),
        (writer.add_unk_token_id, tok.unk_token_id),
    ):
        if value is not None:
            setter(int(value))
    if getattr(tok, "chat_template", None):
        writer.add_chat_template(tok.chat_template)

    def numpy_of(name: str):
        tensor = state[name]
        return tensor.to(dtype=__import__("torch").float32).numpy()

    quant_name = QUANT_TYPES.get(quantization, "F16")
    quant_type = getattr(gguf.GGMLQuantizationType, quant_name, None)
    quantized_count = 0

    def put(gguf_name: str, array):
        """Scrive un tensore, quantizzandolo quando ha senso.

        I tensori 1-D (le norm) restano in F32: pesano pochissimo e
        quantizzarli degrada il modello senza far risparmiare spazio.
        """
        nonlocal quantized_count
        if quantization == "f32":
            writer.add_tensor(gguf_name, array.astype(np.float32))
            return
        if quantization == "f16":
            writer.add_tensor(gguf_name, array.astype(np.float16) if array.ndim > 1 else array)
            return

        if array.ndim > 1 and array.shape[-1] % _QUANT_BLOCK == 0 and quant_type is not None:
            # `quantize` restituisce byte impacchettati: la forma va lasciata
            # dedurre al writer, che risale agli elementi dalla dimensione del
            # blocco. Passando raw_shape si sovrascriverebbe con la forma in
            # elementi e il conto non torna.
            data = gguf.quants.quantize(array.astype(np.float32), quant_type)
            writer.add_tensor(gguf_name, data, raw_dtype=quant_type)
            quantized_count += 1
        else:
            writer.add_tensor(gguf_name, array.astype(np.float16) if array.ndim > 1 else array)

    missing = []
    for gguf_name, hf_name in _TOP_LEVEL.items():
        if hf_name in state:
            put(gguf_name, numpy_of(hf_name))
        elif gguf_name == "output.weight" and config.get("tie_word_embeddings"):
            # pesi legati: llama.cpp riusa l'embedding, non serve duplicarlo
            emit("lm_head legato all'embedding: non duplicato nel GGUF")
        else:
            missing.append(hf_name)

    for layer in range(n_layer):
        for suffix, hf_suffix in _PER_LAYER.items():
            hf_name = f"model.layers.{layer}.{hf_suffix}"
            if hf_name not in state:
                missing.append(hf_name)
                continue
            array = numpy_of(hf_name)
            # la permutazione vale solo per Q e K: sono le uniche a cui si
            # applica RoPE, e sono l'unico punto in cui i due layout divergono
            if suffix == "attn_q.weight":
                array = permute_rope(array, n_head)
            elif suffix == "attn_k.weight":
                array = permute_rope(array, n_head, n_head_kv)
            put(f"blk.{layer}.{suffix}", array)

    if missing:
        writer.close()
        return {"success": False,
                "error": f"Tensori mancanti nel modello: {missing[:5]}"
                         f"{' e altri' if len(missing) > 5 else ''}"}

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()

    size_mb = round(out_path.stat().st_size / (1024 ** 2), 1)
    emit("GGUF scritto: %s (%.1f MB, %s%s)", out_path, size_mb, quant_name,
         f", {quantized_count} tensori quantizzati" if quantized_count else "")
    return {"success": True, "path": str(out_path), "size_mb": size_mb,
            "quantization": quant_name, "quantized_tensors": quantized_count,
            "tensors": len(_TOP_LEVEL) + n_layer * len(_PER_LAYER)}


def _is_bpe(model_dir: Path) -> bool:
    """Distingue i tokenizer BPE (tokenizer.json) da quelli SentencePiece."""
    return (model_dir / "tokenizer.json").exists() and not (model_dir / "tokenizer.model").exists()
