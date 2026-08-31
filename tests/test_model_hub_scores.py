# ==============================================================================
# tests/test_model_hub_scores.py — Il referto di un modello, dove serve
#
# Il Model Hub diceva "nessun benchmark registrato" per modelli che ne avevano
# uno, e per quelli che lo avevano mostrava "0 quesiti superati, 0 tok/s"
# accanto a un punteggio vero. Tre cause, tutte nella lettura del referto, e
# ognuna presente due volte perche' l'inventario e il generatore della scheda
# lo leggevano ciascuno per conto proprio.
# ==============================================================================
import json
import os
import tempfile
import unittest
import uuid
from unittest import mock


def _job(model, score=72.0, status="completed", passed=72, total=100, tok_s=87.8):
    return {
        "id": "bm_test", "model": model, "status": status,
        "suite": "all", "suite_name": "Tutti i Benchmark Ufficiali",
        "created_at": "2026-08-27T22:20:03",
        "metrics": {"overall_score": score, "progress_score": score,
                    "tests_passed": passed, "tests_total": total,
                    "tests_failed": total - passed, "tests_review": 0,
                    "tokens_per_sec": tok_s, "avg_latency_ms": 1940,
                    "decided_accuracy_pct": score},
        "reproducibility": {"reproducible_hash": "SHA256-ABC", "temperature": 0.0,
                            "seed": 42, "mode": "AUDIT_SAMPLE",
                            "dataset_complete": False, "objective_mode": True,
                            "prompt_protocol": 3, "answer_protocol": "logit-ranking",
                            "protocols": {"mmlu": {"mode": "letter_logprob"}}},
    }


class TestModelScores(unittest.TestCase):
    """Una lettura sola, esatta, con i nomi che il motore scrive davvero."""

    def _con_referti(self, job):
        from core.modules.sigma_training_lab.training import model_scores

        cartella = tempfile.mkdtemp()
        percorso = os.path.join(cartella, "risultati.json")
        with open(percorso, "w", encoding="utf-8") as fh:
            json.dump(job, fh)
        return mock.patch.object(model_scores, "RISULTATI", percorso)

    def test_the_real_metric_names_are_read(self):
        from core.modules.sigma_training_lab.training.model_scores import scores_for_model

        with self._con_referti([_job("sigma:google--gemma-4-12B-it-GGUF-Q4_K_M")]):
            referto = scores_for_model("google/gemma-4-12B-it-GGUF-Q4_K_M",
                                       include_suites=False)

        # Prima leggeva `passed_count`, `total_count`, `avg_tok_s`: chiavi che
        # non esistono in nessun referto. Assenti valgono zero, quindi accanto a
        # un punteggio vero comparivano "0/0 quesiti" e "0 tok/s".
        self.assertEqual(referto["score"], 72.0)
        self.assertEqual((referto["tests_passed"], referto["tests_total"]), (72, 100))
        self.assertEqual(referto["tokens_per_sec"], 87.8)

    def test_a_quantization_does_not_lend_its_score_to_the_checkpoint(self):
        from core.modules.sigma_training_lab.training.model_scores import scores_for_model

        with self._con_referti([_job("sigma:google--gemma-4-12B-it-GGUF-Q4_K_M")]):
            checkpoint = scores_for_model("google/gemma-4-12B-it")
            quantizzato = scores_for_model("google/gemma-4-12B-it-GGUF-Q4_K_M")

        # `"a" in "a-gguf-q4"` e' vero, ed e' cosi' che il safetensors ereditava
        # il punteggio della sua quantizzazione. Sono due artefatti diversi.
        self.assertIsNone(checkpoint)
        self.assertIsNotNone(quantizzato)

    def test_the_provider_prefix_and_the_disk_form_are_the_same_model(self):
        from core.modules.sigma_training_lab.training.model_scores import normalizza

        self.assertEqual(normalizza("sigma:google--Gemma-4"), "google/gemma-4")
        self.assertEqual(normalizza("google/Gemma-4"), "google/gemma-4")

    def test_an_unfinished_run_does_not_report_the_official_score(self):
        from core.modules.sigma_training_lab.training.model_scores import scores_for_model

        parziale = _job("sigma:tiny", score=32.0, status="running",
                        passed=32, total=61)
        parziale["metrics"]["progress_score"] = 52.46
        with self._con_referti([parziale]):
            referto = scores_for_model("tiny", include_suites=False)

        # A meta' strada `overall_score` divide per i quesiti previsti, non per
        # quelli fatti: pubblicarlo attribuirebbe al modello come errori le
        # domande che non ha nemmeno visto.
        self.assertEqual(referto["score"], 52.46)
        self.assertFalse(referto["completed"])

    def test_a_completed_run_wins_over_a_more_recent_partial_one(self):
        from core.modules.sigma_training_lab.training.model_scores import scores_for_model

        vecchio = _job("sigma:tiny", score=80.0, status="completed")
        nuovo = _job("sigma:tiny", score=10.0, status="running")
        nuovo["created_at"] = "2026-08-28T10:00:00"
        with self._con_referti([vecchio, nuovo]):
            referto = scores_for_model("tiny", include_suites=False)
        self.assertEqual(referto["score"], 80.0)
        self.assertTrue(referto["completed"])

    def test_no_results_file_means_no_benchmarks_not_an_error(self):
        from core.modules.sigma_training_lab.training import model_scores

        with mock.patch.object(model_scores, "RISULTATI", "/percorso/inesistente.json"):
            self.assertIsNone(model_scores.scores_for_model("qualsiasi"))
            self.assertEqual(model_scores.scores_by_model(), {})

    def test_the_results_path_is_anchored_to_the_installation(self):
        from core.modules.sigma_training_lab.training import model_scores
        from core.modules.sigma_training_lab import paths as module_paths

        # Un percorso relativo trova il file solo se il processo e' partito
        # dalla radice: altrove ogni modello risulta "mai valutato", senza
        # errore e senza indizi.
        self.assertTrue(os.path.isabs(model_scores.RISULTATI))
        self.assertTrue(model_scores.RISULTATI.startswith(str(module_paths.PROJECT_ROOT)))


