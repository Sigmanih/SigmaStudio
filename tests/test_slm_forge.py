# ==============================================================================
# tests/test_slm_forge.py — Forgia di SLM: architetture, GGUF, chat sui checkpoint
# ==============================================================================
"""Copre core/training/forge.py, gguf_export.py, forge_train.py e
checkpoint_chat.py. I test che richiedono la rete o una GPU vengono saltati.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.training_handler as th
from core.training import forge as forge_mod
from core.training import checkpoint_chat as chat_mod
from core.training.gguf_export import permute_rope, _bpe_merges

torch = pytest.importorskip("torch")


@pytest.fixture(autouse=True)
def isolate_training_dirs(tmp_path):
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


# =========================================================== architetture

class TestArchitectures:

    def test_presets_are_ordered_and_coherent(self):
        archs = forge_mod.ARCHITECTURES
        assert [a["params_m"] for a in archs] == sorted(a["params_m"] for a in archs)
        for a in archs:
            assert a["hidden_size"] % a["num_attention_heads"] == 0, \
                f"{a['id']}: hidden non divisibile per le teste"
            assert a["num_attention_heads"] % a["num_key_value_heads"] == 0, \
                f"{a['id']}: GQA non valida"
            assert a["vram_gb"] > 0 and a["tokens_suggested_m"] > 0

    def test_defaults_pick_an_architecture_that_fits(self, monkeypatch):
        def report_with(vram):
            return {"backend": "cuda", "trainable_gpus": [{"name": "GPU", "vram_total_gb": vram}],
                    "capabilities": {"max_vram_gb": vram, "arch": "Test"}}

        monkeypatch.setattr(forge_mod.gpu_layer, "get_accelerator_report",
                            lambda *a, **k: report_with(4.0))
        small_rig = forge_mod.forge_defaults()
        monkeypatch.setattr(forge_mod.gpu_layer, "get_accelerator_report",
                            lambda *a, **k: report_with(24.0))
        big_rig = forge_mod.forge_defaults()

        chosen_small = next(a for a in forge_mod.ARCHITECTURES if a["id"] == small_rig["architecture"])
        chosen_big = next(a for a in forge_mod.ARCHITECTURES if a["id"] == big_rig["architecture"])
        assert chosen_small["vram_gb"] <= 4.0
        assert chosen_big["params_m"] > chosen_small["params_m"]

    def test_distillation_warns_about_the_tokenizer(self, monkeypatch):
        monkeypatch.setattr(forge_mod.gpu_layer, "get_accelerator_report",
                            lambda *a, **k: {"backend": "cuda",
                                             "trainable_gpus": [{"name": "A", "vram_total_gb": 16}],
                                             "capabilities": {"max_vram_gb": 16, "arch": "T"}})
        defaults = forge_mod.forge_defaults(mode="both")
        assert any("tokenizer" in n.lower() for n in defaults["notes"])

    def test_second_gpu_is_offered_for_the_teacher(self, monkeypatch):
        monkeypatch.setattr(forge_mod.gpu_layer, "get_accelerator_report",
                            lambda *a, **k: {"backend": "cuda", "trainable_gpus": [
                                {"name": "A", "vram_total_gb": 16}, {"name": "B", "vram_total_gb": 8}],
                                "capabilities": {"max_vram_gb": 16, "arch": "T"}})
        defaults = forge_mod.forge_defaults(mode="distill")
        assert defaults["teacher_device"] == "cuda:1"


class TestTeacherAccess:
    """I modelli migliori per l'italiano sono ad accesso riservato: va detto
    prima del run, non dopo il download del corpus."""

    def test_gated_teachers_are_flagged_in_the_curated_list(self):
        minerva = [t for t in forge_mod.TEACHER_MODELS if "Minerva" in t["id"]]
        assert minerva, "i Minerva restano proposti, sono i migliori per l'italiano"
        assert all(t["gated"] for t in minerva), "vanno marcati come riservati"
        assert any(not t["gated"] for t in forge_mod.TEACHER_MODELS), \
            "serve almeno un insegnante sempre accessibile"

    def test_gated_repo_gives_an_actionable_message(self, monkeypatch):
        def raise_gated(*args, **kwargs):
            raise Exception("403 Client Error. Cannot access gated repo for url ...")

        monkeypatch.setattr(forge_mod, "_hf_get", raise_gated)
        result = forge_mod.model_accessible("sapienzanlp/Minerva-350M-base-v1.0")
        assert result["accessible"] is False
        assert result["gated"] is True
        assert "termini" in result["error"]
        assert result["url"].endswith("Minerva-350M-base-v1.0")

    def test_open_model_is_reported_accessible(self, monkeypatch):
        monkeypatch.setattr(forge_mod, "_hf_get",
                            lambda *a, **k: {"id": "Qwen/Qwen2.5-0.5B-Instruct",
                                             "gated": False, "downloads": 5_000_000})
        result = forge_mod.model_accessible("Qwen/Qwen2.5-0.5B-Instruct")
        assert result["accessible"] is True and result["error"] is None

    def test_gated_flag_survives_the_string_form(self, monkeypatch):
        """L'hub restituisce 'auto'/'manual', non solo booleani."""
        monkeypatch.setattr(forge_mod, "_hf_get",
                            lambda *a, **k: {"id": "x/y", "gated": "auto"})
        assert forge_mod.model_accessible("x/y")["gated"] is True

    def test_teacher_search_marks_gated_models(self, monkeypatch):
        monkeypatch.setattr(forge_mod, "_hf_get", lambda *a, **k: [
            {"id": "libero/modello", "gated": False, "downloads": 100},
            {"id": "riservato/modello", "gated": "auto", "downloads": 50},
        ])
        found = forge_mod.search_teacher_models("italiano")
        assert found["success"]
        flags = {m["id"]: m["gated"] for m in found["models"]}
        assert flags == {"libero/modello": False, "riservato/modello": True}

    def test_search_failure_falls_back_to_the_curated_list(self, monkeypatch):
        def boom(*args, **kwargs):
            raise Exception("rete assente")

        monkeypatch.setattr(forge_mod, "_hf_get", boom)
        found = forge_mod.search_teacher_models()
        assert found["success"] is False
        assert found["featured"], "senza rete restano gli insegnanti curati"

    def test_loader_rewrites_the_gated_traceback(self, monkeypatch):
        """Il traceback originale seppellisce l'unica informazione utile."""
        from core.training import forge_train
        import transformers

        def raise_gated(*args, **kwargs):
            raise OSError("You are trying to access a gated repo. 403 Client Error.")

        monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", raise_gated)
        with pytest.raises(RuntimeError) as err:
            forge_train.load_teacher("sapienzanlp/Minerva-1B-base-v1.0", "cpu", torch.float32)
        message = str(err.value)
        assert "accesso riservato" in message
        assert "huggingface.co/sapienzanlp/Minerva-1B-base-v1.0" in message
        assert "Qwen" in message, "va indicata un'alternativa libera"


