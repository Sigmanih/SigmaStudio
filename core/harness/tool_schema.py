# ==============================================================================
# core/harness/tool_schema.py — I tool dell'harness, in forma dichiarabile
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Gli stessi tool, descritti nel modo che un provider capisce nativamente.

L'harness parla ai modelli locali con un blocco recintato — ```tool:nome piu'
un oggetto JSON — e una grammatica GBNF che ne impone la forma. E' la scelta
giusta li': un modello da 8B non ha tool-calling affidabile, e vincolare la
decodifica e' l'unico modo di ottenere una chiamata ben formata.

E' pero' la scelta peggiore per un modello che il tool-calling ce l'ha nativo.
Costringerlo a imitare un formato testuale significa usarlo nella sua modalita'
piu' debole, e far passare la sua risposta per quattrocento righe di euristiche
di riparazione scritte per compensare i modelli che quel supporto non ce l'hanno.

Questo modulo e' il ponte: descrive i tool una volta sola in JSON Schema, dice
quali provider sanno usarli, e traduce le `tool_calls` che tornano nella stessa
forma interna che produce l'estrattore testuale — cosi' il resto del ciclo non
sa nemmeno quale delle due strade e' stata percorsa.
"""

import re
import json
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("tool_schema")

#: Provider il cui endpoint accetta `tools` e risponde con `tool_calls`.
#: Elencati invece che dedotti: un provider che dichiara compatibilita' OpenAI
#: senza implementare i tool restituisce un 400 a meta' del run, e scoprirlo
#: allora costa piu' che tenere una lista.
NATIVE_TOOL_PROVIDERS = frozenset({
    "openai", "deepseek", "anthropic", "groq", "openrouter", "together", "mistral",
})

#: Provider serviti dal motore locale: li' vale il percorso recintato piu' GBNF.
LOCAL_PROVIDERS = frozenset({"sigma_engine", "sigma", "sigmaengine", "local", "native", "ollama"})


def supports_native_tools(provider: Optional[str]) -> bool:
    """Se per questo provider conviene dichiarare i tool invece di descriverli."""
    nome = str(provider or "").lower().strip()
    if not nome or nome in LOCAL_PROVIDERS:
        return False
    return nome in NATIVE_TOOL_PROVIDERS


def _f(name: str, description: str, properties: Dict[str, Any],
       required: List[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


_STRINGA = {"type": "string"}
_INTERO = {"type": "integer"}

#: Il catalogo. I nomi sono quelli canonici di `policy.canonical`, cosi' che una
#: chiamata nativa e una recintata finiscano nello stesso ramo di esecuzione.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    _f("read_file", "Legge un file del workspace, con numeri di riga. Obbligatorio prima di modificarlo.",
       {"path": _STRINGA, "offset": _INTERO, "limit": _INTERO}, ["path"]),
    _f("edit_file", "Sostituisce un frammento esatto dentro un file. Il modo normale di modificare.",
       {"path": _STRINGA, "old_string": _STRINGA, "new_string": _STRINGA,
        "replace_all": {"type": "boolean"}}, ["path", "old_string", "new_string"]),
    _f("write_file", "Crea un file nuovo, o ne riscrive uno da zero.",
       {"path": _STRINGA, "content": _STRINGA}, ["path", "content"]),
    _f("append_file", "Aggiunge testo in fondo a un file esistente.",
       {"path": _STRINGA, "content": _STRINGA}, ["path", "content"]),
    _f("terminal", "Esegue un comando di shell nel workspace e ne restituisce output ed exit code.",
       {"command": _STRINGA, "cwd": _STRINGA}, ["command"]),
    _f("list_dir", "Elenca il contenuto di una cartella. La radice del workspace e '.'.",
       {"path": _STRINGA}, ["path"]),
    _f("glob", "Trova file per pattern, dal piu' recente.",
       {"pattern": _STRINGA, "path": _STRINGA, "limit": _INTERO}, ["pattern"]),
    _f("search_code", "Cerca testo dentro i file del workspace.",
       {"query": _STRINGA, "path": _STRINGA}, ["query"]),
    _f("find_symbol", "Dove e' definito un simbolo, senza fare grep.",
       {"query": _STRINGA, "limit": _INTERO}, ["query"]),
    _f("delete", "Elimina un file.", {"path": _STRINGA}, ["path"]),
    _f("restore_file", "Ripristina un file dal backup automatico.", {"path": _STRINGA}, ["path"]),
    _f("screenshot", "Apre una pagina in un browser e ne salva l'immagine.",
       {"url": _STRINGA, "path": _STRINGA}, ["url"]),
    _f("spec", "Registra cosa significa 'finito': la richiesta riformulata e i criteri verificabili.",
       {"understanding": _STRINGA,
        "criteria": {"type": "array", "items": _STRINGA}}, ["understanding", "criteria"]),
    _f("pipeline", "Registra i task del piano per l'obiettivo corrente, con ruolo e dipendenze.",
       {"tasks": {"type": "array", "items": {
           "type": "object",
           "properties": {"id": _STRINGA, "title": _STRINGA, "status": _STRINGA,
                          "role": _STRINGA, "description": _STRINGA,
                          "depends_on": {"type": "array", "items": _STRINGA},
                          "files": {"type": "array", "items": _STRINGA},
                          "verify": _STRINGA},
           "required": ["id", "title"]}}}, ["tasks"]),
    _f("queue_add",
       "Mette il lavoro in una coda persistente, che piu' agenti in parallelo "
       "consumeranno. Da usare quando il lavoro e' troppo grande per un run "
       "solo: una voce per file o per modulo, indipendenti fra loro.",
       {"queue_id": _STRINGA,
        "goal": _STRINGA,
        "replaces": _STRINGA,
        "reason": _STRINGA,
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": _STRINGA, "title": _STRINGA,
                           "verify": _STRINGA,
                           "depends_on": {"type": "array", "items": _STRINGA}},
            "required": ["id", "title"]}}},
       ["queue_id", "items"]),
    _f("complete_goal", "Dichiara finito il lavoro, con la prova di ogni criterio.",
       {"summary": _STRINGA,
        "criteria": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": _STRINGA, "evidence": _STRINGA},
            "required": ["id", "evidence"]}}}, ["summary"]),
]

_PER_NOME = {s["function"]["name"]: s for s in TOOL_SCHEMAS}


def schemas_for(allowed: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Il catalogo, ristretto ai tool che questo run puo' usare.

    Dichiarare un tool che poi verrebbe rifiutato e' peggio che non dichiararlo:
    il modello lo sceglie, il sistema lo nega, e si perde un turno per una
    possibilita' che non esisteva.
    """
    if not allowed:
        return list(TOOL_SCHEMAS)
    nomi = {str(n) for n in allowed}
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in nomi]


