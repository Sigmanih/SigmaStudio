"""
==============================================================================
tests/test_training_handler.py — Test Suite per Training Lab Sigma Studio v7.0
==============================================================================
Verifica completa del ciclo di training: dataset, job, esecuzione, export, hardware.
"""

import os
import sys
import json
import shutil
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import core.training_handler as th

from core.training_handler import (
    # Dataset
    get_featured_datasets, search_hf_datasets, get_hf_dataset_info,
    import_local_dataset, register_hf_dataset, list_datasets, delete_dataset,
    # Jobs
    create_training_job, start_training_job, stop_training_job,
    get_job_status, get_job_logs, list_jobs, delete_job,
    # Export
    export_to_ollama,
    # Hardware
    get_hardware_info,
    # Helpers
    FEATURED_DATASETS, SCRIPT_TEMPLATES, _load_jobs, _save_jobs,
    check_training_dependencies,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(autouse=True)
def isolate_training_dirs(tmp_path):
    """Isola file system del training in directory temporanea."""
    # Salva riferimenti originali
    orig_training_dir = th.TRAINING_DIR
    orig_datasets_dir = th.DATASETS_DIR
    orig_jobs_dir = th.JOBS_DIR
    orig_jobs_file = th.JOBS_FILE
    orig_scripts_dir = th.SCRIPTS_DIR

    # Patchiamo i percorsi con tmp_path
    th.TRAINING_DIR = tmp_path / "training"
    th.DATASETS_DIR = tmp_path / "training" / "datasets"
    th.JOBS_DIR = tmp_path / "training" / "jobs"
    th.JOBS_FILE = tmp_path / "training" / "training_jobs.json"
    th.SCRIPTS_DIR = tmp_path / "training" / "scripts"
    for d in [th.TRAINING_DIR, th.DATASETS_DIR, th.JOBS_DIR, th.SCRIPTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    yield
    # Ripristina originali
    th.TRAINING_DIR = orig_training_dir
    th.DATASETS_DIR = orig_datasets_dir
    th.JOBS_DIR = orig_jobs_dir
    th.JOBS_FILE = orig_jobs_file
    th.SCRIPTS_DIR = orig_scripts_dir


# ===========================================================================
# 1. TEST DATASET FEATURED
# ===========================================================================

class TestFeaturedDatasets:
    """Validazione dei dataset curati pre-caricati."""

    def test_featured_datasets_structure(self):
        """Verifica che tutti i dataset featured abbiano i campi obbligatori."""
        required_fields = {"id", "name", "author", "category", "category_label",
                          "description", "difficulty", "vram_min_gb", "recommended_method"}
        for ds in FEATURED_DATASETS:
            for field in required_fields:
                assert field in ds, f"Manca {field} in {ds.get('id', 'unknown')}"
            assert ds["difficulty"] in ("beginner", "intermediate", "advanced"), \
                f"Difficoltà non valida per {ds['id']}: {ds['difficulty']}"
            assert ds["vram_min_gb"] > 0, f"VRAM non valida per {ds['id']}"

    def test_featured_datasets_categories(self):
        """Verifica raggruppamento per categorie."""
        result = get_featured_datasets()
        assert result["success"] is True
        assert len(result["categories"]) > 0
        all_datasets = []
        for cat in result["categories"]:
            assert "id" in cat
            assert "label" in cat
            assert "datasets" in cat
            assert len(cat["datasets"]) > 0
            all_datasets.extend(cat["datasets"])
        assert len(all_datasets) == len(FEATURED_DATASETS)

    def test_featured_method_badge_valid(self):
        """Verifica che i metodi raccomandati siano tra i template disponibili."""
        valid_methods = set(SCRIPT_TEMPLATES.keys())
        for ds in FEATURED_DATASETS:
            assert ds["recommended_method"] in valid_methods, \
                f"Metodo {ds['recommended_method']} non ha template in {ds['id']}"


# ===========================================================================
# 2. TEST RICERCA HUGGINGFACE
# ===========================================================================

class TestHuggingFaceSearch:
    """Test ricerca dataset su HuggingFace (con mock per evitare chiamate reali)."""

    @patch("core.training_handler.urlopen")
    def test_search_hf_datasets_mock(self, mock_urlopen):
        """Ricerca mockata che restituisce risultati strutturati."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {
                "id": "test/dataset-1",
                "author": "test-author",
                "description": "Test dataset description",
                "downloads": 100000,
                "likes": 500,
                "tags": ["nlp", "instruction"],
                "cardData": {
                    "size_categories": ["1K<n<10K"],
                    "license": "mit",
                    "task_categories": ["text-generation"],
                },
                "lastModified": "2024-01-01T00:00:00Z",
            }
        ]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = search_hf_datasets("test query", limit=10)
        assert result["success"] is True
        assert len(result["results"]) == 1
        ds = result["results"][0]
        assert ds["id"] == "test/dataset-1"
        assert ds["downloads"] == 100000
        assert isinstance(ds["task_categories"], list)

    @patch("core.training_handler.urlopen")
    def test_search_hf_empty_results(self, mock_urlopen):
        """API HuggingFace restituisce lista vuota."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = search_hf_datasets("nonexistent", limit=5)
        assert result["success"] is True
        assert len(result["results"]) == 0

    @patch("core.training_handler.urlopen")
    def test_search_hf_network_error(self, mock_urlopen):
        """Errore di rete non causa crash."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")

        result = search_hf_datasets("test")
        assert result["success"] is False
        assert "error" in result
        assert result["results"] == []

    @patch("core.training_handler.urlopen")
    def test_get_hf_dataset_info_mock(self, mock_urlopen):
        """Info dettagliate dataset con preview.

        Tre chiamate, in quest'ordine: scheda del dataset, struttura
        (config e split), anteprima. La struttura sta in mezzo perche'
        l'anteprima va chiesta sul config giusto: darlo per scontato
        ("default"/"train") la faceva fallire in silenzio su gsm8k,
        openwebtext e su ogni dataset diviso in sottoinsiemi.
        """
        responses = [
            json.dumps({
                "id": "test/dataset",
                "description": "A test dataset",
                "downloads": 50000,
                "likes": 200,
                "tags": ["test"],
                "cardData": {"license": "apache-2.0"},
            }),
            json.dumps({
                "splits": [
                    {"dataset": "test/dataset", "config": "principale", "split": "train"},
                    {"dataset": "test/dataset", "config": "principale", "split": "test"},
                ]
            }),
            json.dumps({
                "rows": [
                    {"row": {"text": "Primo esempio", "label": "A"}},
                    {"row": {"text": "Secondo esempio", "label": "B"}},
                ]
            }),
        ]
        mock_urlopen.side_effect = [
            MagicMock(__enter__=MagicMock(
                return_value=MagicMock(
                    read=MagicMock(return_value=responses[0].encode("utf-8"))
                )
            )),
            MagicMock(__enter__=MagicMock(
                return_value=MagicMock(
                    read=MagicMock(return_value=responses[1].encode("utf-8"))
                )
            )),
            MagicMock(__enter__=MagicMock(
                return_value=MagicMock(
                    read=MagicMock(return_value=responses[2].encode("utf-8"))
                )
            )),
        ]

        result = get_hf_dataset_info("test/dataset")
        assert result["success"] is True
        assert result["id"] == "test/dataset"
        assert len(result["preview"]) == 2
        # struttura scoperta, non assunta
        assert result["config"] == "principale"
        assert result["splits"] == ["train", "test"]
        # e l'anteprima e' stata chiesta proprio su quel config
        preview_url = mock_urlopen.call_args_list[2][0][0].full_url
        assert "config=principale" in preview_url and "split=train" in preview_url


# ===========================================================================
# 3. TEST IMPORT DATASET LOCALE
# ===========================================================================

class TestLocalDatasetImport:
    """Test importazione dataset da file locali in vari formati."""

    def test_import_jsonl(self, tmp_path):
        """Importa file JSONL valido."""
        jsonl_data = [
            {"instruction": "Cos'è AI?", "output": "Intelligenza Artificiale"},
            {"instruction": "Cos'è ML?", "output": "Machine Learning"},
        ]
        src_file = tmp_path / "test_data.jsonl"
        src_file.write_text("\n".join(json.dumps(r) for r in jsonl_data), encoding="utf-8")

        result = import_local_dataset(str(src_file), "test-jsonl")
        assert result["success"] is True
        ds = result["dataset"]
        assert ds["name"] == "test-jsonl"
        assert ds["row_count"] == 2
        assert "instruction" in ds["columns"]
        assert "output" in ds["columns"]

    def test_import_csv(self, tmp_path):
        """Importa file CSV con header."""
        csv_content = "instruction,output\nCiao,Mondo\nCome,Va?\n"
        src_file = tmp_path / "test.csv"
        src_file.write_text(csv_content, encoding="utf-8")

        result = import_local_dataset(str(src_file), "test-csv")
        assert result["success"] is True
        assert result["dataset"]["row_count"] == 2
        assert "instruction" in result["dataset"]["columns"]

    def test_import_txt(self, tmp_path):
        """Importa file TXT (una riga = un esempio)."""
        txt_content = "Prima riga di testo\nSeconda riga di testo\nTerza riga\n"
        src_file = tmp_path / "test.txt"
        src_file.write_text(txt_content, encoding="utf-8")

        result = import_local_dataset(str(src_file), "test-txt")
        assert result["success"] is True
        assert result["dataset"]["row_count"] == 3
        # Verifica che sia stato convertito in JSONL
        assert result["dataset"]["format"] == "txt"

    def test_import_json_array(self, tmp_path):
        """Importa file JSON con array di oggetti."""
        json_data = [
            {"text": "Primo", "label": "A"},
            {"text": "Secondo", "label": "B"},
            {"text": "Terzo", "label": "C"},
        ]
        src_file = tmp_path / "test.json"
        src_file.write_text(json.dumps(json_data), encoding="utf-8")

        result = import_local_dataset(str(src_file), "test-json")
        assert result["success"] is True
        assert result["dataset"]["row_count"] == 3

    def test_import_file_not_found(self):
        """File inesistente restituisce errore."""
        result = import_local_dataset("/nonexistent/file.jsonl")
        assert result["success"] is False
        assert "non trovato" in result["error"].lower()

    def test_register_hf_dataset(self):
        """Registrazione dataset HF (solo metadati, senza download)."""
        with patch("core.training_handler.get_hf_dataset_info") as mock_info:
            mock_info.return_value = {
                "success": True,
                "id": "test/dataset",
                "description": "Test",
                "downloads": 1000,
                "likes": 50,
                "tags": ["test"],
                "preview": [{"text": "test"}],
            }
            result = register_hf_dataset("test/dataset", split="train")
            assert result["success"] is True
            assert result["dataset"]["source"] == "huggingface"
            assert result["dataset"]["hf_id"] == "test/dataset"


# ===========================================================================
# 4. TEST CREAZIONE JOB DI TRAINING
# ===========================================================================

class TestTrainingJobCreation:
    """Test creazione e gestione job di training."""

    def test_create_basic_job(self):
        """Crea job con parametri minimi."""
        config = {
            "base_model": "unsloth/llama-3.2-3b-instruct",
            "dataset_id": "",
            "method": "lora_unsloth",
            "output_name": "test_model",
            "hyperparams": {
                "num_epochs": 3,
                "learning_rate": 2e-4,
                "batch_size": 2,
                "max_seq_length": 2048,
                "lora_r": 16,
                "lora_alpha": 16,
                "gradient_accumulation": 4,
                "text_field": "text",
            },
        }
        result = create_training_job(config)
        assert result["success"] is True
        job = result["job"]
        assert job["status"] == "ready"
        assert len(job["id"]) == 8
        assert job["base_model"] == "unsloth/llama-3.2-3b-instruct"
        assert job["method"] == "lora_unsloth"
        assert os.path.exists(job["script_path"])

    def test_create_job_with_all_hyperparams(self):
        """Crea job con tutti gli iperparametri personalizzati."""
        config = {
            "base_model": "meta-llama/Llama-3.2-3B-Instruct",
            "dataset_id": "",
            "method": "trl_sft",
            "output_name": "sigma_full_test",
            "hyperparams": {
                "num_epochs": 10,
                "learning_rate": 1e-5,
                "batch_size": 8,
                "max_seq_length": 4096,
                "lora_r": 32,
                "lora_alpha": 64,
                "gradient_accumulation": 8,
                "text_field": "instruction",
            },
        }
        result = create_training_job(config)
        assert result["success"] is True
        job = result["job"]
        assert job["hyperparams"]["num_epochs"] == 10
        assert job["hyperparams"]["learning_rate"] == 1e-5
        assert os.path.exists(job["script_path"])

        # Verifica che il template contenga i valori corretti
        script_content = Path(job["script_path"]).read_text(encoding="utf-8")
        assert "num_train_epochs=10" in script_content or "num_epochs=10" in script_content
        # In `trl_sft` il passo non finisce piu' dritto in SFTConfig: ci passa
        # attraverso `PASSO`, che l'addestramento completo puo' abbassare.
        # Quello che conta e' che il valore chiesto arrivi nello script.
        assert ("learning_rate=1e-05" in script_content
                or "PASSO = float(1e-05)" in script_content)

    def test_create_all_method_jobs(self):
        """Crea job per ogni metodo di training disponibile."""
        methods = list(SCRIPT_TEMPLATES.keys())
        for method in methods:
            config = {
                "base_model": "unsloth/llama-3.2-1b-instruct",
                "dataset_id": "",
                "method": method,
                "output_name": f"test_{method}",
                "hyperparams": {
                    "num_epochs": 1,
                    "learning_rate": 2e-4,
                    "batch_size": 1,
                    "max_seq_length": 512,
                    "lora_r": 8,
                    "lora_alpha": 8,
                    "gradient_accumulation": 1,
                    "text_field": "text",
                },
            }
            result = create_training_job(config)
            assert result["success"] is True, f"Fallito metodo {method}: {result.get('error')}"
            assert os.path.exists(result["job"]["script_path"])

    def test_job_persists_to_disk(self):
        """I job vengono correttamente salvati su disco."""
        config = {
            "base_model": "gpt2",
            "method": "full_pretrain",
            "hyperparams": {"num_epochs": 2},
        }
        result = create_training_job(config)
        job_id = result["job"]["id"]

        # Ricarica da disco
        jobs = _load_jobs()
        assert job_id in jobs
        assert jobs[job_id]["status"] == "ready"

    def test_job_listing(self):
        """Lista job dal più recente al più vecchio.

        Confrontare solo le date non bastava: `created_at` ha la granularità
        del secondo, tre job creati di fila hanno la stessa data e qualunque
        ordine soddisfaceva il confronto. Il test passava per caso mentre la
        lista usciva dal più vecchio, e la UI apriva sul primo job mai creato.
        """
        created = []
        for _ in range(3):
            job_id = create_training_job({
                "base_model": "test",
                "method": "lora_unsloth",
                "hyperparams": {},
            })["job_id"]
            created.append(job_id)

        result = list_jobs()
        assert result["success"] is True
        listed = [j["id"] for j in result["jobs"] if j["id"] in created]
        assert listed == list(reversed(created)), "l'ultimo creato deve essere il primo"

        dates = [j["created_at"] for j in result["jobs"]]
        assert dates == sorted(dates, reverse=True)


# ===========================================================================
# 5. TEST ESECUZIONE JOB (SUB PROCESS MOCK)
# ===========================================================================

class TestJobExecution:
    """Test avvio/stop/esecuzione job (con mock del subprocess)."""

    @patch("core.training_handler.subprocess.Popen")
    def test_start_job_creates_process(self, mock_popen):
        """Avvio job crea un processo."""
        # Crea job prima
        config = {
            "base_model": "test",
            "method": "script_custom",
            "hyperparams": {},
        }
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]

        # Mock del processo (binary mode compatibile con text=False)
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        # stdout.read(4096) deve restituire bytes chunks, poi b"" a EOF
        _chunks = [
            b"[SIGMA] Avvio training...\n",
            b"Epoch 1/3, loss: 0.5823\n",
            b"Epoch 2/3, loss: 0.3412\n",
            b"[SIGMA] Training completato!\n",
        ]
        def _mock_read(size=4096):
            if not _chunks:
                return b""
            return _chunks.pop(0)
        mock_proc.stdout.read.side_effect = _mock_read
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        # Avvia job
        result = start_training_job(job_id)
        assert result["success"] is True
        assert result["pid"] == 12345

        # Aspetta che il thread di log finisca
        time.sleep(0.5)

        # Verifica stato
        status = get_job_status(job_id)
        assert status["success"] is True
        assert status["job"]["status"] in ("running", "completed")

    @patch("core.training_handler.subprocess.Popen")
    def test_stop_running_job(self, mock_popen):
        """Ferma un job in esecuzione."""
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.stdout = iter(["output line"])
        mock_popen.return_value = mock_proc

        start_training_job(job_id)
        result = stop_training_job(job_id)
        assert result["success"] is True

    def test_stop_non_existent_job(self):
        """Fermare job inesistente restituisce errore."""
        result = stop_training_job("nonexistent")
        assert result["success"] is False

    def test_get_logs_from_job(self):
        """Legge i log di un job."""
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]

        # Usa th.JOBS_DIR per accedere al path patchato nel modulo
        log_path = th.JOBS_DIR / job_id / "train.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_lines = ["line 1", "line 2", "line 3"]
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        result = get_job_logs(job_id)
        assert result["success"] is True
        assert len(result["lines"]) == 3

    def test_delete_job_removes_files(self):
        """Eliminazione job rimuove anche i file su disco."""
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]

        # Usa th.JOBS_DIR per accedere al path patchato nel modulo
        job_dir = th.JOBS_DIR / job_id
        assert job_dir.exists()

        result = delete_job(job_id)
        assert result["success"] is True
        assert not job_dir.exists()


# ===========================================================================
# 6. TEST EXPORT OLLAMA
# ===========================================================================

class TestOllamaExport:
    """Test export modello trainato verso Ollama."""

    @patch("core.training_handler.subprocess.run")
    def test_export_creates_modelfile(self, mock_run):
        """Export genera Modelfile valido quando c'e' un artefatto da esportare."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]

        # Marca job come completato e crea l'adapter prodotto dal training
        jobs = _load_jobs()
        jobs[job_id]["status"] = "completed"
        _save_jobs(jobs)
        (Path(jobs[job_id]["dir"]) / "adapter").mkdir(parents=True, exist_ok=True)

        result = export_to_ollama(job_id, "sigma-test-model", "Sei un assistente AI.")
        assert result["success"] is True
        assert result["model_name"] == "sigma-test-model"
        assert "Modelfile" in result.get("modelfile_path", "")

    def test_export_fails_when_there_is_nothing_to_export(self):
        """Senza artefatti l'export deve dirlo, non scrivere un Modelfile rotto.

        Prima scriveva un Modelfile che puntava a un adapter inesistente e
        riportava successo: l'utente si ritrovava senza modello e senza errore.
        """
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]
        jobs = _load_jobs()
        jobs[job_id]["status"] = "completed"
        _save_jobs(jobs)

        result = export_to_ollama(job_id, "sigma-test-model")
        assert result["success"] is False
        assert "esportabile" in result["error"].lower()

    @patch("core.training_handler.subprocess.run")
    def test_export_reports_ollama_failure(self, mock_run):
        """Un `ollama create` fallito non deve passare per riuscito."""
        mock_run.return_value = MagicMock(returncode=1, stdout="",
                                          stderr="Error: invalid model reference")
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]
        jobs = _load_jobs()
        jobs[job_id]["status"] = "completed"
        _save_jobs(jobs)
        (Path(jobs[job_id]["dir"]) / "adapter").mkdir(parents=True, exist_ok=True)

        result = export_to_ollama(job_id, "sigma-test-model")
        if shutil.which("ollama"):          # senza Ollama il messaggio e' un altro
            assert result["success"] is False
            assert "invalid model reference" in result["error"]

    def _completed_job_with(self, *subdirs, files=()):
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        job_id = create_training_job(config)["job"]["id"]
        jobs = _load_jobs()
        jobs[job_id]["status"] = "completed"
        _save_jobs(jobs)
        job_dir = Path(jobs[job_id]["dir"])
        for sub in subdirs:
            (job_dir / sub).mkdir(parents=True, exist_ok=True)
        for rel in files:
            target = job_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"GGUF")
        return job_id, job_dir

    @patch("core.training_handler.subprocess.run")
    def test_an_existing_gguf_wins_over_the_safetensors(self, mock_run):
        """Ollama carica un .gguf com'e'; sui safetensors deve convertire e puo'
        non saperlo fare, quindi il .gguf ha la precedenza."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        job_id, job_dir = self._completed_job_with(
            "output/merged_16bit", files=["output/modello-f16.gguf"])

        result = export_to_ollama(job_id, "sigma-test-model")
        assert result["success"] is True
        assert result["source"] == "gguf"
        assert "modello-f16.gguf" in result["modelfile"]

    @patch("core.training_handler.subprocess.run")
    def test_ollama_progress_bars_do_not_swallow_the_error(self, mock_run):
        """Il vero errore va estratto da spinner e sequenze ANSI, non perso."""
        noisy = ("\x1b[?25lcopying file sha256:abc 100%\x1b[K\r"
                 "\x1b[1Gconverting model \x1b[K\n"
                 "Error: improper type for 'qwen35.rope.scaling.factor'\n")
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr=noisy)
        job_id, _ = self._completed_job_with("adapter")

        result = export_to_ollama(job_id, "sigma-test-model")
        if shutil.which("ollama"):
            assert result["success"] is False
            assert result["error"].endswith("improper type for 'qwen35.rope.scaling.factor'")
            assert "\x1b" not in result["error"] and "copying file" not in result["error"]

    @patch("core.training.jobs._convert_to_gguf")
    @patch("core.training_handler.subprocess.run")
    def test_i_pesi_passano_sempre_da_llama_cpp(self, mock_run, mock_convert):
        """Non e' piu' un ripiego: e' la strada principale.

        Il convertitore di Ollama si ferma sulle architetture recenti e, su un
        modello con embedding legate, riesce ma produce uno strato di uscita
        rotto — misurato: "@@@@@@@@@@" invece di una risposta. Un guasto che non
        solleva niente e' il motivo per cui il ripiego non scattava mai.
        """
        if not shutil.which("ollama"):
            pytest.skip("serve il binario ollama")
        job_id, job_dir = self._completed_job_with("output/merged_16bit")
        gguf = job_dir / "output" / "convertito-f16.gguf"

        def convert(model_dir, out_dir):
            gguf.write_bytes(b"GGUF")
            return {"success": True, "gguf_path": gguf}

        mock_convert.side_effect = convert
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = export_to_ollama(job_id, "sigma-test-model")
        assert result["success"] is True
        assert result["source"] == "gguf"
        assert mock_convert.call_count == 1, "senza aspettare che Ollama fallisca"
        assert "convertito-f16.gguf" in result["modelfile"]

    @patch("core.training.jobs._convert_to_gguf")
    @patch("core.training_handler.subprocess.run")
    def test_se_llama_cpp_non_ce_la_fa_prova_comunque_ollama(self, mock_run, mock_convert):
        """Meglio il convertitore imperfetto che nessun export."""
        if not shutil.which("ollama"):
            pytest.skip("serve il binario ollama")
        mock_convert.return_value = {"success": False, "error": "converter mancante"}
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        job_id, _ = self._completed_job_with("output/merged_16bit")

        result = export_to_ollama(job_id, "sigma-test-model")
        assert result["success"] is True
        assert result["source"] == "merged", "si ricade sui pesi cosi' come sono"

    @patch("core.training_handler.subprocess.run")
    def test_quantization_is_passed_to_ollama(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        job_id, _ = self._completed_job_with("adapter")

        result = export_to_ollama(job_id, "sigma-test-model", "", "q4_K_M")
        if shutil.which("ollama"):
            assert result["success"] is True
            assert result["quantization"] == "q4_K_M"
            cmd = mock_run.call_args[0][0]
            assert cmd[cmd.index("--quantize") + 1] == "q4_K_M"

    def test_an_unknown_quantization_is_refused_before_running_anything(self):
        job_id, _ = self._completed_job_with("adapter")
        result = export_to_ollama(job_id, "sigma-test-model", "", "q4_0_XL")
        assert result["success"] is False
        assert "non riconosciuta" in result["error"]

    @patch("core.training_handler.subprocess.run")
    def test_no_quantization_leaves_the_command_alone(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        job_id, _ = self._completed_job_with("adapter")

        result = export_to_ollama(job_id, "sigma-test-model")
        if shutil.which("ollama"):
            assert result["quantization"] is None
            assert "--quantize" not in mock_run.call_args[0][0]

    def test_export_fails_if_not_completed(self):
        """Export fallisce se job non è completato."""
        config = {"base_model": "test", "method": "script_custom", "hyperparams": {}}
        create_result = create_training_job(config)
        job_id = create_result["job"]["id"]

        result = export_to_ollama(job_id, "test-model")
        assert result["success"] is False
        assert "non completato" in result["error"].lower()

    def test_export_fails_if_job_not_found(self):
        """Export fallisce se job inesistente."""
        result = export_to_ollama("nonexistent", "test-model")
        assert result["success"] is False
        assert "non trovato" in result["error"].lower()


# ===========================================================================
# 7. TEST HARDWARE INFO
# ===========================================================================

class TestHardwareInfo:
    """Test rilevamento hardware e diagnostica CUDA."""

    @patch("core.training_handler._query_wmi_gpus")
    @patch("core.training_handler._query_nvidia_smi")
    @patch("core.training_handler._check_torch_cuda")
    def test_hardware_info_structure(self, mock_torch, mock_smi, mock_wmi):
        """Struttura informazione hardware è completa."""
        mock_wmi.return_value = []
        mock_smi.return_value = [
            {
                "index": 0, "name": "NVIDIA RTX 5090", "vram_total_mb": 24576,
                "vram_free_mb": 20000, "vram_used_mb": 4576, "vram_total_gb": 24.0,
                "vram_free_gb": 19.5, "driver_version": "555.85",
                "pcie_gen": 5, "pcie_width": 16, "compute_cap": "12.0",
                "gpu_util_pct": 0.0, "temp_c": 35, "power_draw_w": 30, "power_limit_w": 450,
            }
        ]
        mock_torch.return_value = {
            "torch_available": True, "torch_version": "2.9.0",
            "torch_cuda_version": "13.0", "cuda_available": True,
            "cuda_device_count": 1, "torch_gpu_list": [
                {"index": 0, "name": "NVIDIA RTX 5090", "vram_gb": 24.0,
                 "compute_capability": "12.0", "multi_processor_count": 128}
            ],
            "cudnn_version": "90100", "cuda_error": None,
        }

        result = get_hardware_info()
        assert result["success"] is True
        hw = result["hardware"]
        assert hw["gpu_count"] == 1
        assert len(hw["gpu"]) == 1
        assert hw["gpu"][0]["name"] == "NVIDIA RTX 5090"
        assert hw["torch_available"] is True
        assert hw["cuda_available"] is True
        assert hw["multi_gpu"]["available"] is False
        assert hw["cpu_count"] > 0
        assert hw["ram_gb"] > 0

    @patch("core.training_handler._query_wmi_gpus")
    @patch("core.training_handler._query_nvidia_smi")
    @patch("core.training_handler._check_torch_cuda")
    def test_multi_gpu_detection(self, mock_torch, mock_smi, mock_wmi):
        """Rilevamento multi-GPU corretto."""
        mock_wmi.return_value = []
        mock_smi.return_value = [
            {"index": 0, "name": "RTX 4090", "vram_total_gb": 24.0, "vram_total_mb": 24576, **{k: 0 for k in ["vram_free_mb","vram_used_mb","vram_free_gb","driver_version","pcie_gen","pcie_width","compute_cap","gpu_util_pct","temp_c","power_draw_w","power_limit_w"]}},
            {"index": 1, "name": "RTX 4090", "vram_total_gb": 24.0, "vram_total_mb": 24576, **{k: 0 for k in ["vram_free_mb","vram_used_mb","vram_free_gb","driver_version","pcie_gen","pcie_width","compute_cap","gpu_util_pct","temp_c","power_draw_w","power_limit_w"]}},
        ]
        mock_torch.return_value = {
            "torch_available": True, "cuda_available": True, "cuda_device_count": 2,
            "torch_version": "2.9.0", "torch_cuda_version": "13.0",
            "torch_gpu_list": [], "cudnn_version": None, "cuda_error": None,
        }

        result = get_hardware_info()
        hw = result["hardware"]
        assert hw["gpu_count"] == 2
        assert hw["multi_gpu"]["available"] is True
        assert hw["multi_gpu"]["gpu_count"] == 2
        assert hw["multi_gpu"]["total_vram_gb"] == 48.0
        assert "device_map" in hw["multi_gpu"]["strategy"]

    @patch("core.training_handler._query_wmi_gpus")
    @patch("core.training_handler._query_nvidia_smi")
    @patch("core.training_handler._check_torch_cuda")
    def test_no_gpu_detection(self, mock_torch, mock_smi, mock_wmi):
        """Nessuna GPU rilevata → diagnostica."""
        mock_wmi.return_value = []
        mock_smi.return_value = []
        mock_torch.return_value = {
            "torch_available": False, "cuda_available": False,
            "cuda_device_count": 0, "torch_version": None,
            "torch_cuda_version": None, "torch_gpu_list": [],
            "cudnn_version": None, "cuda_error": "No CUDA",
        }

        result = get_hardware_info()
        hw = result["hardware"]
        assert hw["gpu_count"] == 0
        assert len(hw["gpu"]) == 0
        assert hw["cuda_fix"]["has_issue"] is True


# ===========================================================================
# 8. TEST SCRIPT TEMPLATE FORMATTAZIONE
# ===========================================================================

class TestScriptTemplates:
    """Verifica che i template script vengano formattati correttamente."""

    def test_all_templates_have_required_placeholders(self):
        """Tutti i template contengono i placeholder critici (escluso script_custom che usa {config_json})."""
        required_placeholders = [
            "{job_id}", "{base_model}", "{dataset_name}",
            "{dataset_path}", "{output_dir}", "{num_epochs}",
            "{learning_rate}", "{batch_size}",
        ]
        for method_name, template in SCRIPT_TEMPLATES.items():
            if method_name == "script_custom":
                # script_custom è un template generico che usa {config_json}
                assert "{config_json}" in template, \
                    f"script_custom deve avere almeno {{config_json}}"
                continue
            for ph in required_placeholders:
                assert ph in template, f"Manca placeholder {ph} in {method_name}"

    def test_template_formatting_with_values(self):
        """Formattazione template con valori reali."""
        config = {
            "base_model": "unsloth/llama-3.2-3b-instruct",
            "method": "lora_unsloth",
            "hyperparams": {
                "num_epochs": 3, "learning_rate": 2e-4, "batch_size": 2,
                "max_seq_length": 2048, "lora_r": 16, "lora_alpha": 16,
                "gradient_accumulation": 4, "text_field": "text",
            },
        }
        result = create_training_job(config)
        script = Path(result["job"]["script_path"]).read_text(encoding="utf-8")

        # Placeholder non devono sopravvivere
        assert "{num_epochs}" not in script
        assert "{job_id}" not in script
        assert "{dataset_path}" not in script

    def test_script_custom_contains_config(self):
        """Template custom include configurazione JSON."""
        config = {
            "base_model": "custom-model",
            "method": "script_custom",
            "hyperparams": {"num_epochs": 5, "learning_rate": 1e-4},
        }
        result = create_training_job(config)
        script = Path(result["job"]["script_path"]).read_text(encoding="utf-8")
        assert "custom-model" in script
        assert "num_epochs" in script


# ===========================================================================
# 9. TEST PERSISTENZA E RECUPERO
# ===========================================================================

class TestJobPersistence:
    """Test salvataggio e recupero job su disco."""

    def test_save_and_load_jobs(self):
        """Salva e ricarica lavori da file JSON."""
        jobs = {"test123": {"id": "test123", "status": "running"}}
        _save_jobs(jobs)
        loaded = _load_jobs()
        assert loaded["test123"]["id"] == "test123"
        assert loaded["test123"]["status"] == "running"

    def test_list_datasets_empty(self):
        """Lista dataset vuota restituisce array vuoto."""
        result = list_datasets()
        assert result["success"] is True
        assert isinstance(result["datasets"], list)

    def test_delete_nonexistent_dataset(self):
        """Eliminazione dataset inesistente."""
        result = delete_dataset("nonexistent_id")
        assert result["success"] is False


# ===========================================================================
# 10. TEST UTILITY DI PARSING (da TrainingMonitor)
# ===========================================================================

class TestDependencyCheck:
    """Test controllo dipendenze pre-training."""

    @patch("core.training_handler.subprocess.run")
    def test_check_dependencies_all_installed(self, mock_run):
        """Tutte le dipendenze installate."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Name: torch\nVersion: 2.9.0"
        result = check_training_dependencies("lora_unsloth")
        assert result["method"] == "lora_unsloth"
        assert result["all_installed"] is True

    @patch("core.training_handler.subprocess.run")
    def test_check_dependencies_missing(self, mock_run):
        """Alcune dipendenze mancanti."""
        def side_effect(*args, **kwargs):
            mock = MagicMock()
            pkg = args[0][-1]
            mock.returncode = 0 if pkg == "torch" else 1
            mock.stdout = "Name: torch\nVersion: 2.9.0\n" if pkg == "torch" else ""
            return mock
        mock_run.side_effect = side_effect
        result = check_training_dependencies("lora_unsloth")
        assert result["all_installed"] is False
        assert len(result["missing"]) > 0

    def test_check_dependencies_custom(self):
        """Metodo custom non ha dipendenze."""
        result = check_training_dependencies("script_custom")
        assert result["all_installed"] is True
        assert result["install_command"] == ""