class TestEstimate:

    def test_more_steps_means_more_tokens_and_time(self):
        short = forge_mod.estimate_run("micro", 512, 8, 100, "dataset")
        long = forge_mod.estimate_run("micro", 512, 8, 1000, "dataset")
        assert long["tokens_total"] == 10 * short["tokens_total"]
        assert long["hours"] > short["hours"]

    def test_distillation_is_slower_than_plain_training(self):
        plain = forge_mod.estimate_run("micro", 512, 8, 1000, "dataset")
        distilled = forge_mod.estimate_run("micro", 512, 8, 1000, "both")
        assert distilled["hours"] > plain["hours"], "il forward dell'insegnante deve pesare"

    def test_undertrained_runs_are_flagged(self):
        tiny = forge_mod.estimate_run("base", 512, 1, 10, "dataset")
        assert tiny["note"], "un run cortissimo deve essere segnalato come acerbo"


# =========================================================== GGUF

class TestGgufConversion:

    def test_permutation_is_reversible(self):
        """La permutazione riordina, non altera: applicarla due volte torna all'origine."""
        weight = torch.arange(8 * 4, dtype=torch.float32).reshape(8, 4).numpy()
        once = permute_rope(weight, n_head=2)
        twice = permute_rope(once, n_head=2)
        assert (twice == weight).all()
        assert not (once == weight).all(), "la permutazione deve cambiare qualcosa"

    def test_permutation_preserves_shape_and_values(self):
        weight = torch.randn(16, 8).numpy()
        out = permute_rope(weight, n_head=4)
        assert out.shape == weight.shape
        assert sorted(out.flatten().tolist()) == pytest.approx(sorted(weight.flatten().tolist()))

    def test_grouped_query_uses_the_kv_head_count(self):
        """Con GQA, K ha meno teste di Q: usare n_head sbaglierebbe il raggruppamento."""
        weight = torch.randn(16, 4).numpy()
        as_q = permute_rope(weight, n_head=8)
        as_k = permute_rope(weight, n_head=8, n_head_kv=4)
        assert not (as_q == as_k).all()

    def test_impossible_shape_gives_a_clear_error(self):
        """Meglio un messaggio esplicito che un ValueError di reshape."""
        weight = torch.randn(8, 4).numpy()
        with pytest.raises(ValueError, match="teste"):
            permute_rope(weight, n_head=8)

    def test_merges_parsed_from_both_formats(self, tmp_path):
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "tokenizer.json").write_text(
            json.dumps({"model": {"merges": ["a b", "c d"]}}), encoding="utf-8")
        assert _bpe_merges(legacy) == ["a b", "c d"]

        modern = tmp_path / "modern"
        modern.mkdir()
        (modern / "tokenizer.json").write_text(
            json.dumps({"model": {"merges": [["a", "b"], ["c", "d"]]}}), encoding="utf-8")
        assert _bpe_merges(modern) == ["a b", "c d"]

    def test_missing_tokenizer_file_is_not_fatal(self, tmp_path):
        assert _bpe_merges(tmp_path) == []

    def test_only_writable_quantizations_are_offered(self):
        """Q4_K/Q6_K sono di sola lettura in Python: offrirli darebbe file F32
        etichettati come quantizzati, cioè più grandi dell'F16."""
        import gguf
        from core.training.gguf_export import QUANT_TYPES

        for name in QUANT_TYPES.values():
            if name in ("F32", "F16"):
                continue
            quant_type = getattr(gguf.GGMLQuantizationType, name)
            sample = torch.zeros((32, 64), dtype=torch.float32).numpy()
            gguf.quants.quantize(sample, quant_type)   # deve non sollevare

    def test_quantization_actually_shrinks_the_file(self, tmp_path):
        """Il bug era proprio questo: il Q8_0 usciva più grande dell'F16."""
        from transformers import LlamaConfig, LlamaForCausalLM, AutoTokenizer
        from core.training.gguf_export import export_gguf

        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        tokenizer.pad_token = tokenizer.eos_token
        model_dir = tmp_path / "model"
        torch.manual_seed(0)
        LlamaForCausalLM(LlamaConfig(
            vocab_size=len(tokenizer), hidden_size=64, num_hidden_layers=2,
            num_attention_heads=4, num_key_value_heads=2, intermediate_size=128,
            max_position_embeddings=128, tie_word_embeddings=False,
        )).save_pretrained(model_dir, safe_serialization=True)
        tokenizer.save_pretrained(model_dir)

        sizes = {}
        for quant in ("f16", "q8_0", "q4_0"):
            result = export_gguf(model_dir, tmp_path / f"m.{quant}.gguf", quant)
            assert result["success"], result.get("error")
            sizes[quant] = result["size_mb"]
            if quant != "f16":
                assert result["quantized_tensors"] > 0, f"{quant} non ha quantizzato nulla"

        assert sizes["q8_0"] < sizes["f16"], "Q8_0 deve pesare meno dell'F16"
        assert sizes["q4_0"] < sizes["q8_0"], "Q4_0 deve pesare meno del Q8_0"


