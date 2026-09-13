# ==============================================================================
# core/progetti.py — Dove nascono le applicazioni che gli agenti costruiscono
# Sigma Studio v8
# ==============================================================================
"""L'indirizzo di sviluppo: una cartella sola dove stanno i progetti esterni.

Finora un run si apriva su una cartella qualsiasi, e il selettore
dell'interfaccia offriva la radice di Sigma Studio, la cartella utente e **ogni
lettera di unita'**. Scegliere `C:/` come cartella di lavoro di un ventaglio
era a un clic: da li' un agente ha per definizione il permesso di scrivere
ovunque, perche' «ovunque» e' dentro la sua radice.

Serviva un posto dichiarato. `data/progetti/` di default — dentro `data/`,
che e' la radice del lavoro dell'utente — e cambiabile, perche' i progetti
grossi stanno spesso su un altro disco.

**Questo modulo non e' una difesa da solo.** Una cartella predefinita orienta,
non impedisce: la difesa e' `radice_pericolosa()`, che rifiuta di far partire
un run su una radice troppo larga, e il confine dei percorsi in
`resolve_workspace_path`. Insieme dicono la stessa cosa da due lati: un agente
lavora dentro un progetto, e un disco intero non e' un progetto.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger("progetti")

#: Il nome della cartella dentro `data/`. Sta in `data/` e non in `var/` perche'
#: e' lavoro dell'utente: `var/` si puo' cancellare senza perdere niente, e
#: qui dentro ci sono interi progetti.
CARTELLA_PREDEFINITA = "progetti"

#: Caratteri che non possono stare in un nome di cartella su Windows, piu' gli
#: spazi in testa e in coda che passano inosservati e rompono i percorsi.
_NOME_PULITO = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _percorso_config() -> Path:
    return Path(paths.config_dir()) / "progetti.json"


def radice_progetti() -> Path:
    """La cartella dove nascono i progetti. Creata se non c'e'."""
    scelta = ""
    percorso = _percorso_config()
    if percorso.is_file():
        try:
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            scelta = str(dati.get("root") or "").strip()
        except (OSError, ValueError) as exc:
            log.warning("[Progetti] configurazione illeggibile: %s", exc)

    radice = Path(scelta) if scelta else Path(paths.workspace_dir()) / CARTELLA_PREDEFINITA
    try:
        radice.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("[Progetti] '%s' non creabile: %s", radice, exc)
    return radice.resolve()


def imposta_radice(percorso: str) -> Dict[str, Any]:
    """Cambia l'indirizzo di sviluppo. Ritorna la configurazione risultante.

    Una radice pericolosa viene rifiutata qui e non piu' avanti: accettarla e
    poi impedire ogni run che la usa sarebbe dire di si' e poi di no.
    """
    pulito = str(percorso or "").strip()
    if not pulito:
        raise ValueError("Serve un percorso.")
    motivo = radice_pericolosa(pulito)
    if motivo:
        raise ValueError(motivo)

    radice = Path(pulito).expanduser()
    radice.mkdir(parents=True, exist_ok=True)
    file_config = _percorso_config()
    file_config.parent.mkdir(parents=True, exist_ok=True)
    file_config.write_text(
        json.dumps({"root": str(radice.resolve())}, indent=2), encoding="utf-8")
    return {"root": str(radice.resolve()).replace("\\", "/")}


def nome_valido(nome: str) -> str:
    """Un nome di cartella utilizzabile, o solleva se non se ne ricava uno."""
    pulito = _NOME_PULITO.sub("", str(nome or "")).strip().strip(".")
    if not pulito:
        raise ValueError(
            f"'{nome}' non e' utilizzabile come nome di cartella.")
    return pulito


def crea_progetto(nome: str) -> Path:
    """Crea la cartella di un progetto nuovo sotto la radice dei progetti."""
    cartella = radice_progetti() / nome_valido(nome)
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella


def _e_un_repository(cartella: Path) -> bool:
    return (cartella / ".git").exists()


def elenca_progetti() -> List[Dict[str, Any]]:
    """I progetti presenti, dal piu' recentemente toccato."""
    radice = radice_progetti()
    trovati: List[Dict[str, Any]] = []
    try:
        voci = list(radice.iterdir())
    except OSError as exc:
        log.warning("[Progetti] '%s' non leggibile: %s", radice, exc)
        return []
    for cartella in voci:
        if not cartella.is_dir() or cartella.name.startswith("."):
            continue
        try:
            toccato = cartella.stat().st_mtime
        except OSError:
            toccato = 0.0
        trovati.append({
            "name": cartella.name,
            "path": str(cartella).replace("\\", "/"),
            "is_git": _e_un_repository(cartella),
            "updated_at": toccato,
        })
    return sorted(trovati, key=lambda p: -p["updated_at"])


# ---------------------------------------------------------------------------
# Quali radici non si danno a un agente
# ---------------------------------------------------------------------------
# Il confine dei percorsi impedisce di uscire dalla radice. Non dice niente su
# quanto quella radice sia larga: con `C:/` come radice, «non uscire» non
# vieta piu' nulla. E' l'altra meta' della stessa difesa.

def _radici_di_sistema() -> List[Path]:
    candidate = [os.environ.get("SystemRoot"), os.environ.get("ProgramFiles"),
                 os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramData"),
                 "/etc", "/usr", "/bin", "/sbin", "/var", "/boot", "/System"]
    fuori: List[Path] = []
    for c in candidate:
        if not c:
            continue
        try:
            fuori.append(Path(c).resolve())
        except OSError:
            continue
    return fuori


def radice_pericolosa(percorso: str) -> str:
    """Il motivo per cui quella radice non va data a un agente, o "" se va bene.

    Non e' un elenco di cartelle vietate: e' una domanda sola — quella radice
    e' **un progetto**, o e' il posto dove stanno tutti i progetti e tutto il
    resto? Un disco intero, la cartella utente e le cartelle di sistema
    rispondono la seconda cosa.
    """
    testo = str(percorso or "").strip()
    if not testo:
        return "Nessuna cartella di lavoro indicata."
    try:
        radice = Path(testo).expanduser().resolve()
    except (OSError, RuntimeError):
        return f"'{testo}' non e' un percorso valido."

    if radice.parent == radice:
        return (f"'{radice}' e' la radice di un disco. Un agente che lavora "
                "qui puo' scrivere ovunque: indica la cartella di un progetto.")

    try:
        casa = Path.home().resolve()
    except (OSError, RuntimeError):
        casa = None
    if casa is not None and radice == casa:
        return (f"'{radice}' e' la cartella utente: contiene documenti, "
                "configurazioni e credenziali. Indica la cartella di un progetto.")

    for sistema in _radici_di_sistema():
        if radice == sistema or sistema in radice.parents:
            return (f"'{radice}' sta dentro una cartella di sistema ({sistema}). "
                    "Non e' un posto dove far lavorare un agente.")

    try:
        configurazione = Path(paths.config_dir()).resolve()
    except (OSError, RuntimeError):
        configurazione = None
    if configurazione is not None and (
            radice == configurazione or configurazione == radice):
        return (f"'{radice}' e' la cartella della configurazione, "
                "che contiene credenziali.")

    return ""


def radice_di_lavoro_valida(percorso: Optional[str]) -> str:
    """La radice da usare, o solleva `ValueError` col motivo del rifiuto."""
    testo = str(percorso or "").strip()
    if not testo:
        from core.harness.fs_manager import get_default_workspace_root
        testo = get_default_workspace_root()
    motivo = radice_pericolosa(testo)
    if motivo:
        raise ValueError(motivo)
    return testo
