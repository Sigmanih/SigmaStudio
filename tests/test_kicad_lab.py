# tests/test_kicad_lab.py — KiCad Lab: parser, bridge, cli, mcp_server
# ==============================================================================
"""Il modulo si prova senza KiCad installato per il parser e il bridge; i test
che richiedono kicad-cli sono marcati con skip se l'eseguibile non c'e'.

La strategia e' la stessa di test_eda_lab: gli algoritmi puri (placement,
evaluate, rules) sono gia' coperti dalla suite esistente e non vengono
ridondati qui. Qui si verifica che il parser legga correttamente le
S-expression, che il bridge traduca nel modello Board, e che il server MCP
esponga i tool con gli schema giusti.
"""
import json
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# =============================================================================
# Parser S-expression
# =============================================================================

class TestSExprParser(unittest.TestCase):
    """Il tokenizer e il parser di S-expression."""

    def test_tokenize_semplice(self):
        from core.modules.sigma_kicad_lab.kicad_parser import tokenize
        tokens = tokenize('(kicad_pcb (version 20240108))')
        assert tokens == ["(", "kicad_pcb", "(", "version", "20240108", ")", ")"]

    def test_tokenize_stringa_virgolettata(self):
        from core.modules.sigma_kicad_lab.kicad_parser import tokenize
        tokens = tokenize('(net 1 "GND")')
        assert tokens == ["(", "net", "1", '"GND"', ")"]

    def test_tokenize_stringa_con_escape(self):
        from core.modules.sigma_kicad_lab.kicad_parser import tokenize
        tokens = tokenize(r'(property "Value" "10k\"")')
        assert '"10k\\""' in tokens

    def test_parse_espressione_semplice(self):
        from core.modules.sigma_kicad_lab.kicad_parser import parse_sexpr
        result = parse_sexpr("(version 20240108)")
        assert result == [["version", "20240108"]]

    def test_parse_annidamento(self):
        from core.modules.sigma_kicad_lab.kicad_parser import parse_sexpr
        result = parse_sexpr("(a (b c) (d (e f)))")
        assert result == [["a", ["b", "c"], ["d", ["e", "f"]]]]

    def test_parse_stringa_dequotata(self):
        from core.modules.sigma_kicad_lab.kicad_parser import parse_sexpr
        result = parse_sexpr('(net 1 "GND")')
        assert result == [["net", "1", "GND"]]

    def test_parse_file_vuoto(self):
        from core.modules.sigma_kicad_lab.kicad_parser import parse_sexpr
        result = parse_sexpr("")
        assert result == []

    def test_parentesi_non_bilanciate(self):
        from core.modules.sigma_kicad_lab.kicad_parser import parse_sexpr
        with self.assertRaises(ValueError):
            parse_sexpr("(a (b)")   # manca una chiusura

    def test_parentesi_chiusa_senza_apertura(self):
        from core.modules.sigma_kicad_lab.kicad_parser import parse_sexpr
        with self.assertRaises(ValueError):
            parse_sexpr(")")


# =============================================================================
# Lettura PCB
# =============================================================================

