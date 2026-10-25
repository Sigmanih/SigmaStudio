# ==============================================================================
# core/modules/sigma_developer_lab/__init__.py — Developer Studio & Admin IDE
# Sigma Studio v8 — Modulo installabile
# ==============================================================================
"""L'IDE amministrativo: rotte, flusso di lavoro a fasi, server MCP di sviluppo.

Il motore che fa lavorare l'agente non sta qui: sta nel kernel, in
`core.harness`, perche' serve anche a chi non installa un IDE. Questo modulo
aggiunge cio' che riguarda soltanto lo sviluppo di software:

* le rotte `/api/developer/*` e lo streaming SSE verso la UI (`handlers`);
* l'orchestrazione a cinque fasi analisi → setup → implementazione →
  verifica → consegna, con i ruoli dello sviluppo (`orchestrator`);
* i server MCP di git, lint e test (`mcp_tools`).

Chi vuole modificare Sigma Studio dall'interno installa questo modulo. Chi
vuole solo far eseguire un compito a un modello usa `core.harness` e basta.
"""

from core.modules.sigma_developer_lab.handlers import (
    handle_fs_tree,
    handle_fs_read,
    handle_fs_write,
    handle_fs_delete,
    handle_fs_create,
    handle_fs_rename,
    handle_fs_search,
    handle_terminal_exec,
    handle_agent_chat,
    handle_workspace_roots,
    handle_add_workspace_root,
    handle_remove_workspace_root,
    handle_orchestrator_run,
    handle_orchestrator_status,
    handle_roles_list,
    handle_fs_backups,
    handle_fs_restore,
    register_routes,
    register_mcp,
    ROUTES,
)

__all__ = [
    "handle_fs_tree",
    "handle_fs_read",
    "handle_fs_write",
    "handle_fs_delete",
    "handle_fs_create",
    "handle_fs_rename",
    "handle_fs_search",
    "handle_terminal_exec",
    "handle_agent_chat",
    "handle_workspace_roots",
    "handle_add_workspace_root",
    "handle_remove_workspace_root",
    "handle_orchestrator_run",
    "handle_orchestrator_status",
    "handle_roles_list",
    "handle_fs_backups",
    "handle_fs_restore",
    "register_routes",
    "register_mcp",
    "ROUTES",
]
