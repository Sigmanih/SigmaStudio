# ==============================================================================
# core/engine/unified_runtime.py — Universal Inference Engine & Hardware Dispatcher
#
# Placement is derived, never hardcoded: ModelInspector measures the checkpoint,
# UniversalHardwareProbe measures the machine, MemoryPlanner turns both into the
# max_memory / offload arguments accelerate consumes. Adding a GPU, changing a
# model or moving to another machine changes the plan without a code edit.
# ==============================================================================
import os
import time
import atexit
import threading
from typing import Dict, Any, List, Optional, Generator, Tuple

from core.logger import get_logger
from core.engine.hardware_probe import UniversalHardwareProbe
from core.engine.model_inspector import ModelInspector, ModelFacts
from core.engine.memory_planner import MemoryPlanner, PlacementPlan
from core.engine.sampling import SamplingParams
from core.engine.cancellation import is_cancelled, stopping_criteria_for
from core.engine.prefix_cache import PrefixKVCache

log = get_logger(__name__)

# Spare VRAM required, on top of the cache itself, before a KV cache is held
# between turns. A retained cache is memory the next turn starts from rather
# than memory it can allocate, so the margin has to cover the activations of
# that next turn too.
_PREFIX_CACHE_MIN_SPARE_GB = 1.0

#: Minimum probability the option labels must hold, together, for the ranking
#: between them to mean anything. Below this the model was about to write
#: something else entirely, and the "choice" would be a comparison between two
#: numbers that are both noise.
CHOICE_MIN_MASS = 0.01

#: How many tokens of the model's own punctuation to step over before giving up
#: on finding a label. "Answer: **C**" needs one; two covers a stray space as
#: well. Past that the model is writing prose, not decorating.
CHOICE_DECORATION_STEPS = 2

#: Text a model puts *around* an answer rather than as one.
_DECORATION = {"*", "**", "***", "-", ":", "=", '"', "'", "(", "[", "{", "#",
               "`", "``", "```", ".", "_", "__"}


def _is_decoration(text: str) -> bool:
    """Whether this token is punctuation the answer is about to appear inside."""
    stripped = (text or "").strip()
    return stripped in _DECORATION or (bool(text) and not stripped)

DEFAULT_SYSTEM_PROMPT = (
    "Sei Sigma Assistant, un'architettura AI avanzata, precisa e utile. "
    "Rispondi in italiano in modo esaustivo, dettagliato e strutturato."
)


def _causa_gia_spiegata(error: str) -> bool:
    """La diagnosi ha gia' detto perche', e con che cosa rimediare."""
    testo = str(error or "")
    return len(testo) > 200 and ("**" in testo or "```" in testo)


# ---------------------------------------------------------------------------
# Helpers for batched and constrained inference
# ---------------------------------------------------------------------------

def _describe_exception(exc: BaseException, depth: int = 3) -> str:
    """
    The exception, plus the exceptions it was raised from.

    Transformers hides import failures behind a lazy loader that re-raises as
    ``ModuleNotFoundError: Could not import module 'Qwen3ForCausalLM'. Are this
    object's requirements defined correctly?`` -- a sentence that names the
    symbol and says nothing about why it could not be imported. The cause chain
    carries the real reason (a missing dependency, a partially initialised
    module, a version mismatch), and dropping it turns a five-second diagnosis
    into an afternoon.
    """
    parts = [f"{type(exc).__name__}: {exc}"]
    cause = exc.__cause__ or exc.__context__
    seen = {id(exc)}
    while cause is not None and depth > 0 and id(cause) not in seen:
        seen.add(id(cause))
        parts.append(f"causato da {type(cause).__name__}: {cause}")
        cause = cause.__cause__ or cause.__context__
        depth -= 1
    return " | ".join(parts)


def _unrecognised_architecture(error: str) -> bool:
    """Whether this failure is transformers refusing to know the checkpoint."""
    lowered = str(error or "").lower()
    return ("does not recognize this architecture" in lowered
            or "but transformers does not recognize" in lowered
            or "unrecognized configuration class" in lowered)


def _version_mismatch_advice(model_path: str) -> str:
    """
    Names the real cause when a checkpoint is newer than the library reading it.

    The stock message says "your version of Transformers is out of date" and
    then lists three things to try. The checkpoint itself carries the version it
    was written with, and the installed one is a single import away -- so the
    two numbers can be put side by side, and the guess becomes a statement.
    """
    saved = ""
    try:
        with open(os.path.join(model_path, "config.json"), "r", encoding="utf-8") as fh:
            import json as _json
            saved = str(_json.load(fh).get("transformers_version") or "")
    except Exception:
        saved = ""

    installed = ""
    try:
        import transformers
        installed = str(getattr(transformers, "__version__", ""))
    except Exception:
        installed = ""

    def _parts(value: str):
        numbers = []
        for chunk in str(value).split("."):
            digits = "".join(c for c in chunk if c.isdigit())
            numbers.append(int(digits) if digits else 0)
        return tuple(numbers[:3])

    if saved and installed and _parts(saved) > _parts(installed):
        return (
            f"Il checkpoint e' stato salvato con transformers **{saved}**, "
            f"qui e' installata la **{installed}**: questa architettura non "
            f"esiste ancora nella versione presente.\n\n"
            f"Aggiorna il runtime:\n\n"
            f"```\npip install --upgrade transformers\n```\n\n"
            f"Se non basta perche' il modello e' appena uscito:\n\n"
            f"```\npip install git+https://github.com/huggingface/transformers.git\n```\n\n"
            f"In alternativa usa la variante GGUF dello stesso modello, che non "
            f"passa da transformers."
        )
    if saved or installed:
        return (
            f"Transformers **{installed or '?'}** non conosce questa "
            f"architettura (checkpoint salvato con **{saved or '?'}**). "
            f"Aggiorna con `pip install --upgrade transformers`, oppure usa la "
            f"variante GGUF dello stesso modello."
        )
    return ("Transformers non conosce questa architettura. Aggiorna con "
            "`pip install --upgrade transformers`, oppure usa la variante GGUF "
            "dello stesso modello.")


def _cut_at_stop(text: str, stop) -> Tuple[str, bool]:
    """
    Truncates at the first stop string, reporting whether one was found.

    Batched generation cannot stop the whole batch when one row is finished --
    the others are still decoding -- so a row that ran past its stop sequence
    carries the tail with it. Cutting here makes the batched answer identical
    to the streamed one instead of merely similar.
    """
    if not stop or not text:
        return text, False
    earliest = len(text)
    found = False
    for marker in stop:
        if not marker:
            continue
        at = text.find(marker)
        if at != -1 and at < earliest:
            earliest, found = at, True
    return (text[:earliest], True) if found else (text, False)


def _with_bos(tokenizer, ids: List[int]) -> List[int]:
    """
    The sequence with its begin-of-sequence token, whatever the tokenizer did.

    `add_special_tokens=True` is not a guarantee. Gemma's tokenizer declares a
    BOS and then does not prepend it, and Gemma without BOS is a model outside
    its own training distribution: " Paris" after "The capital of France is"
    scored a log-probability of -18.7 -- a probability of seven billionths --
    and every option ranking was ordering noise. The chat path never showed it
    because the chat template carries the token inside.
    """
    bos = getattr(tokenizer, "bos_token_id", None)
    if bos is None or (ids and ids[0] == bos):
        return ids
    return [int(bos)] + list(ids)


def _decoded_length(new_ids: List[int], eos_id: Optional[int]) -> int:
    """
    How many tokens this row of a batch actually produced.

    Every row of a batch runs for as long as the *longest* row: a sequence that
    finished after four tokens is padded out to the other's forty. Counting the
    padding as output reports a throughput the hardware never reached, and on a
    benchmark that number is the headline. The end-of-sequence token is the
    boundary -- it is generated, so it counts; everything after it is filler.
    """
    if eos_id is None:
        return len(new_ids)
    for position, token in enumerate(new_ids):
        if int(token) == int(eos_id):
            return position + 1
    return len(new_ids)


def _letter_token_ids(tokenizer, letter: str) -> List[int]:
    """
    The tokens that would *be* this option label, if it came next.

    A tokenizer has no single id for "A": there is one for "A" opening a
    segment and another for " A" after a space, and which one a model reaches
    for depends on the chat template it was trained with. Both are scored, and
    the stronger is taken.

    Only spellings that are a single token qualify. This is the whole
    correctness of the method and it is easy to get wrong: a prefixed spelling
    like a newline or "**" followed by the letter tokenizes as *two* tokens,
    and its first token is the newline -- which is shared by every letter. Score
    those and every option receives the same probability, every question is won
    by whichever letter is checked first, and every margin is zero. It looks
    like a model with a position bias and it is a bug in the reader.
    """
    ids: List[int] = []
    for spelling in (letter, " " + letter):
        try:
            encoded = tokenizer.encode(spelling, add_special_tokens=False)
        except Exception:
            continue
        if len(encoded) == 1:
            ids.append(int(encoded[0]))
    seen, unique = set(), []
    for value in ids:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


