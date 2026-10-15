# ==============================================================================
# tests/test_developer_graph.py — Verifica del costruttore del Grafo D3
# ==============================================================================
from pathlib import Path
from core.modules.sigma_developer_lab.graph_builder import build_workspace_graph


def test_build_workspace_graph_structure():
    """Verifica che il grafo del workspace restituisca nodi, link gerarchici e branch."""
    res = build_workspace_graph("core/engine", max_depth=2)
    assert res.get("success") is True
    assert "nodes" in res
    assert "links" in res
    assert "git_branch" in res
    assert len(res["nodes"]) > 0

    # Verifica presenza categorie e flag
    categories = {n["category"] for n in res["nodes"]}
    assert "code" in categories or "folder" in categories

    # Verifica che i link abbiano source e target
    if res["links"]:
        link = res["links"][0]
        assert "source" in link
        assert "target" in link
        assert "type" in link


def test_build_workspace_graph_invalid_path():
    """Verifica comportamento protetto su percorsi inesistenti."""
    res = build_workspace_graph("cartella_inesistente_xyz_123", max_depth=1)
    assert res.get("success") is False
    assert "error" in res