class TestLogParsing:
    """Test funzioni di parsing dei log (simulate lato backend per validazione)."""

    def test_loss_patterns(self):
        """Verifica che i pattern di loss nei template siano parsabili."""
        import re

        test_lines = [
            ("[SIGMA] Epoch 1/10 — loss: 0.5823", 0.5823),
            ("loss=0.1234", 0.1234),
            ("'loss': 0.9876", 0.9876),
            ("train_loss: 1.2345", 1.2345),
            ("step 100/500, loss: 0.45, lr: 2e-5", 0.45),
        ]

        patterns = [
            re.compile(r"loss[:\s=]+([0-9.]+)", re.IGNORECASE),
            re.compile(r"'loss':\s*([0-9.]+)"),
            re.compile(r"train_loss[:\s=]+([0-9.]+)", re.IGNORECASE),
            re.compile(r"\[SIGMA\].*loss:\s*([0-9.]+)", re.IGNORECASE),
        ]

        for line, expected in test_lines:
            found = None
            for p in patterns:
                m = p.search(line)
                if m:
                    found = float(m.group(1))
                    break
            assert found == expected, f"Linea '{line}' → atteso {expected}, ottenuto {found}"

    def test_epoch_pattern(self):
        """Pattern epoca espresso nei log."""
        import re
        test_cases = [
            ("Epoch 3/10", (3, 10)),
            ("epoch 1/5", (1, 5)),
            ("[SIGMA] Epoch 7/20 — loss: 0.5", (7, 20)),
        ]
        pattern = re.compile(r"[Ee]poch\s+(\d+)\s*/\s*(\d+)")
        for line, expected in test_cases:
            m = pattern.search(line)
            assert m is not None, f"Pattern non trovato in: {line}"
            assert (int(m.group(1)), int(m.group(2))) == expected

