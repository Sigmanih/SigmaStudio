# ==============================================================================
# tests/test_training_gpu.py — Accelerator layer, auto-tune, FWE integration
# ==============================================================================
"""Copre core/training/gpu.py, core/training/fwe.py e la generazione degli
script di training. I test non richiedono una GPU: dove serve, l'hardware viene
simulato costruendo un report sintetico."""

import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.training_handler as th
from core.training import gpu as gpu_layer
from core.training import fwe as fwe_layer
from core.training.jobs import (SCRIPT_TEMPLATES, _render, resolve_dataset,
                                resolve_base_model, _parse_progress)


@pytest.fixture(autouse=True)
def isolate_training_dirs(tmp_path):
    """I job creati dai test non devono finire nella cartella training reale."""
    saved = {name: getattr(th, name) for name in
             ("TRAINING_DIR", "DATASETS_DIR", "JOBS_DIR", "JOBS_FILE", "SCRIPTS_DIR")}
    th.TRAINING_DIR = tmp_path / "training"
    th.DATASETS_DIR = th.TRAINING_DIR / "datasets"
    th.JOBS_DIR = th.TRAINING_DIR / "jobs"
    th.JOBS_FILE = th.TRAINING_DIR / "training_jobs.json"
    th.SCRIPTS_DIR = th.TRAINING_DIR / "scripts"
    for d in (th.TRAINING_DIR, th.DATASETS_DIR, th.JOBS_DIR, th.SCRIPTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    yield
    for name, value in saved.items():
        setattr(th, name, value)


# =========================================================== capability table

class TestArchDetection:
    """Compute capability -> architettura e feature."""

    @pytest.mark.parametrize("cc,arch,bf16,fp8", [
        ((6, 1), "Pascal", False, False),
        ((7, 5), "Turing", False, False),
        ((8, 0), "Ampere", True, False),
        ((8, 6), "Ampere", True, False),
        ((8, 9), "Ada Lovelace", True, True),
        ((9, 0), "Hopper", True, True),
        ((12, 0), "Blackwell (RTX 50)", True, True),
    ])
    def test_known_architectures(self, cc, arch, bf16, fp8):
        feats = gpu_layer.nvidia_arch_features(*cc)
        assert feats["arch"] == arch
        assert feats["bf16"] is bf16
        assert feats["fp8"] is fp8

    def test_future_gpu_inherits_newest_features(self):
        """Una compute capability sconosciuta eredita il set piu' recente noto."""
        feats = gpu_layer.nvidia_arch_features(13, 0)
        assert feats["bf16"] and feats["fp8"] and feats["flash_attn"]

    def test_ancient_gpu_has_no_tensor_cores(self):
        feats = gpu_layer.nvidia_arch_features(5, 0)
        assert not feats["tensor_cores"]
        assert not feats["flash_attn"]


# =========================================================== model sizing

class TestModelSizeEstimate:

    @pytest.mark.parametrize("name,expected", [
        ("unsloth/llama-3.2-3b-instruct", 3.0),
        ("unsloth/llama-3.1-8b-instruct", 8.0),
        ("Qwen/Qwen2.5-0.5B", 0.5),
        ("meta-llama/Llama-3.1-70B", 70.0),
        ("gpt2", 0.124),
        ("gpt2-medium", 0.35),
        ("EleutherAI/pythia-160m", 0.16),
        ("from_scratch", 0.05),
    ])
    def test_params_from_name(self, name, expected):
        assert gpu_layer.estimate_model_params_b(name) == pytest.approx(expected, rel=0.01)

    def test_unknown_model_is_conservative(self):
        """Un id sconosciuto deve assumere un modello grande, non piccolo."""
        assert gpu_layer.estimate_model_params_b("qualcosa/di-ignoto") >= 7.0


# =========================================================== auto-tune

def _fake_report(gpus, backend="cuda", flash_attn_pkg=True):
    """Report sintetico con la stessa forma di get_accelerator_report()."""
    trainable = [g for g in gpus if g.get("trainable")]
    torch_info = {"torch_version": "2.11.0", "torch_cuda_version": "12.8", "arch_list": [],
                  "flash_attn_pkg": flash_attn_pkg}
    return {
        "backend": backend,
        "gpus": gpus,
        "trainable_gpus": trainable,
        "gpu_count": len(gpus),
        "trainable_count": len(trainable),
        "total_vram_gb": sum(g["vram_total_gb"] for g in trainable),
        "torch": torch_info,
        "capabilities": gpu_layer.aggregate_capabilities(trainable, torch_info, backend),
    }


def _gpu(index, name, vram_gb, major=12, minor=0):
    feats = gpu_layer.nvidia_arch_features(major, minor)
    return {
        "index": index, "name": name, "vendor": "NVIDIA", "backend": "cuda",
        "vram_total_gb": vram_gb, "arch": feats["arch"], "trainable": True,
        "device_str": f"cuda:{index}", "sm": f"sm_{major}{minor}",
        "supports_bf16": feats["bf16"], "supports_fp16": feats["fp16"],
        "supports_tf32": feats["tf32"], "supports_fp8": feats["fp8"],
        "supports_flash_attn": feats["flash_attn"], "tensor_cores": feats["tensor_cores"],
    }


class TestAutotune:

    def test_blackwell_uses_bf16_and_flash_attention(self):
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.2-3b", report=report)
        assert cfg["dtype"] == "bfloat16"
        assert cfg["bf16"] is True and cfg["fp16"] is False
        assert cfg["attn_implementation"] == "flash_attention_2"
        assert cfg["tf32"] is True

    def test_flash_attention_needs_the_package_installed(self):
        """Blackwell senza flash_attn deve restare su SDPA, non chiedere FA2."""
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)], flash_attn_pkg=False)
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.2-3b", report=report)
        assert cfg["attn_implementation"] == "sdpa"

    def test_turing_falls_back_to_fp16_and_sdpa(self):
        """Su Turing niente bf16 e niente FlashAttention-2."""
        report = _fake_report([_gpu(0, "RTX 2080 Ti", 11.0, major=7, minor=5)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.2-3b", report=report)
        assert cfg["dtype"] == "float16"
        assert cfg["fp16"] is True and cfg["bf16"] is False
        assert cfg["attn_implementation"] == "sdpa"
        assert cfg["tf32"] is False

    def test_identical_gpus_use_ddp(self):
        report = _fake_report([_gpu(0, "RTX 4090", 24.0, 8, 9), _gpu(1, "RTX 4090", 24.0, 8, 9)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.2-3b", report=report)
        assert cfg["strategy"] == "ddp"
        assert len(cfg["gpu_indices"]) == 2

    def test_mixed_gpus_prefer_the_largest_card(self):
        """5070 Ti + 5060: DDP sarebbe limitato dalla scheda piccola."""
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0), _gpu(1, "RTX 5060", 8.0)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.2-3b", report=report)
        assert cfg["strategy"] == "single_gpu"
        assert cfg["gpu_indices"] == [0]
        assert cfg["device"] == "cuda:0"

    def test_model_too_big_spreads_across_gpus(self):
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0), _gpu(1, "RTX 5060", 8.0)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.1-70b", report=report)
        assert cfg["strategy"] == "model_parallel"
        assert cfg["device_map"] == "auto"
        assert cfg["load_in_4bit"] is True

    def test_small_gpu_enables_4bit_for_large_model(self):
        report = _fake_report([_gpu(0, "RTX 3060", 12.0, 8, 6)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.1-8b", report=report)
        assert cfg["load_in_4bit"] is True
        assert cfg["gradient_checkpointing"] is True

    def test_large_gpu_skips_4bit_for_small_model(self):
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "Qwen/Qwen2.5-0.5B", report=report)
        assert cfg["load_in_4bit"] is False

    def test_cpu_only_is_usable(self):
        report = _fake_report([], backend="cpu")
        cfg = gpu_layer.recommend_training_config("trl_sft", "gpt2", report=report)
        assert cfg["device"] == "cpu"
        assert cfg["strategy"] == "cpu"
        assert cfg["batch_size"] == 1
        assert cfg["dtype"] == "float32"

    def test_batch_and_accumulation_are_sane(self):
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        cfg = gpu_layer.recommend_training_config("lora_unsloth", "llama-3.2-3b", report=report)
        assert 1 <= cfg["batch_size"] <= 8
        assert cfg["gradient_accumulation"] >= 1
        assert cfg["effective_batch"] == cfg["batch_size"] * cfg["gradient_accumulation"]

    def test_heterogeneous_capabilities_use_weakest_gpu(self):
        """Una Blackwell + una Turing non possono usare bf16 insieme."""
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0), _gpu(1, "RTX 2080", 8.0, 7, 5)])
        assert report["capabilities"]["bf16"] is False
        assert report["capabilities"]["flash_attn"] is False


