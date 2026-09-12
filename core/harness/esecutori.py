# ==============================================================================
# core/harness/esecutori.py — Dove girano i comandi dell'agente
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Sull'host, o dentro un contenitore che e' una sandbox per costruzione.

I tool di file hanno un recinto: `resolve_workspace_path` rifiuta cio' che esce
dalla cartella di lavoro. Il tool `terminal` non ne ha nessuno. Esegue un
comando di shell con l'ambiente intero del processo e la `cwd` nel workspace,
ma una `cwd` non e' un confine: `cd ..` e' una riga, e da li' si arriva
ovunque. Un recinto sui percorsi scritto in Python e' aggirabile da qualunque
comando.

E c'e' un secondo motivo, che e' quello per cui l'idea e' nata: dentro un
contenitore un modello puo' **installare, compilare, rompere e ricominciare**
senza che nessuno debba fidarsi. Un progetto nuovo in una cartella nuova e'
gia' una sandbox naturale; il contenitore la rende vera.

**La cucitura sta qui e non nei tool di file.** I file continuano a essere
scritti dall'host, e il contenitore monta la stessa cartella: stessi byte, due
viste. Cosi' il diff, i backup, il cancello di revisione e `apply_to_main`
continuano a funzionare senza sapere che esiste un contenitore. Spostare anche
la scrittura dentro il contenitore avrebbe voluto dire riscrivere tutto quello.

**Quattro scelte che non sono dettagli.**

*Si monta il worktree, non il repository.* Con l'isolamento acceso ogni run ha
il suo albero: montare la radice del progetto rimetterebbe in comunicazione i
lavoratori paralleli che l'isolamento serve a separare.

*L'ambiente e' una lista bianca.* L'esecutore sull'host passa
`dict(os.environ)`; dentro il contenitore passa le poche variabili che servono
ai comandi. Ereditare l'ambiente e' comodo finche' non ci si accorge di cosa
contiene.

*La rete e' spenta.* Con una deroga esplicita, perche' `npm install` senza rete
non funziona e senza quella deroga la prima voce della coda fallirebbe facendo
sembrare sbagliata l'idea invece che stretta la regola.

*Se il contenitore non c'e', si dice.* Mai ripiegare in silenzio sull'host: chi
ha acceso la sandbox crederebbe di essere protetto e non lo sarebbe. Un
fallimento visibile e' l'unica forma onesta.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import paths
from core.logger import get_logger

log = get_logger("esecutori")

#: L'immagine se il progetto non ne dichiara una. Contiene Python e Node, cioe'
#: cio' che serve ai progetti che questo sistema costruisce davvero.
IMMAGINE_PREDEFINITA = "python:3.12-slim"

#: Le variabili che il contenitore riceve. Corte apposta: tutto cio' che non e'
#: qui non entra, e questa e' la differenza con l'ambiente dell'host.
AMBIENTE_CONTENITORE: Dict[str, str] = {
    "CI": "1",
    "HOME": "/lavoro",
    "LANG": "C.UTF-8",
    "PYTHONUNBUFFERED": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "npm_config_yes": "true",
    "npm_config_audit": "false",
    "npm_config_fund": "false",
    "npm_config_progress": "false",
}

#: Dove il workspace compare dentro il contenitore.
PUNTO_DI_MONTAGGIO = "/lavoro"

PREDEFINITI: Dict[str, Any] = {
    #: "host" oppure "container". Host finche' non lo si cambia: accendere una
    #: sandbox di nascosto cambierebbe il comportamento di run gia' scritti.
    "mode": "host",
    "image": IMMAGINE_PREDEFINITA,
    #: La rete dentro il contenitore. Spenta salvo deroga.
    "network": False,
    #: Quanta memoria puo' prendersi. Un `npm install` impazzito non deve poter
    #: mettere in ginocchio la macchina che serve anche il modello.
    "memory": "4g",
    "cpus": "2",
}


