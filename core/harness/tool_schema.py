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
                           "files": {"type": "array", "items": _STRINGA},
                           "depends_on": {"type": "array", "items": _STRINGA}},
            "required": ["id", "title"]}}},
       ["queue_id", "items"]),
    _f("propose_verify",
       "Contesta la prova dichiarata quando NON E' ESEGUIBILE — la shell la "
       "rifiuta, un programma non c'e' — e proponi quella giusta. Prima "
       "eseguila tu e falla passare, poi proponila: una prova che nessuno ha "
       "visto girare non e' una prova. Non serve quando la prova gira e "
       "fallisce: quello vuol dire che il lavoro non e' finito.",
       {"command": _STRINGA, "reason": _STRINGA},
       ["command", "reason"]),
    _f("complete_goal", "Dichiara finito il lavoro. Per richieste esplicative, panoramiche o domande dell'utente, il campo summary DEVE contenere la risposta e spiegazione ricca, dettagliata ed esaustiva da presentare all'utente in chat. Per compiti di programmazione, contiene il riassunto delle modifiche e verifiche.",
       {"summary": _STRINGA,
        "criteria": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": _STRINGA, "evidence": _STRINGA},
            "required": ["id", "evidence"]}}}, ["summary"]),
]

# --- EDA: disegnare un circuito in EasyEDA Pro -------------------------------
#: I pin si indicano per NOME ("VOUT", "GND") e non per numero. Il numero e' un
#: dato che il modello dovrebbe ricordare fra due chiamate, e ricordarlo male
#: produce un circuito che sembra giusto; il nome sta scritto sul simbolo.
_PIN = {"type": "array", "items": {
    "type": "object",
    "properties": {"part": _STRINGA, "pin": _STRINGA},
    "required": ["part", "pin"]}}
_PUNTI = {"type": "array", "items": {
    "type": "object",
    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
    "required": ["x", "y"]}}

TOOL_SCHEMAS += [
    _f("eda_status", "Stato del bridge EasyEDA, progetto aperto e numero di pezzi. Da chiamare per prima.",
       {}, []),
    _f("eda_search_part", "Cerca un componente in libreria. Restituisce uuid e library_uuid, che servono a eda_place_part.",
       {"query": _STRINGA, "limit": _INTERO}, ["query"]),
    _f("eda_place_part", "Piazza sul foglio un componente trovato con eda_search_part. Restituisce il suo id.",
       {"uuid": _STRINGA, "library_uuid": _STRINGA,
        "x": {"type": "number"}, "y": {"type": "number"},
        "rotation": _INTERO}, ["uuid", "library_uuid", "x", "y"]),
    _f("eda_list_parts", "I pezzi gia' sul foglio, con id e posizione.", {}, []),
    _f("eda_pins", "La mappa dei pin di un pezzo: nome, numero, coordinate. Chiamalo PRIMA di collegare.",
       {"part": _STRINGA}, ["part"]),
    _f("eda_connect", "Collega dei pin sulla stessa net. I pin si indicano per nome, es. {\"part\": \"<id>\", \"pin\": \"VOUT\"}.",
       {"net": _STRINGA, "pins": _PIN}, ["net", "pins"]),
    _f("eda_wire", "Disegna una pista come spezzata fra due o piu' punti, taggata con la net. Usa le coordinate dei pin lette da eda_pins.",
       {"net": _STRINGA, "points": _PUNTI, "color": _STRINGA}, ["net", "points"]),
    _f("eda_note", "Scrive una nota sul foglio: serve a lasciare per iscritto una decisione o un limite noto.",
       {"text": _STRINGA, "x": {"type": "number"}, "y": {"type": "number"},
        "size": {"type": "number"}, "color": _STRINGA}, ["text", "x", "y"]),
    _f("eda_verify", "Netlist ed ERC nativo di EasyEDA: e' la PROVA che i collegamenti esistono davvero. Obbligatorio prima di complete_goal.",
       {}, []),
    _f("eda_capture", "Salva un'immagine del foglio, cosi' il lavoro si puo' guardare.",
       {"path": _STRINGA}, []),
    _f("eda_save", "Salva il progetto EasyEDA.", {}, []),
    _f("eda_pcb_drc", "Esegue il DRC nativo sul PCB di EasyEDA Pro: verifica piste disconnesse, cortocircuiti e distanze.",
       {}, []),
    _f("eda_pcb_unrouted", "Elenca tutte le net e i pad ancora da sbroccare sul layout PCB.",
       {}, []),
    _f("eda_pcb_route_net", "Traccia piste di rame a 45 gradi fra i pad di una net sul PCB.",
       {"net": _STRINGA, "width_mil": {"type": "number"}, "layer": _INTERO}, ["net"]),
    _f("eda_pcb_add_via", "Piazza un via di rame per cambiare layer sul PCB.",
       {"x": {"type": "number"}, "y": {"type": "number"}, "net": _STRINGA,
        "hole_mil": {"type": "number"}, "diameter_mil": {"type": "number"}}, ["x", "y"]),
    _f("eda_pcb_outline", "Crea o assicura il contorno scheda rettangolare chiuso sul layer Board Outline (11).",
       {"width_mm": {"type": "number"}, "height_mm": {"type": "number"}}, []),
    _f("eda_pcb_route_all", "Instrada automaticamente a 45 gradi tutte le net non ancora collegate sul PCB.",
       {"default_width_mil": {"type": "number"}, "power_width_mil": {"type": "number"}}, []),
    _f("eda_pcb_mounting_holes", "Posiziona 4 fori di fissaggio M3 nei quattro angoli della scheda.",
       {"margin_mm": {"type": "number"}, "hole_dia_mm": {"type": "number"}, "pad_dia_mm": {"type": "number"}}, []),
    _f("eda_export_gerbers", "Esporta i file Gerber per la produzione e fabbricazione JLCPCB del PCB.",
       {}, []),
]

