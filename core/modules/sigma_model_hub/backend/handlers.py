# ==============================================================================
# core/modules/sigma_model_hub/backend/handlers.py
# HTTP Route Handlers for Hugging Face Model Hub & SigmaEngine Deployment
# ==============================================================================
from __future__ import annotations
import os
import json
import urllib.parse
from core.net_utils import safe_urlopen
from core import paths
from core.logger import get_logger
from .hf_client import (search_hf_models, get_hf_model_details, get_effective_hf_token,
                        persist_hf_token, resolve_hf_token)
from .downloader_engine import downloader_manager, DEFAULT_MODELS_DIR
try:
    from .uploader_engine import uploader_manager
except Exception as _up_err:
    uploader_manager = None
from .model_inventory import (scan_local_models, deploy_model_to_sigma_engine,
                            unload_sigma_engine_model, delete_local_model)

log = get_logger(__name__)

_ROOT_DIR = str(paths.project_root())
_CONFIG_PATH = str(paths.model_hub_config_file())


def _load_hub_config() -> dict:
    from .hf_client import get_effective_hf_token
    cfg = {
        "models_dir": DEFAULT_MODELS_DIR,
        "hf_token": "",
        "auto_deploy_on_download": True,
        "preferred_quantization": "Q4_K_M"
    }
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception:
            pass

    # If hf_token is empty in config, check env vars or cached token
    if not cfg.get("hf_token"):
        effective = get_effective_hf_token()
        if effective:
            cfg["hf_token"] = effective

    return cfg


def _save_hub_config(cfg: dict) -> dict:
    existing = _load_hub_config()
    if isinstance(cfg, dict):
        existing.update(cfg)
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    return existing


