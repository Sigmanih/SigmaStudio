# ==============================================================================
# tests/test_pcbnew_bridge.py — Il ponte verso l'API Python di KiCad
# ==============================================================================
"""Questi test girano KiCad davvero: creano schede, caricano footprint dalle
librerie installate e li rileggono da disco.

**Non saltano se KiCad manca.** La prima stesura li marcava `skipif` sulla
disponibilita' di pcbnew: se `disponibile()` avesse risposto male, la suite
sarebbe diventata verde saltandoli tutti, e un'integrazione rotta si sarebbe
presentata come funzionante. Qui l'assenza di KiCad e' un fallimento, perche'
su questa macchina KiCad c'e' e il ponte deve trovarlo: se un giorno non lo
trova piu', e' esattamente la notizia che serve.

La geometria e' l'unica cosa che si puo' sbagliare in silenzio. Un pad nel
posto sbagliato non fa fallire niente: produce coordinate plausibili verso cui
si traccia rame che non collega. Per questo il valore atteso qui sotto non lo
calcoliamo noi — e' dove KiCad stesso mette il pad.
"""
import pytest

from core.modules.sigma_kicad_lab import pcbnew_bridge as P


@pytest.fixture(scope="module")
def kicad():
    """KiCad deve esserci. Se non c'e', i test falliscono: non si saltano."""
    stato = P.disponibile()
    assert stato["ok"], f"KiCad non disponibile: {stato.get('errore')}"
    return stato


# ---------------------------------------------------------------------------
# Presenza e librerie
# ---------------------------------------------------------------------------

class TestDisponibilita:

    def test_trova_pcbnew_e_la_versione(self, kicad):
        assert kicad["versione"]
        assert kicad["python_kicad"].endswith(("python.exe", "python3"))

    def test_trova_la_cartella_delle_librerie(self, kicad):
        assert kicad["cartella_librerie"]

    def test_elenca_le_librerie(self, kicad):
        esito = P.elenca_librerie()
        assert esito["ok"] and esito["totale"] > 50
        assert "Capacitor_SMD" in esito["librerie"]
        assert "Resistor_SMD" in esito["librerie"]


# ---------------------------------------------------------------------------
# Ricerca
# ---------------------------------------------------------------------------

class TestRicerca:

    def test_trova_un_footprint_noto(self, kicad):
        esito = P.cerca_footprint("C_0805_2012Metric", limite=5)
        assert esito["ok"] and esito["totale"] >= 1
        primo = esito["risultati"][0]
        assert primo["libreria"] == "Capacitor_SMD"
        assert "C_0805" in primo["footprint"]

    def test_ricerca_ristretta_a_una_libreria(self, kicad):
        esito = P.cerca_footprint("R_0603", limite=5, libreria="Resistor_SMD")
        assert esito["ok"] and esito["totale"] >= 1
        assert all(r["libreria"] == "Resistor_SMD" for r in esito["risultati"])

    def test_il_limite_viene_rispettato(self, kicad):
        esito = P.cerca_footprint("C_", limite=3)
        assert esito["ok"] and len(esito["risultati"]) <= 3

    def test_query_senza_riscontri(self, kicad):
        esito = P.cerca_footprint("zzz_non_esiste_zzz", limite=5)
        assert esito["ok"] and esito["totale"] == 0


# ---------------------------------------------------------------------------
# Creazione e lettura
# ---------------------------------------------------------------------------

