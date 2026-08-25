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
import struct
import tempfile
from typing import Dict, Any, Generator, List, Optional, Tuple

from core.logger import get_logger
from core.engine import gguf_planner
# Le soglie vivono con i conti che le usano: qui restano importabili con il
# loro nome perche' il percorso di caricamento e la suite di test le leggono.
from core.engine.gguf_planner import (  # noqa: F401
    _CPU_CONTEXT_CEILING,
    _CPU_THREAD_HEADROOM,
    _FLOOR_CONTEXT_TOKENS,
    _GGUF_OVERHEAD_FACTOR,
    _GPU_RESERVE_GB,
    _HOST_RESERVE_FRACTION,
    _HOST_RESERVE_MAX_GB,
    _HOST_RESERVE_MIN_GB,
    _HOST_SCRATCH_GB,
    _KV_QUANT_CONTEXT_THRESHOLD,
    _KV_QUANT_DECODE_PENALTY,
    _KV_QUANT_TYPE,
    _MIN_CONTEXT_TOKENS,
    _N_BATCH_ARM,
    _N_BATCH_DEFAULT,
    _N_BATCH_ROOMY,
    _PROMPT_LOOKUP_TOKENS,
    _SCORES_BUDGET_BYTES,
    _SPECULATION_BUFFER_CAP_GB,
    _SPECULATION_BUFFER_FRACTION,
    _env_context_ceiling,
)
from core.engine.model_inspector import ModelFacts, ModelInspector
from core.engine.backends.base import InferenceBackend, module_available
from core.engine.sampling import SamplingParams
from core.engine.cancellation import is_cancelled

log = get_logger(__name__)


class _StderrCapture:
    """Captures low-level C stderr from llama.cpp to report precise load failure reasons."""
    def __init__(self):
        self._orig_fd = None
        self._tmp = None
        self.output = ""

    def __enter__(self):
        try:
            self._orig_fd = os.dup(2)
            self._tmp = tempfile.TemporaryFile(mode="w+b")
            os.dup2(self._tmp.fileno(), 2)
        except Exception:
            self._orig_fd = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._orig_fd is not None:
            try:
                os.dup2(self._orig_fd, 2)
                os.close(self._orig_fd)
                if self._tmp:
                    self._tmp.seek(0)
                    self.output = self._tmp.read().decode("utf-8", errors="replace")
                    self._tmp.close()
            except Exception:
                pass


def _inspect_gguf_file(filepath: str) -> Dict[str, Any]:
    """Inspects GGUF file header to validate magic bytes, version, and architecture metadata."""
    if not os.path.exists(filepath):
        return {"valid": False, "error": f"File non trovato su disco: {filepath}"}

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return {"valid": False, "error": f"File GGUF vuoto (0 byte): {os.path.basename(filepath)}"}

    try:
        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                f.seek(0)
                sample = f.read(256)
                if b"git-lfs" in sample or sample.startswith(b"version https://git-lfs"):
                    return {
                        "valid": False,
                        "error": (
                            f"Il file '{os.path.basename(filepath)}' è un puntatore Git-LFS di testo ({file_size} byte) "
                            f"invece del vero file binario GGUF. Il download da Hugging Face non è stato completato correttamente. "
                            f"Riscarica il modello dal Model Hub."
                        )
                    }
                return {
                    "valid": False,
                    "error": f"Header non valido: magic bytes {magic!r} invece di 'GGUF'. Il file potrebbe essere corrotto o incompleto."
                }

            version_bytes = f.read(4)
            if len(version_bytes) < 4:
                return {"valid": False, "error": "File GGUF troncato (impossibile leggere versione)"}
            version, = struct.unpack("<I", version_bytes)

            tensor_count_bytes = f.read(8)
            kv_count_bytes = f.read(8)
            if len(tensor_count_bytes) < 8 or len(kv_count_bytes) < 8:
                return {"valid": False, "error": "File GGUF troncato (impossibile leggere metadati tensori)"}

            tensor_count, kv_count = struct.unpack("<QQ", tensor_count_bytes + kv_count_bytes)
            metadata = {}

            for _ in range(min(kv_count, 80)):
                klen_bytes = f.read(8)
                if len(klen_bytes) < 8:
                    break
                klen, = struct.unpack("<Q", klen_bytes)
                if klen > 256 or klen == 0:
                    break
                key_bytes = f.read(klen)
                if len(key_bytes) < klen:
                    break
                key = key_bytes.decode("utf-8", errors="replace")

                vtype_bytes = f.read(4)
                if len(vtype_bytes) < 4:
                    break
                vtype, = struct.unpack("<I", vtype_bytes)

                if vtype == 8:  # String
                    vlen_bytes = f.read(8)
                    if len(vlen_bytes) < 8:
                        break
                    vlen, = struct.unpack("<Q", vlen_bytes)
                    if vlen > 4096:
                        f.seek(vlen, 1)
                        continue
                    val_bytes = f.read(vlen)
                    metadata[key] = val_bytes.decode("utf-8", errors="replace")
                elif vtype == 4:  # UINT32
                    v_bytes = f.read(4)
                    if len(v_bytes) == 4:
                        metadata[key] = struct.unpack("<I", v_bytes)[0]
                elif vtype == 5:  # INT32
                    v_bytes = f.read(4)
                    if len(v_bytes) == 4:
                        metadata[key] = struct.unpack("<i", v_bytes)[0]
                elif vtype == 6:  # FLOAT32
                    v_bytes = f.read(4)
                    if len(v_bytes) == 4:
                        metadata[key] = struct.unpack("<f", v_bytes)[0]
                elif vtype == 7:  # BOOL
                    v_bytes = f.read(1)
                    if len(v_bytes) == 1:
                        metadata[key] = struct.unpack("<?", v_bytes)[0]
                else:
                    break

            arch = metadata.get("general.architecture", "sconosciuta")
            name = metadata.get("general.name", os.path.basename(filepath))
            return {
                "valid": True,
                "version": version,
                "architecture": arch,
                "name": name,
                "tensor_count": tensor_count,
                "file_size_gb": round(file_size / (1024**3), 2),
                "metadata": metadata
            }
    except Exception as exc:
        return {"valid": False, "error": f"Errore lettura header GGUF: {exc}"}