def handle_models_hf_search(self):
    """GET /api/models/hf/search — Cerca modelli su Hugging Face con filtri multi-dimensionali e paginazione."""
    try:
        query = ""
        category = "all"
        size_bracket = "all"
        param_bracket = "all"
        format_filter = "all"
        quant_filter = "all"
        sort = "downloads"
        official_only = False
        provider = "all"
        cursor = None
        page = 1
        limit = 30

        # Parse query params if available
        if hasattr(self, 'path') and '?' in self.path:
            qs = self.path.split('?', 1)[1]
            params = urllib.parse.parse_qs(qs)
            query = params.get('q', [''])[0]
            category = params.get('category', ['all'])[0]
            size_bracket = params.get('size_bracket', ['all'])[0]
            param_bracket = params.get('param_bracket', ['all'])[0]
            format_filter = params.get('format_filter', ['all'])[0]
            quant_filter = params.get('quant_filter', ['all'])[0]
            sort = params.get('sort', ['downloads'])[0]
            official_only = params.get('official_only', ['false'])[0].lower() in ['true', '1', 'yes']
            provider = params.get('provider', ['all'])[0]
            cursor = params.get('cursor', [''])[0] or None
            page = int(params.get('page', ['1'])[0])
            limit = int(params.get('limit', ['30'])[0])

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None
        data = search_hf_models(
            query=query,
            category=category,
            size_bracket=size_bracket,
            param_bracket=param_bracket,
            format_filter=format_filter,
            quant_filter=quant_filter,
            sort=sort,
            official_only=official_only,
            provider=provider,
            cursor=cursor,
            page=page,
            limit=limit,
            hf_token=token
        )

        self.send_json_response({
            "success": True,
            "results": data.get("results", []),
            "total": data.get("total", 0),
            "page": page,
            "next_cursor": data.get("next_cursor"),
            "has_more": data.get("has_more", False)
        })

    except Exception as e:
        log.error("Error in handle_models_hf_search: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)




def handle_models_hf_details(self):
    """GET /api/models/hf/details — Restituisce dettagli e lista file del modello HF."""
    try:
        model_id = ""
        if hasattr(self, 'path') and '?' in self.path:
            qs = self.path.split('?', 1)[1]
            params = urllib.parse.parse_qs(qs)
            model_id = params.get('model_id', [''])[0]

        if not model_id:
            self.send_json_response({"success": False, "error": "model_id mancante"}, 400)
            return

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None
        data = get_hf_model_details(model_id=model_id, hf_token=token)
        self.send_json_response(data)
    except Exception as e:
        log.error("Error in handle_models_hf_details: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_start(self):
    """POST /api/models/hf/download/start — Avvia download in background."""
    try:
        body = self.read_json_body()
        model_id = body.get("model_id")
        filename = body.get("filename")
        download_url = body.get("download_url")

        if not model_id or not filename:
            self.send_json_response({"success": False, "error": "model_id e filename obbligatori"}, 400)
            return

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None

        task = downloader_manager.start_download(
            model_id=model_id,
            filename=filename,
            download_url=download_url,
            hf_token=token
        )
        self.send_json_response({"success": True, "task": task})
    except Exception as e:
        log.error("Error in handle_models_hf_download_start: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_repo(self):
    """POST /api/models/hf/download/repo — Scarica l'intero modello con tutti i suoi file e shard."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model_id = body.get("model_id")
        files = body.get("files")

        if not model_id:
            self.send_json_response({"success": False, "error": "model_id obbligatorio"}, 400)
            return

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None

        task = downloader_manager.start_repo_download(
            model_id=model_id,
            files_list=files,
            hf_token=token
        )
        self.send_json_response({"success": True, "task": task})
    except Exception as e:
        log.error("Error in handle_models_hf_download_repo: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)



def handle_models_hf_downloads_list(self):
    """GET /api/models/hf/downloads — Restituisce tutti i download attivi e completati."""
    try:
        tasks = downloader_manager.get_tasks()
        self.send_json_response({"success": True, "downloads": tasks})
    except Exception as e:
        log.error("Error in handle_models_hf_downloads_list: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_cancel(self):
    """POST /api/models/hf/download/cancel — Annulla un download attivo."""
    try:
        body = self.read_json_body()
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = downloader_manager.cancel_download(task_id)
        self.send_json_response({"success": success, "message": f"Task {task_id} annullato." if success else "Task non trovato o già terminato."})
    except Exception as e:
        log.error("Error in handle_models_hf_download_cancel: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_pause(self):
    """POST /api/models/hf/download/pause — Mette in pausa un download attivo preservando i byte su disco."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = downloader_manager.pause_download(task_id)
        self.send_json_response({"success": success, "message": f"Download #{task_id} messo in pausa." if success else "Task non attivo o già terminato."})
    except Exception as e:
        log.error("Error in handle_models_hf_download_pause: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_resume(self):
    """POST /api/models/hf/download/resume — Riprende un download in pausa o fallito."""
    return handle_models_hf_download_retry(self)


def handle_models_hf_download_retry(self):
    """POST /api/models/hf/download/retry — Riprende/Riprova un download interrotto, in pausa o fallito."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        task = downloader_manager.retry_download(task_id)
        if task:
            self.send_json_response({"success": True, "task": task, "message": f"Download #{task_id} ripreso con successo."})
        else:
            self.send_json_response({"success": False, "error": f"Task #{task_id} non trovato."}, 404)
    except Exception as e:
        log.error("Error in handle_models_hf_download_retry: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_remove(self):
    """POST /api/models/hf/download/remove — Rimuove un task dalla lista e opzionalmente da disco."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        delete_from_disk = bool(body.get("delete_from_disk", False))
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = downloader_manager.remove_task(task_id, delete_from_disk=delete_from_disk)
        self.send_json_response({"success": success, "message": f"Task #{task_id} rimosso con successo." if success else "Task non trovato."})
    except Exception as e:
        log.error("Error in handle_models_hf_download_remove: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_downloads_clear(self):
    """POST /api/models/hf/downloads/clear — Rimuove tutti i download completati, falliti o annullati dalla cronologia."""
    try:
        cleared = downloader_manager.clear_completed_tasks()
        self.send_json_response({"success": True, "cleared_count": cleared, "message": f"{cleared} download rimossi dalla cronologia."})
    except Exception as e:
        log.error("Error in handle_models_hf_downloads_clear: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_whoami(self):
    """GET /api/models/hf/whoami — Verifica il token HF e restituisce username, organizzazioni e permessi di scrittura."""
    try:
        if uploader_manager is None:
            self.send_json_response({"authenticated": False, "error": "Modulo Hugging Face uploader non disponibile."}, 500)
            return

        token = None
        if hasattr(self, 'path') and '?' in self.path:
            qs = self.path.split('?', 1)[1]
            params = urllib.parse.parse_qs(qs)
            token = params.get('token', [None])[0]

        info = uploader_manager.get_whoami(token=token)
        self.send_json_response(info)
    except Exception as e:
        log.error("Error in handle_models_hf_whoami: %s", e)
        self.send_json_response({"authenticated": False, "error": str(e)}, 500)


def handle_models_hf_upload(self):
    """POST /api/models/hf/upload — Avvia il caricamento di un modello locale su Hugging Face Hub."""
    try:
        if uploader_manager is None:
            self.send_json_response({"success": False, "error": "Modulo Hugging Face uploader non disponibile."}, 500)
            return

        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        local_path = body.get("local_path") or body.get("path") or body.get("filename")
        repo_id = body.get("repo_id")
        private = bool(body.get("private", False))
        commit_message = body.get("commit_message", "Upload model via Sigma Studio")
        model_card = body.get("model_card")
        token = body.get("token")

        if not local_path:
            self.send_json_response({"success": False, "error": "local_path mancante"}, 400)
            return

        if not repo_id:
            self.send_json_response({"success": False, "error": "repo_id mancante (formato 'username/repo-name')"}, 400)
            return

        # Resolve local path if relative
        if not os.path.isabs(local_path):
            cfg = _load_hub_config()
            models_dir = cfg.get("models_dir") or DEFAULT_MODELS_DIR
            candidate = os.path.join(models_dir, local_path)
            if os.path.exists(candidate):
                local_path = candidate

        res = uploader_manager.start_upload(
            local_path=local_path,
            repo_id=repo_id,
            private=private,
            commit_message=commit_message,
            model_card=model_card,
            token=token
        )
        status_code = 200 if res.get("success") else 400
        self.send_json_response(res, status_code)
    except Exception as e:
        log.error("Error in handle_models_hf_upload: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_upload_tasks(self):
    """GET /api/models/hf/upload/tasks — Restituisce l'elenco dei task di upload verso Hugging Face."""
    try:
        if uploader_manager is None:
            self.send_json_response({"success": True, "tasks": []})
            return

        tasks = uploader_manager.list_tasks()
        self.send_json_response({"success": True, "tasks": tasks})
    except Exception as e:
        log.error("Error in handle_models_hf_upload_tasks: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_upload_cancel(self):
    """POST /api/models/hf/upload/cancel — Annulla un caricamento attivo verso Hugging Face."""
    try:
        if uploader_manager is None:
            self.send_json_response({"success": False, "error": "Modulo uploader non disponibile."}, 500)
            return

        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = uploader_manager.cancel_upload(task_id)
        self.send_json_response({"success": success, "message": f"Task #{task_id} annullato." if success else "Task non trovato o non attivo."})
    except Exception as e:
        log.error("Error in handle_models_hf_upload_cancel: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_upload_remove(self):
    """POST /api/models/hf/upload/remove — Rimuove un task completato o fallito dalla cronologia."""
    try:
        if uploader_manager is None:
            self.send_json_response({"success": False, "error": "Modulo uploader non disponibile."}, 500)
            return

        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = uploader_manager.remove_task(task_id)
        self.send_json_response({"success": success, "message": f"Task #{task_id} rimosso." if success else "Task non trovato."})
    except Exception as e:
        log.error("Error in handle_models_hf_upload_remove: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_card_preview(self):
    """POST /api/models/hf/card/preview — Genera un'anteprima completa della Model Card (README.md) bilingue."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        local_path = body.get("local_path") or body.get("path") or body.get("filename") or ""
        repo_id = body.get("repo_id") or "sigmanih/my-model"
        custom_notes = body.get("custom_notes")
        include_benchmarks = bool(body.get("include_benchmarks", True))
        include_hardware = bool(body.get("include_hardware", True))
        benchmark_summary = body.get("benchmark_summary")

        # Resolve local path if relative
        if local_path and not os.path.isabs(local_path):
            cfg = _load_hub_config()
            models_dir = cfg.get("models_dir") or DEFAULT_MODELS_DIR
            candidate = os.path.join(models_dir, local_path)
            if os.path.exists(candidate):
                local_path = candidate

        from .uploader_engine import generate_model_card
        card_md = generate_model_card(
            local_path=local_path,
            repo_id=repo_id,
            benchmark_summary=benchmark_summary,
            include_benchmarks=include_benchmarks,
            include_hardware=include_hardware,
            custom_notes=custom_notes
        )
        self.send_json_response({"success": True, "card_markdown": card_md})
    except Exception as e:
        log.error("Error in handle_models_hf_card_preview: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)



def handle_models_local_list(self):
    """GET /api/models/local/list — Restituisce elenco modelli scaricati in locale con metriche benchmark."""
    try:
        cfg = _load_hub_config()
        custom_dir = cfg.get("models_dir")
        models = scan_local_models(custom_dir=custom_dir)

        # I referti dei benchmark li legge il Training Lab, che e' il modulo che
        # li produce: qui si chiedono, non si interpretano. Il Model Hub deve
        # funzionare anche senza quel modulo installato — i moduli sono
        # sganciabili — quindi la sua assenza significa "nessun benchmark", non
        # un errore.
        from core.modules.sigma_model_hub.backend import publications as pubblicazioni

        referti = {}
        try:
            from core.modules.sigma_training_lab.training.model_scores import (
                normalizza, scores_by_model,
            )
            # Con il dettaglio per suite: e' il parametro che serve davvero a
            # scegliere un modello per un compito, e un punteggio complessivo
            # da solo non dice quali materie regge e quali no.
            referti = scores_by_model(include_suites=True)
        except Exception as err:
            log.debug("Referti di benchmark non disponibili: %s", err)
            normalizza = None

        for m in models:
            summary = None
            if normalizza is not None:
                chiave = normalizza(m.get("model_id") or m.get("filename") or "")
                summary = referti.get(chiave)
                if summary is None and chiave:
                    # Solo il nome finale, quando una delle due forme non porta
                    # l'autore. Mai per sottostringa: e' cosi' che un
                    # checkpoint ereditava il punteggio della propria
                    # quantizzazione, che e' un altro artefatto.
                    coda = chiave.split("/")[-1]
                    summary = next((r for k, r in referti.items()
                                    if k.split("/")[-1] == coda), None)
            m["benchmark_summary"] = summary or {"has_benchmarks": False}
            # Dove questo modello e' gia' pubblicato, se lo e'. Serve a poterlo
            # aggiornare senza riscrivere a mano l'identificativo del
            # repository — che riscritto sbagliato non da' errore, crea un
            # secondo repository.
            try:
                m["publication"] = pubblicazioni.get_publication(
                    m.get("path") or m.get("model_id") or m.get("filename") or "")
            except Exception:
                m["publication"] = None

            # Accurate publisher & attribution resolution
            pub = m.get("publication")
            repo_id = (pub.get("repo_id") if isinstance(pub, dict) else "") or ""
            raw_author = m.get("author") or ""
            raw_name = m.get("clean_name") or m.get("display_name") or m.get("filename") or ""

            if repo_id.lower().startswith("sigmanih/") or raw_author.lower() == "sigmanih" or "sigmanih" in raw_name.lower():
                m["author"] = "sigmanih"
                m["publisher"] = "sigmanih"
                m["is_official"] = True
                m["is_sigmanih"] = True
            elif repo_id and "/" in repo_id:
                m["publisher"] = repo_id.split("/")[0]
                m["author"] = repo_id.split("/")[0]
            else:
                m["publisher"] = raw_author or "Altro"

            # Re-evaluate family and category with full publication context
            from core.modules.sigma_model_hub.backend.model_inventory import detect_family_and_category
            family, category = detect_family_and_category(
                name=raw_name,
                architecture=m.get("architecture") or "",
                author=m.get("publisher") or m.get("author") or "",
                is_multimodal=m.get("is_multimodal", False)
            )
            m["family"] = family
            m["category"] = category

        self.send_json_response({"success": True, "models": models})
    except Exception as e:
        log.error("Error in handle_models_local_list: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_local_delete(self):
    """POST /api/models/local/delete — Elimina un modello scaricato dallo storage locale."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model_path = body.get("model_path") or body.get("path") or body.get("model_id") or body.get("filename")
        if not model_path:
            self.send_json_response({"success": False, "error": "model_path o model_id mancante"}, 400)
            return

        cfg = _load_hub_config()
        custom_dir = cfg.get("models_dir")
        res = delete_local_model(model_path, custom_dir=custom_dir)
        status_code = 200 if res.get("success") else 400
        self.send_json_response(res, status_code)
    except Exception as e:
        log.error("Error in handle_models_local_delete: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_speedtest(self):
    """POST /api/models/speedtest — Prova di inferenza vera su questo hardware.

    Due cose insieme, perche' separate si prestano a essere confuse: la misura
    di velocita' e la risposta che il modello ha effettivamente prodotto. Un
    numero senza la risposta si puo' leggere come si vuole; la risposta accanto
    dice a cosa quel numero si riferisce.

    La velocita' riportata e' quella di **una richiesta alla volta**, che e' cio'
    che sente chi chatta — non il throughput aggregato di una valutazione a
    lotti, che con piu' richieste in volo e' sempre piu' alto.
    """
    import time as _time
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model = body.get("model") or body.get("model_id")
        prompt = (body.get("prompt") or
                  "Spiega in tre frasi perché il cielo è azzurro.").strip()
        budget = max(16, min(int(body.get("max_tokens") or 96), 512))

        from core.engine.unified_runtime import sigma_engine
        from core.engine import evaluation

        # 1. La sonda del motore: prefill e decode separati, cronometrati da chi
        #    li esegue. Sono le due fasi che si sentono come cose diverse — la
        #    pausa prima della prima parola, e il ritmo delle successive.
        sonda = sigma_engine.benchmark(prompt_tokens=128, decode_tokens=64,
                                       model_name=model)
        if not sonda.get("success"):
            self.send_json_response(
                {"success": False, "error": sonda.get("error", "Sonda non riuscita")},
                400)
            return

        # 2. Una risposta vera, cronometrata dall'esterno come la vede l'utente.
        inizio = _time.perf_counter()
        risposta = evaluation.complete(
            [{"role": "user", "content": prompt}],
            model_name=model, max_tokens=budget, thinking=None,
        )
        trascorso = max(_time.perf_counter() - inizio, 1e-3)

        hardware = {}
        try:
            profilo = sigma_engine.hardware_profile or {}
            schede = profilo.get("accelerators") or []
            if schede:
                hardware = {"device": schede[0].get("name", ""),
                            "vram_gb": schede[0].get("total_vram_gb", 0)}
        except Exception as err:
            log.debug("Profilo hardware non disponibile: %s", err)

        self.send_json_response({
            "success": True,
            "model": model or sigma_engine.loaded_model_name,
            "backend": sonda.get("backend", ""),
            "hardware": hardware,
            # Le due fasi, misurate dal motore.
            "prefill_tok_s": sonda.get("prefill_tok_s", 0),
            "decode_tok_s": sonda.get("decode_tok_s", 0),
            "prefill_ms": sonda.get("prefill_ms", 0),
            # La risposta vera e il suo tempo, cronometrati da fuori.
            "prompt": prompt,
            "answer": risposta.text,
            "answer_tokens": risposta.tokens,
            "answer_seconds": round(trascorso, 2),
            "answer_tok_s": round(risposta.tokens / trascorso, 2) if risposta.tokens else 0,
            "ttft_ms": round(risposta.ttft_ms, 1),
            "error": risposta.error,
        })
    except Exception as e:
        log.error("Error in handle_models_speedtest: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_local_rename(self):
    """POST /api/models/local/rename — Rinomina un modello sul disco."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        sorgente = (body.get("model_path") or body.get("model_id")
                    or body.get("path") or body.get("filename"))
        nuovo = body.get("new_name") or body.get("name")
        if not sorgente or not nuovo:
            self.send_json_response(
                {"success": False,
                 "error": "Servono il modello da rinominare e il nuovo nome"}, 400)
            return

        from core.modules.sigma_model_hub.backend.model_inventory import rename_local_model
        cfg = _load_hub_config()
        esito = rename_local_model(sorgente, nuovo, custom_dir=cfg.get("models_dir"))
        self.send_json_response(esito, 200 if esito.get("success") else 400)
    except Exception as e:
        log.error("Error in handle_models_local_rename: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_repo_discover(self):
    """POST /api/models/hf/repo/discover — Cerca i repository gia' pubblicati."""
    try:
        cfg = _load_hub_config()
        models = scan_local_models(custom_dir=cfg.get("models_dir"))
        from core.modules.sigma_model_hub.backend.uploader_engine import discover_publications
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        esito = discover_publications(models, body.get("token"))
        self.send_json_response(esito, 200 if esito.get("success") else 400)
    except Exception as e:
        log.error("Error in handle_models_hf_repo_discover: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_repo_attach(self):
    """POST /api/models/hf/repo/attach — Collega un modello a un repository esistente."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        from core.modules.sigma_model_hub.backend.uploader_engine import attach_publication
        esito = attach_publication(
            body.get("local_path") or body.get("local_ref") or body.get("model_id"),
            (body.get("repo_id") or "").strip(),
            body.get("token"),
        )
        self.send_json_response(esito, 200 if esito.get("success") else 400)
    except Exception as e:
        log.error("Error in handle_models_hf_repo_attach: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_card_update(self):
    """POST /api/models/hf/card/update — Riscrive solo la scheda su HF."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        local_ref = (body.get("local_path") or body.get("model_id")
                     or body.get("filename"))
        if not local_ref:
            self.send_json_response({"success": False,
                                     "error": "Modello non indicato"}, 400)
            return
        from core.modules.sigma_model_hub.backend.uploader_engine import update_model_card
        esito = update_model_card(
            local_ref,
            repo_id=body.get("repo_id"),
            card=body.get("card"),
            token=body.get("token"),
            custom_notes=body.get("custom_notes") or None,
            include_benchmarks=bool(body.get("include_benchmarks", True)),
            include_hardware=bool(body.get("include_hardware", True)),
        )
        self.send_json_response(esito, 200 if esito.get("success") else 400)
    except Exception as e:
        log.error("Error in handle_models_hf_card_update: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_publication_forget(self):
    """POST /api/models/publication/forget — Dimentica il legame con HF."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        from core.modules.sigma_model_hub.backend import publications
        riferimento = (body.get("local_path") or body.get("model_id")
                       or body.get("filename") or "")
        # Solo il legame locale: su Hugging Face non tocca niente, e dirlo
        # conta perche' "dimentica" accanto a un repository si puo' leggere
        # come "cancella".
        self.send_json_response({"success": True,
                                 "forgotten": publications.forget_publication(riferimento),
                                 "note": "Il repository su Hugging Face resta intatto."})
    except Exception as e:
        log.error("Error in handle_models_publication_forget: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_repo_status(self):
    """POST /api/models/hf/repo/status — Se il repository esiste gia' su HF."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        repo_id = (body.get("repo_id") or "").strip()
        if not repo_id:
            self.send_json_response({"success": False, "error": "repo_id mancante"}, 400)
            return
        from core.modules.sigma_model_hub.backend.uploader_engine import hf_repo_status
        self.send_json_response(hf_repo_status(repo_id, body.get("token")))
    except Exception as e:
        log.error("Error in handle_models_hf_repo_status: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_repo_rename(self):
    """POST /api/models/hf/repo/rename — Sposta un repository a un altro nome."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        from core.modules.sigma_model_hub.backend.uploader_engine import rename_hf_repo
        esito = rename_hf_repo(body.get("from_id") or body.get("repo_id"),
                               body.get("to_id") or body.get("new_repo_id"),
                               body.get("token"))
        self.send_json_response(esito, 200 if esito.get("success") else 400)
    except Exception as e:
        log.error("Error in handle_models_hf_repo_rename: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_engine_load(self):
    """POST /api/models/engine/load — Carica e attiva il modello in SigmaEngine."""
    try:
        body = self.read_json_body()
        path = body.get("model_path")
        quant = body.get("quantization")

        if not path:
            self.send_json_response({"success": False, "error": "model_path obbligatorio"}, 400)
            return

        res = deploy_model_to_sigma_engine(model_path=path, quantization=quant)
        self.send_json_response(res)
    except Exception as e:
        log.error("Error in handle_models_engine_load: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_engine_unload(self):
    """POST /api/models/engine/unload — Scarica il modello attivo da SigmaEngine."""
    try:
        res = unload_sigma_engine_model()
        self.send_json_response(res)
    except Exception as e:
        log.error("Error in handle_models_engine_unload: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_config_get(self):
    """GET /api/models/config — Restituisce impostazioni del Model Hub e stato del token HF."""
    try:
        from .hf_client import resolve_hf_token

        cfg = _load_hub_config()
        resolved = resolve_hf_token()
        self.send_json_response({
            "success": True,
            "config": cfg,
            # The tab is the only place the token is managed, so it also has to
            # show where an already-active token is coming from: an env var or
            # a huggingface-cli login is not editable from here.
            "hf_has_token": bool(resolved["token"]),
            "hf_token_source": resolved["source"],
            "hf_token_source_detail": resolved["detail"],
        })
    except Exception as e:
        log.error("Error in handle_models_config_get: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_config_save(self):
    """POST /api/models/config — Salva impostazioni del Model Hub e aggiorna i token attivi."""
    try:
        from core.model_paths import models_dir, set_models_dir

        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        if not isinstance(body, dict):
            body = {}

        saved_cfg = _save_hub_config(body)

        # Update models_dir
        new_dir = body.get("models_dir")
        if new_dir:
            resolved_dir = set_models_dir(new_dir)
            downloader_manager.set_models_dir(resolved_dir)

        # A single write path for the token: environment, every config file that
        # is read back on resolution, and the downloads already in flight, so an
        # interrupted gated download retries with the new token straight away.
        hf_token = (body.get("hf_token") or "").strip() if "hf_token" in body else (saved_cfg.get("hf_token") or "").strip()
        persist_hf_token(hf_token)
        saved_cfg["hf_token"] = hf_token

        resolved = resolve_hf_token()
        self.send_json_response({
            "success": True,
            "message": "Impostazioni e Token salvati con successo.",
            "config": saved_cfg,
            "hf_has_token": bool(resolved["token"]),
            "hf_token_source": resolved["source"],
            "hf_token_source_detail": resolved["detail"],
            "active_models_dir": models_dir(),
        })
    except Exception as e:
        log.error("Error in handle_models_config_save: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_test_connection(self):
    """GET/POST /api/models/hf/test-connection — Esegue test completo di connettività verso Hugging Face e verifica token."""
    import time
    import json
    import urllib.request
    import urllib.error

    body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
    if not isinstance(body, dict):
        body = {}
    # A GET carries no body: fall back to the token already configured, so the
    # header pill can test the connection without the settings tab being open.
    token = (body.get("hf_token") or "").strip()
    if not token:
        token = (get_effective_hf_token() or "").strip()

    t_start = time.time()
    reachability_ok = False
    latency_ms = 0
    token_valid = False
    user_info = {}
    error_detail = None

    # 1. Test basic reachability to Hugging Face API
    try:
        req = urllib.request.Request("https://huggingface.co/api/models?limit=1")
        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
        with safe_urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                reachability_ok = True
                latency_ms = round((time.time() - t_start) * 1000, 1)
    except Exception as ex:
        error_detail = f"Impossibile raggiungere i server Hugging Face: {ex}"

    if not reachability_ok:
        self.send_json_response({
            "success": False,
            "connected": False,
            "latency_ms": None,
            "token_valid": False,
            "error": error_detail or "Connessione a Hugging Face fallita. Controlla la connessione internet.",
            "message": "❌ Hugging Face non raggiungibile."
        })
        return

    # 2. Test token if present
    if token:
        try:
            req_auth = urllib.request.Request("https://huggingface.co/api/whoami-v2")
            req_auth.add_header("Authorization", f"Bearer {token}")
            req_auth.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
            with safe_urlopen(req_auth, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    token_valid = True
                    user_info = {
                        "username": data.get("name") or data.get("fullname") or "Utente HF",
                        "email": data.get("email") or "",
                        "type": data.get("type") or "user",
                        "orgs": [o.get("name") for o in data.get("orgs", []) if o.get("name")]
                    }
        except urllib.error.HTTPError as http_err:
            if http_err.code in (401, 403):
                error_detail = "Token Hugging Face non valido o revocato (HTTP 401 Unauthorized)."
            else:
                error_detail = f"Errore verifica token: HTTP {http_err.code}"
        except Exception as ex:
            error_detail = f"Errore verifica token: {ex}"
    else:
        error_detail = "Nessun token configurato (download anonimo con velocità ridotta ~50KB/s e senza accesso a modelli Gated come Llama)."

    msg = f"✅ Connessione a Hugging Face attiva ({latency_ms}ms)."
    if token_valid:
        msg += f" Autenticato come @{user_info.get('username')}."
    else:
        msg += f" {error_detail}"

    self.send_json_response({
        "success": True,
        "connected": True,
        "latency_ms": latency_ms,
        "token_valid": token_valid,
        "token_configured": bool(token),
        "user_info": user_info,
        "error": error_detail if not token_valid else None,
        "message": msg
    })


def handle_models_hf_token_test(self):
    """POST /api/models/hf/token/test — Verifica la validità del token Hugging Face contattando l'API ufficiale."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        token = (body.get("hf_token") or "").strip()
        if not token:
            from .hf_client import get_effective_hf_token
            token = get_effective_hf_token() or ""

        if not token:
            self.send_json_response({"success": False, "error": "Nessun token inserito da verificare."}, 400)
            return

        import urllib.request
        import json
        req = urllib.request.Request("https://huggingface.co/api/whoami-v2")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")

        try:
            with safe_urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    username = data.get("name") or data.get("fullname") or "Utente HF"
                    email = data.get("email") or ""
                    auth_type = data.get("type") or "user"
                    orgs = [o.get("name") for o in data.get("orgs", []) if o.get("name")]
                    self.send_json_response({
                        "success": True,
                        "valid": True,
                        "username": username,
                        "email": email,
                        "type": auth_type,
                        "orgs": orgs,
                        "message": f"✅ Token Hugging Face valido! Autenticato come @{username}."
                    })
                else:
                    self.send_json_response({
                        "success": False,
                        "valid": False,
                        "error": f"Risposta inattesa da Hugging Face: HTTP {resp.status}"
                    }, 400)
        except urllib.error.HTTPError as http_err:
            if http_err.code in (401, 403):
                self.send_json_response({
                    "success": False,
                    "valid": False,
                    "error": "❌ Token non valido o revocato (HTTP 401 Unauthorized). Verifica di aver copiato l'intero token 'hf_...' da huggingface.co/settings/tokens"
                }, 200)
            else:
                self.send_json_response({
                    "success": False,
                    "valid": False,
                    "error": f"Errore server Hugging Face: HTTP {http_err.code}"
                }, 200)
    except Exception as e:
        log.error("Error in handle_models_hf_token_test: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------- conversion

def handle_models_convert_info(self):
    """GET /api/models/convert/info — Modelli convertibili, tipi e stato tooling."""
    try:
        from core.engine.gguf_converter import GgufConverter
        self.send_json_response({
            "success": True,
            "models": GgufConverter.convertible_models(),
            "quantization_types": GgufConverter.quantization_types(),
            "tooling": GgufConverter.converter_status(),
            "jobs": GgufConverter.jobs(),
        })
    except Exception as e:
        log.error("Error in handle_models_convert_info: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_convert_tooling(self):
    """POST /api/models/convert/tooling — Scarica lo script di conversione.

    Con {"force": true} riscarica sopra la copia esistente. Serve perche' il
    riferimento e' un ramo che si muove: senza, la prima copia scaricata resta
    li' per sempre e le architetture uscite dopo risultano non convertibili.
    """
    try:
        from core.engine.gguf_converter import GgufConverter
        body = self.read_json_body() if hasattr(self, "read_json_body") else {}
        res = GgufConverter.fetch_converter(force=bool((body or {}).get("force")))
        self.send_json_response(res, 200 if res.get("success") else 502)
    except Exception as e:
        log.error("Error in handle_models_convert_tooling: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_convert_start(self):
    """POST /api/models/convert/start — Avvia la conversione in GGUF."""
    try:
        from core.engine.gguf_converter import GgufConverter
        body = self.read_json_body() if hasattr(self, "read_json_body") else {}
        res = GgufConverter.start(
            model_name=body.get("model"),
            quantization=body.get("quantization", "Q4_K_M"),
        )
        self.send_json_response(res, 200)
    except Exception as e:
        log.error("Error in handle_models_convert_start: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 200)


def handle_models_convert_jobs(self):
    """GET /api/models/convert/jobs — Stato delle conversioni."""
    try:
        from core.engine.gguf_converter import GgufConverter
        self.send_json_response({"success": True, "jobs": GgufConverter.jobs()})
    except Exception as e:
        log.error("Error in handle_models_convert_jobs: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_browse_dirs(self):
    """
    GET /api/models/browse — Lists subdirectories, for picking a models folder.

    A server-side browser rather than a file input: the browser only ever hands
    back a relative name for a chosen directory, and the path this setting needs
    is an absolute one on the machine running the engine.
    """
    try:
        from urllib.parse import urlparse, parse_qs
        from core.model_paths import models_dir

        query = parse_qs(urlparse(self.path).query)
        requested = (query.get("path", [""])[0] or "").strip()

        if not requested:
            current = models_dir()
            base = os.path.dirname(current) or current
        else:
            base = os.path.abspath(requested)

        if not os.path.isdir(base):
            self.send_json_response(
                {"success": False, "error": f"Non e' una cartella: {base}"}, 400)
            return

        entries = []
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            if not os.path.isdir(full) or name.startswith("."):
                continue
            entries.append({
                "name": name, "path": full, "has_models": _holds_models(full),
            })

        parent = os.path.dirname(base.rstrip(os.sep))
        self.send_json_response({
            "success": True,
            "current": base,
            "parent": parent if parent and parent != base else None,
            "entries": entries,
            "roots": _list_drive_roots(),
        })
    except Exception as e:
        log.error("Error in handle_models_browse_dirs: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def _holds_models(folder: str) -> bool:
    """
    Whether a folder is, or contains, model weights.

    A models directory holds one subfolder per model rather than loose weight
    files, so checking only its own contents marks the very folder the user is
    looking for as empty.
    """
    suffixes = (".safetensors", ".gguf", ".bin")
    try:
        names = os.listdir(folder)
    except Exception:
        return False

    if any(n.endswith(suffixes) for n in names):
        return True

    for name in names[:60]:          # one level down is enough, and bounded
        child = os.path.join(folder, name)
        if not os.path.isdir(child):
            continue
        try:
            if any(n.endswith(suffixes) for n in os.listdir(child)):
                return True
        except Exception:
            continue
    return False


def _list_drive_roots():
    """Mount points to jump to, so the user is not stuck below one root."""
    try:
        import psutil
        return [
            p.mountpoint for p in psutil.disk_partitions(all=False)
            if os.path.isdir(p.mountpoint)
        ]
    except Exception:
        return []


def register_routes(app=None) -> None:
    """Registra tutte le route HTTP di Model Hub su FastAPI / Handler Adapter."""
    get_routes = {
        '/api/models/hf/search': handle_models_hf_search,
        '/api/models/hf/details': handle_models_hf_details,
        '/api/models/hf/downloads': handle_models_hf_downloads_list,
        '/api/models/hf/test-connection': handle_models_hf_test_connection,
        '/api/models/hf/whoami': handle_models_hf_whoami,
        '/api/models/hf/upload/tasks': handle_models_hf_upload_tasks,
        '/api/models/local/list': handle_models_local_list,
        '/api/models/config': handle_models_config_get,
        '/api/models/convert/info': handle_models_convert_info,
        '/api/models/convert/jobs': handle_models_convert_jobs,
        '/api/models/browse': handle_models_browse_dirs,
    }

    post_routes = {
        '/api/models/hf/download/start': handle_models_hf_download_start,
        '/api/models/hf/download/repo': handle_models_hf_download_repo,
        '/api/models/hf/download/pause': handle_models_hf_download_pause,
        '/api/models/hf/download/resume': handle_models_hf_download_resume,
        '/api/models/hf/download/cancel': handle_models_hf_download_cancel,
        '/api/models/hf/download/retry': handle_models_hf_download_retry,
        '/api/models/hf/download/remove': handle_models_hf_download_remove,
        '/api/models/hf/downloads/clear': handle_models_hf_downloads_clear,
        '/api/models/hf/upload': handle_models_hf_upload,
        '/api/models/hf/upload/cancel': handle_models_hf_upload_cancel,
        '/api/models/hf/upload/remove': handle_models_hf_upload_remove,
        '/api/models/hf/card/preview': handle_models_hf_card_preview,
        '/api/models/hf/token/test': handle_models_hf_token_test,
        '/api/models/hf/test-connection': handle_models_hf_test_connection,
        '/api/models/local/delete': handle_models_local_delete,
        '/api/models/local/rename': handle_models_local_rename,
        '/api/models/speedtest': handle_models_speedtest,
        '/api/models/hf/repo/status': handle_models_hf_repo_status,
        '/api/models/hf/repo/discover': handle_models_hf_repo_discover,
        '/api/models/hf/repo/attach': handle_models_hf_repo_attach,
        '/api/models/hf/card/update': handle_models_hf_card_update,
        '/api/models/publication/forget': handle_models_publication_forget,
        '/api/models/hf/repo/rename': handle_models_hf_repo_rename,
        '/api/models/delete': handle_models_local_delete,
        '/api/models/engine/load': handle_models_engine_load,
        '/api/models/engine/unload': handle_models_engine_unload,
        '/api/models/config': handle_models_config_save,
        '/api/models/convert/start': handle_models_convert_start,
        '/api/models/convert/tooling': handle_models_convert_tooling,
    }

    try:
        from core.fastapi_app import FastAPIHandlerAdapter
        for path, fn in get_routes.items():
            setattr(FastAPIHandlerAdapter, fn.__name__, fn)
            FastAPIHandlerAdapter._GET_HANDLERS[path] = fn.__name__
        for path, fn in post_routes.items():
            setattr(FastAPIHandlerAdapter, fn.__name__, fn)
            FastAPIHandlerAdapter._POST_HANDLERS[path] = fn.__name__
        log.info('[sigma_model_hub] Route Model Hub registrate su FastAPIHandlerAdapter.')
    except Exception as e:
        log.warning(f'[sigma_model_hub] Avviso binding FastAPIHandlerAdapter: {e}')


def register_mcp(mcp_hub) -> None:
    """Registra il server MCP di Model Hub nell'hub MCP del kernel."""
    try:
        from .mcp_server import ModelHubMCPServer
        mcp_hub.register_server(ModelHubMCPServer)
        log.info('[sigma_model_hub] Model Hub MCP Server registrato con successo.')
    except Exception as e:
        log.warning(f'[sigma_model_hub] Model Hub MCP Server non registrato: {e}')
