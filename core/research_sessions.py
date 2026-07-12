"""Research Sessions for Sigma Studio — Multi-session research management.
Ogni sessione di ricerca persiste come JSON in research_sessions/ con:
- goal, agenti, pipeline template, micro-obiettivi, actions log, next steps."""

import os
import json
import datetime
import uuid
import threading

RESEARCH_SESSIONS_DIR = "research_sessions"


def _ensure_dir():
    os.makedirs(RESEARCH_SESSIONS_DIR, exist_ok=True)


def _session_path(session_id):
    return os.path.join(RESEARCH_SESSIONS_DIR, f"{session_id}.json")


_save_lock = threading.RLock()


def create_session(name, goal, pipeline_template, agents_config, model_override="", interactive_mode=True) -> dict:
    """Create a new research session."""
    with _save_lock:
        _ensure_dir()
        session_id = f"research_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.datetime.now().isoformat()
        session = {
            "id": session_id,
            "name": name or goal[:80],
            "goal": goal,
            "status": "created",
            "pipeline_template": pipeline_template,
            "model_override": model_override,
            "interactive_mode": interactive_mode,
            "agents": agents_config,
            "micro_objectives": [],
            "actions_log": [],
            "next_steps": [],
            "report": None,
            "created_at": now,
            "updated_at": now,
        }
        with open(_session_path(session_id), "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)
        return session


def get_session(session_id) -> dict:
    """Get a single research session by ID."""
    with _save_lock:
        path = _session_path(session_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def list_sessions() -> list:
    """List all research sessions, newest first."""
    _ensure_dir()
    sessions = []
    for fname in sorted(os.listdir(RESEARCH_SESSIONS_DIR), reverse=True):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(RESEARCH_SESSIONS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "id": data.get("id", fname.replace(".json", "")),
                        "name": data.get("name", ""),
                        "goal": data.get("goal", "")[:120],
                        "status": data.get("status", "unknown"),
                        "pipeline_template": data.get("pipeline_template", ""),
                        "agents_count": len(data.get("agents", [])),
                        "objectives_total": len(data.get("micro_objectives", [])),
                        "objectives_done": sum(1 for o in data.get("micro_objectives", []) if o.get("status") == "done"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                    })
            except Exception:
                pass
    return sessions


def save_session(session: dict):
    """Save/update a research session (thread-safe)."""
    _ensure_dir()
    session["updated_at"] = datetime.datetime.now().isoformat()
    with _save_lock:
        with open(_session_path(session["id"]), "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)


def delete_session(session_id) -> bool:
    """Delete a research session."""
    path = _session_path(session_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


def add_micro_objective(session_id, objective: dict) -> dict:
    """Add a micro-objective to a session."""
    with _save_lock:
        session = get_session(session_id)
        if not session:
            return None
        obj = {
            "id": f"obj_{len(session['micro_objectives']) + 1}",
            "title": objective.get("title", ""),
            "description": objective.get("description", ""),
            "status": "pending",
            "assigned_to": objective.get("assigned_to", ""),
            "actions_hint": objective.get("actions_hint", []),
            "completion_criteria": objective.get("completion_criteria", ""),
            "result": None,
            "iterations": 0,
        }
        session["micro_objectives"].append(obj)
        session["status"] = "active"
        save_session(session)
        return obj


def update_objective(session_id, objective_id, updates: dict):
    """Update a micro-objective status/result."""
    with _save_lock:
        session = get_session(session_id)
        if not session:
            return None
        for obj in session["micro_objectives"]:
            if obj["id"] == objective_id:
                obj.update(updates)
                save_session(session)
                return obj
        return None


def add_actions_log(session_id, actions: list):
    """Append actions to session log."""
    with _save_lock:
        session = get_session(session_id)
        if not session:
            return
        session["actions_log"].extend(actions)
        save_session(session)


def set_next_steps(session_id, steps: list):
    """Set suggested next steps after research completion."""
    with _save_lock:
        session = get_session(session_id)
        if not session:
            return
        session["next_steps"] = steps
        session["status"] = "completed"
        save_session(session)


def check_all_satisfied(session_id) -> tuple:
    """Check if all micro-objectives are satisfied. Returns (all_done, done_count, total)."""
    session = get_session(session_id)
    if not session:
        return False, 0, 0
    objectives = session.get("micro_objectives", [])
    if not objectives:
        return False, 0, 0
    done = sum(1 for o in objectives if o.get("status") == "done")
    return done == len(objectives), done, len(objectives)


def get_failed_objectives(session_id) -> list:
    """Get objectives that failed or are still pending."""
    session = get_session(session_id)
    if not session:
        return []
    return [o for o in session.get("micro_objectives", []) if o.get("status") in ("pending", "failed")]


# ==============================================================================
# API Handlers
# ==============================================================================


def handle_research_create(self):
    """POST /api/research/create — Create a new research session."""
    try:
        req = self.read_json_body()
        name = req.get("name", "").strip()
        goal = req.get("goal", "").strip()
        if not goal:
            return self.send_json_response({"success": False, "error": "Goal richiesto"}, 400)
        pipeline_template = req.get("pipeline_template", "full_analysis")
        agents = req.get("agents", [])
        model_override = req.get("model_override", "")
        interactive_mode = req.get("interactive_mode", True)
        session = create_session(name, goal, pipeline_template, agents, model_override, interactive_mode)
        return self.send_json_response({"success": True, "session": session})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_chat_history(self):
    """GET /api/research/chat_history?id=... — Ricostruisce la cronologia chat di una sessione dagli actions_log e micro_objectives."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        session_id = query.get("id", [None])[0]
        if not session_id:
            return self.send_json_response({"success": False, "error": "id richiesto"}, 400)
        
        session = get_session(session_id)
        if not session:
            return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)
        
        messages = []
        ts = 0
        
        # Piano di lavoro dagli objectives
        objectives = session.get("micro_objectives", [])
        if objectives:
            plan_lines = []
            for o in objectives:
                meta = o.get("assigned_to", "?")
                plan_lines.append(f"📋 **{o.get('title', '')}** → {meta}")
            if plan_lines:
                messages.append({
                    "type": "agent_response", "agent_id": "sigma_architect",
                    "message": "📋 **Piano di lavoro:**\n" + "\n".join(plan_lines),
                    "ts": ts
                })
                ts += 1
        
        # Ricostruisci messaggi dagli actions_log
        actions_log = session.get("actions_log", [])
        # Raggruppa per sessione di esecuzione (separate da obiettivi completati)
        agent_task_map = {}
        for entry in actions_log:
            agent_id = entry.get("agent_id") or entry.get("type", "sistema")
            if agent_id not in agent_task_map:
                agent_task_map[agent_id] = []
            agent_task_map[agent_id].append(entry)
        
        # Messaggi per ogni agente
        for agent_id, entries in agent_task_map.items():
            success = sum(1 for e in entries if e.get("success"))
            fail = sum(1 for e in entries if not e.get("success"))
            if success + fail > 0:
                messages.append({
                    "type": "agent_actions", "agent_id": agent_id,
                    "message": f"⚡ {agent_id}: {success}✅/{fail}❌ azioni",
                    "ts": ts
                })
                ts += 1
        
        # Aggiungi obiettivi completati come messaggi
        for o in objectives:
            if o.get("status") == "done":
                messages.append({
                    "type": "objective_complete", "agent_id": o.get("assigned_to", ""),
                    "message": f"✅ Completato: {o.get('title', '')}",
                    "ts": ts
                })
                ts += 1
        
        # Ordina per timestamp
        messages.sort(key=lambda m: m.get("ts", 0))
        
        return self.send_json_response({"success": True, "messages": messages, "count": len(messages)})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_list(self):
    """GET /api/research/list — List all research sessions."""
    try:
        sessions = list_sessions()
        return self.send_json_response({"success": True, "sessions": sessions})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_status(self):
    """GET /api/research/status — Get detailed status of a session."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        session_id = query.get("id", [None])[0]
        if not session_id:
            return self.send_json_response({"success": False, "error": "id richiesto"}, 400)
        session = get_session(session_id)
        if not session:
            return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)
        all_done, done_count, total = check_all_satisfied(session_id)
        session["all_objectives_done"] = all_done
        session["objectives_progress"] = f"{done_count}/{total}"
        return self.send_json_response({"success": True, "session": session})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_update_agents(self):
    """POST /api/research/update_agents — Update agents in a research session (add/remove/update)."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)
        
        session = get_session(session_id)
        if not session:
            return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)
        
        # Full replace or incremental update
        agents = req.get("agents", None)
        if agents is not None:
            session["agents"] = agents
        else:
            # Incremental update
            action = req.get("action", "")
            agent = req.get("agent", {})
            agent_id = agent.get("agent_id", "") or agent.get("id", "")
            if not agent_id:
                return self.send_json_response({"success": False, "error": "agent_id richiesto"}, 400)
            
            if action == "add":
                # Add agent if not already present
                existing = [a for a in session.get("agents", []) if (a.get("agent_id") or a.get("id")) == agent_id]
                if not existing:
                    session["agents"].append(agent)
            elif action == "remove":
                session["agents"] = [a for a in session.get("agents", []) if (a.get("agent_id") or a.get("id")) != agent_id]
            elif action == "update":
                for a in session.get("agents", []):
                    if (a.get("agent_id") or a.get("id")) == agent_id:
                        a.update({k: v for k, v in agent.items() if k != "agent_id" and k != "id"})
                        break
            else:
                return self.send_json_response({"success": False, "error": f"Azione '{action}' non valida. Usa add/remove/update"}, 400)
        
        save_session(session)
        return self.send_json_response({"success": True, "session": session})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_delete(self):
    """POST /api/research/delete — Delete a research session."""
    try:
        req = self.read_json_body()
        session_id = req.get("id", "").strip()
        if not session_id:
            return self.send_json_response({"success": False, "error": "id richiesto"}, 400)
        ok = delete_session(session_id)
        return self.send_json_response({"success": ok, "error": None if ok else "Sessione non trovata"})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_update_objective(self):
    """POST /api/research/update_objective — Update a session or micro-objective."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)
        
        # If goal is provided without objective_id, update session goal
        goal = req.get("goal")
        objective_id = req.get("objective_id")
        
        if goal and not objective_id:
            session = get_session(session_id)
            if not session:
                return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)
            session["goal"] = goal
            save_session(session)
            return self.send_json_response({"success": True, "session": session})
        
        if not objective_id:
            return self.send_json_response({"success": False, "error": "objective_id richiesto"}, 400)
            
        updates = {k: v for k, v in req.items() if k not in ("session_id", "objective_id")}
        obj = update_objective(session_id, objective_id, updates)
        if not obj:
            return self.send_json_response({"success": False, "error": "Obiettivo non trovato"}, 404)
        return self.send_json_response({"success": True, "objective": obj})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)
