"""Registro durevole dei lavori: claim atomico, lease e recupero esplicito."""
from __future__ import annotations

import json
import math
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


TERMINAL = ("done", "error", "cancelled", "interrupted")


class JobStore:
    def __init__(self, path: Path, *, clock=time.time, max_pending: int = 100, max_running: int = 1):
        self.path = Path(path)
        self.clock = clock
        if type(max_pending) is not int or type(max_running) is not int or min(max_pending, max_running) < 1:
            raise ValueError("I limiti della coda devono essere interi positivi")
        self.max_pending = max_pending
        self.max_running = max_running
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                updated REAL NOT NULL, owner TEXT, lease REAL, cancel INTEGER NOT NULL DEFAULT 0,
                retry_of TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, updated)")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS jobs_retry_pending ON jobs(retry_of)
                WHERE retry_of IS NOT NULL AND status IN ('queued','running')""")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        job = {**json.loads(row["payload"]), "status": row["status"], "cancel_requested": bool(row["cancel"])}
        if row["status"] == "interrupted":
            job["message"] = "Esecuzione interrotta: verificare i risultati prima di riprendere"
        elif row["status"] == "cancelled":
            job["message"] = "Annullato"
        elif row["status"] == "running" and row["cancel"]:
            job["message"] = "Interruzione richiesta"
        return job

    def create(self, job: dict) -> dict:
        payload = json.dumps(job, ensure_ascii=False, allow_nan=False)
        if len(payload.encode("utf-8")) > 256 * 1024:
            raise ValueError("Parametri del lavoro troppo grandi")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            if pending >= self.max_pending:
                raise ValueError("Coda piena: attendere la conclusione dei lavori attivi")
            try:
                db.execute("INSERT INTO jobs(id,payload,status,updated,retry_of) VALUES (?,?,?,?,?)",
                           (job["id"], payload, "queued", self.clock(), job.get("retry_of")))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Un lavoro con questo identificativo o questa ripresa è già in coda") from exc
            db.execute("""DELETE FROM jobs WHERE id IN (
                SELECT id FROM jobs WHERE status IN ('done','error','cancelled','interrupted')
                ORDER BY updated DESC LIMIT -1 OFFSET 200)""")
        return json.loads(payload)

    def list(self) -> list[dict]:
        with self._db() as db:
            return [self._decode(row) for row in db.execute("SELECT * FROM jobs ORDER BY updated DESC, id")]

    def get(self, job_id: str) -> dict | None:
        if not isinstance(job_id, str) or not job_id:
            return None
        with self._db() as db:
            return self._decode(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def claim(self, job_id: str, owner: str, lease_seconds: float = 30) -> bool:
        if not owner or not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError("Proprietario e durata della lease non validi")
        with self._db() as db:
            return db.execute("""UPDATE jobs SET status='running', owner=?, lease=?, updated=?
                WHERE id=? AND status='queued' AND cancel=0 AND (
                SELECT COUNT(*) FROM jobs WHERE status='running' AND lease>=?) < ?""",
                              (owner, self.clock() + lease_seconds, self.clock(), job_id,
                               self.clock(), self.max_running)).rowcount == 1

    def heartbeat(self, job_id: str, owner: str, lease_seconds: float = 30) -> bool:
        with self._db() as db:
            return db.execute("UPDATE jobs SET lease=? WHERE id=? AND owner=? AND status='running' AND lease>=?",
                              (self.clock() + lease_seconds, job_id, owner, self.clock())).rowcount == 1

    def save(self, job: dict, owner: str) -> bool:
        # Il chiamante esclude gli oggetti runtime: nessuna conversione silenziosa in stringa.
        payload = json.dumps(job, ensure_ascii=False, allow_nan=False)
        with self._db() as db:
            return db.execute("""UPDATE jobs SET payload=?,status=?,updated=? WHERE id=?
                AND owner=? AND status='running' AND lease>=?""",
                              (payload, job["status"], self.clock(), job["id"], owner, self.clock())).rowcount == 1

    def cancel(self, job_id: str) -> bool:
        if not isinstance(job_id, str) or not job_id:
            return False
        with self._db() as db:
            return db.execute("""UPDATE jobs SET cancel=1, updated=?,
                status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END
                WHERE id=? AND status IN ('queued','running')""", (self.clock(), job_id)).rowcount == 1

    def recover(self) -> int:
        # Un lavoro interrotto non riparte da solo: potrebbe avere già modificato file o timeline.
        with self._db() as db:
            return db.execute("""UPDATE jobs SET status='interrupted',updated=?
                WHERE status='running' AND lease < ?""", (self.clock(), self.clock())).rowcount

    def forget(self, scope: str) -> None:
        with self._db() as db:
            ids = [(row["id"],) for row in db.execute(
                "SELECT id,payload FROM jobs WHERE status IN ('done','error','cancelled','interrupted')")
                if json.loads(row["payload"]).get("scope") == scope]
            db.executemany("DELETE FROM jobs WHERE id=?", ids)