def _percorso_config() -> Path:
    return Path(paths.config_dir()) / "sandbox.json"


def carica_config() -> Dict[str, Any]:
    """Le preferenze della sandbox, con i predefiniti sotto."""
    configurazione = dict(PREDEFINITI)
    percorso = _percorso_config()
    if percorso.is_file():
        try:
            salvate = json.loads(percorso.read_text(encoding="utf-8"))
            if isinstance(salvate, dict):
                configurazione.update(
                    {k: v for k, v in salvate.items() if k in PREDEFINITI})
        except (OSError, ValueError) as exc:
            log.warning("[Sandbox] configurazione illeggibile: %s", exc)
    return configurazione


def salva_config(valori: Dict[str, Any]) -> Dict[str, Any]:
    """Scrive le preferenze, tenendo solo le chiavi note."""
    corrente = carica_config()
    corrente.update({k: v for k, v in (valori or {}).items() if k in PREDEFINITI})
    percorso = _percorso_config()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(corrente, indent=2), encoding="utf-8")
    return corrente


# ---------------------------------------------------------------------------
# Disponibilita' di Docker
# ---------------------------------------------------------------------------

def docker_disponibile() -> Tuple[bool, str]:
    """Se Docker c'e' ed e' in ascolto. Il secondo valore dice cosa manca.

    Due domande distinte: il comando esiste, e il demone risponde. Su Windows
    il comando c'e' anche quando Docker Desktop e' spento, e l'errore che ne
    esce a quel punto sarebbe indistinguibile da un comando sbagliato.
    """
    eseguibile = shutil.which("docker")
    if not eseguibile:
        return False, (
            "Docker non e' installato su questa macchina. Su Windows serve "
            "Docker Desktop, che a sua volta richiede WSL2 o Hyper-V."
        )
    try:
        esito = subprocess.run(
            [eseguibile, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Docker c'e' ma non risponde: {exc}"
    if esito.returncode != 0:
        return False, (
            "Docker e' installato ma il demone non risponde "
            f"({(esito.stderr or '').strip()[:160]}). Avvia Docker Desktop."
        )
    return True, (esito.stdout or "").strip()


# ---------------------------------------------------------------------------
# Gli esecutori
# ---------------------------------------------------------------------------

@dataclass
class Esito:
    """Com'e' andato un comando. Stessa forma da entrambe le parti."""

    success: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    #: Dove e' girato davvero. Serve a chi legge il resoconto: «passa sull'host
    #: e fallisce nel contenitore» e' una frase che si dira' spesso.
    dove: str = "host"

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "returncode": self.returncode,
                "stdout": self.stdout, "stderr": self.stderr,
                "duration_s": self.duration_s, "dove": self.dove}


class EsecutoreHost:
    """Il comportamento storico: il comando gira su questa macchina."""

    nome = "host"

    def descrizione(self) -> str:
        return "sull'host, senza recinto"

    def esegui(self, comando: str, cwd: str, timeout_s: int = 300,
               should_cancel: Optional[Callable[[], bool]] = None) -> Esito:
        from core.harness.terminal import execute_shell_command_sync

        grezzo = execute_shell_command_sync(
            comando, cwd=cwd, timeout_seconds=timeout_s, should_cancel=should_cancel)
        return Esito(
            success=bool(grezzo.get("success")),
            returncode=int(grezzo.get("returncode") or 0),
            stdout=str(grezzo.get("stdout") or ""),
            stderr=str(grezzo.get("stderr") or ""),
            duration_s=float(grezzo.get("duration_s") or 0.0),
            dove="host",
        )


@dataclass
class EsecutoreContenitore:
    """Il comando gira dentro un contenitore, con il workspace montato.

    Il contenitore e' usa e getta (`--rm`): cio' che l'agente installa dura
    quanto il comando, tranne cio' che scrive nel workspace montato — che e'
    esattamente la distinzione voluta. Il lavoro resta, il disordine no.
    """

    immagine: str = IMMAGINE_PREDEFINITA
    rete: bool = False
    memoria: str = "4g"
    cpu: str = "2"
    ambiente: Dict[str, str] = field(default_factory=lambda: dict(AMBIENTE_CONTENITORE))

    nome = "container"

    def descrizione(self) -> str:
        rete = "con rete" if self.rete else "senza rete"
        return f"nel contenitore {self.immagine}, {rete}"

    def argv(self, comando: str, cwd: str) -> List[str]:
        """La riga di comando di docker. Separata per poterla verificare.

        Il valore di questo metodo e' che si puo' controllare **senza Docker
        installato**: che venga montato il worktree e non il repository, che
        l'ambiente sia una lista bianca e non quello dell'host, che la rete sia
        spenta. Sono le tre cose che rendono il contenitore una sandbox invece
        che un modo complicato di eseguire un comando.
        """
        montaggio = str(Path(cwd).resolve())
        argv = [
            "docker", "run", "--rm",
            "-v", f"{montaggio}:{PUNTO_DI_MONTAGGIO}",
            "-w", PUNTO_DI_MONTAGGIO,
        ]
        if not self.rete:
            argv += ["--network", "none"]
        if self.memoria:
            argv += ["--memory", str(self.memoria)]
        if self.cpu:
            argv += ["--cpus", str(self.cpu)]
        for chiave, valore in sorted(self.ambiente.items()):
            argv += ["-e", f"{chiave}={valore}"]
        argv += [self.immagine, "sh", "-lc", comando]
        return argv

    def esegui(self, comando: str, cwd: str, timeout_s: int = 300,
               should_cancel: Optional[Callable[[], bool]] = None) -> Esito:
        import time

        disponibile, dettaglio = docker_disponibile()
        if not disponibile:
            # Mai ripiegare sull'host: chi ha acceso la sandbox crederebbe di
            # essere protetto senza esserlo, ed e' peggio di non averla.
            return Esito(
                success=False, returncode=127, dove="container",
                stderr=(f"Sandbox richiesta ma non disponibile. {dettaglio}\n"
                        "Il comando NON e' stato eseguito: eseguirlo sull'host "
                        "avrebbe aggirato in silenzio la sandbox che hai chiesto."),
            )

        argv = self.argv(comando, cwd)
        inizio = time.perf_counter()
        try:
            esito = subprocess.run(
                argv, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout_s, stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return Esito(success=False, returncode=124, dove="container",
                         duration_s=round(time.perf_counter() - inizio, 3),
                         stderr=f"Comando interrotto dopo {timeout_s}s nel contenitore.")
        except (OSError, subprocess.SubprocessError) as exc:
            return Esito(success=False, returncode=1, dove="container",
                         stderr=f"Contenitore non avviato: {exc}")

        return Esito(
            success=esito.returncode == 0,
            returncode=esito.returncode,
            stdout=esito.stdout or "",
            stderr=esito.stderr or "",
            duration_s=round(time.perf_counter() - inizio, 3),
            dove="container",
        )


def scegli_esecutore(configurazione: Optional[Dict[str, Any]] = None) -> Any:
    """L'esecutore che la configurazione descrive. Host se non dice altro."""
    cfg = dict(configurazione or carica_config())
    if str(cfg.get("mode") or "host").lower() != "container":
        return EsecutoreHost()
    return EsecutoreContenitore(
        immagine=str(cfg.get("image") or IMMAGINE_PREDEFINITA),
        rete=bool(cfg.get("network")),
        memoria=str(cfg.get("memory") or ""),
        cpu=str(cfg.get("cpus") or ""),
    )


def stato_sandbox() -> Dict[str, Any]:
    """Cosa dire all'interfaccia: com'e' configurata e se puo' funzionare."""
    cfg = carica_config()
    disponibile, dettaglio = docker_disponibile()
    return {
        **cfg,
        "docker_available": disponibile,
        "docker_detail": dettaglio,
        "active": cfg.get("mode") == "container" and disponibile,
    }