class TestFormatoChatEreditato:
    """Un modello esportato deve conservare il formato di conversazione.

    Senza `TEMPLATE` nel Modelfile, Ollama mette il suo predefinito — il prompt
    passato nudo — e un modello istruito smette di rispondere: produce una
    continuazione, che il benchmark conta come illeggibile. Misurato su
    qwen2.5:0.5b-instruct: base 79 risposte valide su 300, ogni candidato
    esportato 0 su 300 con 276 illeggibili — gli stessi numeri a ogni round,
    qualunque fosse l'addestramento. Non era il training: era l'export.
    """

    MODELFILE = '\n'.join([
        '# Modelfile generated by "ollama show"',
        'FROM /blobs/sha256-abc',
        'TEMPLATE """{{- if .Messages }}',
        '<|im_start|>system',
        '{{ .System }}<|im_end|>',
        '{{ end }}"""',
        'PARAMETER stop <|im_start|>',
        'PARAMETER stop <|im_end|>',
        'PARAMETER temperature 0.7',
    ])

    def _con_uscita(self, monkeypatch, testo, returncode=0):
        from core.training import jobs

        monkeypatch.setattr(jobs.shutil, "which", lambda n: "/usr/bin/ollama")
        monkeypatch.setattr(jobs, "_get_subprocess_run", lambda: (
            lambda *a, **k: type("R", (), {"returncode": returncode, "stdout": testo})()))

    def test_il_template_e_gli_stop_vengono_copiati(self, monkeypatch):
        from core.training.jobs import formato_chat_di

        self._con_uscita(monkeypatch, self.MODELFILE)
        out = formato_chat_di("qwen2.5:0.5b-instruct")
        assert "TEMPLATE" in out and "<|im_start|>system" in out
        assert out.count("PARAMETER stop") == 2
        # La temperatura la decidiamo noi: copiarla sovrascriverebbe la scelta.
        assert "temperature" not in out

    def test_un_template_banale_non_si_copia(self, monkeypatch):
        """`{{ .Prompt }}` e' proprio il predefinito da cui stiamo scappando."""
        from core.training.jobs import formato_chat_di

        self._con_uscita(monkeypatch, "FROM /x\nTEMPLATE {{ .Prompt }}\n")
        assert formato_chat_di("un-base") == ""

    def test_un_modello_inesistente_non_rompe_l_export(self, monkeypatch):
        from core.training.jobs import formato_chat_di

        self._con_uscita(monkeypatch, "", returncode=1)
        assert formato_chat_di("mai-visto") == ""

    def test_senza_ollama_si_prosegue(self, monkeypatch):
        from core.training import jobs

        monkeypatch.setattr(jobs.shutil, "which", lambda n: None)
        assert jobs.formato_chat_di("qualcosa") == ""

    def test_il_modelfile_generato_lo_contiene(self, monkeypatch, tmp_path):
        from core.training import jobs

        self._con_uscita(monkeypatch, self.MODELFILE)
        pesi = tmp_path / "pesi"
        pesi.mkdir()
        (pesi / "config.json").write_text("{}", encoding="utf-8")
        jobs.register_ollama_model(pesi, "sigma-prova", system_prompt="",
                                   workdir=tmp_path, template_from="qwen2.5:0.5b-instruct")
        scritto = (tmp_path / "Modelfile").read_text(encoding="utf-8")
        assert scritto.index("FROM") < scritto.index("TEMPLATE")
        assert "<|im_start|>system" in scritto
        assert "PARAMETER stop <|im_end|>" in scritto


