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
from unittest.mock import patch

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


class TestTrainingContinuation:
    """Proseguire un fine-tuning senza perdere quello che il job ha imparato."""

    def _finished_job(self, artifacts=("output/lora_model",), method="lora_unsloth",
                      status="completed"):
        from core.training.jobs import create_training_job, _load_jobs, _save_jobs
        job = create_training_job({
            "base_model": "unsloth/llama-3.2-1b-instruct", "method": method,
            "dataset_id": "x/y", "name": "Base", "hyperparams": {"num_epochs": 2},
        })["job"]
        jobs = _load_jobs()
        jobs[job["id"]]["status"] = status
        _save_jobs(jobs)
        for rel in artifacts:
            (Path(job["dir"]) / rel).mkdir(parents=True, exist_ok=True)
        return job["id"]

    def test_resuming_points_the_script_at_the_existing_adapter(self):
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        parent = self._finished_job()
        result = continue_training_job(parent, {"mode": "resume_adapter"})
        try:
            assert result["success"] is True
            child = _load_jobs()[result["job_id"]]
            assert child["parent_job_id"] == parent
            assert child["continuation_mode"] == "resume_adapter"
            # il modello base non cambia: e' l'adapter a proseguire
            assert child["base_model"] == "unsloth/llama-3.2-1b-instruct"
            source = Path(child["script_path"]).read_text(encoding="utf-8")
            assert "lora_model" in source
            assert "RESUME_ADAPTER = r\"\"" not in source
        finally:
            delete_job(result["job_id"])

    def test_a_fresh_adapter_starts_from_the_merged_weights(self):
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        parent = self._finished_job(artifacts=("output/merged_16bit",))
        result = continue_training_job(parent, {"mode": "fresh_adapter"})
        try:
            assert result["success"] is True
            child = _load_jobs()[result["job_id"]]
            assert child["base_model"].endswith("merged_16bit")
            source = Path(child["script_path"]).read_text(encoding="utf-8")
            assert 'RESUME_ADAPTER = r""' in source   # nessun adapter da riprendere
        finally:
            delete_job(result["job_id"])

    def test_the_dataset_can_change_between_runs(self):
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        parent = self._finished_job()
        result = continue_training_job(parent, {"mode": "resume_adapter",
                                                "dataset_id": "tatsu-lab/alpaca"})
        try:
            assert _load_jobs()[result["job_id"]]["dataset_id"] == "tatsu-lab/alpaca"
        finally:
            delete_job(result["job_id"])

    def test_keeping_the_dataset_is_the_default(self):
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        parent = self._finished_job()
        result = continue_training_job(parent, {"mode": "resume_adapter"})
        try:
            assert _load_jobs()[result["job_id"]]["dataset_id"] == "x/y"
        finally:
            delete_job(result["job_id"])

    def test_the_chain_records_both_ends(self):
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        parent = self._finished_job()
        first = continue_training_job(parent, {"mode": "resume_adapter"})
        (Path(_load_jobs()[first["job_id"]]["dir"]) / "output" / "lora_model").mkdir(parents=True)
        second = continue_training_job(first["job_id"], {"mode": "resume_adapter"})
        try:
            jobs = _load_jobs()
            assert jobs[parent]["children"] == [first["job_id"]]
            assert parent in jobs[second["job_id"]]["lineage"]
            assert first["job_id"] in jobs[second["job_id"]]["lineage"]
        finally:
            delete_job(first["job_id"])
            delete_job(second["job_id"])

    def test_a_missing_adapter_is_refused_with_the_reason(self):
        from core.training.jobs import continue_training_job
        parent = self._finished_job(artifacts=())
        result = continue_training_job(parent, {"mode": "resume_adapter"})
        assert result["success"] is False
        assert "lora_model" in result["error"]

    def test_asking_for_a_fresh_adapter_without_a_merge_says_what_to_do(self):
        from core.training.jobs import continue_training_job
        parent = self._finished_job(artifacts=("output/lora_model",))
        result = continue_training_job(parent, {"mode": "fresh_adapter"})
        assert result["success"] is False
        assert "merged_16bit" in result["error"] and "riprendi l'adapter" in result["error"].lower()

    def test_a_running_job_cannot_be_continued(self):
        from core.training.jobs import continue_training_job
        parent = self._finished_job(status="running")
        result = continue_training_job(parent, {"mode": "resume_adapter"})
        assert result["success"] is False and "esecuzione" in result["error"]

    def test_an_unknown_mode_is_refused(self):
        from core.training.jobs import continue_training_job
        result = continue_training_job(self._finished_job(), {"mode": "magia"})
        assert result["success"] is False and "sconosciuta" in result["error"]

    def test_methods_without_an_adapter_are_refused(self):
        from core.training.jobs import continue_training_job
        parent = self._finished_job(method="fwe_gradus")
        result = continue_training_job(parent, {"mode": "resume_adapter"})
        assert result["success"] is False and "fwe_gradus" in result["error"]

    def test_an_unknown_job_is_refused(self):
        from core.training.jobs import continue_training_job
        assert continue_training_job("non-esiste", {})["success"] is False


