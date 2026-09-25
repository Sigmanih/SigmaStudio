# ==============================================================================
# tests/test_kicad_edit_tools.py — Correggere una scheda, non solo crearla
# ==============================================================================
"""Un layout si popola una volta e si corregge cento: e' qui che si lavora.

Aggiungere un pezzo, tracciare una pista e mettere un via erano le uniche
operazioni di scrittura che esistevano fino al 25 settembre 2026. Non c'era modo
di spostare un piedino di due millimetri, di rinominare `R1` in `R7`, di
cancellare una pista tracciata su una net, di cambiare la net di un pad. Chi
sbagliava poteva solo togliere il pezzo e rimetterlo, e per una pista non poteva
niente: la scheda restava con del rame che non collegava niente.

Qui si prova ognuna delle sei operazioni di correzione, e si prova che cosa
succede quando non si puo' fare: un pezzo che non c'e', un nome gia' occupato,
una pista che non e' dove la si cerca. La geometria si prova sulla carta perche'
e' l'unica cosa che non si vede: una pista tracciata alle coordinate sbagliate e'
un file che si apre senza proteste e una scheda che non funziona.
"""
import textwrap
from pathlib import Path

import pytest

from core.harness.roles import DEV_ROLES
from core.modules.sigma_kicad_lab import tools as K

# Il modulo si aggancia da solo all'avvio, quando il module loader chiama
# `register_harness_tools()`: una prova che importa direttamente deve chiederlo.
K.registra()

#: Due pezzi, una pista, un via, un contorno. Il minimo per poter sbagliare.
PCB = textwrap.dedent("""\
    (kicad_pcb
      (version 20240108)
      (generator "pcbnew")
      (net 0 "")
      (net 1 "GND")
      (net 2 "VCC")
      (gr_line (start 0 0) (end 50 0) (layer "Edge.Cuts") (stroke (width 0.05) (type solid)))
      (gr_line (start 50 0) (end 50 40) (layer "Edge.Cuts") (stroke (width 0.05) (type solid)))
      (gr_line (start 50 40) (end 0 40) (layer "Edge.Cuts") (stroke (width 0.05) (type solid)))
      (gr_line (start 0 40) (end 0 0) (layer "Edge.Cuts") (stroke (width 0.05) (type solid)))
      (segment (start 5 5) (end 5 15) (width 0.25) (layer "F.Cu") (net 1))
      (via (at 5 15) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 1))
      (footprint "Resistor_SMD:R_0603_1608Metric"
        (at 10.5 20.3 90)
        (layer "F.Cu")
        (property "Reference" "R1")
        (property "Value" "10k")
        (pad "1" smd rect (at -0.825 0) (size 0.8 0.95)
          (layers "F.Cu" "F.Paste" "F.Mask")
          (net 1 "GND"))
        (pad "2" smd rect (at 0.825 0) (size 0.8 0.95)
          (layers "F.Cu" "F.Paste" "F.Mask")))
      (footprint "Capacitor_SMD:C_0402_1005Metric"
        (at 20 20)
        (layer "F.Cu")
        (property "Reference" "C1")
        (property "Value" "100nF")
        (pad "1" smd rect (at -0.5 0) (size 0.5 0.6)
          (layers "F.Cu" "F.Paste" "F.Mask")))
    )
    """)


@pytest.fixture
def scheda(tmp_path) -> Path:
    """Un progetto aperto su una scheda di prova, nuovo a ogni prova."""
    percorso = tmp_path / "prova.kicad_pcb"
    percorso.write_text(PCB, encoding="utf-8")
    apertura = K.kicad_open(str(percorso))
    assert apertura["success"], apertura
    K._ultimo_backup.pop(str(percorso), None)
    return percorso


def _testo(scheda: Path) -> str:
    return scheda.read_text(encoding="utf-8")


# --- spostare e ruotare -------------------------------------------------------

def test_move_cambia_la_posizione_e_lascia_i_pad(scheda):
    esito = K.kicad_move_footprint("R1", 20, 30, 45)
    assert esito["success"], esito
    assert esito["x_mm"] == 20 and esito["y_mm"] == 30
    testo = _testo(scheda)
    assert "(at 20 30 45)" in testo
    # I pad sono posizioni relative al pezzo: spostarlo non li tocca.
    assert "(at -0.825 0)" in testo
    assert "(at 0.825 0)" in testo


def test_move_senza_rotazione_non_raddrizza(scheda):
    """Un trascinamento non deve raddrizzare un pezzo ruotato apposta."""
    K.kicad_move_footprint("R1", 12, 22)
    assert "(at 12 22 90)" in _testo(scheda)


def test_move_di_un_pezzo_inesistente_non_tocca_il_file(scheda):
    prima = _testo(scheda)
    esito = K.kicad_move_footprint("U9", 1, 1)
    assert esito["success"] is False
    assert "U9" in esito["error"]
    assert _testo(scheda) == prima


# --- rinominare ---------------------------------------------------------------