# =========================================================== distillazione

class TestDistillationLoss:

    def test_identical_distributions_give_zero_loss(self):
        from core.training.forge_train import distillation_loss

        logits = torch.randn(2, 5, 32)
        loss = distillation_loss(logits, logits.clone(), temperature=2.0)
        assert loss.item() == pytest.approx(0.0, abs=1e-5)

    def test_divergent_distributions_give_positive_loss(self):
        from core.training.forge_train import distillation_loss

        torch.manual_seed(0)
        student = torch.randn(2, 5, 32)
        teacher = torch.randn(2, 5, 32) * 3
        assert distillation_loss(student, teacher, 2.0).item() > 0

    def test_temperature_scaling_keeps_gradients_comparable(self):
        """Il fattore T² esiste per non far sparire il gradiente ad alta temperatura."""
        from core.training.forge_train import distillation_loss

        torch.manual_seed(1)
        student = torch.randn(1, 4, 16, requires_grad=True)
        teacher = torch.randn(1, 4, 16) * 2

        grads = {}
        for temperature in (1.0, 4.0):
            if student.grad is not None:
                student.grad = None
            distillation_loss(student, teacher, temperature).backward(retain_graph=True)
            grads[temperature] = student.grad.abs().mean().item()

        assert grads[4.0] > grads[1.0] * 0.05, \
            "senza il fattore T^2 il gradiente collasserebbe ad alta temperatura"