class TestDatasetSubset:
    """Addestrare su una parte del dataset invece che su tutto.

    MetaMathQA sono 395K esempi: due epoche fanno ~98.000 step, ore di GPU per
    un guadagno che si vede molto prima.
    """

    def _loader(self, max_examples):
        from core.training.jobs import SCRIPT_TEMPLATES, _render, _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": "trl_sft", "dataset_id": "x/y",
             "hyperparams": {"max_examples": max_examples}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["trl_sft"], values)
        node = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "load_train_and_eval")
        namespace = {"json": json, "sigma": lambda *a: None,
                     "VALIDATION_FRACTION": 0.0, "MAX_EXAMPLES": max_examples}
        exec(ast.get_source_segment(source, node), namespace)
        return namespace["load_train_and_eval"], namespace

    def _dataset(self, n):
        from datasets import Dataset
        return Dataset.from_dict({"text": [f"esempio {i}" for i in range(n)]})

    def test_a_subset_is_taken_when_asked(self):
        loader, namespace = self._loader(500)
        namespace["load_training_dataset"] = lambda: self._dataset(5000)
        train, _ = loader()
        assert len(train) == 500

    def test_zero_means_the_whole_dataset(self):
        loader, namespace = self._loader(0)
        namespace["load_training_dataset"] = lambda: self._dataset(3000)
        train, _ = loader()
        assert len(train) == 3000

    def test_a_dataset_smaller_than_the_cap_is_left_alone(self):
        loader, namespace = self._loader(10_000)
        namespace["load_training_dataset"] = lambda: self._dataset(400)
        train, _ = loader()
        assert len(train) == 400

    def test_the_subset_is_shuffled_not_the_first_n(self):
        """Molti dataset sono ordinati per categoria: prendere la testa
        significherebbe allenare su una fetta sola del compito."""
        loader, namespace = self._loader(50)
        namespace["load_training_dataset"] = lambda: self._dataset(5000)
        train, _ = loader()
        taken = {int(t.split()[-1]) for t in train["text"]}
        assert taken != set(range(50))
        assert max(taken) > 500          # pesca in tutto il dataset

    def test_the_same_seed_gives_the_same_subset(self):
        """Due run confrontabili devono vedere gli stessi esempi."""
        first, second = [], []
        for out in (first, second):
            loader, namespace = self._loader(40)
            namespace["load_training_dataset"] = lambda: self._dataset(2000)
            out.extend(loader()[0]["text"])
        assert first == second


