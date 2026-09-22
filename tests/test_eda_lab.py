# ==============================================================================
# tests/test_eda_lab.py — EDA Lab: piazzamento, regole, ponte verso EasyEDA
# ==============================================================================
"""Il modulo si prova senza EasyEDA aperto, ed e' il motivo per cui e' diviso
cosi': gli algoritmi non sanno che EasyEDA esiste, e il ponte che lo sa non
calcola niente. Qui si verificano i primi per intero e del secondo si verifica
la traduzione — unita', nomi dei campi, gate di approvazione — che e' l'unica
parte che si puo' sbagliare a tavolino.

Resta fuori una cosa sola, e va detta: nessuno di questi test ha mai parlato con
EasyEDA. La forma delle risposte e' quella dichiarata dagli `outputSchema` del
server MCP, non quella osservata su un progetto vero.
"""
import math

import pytest

from core.mcp.governance import SAFE, SENSITIVE
from core.modules.sigma_eda_lab import bridge, evaluate, placement, rules
from core.modules.sigma_eda_lab.netlist import (Board, BoardError, Component,
                                                Net, Pin, CLASS_CRITICAL,
                                                CLASS_GROUND, CLASS_POWER)


# ---------------------------------------------------------------------------
# Scheda di prova
# ---------------------------------------------------------------------------

def scheda_con_mcu(x_u1=30.0, y_u1=25.0, sparsi=True) -> Board:
    """Un MCU, quattro condensatori e un connettore bloccato sul bordo."""
    board = Board(width=40.0, height=30.0)
    board.add(Component("U1", 10.0, 10.0, x=x_u1, y=y_u1, footprint="QFN32",
                        primitive_id="p-u1", pins=(
                            Pin("1", -4.0, 5.0, net="VCC"),
                            Pin("2", -2.0, 5.0, net="GND"),
                            Pin("3", 0.0, 5.0, net="D+"),
                            Pin("4", 2.0, 5.0, net="D-"))))
    for i, designator in enumerate(["C1", "C2", "C3", "C4"], start=1):
        x = 5.0 + i * 3.0 if sparsi else x_u1 + i * 0.9
        board.add(Component(designator, 1.6, 0.8, x=x, y=5.0, footprint="0603",
                            primitive_id=f"p-{designator.lower()}", pins=(
                                Pin("1", -0.8, 0.0, net="VCC"),
                                Pin("2", 0.8, 0.0, net="GND"))))
    board.add(Component("J1", 8.0, 4.0, x=5.0, y=15.0, locked=True,
                        footprint="USB-C", primitive_id="p-j1", pins=(
                            Pin("1", -3.0, 0.0, net="VCC"),
                            Pin("2", 3.0, 0.0, net="GND"))))
    board.nets = [
        Net("VCC", (("U1", "1"), ("C1", "1"), ("C2", "1"), ("C3", "1"),
                    ("C4", "1"), ("J1", "1")), CLASS_POWER),
        Net("GND", (("U1", "2"), ("C1", "2"), ("C2", "2"), ("C3", "2"),
                    ("C4", "2"), ("J1", "2")), CLASS_GROUND),
        Net("D+", (("U1", "3"), ("J1", "1"))),
        Net("D-", (("U1", "4"), ("J1", "2"))),
    ]
    return board


# ---------------------------------------------------------------------------
# IPC-2221
# ---------------------------------------------------------------------------

