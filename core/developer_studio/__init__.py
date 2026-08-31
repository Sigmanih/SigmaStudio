# ==============================================================================
# core/developer_studio/__init__.py — Developer Studio Compatibility Bridge
# Re-exports from module core.modules.sigma_developer_lab for backwards compatibility.
# ==============================================================================
from core.modules.sigma_developer_lab import *
from core.modules.sigma_developer_lab.fs_manager import (
    get_workspace_tree,
    read_file_content,
    write_file_content,
    delete_fs_entry,
    create_fs_entry,
    rename_fs_entry,
    search_workspace_files,
    get_default_workspace_root,
    list_file_backups,
    restore_file_backup,
)
from core.modules.sigma_developer_lab.terminal_runner import (
    execute_shell_command_sync,
    stream_shell_command,
)
from core.modules.sigma_developer_lab.admin_agent import (
    stream_admin_agent_turn,
    execute_admin_tool,
)
from core.modules.sigma_developer_lab.handlers import (
    handle_fs_tree,
    handle_fs_read,
    handle_fs_raw,
    handle_fs_write,
    handle_fs_delete,
    handle_fs_create,
    handle_fs_rename,
    handle_fs_search,
    handle_terminal_exec,
    handle_agent_chat,
    handle_workspace_roots,
    handle_get_tasks,
    handle_save_tasks,
    handle_orchestrator_run,
    handle_orchestrator_status,
    handle_roles_list,
    handle_fs_backups,
    handle_fs_restore,
)
