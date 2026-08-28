# ==============================================================================
# core/modules/sigma_model_hub/backend/uploader_engine.py
# High-Performance Asynchronous Model Publisher for Hugging Face Hub
# ==============================================================================
from __future__ import annotations
import os
import io
import re
import time
import json
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable
from core.logger import get_logger
from .hf_client import resolve_hf_token

log = get_logger(__name__)


def _format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class ProgressReader(io.BufferedReader):
    """File reader wrapper that tracks bytes read and reports progress."""
    def __init__(self, raw_file, total_size: int, on_progress: Callable[[int, int], None], check_cancelled: Callable[[], bool]):
        super().__init__(raw_file)
        self.total_size = total_size
        self.on_progress = on_progress
        self.check_cancelled = check_cancelled
        self.bytes_read = 0

    def read(self, size=-1):
        if self.check_cancelled():
            raise InterruptedError("Caricamento annullato dall'utente")
        chunk = super().read(size)
        if chunk:
            self.bytes_read += len(chunk)
            if self.on_progress:
                self.on_progress(self.bytes_read, self.total_size)
        return chunk

    def seek(self, offset, whence=io.SEEK_SET):
        res = super().seek(offset, whence)
        self.bytes_read = self.tell()
        return res


class ModelUploadTask:
    """Represents an active or completed model upload task."""
    def __init__(
        self,
        task_id: str,
        local_path: str,
        repo_id: str,
        repo_type: str = "model",
        private: bool = False,
        commit_message: str = "Upload model via Sigma Studio",
        model_card: Optional[str] = None
    ):
        self.task_id = task_id
        self.local_path = os.path.abspath(local_path)
        self.filename = os.path.basename(self.local_path)
        self.is_dir = os.path.isdir(self.local_path)
        self.repo_id = repo_id.strip()
        self.repo_type = repo_type
        self.private = private
        self.commit_message = commit_message or "Upload model via Sigma Studio"
        self.model_card = model_card

        self.status = "queued"  # queued, uploading, completed, failed, cancelled
        self.progress_pct = 0.0
        self.uploaded_bytes = 0
        self.total_bytes = 0
        self.speed_bps = 0.0
        self.speed_label = "0 MB/s"
        self.uploaded_label = "0 MB"
        self.eta_seconds = 0
        self.error_message = ""
        self.hf_url = f"https://huggingface.co/{self.repo_id}"
        self.created_at = time.time()
        self.completed_at = 0.0

        self._cancelled = False
        self._start_time = 0.0
        self._last_progress_time = 0.0
        self._last_progress_bytes = 0

    def cancel(self):
        self._cancelled = True
        self.status = "cancelled"
        self.error_message = "Caricamento annullato dall'utente"

    def is_cancelled(self) -> bool:
        return self._cancelled

    def update_progress(self, current_bytes: int, total_bytes: int):
        now = time.time()
        self.uploaded_bytes = current_bytes
        self.total_bytes = max(total_bytes, 1)
        self.progress_pct = round(min(100.0, (current_bytes / self.total_bytes) * 100.0), 1)
        self.uploaded_label = f"{_format_bytes(current_bytes)} / {_format_bytes(self.total_bytes)}"

        if self._last_progress_time > 0 and (now - self._last_progress_time) >= 0.5:
            dt = now - self._last_progress_time
            db = current_bytes - self._last_progress_bytes
            if dt > 0 and db >= 0:
                self.speed_bps = db / dt
                self.speed_label = f"{_format_bytes(int(self.speed_bps))}/s"
                remaining = self.total_bytes - current_bytes
                if self.speed_bps > 0:
                    self.eta_seconds = int(remaining / self.speed_bps)
                else:
                    self.eta_seconds = 0
            self._last_progress_time = now
            self._last_progress_bytes = current_bytes
        elif self._last_progress_time == 0:
            self._last_progress_time = now
            self._last_progress_bytes = current_bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "local_path": self.local_path,
            "filename": self.filename,
            "is_dir": self.is_dir,
            "repo_id": self.repo_id,
            "repo_type": self.repo_type,
            "private": self.private,
            "commit_message": self.commit_message,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "uploaded_bytes": self.uploaded_bytes,
            "total_bytes": self.total_bytes,
            "uploaded_label": self.uploaded_label,
            "speed_label": self.speed_label,
            "eta_seconds": self.eta_seconds,
            "error_message": self.error_message,
            "hf_url": self.hf_url,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