class TestLarghezzaPiste:

    def test_valore_di_riferimento(self):
        """1 A, 10 °C, 1 oz su strato esterno: circa 0,30 mm.

        E' il caso che compare su ogni calcolatore IPC-2221 in circolazione, ed
        e' l'unico modo di accorgersi che una costante e' stata digitata male:
        la formula continua a dare numeri plausibili anche sbagliata.
        """
        risultato = rules.trace_width(1.0, delta_t_c=10.0, thickness_oz=1.0,
                                      layer="external")
        assert risultato.width_mm == pytest.approx(0.30, abs=0.01)
        assert risultato.width_mil == pytest.approx(11.8, abs=0.3)

    def test_strato_interno_richiede_piu_rame(self):
        esterno = rules.trace_width(1.0, layer="external").width_mm
        interno = rules.trace_width(1.0, layer="internal").width_mm
        # k raddoppia, e attraverso l'esponente 1/0.725 il rapporto e' ~2.6.
        assert interno / esterno == pytest.approx(2.6, abs=0.1)

    def test_inversa_torna_al_punto_di_partenza(self):
        larghezza = rules.trace_width(2.5, delta_t_c=20.0).width_mm
        assert rules.current_capacity(larghezza, delta_t_c=20.0) == pytest.approx(2.5, rel=1e-3)

    def test_piu_corrente_piu_larga(self):
        assert (rules.trace_width(3.0).width_mm > rules.trace_width(1.0).width_mm)

    def test_consigliata_supera_il_minimo(self):
        minimo = rules.trace_width(2.0).width_mm
        assert rules.suggest_width_mm(2.0) > minimo

    def test_margine_non_puo_assottigliare(self):
        with pytest.raises(rules.RuleError):
            rules.suggest_width_mm(1.0, margin=0.8)

    @pytest.mark.parametrize("kwargs", [
        {"current_a": 0},
        {"current_a": -1},
        {"current_a": 40},            # oltre i 35 A tabellati
        {"current_a": 1, "delta_t_c": 150},
        {"current_a": 1, "thickness_oz": 20},
        {"current_a": 1, "layer": "middle"},
    ])
    def test_fuori_dominio_si_rifiuta(self, kwargs):
        """Fuori tabella la formula darebbe comunque un numero. Non va dato."""
        with pytest.raises(rules.RuleError):
            rules.trace_width(**kwargs)


# ---------------------------------------------------------------------------
# Modello della scheda
# ---------------------------------------------------------------------------

class TestModello:

    def test_rotazione_scambia_l_ingombro(self):
        pezzo = Component("U1", 10.0, 4.0, rotation=90)
        assert pezzo.extent == (4.0, 10.0)

    def test_pin_ruota_intorno_al_centro(self):
        pezzo = Component("U1", 10.0, 10.0, x=0.0, y=0.0, rotation=90,
                          pins=(Pin("1", 2.0, 0.0),))
        x, y = pezzo.pin_position(pezzo.pins[0])
        assert (round(x, 6), round(y, 6)) == (0.0, 2.0)

    def test_lato_inferiore_specchia_la_x(self):
        pezzo = Component("U1", 4.0, 4.0, x=0.0, y=0.0, side="bottom",
                          pins=(Pin("1", 1.5, 0.0),))
        x, _ = pezzo.pin_position(pezzo.pins[0])
        assert x == pytest.approx(-1.5)

    def test_ingombro_nullo_rifiutato(self):
        with pytest.raises(BoardError):
            Component("U1", 0.0, 5.0)

    def test_rotazione_obliqua_rifiutata(self):
        with pytest.raises(BoardError):
            Component("U1", 5.0, 5.0, rotation=37)

    def test_designator_duplicato_rifiutato(self):
        board = Board(10.0, 10.0)
        board.add(Component("R1", 1.0, 1.0))
        with pytest.raises(BoardError):
            board.add(Component("R1", 1.0, 1.0))

    def test_hpwl_di_due_pin(self):
        board = Board(50.0, 50.0)
        board.add(Component("A", 1.0, 1.0, x=0.0, y=0.0, pins=(Pin("1", 0, 0),)))
        board.add(Component("B", 1.0, 1.0, x=3.0, y=4.0, pins=(Pin("1", 0, 0),)))
        board.nets = [Net("N", (("A", "1"), ("B", "1")))]
        assert board.net_hpwl(board.nets[0]) == pytest.approx(7.0)

    def test_inflate_trasforma_la_vicinanza_in_sovrapposizione(self):
        """Due pezzi accostati non si sovrappongono, ma con l'ingombro
        allargato si', ed e' cosi' che il costo impara a lasciare spazio."""
        board = Board(20.0, 20.0)
        board.add(Component("A", 2.0, 2.0, x=5.0, y=5.0))
        board.add(Component("B", 2.0, 2.0, x=7.0, y=5.0))   # bordi a contatto
        assert board.overlap_area() == pytest.approx(0.0)
        assert board.overlap_area(inflate=0.125) > 0.0

    def test_coppie_di_disaccoppiamento_sono_topologiche(self):
        """L'accoppiamento non guarda le distanze: un integrato spostato non
        cambia a chi appartiene un condensatore."""
        board = scheda_con_mcu()
        prima = board.decoupling_pairs()
        assert prima == [("C1", "U1", "VCC"), ("C2", "U1", "VCC"),
                         ("C3", "U1", "VCC"), ("C4", "U1", "VCC")]

        lontano = board.with_components([board.components["U1"].moved(1.0, 1.0)])
        assert lontano.decoupling_pairs() == prima

    def test_anello_si_misura_fra_i_pin(self):
        """Un QFN da 10 mm non puo' avere un condensatore a 3 mm dal proprio
        centro. Misurare fra i pin toglie di mezzo la taglia del package."""
        board = Board(40.0, 30.0)
        board.add(Component("U1", 10.0, 10.0, x=20.0, y=15.0, primitive_id="u",
                            pins=(Pin("1", -4.0, 5.0, net="VCC"),
                                  Pin("2", -2.0, 5.0, net="GND"))))
        board.add(Component("C1", 1.6, 0.8, x=16.5, y=21.0, primitive_id="c",
                            pins=(Pin("1", -0.8, 0.0, net="VCC"),
                                  Pin("2", 0.8, 0.0, net="GND"))))
        board.nets = [Net("VCC", (("U1", "1"), ("C1", "1")), CLASS_POWER),
                      Net("GND", (("U1", "2"), ("C1", "2")), CLASS_GROUND)]
        centro_a_centro = math.hypot(20.0 - 16.5, 15.0 - 21.0)
        anello = board.decoupling_distance("C1", "U1", "VCC")
        assert anello < centro_a_centro
        assert anello < 1.5


