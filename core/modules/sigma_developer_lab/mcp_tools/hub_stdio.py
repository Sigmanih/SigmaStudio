# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/hub_stdio.py - L hub su stdio
# Sigma Studio v8 - Modulo installabile
# ==============================================================================
"""Tutto l hub MCP di Sigma Studio, in ascolto su stdin e stdout.

**A cosa serve.** Il server dei file copre la scrittura; questo copre il resto:
un client esterno - un IDE, un assistente collegato - vede gli stessi tool che
vede Sigma Studio, con la stessa policy. Lint, test, git, docker, cargo, ricerca
semantica, i file: tutto quello che la scheda MCP dell applicazione elenca, e
niente che li non sia acceso.

**La policy vale anche per chi arriva da fuori.** L elenco passa da
`get_aggregated_tools(only_enabled=True)` e ogni chiamata da `execute_tool`,
quindi un tool spento nella scheda e spento anche qui, un server disattivato non
compare, e un tool SENSITIVE resta in attesa di un assenso umano invece di
eseguire. Non e una cortesia: e il motivo per cui questo trasporto si puo
accendere senza aprire una porta di servizio.

**Uso.**

    SIGMA_WORKSPACE_ROOT=/percorso/del/progetto python -m \\
        core.modules.sigma_developer_lab.mcp_tools.hub_stdio

`SIGMA_MCP_ONLY` limita l elenco ai server nominati, per nome esatto e separati
da virgola (`Developer Files`, `Developer Lint`, `Developer Tests`, `Developer Git`,
`Developer Dependencies`, `Semantic Code Search`, `Developer Supervisor`, ...): utile
per non portarsi in contesto cinquanta tool quando ne servono sei. Per esempio,
per lavorare soltanto sui file e sulla qualita:

    SIGMA_MCP_ONLY="Developer Files,Developer Tests,Semantic Code Search,Developer Git"

`SIGMA_MCP_CLIENT` dice **chi siamo**, e serve a una cosa sola ma decisiva: le
righe del diario delle scritture e le richieste di assenso portano quel nome, e
senza si legge `sigma-studio` - cioe' non si sa se ha scritto l'applicazione o
un client collegato. Mettilo sempre (`SIGMA_MCP_CLIENT="Cline"`).

**Una nota sui server che non funzionano.** `Developer Lint` si elenca lo stesso e
rifiuta con il motivo (`pip install ruff`): un tool che dice perche non puo
rispondere e piu utile di un tool che non compare affatto. Chi vuole il lint da
qui installa ruff; senza, conviene lasciarlo fuori dal filtro e usare i test.

**Configurazione in Cline** (file delle impostazioni MCP del client):

    {
      "mcpServers": {
        "sigma-studio": {
          "command": "C:/Users/Sigma/Desktop/Sigma_Studio/.venv/Scripts/python.exe",
          "args": ["-m", "core.modules.sigma_developer_lab.mcp_tools.hub_stdio"],
          "cwd": "C:/Users/Sigma/Desktop/Sigma_Studio",
          "env": {
            "SIGMA_WORKSPACE_ROOT": "C:/Users/Sigma/Desktop/Sigma_Studio",
            "SIGMA_MCP_ONLY": "Developer Files,Developer Tests,Semantic Code Search,Developer Git",
            "SIGMA_MCP_CLIENT": "Cline"
          }
        }
      }
    }

Si spegne come ogni altro server MCP: dalla scheda dell applicazione, e il
processo figlio non vede piu nulla.

**Cosa non deve fare.** Niente stampe su stdout che non siano messaggi del
protocollo: una riga di log li dentro e un messaggio che il client non sa
leggere. I log si spostano su stderr prima di importare qualsiasi cosa.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional

#: Il canale del protocollo, preso prima che qualcuno possa scriverci sopra.
_CANALE = sys.stdout
sys.stdout = sys.stderr

for _flusso, _modo in ((_CANALE, "w"), (sys.stdin, "r")):
    try:
        _flusso.reconfigure(encoding="utf-8", newline="\n")
    except Exception:
        pass


def _log_mai_sul_canale() -> None:
    # Il logger del programma si lega a `sys.stdout` quando viene importato: in
    # un processo figlio quello e il canale dei messaggi, quindi ogni handler che
    # lo tiene va spostato. Si chiama prima di importare l hub e dopo, perche la
    # catena di import fa partire anche i server interni, che scrivono.
    import logging

    for nome in ("sigma", ""):
        for handler in list(logging.getLogger(nome).handlers):
            if getattr(handler, "stream", None) is _CANALE:
                try:
                    handler.setStream(sys.stderr)
                except Exception:
                    pass


def _testo(messaggio: str, errore: bool = False) -> Dict[str, Any]:
    esito: Dict[str, Any] = {"content": [{"type": "text", "text": messaggio}]}
    if errore:
        esito["isError"] = True
    return esito


def _server_ammessi() -> Optional[List[str]]:
    grezzo = str(os.environ.get("SIGMA_MCP_ONLY") or "").strip()
    if not grezzo:
        return None
    return [voce.strip().lower() for voce in grezzo.split(",") if voce.strip()]


#: Chi siamo, per la governance. Serve a una cosa sola ma decisiva: un client
#: esterno **non** puo' consumare l'assenso che ha chiesto lui, quindi la
#: richiesta va marcata con il nome di chi l'ha presentata. Un client che si
#: annuncia (`SIGMA_MCP_CLIENT="Cline"`) si riconosce nella scheda dell'app.
CLIENTE = (os.environ.get("SIGMA_MCP_CLIENT") or "client esterno").strip() or "client esterno"

#: Quanto si aspetta, al massimo, un assenso quando non lo dice nessuno.
ATTESA_PREDEFINITA = 120

#: I due tool di servizio di questo trasporto: non sono dell hub, sono del
#: protocollo. Ci sono sempre, anche con `SIGMA_MCP_ONLY`, perche' senza di loro
#: un tool sensibile sarebbe inusabile da qui: l'assenso lo da' l'umano, ma il
#: client deve poter sapere quando arriva e com'e' finita.
TOOL_DI_SERVIZIO: List[Dict[str, Any]] = [
    {
        "name": "approval_status",
        "description": (
            "Mostra le chiamate in attesa di un assenso umano, o lo stato di una "
            "sola richiesta se indichi request_id. Non esegue niente."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string",
                               "description": "Identificativo della richiesta; vuoto per l elenco"},
            },
            "required": [],
        },
        "annotations": {"server": "Sigma Studio Hub", "safety": "safe",
                        "readOnlyHint": True},
    },
    {
        "name": "await_approval",
        "description": (
            "Aspetta che un operatore approvi o rifiuti una chiamata sensibile e "
            "restituisce l esito. Chiamalo dopo che un tool ha risposto che la "
            "chiamata e in attesa."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string",
                               "description": "Identificativo della richiesta; vuoto per la piu recente di questo client"},
                "timeout_seconds": {"type": "integer",
                                    "description": "Quanto aspettare, max 600 (default 120)"},
            },
            "required": [],
        },
        "annotations": {"server": "Sigma Studio Hub", "safety": "safe",
                        "readOnlyHint": True},
    },
]


class HubMCPServer:
    """L hub, presentato come un unico server MCP.

    Non eredita da `BaseMCPServer` perche la sua lista di tool non e scritta nel
    codice: e quella dell hub, che cambia con la configurazione. Si costruisce
    al momento e si rilegge a ogni `tools/list`, cosi un tool disattivato dalla
    scheda sparisce anche da qui senza riavviare niente.
    """

    name = "Sigma Studio Hub"
    version = "1.0.0"
    description = (
        "Tutti i tool MCP di Sigma Studio, filtrati dalla policy dell applicazione: "
        "file, lint, test, git, docker, cargo, ricerca semantica."
    )

    def __init__(self, hub: Any = None, ammessi: Optional[List[str]] = None):
        self._hub = hub if hub is not None else _hub()
        # `ammessi` esplicito serve a chi vuole questa porta con un filtro fisso
        # (vedi `fs_stdio`): una porta minima non deve poter scavalcare la policy
        # per distrazione, e il filtro e' parte della porta.
        if ammessi is None:
            self._ammessi = _server_ammessi()
        else:
            self._ammessi = [voce.strip().lower() for voce in ammessi if voce.strip()]

    # --- elenco -------------------------------------------------------------

    def _tools(self) -> List[Dict[str, Any]]:
        # I tool di servizio non passano dal filtro: sono del trasporto, e senza
        # di loro un assenso non si potrebbe ne leggere ne attendere.
        elenco: List[Dict[str, Any]] = [dict(voce) for voce in TOOL_DI_SERVIZIO]
        for meta in self._hub.get_aggregated_tools(only_enabled=True):
            nome = str(meta.get("name") or "")
            server = str(meta.get("server") or "")
            if not nome:
                continue
            if self._ammessi and server.strip().lower() not in self._ammessi:
                continue
            if meta.get("ready") is False:
                # Un server non configurato si elenca lo stesso: il rifiuto
                # arriva con il motivo (la dipendenza che manca), che e piu
                # utile di un nome che non compare.
                pass
            elenco.append({
                "name": nome,
                "description": str(meta.get("description") or ""),
                "inputSchema": meta.get("inputSchema") or {"type": "object", "properties": {}},
                "annotations": {
                    "server": server,
                    "safety": str(meta.get("safety") or "safe"),
                    "readOnlyHint": str(meta.get("safety") or "safe") == "safe",
                },
            })
        return elenco

    # --- esecuzione ---------------------------------------------------------

    def _chiama(self, nome: str, argomenti: Dict[str, Any]) -> Dict[str, Any]:
        argomenti = argomenti or {}
        if nome == "approval_status":
            return self._stato_assenso(argomenti)
        if nome == "await_approval":
            return self._attendi_assenso(argomenti)

        # `client=CLIENTE`: da qui non si consuma un assenso, lo si chiede. La
        # richiesta nasce marcata con il nostro nome, e per questo non potra'
        # essere reclamata da noi stessi (vedi `governance.take_approval`).
        esito = self._hub.execute_tool(nome, argomenti, client=CLIENTE)
        stato = str(esito.get("status") or "")
        if stato == "ok":
            risultato = esito.get("result")
            if isinstance(risultato, dict) and "content" in risultato:
                return risultato
            return _testo(json.dumps(risultato, ensure_ascii=False, indent=2)
                          if isinstance(risultato, (dict, list)) else str(risultato))
        if stato == "confirmation_required":
            richiesta = str((esito.get("approval") or {}).get("request_id") or "")
            return _testo(
                "Il tool '%s' chiede un assenso umano e la chiamata e in attesa "
                "(richiesta %s). Non e un errore e non serve riprovare con "
                "l identificativo: l assenso lo da l operatore dalla scheda MCP di "
                "Sigma Studio. Per ricevere l esito appena arriva, chiama "
                "await_approval%s."
                % (nome, richiesta or "senza identificativo",
                   (" con request_id=%s" % richiesta) if richiesta else ""),
                errore=True)
        return _testo(str(esito.get("error") or "Errore sconosciuto."), errore=True)

    # --- l'assenso, visto da fuori ------------------------------------------

    @staticmethod
    def _riassunto(record: Dict[str, Any]) -> Dict[str, Any]:
        """Quel che serve a decidere, senza gli argomenti interi."""
        argomenti = record.get("arguments") or {}
        try:
            resa = json.dumps(argomenti, ensure_ascii=False)
        except (TypeError, ValueError):
            resa = str(argomenti)
        return {
            "request_id": record.get("request_id", ""),
            "tool": record.get("tool", ""),
            "server": record.get("server", ""),
            "client": record.get("client", ""),
            "status": record.get("status", ""),
            "richiesta_il": record.get("created_at", 0),
            "argomenti": resa[:300],
        }

    def _stato_assenso(self, argomenti: Dict[str, Any]) -> Dict[str, Any]:
        from core.mcp import governance

        richiesta = str(argomenti.get("request_id") or "").strip()
        if richiesta:
            record = governance.get_approval(richiesta)
            if not record:
                return _testo(
                    "Richiesta %s non trovata: scaduta, gia eseguita, o mai "
                    "esistita." % richiesta, errore=True)
            return _testo(json.dumps(self._riassunto(record), ensure_ascii=False, indent=2))
        attese = governance.list_pending()
        return _testo(json.dumps(
            {"in_attesa": [self._riassunto(r) for r in attese], "quante": len(attese)},
            ensure_ascii=False, indent=2))

    def _attendi_assenso(self, argomenti: Dict[str, Any]) -> Dict[str, Any]:
        """Aspetta il verdetto e poi l'esito, e non esegue niente da se.

        L'esecuzione e' dell'applicazione: chi ha chiesto la chiamata non la
        esegue e non ne vede il risultato, quindi l'unico modo di saperne qualcosa
        e leggere quel che l'app ha scritto dopo averla eseguita.
        """
        import time

        from core.mcp import governance

        richiesta = str(argomenti.get("request_id") or "").strip()
        try:
            attesa = int(argomenti.get("timeout_seconds") or ATTESA_PREDEFINITA)
        except (TypeError, ValueError):
            attesa = ATTESA_PREDEFINITA
        attesa = max(1, min(attesa, 600))

        if not richiesta:
            # La piu' recente di questo client: un modello che aspetta non deve
            # anche ricordarsi un identificativo.
            mie = [r for r in governance.list_pending()
                   if str(r.get("client") or "") == CLIENTE]
            if not mie:
                return _testo(
                    "Nessuna chiamata di '%s' in attesa di assenso. Usa "
                    "approval_status per l elenco." % CLIENTE, errore=True)
            richiesta = str(mie[-1].get("request_id") or "")

        scadenza = time.time() + attesa
        while True:
            record = governance.get_approval(richiesta)
            if not record:
                return _testo("La richiesta %s non esiste piu (scaduta)." % richiesta, errore=True)
            stato = str(record.get("status") or "")
            if stato == governance.DONE:
                return _testo("Approvata ed eseguita. Esito:\n%s"
                              % (record.get("output") or "(nessun output)"))
            if stato == governance.FAILED:
                return _testo("Approvata ma non riuscita: %s"
                              % (record.get("error") or "nessun dettaglio"), errore=True)
            if stato == governance.REFUSED:
                return _testo("Rifiutata da %s."
                              % (record.get("confirmed_by") or "operatore"), errore=True)
            if time.time() >= scadenza:
                return _testo(
                    "Ancora in attesa dopo %ss (stato: %s). L assenso lo da "
                    "l operatore dalla scheda MCP di Sigma Studio; poi richiama "
                    "await_approval." % (attesa, stato or "sconosciuto"), errore=True)
            time.sleep(1.0)

    # --- protocollo ---------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._tools()

    def handle_json_rpc(self, richiesta: Dict[str, Any]) -> Dict[str, Any]:
        identificativo = richiesta.get("id")
        metodo = richiesta.get("method")
        parametri = richiesta.get("params") or {}

        if metodo == "initialize":
            return {"jsonrpc": "2.0", "id": identificativo, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": self.version},
            }}
        if metodo == "tools/list":
            return {"jsonrpc": "2.0", "id": identificativo,
                    "result": {"tools": self.list_tools()}}
        if metodo == "tools/call":
            nome = str(parametri.get("name") or "")
            argomenti = parametri.get("arguments") or {}
            if not nome:
                return {"jsonrpc": "2.0", "id": identificativo,
                        "error": {"code": -32602, "message": "Manca il nome del tool."}}
            return {"jsonrpc": "2.0", "id": identificativo,
                    "result": self._chiama(nome, argomenti)}
        if metodo in ("resources/list",):
            return {"jsonrpc": "2.0", "id": identificativo, "result": {"resources": []}}
        return {"jsonrpc": "2.0", "id": identificativo,
                "error": {"code": -32601, "message": "Metodo non supportato: %s" % metodo}}


def _hub():
    """L hub del programma, con i server dei moduli registrati.

    In Sigma Studio la registrazione la fa il caricatore dei moduli all avvio;
    qui il processo nasce da fuori, quindi si registra quello che si sa
    registrare. Se un modulo non c e, il suo server semplicemente non compare.
    """
    import core.logger  # noqa: F401  (crea l handler del programma)
    _log_mai_sul_canale()

    from core.mcp.mcp_hub import mcp_hub
    try:
        from core.modules.sigma_developer_lab.handlers import register_mcp
        register_mcp(mcp_hub)
    except Exception as exc:  # pragma: no cover - dipende dai moduli installati
        print("Server MCP del modulo non registrati: %s" % exc, file=sys.stderr)
    _log_mai_sul_canale()
    return mcp_hub


def _scrivi(messaggio: Dict[str, Any]) -> None:
    _CANALE.write(json.dumps(messaggio, ensure_ascii=False) + "\n")
    _CANALE.flush()


def main(argv: Optional[list] = None, server: Any = None) -> int:
    """Il ciclo del protocollo. `server` serve a chi vuole una porta filtrata."""
    server = server if server is not None else HubMCPServer()
    for riga in sys.stdin:
        riga = riga.strip()
        if not riga:
            continue
        try:
            richiesta = json.loads(riga)
        except ValueError:
            _scrivi({"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Messaggio non leggibile come JSON."}})
            continue
        if not isinstance(richiesta, dict) or richiesta.get("id") is None:
            continue
        try:
            _scrivi(server.handle_json_rpc(richiesta))
        except Exception as exc:
            _scrivi({"jsonrpc": "2.0", "id": richiesta.get("id"),
                     "error": {"code": -32603, "message": "Errore interno: %s" % exc}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