def test_rename_cambia_riferimento_e_valore(scheda):
    esito = K.kicad_rename_footprint("R1", "R7", "22k")
    assert esito["success"], esito
    testo = _testo(scheda)
    assert '(property "Reference" "R7")' in testo
    assert '(property "Value" "22k")' in testo
    assert '(property "Reference" "R1")' not in testo


def test_rename_verso_un_nome_occupato_viene_rifiutato(scheda):
    esito = K.kicad_rename_footprint("R1", "C1")
    assert esito["success"] is False
    assert "C1" in esito["error"]
    assert '(property "Reference" "R1")' in _testo(scheda)


# --- cancellare rame ----------------------------------------------------------

def test_delete_track_riconosce_gli_estremi_al_contrario(scheda):
    esito = K.kicad_delete_track([5, 15], [5, 5])
    assert esito["success"], esito
    assert "(segment" not in _testo(scheda)
    # Il via che stava in cima alla pista non c'entra: resta dov'e'.
    assert "(via" in _testo(scheda)


def test_delete_track_che_non_c_e_dice_quale_si_avvicina(scheda):
    esito = K.kicad_delete_track([40, 40], [41, 41])
    assert esito["success"] is False
    assert "5, 5" in esito["error"], esito["error"]
    assert "(segment" in _testo(scheda)


def test_delete_track_chiede_il_layer_giusto(scheda):
    esito = K.kicad_delete_track([5, 5], [5, 15], layer="B.Cu")
    assert esito["success"] is False
    assert "(segment" in _testo(scheda)


def test_delete_via_tollera_il_clic_vicino(scheda):
    esito = K.kicad_delete_via([5.02, 14.98])
    assert esito["success"], esito
    assert "(via" not in _testo(scheda)


# --- contorno -----------------------------------------------------------------

def test_il_contorno_si_sostituisce_non_si_aggiunge(scheda):
    esito = K.kicad_set_board_outline(60, 40)
    assert esito["success"], esito
    assert esito["removed_lines"] == 4
    testo = _testo(scheda)
    assert testo.count('"Edge.Cuts"') == 4, "il contorno vecchio e' rimasto sotto"
    assert "(end 50 0)" not in testo
    assert "(end 60 0)" in testo


# --- net dei pad --------------------------------------------------------------

def test_set_pad_net_scrive_la_net_dentro_il_pad(scheda):
    esito = K.kicad_set_pad_net("R1", "2", "VCC")
    assert esito["success"], esito
    assert esito["net_number"] == 2
    testo = _testo(scheda)
    assert '(net 2 "VCC")' in testo
    # La net sta nel pad, non dopo: fuori dal nodo non apparterrebbe a nessuno.
    assert '(layers "F.Cu" "F.Paste" "F.Mask") (net 2 "VCC"))' in testo


def test_set_pad_net_sostituisce_quella_che_c_era(scheda):
    K.kicad_set_pad_net("R1", "1", "VCC")
    testo = _testo(scheda)
    assert testo.count('"VCC"') == 2, "la net vecchia del pad non e' stata tolta"


def test_set_pad_net_su_un_pad_inesistente_elenca_i_pad(scheda):
    esito = K.kicad_set_pad_net("R1", "9", "GND")
    assert esito["success"] is False
    assert "1" in esito["error"] and "2" in esito["error"]


def test_set_pad_net_crea_la_net_che_non_esiste(scheda):
    esito = K.kicad_set_pad_net("C1", "1", "+3V3")
    assert esito["success"], esito
    assert '(net 3 "+3V3")' in _testo(scheda)


# --- annullare ----------------------------------------------------------------

def test_undo_riporta_la_scheda_com_era(scheda):
    K.kicad_move_footprint("R1", 33, 33, 180)
    assert "(at 33 33 180)" in _testo(scheda)
    esito = K.kicad_undo()
    assert esito["success"], esito
    assert _testo(scheda) == PCB


# --- il contratto con il kernel ----------------------------------------------

NUOVE = ("kicad_move_footprint", "kicad_rename_footprint",
         "kicad_delete_track", "kicad_delete_via",
         "kicad_set_board_outline", "kicad_set_pad_net")


def test_le_nuove_operazioni_sono_dichiarate_e_classificate():
    from core.harness import policy, tool_providers, tool_schema

    for nome in NUOVE:
        assert nome in K.ESECUTORI, f"{nome} non ha un esecutore"
        assert callable(K.ESECUTORI[nome])
        assert nome in K.WRITE_TOOLS, f"{nome} non e' dichiarato fra le scritture"
        assert nome not in K.READ_TOOLS
        assert nome not in policy.READ_ONLY_TOOLS, (
            f"{nome} scrive: in sola lettura non deve passare")
        assert tool_providers.owner(nome) == "sigma_kicad_lab"
        assert len(tool_schema.schemas_for([nome])) == 1, f"{nome} senza schema"


def test_le_nuove_operazioni_sono_concesse_al_ruolo():
    ruolo = DEV_ROLES["kicad_engineer"]
    for nome in NUOVE:
        assert nome in ruolo.tools, f"{nome} non concesso a kicad_engineer"
