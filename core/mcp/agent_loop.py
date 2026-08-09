# ==============================================================================
# core/mcp/agent_loop.py — Letting agents actually call MCP tools
# ==============================================================================
"""Il ponte fra quello che il modello scrive e quello che l'hub esegue.

Fino a ieri gli strumenti erano decorativi: l'elenco finiva nel prompt e nessuno
lo eseguiva, e i tag `<tool_call>` venivano perfino cancellati dal parser delle
risposte. Qui c'è il pezzo mancante.

**Perché un protocollo testuale e non il function calling nativo.** Sigma Studio
parla con Ollama, OpenAI, Anthropic, Groq, DeepSeek e OpenRouter, e con qualunque
modello locale l'utente si sia addestrato nel Training Lab. Il function calling
nativo ha una forma diversa per ognuno di questi, e sui modelli locali fine-tuned
spesso non c'è affatto. Un blocco recintato funziona ovunque, sopravvive allo
streaming token per token, ed è già il modo in cui il progetto estrae i file
dalle risposte.

Il recinto si chiama `sigma-tool` e non `json` per non confondere una chiamata
con un esempio di JSON che il modello sta mostrando all'utente.
"""

import json
import re
from typing import Any, Dict, List, Tuple

from core.logger import get_logger
from core.mcp import governance

log = get_logger(__name__)

# Quante volte l'agente può chiamare strumenti prima di dover rispondere.
# Serve a fermare i cicli in cui il modello richiama sempre lo stesso strumento.
MAX_TOOL_ROUNDS = 4
MAX_CALLS_PER_ROUND = 4
# Un risultato enorme (una inbox, mezza casa domotica) manderebbe in saturazione
# il contesto al giro successivo.
MAX_RESULT_CHARS = 3000

