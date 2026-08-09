# ==============================================================================
# core/mcp/benchmark_server.py — Benchmark MCP Server
# Suite ufficiali, run di valutazione, coda di revisione e grader riutilizzabile
# ==============================================================================
"""Espone la valutazione sui benchmark come strumenti MCP.

Si aggancia all'hub MCP già presente in Sigma (`core/mcp/mcp_hub.py`), quindi non
introduce processi ne' trasporti nuovi: e' registrazione di strumenti sullo stesso
dispatch JSON-RPC degli altri server. Il valore sta nel rendere il benchmark
guidabile da un agente — lanciare un run, leggere lo stato, e soprattutto
prelevare la coda di revisione per far giudicare a un modello i quesiti che il
parser deterministico ha lasciato in sospeso.

Il grader resta in-process (`core.training.answer_parser`): passa da qui solo
come strumento `grade_model_answer`, per chi vuole riusare le stesse regole senza
riscriverle. Spostare il parsing dietro un trasporto significherebbe pagare una
chiamata di rete per ognuno dei ~200.000 quesiti di un run integrale.
"""

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE

log = get_logger(__name__)


class BenchmarkMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="Benchmark MCP",
            version="1.0.0",
            description=("Valutazione su 11 benchmark ufficiali (MMLU, GSM8K, HumanEval, ARC, BBH...), "
                         "gestione dei dataset, coda di revisione e grader delle risposte"),
        )
        self._init_tools()
        self._init_resources()

    def _init_tools(self):
        self.register_tool(
            name="list_benchmark_suites",
            description="Elenca le 11 suite ufficiali con stato della cache e numero di quesiti.",
            input_schema={"type": "object", "properties": {}},
            handler=self._handle_list_suites,
            safety=SAFE,
            category="benchmark",
        )

        self.register_tool(
            name="download_benchmark_suite",
            description="Scarica in cache il dataset ufficiale di una suite ('all' per tutte).",
            input_schema={
                "type": "object",
                "properties": {
                    "suite": {"type": "string", "description": "ID suite (mmlu, gsm8k, humaneval... o 'all')"},
                },
                "required": ["suite"],
            },
            handler=self._handle_download_suite,
            safety=SENSITIVE,
            category="benchmark",
        )

        self.register_tool(
            name="run_benchmark",
            description="Avvia un run di valutazione su un modello Ollama. Ritorna subito con il job_id.",
            input_schema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Nome del modello Ollama"},
                    "suite": {"type": "string", "description": "ID suite o 'all'", "default": "all"},
                    "mode": {"type": "string", "enum": ["full", "sample"], "default": "sample"},
                    "samples": {"type": "integer", "description": "Quesiti da campionare in modalita' sample", "default": 25},
                    "concurrency": {
                        "type": ["integer", "string"],
                        "description": "Richieste in parallelo, oppure 'auto' per usare la capacita' misurata",
                        "default": "auto",
                    },
                },
                "required": ["model"],
            },
            handler=self._handle_run_benchmark,
            safety=SENSITIVE,
            category="benchmark",
        )

        self.register_tool(
            name="measure_parallel_capacity",
            description=("Misura quante richieste in parallelo un modello regge davvero: sale di "
                         "concorrenza finche' il throughput cresce e riporta il limite utile. "
                         "Dice anche quanti agenti concorrenti l'hardware sostiene con quel modello."),
            input_schema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Nome del modello Ollama"},
                    "levels": {
                        "type": "array", "items": {"type": "integer"},
                        "description": "Livelli di concorrenza da provare, es. [1,2,4,8]",
                    },
                    "wait": {"type": "boolean", "description": "Attendere la fine della misura", "default": True},
                },
                "required": ["model"],
            },
            handler=self._handle_measure_capacity,
            safety=SENSITIVE,
            category="benchmark",
        )

        self.register_tool(
            name="get_parallel_capacity",
            description="Stima da VRAM e ultima misura salvata della concorrenza utile di un modello.",
            input_schema={
                "type": "object",
                "properties": {"model": {"type": "string", "description": "Nome del modello Ollama"}},
                "required": ["model"],
            },
            handler=self._handle_get_capacity,
            safety=SAFE,
            category="benchmark",
        )

        self.register_tool(
            name="get_benchmark_status",
            description="Stato e metriche di un run; senza job_id restituisce il piu' recente.",
            input_schema={
                "type": "object",
                "properties": {"job_id": {"type": "string", "description": "ID del job (opzionale)"}},
            },
            handler=self._handle_get_status,
            safety=SAFE,
            category="benchmark",
        )

        self.register_tool(
            name="get_benchmark_review_queue",
            description=("Quesiti che il grader ha lasciato in sospeso — risposta duplice, non "
                         "interpretabile o errore del modello — da giudicare a parte."),
            input_schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID del job"},
                    "limit": {"type": "integer", "description": "Massimo di quesiti restituiti", "default": 50},
                },
                "required": ["job_id"],
            },
            handler=self._handle_review_queue,
            safety=SAFE,
            category="benchmark",
        )

        self.register_tool(
            name="grade_model_answer",
            description=("Applica il grader ufficiale a una singola risposta e restituisce il verdetto "
                         "(pass, fail, ambiguous, unparsable) con il motivo."),
            input_schema={
                "type": "object",
                "properties": {
                    "model_output": {"type": "string", "description": "Testo prodotto dal modello"},
                    "correct_choice": {"type": "string", "description": "Risposta corretta (lettera o valore)"},
                    "suite": {"type": "string", "description": "ID suite, determina il tipo di confronto", "default": "mmlu"},
                    "options": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Opzioni a scelta multipla, es. ['A) uno', 'B) due']",
                    },
                },
                "required": ["model_output", "correct_choice"],
            },
            handler=self._handle_grade_answer,
            safety=SAFE,
            category="benchmark",
        )

    def _init_resources(self):
        self.register_resource(
            uri="benchmark://suites",
            name="Suite di Benchmark Ufficiali",
            description="Stato della cache e conteggio quesiti delle 11 suite",
            mime_type="application/json",
            handler=self._read_suites,
        )
        self.register_resource(
            uri="benchmark://jobs",
            name="Run di Benchmark",
            description="Elenco dei run con metriche aggregate",
            mime_type="application/json",
            handler=self._read_jobs,
        )

    # ---------------------------------------------------------------- handler

    def _handle_list_suites(self, **kwargs):
        try:
            from core.training.benchmarks import get_suite_info
            return {"success": True, "suites": get_suite_info("all")}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_download_suite(self, suite: str = "all", **kwargs):
        try:
            from core.training.benchmarks import download_suite
            return download_suite(suite or "all")
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_run_benchmark(self, model: str = "", suite: str = "all", mode: str = "sample",
                              samples: int = 25, concurrency="auto", **kwargs):
        if not model:
            return {"success": False, "error": "Parametro 'model' obbligatorio"}
        try:
            from core.training.benchmarks import start_benchmark_run
            job = start_benchmark_run(
                model_name=model,
                suite_id=suite or "all",
                num_samples=0 if mode == "full" else int(samples or 25),
                mode=mode or "sample",
                concurrency=concurrency if concurrency is not None else "auto",
            )
            return {
                "success": True, "job_id": job["id"], "status": job["status"],
                "concurrency": job["concurrency"], "concurrency_source": job.get("concurrency_source", ""),
                "job": job,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_measure_capacity(self, model: str = "", levels=None, wait: bool = True, **kwargs):
        if not model:
            return {"success": False, "error": "Parametro 'model' obbligatorio"}
        try:
            from core.training.capacity import (
                DEFAULT_LEVELS, probe_parallel_capacity, start_capacity_probe,
            )
            steps = [int(n) for n in (levels or DEFAULT_LEVELS)]
            if not wait:
                return start_capacity_probe(model, steps)
            result = probe_parallel_capacity(model, steps)
            if not result.get("success"):
                return result
            # Risposta compatta: a un agente serve il numero e il perche', non
            # ogni campione della misura.
            return {
                "success": True,
                "model": model,
                "recommended_parallel": result["recommended_parallel"],
                "peak_tokens_per_sec": result["peak_tokens_per_sec"],
                "bottleneck": result["bottleneck"],
                "advice": result["advice"],
                "vram_estimate_max_parallel": result["estimate"].get("max_parallel"),
                "levels": [{
                    "concurrency": m["concurrency"],
                    "tokens_per_sec": m["aggregate_tokens_per_sec"],
                    "speedup": m.get("speedup"),
                    "efficiency": m.get("efficiency"),
                    "avg_latency_ms": m["avg_latency_ms"],
                    "failed": m["failed"],
                } for m in result["measurements"]],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_capacity(self, model: str = "", **kwargs):
        if not model:
            return {"success": False, "error": "Parametro 'model' obbligatorio"}
        try:
            from core.training.capacity import estimate_capacity, get_profile
            return {"success": True, "model": model,
                    "estimate": estimate_capacity(model), "profile": get_profile(model)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_status(self, job_id: str = "", **kwargs):
        try:
            from core.training.benchmarks import list_benchmark_jobs
            jobs = list_benchmark_jobs()
            if not jobs:
                return {"success": True, "job": None, "message": "Nessun run registrato"}
            job = next((j for j in jobs if j.get("id") == job_id), None) if job_id else jobs[0]
            if not job:
                return {"success": False, "error": f"Job {job_id} non trovato"}
            return {
                "success": True,
                "job_id": job.get("id"),
                "status": job.get("status"),
                "progress": job.get("progress", 0),
                "model": job.get("model"),
                "suite": job.get("suite_name") or job.get("suite"),
                "metrics": job.get("metrics", {}),
                "reproducibility": job.get("reproducibility", {}),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_review_queue(self, job_id: str = "", limit: int = 50, **kwargs):
        if not job_id:
            return {"success": False, "error": "Parametro 'job_id' obbligatorio"}
        try:
            from core.training.benchmarks import get_review_queue
            result = get_review_queue(job_id)
            if not result.get("success"):
                return result
            cap = max(1, int(limit or 50))
            items = result.get("items", [])
            # Ogni voce riporta la risposta grezza e il motivo della sospensione:
            # e' cio' che serve a un giudice esterno per decidere.
            return {
                "success": True,
                "job_id": job_id,
                "model": result.get("model", ""),
                "total_in_queue": result.get("count", 0),
                "verdict_counts": result.get("verdict_counts", {}),
                "items": [{
                    "id": it.get("id"),
                    "suite": it.get("suite"),
                    "category": it.get("category"),
                    "prompt": it.get("prompt"),
                    "options": it.get("options", []),
                    "correct_answer": it.get("correct_answer"),
                    "model_answer": it.get("given_answer"),
                    "verdict": it.get("verdict"),
                    "reason": (it.get("parsed") or {}).get("reason", ""),
                    "candidates": (it.get("parsed") or {}).get("candidates", []),
                } for it in items[:cap]],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_grade_answer(self, model_output: str = "", correct_choice: str = "",
                             suite: str = "mmlu", options=None, **kwargs):
        try:
            from core.training.answer_parser import grade_answer
            item = {
                "suite": suite or "mmlu",
                "options": list(options or []),
                "correct_choice": correct_choice or "",
                "correct_answer": correct_choice or "",
            }
            graded = grade_answer(item, model_output or "")
            return {"success": True, **graded}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ---------------------------------------------------------------- risorse

    def _read_suites(self, uri: str):
        try:
            from core.training.benchmarks import get_suite_info
            return get_suite_info("all")
        except Exception as exc:
            return {"suites": {}, "error": str(exc)}

    def _read_jobs(self, uri: str):
        try:
            from core.training.benchmarks import list_benchmark_jobs
            return {"jobs": list_benchmark_jobs()}
        except Exception as exc:
            return {"jobs": [], "error": str(exc)}
