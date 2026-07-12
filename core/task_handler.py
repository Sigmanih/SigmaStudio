"""Task handlers for Sigma Studio."""
import os
import json
import datetime
import re
from core.agent_registry import get_agent, get_specialized_agent


# Sezioni permesse dentro un modulo (WHITELIST — tutto il resto è vietato)
_ALLOWED_MODULE_SECTIONS = frozenset({
    'teoria', 'test', 'viz', 'docs', 'whitepapers',
})


def _validate_module_path(path):
    """Validate that a file path follows the standard modular structure.
    
    Returns (is_valid, error_reason).
    
    REGOLA WHITELIST: dentro un modulo (data/<topic>/<NN_modulo>/...)
    sono permesse SOLO le 5 sezioni: teoria/, test/, viz/, docs/, whitepapers/
    Qualsiasi altra cartella è automaticamente vietata.
    
    Standard: data/<topic>/<NN_modulo>/<sezione>/<file>
    """
    if not path or not isinstance(path, str):
        return False, "Path vuoto o non valido"
    
    # Normalizza separatori
    normal = path.replace('\\', '/').rstrip('/')
    
    # Path fuori data/ sono permessi (manifesti, scratch, sigma_studio/src)
    if not normal.startswith('data/'):
        return True, ""
    
    parts = normal.split('/')
    
    # data/argomento/file — solo 3 parti = file in root topic
    if len(parts) == 3:
        return False, f"File in root del topic non permesso: {path}. Deve stare dentro un modulo: data/<topic>/<NN_modulo>/<sezione>/<file>"
    
    # data/argomento/NN_nome/ — 4+ parti, controlla modulo
    if len(parts) >= 4:
        module_part = parts[2]
        
        # Controlla se è un path che va direttamente in una sezione senza modulo
        # data/topic/teoria/file.md
        if module_part in _ALLOWED_MODULE_SECTIONS:
            return False, f"Sezione '{module_part}' fuori dal modulo: {path}. Usa data/<topic>/<NN_modulo>/{module_part}/<file>"
        
        # Se siamo dentro un modulo (la parte 2 inizia con numeri e ha _)
        if parts[2][:2].isdigit() and '_' in parts[2]:
            # La parte 3 deve essere una sezione valita della whitelist
            section = parts[3] if len(parts) > 3 else ""
            if not section:
                return False, f"File direttamente nella root del modulo non permesso: {path}. Deve stare in una delle 5 sezioni: teoria/, test/, viz/, docs/, whitepapers/"
            if section not in _ALLOWED_MODULE_SECTIONS:
                return False, f"Cartella '{section}' non permessa dentro il modulo: {path}. Sono permesse SOLO: teoria/, test/, viz/, docs/, whitepapers/"
    
    return True, ""


def _normalize_action_path(path, auto_module=False):
    """Normalize file paths for actions. If a simple filename (no directory) is given,
    prepend 'data/scratch/' so the AI doesn't need to know the full structure.
    
    If auto_module is True and the path goes directly into a topic's sezione/
    without a module folder, automatically wrap it in a default module (01_base/).
    """
    if not path:
        return path
    # If it's just a filename (no slashes, no backslashes), put it in data/scratch/
    if '/' not in path and '\\' not in path:
        return f"data/scratch/{path}"
    # If it starts with a known directory, leave as-is
    if path.startswith(('data/', 'manifesti/', 'sigma_studio/', 'core/', 'scratch/')):
        return path
    # Otherwise, assume it's relative to data/
    return f"data/{path}"


def _sync_module_meta(topic_id, topic_folder, mod_num, mod_name):
    """Update modules_meta.json with a new module entry."""
    try:
        meta = {}
        if os.path.exists('modules_meta.json'):
            with open('modules_meta.json', 'r', encoding='utf-8') as f:
                meta = json.load(f)
        meta.setdefault('modules', {})
        meta.setdefault('topics', {})
        meta['modules'][mod_num] = mod_name
        # Ensure topic exists
        if topic_id not in meta['topics']:
            meta['topics'][topic_id] = {
                "name": topic_id.replace('_', ' ').title(),
                "description": "",
                "domain": "generale",
                "manifesto_ref": "",
                "parent_id": None,
                "folder": topic_folder.replace('\\', '/'),
                "modules": []
            }
        if mod_num not in meta['topics'][topic_id].get('modules', []):
            meta['topics'][topic_id].setdefault('modules', []).append(mod_num)
        with open('modules_meta.json', 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=4)
    except Exception as e:
        print(f"[SIGMA_CHAT_DEBUG] _sync_module_meta error: {e}", flush=True)


