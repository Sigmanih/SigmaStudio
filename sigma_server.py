# ==============================================================================
# SIGMA SERVER | Unified Research Environment
# Backend orchestrator for Sigma Studio v6.2 — modular refactored.
# ==============================================================================

import os
import json
import subprocess
import mimetypes
import signal
import sys
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

# --- Core modules ---
from core.sandbox import is_path_allowed
from core.api_router import register_get_handlers, register_post_handlers, route_get, route_post

# --- Configuration ---
mimetypes.add_type(".js", "application/javascript")
mimetypes.add_type(".css", "text/css")
mimetypes.add_type(".svg", "image/svg+xml")
mimetypes.add_type(".md", "text/markdown")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class SigmaAPIHandler(SimpleHTTPRequestHandler):
    """Lightweight HTTP handler — routes to modular core/ handlers."""

    # Sandbox
    _is_path_allowed = staticmethod(is_path_allowed)

    def do_GET(self):
        route_get(self)

    def do_POST(self):
        route_post(self)

    # --- Helpers ---

    def get_module_meta(self):
        if not os.path.exists('modules_meta.json'):
            return {}
        with open('modules_meta.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_module_meta(self, meta):
        with open('modules_meta.json', 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=4)

    def read_json_body(self):
        len_h = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(len_h).decode('utf-8')) if len_h > 0 else {}

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def serve_static_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            mime, _ = mimetypes.guess_type(file_path)
            self.send_header("Content-Type", mime or "text/plain")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Server Error: {str(e)}")


# --- Import and register all external handlers ---

# 1. Data handlers (modules, topics, knowledge DB, manifesti)
from core.data_handler import (
    handle_api_modules, handle_api_topics, handle_knowledge_db, handle_list_manifesti
)
SigmaAPIHandler.handle_api_modules = handle_api_modules
SigmaAPIHandler.handle_api_topics = handle_api_topics
SigmaAPIHandler.handle_knowledge_db = handle_knowledge_db
SigmaAPIHandler.handle_list_manifesti = handle_list_manifesti

# 2. Module and Topic CRUD
from core.module_handler import (
    handle_create_topic, handle_update_topic, handle_delete_topic,
    handle_create_module, handle_delete_module, handle_update_module
)
SigmaAPIHandler.handle_create_topic = handle_create_topic
SigmaAPIHandler.handle_update_topic = handle_update_topic
SigmaAPIHandler.handle_delete_topic = handle_delete_topic
SigmaAPIHandler.handle_create_module = handle_create_module
SigmaAPIHandler.handle_delete_module = handle_delete_module
SigmaAPIHandler.handle_update_module = handle_update_module

# 3. File CRUD
from core.file_handler import (
    handle_get_file, handle_create_file, handle_delete_file,
    handle_upload_file, handle_run_test
)
SigmaAPIHandler.handle_get_file = handle_get_file
SigmaAPIHandler.handle_create_file = handle_create_file
SigmaAPIHandler.handle_delete_file = handle_delete_file
SigmaAPIHandler.handle_upload_file = handle_upload_file
SigmaAPIHandler.handle_run_test = handle_run_test

# 4. Task handlers
from core.task_handler import handle_api_tasks_get, handle_api_tasks_post, handle_api_tasks_by_agent, handle_api_tasks_assign
SigmaAPIHandler.handle_api_tasks_get = handle_api_tasks_get
SigmaAPIHandler.handle_api_tasks_post = handle_api_tasks_post
SigmaAPIHandler.handle_api_tasks_by_agent = handle_api_tasks_by_agent
SigmaAPIHandler.handle_api_tasks_assign = handle_api_tasks_assign

# 5. Config handlers
from core.config_handler import (
    handle_api_config_get, handle_api_config_post,
    handle_api_ollama_models, handle_api_create_model
)
SigmaAPIHandler.handle_api_config_get = handle_api_config_get
SigmaAPIHandler.handle_api_config_post = handle_api_config_post
SigmaAPIHandler.handle_api_ollama_models = handle_api_ollama_models
SigmaAPIHandler.handle_api_create_model = handle_api_create_model

# 6. Chat handler
from core.chat_handler import handle_chat
SigmaAPIHandler.handle_chat = handle_chat

# 7. Loop handler (task-driven autonomous loop)
from core.loop_handler import handle_chat_loop
SigmaAPIHandler.handle_chat_loop = handle_chat_loop

# 8. Execute handler (continuous feedback loop — Cline-style)
from core.execute_loop import handle_chat_execute
SigmaAPIHandler.handle_chat_execute = handle_chat_execute

# 9. Plan handler (Plan → Act workflow — Cline-style)
from core.plan_handler import handle_chat_plan, handle_chat_execute_plan
SigmaAPIHandler.handle_chat_plan = handle_chat_plan
SigmaAPIHandler.handle_chat_execute_plan = handle_chat_execute_plan

# 10. Sandbox manager (virtual environments, npm, pip, isolated projects)
from core.sandbox_manager import (
    handle_sandbox_create, handle_sandbox_run, handle_sandbox_install,
    handle_sandbox_list, handle_sandbox_destroy, ensure_venv, ensure_npm
)
SigmaAPIHandler.handle_sandbox_create = handle_sandbox_create
SigmaAPIHandler.handle_sandbox_run = handle_sandbox_run
SigmaAPIHandler.handle_sandbox_install = handle_sandbox_install
SigmaAPIHandler.handle_sandbox_list = handle_sandbox_list
SigmaAPIHandler.handle_sandbox_destroy = handle_sandbox_destroy