def _diagnose_load_error(exc: Exception, captured_stderr: str, gguf_info: Dict[str, Any], settings: Dict[str, Any]) -> str:
    """Provides specific actionable guidance on why llama.cpp failed to load the model."""
    err_str = str(exc)
    combined = (captured_stderr + " " + err_str).lower()
    arch = gguf_info.get("architecture") or "sconosciuta"

    # Va guardata per prima: 0xC000001D e' STATUS_ILLEGAL_INSTRUCTION, cioe' la
    # CPU che incontra un'istruzione che non ha. Cadendo in fondo alla catena
    # veniva riportata come "OSError" nudo, e il consiglio generico per la fase
    # di load suggeriva di ridurre il contesto — che non cambia di una virgola
    # quali istruzioni il processore supporti.
    from core.engine.runtime_probe import illegal_instruction_report, is_illegal_instruction

    if is_illegal_instruction(exc=exc, testo=captured_stderr):
        return illegal_instruction_report()

    if "unknown architecture" in combined or "not supported" in combined:
        import llama_cpp
        ver = getattr(llama_cpp, "__version__", "sconosciuta")
        return (
            f"Architettura GGUF '{arch}' non supportata da questa versione di llama-cpp-python (v{ver}). "
            f"Modelli recenti come Qwen 3.5 / Qwen 3.8 richiedono una versione aggiornata di llama-cpp-python "
            f"o una quantizzazione convertita con architettura standard (es. qwen2)."
        )

    if "failed to allocate" in combined or "out of memory" in combined or "bad_alloc" in combined or "insufficient" in combined:
        return (
            f"Memoria RAM/VRAM insufficiente per caricare il modello '{gguf_info.get('name', '')}' su questa macchina. "
            f"Su architetture con poca RAM (es. Raspberry Pi o macchine senza GPU), usa un modello quantizzato più compatto (es. 1B Q4 o Q2) o riduci n_ctx."
        )

    if "invalid magic" in combined or "failed to load model from file" in err_str.lower():
        if gguf_info.get("file_size_gb", 0) < 0.05:
            return (
                f"File GGUF incompleto o non valido ({gguf_info.get('file_size_gb', 0)} GB). "
                f"Il download potrebbe essere stato interrotto o il file è un puntatore Git-LFS. Riscarica il modello."
            )
        if captured_stderr.strip():
            return f"Errore caricamento llama.cpp ('{arch}'): {captured_stderr.strip()}"
        return (
            f"Impossibile caricare il modello GGUF ('{arch}'): {err_str}. "
            f"Possibili cause: architettura non riconosciuta dalla build attuale di llama.cpp o memoria RAM/VRAM esaurita."
        )

    return f"{type(exc).__name__}: {exc}"





