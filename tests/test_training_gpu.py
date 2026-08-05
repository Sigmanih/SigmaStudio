# ==============================================================================
# tests/test_training_gpu.py — Accelerator layer, auto-tune, FWE integration
# ==============================================================================
"""Copre core/training/gpu.py, core/training/fwe.py e la generazione degli
script di training. I test non richiedono una GPU: dove serve, l'hardware viene
simulato costruendo un report sintetico."""

import ast
import json
import os
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

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_every_config_argument_exists_in_the_installed_library(self, method):
        """Ogni chiave passata a SFTConfig/TrainingArguments deve esistere davvero.

        Un template compila anche quando gli si passa un argomento che la
        libreria non conosce: l'errore arriva a runtime, dopo che il job e'
        partito. E' successo con `group_by_length`, tolto da SFTConfig in TRL
        0.24, e ha fatto fallire quattro round consecutivi del ciclo
        automatico prima che qualcuno leggesse il traceback.
        """
        import dataclasses

        from core.training.jobs import _build_script_values

        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"num_epochs": 1, "max_seq_length": 512}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES[method], values)

        classi = {}
        try:
            from trl import SFTConfig
            classi["SFTConfig"] = SFTConfig
        except ImportError:
            pass
        try:
            from transformers import TrainingArguments
            classi["TrainingArguments"] = TrainingArguments
        except ImportError:
            pass
        if not classi:
            pytest.skip("trl/transformers non installati")

        visti = 0
        for nodo in ast.walk(ast.parse(source)):
            if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)):
                continue
            cls = classi.get(nodo.func.id)
            if cls is None:
                continue
            visti += 1
            campi = {f.name for f in dataclasses.fields(cls)}
            passati = {k.arg for k in nodo.keywords if k.arg}
            ignoti = passati - campi
            assert not ignoti, (
                f"{method}: {nodo.func.id} non accetta {sorted(ignoti)} "
                f"in {cls.__module__}")
        assert visti, f"{method}: nessuna configurazione trovata da controllare"

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
        """Prepara le due funzioni vere.

        Il taglio vive in `load_training_dataset`, non piu' in
        `load_train_and_eval`: sostituire la prima con un finto — come faceva
        questa prova — significherebbe saltare proprio cio' che si vuole
        verificare.
        """
        from core.training.jobs import SCRIPT_TEMPLATES, _render, _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": "trl_sft", "dataset_id": "x/y",
             "hyperparams": {"max_examples": max_examples}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["trl_sft"], values)
        namespace = {"json": json, "os": __import__("os"), "sigma": lambda *a: None,
                     "VALIDATION_FRACTION": 0.0, "MAX_EXAMPLES": max_examples,
                     "DATASET_KIND": "hf", "DATASET_PATH": "x/y",
                     "DATASET_SPLIT": "train", "DATASET_CONFIG": "",
                     "LEGACY_HF_DATASETS": {}, "HF_DATASET_CONFIGS": {},
                     "_TEMPLATE_PROPRIO": [None]}
        albero = ast.parse(source)
        namespace["INDIZI_DOMINIO"] = next(
            ast.literal_eval(n.value) for n in albero.body
            if isinstance(n, ast.Assign)
            and getattr(n.targets[0], "id", "") == "INDIZI_DOMINIO")
        # Il caricatore chiama i formattatori e il rapporto sulla composizione:
        # eseguirlo senza di loro proverebbe solo che mancano.
        for nome in ("coppia_a_testo", "turni_a_testo", "composizione_del_dataset",
                     "load_training_dataset", "load_train_and_eval"):
            node = next(n for n in albero.body
                        if isinstance(n, ast.FunctionDef) and n.name == nome)
            exec(ast.get_source_segment(source, node), namespace)
        return namespace["load_train_and_eval"], namespace

    def _sorgente(self, namespace, n):
        """Fa restituire il dataset di prova al vero caricatore."""
        import datasets as D
        D.load_dataset = lambda *a, **k: self._dataset(n)

    def _dataset(self, n):
        from datasets import Dataset

        # Testi realistici, non "esempio 3": il controllo di sanita' rifiuta i
        # testi troppo corti, ed e' giusto che lo faccia — un dataset con
        # dieci caratteri per esempio e' una colonna sbagliata, non dati.
        return Dataset.from_dict({"text": [
            f"### Istruzione:\nDomanda numero {i} sul contenuto del corso.\n\n"
            f"### Risposta:\nUna spiegazione articolata, diversa per ogni "
            f"esempio, che porta alla conclusione numero {i}."
            for i in range(n)]})

    def test_a_subset_is_taken_when_asked(self):
        loader, namespace = self._loader(500)
        self._sorgente(namespace, 5000)
        train, _ = loader()
        assert len(train) == 500

    def test_zero_means_the_whole_dataset(self):
        loader, namespace = self._loader(0)
        self._sorgente(namespace, 3000)
        train, _ = loader()
        assert len(train) == 3000

    def test_a_dataset_smaller_than_the_cap_is_left_alone(self):
        loader, namespace = self._loader(10_000)
        self._sorgente(namespace, 400)
        train, _ = loader()
        assert len(train) == 400

    def test_the_subset_is_shuffled_not_the_first_n(self):
        """Molti dataset sono ordinati per categoria: prendere la testa
        significherebbe allenare su una fetta sola del compito."""
        loader, namespace = self._loader(50)
        self._sorgente(namespace, 5000)
        train, _ = loader()
        # Il numero d'ordine chiude il testo con un punto: va tolto prima di
        # leggerlo come intero.
        taken = {int(t.rsplit(" ", 1)[-1].rstrip(".")) for t in train["text"]}
        assert taken != set(range(50))
        assert max(taken) > 500          # pesca in tutto il dataset

    def test_the_same_seed_gives_the_same_subset(self):
        """Due run confrontabili devono vedere gli stessi esempi."""
        first, second = [], []
        for out in (first, second):
            loader, namespace = self._loader(40)
            self._sorgente(namespace, 2000)
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
        """Fitti costano tempo di scrittura, radi costano ore di training.

        La cadenza viene poi arrotondata al multiplo della validazione: qui si
        passa 1 come cadenza di validazione, cosi' si misura il criterio e non
        l'arrotondamento.
        """
        source = self._script()
        # Estrazione con l'AST: tagliare alla prima riga vuota spezzava la
        # funzione a meta' docstring appena questa e' cresciuta.
        namespace = {}
        nodo = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "save_interval")
        exec(ast.get_source_segment(source, nodo), namespace)
        save_interval = namespace["save_interval"]
        # dataset enorme: si ferma al tetto
        assert save_interval(395_000, 1) == 2000
        # dataset minuscolo: non scende sotto il pavimento
        assert save_interval(50, 1) == 100
        # caso intermedio: ~20 punti di ripresa
        steps = (20_000 * 2) // 8
        assert save_interval(20_000, 1) == pytest.approx(steps // 20, abs=1)

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


class TestHyperparamUpdate:
    """Cambiare batch a run fermo, senza ributtare via gli step già fatti.

    È il caso reale: un run parte con un batch che non entra in VRAM, lo si
    ferma, e lo si vuole riprendere più leggero dal checkpoint.
    """

    def _stopped(self, **hyper):
        from core.training.jobs import create_training_job, _load_jobs, _save_jobs
        job = create_training_job({
            "base_model": "gpt2", "method": "lora_unsloth", "dataset_id": "x/y",
            "hyperparams": {"batch_size": 8, "gradient_accumulation": 4, **hyper},
        })["job"]
        jobs = _load_jobs(); jobs[job["id"]]["status"] = "stopped"; _save_jobs(jobs)
        return job["id"]

    def test_the_new_values_reach_the_script(self):
        from core.training.jobs import update_job_hyperparams, _load_jobs, delete_job
        job_id = self._stopped()
        try:
            result = update_job_hyperparams(job_id, {"batch_size": 2,
                                                     "gradient_accumulation": 16})
            assert result["success"] is True
            source = Path(_load_jobs()[job_id]["script_path"]).read_text(encoding="utf-8")
            # Batch e accumulo passano da due variabili, perche' lo script puo'
            # doverli ridurre da solo su un'architettura che non regge il
            # checkpointing: il valore scelto resta quello, la config lo legge.
            assert "BATCH = 2" in source
            assert "ACCUM = 16" in source
            assert "per_device_train_batch_size=BATCH" in source
            assert "gradient_accumulation_steps=ACCUM" in source
        finally:
            delete_job(job_id)

    def test_keeping_the_effective_batch_raises_no_warning(self):
        """8x4 e 2x16 danno lo stesso numero di step: il checkpoint resta valido."""
        from core.training.jobs import update_job_hyperparams, delete_job
        job_id = self._stopped()
        try:
            result = update_job_hyperparams(job_id, {"batch_size": 2,
                                                     "gradient_accumulation": 16})
            assert result["effective_batch"] == 32
            assert "Attenzione" not in result["message"]
        finally:
            delete_job(job_id)

    def test_changing_the_effective_batch_is_flagged(self):
        from core.training.jobs import update_job_hyperparams, delete_job
        job_id = self._stopped()
        try:
            result = update_job_hyperparams(job_id, {"batch_size": 2})
            assert result["effective_batch"] == 8
            assert "Attenzione" in result["message"]
            assert "checkpoint" in result["message"]
        finally:
            delete_job(job_id)

    def test_a_running_or_paused_job_is_refused(self):
        from core.training.jobs import (update_job_hyperparams, _load_jobs,
                                        _save_jobs, delete_job)
        job_id = self._stopped()
        try:
            for status in ("running", "paused"):
                jobs = _load_jobs(); jobs[job_id]["status"] = status; _save_jobs(jobs)
                result = update_job_hyperparams(job_id, {"batch_size": 2})
                assert result["success"] is False
                assert "Fermalo" in result["error"] or "memoria" in result["error"]
        finally:
            delete_job(job_id)

    def test_the_change_survives_in_the_stored_request(self):
        """Il prossimo `_sync_script_template` deve rigenerare con i valori nuovi."""
        from core.training.jobs import update_job_hyperparams, _load_jobs, delete_job
        job_id = self._stopped()
        try:
            update_job_hyperparams(job_id, {"batch_size": 2, "gradient_accumulation": 16})
            stored = _load_jobs()[job_id]["request"]["hyperparams"]
            assert stored["batch_size"] == 2 and stored["gradient_accumulation"] == 16
        finally:
            delete_job(job_id)

    def test_an_empty_update_is_refused(self):
        from core.training.jobs import update_job_hyperparams, delete_job
        job_id = self._stopped()
        try:
            assert update_job_hyperparams(job_id, {})["success"] is False
        finally:
            delete_job(job_id)


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
        # Il caricatore taglia il dataset prima di formattarlo (legge
        # MAX_EXAMPLES: 0 significa "prendi tutto") e formatta con i due
        # helper, che vanno portati nello stesso ambiente.
        ns = {"json": json, "sigma": lambda *a: None, "MAX_EXAMPLES": 0,
              "_TEMPLATE_PROPRIO": [None]}
        albero = ast.parse(source)
        ns["INDIZI_DOMINIO"] = next(
            ast.literal_eval(n.value) for n in albero.body
            if isinstance(n, ast.Assign)
            and getattr(n.targets[0], "id", "") == "INDIZI_DOMINIO")
        for nome in ("coppia_a_testo", "turni_a_testo", "composizione_del_dataset"):
            aiuto = next(n for n in albero.body
                         if isinstance(n, ast.FunctionDef) and n.name == nome)
            exec(ast.get_source_segment(source, aiuto), ns)
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


class TestTrustRemoteCode:
    """Caricare un modello con architettura propria significa eseguire il
    codice Python del suo repo. E' una scelta di chi lancia il job."""

    def _render(self, method, hyper):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "org/strano", "method": method, "dataset_id": "x/y",
             "hyperparams": hyper}, "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES[method], values)

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft"])
    def test_spento_se_non_lo_si_chiede(self, method):
        source = self._render(method, {"num_epochs": 1})
        assert "TRUST_REMOTE_CODE = False" in source

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft"])
    def test_acceso_solo_su_richiesta(self, method):
        source = self._render(method, {"num_epochs": 1, "trust_remote_code": True})
        assert "TRUST_REMOTE_CODE = True" in source
        assert "trust_remote_code=TRUST_REMOTE_CODE" in source

    def test_il_caricamento_lo_annuncia_nel_log(self):
        """Un job che esegue codice di terzi deve dirlo dove qualcuno lo legge."""
        source = self._render("lora_unsloth", {"trust_remote_code": True})
        assert "ATTENZIONE: trust_remote_code attivo" in source


