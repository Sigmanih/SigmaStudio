# ==============================================================================
# tests/test_sandbox.py — Unit tests for core/sandbox.py
# ==============================================================================
"""Verify that the pathlib-based sandbox correctly allows and blocks paths."""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.sandbox import is_path_allowed, normalize_path


class TestSandboxAllowedPaths:
    """Paths that should be allowed by the sandbox."""

    def test_allowed_data_path(self):
        assert is_path_allowed("data/topic1/01_mod/teoria/file.md") is True

    def test_allowed_manifesti_path(self):
        assert is_path_allowed("manifesti/sigma.md") is True

    def test_allowed_scratch_path(self):
        assert is_path_allowed("scratch/tmp.py") is True

    def test_allowed_core_path(self):
        assert is_path_allowed("core/logger.py") is True

    def test_allowed_sigma_studio_path(self):
        assert is_path_allowed("sigma_studio/src/App.jsx") is True

    def test_allowed_root_file_tasks(self):
        assert is_path_allowed("tasks.json") is True

    def test_allowed_root_file_config(self):
        assert is_path_allowed("config.json") is True

    def test_allowed_root_file_modules_meta(self):
        assert is_path_allowed("modules_meta.json") is True


class TestSandboxBlockedPaths:
    """Paths that should be BLOCKED by the sandbox (security)."""

    def test_block_path_traversal_up(self):
        assert is_path_allowed("../etc/passwd") is False

    def test_block_path_traversal_double_slash(self):
        assert is_path_allowed("data/../../../windows/system32") is False

    def test_block_null_byte(self):
        assert is_path_allowed("data/file\x00.md") is False

    def test_block_empty_string(self):
        assert is_path_allowed("") is False

    def test_block_none(self):
        assert is_path_allowed(None) is False  # type: ignore[arg-type]

    def test_block_absolute_system_path(self):
        assert is_path_allowed("C:/Windows/System32/cmd.exe") is False

    def test_block_home_directory(self):
        assert is_path_allowed("C:/Users/admin/.ssh/id_rsa") is False

    def test_block_unknown_top_level_dir(self):
        assert is_path_allowed("secrets/passwords.txt") is False


class TestNormalizePath:
    def test_normalizes_backslashes(self):
        assert normalize_path("data\\topic\\file.md") == "data/topic/file.md"

    def test_empty_string(self):
        assert normalize_path("") == ""

    def test_none(self):
        assert normalize_path(None) is None  # type: ignore[arg-type]