# GGML type codes, from ggml.h. llama-cpp-python takes the integer, not a name.
_GGML_TYPES = {"f16": 1, "q8_0": 8, "q5_1": 7, "q5_0": 6, "q4_1": 3, "q4_0": 2}












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
            # Dynamic self-healing fallback: attempt on-demand installation if missing
            try:
                log.info("[LlamaCppBackend] llama_cpp not found, attempting dynamic on-demand install...")
                import importlib
                from sigma_launcher import detect_platform, install_inference_kernels  # noqa: E501
                platform_info = detect_platform()
                install_inference_kernels(platform_info, force=True)
                importlib.invalidate_caches()
                available, reason = self.availability()
            except Exception as exc:
                log.warning("[LlamaCppBackend] On-demand install failed: %s", exc)

            if not available:
                return {"success": False, "error": reason, "stage": "availability"}

        # Il runtime viene provato in un sottoprocesso prima di caricarci
        # dentro un modello. Su Windows un'istruzione illegale arriva a ctypes
        # come OSError e si intercetta; su Linux e macOS e' SIGILL e uccide il
        # processo, cioe' il server. Meglio scoprirlo dove muore solo la
        # verifica: l'esito e' in cache, quindi si paga una volta sola.
        from core.engine.runtime_probe import check_runtime, illegal_instruction_report

        prova = check_runtime()
        if not prova.get("ok") and prova.get("motivo") == "istruzione_illegale":
            return {
                "success": False,
                "error": illegal_instruction_report(prova.get("cpu")),
                "stage": "runtime",
                "cpu": prova.get("cpu"),
            }

        model_file = self._resolve_gguf_file(facts)
        if not model_file:
            return {
                "success": False,
                "error": f"Nessun file .gguf trovato in {facts.path}",
                "stage": "discovery",
            }

        model_file = os.path.abspath(model_file)

        # Pre-flight GGUF header inspection & file integrity check
        gguf_info = _inspect_gguf_file(model_file)
        if not gguf_info.get("valid"):
            return {
                "success": False,
                "error": gguf_info.get("error", "File GGUF non valido"),
                "stage": "validation",
                "model_name": facts.name,
                "path": model_file,
            }

        log.info(
            "[LlamaCpp] Modello '%s' GGUF validato: architettura '%s' (v%s, %s tensori, %.2f GB)",
            facts.name, gguf_info.get("architecture"), gguf_info.get("version"),
            gguf_info.get("tensor_count", "?"), gguf_info.get("file_size_gb", 0.0)
        )

        settings = self._plan_settings(facts, hardware, context_tokens)

        # Il piano calcolato puo' essere scavalcato a mano: la macchina a
        # volte dichiara VRAM che non ha davvero, o si vuole tenere un
        # modello su CPU apposta per lasciare la scheda libera.
        from core.engine.load_overrides import apply_to as _applica_override
        settings = _applica_override(settings, facts.name)

        # Force garbage collection and free CUDA allocator before creating Llama instance
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        captured_stderr = ""
        last_exception = None

        # ----------------------------------------------------------------------
        # Tier 1: Primary Planned Placement
        # ----------------------------------------------------------------------
        try:
            from llama_cpp import Llama

            kwargs: Dict[str, Any] = dict(
                model_path=model_file,
                n_gpu_layers=settings["n_gpu_layers"],
                tensor_split=settings["tensor_split"],
                n_ctx=settings["n_ctx"],
                n_threads=settings["n_threads"],
                n_threads_batch=settings.get("n_threads_batch") or settings["n_threads"],
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
            with _StderrCapture() as cap:
                self._llm = self._construct(Llama, kwargs, settings)
            captured_stderr = cap.output
            load_seconds = round(time.perf_counter() - t0, 2)
            self._verify_speculation(settings)

        except Exception as exc:
            last_exception = exc
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

            # ------------------------------------------------------------------
            # Tier 2: Adaptive GPU VRAM Reduction (-25% layers, no flash_attn)
            # ------------------------------------------------------------------
            retry_settings = dict(settings)
            cur_layers = retry_settings.get("n_gpu_layers", 0)
            if cur_layers > 0:
                retry_settings["n_gpu_layers"] = max(1, int(cur_layers * 0.75))
            retry_settings["flash_attn"] = False
            retry_settings["n_batch"] = min(retry_settings.get("n_batch", 512), 256)
            retry_settings["kv_quant"] = None
            # No draft_model is passed on any retry path, so reporting prompt
            # lookup as active would describe a run that is not happening.
            retry_settings["prompt_lookup_tokens"] = 0

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
                with _StderrCapture() as cap:
                    self._llm = self._construct(Llama, retry_kwargs, retry_settings)
                captured_stderr = cap.output
                load_seconds = round(time.perf_counter() - t0, 2)
                settings = retry_settings
                log.info("[LlamaCpp] Recovered '%s' with %d GPU layers", facts.name, retry_settings["n_gpu_layers"])
            except Exception as exc2:
                last_exception = exc2
                log.warning("[LlamaCpp] Partial offload retry failed (%s). Retrying in CPU safe-mode...", exc2)
                gc.collect()

                # --------------------------------------------------------------
                # Tier 3: CPU Safe-Mode (4096 context, batch 128)
                # --------------------------------------------------------------
                cpu_settings = dict(settings)
                cpu_settings["n_gpu_layers"] = 0
                cpu_settings["prompt_lookup_tokens"] = 0
                cpu_settings["flash_attn"] = False
                cpu_settings["n_ctx"] = min(cpu_settings.get("n_ctx", 8192), 4096)
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
                    with _StderrCapture() as cap:
                        self._llm = self._construct(Llama, cpu_kwargs, cpu_settings)
                    captured_stderr = cap.output
                    load_seconds = round(time.perf_counter() - t0, 2)
                    settings = cpu_settings
                    log.info("[LlamaCpp] Recovered '%s' on CPU safe-mode", facts.name)
                except Exception as exc3:
                    last_exception = exc3
                    log.warning("[LlamaCpp] CPU standard load failed (%s). Retrying in Low-RAM Safe Mode (heap load, n_ctx=2048)...", exc3)
                    gc.collect()

                    # ----------------------------------------------------------
                    # Tier 4: Low-Resource / Raspberry Pi Safe Mode (heap load, ctx 2048, batch 64)
                    # ----------------------------------------------------------
                    low_ram_settings = dict(settings)
                    low_ram_settings["n_gpu_layers"] = 0
                    low_ram_settings["prompt_lookup_tokens"] = 0
                    low_ram_settings["flash_attn"] = False
                    low_ram_settings["n_ctx"] = 2048
                    low_ram_settings["n_batch"] = 64
                    low_ram_kwargs = dict(
                        model_path=model_file,
                        n_gpu_layers=0,
                        tensor_split=None,
                        n_ctx=2048,
                        n_threads=max(1, cpu_settings.get("n_threads", 4) - 1),
                        n_batch=64,
                        use_mmap=False,
                        use_mlock=False,
                        flash_attn=False,
                        verbose=False,
                    )
                    try:
                        t0 = time.perf_counter()
                        with _StderrCapture() as cap:
                            self._llm = self._construct(Llama, low_ram_kwargs, low_ram_settings)
                        captured_stderr = cap.output
                        load_seconds = round(time.perf_counter() - t0, 2)
                        settings = low_ram_settings
                        log.info("[LlamaCpp] Recovered '%s' on Low-RAM Safe Mode (ctx=2048)", facts.name)
                    except Exception as exc4:
                        last_exception = exc4
                        log.warning("[LlamaCpp] Low-RAM Safe Mode failed (%s). Retrying with minimal context (1024)...", exc4)
                        gc.collect()

                        # ------------------------------------------------------
                        # Tier 5: Ultra-low Context (1024 tokens)
                        # ------------------------------------------------------
                        micro_settings = dict(settings)
                        micro_settings["n_gpu_layers"] = 0
                        micro_settings["prompt_lookup_tokens"] = 0
                        micro_settings["n_ctx"] = 1024
                        micro_settings["n_batch"] = 32
                        micro_kwargs = dict(
                            model_path=model_file,
                            n_gpu_layers=0,
                            tensor_split=None,
                            n_ctx=1024,
                            n_threads=max(1, cpu_settings.get("n_threads", 4) - 1),
                            n_batch=32,
                            use_mmap=False,
                            use_mlock=False,
                            flash_attn=False,
                            verbose=False,
                        )
                        try:
                            t0 = time.perf_counter()
                            with _StderrCapture() as cap:
                                self._llm = self._construct(Llama, micro_kwargs, micro_settings)
                            captured_stderr = cap.output
                            load_seconds = round(time.perf_counter() - t0, 2)
                            settings = micro_settings
                            log.info("[LlamaCpp] Recovered '%s' with ultra-low context (1024)", facts.name)
                        except Exception as exc5:
                            self._llm = None
                            diag_msg = _diagnose_load_error(exc5, captured_stderr, gguf_info, settings)
                            log.error("[LlamaCpp] All load attempts failed for '%s': %s", facts.name, diag_msg)
                            return {
                                "success": False,
                                "error": diag_msg,
                                "stage": "load",
                                "settings": settings,
                                "model_name": facts.name,
                                "architecture": gguf_info.get("architecture"),
                                "stderr": captured_stderr.strip() if captured_stderr else None,
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
        optional = ("type_k", "type_v", "draft_model", "flash_attn", "use_mmap",
                    "use_mlock", "n_threads_batch")
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
        """Picks the GGUF to load, preferring the first shard of a split set and ignoring mmproj."""
        if os.path.isfile(facts.path) and facts.path.endswith(".gguf"):
            return facts.path
        if not os.path.isdir(facts.path):
            return None

        all_ggufs = sorted(f for f in os.listdir(facts.path) if f.endswith(".gguf"))
        if not all_ggufs:
            return None

        # Exclude mmproj / clip vision projector files from main model resolution
        candidates = [
            f for f in all_ggufs if not (
                f.lower().startswith("mmproj") or "mmproj" in f.lower() or
                "-clip-" in f.lower() or "_clip_" in f.lower() or f.lower().startswith("clip-")
            )
        ]
        if not candidates:
            candidates = all_ggufs

        # llama.cpp opens a split model from its first part and finds the rest.
        first_shard = [c for c in candidates if "00001-of-" in c]
        if first_shard:
            return os.path.join(facts.path, first_shard[0])

        if len(candidates) > 1:
            sized = [(os.path.getsize(os.path.join(facts.path, c)), c)
                     for c in candidates]
            # Pick the largest variant (or standard quant), never a tiny clip/mmproj file
            chosen = max(sized)[1]
            log.info(
                "[LlamaCpp] %d GGUF variants in %s, loading (%s)",
                len(candidates), facts.path, chosen,
            )
            return os.path.join(facts.path, chosen)

        return os.path.join(facts.path, candidates[0])


    # ------------------------------------------------------- pianificazione
    # I conti stanno in core/engine/gguf_planner.py: li usera' anche il backend
    # che avvia llama-server, e due copie della stessa matematica divergono.
    # Questi nomi restano perche' sono l'interfaccia con cui il resto del
    # codice e la suite di test chiedono un piano.

    @classmethod
    def _plan_settings(cls, facts, hardware, context_tokens):
        return gguf_planner._plan_settings(facts, hardware, context_tokens)

    @classmethod
    def _fit_to_host_memory(cls, facts, hardware, requested_ctx, host_weights_gb, n_batch, want_speculation, kv_host_fraction, kv_bytes_per_element):
        return gguf_planner._fit_to_host_memory(facts, hardware, requested_ctx, host_weights_gb, n_batch, want_speculation, kv_host_fraction, kv_bytes_per_element)

    @staticmethod
    def _host_fit_result(ctx, requested_ctx, speculation, required_gb, budget_gb, kv_gb, batch_logits_gb, spec_logits_gb, notes, warning):
        return gguf_planner._host_fit_result(ctx, requested_ctx, speculation, required_gb, budget_gb, kv_gb, batch_logits_gb, spec_logits_gb, notes, warning)

    @staticmethod
    def _merge_host_fit(settings, fit):
        return gguf_planner._merge_host_fit(settings, fit)

    @classmethod
    def _cpu_forecast(cls, facts, settings, hardware):
        return gguf_planner._cpu_forecast(facts, settings, hardware)

    @classmethod
    def _throughput_forecast(cls, facts, settings, hardware):
        return gguf_planner._throughput_forecast(facts, settings, hardware)

    @staticmethod
    def suggest_smaller_variant(facts, hardware):
        return gguf_planner.suggest_smaller_variant(facts, hardware)

    @staticmethod
    def _layers_that_fit(weights_gb, layers, usable_gb, kv_gb):
        return gguf_planner._layers_that_fit(weights_gb, layers, usable_gb, kv_gb)

    @staticmethod
    def _kv_quant_pays_off(plain, halved, layers):
        return gguf_planner._kv_quant_pays_off(plain, halved, layers)

    @staticmethod
    def _cap_batch(desired, facts):
        return gguf_planner._cap_batch(desired, facts)

    @staticmethod
    def _clamp_context(facts, requested):
        return gguf_planner._clamp_context(facts, requested)

    @classmethod
    def _context_ladder(cls, requested):
        return gguf_planner._context_ladder(requested)

    @staticmethod
    def _logits_buffer_gb(facts, rows):
        return gguf_planner._logits_buffer_gb(facts, rows)

    @staticmethod
    def _host_budget_gb(hardware):
        return gguf_planner._host_budget_gb(hardware)

    @staticmethod
    def _render_rate(tokens_per_second):
        return gguf_planner._render_rate(tokens_per_second)