# ---------------------------------------------------------------------------
# Piazzamento
# ---------------------------------------------------------------------------

class TestPiazzamento:

    def test_deterministico(self):
        board = scheda_con_mcu()
        a = placement.optimize(board, iterations=1500, seed=7)
        b = placement.optimize(board, iterations=1500, seed=7)
        assert a.cost_after == pytest.approx(b.cost_after)
        assert ([(c.designator, round(c.x, 6), round(c.y, 6))
                 for c in sorted(a.board.components.values(), key=lambda c: c.designator)]
                == [(c.designator, round(c.x, 6), round(c.y, 6))
                    for c in sorted(b.board.components.values(), key=lambda c: c.designator)])

    def test_semi_diversi_esiti_diversi(self):
        board = scheda_con_mcu()
        a = placement.optimize(board, iterations=1500, seed=1)
        b = placement.optimize(board, iterations=1500, seed=2)
        assert a.cost_after != b.cost_after

    def test_non_peggiora_mai(self):
        board = scheda_con_mcu()
        for seme in (1, 2, 3, 99):
            risultato = placement.optimize(board, iterations=300, seed=seme)
            assert risultato.cost_after <= risultato.cost_before

    def test_migliora_una_scheda_sparpagliata(self):
        board = scheda_con_mcu()
        risultato = placement.optimize(board, iterations=6000)
        assert risultato.cost_after < risultato.cost_before
        assert risultato.improvement_pct > 50

    def test_i_bloccati_non_si_muovono(self):
        board = scheda_con_mcu()
        prima = board.components["J1"]
        dopo = placement.optimize(board, iterations=4000).board.components["J1"]
        assert (dopo.x, dopo.y, dopo.rotation) == (prima.x, prima.y, prima.rotation)

    def test_niente_da_muovere_non_rompe(self):
        board = Board(10.0, 10.0)
        board.add(Component("J1", 2.0, 2.0, x=5.0, y=5.0, locked=True))
        risultato = placement.optimize(board, iterations=100)
        assert risultato.iterations == 0
        assert risultato.moved == []

    def test_resta_dentro_il_contorno(self):
        board = scheda_con_mcu()
        risultato = placement.optimize(board, iterations=6000)
        for pezzo in risultato.board.components.values():
            if pezzo.locked:
                continue
            x0, y0, x1, y1 = pezzo.bbox
            assert x0 >= -1e-6 and y0 >= -1e-6
            assert x1 <= board.width + 1e-6 and y1 <= board.height + 1e-6

    def test_griglia_iniziale_non_sovrappone(self):
        board = scheda_con_mcu()
        disposta = placement.seed_grid(board)
        assert disposta.overlap_area() == pytest.approx(0.0, abs=1e-9)

    def test_elenco_spostamenti_coerente(self):
        board = scheda_con_mcu()
        risultato = placement.optimize(board, iterations=3000)
        for voce in risultato.moved:
            finale = risultato.board.components[voce["designator"]]
            assert finale.x == pytest.approx(voce["to"]["x"], abs=1e-3)
            assert finale.y == pytest.approx(voce["to"]["y"], abs=1e-3)
        assert "J1" not in [v["designator"] for v in risultato.moved]

    def test_il_costo_misura_cio_che_il_valutatore_giudica(self):
        """Il difetto che questo test blocca: un costo cieco a un criterio
        produce schede che lo violano, e le consegna come migliorate."""
        board = scheda_con_mcu()
        risultato = placement.optimize(board, iterations=8000)
        esito = evaluate.evaluate(risultato.board)
        nomi = {c.name: c.status for c in esito.checks}
        assert nomi["sovrapposizioni"] == evaluate.OK
        assert nomi["distanza fra i pezzi"] == evaluate.OK
        assert nomi["disaccoppiamento"] == evaluate.OK