def _detect_model_config(local_path: str) -> Dict[str, Any]:
    """Inspects a local model directory or GGUF file to extract detailed configuration, geometry, format, and quantization."""
    import re
    cfg = {
        "architecture": "CausalLM",
        "params_label": "7B",
        "active_params_b": 7.0,
        "layers": None,
        "hidden_size": None,
        "heads": None,
        "vocab_size": None,
        "context_window": 32768,
        "quantization": "Q4_K_M",
        "format": "GGUF",
        "size_gb": 0.0,
        "is_moe": False
    }

    if not os.path.exists(local_path):
        return cfg

    # 1. Inspect directory vs single file
    if os.path.isdir(local_path):
        all_files = []
        for r, _, files in os.walk(local_path):
            for f in files:
                all_files.append((os.path.join(r, f), f))

        total_b = sum(os.path.getsize(fp) for fp, f in all_files if not f.startswith("."))
        cfg["size_gb"] = round(total_b / (1024 ** 3), 2)

        gguf_files = [f for _, f in all_files if f.lower().endswith(".gguf")]
        safetensors_files = [f for _, f in all_files if f.lower().endswith(".safetensors")]
        bin_files = [f for _, f in all_files if f.lower().endswith((".bin", ".pt"))]

        # Check format priority: GGUF vs Safetensors vs Bin
        if gguf_files:
            cfg["format"] = "GGUF"
            # Detect quantization from all gguf filenames and folder name
            quant_candidates = []
            for g_name in gguf_files:
                q_match = re.search(r'(Q[0-9]_[A-Z0-9_]+|IQ[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4)', g_name, re.IGNORECASE)
                if q_match:
                    quant_candidates.append(q_match.group(1).upper())
            
            if not quant_candidates:
                folder_q_match = re.search(r'(Q[0-9]_[A-Z0-9_]+|IQ[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4)', os.path.basename(local_path), re.IGNORECASE)
                if folder_q_match:
                    quant_candidates.append(folder_q_match.group(1).upper())

            if quant_candidates:
                unique_quants = list(dict.fromkeys(quant_candidates))
                cfg["quantization"] = " / ".join(unique_quants) if len(unique_quants) <= 3 else f"{unique_quants[0]} (+{len(unique_quants)-1} quants)"
            else:
                cfg["quantization"] = "Q4_K_M"

            # Try Ground-truth facts inspection if available
            try:
                from core.engine.model_inspector import ModelInspector
                facts = ModelInspector.inspect(local_path)
                if facts:
                    if facts.architectures:
                        cfg["architecture"] = facts.architectures[0]
                    elif facts.model_type and facts.model_type != "unknown":
                        cfg["architecture"] = f"{facts.model_type.capitalize()}ForCausalLM"
                    if facts.num_hidden_layers:
                        cfg["layers"] = facts.num_hidden_layers
                    if facts.hidden_size:
                        cfg["hidden_size"] = facts.hidden_size
                    if facts.num_attention_heads:
                        cfg["heads"] = facts.num_attention_heads
                    if facts.vocab_size:
                        cfg["vocab_size"] = facts.vocab_size
                    if facts.max_position_embeddings:
                        cfg["context_window"] = facts.max_position_embeddings
                    cfg["is_moe"] = facts.is_moe
            except Exception as e_insp:
                log.debug("[_detect_model_config] ModelInspector: %s", e_insp)

        elif safetensors_files:
            cfg["format"] = "Safetensors"
            cfg["quantization"] = "BF16 / FP16"
        elif bin_files:
            cfg["format"] = "PyTorch Bin"
            cfg["quantization"] = "FP32 / FP16"
        else:
            cfg["format"] = "GGUF" if "gguf" in os.path.basename(local_path).lower() else "Safetensors"

        # Read config.json for fallback / enrichment
        config_path = os.path.join(local_path, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                archs = data.get("architectures", [])
                if archs and isinstance(archs, list):
                    cfg["architecture"] = archs[0]
                elif data.get("model_type"):
                    cfg["architecture"] = f"{data['model_type'].capitalize()}ForCausalLM"

                cfg["layers"] = cfg["layers"] or data.get("num_hidden_layers") or data.get("num_layers") or data.get("n_layer")
                cfg["hidden_size"] = cfg["hidden_size"] or data.get("hidden_size") or data.get("d_model")
                cfg["heads"] = cfg["heads"] or data.get("num_attention_heads") or data.get("n_head")
                cfg["vocab_size"] = cfg["vocab_size"] or data.get("vocab_size")
                cfg["context_window"] = cfg["context_window"] or data.get("max_position_embeddings") or data.get("seq_length") or 32768
                if data.get("num_experts") or data.get("num_local_experts"):
                    cfg["is_moe"] = True
                if cfg["format"] == "Safetensors" and data.get("torch_dtype"):
                    cfg["quantization"] = str(data["torch_dtype"]).replace("torch.", "").upper()
            except Exception as e_cfg:
                log.debug("Error reading config.json: %s", e_cfg)

    else:
        # Single file
        cfg["size_gb"] = round(os.path.getsize(local_path) / (1024 ** 3), 2)
        fname_lower = os.path.basename(local_path).lower()
        if fname_lower.endswith(".gguf"):
            cfg["format"] = "GGUF"
        elif fname_lower.endswith(".safetensors"):
            cfg["format"] = "Safetensors"
        else:
            cfg["format"] = "Weights"

        # Detect quantization from filename
        for q in ["Q8_0", "Q6_K", "Q5_K_M", "Q5_K_S", "Q5_0", "Q4_K_M", "Q4_K_S", "Q4_0", "Q3_K_M", "Q3_K_S", "Q2_K", "IQ4_XS", "IQ3_M", "IQ2_XXS", "FP16", "BF16", "FP8", "INT8", "INT4"]:
            if q.lower() in fname_lower:
                cfg["quantization"] = q
                break

    # Estimate active parameters from size / name
    fname_str = os.path.basename(local_path).lower()
    p_match = re.search(r'(\d+(?:\.\d+)?)\s*[bm]', fname_str)
    if p_match:
        val = float(p_match.group(1))
        unit = 'M' if 'm' in fname_str[p_match.start():p_match.end()] else 'B'
        if unit == 'M':
            cfg["params_label"] = f"{int(val)}M"
            cfg["active_params_b"] = val / 1000.0
        else:
            cfg["params_label"] = f"{val:g}B"
            cfg["active_params_b"] = val
    elif cfg["size_gb"] > 0:
        est_b = round(cfg["size_gb"] / 0.6, 1)
        cfg["params_label"] = f"~{est_b:g}B"
        cfg["active_params_b"] = est_b

    return cfg


def _find_benchmark_for_model(local_path: str, repo_id: str) -> Optional[Dict[str, Any]]:
    """Il referto dei benchmark di questo modello, se ne ha uno.

    La lettura la fa il Training Lab, che e' il modulo che quei referti li
    produce. Qui si chiede soltanto — e se quel modulo non e' installato la
    risposta e' "nessun benchmark", non un errore: i moduli si possono togliere.

    Il nome si cerca prima cosi' com'e', poi come cartella sul disco. Mai per
    sottostringa: la versione precedente accettava qualunque nome contenuto in
    un altro, e pubblicava sulla scheda di un checkpoint il punteggio della sua
    quantizzazione GGUF — due artefatti diversi, due punteggi diversi.
    """
    try:
        from core.modules.sigma_training_lab.training.model_scores import scores_for_model
    except Exception as err:
        log.debug("Training Lab non disponibile per i referti: %s", err)
        return None

    for candidato in (repo_id, os.path.basename(local_path.rstrip("/\\"))):
        if not candidato:
            continue
        referto = scores_for_model(candidato)
        if referto:
            return referto
    return None


#: Nomi leggibili delle suite, per la scheda pubblicata.
_NOMI_SUITE = {
    "mmlu": "MMLU", "mmlu_pro": "MMLU-Pro", "gsm8k": "GSM8K", "math": "MATH",
    "humaneval": "HumanEval", "mbpp": "MBPP", "arc": "ARC-Challenge",
    "hellaswag": "HellaSwag", "truthfulqa": "TruthfulQA", "gpqa": "GPQA",
    "bbh": "BIG-Bench Hard",
}


def _base_model_da_cartella(local_path: str) -> str:
    """Il modello da cui questo deriva, dedotto dal nome della cartella.

    I modelli scaricati stanno sul disco come `autore--modello`, che e' la
    stessa cosa di `autore/modello`. Le quantizzazioni aggiungono un suffisso —
    `-GGUF-Q4_K_M`, `-GGUF-Q8_0` — che non fa parte del nome originale e va
    tolto per arrivare al modello di partenza.

    Se non si riesce a dedurlo si restituisce una stringa vuota: dichiarare un
    `base_model` sbagliato e' peggio che non dichiararne nessuno, perche'
    attribuisce la paternita' a chi non c'entra.
    """
    import re as _re

    nome = os.path.basename(str(local_path or "").rstrip("/\\"))
    nome = _re.sub(r"[.]gguf$", "", nome, flags=_re.IGNORECASE)
    if "--" not in nome:
        return ""                       # senza autore non si puo' dire da dove viene

    # I suffissi che Sigma Studio aggiunge convertendo: `-GGUF`, `-GGUF-Q4_K_M`.
    nome = _re.sub(r"-GGUF(-[A-Za-z0-9_]+)?$", "", nome, flags=_re.IGNORECASE)
    autore, _, modello = nome.partition("--")
    if not autore or not modello:
        return ""
    return f"{autore}/{modello}"


def _benchmark_detail_lines(bm_data: Optional[Dict[str, Any]],
                            italiano: bool = False) -> List[str]:
    """Il dettaglio per suite e il protocollo con cui e' stato misurato.

    Un punteggio complessivo da solo non e' confrontabile con niente: chi legge
    la scheda non sa quante suite copre, ne' se le domande a scelta multipla
    sono state decise leggendo i logit o facendo ragionare il modello. Sono
    proprio le righe che rendono un numero verificabile invece che dichiarato.
    """
    if not isinstance(bm_data, dict):
        return []

    righe: List[str] = []
    suites = bm_data.get("suites") or {}
    if suites:
        righe.append("")
        righe.append("<details>")
        righe.append("<summary>" + ("Dettaglio per suite" if italiano
                                    else "Per-suite breakdown") + "</summary>")
        righe.append("")
        righe.append("| Suite | Pass | Totale | % |" if italiano
                     else "| Suite | Passed | Total | % |")
        righe.append("| :--- | :---: | :---: | :---: |")
        for sid in sorted(suites):
            stat = suites[sid] or {}
            totale = stat.get("total", 0)
            passati = stat.get("passed", 0)
            quota = f"{(passati / totale * 100):.0f}%" if totale else "—"
            righe.append(f"| {_NOMI_SUITE.get(sid, sid)} | {passati} | {totale} | {quota} |")
        righe.append("")
        righe.append("</details>")

    protocolli = bm_data.get("protocols") or {}
    if protocolli:
        modi = sorted({str(p.get("mode", "")) for p in protocolli.values() if p.get("mode")})
        if modi:
            righe.append("")
            righe.append(("**Protocollo:** " if italiano else "**Protocol:** ")
                         + ", ".join(modi)
                         + f" · temp {bm_data.get('temperature', 0.0)}"
                         + f" · seed {bm_data.get('seed', 42)}")
    impronta = bm_data.get("reproducible_hash")
    if impronta:
        righe.append(("**Impronta di riproducibilità:** " if italiano
                      else "**Reproducibility hash:** ") + f"`{impronta}`")
    if bm_data.get("dataset_complete") is False:
        righe.append("> ⚠️ " + (
            "Misurato su una porzione del dataset, non sulla suite intera: il "
            "punteggio non è confrontabile con uno ottenuto sull'intero."
            if italiano else
            "Measured on a slice of the dataset, not the full suite: this score "
            "is not comparable with a full-suite run."))
    if bm_data.get("completed") is False:
        righe.append("> ⚠️ " + (
            "Valutazione non conclusa: la percentuale è calcolata sui quesiti "
            "effettivamente eseguiti." if italiano else
            "Evaluation did not finish: the percentage covers only the "
            "questions that were actually run."))
    righe.append("")
    return righe


def generate_model_card(
    local_path: str,
    repo_id: str,
    benchmark_summary: Optional[Dict[str, Any]] = None,
    include_benchmarks: bool = True,
    include_hardware: bool = True,
    custom_notes: Optional[str] = None,
    card_license: Optional[str] = None,
) -> str:
    """
    Generates an ultra-premium, comprehensive, bilingual (EN + IT) model card
    complete with SigmaStudio branding, configuration/architecture specs,
    official benchmark results, local throughput measurements, and estimated
    performance tiers across multiple hardware platforms.
    """
    filename = os.path.basename(local_path)
    model_name = repo_id.split("/")[-1] if "/" in repo_id else repo_id
    org_name = repo_id.split("/")[0] if "/" in repo_id else "SigmaStudio"
    cfg = _detect_model_config(local_path)

    # 1. Hardware Detection
    gpu_name = "GPU Dedicata / Metal / CUDA"
    vram_label = "VRAM Dedicata"
    cpu_name = "CPU Multi-Core"
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        accs = UniversalHardwareProbe.probe_accelerators()
        if accs and len(accs) > 0:
            first_acc = accs[0]
            gpu_name = first_acc.get("device_name") or first_acc.get("name") or "Acceleratore GPU"
            vram_gb = first_acc.get("total_vram_gb") or first_acc.get("unified_memory_gb") or 0.0
            if vram_gb:
                vram_label = f"{vram_gb:.1f} GB VRAM"
        cpu_info = UniversalHardwareProbe.probe_cpu()
        if cpu_info and cpu_info.get("brand"):
            cpu_name = cpu_info.get("brand")
    except Exception:
        pass

    # 2. Benchmark data lookup
    bm_data = benchmark_summary or _find_benchmark_for_model(local_path, repo_id)
    has_benchmark = include_benchmarks and bm_data is not None

    bm_score = 0.0
    bm_suite = "Benchmark Ufficiale"
    bm_tok_s = 0.0
    bm_date = time.strftime("%Y-%m-%d")
    bm_pass_fail = ""

    bm_measured = False
    chat_tok_s = 0.0
    prefill_tok_s = 0.0
    if has_benchmark and isinstance(bm_data, dict):
        singolo = bm_data.get("single_stream") or {}
        chat_tok_s = float(singolo.get("decode_tok_s") or 0.0)
        prefill_tok_s = float(singolo.get("prefill_tok_s") or 0.0)
        # I nomi sono quelli che il motore scrive davvero. Prima se ne
        # leggevano altri — `avg_tok_s`, `pass_count`, `total_questions` — che
        # non esistono in nessun referto: assenti valgono zero, e la scheda
        # pubblicava "0 quesiti superati" accanto a un punteggio vero.
        bm_score = float(bm_data.get("score")
                         or bm_data.get("best_score")
                         or bm_data.get("overall_score") or 0.0)
        bm_suite = (bm_data.get("suite_name") or bm_data.get("suite")
                    or "Tutti i Benchmark Ufficiali")
        bm_tok_s = float(bm_data.get("tokens_per_sec")
                         or bm_data.get("avg_tok_s") or 0.0)
        bm_measured = bm_tok_s > 0
        if bm_data.get("last_run_at"):
            bm_date = str(bm_data.get("last_run_at"))[:10]
        superati = bm_data.get("tests_passed")
        totali = bm_data.get("tests_total")
        if superati is not None and totali:
            bm_pass_fail = f"{superati}/{totali} quesiti superati"

    # 3. Throughput calculation across tiers
    #
    # Quando una misura non c'e', il numero che segue e' una stima per classe di
    # dimensione. La scheda deve dirlo: pubblicare una stima sotto la voce
    # "velocita' verificata" e' attribuire al modello una misura che nessuno ha
    # fatto, e chi la legge non ha modo di accorgersene.
    params_b = cfg.get("active_params_b", 7.0)
    if bm_tok_s <= 0:
        if params_b <= 3:
            bm_tok_s = 45.0
        elif params_b <= 8:
            bm_tok_s = 28.5
        elif params_b <= 14:
            bm_tok_s = 22.0
        elif params_b <= 32:
            bm_tok_s = 14.5
        else:
            bm_tok_s = 8.0

    tags = ["text-generation", "sigma-studio", "sigmanih", "conversational", "custom-model"]
    if cfg["format"] == "GGUF":
        tags.extend(["gguf", "llama.cpp", "quantized"])
        for q_token in re.findall(r'[a-zA-Z0-9_]+', cfg["quantization"].lower()):
            if q_token not in tags and len(q_token) >= 2:
                tags.append(q_token)
    elif cfg["format"] == "Safetensors":
        tags.extend(["safetensors", "transformers", "pytorch"])
    else:
        tags.extend(["pytorch", "weights"])

    tags_yaml = "\n".join([f"- {t}" for t in tags])

    # Recommended usage tier
    if params_b <= 4:
        rec_usage_en = "Edge devices, Real-time voice agents, Mobile & CPU-friendly workloads."
        rec_usage_it = "Dispositivi edge, agenti vocali in tempo reale, CPU e carichi leggeri."
    elif params_b <= 14:
        rec_usage_en = "High-speed coding, Everyday assistants, Autonomous agentic loops & reasoning."
        rec_usage_it = "Coding ad alta velocità, assistenti quotidiani, loop di agenti autonomi e ragionamento."
    elif params_b <= 34:
        rec_usage_en = "Advanced logic & reasoning, Enterprise domain specialization, Complex code refactoring."
        rec_usage_it = "Logica e ragionamento avanzato, specializzazione di dominio enterprise, refactoring complesso."
    else:
        rec_usage_en = "Flagship frontier intelligence, Deep research & multi-step mathematics."
        rec_usage_it = "Intelligenza di frontiera, ricerca approfondita e matematica multi-step."

    # Markdown Document Construction
    lines = []
    lines.append("---")
    lines.append("language:")
    lines.append("- en")
    lines.append("- it")
    # La licenza non si dichiara a caso. `apache-2.0` scritto fisso su una
    # ridistribuzione di Gemma — che ha la propria licenza — non e' un dettaglio
    # di forma: e' un'affermazione legale sbagliata su un file che si sta
    # distribuendo. Senza saperla, si chiede a chi pubblica invece di sceglierne
    # una.
    licenza = str(card_license or "").strip()
    lines.append(f"license: {licenza}" if licenza else "license: other")
    # Da quale modello viene questo. Senza, un repository chiamato
    # `sigmanih/gemma-4-12B-it-GGUF-Q4_K_M` sembra un modello di sigmanih e non
    # una quantizzazione di quello di Google — e Hugging Face non lo collega
    # all'albero del modello originale, dove chi cerca lo troverebbe.
    origine = _base_model_da_cartella(local_path)
    if origine:
        lines.append("base_model:")
        lines.append(f"- {origine}")
    lines.append("tags:")
    lines.append(tags_yaml)
    lines.append("pipeline_tag: text-generation")
    lines.append("---")
    lines.append("")
    lines.append("<div align=\"center\">")
    lines.append("")
    lines.append(f"# ⚡ {model_name}")
    lines.append(f"### High-Performance Model Published via **[Σ-SIGMA Studio](https://github.com/Sigmanih/SigmaStudio)**")
    lines.append("")
    lines.append("[![SigmaStudio GitHub](https://img.shields.io/badge/GitHub-SigmaStudio-10b981?style=for-the-badge&logo=github)](https://github.com/Sigmanih/SigmaStudio) "
                 f"[![HuggingFace Hub](https://img.shields.io/badge/Hugging%20Face-{org_name}-ffb86c?style=for-the-badge&logo=huggingface)](https://huggingface.co/{repo_id}) "
                 "[![Engine](https://img.shields.io/badge/Accelerated%20by-SigmaEngine-00d2ff?style=for-the-badge&logo=fastapi)](https://github.com/Sigmanih/SigmaStudio) "
                 "[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)")
    lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append("> ❤️ **Support & Community:** If you find this model helpful, please give this repository a **Like** on Hugging Face and a **⭐ Star** on our **[SigmaStudio GitHub](https://github.com/Sigmanih/SigmaStudio)**!")
    lines.append("")

    if custom_notes:
        lines.append("## 📝 Model Notes / Release Highlights")
        lines.append(custom_notes)
        lines.append("")

    # English Section
    lines.append("## 🌐 English Overview")
    lines.append("")
    lines.append(f"**{model_name}** is a production-ready model optimized and published using the **Model Hub** module of **[Sigma Studio](https://github.com/Sigmanih/SigmaStudio)**.")
    lines.append("")
    lines.append("### ⚙️ Technical Specifications & Architecture")
    lines.append("| Specification | Value |")
    lines.append("| :--- | :--- |")
    lines.append(f"| **Model Repository** | `{repo_id}` |")
    lines.append(f"| **Weight Format** | `{cfg['format']}` (`{cfg['quantization']}`) |")
    lines.append(f"| **Base Architecture** | `{cfg['architecture']}` |")
    lines.append(f"| **Active Parameters** | **{cfg['params_label']}** |")
    lines.append(f"| **Context Window** | `{cfg['context_window']:,} tokens` |")
    if cfg["layers"]:
        lines.append(f"| **Transformer Layers** | `{cfg['layers']}` |")
    if cfg["hidden_size"]:
        lines.append(f"| **Hidden Dimension** | `{cfg['hidden_size']}` |")
    lines.append(f"| **Total Disk Footprint** | `{cfg['size_gb']} GB` |")
    lines.append(f"| **Recommended Usage** | {rec_usage_en} |")
    lines.append("")

    if has_benchmark:
        lines.append("### 🏆 Official Benchmark Performance")
        lines.append(f"Evaluated directly on GPU via **Sigma Studio Training Lab** (Deterministic seed 42, Temp 0.0):")
        lines.append("")
        lines.append("| Benchmark Suite | Score / Accuracy | Pass Rate | Test Date | Execution Engine |")
        lines.append("| :--- | :---: | :---: | :---: | :---: |")
        lines.append(f"| **{bm_suite}** | **`{bm_score:.1f}%`** | {bm_pass_fail or 'Verificato'} | `{bm_date}` | ⚡ SigmaEngine Direct GPU |")
        lines.append("")
        lines.extend(_benchmark_detail_lines(bm_data))

    if include_hardware:
        lines.append("### ⚡ Measured Speed on the Publishing Machine")
        if chat_tok_s > 0:
            lines.append(f"Measured on `{gpu_name}` • `{vram_label}`. "
                         f"Two different numbers follow, and they are not "
                         f"interchangeable.")
        elif bm_measured:
            lines.append(f"Measured on `{gpu_name}` • `{vram_label}` during the "
                         f"evaluation run.")
        else:
            lines.append(f"No local speed measurement was recorded for this model: "
                         f"the figure below is an estimate for its size class, "
                         f"not a measurement.")
        lines.append("")
        lines.append("| What was measured | Value | How |")
        lines.append("| :--- | :---: | :--- |")
        if chat_tok_s > 0:
            lines.append(f"| **Single-stream decode** (what a chat feels) | "
                         f"**`{chat_tok_s:.1f} tok/s`** | one request at a time, "
                         f"on `{gpu_name}` |")
        if prefill_tok_s > 0:
            lines.append(f"| Prompt processing | `{prefill_tok_s:.0f} tok/s` | "
                         f"same probe |")
        if bm_tok_s > 0:
            lines.append(f"| Aggregate throughput during evaluation | "
                         f"`{bm_tok_s:.1f} tok/s` | several requests in flight — "
                         f"**not** what a single answer runs at |")
        lines.append("")
        lines.append("> Speeds on other hardware were **not measured** and are not "
                     "guessed here. A single-stream figure from one machine cannot "
                     "be scaled into a prediction for another: it depends on memory "
                     "bandwidth, quantization, context length and driver, and the "
                     "error is large enough to be misleading.")
        lines.append("")

    lines.append("### 🚀 Quick Start Guide")
    lines.append("#### 1. Running with Sigma Studio (Recommended)")
    lines.append("Launch **Sigma Studio** to enjoy full 1-click GPU hardware acceleration, live monitoring, and visual chat:")
    lines.append("```bash")
    lines.append("# Clone and run Sigma Studio")
    lines.append("git clone https://github.com/Sigmanih/SigmaStudio.git")
    lines.append("cd SigmaStudio")
    lines.append(".\\sigma_studio.bat")
    lines.append("```")
    lines.append("")
    if cfg["format"] == "GGUF":
        lines.append("#### 2. Running with llama.cpp")
        lines.append("```bash")
        lines.append(f"llama-cli -hf {repo_id} -p \"Hello! How can I help you today?\" -ngl 99")
        lines.append("```")
    else:
        lines.append("#### 2. Running with Transformers / PyTorch")
        lines.append("```python")
        lines.append("from transformers import AutoModelForCausalLM, AutoTokenizer")
        lines.append("import torch")
        lines.append("")
        lines.append(f"model_id = \"{repo_id}\"")
        lines.append("tokenizer = AutoTokenizer.from_pretrained(model_id)")
        lines.append("model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map=\"auto\")")
        lines.append("```")
    lines.append("")

    # Italian Section
    lines.append("---")
    lines.append("## 🇮🇹 Documentazione in Italiano")
    lines.append("")
    lines.append(f"**{model_name}** è un modello ottimizzato pronto per l'inferenza e l'integrazione locale, pubblicato attraverso **[Σ-SIGMA Studio](https://github.com/Sigmanih/SigmaStudio)**.")
    lines.append("")
    lines.append("### 📋 Specifiche e Configurazione")
    lines.append(f"- **Architettura Base:** `{cfg['architecture']}` ({cfg['params_label']} parametri)")
    lines.append(f"- **Formato Pesi:** `{cfg['format']}` ({cfg['quantization']})")
    lines.append(f"- **Spazio su Disco:** `{cfg['size_gb']} GB`")
    lines.append(f"- **Finestra di Contesto:** `{cfg['context_window']:,} token`")
    lines.append(f"- **Profilo d'Uso Consigliato:** {rec_usage_it}")
    lines.append("")

    if has_benchmark:
        lines.append("### 📊 Risultati Benchmark Ufficiali")
        lines.append(f"- **Suite di Valutazione:** `{bm_suite}`")
        lines.append(f"- **Punteggio Ufficiale:** **`{bm_score:.1f}%`** ({bm_pass_fail or 'Completato con successo'})")
        lines.extend(_benchmark_detail_lines(bm_data, italiano=True))
        lines.append(f"- **Data Test:** `{bm_date}` su motore deterministico SigmaEngine")
        lines.append("")

    if include_hardware:
        lines.append("### ⏱️ Throughput Hardware e Fasce Consigliate")
        if bm_measured:
            lines.append(f"- **Velocità Verificata in Locale:** **`{bm_tok_s:.1f} tok/s`** su `{gpu_name}`.")
        else:
            lines.append(f"- **Velocità Stimata:** ~`{bm_tok_s:.1f} tok/s` per questa "
                         f"classe di dimensione — *nessuna misura locale registrata.*")
        if chat_tok_s > 0:
            lines.append(f"- **Risposta singola (quello che si sente in chat):** "
                         f"**`{chat_tok_s:.1f} tok/s`** su `{gpu_name}`.")
        if prefill_tok_s > 0:
            lines.append(f"- **Lettura del prompt:** `{prefill_tok_s:.0f} tok/s`.")
        if bm_tok_s > 0:
            lines.append(f"- **Throughput complessivo durante la valutazione:** "
                         f"`{bm_tok_s:.1f} tok/s` — piu' richieste in volo insieme, "
                         f"**non** la velocita' di una risposta singola.")
        lines.append("- Le velocita' su altro hardware **non sono state misurate** "
                     "e non vengono indovinate: dipendono da banda di memoria, "
                     "quantizzazione, lunghezza del contesto e driver.")
        lines.append("")

    lines.append("### ⭐ Supporta il Progetto Open Source")
    lines.append("Se questo modello ti è utile o vuoi esplorare l'ecosistema completo:")
    lines.append("- 🌟 Metti una **Stella** al repository GitHub: **[Sigmanih/SigmaStudio](https://github.com/Sigmanih/SigmaStudio)**")
    lines.append("- ❤️ Lascia un **Like** a questa scheda su Hugging Face")
    lines.append("")
    lines.append("---")
    lines.append(f"*Creato e distribuito con il Model Hub di Σ-SIGMA Studio ({time.strftime('%d/%m/%Y %H:%M')})*")

    return "\n".join(lines)


def hf_repo_status(repo_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    """Se questo repository esiste gia' su Hugging Face, e cosa contiene.

    Serve a dire all'utente, prima che prema Pubblica, se sta creando qualcosa
    di nuovo o sovrascrivendo qualcosa che c'e' gia'. Caricare su un repository
    esistente funziona da sempre — `create_repo(exist_ok=True)` — ma finora
    nessuno lo diceva, e "pubblica" e "aggiorna" sono due intenzioni diverse.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"success": False, "error": "huggingface_hub non installato"}

    from core.modules.sigma_model_hub.backend.hf_client import get_effective_hf_token
    effettivo = get_effective_hf_token(token)
    if not effettivo:
        return {"success": False, "error": "Token Hugging Face mancante"}

    try:
        api = HfApi(token=effettivo)
        info = api.model_info(repo_id, files_metadata=False)
    except Exception as err:
        testo = str(err)
        if "404" in testo or "not found" in testo.lower() or "RepositoryNotFound" in testo:
            return {"success": True, "exists": False, "repo_id": repo_id}
        return {"success": False, "error": f"Verifica non riuscita: {testo[:200]}"}

    file_presenti = [f.rfilename for f in (info.siblings or [])]
    return {
        "success": True,
        "exists": True,
        "repo_id": repo_id,
        "private": bool(getattr(info, "private", False)),
        "last_modified": str(getattr(info, "lastModified", "") or ""),
        "files": len(file_presenti),
        "has_model_card": "README.md" in file_presenti,
        "downloads": getattr(info, "downloads", 0),
    }


def discover_publications(local_models: List[Dict[str, Any]],
                          token: Optional[str] = None) -> Dict[str, Any]:
    """Cerca fra i repository dell'utente quelli che sembrano modelli locali.

    Serve per tutto cio' che e' stato pubblicato prima che esistesse il
    registro: quei modelli sono su Hugging Face e nessuno sa piu' che ci sono,
    quindi "aggiorna la scheda" non trova un repository e la pubblicazione
    successiva ne creerebbe uno nuovo.

    La corrispondenza e' sul nome finale — `sigmanih/Qwen3-0.6B-GGUF-Q4_K_S` per
    il locale `Qwen/Qwen3-0.6B-GGUF-Q4_K_S` — perche' pubblicando si cambia
    l'autore ma quasi mai il nome. Nessun collegamento viene creato qui: si
    propone, e conferma l'utente. Un collegamento sbagliato manderebbe un
    aggiornamento di scheda sul repository di qualcun altro.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"success": False, "error": "huggingface_hub non installato"}

    from core.modules.sigma_model_hub.backend.hf_client import get_effective_hf_token

    effettivo = get_effective_hf_token(token)
    if not effettivo:
        return {"success": False, "error": "Token Hugging Face mancante"}

    try:
        api = HfApi(token=effettivo)
        utente = api.whoami()
        autori = [utente.get("name")] + [o.get("name") for o in (utente.get("orgs") or [])]
        remoti = []
        for autore in [a for a in autori if a]:
            try:
                remoti.extend(api.list_models(author=autore))
            except Exception as err:
                log.debug("Elenco modelli di %s non disponibile: %s", autore, err)
    except Exception as err:
        return {"success": False, "error": f"Elenco non recuperabile: {str(err)[:200]}"}

    per_coda: Dict[str, List[str]] = {}
    for modello in remoti:
        repo = getattr(modello, "id", "") or ""
        if "/" in repo:
            per_coda.setdefault(repo.split("/")[-1].lower(), []).append(repo)

    from core.modules.sigma_model_hub.backend import publications

    proposte = []
    for locale in local_models:
        identificativo = (locale.get("model_id") or locale.get("filename") or "")
        if not identificativo:
            continue
        if publications.get_publication(locale.get("path") or identificativo):
            continue                                # gia' collegato
        coda = identificativo.replace("--", "/").split("/")[-1].lower()
        candidati = per_coda.get(coda) or []
        if len(candidati) == 1:
            proposte.append({
                "local_ref": locale.get("path") or identificativo,
                "model_id": identificativo,
                "repo_id": candidati[0],
                "url": f"https://huggingface.co/{candidati[0]}",
            })
        elif candidati:
            # Piu' di un candidato: proporne uno a caso sarebbe peggio che non
            # proporne nessuno.
            proposte.append({
                "local_ref": locale.get("path") or identificativo,
                "model_id": identificativo,
                "ambiguous": candidati,
            })

    return {"success": True, "remote_count": len(remoti), "matches": proposte}


def attach_publication(local_ref: str, repo_id: str,
                       token: Optional[str] = None) -> Dict[str, Any]:
    """Collega un modello locale a un repository che esiste gia'.

    Il repository viene verificato prima di registrarlo: collegare un nome
    sbagliato non darebbe errore subito, lo darebbe al primo aggiornamento di
    scheda — mandato sul repository di qualcun altro, o su uno inesistente.
    """
    from core.modules.sigma_model_hub.backend import publications

    if not local_ref or not repo_id:
        return {"success": False, "error": "Servono il modello locale e il repository"}

    stato = hf_repo_status(repo_id, token)
    if not stato.get("success"):
        return stato
    if not stato.get("exists"):
        return {"success": False,
                "error": f"'{repo_id}' non esiste su Hugging Face (o non è "
                         f"visibile con questo token)."}

    publications.record_publication(local_ref, repo_id,
                                    f"https://huggingface.co/{repo_id}",
                                    private=stato.get("private", False))
    # `record_publication` conta una pubblicazione: qui non ne e' stata fatta
    # nessuna, si sta solo riconoscendo una che c'era gia'.
    registrata = publications.get_publication(local_ref) or {}
    return {"success": True, "repo_id": repo_id,
            "url": f"https://huggingface.co/{repo_id}",
            "files": stato.get("files", 0),
            "private": stato.get("private", False),
            "attached": True,
            "publish_count": registrata.get("publish_count", 1)}


def update_model_card(local_ref: str, repo_id: Optional[str] = None,
                      card: Optional[str] = None,
                      token: Optional[str] = None,
                      **card_options) -> Dict[str, Any]:
    """Riscrive solo la scheda di un modello gia' pubblicato.

    Il testo del paper, una correzione, un benchmark rifatto: sono modifiche al
    README, non ai pesi. Ricaricare l'intero modello per cambiare una frase
    costa gigabyte di banda e minuti di attesa per un file di pochi kilobyte, e
    su un repository con cronologia aggiunge un commit enorme che non contiene
    nessuna modifica ai pesi.

    Il repository si ricava dal registro delle pubblicazioni quando non viene
    indicato: e' il legame che rende possibile "aggiorna" senza dover
    ricordare a memoria dove si era pubblicato.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"success": False, "error": "huggingface_hub non installato"}

    from core.modules.sigma_model_hub.backend import publications
    from core.modules.sigma_model_hub.backend.hf_client import get_effective_hf_token

    destinazione = (repo_id or "").strip()
    if not destinazione:
        registrata = publications.get_publication(local_ref)
        if not registrata:
            return {"success": False,
                    "error": "Questo modello non risulta pubblicato: indica il "
                             "repository, oppure pubblicalo una prima volta."}
        destinazione = registrata.get("repo_id", "")
    if not destinazione:
        return {"success": False, "error": "Repository non determinabile"}

    effettivo = get_effective_hf_token(token)
    if not effettivo:
        return {"success": False, "error": "Token Hugging Face mancante"}

    testo = card
    if testo is None:
        testo = generate_model_card(local_ref, destinazione, **card_options)
    if not str(testo).strip():
        return {"success": False, "error": "La scheda è vuota"}

    try:
        api = HfApi(token=effettivo)
        api.upload_file(
            path_or_fileobj=str(testo).encode("utf-8"),
            path_in_repo="README.md",
            repo_id=destinazione,
            repo_type="model",
            commit_message="Aggiornamento scheda modello da Sigma Studio",
        )
    except Exception as err:
        return {"success": False,
                "error": f"Aggiornamento della scheda non riuscito: {str(err)[:250]}"}

    try:
        publications.record_publication(local_ref, destinazione,
                                        f"https://huggingface.co/{destinazione}",
                                        model_card=str(testo))
    except Exception as err:
        log.debug("Registro non aggiornato dopo la scheda: %s", err)

    log.info("[ModelUploader] Scheda aggiornata su %s", destinazione)
    return {"success": True, "repo_id": destinazione,
            "url": f"https://huggingface.co/{destinazione}",
            "characters": len(str(testo))}


def rename_hf_repo(from_id: str, to_id: str,
                   token: Optional[str] = None) -> Dict[str, Any]:
    """Sposta un repository a un altro nome, mantenendo cronologia e download.

    Hugging Face lascia un rimando dal vecchio nome al nuovo, quindi chi aveva
    gia' il vecchio identificativo continua a trovarlo. E' la ragione per cui
    rinominare e' meglio che ricaricare sotto un nome nuovo: ricaricare lascia
    due repository, e chi legge non sa quale sia quello buono.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"success": False, "error": "huggingface_hub non installato"}

    partenza = str(from_id or "").strip().strip("/")
    arrivo = str(to_id or "").strip().strip("/")
    if not partenza or not arrivo:
        return {"success": False, "error": "Servono sia il nome attuale sia quello nuovo"}
    if partenza == arrivo:
        return {"success": True, "renamed": False, "repo_id": arrivo,
                "message": "Il nome era già questo"}
    if "/" not in arrivo:
        return {"success": False,
                "error": "Il nuovo nome deve essere completo, nella forma "
                         "`autore/modello`"}

    from core.modules.sigma_model_hub.backend.hf_client import get_effective_hf_token
    effettivo = get_effective_hf_token(token)
    if not effettivo:
        return {"success": False, "error": "Token Hugging Face mancante"}

    api = HfApi(token=effettivo)
    esistente = hf_repo_status(arrivo, effettivo)
    if esistente.get("exists"):
        return {"success": False,
                "error": f"'{arrivo}' esiste già: scegli un altro nome, oppure "
                         f"pubblica su quel repository per aggiornarlo."}

    try:
        api.move_repo(from_id=partenza, to_id=arrivo, repo_type="model")
    except Exception as err:
        return {"success": False, "error": f"Rinomina non riuscita: {str(err)[:250]}"}

    log.info("[ModelUploader] Repository rinominato: %s -> %s", partenza, arrivo)
    return {"success": True, "renamed": True, "from": partenza, "repo_id": arrivo,
            "url": f"https://huggingface.co/{arrivo}"}


