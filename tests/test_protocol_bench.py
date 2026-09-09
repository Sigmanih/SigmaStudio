"""Misurare l'aderenza al protocollo, non la cultura generale.

I benchmark che abbiamo misurano domande e risposte. Sono due abilita' diverse:
su questa macchina un modello da 8B con un punteggio rispettabile copiava
`PERCORSO` e `TESTO_ESATTO_DA_SOSTITUIRE` **come valori** — leggeva gli esempi
del prompt e li ripeteva alla lettera. Nessun quiz lo avrebbe mai detto.

Questi test non fanno girare un modello: fanno girare **le prove** su tracce
costruite a mano, per verificare che riconoscano quello che devono riconoscere.
E' l'unico modo di sapere se un metro misura: dargli qualcosa di cui si conosce
gia' la lunghezza.
"""

import json
from pathlib import Path

import pytest

from core.harness import protocol_bench as PB


def _traccia(chiamate, turni=5, raggiunto=True):
    t = PB.Traccia(turni=turni, obiettivo_raggiunto=raggiunto)
    for nome, params, ok in chiamate:
        t.chiamate.append({"tool": nome, "params": params, "ok": ok, "error": ""})
    return t


NOTI = {"spec", "read_file", "write_file", "edit_file", "terminal", "complete_goal",
        "pipeline", "list_dir", "write"}


class TestNomiVeri:
    def test_un_tool_inventato_viene_visto(self):
        t = _traccia([("apri_file", {}, False)])
        p = PB.prova_nomi_veri(t, NOTI)
        assert p.superata is False
        assert "apri_file" in p.dettaglio

    def test_gli_alias_non_contano_come_invenzioni(self):
        """`write` e `write_file` sono lo stesso tool: rifiutare il primo
        misurerebbe il vocabolario, non l'aderenza."""
        t = _traccia([("write", {"path": "a.py"}, True)])
        assert PB.prova_nomi_veri(t, NOTI).superata is True


class TestSegnaposto:
    def test_copiare_un_segnaposto_del_prompt_e_il_fallimento_piu_netto(self):
        """Il modo di fallire dell'8B, registrato e ora misurabile."""
        t = _traccia([("write_file", {"path": "PERCORSO", "content": "x"}, False)])
        p = PB.prova_niente_segnaposto(t)
        assert p.superata is False
        assert "PERCORSO" in p.dettaglio

    def test_un_percorso_vero_non_fa_scattare_niente(self):
        t = _traccia([("write_file", {"path": "core/app.py", "content": "x"}, True)])
        assert PB.prova_niente_segnaposto(t).superata is True

    def test_riconosce_anche_l_ancora_copiata(self):
        t = _traccia([("edit_file",
                       {"path": "a.py", "old_string": "TESTO_ESATTO_DA_SOSTITUIRE"},
                       False)])
        assert PB.prova_niente_segnaposto(t).superata is False


class TestOrdineDelLavoro:
    def test_spec_deve_venire_per_prima(self):
        t = _traccia([("list_dir", {}, True), ("spec", {}, True)])
        p = PB.prova_spec_per_prima(t)
        assert p.superata is False
        assert "posto 2" in p.dettaglio

    def test_non_chiamarla_mai_e_peggio(self):
        t = _traccia([("read_file", {}, True)])
        assert "mai chiamata" in PB.prova_spec_per_prima(t).dettaglio

    def test_modificare_senza_aver_letto_viene_visto(self):
        """Senza aver letto il file non si conosce il testo esatto: l'ancora
        e' inventata."""
        t = _traccia([("edit_file", {"path": "config.py", "old_string": "X"}, False)])
        p = PB.prova_legge_prima_di_modificare(t)
        assert p.superata is False
        assert "config.py" in p.dettaglio

    def test_leggere_e_poi_modificare_va_bene(self):
        t = _traccia([
            ("read_file", {"path": "config.py"}, True),
            ("edit_file", {"path": "config.py", "old_string": "X"}, True),
        ])
        assert PB.prova_legge_prima_di_modificare(t).superata is True

    def test_una_lettura_fallita_non_conta_come_lettura(self):
        t = _traccia([
            ("read_file", {"path": "config.py"}, False),
            ("edit_file", {"path": "config.py"}, False),
        ])
        assert PB.prova_legge_prima_di_modificare(t).superata is False


