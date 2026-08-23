# ==============================================================================
# core/engine/gguf_converter.py — Safetensors -> GGUF conversion in the kernel
#
# Both weight formats are first-class in SigmaEngine, so converting between them
# belongs next to the engine rather than inside the training module: a model
# downloaded from Hugging Face should become runnable on the llama.cpp backend
# without a training job in between.
#
# The pipeline has two stages with very different requirements:
#   1. HF -> GGUF (F16) needs llama.cpp's convert_hf_to_gguf.py, which carries
#      the per-architecture tensor mapping. That script is fetched once and
#      cached; it is the only part that needs the network.
#   2. GGUF -> K-quant runs entirely in-process through llama.dll's
#      llama_model_quantize(), so no external binary is required.
# ==============================================================================
import os
import time
import shutil
import threading
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

from core.logger import get_logger
from core.engine.model_inspector import ModelInspector

log = get_logger(__name__)

from core.model_paths import models_dir, project_root

# Resolved per call rather than captured at import: the Model Hub can point
# the models directory somewhere else while the server is running.
TOOLS_DIR = os.path.join(project_root(), "data", "engine_tools")

# llama.cpp split the converter into a package: convert_hf_to_gguf.py is now a
# thin CLI over conversion/, and the tensor mappings for newer architectures
# live there. Fetching the single file only ever worked for old revisions, and
# silently limited us to architectures that predate the split.
#
# Pulled as one source archive rather than file by file: the tree has ~100
# files, and the bundled gguf-py must come from the same revision as the
# converter or the writer will not know the architectures the converter emits.
CONVERTER_REF = "master"
CONVERTER_ARCHIVE = (
    "https://github.com/ggml-org/llama.cpp/archive/refs/heads/"
    + CONVERTER_REF + ".tar.gz"
)
CONVERTER_DIR = os.path.join(TOOLS_DIR, "llama_cpp_convert_" + CONVERTER_REF)
CONVERTER_PATH = os.path.join(CONVERTER_DIR, "convert_hf_to_gguf.py")
BUNDLED_GGUF_PY = os.path.join(CONVERTER_DIR, "gguf-py")
# Kept for the status payload the UI already renders.
CONVERTER_TAG = CONVERTER_REF

# Quantization levels worth offering, least lossy first. "bpw" is the usual
# bits-per-weight for the scheme and is what the size estimate is built from.
QUANT_TYPES: List[Dict[str, Any]] = [
    {"id": "F16", "label": "F16 (nessuna quantizzazione)", "bpw": 16.0,
     "note": "Massima fedelta', file grande quanto il modello originale."},
    {"id": "Q8_0", "label": "Q8_0", "bpw": 8.5,
     "note": "Praticamente indistinguibile dal F16."},
    {"id": "Q6_K", "label": "Q6_K", "bpw": 6.6,
     "note": "Perdita trascurabile."},
    {"id": "Q5_K_M", "label": "Q5_K_M", "bpw": 5.7,
     "note": "Ottimo compromesso quando la VRAM basta."},
    {"id": "Q4_K_M", "label": "Q4_K_M (consigliato)", "bpw": 4.9,
     "note": "Lo standard: buona qualita', meta' della memoria di Q8."},
    {"id": "Q4_K_S", "label": "Q4_K_S", "bpw": 4.6,
     "note": "Leggermente piu' compatto di Q4_K_M."},
    {"id": "Q3_K_M", "label": "Q3_K_M", "bpw": 3.9,
     "note": "Per hardware limitato; la qualita' cala in modo visibile."},
    {"id": "Q2_K", "label": "Q2_K", "bpw": 3.0,
     "note": "Ultima risorsa, degrado marcato."},
]


@dataclass
class ConversionJob:
    """One safetensors -> GGUF conversion, tracked so the UI can follow it."""
    job_id: str
    source_model: str
    quantization: str
    status: str = "queued"      # queued|converting|quantizing|completed|failed
    progress: int = 0
    stage: str = ""
    message: str = ""
    output_path: Optional[str] = None
    output_size_gb: float = 0.0
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["elapsed_seconds"] = round(
            (self.finished_at or time.time()) - self.started_at, 1
        )
        return data