class TestScheda:

    def test_crea_e_rilegge(self, kicad, tmp_path):
        pcb = tmp_path / "scheda.kicad_pcb"
        creata = P.crea_scheda(str(pcb), 40, 30, net=["GND", "+3V3"])
        assert creata["ok"] and pcb.is_file()

        letta = P.leggi_scheda(str(pcb))
        assert letta["ok"]
        assert letta["larghezza_mm"] == pytest.approx(40, abs=0.1)
        assert letta["altezza_mm"] == pytest.approx(30, abs=0.1)
        assert letta["totale_componenti"] == 0

    def test_le_net_vuote_non_sopravvivono_al_salvataggio(self, kicad, tmp_path):
        """KiCad non salva una net che nessun pad usa. Il ponte lo dichiara
        invece di lasciar credere il contrario: un chiamante che elenca le net
        alla creazione e poi non le ritrova deve sapere perche'."""
        pcb = tmp_path / "vuota.kicad_pcb"
        creata = P.crea_scheda(str(pcb), 40, 30, net=["GND", "+3V3"])
        assert creata["ok"]
        assert set(creata["net_non_persistite"]) == {"GND", "+3V3"}
        assert creata["nota"]
        assert P.leggi_scheda(str(pcb))["net"] == []

    def test_non_sovrascrive_senza_permesso(self, kicad, tmp_path):
        """Una scheda e' lavoro: non si rifa' da zero per sbaglio."""
        pcb = tmp_path / "scheda.kicad_pcb"
        assert P.crea_scheda(str(pcb), 20, 20)["ok"]
        secondo = P.crea_scheda(str(pcb), 30, 30)
        assert secondo["ok"] is False and "gia'" in secondo["errore"]

    def test_sovrascrive_se_richiesto(self, kicad, tmp_path):
        pcb = tmp_path / "scheda.kicad_pcb"
        P.crea_scheda(str(pcb), 20, 20)
        assert P.crea_scheda(str(pcb), 30, 30, sovrascrivi=True)["ok"]

    def test_dimensioni_non_valide(self, kicad, tmp_path):
        esito = P.crea_scheda(str(tmp_path / "x.kicad_pcb"), 0, 30)
        assert esito["ok"] is False

    def test_scheda_inesistente(self, kicad, tmp_path):
        esito = P.leggi_scheda(str(tmp_path / "mai_creata.kicad_pcb"))
        assert esito["ok"] is False and "inesistente" in esito["errore"]


# ---------------------------------------------------------------------------
# Componenti veri
# ---------------------------------------------------------------------------

@pytest.fixture
def scheda(kicad, tmp_path):
    pcb = tmp_path / "montaggio.kicad_pcb"
    P.crea_scheda(str(pcb), 40, 30, net=["GND", "+3V3"])
    return str(pcb)


