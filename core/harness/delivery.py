# ==============================================================================
# core/harness/delivery.py — Il lavoro dell'agente arriva in dev, e si rivede
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Dal branch di un run a una pull request che qualcuno deve accettare.

Fino a qui il lavoro approvato di un run finiva **nell'albero di lavoro**: era
un miglioramento rispetto allo scrivere direttamente, ma la revisione restava
una cosa sola, subito, davanti a un diff. Chi vuole guardare con calma, o
guardare due giorni dopo, o farlo guardare a un altro, non aveva dove.

Qui il lavoro prende la strada normale del software: finisce su un branch di
integrazione — `dev` — e da li' una pull request verso il branch principale.
L'albero di lavoro non viene toccato.

**Niente checkout nel repository dell'utente.** Il merge avviene in un worktree
dedicato sotto `var/`. Fare `git checkout dev` nel repository vivo cambierebbe
i file sotto le mani di chi sta lavorando, ed e' gia' successo una volta in
questo progetto: un server MCP ha creato un branch nel repository sbagliato e
ci ha fatto checkout mentre l'agente credeva di lavorare altrove.

**La pull request si apre con quello che c'e'.** Se `gh` e' installato la si
apre; se c'e' un token la si apre via API; altrimenti si spinge comunque il
branch e si restituisce l'indirizzo su cui aprirla con un click. Non riuscire
ad aprirla non e' un motivo per non consegnare il lavoro.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import paths
from core.logger import get_logger

log = get_logger("delivery")

#: Il branch di integrazione dove atterra il lavoro degli agenti.
BRANCH_INTEGRAZIONE = "dev"

#: I nomi con cui un progetto puo' chiamare il proprio branch principale, in
#: ordine di preferenza. Si sceglie quello che esiste davvero invece di
#: imporne uno: `master` e `main` convivono nel mondo reale, e sbagliare
#: significa aprire una pull request verso un branch che non c'e'.
BRANCH_PRINCIPALI = ("master", "main", "stable", "trunk")

_TIMEOUT_GIT = 300.0


def _git(args: List[str], cwd: Path, timeout_s: float = _TIMEOUT_GIT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

CONFIG_FILE = "delivery.json"

PREDEFINITI: Dict[str, Any] = {
    #: "local" applica il lavoro approvato all'albero di lavoro, com'era prima.
    #: "pull_request" lo porta su `dev` e apre una richiesta verso il principale.
    "mode": "pull_request",
    "integration_branch": BRANCH_INTEGRAZIONE,
    #: Vuoto significa "scoprilo dal repository": vedi `BRANCH_PRINCIPALI`.
    "base_branch": "",
    #: Aprire la richiesta, oltre a spingere il branch.
    "open_pull_request": True,
}


def _percorso_config() -> Path:
    return Path(paths.config_dir()) / CONFIG_FILE


def load_config() -> Dict[str, Any]:
    configurazione = dict(PREDEFINITI)
    percorso = _percorso_config()
    if percorso.is_file():
        try:
            salvate = json.loads(percorso.read_text(encoding="utf-8"))
            if isinstance(salvate, dict):
                configurazione.update(salvate)
        except (OSError, ValueError) as exc:
            log.warning("[Delivery] configurazione illeggibile: %s", exc)
    return configurazione


def save_config(valori: Dict[str, Any]) -> Dict[str, Any]:
    corrente = load_config()
    corrente.update({k: v for k, v in (valori or {}).items() if k in PREDEFINITI})
    percorso = _percorso_config()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(corrente, indent=2), encoding="utf-8")
    return corrente


# ---------------------------------------------------------------------------
# Il repository e i suoi branch
# ---------------------------------------------------------------------------


def remote_url(repo_root: Path | str) -> str:
    res = _git(["remote", "get-url", "origin"], Path(repo_root), timeout_s=30.0)
    return res.stdout.strip() if res.returncode == 0 else ""


