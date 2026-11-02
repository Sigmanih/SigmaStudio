"""Esecutore durevole condiviso dai moduli, senza dipendenze dai laboratori."""
from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
import uuid
import contextvars
from contextlib import nullcontext

from core.job_store import JobStore, TERMINAL
from core.logger import get_logger
from core.resource_pool import ResourceBusy
from core.request_context import get_request_id, request_scope

log = get_logger(__name__)
PUBLIC_FIELDS = ("id", "scope", "kind", "args", "status", "message", "progress",
                 "created", "started", "finished", "result", "error", "retry_of", "request_id", "operation_id")


class JobCancelled(RuntimeError):
    """Interruzione cooperativa richiesta dall'utente."""


def public_job(job: dict) -> dict:
    return {key: job[key] for key in PUBLIC_FIELDS if key in job}


class PersistentJobWorker:
    def __init__(self, store: JobStore, handlers: dict, context, *, blocked=None, reserve=None, id_prefix="job"):
        self.store, self.handlers, self.context = store, handlers, context
        self.blocked = blocked or (lambda job: "")
        self.reserve = reserve or (lambda job: nullcontext())
        self.id_prefix = id_prefix
        self.owner = uuid.uuid4().hex
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._active = None
        self._guard = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="persistent-jobs", daemon=True)
        self._thread.start()

    def submit(self, scope: str, kind: str, args: dict, *, retry_of=None, operation_id=None) -> dict:
        if self._stop.is_set():
            raise RuntimeError("L'esecutore è in chiusura")
        if not isinstance(kind, str) or kind not in self.handlers:
            raise ValueError(f"Operazione sconosciuta: {kind}")
        if not isinstance(args, dict) or not isinstance(scope, str) or not scope:
            raise ValueError("Ambito e parametri del lavoro non validi")
        job = {"id": f"{self.id_prefix}_{uuid.uuid4().hex}", "scope": scope, "kind": kind,
               "args": args, "status": "queued", "message": "In coda", "progress": 0.0,
               "created": time.time(), "result": None, "error": ""}
        job["request_id"] = get_request_id() if get_request_id() != "-" else str(uuid.uuid4())
        job["operation_id"] = operation_id or job["id"]
        if retry_of:
            job["retry_of"] = retry_of
        result = self.store.create(job)
        self._wake.set()
        return result

    def list(self) -> list[dict]:
        self.store.recover()
        jobs = self.store.list()
        for job in jobs:
            if job["status"] == "queued":
                job["message"] = self.blocked(job) or "In coda"
        return jobs

    def retry(self, job_id: str, allowed: set[str]) -> dict:
        previous = self.store.get(job_id)
        if not previous or previous["status"] not in TERMINAL or previous["status"] == "done":
            raise ValueError("Il lavoro non è riprendibile nello stato corrente")
        if previous["kind"] not in allowed:
            raise ValueError("Questa operazione richiede un nuovo avvio esplicito")
        return self.submit(previous["scope"], previous["kind"], previous["args"], retry_of=job_id,
                           operation_id=previous.get("operation_id") or job_id)

    def cancel(self, job_id: str) -> bool:
        cancelled = self.store.cancel(job_id)
        with self._guard:
            if cancelled and self._active and self._active["id"] == job_id:
                self._active["cancel_event"].set()
        self._wake.set()
        return cancelled

    def close(self, timeout: float = 2) -> bool:
        self._stop.set()
        with self._guard:
            if self._active:
                self._active["cancel_event"].set()
        self._wake.set()
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _monitor(self, job: dict, done: threading.Event):
        while not done.wait(1):
            try:
                stored = self.store.get(job["id"])
                if self._stop.is_set() or not stored or stored["cancel_requested"]:
                    job["cancel_event"].set()
                if not self.store.heartbeat(job["id"], self.owner):
                    job["cancel_event"].set()
                    return
                progress = public_job(job)
                # Solo il thread esecutore può pubblicare l'esito finale, dopo la chiusura del monitor.
                progress["status"] = "running"
                if not self.store.save(progress, self.owner):
                    job["cancel_event"].set()
                    return
            except Exception:
                # Senza registro affidabile il lavoro deve fermarsi al prossimo controllo cooperativo.
                job["cancel_event"].set()
                log.exception("Impossibile aggiornare il lavoro %s", job["id"])
                return

    def _run(self, job: dict):
        with request_scope(job.get("request_id") or job["id"]):
            self._execute_job(job)

    def _execute_job(self, job: dict):
        job.update(status="running", started=time.time(), message="Avvio", cancel_event=threading.Event())
        if not self.store.save(public_job(job), self.owner):
            return
        with self._guard:
            self._active = job
        done = threading.Event()
        monitor = threading.Thread(target=contextvars.copy_context().run,
                                   args=(self._monitor, job, done), daemon=True, name="job-lease")
        try:
            monitor.start()
            if self._stop.is_set() or self.store.get(job["id"])["cancel_requested"]:
                raise JobCancelled("Operazione annullata")
            result = self.handlers[job["kind"]](self.context, job)
            result = asyncio.run(result) if inspect.isawaitable(result) else result
            json.dumps(result, allow_nan=False)
            job["result"] = result
            job.update(status="done", progress=1.0, message="Completato")
        except JobCancelled as exc:
            job.update(status="cancelled", error="", message=str(exc))
        except Exception as exc:
            log.exception("Lavoro %s (%s) fallito", job["id"], job["kind"])
            job.update(status="error", error=str(exc), message="Errore")
        finally:
            done.set()
            if monitor.ident is not None:
                monitor.join(timeout=2)
            job["finished"] = time.time()
            try:
                if not self.store.save(public_job(job), self.owner):
                    log.error("Lease persa: risultato del lavoro %s non pubblicato", job["id"])
            finally:
                with self._guard:
                    self._active = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.store.recover()
                queued = sorted((job for job in self.store.list() if job["status"] == "queued"),
                                key=lambda job: (job["created"], job["id"]))
                for job in queued:
                    if self._stop.is_set():
                        break
                    if self.blocked(job):
                        continue
                    try:
                        with self.reserve(job):
                            if self.store.claim(job["id"], self.owner):
                                self._run(job)
                    except ResourceBusy:
                        continue
                self._wake.wait(timeout=2)
                self._wake.clear()
            except Exception:
                log.exception("Coda persistente temporaneamente non disponibile")
                self._stop.wait(2)
