# ==============================================================================
# tests/test_agent_capabilities.py — Verification of Agent Capabilities
# ==============================================================================
"""Test suite validating all agent actions, module creation, file operations,
task management, python execution, web search, and routing logic."""

import os
import sys
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.task_handler import execute_ai_actions, _validate_module_path
from core.store import tasks_store, modules_store
from core.data_handler import rebuild_modules_meta
from core.chat.web_search import _perform_web_search, _search_youtube
from core.chat.prompt_builder import _determine_agent_by_request


TEST_TOPIC = "test_capability_topic"
TEST_MODULE_NAME = "01_test_module"
TEST_MODULE_PATH = f"data/{TEST_TOPIC}/{TEST_MODULE_NAME}"


class DummyHandler:
    """Mock handler providing path permission checking for execute_ai_actions."""
    def _is_path_allowed(self, path: str) -> bool:
        is_valid, _ = _validate_module_path(path)
        return is_valid


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Ensure test data directory is cleaned before and after tests."""
    topic_folder = f"data/{TEST_TOPIC}"
    if os.path.exists(topic_folder):
        shutil.rmtree(topic_folder, ignore_errors=True)
    yield
    if os.path.exists(topic_folder):
        shutil.rmtree(topic_folder, ignore_errors=True)


class TestModuleAndFolderCreation:
    """Test topic & module creation capabilities."""

    def test_create_module_creates_whitelist_folders(self):
        handler = DummyHandler()
        actions = [
            {
                "type": "create_module",
                "topic": TEST_TOPIC,
                "number": "01",
                "name": "test_module"
            }
        ]
        results = execute_ai_actions(handler, actions, "sigma_architect")
        assert len(results) == 1
        assert results[0]["success"] is True

        norm_module_path = TEST_MODULE_PATH.replace("/", os.sep)
        assert os.path.exists(norm_module_path)

    def test_create_module_meta_json_sync(self):
        handler = DummyHandler()
        actions = [
            {
                "type": "create_module",
                "topic": TEST_TOPIC,
                "number": "01",
                "name": "test_module"
            }
        ]
        execute_ai_actions(handler, actions, "sigma_architect")
        meta = rebuild_modules_meta()
        assert TEST_TOPIC in meta.get("topics", {})


class TestFileManagement:
    """Test file creation across all whitelisted categories."""

    def test_create_files_in_all_whitelisted_sections(self):
        handler = DummyHandler()

        # 1. Create module first
        execute_ai_actions(handler, [
            {"type": "create_module", "topic": TEST_TOPIC, "number": "01", "name": "test_module"}
        ], "sigma_architect")

        files_to_create = [
            (f"{TEST_MODULE_PATH}/teoria/definizione.md", "# Definizione Teorema"),
            (f"{TEST_MODULE_PATH}/scripts/calcolo.py", "print('Calcolo completato')"),
            (f"{TEST_MODULE_PATH}/viz/grafico.html", "<!DOCTYPE html><html><body>Visualizzazione</body></html>"),
            (f"{TEST_MODULE_PATH}/docs/appunti.md", "# Documentazione Note"),
        ]

        for path, content in files_to_create:
            actions = [{"type": "create_file", "path": path, "content": content}]
            results = execute_ai_actions(handler, actions, "math_researcher")
            assert len(results) == 1
            assert results[0]["success"] is True, f"Fallimento su: {path} - {results[0].get('error')}"
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as f:
                assert f.read() == content

    def test_edit_and_rename_file_capability(self):
        handler = DummyHandler()
        orig_path = f"{TEST_MODULE_PATH}/scripts/sim.py"
        new_path = f"{TEST_MODULE_PATH}/scripts/sim_v2.py"

        execute_ai_actions(handler, [
            {"type": "create_module", "topic": TEST_TOPIC, "number": "01", "name": "test_module"},
            {"type": "create_file", "path": orig_path, "content": "x = 1"}
        ], "code_architect")

        # Edit
        edit_action = [{"type": "edit_file", "path": orig_path, "content": "x = 42"}]
        res_edit = execute_ai_actions(handler, edit_action, "code_architect")
        assert res_edit[0]["success"] is True

        # Rename
        rename_action = [{"type": "rename_file", "old_path": orig_path, "new_path": new_path}]
        res_rename = execute_ai_actions(handler, rename_action, "code_architect")
        assert res_rename[0]["success"] is True
        assert os.path.exists(new_path)
        assert not os.path.exists(orig_path)

        # Delete
        delete_action = [{"type": "delete_file", "path": new_path}]
        res_delete = execute_ai_actions(handler, delete_action, "code_architect")
        assert res_delete[0]["success"] is True
        assert not os.path.exists(new_path)


class TestTaskAndRoadmapManagement:
    """Test task creation and status updates."""

    def test_update_task_creates_and_updates_status(self):
        handler = DummyHandler()
        task_title = "Task Capability Test 101"

        actions = [
            {
                "type": "update_task",
                "titolo": task_title,
                "status": "in_corso",
                "notifica": "Task avviato da test suite"
            }
        ]
        results = execute_ai_actions(handler, actions, "sigma_architect")
        assert results[0]["success"] is True

        all_tasks = tasks_store.load()
        target = next((t for t in all_tasks if t.get("titolo") == task_title), None)
        assert target is not None
        assert target["status"] == "in_corso"

        # Cleanup test task
        tasks_store.update(lambda ts: [t for t in ts if t.get("titolo") != task_title])


class TestWebSearchCapabilities:
    """Test web search and YouTube link extraction."""

    def test_web_search_general_query(self):
        results = _perform_web_search("Python 3.12 release notes")
        assert isinstance(results, list)
        assert len(results) > 0
        assert "title" in results[0]
        assert "href" in results[0]

    def test_youtube_search_extracts_video_links(self):
        results = _search_youtube("esponenziali in italiano")
        assert isinstance(results, list)
        assert len(results) > 0
        watch_links = [r for r in results if "youtube.com/watch" in r.get("href", "")]
        assert len(watch_links) > 0, "Nessun link video YouTube valido estratto"


class TestAgentRoutingAndManifestos:
    """Test agent manifesto integrity and auto-routing."""

    def test_all_agent_manifestos_exist(self):
        manifestos = [
            "sigma_assistant.md", "sigma_architect.md", "code_architect.md",
            "math_researcher.md", "viz_designer.md", "test_engineer.md",
            "proof_reviewer.md", "sigma_admin.md"
        ]
        for m in manifestos:
            path = os.path.join("manifesti", m)
            assert os.path.exists(path), f"Manifesto mancante: {path}"

    def test_agent_routing_math_query(self):
        manifesto_path = _determine_agent_by_request("Dimostra il teorema di Eulero", {}, "auto")
        assert "math_researcher" in manifesto_path

    def test_agent_routing_code_query(self):
        manifesto_path = _determine_agent_by_request("Scrivi uno script python", {}, "auto")
        assert "code_architect" in manifesto_path or "sigma_assistant" in manifesto_path