# =========================================================== chat checkpoint

class TestMultiGpuStudent:
    """Il training usa tutte le schede, con il batch diviso per capacità."""

    @staticmethod
    def _student(devices, weights):
        from core.training.forge_train import MultiGpuStudent

        student = MultiGpuStudent.__new__(MultiGpuStudent)   # niente GPU nei test
        student.devices = devices
        student.weights = weights
        return student

    def test_batch_split_follows_the_weights(self):
        student = self._student(["cuda:0", "cuda:1"], [0.7, 0.3])
        chunks = student.split(torch.zeros(20, 8))
        assert [c.shape[0] for c in chunks] == [14, 6]

    def test_split_covers_the_whole_batch(self):
        for weights in ([0.5, 0.5], [0.68, 0.32], [0.9, 0.1], [0.4, 0.35, 0.25]):
            student = self._student([f"cuda:{i}" for i in range(len(weights))], weights)
            chunks = student.split(torch.zeros(31, 4))
            assert sum(c.shape[0] for c in chunks if c is not None) == 31

    def test_uneven_gpus_get_uneven_work(self):
        """Una divisione a metà sarebbe limitata dalla scheda più lenta."""
        student = self._student(["cuda:0", "cuda:1"], [0.68, 0.32])
        chunks = student.split(torch.zeros(100, 4))
        assert chunks[0].shape[0] > chunks[1].shape[0] * 1.8

    def test_tiny_batch_still_reaches_every_device(self):
        student = self._student(["cuda:0", "cuda:1"], [0.7, 0.3])
        chunks = student.split(torch.zeros(2, 4))
        assert sum(c.shape[0] for c in chunks if c is not None) == 2

    def test_memory_plan_counts_the_optimizer_state(self, monkeypatch):
        """AdamW tiene due momenti per parametro: dimenticarli fa passare per
        fattibile un batch che poi va in OOM al secondo step."""
        from core.training import forge_train

        import torch as real_torch
        monkeypatch.setattr(real_torch.cuda, "mem_get_info",
                            lambda device: (12 * 1024 ** 3, 16 * 1024 ** 3))

        params = 500_000_000
        usable, _weights, max_batch = forge_train.plan_devices(
            ["cuda:0"], params, teacher_params=0, seq_len=512,
            vocab_size=32000, distilling=False)
        # pesi+grad+Adam = 16 B/par = 8 GB su 12 liberi: resta poco per i logit
        assert usable == ["cuda:0"]
        assert max_batch < 100, "senza lo stato di Adam la stima sarebbe troppo generosa"

    def test_oversized_model_is_excluded_not_crashed(self, monkeypatch):
        import torch as real_torch
        from core.training import forge_train

        monkeypatch.setattr(real_torch.cuda, "mem_get_info",
                            lambda device: (2 * 1024 ** 3, 8 * 1024 ** 3))
        usable, _w, _b = forge_train.plan_devices(
            ["cuda:0"], 600_000_000, teacher_params=500_000_000,
            seq_len=512, vocab_size=151936, distilling=True)
        assert usable == [], "una GPU che non regge la replica va esclusa"

    def test_distillation_reserves_more_memory_per_sequence(self, monkeypatch):
        """Con la KL coesistono molte più copie dei logit che con la sola CE."""
        import torch as real_torch
        from core.training import forge_train

        monkeypatch.setattr(real_torch.cuda, "mem_get_info",
                            lambda device: (10 * 1024 ** 3, 16 * 1024 ** 3))
        _u, _w, plain = forge_train.plan_devices(
            ["cuda:0"], 50_000_000, 0, 512, 32000, distilling=False)
        _u, _w, distilled = forge_train.plan_devices(
            ["cuda:0"], 50_000_000, 0, 512, 32000, distilling=True)
        assert distilled < plain

    def test_forge_config_targets_every_trainable_gpu(self, monkeypatch):
        from core.training import jobs as jobs_mod

        monkeypatch.setattr(jobs_mod.gpu_layer, "get_accelerator_report", lambda *a, **k: {
            "trainable_gpus": [{"index": 0, "device_str": "cuda:0"},
                               {"index": 1, "device_str": "cuda:1"}]})
        assert jobs_mod._forge_config({})["devices"] == ["cuda:0", "cuda:1"]

    def test_forge_job_makes_every_gpu_visible(self, monkeypatch):
        """Senza allargare CUDA_VISIBLE_DEVICES il processo vedrebbe una sola scheda."""
        from core.training.jobs import create_training_job, delete_job
        from core.training import jobs as jobs_mod

        monkeypatch.setattr(jobs_mod.gpu_layer, "get_accelerator_report", lambda *a, **k: {
            "trainable_gpus": [{"index": 0, "device_str": "cuda:0"},
                               {"index": 1, "device_str": "cuda:1"}]})
        result = create_training_job({
            "base_model": "from_scratch", "method": "slm_forge", "dataset_id": "",
            "hyperparams": {"forge_architecture": "nano"},
        })
        try:
            assert result["job"]["visible_gpu_indices"] == [0, 1]
        finally:
            delete_job(result["job_id"])