class TestChiusura:
    def test_chiudere_senza_aver_verificato_niente(self):
        t = _traccia([("write_file", {"path": "a.py"}, True),
                      ("complete_goal", {}, False)])
        p = PB.prova_verifica_prima_di_chiudere(t)
        assert p.superata is False
        assert "senza eseguire" in p.dettaglio

    def test_una_verifica_prima_della_chiusura_basta(self):
        t = _traccia([("write_file", {"path": "a.py"}, True),
                      ("terminal", {"command": "python -m pytest"}, True),
                      ("complete_goal", {}, True)])
        assert PB.prova_verifica_prima_di_chiudere(t).superata is True

    def test_non_provare_mai_a_chiudere_non_e_una_scusante(self):
        t = _traccia([("write_file", {"path": "a.py"}, True)], raggiunto=False)
        assert PB.prova_verifica_prima_di_chiudere(t).superata is False

    def test_chiudere_senza_nominare_i_criteri(self):
        t = _traccia([("complete_goal", {"summary": "fatto"}, True)])
        p = PB.prova_chiude_con_prove(t, ["il file locales/it.json esiste"])
        assert p.superata is False

    def test_chiudere_nominando_le_prove(self):
        t = _traccia([("complete_goal",
                       {"evidence": {"il file locales/it.json esiste":
                                     "creato e validato con json.tool"}}, True)])
        assert PB.prova_chiude_con_prove(t, ["il file locales/it.json esiste"]).superata is True


class TestReazioneAlRifiuto:
    def test_ripetere_identico_dopo_un_rifiuto_viene_visto(self):
        """E' il segno che il modello non ha letto la risposta: su un run vero
        e' costato 45 secondi su 62."""
        stessa = {"summary": "fatto"}
        t = _traccia([("complete_goal", stessa, False), ("complete_goal", stessa, False)])
        p = PB.prova_reagisce_al_rifiuto(t)
        assert p.superata is False
        assert "1 ripetizioni" in p.dettaglio

    def test_cambiare_approccio_dopo_un_rifiuto_va_bene(self):
        t = _traccia([("complete_goal", {"summary": "fatto"}, False),
                      ("terminal", {"command": "python -m pytest"}, True),
                      ("complete_goal", {"summary": "fatto, con test"}, True)])
        assert PB.prova_reagisce_al_rifiuto(t).superata is True

    def test_ripetere_dopo_un_successo_non_e_un_problema(self):
        """Leggere due volte lo stesso file e' inefficiente, non e' non aderire."""
        stessa = {"path": "a.py"}
        t = _traccia([("read_file", stessa, True), ("read_file", stessa, True)])
        assert PB.prova_reagisce_al_rifiuto(t).superata is True


class TestScritturaDaTerminale:
    def test_creare_un_file_da_riga_di_comando_viene_visto(self):
        """Un file scritto cosi' non ha backup, non passa dal controllo di
        sintassi e non risulta fra le modifiche."""
        t = _traccia([("terminal",
                       {"command": "python -c \"open('a.py','w').write_text('x')\""},
                       True)])
        assert PB.prova_non_scrive_da_terminale(t).superata is False

    def test_un_comando_di_verifica_non_e_una_scrittura(self):
        t = _traccia([("terminal", {"command": "python -m pytest tests/ -q"}, True)])
        assert PB.prova_non_scrive_da_terminale(t).superata is True


class TestEfficienza:
    def test_non_arrivare_in_fondo_e_un_fallimento(self):
        """Un modello che non chiude non e' utilizzabile in un ventaglio."""
        t = _traccia([("spec", {}, True)], turni=14, raggiunto=False)
        p = PB.prova_arriva_in_fondo(t, 14)
        assert p.superata is False
        assert "14 turni" in p.dettaglio


