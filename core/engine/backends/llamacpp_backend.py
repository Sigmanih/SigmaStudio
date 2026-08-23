# ==============================================================================
# core/engine/backends/llamacpp_backend.py — GGUF runtime via llama.cpp
#
# llama.cpp is the portable half of the engine. The same GGUF runs on CUDA,
# Metal, Vulkan or plain NEON, and its kernels are fused and graph-friendly in a
# way the transformers path is not, so it stays fast on hardware that cannot
# host a full-precision checkpoint at all.
#
# The adaptation happens in how many layers go to the accelerator and how they
# are split across several of them; everything else llama.cpp handles itself.
# ==============================================================================
import os
import time
from typing import Dict, Any, Generator, List, Optional, Tuple

from core.logger import get_logger
from core.engine.model_inspector import ModelFacts, ModelInspector
from core.engine.backends.base import InferenceBackend, module_available
from core.engine.sampling import SamplingParams
from core.engine.cancellation import is_cancelled

log = get_logger(__name__)

# Room left on each GPU for the CUDA context and per-device scratch.
_GPU_RESERVE_GB = 1.5

# llama.cpp puts more on the GPU than the layers themselves: the output and
# embedding tensors, per-device compute buffers, and the KV cache for whatever
# it offloaded. Measured on a 27B F16 split across two cards, 23 layers
# estimated at 18.0GB actually occupied 21.5GB and filled both cards to the
# last byte, which collapsed throughput to 0.2 tok/s. Sizing layers by their
# raw bytes alone reliably overcommits, so the estimate carries that margin.
_GGUF_OVERHEAD_FACTOR = 1.20
# Fraction of physical cores used when running on CPU. Leaving one core free
# keeps the host responsive, which matters most on the small boards where the
# CPU path is the only path.
_CPU_THREAD_HEADROOM = 1

# Quantizing the KV cache halves it, which can buy back GPU layers -- but it is
# not free. Measured on this project's own hardware, decoding a 3B with every
# layer on the CPU:
#
#     KV f16   8.59 tok/s          KV q8_0   7.65 tok/s      -10.9%
#
# and with every layer on the GPU the same comparison is within noise (+1.8%).
# The dequantization cost lands on whichever device holds the layer, so on a
# split placement the many CPU-resident layers each pay it.
#
# It is therefore applied only when it earns its place: when the halved cache
# moves enough layers onto the accelerator to more than repay the per-token
# cost. Applying it by context length alone -- as this did at first -- gained a
# single layer out of 65 on a model that did not fit anyway, and slowed the 47
# CPU-resident ones down for nothing.
_KV_QUANT_CONTEXT_THRESHOLD = 8192
_KV_QUANT_TYPE = "q8_0"

# The measured decode penalty of a quantized cache on a host-resident layer:
# 8.59 -> 7.65 tok/s on the CPU-only run above. The placement decision is made
# against this number rather than against a rule of thumb.
_KV_QUANT_DECODE_PENALTY = 0.11

# GGML type codes, from ggml.h. llama-cpp-python takes the integer, not a name.
_GGML_TYPES = {"f16": 1, "q8_0": 8, "q5_1": 7, "q5_0": 6, "q4_1": 3, "q4_0": 2}

# Prefill batches. 512 is llama.cpp's conservative default, chosen so it fits
# anywhere; with VRAM to spare a larger batch feeds the GPU properly and cuts
# the wait before the first token on a long prompt.
_N_BATCH_DEFAULT = 512
_N_BATCH_ROOMY = 2048
_N_BATCH_ARM = 128

# n_batch is not free in host RAM. llama-cpp-python allocates a logits buffer of
# n_batch x n_vocab float32 whether or not it ever writes to it, so the cost
# scales with the vocabulary: on a 262144-token vocabulary, n_batch 2048 commits
# 2 GB before a single token is generated. The batch is capped so that buffer
# stays inside this budget -- a faster prefill is not worth two gigabytes the
# machine could have spent on layers.
_SCORES_BUDGET_BYTES = 512 * 2**20

# Prompt lookup decoding: the draft tokens are taken from the prompt itself, so
# there is no second model to load, no VRAM to find and nothing to configure.
# It pays for itself whenever the answer quotes its input -- refactoring, code
# edits, translation, summarising a pasted document -- and costs close to
# nothing when it does not, because a rejected draft is one batched forward
# pass the model was going to make anyway.
_PROMPT_LOOKUP_TOKENS = 10