def _ensure_module_structure(path):
    """Auto-wrap file paths into module structure if they're flat inside a topic.
    
    data/topic/teoria/file.md -> data/topic/01_base/teoria/file.md
    data/topic/docs/file.md -> data/topic/01_base/docs/file.md
    """
    if not path or not path.startswith('data/'):
        return path
    
    parts = path.replace('\\', '/').split('/')
    # Expected: data / topic / sezione / file
    # Need:     data / topic / NN_modulo / sezione / file
    if len(parts) == 4 and parts[2] in ('teoria', 'test', 'viz', 'docs', 'whitepapers'):
        # Flat structure: data/topic/sezione/file
        topic_folder = f"data/{parts[1]}"
        default_mod = _get_or_create_default_module(topic_folder)
        new_path = f"{default_mod.replace('\\', '/')}/{parts[2]}/{parts[3]}"
        return new_path
    
    return path


def _auto_register_file_module(path):
    """When a file is created inside a module, ensure that module is registered in modules_meta.json."""
    try:
        if not path or not path.startswith('data/'):
            return
        parts = path.replace('\\', '/').split('/')
        # Need: data/topic/NN_modulename/sezione/file
        if len(parts) >= 5 and parts[2][:2].isdigit() and '_' in parts[2]:
            topic_id = parts[1]
            mod_folder_name = parts[2]  # e.g., "01_fondamenti"
            mod_num = mod_folder_name[:2]
            mod_name = mod_folder_name[3:].replace('_', ' ').title()
            topic_folder = f"data/{topic_id}"
            
            meta = {}
            if os.path.exists('modules_meta.json'):
                with open('modules_meta.json', 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            
            meta.setdefault('modules', {})
            meta.setdefault('topics', {})
            
            # Register the module if not already there
            if mod_num not in meta.get('modules', {}):
                meta['modules'][mod_num] = mod_name
            
            # Ensure topic exists and has this module
            if topic_id not in meta.get('topics', {}):
                meta['topics'][topic_id] = {
                    "name": topic_id.replace('_', ' ').title(),
                    "description": "",
                    "domain": "generale",
                    "manifesto_ref": "",
                    "parent_id": None,
                    "folder": topic_folder.replace('\\', '/'),
                    "modules": []
                }
            
            if mod_num not in meta['topics'][topic_id].get('modules', []):
                meta['topics'][topic_id].setdefault('modules', []).append(mod_num)
            
            with open('modules_meta.json', 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=4)
    except Exception as e:
        print(f"[SIGMA_CHAT_DEBUG] _auto_register_file_module error: {e}", flush=True)


def _get_or_create_default_module(topic_folder):
    """Ensure a topic has at least one module. If not, create '01_base' as default.
    Returns the module folder path."""
    import json as _json
    # Check if any module folders already exist
    if os.path.isdir(topic_folder):
        for entry in sorted(os.listdir(topic_folder)):
            full = os.path.join(topic_folder, entry)
            if os.path.isdir(full) and entry[:2].isdigit() and '_' in entry:
                return full  # already has a module
    
    # Create default module
    mod_num = '01'
    mod_name = 'base'
    module_path = os.path.join(topic_folder, f"{mod_num}_{mod_name}")
    os.makedirs(module_path, exist_ok=True)
    for sub in ['teoria', 'test', 'viz', 'docs', 'whitepapers']:
        os.makedirs(os.path.join(module_path, sub), exist_ok=True)
    
    # Update modules_meta.json
    if os.path.exists('modules_meta.json'):
        try:
            with open('modules_meta.json', 'r', encoding='utf-8') as f:
                meta = _json.load(f)
            meta.setdefault('modules', {})
            meta['modules'][mod_num] = mod_name.replace('_', ' ').title()
            # Find the topic and add this module
            for topic_id, topic_data in meta.get('topics', {}).items():
                topic_f = topic_data.get('folder', '').replace('\\', '/')
                if topic_f == topic_folder.replace('\\', '/'):
                    if mod_num not in topic_data.get('modules', []):
                        topic_data.setdefault('modules', []).append(mod_num)
                    break
            with open('modules_meta.json', 'w', encoding='utf-8') as f:
                _json.dump(meta, f, indent=4)
            print(f"[SIGMA_CHAT_DEBUG] Created default module: {module_path}", flush=True)
        except Exception as e:
            print(f"[SIGMA_CHAT_DEBUG] Failed to update modules_meta.json: {e}", flush=True)
    
    return module_path


def handle_api_tasks_get(self):
    tasks = []
    if os.path.exists('tasks.json'):
        try:
            with open('tasks.json', 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content.startswith('{') or content.startswith('['):
                tasks = json.loads(content)
            else:
                # Malformed JSON: reset file
                tasks = []
                with open('tasks.json', 'w', encoding='utf-8') as f:
                    json.dump([], f)
        except (json.JSONDecodeError, Exception):
            tasks = []
            try:
                with open('tasks.json', 'w', encoding='utf-8') as f:
                    json.dump([], f)
            except Exception:
                pass
    self.send_json_response(tasks)


def handle_api_tasks_post(self):
    try:
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(self.read_json_body(), f, indent=4)
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_api_tasks_by_agent(self):
    """GET /api/tasks/by_agent — Get tasks assigned to a specific agent.
    Query param: agent_id (e.g., ?agent_id=math1)
    """
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        agent_id = query.get("agent_id", [None])[0]
        tasks = []
        if os.path.exists('tasks.json'):
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks = json.load(f)
        if agent_id:
            tasks = [t for t in tasks if t.get("assigned_to") == agent_id]
        self.send_json_response({"tasks": tasks})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_api_tasks_assign(self):
    """POST /api/tasks/assign — Assign a task to an agent.
    Body: { "task_id": "id_or_titolo", "agent_id": "math1" }
    """
    try:
        req = self.read_json_body()
        task_id = req.get("task_id", "")
        agent_id = req.get("agent_id", "")
        if not task_id or not agent_id:
            return self.send_json_response({"error": "task_id e agent_id richiesti"}, 400)
        
        # Verify agent exists
        from core.agent_registry import get_agent
        agent = get_agent(agent_id)
        if not agent:
            return self.send_json_response({"error": f"Agente '{agent_id}' non trovato"}, 404)
        
        tasks = []
        if os.path.exists('tasks.json'):
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks = json.load(f)
        
        found = False
        for t in tasks:
            if t.get("id") == task_id or t.get("titolo") == task_id:
                t["assigned_to"] = agent_id
                t.setdefault("notifiche", []).append({
                    "da": "system",
                    "messaggio": f"Task assegnato all'agente {agent.get('name', agent_id)}",
                    "timestamp": datetime.datetime.now().isoformat()
                })
                found = True
                break
        
        if not found:
            return self.send_json_response({"error": f"Task '{task_id}' non trovato"}, 404)
        
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=4)
        
        return self.send_json_response({"success": True, "message": f"Task assegnato a {agent.get('name', agent_id)}"})
    except Exception as e:
        return self.send_json_response({"error": str(e)}, 500)


def _add_action_notifications(log, bot_name):
    """Auto-add notifications to the active task for every successful action.
    
    Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
    Ogni create_file, edit_file, delete_file, rename_file, create_module, run_test
    genera automaticamente una notifica nel task attivo in tasks.json.
    """
    if not log:
        return
    try:
        tasks = []
        if os.path.exists('tasks.json'):
            try:
                with open('tasks.json', 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content.startswith('[') or content.startswith('{'):
                    tasks = json.loads(content)
                    if isinstance(tasks, dict):
                        tasks = [tasks]
                else:
                    tasks = []
            except (json.JSONDecodeError, Exception):
                tasks = []
                # Reset corrupted file
                try:
                    with open('tasks.json', 'w', encoding='utf-8') as f:
                        json.dump([], f)
                except Exception:
                    pass
        
        # Find active task (first one with status "in_corso"), or create default
        active_task = None
        for t in tasks:
            if t.get("status") == "in_corso":
                active_task = t
                break
        
        if not active_task:
            # Create a default active task
            active_task = {
                "titolo": f"Operazioni AI - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}",
                "descrizione": "Operazioni automatiche eseguite dall'agente AI",
                "status": "in_corso",
                "priorita": "media",
                "moduli": [],
                "id": int(datetime.datetime.now().timestamp() * 1000),
                "notifiche": []
            }
            tasks.append(active_task)
        
        # Add notification for each successful action
        for entry in log:
            if entry.get("success"):
                action_type = entry.get("type", "")
                path = entry.get("path", "") or entry.get("old_path", "") or ""
                msg = entry.get("message", "")
                
                if action_type in ("create_file", "edit_file", "delete_file", "rename_file", "create_module", "run_test"):
                    if "notifiche" not in active_task:
                        active_task["notifiche"] = []
                    active_task["notifiche"].append({
                        "da": bot_name,
                        "messaggio": f"[{action_type}] {msg}",
                        "timestamp": datetime.datetime.now().isoformat()
                    })
        
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=4)
    except Exception as e:
        print(f"[SIGMA_CHAT_DEBUG] _add_action_notifications error: {e}", flush=True)


def execute_ai_actions(self, actions, bot_name):
    """Execute AI-generated actions (create_file, update_task, run_test).
    
    Ogni azione eseguita con successo genera automaticamente una notifica 
    nel task attivo di tasks.json, seguendo il principio:
    "Una notifica non lasciata è un'azione mai avvenuta."
    """
    import subprocess
    import shutil
    log = []
    if not actions:
        return log

    for action in actions:
        action_type = action.get("type", "")
        try:
            if action_type == "create_file":
                path = _normalize_action_path(action.get("path", ""))
                content = action.get("content", "")
                
                # 🛑 VALIDAZIONE STRUTTURA MODULARE
                valid, error_reason = _validate_module_path(path)
                if not valid:
                    log.append({"type": "create_file", "success": False, "path": path, "error": error_reason})
                    continue
                
                # Auto-create default module if file is in a topic without module structure
                # e.g., data/topic/teoria/file.md -> data/topic/01_base/teoria/file.md
                path = _ensure_module_structure(path)
                if path and self._is_path_allowed(path) and '..' not in path:
                    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    # Auto-register module in modules_meta.json if needed
                    _auto_register_file_module(path)
                    log.append({"type": "create_file", "success": True, "path": path, "message": f"File creato: {path}"})
                else:
                    log.append({"type": "create_file", "success": False, "path": path, "error": f"Path non consentito: {path}"})

            elif action_type == "create_module":
                topic_name = action.get("topic", "").strip()
                mod_num = action.get("number", "").strip().zfill(2) or "01"
                mod_name = action.get("name", "").strip() or "nuovo"
                mod_desc = action.get("description", "")
                if not topic_name:
                    log.append({"type": "create_module", "success": False, "error": "Topic mancante"})
                    continue
                # Find or create topic folder with standard subdirectories
                topic_id = topic_name.lower().replace(' ', '_').replace("'", "")
                topic_folder = f"data/{topic_id}"
                if not os.path.isdir(topic_folder):
                    os.makedirs(topic_folder, exist_ok=True)
                # Ensure module doesn't already exist
                mod_name_slug = mod_name.replace(' ', '_').lower()
                module_folder = os.path.join(topic_folder, f"{mod_num}_{mod_name_slug}")
                if os.path.exists(module_folder):
                    log.append({"type": "create_module", "success": True, "path": module_folder, "message": f"Modulo già esistente: {module_folder}"})
                else:
                    os.makedirs(module_folder, exist_ok=True)
                    for sub in ['teoria', 'test', 'viz', 'docs', 'whitepapers']:
                        os.makedirs(os.path.join(module_folder, sub), exist_ok=True)
                    # Update modules_meta.json
                    _sync_module_meta(topic_id, topic_folder, mod_num, mod_name)
                    log.append({"type": "create_module", "success": True, "path": module_folder, "message": f"Modulo creato: {module_folder}"})

            elif action_type == "edit_file":
                path = _normalize_action_path(action.get("path", ""))
                content = action.get("content", "")
                search = action.get("search", "")
                if path and self._is_path_allowed(path) and os.path.exists(path):
                    if search:
                        with open(path, 'r', encoding='utf-8') as f:
                            old_content = f.read()
                        if search in old_content:
                            new_content = old_content.replace(search, content, 1)
                            with open(path, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            log.append({"type": "edit_file", "success": True, "path": path, "message": f"File modificato: {path}"})
                        else:
                            log.append({"type": "edit_file", "success": False, "path": path, "error": f"Testo da cercare non trovato in {path}"})
                    else:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        log.append({"type": "edit_file", "success": True, "path": path, "message": f"File sovrascritto: {path}"})
                else:
                    log.append({"type": "edit_file", "success": False, "path": path, "error": f"Path non trovato o non consentito: {path}"})

            elif action_type == "rename_file":
                old_path = _normalize_action_path(action.get("old_path", ""))
                new_path = _normalize_action_path(action.get("new_path", ""))
                if old_path and new_path and self._is_path_allowed(old_path) and self._is_path_allowed(new_path) and '..' not in old_path and '..' not in new_path:
                    if os.path.exists(old_path):
                        os.makedirs(os.path.dirname(os.path.abspath(new_path)) or '.', exist_ok=True)
                        os.rename(old_path, new_path)
                        log.append({"type": "rename_file", "success": True, "old_path": old_path, "new_path": new_path, "message": f"File rinominato: {old_path} → {new_path}"})
                    else:
                        log.append({"type": "rename_file", "success": False, "error": f"File non trovato: {old_path}"})
                else:
                    log.append({"type": "rename_file", "success": False, "error": f"Path non consentito: old={old_path}, new={new_path}"})

            elif action_type == "delete_file":
                path = _normalize_action_path(action.get("path", ""))
                if path and self._is_path_allowed(path) and os.path.exists(path):
                    os.remove(path)
                    log.append({"type": "delete_file", "success": True, "path": path, "message": f"File eliminato: {path}"})
                else:
                    log.append({"type": "delete_file", "success": False, "path": path, "error": f"Path non trovato o non consentito: {path}"})

            elif action_type == "update_task":
                titolo = action.get("titolo", "")
                new_status = action.get("status", "")
                notifica = action.get("notifica", f"[{bot_name}] {action.get('notifica', '')}")
                if titolo:
                    tasks = []
                    if os.path.exists('tasks.json'):
                        with open('tasks.json', 'r', encoding='utf-8') as f:
                            tasks = json.load(f)
                    found = False
                    for t in tasks:
                        if t.get("titolo") == titolo:
                            if new_status:
                                t["status"] = new_status
                            if notifica:
                                if "notifiche" not in t:
                                    t["notifiche"] = []
                                t["notifiche"].append({"da": bot_name, "messaggio": notifica, "timestamp": datetime.datetime.now().isoformat()})
                            found = True
                            break
                    if not found:
                        new_task = {
                            "titolo": titolo, "descrizione": action.get("descrizione", ""),
                            "status": new_status or "in_corso", "priorita": action.get("priorita", "media"),
                            "moduli": action.get("moduli", []), "id": int(datetime.datetime.now().timestamp() * 1000),
                            "notifiche": []
                        }
                        if notifica:
                            new_task["notifiche"].append({"da": bot_name, "messaggio": notifica, "timestamp": datetime.datetime.now().isoformat()})
                        tasks.append(new_task)
                    with open('tasks.json', 'w', encoding='utf-8') as f:
                        json.dump(tasks, f, indent=4)
                    log.append({"type": "update_task", "success": True, "titolo": titolo, "message": f"Task aggiornato: {titolo}"})
                else:
                    log.append({"type": "update_task", "success": False, "error": "Titolo task mancante"})

            elif action_type == "run_test":
                path = action.get("path", "")
                if path and self._is_path_allowed(path) and os.path.exists(path):
                    cmd = ["python", "-u", path] if path.endswith('.py') else ["node", path]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
                    log.append({"type": "run_test", "success": res.returncode == 0, "path": path,
                                "stdout": res.stdout[:2000], "stderr": res.stderr[:1000],
                                "exit_code": res.returncode, "message": f"Test eseguito: exit={res.returncode}"})
                else:
                    log.append({"type": "run_test", "success": False, "error": f"Path non trovato: {path}"})

            elif action_type == "read_file":
                path = _normalize_action_path(action.get("path", ""))
                if path and self._is_path_allowed(path) and '..' not in path and os.path.exists(path):
                    try:
                        fsize = os.path.getsize(path)
                        if fsize > 100000:
                            log.append({"type": "read_file", "success": False, "path": path, "error": f"File troppo grande ({fsize} bytes). Massimo 100KB."})
                            continue
                        with open(path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        preview = content[:8000]
                        if len(content) > 8000:
                            preview += f"\n\n... [troncato: mostra {len(preview)}/{len(content)} caratteri]"
                        log.append({"type": "read_file", "success": True, "path": path, "message": f"File letto: {path} ({len(content)} caratteri)", "content": preview})
                    except Exception as e:
                        log.append({"type": "read_file", "success": False, "path": path, "error": f"Errore lettura: {str(e)}"})
                else:
                    log.append({"type": "read_file", "success": False, "path": path, "error": f"Path non trovato o non consentito: {path}"})

            elif action_type == "send_notification":
                destinatario = action.get("destinatario", "dashboard")
                messaggio = action.get("messaggio", "")
                log.append({"type": "send_notification", "success": True, "destinatario": destinatario, "message": messaggio})

            elif action_type == "run_terminal":
                cmd = action.get("cmd", "").strip()
                if not cmd:
                    log.append({
                        "type": "run_terminal", "success": False,
                        "error": "Comando vuoto: manca il parametro 'cmd'! Ogni azione run_terminal DEVE avere 'cmd'. Esempio corretto: {\"type\": \"run_terminal\", \"cmd\": \"dir data\\ /b\"}",
                        "action_raw": action
                    })
                    continue
                # Allowed directories for terminal commands (safety)
                allowed_prefixes = ('sigma_studio', 'data', 'core', 'scratch', 'manifesti', 'viz')
                working_dir = action.get("cwd", "")
                if working_dir and not any(working_dir.startswith(p) for p in allowed_prefixes):
                    working_dir = ""
                cwd = os.path.join(os.getcwd(), working_dir) if working_dir else os.getcwd()
                if not os.path.isdir(cwd):
                    cwd = os.getcwd()
                try:
                    import subprocess
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                        timeout=120, cwd=cwd,
                                        encoding='utf-8', errors='replace')
                    stdout = res.stdout[:3000]
                    stderr = res.stderr[:1000]
                    log.append({
                        "type": "run_terminal", "success": res.returncode == 0,
                        "cmd": cmd[:200], "cwd": cwd,
                        "stdout": stdout, "stderr": stderr,
                        "exit_code": res.returncode,
                        "message": f"Comando eseguito: exit={res.returncode}" + (f" stdout: {stdout[:100]}" if stdout else "") + (f" stderr: {stderr[:100]}" if stderr else "")
                    })
                except subprocess.TimeoutExpired:
                    log.append({"type": "run_terminal", "success": False, "cmd": cmd[:200], "error": "Timeout (120s)"})
                except Exception as e:
                    log.append({"type": "run_terminal", "success": False, "cmd": cmd[:200], "error": str(e)})

        except Exception as e:
            log.append({"type": action_type, "success": False, "error": str(e)})

    # Auto-generate notifications for all successful actions
    # Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
    _add_action_notifications(log, bot_name)

    return log