class UniversalSigmaEngine:
    """
    Universal LLM engine for Sigma Studio.

    Dispatches execution to the best backend available on the device and places
    model weights across VRAM -> RAM -> disk according to measured capacity.
    """

    def __init__(self):
        # Hardware probing is deferred: it spawns subprocesses and touches every
        # volume, which must not happen at import time.
        self._hardware_profile: Optional[Dict[str, Any]] = None
        self._active_backend: Optional[str] = None

        self.loaded_model_name: Optional[str] = None
        self.loaded_model: Optional[Dict[str, Any]] = None
        # Set when a non-safetensors checkpoint is served by a registry backend
        # (llama.cpp today). The transformers path uses model_instance instead.
        self.active_backend_instance = None
        self.model_instance = None
        self.tokenizer_instance = None
        self.model_facts: Optional[ModelFacts] = None
        self.placement_plan: Optional[PlacementPlan] = None
        self.last_load_error: Optional[str] = None
        self.last_device_map_report: Optional[Dict[str, Any]] = None
        self._load_lock = threading.Lock()
        # Whether the resident checkpoint's chat template reads
        # `enable_thinking`. Measured once per load rather than guessed from
        # the model name, and invalidated whenever the weights change.
        self._thinking_switch: Optional[bool] = None

        # One model is resident at a time, so one generation runs at a time.
        # The server is threaded and admits concurrent requests: without this,
        # two chats for different models had one thread unload the weights the
        # other was mid-generation on, and two chats for the same GGUF called
        # into llama.cpp concurrently, which is not thread-safe. The queue is
        # not a limitation added here -- it is the truth about the hardware,
        # made explicit instead of discovered as a crash.
        self._generation_lock = threading.RLock()
        self._generation_waiting = 0
        self._waiting_lock = threading.Lock()

        # Cross-turn KV reuse on the transformers path. On by default because
        # the memory it holds is memory the placement plan already reserved for
        # the context window; SIGMA_PREFIX_CACHE=0 turns it off for a machine
        # where that budget is genuinely tight.
        self.prefix_cache = PrefixKVCache()
        self.prefix_cache_enabled = os.environ.get("SIGMA_PREFIX_CACHE", "1") != "0"
        # Set per load: even when the feature is on, a placement without room
        # to spare must not hold a cache between turns.
        self.prefix_cache_retained = False

    # ------------------------------------------------------------- hardware

    @property
    def has_resident_model(self) -> bool:
        """
        Whether any runtime currently holds weights.

        Residency lives in two places: the transformers path keeps a module in
        model_instance, a registry backend keeps its own handle. Checking only
        one makes the engine reload on top of a model it already has.
        """
        if self.model_instance is not None:
            return True
        backend = self.active_backend_instance
        return backend is not None and backend.is_loaded

    @property
    def hardware_profile(self) -> Dict[str, Any]:
        if self._hardware_profile is None:
            self._hardware_profile = UniversalHardwareProbe.probe_all()
        return self._hardware_profile

    @hardware_profile.setter
    def hardware_profile(self, value: Dict[str, Any]) -> None:
        self._hardware_profile = value
        self._active_backend = None

    @property
    def active_backend(self) -> str:
        if self._active_backend is None:
            self._active_backend = self._determine_optimal_backend()
            log.info("[SigmaEngine] Active backend: %s", self._active_backend)
        return self._active_backend

    def refresh_vram(self) -> Dict[str, Any]:
        """
        Re-reads free VRAM before planning a load.

        Free VRAM is the one input that changes minute to minute (other
        processes, a previously loaded model), so a plan built from a stale
        reading will overcommit.
        """
        profile = self.hardware_profile
        try:
            profile["accelerators"] = UniversalHardwareProbe.probe_accelerators()
            profile["ram"] = UniversalHardwareProbe.probe_ram()
        except Exception as exc:
            log.warning("[SigmaEngine] VRAM refresh failed: %s", exc)
        return profile

    def _determine_optimal_backend(self) -> str:
        """
        Selects the best execution backend that is actually usable here.

        A backend is only reported when its runtime dependency is importable:
        naming a backend whose library is missing produces a plan that cannot
        run.
        """
        # Probe if needed rather than reading the raw field: callers reach this
        # through get_status(), where the accelerator list may not have been
        # populated yet, and an empty list would silently look like a CPU-only
        # machine and select a CPU backend on a box with two GPUs.
        profile = self.hardware_profile
        accs = profile.get("accelerators", [])
        system = profile.get("system", {})
        has_torch = self._module_available("torch")

        if has_torch and any(a.get("type") == "NVIDIA_CUDA" for a in accs):
            return "TORCH_CUDA_SDPA" if not self._module_available("flash_attn") \
                else "TORCH_CUDA_FLASHATTN"
        if has_torch and any(a.get("type") == "AMD_ROCM" for a in accs):
            return "TORCH_ROCM_HIP"
        if has_torch and any(a.get("type") == "APPLE_MPS" for a in accs):
            return "TORCH_APPLE_MPS"
        if self._module_available("llama_cpp"):
            if system.get("is_raspberry_pi") or system.get("is_arm"):
                return "ARM_NEON_LLAMACPP"
            return "CPU_LLAMACPP"
        if self._module_available("onnxruntime"):
            return "ONNX_RUNTIME"
        if has_torch:
            return "TORCH_CPU"
        return "UNAVAILABLE_NO_RUNTIME"

    @staticmethod
    def _module_available(name: str) -> bool:
        import importlib.util
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:
            return False

    def _generate_default_optimizations(self) -> Dict[str, Any]:
        """
        Reports the optimizations that are genuinely active on this machine.

        Every flag here is one the loader actually applies; nothing is reported
        as enabled unless its dependency is installed and its argument is passed
        to the runtime.
        """
        accs = self.hardware_profile.get("accelerators", [])
        has_cuda = any(a.get("type") == "NVIDIA_CUDA" for a in accs)
        has_flash = self._module_available("flash_attn")
        has_fla = self._module_available("fla")

        return {
            "backend": self.active_backend,
            "attention_kernel": self._select_attn_implementation(),
            "flash_attention_2_available": has_flash,
            "linear_attention_kernels": "fla_triton" if has_fla else "torch_fallback",
            "causal_conv1d_available": self._module_available("causal_conv1d"),
            "devices_in_use": len([a for a in accs if "free_vram_gb" in a]),
            "quantization": (
                self.placement_plan.quantization if self.placement_plan else "auto"
            ),
            "max_memory": (
                {str(k): v for k, v in self.placement_plan.max_memory.items()}
                if self.placement_plan else {}
            ),
            "offload_folder": (
                self.placement_plan.offload_folder if self.placement_plan else None
            ),
            "bf16_supported": any(a.get("supports_bf16") for a in accs) if has_cuda else False,
            # Reported from the backend that is actually running, not from a
            # class that was instantiated and never called. The MoE expert
            # cache, the speculative engine and the multi-drive streamer used
            # to be constructed here and appear in this dictionary while none
            # of their methods was reachable from any code path -- three
            # accelerations that existed only in the status panel.
            "speculative": (
                (self.active_backend_instance.telemetry() or {}).get("speculative")
                if self.active_backend_instance is not None else None
            ),
            "kv_cache_type": (
                (self.active_backend_instance.telemetry() or {}).get("kv_quant", "f16")
                if self.active_backend_instance is not None else "f16"
            ),
            "prefix_kv_reuse": self.prefix_cache_enabled,
            "native_mtp_head": bool(self.model_facts and self.model_facts.has_mtp),
        }

    def _select_attn_implementation(self) -> str:
        """Picks the fastest attention kernel whose dependency is installed."""
        if self._module_available("flash_attn"):
            return "flash_attention_2"
        try:
            import torch
            if torch.cuda.is_available() or hasattr(torch.nn.functional, "scaled_dot_product_attention"):
                return "sdpa"
        except Exception:
            pass
        return "eager"

    # -------------------------------------------------------- model discovery

    def _transformers_infeasibility(
        self, facts: ModelFacts, plan: PlacementPlan, profile: Dict[str, Any]
    ) -> Optional[str]:
        """
        Why this checkpoint cannot run through transformers here, or None.

        Three questions, in the order that decides the answer: is there a torch
        at all, is there an accelerator, and does the smallest precision fit in
        what memory exists. A refusal always names the format that would work
        and, where one is already on disk, the folder.
        """
        if not self._module_available("torch"):
            return (
                f"'{facts.name}' e' in safetensors, che richiede PyTorch, non "
                "installato su questa macchina. Converti il modello in GGUF "
                "(Model Hub -> Converti) per usarlo con llama.cpp, che gira "
                "anche senza torch."
            )

        accelerators = [
            a for a in profile.get("accelerators", [])
            if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM", "APPLE_MPS")
        ]
        ram_gb = float((profile.get("ram") or {}).get("available_gb", 0.0) or 0.0)
        smallest_gb = ModelInspector.estimate_footprint(facts, "nf4")["total_gb"]
        if not smallest_gb:
            smallest_gb = facts.total_bytes / 2**30

        alternative = self._gguf_twin(facts)
        if alternative:
            suffix = f" Sullo stesso disco c'e' gia' '{alternative}', in GGUF: usa quello."
        else:
            try:
                from core.engine.gguf_converter import GgufConverter
                compat = GgufConverter.check_compatibility(facts)
                if compat.get("convertible"):
                    suffix = (
                        " Converti il modello in GGUF dal Model Hub: llama.cpp lo esegue "
                        "quantizzato e a blocchi, senza doverlo tenere tutto in memoria."
                    )
                else:
                    suffix = " Questo modello ha un'architettura sperimentale non convertibile in GGUF; per eseguirlo è necessario un hardware con maggiore memoria oppure un modello di parametri inferiori."
            except Exception:
                suffix = " Seleziona un modello con requisiti di memoria compatibili con l'hardware disponibile."

        if not accelerators:
            # CPU-only: transformers has no quantized CPU kernel path here, so
            # the model lands in its full dtype and the figure to beat is the
            # checkpoint on disk, not the 4-bit footprint.
            full_gb = facts.total_bytes / 2**30
            if full_gb > max(ram_gb - 2.0, 1.0):
                return (
                    f"'{facts.name}' occupa {full_gb:.1f} GB e questa macchina non "
                    f"ha acceleratori: transformers lo caricherebbe in RAM, dove "
                    f"ce ne sono {ram_gb:.1f} GB liberi.{suffix}"
                )
            return None

        total_vram = sum(a.get("free_vram_gb", 0.0) for a in accelerators)
        reachable = total_vram + max(ram_gb - 2.0, 0.0)
        if smallest_gb > reachable:
            return (
                f"'{facts.name}' richiede almeno {smallest_gb:.1f} GB anche a 4 bit, "
                f"e qui sono raggiungibili {reachable:.1f} GB fra VRAM "
                f"({total_vram:.1f}) e RAM libera ({ram_gb:.1f}).{suffix}"
            )
        return None

    @staticmethod
    def _gguf_twin(facts: ModelFacts) -> Optional[str]:
        """A folder holding a GGUF of the same checkpoint, if one is local."""
        try:
            from core.model_paths import models_dir
            root = models_dir()
            if not os.path.isdir(root):
                return None
        except Exception:
            return None

        stem = facts.name.lower().split("-gguf")[0]
        for entry in sorted(os.listdir(root)):
            folder = os.path.join(root, entry)
            if not os.path.isdir(folder) or entry == facts.name:
                continue
            if not entry.lower().startswith(stem):
                continue
            if any(f.endswith(".gguf") for f in os.listdir(folder)):
                return entry
        return None

    def find_valid_model_directory(
        self, model_identifier: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Finds the directory and canonical name of a local model with weights.

        Resolution lives in core.model_paths so the engine, the downloader,
        the inventory and the converter all agree on where models are, and
        all follow the directory configured in the Model Hub.
        """
        from core.model_paths import resolve_model_dir, list_model_dirs

        alias_keywords = ("sigmaengine", "sigma-native:latest", "sigma:latest", "default", "auto", "native", "")

        # If alias or empty, check currently loaded resident model first
        if (not model_identifier or str(model_identifier).strip().lower() in alias_keywords) and self.loaded_model_name:
            path = resolve_model_dir(self.loaded_model_name)
            if path:
                return path, os.path.basename(path.rstrip(os.sep + '/'))

        # If specific identifier, try direct resolve
        path = resolve_model_dir(model_identifier)

        # Fallback for alias or when identifier wasn't found directly: pick best available quantized GGUF model directory with weights
        if path is None:
            def _rank_model(p: str) -> int:
                b = os.path.basename(p).lower()
                if any(q in b for q in ("q4", "q5", "q8", "q6", "int4", "int8", "fp8")):
                    return 1
                if "gguf" in b:
                    return 2
                return 3

            candidates = sorted(list_model_dirs(), key=_rank_model)
            path = candidates[0] if candidates else None

        if path is None:
            return None
        return path, os.path.basename(path.rstrip(os.sep + '/'))

    # ------------------------------------------------------------- loading

    def load_native_model(
        self,
        model_identifier: Optional[str] = None,
        context_tokens: int = 32768,
        force_quantization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Loads a local model across all available memory tiers.

        Returns a structured result. Failures carry the real exception text so
        the caller can show the actual cause instead of a generic message.
        """
        with self._load_lock:
            return self._load_native_model_locked(
                model_identifier, context_tokens, force_quantization
            )

    def _load_native_model_locked(
        self,
        model_identifier: Optional[str],
        context_tokens: int,
        force_quantization: Optional[str],
    ) -> Dict[str, Any]:
        model_info = self.find_valid_model_directory(model_identifier)
        if not model_info:
            error = (
                f"Nessun modello con pesi validi trovato in data/models/ per "
                f"'{model_identifier}'."
            )
            self.last_load_error = error
            log.warning("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "discovery"}

        target_path, display_name = model_info

        # Already resident: switching chats that share a model costs nothing.
        if self.has_resident_model and self.loaded_model_name == display_name:
            log.debug("[SigmaEngine] '%s' already resident, reusing", display_name)
            return {
                "success": True,
                "model_name": display_name,
                "already_loaded": True,
                "load_seconds": 0.0,
                "plan": self.placement_plan.to_dict() if self.placement_plan else {},
                "placement": (self.loaded_model or {}).get("placement"),
            }

        # A different model: release the current one first. Two checkpoints
        # cannot share the VRAM budget, and loading over a resident model makes
        # the new plan overcommit and fall back to a host-RAM spill.
        if self.has_resident_model:
            log.info(
                "[SigmaEngine] Switching '%s' -> '%s', releasing current weights",
                self.loaded_model_name, display_name,
            )
            self.unload()

        # ------------------------------------------------------ measure
        try:
            facts = ModelInspector.inspect(target_path)
            if facts is None:
                raise RuntimeError("introspezione del checkpoint fallita")
        except Exception as exc:
            error = f"Impossibile analizzare il modello in {target_path}: {exc}"
            self.last_load_error = error
            log.error("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "inspection"}

        # Formats other than safetensors are served by a dedicated backend
        # chosen for this machine, so GGUF runs on llama.cpp CUDA kernels here
        # and on NEON on an ARM board without the caller knowing the difference.
        if facts.weight_format != "safetensors":
            return self._load_via_backend(facts, display_name, context_tokens)

        # Check completeness before attempting PyTorch / Transformers loading
        if not getattr(facts, "is_complete", True) or getattr(facts, "has_part_files", False):
            missing_text = f"{facts.shards_present}/{facts.total_shards_declared} shard presenti" if getattr(facts, "total_shards_declared", 1) > 1 else "download parziale"
            error = (
                f"Il checkpoint '{facts.name}' è incompleto su disco ({missing_text}). "
                f"Mancano l'indice dei pesi ('model.safetensors.index.json') o gli shard successivi. "
                f"Completa o riprendi il download dal Model Hub per usarlo in chat."
            )
            self.last_load_error = error
            log.warning("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "inspection", "facts": facts.to_dict()}

        # -------------------------------------------------------- plan
        profile = self.refresh_vram()
        plan = MemoryPlanner.build_plan(
            facts,
            profile,
            context_tokens=context_tokens,
            force_quantization=force_quantization,
        )

        # A safetensors checkpoint never reaches the backend registry: the
        # branch above sends only other formats there, so transformers is the
        # only runtime this path can use. That is fine on a workstation and
        # wrong everywhere else -- on a board with no accelerator it means a
        # 27B is loaded in float32 onto four gigabytes of RAM, which does not
        # fail so much as stop responding. The refusal below is what "supported
        # on every platform" actually requires: knowing where it cannot run,
        # and saying which format can.
        infeasible = self._transformers_infeasibility(facts, plan, profile)
        if infeasible:
            self.last_load_error = infeasible
            log.error("[SigmaEngine] %s", infeasible)
            return {
                "success": False,
                "error": infeasible,
                "stage": "feasibility",
                "plan": plan.to_dict(),
                "facts": facts.to_dict(),
            }

        log.info(
            "[SigmaEngine] Loading '%s' | %s | %s",
            display_name, facts.summary(), plan.summary(),
        )
        for warning in plan.warnings:
            log.warning("[SigmaEngine] %s", warning)

        # -------------------------------------------------------- load
        try:
            from core.engine.transformers_compat import ensure_transformers_compatibility
            ensure_transformers_compatibility()

            import torch
            import transformers
            from transformers import AutoTokenizer, BitsAndBytesConfig

            try:
                AutoProcessor = getattr(transformers, "AutoProcessor", None)
            except Exception:
                AutoProcessor = None

            os.environ.setdefault(
                "PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True"
            )

            has_cuda = torch.cuda.is_available()
            if has_cuda:
                try:
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    if hasattr(torch, "set_float32_matmul_precision"):
                        torch.set_float32_matmul_precision("high")
                except Exception:
                    pass

            compute_dtype = (
                torch.bfloat16
                if has_cuda and torch.cuda.is_bf16_supported()
                else (torch.float16 if has_cuda else torch.float32)
            )

            model_cls = ModelInspector.resolve_model_class(facts)
            log.info("[SigmaEngine] Model class: %s", model_cls.__name__)

            # Il livello di compatibilita' puo' far leggere la configurazione di
            # un'architettura che questa transformers non ha, mappandola sulla
            # parente piu' vicina. Va bene per una rinomina; non va bene quando
            # il checkpoint e' proprio piu' nuovo della libreria, perche' allora
            # i pesi non corrispondono ai moduli e il modello *si carica* e
            # risponde a vanvera. Su un benchmark e' l'esito peggiore possibile:
            # un punteggio pieno di numeri, tutti privi di senso.
            declared = (facts.architectures or [""])[0]
            if declared and declared != model_cls.__name__:
                advice = _version_mismatch_advice(target_path)
                if "salvato con transformers" in advice:
                    error = (f"L'architettura `{declared}` non esiste in questa "
                             f"versione di transformers. {advice}")
                    self.last_load_error = error
                    log.error("[SigmaEngine] %s", error)
                    return {
                        "success": False,
                        "error": error,
                        "stage": "preparation",
                        "facts": facts.to_dict(),
                    }
                log.warning(
                    "[SigmaEngine] Architettura '%s' non presente: si usa '%s'.",
                    declared, model_cls.__name__,
                )

            tokenizer = self._load_tokenizer(
                AutoTokenizer, AutoProcessor, target_path, facts
            )
        except Exception as exc:
            error = _describe_exception(exc)
            self.last_load_error = error
            log.error("[SigmaEngine] Preparation failed: %s", error, exc_info=True)
            return {
                "success": False,
                "error": error,
                "stage": "preparation",
                "facts": facts.to_dict(),
            }

        t0 = time.perf_counter()
        model, load_error = self._attempt_load(
            model_cls, target_path, plan, compute_dtype, has_cuda, facts
        )

        # Handle INT8 / SCB parameter incompatibility by automatically retrying with NF4
        if model is None and ("SCB" in str(load_error) or plan.quantization == "int8"):
            log.warning(
                "[SigmaEngine] INT8 placement encountered compatibility issue (%s). Retrying with NF4 4-bit precision...",
                load_error,
            )
            self._free_cuda_cache()
            plan = MemoryPlanner.build_plan(
                facts,
                self.refresh_vram(),
                context_tokens=context_tokens,
                force_quantization="nf4",
                allow_host_spill=False,
            )
            model, load_error = self._attempt_load(
                model_cls, target_path, plan, compute_dtype, has_cuda, facts
            )

        # Any first-attempt failure is potentially recoverable. Free VRAM can
        # drop between planning and loading -- another process, or another model
        # in this one -- so re-probe instead of trusting the reading the failed
        # plan was built on, and allow a host spill rather than leaving the user
        # with no model at all.
        if model is None and has_cuda:
            log.warning(
                "[SigmaEngine] Placement failed (%s). "
                "Re-probing VRAM and retrying with host RAM spill.", load_error,
            )
            self._free_cuda_cache()
            plan = MemoryPlanner.build_plan(
                facts,
                self.refresh_vram(),
                context_tokens=context_tokens,
                force_quantization=force_quantization or ("nf4" if "SCB" in str(load_error) else None),
                allow_host_spill=True,
            )
            plan.warnings.append(
                "First placement failed; replanned against currently free VRAM "
                "with a host-RAM spill, which is slower than a pure-VRAM fit."
            )
            model, load_error = self._attempt_load(
                model_cls, target_path, plan, compute_dtype, has_cuda, facts
            )

        if model is None:
            self.last_load_error = load_error
            log.error(
                "[SigmaEngine] Failed to load '%s': %s", display_name, load_error
            )
            return {
                "success": False,
                "error": load_error,
                "stage": "load",
                "plan": plan.to_dict(),
                "facts": facts.to_dict(),
            }

        model.eval()
        load_seconds = round(time.perf_counter() - t0, 1)

        # ------------------------------------------------------ register
        self.model_instance = model
        self.tokenizer_instance = tokenizer
        self.model_facts = facts
        self.placement_plan = plan
        self.loaded_model_name = display_name
        self.last_load_error = None
        self._thinking_switch = None

        # The cache may grow to the context the plan reserved KV for, and no
        # further: past that it stops being a saving and becomes a second copy
        # of the conversation sitting in VRAM.
        #
        # And only when the placement left room for it at all. Holding a KV
        # cache between turns is memory that is *not* released when the answer
        # ends, so on a plan whose headroom is already inside estimation error
        # it turns a tight fit into an out-of-memory error on the second
        # message. Saving a prefill is not worth losing the conversation.
        headroom = plan.vram_headroom_gb
        if headroom < plan.kv_cache_gb + _PREFIX_CACHE_MIN_SPARE_GB:
            self.prefix_cache.clear("placement too tight to retain KV")
            self.prefix_cache_retained = False
            log.info(
                "[SigmaEngine] Prefix KV reuse off for '%s': %.2fGB headroom does "
                "not cover a %.2fGB cache plus a safety margin.",
                display_name, headroom, plan.kv_cache_gb,
            )
        else:
            self.prefix_cache_retained = True
            self.prefix_cache.configure(display_name, plan.context_tokens)

        actual_placement = self._describe_placement(model)
        self.loaded_model = {
            "name": display_name,
            "path": target_path,
            "format": facts.weight_format,
            "size_gb": round(facts.total_bytes / 2**30, 2),
            "param_count_b": round(facts.param_count / 1e9, 2),
            "quantization": plan.quantization,
            "backend": self.active_backend,
            "placement": actual_placement,
            "plan": plan.to_dict(),
            "load_seconds": load_seconds,
            "loaded_at": time.time(),
            "status": "ready",
        }

        log.info(
            "[SigmaEngine] '%s' loaded in %ss | placement: %s",
            display_name, load_seconds, actual_placement,
        )

        return {
            "success": True,
            "model_name": display_name,
            "load_seconds": load_seconds,
            "plan": plan.to_dict(),
            "facts": facts.to_dict(),
            "placement": actual_placement,
        }

    def _load_via_backend(
        self, facts: ModelFacts, display_name: str, context_tokens: int
    ) -> Dict[str, Any]:
        """Loads a non-safetensors checkpoint through the backend registry."""
        from core.engine.backends import select_backend, explain_unsupported

        backend_cls = select_backend(facts, self.refresh_vram())
        if backend_cls is None:
            error = explain_unsupported(facts)
            self.last_load_error = error
            log.error("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "backend"}

        backend = backend_cls()
        result = backend.load(facts, self.hardware_profile, context_tokens=context_tokens)
        if not result.get("success"):
            self.last_load_error = result.get("error")
            log.error(
                "[SigmaEngine] Backend %s failed: %s",
                backend_cls.name, result.get("error"),
            )
            return result

        self.active_backend_instance = backend
        self.model_facts = facts
        self.loaded_model_name = display_name
        self.placement_plan = None
        self.last_load_error = None
        self._thinking_switch = None
        self.loaded_model = {
            "name": display_name,
            "path": facts.path,
            "format": facts.weight_format,
            "size_gb": round(facts.total_bytes / 2**30, 2),
            "backend": backend_cls.name,
            "placement": result.get("placement", {}),
            "settings": result.get("settings", {}),
            "load_seconds": result.get("load_seconds"),
            "loaded_at": time.time(),
            "status": "ready",
        }

        # A placement that cannot perform is not a silent outcome. The user who
        # loaded a 50GB F16 onto 21GB of VRAM experienced it as "the engine got
        # slower"; the engine knew the ceiling before the first token and said
        # nothing. It is logged loudly and carried in the result so the chat can
        # show it where the wait actually happens.
        warning = (result.get("settings") or {}).get("warning")
        if warning:
            log.warning("[SigmaEngine] %s", warning)
        return result

    @staticmethod
    def _select_attn_implementation() -> Optional[str]:
        """Chooses SDPA (FlashAttention / Memory-Efficient attention) when available."""
        try:
            import torch
            if torch.cuda.is_available():
                return "sdpa"
        except Exception:
            pass
        return None

    def _attempt_load(
        self,
        model_cls,
        target_path: str,
        plan: PlacementPlan,
        compute_dtype,
        has_cuda: bool,
        facts: Optional[ModelFacts] = None,
    ):
        """
        Runs one placement attempt. Returns (model, None) or (None, error_text).
        Errors are returned rather than raised so the caller can replan.
        """
        from transformers import BitsAndBytesConfig

        attn_impl = self._select_attn_implementation()
        load_kwargs: Dict[str, Any] = {
            "low_cpu_mem_usage": True,
            "trust_remote_code": True,
            "dtype": compute_dtype,
        }
        if attn_impl and has_cuda:
            load_kwargs["attn_implementation"] = attn_impl
        device_map: Any = None

        if has_cuda:
            device_map, map_report = self._resolve_device_map(
                model_cls, target_path, facts, plan
            )
            load_kwargs["device_map"] = device_map
            self.last_device_map_report = map_report

            if isinstance(device_map, str):
                # A string strategy passes through the quantizer's own budget
                # shrink, so it needs the compensated numbers.
                load_kwargs["max_memory"] = plan.max_memory_for_string_strategy()

            if plan.offload_folder:
                load_kwargs["offload_folder"] = plan.offload_folder

            quant_config = self._build_quantization_config(
                BitsAndBytesConfig, plan, compute_dtype
            )
            if quant_config is not None:
                load_kwargs["quantization_config"] = quant_config

        log.info(
            "[SigmaEngine] Attempting load: quant=%s device_map=%s offload=%s",
            plan.quantization,
            device_map if isinstance(device_map, str) else "explicit",
            plan.offload_folder,
        )

        try:
            model = model_cls.from_pretrained(target_path, **load_kwargs)
            if not isinstance(device_map, str) and device_map:
                stale = self._stale_placement(model, device_map)
                if stale:
                    # La mappa esplicita nasce da uno scheletro costruito dalla
                    # configurazione, e per un checkpoint multimodale quello
                    # scheletro puo' avere moduli che il modello vero non ha —
                    # torri vision e audio dichiarate nella config e assenti dai
                    # pesi. Le voci che non corrispondono ad alcun modulo
                    # vengono ignorate in silenzio: i moduli restano senza hook,
                    # gli input finiscono su una scheda e la tabella che li
                    # indicizza su un'altra, e la prima risposta muore con
                    # "Expected all tensors to be on the same device".
                    log.warning(
                        "[SigmaEngine] La mappa esplicita cita %d moduli che il "
                        "modello non ha (%s...): la si scarta e si lascia "
                        "collocare ad accelerate.",
                        len(stale), ", ".join(stale[:3]),
                    )
                    del model
                    self._free_cuda_cache()
                    load_kwargs["device_map"] = "sequential"
                    load_kwargs["max_memory"] = plan.max_memory_for_string_strategy()
                    self.last_device_map_report = {
                        "summary": "mappa esplicita scartata: scheletro non "
                                   "corrispondente al checkpoint",
                        "fallback": "sequential",
                        "stale_modules": stale[:20],
                    }
                    model = model_cls.from_pretrained(target_path, **load_kwargs)
            return model, None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def _resolve_device_map(
        self,
        model_cls,
        target_path: str,
        facts: Optional[ModelFacts],
        plan: PlacementPlan,
    ):
        """
        Prefers an explicit, repaired device map; falls back to "sequential".

        The fallback is "sequential" rather than "auto" because "auto" routes
        through get_balanced_memory, which caps every GPU but the last at
        roughly total_size/num_devices. On asymmetric cards that discards the
        larger GPU's capacity: a 16GB + 8GB pair ends up capped near 6GB each
        and the remainder spills to the CPU.
        """
        if facts is not None:
            try:
                from core.engine.transformers_compat import ensure_transformers_compatibility
                ensure_transformers_compatibility()
                from transformers import AutoConfig
                from core.engine.device_map_builder import DeviceMapBuilder

                config = AutoConfig.from_pretrained(
                    target_path, trust_remote_code=True
                )
                built = DeviceMapBuilder.build(model_cls, config, facts, plan)
                if built is not None:
                    return built[0], built[1]
            except Exception as exc:
                log.warning(
                    "[SigmaEngine] Explicit device map unavailable (%s); "
                    "falling back to sequential.", exc,
                )
        return "sequential", None

    @staticmethod
    def _build_quantization_config(
        BitsAndBytesConfig, plan: PlacementPlan, compute_dtype
    ):
        """Builds the bitsandbytes config matching the planner's precision choice."""
        # bitsandbytes refuses any off-GPU dispatch unless this is set, so it
        # must follow the budget actually offered, not the predicted outcome.
        allows_offload = any(
            str(k) in ("cpu", "disk") for k in plan.max_memory
        ) or bool(plan.offload_folder)

        if plan.quantization == "nf4":
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
                llm_int8_enable_fp32_cpu_offload=allows_offload,
            )
        if plan.quantization == "int8":
            return BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_enable_fp32_cpu_offload=allows_offload,
            )
        return None  # bf16: weights load in compute dtype

    @staticmethod
    def _load_tokenizer(AutoTokenizer, AutoProcessor, target_path: str, facts: ModelFacts):
        """
        Loads the tokenizer, preferring the processor for multimodal checkpoints
        so the chat template and special image tokens stay consistent.
        """
        def _ensure_chat_template(tok, facts: ModelFacts):
            if tok is None:
                return tok
            if getattr(tok, "chat_template", None):
                return tok
            mtype = str(getattr(facts, "model_type", "") or "").lower()
            archs = " ".join(str(a).lower() for a in (getattr(facts, "architectures", []) or []))
            if "gemma" in mtype or "gemma" in archs:
                tok.chat_template = (
                    "{{ bos_token }}{% if messages[0]['role'] == 'system' %}{% set loop_messages = messages[1:] %}{% set system_message = messages[0]['content'] %}{% else %}{% set loop_messages = messages %}{% set system_message = '' %}{% endif %}"
                    "{% for message in loop_messages %}"
                    "{% if loop.first and system_message %}{{ '<start_of_turn>user\n' + system_message + '\n\n' + message['content'] | trim + '<end_of_turn>\n' }}"
                    "{% elif message['role'] == 'user' %}{{ '<start_of_turn>user\n' + message['content'] | trim + '<end_of_turn>\n' }}"
                    "{% elif message['role'] == 'assistant' %}{{ '<start_of_turn>model\n' + message['content'] | trim + '<end_of_turn>\n' }}"
                    "{% endif %}"
                    "{% endfor %}"
                    "{% if add_generation_prompt %}{{ '<start_of_turn>model\n' }}{% endif %}"
                )
            elif "qwen" in mtype or "qwen" in archs or "chatglm" in mtype or "glm" in mtype:
                tok.chat_template = (
                    "{% for message in messages %}"
                    "{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n' }}"
                    "{% endfor %}"
                    "{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
                )
            elif "llama" in mtype or "llama" in archs or "mistral" in mtype or "deepseek" in mtype:
                tok.chat_template = (
                    "{% for message in messages %}"
                    "{% if message['role'] == 'system' %}{{ '<|start_header_id|>system<|end_header_id|>\n\n' + message['content'] + '<|eot_id|>' }}"
                    "{% elif message['role'] == 'user' %}{{ '<|start_header_id|>user<|end_header_id|>\n\n' + message['content'] + '<|eot_id|>' }}"
                    "{% elif message['role'] == 'assistant' %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' + message['content'] + '<|eot_id|>' }}"
                    "{% endif %}"
                    "{% endfor %}"
                    "{% if add_generation_prompt %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}{% endif %}"
                )
            return tok

        if facts.is_multimodal and AutoProcessor is not None:
            try:
                processor = AutoProcessor.from_pretrained(
                    target_path, trust_remote_code=True
                )
                tokenizer = getattr(processor, "tokenizer", None)
                if tokenizer is not None:
                    return _ensure_chat_template(tokenizer, facts)
            except Exception as exc:
                log.debug("[SigmaEngine] Processor unavailable, using tokenizer: %s", exc)

        try:
            tok = AutoTokenizer.from_pretrained(target_path, trust_remote_code=True)
            return _ensure_chat_template(tok, facts)
        except Exception as primary_err:
            log.warning("[SigmaEngine] Primary AutoTokenizer loading failed for '%s': %s. Trying direct tokenizer classes...", facts.name, primary_err)

            # Try specific tokenizer class directly (e.g. GemmaTokenizer, LlamaTokenizer)
            try:
                import transformers
                for tok_cls_name in ("GemmaTokenizer", "GemmaTokenizerFast", "LlamaTokenizer", "LlamaTokenizerFast", "PreTrainedTokenizerFast"):
                    tok_cls = getattr(transformers, tok_cls_name, None)
                    if tok_cls is not None:
                        try:
                            tok = tok_cls.from_pretrained(target_path, trust_remote_code=True)
                            log.info("[SigmaEngine] Successfully loaded tokenizer via %s for '%s'", tok_cls_name, facts.name)
                            return _ensure_chat_template(tok, facts)
                        except Exception:
                            continue
            except Exception as direct_err:
                log.debug("[SigmaEngine] Direct tokenizer loading failed: %s", direct_err)

            # Try to borrow tokenizer from other complete local directories in data/models/
            try:
                from core.model_paths import models_dir
                mdir = models_dir()
                if os.path.isdir(mdir):
                    for sub in sorted(os.listdir(mdir)):
                        sub_path = os.path.join(mdir, sub)
                        if os.path.isdir(sub_path) and sub_path != target_path:
                            if os.path.exists(os.path.join(sub_path, "tokenizer.json")) or os.path.exists(os.path.join(sub_path, "tokenizer_config.json")):
                                try:
                                    tok = AutoTokenizer.from_pretrained(sub_path, trust_remote_code=True)
                                    log.info("[SigmaEngine] Successfully borrowed compatible tokenizer from '%s' for '%s'", sub, facts.name)
                                    return _ensure_chat_template(tok, facts)
                                except Exception:
                                    continue
            except Exception as scan_err:
                log.debug("[SigmaEngine] Fallback scan failed: %s", scan_err)

            raise RuntimeError(
                f"File di tokenizer non trovati per '{facts.name}'. "
                f"Il checkpoint su disco ha un download incompleto (manca tokenizer.json). "
                f"Completa il download dal Model Hub oppure seleziona un modello pronto all'uso come 'Qwen--Qwen3.8-27B-GGUF'."
            ) from primary_err

    @staticmethod
    def _describe_placement(model) -> Dict[str, Any]:
        """
        Reports where accelerate actually put the weights.

        This is the ground truth to compare against the plan; a mismatch means
        the budget estimate was wrong.
        """
        device_map = getattr(model, "hf_device_map", None)
        if not device_map:
            try:
                device = str(next(model.parameters()).device)
            except Exception:
                device = "unknown"
            return {"mode": "single_device", "device": device}

        counts: Dict[str, int] = {}
        for device in device_map.values():
            counts[str(device)] = counts.get(str(device), 0) + 1

        return {
            "mode": "sharded",
            "modules_per_device": counts,
            "devices": sorted(counts.keys()),
        }

    def unload(self) -> Dict[str, Any]:
        """
        Releases the model and returns VRAM to the allocator.

        Dropping the reference is not enough: accelerate attaches dispatch hooks
        that hold the module graph alive, so they are removed first. Freed bytes
        are reported so callers can verify the memory actually came back before
        planning the next load.
        """
        previous = self.loaded_model_name
        freed_before = self._vram_used_bytes()
        allocated_before = self._torch_allocated_bytes()

        # The cache holds tensors on the model's devices. Dropping it before
        # the weights is what makes the freed-bytes figure below honest.
        self.prefix_cache.clear("model unloaded")

        # A registry backend owns its own memory (llama.cpp allocates outside
        # the torch allocator), so it must release through its own path.
        if self.active_backend_instance is not None:
            self.active_backend_instance.unload()
            self.active_backend_instance = None

        model = self.model_instance
        if model is not None:
            try:
                from accelerate.hooks import remove_hook_from_module
                remove_hook_from_module(model, recurse=True)
            except Exception as exc:
                log.debug("[SigmaEngine] Hook removal skipped: %s", exc)

        self.model_instance = None
        self.tokenizer_instance = None
        self.loaded_model = None
        self.loaded_model_name = None
        self.model_facts = None
        self.placement_plan = None
        self.last_device_map_report = None
        self._thinking_switch = None
        del model

        self._free_cuda_cache()

        # Two figures, because they answer different questions. The driver delta
        # is what the machine actually gets back and is what a user sees, but
        # other processes move it. The allocator delta counts only tensors this
        # process released, so it is exact regardless of what else is running.
        freed_gb = round((freed_before - self._vram_used_bytes()) / 2**30, 2)
        freed_allocated_gb = round(
            (allocated_before - self._torch_allocated_bytes()) / 2**30, 2
        )
        log.info(
            "[SigmaEngine] Unloaded '%s', released %.2f GB of tensors "
            "(%.2f GB returned to the driver)",
            previous, freed_allocated_gb, freed_gb,
        )
        return {
            "success": True,
            "unloaded": previous,
            "freed_vram_gb": freed_gb,
            "freed_allocated_gb": freed_allocated_gb,
        }

    @staticmethod
    def _free_cuda_cache() -> None:
        """
        Returns cached blocks on every GPU to the driver.

        empty_cache() only releases the caching allocator's pool for the current
        device, so on a multi-GPU split it leaves the secondary cards holding
        gigabytes that the driver still counts as used. The next plan then reads
        a machine with far less free VRAM than it really has.
        """
        try:
            import gc
            import torch
            gc.collect()
            if not torch.cuda.is_available():
                return
            for index in range(torch.cuda.device_count()):
                with torch.cuda.device(index):
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
        except Exception as exc:
            log.debug("[SigmaEngine] Cache release skipped: %s", exc)

    @staticmethod
    def _torch_allocated_bytes() -> int:
        """Bytes of live tensors this process holds, across all CUDA devices."""
        try:
            import torch
            if not torch.cuda.is_available():
                return 0
            return sum(
                torch.cuda.memory_allocated(i)
                for i in range(torch.cuda.device_count())
            )
        except Exception:
            return 0

    @staticmethod
    def _vram_used_bytes() -> int:
        """Total bytes in use across all CUDA devices, or 0 without CUDA."""
        try:
            import torch
            if not torch.cuda.is_available():
                return 0
            total = 0
            for idx in range(torch.cuda.device_count()):
                free, capacity = torch.cuda.mem_get_info(idx)
                total += capacity - free
            return total
        except Exception:
            return 0

    # ---------------------------------------------------------- generation

    #: How long a queued request waits for the engine before giving up. Longer
    #: than any single answer should take, short enough that a wedged
    #: generation surfaces as an error instead of a hung tab.
    GENERATION_QUEUE_TIMEOUT = 600.0

    def generate_stream(
        self,
        prompt: str = "",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        model_name: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
        thinking: Optional[bool] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Serialises access to the engine, then streams the answer.

        Everything below the lock assumes it owns the resident model: it may
        unload it, replace it, and mutate its KV cache. Two threads doing that
        at once is not slower, it is wrong, so the queue is part of the
        contract rather than a tuning choice.
        """
        with self._waiting_lock:
            self._generation_waiting += 1
            position = self._generation_waiting

        acquired = self._generation_lock.acquire(blocking=False)
        try:
            if not acquired:
                # Say so rather than appearing frozen: on a single-model engine
                # a wait is normal, and a silent one reads as a crash.
                yield {
                    "token": "",
                    "status": True,
                    "notice": True,
                    "model_status": (
                        f"⏳ Motore occupato da un'altra richiesta"
                        f"{f' ({position - 1} in attesa)' if position > 1 else ''}..."
                    ),
                    "queue_position": position,
                    "done": False,
                }
                acquired = self._generation_lock.acquire(
                    timeout=self.GENERATION_QUEUE_TIMEOUT
                )
        finally:
            with self._waiting_lock:
                self._generation_waiting -= 1

        if not acquired:
            yield {
                "token": (
                    "\n\n⏳ **Motore occupato**: la richiesta precedente non si è "
                    f"conclusa entro {int(self.GENERATION_QUEUE_TIMEOUT)}s. "
                    "Riprova, oppure scarica il modello dal Model Hub per "
                    "liberare il motore."
                ),
                "token_index": 1,
                "notice": True,
                "error": "engine_busy",
                "done": True,
            }
            return

        try:
            yield from self._generate_stream_locked(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
                messages=messages,
                params=params,
                cancel=cancel,
                thinking=thinking,
                tools=tools,
                tool_choice=tool_choice,
            )
        finally:
            self._generation_lock.release()

    def _generate_stream_locked(
        self,
        prompt: str = "",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        model_name: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
        thinking: Optional[bool] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        retried_after_oom: bool = False,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streams tokens from native inference with live throughput metrics.

        `messages` carries the whole conversation -- system prompt, attached
        file context, prior turns and tool results. Passing only `prompt` and
        `system_prompt` collapses that to a single exchange, so the model loses
        everything the user has already said.

        `params` carries the whole sampler. Callers that predate it still pass
        temperature and max_tokens, which are promoted into the same object, so
        there is exactly one place where sampling is decided either way.

        `cancel` is checked between tokens: when the reader goes away the
        generation stops instead of running to the token budget with nobody
        listening.
        """
        t_start = time.perf_counter()
        token_count = 0

        if params is None:
            params = SamplingParams.resolve(model_name=model_name or "").with_overrides(
                temperature=temperature, max_tokens=max_tokens
            )

        model_info = self.find_valid_model_directory(model_name or self.loaded_model_name)
        target_model = model_info[1] if model_info else (model_name or self.loaded_model_name)

        if target_model is None:
            yield from self._yield_no_model_message()
            return

        def _clean_m_name(name):
            if not name: return ""
            return str(name).strip().lower().replace(".gguf", "").replace("--", "/").split("/")[-1].split("\\")[-1]

        is_already_resident = (
            self.has_resident_model and (
                _clean_m_name(self.loaded_model_name) == _clean_m_name(target_model) or
                _clean_m_name(self.loaded_model_name) == _clean_m_name(model_name) or
                (model_info and self.loaded_model and os.path.abspath(self.loaded_model.get("path", "")) == os.path.abspath(model_info[0]))
            )
        )

        if not is_already_resident:
            yield {
                "token": "",
                "status": True,
                "type": "status",
                "model_status": f"⏳ Caricamento pesi modello `{target_model}` in memoria/VRAM...",
                "text": f"⏳ Caricamento pesi modello `{target_model}` in memoria/VRAM...",
                "loading": True,
                "notice": True,
                "done": False,
            }
            result = self.load_native_model(target_model)
            if not result.get("success"):
                err_text = self._format_load_failure(target_model, result)
                yield {
                    "token": err_text,
                    "message": err_text,
                    "token_index": 1,
                    "notice": True,
                    "error": "load_failed",
                    "done": True,
                }
                return

            load_sec = result.get("load_seconds") or round(time.perf_counter() - t_start, 2)
            load_ms = round(load_sec * 1000, 1)

            placement_warning = (result.get("settings") or {}).get("warning")
            yield {
                "token": "",
                "status": True,
                "load_duration_ms": load_ms,
                "load_seconds": load_sec,
                "model_status": f"⚡ Modello caricato in {load_sec}s",
                "placement_warning": placement_warning,
                "done": False,
            }
            if placement_warning:
                # Shown in the answer bubble, before the first token: this is
                # the moment the user is about to start waiting, and the only
                # moment where knowing why is still useful.
                yield {
                    "token": f"> ⚠️ {placement_warning}\n\n",
                    "status": True,
                    "notice": True,
                    "done": False,
                }

            # Throughput must measure generation, not the load before it.
            t_start = time.perf_counter()

        # A registry backend runs its own generation loop; it owns the model.
        if self.active_backend_instance is not None:
            yield from self.active_backend_instance.generate_stream(
                prompt,
                system_prompt=system_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                messages=self._as_messages(prompt, system_prompt, messages),
                params=params,
                cancel=cancel,
                thinking=thinking,
                tools=tools,
                tool_choice=tool_choice,
            )
            return

        try:
            import torch
            from transformers import TextIteratorStreamer

            streamer = TextIteratorStreamer(
                self.tokenizer_instance,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=300.0,
            )

            inputs = self._build_inputs(
                self._as_messages(prompt, system_prompt, messages),
                thinking=thinking,
            )

            # One sampler, resolved once, adapted here. The token budget still
            # has the last word: it knows what is left of the context window.
            gen_kwargs: Dict[str, Any] = dict(
                **inputs,
                **params.for_transformers(self.tokenizer_instance),
                streamer=streamer,
                use_cache=True,
            )
            gen_kwargs["max_new_tokens"] = self._token_budget(
                params.max_tokens, inputs
            )

            # Reuse the KV of whatever this prompt shares with the last one.
            # In a conversation that is the entire history: the model then
            # prefills only the newest turn instead of re-reading everything
            # it read a minute ago.
            prompt_ids = inputs["input_ids"][0].tolist()
            reused_tokens = 0
            if self.prefix_cache_enabled and self.prefix_cache_retained:
                past, reused_tokens = self.prefix_cache.take(
                    prompt_ids, self.loaded_model_name or ""
                )
                if past is not None:
                    gen_kwargs["past_key_values"] = past
                    # generate() must return the cache it leaves behind, or the
                    # next turn has nothing to crop.
                    gen_kwargs["return_dict_in_generate"] = True
            self.prefix_cache.tokens_prefilled += max(
                len(prompt_ids) - reused_tokens, 0
            )
            if (self.prefix_cache_enabled and self.prefix_cache_retained
                    and "return_dict_in_generate" not in gen_kwargs):
                gen_kwargs["return_dict_in_generate"] = True

            if params.seed is not None:
                from transformers import set_seed
                set_seed(params.seed)

            stopper = stopping_criteria_for(cancel)
            if stopper is not None:
                gen_kwargs["stopping_criteria"] = stopper

            pad_id = getattr(self.tokenizer_instance, "pad_token_id", None)
            eos_id = getattr(self.tokenizer_instance, "eos_token_id", None)
            gen_kwargs["pad_token_id"] = pad_id if pad_id is not None else eos_id

            log.debug("[SigmaEngine] Sampling: %s", params.summary())

            generation_error: List[BaseException] = []
            generation_output: List[Any] = []

            def _run_generate():
                try:
                    with torch.inference_mode():
                        result = self.model_instance.generate(**gen_kwargs)
                    generation_output.append(result)
                except BaseException as exc:  # surfaced to the caller below
                    log.error("[SigmaEngine] Generation thread failed: %s", exc)
                    generation_error.append(exc)
                    # A failed generation leaves a cache of unknown length; the
                    # next turn must not crop something it cannot trust.
                    self.prefix_cache.clear("generation failed")
                    streamer.end()

            thread = threading.Thread(target=_run_generate, daemon=True)
            thread.start()

            first_token_sent = False
            first_token_at = t_start
            for token_text in streamer:
                # The stopping criterion already told generate to wind down;
                # leaving the consumer loop as well means the caller stops
                # paying for tokens nobody will read. The streamer queue is
                # unbounded, so the producer never blocks on our exit.
                if is_cancelled(cancel):
                    break
                if not token_text:
                    continue
                token_count += 1
                now = time.perf_counter()

                # Throughput is reported for the decode phase alone. Prompt
                # processing is a one-off cost that scales with the prompt, and
                # folding it in makes a healthy model look several times slower
                # as soon as the conversation carries real context. It is
                # reported separately, as time-to-first-token.
                if not first_token_sent:
                    first_token_at = now
                    chunk = {
                        "token": token_text,
                        "token_index": token_count,
                        "ttft_ms": round((now - t_start) * 1000, 1),
                        "done": False,
                    }
                    first_token_sent = True
                else:
                    decode_seconds = max(now - first_token_at, 1e-3)
                    chunk = {
                        "token": token_text,
                        "token_index": token_count,
                        "speed_tok_s": round((token_count - 1) / decode_seconds, 1),
                        "done": False,
                    }
                yield chunk

            thread.join(timeout=5.0)

            self._retain_prefix_cache(generation_output, cancel)

            if generation_error:
                failure = generation_error[0]

                # An out-of-memory before the first token is recoverable: the
                # retained cache and the allocator's free blocks are both giving
                # up memory the retry can use. Once tokens have reached the user
                # a retry would repeat them, so the answer is the explanation.
                if (self._is_out_of_memory(failure) and token_count == 0
                        and not retried_after_oom):
                    log.warning(
                        "[SigmaEngine] Out of memory before the first token; "
                        "releasing the prefix cache and retrying once."
                    )
                    self.prefix_cache.clear("out of memory")
                    self.prefix_cache_retained = False
                    self._free_cuda_cache()
                    yield {
                        "token": "",
                        "status": True,
                        "model_status": "♻️ VRAM esaurita: libero la cache e riprovo...",
                        "done": False,
                    }
                    yield from self.generate_stream(
                        prompt=prompt, system_prompt=system_prompt,
                        temperature=temperature, max_tokens=max_tokens,
                        model_name=model_name, messages=messages,
                        params=params, cancel=cancel, thinking=thinking,
                        tools=tools, tool_choice=tool_choice,
                        retried_after_oom=True,
                    )
                    return

                yield {
                    "token": self._explain_generation_failure(failure),
                    "token_index": token_count + 1,
                    "notice": True,
                    "error": "generation_failed",
                    "done": True,
                }
                return

            now = time.perf_counter()
            decode_seconds = max(now - first_token_at, 1e-3)
            yield {
                "token": "",
                "token_index": token_count + 1,
                "speed_tok_s": round(max(token_count - 1, 1) / decode_seconds, 1),
                "total_tokens": token_count,
                "prefill_ms": round((first_token_at - t_start) * 1000, 1),
                "cancelled": is_cancelled(cancel),
                "sampling": params.to_dict(),
                "prefix_reused_tokens": reused_tokens,
                "prompt_tokens": len(prompt_ids),
                "done": True,
            }

        except Exception as exc:
            self.prefix_cache.clear("generation error")
            log.error("[SigmaEngine] Generation error: %s", exc, exc_info=True)
            yield {
                "token": self._explain_generation_failure(exc),
                "token_index": token_count + 1,
                "notice": True,
                "error": "generation_failed",
                "done": True,
            }

    # ------------------------------------------------------ batched inference

    def _ensure_resident(self, model_name: Optional[str]) -> Dict[str, Any]:
        """Loads the requested weights unless they are already the resident ones."""
        model_info = self.find_valid_model_directory(model_name or self.loaded_model_name)
        target = model_info[1] if model_info else (model_name or self.loaded_model_name)
        if target is None:
            return {"success": False, "error": "Nessun modello locale disponibile."}

        def _clean(name):
            if not name:
                return ""
            return (str(name).strip().lower().replace(".gguf", "").replace("--", "/")
                    .split("/")[-1].split("\\")[-1])

        resident = (
            self.has_resident_model and (
                _clean(self.loaded_model_name) == _clean(target)
                or _clean(self.loaded_model_name) == _clean(model_name)
            )
        )
        if resident:
            return {"success": True, "model": target}

        result = self.load_native_model(target)
        result.setdefault("model", target)
        if not result.get("success"):
            # The same diagnosis the chat path renders, rather than a bare
            # exception string: it names the stage and what to do about it.
            result["message"] = self._format_load_failure(target, result)
        return result

    def auto_batch_size(self, requested: int = 0) -> int:
        """
        How many prompts to run together, from what the device has left.

        The KV cache of a batch grows linearly with the batch, so the ceiling is
        free memory rather than a constant. A machine that cannot spare anything
        gets 1, which is the behaviour that existed before batching and is still
        correct -- just slow.
        """
        # Checked before anything a caller can ask for: a registry backend
        # decodes one sequence per context, so a batch of sixteen is not a
        # preference it can decline, it is a number that would be reported in
        # the UI ("x16") while the work happened one prompt at a time.
        if self.active_backend_instance is not None:
            return 1

        if requested and requested > 0:
            return max(1, min(int(requested), 64))

        env = os.environ.get("SIGMA_EVAL_BATCH")
        if env:
            try:
                return max(1, min(int(env), 64))
            except ValueError:
                pass

        profile = {}
        try:
            profile = self.refresh_vram() or {}
        except Exception as exc:
            log.debug("[SigmaEngine] Batch sizing without a fresh probe: %s", exc)

        accelerators = profile.get("accelerators") or []
        free_gb = max((a.get("free_vram_gb") or 0.0) for a in accelerators) if accelerators else 0.0

        if free_gb <= 0:
            # CPU or an unreadable device: RAM is the budget, and a wrong guess
            # here swaps rather than merely slowing down.
            available = (profile.get("ram") or {}).get("available_gb") or 0
            return 2 if available >= 16 else 1

        for threshold, size in ((24, 32), (12, 16), (6, 8), (3, 4), (1.5, 2)):
            if free_gb >= threshold:
                return size
        return 1

    def generate_batch(
        self,
        conversations: List[List[Dict[str, str]]],
        params: Optional[SamplingParams] = None,
        model_name: Optional[str] = None,
        thinking: Optional[bool] = None,
        batch_size: int = 0,
        cancel: Any = None,
        on_result=None,
    ) -> List[Dict[str, Any]]:
        """
        Answers many independent prompts in as few forward passes as possible.

        This is the shape a benchmark actually has -- thousands of prompts that
        do not depend on each other -- and running it one prompt at a time is
        what makes a run take hours while the GPU sits at single-digit
        utilisation. It is deliberately NOT used for chat: a batch cannot be
        streamed, and a chat that answers all at once after ten seconds reads
        as broken even when it is faster.

        Results come back in the caller's order regardless of the order they
        were computed in; the batches themselves are formed by prompt length,
        because padding a short prompt up to a long one is compute spent on
        nothing.
        """
        results: List[Dict[str, Any]] = [
            {"index": i, "text": "", "tokens": 0, "finish_reason": "stop", "error": ""}
            for i in range(len(conversations))
        ]
        if not conversations:
            return results

        acquired = self._generation_lock.acquire(timeout=self.GENERATION_QUEUE_TIMEOUT)
        if not acquired:
            for entry in results:
                entry["error"] = "Motore occupato da un'altra richiesta."
            return results

        try:
            load = self._ensure_resident(model_name)
            if not load.get("success"):
                message = load.get("error", "caricamento non riuscito")
                for entry in results:
                    entry["error"] = f"Caricamento modello fallito: {message}"
                    # A caller running thousands of prompts must be able to tell
                    # "this model will never answer" from "this prompt failed",
                    # and stop rather than write the same row a thousand times.
                    entry["fatal"] = True
                    entry["diagnosis"] = load.get("message", "")
                return results

            if params is None:
                params = SamplingParams.resolve(
                    model_name=model_name or self.loaded_model_name or ""
                )

            if self.active_backend_instance is not None:
                return self._generate_batch_sequential(
                    conversations, params, results, thinking, cancel, on_result
                )
            return self._generate_batch_transformers(
                conversations, params, results, thinking,
                self.auto_batch_size(batch_size), cancel, on_result,
            )
        finally:
            self._generation_lock.release()

    def _generate_batch_sequential(
        self, conversations, params, results, thinking, cancel, on_result,
    ) -> List[Dict[str, Any]]:
        """
        One prompt at a time, for a backend that owns its own decode loop.

        llama.cpp serves a single sequence per context, so there is no batch to
        form. The path exists so callers have one API: they ask for a batch and
        get answers, fast where the runtime allows it and correct everywhere.
        """
        backend = self.active_backend_instance
        slots = 1
        try:
            slots = max(1, int(backend.parallel_slots()))
        except Exception as exc:
            log.debug("[SigmaEngine] Slot paralleli non dichiarati: %s", exc)

        if slots > 1 and len(conversations) > 1:
            return self._generate_batch_over_slots(
                conversations, params, results, thinking, cancel, on_result, slots
            )

        for index, conversation in enumerate(conversations):
            if is_cancelled(cancel):
                results[index]["error"] = "annullato"
                continue
            pieces: List[str] = []
            tokens = 0
            failure = ""
            timed_out = False
            try:
                for chunk in backend.generate_stream(
                    prompt="",
                    messages=conversation,
                    temperature=params.temperature,
                    max_tokens=params.max_tokens,
                    params=params,
                    cancel=cancel,
                    thinking=thinking,
                ):
                    if chunk.get("notice") or chunk.get("error"):
                        failure = failure or str(chunk.get("token") or "errore backend")
                        timed_out = timed_out or chunk.get("error") == "timeout"
                        continue
                    token = chunk.get("token") or ""
                    if token:
                        pieces.append(token)
                    if chunk.get("done"):
                        tokens = int(chunk.get("total_tokens") or 0)
                        if chunk.get("finish_reason") == "timeout":
                            timed_out = True
                            failure = failure or "generazione oltre il tetto di tempo"
            except Exception as exc:
                failure = f"{type(exc).__name__}: {exc}"

            text = "".join(pieces)
            # Il testo prodotto prima del guasto si tiene. Una generazione con
            # catena di ragionamento che scade dopo millecinquecento token ha
            # spesso gia' scritto la risposta: buttarla e contare l'item come
            # errore misura il timeout, non il modello.
            results[index].update({
                "text": text,
                "tokens": tokens or len(text.split()),
                "error": failure if not text else "",
                "warning": failure if text else "",
                "finish_reason": "timeout" if timed_out else ("stop" if not failure else "error"),
            })
            if on_result:
                on_result(results[index])
        return results

    def _in_shrinking_batches(self, order, batch_size, run, on_error, cancel=None,
                              on_done=None, label="Batch"):
        """
        Runs a list of items in groups, shrinking the group when memory says so.

        The shrink is **sticky**. Before, only the group that ran out of memory
        was halved, and the next one started again at the original size -- so
        every group paid an out-of-memory, split, and retried. From the outside
        that is a run which processes many at once, then fewer, then fewer
        still, then one at a time, then breaks: each step is a real allocation
        failure that the previous one had already predicted.

        Once the device has said no at sixteen, it will say no at sixteen again.
        """
        size = max(1, int(batch_size or 1))
        queue = list(order)

        while queue:
            group, queue = queue[:size], queue[size:]
            if is_cancelled(cancel):
                on_error(group, "annullato")
                continue
            try:
                run(group)
            except Exception as exc:
                if self._is_out_of_memory(exc) and len(group) > 1:
                    size = max(1, len(group) // 2)
                    log.warning(
                        "[SigmaEngine] %s: memoria esaurita con %d prompt; "
                        "si prosegue a %d.", label, len(group), size,
                    )
                    self._free_cuda_cache()
                    queue = group + queue
                    continue
                log.error("[SigmaEngine] %s fallito: %s", label, exc, exc_info=True)
                on_error(group, f"{type(exc).__name__}: {exc}")
            if on_done:
                on_done(group)

    def _generate_batch_over_slots(
        self, conversations, params, results, thinking, cancel, on_result, slots,
    ) -> List[Dict[str, Any]]:
        """
        Several prompts at once through a backend that serves several at once.

        The GGUF server is started with `-np 4 --cont-batching`: four slots,
        continuous batching, already paid for. Feeding it one request at a time
        left three of them idle for the whole run -- which is most of why a
        hundred-question suite on a quantised model took hours while the cards
        showed almost no work.

        Not used for the in-process llama.cpp path, which has one context and is
        not thread-safe: there, concurrency is not slower, it is wrong.
        """
        import concurrent.futures

        backend = self.active_backend_instance
        lock = threading.Lock()
        degradato = {"seq": False}

        def _one(index: int) -> None:
            if is_cancelled(cancel):
                results[index]["error"] = "annullato"
                return
            self._stream_one_into(backend, conversations[index], params,
                                  thinking, cancel, results[index])
            if results[index].get("finish_reason") == "timeout":
                degradato["seq"] = True
            if on_result:
                with lock:
                    on_result(results[index])

        rimasti = list(range(len(conversations)))
        while rimasti:
            larghezza = 1 if degradato["seq"] else slots
            gruppo, rimasti = rimasti[:larghezza], rimasti[larghezza:]
            if larghezza == 1:
                _one(gruppo[0])
                continue
            with concurrent.futures.ThreadPoolExecutor(max_workers=larghezza) as pool:
                futures = [pool.submit(_one, i) for i in gruppo]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as exc:
                        log.error("[SigmaEngine] Slot fallito: %s", exc, exc_info=True)
            if degradato["seq"]:
                # Una scadenza con piu' richieste in volo dice che questo
                # server, con questo modello, non regge il parallelismo che
                # dichiara. Si prosegue una alla volta invece di raccogliere
                # scadenze a gruppi di quattro fino alla fine del campione.
                log.warning("[SigmaEngine] Scadenza con %d richieste in volo: "
                            "si prosegue in sequenza.", larghezza)
        return results

    def _stream_one_into(self, backend, conversation, params, thinking, cancel,
                         entry: Dict[str, Any]) -> None:
        """Drains one backend generation into one result row."""
        pieces: List[str] = []
        tokens = 0
        failure = ""
        timed_out = False
        try:
            for chunk in backend.generate_stream(
                prompt="",
                messages=conversation,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                params=params,
                cancel=cancel,
                thinking=thinking,
            ):
                if chunk.get("notice") or chunk.get("error"):
                    failure = failure or str(chunk.get("token") or "errore backend")
                    timed_out = timed_out or chunk.get("error") == "timeout"
                    continue
                token = chunk.get("token") or ""
                if token:
                    pieces.append(token)
                if chunk.get("done"):
                    tokens = int(chunk.get("total_tokens") or 0)
                    if chunk.get("finish_reason") == "timeout":
                        timed_out = True
                        failure = failure or "generazione oltre il tetto di tempo"
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"

        text = "".join(pieces)
        entry.update({
            "text": text,
            "tokens": tokens or len(text.split()),
            "error": failure if not text else "",
            "warning": failure if text else "",
            "finish_reason": "timeout" if timed_out else ("stop" if not failure else "error"),
        })

    def _generate_batch_transformers(
        self, conversations, params, results, thinking, batch_size, cancel, on_result,
    ) -> List[Dict[str, Any]]:
        """Real batching: one `generate` call per group of padded prompts."""
        import torch

        tokenizer = self.tokenizer_instance
        prompts = [self._render_chat(conv, thinking) for conv in conversations]

        # Sorted by token count so a batch is made of prompts of similar size.
        # Padding is computed on the longest member, so mixing a 40-token
        # question with a 4000-token one makes the short one cost the long one.
        lengths = [len(tokenizer(p, add_special_tokens=False)["input_ids"]) for p in prompts]
        order = sorted(range(len(prompts)), key=lambda i: lengths[i])

        def _fallito(group, message):
            for index in group:
                results[index]["error"] = message

        def _consegna(group):
            if on_result:
                for index in group:
                    on_result(results[index])

        self._in_shrinking_batches(
            order, batch_size,
            run=lambda group: self._run_one_batch(group, prompts, params,
                                                  results, tokenizer),
            on_error=_fallito, cancel=cancel, on_done=_consegna,
            label="Generazione a lotti",
        )
        return results

    def _run_one_batch(self, group, prompts, params, results, tokenizer) -> None:
        """Tokenises, generates and decodes a single padded group."""
        import torch

        previous_side = getattr(tokenizer, "padding_side", "right")
        pad_id = getattr(tokenizer, "pad_token_id", None)
        eos_id = getattr(tokenizer, "eos_token_id", None)
        if pad_id is None:
            # Padding on the right of a decoder-only model puts pad tokens
            # between the prompt and the answer; padding left keeps every
            # sequence's last real token at the last position, which is where
            # generation continues from.
            tokenizer.pad_token = getattr(tokenizer, "eos_token", None)
            pad_id = getattr(tokenizer, "pad_token_id", None) or eos_id
        tokenizer.padding_side = "left"

        try:
            batch = tokenizer(
                [prompts[i] for i in group],
                return_tensors="pt", padding=True, add_special_tokens=False,
            )
        finally:
            tokenizer.padding_side = previous_side

        device = self._input_device()
        batch = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch.items()}

        prompt_len = int(batch["input_ids"].shape[-1])
        gen_kwargs: Dict[str, Any] = dict(
            **batch,
            **params.for_transformers(tokenizer),
            use_cache=True,
        )
        gen_kwargs["max_new_tokens"] = self._token_budget(params.max_tokens, batch)
        gen_kwargs["pad_token_id"] = pad_id if pad_id is not None else eos_id

        if params.seed is not None:
            from transformers import set_seed
            set_seed(params.seed)

        t0 = time.perf_counter()
        with torch.inference_mode():
            output = self.model_instance.generate(**gen_kwargs)
        elapsed = max(time.perf_counter() - t0, 1e-3)

        sequences = getattr(output, "sequences", output)
        generated_total = 0
        for row, index in enumerate(group):
            new_ids = sequences[row][prompt_len:]
            produced = _decoded_length(new_ids.tolist(), eos_id)
            text = tokenizer.decode(new_ids, skip_special_tokens=True)
            trimmed, hit_stop = _cut_at_stop(text, params.stop)
            generated_total += produced
            results[index].update({
                "text": trimmed.strip(),
                "tokens": produced,
                "finish_reason": "stop" if (hit_stop or produced < gen_kwargs["max_new_tokens"])
                                 else "length",
                "prompt_tokens": prompt_len,
            })

        # Throughput of the batch as a whole: what the run actually costs. Per
        # prompt it is this divided by the batch, which is the number that made
        # batching worth doing and must therefore be the number reported.
        for index in group:
            results[index]["batch_size"] = len(group)
            results[index]["batch_tokens_per_sec"] = round(generated_total / elapsed, 2)
            results[index]["tokens_per_sec"] = round(
                results[index]["tokens"] / elapsed, 2
            )

    # ---------------------------------------------------- constrained choice

    # ------------------------------------------------- continuation scoring

    #: Una coppia palese, usata per accorgersi che il punteggio a
    #: verosimiglianza e' fuori scala prima che diventi una tabella di numeri.
    CALIBRATION_PAIR = ("The capital of France is", " Paris")
    #: Sotto questa log-verosimiglianza per un token cosi' prevedibile, il
    #: modello non sta rispondendo male: sta lavorando fuori dalla propria
    #: distribuzione. Un token mancante all'inizio della sequenza basta.
    CALIBRATION_FLOOR = -8.0

    def calibration_check(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Chiede al modello una cosa che sa di sicuro, e guarda quanto ci crede.

        Serve perche' un punteggio a verosimiglianza sbagliato non ha l'aspetto
        di un errore: ha l'aspetto di un modello mediocre. Il caso reale che ha
        motivato questo controllo: il tokenizer di Gemma dichiara un token di
        inizio sequenza e poi non lo antepone, nemmeno quando glielo si chiede.
        Senza quel token " Paris" dopo "The capital of France is" valeva -18.7 —
        sette miliardesimi di probabilita' — e le opzioni di ogni quesito
        finivano ordinate dal rumore, producendo punteggi bassi ma credibili.
        """
        context, continuation = self.CALIBRATION_PAIR
        rows = self.continuation_logprobs([(context, continuation)],
                                          model_name=model_name, batch_size=1)
        if not rows or rows[0].get("error"):
            return {"ok": True, "skipped": rows[0].get("error") if rows else "no result"}

        logprob = float(rows[0].get("logprob", 0.0))
        sano = logprob >= self.CALIBRATION_FLOOR
        if not sano:
            log.warning(
                "[SigmaEngine] Calibrazione sospetta: %r vale %.2f di "
                "log-verosimiglianza (atteso sopra %.1f). I punteggi a "
                "verosimiglianza di questo modello non sono affidabili.",
                continuation, logprob, self.CALIBRATION_FLOOR,
            )
        return {"ok": sano, "logprob": round(logprob, 3),
                "floor": self.CALIBRATION_FLOOR}

    def continuation_logprobs(
        self,
        pairs: List[Tuple[str, str]],
        model_name: Optional[str] = None,
        batch_size: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        How likely each continuation is, given its context.

        This is the measurement HellaSwag, ARC and TruthfulQA are actually
        published on, and it asks a different question from letter-reading. The
        model is not asked to pick a label; each candidate ending is scored as
        text, and the one it finds most probable wins. A model that has never
        seen a lettered multiple-choice format still answers this correctly,
        which is the point -- the benchmark is about world knowledge and
        commonsense, not about following an answer-format instruction.

        Returns, per pair: the summed log-probability, the token count and the
        character count, so the caller can normalise the way its protocol says.
        Normalising matters: without it the shortest ending wins almost every
        time, because every extra token can only subtract probability.
        """
        results: List[Dict[str, Any]] = [
            {"index": i, "logprob": float("-inf"), "tokens": 0,
             "characters": len(text or ""), "error": ""}
            for i, (_, text) in enumerate(pairs)
        ]
        if not pairs:
            return results

        acquired = self._generation_lock.acquire(timeout=self.GENERATION_QUEUE_TIMEOUT)
        if not acquired:
            for entry in results:
                entry["error"] = "Motore occupato da un'altra richiesta."
            return results

        try:
            load = self._ensure_resident(model_name)
            if not load.get("success"):
                for entry in results:
                    entry["error"] = f"Caricamento modello fallito: {load.get('error')}"
                    entry["fatal"] = True
                    entry["diagnosis"] = load.get("message", "")
                return results

            if self.active_backend_instance is not None:
                for entry in results:
                    entry["error"] = "unsupported_backend"
                return results

            return self._continuation_logprobs_transformers(
                pairs, results, self.auto_batch_size(batch_size)
            )
        finally:
            self._generation_lock.release()

    def _continuation_logprobs_transformers(
        self, pairs, results, batch_size,
    ) -> List[Dict[str, Any]]:
        import torch

        tokenizer = self.tokenizer_instance
        encoded: List[Tuple[List[int], List[int]]] = []
        for position, (context, continuation) in enumerate(pairs):
            # `add_special_tokens=True` non e' un dettaglio: la famiglia Gemma
            # (e Llama, e altre) vuole il token di inizio sequenza, e senza di
            # quello le statistiche del primo strato sono fuori scala. Si vede
            # subito e si spiega male: " Paris" dopo "The capital of France is"
            # valeva -18.7 di log-verosimiglianza, cioe' una probabilita' di
            # sette miliardesimi, e le opzioni finivano ordinate dal rumore.
            # Il percorso a lettere non ne soffriva perche' passa dal template
            # di chat, che il token di inizio ce l'ha dentro.
            context_ids = _with_bos(tokenizer,
                                    tokenizer.encode(context, add_special_tokens=True))
            # The continuation is tokenized *in context*, not alone: a BPE
            # tokenizer merges across the boundary, and scoring the standalone
            # tokenization would score a sequence the model would never emit.
            whole_ids = _with_bos(tokenizer,
                                  tokenizer.encode(context + continuation,
                                                   add_special_tokens=True))
            overlap = 0
            limit = min(len(context_ids), len(whole_ids))
            while overlap < limit and context_ids[overlap] == whole_ids[overlap]:
                overlap += 1
            continuation_ids = whole_ids[overlap:]
            if not continuation_ids:
                results[position]["error"] = "continuazione vuota"
                encoded.append(([], []))
                continue
            encoded.append((whole_ids[:overlap], continuation_ids))
            results[position]["tokens"] = len(continuation_ids)

        order = sorted((i for i, (_, c) in enumerate(encoded) if c),
                       key=lambda i: len(encoded[i][0]) + len(encoded[i][1]))
        def _fallito(group, message):
            for index in group:
                results[index]["error"] = message

        self._in_shrinking_batches(
            order, batch_size,
            run=lambda group: self._score_one_continuation_batch(
                group, encoded, results, tokenizer),
            on_error=_fallito, label="Confronto delle continuazioni",
        )
        return results

    def _score_one_continuation_batch(self, group, encoded, results, tokenizer) -> None:
        """One padded forward pass; reads the log-probability of each target token."""
        import torch

        sequences = [encoded[i][0] + encoded[i][1] for i in group]
        width = max(len(s) for s in sequences)
        pad_id = getattr(tokenizer, "pad_token_id", None)
        if pad_id is None:
            pad_id = getattr(tokenizer, "eos_token_id", None) or 0

        # Left padding again, for the same reason as everywhere else: it keeps
        # every row's real tokens contiguous at the end, so one offset locates
        # the continuation in every row.
        input_ids, attention = [], []
        for sequence in sequences:
            padding = width - len(sequence)
            input_ids.append([pad_id] * padding + sequence)
            attention.append([0] * padding + [1] * len(sequence))

        device = self._input_device()
        batch = {
            "input_ids": torch.tensor(input_ids).to(device),
            "attention_mask": torch.tensor(attention).to(device),
        }

        with torch.inference_mode():
            logits = self.model_instance(**batch).logits.float()
        log_probs = torch.log_softmax(logits, dim=-1)

        for row, index in enumerate(group):
            context_ids, continuation_ids = encoded[index]
            # Position of the last context token in the padded row. The logits
            # there predict the first continuation token, and so on.
            start = width - len(continuation_ids) - 1
            total = 0.0
            for offset, token in enumerate(continuation_ids):
                total += float(log_probs[row, start + offset, int(token)].item())
            results[index]["logprob"] = total

    def choice_logits(
        self,
        conversations: List[List[Dict[str, str]]],
        letters: List[List[str]],
        model_name: Optional[str] = None,
        thinking: Optional[bool] = None,
        batch_size: int = 0,
        answer_prefix: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Scores the option letters directly, instead of reading them back out of prose.

        A multiple-choice benchmark asks the model to pick one of N labels. The
        generative protocol turns that into: produce up to a thousand tokens of
        reasoning, then hope a regex recovers the label -- which is where both
        the cost and the ambiguous verdicts come from. A model that writes "the
        answer is A, so H is wrong" has not answered twice, it has answered once
        and been misread.

        Reading the logits at the first answer position removes the question.
        There is exactly one distribution, the letters are ranked by it, and the
        winner is a number rather than an interpretation. One forward pass, no
        decoding, and the same answer every time.

        Returns, per item: the chosen letter, the normalised probability of each
        letter, and the margin over the runner-up -- the margin being what tells
        a genuine choice from a coin toss the parser would have had to guess at.
        """
        outcomes: List[Dict[str, Any]] = [
            {"index": i, "choice": None, "probs": {}, "margin": 0.0, "error": ""}
            for i in range(len(conversations))
        ]
        if not conversations:
            return outcomes

        acquired = self._generation_lock.acquire(timeout=self.GENERATION_QUEUE_TIMEOUT)
        if not acquired:
            for entry in outcomes:
                entry["error"] = "Motore occupato da un'altra richiesta."
            return outcomes

        try:
            load = self._ensure_resident(model_name)
            if not load.get("success"):
                for entry in outcomes:
                    entry["error"] = f"Caricamento modello fallito: {load.get('error')}"
                    entry["fatal"] = True
                    entry["diagnosis"] = load.get("message", "")
                return outcomes

            if self.active_backend_instance is not None:
                for entry in outcomes:
                    entry["error"] = "unsupported_backend"
                return outcomes

            return self._choice_logits_transformers(
                conversations, letters, outcomes, thinking,
                self.auto_batch_size(batch_size), answer_prefix,
            )
        finally:
            self._generation_lock.release()

    def _choice_logits_transformers(
        self, conversations, letters, outcomes, thinking, batch_size,
        answer_prefix: str = "",
    ) -> List[Dict[str, Any]]:
        import torch

        tokenizer = self.tokenizer_instance
        # The answer prefix opens the assistant's turn for it. Without one, the
        # position being read is the first token of a free reply, and a model
        # -- especially a small one -- opens with "When", "To" or "Since": the
        # labels are ranked correctly among themselves but hold a thousandth of
        # the probability mass, so the ranking is between two numbers that are
        # both noise. Primed with "Answer:", the very next token is the label.
        prompts = [self._render_chat(conv, thinking) + answer_prefix
                   for conv in conversations]

        # Models decorate. Asked for a label after "Answer:", a chat model very
        # often writes "**C**" -- so the position being read holds ` **` at
        # 0.99 and the labels share a thousandth between them. The ranking among
        # the labels is still right, but reading it there would mean trusting
        # numbers that round to zero. Instead the model is followed into its own
        # formatting: whatever punctuation it insists on is appended to the
        # prompt and the next position is read. A couple of steps is plenty --
        # after that it is not decorating, it is answering in prose.
        def _fallito(group, message):
            for index in group:
                outcomes[index]["error"] = message

        remaining = list(range(len(prompts)))
        for _ in range(CHOICE_DECORATION_STEPS + 1):
            if not remaining:
                break
            retry: List[int] = []
            self._in_shrinking_batches(
                sorted(remaining, key=lambda i: len(prompts[i])), batch_size,
                run=lambda group: retry.extend(self._score_one_choice_batch(
                    group, prompts, letters, outcomes, tokenizer)),
                on_error=_fallito, label="Lettura delle scelte",
            )
            remaining = retry
        return outcomes

    def _score_one_choice_batch(self, group, prompts, letters, outcomes,
                                tokenizer) -> List[int]:
        """
        Reads one padded group's next-token distribution.

        Returns the items whose answer position turned out to hold decoration
        rather than a label: their prompt has been extended with that
        decoration, and they are worth reading again one token further on.
        """
        import torch

        previous_side = getattr(tokenizer, "padding_side", "right")
        if getattr(tokenizer, "pad_token_id", None) is None:
            tokenizer.pad_token = getattr(tokenizer, "eos_token", None)
        tokenizer.padding_side = "left"
        try:
            batch = tokenizer(
                [prompts[i] for i in group],
                return_tensors="pt", padding=True, add_special_tokens=False,
            )
        finally:
            tokenizer.padding_side = previous_side

        device = self._input_device()
        batch = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch.items()}

        with torch.inference_mode():
            logits = self.model_instance(**batch).logits[:, -1, :].float()
        probabilities = torch.softmax(logits, dim=-1)
        leaders = torch.argmax(probabilities, dim=-1).tolist()

        retry: List[int] = []
        for row, index in enumerate(group):
            options = [str(letter) for letter in (letters[index] or [])]
            scores: Dict[str, float] = {}
            for letter in options:
                ids = _letter_token_ids(tokenizer, letter)
                if not ids:
                    continue
                scores[letter] = float(max(probabilities[row, i].item() for i in ids))
            if len(scores) < 2:
                outcomes[index]["error"] = "nessun token di scelta rappresentabile"
                continue

            total = sum(scores.values())
            if total < CHOICE_MIN_MASS or len(set(scores.values())) == 1:
                # Either the model is about to write something that is not a
                # label, or every label scored identically -- which is not a tie
                # a model produces, it is a reader that handed them all the same
                # token. Neither is a choice, and naming the alphabetically
                # first one would be inventing an answer.
                lead = tokenizer.decode([int(leaders[row])])
                if _is_decoration(lead):
                    prompts[index] = prompts[index] + lead
                    retry.append(index)
                    continue
                outcomes[index].update({
                    "error": "distribuzione non concludente",
                    "mass": round(total, 6),
                })
                continue

            normalised = {k: round(v / total, 6) for k, v in scores.items()}
            ranked = sorted(normalised.items(), key=lambda kv: kv[1], reverse=True)
            outcomes[index].update({
                "choice": ranked[0][0],
                "probs": normalised,
                "margin": round(ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0), 6),
                # How much of the model's next-token probability sat on the
                # labels at all. A high-scoring answer with almost no mass
                # behind it is a coin toss dressed as a decision, and the review
                # queue should be able to sort by it.
                "mass": round(total, 6),
                "error": "",
            })
        return retry

    def _explain_generation_failure(self, exc: BaseException) -> str:
        """
        Turns a runtime failure into something the user can act on.

        An out-of-memory error in particular is not a bug report, it is a
        placement that was one allocation too optimistic, and the remedies are
        specific and knowable: a shorter context, a smaller quantization, or a
        GGUF of the same checkpoint that llama.cpp can split more finely. The
        raw CUDA message names none of them.
        """
        text = f"{type(exc).__name__}: {exc}"
        if not self._is_out_of_memory(exc):
            return f"\n\n❌ **Errore SigmaEngine**: {text}"

        plan = self.placement_plan
        lines = [
            "\n\n❌ **VRAM esaurita durante la generazione.**",
            "",
            "Il modello era caricato, ma non e' rimasto spazio per il passo di "
            "calcolo. La cache di prefisso e' stata liberata.",
        ]
        if plan:
            lines.append(
                f"Piano attuale: {plan.quantization.upper()}, contesto "
                f"{plan.context_tokens} token, margine dichiarato "
                f"{plan.vram_headroom_gb:+.2f} GB."
            )

        remedies = []
        if plan and plan.context_tokens > 4096:
            remedies.append(
                f"ridurre il contesto (ora {plan.context_tokens}): e' la leva "
                "piu' diretta, la memoria di calcolo cresce con esso"
            )
        if plan and plan.quantization != "nf4":
            remedies.append("forzare la quantizzazione a NF4 dal Model Hub")
        remedies.append(
            "usare un GGUF dello stesso checkpoint: llama.cpp divide per layer "
            "con grana piu' fine e non ha bisogno di far stare tutto in una volta"
        )
        lines.append("")
        lines.append("Rimedi, dal piu' efficace:")
        lines.extend(f"- {r}" for r in remedies)
        return "\n".join(lines)

    @staticmethod
    def _is_out_of_memory(exc: BaseException) -> bool:
        """
        Whether this failure is memory exhaustion, whatever the accelerator.

        Matched by name and text rather than by class, because the exception
        differs per backend -- torch.cuda.OutOfMemoryError on NVIDIA, a plain
        RuntimeError on ROCm and MPS -- and the engine has to behave the same
        on all of them.
        """
        name = type(exc).__name__
        if "OutOfMemory" in name or "OOM" in name:
            return True
        text = str(exc).lower()
        return "out of memory" in text or "cuda error: out of memory" in text

    def _retain_prefix_cache(self, generation_output: List[Any], cancel: Any) -> None:
        """
        Keeps the KV cache a finished generation left, for the next turn.

        Only a generation that ran to its natural end is kept. A cancelled one
        stopped at an arbitrary token, and the sequence it reports may not be
        the sequence the cache actually covers -- reusing that would not slow
        the next answer down, it would corrupt it.
        """
        if not (self.prefix_cache_enabled and self.prefix_cache_retained):
            return
        if is_cancelled(cancel) or not generation_output:
            self.prefix_cache.clear("generation did not finish")
            return

        result = generation_output[0]
        cache = getattr(result, "past_key_values", None)
        sequences = getattr(result, "sequences", None)
        if cache is None or sequences is None:
            # An older transformers, or a model whose generate() returns a bare
            # tensor: nothing to retain, and nothing broken by not retaining it.
            self.prefix_cache.clear("runtime returned no cache")
            return

        try:
            ids = sequences[0].tolist()
        except Exception as exc:
            log.debug("[SigmaEngine] Cannot read generated ids (%s)", exc)
            self.prefix_cache.clear("unreadable sequence")
            return

        self.prefix_cache.store(ids, cache, self.loaded_model_name or "")

    def _token_budget(self, requested: int, inputs: Dict[str, Any]) -> int:
        """
        How many new tokens this request may generate.

        Bounded by what is left of the model's context after the prompt, rather
        than by a fixed ceiling: a long conversation must not be allowed to run
        past the window and corrupt its own KV cache, while a short one should
        not be cut off early just because some constant said so.
        """
        limit = requested if requested and requested > 0 else 4096

        prompt_tokens = 0
        ids = inputs.get("input_ids")
        if ids is not None and hasattr(ids, "shape"):
            prompt_tokens = int(ids.shape[-1])

        window = 0
        if self.model_facts:
            window = self.model_facts.max_position_embeddings or 0
        if self.placement_plan and self.placement_plan.context_tokens:
            window = min(window, self.placement_plan.context_tokens) if window \
                else self.placement_plan.context_tokens

        if not window:
            window = 32768

        room = window - prompt_tokens - 16
        if room > 0:
            limit = min(limit, room)
        else:
            limit = max(limit, 1024)

        return max(512, limit)

    @staticmethod
    def _as_messages(
        prompt: str,
        system_prompt: str,
        messages: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """
        Normalises the two calling styles into one conversation.

        Callers that already assembled a conversation pass it through intact;
        the older prompt/system_prompt pair is promoted into the same shape.
        """
        if messages:
            return [m for m in messages if m.get("content")]

        conversation = []
        if system_prompt:
            conversation.append({"role": "system", "content": system_prompt})
        conversation.append({"role": "user", "content": prompt})
        return conversation

    # ------------------------------------------------------- prompt rendering

    def _template_honours_thinking(self) -> bool:
        """
        Whether this checkpoint's chat template actually reads ``enable_thinking``.

        Asked instead of assumed. ``apply_chat_template`` forwards unknown
        keyword arguments into the Jinja context, where a template that never
        mentions them ignores them silently -- so passing the flag proves
        nothing. Rendering the same conversation both ways and comparing does:
        if the two strings are identical the switch is inert, and suppressing
        the reasoning block needs a different lever.
        """
        if self._thinking_switch is not None:
            return self._thinking_switch

        probe = [{"role": "user", "content": "ping"}]
        self._thinking_switch = False
        try:
            on = self.tokenizer_instance.apply_chat_template(
                probe, tokenize=False, add_generation_prompt=True,
                enable_thinking=True,
            )
            off = self.tokenizer_instance.apply_chat_template(
                probe, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
            self._thinking_switch = on != off
        except Exception as exc:
            log.debug("[SigmaEngine] Thinking switch probe skipped: %s", exc)
        return self._thinking_switch

    def _suppress_thinking_directive(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Last resort for templates whose thinking switch is inert.

        Only families that published an in-band directive get one. Inventing a
        directive for a family that has none does not disable anything -- it
        adds a line of noise to the prompt, which on a benchmark is a change to
        the measurement rather than to the model.
        """
        name = (self.loaded_model_name or "").lower()
        if "qwen3" not in name and "qwen-3" not in name:
            return messages

        patched = [dict(m) for m in messages]
        for message in reversed(patched):
            if message.get("role") == "user":
                content = str(message.get("content", ""))
                if "/no_think" not in content:
                    message["content"] = f"{content} /no_think".strip()
                break
        return patched

    def _render_chat(
        self,
        messages: List[Dict[str, str]],
        thinking: Optional[bool] = None,
    ) -> str:
        """
        The prompt string this model expects, as text.

        ``thinking`` is tri-state on purpose: None leaves the checkpoint on its
        own default, which is what a chat wants, while False is an explicit
        request to answer without a reasoning block -- what a benchmark and a
        served endpoint want, because a ``<think>`` block spends the token
        budget before the answer and then gets truncated away.
        """
        template_kwargs: Dict[str, Any] = {}
        if thinking is not None:
            if self._template_honours_thinking():
                template_kwargs["enable_thinking"] = bool(thinking)
            elif thinking is False:
                messages = self._suppress_thinking_directive(messages)

        try:
            return self.tokenizer_instance.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                **template_kwargs
            )
        except Exception:
            # No chat template: render the whole transcript rather than
            # dropping every turn but the last.
            return "\n".join(
                f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
                for m in messages
            ) + "\nAssistant:"

    @staticmethod
    def _stale_placement(model, device_map: Dict[str, Any]) -> List[str]:
        """I moduli citati dalla mappa che nel modello caricato non esistono.

        Una mappa con voci fantasma non e' rumore: accelerate colloca solo cio'
        che riconosce, e cio' che non riconosce resta dove capita e senza hook.
        """
        try:
            reali = {name for name, _ in model.named_modules() if name}
        except Exception:
            return []
        return [name for name in device_map
                if name and name not in reali
                and not any(r.startswith(name + ".") for r in reali)]

    def _input_device(self):
        """
        Where `input_ids` has to land for this placement to accept them.

        Asked of the embedding table itself, not guessed from the placement map.
        The map is keyed by module path and a multimodal checkpoint has several
        modules whose name contains "embed" -- text, vision, audio, and on
        Gemma 4 a per-layer input embedding as well. Picking whichever came
        first put the token indices on one card while the table they index sat
        on another, and the model answered with "Expected all tensors to be on
        the same device". The table that consumes `input_ids` is knowable, so it
        is asked rather than inferred.
        """
        import torch

        try:
            embeddings = self.model_instance.get_input_embeddings()
            weight = getattr(embeddings, "weight", None)
            device = getattr(weight, "device", None)
            # An offloaded layer reports `meta`: it has no memory of its own and
            # accelerate will move the input when the hook fires.
            if device is not None and getattr(device, "type", "") != "meta":
                return device
        except Exception as exc:
            log.debug("[SigmaEngine] Input embedding device unavailable: %s", exc)

        device_map = getattr(self.model_instance, "hf_device_map", None)
        if device_map:
            # Second best: the map, but only for the entries that can plausibly
            # be the token embedding, longest-path last so a nested text model
            # wins over a top-level container.
            for key in ("embed_tokens", "wte", "word_embeddings", "embed"):
                for module_name, device in device_map.items():
                    if key in module_name:
                        return f"cuda:{device}" if isinstance(device, int) else device
        try:
            return next(self.model_instance.parameters()).device
        except Exception:
            return "cuda" if torch.cuda.is_available() else "cpu"

    def _build_inputs(
        self,
        messages: List[Dict[str, str]],
        thinking: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Applies the model's chat template and moves tensors to the input device."""
        formatted = self._render_chat(messages, thinking)
        inputs = self.tokenizer_instance(formatted, return_tensors="pt")

        # With a sharded model, inputs must land on the device holding the
        # embedding layer, which is not necessarily cuda:0.
        target_device = self._input_device()
        return {
            k: v.to(target_device) if hasattr(v, "to") else v
            for k, v in inputs.items()
        }

    def _format_load_failure(self, target_model: str, result: Dict[str, Any]) -> str:
        """Renders the real load failure, with guidance matched to the stage."""
        stage = result.get("stage", "load")
        error = result.get("error", "causa sconosciuta")

        # Quando la diagnosi ha gia' spiegato la causa, un suggerimento generico
        # in coda non aiuta: contraddice. E' successo con un'istruzione illegale
        # (0xC000001D), che si e' presentata all'utente con il consiglio di
        # ridurre il contesto.
        if result.get("stage") == "runtime" or _causa_gia_spiegata(error):
            return (f"❌ **SigmaEngine non ha potuto caricare `{target_model}`**\n\n"
                    f"{error}")

        hints = {
            "discovery": (
                "Apri **Model Hub** nella barra laterale per scaricare un modello, "
                "oppure seleziona un provider Cloud in **Impostazioni AI**."
            ),
            "format": (
                "Esegui `python sigma_launcher.py --install` per installare il "
                "runtime GGUF su questo hardware, oppure usa un checkpoint "
                "safetensors."
            ),
            "inspection": "Il checkpoint sembra incompleto: verifica il download.",
            "load": (
                "Se e' un errore di memoria, riduci il contesto o forza una "
                "quantizzazione piu' aggressiva dal Model Hub."
            ),
        }

        # Check for missing files / incomplete checkpoints
        err_lower = error.lower()
        if "no file named model.safetensors" in err_lower or "incompleto" in err_lower or "incomplete" in err_lower or "mancano" in err_lower:
            hints["load"] = (
                "⚠️ **Checkpoint incompleto su disco**: mancano file di pesi o l'indice `model.safetensors.index.json`. "
                "Apri **Model Hub** nella barra laterale per completare il download, oppure seleziona un modello GGUF pronto all'uso."
            )
            hints["inspection"] = hints["load"]

        # Un'architettura sconosciuta non e' un problema di memoria, e il
        # suggerimento su contesto e quantizzazione mandava a cercare dalla
        # parte sbagliata. Qui la causa e' nota e si puo' dire per nome.
        elif _unrecognised_architecture(error):
            info = result.get("facts") or {}
            hints["load"] = _version_mismatch_advice(
                str(info.get("path") or result.get("path") or "")
            )
            hints["inspection"] = hints["load"]
            hints["preparation"] = hints["load"]

        message = (
            f"❌ **SigmaEngine non ha potuto caricare `{target_model}`**\n\n"
            f"**Fase**: {stage}\n"
            f"**Causa**: `{error}`\n\n"
            f"{hints.get(stage, '')}"
        )

        plan = result.get("plan")
        if plan:
            message += (
                f"\n\n*Piano calcolato*: {plan.get('quantization', '?').upper()}, "
                f"{plan.get('total_required_gb', '?')} GB richiesti contro "
                f"{plan.get('total_vram_gb', '?')} GB di VRAM utilizzabile."
            )
        return message

    @staticmethod
    def _yield_no_model_message() -> Generator[Dict[str, Any], None, None]:
        message = (
            "⚠️ **Nessun modello AI locale presente in `data/models/`.**\n\n"
            "SigmaEngine esegue l'inferenza nativa sui pesi locali.\n\n"
            "1. Apri **Model Hub** e scarica un modello Hugging Face.\n"
            "2. Oppure configura un provider Cloud in **Impostazioni** (⚙️)."
        )
        yield {"token": message, "token_index": 1, "notice": True,
               "error": "no_model", "done": True}

    # -------------------------------------------------------------- status

    def context_window(self) -> int:
        """
        The context the resident model actually has, in tokens.

        Not what the checkpoint was trained for: what this machine could
        allocate for it. The planner shrinks the window to fit the VRAM it
        found, and a caller budgeting a conversation against the trained figure
        would build a prompt the runtime then refuses.
        """
        if self.active_backend_instance is not None:
            settings = self.active_backend_instance.telemetry() or {}
            return int(settings.get("n_ctx", 0) or 0)
        if self.placement_plan and self.placement_plan.context_tokens:
            return int(self.placement_plan.context_tokens)
        if self.model_facts and self.model_facts.max_position_embeddings:
            return int(self.model_facts.max_position_embeddings)
        return 0

    def get_status(self) -> Dict[str, Any]:
        """Returns engine state, hardware allocation and the active plan."""
        return {
            "status": "model_loaded" if self.model_instance is not None else "ready",
            "active_backend": self.active_backend,
            "loaded_model": self.loaded_model_name,
            "last_load_error": self.last_load_error,
            "hardware": self.hardware_profile,
            "model_facts": self.model_facts.to_dict() if self.model_facts else None,
            "placement_plan": (
                self.placement_plan.to_dict() if self.placement_plan else None
            ),
            "optimizations": self._generate_default_optimizations(),
            "backends": self.backend_capabilities(),
            "active_backend_name": (
                self.active_backend_instance.name
                if self.active_backend_instance else "transformers"
            ),
            "tiering_summary": self.hardware_profile.get("recommended_tiering"),
            # Real counters, not a claim: hits, misses and how much prefill the
            # cache actually removed on this machine with this conversation.
            "prefix_cache": (
                self.prefix_cache.stats() if self.prefix_cache_enabled
                else {"enabled": False}
            ),
            "generation_busy": self._generation_waiting > 0,
            "generation_queue": self._generation_waiting,
        }

    def backend_capabilities(self) -> Dict[str, Any]:
        """
        Which runtimes this machine can use, and what is missing for the rest.

        Lets the UI explain why a downloaded checkpoint cannot run here and name
        the install that would fix it, instead of failing at load time.
        """
        from core.engine.backends import capability_report

        report = capability_report(self.hardware_profile)
        report["transformers"] = {
            "available": self._module_available("transformers")
            and self._module_available("torch"),
            "reason": (
                "pronto" if self._module_available("transformers")
                else "transformers non installato"
            ),
            "formats": ["safetensors"],
            "quantization": (
                "bitsandbytes" if self._module_available("bitsandbytes")
                else "non disponibile"
            ),
        }
        return report

    def benchmark(
        self,
        prompt_tokens: int = 128,
        decode_tokens: int = 24,
        profile_modules: bool = False,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Measures real prefill and decode speed for the loaded model.

        Loads the model first if needed, so the endpoint is usable from a cold
        engine.
        """
        from core.engine.benchmark import EngineBenchmark

        if not self.has_resident_model:
            target = model_name or self.loaded_model_name
            result = self.load_native_model(target)
            if not result.get("success"):
                return {"success": False, "error": result.get("error")}

        # A registry backend owns its own model and measures itself. Routing
        # everything through the transformers benchmark is why this endpoint
        # answered "no model loaded" for every GGUF -- that is, for the format
        # most models on this machine are actually in.
        if self.active_backend_instance is not None:
            with self._generation_lock:
                return self.active_backend_instance.benchmark(
                    prompt_tokens=prompt_tokens, decode_tokens=decode_tokens,
                )

        # Measuring mutates the KV cache and competes for the device, so it
        # queues behind chat like any other generation.
        with self._generation_lock:
            self.prefix_cache.clear("benchmark run")
            return EngineBenchmark.run(
                self,
                prompt_tokens=prompt_tokens,
                decode_tokens=decode_tokens,
                profile_modules=profile_modules,
            )

    def plan_for_model(
        self,
        model_identifier: Optional[str] = None,
        context_tokens: int = 32768,
        force_quantization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes the placement plan for a model without loading it.

        Lets the UI show what will happen, and on which tiers, before paying the
        cost of a load.
        """
        model_info = self.find_valid_model_directory(model_identifier)
        if not model_info:
            return {
                "success": False,
                "error": f"Modello non trovato: {model_identifier}",
            }

        target_path, display_name = model_info
        facts = ModelInspector.inspect(target_path)
        if facts is None:
            return {"success": False, "error": f"Introspezione fallita: {target_path}"}

        plan = MemoryPlanner.build_plan(
            facts,
            self.refresh_vram(),
            context_tokens=context_tokens,
            force_quantization=force_quantization,
        )
        return {
            "success": True,
            "model_name": display_name,
            "facts": facts.to_dict(),
            "plan": plan.to_dict(),
        }

    def import_and_optimize_hf_model(
        self,
        repo_id: str,
        filename: Optional[str] = None,
        quantization: Optional[str] = None,
        hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Registers a Hugging Face model and plans its hardware placement.

        When the weights are already local the plan is computed from measured
        facts; otherwise the caller is told to download first rather than being
        given invented numbers.
        """
        model_name = filename or repo_id.split("/")[-1]
        model_info = self.find_valid_model_directory(repo_id) or \
            self.find_valid_model_directory(model_name)

        if not model_info:
            return {
                "success": False,
                "error": (
                    f"'{repo_id}' non e' presente in data/models/. Scaricalo dal "
                    "Model Hub: il piano hardware viene calcolato sui pesi reali."
                ),
                "requires_download": True,
            }

        target_path, display_name = model_info
        facts = ModelInspector.inspect(target_path)
        if facts is None:
            return {"success": False, "error": f"Introspezione fallita: {target_path}"}

        plan = MemoryPlanner.build_plan(
            facts, self.refresh_vram(), force_quantization=quantization
        )

        self.loaded_model = {
            "repo_id": repo_id,
            "name": display_name,
            "path": target_path,
            "quantization": plan.quantization,
            "size_gb": round(facts.total_bytes / 2**30, 2),
            "param_count_b": round(facts.param_count / 1e9, 2),
            "backend": self.active_backend,
            "plan": plan.to_dict(),
            "facts": facts.to_dict(),
            "imported_at": time.time(),
            "status": "planned",
        }

        return {
            "success": True,
            "message": (
                f"{display_name} analizzato: {facts.param_count / 1e9:.1f}B parametri, "
                f"piano {plan.summary()}"
            ),
            "model": self.loaded_model,
        }


# Singleton engine instance. Construction is cheap: hardware probing happens on
# first access, not at import time.
sigma_engine = UniversalSigmaEngine()


@atexit.register
def _release_engine_on_exit() -> None:
    """
    Returns model memory when the program closes.

    Completes the residency contract: weights stay put across chats and are
    released on an explicit request, a switch to a different model, or here.
    """
    try:
        if sigma_engine.model_instance is not None:
            sigma_engine.unload()
    except Exception:
        # Interpreter shutdown tears down CUDA and threading in an order we do
        # not control; a failure here must never mask the real exit path.
        pass