# =========================================================== env & runtime

class TestCudaEnv:

    def test_visible_devices_restricted_to_selected_gpus(self):
        env = gpu_layer.cuda_env_vars([1], backend="cuda")
        assert env["CUDA_VISIBLE_DEVICES"] == "1"
        assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"

    def test_allocator_config_is_platform_aware(self):
        """expandable_segments non esiste nell'allocatore CUDA di Windows."""
        env = gpu_layer.cuda_env_vars([0], backend="cuda")
        conf = env["PYTORCH_CUDA_ALLOC_CONF"]
        if sys.platform == "win32":
            assert "expandable_segments" not in conf
        else:
            assert "expandable_segments" in conf

    def test_cpu_backend_has_no_cuda_vars(self):
        env = gpu_layer.cuda_env_vars(backend="cpu")
        assert "CUDA_VISIBLE_DEVICES" not in env
        assert env["PYTHONUNBUFFERED"] == "1"


# =========================================================== script generation

class TestGeneratedScripts:

    @pytest.mark.parametrize("method", sorted(SCRIPT_TEMPLATES))
    def test_every_template_renders_valid_python(self, method):
        from core.training.jobs import create_training_job, delete_job
        result = create_training_job({
            "base_model": "Qwen/Qwen2.5-0.5B", "method": method, "dataset_id": "x/y",
            "hyperparams": {"num_epochs": 1, "learning_rate": 2e-4, "max_seq_length": 512},
        })
        try:
            source = Path(result["job"]["script_path"]).read_text(encoding="utf-8")
            ast.parse(source)                     # deve compilare
            assert "{tune_json}" not in source    # nessun placeholder residuo
            assert "TUNE = json.loads" in source  # ricetta hardware iniettata
        finally:
            delete_job(result["job_id"])

    def test_render_leaves_python_braces_untouched(self):
        """Il renderer non deve toccare dict/f-string dello script."""
        template = 'x = {"a": 1}\nname = "{base_model}"\nf = f"{x}"'
        out = _render(template, {"base_model": "gpt2"})
        assert '{"a": 1}' in out
        assert 'name = "gpt2"' in out
        assert 'f"{x}"' in out

    def test_windows_pretrain_uses_no_dataloader_workers(self):
        """Su Windows num_workers>0 fa rieseguire lo script a ogni worker."""
        assert 'dataloader_num_workers=0 if os.name == "nt" else 4' \
            in SCRIPT_TEMPLATES["full_pretrain"]


