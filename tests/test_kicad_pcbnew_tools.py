"""Test dei sei tool pcbnew bridge esposti all'harness.

Questi test NON si saltano se KiCad non e' disponibile: su questa macchina
KiCad c'e', e un test che si salta da solo renderebbe verde una suite che
non ha verificato niente. Se il ponte non parte, il test deve fallire.
"""
import pytest

from core.harness import policy as pol
from core.harness import tool_schema as ts
from core.harness.roles import DEV_ROLES
from core.modules.sigma_kicad_lab import pcbnew_bridge as pcb
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


# --- 6. l'indice dei footprint: la ricerca non riapre le librerie ogni volta --

def test_la_ricerca_arriva_dall_indice():
    """Cercare non deve costare una scansione di 155 librerie.

    Misurato su KiCad 10.0.6 prima e dopo l'indice: 5,63 s a ogni ricerca,
    poi 1,0 ms in memoria e 7,0 ms da un processo nuovo (indice su disco da
    15.450 voci).
    """
    indice = pcb.indice_footprint()
    assert indice["ok"] is True, indice
    assert indice["totale"] > 1000, f"indice sospetto: {indice['totale']} voci"
    assert indice["librerie"] > 50, indice["librerie"]

    trovato = pcb.cerca_footprint("R_0805", limite=5)
    assert trovato["ok"] is True, trovato
    assert trovato["risultati"], "l'indice non ha trovato un footprint che c'e'"
    assert trovato["da_indice"] is True, (
        "la ricerca e' tornata al sottoprocesso KiCad: l'indice non e' innestato"
    )


def test_a_pari_merito_vince_il_nome_esatto():
    """Chi scrive il nome intero vuole quello, non una variante piu' lunga."""
    trovato = pcb.cerca_footprint("R_0805_2012Metric", limite=5)
    primo = trovato["risultati"][0]["footprint"]
    assert primo == "R_0805_2012Metric", (
        f"il primo risultato e' '{primo}': l'ordine e' tornato alfabetico, e "
        "una variante HandSolder scavalca il nome chiesto"
    )


def test_il_lato_bottom_ribalta_il_pezzo(tmp_path):
    """Un SMD sul lato inferiore e' la norma su una scheda densa."""
    percorso = str(tmp_path / "sotto.kicad_pcb")
    assert kt.kicad_new_board(percorso=percorso, larghezza_mm=40,
                              altezza_mm=30)["success"] is True

    esito = kt.kicad_add_part(
        percorso=percorso, libreria="Resistor_SMD",
        footprint="R_0805_2012Metric", riferimento="R1", valore="10k",
        x_mm=10.0, y_mm=10.0, lato="bottom")
    assert esito["success"] is True, esito
    assert esito["lato"] == "bottom", esito

    riletta = kt.kicad_read_board_full(percorso=percorso)
    assert riletta["success"] is True, riletta
    pezzo = riletta["componenti"][0]
    # La posizione non deve essersi mossa col ribaltamento: il pezzo cambia
    # lato, non posto — altrimenti un inserimento sposta lavoro gia' fatto.
    assert pezzo["lato"] == "bottom", pezzo
    assert (pezzo["x_mm"], pezzo["y_mm"]) == (10.0, 10.0), pezzo


def test_un_rifiuto_non_torna_come_successo(tmp_path):
    """Il rifiuto del lavoratore deve arrivare come errore, non come successo.

    `_esito` scartava la chiave `ok` dei payload di pcbnew e teneva il proprio
    `riuscito`: un riferimento gia' usato usciva come `success: true`, e un
    agente che legge un successo non riprova.
    """
    percorso = str(tmp_path / "doppio.kicad_pcb")
    assert kt.kicad_new_board(percorso=percorso, larghezza_mm=40,
                              altezza_mm=30)["success"] is True
    primo = kt.kicad_add_part(percorso=percorso, libreria="Resistor_SMD",
                              footprint="R_0805_2012Metric", riferimento="R7",
                              valore="10k", x_mm=5.0, y_mm=5.0)
    assert primo["success"] is True, primo

    bis = kt.kicad_add_part(percorso=percorso, libreria="Resistor_SMD",
                            footprint="R_0805_2012Metric", riferimento="R7",
                            valore="10k", x_mm=10.0, y_mm=5.0)
    assert bis["success"] is False, (
        f"un riferimento gia' usato e' tornato come successo: {bis}")
    assert bis.get("error"), bis
