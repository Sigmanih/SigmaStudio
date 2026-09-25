"""Test dei sei tool pcbnew bridge esposti all'harness.

Questi test NON si saltano se KiCad non e' disponibile: su questa macchina
KiCad c'e', e un test che si salta da solo renderebbe verde una suite che
non ha verificato niente. Se il ponte non parte, il test deve fallire.
"""
import pytest

from core.harness import policy as pol
from core.harness import tool_schema as ts
from core.harness.roles import DEV_ROLES
from core.modules.sigma_kicad_lab import tools as kt

# Come in `test_kicad_harness_tools`: la registrazione la fa il module loader
# all'avvio, e una prova che importa il modulo direttamente deve chiederla.
kt.registra()

SEI = [
    "kicad_pcbnew_status",
    "kicad_libraries",
    "kicad_search_footprint",
    "kicad_new_board",
    "kicad_add_part",
    "kicad_read_board_full",
]


# --- 1. i sei tool sono dichiarati E hanno un esecutore ----------------------

def test_sei_tool_dichiarati_e_esecutori():
    for nome in SEI:
        assert nome in kt.ESECUTORI, f"{nome} non e' in ESECUTORI"
        assert callable(kt.ESECUTORI[nome])


def test_elenchi_coincidono():
    """Ogni tool dichiarato ha un esecutore e viceversa."""
    dichiarati = set(SEI)
    esecutori = {n for n in kt.ESECUTORI if n.startswith("kicad_")}
    assert dichiarati <= esecutori


# --- 2. ogni tool concesso al ruolo ha uno schema ----------------------------

def test_ogni_tool_del_ruolo_ha_schema():
    ruolo = DEV_ROLES["kicad_engineer"]
    tools = ruolo.tools
    for nome in SEI:
        assert nome in tools, f"{nome} non concesso al ruolo kicad_engineer"
    schemi = ts.schemas_for(tools)
    assert len(schemi) == len(tools), (
        f"schemi={len(schemi)} tools={len(tools)}: manca uno schema")


# --- 3. letture in READ_ONLY_TOOLS, scritture no -----------------------------

def test_classificazione_read_write():
    letture = {"kicad_pcbnew_status", "kicad_libraries",
               "kicad_search_footprint", "kicad_read_board_full"}
    scritture = {"kicad_new_board", "kicad_add_part"}
    for nome in letture:
        assert nome in kt.READ_TOOLS, f"{nome} non in READ_TOOLS"
        assert nome in pol.READ_ONLY_TOOLS, f"{nome} non in READ_ONLY_TOOLS"
        assert nome not in kt.WRITE_TOOLS
    for nome in scritture:
        assert nome in kt.WRITE_TOOLS, f"{nome} non in WRITE_TOOLS"
        assert nome not in pol.READ_ONLY_TOOLS
        assert nome not in kt.READ_TOOLS


def test_aliases_contengono_sei():
    for nome in SEI:
        assert pol.ALIASES.get(nome) == nome, f"alias mancante per {nome}"


# --- 4. giro vero: crea scheda, aggiungi componente, rileggi -----------------

def test_giro_vero_scheda(tmp_path):
    percorso = str(tmp_path / "scheda.kicad_pcb")
    r1 = kt.kicad_new_board(percorso=percorso, larghezza_mm=50.0,
                            altezza_mm=40.0)
    assert r1["success"] is True, r1
    assert r1["tool"] == "kicad_new_board"

    r2 = kt.kicad_add_part(
        percorso=percorso, libreria="Capacitor_SMD",
        footprint="C_0805_2012Metric", riferimento="C1", valore="100nF",
        x_mm=10.0, y_mm=10.0, rotazione=0.0,
        net_per_pad={"1": "GND", "2": "VCC"})
    assert r2["success"] is True, r2
    assert r2["tool"] == "kicad_add_part"

    r3 = kt.kicad_read_board_full(percorso=percorso)
    assert r3["success"] is True, r3
    assert r3["tool"] == "kicad_read_board_full"
    # il componente deve essere ritrovato nella scheda
    testo = str(r3)
    assert "C1" in testo, f"componente C1 non ritrovato: {testo[:400]}"


# --- 5. sinonimi funzionano --------------------------------------------------

def test_sinonimi_ref_e_riferimento(tmp_path):
    percorso = str(tmp_path / "scheda2.kicad_pcb")
    assert kt.kicad_new_board(percorso=percorso, larghezza_mm=30,
                              altezza_mm=20)["success"] is True

    # stessa chiamata con 'ref' e con 'riferimento': devono dare lo stesso esito
    a = kt.esegui("kicad_add_part", {
        "percorso": percorso, "libreria": "Capacitor_SMD",
        "footprint": "C_0805_2012Metric", "ref": "C9", "valore": "10nF",
        "x": 5.0, "y": 5.0})
    b = kt.esegui("kicad_add_part", {
        "percorso": percorso, "libreria": "Capacitor_SMD",
        "footprint": "C_0805_2012Metric", "riferimento": "C10", "valore": "10nF",
        "x_mm": 6.0, "y_mm": 6.0})
    assert a["success"] is True, a
    assert b["success"] is True, b
    assert a["tool"] == b["tool"] == "kicad_add_part"


def test_sinonimi_path_e_lib(tmp_path):
    percorso = str(tmp_path / "scheda3.kicad_pcb")
    r = kt.esegui("kicad_new_board", {
        "path": percorso, "width": 25.0, "height": 20.0})
    assert r["success"] is True, r

    s = kt.esegui("kicad_search_footprint", {"q": "C_0805", "lib": "Capacitor_SMD"})
    assert s["success"] is True, s
