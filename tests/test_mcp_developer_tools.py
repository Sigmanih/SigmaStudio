# ==============================================================================
# tests/test_mcp_developer_tools.py — Test per i server MCP del Developer Studio
# ==============================================================================
"""Test pytest per i 5 server MCP aggiunti al Developer Studio:
DepsMCPServer, HealthMCPServer, ProfileMCPServer, ScreenshotMCPServer,
SemanticMCPServer, più il bridge.

Ogni server viene istanziato, i tool verificati, e le chiamate testate
con dati controllati. Nessuna dipendenza esterna richiesta.
"""
import json
import os
import textwrap

import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Deps Server
# ---------------------------------------------------------------------------
from core.modules.sigma_developer_lab.mcp_tools.deps_server import (
    DepsMCPServer,
    _parse_requirements,
    _parse_package_json,
)


class TestDepsServer:

    def test_registrazione_tool(self):
        server = DepsMCPServer()
        names = [t["name"] for t in server.list_tools()]
        assert "deps_audit" in names

    def test_schema_deps_audit(self):
        server = DepsMCPServer()
        tool = next(t for t in server.list_tools() if t["name"] == "deps_audit")
        props = tool["inputSchema"]["properties"]
        assert "check_vulnerabilities" in props
        assert "include_dev" in props

    def test_safety_safe(self):
        server = DepsMCPServer()
        tool = next(t for t in server.list_tools() if t["name"] == "deps_audit")
        assert tool["safety"] == "safe"

    def test_call_tool_senza_vulnerabilita(self):
        """call_tool con check_vulnerabilities=False non esplode."""
        server = DepsMCPServer()
        result = server.call_tool("deps_audit", {"check_vulnerabilities": False})
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        assert "python" in payload
        assert "javascript" in payload

    def test_missing_dependency_tipo_stringa(self):
        """Il return di missing_dependency deve essere str o None, mai tupla."""
        server = DepsMCPServer()
        val = server.missing_dependency()
        assert val is None or isinstance(val, str)

    def test_parse_requirements_file_finto(self, tmp_path):
        reqs = tmp_path / "requirements.txt"
        reqs.write_text("flask>=2.0\nrequests\n# commento\n-r extra.txt\n", encoding="utf-8")
        deps = _parse_requirements(reqs)
        assert len(deps) == 2
        assert deps[0]["name"] == "flask"
        assert deps[0]["version"] == "2.0"
        assert deps[1]["name"] == "requests"
        assert deps[1]["version"] == "any"

    def test_parse_requirements_file_assente(self, tmp_path):
        deps = _parse_requirements(tmp_path / "non_esiste.txt")
        assert deps == []

    def test_parse_package_json(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"},
            "devDependencies": {"vite": "^5.0.0"},
        }), encoding="utf-8")
        deps = _parse_package_json(pkg)
        assert len(deps) == 2
        nomi = {d["name"] for d in deps}
        assert "react" in nomi
        assert "vite" in nomi

    def test_parse_package_json_malformato(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text("{malformato", encoding="utf-8")
        deps = _parse_package_json(pkg)
        assert deps == []


# ---------------------------------------------------------------------------
# Health Server
# ---------------------------------------------------------------------------
from core.modules.sigma_developer_lab.mcp_tools.health_server import (
    HealthMCPServer,
    _check_file,
    _check_python_env,
    _check_cli_tool,
)


class TestHealthServer:

    def test_registrazione_tool(self):
        server = HealthMCPServer()
        names = [t["name"] for t in server.list_tools()]
        assert "server_health" in names

    def test_call_tool_chiavi_report(self):
        server = HealthMCPServer()
        result = server.call_tool("server_health", {"check_http": False})
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        for chiave in ("timestamp", "workspace_root", "python_env",
                       "key_files", "cli_tools", "project_stats", "summary"):
            assert chiave in payload, f"Chiave mancante: {chiave}"

    def test_check_file_esistente(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("ciao", encoding="utf-8")
        info = _check_file(f)
        assert info["exists"] is True
        assert info["is_file"] is True
        assert info["size_bytes"] == 4

    def test_check_file_inesistente(self, tmp_path):
        info = _check_file(tmp_path / "non_esiste.txt")
        assert info["exists"] is False

    def test_python_env_ha_versione(self):
        env = _check_python_env()
        assert "version" in env
        assert env["version"]  # non vuoto

    def test_check_cli_python(self):
        info = _check_cli_tool("python")
        assert info["available"] is True

    def test_check_cli_inesistente(self):
        info = _check_cli_tool("tool_che_non_esiste_xyz_42")
        assert info["available"] is False

    def test_is_configured_sempre_true(self):
        server = HealthMCPServer()
        assert server.is_configured() is True


# ---------------------------------------------------------------------------
# Profile Server
# ---------------------------------------------------------------------------
from core.modules.sigma_developer_lab.mcp_tools.profile_server import (
    ProfileMCPServer,
    _profile_function,
    _get_peak_memory_kb,
)


class TestProfileServer:

    def test_registrazione_tool(self):
        server = ProfileMCPServer()
        names = [t["name"] for t in server.list_tools()]
        assert "profile_app" in names

    def test_version_presente(self):
        server = ProfileMCPServer()
        assert server.version == "1.0.0"

    def test_schema_coerente(self):
        server = ProfileMCPServer()
        tool = next(t for t in server.list_tools() if t["name"] == "profile_app")
        props = tool["inputSchema"]["properties"]
        assert "target_type" in props
        assert "target" in props
        required = tool["inputSchema"]["required"]
        assert "target_type" in required
        assert "target" in required

    def test_profiling_funzione_nota(self):
        """Profila os.path.exists — funzione sempre disponibile, veloce."""
        result = _profile_function("os.path.exists", args=["."])
        assert result["success"] is True
        assert result["duration_ms"] >= 0
        assert isinstance(result["top_functions"], list)
        assert result["total_calls"] >= 1

    def test_profiling_funzione_inesistente(self):
        result = _profile_function("non.esiste.funzione_xyz")
        assert result["success"] is False
        assert "error" in result

    def test_call_tool_function(self):
        server = ProfileMCPServer()
        result = server.call_tool("profile_app", {
            "target_type": "function",
            "target": "os.path.exists",
            "args": ["."],
        })
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is True

    def test_call_tool_http_url_inesistente(self):
        """Un URL inesistente deve restituire success=False senza crashare."""
        server = ProfileMCPServer()
        result = server.call_tool("profile_app", {
            "target_type": "http",
            "target": "http://127.0.0.1:1/non_esiste",
            "timeout": 1,
        })
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False
        assert "error" in payload

    def test_call_tool_target_type_invalido(self):
        server = ProfileMCPServer()
        result = server.call_tool("profile_app", {
            "target_type": "invalido",
            "target": "qualcosa",
        })
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False

    def test_peak_memory_non_esplode(self):
        """_get_peak_memory_kb non deve mai lanciare eccezioni."""
        val = _get_peak_memory_kb()
        assert isinstance(val, int)
        assert val >= 0


# ---------------------------------------------------------------------------
# Screenshot Server
# ---------------------------------------------------------------------------
from core.modules.sigma_developer_lab.mcp_tools.screenshot_server import (
    ScreenshotMCPServer,
)


class TestScreenshotServer:

    def test_registrazione_tool(self):
        server = ScreenshotMCPServer()
        names = [t["name"] for t in server.list_tools()]
        assert "screenshot_page" in names

    def test_version_presente(self):
        server = ScreenshotMCPServer()
        assert server.version == "1.0.0"

    def test_missing_dependency_tipo(self):
        """missing_dependency deve restituire str (suggerimento) o None."""
        server = ScreenshotMCPServer()
        val = server.missing_dependency()
        assert val is None or isinstance(val, str)

    def test_schema_url_required(self):
        server = ScreenshotMCPServer()
        tool = next(t for t in server.list_tools() if t["name"] == "screenshot_page")
        assert "url" in tool["inputSchema"]["required"]

    def test_call_senza_url(self):
        server = ScreenshotMCPServer()
        result = server.call_tool("screenshot_page", {})
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        assert payload["success"] is False


# ---------------------------------------------------------------------------
# Semantic Server
# ---------------------------------------------------------------------------
from core.modules.sigma_developer_lab.mcp_tools.semantic_server import (
    SemanticMCPServer,
    _tokenize,
    _compute_tf,
    _compute_idf,
    _cosine_similarity,
)


class TestSemanticServer:

    def test_registrazione_4_tool(self):
        server = SemanticMCPServer()
        names = [t["name"] for t in server.list_tools()]
        assert "semantic_search" in names
        assert "index_codebase" in names
        assert "index_status" in names
        assert "explain_code" in names

    def test_version_presente(self):
        server = SemanticMCPServer()
        assert server.version == "1.0.0"

    def test_tokenize(self):
        tokens = _tokenize("def calcola_totale(items):")
        assert "def" in tokens
        assert "calcola_totale" in tokens
        assert "items" in tokens

    def test_compute_tf(self):
        tf = _compute_tf(["hello", "world", "hello"])
        assert tf["hello"] == pytest.approx(2 / 3)
        assert tf["world"] == pytest.approx(1 / 3)

    def test_compute_idf(self):
        docs = [["hello", "world"], ["hello", "python"], ["world", "python"]]
        idf = _compute_idf(docs)
        assert "hello" in idf
        assert "python" in idf
        # hello appare in 2 doc su 3, python in 2 su 3 → stessa IDF
        assert idf["hello"] == pytest.approx(idf["python"])

    def test_cosine_similarity_identico(self):
        v = {"a": 1.0, "b": 2.0}
        sim = _cosine_similarity(v, v)
        assert sim == pytest.approx(1.0)

    def test_cosine_similarity_ortogonale(self):
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        sim = _cosine_similarity(v1, v2)
        assert sim == pytest.approx(0.0)

    def test_build_index_su_directory_tmp(self, tmp_path, monkeypatch):
        """Costruisce un indice su una directory temporanea con file finti."""
        (tmp_path / "modulo.py").write_text(
            "def gestione_errori():\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "utils.js").write_text(
            "function handleError(err) { console.log(err); }\n", encoding="utf-8"
        )
        # Fa puntare resolve_root alla directory tmp
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        server = SemanticMCPServer()
        result = server.call_tool("index_codebase", {})
        assert result["isError"] is False
        payload = json.loads(result["content"][0]["text"])
        assert payload["total_documents"] >= 2

    def test_ricerca_con_risultati(self, tmp_path, monkeypatch):
        (tmp_path / "rete.py").write_text(
            "import socket\ndef connetti_socket(host, port):\n    s = socket.socket()\n    s.connect((host, port))\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        server = SemanticMCPServer()
        server._build_index()
        results = server._semantic_search("socket connection", top_k=5)
        assert len(results) >= 1
        assert any("rete.py" in r["file"] for r in results)

    def test_force_fallback(self, tmp_path, monkeypatch):
        """Con force_fallback=True si salta il cosine e si usa il matching fuzzy."""
        (tmp_path / "auth.py").write_text(
            "def login(user, password):\n    token = create_jwt(user)\n    return token\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        server = SemanticMCPServer()
        server._build_index()
        results = server._semantic_search("autenticazione", top_k=5, force_fallback=True)
        # Il sinonimo "autenticazione" → ["auth", "login", "token", ...] deve matchare
        assert len(results) >= 1

    def test_explain_code(self, tmp_path, monkeypatch):
        (tmp_path / "mcp_hub.py").write_text(
            "class MCPHub:\n    def register(self):\n        pass\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        server = SemanticMCPServer()
        server._build_index()
        result = server._explain_code("MCPHub")
        assert "error" not in result
        assert result["symbol"] == "MCPHub"
        assert result["occurrences"] >= 1

    def test_explain_code_simbolo_mancante(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        (tmp_path / "vuoto.py").write_text("x = 1\n", encoding="utf-8")
        server = SemanticMCPServer()
        server._build_index()
        result = server._explain_code("ClasseInesistente")
        assert "error" in result

    def test_index_status_prima_e_dopo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        (tmp_path / "f.py").write_text(
            "def calcola_totale(items):\n    return sum(items)\n",
            encoding="utf-8",
        )
        server = SemanticMCPServer()
        # Prima dell'indicizzazione l'indice non esiste o è vuoto
        result_prima = server.call_tool("index_status", {})
        payload_prima = json.loads(result_prima["content"][0]["text"])
        # Costruisce l'indice
        server.call_tool("index_codebase", {})
        # Dopo l'indicizzazione deve avere almeno 1 documento
        result_dopo = server.call_tool("index_status", {})
        payload_dopo = json.loads(result_dopo["content"][0]["text"])
        assert payload_dopo.get("total_documents", 0) >= 1

    def test_percorsi_relativi_nel_indice(self, tmp_path, monkeypatch):
        """I path nell'indice devono essere relativi alla root, non assoluti."""
        sub = tmp_path / "core" / "modulo.py"
        sub.parent.mkdir(parents=True)
        sub.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(
            "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root",
            lambda *a, **kw: str(tmp_path),
        )
        server = SemanticMCPServer()
        server._build_index()
        paths = [d["path"] for d in server._index["documents"]]
        for p in paths:
            assert not Path(p).is_absolute(), f"Path assoluto nell'indice: {p}"


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------
from core.modules.sigma_developer_lab.mcp_tools.bridge import (
    ADMIN_TO_MCP,
    is_mcp_tool,
    is_local_tool,
)


class TestBridge:

    def test_nuovi_tool_presenti(self):
        for nome in ("deps_audit", "server_health", "profile_app",
                      "screenshot_page", "semantic_search", "index_codebase",
                      "index_status", "explain_code"):
            assert nome in ADMIN_TO_MCP, f"Tool '{nome}' mancante nel bridge"

    def test_is_mcp_tool_nuovi(self):
        assert is_mcp_tool("deps_audit")
        assert is_mcp_tool("server_health")
        assert is_mcp_tool("semantic_search")

    def test_is_local_tool(self):
        assert is_local_tool("read_file")
        assert is_local_tool("terminal")
        assert not is_local_tool("deps_audit")