class TestGradientCheckpointing:
    """Unsloth attiva il checkpointing per conto suo in `from_pretrained`:
    `use_gradient_checkpointing` ha "unsloth" come valore predefinito, e da li'
    chiama `_set_gradient_checkpointing` sul modello. Passarlo solo a
    `get_peft_model` non bastava — le architetture che non lo supportano si
    fermavano, e su tutte le altre si pagava il rallentamento anche quando
    l'autotune aveva deciso di non usarlo."""

    def _sorgente(self):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": "lora_unsloth", "dataset_id": "x/y",
             "hyperparams": {"num_epochs": 1}}, "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES["lora_unsloth"], values)

    def test_al_caricamento_non_si_dice_niente_a_unsloth(self):
        """Misurato tre volte sullo stesso lavoro (Qwen2.5-0.5B, batch 8, seq
        1024): non passare il parametro da' 1,1 GB e 0,72 s/step; passarlo
        `False` da' 47 GB e 346 s/step; passarlo `"unsloth"` da' 23 GB e un run
        che non parte. Unsloth decide da se', e decide meglio."""
        source = self._sorgente()
        # Il caricamento vive in una funzione, perche' va rifatto se il modello
        # non regge la precisione scelta: la finestra si chiude sulla parentesi
        # indentata, non sulla prima `)` — quella cadrebbe dentro
        # `bool(TUNE.get(...))`.
        blocco = source.split("FastLanguageModel.from_pretrained(")[1].split("\n    )")[0]
        assert "use_gradient_checkpointing" not in blocco
        assert "**CARICAMENTO" in blocco

    def test_ma_si_puo_forzare_a_spegnerlo(self):
        """L'unica eccezione: un'architettura che non lo supporta affatto."""
        source = self._sorgente()
        assert ('CARICAMENTO = {} if SUPPORTA_CHECKPOINTING '
                'else {"use_gradient_checkpointing": False}') in source

    def test_il_trainer_si_spegne_solo_dove_serve(self):
        """`SFTConfig` di Unsloth ha `gradient_checkpointing=True` come
        predefinito, ed e' il valore con cui i run buoni hanno sempre girato:
        va lasciato, tranne sulle architetture che non lo reggono."""
        source = self._sorgente()
        assert "gradient_checkpointing=SUPPORTA_CHECKPOINTING" in source

    def test_il_trainer_non_lo_riaccende_da_solo(self):
        """`SFTConfig` di Unsloth ha `gradient_checkpointing=True` come
        predefinito, e il Trainer lo attiva all'inizio di `train()` comunque
        sia stato caricato il modello."""
        source = self._sorgente()
        blocco = source.split("args=SFTConfig(")[1].split("\n    )")[0]
        assert "gradient_checkpointing=" in blocco


