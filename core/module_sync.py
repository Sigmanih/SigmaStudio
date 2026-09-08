# ==============================================================================
# core/module_sync.py — Il lavoro sui moduli torna al repository dei moduli
# Sigma Studio v8
# ==============================================================================
"""Il verso inverso di `module_loader`: dall'albero vivo al repository dei moduli.

Si sviluppa dentro Sigma Studio — e' li' che c'e' l'IDE, l'agente e il
programma in esecuzione — ma i moduli non appartengono a questo repository:
ognuno dichiara nel proprio `manifest.json` da quale repository viene e in
quale cartella ci sta dentro. Il loader sa portarli da li' a qui. Finora non
esisteva niente che li riportasse indietro, e la conseguenza era che il lavoro
fatto sui moduli **non stava in nessun repository**: non in questo, che li
ignora, e non nel loro, che non veniva mai aggiornato. Un `git clean` bastava
a cancellarlo.

**La sorgente di verita' e' l'albero vivo.** Si modifica qui, si pubblica di
la'. Il file del modulo che sta in Sigma Studio vince su quello nel repository,
perche' e' quello che gira.

**Cosa viene rispecchiato, e cosa no.** Solo i due sottoalberi che il loader
sa installare — `backend/` e `frontend/` — piu' i file di radice del modulo
(`manifest.json`, `requirements.txt`, `README.md`). Tutto il resto di quella
cartella nel repository, `tests/` compreso, non viene toccato: rispecchiare
significa anche cancellare cio' che non esiste piu' qui, e cancellare file che
questo lato non sa produrre sarebbe distruggere lavoro senza guardarlo.
"""

from __future__ import annotations

import filecmp
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core import paths
from core.logger import get_logger

log = get_logger("module_sync")

_CORE_MODULES_DIR = Path(paths.modules_backend_dir())
_FRONTEND_MODULES_DIR = Path(paths.frontend_modules_dir())

#: File di radice del modulo: il loader li copia dentro il backend installato,
#: quindi qui li ritrova li' e li rimette al posto giusto.
FILE_DI_RADICE = ("manifest.json", "requirements.txt", "README.md")

#: Cartelle e file che non appartengono a un repository: prodotti di
#: compilazione, cache, dipendenze scaricate.
ESCLUSI = (
    "__pycache__", ".git", ".pytest_cache", "node_modules", ".venv",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".DS_Store",
)
ESTENSIONI_ESCLUSE = (".pyc", ".pyo", ".pyd", ".log", ".tmp", ".swp")