class TestCheckpointChat:

    def test_chat_runs_on_cpu_by_default(self):
        """Il training è il carico da ottimizzare: la prova non tocca le GPU."""
        assert chat_mod.pick_inference_device() == "cpu"
        assert chat_mod.pick_inference_device(training_indices=[0, 1]) == "cpu"

    def test_training_gpu_is_never_used_for_inference(self, monkeypatch):
        monkeypatch.setattr(chat_mod.gpu_layer, "get_accelerator_report", lambda *a, **k: {
            "trainable_gpus": [
                {"index": 0, "device_str": "cuda:0", "vram_used_mb": 12000},
                {"index": 1, "device_str": "cuda:1", "vram_used_mb": 100},
            ]})
        assert chat_mod.pick_inference_device(training_indices=[0], prefer="gpu") == "cuda:1"

    def test_falls_back_to_cpu_when_every_gpu_trains(self, monkeypatch):
        monkeypatch.setattr(chat_mod.gpu_layer, "get_accelerator_report", lambda *a, **k: {
            "trainable_gpus": [{"index": 0, "device_str": "cuda:0", "vram_used_mb": 12000}]})
        assert chat_mod.pick_inference_device(training_indices=[0], prefer="gpu") == "cpu"

    def test_prefers_the_emptiest_free_gpu(self, monkeypatch):
        monkeypatch.setattr(chat_mod.gpu_layer, "get_accelerator_report", lambda *a, **k: {
            "trainable_gpus": [
                {"index": 0, "device_str": "cuda:0", "vram_used_mb": 5000},
                {"index": 1, "device_str": "cuda:1", "vram_used_mb": 50},
            ]})
        assert chat_mod.pick_inference_device(prefer="gpu") == "cuda:1"

    def test_no_gpu_means_cpu(self, monkeypatch):
        monkeypatch.setattr(chat_mod.gpu_layer, "get_accelerator_report",
                            lambda *a, **k: {"trainable_gpus": []})
        assert chat_mod.pick_inference_device(prefer="gpu") == "cpu"

    def test_checkpoints_are_listed_newest_first(self, tmp_path, monkeypatch):
        import time

        monkeypatch.setattr(chat_mod, "JOBS_DIR", tmp_path)
        base = tmp_path / "job1" / "output" / "checkpoints"
        for step in (10, 20):
            path = base / f"step-{step}"
            path.mkdir(parents=True)
            (path / "config.json").write_text("{}", encoding="utf-8")
            (path / "sigma_step.json").write_text(json.dumps({"step": step}), encoding="utf-8")
            time.sleep(0.02)

        listed = chat_mod.list_checkpoints("job1")["checkpoints"]
        assert [c["step"] for c in listed] == [20, 10]

    def test_empty_prompt_is_refused(self):
        assert chat_mod.chat(job_id="x", prompt="  ")["success"] is False

    def test_missing_checkpoint_gives_a_clear_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(chat_mod, "JOBS_DIR", tmp_path)
        answer = chat_mod.chat(job_id="inesistente", prompt="ciao")
        assert answer["success"] is False
        assert "checkpoint" in answer["error"].lower()


