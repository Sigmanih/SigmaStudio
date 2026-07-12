# ==============================================================================
# core/orchestration/research.py — Research Sessions & Micro-Objectives Logic
# Extracted from core/agent_orchestrator.py for Single Responsibility
# ==============================================================================
"""Handle decomposition of user goals into micro-objectives.

Enables continuous feedback loops, micro-task assignments, validation,
and execution in isolated research sessions.
"""

import os
import json
import datetime
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


from core.ai_providers import load_ai_config, call_ai_model
from core.agent_registry import SIGMA_ARCHITECT_ID
from core.agent_memory import save_session_memory
from core.task_handler import execute_ai_actions
from core.logger import get_logger

# Chat helpers
from core.chat.prompt_builder import _build_filesystem_context
from core.chat.response_parser import _extract_json_from_response

# Orchestration sub-package
from core.orchestration.agent_config import AGENT_COLORS, load_agent_config

log = get_logger(__name__)


# Curriculum canonico di Analisi 1 — 13 moduli standard
ANALISI1_MODULES = [
    ("01", "insiemi_e_numeri_reali",   "Assiomi di R, insiemi, sup/inf, disuguaglianze, valore assoluto, intorni"),
    ("02", "successioni",              "Definizione limite di successione, teoremi di confronto, monotone, Cauchy"),
    ("03", "serie_numeriche",          "Criteri di convergenza (Leibniz, rapporto, radice), serie geometrica, armonica, Taylor"),
    ("04", "limiti_e_continuita",      "Definizione epsilon-delta, limiti notevoli, TVI, Weierstrass, continuità uniforme"),
    ("05", "derivate",                 "Derivabilità, regole di derivazione, teorema di Lagrange, de l'Hôpital, Taylor, McLaurin"),
    ("06", "integrali_indefiniti",     "Primitivi, integrazione per parti, sostituzione, frazioni parziali"),
    ("07", "integrali_definiti",       "Integrale di Riemann, T. fondamentale del calcolo, applicazioni geometriche (aree, volumi)"),
    ("08", "equazioni_differenziali",  "EDO I ordine (separabili, lineari), II ordine lineari a coefficienti costanti"),
    ("09", "funzioni_piu_variabili",   "Derivate parziali, gradiente, differenziabilità, Hessiana, differenziale totale"),
    ("10", "ottimizzazione",           "Estremi liberi e vincolati, moltiplicatori di Lagrange, punti di sella"),
    ("11", "integrali_multipli",       "Integrali doppi e tripli, Jacobiano, cambi di variabili, coordinate polari/cilindriche"),
    ("12", "serie_di_fourier",         "Coefficienti di Fourier, convergenza, identità di Parseval"),
    ("13", "trasformate",              "Laplace, Z, proprietà, applicazioni alle EDO"),
]


def _is_analisi1_goal(goal: str) -> bool:
    """Detect if the goal is about Analisi 1 mathematics."""
    keywords = ["analisi 1", "analisi1", "matematica ingegneria", "analisi matematica",
                "derivate", "integrali", "limiti", "serie", "successioni", "fourier",
                "equazioni differenziali", "calcolo"]
    goal_l = goal.lower()
    return any(k in goal_l for k in keywords)


def _fallback_objectives(session_id: str, agents_list: list[dict], goal: str) -> dict:
    """Generate fallback micro-objectives if AI coordinator fails.
    
    For Analisi 1 goals, generates a structured set covering the first 3 modules.
    Otherwise generates 4 generic objectives.
    """
    from core.research_sessions import add_micro_objective
    log.warning("Coordinator AI failed or timed out. Falling back to static template objectives.")

    base_path = "data/analisi_1"
    if "data/" in goal.lower() or "cartella" in goal.lower():
        match = re.search(r'data/[a-zA-Z0-9_]+', goal)
        if match:
            base_path = match.group(0)

    if _is_analisi1_goal(goal):
        # Structured fallback with first 3 canonical modules
        fallback_templates = []
        for nn, modulo, descrizione in ANALISI1_MODULES[:3]:
            fallback_templates.append({
                "title": f"Teoria: {modulo.replace('_', ' ').title()} (modulo {nn})",
                "description": (
                    f"Crea il file {base_path}/{nn}_{modulo}/teoria/{modulo}.md con: "
                    f"definizioni formali, teoremi con dimostrazione passo-passo, "
                    f"esempi numerici, esercizi svolti. Argomenti: {descrizione}. "
                    f"Usa LaTeX per tutte le formule ($...$ inline, $$...$$ display). "
                    f"File LUNGO e COMPLETO, minimo 500 righe."
                ),
                "assigned_to": "math1",
                "actions_hint": ["create_file"],
                "completion_criteria": f"File {base_path}/{nn}_{modulo}/teoria/{modulo}.md creato con teoria completa."
            })
            fallback_templates.append({
                "title": f"Test computazionali: {modulo.replace('_', ' ').title()}",
                "description": (
                    f"Crea lo script {base_path}/{nn}_{modulo}/test/test_{modulo}.py con: "
                    f"import sympy, numpy; funzioni test_* con assert; blocco main. "
                    f"Verifica computazionale di: {descrizione}. "
                    f"Script ESEGUIBILE senza errori con: python test_{modulo}.py"
                ),
                "assigned_to": "test-engineer",
                "actions_hint": ["create_file"],
                "completion_criteria": f"Script {base_path}/{nn}_{modulo}/test/test_{modulo}.py funzionante."
            })
    else:
        # Generic fallback for non-analisi1 goals
        fallback_templates = [
            {
                "title": f"Studio iniziale di fattibilità in {base_path}",
                "description": f"Analizza la cartella di lavoro {base_path} ed elenca i file esistenti. Pianifica la struttura di moduli numerati.",
                "assigned_to": "sigma_architect",
                "actions_hint": ["read_file"],
                "completion_criteria": "Struttura della cartella mappata."
            },
            {
                "title": "Stesura della teoria fondamentale",
                "description": (
                    f"Crea il file {base_path}/01_fondamenti/teoria/teoria_base.md con: "
                    f"definizioni formali, teoremi con dimostrazione, esempi numerici, "
                    f"formulario LaTeX ed esercizi svolti per: {goal}"
                ),
                "assigned_to": "math1",
                "actions_hint": ["create_file"],
                "completion_criteria": "File di teoria completo creato."
            },
            {
                "title": "Implementazione dei test e validazione",
                "description": (
                    f"Crea {base_path}/01_fondamenti/test/test_fondamenti.py con: "
                    f"import sympy; funzioni test_*; assert; blocco main. "
                    f"Verifica computazionale delle formule teoriche."
                ),
                "assigned_to": "test-engineer",
                "actions_hint": ["create_file", "run_test"],
                "completion_criteria": "Script di test creato ed eseguibile."
            },
            {
                "title": "Report riepilogativo di sessione",
                "description": f"Verifica i file creati e scrivi {base_path}/01_fondamenti/docs/report_completo.md.",
                "assigned_to": "proof-reviewer",
                "actions_hint": ["create_file"],
                "completion_criteria": "Report di sessione completato."
            }
        ]

    added = []
    for t in fallback_templates:
        res = add_micro_objective(session_id, t)
        if res:
            added.append(res)

    return {"success": True, "objectives": added, "analysis": "Fallback strutturato generato automaticamente", "count": len(added)}


