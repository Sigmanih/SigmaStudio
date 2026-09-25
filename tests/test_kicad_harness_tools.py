# ==============================================================================
# tests/test_kicad_harness_tools.py — I tool KiCad visti dall'harness
# ==============================================================================
"""Perche' una squadra di agenti possa progettare una scheda servono tre cose,
e si provano tutte senza aprire KiCad.

La prima e' che i tool esistano davvero per il modello: dichiarati, smistati,
concessi al ruolo. Prima di questo file il ruolo `kicad_engineer` ne concedeva
dieci che nessuno aveva mai scritto, e un agente li avrebbe chiamati nel vuoto.

La seconda e' che le scritture rifiutino cio' che non ha senso *prima* di
toccare il file. Un via col foro piu' largo del diametro, una pista su un layer
che non e' di rame, due pezzi con lo stesso riferimento: sono file che KiCad
riapre senza protestare e schede che non funzionano.

La terza e' la geometria. Un pad in posizione sbagliata non fa fallire niente:
produce coordinate plausibili verso cui si traccia rame che non collega. E' il
difetto che questo file guarda piu' da vicino, perche' e' l'unico che non si
vede.
"""
import textwrap

import pytest

from core.harness import policy
from core.harness.roles import DEV_ROLES
from core.harness.tool_schema import TOOL_SCHEMAS, schemas_for
from core.modules.sigma_kicad_lab import kicad_parser as parser
from core.modules.sigma_kicad_lab import pcb_writer
from core.modules.sigma_kicad_lab import tools as K

# Il modulo si aggancia da solo all'avvio, quando il module loader chiama
# `register_harness_tools()`. Una prova importa il codice senza passare di li',
# quindi la registrazione si chiede qui: senza, gli schemi dei tool e i permessi
# di lettura non esisterebbero e la prova misurerebbe un sistema che non c'e'.
K.registra()