def branch_remoti(repo_root: Path | str) -> List[str]:
    """I branch che esistono sul remoto, per nome semplice."""
    res = _git(["ls-remote", "--heads", "origin"], Path(repo_root))
    if res.returncode != 0:
        return []
    nomi = []
    for riga in res.stdout.splitlines():
        pezzi = riga.split("refs/heads/", 1)
        if len(pezzi) == 2 and pezzi[1].strip():
            nomi.append(pezzi[1].strip())
    return nomi


def scopri_branch_principale(repo_root: Path | str, preferito: str = "") -> str:
    """Il branch verso cui aprire la richiesta.

    Chiedere «verso master» in un repository che ha solo `main` produrrebbe una
    pull request verso un branch inesistente: si guarda cosa c'e' davvero, e si
    rispetta la preferenza solo se corrisponde a qualcosa.
    """
    disponibili = branch_remoti(repo_root)
    if preferito and preferito in disponibili:
        return preferito
    if preferito and disponibili:
        log.info("[Delivery] '%s' non esiste sul remoto: uso quello che c'e'", preferito)
    for nome in BRANCH_PRINCIPALI:
        if nome in disponibili:
            return nome
    return disponibili[0] if disponibili else "main"


# ---------------------------------------------------------------------------
# Il worktree di consegna
# ---------------------------------------------------------------------------


def _cartella_consegna(repo_root: Path) -> Path:
    nome = repo_root.name or "repo"
    return Path(paths.var_dir()) / "delivery_worktrees" / nome


def _prepara_worktree(repo_root: Path, branch_dev: str, branch_base: str) -> Tuple[Optional[Path], str]:
    """Un worktree agganciato a `dev`, senza toccare l'albero dell'utente.

    Se `dev` non esiste ancora nasce dal branch principale, cosi' la prima
    richiesta contiene soltanto il lavoro dell'agente e non un anno di storia.
    """
    destinazione = _cartella_consegna(repo_root)
    destinazione.parent.mkdir(parents=True, exist_ok=True)

    _git(["fetch", "origin"], repo_root)

    remoti = branch_remoti(repo_root)
    if branch_dev in remoti:
        punto_di_partenza = f"origin/{branch_dev}"
    elif branch_base in remoti:
        punto_di_partenza = f"origin/{branch_base}"
    else:
        punto_di_partenza = "HEAD"

    if (destinazione / ".git").exists():
        # Riallinea il worktree esistente al remoto. Qui `reset --hard` e'
        # corretto: e' una cartella di servizio, e cio' che contiene e' sempre
        # ricostruibile dal branch del run.
        _git(["checkout", branch_dev], destinazione)
        _git(["reset", "--hard", punto_di_partenza], destinazione)
        _git(["clean", "-fd"], destinazione)
        return destinazione, ""

    if destinazione.exists():
        shutil.rmtree(destinazione, ignore_errors=True)
    res = _git(
        ["worktree", "add", "-B", branch_dev, str(destinazione), punto_di_partenza],
        repo_root,
    )
    if res.returncode != 0:
        return None, f"worktree di consegna non creato: {res.stderr.strip()[:300]}"
    return destinazione, ""


# ---------------------------------------------------------------------------
# La pull request
# ---------------------------------------------------------------------------


def _slug_github(url: str) -> str:
    """`owner/repo` da un indirizzo git, o stringa vuota se non e' GitHub."""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url or "")
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def compare_url(url_remoto: str, base: str, testa: str) -> str:
    """L'indirizzo su cui aprire la richiesta a mano, con un click."""
    slug = _slug_github(url_remoto)
    if not slug:
        return ""
    return f"https://github.com/{slug}/compare/{base}...{testa}?expand=1"