# ---------------------------------------------------------------------------
# Valutazione
# ---------------------------------------------------------------------------

class TestValutazione:

    def test_scheda_buona_passa(self):
        board = scheda_con_mcu()
        esito = evaluate.evaluate(placement.optimize(board, iterations=8000).board)
        assert esito.verdict == evaluate.OK
        assert esito.score == 100

    def test_sovrapposizione_boccia(self):
        board = Board(20.0, 20.0)
        board.add(Component("U1", 5.0, 5.0, x=10.0, y=10.0))
        board.add(Component("U2", 5.0, 5.0, x=11.0, y=10.0))
        esito = evaluate.evaluate(board)
        assert esito.verdict == evaluate.FAIL
        fallito = next(c for c in esito.checks if c.name == "sovrapposizioni")
        assert {fallito.offenders[0]["a"], fallito.offenders[0]["b"]} == {"U1", "U2"}

    def test_fuori_contorno_boccia(self):
        board = Board(20.0, 20.0)
        board.add(Component("U1", 5.0, 5.0, x=19.0, y=10.0))
        esito = evaluate.evaluate(board)
        assert next(c for c in esito.checks
                    if c.name == "contorno").status == evaluate.FAIL

    def test_pezzi_troppo_vicini_avvertono(self):
        board = Board(20.0, 20.0)
        board.add(Component("R1", 2.0, 1.0, x=8.0, y=10.0))
        board.add(Component("R2", 2.0, 1.0, x=10.1, y=10.0))   # 0,1 mm di luce
        controllo = next(c for c in evaluate.evaluate(board).checks
                         if c.name == "distanza fra i pezzi")
        assert controllo.status == evaluate.WARN

    def test_disaccoppiamento_lontano_boccia(self):
        board = scheda_con_mcu()
        controllo = next(c for c in evaluate.evaluate(board).checks
                         if c.name == "disaccoppiamento")
        assert controllo.status == evaluate.FAIL
        assert controllo.offenders

    def test_pezzo_scollegato_avverte(self):
        board = scheda_con_mcu()
        board.add(Component("H1", 3.0, 3.0, x=35.0, y=5.0))   # foro di fissaggio
        controllo = next(c for c in evaluate.evaluate(board).checks
                         if c.name == "pezzi scollegati")
        assert controllo.status == evaluate.WARN
        assert controllo.offenders == [{"designator": "H1"}]

    def test_net_critica_lunga_avverte(self):
        board = Board(60.0, 60.0)
        board.add(Component("U1", 2.0, 2.0, x=2.0, y=2.0, pins=(Pin("1", 0, 0),)))
        board.add(Component("Y1", 2.0, 2.0, x=55.0, y=55.0, pins=(Pin("1", 0, 0),)))
        board.add(Component("R1", 2.0, 2.0, x=10.0, y=10.0, pins=(Pin("1", 0, 0),)))
        board.add(Component("R2", 2.0, 2.0, x=12.0, y=12.0, pins=(Pin("1", 0, 0),)))
        board.nets = [
            Net("XTAL", (("U1", "1"), ("Y1", "1")), CLASS_CRITICAL),
            Net("SIG", (("R1", "1"), ("R2", "1"))),
        ]
        controllo = next(c for c in evaluate.evaluate(board).checks
                         if c.name == "net critiche")
        assert controllo.status == evaluate.WARN
        assert controllo.offenders[0]["net"] == "XTAL"

    def test_il_punteggio_scende_coi_difetti(self):
        buona = evaluate.evaluate(
            placement.optimize(scheda_con_mcu(), iterations=8000).board)
        cattiva = evaluate.evaluate(scheda_con_mcu())
        assert buona.score > cattiva.score

    def test_il_referto_e_serializzabile(self):
        import json
        referto = evaluate.evaluate(scheda_con_mcu()).to_dict()
        assert json.loads(json.dumps(referto))["verdict"] in ("ok", "warn", "fail")