# --- KiCad: progettare una scheda vera ---------------------------------------
#: I pad si indicano per riferimento e numero, le net per nome: un agente non
#: deve tenere a mente indici interni fra una chiamata e l'altra.
_XY = {"type": "number"}
_PUNTI_MM = {"type": "array", "items": {
    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}}

TOOL_SCHEMAS += [
    _f("kicad_status", "KiCad e' installato? Che versione? Che progetto e' aperto? Chiamalo per primo.", {}, []),
    _f("kicad_open", "Apre un progetto KiCad (cartella, .kicad_pro o .kicad_pcb) e lo rende quello corrente.",
       {"path": _STRINGA}, ["path"]),
    _f("kicad_board_read", "Contorno, numero di pezzi e di net della scheda aperta.", {}, []),
    _f("kicad_list_parts", "I footprint sulla scheda: riferimento, valore, posizione, lato, numero di pad.", {}, []),
    _f("kicad_pads", "I pad di un footprint con net e posizione assoluta. Chiamalo PRIMA di instradare.",
       {"part": _STRINGA}, ["part"]),
    _f("kicad_nets", "Le net della scheda, con quanti pad tocca ciascuna.", {}, []),
    _f("kicad_trace_width", "Larghezza minima di una pista per una corrente, secondo IPC-2221.",
       {"current_a": {"type": "number"}, "delta_t_c": {"type": "number"},
        "thickness_oz": {"type": "number"},
        "layer": {"type": "string", "enum": ["external", "internal"]}}, ["current_a"]),
    _f("kicad_board_evaluate", "Giudica il piazzamento: sovrapposizioni, contorno, distanze, disaccoppiamento.", {}, []),
    _f("kicad_placement_optimize", "Calcola un piazzamento migliore. NON scrive: restituisce gli spostamenti proposti.",
       {"iterations": _INTERO, "seed": _INTERO,
        "lock": {"type": "array", "items": _STRINGA}}, []),
    _f("kicad_placement_apply", "Riscrive le posizioni nel .kicad_pcb. Con dry_run non tocca il file.",
       {"moves": {"type": "array", "items": {"type": "object", "properties": {
           "reference": _STRINGA, "x_mm": _XY, "y_mm": _XY, "rotation": _INTERO},
           "required": ["reference", "x_mm", "y_mm"]}},
        "dry_run": {"type": "boolean"}}, ["moves"]),
    _f("kicad_add_track", "Traccia un segmento di pista fra due punti, in millimetri.",
       {"start": {"type": "array", "items": _XY}, "end": {"type": "array", "items": _XY},
        "width_mm": _XY, "layer": _STRINGA, "net": _STRINGA},
       ["start", "end", "width_mm"]),
    _f("kicad_add_route", "Instrada una spezzata fra piu' punti: il modo normale di collegare due pad.",
       {"points": _PUNTI_MM, "width_mm": _XY, "layer": _STRINGA, "net": _STRINGA},
       ["points", "width_mm"]),
    _f("kicad_add_via", "Mette un via passante fra due layer di rame.",
       {"at": {"type": "array", "items": _XY}, "size_mm": _XY, "drill_mm": _XY,
        "net": _STRINGA, "layers": {"type": "array", "items": _STRINGA}}, ["at"]),
    _f("kicad_add_footprint", "Mette un footprint sulla scheda: fori di fissaggio, fiducial, schermature.",
       {"library_id": _STRINGA, "reference": _STRINGA, "value": _STRINGA,
        "x_mm": _XY, "y_mm": _XY, "rotation": _XY, "layer": _STRINGA,
        "pads": {"type": "array", "items": {"type": "object"}}},
       ["library_id", "reference", "value", "x_mm", "y_mm"]),
    _f("kicad_remove_footprint", "Toglie un footprint dalla scheda. Il rame che lo raggiungeva resta.",
       {"reference": _STRINGA}, ["reference"]),
    _f("kicad_undo", "Annulla l'ultima scrittura sul PCB, dalla copia fatta prima di applicarla.", {}, []),
    _f("kicad_drc", "Design Rule Check di KiCad sul PCB: la prova che il rame sta in piedi. Obbligatorio prima di complete_goal.", {}, []),
    _f("kicad_erc", "Electrical Rule Check sullo schematico.", {}, []),
    _f("kicad_export_gerbers", "Gerber e file di foratura: il pacchetto che si manda in fabbrica.",
       {"output_dir": _STRINGA}, []),
    _f("kicad_export_bom", "La distinta base, dallo schematico.", {"output_path": _STRINGA}, []),
    _f("kicad_render", "Un immagine della scheda (3d o svg), cosi il lavoro si puo guardare.",
       {"output_path": _STRINGA, "mode": {"type": "string", "enum": ["3d", "svg"]}}, []),
    # pcbnew bridge: creazione e ispezione diretta via API pcbnew
    _f("kicad_pcbnew_status",
       "Verifica che il ponte pcbnew sia disponibile prima di creare o leggere schede: restituisce versione di KiCad e percorsi trovati. Usalo come primo passo quando non sai se l'ambiente e pronto.",
       {}, []),
    _f("kicad_libraries",
       "Elenco delle librerie di footprint installate. Usalo per scegliere la libreria giusta prima di cercare un footprint o aggiungerlo alla scheda.",
       {}, []),
    _f("kicad_search_footprint",
       "Cerca footprint nelle librerie KiCad per nome o parola chiave. Usalo quando conosci il tipo di componente (es. C_0805, R_0402) ma non la libreria esatta.",
       {"query": _STRINGA,
        "limite": {"type": "integer", "default": 20},
        "libreria": _STRINGA}, ["query"]),
    _f("kicad_new_board",
       "Crea una nuova scheda KiCad vuota con le dimensioni date. Usalo per iniziare un progetto PCB da zero, prima di aggiungere componenti.",
       {"percorso": _STRINGA,
        "larghezza_mm": _XY,
        "altezza_mm": _XY,
        "net": {"type": "array", "items": _STRINGA},
        "sovrascrivi": {"type": "boolean", "default": False}}, ["percorso"]),
    _f("kicad_add_part",
       "Aggiunge un componente (footprint) a una scheda esistente, con posizione, rotazione e net per pad. Usalo dopo kicad_new_board per popolare la scheda.",
       {"percorso": _STRINGA,
        "libreria": _STRINGA,
        "footprint": _STRINGA,
        "riferimento": _STRINGA,
        "valore": _STRINGA,
        "x_mm": _XY, "y_mm": _XY,
        "rotazione": _XY,
        "net_per_pad": {"type": "object"}},
       ["percorso", "libreria", "footprint", "riferimento"]),
    _f("kicad_read_board_full",
       "Legge lo stato completo di una scheda KiCad: dimensioni, componenti, net. Usalo per verificare che kicad_new_board e kicad_add_part abbiano prodotto il risultato atteso.",
       {"percorso": _STRINGA}, ["percorso"]),
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