# Un file .kicad_pcb minimale ma realistico
_MINI_PCB = textwrap.dedent("""\
    (kicad_pcb
      (version 20240108)
      (generator "pcbnew")
      (net 0 "")
      (net 1 "GND")
      (net 2 "VCC")
      (gr_line (start 0 0) (end 50 0) (layer "Edge.Cuts") (width 0.05))
      (gr_line (start 50 0) (end 50 40) (layer "Edge.Cuts") (width 0.05))
      (gr_line (start 50 40) (end 0 40) (layer "Edge.Cuts") (width 0.05))
      (gr_line (start 0 40) (end 0 0) (layer "Edge.Cuts") (width 0.05))
      (footprint "Resistor_SMD:R_0603_1608Metric"
        (at 10.5 20.3 90)
        (layer "F.Cu")
        (property "Reference" "R1")
        (property "Value" "10k")
        (pad "1" smd rect (at -0.825 0) (size 0.8 0.95)
          (layers "F.Cu" "F.Paste" "F.Mask")
          (net 1 "GND"))
        (pad "2" smd rect (at 0.825 0) (size 0.8 0.95)
          (layers "F.Cu" "F.Paste" "F.Mask")
          (net 2 "VCC")))
      (footprint "Capacitor_SMD:C_0402_1005Metric"
        (at 25.0 15.0)
        locked
        (layer "F.Cu")
        (property "Reference" "C1")
        (property "Value" "100nF")
        (pad "1" smd rect (at -0.5 0) (size 0.5 0.6)
          (layers "F.Cu" "F.Paste" "F.Mask")
          (net 1 "GND"))
        (pad "2" smd rect (at 0.5 0) (size 0.5 0.6)
          (layers "F.Cu" "F.Paste" "F.Mask")
          (net 2 "VCC"))))
""")


