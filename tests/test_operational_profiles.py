"""I profili operativi, e l'approvazione che deve davvero fermare il lavoro.

Due cose che esistevano solo a meta'. I profili `read_only` e `plan_only`
erano definiti e non chiamati da nessuno: un permesso dichiarato e mai
applicato, cioe' il tipo di sicurezza che sembra esserci. L'orchestratore
emetteva `approval_required` e proseguiva comunque: chiedere il permesso senza
ascoltare la risposta e' peggio che non chiedere, perche' l'utente crede di
avere un veto che non ha.
"""

import threading
import time

import pytest

from core.harness.policy import ToolPolicy


class TestProfili:
    def test_in_sola_lettura_non_si_scrive_ne_si_esegue(self):
        p = ToolPolicy.for_profile("read_only")
        assert p.permits("read_file")
        assert p.permits("search_code")
        assert not p.permits("write_file")
        assert not p.permits("edit_file")
        assert not p.permits("terminal")
        assert not p.permits("delete")

    def test_in_sola_pianificazione_non_si_guarda_nemmeno_la_pagina(self):
        p = ToolPolicy.for_profile("plan_only")
        assert p.permits("read_file")
        assert not p.permits("screenshot")
        assert not p.permits("write_file")

    def test_un_profilo_sconosciuto_non_restringe(self):
        """Un nome sbagliato non deve bloccare il lavoro in silenzio."""
        for nome in ("", "qualsiasi_cosa", None):
            assert not ToolPolicy.for_profile(nome).restricted

    def test_i_profili_non_si_aggirano_con_un_alias(self):
        p = ToolPolicy.for_profile("read_only")
        for alias in ("shell", "exec", "write", "rm", "str_replace"):
            assert not p.permits(alias), alias

    def test_anche_in_sola_lettura_si_puo_chiudere_il_lavoro(self):
        """Un audit deve poter dichiarare finito cio' che ha analizzato."""
        p = ToolPolicy.for_profile("read_only")
        assert p.permits("complete_goal")
        assert p.permits("spec")


class TestIntersezione:
    """Il profilo e' un tetto, il ruolo restringe dentro quel tetto."""

    def test_il_profilo_vince_sui_tool_del_ruolo(self):
        coder = ToolPolicy.of(("read_file", "write_file", "terminal"), label="Coder")
        risultante = ToolPolicy.for_profile("read_only").intersect(coder)
        assert risultante.permits("read_file")
        assert not risultante.permits("write_file")
        assert not risultante.permits("terminal")

    def test_il_ruolo_restringe_dentro_il_profilo(self):
        ristretto = ToolPolicy.of(("read_file",), label="Reviewer")
        risultante = ToolPolicy.for_profile("read_only").intersect(ristretto)
        assert risultante.permits("read_file")
        assert not risultante.permits("search_code")

    def test_intersecare_con_nessuna_restrizione_non_cambia_nulla(self):
        profilo = ToolPolicy.for_profile("read_only")
        assert profilo.intersect(ToolPolicy.unrestricted()).visible_tools() == profilo.visible_tools()
        assert ToolPolicy.unrestricted().intersect(profilo).visible_tools() == profilo.visible_tools()

    def test_l_intersezione_conserva_i_tool_di_controllo(self):
        """Anche restringendo fino all'osso, si deve poter chiudere."""
        a = ToolPolicy.of(("read_file",))
        b = ToolPolicy.of(("terminal",))
        assert a.intersect(b).permits("complete_goal")

    def test_l_etichetta_dice_da_dove_viene_il_divieto(self):
        risultante = ToolPolicy.for_profile("read_only").intersect(
            ToolPolicy.of(("read_file",), label="Reviewer")
        )
        assert "Sola Lettura" in risultante.label
        assert "Reviewer" in risultante.label


class TestApprovazioneDelleFasi:
    """L'attesa vera, non l'evento emesso e dimenticato."""

    @pytest.fixture
    def orchestratore(self):
        modulo = pytest.importorskip(
            "core.modules.sigma_developer_lab.orchestrator",
            reason="modulo sigma_developer_lab non installato",
        )
        return modulo.DevOrchestrator(workspace_root=".", session_id="test")

    def test_una_decisione_arrivata_prima_dell_attesa_non_si_perde(self, orchestratore):
        """La UI puo' rispondere prima che il thread arrivi ad aspettare."""
        orchestratore.approve("analyze", "approved")
        assert orchestratore._wait_for_approval("analyze") == "approved"

    def test_l_approvazione_sblocca_chi_aspetta(self, orchestratore):
        esito = {}

        def attende():
            esito["decisione"] = orchestratore._wait_for_approval("implement")

        t = threading.Thread(target=attende, daemon=True)
        t.start()
        for _ in range(100):          # attende che il thread sia in attesa
            if orchestratore.pending_approval() == "implement":
                break
            time.sleep(0.01)

        assert orchestratore.approve("implement", "approved") is True
        t.join(timeout=5)
        assert esito["decisione"] == "approved"

    def test_il_rifiuto_arriva_come_rifiuto(self, orchestratore):
        esito = {}
        t = threading.Thread(
            target=lambda: esito.update(d=orchestratore._wait_for_approval("verify")),
            daemon=True,
        )
        t.start()
        for _ in range(100):
            if orchestratore.pending_approval() == "verify":
                break
            time.sleep(0.01)
        orchestratore.approve("verify", "rejected")
        t.join(timeout=5)
        assert esito["d"] == "rejected"

    def test_annullare_sblocca_chi_aspetta(self, orchestratore):
        """Premere stop non deve lasciare un thread fermo fino al timeout."""
        esito = {}
        t = threading.Thread(
            target=lambda: esito.update(d=orchestratore._wait_for_approval("deliver")),
            daemon=True,
        )
        t.start()
        for _ in range(100):
            if orchestratore.pending_approval() == "deliver":
                break
            time.sleep(0.01)
        orchestratore.cancel()
        t.join(timeout=5)
        assert esito["d"] == "rejected"

    def test_approvare_una_fase_che_nessuno_aspetta_lo_dice(self, orchestratore):
        """La UI deve poter distinguere una risposta accolta da una in ritardo."""
        assert orchestratore.approve("fase_inesistente") is False

    def test_il_timeout_non_vale_come_consenso(self, orchestratore, monkeypatch):
        modulo = pytest.importorskip("core.modules.sigma_developer_lab.orchestrator")
        monkeypatch.setattr(modulo, "APPROVAL_TIMEOUT_S", 0.05)
        assert orchestratore._wait_for_approval("analyze") == "timeout"