class TestStaleScriptRegeneration:
    """Uno script congelato prima di una correzione al template va rigenerato."""

    def _job(self, method="trl_sft"):
        from core.training.jobs import create_training_job
        result = create_training_job({
            "base_model": "gpt2", "method": method, "dataset_id": "x/y",
            "hyperparams": {"num_epochs": 1},
        })
        return result["job"]

    def test_a_fresh_script_is_left_alone(self):
        from core.training.jobs import _sync_script_template, delete_job
        job = self._job()
        try:
            before = Path(job["script_path"]).read_text(encoding="utf-8")
            assert _sync_script_template(job) is False
            assert Path(job["script_path"]).read_text(encoding="utf-8") == before
        finally:
            delete_job(job["id"])

    def test_an_outdated_script_is_rebuilt(self):
        from core.training.jobs import _sync_script_template, delete_job
        job = self._job()
        try:
            path = Path(job["script_path"])
            path.write_text("# SIGMA_TEMPLATE: 000000000000\nprint('vecchio')\n",
                            encoding="utf-8")
            assert _sync_script_template(job) is True
            rebuilt = path.read_text(encoding="utf-8")
            assert "vecchio" not in rebuilt
            ast.parse(rebuilt)
        finally:
            delete_job(job["id"])

    def test_an_untagged_script_counts_as_outdated(self):
        """I job creati prima del tag non hanno modo di dichiararsi aggiornati."""
        from core.training.jobs import _sync_script_template, delete_job
        job = self._job()
        try:
            path = Path(job["script_path"])
            path.write_text("print('senza tag')\n", encoding="utf-8")
            assert _sync_script_template(job) is True
            assert "senza tag" not in path.read_text(encoding="utf-8")
        finally:
            delete_job(job["id"])

    def test_a_hand_edited_custom_script_is_never_overwritten(self):
        from core.training.jobs import _sync_script_template, delete_job
        job = self._job(method="script_custom")
        try:
            path = Path(job["script_path"])
            path.write_text("# modificato a mano\n", encoding="utf-8")
            assert _sync_script_template(job) is False
            assert path.read_text(encoding="utf-8") == "# modificato a mano\n"
        finally:
            delete_job(job["id"])