class TestLocalRename(unittest.TestCase):
    """Rinominare non deve poter fare cio' che cancellare ha il divieto di fare."""

    def _cartella(self):
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "autore--modello"))
        return base

    def test_a_model_is_renamed_on_disk(self):
        from core.modules.sigma_model_hub.backend.model_inventory import rename_local_model

        base = self._cartella()
        esito = rename_local_model("autore--modello", "nuovo/nome", custom_dir=base)
        self.assertTrue(esito["success"])
        self.assertTrue(os.path.isdir(os.path.join(base, "nuovo--nome")))
        # `autore/modello` e' come Hugging Face nomina le cose, `autore--modello`
        # e' come sta sul disco: la stessa convenzione dei modelli scaricati.
        self.assertEqual(esito["model_id"], "nuovo/nome")

    def test_a_name_cannot_escape_the_models_folder(self):
        from core.modules.sigma_model_hub.backend.model_inventory import rename_local_model

        base = self._cartella()
        for cattivo in ("../fuori", "..\\fuori", "/tmp/assoluto"):
            esito = rename_local_model("autore--modello", cattivo, custom_dir=base)
            self.assertFalse(esito["success"], cattivo)
        self.assertTrue(os.path.isdir(os.path.join(base, "autore--modello")))

    def test_an_existing_name_is_refused(self):
        from core.modules.sigma_model_hub.backend.model_inventory import rename_local_model

        base = self._cartella()
        os.makedirs(os.path.join(base, "gia--presente"))
        esito = rename_local_model("autore--modello", "gia/presente", custom_dir=base)
        self.assertFalse(esito["success"])
        self.assertIn("già", esito["error"])

    def test_an_empty_name_changes_nothing(self):
        from core.modules.sigma_model_hub.backend.model_inventory import rename_local_model

        base = self._cartella()
        self.assertFalse(rename_local_model("autore--modello", "   ",
                                            custom_dir=base)["success"])
        self.assertTrue(os.path.isdir(os.path.join(base, "autore--modello")))


