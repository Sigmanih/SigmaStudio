# ==============================================================================
# tests/test_ai_integration.py — End-to-End Local AI Integration Test Suite
# Sigma Studio v7.0
# ==============================================================================
"""Comprehensive test suite validating end-to-end local AI capabilities:
- Chat response & reasoning separation
- Topic & module creation with 5 mandatory subdirectories (teoria, code, viz, test, docs)
- File creation from AI output (explicit Path, pseudo-commands, fallback)
- File modification and content updates
- File deletion and metadata store synchronization
"""

import os
import sys
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.task_handler import execute_ai_actions, _validate_module_path
from core.chat_handler import (
    _extract_and_create_files_from_text,
    _sanitize_history_message,
    _ensure_module_subfolders,
    _normalize_data_path,
)
from core.chat.response_parser import _clean_all_tags
from core.data_handler import rebuild_modules_meta
from core.store import modules_store


TEST_TOPIC = "test_ai_topic"
TEST_MODULE = "01_limiti_e_continuita"
TEST_TOPIC_DIR = f"data/{TEST_TOPIC}"
TEST_MODULE_DIR = f"{TEST_TOPIC_DIR}/{TEST_MODULE}"


class DummyHandler:
    """Mock HTTP handler for execute_ai_actions permission validation."""
    def _is_path_allowed(self, path: str) -> bool:
        is_valid, _ = _validate_module_path(path)
        return is_valid


@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """Clean up test_ai_topic directory before and after each test."""
    if os.path.exists(TEST_TOPIC_DIR):
        shutil.rmtree(TEST_TOPIC_DIR, ignore_errors=True)
    yield
    if os.path.exists(TEST_TOPIC_DIR):
        shutil.rmtree(TEST_TOPIC_DIR, ignore_errors=True)


class TestLocalAIChatResponse:
    """Test AI chat response parsing, reasoning extraction, and history sanitization."""

    def test_reasoning_monologue_separation(self):
        raw_output = """Analyze User Input: The user asks about calculus.
Identify Key Constraints: Use LaTeX notation.
Draft Generation: Write limits definition.
Proceeds.✅
Ciao! Ecco la trattazione formale sui limiti di funzione."""

        response_text, thinking_text = _clean_all_tags(raw_output)
        assert thinking_text is not None
        assert "Analyze User Input" in thinking_text
        assert "Ciao! Ecco la trattazione formale" in response_text

    def test_history_sanitization_removes_old_roles(self):
        old_history = """FROM llama3.2
SYSTEM \"\"\" Sei Sigma Assistant... \"\"\"
Ruolo attivo: Sigma Assistant
Analyze User Input: Previous turn reasoning monologue.
Proceeds.✅
Ciao, come posso aiutarti?"""

        clean_hist = _sanitize_history_message(old_history)
        assert "SYSTEM" not in clean_hist
        assert "Ruolo attivo" not in clean_hist
        assert "Analyze User Input" not in clean_hist
        assert "Ciao, come posso aiutarti?" in clean_hist


class TestLocalAITopicCreation:
    """Test topic & module creation with automatic 5 subdirectories."""

    def test_create_module_builds_all_5_subdirectories(self):
        handler = DummyHandler()
        actions = [
            {
                "type": "create_module",
                "topic": TEST_TOPIC,
                "number": "01",
                "name": "limiti_e_continuita"
            }
        ]
        results = execute_ai_actions(handler, actions, "sigma_architect")
        assert len(results) == 1
        assert results[0]["success"] is True

        norm_path = TEST_MODULE_DIR.replace("/", os.sep)
        assert os.path.exists(norm_path)

        for sub in ("teoria", "scripts", "viz", "test", "docs"):
            sub_path = os.path.join(norm_path, sub)
            assert os.path.exists(sub_path), f"Mandatory subfolder missing: {sub_path}"

    def test_ensure_module_subfolders_helper(self):
        target_file = f"{TEST_MODULE_DIR}/teoria/limiti.md"
        _ensure_module_subfolders(target_file)
        
        for sub in ("teoria", "scripts", "viz", "test", "docs"):
            sub_dir = f"{TEST_MODULE_DIR}/{sub}".replace("/", os.sep)
            assert os.path.exists(sub_dir)