class TestGeneratedDatasetLoader:
    """Il loader vive dentro lo script generato: lo si estrae e lo si esegue."""

    @staticmethod
    def _loader(dataset_id):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": "trl_sft", "dataset_id": dataset_id,
             "hyperparams": {}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["trl_sft"], values)
        fn = next(n for n in ast.parse(source).body
                  if isinstance(n, ast.FunctionDef) and n.name == "load_training_dataset")
        ns = {"json": json, "sigma": lambda *a: None}
        exec(ast.get_source_segment(source, fn), ns)
        return ns["load_training_dataset"]

    def test_gsm8k_is_loaded_with_its_config_name(self, monkeypatch):
        """gsm8k ha due sottoinsiemi: senza config load_dataset si rifiuta."""
        import datasets
        calls = []
        monkeypatch.setattr(datasets, "load_dataset", lambda path, name=None, **kw: (
            calls.append((path, name)),
            datasets.Dataset.from_dict({"question": ["2+2?"], "answer": ["fa 4"]}))[1])
        ds = self._loader("gsm8k")()
        assert calls == [("openai/gsm8k", "main")]
        # e la risposta deve finire nel testo, non solo la domanda
        assert ds.column_names == ["text"]
        assert "2+2?" in ds[0]["text"] and "fa 4" in ds[0]["text"]

    def test_unknown_dataset_falls_back_to_the_first_config(self, monkeypatch):
        import datasets
        seen = []

        def fake_load(path, name=None, **kw):
            seen.append(name)
            if name is None:
                raise ValueError("Config name is missing.\nPlease pick one among: ['a', 'b']")
            return datasets.Dataset.from_dict({"text": ["ciao"]})

        monkeypatch.setattr(datasets, "load_dataset", fake_load)
        monkeypatch.setattr(datasets, "get_dataset_config_names", lambda p, **kw: ["a", "b"])
        assert self._loader("tizio/dataset-ignoto")()[0]["text"] == "ciao"
        assert seen == [None, "a"]


# =========================================================== dataset & log