class TestHfRepoRename(unittest.TestCase):
    """Rinominare su HF lascia un rimando; ricaricare lascia due repository."""

    def test_a_short_name_is_refused(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import rename_hf_repo

        esito = rename_hf_repo("autore/modello", "solomodello")
        self.assertFalse(esito["success"])
        self.assertIn("autore/modello", esito["error"])

    def test_the_same_name_is_not_an_error(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import rename_hf_repo

        esito = rename_hf_repo("a/b", "a/b")
        self.assertTrue(esito["success"])
        self.assertFalse(esito["renamed"])


class TestModelCardBenchmarks(unittest.TestCase):
    """La scheda pubblicata deve poter essere verificata da chi la legge."""

    def test_the_card_carries_the_per_suite_breakdown(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import (
            _benchmark_detail_lines,
        )

        righe = _benchmark_detail_lines({
            "suites": {"mmlu": {"passed": 11, "total": 14},
                       "gsm8k": {"passed": 9, "total": 9}},
            "protocols": {"mmlu": {"mode": "letter_logprob"}},
            "reproducible_hash": "SHA256-ABC", "temperature": 0.0, "seed": 42,
            "dataset_complete": True, "completed": True,
        })
        testo = "\n".join(righe)
        # Un punteggio complessivo da solo non e' confrontabile con niente.
        self.assertIn("MMLU", testo)
        self.assertIn("79%", testo)
        self.assertIn("letter_logprob", testo)
        self.assertIn("SHA256-ABC", testo)

    def test_a_partial_dataset_is_declared_on_the_card(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import (
            _benchmark_detail_lines,
        )

        testo = "\n".join(_benchmark_detail_lines(
            {"dataset_complete": False, "completed": True}, italiano=True))
        self.assertIn("porzione del dataset", testo)

    def test_nothing_is_invented_when_there_is_no_report(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import (
            _benchmark_detail_lines,
        )
        self.assertEqual(_benchmark_detail_lines(None), [])


class TestPublicationLink(unittest.TestCase):
    """Il legame fra il modello sul disco e il repository che lo ospita.

    Senza, la pubblicazione era senza memoria: per aggiornare il paper bisognava
    ricordarsi a mano dove si era pubblicato, e riscriverlo sbagliato non dava
    errore — creava un secondo repository.
    """

    def _registro(self):
        from core.modules.sigma_model_hub.backend import publications

        cartella = tempfile.mkdtemp()
        return publications, mock.patch.object(
            publications, "_registro_path",
            return_value=os.path.join(cartella, "pub.json"))

    def test_a_model_id_is_not_mistaken_for_a_path(self):
        from core.modules.sigma_model_hub.backend.publications import _normalizza

        # `autore/modello` contiene una barra ed e' il modo standard di nominare
        # un modello, non un percorso: tenerne solo la coda faceva finire sulla
        # stessa riga due modelli di autori diversi.
        self.assertEqual(_normalizza("autore/modello"), "autore/modello")
        self.assertEqual(_normalizza("google--Gemma-4"), "google/gemma-4")

    def test_publishing_records_where_it_went(self):
        publications, patch = self._registro()
        with patch:
            publications.record_publication("google--gemma-4", "sigmanih/g4")
            riga = publications.get_publication("google/gemma-4")
        self.assertEqual(riga["repo_id"], "sigmanih/g4")
        self.assertEqual(riga["publish_count"], 1)

    def test_publishing_twice_updates_the_same_row(self):
        publications, patch = self._registro()
        with patch:
            publications.record_publication("m", "autore/uno")
            publications.record_publication("m", "autore/due")
            righe = publications.all_publications()
            riga = publications.get_publication("m")
        # Un modello sta in un repository: se cambia, e' quello nuovo che conta.
        self.assertEqual(len(righe), 1)
        self.assertEqual(riga["repo_id"], "autore/due")
        self.assertEqual(riga["publish_count"], 2)

    def test_the_link_follows_a_local_rename(self):
        publications, patch = self._registro()
        with patch:
            publications.record_publication("vecchio--nome", "autore/repo")
            publications.rename_local_reference("vecchio--nome", "nuovo--nome")
            self.assertIsNone(publications.get_publication("vecchio/nome"))
            self.assertEqual(publications.get_publication("nuovo/nome")["repo_id"],
                             "autore/repo")

    def test_forgetting_the_link_touches_nothing_on_hugging_face(self):
        publications, patch = self._registro()
        with patch:
            publications.record_publication("m", "autore/repo")
            self.assertTrue(publications.forget_publication("m"))
            self.assertIsNone(publications.get_publication("m"))
            self.assertFalse(publications.forget_publication("m"))

    def test_updating_a_card_needs_a_known_repository(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import update_model_card

        publications, patch = self._registro()
        with patch:
            esito = update_model_card("mai-pubblicato")
        self.assertFalse(esito["success"])
        self.assertIn("non risulta pubblicato", esito["error"])

    def test_update_repo_id_updates_registry_and_card(self):
        publications, patch = self._registro()
        with patch:
            publications.record_publication("Qwen--Qwen3-0.6B-GGUF-Q4_K_S", "sigmanih/Qwen-Qwen3-0", model_card="# ⚡ Qwen-Qwen3-0")
            updated = publications.update_repo_id("sigmanih/Qwen-Qwen3-0", "sigmanih/Qwen-Qwen3-0.6B-GGUF-Q4_K_S")
            self.assertTrue(updated)
            pub = publications.get_publication("Qwen/Qwen3-0.6B-GGUF-Q4_K_S")
            self.assertEqual(pub["repo_id"], "sigmanih/Qwen-Qwen3-0.6B-GGUF-Q4_K_S")
            self.assertIn("Qwen-Qwen3-0.6B-GGUF-Q4_K_S", pub["model_card"])

    def test_model_card_title_handles_decimal_parameter_models(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import generate_model_card
        card = generate_model_card("Qwen--Qwen3-0.6B-GGUF-Q4_K_S", "sigmanih/Qwen-Qwen3-0.6B-GGUF-Q4_K_S")
        self.assertIn("# ⚡ Qwen-Qwen3-0.6B-GGUF-Q4_K_S", card)
        self.assertIn("sigmanih/Qwen-Qwen3-0.6B-GGUF-Q4_K_S", card)



class TestHonestSpeedReporting(unittest.TestCase):
    """Due velocità diverse non possono comparire come se fossero la stessa."""

    def test_the_card_no_longer_invents_speeds_for_other_hardware(self):
        import inspect
        from core.modules.sigma_model_hub.backend import uploader_engine

        sorgente = inspect.getsource(uploader_engine.generate_model_card)
        # Moltiplicare una misura locale per fattori inventati (1.8, 2.5...) e
        # presentarla come "Estimated Speed" per una RTX 4090 non e' una stima:
        # e' un numero senza origine. Diceva a chi legge che il proprio hardware
        # avrebbe fatto 96-131 tok/s mentre ne faceva sessanta.
        for fabbricato in ("* 1.8", "* 2.5", "* 1.1", "* 1.5", "tier1_speed"):
            self.assertNotIn(fabbricato, sorgente, fabbricato)
        self.assertIn("not measured", sorgente)

    def test_single_stream_and_aggregate_are_labelled_apart(self):
        import inspect
        from core.modules.sigma_model_hub.backend import uploader_engine

        sorgente = inspect.getsource(uploader_engine.generate_model_card)
        # Il totale di un run a lotti e' sempre piu' alto di quanto veda chi
        # aspetta una risposta sola: sono due misure, e vanno dette come due.
        self.assertIn("Single-stream decode", sorgente)
        self.assertIn("Aggregate throughput", sorgente)

    def test_the_run_records_the_single_stream_measurement(self):
        import inspect
        from core.modules.sigma_training_lab.training import benchmarks

        sorgente = inspect.getsource(benchmarks._run_official_benchmark)
        self.assertIn("single_stream", sorgente)
        self.assertIn("sigma_engine.benchmark", sorgente)


class TestRoutesAreRegistered(unittest.TestCase):
    """Due tabelle di rotte, e una non sapeva delle nuove.

    Gli handler esistevano, il modulo li dichiarava, e il browser riceveva 404:
    `core/api_router.py` tiene una seconda tabella e vince sulla prima. Una
    rotta aggiunta in un posto solo non arriva mai al server.
    """

    def test_every_new_model_hub_route_answers(self):
        import core.fastapi_app  # noqa: F401  (registra le rotte)
        from core.fastapi_app import FastAPIHandlerAdapter

        attese = (
            "/api/models/speedtest",
            "/api/models/local/rename",
            "/api/models/hf/repo/status",
            "/api/models/hf/repo/rename",
            "/api/models/hf/repo/attach",
            "/api/models/hf/repo/discover",
            "/api/models/hf/card/update",
            "/api/models/publication/forget",
        )
        registrate = FastAPIHandlerAdapter._POST_HANDLERS
        mancanti = [p for p in attese if p not in registrate]
        self.assertEqual(mancanti, [], f"rotte non registrate: {mancanti}")

    def test_the_handler_exists_for_each_registered_name(self):
        import core.fastapi_app  # noqa: F401
        from core.fastapi_app import FastAPIHandlerAdapter

        # Una rotta che punta a un nome inesistente da' 500 invece di 404, e si
        # scopre solo premendo il pulsante.
        for percorso, nome in FastAPIHandlerAdapter._POST_HANDLERS.items():
            if percorso.startswith("/api/models/"):
                self.assertTrue(hasattr(FastAPIHandlerAdapter, nome),
                                f"{percorso} -> {nome} non esiste")

    def test_both_route_tables_agree_on_the_model_hub(self):
        import inspect
        from core.modules.sigma_model_hub.backend import handlers
        from core import api_router

        modulo = inspect.getsource(handlers.register_routes)
        maestra = inspect.getsource(api_router)
        for percorso in ("/api/models/speedtest", "/api/models/hf/repo/attach"):
            self.assertIn(percorso, modulo, f"{percorso} manca nel modulo")
            self.assertIn(percorso, maestra, f"{percorso} manca in api_router")


class TestAttachExistingRepository(unittest.TestCase):
    """Cio' che era pubblicato prima del registro deve poter essere ritrovato."""

    def test_attaching_verifies_the_repository_first(self):
        from unittest import mock
        from core.modules.sigma_model_hub.backend import uploader_engine

        with mock.patch.object(uploader_engine, "hf_repo_status",
                               return_value={"success": True, "exists": False}):
            esito = uploader_engine.attach_publication("m", "autore/inesistente")
        # Collegare un nome sbagliato non darebbe errore subito: lo darebbe al
        # primo aggiornamento di scheda, mandato altrove.
        self.assertFalse(esito["success"])
        self.assertIn("non esiste", esito["error"])

    def test_attaching_needs_both_sides(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import attach_publication

        self.assertFalse(attach_publication("", "autore/repo")["success"])
        self.assertFalse(attach_publication("m", "")["success"])


class TestCardProvenance(unittest.TestCase):
    """Un repository senza provenienza sembra un modello proprio."""

    def test_the_base_model_is_derived_from_the_folder(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import (
            _base_model_da_cartella,
        )
        # `sigmanih/gemma-4-12B-it-GGUF-Q4_K_M` senza `base_model` sembra un
        # modello di sigmanih e non una quantizzazione di quello di Google, e
        # Hugging Face non lo collega all'albero del modello originale.
        self.assertEqual(
            _base_model_da_cartella("store/models/google--gemma-4-12B-it-GGUF-Q4_K_M"),
            "google/gemma-4-12B-it")
        self.assertEqual(
            _base_model_da_cartella("store/models/Qwen--Qwen3-0.6B"), "Qwen/Qwen3-0.6B")

    def test_an_undeducible_origin_is_left_blank(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import (
            _base_model_da_cartella,
        )
        # Dichiarare un `base_model` sbagliato attribuisce la paternità a chi
        # non c'entra: peggio che non dichiararne nessuno.
        self.assertEqual(_base_model_da_cartella("store/models/sigma-alpaca-3b-gguf"), "")
        self.assertEqual(_base_model_da_cartella(""), "")

    def test_the_licence_is_not_asserted_without_knowing_it(self):
        import inspect
        from core.modules.sigma_model_hub.backend import uploader_engine

        sorgente = inspect.getsource(uploader_engine.generate_model_card)
        # `license: apache-2.0` scritto fisso su una ridistribuzione di Gemma —
        # che ha la propria licenza — è un'affermazione legale sbagliata su un
        # file che si sta distribuendo.
        self.assertNotIn('"license: apache-2.0"', sorgente)
        self.assertIn("card_license", sorgente)


class TestWeightFormatTags(unittest.TestCase):
    """I tag dicono a chi cerca con che cosa si carica il modello."""

    def _tags(self, cartella):
        from core.modules.sigma_model_hub.backend.uploader_engine import generate_model_card

        scheda = generate_model_card(cartella, "tizio/prova")
        blocco = scheda[scheda.index("tags:"):scheda.index("pipeline_tag")]
        return [r.strip("- ").strip() for r in blocco.splitlines()[1:] if r.strip()]

    def test_a_gguf_is_not_announced_as_safetensors(self):
        cartella = tempfile.mkdtemp()
        with open(os.path.join(cartella, "modello.Q4_K_M.gguf"), "wb") as fh:
            fh.write(b"GGUF" + bytes(64))
        tag = self._tags(cartella)
        self.assertIn("gguf", tag)
        for sbagliato in ("safetensors", "transformers"):
            self.assertNotIn(sbagliato, tag)

    def test_safetensors_keeps_its_own_tags(self):
        cartella = tempfile.mkdtemp()
        with open(os.path.join(cartella, "model.safetensors"), "wb") as fh:
            fh.write(bytes(64))
        tag = self._tags(cartella)
        self.assertIn("safetensors", tag)
        self.assertNotIn("gguf", tag)

    def test_an_unrecognised_folder_declares_no_format(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import _detect_model_config

        cartella = tempfile.mkdtemp()
        with open(os.path.join(cartella, "leggimi.txt"), "w") as fh:
            fh.write("niente pesi qui")

        # Il nome di una cartella può dire "gguf", ma non può dire
        # "safetensors": era una supposizione presentata come un fatto, e sulla
        # scheda diventava `tags: safetensors, transformers, pytorch` su una
        # cartella in cui non era stato trovato un solo file di pesi.
        self.assertEqual(_detect_model_config(cartella)["format"], "Sconosciuto")
        tag = self._tags(cartella)
        for inventato in ("safetensors", "gguf", "pytorch", "transformers"):
            self.assertNotIn(inventato, tag)

    def test_a_missing_path_invents_nothing(self):
        from core.modules.sigma_model_hub.backend.uploader_engine import _detect_model_config

        cfg = _detect_model_config("/percorso/che/non/esiste")
        self.assertEqual(cfg["format"], "Sconosciuto")
        self.assertEqual(cfg["quantization"], "sconosciuta")


class TestBenchmarkExtensionAndSuiteFiltering(unittest.TestCase):
    def test_store_read_page_suite_filtering(self):
        from core.modules.sigma_training_lab.training import benchmark_store as store

        job_id = f"test_filter_{uuid.uuid4().hex[:8]}"
        items = [
            {"id": "item_1", "suite": "mmlu", "suite_name": "MMLU", "verdict": "pass", "prompt": "MMLU Q1"},
            {"id": "item_2", "suite": "arc", "suite_name": "ARC", "verdict": "fail", "prompt": "ARC Q1"},
            {"id": "item_3", "suite": "mbpp", "suite_name": "MBPP", "verdict": "pass", "prompt": "MBPP Q1"},
            {"id": "item_4", "suite": "mmlu_pro", "suite_name": "MMLU-Pro", "verdict": "pass", "prompt": "MMLU-Pro Q1"},
        ]
        store.append_results(job_id, items)

        try:
            # 1. Read all
            all_page = store.read_page(job_id, page=1, page_size=10, suite="all")
            self.assertEqual(all_page["total"], 4)

            # 2. Filter by exact suite
            mmlu_page = store.read_page(job_id, page=1, page_size=10, suite="mmlu")
            self.assertEqual(mmlu_page["total"], 1)
            self.assertEqual(mmlu_page["results"][0]["id"], "item_1")

            # 3. Filter with case/hyphen variation
            mmlu_pro_page = store.read_page(job_id, page=1, page_size=10, suite="MMLU-Pro")
            self.assertEqual(mmlu_pro_page["total"], 1)
            self.assertEqual(mmlu_pro_page["results"][0]["id"], "item_4")

            # 4. Get evaluated item ids
            ids = store.get_evaluated_item_ids(job_id)
            self.assertEqual(ids, {"item_1", "item_2", "item_3", "item_4"})

            # 5. Suite breakdown
            breakdown = store.suite_breakdown(job_id)
            self.assertIn("mmlu", breakdown)
            self.assertIn("arc", breakdown)
            self.assertIn("mbpp", breakdown)
            self.assertEqual(breakdown["mmlu"]["passed"], 1)
            self.assertEqual(breakdown["arc"]["failed"], 1)

            # 6. Test read_all_results and replace_job_results
            all_res = store.read_all_results(job_id)
            self.assertEqual(len(all_res), 4)

            # Update arc item from fail to pass
            updated = []
            for r in all_res:
                if r["id"] == "item_2":
                    r = dict(r, verdict="pass", passed=True)
                updated.append(r)
            store.replace_job_results(job_id, updated)

            reloaded = store.read_all_results(job_id)
            self.assertEqual(len(reloaded), 4)
            arc_item = next(r for r in reloaded if r["id"] == "item_2")
            self.assertEqual(arc_item["verdict"], "pass")
            self.assertTrue(arc_item["passed"])

            new_breakdown = store.suite_breakdown(job_id)
            self.assertEqual(new_breakdown["arc"]["passed"], 1)
            self.assertEqual(new_breakdown["arc"]["failed"], 0)
        finally:
            store.delete_results(job_id)


if __name__ == "__main__":
    unittest.main()