PCB_PROVA = textwrap.dedent("""\
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


@pytest.fixture
def scheda(tmp_path):
    """Un .kicad_pcb usa e getta, con il progetto gia' aperto sui tool."""
    pcb = tmp_path / "prova.kicad_pcb"
    pcb.write_text(PCB_PROVA, encoding="utf-8")
    K.kicad_open(str(tmp_path))
    return pcb


# ---------------------------------------------------------------------------
# La geometria — il difetto che non si vede
# ---------------------------------------------------------------------------

class TestRotazioneDeiPad:
    """In un file KiCad l'asse Y punta in basso, mentre l'angolo di
    `(at x y angolo)` e' antiorario come lo vede chi guarda. Le due convenzioni
    insieme danno una rotazione ORARIA nelle coordinate del file.

    Con la rotazione antioraria dei libri di testo i pad di ogni componente
    ruotato finivano specchiati intorno al proprio centro. Le coordinate
    restavano plausibili e dentro la scheda: nessuna lettura se ne accorgeva, e
    ogni pista tracciata verso quei pad sarebbe atterrata su quello sbagliato.

    Il numero qui sotto non e' calcolato da noi: e' dove il DRC di KiCad dice
    che sta il pad 1 di R1."""

    def test_pad_ruotato_concorda_con_kicad(self, scheda):
        pads = {p["number"]: p for p in K.kicad_pads("R1")["pads"]}
        assert pads["1"]["net"] == "GND"
        assert pads["1"]["x"] == pytest.approx(10.5, abs=1e-3)
        assert pads["1"]["y"] == pytest.approx(21.125, abs=1e-3)

    def test_i_due_pad_non_sono_scambiati(self, scheda):
        pads = {p["number"]: p for p in K.kicad_pads("R1")["pads"]}
        assert pads["2"]["y"] == pytest.approx(19.475, abs=1e-3)
        assert pads["1"]["y"] > pads["2"]["y"]

    def test_senza_rotazione_l_offset_resta_tale(self, scheda):
        pads = {p["number"]: p for p in K.kicad_pads("C1")["pads"]}
        assert pads["1"]["x"] == pytest.approx(24.5, abs=1e-3)
        assert pads["2"]["x"] == pytest.approx(25.5, abs=1e-3)
        assert pads["1"]["y"] == pytest.approx(15.0, abs=1e-3)

    @pytest.mark.parametrize("angolo,atteso", [
        (0, (9.675, 20.3)), (90, (10.5, 21.125)),
        (180, (11.325, 20.3)), (270, (10.5, 19.475)),
    ])
    def test_i_quattro_angoli_ortogonali(self, tmp_path, angolo, atteso):
        """Il pad 1 gira in senso orario nelle coordinate del file."""
        pcb = tmp_path / f"r{angolo}.kicad_pcb"
        pcb.write_text(PCB_PROVA.replace("(at 10.5 20.3 90)",
                                         f"(at 10.5 20.3 {angolo})"),
                       encoding="utf-8")
        info = parser.read_pcb(pcb)
        pad = next(p for p in info.footprints[0].pads if p.number == "1")
        assert (pad.x, pad.y) == pytest.approx(atteso, abs=1e-3)


# ---------------------------------------------------------------------------
# Le scritture rifiutano prima di scrivere
# ---------------------------------------------------------------------------

class TestScrittureRifiutate:

    def test_via_col_foro_piu_largo_del_diametro(self, scheda):
        prima = scheda.read_text(encoding="utf-8")
        esito = K.kicad_add_via([5, 5], size_mm=0.4, drill_mm=0.8)
        assert esito["success"] is False
        assert "corona" in esito["error"]
        assert scheda.read_text(encoding="utf-8") == prima

    def test_pista_su_layer_non_di_rame(self, scheda):
        prima = scheda.read_text(encoding="utf-8")
        esito = K.kicad_add_track([1, 1], [2, 2], 0.2, layer="Edge.Cuts")
        assert esito["success"] is False
        assert scheda.read_text(encoding="utf-8") == prima

    def test_pista_di_lunghezza_zero(self, scheda):
        esito = K.kicad_add_track([5, 5], [5, 5], 0.2)
        assert esito["success"] is False

    def test_larghezza_non_positiva(self, scheda):
        assert K.kicad_add_track([1, 1], [2, 2], 0)["success"] is False

    def test_riferimento_gia_usato(self, scheda):
        """Due pezzi con lo stesso riferimento rendono ambiguo ogni comando
        successivo che li nomini — compresi quelli dell'agente."""
        esito = K.kicad_add_footprint("Lib:Fp", "R1", "x", 40, 30)
        assert esito["success"] is False
        assert "R1" in esito["error"]

    def test_percorso_con_un_punto_solo(self, scheda):
        assert K.kicad_add_route([[1, 1]], 0.2)["success"] is False


# ---------------------------------------------------------------------------
# Le scritture che devono riuscire
# ---------------------------------------------------------------------------

class TestScritture:

    def test_pista_fra_due_pad(self, scheda):
        a = next(p for p in K.kicad_pads("R1")["pads"] if p["net"] == "VCC")
        b = next(p for p in K.kicad_pads("C1")["pads"] if p["net"] == "VCC")
        esito = K.kicad_add_track([a["x"], a["y"]], [b["x"], b["y"]],
                                  0.3, net="VCC")
        assert esito["success"] is True
        assert esito["net_number"] == 2
        assert "(segment" in scheda.read_text(encoding="utf-8")

    def test_una_pista_senza_net_lo_dichiara(self, scheda):
        """Rame che il DRC non sa a chi appartenga: si accetta, ma va detto."""
        esito = K.kicad_add_track([5, 5], [10, 5], 0.3)
        assert esito["success"] is True
        assert esito["warning"]

    def test_percorso_come_catena_di_segmenti(self, scheda):
        esito = K.kicad_add_route([[5, 5], [5, 10], [12, 10]], 0.25, net="GND")
        assert esito["success"] is True
        assert esito["segments"] == 2
        assert esito["length_mm"] == pytest.approx(12.0, abs=1e-3)

    def test_via_riporta_la_corona(self, scheda):
        esito = K.kicad_add_via([30, 30], 0.8, 0.4, net="GND")
        assert esito["success"] is True
        assert esito["annular_ring_mm"] == pytest.approx(0.2)

    def test_net_nuova_riceve_un_numero_libero(self, scheda):
        esito = K.kicad_add_track([5, 5], [10, 10], 0.2, net="SDA")
        assert esito["net_number"] == 3
        assert '(net 3 "SDA")' in scheda.read_text(encoding="utf-8")

    def test_una_net_gia_esistente_non_si_duplica(self, scheda):
        """Si contano le DICHIARAZIONI di net, non le occorrenze del testo: la
        stessa forma `(net 1 "GND")` compare anche dentro ogni pad che ci sta
        sopra, e contarle tutte farebbe fallire un comportamento corretto."""
        K.kicad_add_track([5, 5], [10, 10], 0.2, net="GND")
        K.kicad_add_track([11, 11], [12, 12], 0.2, net="GND")
        dichiarate = pcb_writer.net_numbers(scheda.read_text(encoding="utf-8"))
        assert dichiarate["GND"] == 1
        assert set(dichiarate) == {"", "GND", "VCC"}, "nessuna net nuova"

    def test_footprint_aggiunto_si_rilegge(self, scheda):
        assert K.kicad_add_footprint(
            "MountingHole:MountingHole_3.2mm_M3", "H1", "M3", 45, 35)["success"]
        riferimenti = {p["reference"] for p in K.kicad_list_parts()["parts"]}
        assert "H1" in riferimenti

    def test_footprint_rimosso_sparisce(self, scheda):
        K.kicad_add_footprint("Lib:Fp", "H9", "v", 45, 35)
        assert K.kicad_remove_footprint("H9")["success"] is True
        riferimenti = {p["reference"] for p in K.kicad_list_parts()["parts"]}
        assert "H9" not in riferimenti
        assert {"R1", "C1"} <= riferimenti

    def test_il_file_resta_bilanciato(self, scheda):
        """Ogni inserimento avviene prima della parentesi finale: se sbagliasse
        il punto, KiCad non riaprirebbe piu' il file."""
        K.kicad_add_track([5, 5], [10, 10], 0.2, net="GND")
        K.kicad_add_via([20, 20], net="VCC")
        K.kicad_add_footprint("Lib:Fp", "H2", "v", 40, 30)
        testo = scheda.read_text(encoding="utf-8")
        assert testo.count("(") == testo.count(")")
        assert parser.read_pcb(scheda) is not None


# ---------------------------------------------------------------------------
# Copie di sicurezza e ritorno indietro
# ---------------------------------------------------------------------------

class TestCopieDiSicurezza:

    def test_ogni_scrittura_lascia_una_copia(self, scheda):
        esito = K.kicad_add_track([5, 5], [10, 10], 0.3, net="GND")
        assert esito["backup"]
        copie = list((scheda.parent / ".sigma_backups").glob("*.kicad_pcb"))
        assert copie

    def test_la_copia_contiene_il_prima(self, scheda):
        prima = scheda.read_text(encoding="utf-8")
        esito = K.kicad_add_track([5, 5], [10, 10], 0.3, net="GND")
        from pathlib import Path
        assert Path(esito["backup"]).read_text(encoding="utf-8") == prima

    def test_undo_riporta_il_file_com_era(self, scheda):
        prima = scheda.read_text(encoding="utf-8")
        K.kicad_add_footprint("Lib:Fp", "H3", "v", 40, 30)
        assert K.kicad_undo()["success"] is True
        assert scheda.read_text(encoding="utf-8") == prima

    def test_undo_senza_niente_da_annullare(self, scheda):
        K._ultimo_backup.pop(str(scheda), None)
        assert K.kicad_undo()["success"] is False


# ---------------------------------------------------------------------------
# Contesto ed errori utili
# ---------------------------------------------------------------------------

class TestContesto:

    def test_senza_progetto_aperto_lo_dice(self, monkeypatch):
        monkeypatch.setitem(K._progetto, "pcb", None)
        esito = K.kicad_list_parts()
        assert esito["success"] is False
        assert "kicad_open" in esito["error"]

    def test_percorso_senza_file_kicad(self, tmp_path):
        assert K.kicad_open(str(tmp_path))["success"] is False

    def test_pezzo_inesistente_elenca_quelli_veri(self, scheda):
        """L'errore deve insegnare al modello, non solo fermarlo."""
        esito = K.kicad_pads("Z99")
        assert esito["success"] is False
        assert "R1" in esito["error"] and "C1" in esito["error"]

    def test_erc_senza_schematico_lo_spiega(self, scheda):
        esito = K.kicad_erc()
        assert esito["success"] is False
        assert "kicad_sch" in esito["error"]


# ---------------------------------------------------------------------------
# Catalogo, policy e ruolo
# ---------------------------------------------------------------------------

class TestCablaggio:

    def test_ogni_esecutore_e_dichiarato(self):
        dichiarati = {s["function"]["name"] for s in TOOL_SCHEMAS
                      if s["function"]["name"].startswith("kicad_")}
        assert dichiarati == set(K.ESECUTORI)

    def test_il_dispatcher_delega(self):
        esito = K.esegui("kicad_status", {})
        assert esito is not None and esito["tool"] == "kicad_status"

    def test_il_dispatcher_ignora_gli_altri(self):
        assert K.esegui("read_file", {"path": "x"}) is None

    def test_argomenti_sbagliati_non_esplodono(self):
        esito = K.esegui("kicad_pads", {"sbagliato": 1})
        assert esito["success"] is False

    def test_le_letture_sono_sola_lettura(self):
        assert K.READ_TOOLS <= policy.READ_ONLY_TOOLS

    def test_le_scritture_non_lo_sono(self):
        assert not (K.WRITE_TOOLS & policy.READ_ONLY_TOOLS)

    def test_drc_e_una_lettura(self):
        """Un revisore deve poter chiedere la prova senza poter scrivere."""
        assert "kicad_drc" in policy.READ_ONLY_TOOLS

    @pytest.mark.parametrize("alias,atteso", [
        ("instrada", "kicad_add_route"), ("verifica_pcb", "kicad_drc"),
    ])
    def test_alias_italiani(self, alias, atteso):
        assert policy.canonical(alias) == atteso

    def test_il_ruolo_ha_tutti_i_tool(self):
        ruolo = DEV_ROLES["kicad_engineer"]
        assert set(K.ESECUTORI) <= set(ruolo.tools)

    def test_ogni_tool_del_ruolo_ha_uno_schema(self):
        """Un tool concesso senza schema non arriva mai al modello: era il caso
        di tutti e dieci i tool KiCad prima di questo lavoro."""
        ruolo = DEV_ROLES["kicad_engineer"]
        assert len(schemas_for(ruolo.tools)) == len(ruolo.tools)

    def test_il_ruolo_non_scrive_codice(self):
        """Progetta schede: un giro andato male non deve poter riscrivere il
        kernel. I file del progetto si toccano dai tool kicad_*, che fanno una
        copia prima di ogni scrittura."""
        ruolo = DEV_ROLES["kicad_engineer"]
        assert not ({"write_file", "edit_file", "terminal", "delete"}
                    & set(ruolo.tools))

    def test_ogni_esito_dichiara_tool_e_success(self, monkeypatch):
        monkeypatch.setitem(K._progetto, "pcb", None)
        for nome in K.ESECUTORI:
            esito = K.esegui(nome, {})
            if esito is None:
                continue
            assert esito["tool"] == nome
            assert isinstance(esito["success"], bool)

    def test_success_non_viene_sovrascritto_dal_payload(self):
        """`ok` e `success` arrivavano insieme dai report di kicad-cli e da
        WriteResult: con il vecchio nome del parametro Python li vedeva come
        due valori per lo stesso argomento, e operazioni riuscite venivano
        riportate come fallite."""
        esito = K._esito("x", True, ok=False, altro=1)
        assert esito["success"] is True
        assert "ok" not in esito


class TestSeparazioneDeiVerdetti:
    """`success` dice se il tool ha girato, `drc_passed` se la scheda passa.
    Fusi in un campo solo, un agente non distingue un DRC che non parte da un
    DRC che boccia — e sono situazioni opposte: la prima si riprova, la seconda
    si corregge."""

    def test_drc_con_violazioni_e_comunque_eseguito(self, scheda, monkeypatch):
        from core.modules.sigma_kicad_lab import kicad_cli as cli
        monkeypatch.setattr(cli, "run_drc", lambda p, o=None: {
            "ok": True, "success": False, "total_errors": 3, "violations": []})
        esito = K.kicad_drc()
        assert esito["success"] is True
        assert esito["drc_passed"] is False
        assert esito["total_errors"] == 3

    def test_drc_pulito(self, scheda, monkeypatch):
        from core.modules.sigma_kicad_lab import kicad_cli as cli
        monkeypatch.setattr(cli, "run_drc", lambda p, o=None: {
            "ok": True, "success": True, "total_errors": 0, "violations": []})
        esito = K.kicad_drc()
        assert esito["success"] is True and esito["drc_passed"] is True