class TestArchitetturaIncompleta:
    """Alcuni repo con architettura propria non implementano
    `get_input_embeddings`, e transformers 5 non lo indovina piu' da solo."""

    def _shim(self):
        """Estrae la funzione dal template e la esegue in un ambiente pulito."""
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "org/strano", "method": "lora_unsloth", "dataset_id": "x/y",
             "hyperparams": {"trust_remote_code": True}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["lora_unsloth"], values)
        nodo = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "completa_architettura")
        detto = []
        ns = {"sigma": lambda m: detto.append(m)}
        exec(ast.get_source_segment(source, nodo), ns)
        return ns["completa_architettura"], detto

    def test_riconosce_chi_lo_implementa_davvero(self, monkeypatch):
        """In transformers 5 il metodo sta in `EmbeddingAccessMixin`: escludere
        il solo `PreTrainedModel` faceva scambiare il fallback della libreria
        per un'implementazione dell'autore, e il modello restava rotto."""
        import transformers

        class MixinDiLibreria:
            def get_input_embeddings(self):
                raise NotImplementedError
        MixinDiLibreria.__module__ = "transformers.modeling_utils"

        class ModelloAltrui(MixinDiLibreria):
            pass
        ModelloAltrui.__module__ = "transformers_modules.org.strano"

        completa, detto = self._shim()
        monkeypatch.setattr(transformers.AutoConfig, "from_pretrained",
                            classmethod(lambda cls, *a, **k: type(
                                "C", (), {"auto_map": {"AutoModelForCausalLM": "x.Y"}})()))
        monkeypatch.setattr("transformers.dynamic_module_utils.get_class_from_dynamic_module",
                            lambda ref, mid, **k: ModelloAltrui)
        completa("org/strano")
        assert "get_input_embeddings" in ModelloAltrui.__dict__, \
            "il metodo della libreria non conta come implementazione"

    def test_non_tocca_chi_lo_dichiara(self, monkeypatch):
        import transformers

        class ModelloCompleto:
            def get_input_embeddings(self):
                return "la mia"
        ModelloCompleto.__module__ = "transformers_modules.org.strano"
        originale = ModelloCompleto.get_input_embeddings

        completa, _ = self._shim()
        monkeypatch.setattr(transformers.AutoConfig, "from_pretrained",
                            classmethod(lambda cls, *a, **k: type(
                                "C", (), {"auto_map": {"AutoModelForCausalLM": "x.Y"}})()))
        monkeypatch.setattr("transformers.dynamic_module_utils.get_class_from_dynamic_module",
                            lambda ref, mid, **k: ModelloCompleto)
        completa("org/strano")
        assert ModelloCompleto.get_input_embeddings is originale

    def test_con_due_embedding_non_tira_a_indovinare(self, monkeypatch):
        """Addestrare la matrice sbagliata e' peggio di un errore chiaro."""
        import torch.nn as nn
        import transformers

        class Ambiguo(nn.Module):
            def __init__(self):
                super().__init__()
                self.una = nn.Embedding(4, 2)
                self.altra = nn.Embedding(4, 2)
        Ambiguo.__module__ = "transformers_modules.org.strano"

        completa, _ = self._shim()
        monkeypatch.setattr(transformers.AutoConfig, "from_pretrained",
                            classmethod(lambda cls, *a, **k: type(
                                "C", (), {"auto_map": {"AutoModelForCausalLM": "x.Y"}})()))
        monkeypatch.setattr("transformers.dynamic_module_utils.get_class_from_dynamic_module",
                            lambda ref, mid, **k: Ambiguo)
        completa("org/strano")
        with pytest.raises(NotImplementedError, match="2 embedding"):
            Ambiguo().get_input_embeddings()


class TestGuardiaVram:
    """Sforare la VRAM su Windows non produce un errore: il driver pagina in
    RAM di sistema e il run continua, centinaia di volte piu' lento. Un ciclo
    automatico ci resta dentro per giorni senza che nessuno se ne accorga."""

    def _callback(self, method="lora_unsloth"):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"max_seq_length": 1024}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES[method], values)
        limite = next(n for n in ast.parse(source).body
                      if isinstance(n, ast.Assign)
                      and getattr(n.targets[0], "id", "") == "VRAM_LIMITE")
        return limite, source

    def test_il_limite_lascia_un_margine_ma_non_troppo(self):
        limite, _ = self._callback()
        valore = limite.value.value
        assert 1.0 < valore <= 1.15, "un margine, non una scappatoia"

    def test_un_picco_isolato_non_ferma_il_run(self):
        """Una lettura sola puo' essere un'allocazione transitoria."""
        _, source = self._callback()
        assert "self.sforata >= 3" in source

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_la_guardia_c_e_in_ogni_metodo(self, method):
        _, source = self._callback(method)
        assert '"VRAM sforata: ' in source

    def test_il_messaggio_dice_cosa_cambiare(self):
        """Un errore che non suggerisce la mossa successiva costa un altro giro."""
        _, source = self._callback()
        # Il commento nel costruttore contiene la stessa parola: si cerca il
        # testo del messaggio vero, non la prima occorrenza.
        blocco = source.split('"VRAM sforata: ')[1][:600]
        assert "batch_size" in blocco and "max_seq_length" in blocco


class TestCheckpointingSuUnsloth:

    def test_un_modello_piccolo_non_ha_bisogno_del_checkpointing(self):
        """Sull'adapter il checkpointing di Unsloth significa offload verso la
        RAM di sistema: su un modello che nella scheda ci sta comodo e' un
        costo puro, e su Windows arriva a bloccare la macchina."""
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        cfg = gpu_layer.recommend_training_config(
            "lora_unsloth", "Qwen/Qwen2.5-0.5B", 1024, report=report)
        assert cfg["gradient_checkpointing"] is False

    def test_gli_altri_metodi_decidono_come_prima(self):
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        piccolo = gpu_layer.recommend_training_config(
            "trl_sft", "Qwen/Qwen2.5-0.5B", 1024, report=report)
        grande = gpu_layer.recommend_training_config(
            "trl_sft", "meta-llama/Llama-3.1-8B", 1024, report=report)
        assert piccolo["gradient_checkpointing"] is False
        assert grande["gradient_checkpointing"] is True


class TestGuardiaRam:
    """La RAM di sistema e' la meta' piu' grave del problema: con l'offload dei
    gradienti Unsloth sposta i tensori nella memoria dell'host, Windows non la
    protegge, e non arriva nessun errore — arriva che la macchina si pianta e
    va riavviata, perdendo tutto il lavoro del run."""

    def _sorgente(self, method="lora_unsloth"):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"max_seq_length": 1024}}, "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES[method], values)

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_c_e_in_ogni_metodo(self, method):
        assert "RAM di sistema quasi esaurita" in self._sorgente(method)

    def test_la_soglia_lascia_margine_per_reagire(self):
        limite = next(n for n in ast.parse(self._sorgente()).body
                      if isinstance(n, ast.Assign)
                      and getattr(n.targets[0], "id", "") == "RAM_LIMITE_PCT")
        assert 85.0 <= limite.value.value <= 95.0, \
            "sotto si ferma per niente, sopra si ferma quando e' gia' tardi"

    def test_un_picco_isolato_non_ferma_il_run(self):
        assert "self.ram_scarsa >= 3" in self._sorgente()

    def test_psutil_assente_non_fa_fallire_il_training(self):
        """La guardia e' un di piu': se manca la libreria il run prosegue."""
        source = self._sorgente()
        blocco = source.split("import psutil")[1][:900]
        assert "except ImportError" in blocco

    def test_il_messaggio_nomina_la_causa_probabile(self):
        blocco = self._sorgente().split('"RAM di sistema quasi esaurita')[1][:400]
        assert "offload" in blocco and "batch_size" in blocco


class TestFermareDavvero:
    """Fermare un job deve fermarlo davvero.

    Il `python.exe` del venv e' un lanciatore che genera l'interprete vero come
    figlio, ed e' il figlio a tenere i tensori. Terminando solo il padre il
    training resta vivo, orfano, con decine di GB in mano: misurati 41 GB su
    due job che avevano risposto "fermato con successo". Bastano tre stop per
    mandare la macchina al riavvio.
    """

    def test_ai_figli_ci_si_arriva(self, monkeypatch):
        from core.training import jobs

        terminati = []

        class FintoProc:
            def __init__(self, nome):
                self.nome = nome

            def terminate(self):
                terminati.append(self.nome)

            def kill(self):
                terminati.append(self.nome + "!")

        figli = [FintoProc("figlio1"), FintoProc("figlio2")]
        radice = FintoProc("padre")
        radice.children = lambda recursive=False: figli

        finto_psutil = type("P", (), {
            "Process": staticmethod(lambda pid: radice),
            "wait_procs": staticmethod(lambda procs, timeout=None: (procs, [])),
        })
        monkeypatch.setitem(sys.modules, "psutil", finto_psutil)

        assert jobs._termina_albero(123) == 3
        assert terminati == ["figlio1", "figlio2", "padre"]

    def test_chi_resiste_viene_ucciso(self, monkeypatch):
        """Su Windows un processo dentro una chiamata CUDA ignora il terminate."""
        from core.training import jobs

        uccisi = []

        class Testardo:
            def terminate(self):
                pass

            def kill(self):
                uccisi.append("kill")

        ostinato = Testardo()
        ostinato.children = lambda recursive=False: []
        finto_psutil = type("P", (), {
            "Process": staticmethod(lambda pid: ostinato),
            "wait_procs": staticmethod(lambda procs, timeout=None: ([], list(procs))),
        })
        monkeypatch.setitem(sys.modules, "psutil", finto_psutil)

        jobs._termina_albero(123)
        assert uccisi == ["kill"]

    def test_uno_stop_che_non_ferma_niente_lo_dice(self, monkeypatch, tmp_path):
        """Rispondere "fermato" a un processo ancora vivo e' il modo in cui si
        accumulano orfani senza che nessuno se ne accorga."""
        from core.training import jobs

        monkeypatch.setattr(jobs, "_load_jobs", lambda: {"j1": {"id": "j1", "pid": 999}})
        monkeypatch.setattr(jobs, "_save_jobs", lambda j: None)
        monkeypatch.setattr(jobs, "_termina_albero", lambda pid, attesa=12.0: 1)
        monkeypatch.setattr(jobs, "_pid_alive", lambda pid, script_path="": True)

        out = jobs.stop_training_job("j1")
        assert not out["success"]
        assert "999" in out["error"] and "memoria" in out["error"]