class TestLetturaDelTranscript:
    def test_gli_eventi_diventano_chiamate_interrogabili(self):
        eventi = [
            {"type": "tool_result", "tool": "spec", "result": {"success": True}},
            {"type": "tool_result", "tool": "write_file",
             "result": {"success": True, "path": "a.py"}},
            {"type": "run_metrics", "turns": 6, "goal_reached": True},
        ]
        t = PB.osserva(eventi)
        assert t.nomi() == ["spec", "write_file"]
        assert t.turni == 6
        assert t.obiettivo_raggiunto is True
        assert t.primo("write_file") == 1

    def test_un_tool_mai_chiamato_non_ha_posizione(self):
        assert PB.osserva([]).primo("spec") == -1


class TestControlliSulRisultato:
    def test_il_json_atteso_viene_verificato(self, tmp_path):
        (tmp_path / "locales").mkdir()
        (tmp_path / "locales" / "it.json").write_text('{"titolo": "Ciao"}', encoding="utf-8")
        controlla = PB._controlla_json("locales/it.json", "titolo", "Ciao")
        assert controlla(tmp_path) == ""

    def test_un_valore_sbagliato_viene_detto(self, tmp_path):
        (tmp_path / "locales").mkdir()
        (tmp_path / "locales" / "it.json").write_text('{"titolo": "Hello"}', encoding="utf-8")
        motivo = PB._controlla_json("locales/it.json", "titolo", "Ciao")(tmp_path)
        assert "Hello" in motivo

    def test_un_file_mancante_viene_detto(self, tmp_path):
        assert "non esiste" in PB._controlla_json("x.json", "a", "b")(tmp_path)

    def test_un_json_rotto_viene_detto(self, tmp_path):
        (tmp_path / "x.json").write_text("{non json", encoding="utf-8")
        assert "non e' JSON valido" in PB._controlla_json("x.json", "a", "b")(tmp_path)


class TestIlRapporto:
    def test_il_punteggio_e_la_frazione_di_prove_superate(self):
        e = PB.EsitoScenario(scenario="x", model="m", prove=[
            PB.Prova("a", "", superata=True),
            PB.Prova("b", "", superata=True),
            PB.Prova("c", "", superata=False),
            PB.Prova("d", "", superata=False),
        ])
        assert e.punteggio == 50.0
        assert e.superate == 2

    def test_gli_scenari_sono_preparati_su_disco(self):
        """Ogni scenario deve poter essere allestito davvero, altrimenti il
        banco misura un ambiente che non esiste."""
        for scenario in PB.SCENARI:
            radice = PB._prepara(scenario)
            try:
                for percorso in scenario.file:
                    assert (radice / percorso).is_file(), f"{scenario.id}: manca {percorso}"
                assert (radice / ".git").is_dir(), f"{scenario.id}: non e' un repo"
            finally:
                # `ignore_errors` lasciava mezze cartelle: su Windows gli
                # oggetti dentro `.git` sono in sola lettura e `rmtree` si
                # ferma sul primo, senza dirlo. Se ne trovano sei nella
                # cartella temporanea dopo pochi giri.
                PB.pulisci(radice)

    def test_ogni_scenario_dichiara_come_si_dimostra(self):
        """Senza, l'agente deve indovinare la verifica e il banco misurerebbe
        anche quello — che e' un'altra cosa."""
        for scenario in PB.SCENARI:
            assert scenario.verifica, f"{scenario.id} non dichiara una verifica"
            assert scenario.criteri, f"{scenario.id} non dichiara criteri"
            assert scenario.controllo is not None, f"{scenario.id} non controlla il risultato"


class TestRaggiungibilita:
    def test_si_puo_lanciare_da_riga_di_comando(self):
        assert callable(PB._main)

    def test_il_rapporto_e_leggibile_dal_cancello(self):
        """Cosi' un run che misura un modello puo' dimostrare di averlo fatto."""
        from core.harness.verification import parse_verification

        riga = "SIGMA-CHECK " + json.dumps(
            {"check": "protocollo-tool", "checked": 20, "problems": 0})
        assert parse_verification("python -m core.harness.protocol_bench m", 0,
                                  riga).is_valid is True