class TestConvertitoreGguf:
    """Chi converte i pesi in GGUF non e' una scelta indifferente.

    Il convertitore interno di Ollama ha sbagliato tre volte su tre: si ferma
    sulle architetture recenti (Qwen3.5, AILO) e — molto peggio — su un modello
    con embedding legate riesce, ma produce uno strato di uscita rotto. Misurato
    sugli stessi pesi di un Qwen2.5-0.5B fuso: da Ollama la risposta e'
    "@@@@@@@@@@", da llama.cpp e' un numero. Un guasto che non solleva niente e'
    il motivo per cui il ripiego "solo se fallisce" non scattava mai.
    """

    def _prepara(self, monkeypatch, tmp_path, con_llamacpp=True):
        from core.training import jobs

        pesi = tmp_path / "merged"
        pesi.mkdir()
        (pesi / "config.json").write_text("{}", encoding="utf-8")
        gguf = tmp_path / "merged-f16.gguf"
        convertiti = []

        monkeypatch.setattr(jobs, "find_gguf_converter",
                            lambda: "/llama.cpp/convert.py" if con_llamacpp else None)

        def finta_conversione(sorgente, destinazione):
            convertiti.append(str(sorgente))
            gguf.write_bytes(b"gguf")
            return {"success": True, "gguf_path": gguf}

        monkeypatch.setattr(jobs, "_convert_to_gguf", finta_conversione)
        monkeypatch.setattr(jobs.shutil, "which", lambda n: "/usr/bin/ollama")
        monkeypatch.setattr(jobs, "formato_chat_di", lambda m: "")
        monkeypatch.setattr(jobs, "_get_subprocess_run", lambda: (
            lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()))
        return pesi, gguf, convertiti

    def test_una_cartella_di_pesi_passa_da_llamacpp(self, monkeypatch, tmp_path):
        from core.training import jobs

        pesi, gguf, convertiti = self._prepara(monkeypatch, tmp_path)
        esito = jobs.register_ollama_model(pesi, "sigma-prova", system_prompt="",
                                           workdir=tmp_path)
        assert esito["success"] and esito["source"] == "gguf"
        assert convertiti == [str(pesi)]
        assert str(gguf).replace("\\", "/") in (tmp_path / "Modelfile").read_text(encoding="utf-8")

    def test_senza_llamacpp_si_lascia_fare_a_ollama(self, monkeypatch, tmp_path):
        """Meglio il convertitore imperfetto che nessun export."""
        from core.training import jobs

        pesi, _, convertiti = self._prepara(monkeypatch, tmp_path, con_llamacpp=False)
        esito = jobs.register_ollama_model(pesi, "sigma-prova", system_prompt="",
                                           workdir=tmp_path)
        assert esito["success"] and not convertiti
        assert str(pesi).replace("\\", "/") in (tmp_path / "Modelfile").read_text(encoding="utf-8")

    def test_un_gguf_gia_pronto_non_si_riconverte(self, monkeypatch, tmp_path):
        from core.training import jobs

        _, gguf, convertiti = self._prepara(monkeypatch, tmp_path)
        gguf.write_bytes(b"gguf")
        jobs.register_ollama_model(gguf, "sigma-prova", system_prompt="", workdir=tmp_path)
        assert not convertiti

    def test_un_adapter_non_si_converte(self, monkeypatch, tmp_path):
        """Un adapter va montato sopra la base, non trasformato in un modello."""
        from core.training import jobs

        pesi, _, convertiti = self._prepara(monkeypatch, tmp_path)
        jobs.register_ollama_model(pesi, "sigma-prova", system_prompt="",
                                   workdir=tmp_path, adapter_base="qwen2.5:0.5b")
        assert not convertiti
