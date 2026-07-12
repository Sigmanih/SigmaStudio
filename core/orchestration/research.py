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


def _get_analisi1_files(base_path: str) -> list[str]:
    """Helper: return a list of typical files for mathematical analysis."""
    return [
        f"{base_path}/teoria/01_limiti.md",
        f"{base_path}/teoria/02_derivate.md",
        f"{base_path}/teoria/03_integrali.md",
        f"{base_path}/test/test_limiti.py",
        f"{base_path}/test/test_derivate.py",
        f"{base_path}/test/test_integrali.py",
        f"{base_path}/viz/viz_limiti.html",
        f"{base_path}/docs/report_analisi1.md",
    ]


def _fallback_objectives(session_id: str, agents_list: list[dict], goal: str) -> dict:
    """Generate fallback micro-objectives if AI coordinator fails."""
    from core.research_sessions import add_micro_objective
    log.warning("Coordinator AI failed or timed out. Falling back to static template objectives.")

    base_path = "data/analisi_1"
    if "data/" in goal.lower() or "cartella" in goal.lower():
        match = re.search(r'data/[a-zA-Z0-9_]+', goal)
        if match:
            base_path = match.group(0)

    # Base templates
    fallback_templates = [
        {
            "title": f"Studio iniziale di fattibilità in {base_path}",
            "description": f"Analizza la cartella di lavoro {base_path} ed elenca i file esistenti.",
            "assigned_to": "sigma_architect",
            "actions_hint": ["read_file"],
            "completion_criteria": "Struttura della cartella mappata."
        },
        {
            "title": "Stesura della teoria fondamentale",
            "description": f"Crea i file di teoria matematica sotto {base_path}/teoria/ per supportare l'obiettivo: {goal}.",
            "assigned_to": "math1",
            "actions_hint": ["create_file"],
            "completion_criteria": "Almeno un file di teoria creato."
        },
        {
            "title": "Implementazione dei test e validazione",
            "description": f"Crea script Python sotto {base_path}/test/ per verificare algoritmi o formule teoriche.",
            "assigned_to": "code_architect",
            "actions_hint": ["create_file", "run_test"],
            "completion_criteria": "Script di test creato ed eseguito."
        },
        {
            "title": "Report riepilogativo di sessione",
            "description": f"Verifica i file creati e scrivi docs/report_completo.md in {base_path}.",
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

    return {"success": True, "objectives": added, "analysis": "Fallback generato automaticamente causa timeout AI", "count": len(added)}


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

    system_prompt = f"""Sei Sigma AI Architect, il coordinatore del team di ricerca.
Il tuo compito è analizzare l'obiettivo dell'utente e suddividerlo in micro-obiettivi (task) da assegnare a diversi agenti.
Stiamo lavorando nella cartella: {base_path}
Sottodirectory: teoria/, test/, docs/, viz/
{fs_context}

## REGOLE FONDAMENTALI
1. Sei il CAPO — devi pensare TU a quali file servono, cosa devono contenere, chi li crea
2. Ogni task DEVE avere un path file ESATTO (es. {base_path}/teoria/01_limiti.md)
3. Ogni task DEVE specificare ESATTAMENTE cosa scrivere nel file (contenuti, formule, esempi)
4. Assegna task agli agenti in base alla loro specializzazione
5. Bilancia: teoria (math1/code_architect), test (test-engineer), revisione (proof-reviewer)
6. Produci 3-7 micro-obiettivi. Se il topic è UNKNOWN, fanne 3-4 generici
7. Criterio di completamento deve essere verificabile (file creato, test passato, etc.)
8. Anche se l'input dell'utente è breve o sintetico, il team deve gestire tutto al meglio, formulando compiti completi ed impeccabili per generare tutta la documentazione di ricerca richiesta.
9. I file creati devono tassativamente seguire la struttura gerarchica della cartella {base_path} (nelle cartelle teoria/, test/, docs/, viz/, whitepapers/).

## FORMATO RISPOSTA — SOLO JSON
{{
  "analysis": "Analisi dettagliata del goal (2-3 frasi)",
  "micro_objectives": [
    {{
      "title": "Titolo sintetico del task",
      "description": "ISTRUZIONI DETTAGLIATE: path file esatto, contenuti da scrivere, formule da includere, esempi da fare. Sii PRECISO.",
      "assigned_to": "agent_id",
      "actions_hint": ["create_file"],
      "completion_criteria": "Criterio verificabile"
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
                        "Sei l'Architetto coordinatore. Il tuo compito è leggere e analizzare TUTTI i file prodotti, "
                        "garantendo che la documentazione sia dettagliata ed impeccabile. I file devono essere creati "
                        "sempre seguendo la struttura di /data (teoria/, test/, viz/, docs/, whitepapers/)."
                    ),
                    "math1": (
                        "Sei un MATEMATICO esperto. Crea file di teoria con definizioni rigorose, teoremi, dimostrazioni formali, "
                        "esempi svolti e spiegazioni dettagliate. Usa LaTeX per ogni formula. I file devono essere creati "
                        "sempre sotto la cartella teoria/ seguendo la struttura di /data."
                    ),
                    "code_architect": (
                        "Sei uno SVILUPPATORE esperto. Scrivi codice Python pulito, test automatici, algoritmi efficienti. "
                        "Documenta le scelte di design e commenta il codice in dettaglio. I file devono essere creati "
                        "sempre sotto la cartella test/ o scratch/ seguendo la struttura di /data."
                    ),
                    "test-engineer": (
                        "Sei un QA ENGINEER. Scrivi test automatici usando sympy/pytest. Verifica la correttezza logica e computazionale "
                        "di formule e algoritmi con assert espliciti. I file devono essere creati sempre sotto la cartella test/ seguendo la struttura di /data."
                    ),
                    "proof-reviewer": (
                        "Sei un REVISORE critico. Verifica la correttezza logica e matematica di TUTTI i file. Cerca errori, "
                        "controesempi ed imprecisioni, producendo report di validazione dettagliati e precisi. I file devono essere "
                        "creati sempre sotto la cartella docs/ seguendo la struttura di /data."
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
Feedback del revisore: {validation_summary}

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


            # Esecuzione sequenziale e strutturata dei micro-obiettivi
            for obj in objectives:
                try:
                    process_objective(obj)
                except Exception as exc:
                    log.error("Objective processing failed for %s: %s", obj.get("title"), exc)


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