class LlamaCppBackend(InferenceBackend):
    """Runs GGUF checkpoints through llama-cpp-python."""

    name = "llama_cpp"
    supported_formats = ("gguf",)

    #: Set the first time this build is caught mis-sizing its logits buffer for
    #: speculative decoding (see _verify_speculation). Remembered per process so
    #: later loads do not request a drafter that is already known to be unusable.
    _prompt_lookup_broken = False

    def __init__(self):
        self._llm = None
        self._facts: Optional[ModelFacts] = None
        self._settings: Dict[str, Any] = {}

    # --------------------------------------------------------- capabilities

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        if not module_available("llama_cpp"):
            # The launcher resolves the right wheel index (or source build) for
            # this machine; naming a fixed CUDA tag here sent ARM and CPU hosts
            # after a wheel that does not exist for them.
            return False, (
                "llama-cpp-python non installato: esegui "
                "`python sigma_launcher.py --install` per installarlo "
                "automaticamente per questo hardware "
                "(dettagli in requirements/inference.txt)."
            )
        return True, "pronto"

    @classmethod
    def score(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> int:
        """
        GGUF is llama.cpp's native format, so it always wins for it. The margin
        widens without a CUDA GPU, where the alternative would be float32 on the
        CPU rather than quantized kernels.
        """
        has_cuda = any(
            a.get("type") == "NVIDIA_CUDA"
            for a in hardware.get("accelerators", [])
        )
        return 90 if has_cuda else 100

    # -------------------------------------------------------------- runtime

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def load(
        self,
        facts: ModelFacts,
        hardware: Dict[str, Any],
        context_tokens: int = 8192,
        **options,
    ) -> Dict[str, Any]:
        available, reason = self.availability()
        if not available:
            return {"success": False, "error": reason, "stage": "availability"}

        model_file = self._resolve_gguf_file(facts)
        if not model_file:
            return {
                "success": False,
                "error": f"Nessun file .gguf trovato in {facts.path}",
                "stage": "discovery",
            }

        model_file = os.path.abspath(model_file)
        settings = self._plan_settings(facts, hardware, context_tokens)

        # Force garbage collection and free CUDA allocator before creating Llama instance
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        try:
            from llama_cpp import Llama

            kwargs: Dict[str, Any] = dict(
                model_path=model_file,
                n_gpu_layers=settings["n_gpu_layers"],
                tensor_split=settings["tensor_split"],
                n_ctx=settings["n_ctx"],
                n_threads=settings["n_threads"],
                n_batch=settings["n_batch"],
                flash_attn=settings["flash_attn"],
                verbose=False,
            )

            if settings.get("kv_quant") and settings.get("flash_attn"):
                code = _GGML_TYPES.get(settings["kv_quant"])
                if code is not None:
                    kwargs["type_k"] = code
                    kwargs["type_v"] = code

            draft = self._build_draft_model(settings)
            if draft is not None:
                kwargs["draft_model"] = draft

            t0 = time.perf_counter()
            self._llm = self._construct(Llama, kwargs, settings)
            load_seconds = round(time.perf_counter() - t0, 2)
            self._verify_speculation(settings)

        except Exception as exc:
            log.warning(
                "[LlamaCpp] Primary load failed for '%s' (%s: %s). Retrying with adaptive VRAM rebalance...",
                facts.name, type(exc).__name__, exc,
            )
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

            # Fallback 1: Reduce GPU layers by ~25%, disable flash_attn and reduce batch
            retry_settings = dict(settings)
            cur_layers = retry_settings.get("n_gpu_layers", 0)
            if cur_layers > 0:
                retry_settings["n_gpu_layers"] = max(1, int(cur_layers * 0.75))
            retry_settings["flash_attn"] = False
            retry_settings["n_batch"] = min(retry_settings.get("n_batch", 512), 256)
            retry_settings["kv_quant"] = None

            retry_kwargs = dict(
                model_path=model_file,
                n_gpu_layers=retry_settings["n_gpu_layers"],
                tensor_split=retry_settings["tensor_split"],
                n_ctx=min(retry_settings["n_ctx"], 16384),
                n_threads=retry_settings["n_threads"],
                n_batch=retry_settings["n_batch"],
                flash_attn=False,
                verbose=False,
            )

            try:
                t0 = time.perf_counter()
                self._llm = self._construct(Llama, retry_kwargs, retry_settings)
                load_seconds = round(time.perf_counter() - t0, 2)
                settings = retry_settings
                log.info("[LlamaCpp] Recovered '%s' with %d GPU layers", facts.name, retry_settings["n_gpu_layers"])
            except Exception as exc2:
                # Fallback 2: Conservative CPU/Host-RAM safe load
                log.warning("[LlamaCpp] Partial offload retry failed (%s). Retrying in CPU safe-mode...", exc2)
                gc.collect()
                cpu_settings = dict(settings)
                cpu_settings["n_gpu_layers"] = 0
                cpu_settings["flash_attn"] = False
                cpu_settings["n_ctx"] = min(cpu_settings.get("n_ctx", 8192), 8192)
                cpu_settings["n_batch"] = 128
                cpu_kwargs = dict(
                    model_path=model_file,
                    n_gpu_layers=0,
                    tensor_split=None,
                    n_ctx=cpu_settings["n_ctx"],
                    n_threads=cpu_settings["n_threads"],
                    n_batch=128,
                    flash_attn=False,
                    verbose=False,
                )
                try:
                    t0 = time.perf_counter()
                    self._llm = self._construct(Llama, cpu_kwargs, cpu_settings)
                    load_seconds = round(time.perf_counter() - t0, 2)
                    settings = cpu_settings
                    log.info("[LlamaCpp] Recovered '%s' on CPU safe-mode", facts.name)
                except Exception as exc3:
                    self._llm = None
                    return {
                        "success": False,
                        "error": f"{type(exc3).__name__}: {exc3}",
                        "stage": "load",
                        "settings": settings,
                    }

        self._facts = facts
        self._settings = dict(settings, load_seconds=load_seconds)

        log.info(
            "[LlamaCpp] Loaded '%s' in %.2fs | %s/%s layers on GPU | ctx %d | "
            "batch %d | KV %s | prompt-lookup %s",
            facts.name, load_seconds, settings["n_gpu_layers"],
            facts.num_hidden_layers or "?", settings["n_ctx"],
            settings["n_batch"], settings.get("kv_quant") or "f16",
            settings.get("prompt_lookup_tokens") or "off",
        )
        return {
            "success": True,
            "backend": self.name,
            "model_name": facts.name,
            "load_seconds": load_seconds,
            "settings": settings,
            "placement": self.describe_placement(),
        }

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        messages: Optional[List[Dict[str, str]]] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
    ) -> Generator[Dict[str, Any], None, None]:
        if self._llm is None:
            yield {
                "token": "❌ **LlamaCpp**: nessun modello caricato.",
                "token_index": 1,
                "done": True,
            }
            return

        if not messages:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        if params is None:
            params = SamplingParams.resolve(
                model_name=self._facts.name if self._facts else ""
            ).with_overrides(temperature=temperature, max_tokens=max_tokens)

        # The context window is fixed at load; asking for more new tokens than
        # remain past the prompt is how llama.cpp raises mid-answer instead of
        # answering shorter.
        params = params.with_overrides(
            max_tokens=self._token_budget(params.max_tokens, messages)
        )

        t_start = time.perf_counter()
        token_count = 0
        first_token_sent = False
        first_token_at = t_start
        stream = None

        call_kwargs = params.for_llama_cpp()
        if params.grammar:
            # Compiled here, at the last moment: SamplingParams carries the
            # grammar as text so it stays importable on hosts with no llama.cpp,
            # and a grammar this build rejects costs the constraint, not the turn.
            from core.engine.grammars import compile_for_llama_cpp

            compiled = compile_for_llama_cpp(params.grammar)
            if compiled is not None:
                call_kwargs["grammar"] = compiled

        try:
            stream = self._llm.create_chat_completion(
                messages=messages,
                stream=True,
                **call_kwargs,
            )

            for chunk in stream:
                if is_cancelled(cancel):
                    # Closing the generator unwinds llama.cpp's sampling loop;
                    # without it the model keeps decoding into a queue nobody
                    # drains, holding the only resident model hostage.
                    break

                delta = chunk.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content")
                if not text:
                    continue

                token_count += 1
                now = time.perf_counter()
                # Decode-only throughput; prompt processing is reported apart as
                # time-to-first-token so a long context does not read as a slow
                # model.
                if not first_token_sent:
                    first_token_at = now
                    first_token_sent = True
                    payload: Dict[str, Any] = {
                        "token": text,
                        "token_index": token_count,
                        "ttft_ms": round((now - t_start) * 1000, 1),
                        "done": False,
                    }
                else:
                    payload = {
                        "token": text,
                        "token_index": token_count,
                        "speed_tok_s": round(
                            (token_count - 1) / max(now - first_token_at, 1e-3), 1
                        ),
                        "done": False,
                    }
                yield payload

            now = time.perf_counter()
            yield {
                "token": "",
                "token_index": token_count + 1,
                "speed_tok_s": round(
                    max(token_count - 1, 1) / max(now - first_token_at, 1e-3), 1
                ),
                "total_tokens": token_count,
                "prefill_ms": round((first_token_at - t_start) * 1000, 1),
                "cancelled": is_cancelled(cancel),
                "sampling": params.to_dict(),
                "done": True,
            }

        except Exception as exc:
            log.error("[LlamaCpp] Generation failed: %s", exc, exc_info=True)
            yield {
                "token": f"\n\n❌ **Errore LlamaCpp**: {type(exc).__name__}: {exc}",
                "token_index": token_count + 1,
                "done": True,
            }
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception as exc:
                    log.debug("[LlamaCpp] stream close skipped: %s", exc)

    def unload(self) -> Dict[str, Any]:
        previous = self._facts.name if self._facts else None
        if self._llm is not None:
            try:
                self._llm.close()
            except Exception as exc:
                log.debug("[LlamaCpp] close() skipped: %s", exc)
        self._llm = None
        self._facts = None
        self._settings = {}
        return {"success": True, "unloaded": previous}

    def describe_placement(self) -> Dict[str, Any]:
        if not self._settings:
            return {}
        total = self._facts.num_hidden_layers if self._facts else 0
        offloaded = self._settings.get("n_gpu_layers", 0)
        return {
            "mode": "llama_cpp",
            "layers_total": total,
            "layers_on_gpu": offloaded,
            "layers_on_cpu": max(total - offloaded, 0) if offloaded >= 0 else 0,
            "tensor_split": self._settings.get("tensor_split"),
            "fully_offloaded": offloaded < 0 or (total and offloaded >= total),
            # Reported after the load, not before: _construct drops any option
            # this wheel rejected, so these are what is running.
            "kv_cache_type": self._settings.get("kv_quant") or "f16",
            "kv_saving_gb": self._settings.get("kv_saving_gb"),
            "prefill_batch": self._settings.get("n_batch"),
            "speculative": (
                f"prompt_lookup:{self._settings['prompt_lookup_tokens']}"
                if self._settings.get("prompt_lookup_tokens") else None
            ),
            "degraded": self._settings.get("degraded"),
        }

    def telemetry(self) -> Dict[str, Any]:
        return dict(self._settings)

    # ------------------------------------------------------------ benchmark

    def benchmark(self, prompt_tokens: int = 128, decode_tokens: int = 24) -> Dict[str, Any]:
        """
        Times prefill and decode separately on this machine.

        The two phases are bound by different things -- prefill by batched
        matmul throughput, decode by how fast the weights can be read -- so a
        single tokens-per-second figure hides which one is the problem. They
        are measured through the low-level eval/sample loop rather than through
        create_completion, because that would fold the prompt into the decode
        number and make a long context look like a slow model.
        """
        if self._llm is None:
            return {"success": False, "error": "Nessun modello caricato.",
                    "backend": self.name}

        try:
            # A repeated fragment tokenizes predictably, so the measured prompt
            # is the length that was asked for rather than roughly it.
            seed_text = "Sigma Studio misura la velocita del motore. " * 200
            tokens = self._llm.tokenize(seed_text.encode("utf-8"))[:prompt_tokens]
            if len(tokens) < 8:
                return {"success": False, "error": "Prompt di prova troppo corto.",
                        "backend": self.name}

            # Warm-up: the first eval after a load pays for buffer allocation
            # and kernel selection, which belong to neither phase.
            self._llm.reset()
            self._llm.eval(tokens[:8])

            self._llm.reset()
            t0 = time.perf_counter()
            self._llm.eval(tokens)
            prefill_seconds = time.perf_counter() - t0

            decoded = 0
            t0 = time.perf_counter()
            for _ in range(max(decode_tokens, 1)):
                token = self._llm.sample()
                if token == self._llm.token_eos():
                    break
                self._llm.eval([token])
                decoded += 1
            decode_seconds = time.perf_counter() - t0
            self._llm.reset()
        except Exception as exc:
            log.error("[LlamaCpp] Benchmark failed: %s", exc, exc_info=True)
            return {"success": False, "error": f"{type(exc).__name__}: {exc}",
                    "backend": self.name}

        prefill_tps = round(len(tokens) / max(prefill_seconds, 1e-6), 1)
        decode_tps = round(decoded / max(decode_seconds, 1e-6), 1)

        return {
            "success": True,
            "backend": self.name,
            "model": self._facts.name if self._facts else None,
            "prompt_tokens": len(tokens),
            "prefill": {
                "seconds": round(prefill_seconds, 4),
                "tokens_per_second": prefill_tps,
            },
            "decode": {
                "tokens": decoded,
                "seconds": round(decode_seconds, 4),
                "tokens_per_second": decode_tps,
            },
            "placement": self.describe_placement(),
            "settings": self.telemetry(),
            "verdict": self._verdict(decode_tps),
        }

    def _verdict(self, decode_tps: float) -> Dict[str, Any]:
        """
        Names what is holding decode back, when the placement makes it obvious.

        Layers left on the host bus dominate everything else by an order of
        magnitude, so when there are any, saying anything else would be
        misleading. Where the model is fully on the accelerator this backend
        cannot see inside the kernels, and it says so rather than guessing.
        """
        total = self._facts.num_hidden_layers if self._facts else 0
        on_gpu = self._settings.get("n_gpu_layers", 0)
        if total and 0 <= on_gpu < total:
            return {
                "bound_by": "host_memory",
                "detail": (
                    f"{total - on_gpu} dei {total} layer girano dalla RAM di "
                    f"sistema. Una quantizzazione piu' compatta, o un contesto "
                    f"piu' corto, li riporterebbe in VRAM."
                ),
            }
        if self._settings.get("device") in ("cpu", "arm_neon"):
            return {
                "bound_by": "cpu_compute",
                "detail": f"Esecuzione su CPU a {decode_tps} tok/s, senza acceleratore.",
            }
        return {
            "bound_by": "unknown",
            "detail": (
                "Modello interamente sull'acceleratore. llama.cpp non espone il "
                "dettaglio per kernel: usa il profiler della sua build per "
                "scendere sotto questo livello."
            ),
        }

    # ------------------------------------------------- optional accelerations

    @classmethod
    def _build_draft_model(cls, settings: Dict[str, Any]):
        """
        The prompt-lookup drafter, when this build of llama.cpp ships one.

        Returned as None on any older wheel: speculative decoding is a speedup,
        and a speedup that refuses to load a model is a regression. The setting
        is corrected in place so telemetry reports what is running rather than
        what was asked for.
        """
        if not settings.get("prompt_lookup_tokens"):
            return None
        if cls._prompt_lookup_broken:
            settings["prompt_lookup_tokens"] = 0
            return None
        try:
            from llama_cpp.llama_speculative import LlamaPromptLookupDecoding
        except Exception as exc:
            log.debug("[LlamaCpp] Prompt lookup unavailable in this build: %s", exc)
            settings["prompt_lookup_tokens"] = 0
            return None
        try:
            return LlamaPromptLookupDecoding(
                num_pred_tokens=settings["prompt_lookup_tokens"]
            )
        except Exception as exc:
            log.warning("[LlamaCpp] Prompt lookup could not be built: %s", exc)
            settings["prompt_lookup_tokens"] = 0
            return None

    def _verify_speculation(self, settings: Dict[str, Any]) -> None:
        """
        Checks that speculative decoding can actually run on this build.

        llama-cpp-python 0.3.34 forces its per-token logits buffer on whenever a
        draft model is present, but sizes that buffer from the `logits_all`
        argument, which is still False. The two disagree, and the object loads
        and answers short prompts perfectly well -- then raises

            could not broadcast input array from shape (N,) into shape (0,)

        the first time a prompt is longer than one batch, because the rows it
        wants to write past n_batch do not exist. A first chat message with a
        real system prompt is already past that, so it fails on the first
        substantial turn rather than on an edge case.

        The invariant is checked rather than the version: `_logits_all` on means
        every evaluated token needs a row, so the buffer must span the whole
        context. When it does not, the drafter is removed in place -- setting
        both fields leaves exactly the object that would have been built without
        one, so no second load is paid -- and the verdict is remembered so later
        loads never request it again. A build that fixes the mismatch passes the
        same check and keeps the speedup, with nothing to update here.
        """
        llm = self._llm
        if llm is None or not settings.get("prompt_lookup_tokens"):
            return
        if not getattr(llm, "_logits_all", False):
            return                       # buffer is never written; nothing to overflow

        scores = getattr(llm, "scores", None)
        n_ctx = int(settings.get("n_ctx", 0) or 0)
        rows = int(getattr(scores, "shape", (0,))[0]) if scores is not None else 0
        if rows >= n_ctx:
            return                       # consistent: speculation is safe here

        log.warning(
            "[LlamaCpp] Prompt lookup disabilitato: questa build alloca %d righe "
            "di logits per un contesto di %d token, e fallirebbe al primo prompt "
            "piu' lungo di un batch. Il modello resta caricato senza speculative "
            "decoding.", rows, n_ctx,
        )
        try:
            llm.draft_model = None
            llm._logits_all = False
        except Exception as exc:
            log.error("[LlamaCpp] Cannot disable the drafter in place: %s", exc)

        settings["prompt_lookup_tokens"] = 0
        settings.setdefault("degraded", []).append(
            "prompt lookup non supportato da questa build di llama-cpp-python "
            "(buffer dei logits dimensionato su n_batch invece che su n_ctx)"
        )
        type(self)._prompt_lookup_broken = True

    @classmethod
    def _construct(cls, Llama, kwargs: Dict[str, Any], settings: Dict[str, Any]):
        """
        Builds the Llama handle, dropping arguments this wheel does not know.

        The wheel is chosen per accelerator and per platform, so the same
        checkpoint runs against several llama.cpp versions across the machines
        Sigma Studio supports. An argument added in a later release must cost
        its own optimisation, never the load: the failure is retried without
        the optional keys, and the settings are corrected so the placement
        report stays true.
        """
        optional = ("type_k", "type_v", "draft_model", "flash_attn")
        try:
            return Llama(**kwargs)
        except TypeError as exc:
            dropped = [key for key in optional if key in kwargs]
            if not dropped:
                raise
            log.warning(
                "[LlamaCpp] This build rejected %s (%s); retrying without it.",
                ", ".join(dropped), exc,
            )
            for key in dropped:
                kwargs.pop(key, None)
            settings["kv_quant"] = None
            settings["prompt_lookup_tokens"] = 0
            settings.setdefault("degraded", []).append(
                f"argomenti non supportati da questa build: {', '.join(dropped)}"
            )
            return Llama(**kwargs)

    # ------------------------------------------------------------ planning

    def _token_budget(self, requested: int, messages: List[Dict[str, str]]) -> int:
        """
        How many new tokens fit in what is left of the context window.

        The window is fixed when the model is placed, so a long conversation
        plus a fat system prompt can leave less room than the caller asked for.
        llama.cpp answers that by raising, which loses the turn; answering
        shorter keeps it.

        The prompt is tokenized with the model's own tokenizer, so this is a
        real count rather than a ratio guessed from characters.
        """
        limit = requested if requested and requested > 0 else 2048
        n_ctx = int(self._settings.get("n_ctx", 0) or 0)
        if not n_ctx or self._llm is None:
            return limit

        text = "\n".join(m.get("content", "") or "" for m in messages)
        try:
            prompt_tokens = len(self._llm.tokenize(text.encode("utf-8")))
        except Exception:
            # A tokenizer that refuses the input must not cost the whole turn:
            # four characters per token is the conservative direction here.
            prompt_tokens = len(text) // 4

        # Room for the chat template's own control tokens on top of the text.
        room = n_ctx - prompt_tokens - 128
        if room <= 0:
            log.warning(
                "[LlamaCpp] Prompt (~%d tok) fills the %d token window; "
                "generating a minimal answer. Trim the history or reload with "
                "a larger context.", prompt_tokens, n_ctx,
            )
            return 64
        return max(1, min(limit, room))

    @staticmethod
    def _resolve_gguf_file(facts: ModelFacts) -> Optional[str]:
        """Picks the GGUF to load, preferring the first shard of a split set."""
        if os.path.isfile(facts.path) and facts.path.endswith(".gguf"):
            return facts.path
        if not os.path.isdir(facts.path):
            return None

        candidates = sorted(f for f in os.listdir(facts.path) if f.endswith(".gguf"))
        if not candidates:
            return None

        # llama.cpp opens a split model from its first part and finds the rest.
        first_shard = [c for c in candidates if "00001-of-" in c]
        if first_shard:
            return os.path.join(facts.path, first_shard[0])

        # Several unrelated GGUFs in one folder means different quantizations of
        # the same model. Alphabetical order would pick "F16" over "Q4_K_S",
        # loading the largest variant precisely when a smaller one was made to
        # fit; the smallest is the one that was converted to be usable here.
        if len(candidates) > 1:
            sized = [(os.path.getsize(os.path.join(facts.path, c)), c)
                     for c in candidates]
            chosen = min(sized)[1]
            log.info(
                "[LlamaCpp] %d GGUF variants in %s, loading the smallest (%s)",
                len(candidates), facts.path, chosen,
            )
            return os.path.join(facts.path, chosen)

        return os.path.join(facts.path, candidates[0])

    @classmethod
    def _plan_settings(
        cls, facts: ModelFacts, hardware: Dict[str, Any], context_tokens: int
    ) -> Dict[str, Any]:
        """
        Chooses offload depth, split and threading for this machine.

        The single decision that matters is how many layers reach the
        accelerator: everything left behind is read over the host bus on every
        token.
        """
        accelerators = hardware.get("accelerators", [])
        cpu = hardware.get("cpu", {})
        system = hardware.get("system", {})

        gpus = [
            a for a in accelerators
            if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM") and "free_vram_gb" in a
        ]
        gpus.sort(
            key=lambda a: (a.get("multi_processor_count", 0), a.get("free_vram_gb", 0)),
            reverse=True,
        )

        n_ctx = cls._clamp_context(facts, context_tokens)
        physical_cores = int(cpu.get("cores_physical", 4) or 4)
        n_threads = max(physical_cores - _CPU_THREAD_HEADROOM, 1)

        # Apple silicon shares one memory pool, so everything goes to the GPU.
        if any(a.get("type") == "APPLE_MPS" for a in accelerators):
            return {
                "n_gpu_layers": -1, "tensor_split": None, "n_ctx": n_ctx,
                "n_threads": n_threads,
                "n_batch": cls._cap_batch(_N_BATCH_ROOMY, facts),
                "flash_attn": True,
                "kv_quant": _KV_QUANT_TYPE if n_ctx > _KV_QUANT_CONTEXT_THRESHOLD else None,
                "prompt_lookup_tokens": _PROMPT_LOOKUP_TOKENS,
                "device": "metal",
            }

        if not gpus:
            # CPU-only, which is the normal case on ARM boards. Smaller batches
            # keep peak memory down where there is little of it to spare.
            #
            # No KV quantization here: it rides on flash attention, which this
            # path does not enable, and dequantizing the cache on every step
            # would cost the CPU exactly what it cannot spare. Prompt lookup,
            # on the other hand, is worth most precisely here -- a board that
            # decodes at two tokens a second gains the most from the tokens it
            # can skip decoding.
            is_arm = bool(system.get("is_arm") or system.get("is_raspberry_pi"))
            return {
                "n_gpu_layers": 0, "tensor_split": None, "n_ctx": n_ctx,
                "n_threads": n_threads,
                "n_batch": cls._cap_batch(
                    _N_BATCH_ARM if is_arm else _N_BATCH_DEFAULT, facts),
                "flash_attn": False,
                "kv_quant": None,
                "prompt_lookup_tokens": _PROMPT_LOOKUP_TOKENS,
                "device": "arm_neon" if is_arm else "cpu",
            }

        usable = [max(g.get("free_vram_gb", 0.0) - _GPU_RESERVE_GB, 0.0) for g in gpus]
        total_usable = sum(usable)
        weights_gb = facts.total_bytes / 2**30
        layers = facts.num_hidden_layers or 0

        # Quantizing the KV cache is decided against the placement it produces,
        # not against the context length: the question is not "is the cache
        # big?" but "does halving it move enough layers onto the accelerator to
        # repay what it costs on the ones that stay behind?"
        kv_gb_f16 = ModelInspector.estimate_kv_cache_gb(facts, n_ctx)

        plain = cls._layers_that_fit(weights_gb, layers, total_usable, kv_gb_f16)
        halved = cls._layers_that_fit(weights_gb, layers, total_usable, kv_gb_f16 / 2)

        kv_quant = None
        if n_ctx > _KV_QUANT_CONTEXT_THRESHOLD and layers:
            if cls._kv_quant_pays_off(plain, halved, layers):
                kv_quant = _KV_QUANT_TYPE

        kv_gb = round(kv_gb_f16 / 2, 3) if kv_quant else kv_gb_f16
        n_gpu_layers = halved if kv_quant else plain

        tensor_split = None
        if len(gpus) > 1 and total_usable > 0:
            tensor_split = [round(u / total_usable, 4) for u in usable]

        # A larger prefill batch only helps where there is memory to hold it.
        # On a card that is already full, it competes with the weights.
        headroom_gb = total_usable - (weights_gb * _GGUF_OVERHEAD_FACTOR + kv_gb)
        n_batch = cls._cap_batch(
            _N_BATCH_ROOMY if headroom_gb > 1.0 else _N_BATCH_DEFAULT, facts
        )

        settings = {
            "n_gpu_layers": n_gpu_layers,
            "tensor_split": tensor_split,
            "n_ctx": n_ctx,
            "n_threads": n_threads,
            "n_batch": n_batch,
            "flash_attn": True,
            "kv_quant": kv_quant,
            "prompt_lookup_tokens": _PROMPT_LOOKUP_TOKENS,
            "device": "cuda",
            "usable_vram_gb": round(total_usable, 2),
            "weights_gb": round(weights_gb, 2),
            "kv_cache_gb": kv_gb,
            "kv_cache_gb_f16": kv_gb_f16,
            "logits_buffer_gb": round(
                n_batch * max(int(getattr(facts, "vocab_size", 0) or 0), 1) * 4 / 2**30, 2
            ),
        }
        if kv_quant:
            settings["kv_saving_gb"] = round(kv_gb_f16 - kv_gb, 2)
        settings.update(cls._throughput_forecast(facts, settings, hardware))
        return settings

    # Host memory bandwidth actually reached by a streaming read, as opposed to
    # the figure on the module label. Dual-channel DDR4/DDR5 desktops land here;
    # it is a stated assumption, not a measurement, and is labelled as such
    # wherever the forecast is shown.
    _HOST_BANDWIDTH_GB_S = 12.0
    # A page fault to NVMe is roughly an order of magnitude worse again.
    _DISK_BANDWIDTH_GB_S = 1.5

    @classmethod
    def _throughput_forecast(
        cls, facts: ModelFacts, settings: Dict[str, Any], hardware: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Says what this placement will feel like, before the user finds out.

        Decoding reads every weight once per token, so the layers left off the
        accelerator set a hard ceiling that no amount of tuning moves: bytes on
        the host bus divided by the bandwidth of that bus. The engine used to
        produce this placement in silence and let the user discover it as "the
        model is slow now" -- a 50GB F16 on 21GB of VRAM answers at a third of
        a token per second, and nothing said so.

        Worse is when the host-resident part does not fit in free RAM either.
        Then it is paged from the model file on every token, an order of
        magnitude slower again, and that case is worth its own warning because
        it is the difference between slow and unusable.
        """
        layers = facts.num_hidden_layers or 0
        on_gpu = settings.get("n_gpu_layers", 0)
        weights_gb = facts.total_bytes / 2**30

        if not layers or on_gpu < 0 or on_gpu >= layers:
            return {"forecast": {"placement": "fully_offloaded"}}

        off_gpu = layers - on_gpu
        host_gb = weights_gb * off_gpu / layers
        free_ram = float((hardware.get("ram") or {}).get("available_gb", 0.0) or 0.0)
        paging = free_ram > 0 and host_gb > free_ram

        bandwidth = cls._DISK_BANDWIDTH_GB_S if paging else cls._HOST_BANDWIDTH_GB_S
        ceiling = round(bandwidth / max(host_gb, 1e-6), 2)

        forecast = {
            "placement": "split",
            "layers_on_gpu": on_gpu,
            "layers_on_host": off_gpu,
            "host_gb_per_token": round(host_gb, 1),
            "free_ram_gb": round(free_ram, 1),
            "pages_from_disk": paging,
            "estimated_tokens_per_second": ceiling,
            "assumed_bandwidth_gb_s": bandwidth,
        }

        if paging:
            settings["warning"] = (
                f"{off_gpu} dei {layers} layer non stanno in VRAM e i {host_gb:.0f} GB "
                f"che restano non entrano nemmeno nella RAM libera ({free_ram:.0f} GB): "
                f"verranno letti dal disco a ogni token. Attesa realistica: "
                f"{cls._render_rate(ceiling)}. Serve una quantizzazione piu' compatta."
            )
        else:
            rimasti = (
                "l'ultimo layer viene letto" if off_gpu == 1
                else f"gli altri {off_gpu} vengono letti"
            )
            quanti = f"{host_gb:.1f} GB" if host_gb < 10 else f"{host_gb:.0f} GB"
            settings["warning"] = (
                f"{on_gpu} dei {layers} layer stanno in VRAM: {rimasti} dalla RAM "
                f"di sistema, {quanti} a ogni token. Tetto stimato "
                f"{cls._render_rate(ceiling)}, indipendente da ogni altra "
                f"ottimizzazione."
            )

        alternative = cls.suggest_smaller_variant(facts, hardware)
        if alternative:
            forecast["better_variant"] = alternative
            settings["warning"] += (
                f" Su questo disco c'e' gia' '{alternative['name']}' "
                f"({alternative['size_gb']} GB): entrerebbe "
                f"{'quasi tutto' if alternative['partial'] else 'interamente'} in VRAM."
            )
        return {"forecast": forecast}

    @staticmethod
    def _render_rate(tokens_per_second: float) -> str:
        """A rate a person can read, including the ones that round to zero."""
        if tokens_per_second >= 1:
            return f"~{tokens_per_second:.1f} token/s"
        if tokens_per_second >= 0.1:
            return f"~{tokens_per_second:.2f} token/s"
        seconds = 1.0 / max(tokens_per_second, 1e-9)
        return f"meno di 0,1 token/s (circa {seconds:.0f}s per token)"

    @staticmethod
    def suggest_smaller_variant(
        facts: ModelFacts, hardware: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Another local copy of this model that would actually fit.

        Naming the remedy matters more than naming the problem: the user who
        hit this had the Q4_K_S of the very same checkpoint sitting in the next
        folder, and no part of the product mentioned it.

        Matching is on the model name with the quantization suffix removed, so
        'Qwen--Qwen3.8-27B-GGUF-Q4_K_S' is recognised as a variant of
        'Qwen--Qwen3.8-27B-GGUF' without a registry to keep in step.
        """
        try:
            from core.model_paths import models_dir
            root = models_dir()
            if not os.path.isdir(root):
                return None
        except Exception:
            return None

        usable = sum(
            max(a.get("free_vram_gb", 0.0) - _GPU_RESERVE_GB, 0.0)
            for a in hardware.get("accelerators", [])
            if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM")
        )
        if usable <= 0:
            return None

        def stem(name: str) -> str:
            lowered = name.lower()
            for marker in ("-gguf", "_gguf", ".gguf"):
                index = lowered.find(marker)
                if index > 0:
                    return lowered[:index]
            return lowered

        target = stem(facts.name)
        current_gb = facts.total_bytes / 2**30
        best = None

        for entry in sorted(os.listdir(root)):
            folder = os.path.join(root, entry)
            if not os.path.isdir(folder) or entry == facts.name:
                continue
            if stem(entry) != target:
                continue
            files = [f for f in os.listdir(folder) if f.endswith(".gguf")]
            if not files:
                continue
            size_gb = min(
                os.path.getsize(os.path.join(folder, f)) for f in files
            ) / 2**30
            if size_gb >= current_gb:
                continue
            candidate = {
                "name": entry,
                "size_gb": round(size_gb, 1),
                "partial": size_gb * _GGUF_OVERHEAD_FACTOR > usable,
            }
            # Prefer the largest variant that still fits: quality first among
            # the options that solve the speed problem.
            if best is None or (candidate["size_gb"] > best["size_gb"]
                                and not candidate["partial"]):
                best = candidate
        return best

    @staticmethod
    def _layers_that_fit(
        weights_gb: float, layers: int, usable_gb: float, kv_gb: float
    ) -> int:
        """
        How many layers the accelerator can hold, or -1 when all of them can.

        -1 is llama.cpp's own way of saying "offload everything", and it is not
        the same as the layer count: it also lets the runtime place the output
        and embedding tensors, which a numeric limit does not.
        """
        if not layers:
            return -1
        if (weights_gb * _GGUF_OVERHEAD_FACTOR + kv_gb) <= usable_gb:
            return -1
        per_layer = (weights_gb / layers) * _GGUF_OVERHEAD_FACTOR
        budget = max(usable_gb - kv_gb, 0.0)
        return min(max(int(budget / max(per_layer, 1e-6)), 0), layers)

    @staticmethod
    def _kv_quant_pays_off(plain: int, halved: int, layers: int) -> bool:
        """
        Whether halving the cache saves more than dequantizing it costs.

        Decode on a split placement is dominated by the weights read over the
        host bus, which is proportional to the layers left behind. Quantizing
        the cache multiplies per-token work by the measured penalty but reduces
        that count, so the trade is simply

            host_layers(halved) x penalty  <  host_layers(plain)

        Counting layers moved, as the first version did, gets this backwards at
        both ends: it rejected a case that cut host traffic fourfold because
        only three layers moved, and accepted one that moved a single layer of
        sixty-five while slowing the other forty-seven down.
        """
        if plain == -1:
            return False                  # already fully offloaded; nothing to buy
        if halved == -1:
            return True                   # buys full offload: always worth it

        host_plain = max(layers - plain, 0)
        host_halved = max(layers - halved, 0)
        if host_plain == 0:
            return False
        return host_halved * (1.0 + _KV_QUANT_DECODE_PENALTY) < host_plain

    @staticmethod
    def _cap_batch(desired: int, facts: ModelFacts) -> int:
        """
        The largest prefill batch whose logits buffer stays inside the budget.

        llama-cpp-python allocates n_batch x n_vocab float32 up front, so the
        cost of a bigger batch is set by the vocabulary rather than by the
        model's size. Modern vocabularies are large enough that this dominates:
        at 262144 tokens each batch slot costs a megabyte, so the roomy 2048
        would commit two gigabytes of host RAM before generating anything.
        """
        vocab = int(getattr(facts, "vocab_size", 0) or 0)
        if vocab <= 0:
            # Unknown vocabulary means unknown cost, and the roomy batch is an
            # optimisation while two gigabytes of committed RAM is a real loss.
            # Refusing to guess upward is the only safe direction here.
            return min(desired, _N_BATCH_DEFAULT)
        affordable = _SCORES_BUDGET_BYTES // (vocab * 4)
        # Never below llama.cpp's own floor: a batch smaller than 128 makes
        # prefill slower than the memory it saves is worth.
        return max(min(desired, int(affordable)), 128)

    @staticmethod
    def _clamp_context(facts: ModelFacts, requested: int) -> int:
        """Keeps the context within what the checkpoint was trained for."""
        trained = facts.max_position_embeddings or 0
        if trained and requested > trained:
            return trained
        return max(requested, 512)
