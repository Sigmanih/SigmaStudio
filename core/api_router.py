"""API routing dispatch for Sigma Studio server."""
import os
from urllib.parse import urlparse


def register_get_handlers(handler_class):
    """Register GET API handlers on the handler class."""
    core_routes = {
        '/api/modules': 'handle_api_modules',
        '/api/topics': 'handle_api_topics',
        '/api/tasks': 'handle_api_tasks_get',
        '/api/get_file': 'handle_get_file',
        '/api/list_manifesti': 'handle_list_manifesti',
        '/api/manifesti': 'handle_list_manifesti',
        '/api/knowledge_db': 'handle_knowledge_db',
        '/api/config': 'handle_api_config_get',
        '/api/config/hf_token': 'handle_hf_token_get',
        '/api/ollama_models': 'handle_api_ollama_models',
        '/api/tags': 'handle_ollama_tags',
        '/api/version': 'handle_ollama_version',
        '/api/ps': 'handle_ollama_ps',
        '/v1/models': 'handle_v1_models',
        '/api/v1/models': 'handle_v1_models',
        '/api/engine/server_info': 'handle_engine_server_info',
        '/api/tts/engines': 'handle_tts_engines_fallback',
        '/api/engine/status': 'handle_engine_status',
        '/api/engine/profile': 'handle_engine_profile',
        '/api/engine/overrides': 'handle_engine_overrides_get',
        '/api/engine/runtime_check': 'handle_engine_runtime_check',
        '/api/engine/models': 'handle_engine_models',




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
        # Training & Hardware Lab
        '/api/training/datasets': 'handle_training_list_datasets',
        '/api/training/datasets/search': 'handle_training_dataset_search',
        '/api/training/datasets/featured': 'handle_training_featured_datasets',
        '/api/training/jobs': 'handle_training_list_jobs',
        '/api/training/job/status': 'handle_training_job_status',
        '/api/training/job/logs': 'handle_training_job_logs',
        '/api/training/job/metrics': 'handle_training_job_metrics',
        '/api/training/job/lineage': 'handle_training_job_lineage',
        '/api/training/export/quant_levels': 'handle_training_quant_levels',
        '/api/training/identity': 'handle_training_identity',
        '/api/training/autopilot/status': 'handle_training_autopilot_status',
        '/api/training/models/local': 'handle_training_models_local',
        '/api/training/models/search': 'handle_training_models_search',
        '/api/training/models/pull_status': 'handle_training_models_pull_status',
        '/api/training/job/continuation_modes': 'handle_training_continuation_modes',
        '/api/training/hardware': 'handle_training_hardware',
        '/api/training/gpu/capabilities': 'handle_training_gpu_capabilities',
        '/api/training/gpu/autotune': 'handle_training_gpu_autotune',
        '/api/training/fwe/status': 'handle_training_fwe_status',
        '/api/training/fwe/runs': 'handle_training_fwe_runs',
        '/api/training/forge/status': 'handle_training_forge_status',
        '/api/training/forge/datasets': 'handle_training_forge_datasets',
        '/api/training/forge/configs': 'handle_training_forge_configs',
        '/api/training/forge/estimate': 'handle_training_forge_estimate',
        '/api/training/forge/checkpoints': 'handle_training_forge_checkpoints',
        '/api/training/forge/verify': 'handle_training_forge_verify',
        '/api/training/forge/teachers': 'handle_training_forge_teachers',
        '/api/training/forge/verify_model': 'handle_training_forge_verify_model',
        '/api/hardware/status': 'handle_hardware_status',
        '/api/hardware/restart-ollama': 'handle_hardware_restart_ollama',
        '/api/hardware/gpu/processes': 'handle_hardware_gpu_processes',
        '/api/hardware/gpu-processes': 'handle_hardware_gpu_processes',
        '/api/system/capabilities': 'handle_system_capabilities',
        '/api/system/available_modules': 'handle_system_available_modules',
        # MCP approvals awaiting the operator
        '/api/mcp/pending': 'handle_mcp_pending',
        # MCP Endpoints
        '/api/mcp/servers': 'handle_mcp_servers',
        '/api/mcp/tools': 'handle_mcp_tools',
        '/api/mcp/resources': 'handle_mcp_resources',
        '/api/mcp/ha/entities': 'handle_mcp_ha_entities',
        # Swarm Endpoints
        '/api/swarm/agents': 'handle_swarm_agents',
        # Benchmark Endpoints
        '/api/training/benchmark/models': 'handle_training_benchmark_models',
        '/api/training/benchmark/jobs': 'handle_training_benchmark_jobs',
        '/api/training/benchmark/suite_info': 'handle_training_benchmark_suite_info',
        '/api/training/benchmark/results': 'handle_training_benchmark_results',
        '/api/training/benchmark/review': 'handle_training_benchmark_review',
        '/api/training/benchmark/audit': 'handle_training_benchmark_audit',
        '/api/training/benchmark/capacity': 'handle_training_benchmark_capacity',
        '/api/training/benchmark/capacity/status': 'handle_training_benchmark_capacity_status',
        '/api/training/benchmark/endpoints': 'handle_training_benchmark_endpoints',
        # Knowledge Nodes Endpoints
        '/api/nodes': 'handle_get_nodes',
        # Skills & applicazioni gestite & Marketplace & Manifesti Hub

        '/api/skills': 'handle_skills_list',
        '/api/apps': 'handle_apps_status',
        '/api/marketplace/modules': 'handle_marketplace_modules',
        '/api/manifesti/hub': 'handle_manifesti_hub',
        '/api/modules/audio_studio/status': 'handle_audio_studio_status',
        '/api/modules/audio_studio/stations': 'handle_audio_studio_stations',
        # Model Hub & HF Downloader / Uploader
        '/api/models/hf/search': 'handle_models_hf_search',
        '/api/models/hf/details': 'handle_models_hf_details',
        '/api/models/hf/downloads': 'handle_models_hf_downloads_list',
        '/api/models/hf/test-connection': 'handle_models_hf_test_connection',
        '/api/models/hf/whoami': 'handle_models_hf_whoami',
        '/api/models/hf/upload/tasks': 'handle_models_hf_upload_tasks',
        '/api/models/local/list': 'handle_models_local_list',
        '/api/models/config': 'handle_models_config_get',
        '/api/models/convert/info': 'handle_models_convert_info',
        '/api/models/convert/jobs': 'handle_models_convert_jobs',
        '/api/models/browse': 'handle_models_browse_dirs',
        # System & Memory Cleanup
        '/api/system/clear-memory': 'handle_system_clear_memory',
    }
    # Merge, never replace. Optional modules register their own routes
    # through the module loader, which runs before this; assigning a fresh
    # dict here silently discarded every one of them, so a module's
    # endpoints answered 404 while its UI was fully wired up.
    existing = getattr(handler_class, '_GET_HANDLERS', None) or {}
    handler_class._GET_HANDLERS = {**core_routes, **existing}