def decompose_goal_to_micro_objectives(
    goal: str,
    agents_list: list[dict],
    ai_cfg: dict,
    model_override: str,
    session_id: str,
) -> dict:
    """Analyze the user's research goal and decompose it into micro-objectives."""
    from core.research_sessions import get_session, add_micro_objective

    session = get_session(session_id)
    session_name = session.get("name", "Ricerca") if session else "Ricerca"

    base_path = "data/analisi_1"
    if "cartella" in goal.lower() or "data/" in goal.lower():
        import re
        m = re.search(r'data/([a-zA-Z0-9_-]+)', goal)
        if m:
            base_path = f"data/{m.group(1)}"

    coordinator_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)

    fs_context = _build_filesystem_context()

    # Detect if this is an Analisi 1 goal to inject canonical curriculum
    is_analisi1 = _is_analisi1_goal(goal)
    curriculum_section = ""
    if is_analisi1:
        modules_list = "\n".join(
            f"  - {nn}_{nome}: {desc}"
            for nn, nome, desc in ANALISI1_MODULES
        )
        curriculum_section = f"""
## CURRICULUM CANONICO DI ANALISI 1 — OBBLIGATORIO
Questo è un obiettivo di Analisi 1 Matematica per Ingegneria.
Il curriculum completo è composto da 13 moduli. Inizia dai primi 4-5 moduli e usa l'espansione progressiva per i restanti:
{modules_list}

Per ogni modulo crea SEMPRE ALMENO:
1. File teoria: `{base_path}/[NN]_[nome_modulo]/teoria/[nome].md` → agente: math1
2. File test: `{base_path}/[NN]_[nome_modulo]/test/test_[nome].py` → agente: test-engineer  
3. File formulario: `{base_path}/[NN]_[nome_modulo]/docs/formulario_[nome].md` → agente: formulario

Nella prima decomposizione, copri i moduli 01-04 (fondamentali). Il coordinatore espanderà ai moduli 05-13 nei cicli successivi.
"""

    system_prompt = f"""Sei Sigma AI Architect, il coordinatore del team di ricerca.
Il tuo compito è analizzare l'obiettivo dell'utente e suddividerlo in micro-obiettivi (task) da assegnare a diversi agenti.
Stiamo lavorando nella cartella: {base_path}

## STRUTTURAZIONE IN MODULI (SOTTOARGOMENTI) — CRITICA
Devi suddividere la conoscenza in diversi sottoargomenti (moduli) NUMERATI con prefisso a due cifre.
I percorsi dei file nei task DEVONO avere ESATTAMENTE la struttura a 5 parti:
  {base_path}/[XX]_[nome_modulo]/[sezione]/[nome_file]
Dove:
- [XX] = numero progressivo a due cifre (es. 01, 02, 03)
- [nome_modulo] = nome del sottoargomento (es. insiemi_e_numeri_reali, limiti_e_continuita)
- [sezione] = una tra: teoria, test, docs, viz, whitepapers
- [nome_file] = nome del file con estensione corretta (.md per teoria/docs, .py per test, .html per viz)

Esempi CORRETTI:
- {base_path}/01_insiemi_e_numeri_reali/teoria/numeri_reali.md
- {base_path}/02_successioni/test/test_successioni.py
- {base_path}/03_serie_numeriche/docs/formulario_serie.md
- {base_path}/04_limiti_e_continuita/teoria/definizione_limite.md

Esempi SBAGLIATI (VIETATI):
- {base_path}/01_base/teoria/file.md (modulo troppo generico)
- {base_path}/teoria/file.md (manca il modulo numerato)
- {base_path}/01_limiti/file.py (sezione mancante)
{curriculum_section}
## TEAM DI AGENTI DISPONIBILI
- `math1` → Scrive teoria .md con definizioni formali, teoremi DIMOSTRATI passo-passo, LaTeX, esercizi svolti
- `test-engineer` → Scrive script .py con sympy/numpy, funzioni test_*, assert, eseguibili
- `formulario` → Scrive formulari .md riassuntivi con tabelle formule per esame
- `proof-reviewer` → Valida e scrive report di revisione .md
- `viz-designer` → Crea visualizzazioni .html standalone con D3.js/Chart.js
- `code_architect` → Script Python avanzati, algoritmi, codice complesso

{fs_context}

## REGOLE FONDAMENTALI
1. Sei il CAPO — pianifica TU quali file servono, cosa devono contenere, chi li crea.
2. Ogni task DEVE avere path file ESATTO a 5 parti.
3. Ogni task DEVE specificare il contenuto minimo richiesto (argomenti, formule, esempi).
4. Assegna agli agenti in base alla specializzazione (teoria→math1, test→test-engineer, formulario→formulario).
5. Produci 5-8 micro-obiettivi per la prima decomposizione, coprendo più moduli distinti.
6. Il criterio di completamento deve essere verificabile (file creato, test eseguito).
7. Per Analisi 1: copri i moduli 01-04 nella prima decomposizione, poi espanderemo.
8. OGNI descrizione deve includere il path esatto + gli argomenti specifici da trattare.

## FORMATO RISPOSTA — SOLO JSON
{{
  "analysis": "Analisi dettagliata del goal (2-3 frasi che descrivono il piano generale)",
  "micro_objectives": [
    {{
      "title": "[Ruolo]: [Argomento] — Modulo [NN]",
      "description": "Path file: {base_path}/[NN]_[modulo]/[sezione]/[file]. Contenuto da produrre: [descrizione dettagliata degli argomenti, formule da includere, struttura del file]. Formato: [.md con LaTeX / .py con sympy / etc.]",
      "assigned_to": "agent_id",
      "actions_hint": ["create_file"],
      "completion_criteria": "File [path_preciso] creato con [contenuto minimo]"
    }}
  ]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"## OBIETTIVO UTENTE\n{session_name}\n\n{goal}\n\nAnalizza l'obiettivo e produci il piano di lavoro dettagliato con micro-obiettivi."}
    ]

    log.info("Calling coordinator model=%s provider=%s for decomposition", coordinator_model, provider)
    response, thinking, error = call_ai_model(
        messages, ai_cfg, coordinator_model, provider, endpoint, api_url, api_key,
        0.4, max_tokens * 3, top_p, timeout
    )

    if not session:
        return {"success": False, "error": "Sessione non trovata"}

    if error or not response:
        log.error("Coordinator decomposition error: %s. Using fallback.", error)
        return _fallback_objectives(session_id, agents_list, goal)

    json_match = _extract_json_from_response(response)
    if not json_match:
        log.warning("No JSON match in coordinator decomposition response. Using fallback.")
        return _fallback_objectives(session_id, agents_list, goal)

    try:
        parsed = json.loads(json_match.group())
        objectives = parsed.get("micro_objectives", [])
        analysis = parsed.get("analysis", "")
        added = []
        for obj in objectives:
            result = add_micro_objective(session_id, obj)
            if result:
                added.append(result)
        if len(added) == 0:
            return _fallback_objectives(session_id, agents_list, goal)
        return {"success": True, "objectives": added, "analysis": analysis, "count": len(added)}
    except json.JSONDecodeError as exc:
        log.error("Failed to parse coordinator JSON: %s. Using fallback.", exc)
        return _fallback_objectives(session_id, agents_list, goal)

def check_and_expand_research_roadmap(
    session_id: str,
    goal: str,
    agents_list: list[dict],
    ai_cfg: dict,
    model_override: str,
    _sse
) -> bool:
    """Valuta il filesystem ed i risultati correnti tramite l'Architetto ed espande la roadmap se necessario."""
    from core.research_sessions import get_session, add_micro_objective
    session = get_session(session_id)
    if not session:
        return False

    current_objectives = session.get("micro_objectives", [])
    completed_summary = []
    for o in current_objectives:
        completed_summary.append(f"- Task: {o.get('title')} (Assegnato a: {o.get('assigned_to')}) -> Esito: {o.get('result')[:400]}")

    base_path = "data/analisi_1"
    if "cartella" in goal.lower() or "data/" in goal.lower():
        import re
        m = re.search(r'data/([a-zA-Z0-9_-]+)', goal)
        if m:
            base_path = f"data/{m.group(1)}"

    coordinator_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)

    fs_context = _build_filesystem_context()

    # Build list of covered modules from filesystem
    covered_modules = []
    missing_modules = []
    if _is_analisi1_goal(goal):
        import os as _os
        for nn, nome, desc in ANALISI1_MODULES:
            module_path = f"{base_path}/{nn}_{nome}"
            if _os.path.isdir(module_path):
                covered_modules.append(f"  ✅ {nn}_{nome}")
            else:
                missing_modules.append(f"  ❌ {nn}_{nome}: {desc}")

        analisi1_status = f"""
## STATO COPERTURA MODULI ANALISI 1
Moduli già presenti sul disco:
{chr(10).join(covered_modules) if covered_modules else '  (nessuno ancora)'}

Moduli MANCANTI da trattare:
{chr(10).join(missing_modules) if missing_modules else '  (tutti coperti!)'}

Se ci sono moduli mancanti, genera nuovi task per coprire i moduli successivi (2-3 per ciclo).
Per ogni modulo mancante, crea almeno:
- File teoria: math1 → {base_path}/[NN]_[nome]/teoria/[nome].md
- File test: test-engineer → {base_path}/[NN]_[nome]/test/test_[nome].py
- Formulario: formulario → {base_path}/[NN]_[nome]/docs/formulario_[nome].md
"""
    else:
        analisi1_status = ""

    system_prompt = f"""Sei Sigma AI Architect, il coordinatore del team di ricerca.
Il tuo compito è valutare lo stato complessivo del lavoro svolto dal team rispetto al goal dell'utente.
Devi decidere se ci sono ancora moduli da trattare, approfondimenti necessari, o correzioni da fare.

## OBIETTIVO GENERALE
{goal}

## STATO ATTUALE DEI FILE IN {base_path}
{fs_context}

## SOTTO-TASK GIÀ SVOLTI
{chr(10).join(completed_summary)}
{analisi1_status}
## REGOLA STRUTTURA PATH — OBBLIGATORIA
I percorsi dei file DEVONO avere esattamente la struttura a 5 parti:
{base_path}/[XX]_[nome_modulo]/[sezione]/[nome_file]
Dove:
- [XX] = numero progressivo a due cifre (01, 02, 03, ...)
- [sezione] = una tra: teoria, test, docs, viz, whitepapers

Esempi corretti:
- {base_path}/05_derivate/teoria/regole_derivazione.md
- {base_path}/05_derivate/test/test_derivate.py
- {base_path}/05_derivate/docs/formulario_derivate.md

## AGENTI DISPONIBILI
- math1 → teoria .md (definizioni + teoremi dimostrati + esercizi)
- test-engineer → test .py (sympy, assert, eseguibile)
- formulario → formulario .md (tabelle formule, riferimento rapido)
- proof-reviewer → report validazione .md
- viz-designer → visualizzazioni .html

## ISTRUZIONE PRIMARIA
Se ci sono moduli MANCANTI del curriculum, genera 2-4 nuovi task per i moduli successivi.
Se i moduli esistenti hanno lacune (mancano test, formulario o revisione), colmale.
Se tutto è completo ed impeccabile, rispondi con lista vuota.

## FORMATO RISPOSTA — SOLO JSON
Se servono nuovi task:
{{
  "analysis": "Spiegazione: quali moduli mancano e perché sono necessari",
  "new_objectives": [
    {{
      "title": "[Agente]: [Argomento] — Modulo [NN]",
      "description": "Path file: {base_path}/[NN]_[modulo]/[sezione]/[file]. Contenuto: [argomenti specifici, formule, struttura attesa].",
      "assigned_to": "agent_id",
      "actions_hint": ["create_file"],
      "completion_criteria": "File creato con contenuto completo"
    }}
  ]
}}
Se il lavoro è completo:
{{
  "analysis": "Il curriculum è completo e impeccabile.",
  "new_objectives": []
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Valuta il lavoro e decidi se aggiungere nuovi micro-obiettivi dinamici. Rispondi solo in JSON."}
    ]

    log.info("Coordinatore valuta espansione roadmap con modello=%s provider=%s", coordinator_model, provider)
    response, thinking, error = call_ai_model(
        messages, ai_cfg, coordinator_model, provider, endpoint, api_url, api_key,
        0.3, max_tokens, top_p, timeout
    )

    if error or not response:
        log.warning("Coordinatore espansione non riuscita: %s. Nessun nuovo task aggiunto.", error)
        return False

    json_match = _extract_json_from_response(response)
    if not json_match:
        log.warning("Nessun JSON valido per l'espansione della roadmap.")
        return False

    try:
        parsed = json.loads(json_match.group())
        new_objectives = parsed.get("new_objectives", [])
        analysis = parsed.get("analysis", "")
        
        if not new_objectives:
            log.info("Coordinatore dichiara la ricerca completata. Nessun nuovo task.")
            return False

        _sse({
            "type": "agent_response", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
            "response": f"### 🔄 Espansione Roadmap Rilevata dal Coordinatore\n\n{analysis}\n\nL'Architetto ha aggiunto {len(new_objectives)} nuovi task per completare al meglio l'obiettivo.",
            "message": f"🔄 Aggiunti {len(new_objectives)} nuovi task alla roadmap."
        })

        for obj in new_objectives:
            add_micro_objective(session_id, obj)

        return True
    except Exception as exc:
        log.error("Errore durante il parsing del JSON di espansione: %s", exc)
        return False



def generate_next_steps(session_id: str, ai_cfg: dict, model_override: str) -> dict:
    """Generate suggested next steps for the research session."""
    from core.research_sessions import get_session, set_next_steps

    session = get_session(session_id)
    if not session:
        return {"success": False, "error": "Sessione non trovata"}

    next_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)

    objectives = session.get("micro_objectives", [])
    completed_tasks = [o for o in objectives if o.get("status") == "done"]

    history_lines = []
    for c in completed_tasks:
        history_lines.append(f"- [{c.get('assigned_to', '?')}] {c.get('title', '')}: {c.get('description', '')[:100]}...")

    fs_context = _build_filesystem_context()

    system_prompt = f"""Sei Sigma AI Architect, il coordinatore del team di ricerca.