class TestProcessiSullaGpu:
    """Chi occupa la GPU deve essere visibile e chiudibile dalla scheda Hardware.

    Un training rimasto orfano — Sigma chiuso, il figlio ancora vivo — non
    compariva da nessuna parte: il job non aveva piu' un tasto Stop, e l'unico
    pulsante della scheda Hardware («Pulisci VRAM») riavvia Ollama e non tocca i
    processi di training. L'unica via era il Task Manager.
    """

    def _smi(self, compute_apps):
        """Finto nvidia-smi: mappa delle schede piu' l'elenco dei processi."""
        def finto(cmd, timeout=5.0):
            argomenti = " ".join(cmd)
            if "--query-gpu=" in argomenti:
                return "0, GPU-aaa, NVIDIA GeForce RTX 5070 Ti\n1, GPU-bbb, NVIDIA GeForce RTX 5060\n"
            if "--query-compute-apps=" in argomenti:
                return compute_apps
            return ""
        return finto

    def test_vram_non_disponibile_non_diventa_zero(self, monkeypatch):
        """Su Windows WDDM il driver non attribuisce la VRAM ai processi.

        Scrivere 0 al posto di `[N/A]` mostrerebbe "0 GB" accanto a un training
        che ne sta usando cinque: una misura sbagliata e' peggio di nessuna.
        """
        monkeypatch.setattr(gpu_layer.shutil, "which", lambda _: "nvidia-smi")
        monkeypatch.setattr(gpu_layer, "_run", self._smi("111, [N/A], GPU-aaa\n"))
        monkeypatch.setitem(sys.modules, "psutil", None)

        processi = gpu_layer.probe_gpu_processes()
        assert len(processi) == 1
        assert processi[0]["vram_mb"] is None
        assert processi[0]["vram_gb"] is None

    def test_la_scheda_arriva_come_indice(self, monkeypatch):
        """nvidia-smi identifica la GPU di un processo per uuid, Sigma per indice."""
        monkeypatch.setattr(gpu_layer.shutil, "which", lambda _: "nvidia-smi")
        monkeypatch.setattr(gpu_layer, "_run",
                            self._smi("111, 4096, GPU-bbb\n222, 8192, GPU-aaa\n"))
        monkeypatch.setitem(sys.modules, "psutil", None)

        per_pid = {p["pid"]: p for p in gpu_layer.probe_gpu_processes()}
        assert per_pid[111]["gpu_index"] == 1
        assert per_pid[222]["gpu_index"] == 0
        assert per_pid[222]["vram_gb"] == 8.0
        # Chi occupa piu' memoria per primo: e' quello che si sta cercando.
        assert gpu_layer.probe_gpu_processes()[0]["pid"] == 222

    def test_il_figlio_risale_al_job_del_padre(self, monkeypatch):
        """Il pid registrato e' il lanciatore, quello sulla GPU e' il figlio.

        Senza risalire la catena dei processi i due numeri non si incontrano mai
        e il training risulta "esterno a Sigma", cioe' inattribuibile.
        """
        from core.training import jobs

        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes",
                            lambda: [{"pid": 36672, "cmdline": "", "gpu_index": 0,
                                      "vram_mb": None, "started_at": ""}])
        monkeypatch.setattr(jobs, "_catena_di_processi",
                            lambda pid: [36672, 22648, 20140] if pid == 36672 else [pid])
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {
            "dc8286b1": {"id": "dc8286b1", "pid": 22648, "status": "running",
                         "method": "lora_unsloth", "base_model": "Qwen/Qwen2.5-0.5B"}})

        voce = jobs.gpu_process_inventory()["processes"][0]
        assert voce["job_id"] == "dc8286b1"
        assert voce["attribution"] == "pid"
        assert voce["kind"] == "training"
        assert voce["killable"]

    def test_un_processo_vivo_su_un_job_finito_e_un_orfano(self, monkeypatch):
        from core.training import jobs

        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes",
                            lambda: [{"pid": 500, "cmdline": "", "gpu_index": 0,
                                      "vram_mb": None, "started_at": ""}])
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_load_jobs",
                            lambda: {"j1": {"id": "j1", "pid": 500, "status": "completed"}})

        esito = jobs.gpu_process_inventory()
        assert esito["orfani"] == 1
        assert esito["processes"][0]["orphan"] is True

    def test_sigma_non_si_chiude_da_solo(self, monkeypatch):
        """Il processo di Sigma non deve nemmeno avere il pulsante.

        Liberare la GPU chiudendo il server chiuderebbe anche l'interfaccia da
        cui e' arrivata la richiesta.
        """
        from core.training import jobs

        nostro = os.getpid()
        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes",
                            lambda: [{"pid": nostro, "cmdline": "", "gpu_index": 0,
                                      "vram_mb": None, "started_at": ""}])
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {})

        voce = jobs.gpu_process_inventory()["processes"][0]
        assert voce["kind"] == "sigma"
        assert voce["killable"] is False
        assert not jobs.terminate_gpu_process(nostro)["success"]

    def test_un_processo_estraneo_resta_estraneo(self, monkeypatch):
        """`--query-compute-apps` elenca anche i browser: non vanno confusi."""
        from core.training import jobs

        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes",
                            lambda: [{"pid": 777, "cmdline": "brave.exe --type=gpu-process",
                                      "gpu_index": 1, "vram_mb": None, "started_at": ""}])
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {"j1": {"id": "j1", "pid": 22648,
                                                               "status": "running"}})

        voce = jobs.gpu_process_inventory()["processes"][0]
        assert voce["kind"] == "esterno"
        assert voce["job_id"] is None

    def test_se_il_pid_registrato_e_morto_si_chiude_comunque(self, monkeypatch):
        """`stop_training_job` parte dal pid nel registro; se quello e' vecchio
        l'albero vero resta in piedi e la GPU occupata."""
        from core.training import jobs

        vivi = {4242}
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_pid_alive",
                            lambda pid, script_path="": int(pid) in vivi)
        monkeypatch.setattr(jobs, "_load_jobs",
                            lambda: {"j1": {"id": "j1", "pid": 4242, "status": "running"}})
        monkeypatch.setattr(jobs, "_save_jobs", lambda j: None)
        # Lo stop "riesce" senza toccare niente: il pid nel registro era gia' morto.
        monkeypatch.setattr(jobs, "stop_training_job",
                            lambda job_id: {"success": True, "message": "fermato"})

        def albero(pid, attesa=12.0):
            vivi.discard(int(pid))
            return 2

        monkeypatch.setattr(jobs, "_termina_albero", albero)

        esito = jobs.terminate_gpu_process(4242)
        assert esito["success"]
        assert esito["job_id"] == "j1"
        assert 4242 not in vivi

    def test_un_processo_che_sopravvive_viene_dichiarato_tale(self, monkeypatch):
        from core.training import jobs

        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_pid_alive", lambda pid, script_path="": True)
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {})
        monkeypatch.setattr(jobs, "_termina_albero", lambda pid, attesa=12.0: 1)

        esito = jobs.terminate_gpu_process(4242)
        assert not esito["success"]
        assert "4242" in esito["error"]

    def test_un_pid_inventato_non_passa(self):
        from core.training import jobs

        assert not jobs.terminate_gpu_process("pippo")["success"]
        assert not jobs.terminate_gpu_process(-1)["success"]

    def test_il_compositore_del_desktop_non_si_tocca(self, monkeypatch):
        """`dwm.exe` disegna il desktop e apre un contesto sulla GPU: compariva
        nella lista con accanto un pulsante «Termina»."""
        from core.training import jobs

        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes",
                            lambda: [{"pid": 2252, "name": "dwm.exe", "cmdline": "",
                                      "gpu_index": 1, "vram_mb": None, "started_at": ""}])
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {})

        voce = jobs.gpu_process_inventory()["processes"][0]
        assert voce["kind"] == "sistema"
        assert voce["killable"] is False

    def test_la_protezione_vale_anche_chiamando_l_endpoint(self, monkeypatch):
        """Nascondere il pulsante non basta: /gpu/kill accetta un pid qualunque."""
        from core.training import jobs

        finto_psutil = type("P", (), {
            "Process": staticmethod(lambda pid: type("X", (), {
                "name": lambda self: "lsass.exe",
                "cmdline": lambda self: [],
            })()),
        })
        monkeypatch.setitem(sys.modules, "psutil", finto_psutil)
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_pid_alive", lambda pid, script_path="": True)
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {})
        monkeypatch.setattr(jobs, "_termina_albero",
                            lambda pid, attesa=12.0: pytest.fail("non deve toccarlo"))

        esito = jobs.terminate_gpu_process(888)
        assert not esito["success"]
        assert "lsass.exe" in esito["error"]

    def test_lo_stesso_processo_su_due_schede_e_una_riga_sola(self, monkeypatch):
        """nvidia-smi elenca un processo una volta per GPU: Sigma, che le
        interroga entrambe, compariva due volte identico."""
        from core.training import jobs

        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes", lambda: [
            {"pid": 9244, "name": "python.exe", "cmdline": "", "gpu_index": 0,
             "gpu_name": "RTX 5070 Ti", "vram_mb": 2048.0, "vram_gb": 2.0, "started_at": ""},
            {"pid": 9244, "name": "python.exe", "cmdline": "", "gpu_index": 1,
             "gpu_name": "RTX 5060", "vram_mb": 1024.0, "vram_gb": 1.0, "started_at": ""},
        ])
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {})

        processi = jobs.gpu_process_inventory()["processes"]
        assert len(processi) == 1
        assert [g["name"] for g in processi[0]["gpus"]] == ["RTX 5070 Ti", "RTX 5060"]
        # La VRAM del processo e' quella che occupa in tutto, non su una scheda.
        assert processi[0]["vram_gb"] == 3.0

    def test_due_schede_non_misurabili_restano_non_misurabili(self, monkeypatch):
        """Sommare dei `None` non deve produrre uno zero che sembra una misura."""
        from core.training import jobs

        monkeypatch.setattr(jobs.gpu_layer, "probe_gpu_processes", lambda: [
            {"pid": 9244, "name": "python.exe", "cmdline": "", "gpu_index": 0,
             "gpu_name": "a", "vram_mb": None, "vram_gb": None, "started_at": ""},
            {"pid": 9244, "name": "python.exe", "cmdline": "", "gpu_index": 1,
             "gpu_name": "b", "vram_mb": None, "vram_gb": None, "started_at": ""},
        ])
        monkeypatch.setattr(jobs, "_catena_di_processi", lambda pid: [pid])
        monkeypatch.setattr(jobs, "_load_jobs", lambda: {})

        voce = jobs.gpu_process_inventory()["processes"][0]
        assert voce["vram_mb"] is None and voce["vram_gb"] is None