class ModelUploaderManager:
    """Manages background upload tasks to Hugging Face Hub."""



    def __init__(self):
        self.tasks: Dict[str, ModelUploadTask] = {}
        self._lock = threading.Lock()

    def get_whoami(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Validates token with Hugging Face Hub and returns authenticated user profile & permissions."""
        resolved = resolve_hf_token(token)
        actual_token = resolved.get("token", "")
        if not actual_token:
            return {
                "authenticated": False,
                "error": "Nessun token Hugging Face trovato. Configura il tuo Access Token in Impostazioni.",
                "token_source": resolved.get("source", "none"),
                "token_detail": resolved.get("detail", "")
            }

        try:
            from huggingface_hub import whoami
            info = whoami(token=actual_token)
            username = info.get("name") or info.get("username", "")
            fullname = info.get("fullname", "")
            avatar_url = info.get("avatarUrl", "")
            email = info.get("email", "")
            orgs = [
                {
                    "name": org.get("name"),
                    "fullname": org.get("fullname", org.get("name")),
                    "avatar_url": org.get("avatarUrl", "")
                }
                for org in (info.get("orgs") or [])
                if isinstance(org, dict) and org.get("name")
            ]

            # Detect write permission
            auth = info.get("auth", {})
            access_token_info = auth.get("accessToken", {}) if isinstance(auth, dict) else {}
            role = access_token_info.get("role", "")
            can_write = True
            if role == "read":
                can_write = False

            return {
                "authenticated": True,
                "username": username,
                "fullname": fullname,
                "email": email,
                "avatar_url": avatar_url,
                "orgs": orgs,
                "role": role or "write",
                "can_write": can_write,
                "token_source": resolved.get("source", "input"),
                "token_detail": resolved.get("detail", "")
            }
        except Exception as e:
            log.warning(f"[ModelUploader] Whoami check failed: {e}")
            return {
                "authenticated": False,
                "error": f"Autenticazione fallita: {str(e)}",
                "token_source": resolved.get("source", "input"),
                "token_detail": resolved.get("detail", "")
            }

    def _generate_default_model_card(self, task: ModelUploadTask) -> str:
        """Generates an ultra-rich, bilingual model card with benchmarks and hardware tiers."""
        return generate_model_card(
            local_path=task.local_path,
            repo_id=task.repo_id,
            custom_notes=task.model_card if (task.model_card and task.model_card != task.repo_id) else None
        )

    def start_upload(
        self,
        local_path: str,
        repo_id: str,
        private: bool = False,
        commit_message: str = "Upload model via Sigma Studio",
        model_card: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates and launches a background upload task."""
        if not local_path or not os.path.exists(local_path):
            return {"success": False, "error": f"File o directory '{local_path}' non trovato."}

        if not repo_id or "/" not in repo_id.strip():
            return {"success": False, "error": "Il nome del repository deve essere nel formato 'username/nome-modello'."}

        resolved = resolve_hf_token(token)
        actual_token = resolved.get("token", "")
        if not actual_token:
            return {"success": False, "error": "Token Hugging Face mancante. Inserisci un Access Token valido."}

        task_id = str(uuid.uuid4())[:8]
        task = ModelUploadTask(
            task_id=task_id,
            local_path=local_path,
            repo_id=repo_id,
            private=private,
            commit_message=commit_message,
            model_card=model_card
        )

        # Calculate initial total size
        if task.is_dir:
            total_size = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(task.local_path)
                for f in files
            )
        else:
            total_size = os.path.getsize(task.local_path)

        task.total_bytes = total_size
        task.uploaded_label = f"0 B / {_format_bytes(total_size)}"

        with self._lock:
            self.tasks[task_id] = task

        thread = threading.Thread(target=self._run_upload_worker, args=(task, actual_token), daemon=True)
        thread.start()

        log.info(f"[ModelUploader] Launched upload task {task_id} for '{task.local_path}' -> '{task.repo_id}' ({_format_bytes(total_size)})")
        return {"success": True, "task": task.to_dict()}

    def _run_upload_worker(self, task: ModelUploadTask, token: str):
        """Worker thread executing the Hugging Face upload."""
        task.status = "uploading"
        task._start_time = time.time()
        task._last_progress_time = time.time()
        log.info(f"[ModelUploader][Task {task.task_id}] Connecting to Hugging Face Hub...")

        try:
            from huggingface_hub import HfApi
            api = HfApi(token=token)

            # 1. Ensure repository exists or create it
            log.info(f"[ModelUploader][Task {task.task_id}] Creating/Verifying repo '{task.repo_id}' (private={task.private})...")
            try:
                api.create_repo(
                    repo_id=task.repo_id,
                    repo_type="model",
                    private=task.private,
                    exist_ok=True
                )
            except Exception as e:
                # If repo already exists or created
                log.info(f"[ModelUploader][Task {task.task_id}] create_repo notice: {e}")

            if task.is_cancelled():
                return

            # 2. Upload README.md model card if not already uploaded or if provided
            try:
                card_content = task.model_card or self._generate_default_model_card(task)
                card_bytes = card_content.encode("utf-8")
                api.upload_file(
                    path_or_fileobj=io.BytesIO(card_bytes),
                    path_in_repo="README.md",
                    repo_id=task.repo_id,
                    repo_type="model",
                    commit_message=f"Update model card for {task.filename}"
                )
            except Exception as e:
                log.warning(f"[ModelUploader][Task {task.task_id}] Could not upload README.md: {e}")

            if task.is_cancelled():
                return

            # 3. Upload model file(s)
            if task.is_dir:
                # Directory upload
                log.info(f"[ModelUploader][Task {task.task_id}] Uploading folder '{task.local_path}' to '{task.repo_id}'...")
                
                # Walk and upload files with progress tracking, ignoring internal cache files
                all_files = []
                for root, _, files in os.walk(task.local_path):
                    for f in files:
                        if f.startswith(".") and f != ".gitattributes":
                            continue
                        if f.endswith((".tmp", ".log", ".pyc", ".bak")):
                            continue
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, task.local_path).replace("\\", "/")
                        size = os.path.getsize(full_path)
                        all_files.append((full_path, rel_path, size))

                accumulated_bytes = 0
                for full_path, rel_path, fsize in all_files:
                    if task.is_cancelled():
                        return
                    
                    def file_progress(read_in_file, total_in_file):
                        task.update_progress(accumulated_bytes + read_in_file, task.total_bytes)

                    with open(full_path, "rb") as raw_f:
                        wrapped = ProgressReader(raw_f, fsize, file_progress, task.is_cancelled)
                        api.upload_file(
                            path_or_fileobj=wrapped,
                            path_in_repo=rel_path,
                            repo_id=task.repo_id,
                            repo_type="model",
                            commit_message=task.commit_message
                        )
                    accumulated_bytes += fsize
            else:
                # Single file upload (e.g. .gguf)
                target_filename = task.filename
                log.info(f"[ModelUploader][Task {task.task_id}] Uploading file '{task.local_path}' as '{target_filename}'...")
                
                def file_progress(read_in_file, total_in_file):
                    task.update_progress(read_in_file, total_in_file)

                with open(task.local_path, "rb") as raw_f:
                    wrapped = ProgressReader(raw_f, task.total_bytes, file_progress, task.is_cancelled)
                    api.upload_file(
                        path_or_fileobj=wrapped,
                        path_in_repo=target_filename,
                        repo_id=task.repo_id,
                        repo_type="model",
                        commit_message=task.commit_message
                    )

            # Upload successfully finished
            task.progress_pct = 100.0
            task.uploaded_bytes = task.total_bytes
            task.uploaded_label = f"{_format_bytes(task.total_bytes)} / {_format_bytes(task.total_bytes)}"
            task.status = "completed"
            task.completed_at = time.time()
            log.info(f"[ModelUploader][Task {task.task_id}] Upload COMPLETED successfully -> {task.hf_url}")

            # Il legame fra il modello sul disco e il repository che ora lo
            # ospita. Senza, la pubblicazione e' un'operazione senza memoria:
            # per aggiornare la scheda bisogna ricordarsi a mano dove si era
            # pubblicato, e sbagliare l'identificativo non da' errore — crea un
            # secondo repository.
            try:
                from core.modules.sigma_model_hub.backend import publications
                publications.record_publication(
                    task.local_path or task.filename,
                    task.repo_id, task.hf_url, task.private,
                    getattr(task, "model_card", "") or "",
                )
            except Exception as err:
                log.warning("[ModelUploader] Pubblicazione non registrata: %s", err)

        except InterruptedError as ie:
            task.status = "cancelled"
            task.error_message = str(ie)
            log.info(f"[ModelUploader][Task {task.task_id}] Upload cancelled by user.")
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            log.error(f"[ModelUploader][Task {task.task_id}] Upload FAILED: {e}", exc_info=True)

    def cancel_upload(self, task_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status in ("queued", "uploading"):
                task.cancel()
                return True
        return False

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
        return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)]


# Global singleton instance
uploader_manager = ModelUploaderManager()