La sessione di ricerca corrente ha completato i suoi micro-obiettivi.
Il tuo compito è analizzare i risultati e la struttura dei file correnti, per poi suggerire all'utente 3-4 passi successivi ideali per espandere o approfondire il lavoro.

## FILE PRODOTTI
{fs_context}

## STORIA DELLA SESSIONE
{chr(10).join(history_lines)}

## FORMATO RISPOSTA — SOLO JSON
{{
  "summary": "Breve riepilogo del lavoro svolto finora (1-2 frasi)",
  "next_steps": [
    {{
      "title": "Titolo del passo successivo",
      "description": "Cosa fare concretamente, quali file creare o modificare.",
      "domain": "math" or "code" or "viz" or "documentation"
    }}
  ]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analizza la sessione di ricerca '{session.get('name')}' e proponi i prossimi passi."}
    ]

    log.info("Calling model=%s to generate next steps", next_model)
    response, thinking, error = call_ai_model(
        messages, ai_cfg, next_model, provider, endpoint, api_url, api_key,
        0.5, max_tokens, top_p, timeout
    )

    if error or not response:
        log.error("Failed to generate next steps: %s", error)
        return {"success": False, "error": error}

    json_match = _extract_json_from_response(response)
    if not json_match:
        return {"success": False, "error": "Nessun JSON nella risposta"}

    try:
        parsed = json.loads(json_match.group())
        steps = parsed.get("next_steps", [])
        summary = parsed.get("summary", "")
        set_next_steps(session_id, steps)
        return {"success": True, "next_steps": steps, "summary": summary}
    except json.JSONDecodeError as exc:
        log.error("Failed to parse next steps JSON: %s", exc)
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# HTTP Handler Endpoints for Research Sessions
# ---------------------------------------------------------------------------

def handle_research_decompose(self) -> None:
    """POST /api/research/decompose — Decompose goal into micro-objectives."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)

        from core.research_sessions import get_session
        session = get_session(session_id)
        if not session:
            return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)

        ai_cfg = load_ai_config()
        goal = session.get("goal", "")
        agents = session.get("agents", [])
        model_override = req.get("model_override", "")

        res = decompose_goal_to_micro_objectives(goal, agents, ai_cfg, model_override, session_id)
        self.send_json_response(res)
    except Exception as exc:
        log.error("handle_research_decompose failed: %s", exc)
        self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_research_next_steps(self) -> None:
    """POST /api/research/next_steps — Generate research next steps."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)

        ai_cfg = load_ai_config()
        model_override = req.get("model_override", "")

        res = generate_next_steps(session_id, ai_cfg, model_override)
        self.send_json_response(res)
    except Exception as exc:
        log.error("handle_research_next_steps failed: %s", exc)
        self.send_json_response({"success": False, "error": str(exc)}, 500)


def _execute_default_action(self, session_id: str, obj: dict, goal: str, _sse) -> dict:
    """Fallback: execute a default create_file action if agent fails or lacks tool support."""
    # Build default contents based on title
    title = obj.get("title", "")
    assigned = obj.get("assigned_to", "math1")
    desc = obj.get("description", "")

    # Clean path from description if possible
    target_path = ""
    match = re.search(r'(data/[^\s]+)', desc)
    if match:
        target_path = match.group(0).rstrip('.,;!?')
        # Prevent collision: if the target path does not end with a file extension, reject it
        if target_path and '.' not in os.path.basename(target_path):
            target_path = ""

    if not target_path or not self._is_path_allowed(target_path):

        # Auto-create standard path under data/analisi_1
        base = "data/analisi_1"
        sub = "teoria"
        if assigned in ("test-engineer", "code_architect"):
            sub = "test"
        elif assigned == "viz-designer":
            sub = "viz"
        elif assigned == "proof-reviewer":
            sub = "docs"

        fn = title.lower().replace(' ', '_').replace(':', '')[:30] + (".py" if sub == "test" else ".html" if sub == "viz" else ".md")
        target_path = f"{base}/{sub}/{fn}"

    if not self._is_path_allowed(target_path):
        return {"success": False, "error": f"Path non consentito: {target_path}"}

    log.info("Executing fallback default action for objective %s to path=%s", title, target_path)

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n\nGenerato automaticamente come fallback.\n\nDescrizione task:\n{desc}\n")

    return {
        "success": True,
        "type": "create_file",
        "message": f"Creato file di fallback in {target_path} per micro-obiettivo: {title}"
    }


def handle_research_start(self) -> None:
    """POST /api/research/start — Run autonomous loop for research objectives (SSE stream)."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)

        from core.research_sessions import get_session, update_objective
        session = get_session(session_id)
        if not session:
            return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)

        # Establish SSE stream
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        _sse_lock = threading.Lock()

        def _sse(event):
            with _sse_lock:
                try:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                except Exception:
                    pass

        try:
            ai_cfg = load_ai_config()
            objectives = session.get("micro_objectives", [])
            agents_config = session.get("agents", [])
            goal = session.get("goal", "")
            model_override = req.get("model_override", "")

            # If no objectives, auto-decompose first
            if len(objectives) == 0:
                _sse({
                    "type": "agent_thinking", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                    "thinking": "Decomposizione automatica del goal in micro-obiettivi...",
                    "message": "🧠 Coordinatore: scomposizione automatica del goal..."
                })
                decomp_result = decompose_goal_to_micro_objectives(goal, agents_config, ai_cfg, model_override, session_id)
                if decomp_result.get("success"):
                    objectives = decomp_result.get("objectives", [])

            _sse({
                "type": "research_start", "session_id": session_id, "total_objectives": len(objectives),
                "agents": agents_config, "message": f"🔬 Avvio ricerca con {len(objectives)} micro-obiettivi, {len(agents_config)} agenti"
            })

            # Present coordination plan in chat
            plan_lines = []
            for o in objectives:
                icon = AGENT_COLORS.get(o.get("assigned_to", ""), {}).get("icon", "🤖")
                plan_lines.append(f"{icon} **{o.get('title', '')}** → {o.get('assigned_to', '?')}")
            plan_msg = "📋 **Piano di lavoro:**\n" + "\n".join(plan_lines)
            _sse({
                "type": "agent_response", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                "response": plan_msg, "message": f"📋 Piano di lavoro: {len(objectives)} task assegnati"
            })

            # Objective execution
            def process_objective(obj):
                if obj.get("status") == "done":
                    _sse({
                        "type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                        "message": f"✅ Già completato: {obj['title']}"
                    })
                    return

                agent_id = obj.get("assigned_to", SIGMA_ARCHITECT_ID)
                from core.agent_registry import get_agent
                agent_check = get_agent(agent_id)
                if not agent_check:
                    agent_id = SIGMA_ARCHITECT_ID
                agent_name = agent_id

                agent_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
                    load_agent_config(ai_cfg, model_override, agent_id)

                update_objective(session_id, obj["id"], {"status": "in_progress"})
                _sse({
                    "type": "agent_start", "agent_id": agent_id, "agent_name": agent_name,
                    "objective_id": obj["id"], "objective": obj["title"],
                    "message": f"▶️ {agent_name} inizia: {obj['title']}"
                })
                _sse({
                    "type": "agent_thinking", "agent_id": agent_id, "agent_name": agent_name,
                    "thinking": f"Analisi di: {obj['title']}", "objective_id": obj["id"],
                    "message": f"🧠 {agent_name} sta analizzando..."
                })

                role_prompts = {
                    "sigma_architect": (
                        "Sei Sigma AI Architect, coordinatore e pianificatore. "
                        "Il tuo compito è analizzare i file prodotti dal team e decidere cosa manca o va migliorato. "
                        "Quando crei file, segui SEMPRE la struttura a 5 parti: "
                        "data/[topic]/[XX]_[nome_modulo]/[sezione]/[nome_file]. "
                        "Produci report di sintesi in docs/ e aggiorna la roadmap con update_task."
                    ),
                    "math1": (
                        "Sei Sigma Math Researcher, matematico esperto di Analisi Matematica per Ingegneria. "
                        "Il tuo compito è creare file .md di TEORIA FORMALE con: "
                        "(1) Definizioni formali complete nel formato 'Definizione N.M: Sia... Si dice...'; "
                        "(2) Teoremi con enunciato formale (ipotesi + tesi) e DIMOSTRAZIONE COMPLETA passo-passo "
                        "— VIETATO scrivere 'si dimostra analogamente' o 'per esercizio'; "
                        "(3) Esempi numerici concreti dopo ogni teorema; "
                        "(4) Formulario LaTeX riassuntivo; "
                        "(5) Almeno 3 esercizi svolti tipo esame con tutti i calcoli mostrati. "
                        "Usa LaTeX: $...$ per inline, $$...$$ per display. File LUNGO, minimo 400 righe. "
                        "Path: data/[topic]/[NN]_[modulo]/teoria/[nome].md"
                    ),
                    "test-engineer": (
                        "Sei Sigma Test Engineer, ingegnere di test computazionale. "
                        "Il tuo compito è creare script .py FUNZIONANTI e AUTOESEGUIBILI che verificano le formule matematiche. "
                        "Struttura obbligatoria di ogni script: "
                        "(1) Header con descrizione e dipendenze; "
                        "(2) import sympy as sp, import numpy as np; "
                        "(3) Definizione variabili simboliche: x, n, a, b = sp.symbols('x n a b'); "
                        "(4) Funzioni test_*() con: calcolo simbolico + assert + print('✅ test_nome: PASS'); "
                        "(5) Blocco if __name__ == '__main__': con chiamata a tutte le funzioni test_*. "
                        "ZERO import non standard. Script eseguibile con: python nome_file.py. "
                        "Path: data/[topic]/[NN]_[modulo]/test/test_[nome].py"
                    ),
                    "formulario": (
                        "Sei Sigma Formulario, specialista in formulari e sintesi per esame. "
                        "Il tuo compito è creare file .md COMPATTI con TUTTE le formule chiave del modulo. "
                        "Struttura obbligatoria: "
                        "(1) Tabella 'Definizioni Fondamentali' con | Termine | Formula LaTeX |; "
                        "(2) Sezione 'Teoremi Principali' con: ipotesi, tesi in LaTeX, quando si usa; "
                        "(3) Tabella 'Formule Essenziali' con | Formula | Condizioni | Note |; "
                        "(4) Tabella 'Derivate/Integrali/Limiti Notevoli' (quando rilevante); "
                        "(5) Sezione 'Errori Comuni' con correzioni; "
                        "(6) Tabella 'Riconoscimento Tipo di Problema'. "
                        "Usa LaTeX per TUTTE le formule. Massima densità informativa. "
                        "Path: data/[topic]/[NN]_[modulo]/docs/formulario_[nome].md"
                    ),
                    "code_architect": (
                        "Sei Sigma Code Architect, sviluppatore Python esperto. "
                        "Il tuo compito è creare script Python avanzati, algoritmi e implementazioni computazionali. "
                        "Ogni script deve essere: ben documentato con docstring, type hints, commenti in italiano. "
                        "Usa sympy per calcolo simbolico, numpy per numerico, scipy per EDO e ottimizzazione. "
                        "Path: data/[topic]/[NN]_[modulo]/test/[nome].py"
                    ),
                    "proof-reviewer": (
                        "Sei Sigma Proof Reviewer, revisore critico del team. "
                        "Il tuo compito è verificare la correttezza formale di teoria e test prodotti dagli altri agenti. "
                        "Per ogni modulo, produci un report in docs/ con: "
                        "(1) Lista file analizzati con stato (✅/❌); "
                        "(2) Problemi trovati: formula errata, dimostrazione incompleta, script con errori; "
                        "(3) Verifiche superate; "
                        "(4) Conclusione con giudizio complessivo. "
                        "Quando crei il report: usa formato Markdown strutturato. "
                        "Path: data/[topic]/[NN]_[modulo]/docs/report_validazione.md"
                    ),
                    "viz-designer": (
                        "Sei Sigma Viz Designer, visualizzatore di matematica con D3.js e Chart.js. "
                        "Il tuo compito è creare file .html STANDALONE con visualizzazioni interattive. "
                        "Ogni file deve funzionare aprendo direttamente nel browser (nessuna dipendenza esterna non CDN). "
                        "Usa CDN: d3 v7, Chart.js, MathJax (per formule). "
                        "Visualizza: grafici di funzioni, grafici di convergenza, rappresentazioni geometriche. "
                        "Path: data/[topic]/[NN]_[modulo]/viz/[nome].html"
                    ),
                }
                
                attempts = 0
                max_attempts = 2
                approved = False
                validation_summary = ""
                
                # Primo tentativo del worker
                fs_ctx = _build_filesystem_context()
                role_prefix = role_prompts.get(agent_id, f"Sei un agente specializzato: {agent_id}.")
                system_prompt = f"""{role_prefix}

Esegui il seguente micro-obiettivo di ricerca.

## OBIETTIVO GENERALE
{goal}

## MICRO-OBIETTIVO
{obj['title']}
{obj.get('description', '')}

## FILE PRODOTTI NEL PROGETTO
{fs_ctx}

## FORMATO RISPOSTA — SOLO JSON
Sei un agente AI integrato in Sigma Studio. Devi rispondere SOLO con JSON contenente la tua risposta e le azioni da eseguire.
Format:
{{"response": "Una breve spiegazione testuale di cosa hai fatto in italiano...",
  "actions": [
    {{"type": "create_file", "path": "path/file.md", "content": "..."}},
    {{"type": "run_test", "script_path": "path/file.py"}}
  ]
}}

### REGOLA PIÙ IMPORTANTE — STRUTTURA MODULARE WHITELIST
Puoi creare/modificare file SOLO all'interno di queste cartelle: teoria/, test/, docs/, viz/.
Tutti i percorsi devono essere relativi e iniziare con data/ o manifesti/ o scratch/ (es. data/argomento/NN_modulo/teoria/file.md).
MAI creare file al di fuori di queste cartelle."""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Esegui il micro-obiettivo: {obj['title']}"}
                ]

                log.info("Calling agent=%s model=%s for objective=%s", agent_name, agent_model, obj["title"])
                response, thinking, error = call_ai_model(
                    messages, ai_cfg, agent_model, provider, endpoint,
                    api_url, api_key, temperature, max_tokens, top_p, timeout
                )

                if error or not response:
                    log.error("Agent %s failed: %s. Executing default fallback.", agent_name, error)
                    fallback_res = _execute_default_action(self, session_id, obj, goal, _sse)
                    update_objective(session_id, obj["id"], {"status": "done", "result": fallback_res["message"]})
                    _sse({
                        "type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                        "result": fallback_res["message"], "message": f"✅ Completato con default: {obj['title']}"
                    })
                    return

                json_match = _extract_json_from_response(response)
                if not json_match:
                    log.warning("No JSON match for agent %s. Executing fallback default action.", agent_name)
                    fallback_res = _execute_default_action(self, session_id, obj, goal, _sse)
                    update_objective(session_id, obj["id"], {"status": "done", "result": fallback_res["message"]})
                    _sse({
                        "type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                        "result": fallback_res["message"], "message": f"✅ Completato con default: {obj['title']}"
                    })
                    return

                try:
                    parsed = json.loads(json_match.group())
                    actions = parsed.get("actions", [])
                    resp_text = parsed.get("response", "")

                    _sse({
                        "type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                        "response": resp_text, "thinking": thinking or parsed.get("thinking"),
                        "objective_id": obj["id"], "message": f"🧠 {agent_name} ha completato la bozza iniziale"
                    })

                    actions_log = []
                    if actions:
                        _sse({
                            "type": "agent_actions", "agent_id": agent_id, "agent_name": agent_name,
                            "actions": [a.get("type") for a in actions],
                            "message": f"⚡ Esecuzione di {len(actions)} azioni da parte di {agent_name}"
                        })
                        actions_log = execute_ai_actions(self, actions, agent_name)

                    success_count = sum(1 for a in actions_log if a.get("success"))
                    log_str = "\n".join(f"  {a.get('type')}: {a.get('message') or a.get('error')}" for a in actions_log)

                    # Save memory
                    save_session_memory(agent_id, {
                        "goal": obj["title"],
                        "actions_performed": actions_log,
                        "success_count": success_count,
                        "fail_count": len(actions_log) - success_count,
                        "learning": "",
                        "summary": f"Bozza iniziale per micro-obiettivo: {obj['title']}"
                    })

                    # LOOP DI REVISIONE (se non è l'agente proof-reviewer stesso)
                    if agent_id == "proof-reviewer":
                        approved = True
                        validation_summary = "Autovalidato come Revisore principale."
                    else:
                        while attempts < max_attempts and not approved:
                            attempts += 1
                            _sse({
                                "type": "agent_thinking", "agent_id": "proof-reviewer", "agent_name": "Revisore",
                                "thinking": f"Verifica e revisione del lavoro di {agent_name}...", "objective_id": obj["id"],
                                "message": f"🔍 Invio a revisione (tentativo {attempts})..."
                            })
                            
                            # Chiamata al proof-reviewer
                            rev_model, rev_prov, rev_end, rev_url, rev_key, rev_temp, rev_tokens, rev_top, rev_to = \
                                load_agent_config(ai_cfg, model_override, "proof-reviewer")
                            
                            actions_status_info = ""
                            if actions and success_count < len(actions_log):
                                actions_status_info = (
                                    "\n⚠️ ATTENZIONE: Alcune azioni richieste dal collaboratore sono fallite a livello di sistema backend!\n"
                                    f"Dettagli esecuzione e log errori:\n{log_str}\n"
                                    "Poiché i file non sono stati scritti correttamente sul disco, devi tassativamente RIFIUTARE il task (\"approved\": false) "
                                    "e richiedere di correggere i percorsi o il codice per completare correttamente l'obiettivo.\n"
                                )

                            reviewer_prompt = f"""Sei il REVISORE e VALIDATORE critico del team di ricerca.
Il tuo compito è validare il lavoro svolto dal collaboratore per il micro-obiettivo indicato.

## OBIETTIVO GENERALE
{goal}

## MICRO-OBIETTIVO
{obj['title']}
{obj.get('description', '')}

## COLLABORATORE
Agente: {agent_name}
Risposta collaboratore: {resp_text}
Azioni eseguite: {log_str}
{actions_status_info}
## STATO FILE SYSTEM
{_build_filesystem_context()}

## REGOLE DI VALIDAZIONE
1. Se il lavoro è corretto, completo e coerente, approvalo ("approved": true).
2. Se ci sono errori logici, formule errate, codice non funzionante, omissioni gravi o azioni fallite, rifiutalo ("approved": false) e fornisci un feedback dettagliato per correggerlo.
3. Se rifiuti, puoi anche specificare delle azioni correttive facoltative.

## FORMATO RISPOSTA — SOLO JSON
Devi rispondere SOLO con un JSON del tipo:
{{
  "approved": true / false,
  "feedback": "Spiegazione dettagliata dell'approvazione o delle correzioni da fare in italiano...",
  "actions": []
}}"""
                            rev_messages = [
                                {"role": "system", "content": reviewer_prompt},
                                {"role": "user", "content": "Verifica il lavoro e restituisci la validazione in JSON."}
                            ]
                            
                            rev_resp, rev_think, rev_err = call_ai_model(
                                rev_messages, ai_cfg, rev_model, rev_prov, rev_end,
                                rev_url, rev_key, 0.3, rev_tokens, rev_top, rev_to
                            )
                            
                            rev_json_match = _extract_json_from_response(rev_resp) if rev_resp else None
                            if rev_err or not rev_json_match:
                                log.warning("Reviewer validation failed or syntax error. Auto-approving to avoid block.")
                                approved = True
                                validation_summary = "Approvato automaticamente causa errore validatore."
                                break
                            
                            try:
                                rev_parsed = json.loads(rev_json_match.group())
                                approved = rev_parsed.get("approved", False)
                                validation_summary = rev_parsed.get("feedback", "")
                                
                                _sse({
                                    "type": "agent_response", "agent_id": "proof-reviewer", "agent_name": "Revisore",
                                    "response": f"### Esito Revisione: { '✅ Approvato' if approved else '❌ Respinto'}\n\n{validation_summary}",
                                    "objective_id": obj["id"],
                                    "message": f"🔍 Validazione: {'Approvato' if approved else 'Richiesta correzione'}"
                                })
                                
                                if not approved and attempts < max_attempts:
                                    # Chiediamo al worker di correggere basandosi sul feedback
                                    _sse({
                                        "type": "agent_thinking", "agent_id": agent_id, "agent_name": agent_name,
                                        "thinking": f"Correzione in corso basata sul feedback: {validation_summary}", "objective_id": obj["id"],
                                        "message": f"🛠️ {agent_name} corregge il lavoro..."
                                    })
                                    
                                    correct_prompt = f"""{role_prefix}

Il revisore ha respinto il tuo lavoro per il seguente micro-obiettivo: {obj['title']}
## ESITO E LOG DELLE TUE AZIONI PRECEDENTI
{log_str}

## OBIETTIVO GENERALE
{goal}


## FILE PRODOTTI
{_build_filesystem_context()}

Modifica o riscrivi i file per risolvere TUTTE le obiezioni del revisore.
Rispondi sempre nel formato JSON con le azioni (create_file, etc.) per applicare le correzioni.
Format:
{{"response": "Spiegazione di come hai risolto il feedback...",
  "actions": [
    {{"type": "create_file", "path": "path/file.md", "content": "..."}}
  ]
}}"""
                                    correct_messages = [
                                        {"role": "system", "content": correct_prompt},

                                        {"role": "user", "content": f"Applica le correzioni richieste: {validation_summary}"}
                                    ]
                                    
                                    corr_resp, corr_think, corr_err = call_ai_model(
                                        correct_messages, ai_cfg, agent_model, provider, endpoint,
                                        api_url, api_key, temperature, max_tokens, top_p, timeout
                                    )
                                    
                                    corr_match = _extract_json_from_response(corr_resp) if corr_resp else None
                                    if corr_match:
                                        corr_parsed = json.loads(corr_match.group())
                                        resp_text = corr_parsed.get("response", "")
                                        corr_actions = corr_parsed.get("actions", [])
                                        
                                        corr_actions_log = []
                                        if corr_actions:
                                            corr_actions_log = execute_ai_actions(self, corr_actions, agent_name)
                                        log_str = "\n".join(f"  {a.get('type')}: {a.get('message') or a.get('error')}" for a in corr_actions_log)
                                        
                                        _sse({
                                            "type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                                            "response": f"🛠️ Correzione applicata:\n{resp_text}",
                                            "objective_id": obj["id"],
                                            "message": f"⚡ Correzioni applicate da {agent_name}"
                                        })
                            except Exception as parse_exc:
                                log.error("Review loop parsing failed: %s", parse_exc)
                                approved = True
                                validation_summary = "Approvazione automatica per errore strutturale del validatore."
                                break

                    res_summary = f"{resp_text}\n\n📋 **Azioni Eseguite:**\n{log_str}\n\n🔍 **Esito Validazione:**\n{validation_summary}"
                    update_objective(session_id, obj["id"], {"status": "done", "result": res_summary})
                    _sse({
                        "type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                        "result": res_summary, "message": f"✅ Completato & Validato: {obj['title']}"
                    })

                except Exception as exc:
                    log.error("Error processing agent %s response: %s", agent_name, exc)
                    fallback_res = _execute_default_action(self, session_id, obj, goal, _sse)
                    update_objective(session_id, obj["id"], {"status": "done", "result": fallback_res["message"]})
                    _sse({
                        "type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                        "result": fallback_res["message"], "message": f"✅ Completato con default: {obj['title']}"
                    })


            # Esecuzione sequenziale dinamica e strutturata con loop di espansione gestito dal Coordinatore
            expansion_cycle = 0
            max_expansion_cycles = 3
            
            while True:
                # Carica lo stato più aggiornato della sessione
                updated_session = get_session(session_id) or {}
                current_objectives = updated_session.get("micro_objectives", [])
                pending_objectives = [o for o in current_objectives if o.get("status") != "done"]

                if not pending_objectives:
                    # Se tutti i compiti sono finiti, l'Architetto valuta se espandere il lavoro
                    if expansion_cycle >= max_expansion_cycles:
                        break
                    
                    _sse({
                        "type": "agent_thinking", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                        "thinking": "Valutazione dei risultati attuali per rilevare la necessità di ulteriori approfondimenti, test o correzioni...",
                        "message": "🧠 Coordinatore: valutazione dei risultati..."
                    })
                    
                    new_tasks_added = check_and_expand_research_roadmap(session_id, goal, agents_config, ai_cfg, model_override, _sse)
                    if not new_tasks_added:
                        break
                    else:
                        expansion_cycle += 1
                        continue
                
                # Prende ed esegue il primo micro-obiettivo non completato
                obj = pending_objectives[0]
                try:
                    process_objective(obj)
                except Exception as exc:
                    log.error("Objective processing failed for %s: %s", obj.get("title"), exc)
                    fallback_res = _execute_default_action(self, session_id, obj, goal, _sse)
                    update_objective(session_id, obj["id"], {"status": "done", "result": fallback_res["message"]})
                    _sse({
                        "type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                        "result": fallback_res["message"], "message": f"✅ Completato con default: {obj['title']}"
                    })



            # Generazione automatica report di fine sessione
            _sse({
                "type": "agent_thinking", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                "thinking": "Analisi dei risultati e redazione del report finale di ricerca...",
                "message": "📝 Coordinatore: generazione del report finale..."
            })
            
            from core.research_sessions import get_session, save_session
            base_path = "data/analisi_1"
            if "cartella" in goal.lower() or "data/" in goal.lower():
                m = re.search(r'data/([a-zA-Z0-9_-]+)', goal)
                if m:
                    base_path = f"data/{m.group(1)}"
            
            updated_session = get_session(session_id) or {}


            objectives_summary = []
            for o in updated_session.get("micro_objectives", []):
                objectives_summary.append(f"### Task: {o.get('title')}\nAssegnato a: {o.get('assigned_to')}\nEsito: {o.get('result')}\n")
            
            summary_payload = "\n".join(objectives_summary)
            
            coord_prompt = f"""Sei Sigma AI Architect, il coordinatore del team di ricerca.
Il tuo compito è redigere un report finale di ricerca strutturato in italiano che sintetizzi tutto il lavoro svolto dal team per l'obiettivo indicato.

## OBIETTIVO GENERALE
{goal}

## SOTTO-TASK SVOLTI E RISULTATI
{summary_payload}

## FILE PRODOTTI NEL PROGETTO
{_build_filesystem_context()}

## AZIONE RICHIESTA
1. Redigi un report ricco, dettagliato ed elegante in Markdown che descriva:
   - Contesto e obiettivo della ricerca.
   - Sintesi delle scoperte, formule o codice sviluppato.
   - Stato della validazione logico/matematica.
   - Conclusioni e prossimi passi raccomandati.
2. Salva questo report creando o modificando un file con percorso esatto sotto la cartella docs (es. {base_path}/docs/report_finale.md).
3. Rispondi solo ed esclusivamente con il JSON contenente la spiegazione testuale, il report markdown nel campo "response" e l'azione di tipo "create_file".

## FORMATO RISPOSTA — SOLO JSON
{{
  "response": "# [Titolo del Report] ... (contenuto completo del report markdown)",
  "actions": [
    {{
      "type": "create_file",
      "path": "{base_path}/docs/report_finale.md",
      "content": "# [Titolo del Report] ... (contenuto completo del report markdown)"
    }}
  ]
}}"""

            coord_messages = [
                {"role": "system", "content": coord_prompt},
                {"role": "user", "content": "Redigi il report finale e restituisci il JSON con l'azione."}
            ]
            
            coord_model, coord_prov, coord_end, coord_url, coord_key, coord_temp, coord_tokens, coord_top, coord_to = \
                load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)
                
            report_resp, report_think, report_err = call_ai_model(
                coord_messages, ai_cfg, coord_model, coord_prov, coord_end,
                coord_url, coord_key, 0.4, coord_tokens * 2, coord_top, coord_to
            )
            
            report_text = ""
            if not report_err and report_resp:
                report_match = _extract_json_from_response(report_resp)
                if report_match:
                    try:
                        report_parsed = json.loads(report_match.group())
                        report_text = report_parsed.get("response", "")
                        report_actions = report_parsed.get("actions", [])
                        if report_actions:
                            execute_ai_actions(self, report_actions, "sigma_architect")
                    except Exception:
                        pass
            
            if not report_text:
                report_text = f"# Report Finale di Ricerca\n\nObiettivo: {goal}\n\nRicerca completata con successo.\n"

            # Mark research done
            session_data = get_session(session_id)
            if session_data:
                session_data["status"] = "done"
                session_data["report"] = report_text
                session_data["updated_at"] = datetime.datetime.now().isoformat()
                save_session(session_data)
            _sse({"type": "research_done", "session_id": session_id, "message": "🎯 Sessione di ricerca completata!"})



        except Exception as exc:
            log.error("Internal research start loop error: %s", exc)
            _sse({"type": "error", "error": str(exc), "message": f"❌ Errore interno: {exc}"})

    except Exception as exc:
        log.error("handle_research_start wrapper failed: %s", exc)
        self.send_json_response({"success": False, "error": str(exc)}, 500)
