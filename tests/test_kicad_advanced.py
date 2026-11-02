"""Gli endpoint nuovi devono produrre artefatti reali e rifiutare verdetti vecchi."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.modules.sigma_kicad_lab import tools as K, kicad_cli as C, pcbnew_bridge as B


@pytest.fixture
def board(tmp_path):
    if not B.disponibile().get("ok"):
        pytest.skip("KiCad/pcbnew non disponibile: integrazione nativa non verificata.")
    path = tmp_path / "board.kicad_pcb"
    made = B.crea_scheda(str(path), larghezza_mm=50, altezza_mm=40)
    assert made["ok"], made
    added = B.aggiungi_componente(str(path), libreria="Resistor_SMD", footprint="R_0603_1608Metric",
                                 riferimento="R1", valore="10k", x_mm=10, y_mm=10,
                                 net_per_pad={"1": "GND", "2": "VCC"})
    assert added["ok"], added
    assert K.kicad_open(str(path))["success"]
    return path


@pytest.mark.parametrize("name,args", [
    ("kicad_constructor_hole", {"reference": "H1", "x_mm": 4, "y_mm": 4}),
    ("kicad_constructor_fiducial", {"reference": "FID1", "x_mm": 4, "y_mm": 4}),
    ("kicad_constructor_testpoint", {"reference": "TP1", "x_mm": 4, "y_mm": 4, "net": "GND"}),
    ("kicad_constructor_silkscreen", {"text": "SIGMA", "x_mm": 4, "y_mm": 4}),
    ("kicad_zone_add", {"points": [[1, 1], [45, 1], [45, 35], [1, 35]], "net": "GND"}),
])
def test_modifica_nativa_si_rilegge_e_si_puo_annullare(board, name, args):
    before = board.read_bytes()
    result = K.esegui(name, args)
    assert result["success"], result
    assert Path(result["backup"]).read_bytes() == before
    after = board.read_bytes()
    assert before != after
    if "reference" in args:
        assert args["reference"].encode() in after
    elif name == "kicad_constructor_silkscreen":
        assert b'SIGMA' in after
    else:
        assert b"(zone" in after
    assert B.leggi_scheda(str(board))["ok"]
    assert K.kicad_undo()["success"]
    assert board.read_bytes() == before
    assert K.kicad_redo()["success"]
    assert board.read_bytes() == after


def test_nuova_scrittura_invalida_redo(board):
    assert K.kicad_add_track([1, 1], [2, 2], 0.25)["success"]
    assert K.kicad_undo()["success"]
    assert K.kicad_add_track([3, 3], [4, 4], 0.25)["success"]
    assert not K.kicad_redo()["success"]


def test_regole_e_classi_preservano_la_configurazione_del_progetto(board):
    project = board.with_suffix(".kicad_pro")
    project.write_text(json.dumps({"meta": {"version": 1}, "sentinella": {"dato": 7}}), encoding="utf-8")
    assert K.kicad_open(str(board))["success"]
    result = K.esegui("kicad_netclass_set", {"name": "Power", "track_width_mm": 0.8, "net_pattern": "VCC*"})
    assert result["success"], result
    data = json.loads(project.read_text())
    assert data["sentinella"] == {"dato": 7}
    assert data["net_settings"]["classes"][0]["track_width"] == 0.8
    assert Path(result["backup"]).is_file()
    rules = '(version 1)\n(rule "clearance" (constraint clearance (min 0.25mm)))\n'
    result = K.esegui("kicad_rules_set", {"rules": rules})
    assert result["success"], result
    assert board.with_suffix(".kicad_dru").read_text() == rules


def test_netlist_sincronizza_i_pad_e_non_simula_componenti(board):
    path = board.with_suffix(".xml")
    path.write_text('<export><nets><net name="NUOVA"><node ref="R1" pin="1"/></net></nets></export>', encoding="utf-8")
    result = K.esegui("kicad_sync_netlist", {"netlist_path": str(path)})
    assert result["success"], result
    assert "NUOVA" in B.leggi_scheda(str(board))["net"]
    before = board.read_bytes()
    path.write_text('<export><nets><net name="X"><node ref="ASSENTE" pin="1"/></net></nets></export>', encoding="utf-8")
    assert not K.esegui("kicad_sync_netlist", {"netlist_path": str(path)})["success"]
    assert board.read_bytes() == before


def test_export_reali_producono_file(board, tmp_path):
    result = K.esegui("kicad_export_pickplace", {"output_path": str(tmp_path / "assembly.csv")})
    assert result["success"] and Path(result["output_path"]).is_file(), result
    result = K.esegui("kicad_export_gerbers", {"output_dir": str(tmp_path / "gerbers")})
    assert result["success"], result
    assert result["gerbers"]["files"]
    assert result["drill"]["files"]
    rendered = C.render_3d(board, tmp_path / "board.png", width=160, height=100)
    assert rendered["success"], rendered
    assert (tmp_path / "board.png").read_bytes().startswith(b"\x89PNG")


@pytest.mark.parametrize("kind", ["run_drc", "run_erc"])
def test_un_report_vecchio_non_prova_una_verifica_nuova(tmp_path, monkeypatch, kind):
    source = tmp_path / "board.kicad_pcb"
    source.write_text("prova")
    old = tmp_path / "report.json"
    old.write_text('{"violations": []}')
    monkeypatch.setattr(C, "require_kicad_cli", lambda: Path("kicad-cli"))
    monkeypatch.setattr(C, "_run", lambda *a: SimpleNamespace(returncode=0))
    with pytest.raises(C.KiCadCLIError, match="non ha prodotto"):
        getattr(C, kind)(source, old)
    assert json.loads(old.read_text()) == {"violations": []}


def test_drc_conta_anche_connessioni_mancanti(tmp_path, monkeypatch):
    source = tmp_path / "board.kicad_pcb"
    source.write_text("prova")
    monkeypatch.setattr(C, "require_kicad_cli", lambda: Path("kicad-cli"))

    def run(command, operation):
        Path(command[command.index("-o") + 1]).write_text(json.dumps({"violations": [],
            "unconnected_items": [{"severity": "error"}]}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(C, "_run", run)
    result = C.run_drc(source)
    assert not result["success"] and result["total_errors"] == 1


def test_due_richieste_http_non_si_scambiano_il_progetto(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.modules.sigma_kicad_lab.handlers import _route_per_tool

    paths = [tmp_path / "uno.kicad_pcb", tmp_path / "due.kicad_pcb"]
    for path in paths:
        path.write_text("(kicad_pcb)")
    barrier = threading.Barrier(2, timeout=5)
    before = dict(K._progetto)

    def inspect():
        barrier.wait()
        return {"success": True, "path": str(K._pcb())}

    monkeypatch.setitem(K.ESECUTORI, "kicad_board_read", inspect)
    app = FastAPI()
    app.add_api_route("/read", _route_per_tool("kicad_board_read"), methods=["POST"])

    def request(path):
        with TestClient(app) as client:
            response = client.post("/read", json={"project": str(path)})
            assert response.status_code == 200
            return response.json()["path"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(request, paths)) == [str(path) for path in paths]
    assert K._progetto == before


def test_creazione_del_template_non_sovrascrive_il_lavoro(tmp_path):
    from core.modules.sigma_kicad_lab.kicad_parser import create_empty_project
    result = create_empty_project(tmp_path, "progetto")
    original = {key: Path(value).read_bytes() for key, value in result.items() if key.endswith("_path")}
    with pytest.raises(FileExistsError):
        create_empty_project(tmp_path, "progetto", width_mm=100)
    assert all(Path(result[key]).read_bytes() == content for key, content in original.items())
    if B.disponibile().get("ok"):
        assert B.leggi_scheda(result["pcb_path"])["ok"]
        assert C.run_drc(Path(result["pcb_path"]))["ok"]
        assert C.run_erc(Path(result["sch_path"]))["ok"]


def test_mcp_pubblica_solo_esecutori_reali_e_classifica_le_scritture():
    from core.modules.sigma_kicad_lab.mcp_server import KiCadLabMCPServer
    from core.mcp.governance import SENSITIVE
    entries = {entry["name"]: entry for entry in KiCadLabMCPServer().list_tools()}
    assert set(entries) == set(K.ESECUTORI) | {"kicad_open_project"}
    assert all(entries[name]["safety"] == SENSITIVE for name in K.WRITE_TOOLS)


def test_registrazione_mcp_consegna_un_istanza():
    from core.modules.sigma_kicad_lab.handlers import register_mcp
    from core.mcp.base_server import BaseMCPServer
    received = []
    register_mcp(SimpleNamespace(register_server=received.append))
    assert len(received) == 1 and isinstance(received[0], BaseMCPServer)


def test_un_componente_senza_net_non_viene_collegato_a_massa(tmp_path):
    if not B.disponibile().get("ok"):
        pytest.skip("KiCad/pcbnew non disponibile.")
    path = tmp_path / "libera.kicad_pcb"
    assert B.crea_scheda(str(path), larghezza_mm=40, altezza_mm=30)["ok"]
    result = K.kicad_add_part(percorso=str(path), libreria="Resistor_SMD",
                              footprint="R_0603_1608Metric", riferimento="R1", net_per_pad={})
    assert result["success"], result
    assert B.leggi_scheda(str(path))["net"] == []


def test_erc_non_perde_gli_errori_dei_singoli_fogli(tmp_path, monkeypatch):
    source = tmp_path / "project.kicad_sch"
    source.write_text("prova")
    monkeypatch.setattr(C, "require_kicad_cli", lambda: Path("kicad-cli"))

    def run(command, operation):
        Path(command[command.index("-o") + 1]).write_text(json.dumps({"sheets": [
            {"path": "/", "violations": []}, {"path": "/power", "violations": [{"severity": "error"}]}]}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(C, "_run", run)
    report = C.run_erc(source)
    assert report["total_errors"] == 1 and not report["success"]


def test_aprire_una_scheda_non_associa_uno_schematico_estraneo(tmp_path):
    board = tmp_path / "uno.kicad_pcb"
    board.write_text("(kicad_pcb)")
    (tmp_path / "due.kicad_sch").write_text("(kicad_sch)")
    assert K.kicad_open(str(board))["success"]
    assert K._project()["sch"] is None
    (tmp_path / "due.kicad_pcb").write_text("(kicad_pcb)")
    assert not K.kicad_open(str(tmp_path))["success"]