class TestJobContinuation:
    """Estendere un run FWE: lo script e' un file congelato su disco, quindi un
    job creato con una versione precedente del template va rigenerato."""

    def test_override_detection_ignores_the_comment(self):
        """Il template cita GRADUS_STEPS anche in un commento: cercare il nome
        farebbe passare per aggiornato uno script col totale cablato."""
        from core.training.jobs import _STEPS_OVERRIDE_RE

        legacy = ('# Riavviando il job con GRADUS_STEPS piu\' alto si continua\n'
                  'TOTAL_STEPS = 600\n')
        current = 'TOTAL_STEPS = int(os.environ.get("GRADUS_STEPS") or 600)\n'
        assert not _STEPS_OVERRIDE_RE.search(legacy)
        assert _STEPS_OVERRIDE_RE.search(current)

    def test_legacy_script_is_regenerated(self):
        from core.training.jobs import create_training_job, delete_job, _refresh_script

        result = create_training_job({
            "base_model": "qwen0.5b-instruct", "method": "fwe_gradus", "dataset_id": "",
            "hyperparams": {"fwe_steps": 600},
        })
        job = result["job"]
        try:
            script = Path(job["script_path"])
            # riporta lo script alla forma precedente: totale cablato
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    'TOTAL_STEPS = int(os.environ.get("GRADUS_STEPS") or 600)',
                    "TOTAL_STEPS = 600"),
                encoding="utf-8")

            refreshed = _refresh_script(job, 1800)
            assert refreshed["success"] and refreshed["regenerated"]
            source = script.read_text(encoding="utf-8")
            assert 'os.environ.get("GRADUS_STEPS")' in source
            assert "or 1800)" in source
        finally:
            delete_job(job["id"])

    def test_current_script_is_left_alone(self):
        from core.training.jobs import create_training_job, delete_job, _refresh_script

        result = create_training_job({
            "base_model": "qwen0.5b-instruct", "method": "fwe_gradus", "dataset_id": "",
            "hyperparams": {"fwe_steps": 600},
        })
        try:
            refreshed = _refresh_script(result["job"], 1800)
            assert refreshed["success"] and not refreshed["regenerated"]
        finally:
            delete_job(result["job_id"])

    def test_old_job_without_request_is_still_extendable(self):
        """I job creati prima che la richiesta venisse salvata devono comunque
        potersi estendere: i metadati contengono già tutto il necessario."""
        from core.training.jobs import create_training_job, delete_job, _refresh_script

        result = create_training_job({
            "base_model": "qwen0.5b-instruct", "method": "fwe_gradus", "dataset_id": "",
            "hyperparams": {"fwe_steps": 600, "fwe_include": "_proj", "fwe_vq": 512},
        })
        job = dict(result["job"])
        try:
            script = Path(job["script_path"])
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    'TOTAL_STEPS = int(os.environ.get("GRADUS_STEPS") or 600)',
                    "TOTAL_STEPS = 600"),
                encoding="utf-8")
            job.pop("request", None)          # com'erano i job piu' vecchi

            refreshed = _refresh_script(job, 1800)
            assert refreshed["success"] and refreshed["regenerated"]
            source = script.read_text(encoding="utf-8")
            assert "or 1800)" in source
            assert 'include="_proj"' in source      # iperparametri preservati
            assert "vq=512" in source
        finally:
            delete_job(result["job_id"])

    def test_unusable_job_gets_an_actionable_error(self):
        """Senza metodo né modello non si può rigenerare: dillo, non fallire e basta."""
        from core.training.jobs import create_training_job, delete_job, _refresh_script

        result = create_training_job({
            "base_model": "qwen0.5b-instruct", "method": "fwe_gradus", "dataset_id": "",
            "hyperparams": {"fwe_steps": 600},
        })
        job = dict(result["job"])
        try:
            script = Path(job["script_path"])
            script.write_text("TOTAL_STEPS = 600\n", encoding="utf-8")
            job.pop("request", None)
            job.pop("method", None)

            refreshed = _refresh_script(job, 1800)
            assert refreshed["success"] is False
            assert "checkpoint" in refreshed["error"]
            assert str(script) in refreshed["error"]
        finally:
            delete_job(result["job_id"])

    def test_cannot_shrink_a_run(self):
        from core.training.jobs import create_training_job, start_training_job, delete_job

        result = create_training_job({
            "base_model": "qwen0.5b-instruct", "method": "fwe_gradus", "dataset_id": "",
            "hyperparams": {"fwe_steps": 600},
        })
        try:
            answer = start_training_job(result["job_id"], total_steps=300)
            assert answer["success"] is False
            assert "600" in answer["error"]
        finally:
            delete_job(result["job_id"])


