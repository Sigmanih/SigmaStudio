# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/fs_server.py - File di sviluppo
# Sigma Studio v8 - Modulo installabile
# ==============================================================================
"""Le primitive di filesystem dell harness, esposte come tool MCP.

**Perche esiste.** Nel Developer Studio i tool che scrivono file non passano
dall hub MCP: sono `LOCAL_TOOLS` del ciclo (`core/harness/fs_tools.py`), e l hub
non li vede. Un agente esterno - un altro IDE, un assistente collegato - non
aveva modo di scrivere con le stesse garanzie degli agenti locali: backup
automatico, controllo di sintassi, rifiuto dei troncamenti involontari. Finiva
per usare la shell, e una scrittura dalla shell e una scrittura di cui nessuno
sa niente: e il caso dei dieci estratti in `tools/*_src.txt`, e quello delle
modifiche che il cancello di completamento non riesce a dimostrare.

**Dove resta la traccia.** Il ledger dell harness appartiene a una sessione di
agente, e chi arriva da fuori non ne ha una: le sue scritture finiscono nel
diario del modulo, `var/modules/sigma_developer_lab/mcp_writes.jsonl`, una riga
per ogni tentativo - percorso, tool, esito, motivo del rifiuto, backup - compresi
i tentativi rifiutati, che sono la parte piu interessante da leggere.

**Cosa espone.** Quattro tool, gli stessi che usa il ciclo, non un accesso
grezzo al disco. `edit_file_exact` e la ragione per cui vale la pena: sostituisce
un frammento esatto e, quando non lo trova, dice **perche** - la riga piu simile,
la percentuale di somiglianza, in cosa differisce - invece di fallire e basta.
Chi corregge una patch sbagliata non deve rileggere il file per indovinare.

**Come si spegne.** Come ogni altro server MCP, dall hub: un tool spento qui e
spento per tutti (`/api/mcp/policy`). I tool di scrittura nascono SENSITIVE,
quindi la prima volta chiedono un assenso umano.

**Dove si scrive.** Dentro la radice di lavoro, sempre: un percorso che esce
solleva e la chiamata fallisce con il motivo. La radice la decide
`SIGMA_WORKSPACE_ROOT` quando c e - serve al trasporto stdio, che viene lanciato
da fuori - e altrimenti quella predefinita del workspace.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.paths import module_state
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from core.harness.fs_manager import get_default_workspace_root, write_file_content
from core.harness.fs_tools import (
    append_file_content,
    edit_file_content,
    read_file_slice,
    would_truncate,
)

log = get_logger(__name__)

#: Il nome della variabile che punta la radice: la usa chi lancia il server come
#: processo figlio, che non ha un workspace predefinito da cui dedurla.
VAR_RADICE = "SIGMA_WORKSPACE_ROOT"

#: Dove si puo spostare il diario delle scritture, quando il predefinito non va.
VAR_DIARIO = "SIGMA_MCP_WRITE_LOG"

#: Quante righe restituisce una lettura quando non lo dice nessuno.
LETTURA_PREDEFINITA = 800

#: Oltre questo, il diario delle scritture gira pagina (una sola di storia).
TETTO_DIARIO = 2_000_000

#: Quante righe di diario si mostrano quando non lo dice nessuno.
RIGHE_DI_DIARIO = 50


def radice_di_lavoro() -> Path:
    """Dove si scrive: la variabile d ambiente, o il workspace predefinito."""
    scelta = str(os.environ.get(VAR_RADICE) or "").strip()
    return Path(scelta or get_default_workspace_root()).resolve()


def _dentro_la_radice(percorso: str, radice: Optional[Path] = None) -> Path:
    """Il percorso risolto, se sta nella radice. Altrimenti solleva.

    Un tool che espone la scrittura a un chiamante esterno non puo accettare un
    percorso che esce: `..`, un assoluto altrove e un collegamento simbolico
    portano fuori dall albero nello stesso modo, e `resolve()` li vede tutti.
    """
    base = radice or radice_di_lavoro()
    grezzo = str(percorso or "").strip().strip(chr(39) + chr(34) + chr(96))
    if not grezzo:
        raise ValueError("Manca il percorso.")
    candidato = Path(grezzo)
    intero = candidato.resolve() if candidato.is_absolute() else (base / candidato).resolve()
    if intero != base and not intero.is_relative_to(base):
        raise ValueError(
            "Percorso rifiutato: %s sta fuori dalla cartella di lavoro (%s). "
            "Usa un percorso relativo a quella." % (grezzo, base)
        )
    return intero


def _testo(messaggio: str, errore: bool = False) -> Dict[str, Any]:
    """La forma di risposta che l hub e i client MCP si aspettano."""
    esito: Dict[str, Any] = {"content": [{"type": "text", "text": messaggio}]}
    if errore:
        esito["isError"] = True
    return esito


def diario_delle_scritture() -> Path:
    """Il file in cui finisce la traccia: uno per installazione, non per radice.

    La variabile d ambiente serve a chi vuole la traccia altrove, e ai test, che
    altrimenti sporcherebbero il diario dell installazione vera.
    """
    scelto = str(os.environ.get(VAR_DIARIO) or "").strip()
    if scelto:
        return Path(scelto).resolve()
    return module_state("sigma_developer_lab") / "mcp_writes.jsonl"


def chi_scrive() -> str:
    """Chi sta scrivendo, per il diario.

    Il nome arriva dall ambiente perche e li che il trasporto lo mette: il
    processo figlio che serve un client esterno nasce con `SIGMA_MCP_CLIENT`
    addosso, quindi ogni riga che scrive sa da chi viene. Dentro l applicazione
    la variabile non c e, e allora la riga dice che ha scritto Sigma Studio.
    """
    return (os.environ.get("SIGMA_MCP_CLIENT") or "sigma-studio").strip() or "sigma-studio"


def _gira_pagina(percorso: Path) -> None:
    """Oltre il tetto, il diario vecchio diventa la pagina precedente.

    Un file che cresce senza fine non e una traccia: e un disco che si riempie
    finche qualcosa smette di funzionare. Si tiene una pagina sola di storia,
    perche due bastano a capire cosa e appena successo, e chi vuole di piu
    legge i backup dei file, che sono la fonte vera.
    """
    try:
        if percorso.is_file() and percorso.stat().st_size > TETTO_DIARIO:
            precedente = percorso.with_suffix(".1.jsonl")
            precedente.unlink(missing_ok=True)
            percorso.replace(precedente)
    except OSError as exc:
        log.warning("Diario non ruotato: %s", exc)


def _annota(voce: Dict[str, Any]) -> None:
    """Aggiunge una riga al diario. Non solleva mai.

    Un diario che fa fallire la scrittura che doveva registrare sarebbe peggio del
    diario mancante: se la traccia non si aggiorna lo diciamo nel log, e la
    modifica resta fatta.
    """
    try:
        percorso = diario_delle_scritture()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        _gira_pagina(percorso)
        riga = dict(voce)
        riga.setdefault("chi", chi_scrive())
        riga["pid"] = os.getpid()
        riga["quando"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        # I campi che non dicono niente si tolgono: `"byte": null` in una riga di
        # diario e' rumore che sembra informazione, e chi legge deve poter
        # credere a quello che c'e' scritto.
        riga = {chiave: valore for chiave, valore in riga.items() if valore is not None}
        with percorso.open("a", encoding="utf-8") as flusso:
            flusso.write(json.dumps(riga, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.warning("Diario delle scritture non aggiornato: %s", exc)


class DeveloperFsMCPServer(BaseMCPServer):
    """Lettura a finestre, modifica esatta, scrittura e append sui file."""

    def __init__(self):
        super().__init__(
            name="Developer Files",
            version="1.0.0",
            description=(
                "Le primitive di filesystem dell harness come tool MCP: lettura a "
                "finestre con i buchi dichiarati, modifica per frammento esatto con "
                "diagnostica, scrittura e aggiunta in coda. Backup automatico e una "
                "riga di diario per ogni tentativo di scrittura."
            ),
        )
        self._register_tools()

    def is_configured(self) -> bool:
        return radice_di_lavoro().is_dir()

    def missing_dependency(self) -> Optional[str]:
        return None

    # --- registrazione ------------------------------------------------------

    def _register_tools(self) -> None:
        self.register_tool(
            name="read_file_window",
            description=(
                "Legge una finestra di un file, con i numeri di riga. Dice quante "
                "righe ha il file in tutto e se ne restano oltre la finestra."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo al workspace"},
                    "offset": {"type": "integer", "description": "Prima riga, da 1 (default 1)"},
                    "limit": {"type": "integer", "description": "Quante righe (default 800, max 5000)"},
                },
                "required": ["path"],
            },
            handler=self._read_window,
            safety=SAFE,
            category="developer_fs",
        )
        self.register_tool(
            name="edit_file_exact",
            description=(
                "Sostituisce un frammento esatto di un file. Se non lo trova dice "
                "quale riga gli somiglia di piu e in cosa differisce (indentazione, "
                "spazi, contenuto), cosi la correzione non richiede di rileggere."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo al workspace"},
                    "old_string": {"type": "string", "description": "Testo esatto da sostituire"},
                    "new_string": {"type": "string", "description": "Testo nuovo"},
                    "replace_all": {"type": "boolean", "description": "Sostituisce tutte le occorrenze (default false)"},
                },
                "required": ["path", "old_string", "new_string"],
            },
            handler=self._edit_exact,
            safety=SENSITIVE,
            category="developer_fs",
        )
        self.register_tool(
            name="write_file",
            description=(
                "Scrive un file (lo crea o lo riscrive). Rifiuta di rimpicciolirlo "
                "sotto una soglia: un troncamento perde lavoro, e si accetta solo "
                "chiedendolo con allow_truncate."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo al workspace"},
                    "content": {"type": "string", "description": "Contenuto completo del file"},
                    "allow_truncate": {"type": "boolean", "description": "Accetta di rimpicciolire (default false)"},
                },
                "required": ["path", "content"],
            },
            handler=self._write,
            safety=SENSITIVE,
            category="developer_fs",
        )
        self.register_tool(
            name="append_file",
            description="Aggiunge testo in fondo a un file, creandolo se non esiste.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo al workspace"},
                    "content": {"type": "string", "description": "Testo da aggiungere in coda"},
                },
                "required": ["path", "content"],
            },
            handler=self._append,
            safety=SENSITIVE,
            category="developer_fs",
        )
        self.register_tool(
            name="read_write_journal",
            description=(
                "Legge il diario delle scritture: chi ha scritto cosa, quando, "
                "com'e finita, e quali tentativi sono stati rifiutati (e perche)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Filtra per percorso (sottostringa)"},
                    "esito": {"type": "string", "description": "Filtra per esito: scritto, modificato, aggiunto, rifiutato, fuori radice, fallito"},
                    "ultime": {"type": "integer", "description": "Quante righe, dalle piu recenti (default 50, max 1000)"},
                },
                "required": [],
            },
            handler=self._read_journal,
            safety=SAFE,
            category="developer_fs",
        )

    # --- i quattro tool -----------------------------------------------------

    def _read_window(self, path: str, offset: int = 1, limit: int = LETTURA_PREDEFINITA) -> Dict[str, Any]:
        try:
            intero = _dentro_la_radice(path)
        except ValueError as exc:
            return _testo(str(exc), errore=True)
        esito = read_file_slice(str(intero), offset=offset, limit=limit)
        if not esito.get("success"):
            return _testo("Lettura fallita: %s" % esito.get("error", "causa non nota"), errore=True)
        totale = esito.get("total_lines")
        intestazione = "%s - righe %s-%s di %s" % (
            esito.get("path"), esito.get("offset"), esito.get("last_line"), totale)
        corpo = esito.get("numbered") or esito.get("content") or ""
        coda = ""
        if esito.get("has_more"):
            coda = (
                "\n\n[Il file continua oltre la riga %s. Per leggere il resto: "
                "read_file_window con offset=%s]"
                % (esito.get("last_line"), int(esito.get("last_line") or 0) + 1)
            )
        return _testo("%s\n%s%s" % (intestazione, corpo, coda))

    def _edit_exact(self, path: str, old_string: str, new_string: str,
                    replace_all: bool = False) -> Dict[str, Any]:
        try:
            intero = _dentro_la_radice(path)
        except ValueError as exc:
            _annota({"tool": "edit_file_exact", "path": path, "esito": "fuori radice",
                     "motivo": str(exc)})
            return _testo(str(exc), errore=True)
        esito = edit_file_content(str(intero), old_string, new_string,
                                  replace_all=bool(replace_all),
                                  root=str(radice_di_lavoro()))
        if not esito.get("success"):
            # Il messaggio porta gia la diagnostica: riga piu simile, percentuale,
            # in cosa differisce. Vale piu di un errore generico, e va dato intero.
            _annota({"tool": "edit_file_exact", "path": path, "esito": "rifiutato",
                     "motivo": str(esito.get("error", ""))[:300]})
            return _testo("Modifica non applicata.\n%s" % esito.get("error", ""), errore=True)
        _annota({"tool": "edit_file_exact", "path": esito.get("path") or path,
                 "esito": "modificato",
                 "righe": "%s -> %s" % (esito.get("lines_before"), esito.get("lines_after"))})
        return _testo(
            "Modificato %s: %s righe -> %s (+%s/-%s)."
            % (esito.get("path"), esito.get("lines_before"), esito.get("lines_after"),
               esito.get("lines_added"), esito.get("lines_removed"))
        )

    def _write(self, path: str, content: str, allow_truncate: bool = False) -> Dict[str, Any]:
        try:
            intero = _dentro_la_radice(path)
        except ValueError as exc:
            _annota({"tool": "write_file", "path": path, "esito": "fuori radice",
                     "motivo": str(exc)})
            return _testo(str(exc), errore=True)
        if intero.is_dir():
            return _testo("Il percorso e una cartella: %s" % path, errore=True)
        if intero.exists() and not allow_truncate:
            try:
                precedente = intero.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return _testo("File non leggibile: %s" % exc, errore=True)
            if would_truncate(precedente, content):
                _annota({"tool": "write_file", "path": path, "esito": "rifiutato",
                         "motivo": "troncamento: %d righe -> %d"
                                   % (len(precedente.splitlines()),
                                      len(str(content or "").splitlines()))})
                return _testo(
                    "Rifiutato: %s contiene %d righe e questa scrittura ne porta %d. "
                    "Se devi cambiarne una parte usa edit_file_exact; se il "
                    "rimpicciolimento e voluto, ripeti con allow_truncate."
                    % (path, len(precedente.splitlines()), len(str(content or "").splitlines())),
                    errore=True)
        esito = write_file_content(str(intero), content, root=str(radice_di_lavoro()))
        if not esito.get("success"):
            _annota({"tool": "write_file", "path": path, "esito": "fallito",
                     "motivo": str(esito.get("error", ""))[:300]})
            return _testo("Scrittura fallita: %s" % esito.get("error", ""), errore=True)
        _annota({"tool": "write_file", "path": esito.get("path") or path,
                 "esito": "scritto", "byte": esito.get("size"),
                 "backup": esito.get("backup_id")})
        # `write_file_content` non conta le righe: il suo messaggio dice il
        # nome del file, e quello basta e avanza.
        return _testo(esito.get("message") or ("Scritto %s." % path))

    def _append(self, path: str, content: str) -> Dict[str, Any]:
        try:
            intero = _dentro_la_radice(path)
        except ValueError as exc:
            _annota({"tool": "append_file", "path": path, "esito": "fuori radice",
                     "motivo": str(exc)})
            return _testo(str(exc), errore=True)
        esito = append_file_content(str(intero), content, root=str(radice_di_lavoro()))
        if not esito.get("success"):
            _annota({"tool": "append_file", "path": path, "esito": "fallito",
                     "motivo": str(esito.get("error", ""))[:300]})
            return _testo("Aggiunta non riuscita: %s" % esito.get("error", ""), errore=True)
        _annota({"tool": "append_file", "path": esito.get("path") or path,
                 "esito": "aggiunto", "byte": esito.get("size")})
        return _testo(esito.get("message") or "Contenuto aggiunto.")

    # --- il diario, riletto -------------------------------------------------

    def _read_journal(self, path: str = "", esito: str = "",
                      ultime: int = RIGHE_DI_DIARIO) -> Dict[str, Any]:
        """Le ultime righe del diario, filtrate. In sola lettura.

        Anche le righe rifiutate escono: un tentativo di scrivere fuori dalla
        radice e la cosa piu interessante che il diario possa raccontare, e
        senza un lettore quella traccia resterebbe un file che nessuno apre.
        """
        try:
            quante = max(1, min(int(ultime or RIGHE_DI_DIARIO), 1000))
        except (TypeError, ValueError):
            quante = RIGHE_DI_DIARIO

        percorso = diario_delle_scritture()
        if not percorso.is_file():
            return _testo("Il diario e ancora vuoto: nessuna scrittura registrata.")
        try:
            grezzo = percorso.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return _testo("Diario non leggibile: %s" % exc, errore=True)

        scelte: List[Dict[str, Any]] = []
        totale = 0
        for riga in grezzo:
            riga = riga.strip()
            if not riga:
                continue
            try:
                voce = json.loads(riga)
            except ValueError:
                # Una riga a meta (scrittura interrotta) non invalida le altre:
                # il diario si legge anche mentre qualcuno ci scrive.
                continue
            if not isinstance(voce, dict):
                continue
            totale += 1
            if path and str(path).lower() not in str(voce.get("path", "")).lower():
                continue
            if esito and str(esito).lower() != str(voce.get("esito", "")).lower():
                continue
            scelte.append(voce)

        if not scelte:
            return _testo(
                "Nessuna riga corrisponde al filtro (%d righe nel diario)." % totale)
        return _testo(json.dumps(
            {"righe": scelte[-quante:], "mostrate": len(scelte[-quante:]), "totale": totale},
            ensure_ascii=False, indent=2))

