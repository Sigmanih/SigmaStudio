# ==============================================================================
# core/harness/worktree.py — Isolamento fisico del workspace tramite Git Worktree
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Isolamento dell'agente tramite Git Worktree e checkpoint di turno.

Finora l'agente scriveva direttamente nell'albero vivo del repository dal quale
l'applicazione stessa e' in esecuzione. I backup erano gestiti per singolo file,
rendendo impossibile l'operazione essenziale «annulla tutto cio' che l'agente ha
fatto negli ultimi N turni» in caso di deriva.

Questo modulo alloca un `git worktree` separato e isolato per ogni sessione di
sviluppo:
1. L'agente legge, scrive e compila in una copia fisica del repository.
2. A ogni turno concluso viene creato un checkpoint (commit locale sul branch di
   sessione).
3. `rollback()` riporta l'albero a un checkpoint preciso via `git reset
   --hard`. E' un'operazione disponibile, non automatica: nessuno la invoca da
   solo, perche' uno stallo del modello non dice che il codice scritto fino a
   quel punto sia sbagliato, e annullarlo d'ufficio butterebbe via lavoro buono.
   Chi la usa deve essere qualcuno che ha guardato.
4. Al termine del run, a obiettivo raggiunto le modifiche passano sull'albero
   principale. **Altrimenti restano sul branch della sessione**: non vengono
   cancellate. Vedi `release_session_worktree` per il perche'.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger("worktree")


def _run_git(args: List[str], cwd: Path, timeout_s: float = 30.0) -> subprocess.CompletedProcess:
    """Esegue un comando git nel percorso indicato gestendo codifiche ed errori."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


def is_git_repository(path: Path | str) -> bool:
    """Verifica se il percorso fa parte di un repository Git valido."""
    p = Path(path)
    if not p.is_dir():
        return False
    try:
        res = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=p, timeout_s=5.0)
        return res.returncode == 0 and "true" in res.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


@dataclass
class WorktreeSession:
    """Rappresenta un worktree isolato allocato per un run dell'agente."""

    session_id: str
    repo_root: Path
    worktree_path: Path
    branch_name: str
    #: Il commit da cui il worktree e' partito. E' la base rispetto a cui si
    #: calcola cosa ha fatto il run: contare i checkpoint per risalire indietro
    #: con `HEAD~N` da' la stessa risposta solo finche' i due numeri coincidono,
    #: e smettono di coincidere al primo rollback o al primo checkpoint fallito.
    base_commit: str = ""
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)

    def checkpoint(self, turn_idx: int, message: str = "") -> Optional[str]:
        """Crea uno snapshot di turno committando tutte le modifiche sul branch isolato."""
        if not self.worktree_path.is_dir():
            return None
        try:
            # 1. Aggiungi tutti i file toccati
            _run_git(["add", "-A"], cwd=self.worktree_path)

            # 2. Controlla se c'e' qualcosa di nuovo da salvare
            status = _run_git(["status", "--porcelain"], cwd=self.worktree_path)
            has_changes = bool(status.stdout.strip())

            msg = f"sigma-run[{self.session_id}] turno {turn_idx}"
            if message:
                msg += f": {message}"

            res = _run_git(["commit", "-m", msg, "--allow-empty"], cwd=self.worktree_path)
            if res.returncode != 0:
                log.warning("[Worktree] Checkpoint turno %d non riuscito: %s", turn_idx, res.stderr)
                return None

            # Ottieni l'hash del commit appena generato
            rev = _run_git(["rev-parse", "HEAD"], cwd=self.worktree_path)
            commit_hash = rev.stdout.strip()

            record = {
                "turn": turn_idx,
                "commit": commit_hash,
                "has_changes": has_changes,
                "message": msg,
            }
            self.checkpoints.append(record)
            log.info("[Worktree] Checkpoint creato per turno %d (%s)", turn_idx, commit_hash[:8])
            return commit_hash
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("[Worktree] Errore durante il checkpoint del turno %d: %s", turn_idx, exc)
            return None

    def rollback(self, turns_back: int = 1) -> bool:
        """Annulla il lavoro degli ultimi N turni ripristinando l'albero via git reset."""
        if not self.worktree_path.is_dir() or turns_back <= 0:
            return False
        try:
            target = f"HEAD~{turns_back}"
            res = _run_git(["reset", "--hard", target], cwd=self.worktree_path)
            if res.returncode != 0:
                log.error("[Worktree] Rollback a %s fallito: %s", target, res.stderr)
                return False

            _run_git(["clean", "-fd"], cwd=self.worktree_path)
            # Rimuovi i checkpoint annullati dalla cronologia locale
            del self.checkpoints[-turns_back:]
            log.info("[Worktree] Rollback di %d turni eseguito con successo su %s", turns_back, target)
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            log.error("[Worktree] Errore durante il rollback: %s", exc)
            return False

    def _diff(self, extra: List[str]) -> str:
        """Il confronto fra il punto di partenza e lo stato attuale del lavoro.

        Due cose lo rendono diverso da un `git diff` qualsiasi, e sono le due
        che servono a chi deve rivedere:

        **La base e' il commit di partenza**, non `HEAD~<numero checkpoint>`.
        Il conteggio mente appena c'e' stato un rollback, ed e' lo stesso
        difetto che faceva applicare all'albero principale la porzione
        sbagliata del lavoro.

        **Si guarda l'albero di lavoro, non l'ultimo commit.** L'ultimo turno
        puo' avere scritto dopo l'ultimo checkpoint, e i file nuovi non sono
        ancora tracciati: `git add -A` li mette nell'indice — senza committare
        — cosi' il diff comprende tutto cio' che il run ha prodotto. Mostrare
        meno significherebbe far approvare qualcosa di diverso da cio' che poi
        viene applicato.
        """
        if not self.worktree_path.is_dir():
            return ""
        base = self.base_commit
        if not base:
            return ""
        try:
            _run_git(["add", "-A"], cwd=self.worktree_path)
            res = _run_git(["diff", "--cached", base] + extra, cwd=self.worktree_path)
            return res.stdout
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("[Worktree] diff non calcolabile: %s", exc)
            return ""

    def diff_from_main(self) -> str:
        """Il diff completo di tutto cio' che il run ha prodotto."""
        return self._diff([])

    def diff_stat_from_main(self) -> str:
        """L'elenco dei file toccati con quante righe: la vista d'insieme.

        Su un lavoro da duecento file il diff intero non si legge; questo si',
        ed e' quello che dice se il run ha toccato cio' che doveva.
        """
        return self._diff(["--stat"])

    def changed_files(self) -> List[str]:
        """I file toccati dal run, per contarli e nominarli."""
        grezzo = self._diff(["--name-only"])
        return [r.strip() for r in grezzo.splitlines() if r.strip()]

    def apply_to_main(self) -> bool:
        """Applica le modifiche validate dal worktree al repository principale."""
        if not self.worktree_path.is_dir() or not self.repo_root.is_dir():
            return False
        try:
            # L'ultimo turno puo' avere scritto dopo l'ultimo checkpoint: il
            # diff guarda solo cio' che e' stato committato, e senza questo si
            # perderebbe in silenzio proprio la modifica finale — quella che
            # ha chiuso l'obiettivo.
            self.checkpoint(len(self.checkpoints) + 1, "chiusura del run")

            # Crea una patch unificata dal branch del worktree e applicala sul repo originario
            base = self.base_commit or f"HEAD~{len(self.checkpoints)}"
            diff_res = _run_git(["diff", base, "HEAD"], cwd=self.worktree_path)
            patch = diff_res.stdout
            if not patch.strip():
                return True  # Nessuna modifica da applicare

            apply_res = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                input=patch,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30.0,
            )
            if apply_res.returncode != 0:
                log.error("[Worktree] Applicazione modifiche a main fallita: %s", apply_res.stderr)
                return False
            log.info("[Worktree] Modifiche della sessione %s applicate con successo a main", self.session_id)
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            log.error("[Worktree] Errore applicazione a main: %s", exc)
            return False

    def has_work(self) -> bool:
        """True se almeno un checkpoint ha davvero salvato qualcosa.

        I checkpoint di turno si fanno con `--allow-empty`, quindi la loro
        esistenza non dice nulla: un run che non ha toccato niente ne accumula
        uno per turno. Cio' che conta e' se qualcuno di quei commit conteneva
        modifiche vere, ed e' l'unica domanda che deve decidere se il branch
        vale la pena di essere conservato.
        """
        return any(c.get("has_changes") for c in self.checkpoints)

    def close(self, discard_branch: bool = True) -> None:
        """Rilascia il worktree. Il branch resta, se non si chiede di buttarlo."""
        try:
            # 1. Rimuovi il worktree tramite comando git
            if self.repo_root.is_dir():
                _run_git(["worktree", "remove", "--force", str(self.worktree_path)], cwd=self.repo_root)
                if discard_branch:
                    _run_git(["branch", "-D", self.branch_name], cwd=self.repo_root)

            # 2. Pulizia fisica della cartella se rimasta
            if self.worktree_path.exists():
                shutil.rmtree(self.worktree_path, ignore_errors=True)
            log.info("[Worktree] Sessione %s rilasciata correttamente", self.session_id)
        except Exception as exc:
            log.warning("[Worktree] Pulizia worktree %s: %s", self.session_id, exc)


# ---------------------------------------------------------------------------
# Registro globale delle sessioni worktree
# ---------------------------------------------------------------------------

_active_worktrees: Dict[str, WorktreeSession] = {}


def create_session_worktree(repo_root: Path | str, session_id: str) -> Optional[WorktreeSession]:
    """Crea e isola un worktree git dedicato per la sessione specificata."""
    root = Path(repo_root).resolve()
    if not is_git_repository(root):
        log.debug("[Worktree] '%s' non e' un repo git valido: isolamento worktree saltato", root)
        return None

    sid = str(session_id or "").strip()
    if not sid:
        return None

    target_dir = paths.var_dir() / "dev_worktrees" / sid
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    branch_name = f"sigma-run/{sid}"

    try:
        # Se esisteva gia' un worktree orfano, rimuovilo prima
        if target_dir.exists():
            _run_git(["worktree", "remove", "--force", str(target_dir)], cwd=root)
            shutil.rmtree(target_dir, ignore_errors=True)

        # Crea il nuovo worktree basato su HEAD con branch dedicato
        res = _run_git(["worktree", "add", "-B", branch_name, str(target_dir), "HEAD"], cwd=root)
        if res.returncode != 0:
            log.warning("[Worktree] Impossibile creare worktree per %s: %s", sid, res.stderr)
            return None

        rev = _run_git(["rev-parse", "HEAD"], cwd=target_dir)
        session = WorktreeSession(
            session_id=sid,
            repo_root=root,
            worktree_path=target_dir,
            branch_name=branch_name,
            base_commit=rev.stdout.strip() if rev.returncode == 0 else "",
        )
        _active_worktrees[sid] = session
        log.info("[Worktree] Isolamento attivato per sessione %s in %s", sid, target_dir)
        return session
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("[Worktree] Eccezione allocazione worktree: %s", exc)
        return None


def get_session_worktree(session_id: str) -> Optional[WorktreeSession]:
    """Recupera la sessione worktree attiva per una session_id."""
    return _active_worktrees.get(str(session_id or "").strip())


def release_session_worktree(session_id: str, apply_changes: bool = False) -> Dict[str, Any]:
    """Chiude il worktree di una sessione e dice cosa ne e' stato del lavoro.

    **Un run che non raggiunge l'obiettivo non e' un run da buttare.** Qui
    prima si cancellava il branch ogni volta che `apply_changes` era falso, e
    poiche' il cancello di completamento e' severo per costruzione — richiede
    una verifica verde, non la parola dell'agente — "obiettivo non raggiunto"
    e' l'esito ordinario, non quello eccezionale. Trenta turni di lavoro buono
    sparivano perche' mancava l'ultimo passo, e sparivano in silenzio.

    Adesso il branch resta. Costa una riga in `git branch` e vale l'intero
    contenuto del run: chi non lo vuole lo cancella, chi lo vuole lo ritrova.
    Si butta solo quando non c'e' niente da salvare, o quando il lavoro e' gia'
    stato trasferito sull'albero principale.

    Ritorna un resoconto: cosa e' stato applicato, quale branch e' rimasto, e
    quanti checkpoint conteneva — serve a dirlo a chi ha lanciato il run,
    perche' un branch di cui nessuno conosce il nome e' perso comunque.
    """
    sid = str(session_id or "").strip()
    session = _active_worktrees.pop(sid, None)
    if session is None:
        return {"released": False, "applied": False, "branch": "", "checkpoints": 0}

    aveva_lavoro = session.has_work()
    applicato = False
    if apply_changes:
        applicato = session.apply_to_main()

    # Il branch si butta solo se il lavoro e' al sicuro altrove, o se non c'e'.
    scarta_branch = applicato or not aveva_lavoro
    session.close(discard_branch=scarta_branch)

    resoconto = {
        "released": True,
        "applied": applicato,
        "branch": "" if scarta_branch else session.branch_name,
        "checkpoints": len([c for c in session.checkpoints if c.get("has_changes")]),
    }
    if resoconto["branch"]:
        log.info(
            "[Worktree] Lavoro della sessione %s conservato sul branch '%s' "
            "(%d checkpoint con modifiche)",
            sid, resoconto["branch"], resoconto["checkpoints"],
        )
    return resoconto
