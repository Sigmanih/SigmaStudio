# ==============================================================================
# core/harness/workspace.py — Su quale progetto sta lavorando questo run
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""La radice del workspace attivo, per gli strumenti che non la ricevono.

I tool di filesystem ricevono il workspace come argomento e lo rispettano. I
server MCP no: sono singleton condivisi, invocati con i soli parametri che il
modello scrive nella chiamata, e nessun modello scrive «e comunque lavora in
D:\\quel\\progetto». Il risultato era che `git_status`, `git_commit` e i loro
fratelli ripiegavano sul workspace predefinito del server — cioe' su Sigma
Studio — qualunque cosa l'agente avesse chiesto.

Non e' un dettaglio. Un run dell'orchestratore puntato su una cartella di prova
ha creato un branch **nel repository di Sigma Studio** e ci ha fatto checkout,
e con `auto_approve` attivo la stessa sequenza sarebbe arrivata a `git_commit`
e `git_push`: modifiche committate e spinte sul repository sbagliato, senza che
nessuno avesse chiesto niente del genere.

La radice e' quindi una proprieta' del *run*, non della chiamata, e vive qui —
in una variabile di contesto, cosi' che due run in parallelo non si scambino il
progetto sotto i piedi.
"""

import contextvars
from typing import Optional

from core.logger import get_logger

log = get_logger("workspace")

#: La radice su cui sta lavorando il run corrente. Vuota significa "usa il
#: predefinito", che e' il comportamento storico e resta corretto per la chat.
_radice_attiva: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sigma_workspace_root", default=""
)


def set_active_root(root: Optional[str]) -> contextvars.Token:
    """Dichiara su quale progetto lavora questo run. Ritorna il token di ripristino."""
    return _radice_attiva.set(str(root or ""))


def reset_active_root(token: contextvars.Token) -> None:
    """Riporta la radice a com'era prima della corrispondente `set_active_root`."""
    try:
        _radice_attiva.reset(token)
    except ValueError:
        # Token di un altro contesto: succede se il run e' finito su un thread
        # diverso da quello che lo aveva aperto. Non c'e' niente da ripristinare
        # e non c'e' motivo di far fallire la chiusura per questo.
        log.debug("[Workspace] token di ripristino non valido in questo contesto")


def active_root() -> str:
    """La radice del run corrente, o stringa vuota se nessuno l'ha dichiarata."""
    return _radice_attiva.get()


def resolve_root(explicit: Optional[str] = None) -> str:
    """La radice da usare: quella esplicita, quella del run, o il predefinito.

    L'ordine e' quello dell'informazione piu' specifica: chi passa una radice
    esplicita sa cosa vuole, chi non la passa eredita quella del run, e solo in
    assenza di entrambe si ricade sul workspace predefinito del server.
    """
    if explicit:
        return str(explicit)
    corrente = active_root()
    if corrente:
        return corrente
    from core.harness.fs_manager import get_default_workspace_root
    return get_default_workspace_root()


# ------------------------------------------------------------------------------
# Cosa c'era qui, e perche' non c'e' piu'
#
# `get_workspace_git_status()` e `is_workspace_clean()` promettevano lo stato
# git del workspace «via IPC Named Pipe in meno di 1 ms», appoggiandosi a
# `core/harness/fs.py`. Tre cose non andavano, e insieme facevano una
# funzionalita' che non poteva funzionare e che nessuno usava:
#
# - `fs.py` scriveva sulla pipe il JSON grezzo `{"cmd": "git_status"}`, mentre
#   il server Rust pretende un frame binario con intestazione `SIGM` di 16 byte
#   e un opcode. La lettura IPC non poteva riuscire **mai**: si ripiegava
#   sempre sul comando `git`, e il «meno di 1 ms» non e' mai stato misurato;
# - il parsing di `git status --porcelain` era sbagliato. Il primo ramo
#   catturava ogni codice contenente `A`, `M`, `D` o `R`, quindi la lista
#   `modified` restava sempre vuota e i file modificati non in stage finivano
#   fra gli `staged`. Chi ci avesse creduto avrebbe letto il contrario;
# - **nessuno le chiamava**. Fuori da questo file non c'era un solo chiamante.
#
# Era l'ottava occorrenza dello schema «scritto, testato, scollegato» che
# STATO_HARNESS.md paragrafo 2 descrive. Il tool nativo che servirebbe esiste
# gia' nel kernel e si chiama `fast_git_status`: se un giorno il percorso
# veloce servira' davvero, si parte da li' e dal frame binario di
# `NamedPipeClient`, non da un protocollo inventato.
# ------------------------------------------------------------------------------