class GgufConverter:
    """Converts local Hugging Face checkpoints into GGUF, with quantization."""

    _jobs: Dict[str, ConversionJob] = {}
    _lock = threading.Lock()

    # ------------------------------------------------------------- discovery

    @classmethod
    def convertible_models(cls) -> List[Dict[str, Any]]:
        """Local safetensors models that can be converted, with size estimates."""
        results: List[Dict[str, Any]] = []
        base = models_dir()
        if not os.path.isdir(base):
            return results

        for entry in sorted(os.listdir(base)):
            path = os.path.join(base, entry)
            if not os.path.isdir(path):
                continue
            facts = ModelInspector.inspect(path)
            if facts is None or facts.weight_format not in ("safetensors", "gguf"):
                continue

            # An existing GGUF can be re-quantized without redoing the slow
            # Hugging Face conversion: that stage is already paid for, and
            # dropping an F16 to Q4_K_M is a straight file transform. Offering
            # it here is the difference between minutes and hours when the
            # first choice turns out too large for the machine.
            already_gguf = facts.weight_format == "gguf"
            if already_gguf and not cls._is_requantizable(path):
                continue

            results.append({
                "name": entry,
                "path": path,
                "source_format": facts.weight_format,
                "architecture": (facts.architectures or ["?"])[0],
                "params_b": round(facts.param_count / 1e9, 2),
                "size_gb": round(facts.total_bytes / 2**30, 2),
                "layers": facts.num_hidden_layers,
                "is_multimodal": facts.is_multimodal,
                "estimated_outputs": cls._estimate_outputs(facts),
                "fits_in_vram": cls._vram_fit(cls._estimate_outputs(facts)),
                "already_converted": os.path.isdir(path + "-GGUF"),
                "compatibility": cls.check_compatibility(facts),
            })
        return results

    @staticmethod
    def _is_requantizable(path: str) -> bool:
        """
        Whether a GGUF is large enough that re-quantizing it is worth offering.

        Anything already at Q4 or below has little left to give, and shrinking
        it further costs quality for space that is no longer the constraint.
        """
        try:
            names = [f for f in os.listdir(path) if f.endswith(".gguf")]
        except Exception:
            return False
        if not names:
            return False
        joined = " ".join(names).upper()
        return any(tag in joined for tag in ("F16", "F32", "BF16", "Q8_0", "Q6_K"))

    @staticmethod
    def _estimate_outputs(facts) -> Dict[str, float]:
        """Approximate GGUF size per quantization, from the real parameter count."""
        params = facts.param_count
        if not params and facts.weight_format == "gguf" and facts.total_bytes:
            # GGUF headers carry no parameter count; infer it from the file size
            # and the precision the name implies, so the estimates stay usable.
            bits = 16.0
            upper = os.path.basename(facts.path).upper()
            for q in QUANT_TYPES:
                if q["id"] in upper:
                    bits = q["bpw"]
                    break
            params = int(facts.total_bytes * 8 / bits)
        if not params:
            return {}
        return {
            q["id"]: round(params * q["bpw"] / 8 / 2**30, 2)
            for q in QUANT_TYPES
        }

    @staticmethod
    def _vram_fit(estimates: Dict[str, float]) -> Dict[str, Any]:
        """
        Which quantizations fit entirely in VRAM on this machine.

        The difference is not marginal: a model that fits runs from GPU memory,
        one that does not streams most of its layers over the host bus and
        loses an order of magnitude of throughput. Converting is slow enough
        that this belongs on screen before the choice, not after it.
        """
        try:
            from core.engine.hardware_probe import UniversalHardwareProbe
            accelerators = UniversalHardwareProbe.probe_accelerators()
        except Exception:
            return {}

        vram = sum(
            a.get("free_vram_gb", 0.0) for a in accelerators
            if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM")
        )
        if not vram:
            return {}

        # Room for the KV cache and compute buffers alongside the weights.
        budget = max(vram - 2.5, 0.0)
        result: Dict[str, Any] = {
            "usable_vram_gb": round(budget, 2),
            "per_quantization": {
                name: size <= budget for name, size in estimates.items()
            },
        }
        fitting = [n for n, ok in result["per_quantization"].items() if ok]
        result["largest_that_fits"] = fitting[0] if fitting else None
        return result

    @classmethod
    def quantization_types(cls) -> List[Dict[str, Any]]:
        return list(QUANT_TYPES)

    # -------------------------------------------------------------- tooling

    @classmethod
    def converter_status(cls) -> Dict[str, Any]:
        """
        Whether the pieces needed for conversion are present.

        The two stages fail for different reasons and are reported separately,
        so a missing converter script does not look like a broken runtime.
        """
        import importlib
        from core.engine.backends.base import module_available

        writer = module_available("gguf")
        quantizer = module_available("llama_cpp")

        # Auto-recover quantizer (llama_cpp) if not yet imported/present
        if not quantizer:
            try:
                from sigma_launcher import detect_platform, install_inference_kernels
                platform_info = detect_platform()
                install_inference_kernels(platform_info)
                importlib.invalidate_caches()
                quantizer = module_available("llama_cpp")
            except Exception:
                pass

        # Auto-recover gguf package if missing
        if not writer:
            try:
                import sys
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", "gguf>=0.1.0"], check=False)
                importlib.invalidate_caches()
                writer = module_available("gguf")
            except Exception:
                pass

        script = os.path.exists(CONVERTER_PATH)
        return {
            "gguf_writer": writer,
            "quantizer": quantizer,
            "converter_script": script,
            "converter_version": CONVERTER_TAG,
            "converter_path": CONVERTER_PATH,
            "ready": writer and quantizer and script,
        }

    @classmethod
    def fetch_converter(cls, timeout: int = 300) -> Dict[str, Any]:
        """
        Downloads llama.cpp's conversion tooling.

        Kept as an explicit action rather than something a conversion triggers
        on its own: it fetches code from the internet that then executes
        locally, which should be a decision the operator makes knowingly.
        """
        import io as _io
        import tarfile
        import urllib.request

        if os.path.exists(CONVERTER_PATH):
            return {
                "success": True, "cached": True, "path": CONVERTER_PATH,
                "message": "Convertitore gia' presente.",
            }

        os.makedirs(TOOLS_DIR, exist_ok=True)
        wanted_prefixes = ("convert_hf_to_gguf.py", "conversion/", "gguf-py/")

        try:
            log.info("[GgufConverter] Fetching llama.cpp tooling (%s)", CONVERTER_REF)
            request = urllib.request.Request(
                CONVERTER_ARCHIVE, headers={"User-Agent": "sigma-studio"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()

            extracted = 0
            with tarfile.open(fileobj=_io.BytesIO(payload), mode="r:gz") as archive:
                for member in archive.getmembers():
                    if not member.isfile():
                        continue
                    # Strip the "llama.cpp-<ref>/" prefix the archive adds.
                    relative = member.name.split("/", 1)[-1]
                    if not relative.startswith(wanted_prefixes):
                        continue
                    # Never let an archive path escape the target directory.
                    target = os.path.normpath(os.path.join(CONVERTER_DIR, relative))
                    if not target.startswith(os.path.normpath(CONVERTER_DIR)):
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        continue
                    with open(target, "wb") as handle:
                        handle.write(source.read())
                    extracted += 1

            if not os.path.exists(CONVERTER_PATH):
                raise RuntimeError("l'archivio non conteneva convert_hf_to_gguf.py")

        except Exception as exc:
            log.error("[GgufConverter] Fetch failed: %s", exc)
            return {"success": False, "error": str(type(exc).__name__) + ": " + str(exc)}

        return {
            "success": True,
            "path": CONVERTER_PATH,
            "files": extracted,
            "size_mb": round(len(payload) / 2**20, 1),
            "message": (
                "Strumenti di conversione llama.cpp scaricati ("
                + str(extracted) + " file)."
            ),
        }

    # ------------------------------------------------------- compatibility

    @classmethod
    def check_compatibility(cls, facts) -> Dict[str, Any]:
        """
        Whether this checkpoint can be converted AND then actually run here.

        Three independent components have to know the architecture, and they
        ship on different schedules: the converter writes it, the gguf package
        encodes it, and llama.cpp's runtime executes it. Converting a 50GB model
        only to have the runtime reject the result is hours wasted, so all three
        are checked before any work starts, and the one that is behind is named.
        """
        hf_type = (facts.model_type or "").lower()
        # Hugging Face and GGUF spell architectures differently: transformers
        # calls it "qwen3_5", the GGUF file records "qwen35". Checking the
        # runtime for the Hugging Face spelling reports every such model as
        # unsupported when it runs perfectly well.
        gguf_arch = cls._gguf_arch_name(hf_type)
        report = {
            "architecture": hf_type,
            "gguf_architecture": gguf_arch,
            "hf_class": (facts.architectures or ["?"])[0],
            "converter": cls._converter_supports(facts),
            "writer": gguf_arch is not None,
            "runtime": cls._runtime_supports(gguf_arch),
        }
        blocking = [name for name in ("converter", "writer", "runtime")
                    if report[name] is False]
        report["convertible"] = report["converter"] is not False and             report["writer"] is not False
        report["runnable"] = report["runtime"] is not False
        report["blocked_by"] = blocking

        if not blocking:
            report["summary"] = "Compatibile: conversione ed esecuzione supportate."
        elif blocking == ["runtime"]:
            report["summary"] = (
                "llama.cpp installato non sa eseguire l'architettura '"
                + str(gguf_arch or hf_type) +
                "'. La conversione riuscirebbe, ma il GGUF non sarebbe "
                "caricabile finche' non aggiorni llama-cpp-python."
            )
        else:
            report["summary"] = (
                "Architettura '" + hf_type + "' non supportata da: "
                + ", ".join(blocking) + "."
            )
        return report

    @classmethod
    def _converter_supports(cls, facts) -> Optional[bool]:
        """
        Whether the fetched converter registers this HF class.

        None when the tooling is not installed yet, which is unknown rather
        than unsupported.
        """
        if not os.path.isdir(CONVERTER_DIR):
            return None
        target = (facts.architectures or [""])[0]
        if not target:
            return None

        conversion_pkg = os.path.join(CONVERTER_DIR, "conversion")
        search_roots = [conversion_pkg] if os.path.isdir(conversion_pkg)             else [CONVERTER_DIR]
        needle = '"' + target + '"'
        alt = "'" + target + "'"
        for root in search_roots:
            for folder, _dirs, files in os.walk(root):
                for name in files:
                    if not name.endswith(".py"):
                        continue
                    try:
                        with open(os.path.join(folder, name), "r",
                                  encoding="utf-8", errors="ignore") as handle:
                            body = handle.read()
                    except Exception:
                        continue
                    if needle in body or alt in body:
                        return True
        return False

    @classmethod
    def _get_gguf_module(cls):
        """Import gguf package, prioritizing the bundled version in CONVERTER_DIR."""
        import sys
        if os.path.isdir(BUNDLED_GGUF_PY) and BUNDLED_GGUF_PY not in sys.path:
            sys.path.insert(0, BUNDLED_GGUF_PY)
        try:
            import gguf
            return gguf
        except Exception:
            return None

    @classmethod
    def _gguf_arch_name(cls, hf_model_type: str) -> Optional[str]:
        """
        The GGUF architecture string for a Hugging Face model_type.

        Matched with canonical mappings and by ignoring separators, because the
        two ecosystems punctuate the same architecture differently ("qwen3_5" against "qwen35").
        """
        if not hf_model_type:
            return None

        lowered = hf_model_type.lower()
        KNOWN_MAPPINGS = {
            "qwen3_5": "qwen35",
            "qwen3.5": "qwen35",
            "qwen35": "qwen35",
            "qwen3_5_moe": "qwen35moe",
            "qwen35moe": "qwen35moe",
            "qwen3": "qwen3",
            "qwen3_moe": "qwen3moe",
            "qwen2": "qwen2",
            "qwen2_5": "qwen2",
            "qwen2.5": "qwen2",
            "qwen2_moe": "qwen2moe",
            "qwen2_vl": "qwen2vl",
            "llama": "llama",
            "deepseek_v4": "deepseek4",
            "deepseek_v3": "deepseek2",
            "deepseek_v2": "deepseek2",
            "deepseek": "deepseek",
            "glm_moe_dsa": "glm-dsa",
            "glm_dsa": "glm-dsa",
            "chatglm": "chatglm",
            "glm4": "glm4",
            "mistral": "llama",
            "gemma": "gemma",
            "gemma2": "gemma2",
            "phi3": "phi3",
            "phi2": "phi2",
            "starcoder2": "starcoder2",
            "command_r": "command-r",
            "cohere": "command-r",
        }

        if lowered in KNOWN_MAPPINGS:
            return KNOWN_MAPPINGS[lowered]

        flat_no_v = lowered.replace("_", "").replace("-", "").replace(".", "").replace("v", "")
        if flat_no_v in KNOWN_MAPPINGS:
            return KNOWN_MAPPINGS[flat_no_v]

        gguf_mod = cls._get_gguf_module()
        if gguf_mod is not None:
            flat = lowered.replace("_", "").replace("-", "").replace(".", "")
            for member in gguf_mod.MODEL_ARCH:
                name = gguf_mod.MODEL_ARCH_NAMES.get(member, "")
                name_flat = name.replace("_", "").replace("-", "").replace(".", "")
                if name_flat == flat or name_flat.replace("v", "") == flat_no_v:
                    return name

        return None

    @staticmethod
    def _runtime_supports(arch: Optional[str]) -> Optional[bool]:
        """
        Whether the installed llama.cpp runtime knows this architecture.

        There is no API that enumerates them, so the architecture name is looked
        for in the shared library's string table. Coarse, but it distinguishes a
        runtime that predates an architecture from one that has it, which is the
        question that matters.
        """
        if not arch:
            return None
        try:
            import llama_cpp
            lib_dir = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
            if not os.path.isdir(lib_dir):
                return None
            for name in os.listdir(lib_dir):
                if not name.startswith("llama") or not name.endswith((".dll", ".so", ".dylib")):
                    continue
                with open(os.path.join(lib_dir, name), "rb") as handle:
                    if arch.encode("ascii", "ignore") in handle.read():
                        return True
            return False
        except Exception:
            return None

    # ----------------------------------------------------------------- jobs

    @classmethod
    def start(cls, model_name: str, quantization: str = "Q4_K_M") -> Dict[str, Any]:
        """Queues a conversion and returns at once; poll the job for progress."""
        source = os.path.join(models_dir(), model_name)
        if not os.path.isdir(source):
            return {"success": False, "error": "Modello non trovato: " + str(model_name)}

        if quantization not in {q["id"] for q in QUANT_TYPES}:
            return {"success": False,
                    "error": "Quantizzazione non valida: " + str(quantization)}

        facts = ModelInspector.inspect(source)
        if facts is not None:
            compat = cls.check_compatibility(facts)
            if compat["blocked_by"]:
                return {
                    "success": False,
                    "error": compat["summary"],
                    "compatibility": compat,
                }

        status = cls.converter_status()
        if not status["ready"]:
            missing = [k for k in ("gguf_writer", "quantizer", "converter_script")
                       if not status[k]]
            return {
                "success": False,
                "error": "Strumenti mancanti: " + ", ".join(missing),
                "converter_status": status,
            }

        with cls._lock:
            # One at a time: conversion is disk and CPU bound, and two running
            # together would compete for the same scratch space.
            if any(j.status in ("queued", "converting", "quantizing")
                   for j in cls._jobs.values()):
                return {"success": False, "error": "Una conversione e' gia' in corso."}
            job = ConversionJob(
                job_id=uuid.uuid4().hex[:8],
                source_model=model_name,
                quantization=quantization,
            )
            cls._jobs[job.job_id] = job

        threading.Thread(target=cls._run, args=(job, source), daemon=True).start()
        return {"success": True, "job": job.to_dict()}

    @classmethod
    def jobs(cls) -> List[Dict[str, Any]]:
        return [
            j.to_dict() for j in
            sorted(cls._jobs.values(), key=lambda j: j.started_at, reverse=True)
        ]

    @classmethod
    def job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        found = cls._jobs.get(job_id)
        return found.to_dict() if found else None

    # ------------------------------------------------------------ execution

    @classmethod
    def _run(cls, job: ConversionJob, source: str) -> None:
        # A GGUF source already lives in a '-GGUF' folder; reuse it rather
        # than nesting another one inside it.
        base_name = job.source_model
        if base_name.endswith("-GGUF"):
            base_name = base_name[:-5]
        for suffix in ("-" + q["id"] for q in QUANT_TYPES):
            if base_name.endswith(suffix):
                base_name = base_name[: -len(suffix)]
                break

        # One directory per quantization. Sharing a folder made every variant
        # collapse into a single inventory entry whose size was their sum, and
        # left the loader picking whichever filename sorted first -- so a freshly
        # made Q4 was invisible while the engine kept loading the F16 beside it.
        target_dir = os.path.join(
            models_dir(), base_name + "-GGUF-" + job.quantization
        )
        os.makedirs(target_dir, exist_ok=True)
        intermediate = os.path.join(target_dir, job.source_model + "-f16.gguf")
        final_name = job.source_model + "." + job.quantization + ".gguf"
        final_path = os.path.join(target_dir, final_name)

        existing_gguf = cls._existing_gguf(source)

        try:
            if existing_gguf:
                # Source is already GGUF: the expensive Hugging Face conversion
                # was done on a previous run, so go straight to quantizing it.
                intermediate = existing_gguf
                job.stage = "reuse_gguf"
                job.message = "GGUF gia' presente: si passa alla quantizzazione."
                job.progress = 50
            else:
                job.status = "converting"
                job.stage = "hf_to_gguf"
                job.message = "Conversione dei pesi in GGUF F16..."
                job.progress = 5
                cls._convert_to_f16(source, intermediate)

            if job.quantization == "F16":
                if existing_gguf:
                    raise RuntimeError(
                        "il modello di partenza e' gia' in questo formato"
                    )
                shutil.move(intermediate, final_path)
            else:
                job.status = "quantizing"
                job.stage = "quantize"
                job.message = "Quantizzazione in " + job.quantization + "..."
                job.progress = 60
                cls._quantize(intermediate, final_path, job.quantization)
                # Remove the F16 intermediate we produced ourselves: it is
                # several times the final file and would fill the disk on every
                # conversion. A pre-existing source GGUF is the user's, and
                # stays where it is.
                if not existing_gguf and os.path.exists(intermediate):
                    os.remove(intermediate)

            job.output_path = final_path
            job.output_size_gb = round(os.path.getsize(final_path) / 2**30, 2)
            job.status = "completed"
            job.progress = 100
            job.stage = "done"
            job.message = (
                final_name + " pronto (" + str(job.output_size_gb) + " GB). "
                "Selezionalo dal Model Hub per usarlo con il backend llama.cpp."
            )
            log.info("[GgufConverter] %s -> %s", job.source_model, final_path)

        except Exception as exc:
            job.status = "failed"
            job.error = str(type(exc).__name__) + ": " + str(exc)
            job.message = "Conversione fallita."
            log.error("[GgufConverter] Job %s failed: %s", job.job_id, exc,
                      exc_info=True)
            if not existing_gguf and os.path.exists(intermediate):
                try:
                    os.remove(intermediate)
                except Exception:
                    pass
        finally:
            job.finished_at = time.time()

    @staticmethod
    def _existing_gguf(source: str) -> Optional[str]:
        """The GGUF already in a source directory, if it holds one."""
        if not os.path.isdir(source):
            return None
        names = sorted(f for f in os.listdir(source) if f.endswith(".gguf"))
        return os.path.join(source, names[0]) if names else None

    @staticmethod
    def _convert_to_f16(source: str, output: str) -> None:
        """
        Runs llama.cpp's converter in a subprocess.

        A subprocess rather than an import: the script is written as a CLI with
        module-level per-architecture state, and a conversion that exhausts
        memory must not take the server down with it.
        """
        import sys

        command = [
            sys.executable, CONVERTER_PATH, source,
            "--outfile", output, "--outtype", "f16",
        ]
        # The converter and the gguf writer must come from the same revision;
        # letting it fall back to the pip-installed gguf pairs a new converter
        # with an older writer that does not know the architectures it emits.
        env = dict(os.environ)
        if os.path.isdir(BUNDLED_GGUF_PY):
            env["PYTHONPATH"] = os.pathsep.join(
                [BUNDLED_GGUF_PY] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
            )
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=3 * 60 * 60, env=env,
        )
        if result.returncode != 0:
            output_text = (result.stderr or result.stdout or "").strip()
            tail = output_text.splitlines()[-4:] or ["nessun output"]
            raise RuntimeError("convert_hf_to_gguf ha fallito: " + " | ".join(tail))
        if not os.path.exists(output):
            raise RuntimeError("la conversione non ha prodotto alcun file")

    @staticmethod
    def _quantize(source: str, output: str, quant_type: str) -> None:
        """Quantizes in-process through llama.dll, so no external tool is needed."""
        import ctypes
        from llama_cpp import llama_cpp as C

        ftype = getattr(C, "LLAMA_FTYPE_MOSTLY_" + quant_type, None)
        if ftype is None:
            raise ValueError("llama.cpp non conosce il tipo " + str(quant_type))

        params = C.llama_model_quantize_default_params()
        params.ftype = ftype
        params.nthread = max((os.cpu_count() or 4) - 1, 1)

        code = C.llama_model_quantize(
            source.encode("utf-8"), output.encode("utf-8"), ctypes.byref(params)
        )
        if code != 0:
            raise RuntimeError("llama_model_quantize ha restituito " + str(code))