def tool_calls_to_invocations(tool_calls: Any) -> List[Dict[str, Any]]:
    """Traduce le `tool_calls` native nella forma interna del ciclo.

    La forma interna e' quella che produce l'estrattore testuale — `{"tool":
    nome, "params": {...}}` — e mantenerla identica e' il punto: l'esecuzione,
    i permessi, il ledger e il cancello di completamento restano un solo
    percorso, e il tool-calling nativo diventa un modo diverso di *ottenere* la
    chiamata, non un secondo agente.
    """
    invocazioni: List[Dict[str, Any]] = []
    for chiamata in tool_calls or []:
        if not isinstance(chiamata, dict):
            continue
        funzione = chiamata.get("function") or {}
        nome = str(funzione.get("name") or "").strip()
        if not nome:
            continue
        grezzi = funzione.get("arguments")
        if isinstance(grezzi, dict):
            params: Dict[str, Any] = dict(grezzi)
        else:
            try:
                params = json.loads(grezzi or "{}")
                if not isinstance(params, dict):
                    raise ValueError("gli argomenti non sono un oggetto")
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                # Anche un provider nativo puo' troncare gli argomenti. Si
                # segnala come chiamata malformata, che il ciclo sa gia'
                # gestire, invece di scartarla in silenzio.
                log.warning("[ToolSchema] argomenti illeggibili per '%s': %s", nome, exc)
                params = {"__malformed__": True, "raw": str(grezzi or "")}
        invocazioni.append({
            "tool": nome.lower(),
            "params": params,
            "id": chiamata.get("id") or "",
            "native": True,
        })
    return invocazioni


def adapt_prompt_for_native_tools(prompt: str) -> str:
    """Adatta il system prompt quando il provider supporta i tool nativi.

    Rimuove l'obbligo di formattare il testo con blocchi recintati ```tool:...```
    evitando che modelli cloud avanzati (OpenAI, Anthropic, DeepSeek) si confondano
    fra l'emissione di testo e l'emissione di chiamate di funzione strutturate.
    """
    if not prompt:
        return ""

    # Sostituisce la regola del formato recintato con l'istruzione per i tool nativi
    p = re.sub(
        r"## REGOLA FONDAMENTALE[\s\S]*?```tool:NOME_DEL_TOOL[\s\S]*?```",
        "## REGOLA FONDAMENTALE (TOOL-CALLING NATIVO ATTIVO)\n"
        "Hai a disposizione strumenti dichiarati nativamente nella piattaforma.\n"
        "Ad ogni turno invoca lo strumento appropriato per compiere un'azione concreta.\n"
        "Non emettere blocchi markdown per invocare i tool: usa le chiamate di funzione della piattaforma.\n"
        "Segui rigorosamente il ciclo di lavoro (specifica -> pianifica -> orientati -> leggi -> agisci -> verifica -> chiudi).",
        prompt,
    )

    # Rimuove l'elenco testuale dei parametri tool se già descritti nello schema nativo
    p = re.sub(
        r"## TOOL DISPONIBILI[\s\S]*?(?=\n## |\Z)",
        "## TOOL DISPONIBILI\nI parametri dettagliati di ciascun tool sono descritti nello schema strutturato fornito al modello.\n",
        p,
    )
    return p.strip()
