import os
import pytest
from core.harness.loop import resolve_workspace_path, execute_admin_tool

def test_resolve_relative_to_active_cwd(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    frontend = workspace / "frontend"
    frontend.mkdir()
    (frontend / "src").mkdir()
    app_file = frontend / "src" / "App.jsx"
    app_file.write_text("// frontend app", encoding="utf-8")

    # Senza active_cwd, "frontend/src/App.jsx" si risolve correttamente
    assert resolve_workspace_path("frontend/src/App.jsx", str(workspace)) == str(app_file)

    # Con active_cwd impostato sulla cartella frontend, "src/App.jsx" punta direttamente a frontend/src/App.jsx
    resolved = resolve_workspace_path("src/App.jsx", str(workspace), active_cwd=str(frontend))
    assert resolved == str(app_file)

def test_terminal_cd_command_tracks_new_cwd(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subfolder = workspace / "frontend"
    subfolder.mkdir()

    res = execute_admin_tool(
        "terminal",
        {"command": "cd frontend"},
        str(workspace),
        active_cwd=str(workspace)
    )

    assert res.get("success") is True
    assert res.get("new_cwd") == str(subfolder)
    assert "Directory attiva" in res.get("stdout", "")