# ---------------------------------------------------------------------------
# Ponte verso EasyEDA
# ---------------------------------------------------------------------------

class TestUnita:

    def test_riconosce_i_mil(self):
        """Una scheda da 40 mm con i pezzi sparsi su ~1200 unita': mil."""
        probe = bridge.detect_scale((40.0, 30.0),
                                    [(200.0, 200.0), (1400.0, 900.0)])
        assert probe.guess == "mil"
        assert probe.confident
        assert probe.scale_mm_per_unit == pytest.approx(0.0254, rel=1e-6)

    def test_riconosce_i_millimetri(self):
        probe = bridge.detect_scale((40.0, 30.0), [(5.0, 5.0), (35.0, 25.0)])
        assert probe.guess == "mm"
        assert probe.confident

    def test_riconosce_i_decimi_di_mil(self):
        probe = bridge.detect_scale((40.0, 30.0), [(2000.0, 2000.0), (14000.0, 9000.0)])
        assert probe.guess == "mil/10"
        assert probe.confident

    def test_numeri_incoerenti_non_sono_affidabili(self):
        """Centomila unita' su una scheda da 40 mm non tornano con nessuna delle
        tre unita' possibili: il risultato non va usato per scrivere.

        La soglia e' larga di proposito. Le tre unita' candidate distano fra
        loro un fattore quattrocento, quindi quasi ogni numero plausibile trova
        una lettura che sta in piedi — ed e' giusto cosi': serve a fermare gli
        ordini di grandezza sbagliati, non a indovinare fra due letture
        entrambe sensate."""
        probe = bridge.detect_scale((40.0, 30.0), [(0.0, 0.0), (100000.0, 100000.0)])
        assert not probe.confident
        assert probe.note

    def test_escursione_assurdamente_piccola_insospettisce(self):
        """Mezzo millimetro di escursione su una scheda da 40 mm: o i pezzi
        sono tutti impilati, o l'unita' letta non e' quella che sembra."""
        probe = bridge.detect_scale((40.0, 30.0), [(10.0, 10.0), (10.5, 10.2)])
        assert not probe.confident

    def test_senza_coordinate_non_finge(self):
        probe = bridge.detect_scale((40.0, 30.0), [])
        assert not probe.confident