class TestCheckpointing:
    """Un run fermato non deve lasciare le sue ore per terra.

    Salvare a fine epoca sembra ragionevole finché un'epoca non dura 47.000
    step: il run notturno su MetaMathQA è stato fermato dopo ~850 step e non
    aveva prodotto un solo checkpoint.
    """

    def _script(self, method="lora_unsloth", **hyper):
        from core.training.jobs import SCRIPT_TEMPLATES, _render, _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"num_epochs": 2, "batch_size": 2,
                             "gradient_accumulation": 4, **hyper}},
            "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES[method], values)

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_checkpoints_are_written_by_step_not_by_epoch(self, method):
        source = self._script(method)
        assert 'save_strategy="steps"' in source
        assert "save_steps=SAVE_EVERY" in source
        assert 'save_strategy="epoch"' not in source

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_a_restart_picks_up_the_last_checkpoint(self, method):
        source = self._script(method)
        assert "resume_from_checkpoint=RESUME_FROM" in source
        assert "_last_checkpoint" in source

    def test_the_save_interval_stays_between_its_bounds(self):
        """Fitti costano tempo di scrittura, radi costano ore di training."""
        source = self._script()
        namespace = {}
        start = source.index("def save_interval")
        exec(source[start:source.index("\n\n", start)], namespace)
        save_interval = namespace["save_interval"]
        # dataset enorme: si ferma al tetto
        assert save_interval(395_000) == 2000
        # dataset minuscolo: non scende sotto il pavimento
        assert save_interval(50) == 100
        # caso intermedio: ~20 punti di ripresa
        steps = (20_000 * 2) // 8
        assert save_interval(20_000) == pytest.approx(steps // 20, abs=1)

    def test_the_last_checkpoint_is_the_one_with_the_highest_step(self, tmp_path):
        """L'ordinamento alfabetico metterebbe checkpoint-9 dopo checkpoint-40."""
        source = self._script()
        namespace = {"os": __import__("os")}
        start = source.index("def _last_checkpoint")
        exec(source[start:source.index("RESUME_FROM =", start)], namespace)
        for step in (9, 40, 100):
            (tmp_path / f"checkpoint-{step}").mkdir()
        (tmp_path / "lora_model").mkdir()      # non è un checkpoint
        assert namespace["_last_checkpoint"](str(tmp_path)).endswith("checkpoint-100")

    def test_no_checkpoint_means_a_clean_start(self, tmp_path):
        source = self._script()
        namespace = {"os": __import__("os")}
        start = source.index("def _last_checkpoint")
        exec(source[start:source.index("RESUME_FROM =", start)], namespace)
        assert namespace["_last_checkpoint"](str(tmp_path)) is None
        assert namespace["_last_checkpoint"](str(tmp_path / "mai-esistita")) is None


class TestPauseAndResume:
    """Sospendere un training senza perdere un solo step.

    Il processo viene congelato dal sistema operativo, quindi riprende
    esattamente dov'era invece di ripartire da un checkpoint. Il test lo prova
    su un processo vero, guardando lo stato che il sistema gli attribuisce.
    """

    def _running_job(self):
        """Job con uno script che dorme: serve un processo reale da sospendere."""
        from core.training.jobs import (create_training_job, start_training_job,
                                        _load_jobs, _save_jobs)
        job = create_training_job({
            "base_model": "gpt2", "method": "script_custom",
            "dataset_id": "", "hyperparams": {},
        })["job"]
        Path(job["script_path"]).write_text(
            "import time\nfor _ in range(600):\n    time.sleep(0.5)\n", encoding="utf-8")
        # Lo script è già a posto: la risincronizzazione lo rigenererebbe.
        jobs = _load_jobs()
        jobs[job["id"]]["method"] = "script_custom"
        _save_jobs(jobs)
        assert start_training_job(job["id"])["success"]
        return job["id"]

    def test_a_running_job_can_be_frozen_and_let_go(self):
        import psutil
        from core.training.jobs import (pause_training_job, resume_training_job,
                                        stop_training_job, _load_jobs, delete_job)
        job_id = self._running_job()
        try:
            pid = _load_jobs()[job_id]["pid"]
            process = psutil.Process(pid)

            paused = pause_training_job(job_id)
            assert paused["success"] is True, paused.get("error")
            assert _load_jobs()[job_id]["status"] == "paused"
            assert process.status() == psutil.STATUS_STOPPED
            # e la pausa dice a chiare lettere cosa non fa
            assert "VRAM" in paused["message"]

            resumed = resume_training_job(job_id)
            assert resumed["success"] is True, resumed.get("error")
            assert _load_jobs()[job_id]["status"] == "running"
            assert process.status() != psutil.STATUS_STOPPED
        finally:
            stop_training_job(job_id)
            delete_job(job_id)

    def test_pausing_something_that_is_not_running_is_refused(self):
        from core.training.jobs import create_training_job, pause_training_job, delete_job
        job = create_training_job({"base_model": "gpt2", "method": "script_custom",
                                   "dataset_id": "", "hyperparams": {}})["job"]
        try:
            result = pause_training_job(job["id"])
            assert result["success"] is False and "esecuzione" in result["error"]
        finally:
            delete_job(job["id"])

    def test_resuming_a_job_whose_process_died_says_so(self):
        """Altrimenti resterebbe 'paused' per sempre, in attesa di nessuno."""
        from core.training.jobs import (create_training_job, resume_training_job,
                                        _load_jobs, _save_jobs, delete_job)
        job = create_training_job({"base_model": "gpt2", "method": "script_custom",
                                   "dataset_id": "", "hyperparams": {}})["job"]
        jobs = _load_jobs()
        jobs[job["id"]].update({"status": "paused", "pid": 999999})
        _save_jobs(jobs)
        try:
            result = resume_training_job(job["id"])
            assert result["success"] is False
            assert _load_jobs()[job["id"]]["status"] == "stopped"
        finally:
            delete_job(job["id"])

    def test_a_running_stage_offers_pause_and_a_paused_one_offers_resume(self):
        from core.training.jobs import (create_training_job, get_job_lineage,
                                        _load_jobs, _save_jobs, delete_job)
        job = create_training_job({"base_model": "gpt2", "method": "lora_unsloth",
                                   "dataset_id": "x/y", "hyperparams": {}})["job"]
        try:
            for status, expected in (("running", "pause"), ("paused", "resume")):
                jobs = _load_jobs(); jobs[job["id"]]["status"] = status; _save_jobs(jobs)
                assert expected in get_job_lineage(job["id"])["stages"][0]["actions"]
        finally:
            delete_job(job["id"])


class TestSpecialisationChain:
    """LoRA → merge → nuova base → LoRA: la catena che specializza per fasi.

    Ogni fase è un job a sé, con i suoi artefatti e il suo log, così si può
    valutare da sola e confrontare con quella prima.
    """

    def _trained(self, artifacts=("output/lora_model",), method="lora_unsloth"):
        from core.training.jobs import create_training_job, _load_jobs, _save_jobs
        job = create_training_job({
            "base_model": "unsloth/llama-3.2-1b-instruct", "method": method,
            "dataset_id": "gsm8k", "name": "LoRA GSM8K", "hyperparams": {},
        })["job"]
        jobs = _load_jobs()
        jobs[job["id"]]["status"] = "completed"
        _save_jobs(jobs)
        for rel in artifacts:
            (Path(job["dir"]) / rel).mkdir(parents=True, exist_ok=True)
        return job["id"]

    def _merge(self, parent, stage_name="Qwythos Reasoning v1", merged=True):
        """Merge senza lanciare il processo: interessa la struttura, non la GPU."""
        from core.training.jobs import merge_job_adapter, _load_jobs, _save_jobs
        with patch("core.training.jobs.start_training_job",
                   return_value={"success": True}):
            result = merge_job_adapter(parent, {"stage_name": stage_name})
        assert result["success"] is True, result.get("error")
        jobs = _load_jobs()
        jobs[result["job_id"]]["status"] = "completed"
        _save_jobs(jobs)
        if merged:
            (Path(jobs[result["job_id"]]["dir"]) / "output" / "merged_16bit").mkdir(parents=True)
        return result["job_id"]

    def test_the_merge_is_its_own_job_with_the_adapter_wired_in(self):
        from core.training.jobs import _load_jobs, delete_job
        parent = self._trained()
        merge_id = self._merge(parent)
        try:
            job = _load_jobs()[merge_id]
            assert job["method"] == "merge_adapter"
            assert job["stage_name"] == "Qwythos Reasoning v1"
            assert job["source_job_id"] == parent
            # il metodo di training si tramanda: il merge non ne ha uno suo
            assert job["train_method"] == "lora_unsloth"
            source = Path(job["script_path"]).read_text(encoding="utf-8")
            assert "lora_model" in source and "merge_and_unload" in source
        finally:
            delete_job(merge_id)

    def test_merging_without_an_adapter_is_refused(self):
        from core.training.jobs import merge_job_adapter
        parent = self._trained(artifacts=())
        result = merge_job_adapter(parent, {})
        assert result["success"] is False
        assert "adapter" in result["error"]

    def test_a_merged_stage_becomes_the_base_of_the_next_one(self):
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        merge_id = self._merge(self._trained())
        nxt = continue_training_job(merge_id, {"dataset_id": "x/math",
                                               "stage_name": "Qwythos Reasoning v2"})
        try:
            assert nxt["success"] is True
            child = _load_jobs()[nxt["job_id"]]
            # da una fase fusa si riparte per forza con un adapter nuovo
            assert child["continuation_mode"] == "fresh_adapter"
            assert child["base_model"].endswith("merged_16bit")
            assert child["method"] == "lora_unsloth"     # ereditato dal training
            assert child["stage_name"] == "Qwythos Reasoning v2"
        finally:
            delete_job(nxt["job_id"])

    def test_resuming_an_adapter_is_impossible_after_a_merge(self):
        """Chiedere resume_adapter su una fase fusa non deve rompere: quel
        lavoro è già dentro i pesi, quindi si ricade su fresh_adapter."""
        from core.training.jobs import continue_training_job, _load_jobs, delete_job
        merge_id = self._merge(self._trained())
        nxt = continue_training_job(merge_id, {"mode": "resume_adapter"})
        try:
            assert nxt["success"] is True
            assert _load_jobs()[nxt["job_id"]]["continuation_mode"] == "fresh_adapter"
        finally:
            delete_job(nxt["job_id"])

    def test_the_lineage_reads_the_whole_chain_in_order(self):
        from core.training.jobs import (continue_training_job, get_job_lineage,
                                        _load_jobs, _save_jobs, delete_job)
        first = self._trained()
        merge1 = self._merge(first, "Qwythos Reasoning v1")
        second = continue_training_job(merge1, {"dataset_id": "x/math"})["job_id"]
        jobs = _load_jobs()
        jobs[second]["status"] = "completed"
        _save_jobs(jobs)
        (Path(jobs[second]["dir"]) / "output" / "lora_model").mkdir(parents=True)
        merge2 = self._merge(second, "Qwythos Reasoning v2")
        try:
            chain = get_job_lineage(merge2)
            assert chain["success"] is True
            assert [s["id"] for s in chain["stages"]] == [first, merge1, second, merge2]
            assert [s["kind"] for s in chain["stages"]] == ["train", "merge", "train", "merge"]
            assert chain["stages"][-1]["stage_name"] == "Qwythos Reasoning v2"
            assert chain["stages"][-1]["is_current"] is True
        finally:
            for jid in (merge2, second, merge1, first):
                delete_job(jid)

    def test_the_lineage_is_the_same_seen_from_any_stage(self):
        from core.training.jobs import get_job_lineage, delete_job
        first = self._trained()
        merge1 = self._merge(first)
        try:
            dal_primo = [s["id"] for s in get_job_lineage(first)["stages"]]
            dal_merge = [s["id"] for s in get_job_lineage(merge1)["stages"]]
            assert dal_primo == dal_merge == [first, merge1]
        finally:
            delete_job(merge1)
            delete_job(first)

    def test_the_actions_offered_follow_the_artefacts_on_disk(self):
        from core.training.jobs import get_job_lineage, delete_job
        parent = self._trained()
        try:
            stage = get_job_lineage(parent)["stages"][0]
            assert "merge" in stage["actions"] and "continue" in stage["actions"]
            assert "benchmark" not in stage["actions"]   # nessun modello autonomo
        finally:
            delete_job(parent)

    def test_a_stage_without_artefacts_offers_no_next_step(self):
        from core.training.jobs import get_job_lineage, delete_job
        parent = self._trained(artifacts=())
        try:
            actions = get_job_lineage(parent)["stages"][0]["actions"]
            assert "merge" not in actions and "continue" not in actions
            assert "delete" in actions
        finally:
            delete_job(parent)

    def test_a_running_stage_can_only_be_paused_or_stopped(self):
        """Su un run in corso non ha senso offrire merge o continuazione: gli
        artefatti non sono ancora quelli definitivi."""
        from core.training.jobs import get_job_lineage, _load_jobs, _save_jobs, delete_job
        parent = self._trained()
        jobs = _load_jobs(); jobs[parent]["status"] = "running"; _save_jobs(jobs)
        try:
            assert get_job_lineage(parent)["stages"][0]["actions"] == ["pause", "stop"]
        finally:
            delete_job(parent)

    def test_an_unknown_job_has_no_lineage(self):
        from core.training.jobs import get_job_lineage
        assert get_job_lineage("non-esiste")["success"] is False


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
