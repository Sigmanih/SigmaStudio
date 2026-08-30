# ==============================================================================
# core/engine/model_inspector.py — Ground-truth model introspection
#
# Reads what a model ACTUALLY is from its own files (config.json +
# model.safetensors.index.json + safetensors headers) instead of guessing from
# the folder name. Everything downstream — layer partitioning, VRAM budgeting,
# device maps — depends on these numbers being real.
# ==============================================================================
import os
import json
import re
import struct
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

# Version of the cached .sigma_facts.json payload. Bump it whenever a field
# starts being populated that older caches do not carry: the fingerprint only
# notices a directory that changed, so a model inspected before the new field
# existed would keep reporting the old, incomplete answer forever. Raised to 4
# when the GGUF path began reading vocab_size, which the llama.cpp planner needs
# to size its prefill batch.
_FACTS_SCHEMA = 6

# Bytes per element, by safetensors dtype string.
_DTYPE_BYTES = {
    "F64": 8, "I64": 8,
    "F32": 4, "I32": 4,
    "F16": 2, "BF16": 2, "I16": 2,
    "F8_E4M3": 1, "F8_E5M2": 1, "I8": 1, "U8": 1, "BOOL": 1,
    "F4": 0.5, "I4": 0.5,
}

# Effective bytes/param for bitsandbytes NF4 with double quantization.
# 4 bits payload + ~0.127 bits of (double-quantized) absmax scales = 4.127 bits.
_NF4_BYTES_PER_PARAM = 4.127 / 8.0
_INT8_BYTES_PER_PARAM = 1.0 + (0.5 / 8.0)

# Tensors that bitsandbytes leaves in full compute dtype.
_NEVER_QUANTIZED_HINTS = ("embed_tokens", "lm_head", "wte", "shared", "embeddings")