class TestArchitettureFatteAMano:
    """Un'architettura che non regge il checkpointing e' quasi sempre scritta a
    mano, e chi la scrive a mano scrive anche l'attenzione a mano: `softmax(q @
    k.T)` materializza una matrice (batch x teste x T x T) per **ogni**
    livello, e senza checkpointing restano tutte fino al backward.

    Misurato su Ailo340m-v4 (32 livelli, 12 teste, contesto 1024): batch 8 =
    53 GB su una scheda da 15,9 e OutOfMemory; batch 2 = un paio di GB.
    """

    def _esegui(self, supporta, batch=8, accum=4):
        """Esegue il pezzo di script che decide batch e accumulo."""
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": "lora_unsloth", "dataset_id": "x/y",
             "hyperparams": {"batch_size": batch, "gradient_accumulation": accum}},
            "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["lora_unsloth"], values)
        inizio = source.index("BATCH = ")
        pezzo = source[inizio:source.index("model, tokenizer =", inizio)]
        ns = {"SUPPORTA_CHECKPOINTING": supporta, "sigma": lambda m: None}
        exec(pezzo, ns)
        return ns["BATCH"], ns["ACCUM"]

    def test_un_architettura_normale_non_viene_toccata(self):
        assert self._esegui(supporta=True) == (8, 4)

    def test_senza_checkpointing_il_batch_si_riduce(self):
        batch, _ = self._esegui(supporta=False)
        assert batch == 2

    def test_il_batch_efficace_resta_lo_stesso(self):
        """Ridurre il batch senza compensare cambierebbe l'addestramento, non
        solo la memoria: il gradiente verrebbe da un campione piu' piccolo."""
        prima = 8 * 4
        batch, accum = self._esegui(supporta=False, batch=8, accum=4)
        assert batch * accum == prima

    def test_un_batch_gia_piccolo_non_si_tocca(self):
        assert self._esegui(supporta=False, batch=2, accum=16) == (2, 16)
        assert self._esegui(supporta=False, batch=1, accum=32) == (1, 32)


