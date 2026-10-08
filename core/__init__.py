# ==============================================================================
# core/__init__.py — Inizializzazione package e risolutore retrocompatibile
# Sigma Studio v8 — Kernel Core
# ==============================================================================
import sys
import importlib
from importlib.abc import MetaPathFinder

# Mappatura dei moduli riorganizzati in sottocartelle
_CORE_SUBMODULE_MAP = {
    # Handlers
    "chat_handler": "core.handlers.chat_handler",
    "config_handler": "core.handlers.config_handler",
    "data_handler": "core.handlers.data_handler",
    "file_handler": "core.handlers.file_handler",
    "loop_handler": "core.handlers.loop_handler",
    "mcp_handler": "core.handlers.mcp_handler",
    "module_handler": "core.handlers.module_handler",
    "plan_handler": "core.handlers.plan_handler",
    "swarm_handler": "core.handlers.swarm_handler",
    "system_handler": "core.handlers.system_handler",
    "task_handler": "core.handlers.task_handler",
    # Security
    "sandbox": "core.security.sandbox",
    "sandbox_manager": "core.security.sandbox_manager",
    "ssl_manager": "core.security.ssl_manager",
    "dep_installer": "core.security.dep_installer",
    # System
    "backup_manager": "core.system.backup_manager",
    "system_cleanup": "core.system.system_cleanup",
    "runtime_env": "core.system.runtime_env",
    "net_utils": "core.system.net_utils",
    "first_run": "core.system.first_run",
    # Agents
    "agent_memory": "core.agents.agent_memory",
    "agent_orchestrator": "core.agents.agent_orchestrator",
    "agent_registry": "core.agents.agent_registry",
    "agent_templates": "core.agents.agent_templates",
    "assistant_orchestrator": "core.agents.assistant_orchestrator",
    "manifests_catalog": "core.agents.manifests_catalog",
    # Workspace
    "progetti": "core.workspace.progetti",
    "scheda_progetto": "core.workspace.scheda_progetto",
    "creative_gallery": "core.workspace.creative_gallery",
    "research_sessions": "core.workspace.research_sessions",
    "pdf_extractor": "core.workspace.pdf_extractor",
}


class _CoreAliasFinder(MetaPathFinder):
    """Garantisce la retrocompatibilità per import legacy tipo 'from core.sandbox import ...'."""
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith("core."):
            sub = fullname[5:]
            if sub in _CORE_SUBMODULE_MAP:
                target_name = _CORE_SUBMODULE_MAP[sub]
                try:
                    mod = importlib.import_module(target_name)
                    sys.modules[fullname] = mod
                    return mod.__spec__
                except Exception:
                    return None
        return None


# Registra il finder in cima a sys.meta_path se non già presente
if not any(isinstance(f, _CoreAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _CoreAliasFinder())

# Inizializzazione SSL resiliente (ora da core.system.net_utils)
try:
    from core.system.net_utils import setup_resilient_ssl
    setup_resilient_ssl()
except Exception:
    pass