class TestLaSandboxNonRestaInGiro:
    """Ogni esecuzione del banco allestisce un repository temporaneo. Senza
    pulizia, su una macchina che gira da mesi diventano gigabyte di repository
    morti — e su Windows non basta `rmtree`, perche' gli oggetti dentro `.git`
    sono in sola lettura e la cancellazione si ferma sul primo senza dirlo."""

    def test_pulisci_rimuove_anche_un_repository_git(self, tmp_path):
        import subprocess

        radice = tmp_path / "sandbox"
        radice.mkdir()
        (radice / "app.py").write_text("X = 1\n", encoding="utf-8")
        for a in (["init", "-b", "main"], ["config", "user.email", "t@s"],
                  ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git"] + a, cwd=str(radice), capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=str(radice), capture_output=True)
        subprocess.run(["git", "commit", "-m", "x"], cwd=str(radice), capture_output=True)
        assert (radice / ".git").is_dir()

        PB.pulisci(radice)

        assert not radice.exists(), "la sandbox non e' stata rimossa del tutto"

    def test_pulisci_non_esplode_su_una_cartella_che_non_c_e(self, tmp_path):
        PB.pulisci(tmp_path / "mai_esistita")

    def test_una_prova_riuscita_non_lascia_niente(self):
        """E una fallita lascia tutto, perche' e' l'unica cosa che spiega."""
        import inspect

        sorgente = inspect.getsource(PB.esegui_scenario)
        assert "pulisci(radice)" in sorgente
        assert "esito.sandbox = str(radice)" in sorgente


class TestIlTempoEUnaMisura:
    """Un banco che aspetta all'infinito non distingue «lento» da «bloccato»,
    e proprio la lentezza e' cio' che si vuole misurare: gemma-12B ha tenuto la
    macchina occupata 24 minuti su due scenari da tre righe, senza emettere una
    riga di avanzamento. Non e' un modello da scartare per questo — e' un fatto
    che il banco deve dire in cinque minuti invece che in venticinque.
    """

    def test_ogni_scenario_ha_un_tetto_di_tempo(self):
        for scenario in PB.SCENARI:
            assert scenario.tetto_secondi > 0

    def test_lo_scenario_scaduto_lo_dichiara(self, monkeypatch, tmp_path):
        """Fermarsi senza dirlo sarebbe peggio di non fermarsi."""
        import core.harness.loop as modulo_loop

        def infinito(messages, **kw):
            # Consuma tempo davvero: senza, diecimila yield finiscono in un
            # millisecondo e il tetto non fa in tempo a scattare — il finto
            # sarebbe piu' veloce del fenomeno che deve simulare.
            import time as _t

            annulla = kw.get("should_cancel")
            for _ in range(10000):
                if annulla and annulla():
                    break
                _t.sleep(0.005)
                yield {"type": "token", "text": "..."}
            yield {"type": "run_metrics", "turns": 3, "goal_reached": False}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", infinito)
        scenario = PB.Scenario(
            id="lento", descrizione="", file={"a.py": "X = 1\n"},
            obiettivo="fai qualcosa", criteri=["fatto"],
            verifica="python -c \"pass\"", tetto_secondi=0.05,
        )

        esito = PB.esegui_scenario(scenario, "modello-lento")

        assert esito.scaduto is True
        assert "oltre il tempo concesso" in esito.errore
        PB.pulisci(Path(esito.sandbox)) if esito.sandbox else None

    def test_uno_scenario_veloce_non_risulta_scaduto(self, monkeypatch):
        import core.harness.loop as modulo_loop

        def svelto(messages, **kw):
            yield {"type": "run_metrics", "turns": 2, "goal_reached": True}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", svelto)
        scenario = PB.Scenario(
            id="svelto", descrizione="", file={"a.py": "X = 1\n"},
            obiettivo="fai", criteri=["fatto"], verifica="python -c \"pass\"",
            tetto_secondi=60.0,
        )
        esito = PB.esegui_scenario(scenario, "m")
        assert esito.scaduto is False
        if esito.sandbox:
            PB.pulisci(Path(esito.sandbox))


class TestSiVedeCosaStaFacendo:
    def test_il_banco_riferisce_scenario_per_scenario(self, monkeypatch):
        """Venti minuti di silenzio non dicono a chi guarda se convenga
        aspettare."""
        import core.harness.loop as modulo_loop

        def svelto(messages, **kw):
            yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", svelto)
        visti = []
        PB.esegui("m", scenari=["file_nuovo"], progresso=visti.append)

        fasi = [v["fase"] for v in visti]
        assert "inizio" in fasi and "fine" in fasi
        assert visti[0]["scenario"] == "file_nuovo"
        assert visti[0]["totale"] == 1


class TestIlConteggioDeiTurniNonMente:
    """Un run fermato per tempo scaduto non emette il consuntivo finale: dire
    «fermo dopo 0 turni» su un modello che ne ha fatti dodici e' un resoconto
    che mente, ed e' esattamente cosa e' comparso nella prima misura vera."""

    def test_i_turni_si_contano_anche_senza_consuntivo(self):
        eventi = [
            {"type": "turn_start", "turn": 1},
            {"type": "tool_result", "tool": "spec", "result": {"success": True}},
            {"type": "turn_start", "turn": 2},
            {"type": "tool_result", "tool": "write_file", "result": {"success": True}},
            {"type": "turn_start", "turn": 3},
        ]
        t = PB.osserva(eventi)
        assert t.turni == 0, "senza consuntivo non c'e' un totale dichiarato"
        assert t.turni_visti == 3

    def test_il_consuntivo_quando_c_e_ha_la_precedenza(self):
        eventi = [
            {"type": "turn_start", "turn": 1},
            {"type": "run_metrics", "turns": 9, "goal_reached": True},
        ]
        t = PB.osserva(eventi)
        assert t.turni == 9


class TestUnModelloCheNonRispondeNonHaUnPunteggio:
    """E' successo davvero: il Qwen 27B non si e' caricato, e il banco ha
    stampato 50.0 — meta' delle prove sono negative per costruzione quando non
    succede niente. Un numero che sembra una misura e non lo e' e' peggio di
    nessun numero, perche' finisce in una tabella e qualcuno ci decide sopra.
    """

    def _senza_risposta(self, monkeypatch, eventi):
        import core.harness.loop as modulo_loop

        def muto(messages, **kw):
            for e in eventi:
                yield e

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", muto)
        scenario = PB.Scenario(
            id="muto", descrizione="", file={"a.py": "X = 1\n"},
            obiettivo="fai", criteri=["fatto"], verifica="python -c \"pass\"",
        )
        return PB.esegui_scenario(scenario, "modello-che-non-parte")

    def test_nessuna_chiamata_e_nessun_testo_non_e_un_punteggio(self, monkeypatch):
        esito = self._senza_risposta(monkeypatch, [
            {"type": "run_metrics", "turns": 14, "goal_reached": False},
        ])
        assert esito.prove == []
        assert "non si e' caricato" in esito.errore

    def test_l_errore_del_motore_viene_riportato_tale_e_quale(self, monkeypatch):
        esito = self._senza_risposta(monkeypatch, [
            {"type": "error", "error": "failed to load model"},
            {"type": "run_metrics", "turns": 1, "goal_reached": False},
        ])
        assert "failed to load model" in esito.errore

    def test_uno_scenario_non_misurato_non_entra_nella_media(self, monkeypatch):
        import core.harness.loop as modulo_loop

        def muto(messages, **kw):
            yield {"type": "run_metrics", "turns": 1, "goal_reached": False}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", muto)
        rapporto = PB.esegui("m", scenari=["file_nuovo"])

        assert rapporto["totali"] == 0
        assert rapporto["punteggio"] == 0.0
        assert "file_nuovo" in rapporto["non_misurati"]

    def test_una_risposta_anche_solo_testuale_vale_come_misura(self, monkeypatch):
        """Un modello che parla e sbaglia e' misurabile: e' diverso da uno che
        non c'e'."""
        esito = self._senza_risposta(monkeypatch, [
            {"type": "token", "text": "Ci penso io."},
            {"type": "run_metrics", "turns": 3, "goal_reached": False},
        ])
        assert esito.prove, "un modello che ha parlato va misurato"
        if esito.sandbox:
            PB.pulisci(Path(esito.sandbox))
