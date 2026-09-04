"""Il permesso d'uso dei tool, e i due modi in cui si aggira da solo.

La policy esiste perche' `DevRole.tools` era una dichiarazione senza effetto:
il Reviewer poteva scrivere file come il Coder. Renderla effettiva introduce
pero' due modi di sbagliare che questi test fissano.

Il primo e' l'alias: l'agente accetta `write`, `shell`, `rm` come sinonimi, e
una policy che confronta stringhe grezze sarebbe aggirata dal primo sinonimo
che il modello sceglie di usare — cioe' subito, perche' i modelli locali li
usano tutti.

Il secondo e' l'eccesso di zelo: vietare a un ruolo di chiudere il proprio
lavoro lo renderebbe incapace di finire, e un elenco di tool dimenticato non
deve valere come divieto totale.
"""

import pytest

from core.developer_studio.role_engine import DEV_ROLES, RoleEngine
from core.developer_studio.tool_policy import (
    CONTROL_TOOLS,
    ToolPolicy,
    canonical,
)


class TestNomeCanonico:
    def test_gli_alias_di_scrittura_collassano_su_uno(self):
        for alias in ("write", "save_file", "write_file"):
            assert canonical(alias) == "write_file"

    def test_gli_alias_di_esecuzione_collassano_su_uno(self):
        for alias in ("shell", "exec", "command", "terminal"):
            assert canonical(alias) == "terminal"

    def test_gli_alias_di_cancellazione_collassano_su_uno(self):
        for alias in ("rm", "delete_file", "remove_file", "delete"):
            assert canonical(alias) == "delete"

    def test_un_tool_mcp_passa_immutato(self):
        """I tool del bridge non hanno alias: la policy li nomina come il bridge."""
        for nome in ("git_commit", "run_tests", "lint_python"):
            assert canonical(nome) == nome

    def test_il_nome_e_normalizzato_ma_non_inventato(self):
        assert canonical("  WRITE_FILE ") == "write_file"
        assert canonical("tool_inesistente") == "tool_inesistente"
        assert canonical("") == ""


class TestRestrizione:
    def test_un_elenco_vuoto_non_e_un_divieto(self):
        """Un elenco dimenticato e' un incidente, non la volonta' di bloccare tutto."""
        for vuoto in (None, (), []):
            policy = ToolPolicy.of(vuoto)
            assert not policy.restricted
            assert policy.permits("terminal")

    def test_cio_che_non_e_elencato_e_vietato(self):
        policy = ToolPolicy.of(("read_file", "search_code"), label="Reviewer")
        assert policy.permits("read_file")
        assert not policy.permits("write_file")
        assert not policy.permits("terminal")

    def test_il_divieto_non_si_aggira_con_un_alias(self):
        """Il punto dell'intero modulo: `shell` e' `terminal` anche se si chiama altrimenti."""
        policy = ToolPolicy.of(("read_file",))
        for alias in ("shell", "exec", "command", "rm", "write", "str_replace"):
            assert not policy.permits(alias), alias

    def test_il_permesso_vale_per_tutti_gli_alias(self):
        policy = ToolPolicy.of(("terminal",))
        for alias in ("shell", "exec", "command", "terminal"):
            assert policy.permits(alias), alias

    def test_i_tool_di_controllo_restano_sempre_permessi(self):
        """Vietare `complete_goal` renderebbe il ruolo incapace di dichiarare finito."""
        policy = ToolPolicy.of(("read_file",))
        for tool in CONTROL_TOOLS:
            assert policy.permits(tool)
        assert policy.permits("finish_task")  # alias di complete_goal


class TestMessaggioDiRifiuto:
    def test_il_rifiuto_nomina_le_alternative(self):
        """Un rifiuto che non dice cosa si puo' fare produce un secondo tentativo identico."""
        policy = ToolPolicy.of(("read_file", "search_code"), label="Reviewer")
        messaggio = policy.refusal("terminal")
        assert "terminal" in messaggio
        assert "read_file" in messaggio
        assert "Reviewer" in messaggio

    def test_il_rifiuto_usa_il_nome_canonico(self):
        policy = ToolPolicy.of(("read_file",))
        assert "terminal" in policy.refusal("shell")

    def test_la_sezione_di_prompt_esiste_solo_se_c_e_una_restrizione(self):
        assert ToolPolicy.unrestricted().prompt_section() == ""
        sezione = ToolPolicy.of(("read_file",)).prompt_section()
        assert "read_file" in sezione


class TestCoerenzaConIRuoli:
    """La policy e `is_tool_allowed` devono rispondere la stessa cosa.

    Sono due strade verso la stessa domanda: una la percorre la UI per dire
    all'utente cosa il ruolo puo' fare, l'altra il loop per decidere se
    eseguire. Divergere significherebbe mostrare un permesso e negarne un altro.
    """

    @pytest.mark.parametrize("role_id", sorted(DEV_ROLES))
    def test_ogni_ruolo_puo_usare_i_propri_tool(self, role_id):
        engine = RoleEngine()
        role = DEV_ROLES[role_id]
        for tool in role.tools:
            assert engine.is_tool_allowed(role_id, tool), f"{role_id}/{tool}"

    def test_il_coder_non_puo_spingere_su_git(self):
        assert not RoleEngine().is_tool_allowed("coder", "git_push")

    def test_il_reviewer_non_puo_eseguire_comandi(self):
        engine = RoleEngine()
        assert not engine.is_tool_allowed("reviewer", "terminal")
        assert not engine.is_tool_allowed("reviewer", "shell")

    @pytest.mark.parametrize("role_id", sorted(DEV_ROLES))
    def test_ogni_ruolo_ha_un_budget_di_turni_sufficiente(self, role_id):
        """Cinque turni per tutti era il difetto: non bastano a leggere, modificare e verificare."""
        assert DEV_ROLES[role_id].max_turns >= 10
