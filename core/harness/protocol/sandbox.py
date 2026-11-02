# ==============================================================================
# core/modules/sigma_benchmark_lab/protocol/sandbox.py — SandboxJail per benchmark tool
# Sigma Studio v8 — Isolamento e protezione zero-trust
# ==============================================================================
"""SandboxJail per isolare l'esecuzione dei test di aderenza ai tool.

I modelli di piccole dimensioni (1B, 3B, 7B, 8B) o con scarso allineamento
possono allucinare percorsi assoluti, traversare directory con `../` o tentare
operazioni ricorsive. La SandboxJail confina tassativamente ogni operazione di
filesystem e terminale all'interno di una cartella temporanea effimera,
impedendo qualsiasi accesso in lettura o scrittura ai file reali del kernel.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("protocol_sandbox")


class SandboxJailError(PermissionError):
    """Sollevata quando un modello tenta di accedere a percorsi fuori dalla sandbox."""
    pass


def pulisci(radice: Path | str) -> None:
    """Cancella una sandbox, anche quando git l'ha resa ostinata.

    Su Windows gli oggetti dentro `.git` sono in sola lettura, e `rmtree` si
    ferma sul primo. Rimuoviamo il readonly per garantire pulizia completa.
    """
    rad = Path(radice)
    if not rad.exists():
        return

    def _insisti(funzione, percorso, _info):
        try:
            os.chmod(percorso, stat.S_IWRITE)
            funzione(percorso)
        except OSError:
            pass

    try:
        shutil.rmtree(rad, onerror=_insisti)
    except Exception as exc:
        log.warning("[SandboxJail] errore pulizia sandbox %s: %s", rad, exc)


@dataclass
class SandboxJail:
    """Una sandbox effimera a isolamento totale per un singolo scenario."""

    scenario_id: str
    root: Path = field(init=False)
    violations: List[str] = field(default_factory=list)
    _active: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix=f"sigmabench_jail_{self.scenario_id}_")).resolve()
        self._active = True

    def setup_workspace(self, initial_files: Dict[str, str]) -> None:
        """Popola la sandbox con i file dello scenario e prepara il repo Git."""
        for rel_path, content in initial_files.items():
            safe_target = self.resolve_safe_path(rel_path)
            safe_target.parent.mkdir(parents=True, exist_ok=True)
            safe_target.write_text(content, encoding="utf-8")

        # Inizializza un repository Git locale isolato per il tracciamento
        git_cmds = [
            ["init", "-b", "main"],
            ["config", "user.email", "bench@sigma.local"],
            ["config", "user.name", "SigmaBenchJail"],
            ["config", "commit.gpgsign", "false"],
        ]
        for args in git_cmds:
            subprocess.run(["git"] + args, cwd=str(self.root), capture_output=True)

        subprocess.run(["git", "add", "-A"], cwd=str(self.root), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init_scenario"], cwd=str(self.root), capture_output=True)

    def is_safe_path(self, requested_path: str | Path) -> bool:
        """Verifica se un percorso si trova rigorosamente all'interno della sandbox."""
        if not requested_path:
            return False
        try:
            req = Path(requested_path)
            if PureWindowsPath(str(requested_path)).drive and not req.is_absolute():
                return False
            if req.is_absolute():
                resolved = req.resolve()
            else:
                resolved = (self.root / req).resolve()
            return resolved == self.root or self.root in resolved.parents
        except Exception:
            return False

    def resolve_safe_path(self, requested_path: str | Path) -> Path:
        """Risolve un percorso verificando che non tenti path-traversal fuori dalla sandbox."""
        req = Path(requested_path)
        if req.is_absolute():
            resolved = req.resolve()
        else:
            resolved = (self.root / req).resolve()

        if not self.is_safe_path(requested_path):
            msg = f"Tentativo di accesso esterno alla sandbox: {requested_path!r} -> {resolved!r}"
            self.violations.append(msg)
            log.warning("[SandboxJail] %s", msg)
            raise SandboxJailError(f"AccessDenied: il percorso {requested_path!r} e' fuori dal perimetro della sandbox.")

        return resolved

    def pulisci(self) -> None:
        """Rimuove completamente la sandbox e i suoi file temporanei."""
        if not self._active:
            return
        pulisci(self.root)
        self._active = False


def _prepara(scenario: Any) -> Path:
    """Prepara una sandbox per uno scenario e ritorna la radice."""
    jail = SandboxJail(scenario_id=getattr(scenario, "id", "sc"))
    jail.setup_workspace(getattr(scenario, "file", {}))
    return jail.root