class TestLocalAIFileCreation:
    """Test physical file creation from AI output patterns."""

    def test_explicit_path_and_codeblock_extraction(self):
        ai_response = f"""Ecco la teoria formale sui limiti:

Path: {TEST_MODULE_DIR}/teoria/limiti.md
```markdown
# Il Concetto di Limite
Sia $f: A \\to \\mathbb{{R}}$ una funzione.
```
"""
        created, _ = _extract_and_create_files_from_text(ai_response, TEST_TOPIC)
        assert len(created) > 0
        file_path = created[0].replace("/", os.sep)
        assert os.path.exists(file_path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# Il Concetto di Limite" in content

    def test_emoji_and_inline_path_extraction(self):
        ai_response = f"""Ho generato lo script di calcolo:

### 📄 {TEST_MODULE_DIR}/scripts/calcolo.py
```python
def calcola_limite(x):
    return 1 / x
```
"""
        created, _ = _extract_and_create_files_from_text(ai_response, TEST_TOPIC)
        assert len(created) > 0
        file_path = created[0].replace("/", os.sep)
        assert os.path.exists(file_path)

    def test_fallback_file_creation_when_prompt_requests_topic(self):
        ai_response = """# Analisi Matematica 1
Trattazione approfondita sulle successioni e serie numeriche."""
        
        created, _ = _extract_and_create_files_from_text(ai_response, "crea l'argomento analisi 1")
        assert len(created) > 0
        assert os.path.exists(created[0].replace("/", os.sep))

    def test_self_healing_multi_language_extraction(self):
        ai_response = f"""Ecco la documentazione ed i file per lo studio di funzioni:

Path: {TEST_MODULE_DIR}/teoria/01_teoria.md
```markdown
# Teoria dello Studio di Funzioni
```

Path: {TEST_MODULE_DIR}/scripts/01_script.py
```python
import sympy as sp
x = sp.Symbol('x')
```

Path: {TEST_MODULE_DIR}/viz/01_grafico.html
```html
<!DOCTYPE html><html><body>Grafico</body></html>
```
"""
        created, _ = _extract_and_create_files_from_text(ai_response, TEST_TOPIC)
        assert len(created) == 3
        for path in created:
            norm_p = path.replace("/", os.sep)
            assert os.path.exists(norm_p)
            
        # Verify 5 mandatory subdirectories exist under module folder
        for sub in ("teoria", "scripts", "viz", "test", "docs"):
            sub_p = os.path.join(TEST_MODULE_DIR.replace("/", os.sep), sub)
            assert os.path.exists(sub_p)


class TestLocalAIFileModification:
    """Test modifying existing files via AI actions."""

    def test_edit_file_updates_content_on_disk(self):
        handler = DummyHandler()
        
        # 1. Create file first
        file_path = f"{TEST_MODULE_DIR}/teoria/limiti.md"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Titolo Iniziale\nTesto base.")

        # 2. Execute edit action
        actions = [
            {
                "type": "edit_file",
                "path": file_path,
                "content": "# Titolo Aggiornato dall'IA\nTesto modificato con notazione LaTeX: $x \\to 0$."
            }
        ]
        results = execute_ai_actions(handler, actions, "math_researcher")
        assert len(results) == 1
        assert results[0]["success"] is True

        with open(file_path.replace("/", os.sep), "r", encoding="utf-8") as f:
            updated_content = f.read()
        assert "# Titolo Aggiornato dall'IA" in updated_content
        assert "$x \\to 0$" in updated_content


class TestLocalAIFileDeletion:
    """Test deleting files and metadata store synchronization."""

    def test_delete_file_removes_file_from_disk(self):
        handler = DummyHandler()
        
        file_path = f"{TEST_MODULE_DIR}/teoria/limiti_temp.md"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Temp content")

        assert os.path.exists(file_path.replace("/", os.sep))

        actions = [
            {
                "type": "delete_file",
                "path": file_path
            }
        ]
        results = execute_ai_actions(handler, actions, "sigma_architect")
        assert len(results) == 1
        assert results[0]["success"] is True
        assert not os.path.exists(file_path.replace("/", os.sep))

    def test_rebuild_modules_meta_sync(self):
        os.makedirs(f"{TEST_MODULE_DIR}/teoria", exist_ok=True)
        with open(f"{TEST_MODULE_DIR}/teoria/01_limiti.md", "w", encoding="utf-8") as f:
            f.write("# Limiti")

        meta = rebuild_modules_meta()
        assert TEST_TOPIC in meta.get("topics", {})