def _apri_con_gh(repo_root: Path, base: str, testa: str,
                 titolo: str, corpo: str) -> Tuple[str, str]:
    if not shutil.which("gh"):
        return "", "gh non installato"
    try:
        res = subprocess.run(
            ["gh", "pr", "create", "--base", base, "--head", testa,
             "--title", titolo, "--body", corpo],
            cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", f"gh non eseguibile: {exc}"

    uscita = (res.stdout or "") + (res.stderr or "")
    m = re.search(r"https://github\.com/\S+/pull/\d+", uscita)
    if m:
        return m.group(0), ""
    if "already exists" in uscita.lower():
        # Una richiesta gia' aperta e' esattamente cio' che serve: il branch e'
        # stato aggiornato e la richiesta la riflette.
        m2 = re.search(r"https://github\.com/\S+/pull/\d+", uscita)
        return (m2.group(0) if m2 else ""), "richiesta gia' aperta"
    return "", (res.stderr or "gh non ha restituito un indirizzo").strip()[:300]


def _apri_con_api(url_remoto: str, base: str, testa: str,
                  titolo: str, corpo: str) -> Tuple[str, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    slug = _slug_github(url_remoto)
    if not token or not slug:
        return "", "nessun token GitHub disponibile"

    richiesta = urllib.request.Request(
        f"https://api.github.com/repos/{slug}/pulls",
        data=json.dumps({"title": titolo, "body": corpo,
                         "head": testa, "base": base}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "SigmaStudio-Harness",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
            return str(dati.get("html_url") or ""), ""
    except urllib.error.HTTPError as exc:
        corpo_errore = exc.read().decode("utf-8", "replace")[:300]
        if "pull request already exists" in corpo_errore.lower():
            return "", "richiesta gia' aperta"
        return "", f"API GitHub {exc.code}: {corpo_errore}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return "", f"API GitHub non raggiungibile: {exc}"


# ---------------------------------------------------------------------------
# Consegna
# ---------------------------------------------------------------------------


@dataclass
class Consegna:
    """Cosa e' successo al lavoro di un run."""

    delivered: bool = False
    branch: str = ""
    base: str = ""
    pushed: bool = False
    pull_request_url: str = ""
    compare_url: str = ""
    files: List[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivered": self.delivered, "branch": self.branch, "base": self.base,
            "pushed": self.pushed, "pull_request_url": self.pull_request_url,
            "compare_url": self.compare_url, "files": self.files, "error": self.error,
        }


def _corpo_richiesta(obiettivo: str, file: List[str], branch_run: str,
                     resoconto: str = "") -> str:
    """Il corpo della richiesta: cosa e' stato fatto e come lo sappiamo.

    Prima elencava obiettivo e nomi di file. Chi doveva accettare il lavoro
    non trovava scritto da nessuna parte **quali criteri** l'agente avesse
    accettato ne' **quale comando** avesse dimostrato il lavoro — e sono le
    due cose che si vogliono sapere prima di premere merge. Il ledger le
    aveva gia' registrate mentre succedevano; qui vengono messe in cima.
    """
    righe = ["Lavoro prodotto da un run dell'agente di Sigma Studio.", ""]
    if resoconto.strip():
        righe += [resoconto.strip(), "", "---", ""]
    righe += [
        f"**Obiettivo:** {obiettivo.strip() or '(non dichiarato)'}",
        "",
        f"**File toccati:** {len(file)}",
    ]
    for nome in file[:60]:
        righe.append(f"- `{nome}`")
    if len(file) > 60:
        righe.append(f"- … e altri {len(file) - 60}")
    righe += [
        "",
        f"Branch del run: `{branch_run}`.",
        "",
        "Il lavoro e' passato dal cancello di completamento dell'harness e dalla",
        "revisione del diff. Resta da accettare qui.",
    ]
    return "\n".join(righe)


#: La consegna usa un worktree di servizio per repository: due run che
#: consegnano insieme si troverebbero a fare merge e push nella stessa cartella,
#: e il secondo vedrebbe l'albero a meta' del primo. Con il ventaglio di run
#: paralleli non e' un caso limite, e' il caso normale.
_lucchetti_consegna: Dict[str, threading.Lock] = {}
_lucchetto_registro = threading.Lock()


def _lucchetto_per(radice: Path) -> threading.Lock:
    chiave = str(radice)
    with _lucchetto_registro:
        lucchetto = _lucchetti_consegna.get(chiave)
        if lucchetto is None:
            lucchetto = threading.Lock()
            _lucchetti_consegna[chiave] = lucchetto
        return lucchetto


def deliver_branch(
    repo_root: Path | str,
    branch_run: str,
    obiettivo: str = "",
    file: Optional[List[str]] = None,
    configurazione: Optional[Dict[str, Any]] = None,
    resoconto: str = "",
) -> Consegna:
    """Porta il branch di un run su `dev` e apre la richiesta verso il principale.

    Non tocca l'albero di lavoro dell'utente: il merge avviene in un worktree
    di servizio. Se qualcosa va storto, il lavoro resta comunque sul branch del
    run — non si perde mai per un errore di consegna.

    Una consegna per volta e per repository: il worktree di servizio e' uno
    solo, e due che ci lavorassero insieme si passerebbero un albero a meta'.
    """
    radice = Path(repo_root).resolve()
    with _lucchetto_per(radice):
        return _deliver_branch_bloccato(radice, branch_run, obiettivo, file,
                                        configurazione, resoconto)


def _deliver_branch_bloccato(
    radice: Path,
    branch_run: str,
    obiettivo: str = "",
    file: Optional[List[str]] = None,
    configurazione: Optional[Dict[str, Any]] = None,
    resoconto: str = "",
) -> Consegna:
    cfg = configurazione or load_config()
    dev = str(cfg.get("integration_branch") or BRANCH_INTEGRAZIONE)
    base = scopri_branch_principale(radice, str(cfg.get("base_branch") or ""))
    esito = Consegna(branch=dev, base=base, files=list(file or []))

    lavoro, errore = _prepara_worktree(radice, dev, base)
    if lavoro is None:
        esito.error = errore
        return esito

    unione = _git(
        ["merge", "--no-ff", branch_run, "-m",
         f"Lavoro dell'agente: {obiettivo.strip()[:120] or branch_run}"],
        lavoro,
    )
    if unione.returncode != 0:
        _git(["merge", "--abort"], lavoro)
        esito.error = (
            f"il lavoro non si innesta su '{dev}' senza conflitti: "
            f"{unione.stderr.strip()[:200]}. Resta sul branch '{branch_run}'."
        )
        return esito

    spinta = _git(["push", "origin", dev], lavoro)
    if spinta.returncode != 0:
        esito.error = (
            f"push di '{dev}' non riuscito: {spinta.stderr.strip()[:200]}. "
            f"Il merge e' pronto in {lavoro}."
        )
        return esito
    esito.pushed = True
    esito.delivered = True

    url = remote_url(radice)
    esito.compare_url = compare_url(url, base, dev)

    if not cfg.get("open_pull_request", True):
        return esito

    titolo = f"Agente: {obiettivo.strip()[:100] or branch_run}"
    corpo = _corpo_richiesta(obiettivo, esito.files, branch_run, resoconto)

    indirizzo, motivo = _apri_con_gh(radice, base, dev, titolo, corpo)
    if not indirizzo:
        indirizzo, motivo_api = _apri_con_api(url, base, dev, titolo, corpo)
        motivo = motivo_api or motivo
    if indirizzo:
        esito.pull_request_url = indirizzo
    elif motivo:
        # Il branch e' su GitHub: la richiesta si apre con un click. Non e' un
        # fallimento della consegna, ed e' importante non presentarlo come tale.
        log.info("[Delivery] richiesta non aperta automaticamente (%s): %s",
                 motivo, esito.compare_url)
    return esito


def deliver_session(
    session_id: str,
    repo_root: Path | str,
    obiettivo: str = "",
    file: Optional[List[str]] = None,
) -> Consegna:
    """Consegna il lavoro di una sessione, dal nome del suo branch."""
    return deliver_branch(
        repo_root,
        f"sigma-run/{str(session_id or '').strip()}",
        obiettivo=obiettivo,
        file=file,
    )


def in_pull_request_mode(configurazione: Optional[Dict[str, Any]] = None) -> bool:
    cfg = configurazione or load_config()
    return str(cfg.get("mode") or "").lower().strip() == "pull_request"