class TestFormatiDataset:
    """Riconoscere il formato di un dataset, o fermarsi.

    E' il difetto piu' costoso trovato finora, perche' non somigliava a un
    errore: il ripiego prendeva la prima colonna di testo e il training partiva.
    Su OpenOrca quella colonna era `id`, e il modello ha passato ore a imparare
    stringhe come "niv.242684"; su MetaMathQA era `type`, cioe' una dozzina di
    etichette; su OpenMathInstruct-2 era `problem`, cioe' le domande senza mai
    una risposta. I benchmark successivi davano 100% di risposte illeggibili, e
    ogni round veniva scartato — il ciclo funzionava, i dati no.
    """

    def _formatta(self, colonne):
        """Fa girare la catena di riconoscimento su uno schema di colonne."""
        import datasets as D
        from datasets import Dataset

        from core.training.jobs import _build_script_values

        values = _build_script_values(
            {"base_model": "gpt2", "method": "trl_sft", "dataset_id": "x/y",
             "hyperparams": {}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["trl_sft"], values)
        albero = ast.parse(source)
        pezzi = {n.name: ast.get_source_segment(source, n) for n in albero.body
                 if isinstance(n, ast.FunctionDef)
                 and n.name in ("load_training_dataset", "load_train_and_eval",
                                "coppia_a_testo", "turni_a_testo",
                                "composizione_del_dataset")}

        n = max(len(v) for v in colonne.values())
        ds = Dataset.from_dict({k: (v * n)[:n] for k, v in colonne.items()})
        vecchio = D.load_dataset
        D.load_dataset = lambda *a, **k: ds
        try:
            ns = {"sigma": lambda m: None, "json": json, "os": __import__("os"),
                  "DATASET_KIND": "hf", "DATASET_PATH": "x/y", "DATASET_SPLIT": "train",
                  "DATASET_CONFIG": "", "LEGACY_HF_DATASETS": {}, "HF_DATASET_CONFIGS": {},
                  "VALIDATION_FRACTION": 0.0, "MAX_EXAMPLES": 0,
                  # Senza template di chat i formattatori usano lo schema
                  # testuale: e' quello che questi test verificano.
                  "_TEMPLATE_PROPRIO": [None]}
            ns["INDIZI_DOMINIO"] = next(
                ast.literal_eval(n.value) for n in albero.body
                if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", "") == "INDIZI_DOMINIO")
            for nome in ("coppia_a_testo", "turni_a_testo", "composizione_del_dataset",
                         "load_training_dataset", "load_train_and_eval"):
                exec(pezzi[nome], ns)
            train, _ = ns["load_train_and_eval"]()
            return str(train["text"][0])
        finally:
            D.load_dataset = vecchio

    LUNGA = ["Una risposta articolata che spiega il ragionamento fino alla conclusione."]

    def test_openorca_usa_domanda_e_risposta_non_l_id(self):
        testo = self._formatta({"id": ["niv.242684"], "system_prompt": ["Sei un assistente."],
                                "question": ["Quanto fa 2+2?"], "response": self.LUNGA})
        assert "niv.242684" not in testo
        assert "Quanto fa 2+2?" in testo and "ragionamento" in testo

    def test_openmathinstruct_include_la_soluzione(self):
        testo = self._formatta({"problem": ["Ava ha tre mele e ne compra altre due."],
                                "generated_solution": self.LUNGA,
                                "expected_answer": ["5"], "problem_source": ["aug"]})
        assert "ragionamento" in testo, "senza la soluzione impara solo le domande"

    def test_metamathqa_non_si_addestra_sulle_etichette(self):
        testo = self._formatta({"type": ["MATH_AnsAug"], "query": ["Quanto fa 5*6?"],
                                "original_question": ["5*6?"], "response": self.LUNGA})
        assert "MATH_AnsAug" not in testo
        assert "Quanto fa 5*6?" in testo and "ragionamento" in testo

    def test_una_coppia_non_prevista_ferma_il_run(self):
        """Prenderne una sola insegnerebbe meta' del compito, e in silenzio."""
        with pytest.raises(SystemExit, match="coppia domanda/risposta"):
            self._formatta({"domanda": ["Perche' il cielo e' blu e come si spiega?"],
                            "spiegazione": self.LUNGA, "tag": ["fisica"]})

    def test_una_colonna_di_etichette_ferma_il_run(self):
        with pytest.raises(SystemExit):
            self._formatta({"categoria": ["sport"] * 30 + ["musica"] * 30})

    def test_una_colonna_di_identificativi_ferma_il_run(self):
        with pytest.raises(SystemExit):
            self._formatta({"chiave": ["ab.%d" % i for i in range(60)]})

    def test_un_tag_non_viene_scambiato_per_meta_di_una_coppia(self):
        """Una colonna corta e ripetuta e' un'etichetta: se contasse come
        contenuto, ogni dataset con un `source` si fermerebbe per niente."""
        testo = self._formatta({"instruction": ["Scrivi una funzione"], "input": [""],
                                "output": ["def f(): pass"], "source": ["github"]})
        assert "def f(): pass" in testo


class TestMemoriaRealistica:
    """La memoria che conta e' quella che il driver vede, non quella che
    PyTorch dichiara.

    `max_memory_allocated` conta i tensori vivi: misurati 9,4 GB dichiarati
    mentre la scheda ne aveva 15,4 su 16,3. La guardia contro lo sforamento
    dormiva proprio mentre la memoria finiva, e il run degradava da 18 a 83
    secondi per passo senza che nulla si fermasse.
    """

    def _sorgente(self, method="lora_unsloth"):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"max_seq_length": 1024}}, "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES[method], values)

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_si_chiede_al_driver_non_all_allocatore(self, method):
        source = self._sorgente(method)
        assert "torch.cuda.mem_get_info()" in source
        # Il nome compare ancora nel commento che spiega perche' non si usa:
        # quello che conta e' che non sia piu' chiamato.
        assert "torch.cuda.max_memory_allocated()" not in source

    def test_un_run_che_rallenta_su_scheda_piena_si_ferma(self):
        """Rallentare *mentre* la scheda e' quasi piena non e' un caso: e'
        l'allocatore che sfoga in RAM di sistema, e da li' non si riprende."""
        source = self._sorgente()
        assert "self.strozzato >= 3" in source
        blocco = source.split("Il run sta rallentando su una scheda piena")[1][:400]
        assert "batch_size" in blocco and "max_seq_length" in blocco

    def test_un_rallentamento_su_scheda_libera_non_ferma_niente(self):
        """Un run lento ma con memoria disponibile ha un'altra causa: fermarlo
        toglierebbe lavoro buono."""
        source = self._sorgente()
        assert "self.ultima_vram > 0.90" in source


class TestStimaAttivazioni:

    def test_la_stima_riflette_la_misura(self):
        """La costante veniva da run su dati poi rivelatisi sbagliati:
        sequenze di dieci caratteri, che dopo la tokenizzazione non riempivano
        niente. Con testo vero da 1024 token e un modello da 0,5B la spesa e'
        ~1,8 GB a sequenza."""
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        cfg = gpu_layer.recommend_training_config(
            "lora_unsloth", "Qwen/Qwen2.5-0.5B", 1024, report=report)
        per_seq = 5.5 * (1024 / 2048.0) * max(0.35, cfg["params_b"]) ** 0.7
        assert 1.5 <= per_seq <= 2.2, "la stima deve stare vicino alla misura"
        # E il batch che ne deriva deve lasciare margine sulla scheda.
        assert cfg["batch_size"] * per_seq < 16.0 * 0.85

    def test_il_batch_efficace_resta_quello_voluto(self):
        report = _fake_report([_gpu(0, "RTX 5070 Ti", 16.0)])
        cfg = gpu_layer.recommend_training_config(
            "lora_unsloth", "Qwen/Qwen2.5-0.5B", 1024, report=report)
        effettivo = cfg["batch_size"] * cfg["gradient_accumulation"]
        assert 24 <= effettivo <= 40, "ridurre il batch senza compensare cambia l'addestramento"

    def test_una_scheda_occupata_abbassa_il_batch(self):
        """Ma non fino a uno: chi la occupa spesso la libera fra un minuto."""
        piena = _fake_report([dict(_gpu(0, "RTX 5070 Ti", 16.0), vram_free_gb=0.4)])
        vuota = _fake_report([dict(_gpu(0, "RTX 5070 Ti", 16.0), vram_free_gb=15.5)])
        con = gpu_layer.recommend_training_config("lora_unsloth", "Qwen/Qwen2.5-0.5B",
                                                  1024, report=piena)["batch_size"]
        senza = gpu_layer.recommend_training_config("lora_unsloth", "Qwen/Qwen2.5-0.5B",
                                                    1024, report=vuota)["batch_size"]
        assert 1 < con < senza


class TestCadenzeAllineate:
    """Salvataggio e validazione devono cadere insieme.

    Con `load_best_model_at_end` il Trainer deve poter far coincidere il
    checkpoint migliore con una misura: se i due passi non si allineano si
    rifiuta di partire — *"found 100, which is not a round multiple of 52"* —
    e il round fallisce prima ancora del primo step. E' successo due volte di
    fila, fermando il ciclo.
    """

    def _cadenze(self, esempi, method="lora_unsloth"):
        from core.training.jobs import _build_script_values

        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"num_epochs": 1, "batch_size": 8,
                             "gradient_accumulation": 4}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES[method], values)
        # `eval_interval` legge una costante definita altrove nello script.
        costante = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.Assign)
                        and getattr(n.targets[0], "id", "") == "TARGET_EVALS")
        ns = {"TARGET_EVALS": costante.value.value}
        for nome in ("eval_interval", "save_interval"):
            nodo = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == nome)
            exec(ast.get_source_segment(source, nodo), ns)
        ogni = ns["eval_interval"](esempi)
        return ogni, ns["save_interval"](esempi, ogni)

    @pytest.mark.parametrize("esempi", [1000, 5000, 30000, 100000, 395000])
    def test_il_salvataggio_e_multiplo_della_validazione(self, esempi):
        ogni, salva = self._cadenze(esempi)
        assert salva % ogni == 0, f"{salva} non e' multiplo di {ogni}"

    def test_resta_una_cadenza_sensata(self):
        """Allineare non deve stravolgere: i checkpoint restano abbastanza
        fitti da non perdere ore di lavoro, e abbastanza radi da non costare
        piu' del training."""
        _, salva = self._cadenze(30000)
        assert 50 <= salva <= 2500

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft"])
    def test_vale_per_ogni_metodo(self, method):
        ogni, salva = self._cadenze(30000, method)
        assert salva % ogni == 0


class TestTaglioPrimaDellaFormattazione:
    """Il sottoinsieme va estratto prima di trasformare il dataset.

    OpenMathInstruct-2 ha 13.972.791 righe. Formattarle tutte per tenerne
    30.000 sono minuti di CPU e qualche giga di cache a ogni round, buttati —
    e il progresso a schermo dice 8% quando il lavoro utile e' gia' finito.
    """

    def _sorgente(self, method="trl_sft"):
        from core.training.jobs import _build_script_values
        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {"max_examples": 30000}}, "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES[method], values)

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft", "full_pretrain"])
    def test_il_taglio_precede_la_trasformazione(self, method):
        source = self._sorgente(method)
        taglio = source.index("prima della formattazione")
        assert 0 < taglio < source.index(".map(")

    def test_il_taglio_avviene_una_volta_sola(self):
        """Tagliare due volte non sbaglia il risultato, ma rimescolare un
        campione gia' estratto e' lavoro che non serve a nessuno."""
        source = self._sorgente()
        assert source.count("shuffle(seed=42).select(range(MAX_EXAMPLES))") == 1

    def test_il_campione_resta_mescolato(self):
        """I dataset sono spesso ordinati per categoria: prendere la testa
        significherebbe addestrare su una fetta sola del compito."""
        source = self._sorgente()
        assert "shuffle(seed=42)" in source