class TestClassificazioneNet:

    @pytest.mark.parametrize("nome,atteso", [
        ("GND", CLASS_GROUND), ("AGND", CLASS_GROUND), ("VSS", CLASS_GROUND),
        ("VCC", CLASS_POWER), ("+3V3", CLASS_POWER), ("VBUS", CLASS_POWER),
        ("SDA", "signal"), ("RESET_N", "signal"), ("", "signal"),
    ])
    def test_nomi_noti(self, nome, atteso):
        assert bridge.classify_net(nome) == atteso

    def test_un_prefisso_non_basta(self):
        """`GNDSENSE` non e' massa: senza separatore e' un'altra net."""
        assert bridge.classify_net("GNDSENSE") == "signal"
        assert bridge.classify_net("GND_2") == CLASS_GROUND


class TestRisposteMcp:

    def test_preferisce_il_contenuto_strutturato(self):
        payload = bridge._payload(
            {"structuredContent": {"total": 3}, "content": [
                {"type": "text", "text": '{"total": 99}'}]}, "x")
        assert payload["total"] == 3

    def test_ripiega_sul_testo_json(self):
        payload = bridge._payload(
            {"content": [{"type": "text", "text": '{"total": 7}'}]}, "x")
        assert payload["total"] == 7

    def test_errore_dichiarato_diventa_eccezione(self):
        with pytest.raises(bridge.BridgeError, match="niente PCB"):
            bridge._payload({"isError": True,
                             "content": [{"type": "text", "text": "niente PCB"}]}, "x")

    def test_forma_incomprensibile_non_passa_in_silenzio(self):
        with pytest.raises(bridge.BridgeError):
            bridge._payload({"content": [{"type": "image", "data": "..."}]}, "x")


class HubFinto:
    """Un hub che registra le chiamate invece di eseguirle."""

    def __init__(self, risposte=None, stato="ok"):
        self.chiamate = []
        self.risposte = risposte or {}
        self.stato = stato

    def execute_tool(self, tool, arguments=None):
        self.chiamate.append((tool, arguments or {}))
        if self.stato == "confirmation_required":
            # La forma e' quella vera di governance.create_approval: un finto
            # che si inventa i nomi dei campi verifica se' stesso, non il codice.
            return {"status": "confirmation_required",
                    "approval": {"request_id": "mcp-a1", "tool": tool,
                                 "server": "EasyEDA Pro", "status": "pending"}}
        if self.stato == "error":
            return {"status": "error", "error": "server spento"}
        corpo = self.risposte.get(tool, {"ok": True})
        return {"status": "ok", "result": {"structuredContent": corpo,
                                           "isError": False}}


class TestScrittura:

    def test_dry_run_usa_preview_e_non_conferma(self):
        """Il primo giro su un progetto vero non deve poter muovere niente."""
        board = scheda_con_mcu()
        hub = HubFinto()
        esito = bridge.apply_placement(board, dry_run=True, hub=hub)

        assert esito.dry_run
        assert hub.chiamate, "nessuna chiamata inviata"
        for _, arguments in hub.chiamate:
            assert arguments["mode"] == "preview"
            assert "confirmWrite" not in arguments

    def test_scrittura_vera_dichiara_la_conferma(self):
        hub = HubFinto()
        bridge.apply_placement(scheda_con_mcu(), dry_run=False, hub=hub)
        for _, arguments in hub.chiamate:
            assert arguments["mode"] == "apply"
            assert arguments["confirmWrite"] is True

    def test_converte_i_millimetri_in_mil(self):
        """EasyEDA vuole mil. Sbagliare qui sposta i pezzi di quaranta volte."""
        board = Board(40.0, 30.0)
        board.add(Component("R1", 1.0, 1.0, x=25.4, y=12.7, primitive_id="p1"))
        hub = HubFinto()
        bridge.apply_placement(board, dry_run=True, hub=hub)

        _, arguments = hub.chiamate[0]
        assert arguments["xMil"] == pytest.approx(1000.0, abs=0.01)
        assert arguments["yMil"] == pytest.approx(500.0, abs=0.01)

    def test_i_bloccati_si_saltano(self):
        hub = HubFinto()
        esito = bridge.apply_placement(scheda_con_mcu(), dry_run=True, hub=hub)
        assert "J1" not in [a["primitiveId"] for _, a in hub.chiamate]
        assert any(s["designator"] == "J1" and s["reason"] == "bloccato"
                   for s in esito.skipped)

    def test_senza_primitive_id_si_salta(self):
        board = Board(20.0, 20.0)
        board.add(Component("R1", 1.0, 1.0, x=10.0, y=10.0))   # nessun id
        esito = bridge.apply_placement(board, dry_run=True, hub=HubFinto())
        assert esito.applied == []
        assert esito.skipped[0]["reason"] == "nessun primitiveId nel progetto"

    def test_l_approvazione_risale_al_chiamante(self):
        """Il gate che ferma una scrittura non e' un guasto da inghiottire."""
        hub = HubFinto(stato="confirmation_required")
        with pytest.raises(bridge.ApprovalRequired) as caught:
            bridge.apply_placement(scheda_con_mcu(), dry_run=False, hub=hub)
        assert caught.value.request_id == "mcp-a1"
        assert "mcp-a1" in str(caught.value)

    def test_un_errore_per_pezzo_non_ferma_gli_altri(self):
        hub = HubFinto(stato="error")
        esito = bridge.apply_placement(scheda_con_mcu(), dry_run=True, hub=hub)
        assert esito.applied == []
        assert len(esito.failed) >= 4