TOOL_BLOCK = re.compile(r"```sigma-tool\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


# --- prompt ------------------------------------------------------------------

def build_tools_prompt(tools: List[Dict[str, Any]]) -> str:
    """La sezione di prompt che descrive gli strumenti disponibili.

    Elenca solo gli strumenti accesi e pronti: uno strumento spento nel prompt è
    una promessa che l'hub poi rifiuta, e il modello ci sbatte contro a vuoto.
    """
    if not tools:
        return ""

    lines = [
        "\n## STRUMENTI MCP DISPONIBILI",
        "",
        "Puoi eseguire uno strumento scrivendo un blocco come questo:",
        "",
        "```sigma-tool",
        '{"tool": "nome_strumento", "arguments": {"parametro": "valore"}}',
        "```",
        "",
        "Regole:",
        "- **AGISCI, NON SPIEGARE.** Se l'utente chiede un'azione che uno strumento sa fare, emetti "
        "il blocco e basta. Non descrivere la procedura, non elencare i passi, non scrivere istruzioni "
        "su come si userebbe lo strumento: quello lo legge già lui nella scheda. Una frase di contesto "
        "prima del blocco è il massimo consentito.",
        "- **NON INVENTARE MAI un identificativo.** Se non hai in mano l'elenco reale, chiama prima lo "
        "strumento che lo elenca e usa gli id che ti tornano, alla lettera. Un id inventato fa fallire "
        "l'intera chiamata, anche per le entità corrette che stavano nello stesso comando.",
        "- Compila tutti i parametri obbligatori. Se non sai cosa mettere, chiedilo all'utente invece di "
        "riempirlo con un valore verosimile.",
        "- Se uno strumento accetta un elenco o un'area, usalo UNA volta sola su tutti gli elementi "
        "invece di ripeterlo per ognuno: tre chiamate identiche significano tre conferme da chiedere "
        "all'utente per una richiesta sola.",
        "- Usa uno strumento solo se serve davvero a rispondere: non chiamarli per mostrare cosa sai fare.",
        "- Gli strumenti marcati [conferma] agiscono sul mondo reale e vengono mostrati all'utente per "
        "approvazione. Una riga per dire cosa stai per fare, non un paragrafo.",
        "- Se uno strumento fallisce, leggi l'errore e correggi gli argomenti invece di ripetere la stessa chiamata.",
        "",
    ]

    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for tool in tools:
        by_category.setdefault(tool.get("category", "general"), []).append(tool)

    for category, group in sorted(by_category.items()):
        lines.append(f"### {category}")
        for tool in group:
            mark = " [conferma]" if tool.get("safety") == governance.SENSITIVE else ""
            lines.append(f"- **{tool['name']}**{mark}: {tool.get('description', '')}")
            params = (tool.get("inputSchema") or {}).get("properties") or {}
            required = set((tool.get("inputSchema") or {}).get("required") or [])
            if params:
                rendered = ", ".join(
                    f"{name}{'*' if name in required else ''}: {spec.get('type', 'string')}"
                    for name, spec in params.items()
                )
                lines.append(f"  argomenti — {rendered}")
        lines.append("")

    return "\n".join(lines)


# --- parsing -----------------------------------------------------------------

def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Le chiamate a strumento contenute in una risposta, in ordine.

    Un blocco malformato non viene ignorato in silenzio: torna con l'errore di
    parsing, così l'agente riceve indietro il motivo e può correggersi.
    """
    calls: List[Dict[str, Any]] = []

    for match in TOOL_BLOCK.finditer(text or ""):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            calls.append({"tool": "", "arguments": {}, "raw": raw,
                          "parse_error": f"JSON non valido: {exc}"})
            continue

        if not isinstance(payload, dict):
            calls.append({"tool": "", "arguments": {}, "raw": raw,
                          "parse_error": "Il blocco deve contenere un oggetto JSON."})
            continue

        # Tollera le forme più comuni: {"tool": ...} e {"name": ...}, con
        # arguments oppure parameters. Un modello locale sbaglia spesso il nome
        # del campo, non l'intenzione.
        name = payload.get("tool") or payload.get("name") or ""
        arguments = payload.get("arguments")
        if arguments is None:
            arguments = payload.get("parameters")
        if arguments is None:
            arguments = {k: v for k, v in payload.items() if k not in ("tool", "name")}

        if not name:
            calls.append({"tool": "", "arguments": {}, "raw": raw,
                          "parse_error": "Manca il campo 'tool'."})
            continue

        calls.append({"tool": name, "arguments": arguments if isinstance(arguments, dict) else {},
                      "raw": raw})

        if len(calls) >= MAX_CALLS_PER_ROUND:
            break

    return calls


def strip_tool_blocks(text: str) -> str:
    """Toglie i blocchi di chiamata dal testo mostrato all'utente."""
    cleaned = TOOL_BLOCK.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


# --- execution ---------------------------------------------------------------

def _truncate(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2) if not isinstance(payload, str) else payload
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[:MAX_RESULT_CHARS] + f"\n[… risultato troncato, {len(text)} caratteri in totale]"


def execute_calls(calls: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Esegue le chiamate del giro. Ritorna (esiti, approvazioni_in_attesa).

    Ogni chiamata che richiede un assenso viene messa in attesa — tutte, non
    solo la prima. La versione precedente si fermava alla prima e buttava via il
    resto: l'agente chiedeva di spegnere tre luci, l'operatore ne vedeva una, e
    le altre due sparivano senza che niente lo dicesse.

    Le chiamate *sicure* che seguono una in attesa non partono comunque, perché
    leggerebbero uno stato che sta per cambiare — ma vengono dichiarate come
    rimandate, invece di svanire.
    """
    from core.mcp import mcp_hub

    outcomes: List[Dict[str, Any]] = []
    approvals: List[Dict[str, Any]] = []

    for call in calls:
        if call.get("parse_error"):
            outcomes.append({"tool": call.get("tool") or "(sconosciuto)", "ok": False,
                             "output": f"Blocco non eseguito — {call['parse_error']}"})
            continue

        if approvals:
            # Qualcosa è in attesa: una lettura adesso fotograferebbe lo stato
            # di prima. La si rimanda dicendolo, non la si perde.
            meta = mcp_hub.find_tool(call["tool"])
            if not meta or meta.get("safety") != governance.SENSITIVE:
                outcomes.append({
                    "tool": call["tool"], "ok": False, "deferred": True,
                    "output": "Non eseguito: in attesa che l'utente decida sulle chiamate precedenti. "
                              "Richiamalo dopo la loro conferma se serve ancora.",
                })
                continue

        result = mcp_hub.execute_tool(call["tool"], call["arguments"])

        if result["status"] == "confirmation_required":
            approvals.append(result["approval"])
            continue

        if result["status"] == "error":
            outcomes.append({"tool": call["tool"], "ok": False, "output": result["error"]})
            continue

        content = result["result"].get("content", [])
        text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
        outcomes.append({"tool": call["tool"], "ok": True,
                         "server": result.get("server", ""),
                         "output": _truncate(text or result["result"])})

    return outcomes, approvals


def format_results_for_model(outcomes: List[Dict[str, Any]]) -> str:
    """Il messaggio che riporta al modello com'è andata."""
    if not outcomes:
        return ""
    blocks = ["## RISULTATI DEGLI STRUMENTI", ""]
    for item in outcomes:
        verdict = "eseguito" if item["ok"] else "FALLITO"
        blocks.append(f"### {item['tool']} — {verdict}")
        blocks.append("```")
        blocks.append(item["output"])
        blocks.append("```")
        blocks.append("")
    blocks.append("Prosegui la risposta all'utente usando questi risultati. "
                  "Non ripetere la stessa chiamata se è andata a buon fine.")
    return "\n".join(blocks)