class TestFormatoCoerente:
    """Il formato con cui si addestra dev'essere quello con cui si interroga.

    Non e' una raffinatezza: e' il difetto che ha reso inservibili giorni di
    round. Il modello imparava a continuare "### Istruzione: ... ### Risposta:"
    e il benchmark lo interrogava con i marcatori di chat del suo tokenizer.
    Due lingue diverse, e le risposte diventavano illeggibili.
    """

    def _pezzi(self):
        from core.training.jobs import _build_script_values

        values = _build_script_values(
            {"base_model": "gpt2", "method": "trl_sft", "dataset_id": "x/y",
             "hyperparams": {}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["trl_sft"], values)
        ns = {"sigma": lambda m: None, "_TEMPLATE_PROPRIO": [None]}
        for nome in ("usa_template_del_modello", "coppia_a_testo", "turni_a_testo"):
            nodo = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == nome)
            exec(ast.get_source_segment(source, nodo), ns)
        return ns

    class FintoTokenizer:
        def __init__(self, template="{{ messaggi }}"):
            self.chat_template = template

        def apply_chat_template(self, messaggi, tokenize=False):
            return "".join(f"<|{m['role']}|>{m['content']}" for m in messaggi)

    def test_un_modello_istruito_usa_il_suo_formato(self):
        ns = self._pezzi()
        assert ns["usa_template_del_modello"](self.FintoTokenizer()) is True
        testo = ns["coppia_a_testo"]("Quanto fa 2+2?", "Fa quattro.")
        assert testo == "<|user|>Quanto fa 2+2?<|assistant|>Fa quattro."
        assert "### Istruzione" not in testo

    def test_un_modello_base_resta_sullo_schema_testuale(self):
        """Senza template di chat, i marcatori non esistono: inventarli
        insegnerebbe un formato che il modello non conosce."""
        ns = self._pezzi()
        assert ns["usa_template_del_modello"](self.FintoTokenizer(template=None)) is False
        testo = ns["coppia_a_testo"]("Quanto fa 2+2?", "Fa quattro.")
        assert "### Istruzione:" in testo and "### Risposta:" in testo

    def test_il_prompt_di_sistema_diventa_un_turno(self):
        ns = self._pezzi()
        ns["usa_template_del_modello"](self.FintoTokenizer())
        testo = ns["coppia_a_testo"]("Domanda", "Risposta", sistema="Sei un assistente.")
        assert testo.startswith("<|system|>Sei un assistente.")

    def test_i_ruoli_dei_dataset_si_normalizzano(self):
        """`human`/`gpt` di OpenHermes non sono ruoli validi per un template:
        vanno tradotti, o il tokenizer li rifiuta."""
        ns = self._pezzi()
        ns["usa_template_del_modello"](self.FintoTokenizer())
        testo = ns["turni_a_testo"]([{"from": "human", "value": "Ciao"},
                                     {"from": "gpt", "value": "Ciao a te"}])
        assert testo == "<|user|>Ciao<|assistant|>Ciao a te"

    def test_un_template_che_esplode_non_ferma_il_training(self):
        """Meglio addestrare sullo schema testuale che non addestrare."""
        ns = self._pezzi()

        class Rotto:
            chat_template = "{{ rotto"

            def apply_chat_template(self, messaggi, tokenize=False):
                raise ValueError("template non valido")

        ns["usa_template_del_modello"](Rotto())
        testo = ns["coppia_a_testo"]("Domanda", "Risposta")
        assert "### Istruzione:" in testo

    @pytest.mark.parametrize("method", ["lora_unsloth", "trl_sft"])
    def test_il_tokenizer_viene_registrato_prima_del_dataset(self, method):
        """Registrarlo dopo significherebbe formattare gli esempi senza sapere
        che formato usa il modello."""
        from core.training.jobs import _build_script_values

        values = _build_script_values(
            {"base_model": "gpt2", "method": method, "dataset_id": "x/y",
             "hyperparams": {}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES[method], values)
        assert (source.index("usa_template_del_modello(tokenizer)")
                < source.index("train_dataset, eval_dataset = load_train_and_eval()"))


class TestComposizioneDataset:
    """Di cosa parla un dataset, prima di addestrarci sopra.

    Il ciclo assume che il dataset scelto copra la competenza che vuole
    migliorare. Quando l'assunzione e' sbagliata se ne accorge dopo un round
    intero — misurato su OpenOrca, che il ciclo usa per il ragionamento (26%,
    giusto) ma che di matematica ne ha l'1%.
    """

    def _funzione(self):
        from core.training.jobs import _build_script_values

        values = _build_script_values(
            {"base_model": "gpt2", "method": "trl_sft", "dataset_id": "x/y",
             "hyperparams": {}}, "tj", Path("unused"))
        source = _render(SCRIPT_TEMPLATES["trl_sft"], values)
        albero = ast.parse(source)
        ns = {"INDIZI_DOMINIO": next(
            ast.literal_eval(n.value) for n in albero.body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "INDIZI_DOMINIO")}
        nodo = next(n for n in albero.body if isinstance(n, ast.FunctionDef)
                    and n.name == "composizione_del_dataset")
        exec(ast.get_source_segment(source, nodo), ns)
        return ns["composizione_del_dataset"]

    def test_riconosce_la_matematica(self):
        composizione = self._funzione()
        righe = composizione(["Calcola l'integral di x^2", "solve for x nell'equazione"])
        assert "matematica" in righe[0]

    def test_riconosce_il_codice(self):
        composizione = self._funzione()
        righe = composizione(["def somma(a, b):\n    return a + b", "import os"])
        assert "codice 100%" in righe[0]

    def test_un_esempio_puo_contare_in_piu_domini(self):
        """Un problema di matematica spiegato passo per passo e' matematica *e*
        ragionamento: fingere che sia una cosa sola darebbe percentuali piu'
        pulite e piu' false."""
        composizione = self._funzione()
        righe = composizione(["Calcola l'integral, therefore il risultato e' due"])
        assert "matematica" in righe[0] and "ragionamento" in righe[0]

    def test_un_dataset_irriconoscibile_lo_dice(self):
        composizione = self._funzione()
        righe = composizione(["Il gatto dorme sul divano.", "Domani piove."])
        assert "nessun dominio riconosciuto" in righe[0]

    def test_le_percentuali_stanno_sul_campione(self):
        composizione = self._funzione()
        righe = composizione(["def f(): pass"] + ["testo neutro"] * 3)
        assert "codice 25%" in righe[0]


class TestNormalizzazioneDellaPerdita:
    """Dalla 4.46 il Trainer smette di dividere la loss per l'accumulo se il
    forward del modello ha un `**kwargs`, dando per scontato che dentro ci
    finisca `num_items_in_batch` e che il modello lo usi. Un'architettura
    scritta a mano quel parametro lo ingoia, e allora non normalizza nessuno
    dei due: loss e gradienti escono moltiplicati per l'accumulo.

    Misurato su Ailo340m-v4 con accumulo 16: loss riportata 63,5 al primo
    passo dove quella vera era 3,97 — sopra il tetto del caso puro (10,8),
    quindi indistinguibile da un modello che non impara affatto.
    """

    def _sonda(self):
        from core.training.jobs import _ARCH_SHIM
        inizio = _ARCH_SHIM.index("def normalizza_la_perdita")
        detto = []
        ns = {"sigma": lambda m: detto.append(m)}
        exec(compile(_ARCH_SHIM[inizio:], "shim", "exec"), ns)
        return ns["normalizza_la_perdita"], detto

    def _finto_trainer(self, model, accumulo=16):
        import types

        class FintoTrainer:
            def __init__(self):
                self.model = model
                self.model_accepts_loss_kwargs = True
                self.args = types.SimpleNamespace(
                    gradient_accumulation_steps=accumulo)
        return FintoTrainer()

    def _modello(self, onora):
        """Un modello minimo che onora o ignora `num_items_in_batch`."""
        import types
        import torch.nn as nn
        import torch.nn.functional as F

        class Modellino(nn.Module):
            def __init__(self):
                super().__init__()
                self.emb = nn.Embedding(16, 8)
                self.testa = nn.Linear(8, 16)

            def forward(self, input_ids, labels=None, **kwargs):
                logits = self.testa(self.emb(input_ids))
                perdita = F.cross_entropy(
                    logits.view(-1, 16), labels.view(-1),
                    reduction="sum" if onora else "mean")
                if onora:
                    perdita = perdita / kwargs["num_items_in_batch"]
                return types.SimpleNamespace(loss=perdita)

        return Modellino()

    def test_chi_ignora_il_conteggio_viene_normalizzato_dal_trainer(self):
        normalizza, detto = self._sonda()
        trainer = self._finto_trainer(self._modello(onora=False))
        assert normalizza(trainer) is False
        assert trainer.model_accepts_loss_kwargs is False, \
            "senza questo la loss riportata resta moltiplicata per l'accumulo"
        assert any("16x" in m for m in detto), \
            "il log deve dire di quanto sarebbe stato l'errore"

    def test_chi_lo_onora_resta_intoccato(self):
        """I modelli di transformers normalizzano sul conteggio dei token, che
        e' piu' preciso della divisione per l'accumulo: togliergliela sarebbe
        un peggioramento."""
        normalizza, detto = self._sonda()
        trainer = self._finto_trainer(self._modello(onora=True))
        assert normalizza(trainer) is True
        assert trainer.model_accepts_loss_kwargs is True
        assert detto == []

    def test_il_dropout_non_viene_scambiato_per_normalizzazione(self):
        """La sonda confronta due chiamate: con il dropout acceso darebbero
        numeri diversi anche a un modello che il conteggio lo ignora, e la
        sonda leggerebbe rumore come se fosse la normalizzazione giusta."""
        import torch.nn as nn
        normalizza, _ = self._sonda()
        modello = self._modello(onora=False)
        modello.buco = nn.Dropout(0.9)
        originale = modello.forward

        def con_dropout(input_ids, labels=None, **kwargs):
            fuori = originale(input_ids, labels=labels, **kwargs)
            rumore = modello.buco(fuori.loss.new_ones(64)).sum()
            fuori.loss = fuori.loss + rumore
            return fuori

        modello.forward = con_dropout
        modello.train()
        trainer = self._finto_trainer(modello)
        assert normalizza(trainer) is False, \
            "la sonda deve misurare in eval, altrimenti legge il dropout"
        assert modello.training, "lo stato del modello va restituito com'era"

    def test_un_forward_che_rifiuta_il_parametro_non_ferma_il_job(self):
        """Meglio la normalizzazione prudente di un'eccezione a meta' avvio."""
        import torch.nn as nn
        normalizza, detto = self._sonda()

        class Rigido(nn.Module):
            def __init__(self):
                super().__init__()
                self.p = nn.Linear(2, 2)

            def forward(self, input_ids, labels=None):
                raise TypeError("num_items_in_batch non previsto")

        trainer = self._finto_trainer(Rigido())
        assert normalizza(trainer) is False
        assert trainer.model_accepts_loss_kwargs is False
        assert any("prudente" in m for m in detto)

    def test_e_agganciata_prima_di_ogni_training(self):
        """Una sonda che nessuno chiama non corregge niente."""
        from core.training.jobs import SCRIPT_TEMPLATES
        for nome in ("lora_unsloth", "trl_sft"):
            corpo = SCRIPT_TEMPLATES[nome]
            assert "normalizza_la_perdita(trainer)" in corpo, nome
            assert (corpo.index("normalizza_la_perdita(trainer)")
                    < corpo.index("trainer.train(")), \
                nome + ": la sonda deve girare prima del training"


class TestAddestramentoCompleto:
    """Sotto il miliardo di parametri LoRA e' una gabbia senza il vantaggio che
    la giustifica: il modello e' poco addestrato e i pesi vanno mossi davvero.
    `lora_r = 0` significa niente LoRA."""

    def _sorgente(self, lora_r, learning_rate=2e-4):
        from core.training.jobs import _build_script_values, SCRIPT_TEMPLATES
        values = _build_script_values(
            {"base_model": "org/piccolo", "method": "trl_sft", "dataset_id": "x/y",
             "hyperparams": {"lora_r": lora_r, "learning_rate": learning_rate}},
            "tj", Path("unused"))
        return _render(SCRIPT_TEMPLATES["trl_sft"], values)

    def test_rank_zero_sceglie_i_pesi_veri(self):
        sorgente = self._sorgente(0)
        assert "ADDESTRAMENTO_COMPLETO = int(0) <= 0" in sorgente
        albero = ast.parse(sorgente)
        assert albero is not None, "il sorgente reso deve restare valido"

    def test_rank_positivo_resta_lora(self):
        sorgente = self._sorgente(16)
        assert "ADDESTRAMENTO_COMPLETO = int(16) <= 0" in sorgente
        assert "get_peft_model" in sorgente

    def test_il_passo_di_lora_viene_abbassato_sui_pesi_veri(self):
        """2e-4 e' corretto per una matrice che parte da zero ed e' distruttivo
        su pesi gia' addestrati. Il tetto e' dichiarato nel log."""
        sorgente = self._sorgente(0)
        assert "TETTO = 5e-5" in sorgente
        assert "PASSO = TETTO" in sorgente
        assert "learning_rate=PASSO" in sorgente

    def test_un_passo_gia_prudente_non_viene_toccato(self):
        sorgente = self._sorgente(0, learning_rate=1e-5)
        assert "PASSO = float(1e-05)" in sorgente

    def test_il_modello_intero_non_finisce_in_lora_model(self):
        """L'export cerca `model/` come sorgente autonoma e `lora_model/` come
        adapter da fondere: sbagliare cartella manderebbe a Ollama un modello
        intero spacciato per adapter."""
        sorgente = self._sorgente(0)
        assert 'ADDESTRAMENTO_COMPLETO else "/lora_model"' in sorgente
        assert '"/model" if ADDESTRAMENTO_COMPLETO' in sorgente

    def test_le_proiezioni_lora_sono_dedotte_anche_qui(self):
        """`trl_sft` aveva i nomi canonici scritti a mano: su un'architettura
        che chiama le sue proiezioni `out_proj`/`w1`/`w2` PEFT non trovava
        nessun bersaglio e il run girava senza imparare niente."""
        assert "proiezioni_lora(model," in self._sorgente(16)


class TestGuardiaRankZero:
    """`lora_r = 0` vuol dire "addestra i pesi", e solo `trl_sft` lo sa fare.
    Chiederlo su Unsloth passerebbe rank 0 a PEFT — un adapter di dimensione
    nulla — e il run arriverebbe in fondo senza aver aggiornato niente."""

    def test_rank_zero_sposta_il_metodo(self):
        from core.training.jobs import metodo_effettivo
        assert metodo_effettivo("lora_unsloth", {"lora_r": 0}) == "trl_sft"

    def test_rank_normale_resta_dov_era(self):
        from core.training.jobs import metodo_effettivo
        assert metodo_effettivo("lora_unsloth", {"lora_r": 16}) == "lora_unsloth"
        assert metodo_effettivo("lora_unsloth", {}) == "lora_unsloth"

    def test_gli_altri_metodi_non_si_toccano(self):
        from core.training.jobs import metodo_effettivo
        for metodo in ("full_pretrain", "slm_forge", "script_custom", "trl_sft"):
            assert metodo_effettivo(metodo, {"lora_r": 0}) == metodo

    def test_un_rank_illeggibile_non_fa_esplodere_la_creazione(self):
        from core.training.jobs import metodo_effettivo
        assert metodo_effettivo("lora_unsloth", {"lora_r": "boh"}) == "lora_unsloth"
        assert metodo_effettivo("lora_unsloth", {"lora_r": None}) == "lora_unsloth"

    def test_il_job_creato_riceve_davvero_lo_script_giusto(self):
        """Il guardrail deve valere anche per chi crea job dalle API o
        dall'autopilota, che l'interfaccia non la attraversano."""
        from core.training.jobs import _build_script_values, SCRIPT_TEMPLATES
        values = _build_script_values(
            {"base_model": "org/piccolo", "method": "lora_unsloth", "dataset_id": "x/y",
             "hyperparams": {"lora_r": 0}}, "tj", Path("unused"))
        assert values["method_label"] == "SFT (TRL + PEFT)"