class TestLetturaScheda:

    def _hub(self):
        return HubFinto(risposte={
            "easyeda_board_dimensions": {
                "project_id": "p", "width_mm": 40.0, "height_mm": 30.0,
                "has_outline": True, "mounting_hole_count": 0},
            "easyeda_pcb_components": {
                "project_id": "p", "total": 2, "components": [
                    {"primitiveId": "p-u1", "designator": "U1", "x": 800.0,
                     "y": 600.0, "rotation": 0, "layer": 1, "locked": False,
                     "footprintName": "QFN32"},
                    {"primitiveId": "p-j1", "designator": "J1", "x": 200.0,
                     "y": 400.0, "rotation": 93, "layer": 2, "locked": True,
                     "footprintName": "USB-C"},
                ]},
        })

    def test_traduce_in_millimetri(self):
        board, probe = bridge.read_board("p", hub=self._hub())
        assert probe.guess == "mil"
        assert board.width == pytest.approx(40.0)
        assert board.components["U1"].x == pytest.approx(800.0 * 0.0254)

    def test_layer_diventa_lato(self):
        board, _ = bridge.read_board("p", hub=self._hub())
        assert board.components["U1"].side == "top"
        assert board.components["J1"].side == "bottom"

    def test_blocco_dal_progetto(self):
        board, _ = bridge.read_board("p", hub=self._hub())
        assert board.components["J1"].locked

    def test_rotazione_obliqua_si_arrotonda(self):
        """93 gradi non stanno nel modello. Arrotondare e' meglio che rifiutare
        la scheda, ma il pezzo verra' raddrizzato se si riapplica."""
        board, _ = bridge.read_board("p", hub=self._hub())
        assert board.components["J1"].rotation == 90

    def test_senza_contorno_si_ferma(self):
        hub = HubFinto(risposte={"easyeda_board_dimensions": {
            "project_id": "p", "has_outline": False, "mounting_hole_count": 0}})
        with pytest.raises(bridge.BridgeError, match="contorno"):
            bridge.read_board("p", hub=hub)