def register_post_handlers(handler_class):
    """Register POST API handlers on the handler class."""
    core_routes = {
        '/api/mcp/rpc': 'handle_mcp_rpc',
        '/api/mcp/policy': 'handle_mcp_policy',
        '/api/mcp/integration': 'handle_mcp_integration',
        '/api/mcp/test': 'handle_mcp_test_integration',
        '/api/mcp/ha/control': 'handle_mcp_ha_control',
        '/api/mcp/external/add': 'handle_mcp_external_add',
        '/api/mcp/external/remove': 'handle_mcp_external_remove',
        '/api/mcp/external/connect': 'handle_mcp_external_connect',
        '/api/mcp/approve': 'handle_mcp_approve',
        '/v1/embeddings': 'handle_v1_embeddings',
        '/api/v1/embeddings': 'handle_v1_embeddings',
        '/api/show': 'handle_ollama_show',
        '/api/embed': 'handle_v1_embeddings',
        '/api/embeddings': 'handle_v1_embeddings',
        '/api/engine/provider_server/toggle': 'handle_provider_server_toggle',
        '/api/swarm/plan': 'handle_swarm_plan',
        '/api/swarm/execute': 'handle_swarm_execute',
        '/api/nodes/create': 'handle_create_node',
        '/api/nodes/delete': 'handle_delete_node',
        '/api/router/train': 'handle_router_train',
        '/api/hardware/config': 'handle_hardware_config',
        '/api/hardware/restart-ollama': 'handle_hardware_restart_ollama',
        '/api/hardware/gpu/kill': 'handle_hardware_gpu_kill',
        '/api/hardware/kill-process': 'handle_hardware_gpu_kill',
        '/api/hardware/kill_process': 'handle_hardware_gpu_kill',
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
        '/api/chat/extract_files': 'handle_chat_extract_files',
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
        '/api/manifesti/update_image': 'handle_update_manifesto_image',
        '/api/agents/upload_image': 'handle_upload_agent_image',
        '/api/upload_user_avatar': 'handle_upload_user_avatar',
        '/api/ai/action': 'handle_api_action',
        '/api/rename_file': 'handle_rename_file',
        '/api/rollback': 'handle_api_rollback',
        # Training Lab
        '/api/training/dataset/import': 'handle_training_dataset_import',
        '/api/training/dataset/register_hf': 'handle_training_dataset_register_hf',
        '/api/training/dataset/delete': 'handle_training_dataset_delete',
        '/api/training/job/create': 'handle_training_job_create',
        '/api/training/job/start': 'handle_training_job_start',
        '/api/training/job/continue': 'handle_training_job_continue',
        '/api/training/job/merge': 'handle_training_job_merge',
        '/api/training/job/stop': 'handle_training_job_stop',
        '/api/training/job/pause': 'handle_training_job_pause',
        '/api/training/job/resume': 'handle_training_job_resume',
        '/api/training/job/update': 'handle_training_job_update',
        '/api/training/models/pull': 'handle_training_models_pull',
        '/api/training/models/import': 'handle_training_models_import',
        '/api/training/autopilot/start': 'handle_training_autopilot_start',
        '/api/training/autopilot/stop': 'handle_training_autopilot_stop',
        '/api/training/autopilot/reset': 'handle_training_autopilot_reset',
        '/api/training/autopilot/reopen': 'handle_training_autopilot_reopen',
        '/api/training/autopilot/drop_rounds': 'handle_training_autopilot_drop_rounds',
        '/api/training/autopilot/cleanup': 'handle_training_autopilot_cleanup',
        '/api/training/job/delete': 'handle_training_job_delete',
        '/api/training/export/ollama': 'handle_training_export_ollama',
        '/api/training/dependencies': 'handle_training_dependencies',
        '/api/training/job/clear_logs': 'handle_training_clear_logs',
        '/api/training/fwe/selftest': 'handle_training_fwe_selftest',
        '/api/training/forge/chat': 'handle_training_forge_chat',
        '/api/training/forge/unload': 'handle_training_forge_unload',
        '/api/training/benchmark/run': 'handle_training_benchmark_run',
        '/api/training/benchmark/extend': 'handle_training_benchmark_extend',
        '/api/training/benchmark/delete': 'handle_training_benchmark_delete',
        '/api/training/benchmark/cancel': 'handle_training_benchmark_cancel',
        '/api/training/benchmark/pause': 'handle_training_benchmark_pause',
        '/api/training/benchmark/resume': 'handle_training_benchmark_resume',
        '/api/training/benchmark/download': 'handle_training_benchmark_download',
        '/api/training/benchmark/capacity/probe': 'handle_training_benchmark_capacity_probe',
        '/api/training/benchmark/endpoints/start': 'handle_training_benchmark_endpoint_start',
        '/api/training/benchmark/endpoints/stop': 'handle_training_benchmark_endpoint_stop',
        '/api/training/benchmark/endpoints/add': 'handle_training_benchmark_endpoint_add',
        '/api/training/benchmark/endpoints/remove': 'handle_training_benchmark_endpoint_remove',
        '/api/config/hf_token': 'handle_hf_token_config',
        '/api/engine/partition': 'handle_engine_partition',
        '/api/engine/hf/import': 'handle_engine_hf_import',
        '/api/engine/optimize': 'handle_engine_optimize',
        '/api/engine/overrides': 'handle_engine_overrides_set',
        '/api/engine/overrides/clear': 'handle_engine_overrides_clear',
        '/api/engine/plan': 'handle_engine_plan',
        '/api/engine/unload': 'handle_engine_unload',
        '/api/engine/benchmark': 'handle_engine_benchmark',
        '/api/skills/toggle': 'handle_skills_toggle',


        '/api/apps/launch': 'handle_apps_launch',
        '/api/apps/autoconfigure': 'handle_apps_autoconfigure',
        '/api/marketplace/install': 'handle_marketplace_install',
        '/api/marketplace/uninstall': 'handle_marketplace_uninstall',
        '/api/marketplace/rebuild': 'handle_marketplace_rebuild',
        '/api/manifesti/install_from_hub': 'handle_manifesti_install_from_hub',
        '/api/manifesti/uninstall': 'handle_manifesti_uninstall',
        '/api/models/hf/download/start': 'handle_models_hf_download_start',
        '/api/models/hf/download/repo': 'handle_models_hf_download_repo',
        '/api/models/hf/download/pause': 'handle_models_hf_download_pause',
        '/api/models/hf/download/resume': 'handle_models_hf_download_resume',
        '/api/models/hf/download/cancel': 'handle_models_hf_download_cancel',
        '/api/models/hf/download/retry': 'handle_models_hf_download_retry',
        '/api/models/hf/download/remove': 'handle_models_hf_download_remove',
        '/api/models/hf/downloads/clear': 'handle_models_hf_downloads_clear',
        '/api/models/hf/upload': 'handle_models_hf_upload',
        '/api/models/hf/upload/cancel': 'handle_models_hf_upload_cancel',
        '/api/models/hf/upload/remove': 'handle_models_hf_upload_remove',
        '/api/models/hf/card/preview': 'handle_models_hf_card_preview',
        '/api/models/hf/token/test': 'handle_models_hf_token_test',
        '/api/models/hf/test-connection': 'handle_models_hf_test_connection',
        '/api/models/local/delete': 'handle_models_local_delete',
        '/api/models/delete': 'handle_models_local_delete',
        '/api/models/local/rename': 'handle_models_local_rename',
        '/api/models/speedtest': 'handle_models_speedtest',
        '/api/models/hf/repo/status': 'handle_models_hf_repo_status',
        '/api/models/hf/repo/rename': 'handle_models_hf_repo_rename',
        '/api/models/hf/repo/attach': 'handle_models_hf_repo_attach',
        '/api/models/hf/repo/discover': 'handle_models_hf_repo_discover',
        '/api/models/hf/card/update': 'handle_models_hf_card_update',
        '/api/models/publication/forget': 'handle_models_publication_forget',
        '/api/models/engine/load': 'handle_models_engine_load',
        '/api/models/engine/unload': 'handle_models_engine_unload',
        '/api/models/config': 'handle_models_config_save',
        '/api/models/convert/start': 'handle_models_convert_start',
        '/api/models/convert/tooling': 'handle_models_convert_tooling',
        # System & Memory Cleanup
        '/api/system/clear-memory': 'handle_system_clear_memory',
        '/api/tasks/clear-all': 'handle_system_clear_memory',
    }
    existing = getattr(handler_class, '_POST_HANDLERS', None) or {}
    handler_class._POST_HANDLERS = {**core_routes, **existing}







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


# ---------------------------------------------------------------------------
# RESTful extension stubs (DELETE / PATCH)
# ---------------------------------------------------------------------------
# Registered in sigma_server.py via do_DELETE / do_PATCH.
# Add endpoint → handler mappings here as the API evolves.

_DELETE_HANDLERS: dict = {}
_PATCH_HANDLERS: dict = {}


def route_delete(self) -> None:
    """Route DELETE requests to registered handlers (REST support)."""
    parsed = urlparse(self.path)
    handler_name = _DELETE_HANDLERS.get(parsed.path)
    if handler_name and hasattr(self, handler_name):
        return getattr(self, handler_name)()
    self.send_error(405, "Method Not Allowed")


def route_patch(self) -> None:
    """Route PATCH requests to registered handlers (REST support)."""
    parsed = urlparse(self.path)
    handler_name = _PATCH_HANDLERS.get(parsed.path)
    if handler_name and hasattr(self, handler_name):
        return getattr(self, handler_name)()
    self.send_error(405, "Method Not Allowed")
