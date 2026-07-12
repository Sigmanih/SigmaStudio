"""API routing dispatch for Sigma Studio server."""
import os
from urllib.parse import urlparse


def register_get_handlers(handler_class):
    """Register GET API handlers on the handler class."""
    handler_class._GET_HANDLERS = {
        '/api/modules': 'handle_api_modules',
        '/api/topics': 'handle_api_topics',
        '/api/tasks': 'handle_api_tasks_get',
        '/api/get_file': 'handle_get_file',
        '/api/list_manifesti': 'handle_list_manifesti',
        '/api/knowledge_db': 'handle_knowledge_db',
        '/api/config': 'handle_api_config_get',
        '/api/ollama_models': 'handle_api_ollama_models',
        '/api/sandbox/list': 'handle_sandbox_list',
        '/api/agents': 'handle_agents_list',
        '/api/agents/get': 'handle_agents_get',
        '/api/agents/for_topic': 'handle_agents_for_topic',
        '/api/tasks/by_agent': 'handle_api_tasks_by_agent',
        '/api/agents/templates': 'handle_agents_templates',
        '/api/agents/colors': 'handle_agents_colors',
        '/api/chat/pipeline/status': 'handle_pipeline_status',
        '/api/context/get': 'handle_context_get',
        '/api/context/chat_log': 'handle_context_chat_log',
        '/api/research/list': 'handle_research_list',
        '/api/research/status': 'handle_research_status',
        '/api/research/chat_history': 'handle_research_chat_history',
    }


def register_post_handlers(handler_class):
    """Register POST API handlers on the handler class."""
    handler_class._POST_HANDLERS = {
        '/api/run_test': 'handle_run_test',
        '/api/create_file': 'handle_create_file',
        '/api/delete_file': 'handle_delete_file',
        '/api/tasks': 'handle_api_tasks_post',
        '/api/create_module': 'handle_create_module',
        '/api/delete_module': 'handle_delete_module',
        '/api/upload_file': 'handle_upload_file',
        '/api/update_module': 'handle_update_module',
        '/api/create_topic': 'handle_create_topic',
        '/api/update_topic': 'handle_update_topic',
        '/api/delete_topic': 'handle_delete_topic',
        '/api/config': 'handle_api_config_post',
        '/api/chat': 'handle_chat',
        '/api/chat/loop': 'handle_chat_loop',
        '/api/chat/execute': 'handle_chat_execute',
        '/api/chat/plan': 'handle_chat_plan',
        '/api/chat/execute_plan': 'handle_chat_execute_plan',
        '/api/chat/orchestrate': 'handle_chat_orchestrate',
        '/api/create_model': 'handle_api_create_model',
        '/api/ollama_models': 'handle_api_ollama_models',
        '/api/sandbox/create': 'handle_sandbox_create',
        '/api/sandbox/run': 'handle_sandbox_run',
        '/api/sandbox/install': 'handle_sandbox_install',
        '/api/sandbox/destroy': 'handle_sandbox_destroy',
        '/api/agents/register': 'handle_agents_register',
        '/api/agents/update': 'handle_agents_update',
        '/api/tasks/assign': 'handle_api_tasks_assign',
        '/api/agents/create': 'handle_agents_create',
        '/api/chat/pipeline/start': 'handle_pipeline_start',
        '/api/chat/pipeline/stop': 'handle_pipeline_stop',
        '/api/context/share': 'handle_context_share',
        '/api/context/chat_message': 'handle_chat_message_save',
        '/api/research/create': 'handle_research_create',
        '/api/research/delete': 'handle_research_delete',
        '/api/research/update_objective': 'handle_research_update_objective',
        '/api/research/update_agents': 'handle_research_update_agents',
        '/api/research/decompose': 'handle_research_decompose',
        '/api/research/next_steps': 'handle_research_next_steps',
        '/api/research/start': 'handle_research_start',
    }


def route_get(self):
    """Route GET request to appropriate handler."""
    parsed = urlparse(self.path)
    rel_path = parsed.path.lstrip('/')
    
    if parsed.path.startswith('/api/'):
        handler_name = self._GET_HANDLERS.get(parsed.path)
        if handler_name:
            handler = getattr(self, handler_name)
            return handler()
        return self.send_error(404, "API not found")
    
    return _serve_static(self, rel_path)


def route_post(self):
    """Route POST request to appropriate handler."""
    parsed = urlparse(self.path)
    handler_name = self._POST_HANDLERS.get(parsed.path)
    if handler_name:
        handler = getattr(self, handler_name)
        return handler()
    self.send_error(404, "Endpoint not found")


def _serve_static(self, rel_path):
    """Serve static files from dist/ directory."""
    import os
    dist_path = os.path.join('sigma_studio', 'dist')
    fs_rel_path = rel_path.replace('/', os.sep)
    file_path = os.path.join(dist_path, fs_rel_path) if fs_rel_path else os.path.join(dist_path, 'index.html')
    
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        if os.path.exists(fs_rel_path) and not os.path.isdir(fs_rel_path):
            file_path = fs_rel_path
        else:
            is_file_request = "." in os.path.basename(fs_rel_path)
            file_path = os.path.join(dist_path, 'index.html') if not is_file_request or not fs_rel_path else None
            if not file_path:
                return self.send_error(404, f"File {rel_path} non trovato")
    
    self.serve_static_file(file_path)