# =========================================================== job forge

class TestForgeJob:

    def test_distillation_forces_the_teacher_tokenizer(self):
        """Vincolo non negoziabile: i logit servono sullo stesso vocabolario."""
        from core.training.jobs import _forge_config

        config = _forge_config({"forge_mode": "both", "forge_tokenizer_mode": "train"})
        assert config["tokenizer_mode"] == "teacher"

        plain = _forge_config({"forge_mode": "dataset", "forge_tokenizer_mode": "train"})
        assert plain["tokenizer_mode"] == "train"

    def test_script_is_valid_python_and_carries_the_config(self):
        import ast
        from core.training.jobs import create_training_job, delete_job

        result = create_training_job({
            "base_model": "from_scratch", "method": "slm_forge", "dataset_id": "",
            "output_name": "slm_test",
            "hyperparams": {"forge_architecture": "nano", "forge_mode": "distill",
                            "forge_max_steps": 50, "forge_export_formats": ["gguf_q8"]},
        })
        try:
            source = Path(result["job"]["script_path"]).read_text(encoding="utf-8")
            ast.parse(source)
            assert "run_forge" in source and "run_exports" in source
            assert "{forge_json}" not in source
        finally:
            delete_job(result["job_id"])

    def test_defaults_used_when_nothing_is_specified(self):
        from core.training.jobs import _forge_config

        config = _forge_config({})
        assert config["sources"], "deve esserci almeno un corpus di partenza"
        assert config["architecture"]["id"] in {a["id"] for a in forge_mod.ARCHITECTURES}
        assert config["export_formats"]