# 11. Agent registry
from core.agent_registry import (
    handle_agents_list, handle_agents_get, handle_agents_register,
    handle_agents_update, handle_agents_for_topic,
)
SigmaAPIHandler.handle_agents_list = handle_agents_list
SigmaAPIHandler.handle_agents_get = handle_agents_get
SigmaAPIHandler.handle_agents_register = handle_agents_register
SigmaAPIHandler.handle_agents_update = handle_agents_update
SigmaAPIHandler.handle_agents_for_topic = handle_agents_for_topic

# 12. Agent orchestrator (multi-agent collaboration)
from core.agent_orchestrator import handle_chat_orchestrate
SigmaAPIHandler.handle_chat_orchestrate = handle_chat_orchestrate

# 13. Agent templates (scaffolding new agents)
from core.agent_templates import handle_agents_templates, handle_agents_create
SigmaAPIHandler.handle_agents_templates = handle_agents_templates
SigmaAPIHandler.handle_agents_create = handle_agents_create

# 14. Pipeline engine (DAG pipeline execution with feedback loops)
from core.pipeline_engine import handle_pipeline_start, handle_pipeline_status, handle_pipeline_stop
SigmaAPIHandler.handle_pipeline_start = handle_pipeline_start
SigmaAPIHandler.handle_pipeline_status = handle_pipeline_status
SigmaAPIHandler.handle_pipeline_stop = handle_pipeline_stop

# 15. Context Broker (SQLite shared context between agents)
from core.context_broker import handle_context_share, handle_context_get, handle_context_chat_log, handle_chat_message_save
SigmaAPIHandler.handle_context_share = handle_context_share
SigmaAPIHandler.handle_context_get = handle_context_get
SigmaAPIHandler.handle_context_chat_log = handle_context_chat_log
SigmaAPIHandler.handle_chat_message_save = handle_chat_message_save

# 16. Research Sessions (multi-session research with micro-objectives)
from core.research_sessions import (
    handle_research_create, handle_research_list, handle_research_status,
    handle_research_delete, handle_research_update_objective
)
SigmaAPIHandler.handle_research_create = handle_research_create
SigmaAPIHandler.handle_research_list = handle_research_list
SigmaAPIHandler.handle_research_status = handle_research_status
SigmaAPIHandler.handle_research_delete = handle_research_delete
SigmaAPIHandler.handle_research_update_objective = handle_research_update_objective

# 17. Research Decompose + Next Steps (Agent Orchestrator v2)
from core.agent_orchestrator import handle_research_decompose, handle_research_next_steps
SigmaAPIHandler.handle_research_decompose = handle_research_decompose
SigmaAPIHandler.handle_research_next_steps = handle_research_next_steps

# --- Register routing ---
register_get_handlers(SigmaAPIHandler)
register_post_handlers(SigmaAPIHandler)


# ==============================================================================
# STARTUP
# ==============================================================================

def graceful_shutdown(signum, frame):
    print("\n[SIGMA_SERVER] Shutting down gracefully...")
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Rebuild modules_meta.json from filesystem (merge with existing to preserve custom fields)
    existing_meta = {}
    if os.path.exists('modules_meta.json'):
        try:
            with open('modules_meta.json', 'r', encoding='utf-8') as f:
                existing_meta = json.load(f)
        except Exception:
            pass

    meta = {}
    data_dir = 'data'
    if os.path.isdir(data_dir):
        topics = {}
        modules = {}
        existing_topics = existing_meta.get("topics", {})

        # Collect all valid topic folder names from filesystem
        valid_topics = set()
        for topic in sorted(os.listdir(data_dir)):
            tp = os.path.join(data_dir, topic)
            if os.path.isdir(tp):
                valid_topics.add(topic)
                topic_modules = []
                for mod in sorted(os.listdir(tp)):
                    mp = os.path.join(tp, mod)
                    if not os.path.isdir(mp) or not (mod[:2].isdigit()):
                        continue
                    num = mod[:2]
                    mname = mod[3:].replace('_', ' ').title()
                    modules[num] = mname
                    topic_modules.append(num)

                # Merge filesystem data with existing metadata (preserves parent_id, desc, domain, etc.)
                topics[topic] = existing_topics.get(topic, {}).copy()
                topics[topic]["folder"] = tp.replace('\\', '/')
                topics[topic]["modules"] = topic_modules
                # Ensure defaults for any missing keys
                if "name" not in topics[topic]:
                    topics[topic]["name"] = topic
                if "description" not in topics[topic]:
                    topics[topic]["description"] = ""

        # Remove stale parent_id references (topics that no longer exist on disk)
        for topic_id, topic_data in topics.items():
            pid = topic_data.get("parent_id")
            if pid and pid not in valid_topics:
                topics[topic_id]["parent_id"] = None
                topics[topic_id].pop("parent_id", None)

        meta = {"topics": topics, "modules": modules}
    with open('modules_meta.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=4)

    # Ensure virtual environment exists (for AI terminal access)
    print("[SIGMA_SERVER] Checking virtual environment...")
    venv_ok, venv_msg = ensure_venv()
    print(f"[SIGMA_SERVER] {venv_msg}")
    
    # Auto-build frontend assets
    npm_path = shutil.which('npm')
    if npm_path:
        print("[SIGMA_SERVER] Building frontend assets...")
        res = subprocess.run([npm_path, 'run', 'build'], cwd='sigma_studio', capture_output=True, text=True)
        if res.returncode == 0:
            print("[SIGMA_SERVER] Frontend built successfully.")
        else:
            print(f"[SIGMA_SERVER] Frontend build failed:\n{res.stderr}")
    else:
        print("[SIGMA_SERVER] WARNING: npm not found, skipping frontend build.")

    print("[SIGMA_SERVER] Listening on http://localhost:8000")
    try:
        ThreadedHTTPServer(('', 8000), SigmaAPIHandler).serve_forever()
    except KeyboardInterrupt:
        graceful_shutdown(None, None)