class TestComponenti:

    def test_aggiunge_un_footprint_di_libreria(self, scheda):
        esito = P.aggiungi_componente(
            scheda, "Capacitor_SMD", "C_0805_2012Metric", "C1", "10uF",
            20, 15, 0, {"1": "+3V3", "2": "GND"})
        assert esito["ok"]
        assert esito["pad"] == 2
        assert {n["net"] for n in esito["net_assegnate"]} == {"+3V3", "GND"}

    def test_il_componente_si_rilegge(self, scheda):
        P.aggiungi_componente(scheda, "Capacitor_SMD", "C_0805_2012Metric",
                              "C1", "10uF", 20, 15, 0, {"1": "+3V3", "2": "GND"})
        letta = P.leggi_scheda(scheda)
        assert letta["totale_componenti"] == 1
        comp = letta["componenti"][0]
        assert comp["riferimento"] == "C1"
        assert comp["valore"] == "10uF"
        assert comp["x_mm"] == pytest.approx(20) and comp["y_mm"] == pytest.approx(15)

    def test_i_pad_portano_la_loro_net(self, scheda):
        P.aggiungi_componente(scheda, "Capacitor_SMD", "C_0805_2012Metric",
                              "C1", "10uF", 20, 15, 0, {"1": "+3V3", "2": "GND"})
        pad = {p["numero"]: p for p in P.leggi_scheda(scheda)["componenti"][0]["pad"]}
        assert pad["1"]["net"] == "+3V3"
        assert pad["2"]["net"] == "GND"

    def test_la_rotazione_sposta_i_pad_come_dice_kicad(self, scheda):
        """Il numero atteso non lo calcoliamo noi: e' dove KiCad mette il pad.

        C_0805 ha il pad 1 a offset (-0,95, 0). A 90 gradi, col centro in
        (20, 15), KiCad lo colloca a (20, 15,95): la rotazione nelle coordinate
        del file e' ORARIA, perche' l'asse Y punta in basso mentre l'angolo e'
        antiorario per chi guarda. E' la stessa convenzione che il parser
        testuale sbagliava, e che qui arriva gratis dalla libreria ufficiale.
        """
        P.aggiungi_componente(scheda, "Capacitor_SMD", "C_0805_2012Metric",
                              "C1", "10uF", 20, 15, 90, {"1": "+3V3", "2": "GND"})
        comp = P.leggi_scheda(scheda)["componenti"][0]
        assert comp["rotazione"] == pytest.approx(90)
        pad = {p["numero"]: p for p in comp["pad"]}
        assert pad["1"]["x_mm"] == pytest.approx(20, abs=0.01)
        assert pad["1"]["y_mm"] == pytest.approx(15.95, abs=0.01)
        assert pad["2"]["y_mm"] == pytest.approx(14.05, abs=0.01)

    def test_net_nuova_viene_creata(self, scheda):
        """Rifiutare un componente per una net non ancora dichiarata
        costringerebbe a elencarle tutte in anticipo."""
        esito = P.aggiungi_componente(
            scheda, "Resistor_SMD", "R_0603_1608Metric", "R1", "10k",
            30, 20, 0, {"1": "SDA", "2": "GND"})
        assert esito["ok"]
        assert "SDA" in P.leggi_scheda(scheda)["net"]

    def test_due_componenti_convivono(self, scheda):
        P.aggiungi_componente(scheda, "Capacitor_SMD", "C_0805_2012Metric",
                              "C1", "10uF", 20, 15, 0, {"1": "+3V3"})
        P.aggiungi_componente(scheda, "Resistor_SMD", "R_0603_1608Metric",
                              "R1", "10k", 30, 20, 0, {"1": "+3V3"})
        riferimenti = {c["riferimento"]
                       for c in P.leggi_scheda(scheda)["componenti"]}
        assert riferimenti == {"C1", "R1"}


# ---------------------------------------------------------------------------
# Gli errori, che devono spiegare
# ---------------------------------------------------------------------------

class TestErrori:

    def test_libreria_inesistente(self, scheda):
        esito = P.aggiungi_componente(scheda, "Libreria_Finta", "X", "R9")
        assert esito["ok"] is False
        assert "inesistente" in esito["errore"].lower()

    def test_footprint_inesistente(self, scheda):
        esito = P.aggiungi_componente(scheda, "Capacitor_SMD",
                                      "C_NON_ESISTE_9999", "C9")
        assert esito["ok"] is False
        assert "non trovato" in esito["errore"].lower()

    def test_riferimento_duplicato(self, scheda):
        """Due pezzi con lo stesso riferimento rendono ambiguo ogni comando
        successivo che li nomini."""
        P.aggiungi_componente(scheda, "Capacitor_SMD", "C_0805_2012Metric",
                              "C1", "10uF", 20, 15)
        secondo = P.aggiungi_componente(scheda, "Capacitor_SMD",
                                        "C_0805_2012Metric", "C1", "1uF", 25, 15)
        assert secondo["ok"] is False and "C1" in secondo["errore"]

    def test_scheda_mancante(self, kicad, tmp_path):
        esito = P.aggiungi_componente(str(tmp_path / "vuoto.kicad_pcb"),
                                      "Capacitor_SMD", "C_0805_2012Metric", "C1")
        assert esito["ok"] is False

    def test_comando_sconosciuto_non_esplode(self, kicad):
        esito = P._esegui("comando_che_non_esiste")
        assert esito["ok"] is False and "sconosciuto" in esito["errore"]
