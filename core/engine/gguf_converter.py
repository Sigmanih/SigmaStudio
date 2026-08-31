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
import json
import time
import shutil
import threading
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

from core import paths
from core.logger import get_logger
from core.engine.model_inspector import ModelInspector

log = get_logger(__name__)

from core.model_paths import models_dir, project_root

# Resolved per call rather than captured at import: the Model Hub can point
# the models directory somewhere else while the server is running.
TOOLS_DIR = str(paths.engine_tools_dir())

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


#: Byte per parametro degli intermedi che il convertitore sa produrre. Non
#: stime: sono le larghezze dei tipi.
#: "auto" lascia scegliere allo script il tipo a 16 bit di massima fedelta
#: per quel modello (bf16 se il modello e bf16), che occupa quanto f16.
_INTERMEDIATE_BPP = {"auto": 2.0, "f16": 2.0, "bf16": 2.0, "q8_0": 1.0625}
#: Margine da lasciare sul volume. Riempire un disco fino all'ultimo byte fa
#: fallire altro, non solo la conversione.
_DISK_HEADROOM_GB = 5.0


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
            # A store accumulates half-downloaded, hand-copied and foreign
            # directories. One of them failing to parse must not empty the
            # whole list: skip it, say so in the log, keep scanning.
            try:
                facts = ModelInspector.inspect(path)
            except Exception as exc:  # noqa: BLE001 - any malformed directory
                log.warning(
                    "[GgufConverter] '%s' non ispezionabile, escluso dalla lista: %s",
                    entry, exc,
                )
                continue
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

            try:
                estimated = cls._estimate_outputs(facts)
                compatibility = cls.check_compatibility(facts)
            except Exception as exc:  # noqa: BLE001 - stima non essenziale
                log.warning(
                    "[GgufConverter] stima non riuscita per '%s': %s", entry, exc
                )
                estimated, compatibility = [], {}

            results.append({
                "moe": cls._moe_note(facts),
                "name": entry,
                "path": path,
                "source_format": facts.weight_format,
                "architecture": (facts.architectures or ["?"])[0],
                "params_b": round(facts.param_count / 1e9, 2),
                "size_gb": round(facts.total_bytes / 2**30, 2),
                "layers": facts.num_hidden_layers,
                "is_multimodal": facts.is_multimodal,
                "estimated_outputs": estimated,
                "fits_in_vram": cls._vram_fit(estimated),
                "already_converted": os.path.isdir(path + "-GGUF"),
                "compatibility": compatibility,
            })
        return results

    @staticmethod
    def _free_disk_gb(path: str) -> float:
        """Spazio libero sul volume che ospita `path`, in GB."""
        import shutil

        try:
            return shutil.disk_usage(os.path.dirname(os.path.abspath(path))).free / 2**30
        except OSError:
            return 0.0

    @classmethod
    def _plan_conversion_space(cls, facts, quantization: str,
                               output_dir: str) -> Dict[str, Any]:
        """Se la conversione ci sta sul disco, e con quale intermedio.

        Intermedio e file finale coesistono: il quantizzatore legge il primo
        mentre scrive il secondo, quindi serve la somma dei due e non il
        maggiore. E' l'errore che fa scoprire il disco pieno a meta' strada.
        """
        params = getattr(facts, "param_count", 0) or 0
        if not params:
            # Senza il numero di parametri non si puo' decidere: si lascia
            # procedere invece di bloccare su un'incertezza nostra.
            return {"ok": True, "intermediate": "auto", "reason": "dimensione ignota"}

        finale_bpw = next((q["bpw"] for q in QUANT_TYPES if q["id"] == quantization), 4.87)
        finale_gb = params * finale_bpw / 8 / 2**30
        libero_gb = cls._free_disk_gb(output_dir) - _DISK_HEADROOM_GB

        for tipo in ("auto", "q8_0"):
            intermedio_gb = params * _INTERMEDIATE_BPP[tipo] / 2**30
            if intermedio_gb + finale_gb <= libero_gb:
                return {
                    "ok": True,
                    "intermediate": tipo,
                    "intermediate_gb": round(intermedio_gb, 1),
                    "final_gb": round(finale_gb, 1),
                    "free_gb": round(libero_gb, 1),
                    "downgraded": tipo != "auto",
                }

        minimo_gb = params * _INTERMEDIATE_BPP["q8_0"] / 2**30 + finale_gb
        return {
            "ok": False,
            "intermediate": "q8_0",
            "intermediate_gb": round(params * _INTERMEDIATE_BPP["q8_0"] / 2**30, 1),
            "final_gb": round(finale_gb, 1),
            "free_gb": round(libero_gb, 1),
            "needed_gb": round(minimo_gb, 1),
            "missing_gb": round(minimo_gb - libero_gb, 1),
        }

    @staticmethod
    def _moe_note(facts) -> Optional[Dict[str, Any]]:
        """Cosa dire della VRAM quando il modello e' a esperti.

        Un MoE non tiene tutti gli esperti sulla scheda: di 512 un token ne
        accende 10, e il pianificatore li lascia in RAM con `-ncmoe`. Misurare
        il peso intero contro la VRAM risponde a una domanda che nessuno ha
        fatto, e la risposta scoraggia una configurazione che funziona.
        """
        if not getattr(facts, "is_moe", False):
            return None

        totali = int(getattr(facts, "num_experts", 0) or 0)
        attivi = int(getattr(facts, "experts_used", 0) or 0)
        return {
            "is_moe": True,
            "experts_total": totali,
            "experts_used_per_token": attivi,
            "note": (
                f"Modello a esperti ({attivi} attivi su {totali} per token): gli "
                "esperti restano in RAM con l'offload `-ncmoe` e non occupano "
                "VRAM. Il peso complessivo NON e quindi il requisito della "
                "scheda. Il vincolo reale e la RAM libera: gli esperti che non "
                "ci stanno vengono letti dal disco a ogni token."
            ),
        }

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
                from sigma_launcher import detect_platform, install_gguf_runtime
                platform_info = detect_platform()
                install_gguf_runtime(platform_info)
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
            # Da quale giorno di "master" viene questo albero. Senza la data
            # la versione dice "master" per sempre, che di un ramo che si
            # muove ogni giorno non dice niente.
            "fetched_at": cls._converter_fetched_at(),
            "ready": writer and quantizer and script,
        }

    @staticmethod
    def _converter_fetched_at() -> Optional[str]:
        """Quando e' stato scaricato lo snapshot del convertitore."""
        try:
            return time.strftime(
                "%Y-%m-%d", time.localtime(os.path.getmtime(CONVERTER_PATH)))
        except Exception:
            return None

    @classmethod
    def fetch_converter(cls, timeout: int = 300, force: bool = False) -> Dict[str, Any]:
        """
        Downloads llama.cpp's conversion tooling.

        Kept as an explicit action rather than something a conversion triggers
        on its own: it fetches code from the internet that then executes
        locally, which should be a decision the operator makes knowingly.

        `force` re-downloads over a copy that is already there. Without it
        there was no way to move the snapshot forward: the ref is "master",
        which sounds like something that keeps up, but the first fetch froze
        it and every later call returned "already present". Months of
        architectures accumulated upstream while the local tree stayed at the
        day it was pulled, and the failure it produced -- a model llama.cpp
        runs but the converter has never heard of -- reads like the model is
        unsupported rather than like the toolchain is old.

        The new tree is assembled beside the old one and swapped in only once
        it is complete: a download that dies halfway leaves the converter that
        was working exactly where it was.
        """
        import io as _io
        import tarfile
        import urllib.request

        if os.path.exists(CONVERTER_PATH) and not force:
            return {
                "success": True, "cached": True, "path": CONVERTER_PATH,
                "fetched_at": cls._converter_fetched_at(),
                "message": "Convertitore gia' presente.",
            }

        os.makedirs(TOOLS_DIR, exist_ok=True)
        destinazione = CONVERTER_DIR + ".new" if force else CONVERTER_DIR
        if force:
            shutil.rmtree(destinazione, ignore_errors=True)
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
                    target = os.path.normpath(os.path.join(destinazione, relative))
                    if not target.startswith(os.path.normpath(destinazione)):
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        continue
                    with open(target, "wb") as handle:
                        handle.write(source.read())
                    extracted += 1

            if not os.path.exists(os.path.join(destinazione, "convert_hf_to_gguf.py")):
                raise RuntimeError("l'archivio non conteneva convert_hf_to_gguf.py")

            if destinazione != CONVERTER_DIR:
                precedente = CONVERTER_DIR + ".old"
                shutil.rmtree(precedente, ignore_errors=True)
                if os.path.isdir(CONVERTER_DIR):
                    os.rename(CONVERTER_DIR, precedente)
                os.rename(destinazione, CONVERTER_DIR)
                shutil.rmtree(precedente, ignore_errors=True)

        except Exception as exc:
            log.error("[GgufConverter] Fetch failed: %s", exc)
            if destinazione != CONVERTER_DIR:
                shutil.rmtree(destinazione, ignore_errors=True)
            return {"success": False, "error": str(type(exc).__name__) + ": " + str(exc)}

        return {
            "success": True,
            "path": CONVERTER_PATH,
            "fetched_at": cls._converter_fetched_at(),
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
        converter_ok = cls._converter_supports(facts)
        writer_ok = cls._writer_supports(gguf_arch) if gguf_arch else False
        runtime_ok = cls._runtime_supports(gguf_arch) if gguf_arch else False

        report = {
            "architecture": hf_type,
            "gguf_architecture": gguf_arch,
            "hf_class": (facts.architectures or ["?"])[0],
            "converter": converter_ok,
            "writer": writer_ok,
            "runtime": runtime_ok,
        }
        blocking = [name for name in ("converter", "writer", "runtime")
                    if report[name] is False]
        report["convertible"] = report["converter"] is not False and report["writer"] is not False
        report["runnable"] = report["runtime"] is not False
        report["blocked_by"] = blocking

        nome = str(gguf_arch or hf_type)
        build = cls._runtime_build()
        report["runtime_build"] = build

        # Ogni messaggio nomina il componente indietro e come si aggiorna: sono
        # due cose diverse, tenute da due bottoni diversi, e dire soltanto
        # "non supportata" ha lasciato per giorni un modello valido fermo su
        # disco senza indicare che bastava aggiornare il motore.
        aggiorna_motore = (
            "Aggiorna il runtime dal pannello del motore (build installata: "
            + (build or "nessuna") + ")."
        )
        aggiorna_convertitore = (
            "Aggiorna gli strumenti di conversione dal Model Hub "
            "(Convertitore GGUF -> Aggiorna)."
        )

        # Il writer e' il segnale autorevole: il pacchetto gguf e il runtime
        # llama.cpp nascono dallo stesso progetto, quindi se il writer non
        # conosce l'architettura non la conoscera' nemmeno una build piu'
        # recente. Consigliare un aggiornamento manderebbe a cercare una
        # versione che nessuno ha pubblicato.
        if report["writer"] is False:
            report["upstream_missing"] = True
            report["summary"] = (
                "L'architettura '" + nome + "' non e ancora implementata in "
                "llama.cpp: il writer GGUF non la conosce, e non la conoscera "
                "nemmeno un runtime piu recente finche il supporto non arriva "
                "a monte. Aggiornare gli strumenti non aiuta. Il modello resta "
                "utilizzabile con il backend transformers, se la memoria basta."
            )
        elif not blocking:
            report["summary"] = "Compatibile: conversione ed esecuzione supportate."
        elif blocking == ["runtime"]:
            report["summary"] = (
                "Il runtime llama.cpp installato non conosce l'architettura '"
                + nome + "'. La conversione riuscirebbe, ma il GGUF non "
                "sarebbe caricabile. " + aggiorna_motore
            )
        elif "runtime" not in blocking:
            report["summary"] = (
                "Il motore esegue l'architettura '" + nome + "', ma "
                + ("il convertitore non la scrive" if "converter" in blocking
                   else "il pacchetto gguf non la sa scrivere")
                + ". Un GGUF gia' pronto di questo modello si carica lo stesso; "
                "per produrne uno dai safetensors: " + aggiorna_convertitore
            )
        else:
            report["summary"] = (
                "Architettura '" + nome + "' non supportata da: "
                + ", ".join(blocking) + ". " + aggiorna_motore + " "
                + aggiorna_convertitore
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
        targets = list(facts.architectures or [])
        if not targets and facts.model_type:
            targets = [facts.model_type]
        if not targets:
            return None

        hf_type = (facts.model_type or "").lower()

        # There is deliberately no blocklist here. Which architectures can be
        # converted is a property of the converter on disk, not of this file:
        # a hand-written list of "experimental, impossible" ones goes stale the
        # moment upstream implements them, and from then on it refuses models
        # that work. qwen4exp is the case that proved it -- hyper-connections
        # and the linear-attention mixer were declared unsupportable by GGUF
        # while llama.cpp had already shipped both, and a valid 119GB quant sat
        # on disk unusable because this function answered from memory instead
        # of looking. The walk below asks the converter we actually have.

        # Build candidate class and arch strings
        expanded_targets = set(targets)
        for t in list(targets):
            expanded_targets.add(t.replace("Unified", ""))
            expanded_targets.add(t.replace("ConditionalGeneration", "CausalLM"))
            expanded_targets.add(t.replace("ForCausalLM", "ForConditionalGeneration"))
            expanded_targets.add(t.replace("3_8", "3").replace("3.8", "3"))
            expanded_targets.add(t.replace("2_5", "2").replace("2.5", "2"))

        conversion_pkg = os.path.join(CONVERTER_DIR, "conversion")
        search_roots = [conversion_pkg] if os.path.isdir(conversion_pkg) else [CONVERTER_DIR]

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
                    for target in expanded_targets:
                        needle = '"' + target + '"'
                        alt = "'" + target + "'"
                        if needle in body or alt in body:
                            return True

        # The family has a file, but this exact class is not registered in it.
        # That is "unknown", not "supported": the class name is how the
        # converter dispatches, and claiming support for one it never
        # registered promises a conversion that dies on the first tensor.
        # Unknown does not block -- it only stops us from guaranteeing.
        for base in ("gemma", "llama", "qwen", "mistral", "phi", "deepseek", "glm", "starcoder", "minicpm", "smollm", "internlm", "baichuan", "falcon"):
            if base in hf_type:
                return None

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

        lowered = str(hf_model_type).lower().strip()
        KNOWN_MAPPINGS = {
            "gemma4": "gemma4",
            "gemma4_unified": "gemma4",
            "gemma4_it": "gemma4",
            "gemma4_text": "gemma4",
            "gemma4-assistant": "gemma4-assistant",
            "gemma4_assistant": "gemma4-assistant",
            "gemma3": "gemma3",
            "gemma3_unified": "gemma3",
            "gemma3n": "gemma3n",
            "gemma2": "gemma2",
            "gemma": "gemma",
            "qwen3_5": "qwen35",
            "qwen3.5": "qwen35",
            "qwen35": "qwen35",
            "qwen3_5_moe": "qwen35moe",
            "qwen35moe": "qwen35moe",
            "qwen3": "qwen3",
            "qwen3_moe": "qwen3moe",
            "qwen3_next": "qwen3next",
            "qwen3next": "qwen3next",
            "qwen4_exp": "qwen4exp",
            "qwen4exp": "qwen4exp",
            "qwen3_8": "qwen3",
            "qwen3.8": "qwen3",
            "qwen3_unified": "qwen3",
            "qwen2": "qwen2",
            "qwen2_5": "qwen2",
            "qwen2.5": "qwen2",
            "qwen2_moe": "qwen2moe",
            "qwen2_vl": "qwen2vl",
            "llama": "llama",
            "llama3": "llama",
            "llama3.1": "llama",
            "llama3.2": "llama",
            "llama3.3": "llama",
            "llama4": "llama4",
            "deepseek_v4": "deepseek4",
            "deepseek_v3": "deepseek2",
            "deepseek_v2": "deepseek2",
            "deepseek": "deepseek",
            "glm_moe_dsa": "glm-dsa",
            "glm_dsa": "glm-dsa",
            "chatglm": "chatglm",
            "glm4": "glm4",
            "glm4_unified": "glm4",
            "glm4moe": "glm4moe",
            "mistral": "llama",
            "mistral3": "mistral3",
            "mistral4": "mistral4",
            "smollm": "llama",
            "smollm2": "llama",
            "smollm3": "smollm3",
            "phi4": "phi3",
            "phi3": "phi3",
            "phi2": "phi2",
            "starcoder2": "starcoder2",
            "command_r": "command-r",
            "cohere": "command-r",
            "internlm2": "internlm2",
            "minicpm": "minicpm",
            "minicpm3": "minicpm3",
            "nemotron": "nemotron",
            "granite": "granite",
            "olmo": "olmo",
            "olmo2": "olmo2",
            "olmoe": "olmoe",
            "falcon": "falcon",
            "baichuan": "baichuan",
        }

        if lowered in KNOWN_MAPPINGS:
            return KNOWN_MAPPINGS[lowered]

        cleaned = (
            lowered
            .replace("_unified", "")
            .replace("-unified", "")
            .replace("_text", "")
            .replace("-text", "")
            .replace("_vision", "")
            .replace("-vision", "")
            .replace("_audio", "")
            .replace("-audio", "")
            .replace("_it", "")
            .replace("-it", "")
            .replace("_instruct", "")
            .replace("-instruct", "")
        )
        if cleaned in KNOWN_MAPPINGS:
            return KNOWN_MAPPINGS[cleaned]

        flat_no_v = lowered.replace("_", "").replace("-", "").replace(".", "").replace("v", "")
        if flat_no_v in KNOWN_MAPPINGS:
            return KNOWN_MAPPINGS[flat_no_v]

        gguf_mod = cls._get_gguf_module()
        if gguf_mod is not None:
            flat = lowered.replace("_", "").replace("-", "").replace(".", "")
            cleaned_flat = cleaned.replace("_", "").replace("-", "").replace(".", "")
            for member in gguf_mod.MODEL_ARCH:
                name = gguf_mod.MODEL_ARCH_NAMES.get(member, "")
                name_flat = name.replace("_", "").replace("-", "").replace(".", "")
                if name in (lowered, cleaned):
                    return name
                if name_flat in (flat, cleaned_flat):
                    return name
                if name_flat.replace("v", "") in (flat_no_v, cleaned_flat.replace("v", "")):
                    return name

            # Fuzzy prefix match in MODEL_ARCH_NAMES
            for member in gguf_mod.MODEL_ARCH:
                name = gguf_mod.MODEL_ARCH_NAMES.get(member, "")
                if name and (cleaned.startswith(name) or name.startswith(cleaned)):
                    return name

        # Fallback to llama ONLY if the model type is genuinely in the llama family
        llama_like = ("llama", "alpaca", "vicuna", "wizard", "openllama")
        if any(like in lowered for like in llama_like):
            return "llama"

        return None

    @staticmethod
    def _runtime_libraries() -> List[str]:
        """The shared libraries of the engine that actually answers requests.

        The llama.cpp build under store/engine_runtime comes first: that is what
        llamaserver_backend launches. The llama_cpp package is only a fallback
        for installations that still run in-process.
        """
        libraries: List[str] = []
        try:
            from core.engine import llama_runtime
            server = llama_runtime.installed_server()
            if server is not None:
                libraries.extend(
                    str(f) for f in server.parent.iterdir()
                    if f.is_file() and f.name.lower().startswith(("llama", "libllama"))
                    and f.suffix.lower() in (".dll", ".so", ".dylib")
                )
        except Exception:
            pass
        if libraries:
            return libraries
        try:
            import llama_cpp
            lib_dir = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
            if os.path.isdir(lib_dir):
                libraries.extend(
                    os.path.join(lib_dir, name) for name in os.listdir(lib_dir)
                    if name.lower().startswith(("llama", "libllama"))
                    and name.endswith((".dll", ".so", ".dylib"))
                )
        except Exception:
            pass
        return libraries

    @classmethod
    def _runtime_supports(cls, arch: Optional[str]) -> Optional[bool]:
        """
        Whether the installed llama.cpp runtime knows this architecture.

        There is no API that enumerates them, so the architecture name is looked
        for in the shared library's string table. Coarse, but it distinguishes a
        runtime that predates an architecture from one that has it, which is the
        question that matters.

        The libraries read are the engine's own. Reading llama_cpp's bundled
        lib, as this did, answered about a package the server has not used
        since it moved to the standalone binaries: it reported "unknown" for
        architectures the engine knows, and would have promised support for
        ones it cannot load.
        """
        if not arch:
            return None
        libraries = cls._runtime_libraries()
        if not libraries:
            return None
        # The null terminator is part of the needle. Without it "qwen3" matches
        # inside "qwen3next" and every runtime appears to support everything
        # that shares a prefix with something it has.
        needle = arch.encode("ascii", "ignore") + b"\x00"
        for path in libraries:
            try:
                with open(path, "rb") as handle:
                    if needle in handle.read():
                        return True
            except Exception:
                continue
        return False

    @classmethod
    def _runtime_build(cls) -> Optional[str]:
        """The engine build name, for messages that have to name what is behind."""
        try:
            from core.engine import llama_runtime
            info = llama_runtime.installed_build_info()
            return info.get("build") if info else None
        except Exception:
            return None

    @classmethod
    def _writer_supports(cls, arch: Optional[str]) -> Optional[bool]:
        """
        Whether the bundled gguf package can write this architecture.

        Asked of the package rather than of a mapping table in this file: the
        table only says how transformers and GGUF spell the same architecture,
        which is true whether or not the writer implements it. Deriving one
        from the other reports a model as writable because we know its name.
        """
        if not arch:
            return None
        gguf_mod = cls._get_gguf_module()
        if gguf_mod is None:
            return None
        try:
            return arch in set(gguf_mod.MODEL_ARCH_NAMES.values())
        except Exception:
            return None

    # ----------------------------------------------------------------- jobs

    @classmethod
    def start(cls, model_name: str, quantization: str = "Q4_K_M") -> Dict[str, Any]:
        """Queues a conversion and returns at once; poll the job for progress."""
        source = os.path.join(models_dir(), model_name)
        if not os.path.isdir(source):
            return {"success": False, "error": "Modello non trovato: " + str(model_name)}

        part_files = [f for f in os.listdir(source) if f.endswith((".part", ".download", ".tmp"))]
        if part_files:
            return {
                "success": False,
                "error": f"Il modello su disco ha un download incompleto ({len(part_files)} file .part in sospeso). Completa o riprendi il download dal Model Hub prima di convertire."
            }

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

        # Lo spazio si verifica prima di iniziare: le dimensioni sono note, e
        # scoprire il disco pieno a meta' costa dieci minuti e un file enorme
        # da cancellare a mano.
        piano_spazio = {"ok": True, "intermediate": "auto"}
        if facts is not None:
            piano_spazio = cls._plan_conversion_space(facts, quantization, models_dir())
            if not piano_spazio["ok"]:
                return {
                    "success": False,
                    "error": (
                        f"Spazio su disco insufficiente: servono circa "
                        f"{piano_spazio['needed_gb']} GB "
                        f"({piano_spazio['intermediate_gb']} GB di file intermedio "
                        f"piu {piano_spazio['final_gb']} GB di risultato, che "
                        f"coesistono durante la quantizzazione) e ne sono liberi "
                        f"{piano_spazio['free_gb']} GB. "
                        f"Liberane almeno {piano_spazio['missing_gb']} GB e riprova."
                    ),
                    "disk_plan": piano_spazio,
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

        threading.Thread(
            target=cls._run,
            args=(job, source, piano_spazio.get("intermediate", "auto")),
            daemon=True,
        ).start()
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
    def _run(cls, job: ConversionJob, source: str, outtype: str = "auto") -> None:
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
        intermediate = os.path.join(
            target_dir, job.source_model + "-" + outtype + ".gguf"
        )
        final_name = job.source_model + "." + job.quantization + ".gguf"
        final_path = os.path.join(target_dir, final_name)

        existing_gguf = cls._existing_gguf(source)

        try:
            if existing_gguf:
                # Source is already GGUF: the expensive Hugging Face conversion
                # was done on a previous run, so go straight to quantizing it.
                intermediate = existing_gguf
                job.stage = "reuse_gguf"
                job.progress = 50
                sorgente = os.path.basename(existing_gguf)
                if cls._precisione_gguf(sorgente) < 8.5:
                    # Quantizzare da un file gia' quantizzato arrotonda due
                    # volte, e nel risultato non si vede: va detto qui, perche'
                    # dopo non lo dira' piu' nessuno.
                    job.message = (
                        "Si riparte da " + sorgente + ", gia' quantizzato: il "
                        "risultato subira' due arrotondamenti. Per la qualita' "
                        "migliore converti di nuovo dai safetensors."
                    )
                else:
                    job.message = (
                        "Si riparte da " + sorgente + ": si passa direttamente "
                        "alla quantizzazione."
                    )
            else:
                job.status = "converting"
                job.stage = "hf_to_gguf"
                job.message = (
                    "Conversione dei pesi in GGUF ("
                    + ("massima fedelta a 16 bit" if outtype == "auto" else outtype)
                    + ")..."
                )
                job.progress = 5
                cls._convert_to_intermediate(source, intermediate, outtype)

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

    #: Bit per peso impliciti nel nome di un GGUF. Servono a scegliere la
    #: sorgente quando in una cartella ce n'e' piu' d'uno. L'ordine conta:
    #: "F16" e' contenuto in "BF16", quindi il piu' specifico va prima.
    _PRECISIONE_NOME = (
        ("F32", 32.0), ("BF16", 16.0), ("F16", 16.0),
        ("Q8_0", 8.5), ("Q6_K", 6.6),
        ("Q5_K_M", 5.7), ("Q5_K_S", 5.5), ("Q5_0", 5.5),
        ("Q4_K_M", 4.9), ("Q4_K_S", 4.6), ("Q4_0", 4.5),
        ("Q3_K_M", 3.9), ("Q3_K_S", 3.5), ("Q2_K", 3.0),
    )

    @classmethod
    def _precisione_gguf(cls, nome: str) -> float:
        """Quanti bit per peso promette il nome di questo file."""
        alto = os.path.basename(nome).upper()
        for tag, bpw in cls._PRECISIONE_NOME:
            if tag in alto:
                return bpw
        # Senza indizi si assume l'intermedio a 16 bit: e' cio' che produce
        # questo convertitore quando non mette un tag nel nome.
        return 16.0

    @classmethod
    def _existing_gguf(cls, source: str) -> Optional[str]:
        """Il GGUF a precisione piu' alta gia' presente nella cartella.

        Prima si prendeva il primo in ordine alfabetico. Con un Q8_0 e un
        Q4_K_M nella stessa cartella, "Q4_K_M" viene prima: si ripartiva dal
        piu' povero dei due e il risultato portava due arrotondamenti invece di
        uno, senza che niente lo dicesse.
        """
        if not os.path.isdir(source):
            return None
        nomi = [f for f in os.listdir(source) if f.endswith(".gguf")]
        if not nomi:
            return None
        # A parita' di precisione il nome decide, cosi' la scelta e' stabile.
        migliore = max(nomi, key=lambda n: (cls._precisione_gguf(n), n))
        return os.path.join(source, migliore)

    @staticmethod
    def _convert_to_intermediate(source: str, output: str,
                                 outtype: str = "auto") -> None:
        """
        Runs llama.cpp's converter in a subprocess.

        A subprocess rather than an import: the script is written as a CLI with
        module-level per-architecture state, and a conversion that exhausts
        memory must not take the server down with it.
        """
        import sys

        # 1. Pre-conversion completeness check
        if os.path.isdir(source):
            dir_files = os.listdir(source)
            part_files = [f for f in dir_files if f.endswith((".part", ".download", ".tmp"))]
            if part_files:
                raise RuntimeError(
                    f"Il modello su disco ha un download incompleto ({len(part_files)} file .part/download in sospeso). "
                    f"Completa o riprendi il download dal Model Hub prima di avviare la conversione GGUF."
                )
            index_path = os.path.join(source, "model.safetensors.index.json")
            if os.path.exists(index_path):
                try:
                    with open(index_path, "r", encoding="utf-8") as f_idx:
                        idx_data = json.load(f_idx)
                    weight_map = idx_data.get("weight_map", {})
                    declared_shards = set(weight_map.values())
                    missing = [f for f in declared_shards if not os.path.exists(os.path.join(source, f))]
                    if missing:
                        raise RuntimeError(
                            f"Il modello è incompleto: mancano {len(missing)} shard su {len(declared_shards)} dichiarati. "
                            f"Completa il download dal Model Hub prima di convertire."
                        )
                except (json.JSONDecodeError, OSError):
                    pass

        command = [
            sys.executable, CONVERTER_PATH, source,
            "--outfile", output, "--outtype", outtype,
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
            # Diagnostic for experimental / unmapped architectures or tensors
            if "is not supported" in output_text or "Can not map tensor" in output_text:
                lines = [l for l in output_text.splitlines() if "ERROR" in l or "ValueError" in l or "Can not map" in l or "not supported" in l]
                tail = lines[-3:] if lines else output_text.splitlines()[-3:]
                raise RuntimeError("L'architettura o i tensori del modello non sono ancora supportati da convert_hf_to_gguf di llama.cpp: " + " | ".join(tail))
            tail = output_text.splitlines()[-4:] or ["nessun output"]
            raise RuntimeError("convert_hf_to_gguf ha fallito: " + " | ".join(tail))
        if not os.path.exists(output):
            raise RuntimeError("la conversione non ha prodotto alcun file")

    @classmethod
    def _quantize(cls, source: str, output: str, quant_type: str) -> None:
        """Quantizes in-process through llama.dll, so no external tool is needed."""
        import ctypes
        from llama_cpp import llama_cpp as C

        ftype = getattr(C, "LLAMA_FTYPE_MOSTLY_" + quant_type, None)
        if ftype is None:
            raise ValueError("llama.cpp non conosce il tipo " + str(quant_type))

        params = C.llama_model_quantize_default_params()
        params.ftype = ftype
        params.nthread = max((os.cpu_count() or 4) - 1, 1)

        # Il log della libreria si raccoglie: senza, un fallimento arriva
        # all'utente come "ha restituito 1" e il motivo -- un tensore con
        # dimensioni non divisibili per 256, il disco pieno, un file corrotto --
        # resta sullo stderr del server, dove nessuno lo cerca.
        cls._assicura_log_llama(C)
        cls._log_righe = []
        try:
            code = C.llama_model_quantize(
                source.encode("utf-8"), output.encode("utf-8"), ctypes.byref(params)
            )
            righe = list(cls._log_righe)
        finally:
            cls._log_righe = None

        if code != 0:
            dettaglio = cls._motivo_quantizzazione(righe, quant_type)
            raise RuntimeError(
                "quantizzazione in " + str(quant_type) + " fallita (codice "
                + str(code) + "). " + dettaglio
            )

    #: La callback di log di llama.cpp e il suo bersaglio. Si installa una
    #: volta sola e non si toglie mai: `llama_log_set(None, ...)` solleva
    #: ArgumentError invece di disinstallare, e una callback raccolta dal
    #: garbage collector mentre la libreria puo' ancora chiamarla fa cadere il
    #: processo. La raccolta si accende riempiendo `_log_righe`.
    _log_cb = None
    _log_righe: Optional[List[str]] = None

    @classmethod
    def _assicura_log_llama(cls, C) -> None:
        """Instrada il log di llama.cpp, una volta per processo."""
        import ctypes

        if cls._log_cb is not None:
            return

        @ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
        def _inoltra(_livello, testo, _dati):
            try:
                riga = (testo or b"").decode("utf-8", errors="replace").strip()
            except Exception:
                return
            if not riga:
                return
            bersaglio = cls._log_righe
            if bersaglio is not None:
                # Solo la coda: una conversione riuscita ne produce migliaia, e
                # quando fallisce il messaggio utile e' in fondo.
                bersaglio.append(riga)
                del bersaglio[:-40]
            log.debug("[llama.cpp] %s", riga)

        cls._log_cb = _inoltra
        C.llama_log_set(_inoltra, ctypes.c_void_p(0))

    #: Righe di llama.cpp che spiegano un fallimento, con la traduzione di cosa
    #: puo' farci l'utente. La prima che compare vince.
    _CAUSE_NOTE = (
        ("not divisible by",
         "Il modello ha tensori con righe non multiple di 256, che i tipi K "
         "(Q2_K, Q3_K, Q4_K...) non sanno dividere in blocchi. Prova Q8_0 o "
         "Q4_0, che non hanno questo vincolo."),
        ("failed to write",
         "Scrittura interrotta: quasi sempre spazio esaurito sul volume di "
         "destinazione mentre il file intermedio e' ancora li'."),
        ("No space left",
         "Disco pieno durante la scrittura del risultato."),
        ("unknown model architecture",
         "L'architettura non e' supportata da questa build di llama.cpp."),
        ("failed to load model",
         "Il file di partenza non si apre: se e' un intermedio rimasto da una "
         "conversione interrotta, cancellalo e rifai la conversione."),
    )

    @classmethod
    def _motivo_quantizzazione(cls, righe: List[str], quant_type: str) -> str:
        """Da cosa ha scritto llama.cpp a cosa puo' farci chi legge."""
        testo = " ".join(righe)
        for indizio, spiegazione in cls._CAUSE_NOTE:
            if indizio.lower() in testo.lower():
                return spiegazione
        ultima = next((r for r in reversed(righe) if r), "")
        if ultima:
            return "llama.cpp ha riportato: " + ultima
        return ("llama.cpp non ha lasciato dettagli. Cause tipiche: spazio su "
                "disco esaurito, oppure un tipo K su un modello con dimensioni "
                "non compatibili.")