@dataclass
class ModelFacts:
    """Ground truth about a local model directory."""
    path: str
    name: str
    model_type: str = "unknown"
    architectures: List[str] = field(default_factory=list)
    weight_format: str = "safetensors"          # safetensors | gguf | bin

    # Transformer geometry (from text_config when multimodal)
    num_hidden_layers: int = 0
    hidden_size: int = 0
    head_dim: int = 0
    num_attention_heads: int = 0
    num_key_value_heads: int = 0
    vocab_size: int = 0
    max_position_embeddings: int = 0
    tie_word_embeddings: bool = False
    layer_types: List[str] = field(default_factory=list)
    torch_dtype: str = "bfloat16"

    # Completeness and shard tracking
    is_complete: bool = True
    has_part_files: bool = False
    total_shards_declared: int = 1
    shards_present: int = 1
    missing_shards_count: int = 0

    # Structure flags
    is_moe: bool = False
    num_experts: int = 0
    experts_used: int = 0                        # experts routed per token
    is_multimodal: bool = False
    has_mtp: bool = False                        # native multi-token-prediction head

    # Discovered from the weight index — never hardcoded.
    layer_prefix: str = ""                       # e.g. "model.language_model.layers"
    auxiliary_prefixes: List[str] = field(default_factory=list)  # visual / mtp / etc.

    # Real measured sizes
    total_bytes: int = 0
    expert_bytes: int = 0                        # MoE expert tensors, measured
    host_only_bytes: int = 0                     # tensors llama.cpp keeps in RAM
    param_count: int = 0
    quantizable_params: int = 0
    resident_params: int = 0                     # params bnb keeps in compute dtype

    def summary(self) -> str:
        return (
            f"{self.name}: {self.param_count / 1e9:.2f}B params, "
            f"{self.total_bytes / 2**30:.1f}GB on disk, "
            f"{self.num_hidden_layers} layers, "
            f"prefix='{self.layer_prefix}'"
            + (", multimodal" if self.is_multimodal else "")
            + (", MoE" if self.is_moe else "")
            + (", MTP" if self.has_mtp else "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelInspector:
    """Extracts ground-truth facts from a local model directory."""

    @classmethod
    def inspect(cls, model_path: str, use_cache: bool = True) -> Optional[ModelFacts]:
        """
        Reads config + weight index + safetensors headers.
        Results are cached in the model dir so repeated loads are instant.
        """
        if not os.path.isdir(model_path):
            log.warning("[ModelInspector] Not a directory: %s", model_path)
            return None

        cache_file = os.path.join(model_path, ".sigma_facts.json")
        fingerprint = cls._directory_fingerprint(model_path)

        if use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                # The fingerprint guards against a directory that changed after
                # being inspected. A conversion creates its output folder before
                # the weights land in it, so an inspection during that window
                # cached "no weights here" and, with nothing to invalidate it,
                # kept reporting that long after the model was complete.
                if cached.get("_schema") == _FACTS_SCHEMA and cached.get("_fingerprint") == fingerprint:
                    cached.pop("_schema", None)
                    cached.pop("_fingerprint", None)
                    # Il percorso non si prende dalla cache. La cache vive
                    # *dentro* la cartella del modello e ne conserva la
                    # posizione assoluta, mentre l'impronta e' fatta di nome,
                    # dimensione e data del file: spostare la cartella non la
                    # cambia. Chi sposta i modelli su un altro disco dal Model
                    # Hub — cosa che l'applicazione offre — si ritroverebbe
                    # ogni modello che dichiara di stare dove non e' piu', e il
                    # caricamento fallirebbe con "nessun file .gguf trovato" su
                    # un file che esiste.
                    cached["path"] = model_path
                    return ModelFacts(**cached)
                log.debug("[ModelInspector] Cache stale for %s, re-inspecting", model_path)
            except Exception as exc:
                log.debug("[ModelInspector] Ignoring unreadable cache: %s", exc)

        facts = ModelFacts(path=model_path, name=os.path.basename(model_path.rstrip("\\/")))

        cls._read_config(facts)
        cls._read_weight_layout(facts)

        if facts.num_hidden_layers and not facts.layer_types:
            facts.layer_types = ["full_attention"] * facts.num_hidden_layers

        try:
            payload = facts.to_dict()
            payload["_schema"] = _FACTS_SCHEMA
            payload["_fingerprint"] = fingerprint
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            log.debug("[ModelInspector] Could not write facts cache: %s", exc)

        log.info("[ModelInspector] %s", facts.summary())
        return facts

    @staticmethod
    def _directory_fingerprint(model_path: str) -> str:
        """
        Cheap signature of a model directory's weight files.

        Names, sizes and modification times of the files that define the model.
        Reading them costs a stat per file, which is nothing next to re-parsing
        every safetensors header, but changes the moment the directory does.
        """
        try:
            entries = []
            for root, _dirs, files in os.walk(model_path):
                for name in sorted(files):
                    if name.startswith("."):
                        continue
                    if not name.endswith((".safetensors", ".gguf", ".bin", ".json")):
                        continue
                    full = os.path.join(root, name)
                    if not os.path.isfile(full):
                        continue
                    stat = os.stat(full)
                    rel = os.path.relpath(full, model_path).replace("\\", "/")
                    entries.append(f"{rel}:{stat.st_size}:{int(stat.st_mtime)}")
            return "|".join(entries)
        except Exception:
            return ""

    # ------------------------------------------------------------------ config

    @classmethod
    def _read_config(cls, facts: ModelFacts) -> None:
        config_path = os.path.join(facts.path, "config.json")
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as exc:
            log.warning("[ModelInspector] Unreadable config.json: %s", exc)
            return

        facts.model_type = cfg.get("model_type", "unknown")
        facts.architectures = cfg.get("architectures", []) or []
        facts.is_multimodal = any(
            k in cfg for k in ("vision_config", "audio_config", "video_config")
        )

        # Multimodal configs nest the transformer geometry under text_config.
        text = cfg.get("text_config") or cfg.get("llm_config") or cfg
        facts.num_hidden_layers = int(text.get("num_hidden_layers", 0) or 0)
        facts.hidden_size = int(text.get("hidden_size", 0) or 0)
        facts.num_attention_heads = int(text.get("num_attention_heads", 0) or 0)
        facts.num_key_value_heads = int(
            text.get("num_key_value_heads", facts.num_attention_heads) or 0
        )
        facts.vocab_size = int(text.get("vocab_size", 0) or 0)
        facts.max_position_embeddings = int(text.get("max_position_embeddings", 0) or 0)
        facts.tie_word_embeddings = bool(
            text.get("tie_word_embeddings", cfg.get("tie_word_embeddings", False))
        )
        facts.torch_dtype = str(text.get("dtype") or text.get("torch_dtype") or "bfloat16")
        facts.layer_types = list(text.get("layer_types", []) or [])

        head_dim = text.get("head_dim")
        if not head_dim and facts.num_attention_heads:
            head_dim = facts.hidden_size // facts.num_attention_heads
        facts.head_dim = int(head_dim or 0)

        for key in ("num_experts", "num_local_experts", "n_routed_experts"):
            if text.get(key):
                facts.num_experts = int(text[key])
                facts.is_moe = True
                break

        # How many of them actually run per token. Without it the experts look
        # like weights that are read on every token, which is the opposite of
        # why they can be left in host memory.
        for key in ("num_experts_per_tok", "num_experts_per_token", "moe_topk"):
            if text.get(key):
                facts.experts_used = int(text[key])
                break

    # ------------------------------------------------------------ weight layout

    @classmethod
    def _read_weight_layout(cls, facts: ModelFacts) -> None:
        """Discovers the real layer prefix and measures true tensor sizes."""
        # Check for GGUF files (at root or in subfolders)
        gguf_files: List[str] = []
        for root, _dirs, files in os.walk(facts.path):
            for f in sorted(files):
                if f.endswith(".gguf"):
                    gguf_files.append(os.path.relpath(os.path.join(root, f), facts.path))

        if gguf_files:
            facts.weight_format = "gguf"
            main_ggufs = [
                f for f in gguf_files if not (
                    os.path.basename(f).lower().startswith("mmproj") or "mmproj" in os.path.basename(f).lower() or
                    "-clip-" in os.path.basename(f).lower() or "_clip_" in os.path.basename(f).lower() or os.path.basename(f).lower().startswith("clip-")
                )
            ]
            mmproj_files = [f for f in gguf_files if f not in main_ggufs]
            if mmproj_files:
                facts.is_multimodal = True

            primary_gguf = main_ggufs[0] if main_ggufs else gguf_files[0]
            target_files = main_ggufs if main_ggufs else gguf_files
            facts.shards_present = len(target_files)
            facts.total_shards_declared = len(target_files)
            facts.total_bytes = sum(
                os.path.getsize(os.path.join(facts.path, f)) for f in target_files
            )
            cls._read_gguf_metadata(facts, os.path.join(facts.path, primary_gguf))
            cls._read_gguf_tensor_sizes(
                facts, [os.path.join(facts.path, f) for f in target_files])
            return

        files = os.listdir(facts.path)
        index_path = os.path.join(facts.path, "model.safetensors.index.json")

        part_files = [f for f in files if f.endswith((".part", ".download", ".tmp"))]
        if part_files:
            facts.has_part_files = True
            facts.is_complete = False

        # Bound before the branch that may not run: a model saved as a single
        # `model.safetensors` has no index, and so does one whose index fails
        # to parse. Both are ordinary, and neither should reach the fallback
        # below with this name unbound.
        shard_files: List[str] = []

        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
                weight_map = index.get("weight_map", {})
                facts.total_bytes = int(index.get("metadata", {}).get("total_size", 0))
                cls._detect_prefixes(facts, list(weight_map.keys()))
                declared_shards = sorted(set(weight_map.values()))
                facts.total_shards_declared = len(declared_shards)
                shard_files = [f for f in declared_shards if os.path.exists(os.path.join(facts.path, f))]
                facts.shards_present = len(shard_files)
                if len(shard_files) < len(declared_shards):
                    facts.is_complete = False
                    facts.missing_shards_count = len(declared_shards) - len(shard_files)
            except Exception as exc:
                log.warning("[ModelInspector] Unreadable weight index: %s", exc)

        if not shard_files:
            shard_files = sorted(f for f in files if f.endswith(".safetensors"))
            facts.shards_present = len(shard_files)
            if not shard_files:
                facts.weight_format = "bin"
                facts.total_bytes = sum(
                    os.path.getsize(os.path.join(facts.path, f))
                    for f in files if f.endswith(".bin")
                )
                return

            # Check if this is a multi-shard repo without index file
            max_shard_idx = 1
            for sf in shard_files:
                m_match = re.search(r"-of-(\d+)\.safetensors", sf)
                if m_match:
                    try:
                        max_shard_idx = max(max_shard_idx, int(m_match.group(1)))
                    except Exception:
                        pass
            facts.total_shards_declared = max_shard_idx
            if max_shard_idx > 1:
                if len(shard_files) < max_shard_idx or not os.path.exists(index_path):
                    facts.is_complete = False
                    facts.missing_shards_count = max(0, max_shard_idx - len(shard_files))

        cls._measure_tensors(facts, shard_files)

        if not facts.total_bytes:
            facts.total_bytes = sum(
                os.path.getsize(os.path.join(facts.path, f)) for f in shard_files
            )

    # GGUF metadata value types, per the format specification.
    _GGUF_UINT8, _GGUF_INT8, _GGUF_UINT16, _GGUF_INT16 = 0, 1, 2, 3
    _GGUF_UINT32, _GGUF_INT32, _GGUF_FLOAT32, _GGUF_BOOL = 4, 5, 6, 7
    _GGUF_STRING, _GGUF_ARRAY = 8, 9
    _GGUF_UINT64, _GGUF_INT64, _GGUF_FLOAT64 = 10, 11, 12

    _GGUF_SCALARS = {
        _GGUF_UINT8: ("<B", 1), _GGUF_INT8: ("<b", 1),
        _GGUF_UINT16: ("<H", 2), _GGUF_INT16: ("<h", 2),
        _GGUF_UINT32: ("<I", 4), _GGUF_INT32: ("<i", 4),
        _GGUF_FLOAT32: ("<f", 4), _GGUF_BOOL: ("<?", 1),
        _GGUF_UINT64: ("<Q", 8), _GGUF_INT64: ("<q", 8),
        _GGUF_FLOAT64: ("<d", 8),
    }

    @classmethod
    def _read_gguf_metadata(cls, facts: ModelFacts, gguf_path: str) -> None:
        """
        Reads geometry from a GGUF file's own header.

        Parsed directly rather than through llama-cpp-python so a model can be
        inspected and planned on a machine where that backend is not installed
        -- which is exactly the case when deciding whether to install it.
        """
        try:
            with open(gguf_path, "rb") as handle:
                if handle.read(4) != b"GGUF":
                    log.debug("[ModelInspector] Not a GGUF file: %s", gguf_path)
                    return
                struct.unpack("<I", handle.read(4))[0]           # format version
                struct.unpack("<Q", handle.read(8))[0]           # tensor count
                kv_count = struct.unpack("<Q", handle.read(8))[0]

                metadata: Dict[str, Any] = {}
                for _ in range(min(kv_count, 4096)):
                    key = cls._read_gguf_string(handle)
                    if key is None:
                        break
                    value_type = struct.unpack("<I", handle.read(4))[0]
                    metadata[key] = cls._read_gguf_value(handle, value_type)
        except Exception as exc:
            log.debug("[ModelInspector] GGUF header unreadable: %s", exc)
            return

        arch = str(metadata.get("general.architecture", "") or "")
        facts.model_type = arch or "gguf"
        if arch:
            facts.architectures = [arch]

        def geometry(suffix: str, default: int = 0) -> int:
            value = metadata.get(f"{arch}.{suffix}") if arch else None
            return int(value) if isinstance(value, (int, float)) else default

        facts.num_hidden_layers = geometry("block_count")
        facts.hidden_size = geometry("embedding_length")
        facts.num_attention_heads = geometry("attention.head_count")
        facts.num_key_value_heads = geometry(
            "attention.head_count_kv", facts.num_attention_heads
        )
        facts.max_position_embeddings = geometry("context_length")
        facts.num_experts = geometry("expert_count")
        facts.experts_used = geometry("expert_used_count")
        facts.is_moe = facts.num_experts > 0

        head_dim = geometry("attention.key_length")
        if not head_dim and facts.num_attention_heads:
            head_dim = facts.hidden_size // facts.num_attention_heads
        facts.head_dim = head_dim

        # The vocabulary decides more than tokenization: llama-cpp-python sizes
        # its logits buffer as n_batch x n_vocab float32, so on a large-vocab
        # model the prefill batch costs a megabyte per slot in host RAM. Leaving
        # this at zero, as the GGUF path used to, meant that cost was invisible
        # to the planner exactly where it is largest.
        vocab = geometry("vocab_size")
        if not vocab:
            # Not every converter writes vocab_size; the token list is always
            # there, and the header parser already recorded its length rather
            # than materialising a quarter of a million strings.
            vocab = cls._gguf_array_length(metadata.get("tokenizer.ggml.tokens"))
        facts.vocab_size = vocab

        # Hybrid models interleave full attention with linear/recurrent layers,
        # and GGUF records that as an interval rather than a list. Only the full
        # attention layers hold a KV cache that grows with the context; treating
        # all of them as full attention overstates the cache several-fold and
        # makes the planner leave layers on the CPU that would have fit.
        interval = geometry("full_attention_interval")
        if interval > 1 and facts.num_hidden_layers:
            facts.layer_types = [
                "full_attention" if (i + 1) % interval == 0 else "linear_attention"
                for i in range(facts.num_hidden_layers)
            ]

        # GGUF ships already quantized, so the whole file is the resident cost;
        # there is no separate quantizable/resident split to model.
        facts.param_count = 0
        facts.quantizable_params = 0
        facts.resident_params = 0

    @classmethod
    def _read_gguf_tensor_sizes(cls, facts: ModelFacts, gguf_paths: List[str]) -> None:
        """
        How many bytes the mixture-of-experts tensors occupy, across all shards.

        On a MoE model the placement question is not "how many layers fit on
        the accelerator" but "which tensors". The experts are both the largest
        part and the part a single token barely touches -- ten of five hundred
        and twelve, here -- so they are what belongs in host memory while the
        rest of the model sits on the card. Deciding that needs their real
        size, and the ratio is nothing like constant: two thirds of the weights
        in one model, a fifth in another.

        The size of a tensor is taken as the distance to the next one rather
        than computed from its quantization type. The file already records
        where each begins, whereas a table of block sizes is a second copy of
        ggml's type list that would go stale every time a type is added.

        Shared experts are deliberately excluded: they run for every token, so
        moving them off the accelerator costs on every token too. Only the
        routed experts (`_exps`) are counted.

        Measured alongside them is what llama.cpp will not put on a device at
        all: the per-layer embedding table, which is a lookup rather than a
        matrix multiply and stays in host memory however deep the offload
        goes. It is 33 of the 111 GiB in Qwen3.8-Flash-Next, so counting it as
        VRAM-bound makes a model that runs look impossible to place.
        """
        alignment = 32
        total = 0
        host_only = 0
        for path in gguf_paths:
            try:
                size_on_disk = os.path.getsize(path)
                with open(path, "rb") as handle:
                    if handle.read(4) != b"GGUF":
                        continue
                    handle.seek(4, os.SEEK_CUR)  # format version
                    tensor_count = struct.unpack("<Q", handle.read(8))[0]
                    kv_count = struct.unpack("<Q", handle.read(8))[0]

                    for _ in range(kv_count):
                        key = cls._read_gguf_string(handle)
                        value_type = struct.unpack("<I", handle.read(4))[0]
                        value = cls._read_gguf_value(handle, value_type)
                        if key == "general.alignment" and isinstance(value, int) and value > 0:
                            alignment = value

                    entries = []
                    for _ in range(tensor_count):
                        name = cls._read_gguf_string(handle) or ""
                        dim_count = struct.unpack("<I", handle.read(4))[0]
                        handle.seek(8 * dim_count + 4, os.SEEK_CUR)  # dims + ggml type
                        offset = struct.unpack("<Q", handle.read(8))[0]
                        entries.append((offset, name))

                    data_start = handle.tell()
                    if data_start % alignment:
                        data_start += alignment - (data_start % alignment)

                entries.sort()
                payload = size_on_disk - data_start
                for index, (offset, name) in enumerate(entries):
                    end = entries[index + 1][0] if index + 1 < len(entries) else payload
                    if "_exps" in name:
                        total += max(end - offset, 0)
                    elif "per_layer_token_embd" in name:
                        host_only += max(end - offset, 0)
            except Exception as exc:
                log.debug("[ModelInspector] Tensor table unreadable in %s: %s", path, exc)
                return

        facts.expert_bytes = total
        facts.host_only_bytes = host_only
        if total and not facts.is_moe:
            facts.is_moe = True

    @classmethod
    def _read_gguf_string(cls, handle) -> Optional[str]:
        raw_len = handle.read(8)
        if len(raw_len) < 8:
            return None
        length = struct.unpack("<Q", raw_len)[0]
        if length > 64 * 1024 * 1024:
            return None
        return handle.read(length).decode("utf-8", errors="replace")

    @staticmethod
    def _gguf_array_length(marker: Any) -> int:
        """The element count recorded for a skipped GGUF array, or 0."""
        if not isinstance(marker, str) or not marker.startswith("<array["):
            return 0
        try:
            return int(marker[len("<array["):-2])
        except ValueError:
            return 0

    @classmethod
    def _read_gguf_value(cls, handle, value_type: int) -> Any:
        """Reads one metadata value, skipping over arrays we do not need."""
        if value_type in cls._GGUF_SCALARS:
            fmt, size = cls._GGUF_SCALARS[value_type]
            return struct.unpack(fmt, handle.read(size))[0]

        if value_type == cls._GGUF_STRING:
            return cls._read_gguf_string(handle)

        if value_type == cls._GGUF_ARRAY:
            elem_type = struct.unpack("<I", handle.read(4))[0]
            count = struct.unpack("<Q", handle.read(8))[0]
            # Tokenizer vocabularies live here and can be hundreds of thousands
            # of entries; walk past them rather than materialising them.
            if elem_type in cls._GGUF_SCALARS:
                handle.seek(cls._GGUF_SCALARS[elem_type][1] * count, os.SEEK_CUR)
            elif elem_type == cls._GGUF_STRING:
                for _ in range(count):
                    if cls._read_gguf_string(handle) is None:
                        break
            return f"<array[{count}]>"

        raise ValueError(f"unsupported GGUF value type {value_type}")

    @classmethod
    def _detect_prefixes(cls, facts: ModelFacts, tensor_names: List[str]) -> None:
        """
        Finds the actual '<...>.layers' prefix used by this checkpoint.

        This is what makes device maps portable: 'model.layers' (Llama/Qwen2),
        'model.language_model.layers' (Qwen3.5-VL), 'transformer.h' (GPT-2), etc.
        The decoder stack is whichever prefix carries the most tensors.
        """
        counts: Dict[str, int] = {}
        for name in tensor_names:
            parts = name.split(".")
            for i, part in enumerate(parts):
                if part.isdigit() and i > 0:
                    prefix = ".".join(parts[:i])
                    counts[prefix] = counts.get(prefix, 0) + 1
                    break

        if counts:
            facts.layer_prefix = max(counts.items(), key=lambda kv: kv[1])[0]
            facts.auxiliary_prefixes = sorted(
                p for p in counts
                if p != facts.layer_prefix and not p.startswith(facts.layer_prefix)
            )

        facts.has_mtp = any(n.startswith("mtp.") for n in tensor_names)
        if not facts.is_multimodal:
            facts.is_multimodal = any(
                ".visual." in n or n.startswith("visual.") or ".vision_tower." in n
                for n in tensor_names
            )
        if not facts.is_moe:
            facts.is_moe = any(".experts." in n for n in tensor_names)

    @classmethod
    def _measure_tensors(cls, facts: ModelFacts, shard_files: List[str]) -> None:
        """
        Reads only the safetensors headers (not the payload) to get exact dtype
        and shape per tensor, then splits params into quantizable (2-D Linear
        weights) vs resident (embeddings, lm_head, norms, conv kernels).
        """
        total_params = 0
        quantizable = 0
        resident = 0
        measured_bytes = 0
        expert_bytes = 0

        for shard in shard_files:
            full_path = os.path.join(facts.path, shard)
            header = cls._read_safetensors_header(full_path)
            if not header:
                continue

            for name, meta in header.items():
                if name == "__metadata__" or not isinstance(meta, dict):
                    continue
                shape = meta.get("shape") or []
                dtype = meta.get("dtype", "BF16")
                if not shape:
                    continue

                numel = 1
                for dim in shape:
                    numel *= int(dim)
                total_params += numel
                tensor_bytes = int(numel * _DTYPE_BYTES.get(dtype, 2))
                measured_bytes += tensor_bytes
                # Same question as on the GGUF side, asked of the checkpoint's
                # own naming: "model.layers.N.mlp.experts.M.up_proj.weight".
                if ".experts." in name:
                    expert_bytes += tensor_bytes

                is_linear_weight = (
                    len(shape) == 2
                    and name.endswith(".weight")
                    and not any(hint in name for hint in _NEVER_QUANTIZED_HINTS)
                )
                if is_linear_weight:
                    quantizable += numel
                else:
                    resident += numel

        if total_params:
            facts.param_count = total_params
            facts.quantizable_params = quantizable
            facts.resident_params = resident
        if expert_bytes:
            facts.expert_bytes = expert_bytes
        if measured_bytes and not facts.total_bytes:
            facts.total_bytes = measured_bytes

    @staticmethod
    def _read_safetensors_header(path: str) -> Optional[Dict[str, Any]]:
        """Parses the JSON header at the start of a .safetensors file."""
        try:
            with open(path, "rb") as f:
                raw_len = f.read(8)
                if len(raw_len) < 8:
                    return None
                header_len = struct.unpack("<Q", raw_len)[0]
                if header_len <= 0 or header_len > 200 * 1024 * 1024:
                    return None
                return json.loads(f.read(header_len).decode("utf-8"))
        except Exception as exc:
            log.debug("[ModelInspector] Header read failed for %s: %s", path, exc)
            return None

    # --------------------------------------------------------------- estimates

    @classmethod
    def estimate_footprint(
        cls,
        facts: ModelFacts,
        quantization: str = "nf4",
        compute_dtype_bytes: int = 2,
    ) -> Dict[str, float]:
        """
        Estimates resident memory for the weights under a given quantization.

        Returns GB figures. bitsandbytes keeps embeddings, lm_head, norms and
        conv kernels in compute dtype — on large-vocab models that residual is
        several GB and is exactly what makes naive VRAM plans overflow.
        """
        if not facts.param_count:
            return {
                "quantized_gb": 0.0,
                "resident_gb": 0.0,
                "total_gb": round(facts.total_bytes / 2**30, 2),
                "quantization": quantization,
            }

        per_param = {
            "nf4": _NF4_BYTES_PER_PARAM,
            "fp4": _NF4_BYTES_PER_PARAM,
            "int8": _INT8_BYTES_PER_PARAM,
        }.get((quantization or "").lower(), float(compute_dtype_bytes))

        quantized_gb = (facts.quantizable_params * per_param) / 2**30
        resident_gb = (facts.resident_params * compute_dtype_bytes) / 2**30

        return {
            "quantized_gb": round(quantized_gb, 2),
            "resident_gb": round(resident_gb, 2),
            "total_gb": round(quantized_gb + resident_gb, 2),
            "quantization": quantization,
            "quantizable_params": facts.quantizable_params,
            "resident_params": facts.resident_params,
        }

    @classmethod
    def estimate_kv_cache_gb(
        cls,
        facts: ModelFacts,
        context_tokens: int,
        batch_size: int = 1,
        bytes_per_element: int = 2,
    ) -> float:
        """
        KV cache growth for a given context length.

        Only full-attention layers scale with sequence length; linear-attention
        layers carry a constant-size recurrent state, which is why hybrid models
        tolerate far longer contexts than their layer count suggests.
        """
        if not facts.num_hidden_layers or not facts.head_dim:
            return 0.0

        if facts.layer_types:
            attn_layers = sum(1 for t in facts.layer_types if t == "full_attention")
            if attn_layers == 0:
                attn_layers = facts.num_hidden_layers
        else:
            attn_layers = facts.num_hidden_layers

        kv_heads = facts.num_key_value_heads or facts.num_attention_heads or 1
        per_token = 2 * attn_layers * kv_heads * facts.head_dim * bytes_per_element
        return round((per_token * context_tokens * batch_size) / 2**30, 3)

    @classmethod
    def resolve_model_class(cls, facts: ModelFacts):
        """
        Returns the transformers class this checkpoint declares, with automatic
        architecture alias fallback for newly released or unified models.
        """
        from core.engine.transformers_compat import ensure_transformers_compatibility, resolve_model_architecture_class
        ensure_transformers_compatibility()

        import transformers

        for arch in facts.architectures:
            model_cls = resolve_model_architecture_class(arch, is_multimodal=facts.is_multimodal)
            if model_cls is not None:
                return model_cls

        if facts.is_multimodal:
            fallback = getattr(transformers, "AutoModelForImageTextToText", None) or getattr(transformers, "AutoModelForVision2Seq", None)
            if fallback is not None:
                log.info("[ModelInspector] Falling back to AutoModelForImageTextToText")
                return fallback

        return transformers.AutoModelForCausalLM