class TestNetlistDalloSchematico:

    def test_forma_a_oggetti(self):
        hub = HubFinto(risposte={"easyeda_schematic_validate_netlist": {
            "nets": [{"name": "GND", "pins": [
                {"designator": "U1", "pinNumber": "2"},
                {"designator": "C1", "pinNumber": "2"}]}]}})
        nets = bridge.netlist_from_schematic("p", hub=hub)
        assert nets[0].connections == (("U1", "2"), ("C1", "2"))
        assert nets[0].net_class == CLASS_GROUND

    def test_forma_piatta(self):
        hub = HubFinto(risposte={"easyeda_schematic_validate_netlist": {
            "nets": [{"netName": "VCC", "connections": ["U1.1", "C1-1"]}]}})
        nets = bridge.netlist_from_schematic("p", hub=hub)
        assert nets[0].connections == (("U1", "1"), ("C1", "1"))
        assert nets[0].net_class == CLASS_POWER

    def test_net_con_un_pin_solo_si_scarta(self):
        hub = HubFinto(risposte={"easyeda_schematic_validate_netlist": {
            "nets": [{"name": "NC", "pins": [{"designator": "U1", "pinNumber": "9"}]}]}})
        assert bridge.netlist_from_schematic("p", hub=hub) == []


# ---------------------------------------------------------------------------
# Server MCP del modulo
# ---------------------------------------------------------------------------

class TestServerMcp:

    def _server(self):
        from core.modules.sigma_eda_lab.mcp_server import EdaLabMCPServer
        return EdaLabMCPServer()

    def test_tool_registrati(self):
        nomi = {t["name"] for t in self._server().list_tools()}
        assert {"eda_trace_width", "eda_board_read", "eda_placement_optimize",
                "eda_placement_apply", "eda_board_evaluate",
                "eda_bridge_status"} <= nomi

    def test_solo_l_applicazione_e_sensibile(self):
        """L'unico tool che tocca il progetto e' l'unico che deve fermarsi."""
        per_nome = {t["name"]: t["safety"] for t in self._server().list_tools()}
        assert per_nome["eda_placement_apply"] == SENSITIVE
        assert per_nome["eda_placement_optimize"] == SAFE
        assert per_nome["eda_board_read"] == SAFE
        assert per_nome["eda_board_evaluate"] == SAFE

    def test_larghezza_pista_risponde_senza_easyeda(self):
        esito = self._server().call_tool("eda_trace_width", {"current_a": 1.0})
        assert not esito["isError"]

    def test_corrente_impossibile_spiega_invece_di_esplodere(self):
        server = self._server()
        risposta = server._trace_width(current_a=100.0)
        assert risposta["ok"] is False
        assert "35" in risposta["error"]


# ---------------------------------------------------------------------------
# La modifica al kernel: safety per tool dalle annotations MCP
# ---------------------------------------------------------------------------

class TestSafetyDalleAnnotations:

    def _server(self, **spec):
        from core.mcp.client import ExternalMCPServer
        base = {"id": "x", "name": "Finto", "command": "cmd"}
        return ExternalMCPServer({**base, **spec})

    def test_senza_opt_in_nulla_cambia(self):
        """Il comportamento storico resta quello di prima per chi non chiede
        niente: un server non fidato ha tutti i tool sensibili."""
        server = self._server()
        assert server._tool_safety({"annotations": {"readOnlyHint": True}}) == SENSITIVE

    def test_con_opt_in_le_letture_diventano_safe(self):
        server = self._server(trust_annotations=True)
        assert server._tool_safety({"annotations": {"readOnlyHint": True}}) == SAFE

    def test_le_scritture_restano_sensibili(self):
        server = self._server(trust_annotations=True)
        assert server._tool_safety({"annotations": {"readOnlyHint": False}}) == SENSITIVE

    def test_distruttivo_non_si_declassa(self):
        """Un'etichetta contraddittoria si risolve sempre dalla parte prudente."""
        server = self._server(trust_annotations=True)
        assert server._tool_safety(
            {"annotations": {"readOnlyHint": True, "destructiveHint": True}}) == SENSITIVE

    def test_senza_annotations_si_eredita_dal_server(self):
        server = self._server(trust_annotations=True)
        assert server._tool_safety({}) == SENSITIVE
        assert server._tool_safety({"annotations": "non un oggetto"}) == SENSITIVE

    def test_server_dichiarato_di_sola_lettura_resta_tale(self):
        server = self._server(read_only=True, trust_annotations=True)
        assert server._tool_safety({"annotations": {"readOnlyHint": False}}) == SAFE