class TestReadPcb(unittest.TestCase):
    """Lettura di un file .kicad_pcb."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.pcb_file = self.tmp / "test.kicad_pcb"
        self.pcb_file.write_text(_MINI_PCB, encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_legge_dimensioni_scheda(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        self.assertAlmostEqual(info.width_mm, 50.0, places=1)
        self.assertAlmostEqual(info.height_mm, 40.0, places=1)

    def test_legge_net(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        nomi = {n.name for n in info.nets}
        assert "GND" in nomi
        assert "VCC" in nomi

    def test_legge_footprint(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        refs = {fp.reference for fp in info.footprints}
        assert "R1" in refs
        assert "C1" in refs

    def test_footprint_posizione(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        r1 = next(fp for fp in info.footprints if fp.reference == "R1")
        self.assertAlmostEqual(r1.x, 10.5, places=1)
        self.assertAlmostEqual(r1.y, 20.3, places=1)
        self.assertAlmostEqual(r1.rotation, 90.0, places=1)

    def test_footprint_locked(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        c1 = next(fp for fp in info.footprints if fp.reference == "C1")
        assert c1.locked is True
        r1 = next(fp for fp in info.footprints if fp.reference == "R1")
        assert r1.locked is False

    def test_pad_con_net(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        r1 = next(fp for fp in info.footprints if fp.reference == "R1")
        assert len(r1.pads) == 2
        net_names = {p.net_name for p in r1.pads}
        assert "GND" in net_names
        assert "VCC" in net_names

    def test_origine_board(self):
        from core.modules.sigma_kicad_lab.kicad_parser import read_pcb
        info = read_pcb(self.pcb_file)
        self.assertAlmostEqual(info.origin_x, 0.0, places=1)
        self.assertAlmostEqual(info.origin_y, 0.0, places=1)


# =============================================================================
# Bridge — da KiCad a modello Board
# =============================================================================

class TestBridge(unittest.TestCase):
    """Il bridge traduce KiCadBoardInfo in Board."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.pcb_file = self.tmp / "test.kicad_pcb"
        self.pcb_file.write_text(_MINI_PCB, encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_board_dimensioni(self):
        from core.modules.sigma_kicad_lab.bridge import read_board
        board = read_board(self.pcb_file)
        self.assertAlmostEqual(board.width, 50.0, places=1)
        self.assertAlmostEqual(board.height, 40.0, places=1)

    def test_read_board_componenti(self):
        from core.modules.sigma_kicad_lab.bridge import read_board
        board = read_board(self.pcb_file)
        assert "R1" in board.components
        assert "C1" in board.components

    def test_read_board_net(self):
        from core.modules.sigma_kicad_lab.bridge import read_board
        board = read_board(self.pcb_file)
        nomi = {n.name for n in board.nets}
        assert "GND" in nomi
        assert "VCC" in nomi

    def test_read_board_locked(self):
        from core.modules.sigma_kicad_lab.bridge import read_board
        board = read_board(self.pcb_file)
        assert board.components["C1"].locked is True
        assert board.components["R1"].locked is False

    def test_classify_net_gnd(self):
        from core.modules.sigma_kicad_lab.bridge import classify_net
        from core.modules.sigma_eda_lab.netlist import CLASS_GROUND
        assert classify_net("GND") == CLASS_GROUND
        assert classify_net("AGND") == CLASS_GROUND

    def test_classify_net_power(self):
        from core.modules.sigma_kicad_lab.bridge import classify_net
        from core.modules.sigma_eda_lab.netlist import CLASS_POWER
        assert classify_net("VCC") == CLASS_POWER
        assert classify_net("+3V3") == CLASS_POWER

    def test_classify_net_signal(self):
        from core.modules.sigma_kicad_lab.bridge import classify_net
        from core.modules.sigma_eda_lab.netlist import CLASS_SIGNAL
        assert classify_net("SPI_CLK") == CLASS_SIGNAL

    def test_find_project_files(self):
        from core.modules.sigma_kicad_lab.bridge import find_project_files
        # Crea file finti del progetto
        (self.tmp / "test.kicad_pro").write_text("{}", encoding="utf-8")
        (self.tmp / "test.kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        result = find_project_files(self.pcb_file)
        assert result["pcb"] == self.pcb_file
        assert result["pro"] == self.tmp / "test.kicad_pro"
        assert result["sch"] == self.tmp / "test.kicad_sch"


# =============================================================================
# Scrittura — modifica posizioni
# =============================================================================

class TestWritePositions(unittest.TestCase):
    """Riscrittura mirata delle posizioni nel file .kicad_pcb."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.pcb_file = self.tmp / "test.kicad_pcb"
        self.pcb_file.write_text(_MINI_PCB, encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_aggiorna_posizione_footprint(self):
        from core.modules.sigma_kicad_lab.kicad_parser import (
            update_footprint_position, read_pcb,
        )
        ok = update_footprint_position(self.pcb_file, "R1", 30.0, 25.0, 180.0)
        assert ok is True
        # Rileggi e verifica
        info = read_pcb(self.pcb_file)
        r1 = next(fp for fp in info.footprints if fp.reference == "R1")
        self.assertAlmostEqual(r1.x, 30.0, places=1)
        self.assertAlmostEqual(r1.y, 25.0, places=1)
        self.assertAlmostEqual(r1.rotation, 180.0, places=1)

    def test_footprint_non_trovato(self):
        from core.modules.sigma_kicad_lab.kicad_parser import update_footprint_position
        ok = update_footprint_position(self.pcb_file, "Q999", 10.0, 10.0)
        assert ok is False

    def test_apply_placement_dry_run(self):
        from core.modules.sigma_kicad_lab.bridge import read_board, apply_placement
        board = read_board(self.pcb_file)
        outcome = apply_placement(board, self.pcb_file, dry_run=True)
        assert outcome.dry_run is True
        # In dry_run non modifica il file
        testo_originale = self.pcb_file.read_text(encoding="utf-8")
        assert testo_originale == _MINI_PCB


# =============================================================================
# kicad-cli
# =============================================================================

class TestKiCadCli(unittest.TestCase):
    """Il wrapper kicad-cli: verifica che le funzioni esistano e gestiscano
    l'assenza di KiCad senza crash."""

    def test_find_kicad_cli_non_crasha(self):
        """find_kicad_cli restituisce None o un Path, mai un'eccezione."""
        from core.modules.sigma_kicad_lab.kicad_cli import find_kicad_cli
        result = find_kicad_cli()
        assert result is None or isinstance(result, Path)

    def test_require_kicad_cli_senza_kicad(self):
        """Se KiCad non c'e', solleva un errore chiaro."""
        from core.modules.sigma_kicad_lab.kicad_cli import (
            require_kicad_cli, KiCadCLIError,
        )
        with patch("core.modules.sigma_kicad_lab.kicad_cli.find_kicad_cli",
                    return_value=None):
            with self.assertRaises(KiCadCLIError) as ctx:
                require_kicad_cli()
            assert "non trovato" in str(ctx.exception)


# =============================================================================
# MCP Server — registrazione tool
# =============================================================================

class TestMCPServer(unittest.TestCase):
    """Il server MCP registra tutti i tool con gli schema giusti."""

    def test_tool_registrati(self):
        from core.modules.sigma_kicad_lab.mcp_server import KiCadLabMCPServer
        server = KiCadLabMCPServer()
        tools = server.list_tools()
        nomi = {t["name"] for t in tools}
        attesi = {
            "kicad_status", "kicad_board_read", "kicad_placement_optimize",
            "kicad_placement_apply", "kicad_board_evaluate",
            "kicad_trace_width", "kicad_drc", "kicad_erc",
            "kicad_export_gerbers", "kicad_export_bom",
        }
        assert attesi.issubset(nomi), f"Mancano: {attesi - nomi}"

    def test_placement_apply_e_sensitive(self):
        from core.modules.sigma_kicad_lab.mcp_server import KiCadLabMCPServer
        from core.mcp.governance import SENSITIVE
        server = KiCadLabMCPServer()
        tools = {t["name"]: t for t in server.list_tools()}
        assert tools["kicad_placement_apply"]["safety"] == SENSITIVE

    def test_tool_safe(self):
        from core.modules.sigma_kicad_lab.mcp_server import KiCadLabMCPServer
        from core.mcp.governance import SAFE
        server = KiCadLabMCPServer()
        tools = {t["name"]: t for t in server.list_tools()}
        for nome in ["kicad_status", "kicad_board_read", "kicad_drc",
                     "kicad_erc", "kicad_trace_width"]:
            assert tools[nome]["safety"] == SAFE, f"{nome} non e' SAFE"

    def test_trace_width_funziona(self):
        """Il tool trace_width non dipende da KiCad: usa solo la formula IPC."""
        from core.modules.sigma_kicad_lab.mcp_server import KiCadLabMCPServer
        server = KiCadLabMCPServer()
        result = server.call_tool("kicad_trace_width", {"current_a": 1.0})
        assert result.get("isError") is not True


# =============================================================================
# Handlers — registrazione nel kernel
# =============================================================================

class TestHandlers(unittest.TestCase):
    """Il modulo si registra senza errori e definisce le route HTTP."""

    def test_register_routes_con_app(self):
        from core.modules.sigma_kicad_lab.handlers import register_routes, ROUTES
        app = MagicMock()
        register_routes(app)
        assert app.add_api_route.call_count == len(ROUTES)
        assert len(ROUTES) >= 12

    def test_register_mcp_con_hub_finto(self):
        from core.modules.sigma_kicad_lab.handlers import register_mcp
        hub = MagicMock()
        register_mcp(hub)
        hub.register_server.assert_called_once()

    def test_create_empty_project(self):
        import tempfile
        from core.modules.sigma_kicad_lab.kicad_parser import create_empty_project, read_pcb, board_to_dict
        with tempfile.TemporaryDirectory() as tmpdir:
            res = create_empty_project(Path(tmpdir), "test_board", width_mm=70.0, height_mm=50.0)
            assert Path(res["pro_path"]).is_file()
            assert Path(res["sch_path"]).is_file()
            assert Path(res["pcb_path"]).is_file()

            # Verifica che il PCB generato sia leggibile da read_pcb
            info = read_pcb(Path(res["pcb_path"]))
            assert abs(info.width_mm - 70.0) < 0.1
            assert abs(info.height_mm - 50.0) < 0.1

            # Verifica serializzazione board_to_dict
            d = board_to_dict(info)
            assert d["width_mm"] == 70.0
            assert d["height_mm"] == 50.0


if __name__ == "__main__":
    unittest.main()