class TestDatasetResolution:

    def test_bare_hf_id_is_recognised(self):
        ds = resolve_dataset("tatsu-lab/alpaca")
        assert ds["kind"] == "hf"
        assert ds["path"] == "tatsu-lab/alpaca"

    def test_unknown_id_is_not_fatal(self):
        ds = resolve_dataset("non-esiste")
        assert ds["kind"] == "unknown"

    def test_empty_id_is_not_fatal(self):
        assert resolve_dataset("")["kind"] == "unknown"


class TestBaseModelResolution:

    @pytest.mark.parametrize("model_id", [
        "empero-ai/Qwythos-9B-Claude-Mythos-5-1M",
        "unsloth/llama-3.2-3b-instruct",
        "gpt2",
        "qwen0.5b-instruct",   # target FWE
        "from_scratch",        # SLM Forge
    ])
    def test_valid_ids_pass_through(self, model_id):
        assert resolve_base_model(model_id) == model_id

    def test_local_weight_directory_is_accepted(self, tmp_path):
        (tmp_path / "config.json").write_text("{}", encoding="utf-8")
        assert resolve_base_model(str(tmp_path)) == str(tmp_path).replace("\\", "/")

    def test_ollama_tag_is_rejected_with_an_actionable_message(self):
        """Il caso vero: un tag scelto dal gruppo Ollama del selettore."""
        with pytest.raises(ValueError) as err:
            resolve_base_model("pdurlej/qwythos-9b-claude-mythos-5-1m:latest")
        msg = str(err.value)
        assert "Ollama" in msg and "GGUF" in msg
        # Il messaggio deve suggerire cosa cercare su HuggingFace.
        assert "qwythos-9b-claude-mythos-5-1m" in msg

    def test_empty_id_is_rejected(self):
        with pytest.raises(ValueError):
            resolve_base_model("")

    def test_job_creation_fails_cleanly_on_an_ollama_tag(self):
        from core.training.jobs import create_training_job
        result = create_training_job({
            "base_model": "llama3.2:latest", "method": "trl_sft",
            "dataset_id": "", "hyperparams": {},
        })
        assert result["success"] is False
        assert "Ollama" in result["error"]


class TestProgressParsing:

    def test_sigma_progress_line(self):
        state = {}
        line = "[SIGMA] Epoch 2/3 step 40/120 (33.3%) - loss: 0.4521 | lr: 2.00e-04"
        assert _parse_progress(line, state)
        assert state["current_epoch"] == 2 and state["total_epochs"] == 3
        assert state["current_step"] == 40 and state["total_steps"] == 120
        assert state["last_loss"] == pytest.approx(0.4521)
        assert state["progress_pct"] == pytest.approx(33.3)

    def test_plain_line_changes_nothing(self):
        state = {}
        assert not _parse_progress("caricamento del modello...", state)


# =========================================================== FWE

class TestFweIntegration:

    def test_engine_is_vendored(self):
        avail = fwe_layer.fwe_available()
        assert Path(avail["engine_path"]).exists()
        assert "gradus" not in avail["missing"]

    def test_defaults_scale_with_vram(self, monkeypatch):
        """Meno VRAM = meno tensori coperti e codebook piu' piccolo."""
        def report_with(vram):
            return _fake_report([_gpu(0, "GPU", vram)])

        monkeypatch.setattr(gpu_layer, "get_accelerator_report", lambda *a, **k: report_with(24.0))
        big = fwe_layer.fwe_defaults()
        monkeypatch.setattr(gpu_layer, "get_accelerator_report", lambda *a, **k: report_with(6.0))
        small = fwe_layer.fwe_defaults()

        assert big["fwe_include"] == "_proj"
        assert small["fwe_include"] != "_proj"
        assert big["fwe_vq"] > small["fwe_vq"]
        assert big["fwe_steps"] > small["fwe_steps"]

    def test_status_payload_is_complete(self):
        status = fwe_layer.fwe_status()
        assert status["success"] is True
        assert {"engine", "defaults", "runs", "targets", "datasets"} <= set(status)
        assert all("id" in t and "label" in t for t in status["targets"])