#: Nomi che di solito contengono credenziali. Un modulo non dovrebbe averne —
#: la configurazione vive in `config/`, che sta fuori — ma se ce ne finisce uno
#: la sincronizzazione lo pubblicherebbe su GitHub, e da li' non si torna.
SOSPETTI_SEGRETI = re.compile(
    r"(^\.env|(^|[._-])(secret|secrets|credential|credentials|token|apikey|api_key)([._-]|$)"
    r"|\.pem$|\.key$|id_rsa)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Cosa c'e' da sincronizzare
# ---------------------------------------------------------------------------


@dataclass
class ModuloLocale:
    """Un modulo installato e il posto da cui viene."""

    module_id: str
    repository: str
    branch: str
    path_nel_repo: str
    backend_dir: Path
    frontend_dir: Optional[Path]

    @property
    def ha_sorgente(self) -> bool:
        return self.backend_dir.is_dir() or bool(
            self.frontend_dir and self.frontend_dir.is_dir()
        )


def _leggi_manifest(percorso: Path) -> Dict[str, Any]:
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("[ModuleSync] manifest illeggibile in %s: %s", percorso, exc)
        return {}


def discover_modules() -> List[ModuloLocale]:
    """I moduli installati che dichiarano un repository di provenienza.

    Un modulo senza `repository` nel manifest non e' un modulo pubblicato: non
    si inventa dove mandarlo.
    """
    trovati: List[ModuloLocale] = []
    if not _CORE_MODULES_DIR.is_dir():
        return trovati

    for cartella in sorted(_CORE_MODULES_DIR.iterdir()):
        manifest_path = cartella / "manifest.json"
        if not manifest_path.is_file():
            continue
        dati = _leggi_manifest(manifest_path)
        repository = str(dati.get("repository") or "").strip()
        if not repository:
            continue
        # Un manifest puo' dichiarare l'indirizzo nella forma con cui si copia
        # dal browser — ".../tree/main/modules/x" — che non e' un indirizzo git
        # clonabile. Il loader sa gia' districarla: si riusa quella, invece di
        # tenerne una seconda copia che col tempo divergerebbe.
        branch_dichiarato = str(dati.get("branch") or "").strip()
        path_dichiarato = str(dati.get("path") or "").strip("/")
        try:
            from core.module_loader import _sanitize_git_url
            repository, branch_url, path_url = _sanitize_git_url(repository)
            branch_dichiarato = branch_dichiarato or branch_url
            path_dichiarato = path_dichiarato or path_url
        except ImportError:
            pass
        # Il nome della cartella vince sull'`id` dichiarato: e' quello che il
        # sistema usa davvero per importare il modulo, e un manifest che dice
        # altro descrive un modulo che non esiste.
        module_id = cartella.name
        frontend = _FRONTEND_MODULES_DIR / module_id
        trovati.append(ModuloLocale(
            module_id=module_id,
            repository=repository,
            branch=branch_dichiarato or "main",
            path_nel_repo=path_dichiarato or f"modules/{module_id}",
            backend_dir=cartella,
            frontend_dir=frontend if frontend.is_dir() else None,
        ))
    return trovati


#: Cartelle sotto `core/modules/` che non sono moduli e non vanno segnalate.
_NON_MODULI = frozenset({"__pycache__", "common", ".pytest_cache"})


def orphan_modules() -> List[Dict[str, str]]:
    """I moduli installati che nessuna sincronizzazione puo' pubblicare.

    Un modulo senza `manifest.json`, o con un manifest che non dice da dove
    viene, viene saltato: e' giusto, perche' non si inventa dove mandarlo. Ma
    saltarlo **in silenzio** e' come non averlo — il suo codice gira e non sta
    in nessun repository, ed e' esattamente cosi' che `sigma_audio_studio` e'
    rimasto fuori senza che nessuno se ne accorgesse.

    Qui vengono elencati con il motivo, perche' un problema che si vede si
    risolve.
    """
    orfani: List[Dict[str, str]] = []
    for radice, tipo in ((_CORE_MODULES_DIR, "backend"),
                         (_FRONTEND_MODULES_DIR, "frontend")):
        if not radice.is_dir():
            continue
        for cartella in sorted(radice.iterdir()):
            if not cartella.is_dir() or cartella.name in _NON_MODULI:
                continue
            if cartella.name.startswith("."):
                continue
            manifest = _CORE_MODULES_DIR / cartella.name / "manifest.json"
            if not manifest.is_file():
                motivo = "nessun manifest.json"
            elif not str(_leggi_manifest(manifest).get("repository") or "").strip():
                motivo = "il manifest non dichiara da quale repository viene"
            else:
                continue
            if any(o["module_id"] == cartella.name for o in orfani):
                continue
            orfani.append({"module_id": cartella.name, "reason": motivo, "side": tipo})
    return orfani


# ---------------------------------------------------------------------------
# Rispecchiamento di un sottoalbero
# ---------------------------------------------------------------------------


def _copia(sorgente: Path, destinazione: Path) -> None:
    """Copia il contenuto, non la data.

    `shutil.copy2` avrebbe portato con se' anche la data del file di partenza,
    e li' nasceva un difetto intermittente: git decide se un file e' cambiato
    guardando prima la coppia (data, dimensione) registrata nell'indice, e solo
    se una delle due e' diversa va a rileggere il contenuto. Due versioni della
    stessa riga hanno la stessa dimensione; con la data ereditata dal sorgente
    capitava che coincidesse anche quella, e allora `git status` dichiarava il
    file invariato. La modifica era sul disco, il commit non partiva, e non lo
    diceva nessuno.

    Una data nuova a ogni copia toglie il caso: e' sempre piu' recente di
    quella nell'indice. Del resto qui non si sta facendo un backup, si sta
    pubblicando: la data che conta e' quella del commit.
    """
    shutil.copyfile(sorgente, destinazione)


def _da_ignorare(nome: str) -> bool:
    if nome in ESCLUSI:
        return True
    return any(nome.endswith(est) for est in ESTENSIONI_ESCLUSE)


def _file_rilevanti(radice: Path) -> Iterable[Path]:
    """I percorsi relativi dei file da pubblicare sotto `radice`."""
    for cartella_corrente, sottocartelle, file in os.walk(radice):
        sottocartelle[:] = [d for d in sottocartelle if not _da_ignorare(d)]
        for nome in file:
            if _da_ignorare(nome):
                continue
            yield Path(cartella_corrente, nome).relative_to(radice)


@dataclass
class Rispecchiamento:
    """Cosa e' cambiato rispecchiando un sottoalbero."""

    aggiunti: List[str] = field(default_factory=list)
    modificati: List[str] = field(default_factory=list)
    rimossi: List[str] = field(default_factory=list)
    segreti_saltati: List[str] = field(default_factory=list)

    @property
    def vuoto(self) -> bool:
        return not (self.aggiunti or self.modificati or self.rimossi)

    def unisci(self, altro: "Rispecchiamento", prefisso: str = "") -> None:
        for campo in ("aggiunti", "modificati", "rimossi", "segreti_saltati"):
            getattr(self, campo).extend(
                f"{prefisso}{v}" for v in getattr(altro, campo)
            )


def mirror_tree(sorgente: Path, destinazione: Path,
                apply: bool = True) -> Rispecchiamento:
    """Rende `destinazione` identica a `sorgente`, cancellazioni comprese.

    Cancellare e' la meta' che serve davvero: senza, un file rinominato qui
    resta anche col vecchio nome nel repository, e chi installa il modulo si
    ritrova due versioni dello stesso codice.

    Con `apply=False` calcola e basta, senza toccare niente. Serve alla prova
    a vuoto, che altrimenti non sarebbe una prova: rispecchiando davvero,
    consumava le differenze che stava elencando, e la volta dopo dichiarava
    tutto allineato. Chi guardava il pannello avrebbe letto "niente da
    pubblicare" su del lavoro mai pubblicato.
    """
    esito = Rispecchiamento()
    if not sorgente.is_dir():
        return esito

    attesi = set()
    for relativo in _file_rilevanti(sorgente):
        if SOSPETTI_SEGRETI.search(relativo.name):
            # Pubblicare su GitHub non si annulla: nel dubbio non parte.
            esito.segreti_saltati.append(str(relativo).replace("\\", "/"))
            log.warning(
                "[ModuleSync] '%s' non pubblicato: il nome fa pensare a "
                "credenziali", relativo,
            )
            continue
        attesi.add(relativo)

        src = sorgente / relativo
        dst = destinazione / relativo
        chiave = str(relativo).replace("\\", "/")
        if not dst.exists():
            if apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                _copia(src, dst)
            esito.aggiunti.append(chiave)
        elif not filecmp.cmp(src, dst, shallow=False):
            if apply:
                _copia(src, dst)
            esito.modificati.append(chiave)

    if destinazione.is_dir():
        for relativo in list(_file_rilevanti(destinazione)):
            if relativo in attesi:
                continue
            if apply:
                (destinazione / relativo).unlink(missing_ok=True)
            esito.rimossi.append(str(relativo).replace("\\", "/"))

    if apply:
        _rimuovi_cartelle_vuote(destinazione)
    return esito


def _rimuovi_cartelle_vuote(radice: Path) -> None:
    if not radice.is_dir():
        return
    for cartella, _, _ in sorted(os.walk(radice), reverse=True):
        p = Path(cartella)
        if p == radice:
            continue
        try:
            if not any(p.iterdir()):
                p.rmdir()
        except OSError:
            pass


def stage_module(modulo: ModuloLocale, radice_repo: Path,
                 apply: bool = True) -> Rispecchiamento:
    """Porta un modulo dall'albero vivo dentro la copia del suo repository.

    Con `apply=False` dice soltanto cosa cambierebbe.
    """
    destinazione = radice_repo / modulo.path_nel_repo
    if apply:
        destinazione.mkdir(parents=True, exist_ok=True)

    esito = Rispecchiamento()

    # I file di radice: il loader li deposita dentro il backend installato,
    # quindi e' li' che stanno adesso, ed e' dalla radice che vanno ripresi.
    for nome in FILE_DI_RADICE:
        origine = modulo.backend_dir / nome
        arrivo = destinazione / nome
        if not origine.is_file():
            continue
        if not arrivo.exists():
            if apply:
                arrivo.parent.mkdir(parents=True, exist_ok=True)
                _copia(origine, arrivo)
            esito.aggiunti.append(nome)
        elif not filecmp.cmp(origine, arrivo, shallow=False):
            if apply:
                _copia(origine, arrivo)
            esito.modificati.append(nome)

    # Il backend, meno i file di radice che hanno gia' il loro posto.
    backend_esito = _mirror_backend(modulo.backend_dir, destinazione / "backend", apply)
    esito.unisci(backend_esito, "backend/")

    if modulo.frontend_dir:
        esito.unisci(
            mirror_tree(modulo.frontend_dir, destinazione / "frontend", apply),
            "frontend/",
        )

    return esito


def _mirror_backend(sorgente: Path, destinazione: Path,
                    apply: bool = True) -> Rispecchiamento:
    """Come `mirror_tree`, ma senza i file che appartengono alla radice.

    Copiarli anche qui li duplicherebbe: il loader li rimettera' comunque nel
    backend al momento dell'installazione, ed e' quella la copia buona.
    """
    if not sorgente.is_dir():
        return Rispecchiamento()

    # La cartella d'appoggio sta FUORI dal repository. Metterla dentro creava
    # l'albero del modulo anche durante una prova a vuoto — che a quel punto
    # non era piu' a vuoto — e lasciava una cartella nascosta dentro il
    # repository se qualcosa si fermava a meta'.
    temporanea = Path(tempfile.mkdtemp(prefix="sigma_module_sync_"))
    try:
        for relativo in _file_rilevanti(sorgente):
            if relativo.parent == Path(".") and relativo.name in FILE_DI_RADICE:
                continue
            arrivo = temporanea / relativo
            arrivo.parent.mkdir(parents=True, exist_ok=True)
            _copia(sorgente / relativo, arrivo)
        return mirror_tree(temporanea, destinazione, apply)
    finally:
        shutil.rmtree(temporanea, ignore_errors=True)


# ---------------------------------------------------------------------------
# La copia di lavoro del repository dei moduli
# ---------------------------------------------------------------------------


def _esegui_git(args: List[str], cwd: Path, timeout_s: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
    )


def _nome_cartella_repo(repository: str) -> str:
    pulito = repository.rstrip("/")
    if pulito.endswith(".git"):
        pulito = pulito[:-4]
    return pulito.rsplit("/", 1)[-1] or "moduli"


def repo_workdir(repository: str) -> Path:
    """Dove vive la copia di lavoro di un repository dei moduli.

    Sotto `var/`, che e' stato di runtime: non appartiene a questo repository e
    non va versionata: e' un mezzo, non un contenuto.
    """
    return Path(paths.var_dir()) / "module_repos" / _nome_cartella_repo(repository)


def ensure_clone(repository: str, branch: str = "main") -> Tuple[Optional[Path], str]:
    """La copia di lavoro aggiornata del repository. Ritorna (percorso, errore)."""
    destinazione = repo_workdir(repository)
    destinazione.parent.mkdir(parents=True, exist_ok=True)

    if not (destinazione / ".git").is_dir():
        if destinazione.exists():
            shutil.rmtree(destinazione, ignore_errors=True)
        res = subprocess.run(
            ["git", "clone", "--branch", branch, repository, str(destinazione)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600.0,
        )
        if res.returncode != 0:
            return None, f"clone fallito: {res.stderr.strip()[:400]}"
        return destinazione, ""

    fetch = _esegui_git(["fetch", "origin", branch], destinazione, timeout_s=300.0)
    if fetch.returncode != 0:
        return destinazione, f"fetch fallito: {fetch.stderr.strip()[:400]}"

    # Il rispecchiamento di una volta precedente puo' aver lasciato modifiche
    # non committate — una prova a vuoto le lascia sempre — e `rebase` su un
    # albero sporco si rifiuta di partire. Quei file si buttano senza pensarci:
    # non li ha scritti nessuno a mano, li produce `stage_module` dall'albero
    # vivo, e verranno riprodotti identici fra un istante.
    sporco = _esegui_git(["status", "--porcelain"], destinazione)
    if sporco.stdout.strip():
        _esegui_git(["checkout", "--", "."], destinazione)
        _esegui_git(["clean", "-fd"], destinazione)

    # `rebase` e non `reset --hard`: se un push precedente non era andato a
    # buon fine, i commit locali sono l'unica copia di quel lavoro e azzerarli
    # sarebbe esattamente il difetto che questo modulo esiste per togliere.
    rebase = _esegui_git(["rebase", f"origin/{branch}"], destinazione)
    if rebase.returncode != 0:
        _esegui_git(["rebase", "--abort"], destinazione)
        return destinazione, (
            "la copia locale diverge dal remoto e il riallineamento non e' "
            "automatico: risolvi a mano in " + str(destinazione)
        )
    return destinazione, ""


# ---------------------------------------------------------------------------
# La sincronizzazione
# ---------------------------------------------------------------------------


def _messaggio_commit(cambiati: Dict[str, Rispecchiamento], nota: str = "") -> str:
    nomi = sorted(cambiati)
    if len(nomi) == 1:
        titolo = f"Aggiorna {nomi[0]} da Sigma Studio"
    else:
        titolo = f"Aggiorna {len(nomi)} moduli da Sigma Studio"

    righe = [titolo, ""]
    if nota:
        righe += [nota, ""]
    for nome in nomi:
        e = cambiati[nome]
        righe.append(
            f"* {nome}: {len(e.aggiunti)} aggiunti, "
            f"{len(e.modificati)} modificati, {len(e.rimossi)} rimossi"
        )
    return "\n".join(righe)


def sync_modules(
    module_ids: Optional[Iterable[str]] = None,
    push: bool = False,
    nota: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Riporta i moduli modificati nel loro repository.

    `push` e' separato dal commit apposta: committare e' reversibile e resta
    su questa macchina, pubblicare no. Chi chiama decide, e per l'automatismo
    la decisione la prende la configurazione dell'utente, non questo modulo.

    `dry_run` prepara tutto e si ferma prima di committare: serve a vedere cosa
    partirebbe.
    """
    voluti = set(module_ids) if module_ids else None
    moduli = [
        m for m in discover_modules()
        if m.ha_sorgente and (voluti is None or m.module_id in voluti)
    ]

    esito: Dict[str, Any] = {
        "success": True, "repos": [], "changed": {}, "skipped_secrets": [],
        "errors": [], "pushed": False, "committed": False, "dry_run": bool(dry_run),
        # Cio' che gira ma non puo' essere pubblicato da nessuna parte.
        "orphans": orphan_modules(),
    }
    if not moduli:
        esito["message"] = "Nessun modulo da sincronizzare."
        return esito

    per_repo: Dict[Tuple[str, str], List[ModuloLocale]] = {}
    for m in moduli:
        per_repo.setdefault((m.repository, m.branch), []).append(m)

    for (repository, branch), gruppo in per_repo.items():
        radice, errore = ensure_clone(repository, branch)
        if radice is None:
            esito["success"] = False
            esito["errors"].append(f"{repository}: {errore}")
            continue
        if errore:
            esito["success"] = False
            esito["errors"].append(f"{repository}: {errore}")
            continue

        cambiati: Dict[str, Rispecchiamento] = {}
        for modulo in gruppo:
            rispecchiato = stage_module(modulo, radice, apply=not dry_run)
            esito["skipped_secrets"].extend(
                f"{modulo.module_id}/{s}" for s in rispecchiato.segreti_saltati
            )
            if not rispecchiato.vuoto:
                cambiati[modulo.module_id] = rispecchiato

        riepilogo = {
            nome: {
                "aggiunti": e.aggiunti, "modificati": e.modificati, "rimossi": e.rimossi,
            }
            for nome, e in cambiati.items()
        }
        esito["changed"].update(riepilogo)
        esito["repos"].append({
            "repository": repository, "branch": branch,
            "workdir": str(radice), "modules": [m.module_id for m in gruppo],
        })

        if not cambiati:
            log.info("[ModuleSync] %s: nessuna modifica da pubblicare", repository)
            continue
        if dry_run:
            continue

        _esegui_git(["add", "-A"], radice)
        stato = _esegui_git(["status", "--porcelain"], radice)
        if not stato.stdout.strip():
            # Il rispecchiamento ha scritto qualcosa e git non lo vede: e' la
            # cache di stat dell'indice. Si forza una rilettura vera invece di
            # concludere che non c'era niente da fare — e' esattamente cosi'
            # che una modifica spariva senza un messaggio.
            log.warning(
                "[ModuleSync] %s: %d moduli modificati ma git non vede nulla, "
                "rileggo l'indice", repository, len(cambiati),
            )
            _esegui_git(["update-index", "--really-refresh"], radice)
            _esegui_git(["add", "-A"], radice)
            stato = _esegui_git(["status", "--porcelain"], radice)
        if not stato.stdout.strip():
            esito["success"] = False
            esito["errors"].append(
                f"{repository}: {len(cambiati)} moduli risultano modificati ma "
                "git non registra alcuna differenza. Il lavoro e' in "
                f"{radice}: controllalo prima di rifare la sincronizzazione."
            )
            continue

        commit = _esegui_git(
            ["commit", "-m", _messaggio_commit(cambiati, nota)], radice
        )
        if commit.returncode != 0:
            esito["success"] = False
            esito["errors"].append(
                f"{repository}: commit fallito: {commit.stderr.strip()[:300]}"
            )
            continue
        esito["committed"] = True
        log.info("[ModuleSync] %s: commit creato per %s",
                 repository, ", ".join(sorted(cambiati)))

        if push:
            spinta = _esegui_git(["push", "origin", branch], radice, timeout_s=600.0)
            if spinta.returncode != 0:
                esito["success"] = False
                esito["errors"].append(
                    f"{repository}: push fallito: {spinta.stderr.strip()[:300]}. "
                    "Il commit resta in " + str(radice)
                )
            else:
                esito["pushed"] = True
                log.info("[ModuleSync] %s: pubblicato su %s", repository, branch)

    return esito


def modules_touched_by(paths_toccati: Iterable[str]) -> List[str]:
    """Quali moduli riguardano dei percorsi modificati.

    Serve a chi ha appena scritto dei file e non sa se appartengano a un
    modulo: un run dell'agente, per esempio.
    """
    noti = {m.module_id: m for m in discover_modules()}
    colpiti: List[str] = []
    for grezzo in paths_toccati:
        try:
            p = Path(str(grezzo)).resolve()
        except (OSError, ValueError):
            continue
        for module_id, modulo in noti.items():
            if module_id in colpiti:
                continue
            radici = [modulo.backend_dir]
            if modulo.frontend_dir:
                radici.append(modulo.frontend_dir)
            for radice in radici:
                try:
                    p.relative_to(radice.resolve())
                except ValueError:
                    continue
                colpiti.append(module_id)
                break
    return colpiti


# ---------------------------------------------------------------------------
# Sincronizzazione automatica
# ---------------------------------------------------------------------------
#
# Si sviluppa dentro Sigma Studio e si pubblica di la': l'automatismo esiste
# perche' il passaggio manuale e' esattamente quello che finora non avveniva
# mai, ed e' il motivo per cui il repository dei moduli era rimasto indietro.

CONFIG_FILE = "module_sync.json"

#: Cosa fare quando un run tocca dei file di un modulo. Il commit e' acceso
#: perche' e' locale e reversibile; il push perche' l'utente ha chiesto che il
#: lavoro finisca nel posto giusto senza doverci pensare ogni volta.
PREDEFINITI: Dict[str, Any] = {
    "auto_commit": True,
    "auto_push": True,
    #: Quanto attendere prima di ripetere una sincronizzazione non
    #: richiesta. Salvare un file nell'editor e' un gesto continuo:
    #: senza attesa ogni battuta di "salva" diventerebbe un commit, e la
    #: storia del repository dei moduli sarebbe illeggibile.
    "min_interval_s": 180,
    #: Se mostrare il pannello di pubblicazione nel Developer Studio.
    #:
    #: Spento di default, e non e' prudenza generica: pubblicare vuol dire
    #: spingere su un repository che appartiene a qualcuno. Chi installa Sigma
    #: Studio non ha i permessi su SigmaStudio-Moduli, e un pulsante che
    #: fallisce sempre e' peggio di un pulsante assente. Lo accende chi quei
    #: permessi ce li ha.
    "show_publish_ui": False,
}


def _percorso_config() -> Path:
    return Path(paths.config_dir()) / CONFIG_FILE


def load_config() -> Dict[str, Any]:
    """Le preferenze di sincronizzazione, con i predefiniti sotto."""
    configurazione = dict(PREDEFINITI)
    percorso = _percorso_config()
    if percorso.is_file():
        try:
            salvate = json.loads(percorso.read_text(encoding="utf-8"))
            if isinstance(salvate, dict):
                configurazione.update(salvate)
        except (OSError, ValueError) as exc:
            log.warning("[ModuleSync] configurazione illeggibile: %s", exc)
    return configurazione


def save_config(valori: Dict[str, Any]) -> Dict[str, Any]:
    """Scrive le preferenze, tenendo solo le chiavi note."""
    corrente = load_config()
    corrente.update({k: v for k, v in (valori or {}).items() if k in PREDEFINITI})
    percorso = _percorso_config()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(corrente, indent=2), encoding="utf-8")
    return corrente


#: Quando e' stata l'ultima sincronizzazione automatica non richiesta.
_ultima_automatica: float = 0.0
_lucchetto_automatica = threading.Lock()


def auto_sync_paths(
    paths_toccati: Iterable[str],
    nota: str = "",
    immediate: bool = True,
) -> Optional[Dict[str, Any]]:
    """Sincronizza i moduli toccati da questi percorsi, se la config lo prevede.

    `immediate` distingue i due momenti in cui l'automatismo scatta. La fine di
    un run e' un evento raro e concluso: si sincronizza subito. Il salvataggio
    di un file nell'editor no — e' un gesto che si ripete ogni pochi secondi, e
    trattarlo allo stesso modo riempirebbe il repository di commit da una riga.
    Li' si aspetta `min_interval_s` fra una volta e l'altra.

    Ritorna None quando non c'e' niente da fare. Non solleva mai: e' un passo
    accessorio, e far fallire un salvataggio perche' git non risponde sarebbe
    sproporzionato.
    """
    global _ultima_automatica
    try:
        configurazione = load_config()
        if not configurazione.get("auto_commit", True):
            return None

        if not immediate:
            attesa = float(configurazione.get("min_interval_s", 180) or 0)
            with _lucchetto_automatica:
                if time.monotonic() - _ultima_automatica < attesa:
                    return None
                _ultima_automatica = time.monotonic()
        else:
            with _lucchetto_automatica:
                _ultima_automatica = time.monotonic()

        toccati = modules_touched_by(paths_toccati)
        if not toccati:
            return None
        return sync_modules(
            module_ids=toccati,
            push=bool(configurazione.get("auto_push", True)),
            nota=nota,
        )
    except Exception as exc:
        log.warning("[ModuleSync] sincronizzazione automatica non riuscita: %s", exc)
        return {"success": False, "errors": [str(exc)], "changed": {}}


def auto_sync_in_background(paths_toccati: Iterable[str], nota: str = "") -> None:
    """Come sopra, ma senza far aspettare chi ha appena salvato un file.

    Parlare con GitHub puo' richiedere secondi; un salvataggio nell'editor deve
    tornare subito. Il thread e' `daemon` perche' una sincronizzazione in corso
    non e' un buon motivo per tenere in vita il programma alla chiusura.
    """
    percorsi = [str(p) for p in paths_toccati]
    if not percorsi:
        return
    threading.Thread(
        target=lambda: auto_sync_paths(percorsi, nota=nota, immediate=False),
        name="module-sync",
        daemon=True,
    ).start()


# ---------------------------------------------------------------------------
# Uso da riga di comando
# ---------------------------------------------------------------------------
#     python -m core.module_sync            cosa partirebbe, senza far partire niente
#     python -m core.module_sync --push     pubblica
#     python -m core.module_sync --push --module sigma_network


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Riporta il lavoro fatto sui moduli nel loro repository.",
    )
    parser.add_argument("--push", action="store_true",
                        help="pubblica sul remoto (senza, si ferma al commit locale)")
    parser.add_argument("--module", action="append", dest="modules", metavar="ID",
                        help="limita a un modulo; ripetibile")
    parser.add_argument("--note", default="", help="riga di contesto nel messaggio di commit")
    parser.add_argument("--commit", action="store_true",
                        help="committa in locale (senza --push ne' --commit e' una prova a vuoto)")
    args = parser.parse_args(argv)

    esito = sync_modules(
        module_ids=args.modules,
        push=args.push,
        nota=args.note,
        dry_run=not (args.push or args.commit),
    )

    cambiati = esito.get("changed") or {}
    if not cambiati:
        print("Nessuna modifica da pubblicare.")
    for nome in sorted(cambiati):
        c = cambiati[nome]
        print("%-26s +%-4d ~%-4d -%d" % (
            nome, len(c["aggiunti"]), len(c["modificati"]), len(c["rimossi"])))

    for sospetto in esito.get("skipped_secrets") or []:
        print(f"NON pubblicato (sembra una credenziale): {sospetto}")

    for orfano in esito.get("orphans") or []:
        print("FUORI DA OGNI REPOSITORY: %s (%s)"
              % (orfano["module_id"], orfano["reason"]))

    if esito.get("dry_run") and cambiati:
        print("\nProva a vuoto: niente e' stato committato. Aggiungi --push per pubblicare.")
    elif esito.get("pushed"):
        print("\nPubblicato.")
    elif esito.get("committed"):
        print("\nCommit creato in locale, non pubblicato. Aggiungi --push per mandarlo.")

    for errore in esito.get("errors") or []:
        print(f"ERRORE: {errore}")
    return 0 if esito.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
