"""Contratto dei backend di esecuzione.

Sigma non deve conoscere l'implementazione interna di ComfyUI. Parla con un
backend che espone sempre le stesse operazioni: scoperta modelli, stato del
sistema, coda, invio job, stato job, annullamento, storico e output.

Aggiungere vLLM, llama.cpp, Diffusers o un servizio remoto significa scrivere una
classe che rispetta questo contratto — la logica di Sigma non cambia.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict


@dataclass
class BackendJob:
    """Stato di un job, con la stessa forma per qualunque backend."""
    job_id: str
    status: str = "pending"        # pending | running | done | error | cancelled
    progress: float = 0.0          # 0..100
    node: str = ""                 # passo corrente, se il backend lo espone
    error: str = ""
    outputs: list = field(default_factory=list)   # [{filename, kind, subfolder}]

    @property
    def finished(self) -> bool:
        return self.status in ("done", "error", "cancelled")

    def to_dict(self):
        return {**asdict(self), "finished": self.finished}


class BackendUnavailable(RuntimeError):
    """Il backend non risponde: distinguibile da un errore di esecuzione."""


class GenerationBackend(ABC):
    """Interfaccia minima che ogni motore di esecuzione deve offrire."""

    id: str = ""
    label: str = ""

    # --- stato ---------------------------------------------------------

    @abstractmethod
    async def is_available(self) -> bool:
        """True se il backend risponde adesso."""

    @abstractmethod
    async def get_system_stats(self) -> dict:
        """Versione, device e memoria, normalizzati."""

    @abstractmethod
    async def discover_models(self) -> dict:
        """Modelli che il runtime espone, per categoria."""

    # --- esecuzione ----------------------------------------------------

    @abstractmethod
    async def get_queue(self) -> dict:
        """Job in esecuzione e in attesa."""

    @abstractmethod
    async def submit(self, payload: dict) -> str:
        """Accoda un lavoro e ritorna il suo id."""

    @abstractmethod
    async def get_job_status(self, job_id: str) -> BackendJob:
        """Stato corrente del job."""

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Annulla un job in coda o in esecuzione."""

    @abstractmethod
    async def get_history(self, job_id: str) -> dict:
        """Record storico grezzo del job, per diagnosi."""

    @abstractmethod
    async def get_outputs(self, job_id: str) -> list[tuple[bytes, str]]:
        """File prodotti, come coppie (bytes, nome)."""

    # --- helper condiviso ----------------------------------------------

    async def run(self, payload: dict, progress_cb=None, timeout_s: int = 600) -> tuple[bytes, str]:
        """Invia, attende e restituisce il primo output.

        L'attesa vera è compito della sottoclasse quando può fare di meglio
        (websocket); questa versione basata su polling è il minimo garantito.
        """
        import asyncio

        job_id = await self.submit(payload)
        waited, delay = 0.0, 1.0
        while waited < timeout_s:
            job = await self.get_job_status(job_id)
            if progress_cb:
                progress_cb(job.to_dict())
            if job.status == "error":
                raise RuntimeError(job.error or "Esecuzione fallita")
            if job.finished:
                break
            await asyncio.sleep(delay)
            waited += delay
            delay = min(delay * 1.3, 5.0)
        else:
            raise TimeoutError(f"{self.label}: timeout dopo {timeout_s}s")

        outputs = await self.get_outputs(job_id)
        if not outputs:
            raise RuntimeError(f"{self.label}: nessun file prodotto")
        return outputs[0]
