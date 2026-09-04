"""I ruoli come dato: cosa deve reggere perche' si possano modificare a mano.

Un ruolo modificabile da un file e' la premessa di tutto il resto — la tab
Pipelines che lo edita, lo scheduler che ne legge il modello, il provider che
lo espone. Ma un file scritto a mano e' anche il posto dove si sbaglia, e le
tre cose che non devono succedere sono: un file rotto che lascia il sistema
senza ruoli, un campo con un refuso applicato in silenzio, e un file che
ricopia i predefiniti diventando la copia da aggiornare a mano.
"""

import json

import pytest

from core.harness import role_registry
from core.harness.roles import DEV_ROLES, RoleEngine


@pytest.fixture
def config_isolata(tmp_path, monkeypatch):
    percorso = tmp_path / "roles.json"
    monkeypatch.setattr(role_registry, "roles_config_file", lambda: percorso)
    role_registry.invalidate()
    yield percorso
    role_registry.invalidate()


def _scrivi(percorso, ruoli):
    percorso.write_text(json.dumps({"roles": ruoli}), encoding="utf-8")


class TestComposizione:
    def test_senza_file_valgono_i_predefiniti(self, config_isolata):
        ruoli = role_registry.load_roles()
        assert set(ruoli) == set(DEV_ROLES)

    def test_un_campo_ridefinito_non_ne_trascina_altri(self, config_isolata):
        """Cambiare il modello del Coder non deve costringere a ricopiarne il prompt."""
        _scrivi(config_isolata, {"coder": {"model": "qwen2.5-coder-7b"}})
        coder = role_registry.load_roles()["coder"]
        assert coder.model == "qwen2.5-coder-7b"
        assert coder.system_prompt == DEV_ROLES["coder"].system_prompt
        assert coder.tools == DEV_ROLES["coder"].tools

    def test_le_sequenze_arrivano_come_tuple(self, config_isolata):
        _scrivi(config_isolata, {"reviewer": {"tools": ["read_file", "search_code"]}})
        reviewer = role_registry.load_roles()["reviewer"]
        assert reviewer.tools == ("read_file", "search_code")

    def test_si_puo_aggiungere_un_ruolo_nuovo(self, config_isolata):
        _scrivi(config_isolata, {
            "docs": {
                "name": "Documentalista",
                "system_prompt": "Scrivi documentazione.",
                "tools": ["read_file", "write_file"],
                "model": "qwen3-8b",
            }
        })
        ruoli = role_registry.load_roles()
        assert "docs" in ruoli
        assert ruoli["docs"].model == "qwen3-8b"
        assert ruoli["docs"].max_turns == 12          # default del dataclass

    def test_un_ruolo_nuovo_senza_prompt_viene_scartato(self, config_isolata):
        """Senza prompt non e' un ruolo: applicarlo darebbe un agente muto."""
        _scrivi(config_isolata, {"vuoto": {"name": "Vuoto"}})
        assert "vuoto" not in role_registry.load_roles()


class TestRobustezza:
    def test_un_file_rotto_non_lascia_il_sistema_senza_ruoli(self, config_isolata):
        config_isolata.write_text("{ questo non e' json", encoding="utf-8")
        assert set(role_registry.load_roles()) == set(DEV_ROLES)

    def test_un_campo_sconosciuto_viene_ignorato_non_applicato(self, config_isolata):
        """Un refuso non deve valere come impostazione attiva."""
        _scrivi(config_isolata, {"coder": {"temperatura": 0.9, "temperature": 0.15}})
        assert role_registry.load_roles()["coder"].temperature == 0.15

    def test_l_id_non_si_riscrive_dal_file(self, config_isolata):
        _scrivi(config_isolata, {"coder": {"id": "altro", "temperature": 0.11}})
        ruoli = role_registry.load_roles()
        assert "altro" not in ruoli
        assert ruoli["coder"].id == "coder"

    def test_anche_un_elenco_invece_di_un_oggetto_funziona(self, config_isolata):
        """I file scritti a mano alternano le due forme: accettarle entrambe costa poco."""
        config_isolata.write_text(
            json.dumps({"roles": [{"id": "coder", "temperature": 0.12}]}),
            encoding="utf-8",
        )
        assert role_registry.load_roles()["coder"].temperature == 0.12

    def test_una_modifica_al_file_viene_rivista(self, config_isolata):
        _scrivi(config_isolata, {"coder": {"temperature": 0.11}})
        assert role_registry.load_roles()["coder"].temperature == 0.11
        _scrivi(config_isolata, {"coder": {"temperature": 0.22}})
        assert role_registry.load_roles(force=True)["coder"].temperature == 0.22


class TestScrittura:
    def test_salva_solo_cio_che_differisce(self, config_isolata):
        """Un file che ricopia i predefiniti e' la copia da aggiornare a mano."""
        role_registry.save_role("coder", {"model": "qwen2.5-coder-7b"})
        salvato = json.loads(config_isolata.read_text(encoding="utf-8"))
        assert salvato["roles"]["coder"] == {"model": "qwen2.5-coder-7b"}

    def test_salvare_due_volte_accumula_invece_di_sostituire(self, config_isolata):
        role_registry.save_role("coder", {"model": "qwen2.5-coder-7b"})
        role_registry.save_role("coder", {"max_turns": 30})
        salvato = json.loads(config_isolata.read_text(encoding="utf-8"))["roles"]["coder"]
        assert salvato == {"model": "qwen2.5-coder-7b", "max_turns": 30}

    def test_un_campo_non_modificabile_viene_rifiutato(self, config_isolata):
        with pytest.raises(ValueError):
            role_registry.save_role("coder", {"qualcosa_di_inventato": 1})

    def test_il_ruolo_risultante_torna_al_chiamante(self, config_isolata):
        risultante = role_registry.save_role("coder", {"max_turns": 40})
        assert risultante["id"] == "coder"
        assert risultante["max_turns"] == 40

    def test_il_ripristino_riporta_al_predefinito(self, config_isolata):
        role_registry.save_role("coder", {"max_turns": 40})
        assert role_registry.delete_role("coder") is True
        assert role_registry.load_roles()["coder"].max_turns == DEV_ROLES["coder"].max_turns

    def test_ripristinare_cio_che_non_e_personalizzato_lo_dice(self, config_isolata):
        assert role_registry.delete_role("coder") is False


class TestIntegrazioneColMotore:
    def test_il_motore_dei_ruoli_legge_dal_registro(self, config_isolata):
        _scrivi(config_isolata, {"docs": {
            "name": "Documentalista",
            "system_prompt": "Scrivi documentazione.",
            "tools": ["read_file"],
        }})
        role_registry.invalidate()
        engine = RoleEngine()
        assert "docs" in engine.roles
        assert engine.is_tool_allowed("docs", "read_file")
        assert not engine.is_tool_allowed("docs", "terminal")

    def test_si_possono_passare_ruoli_espliciti(self):
        """Serve ai test e a chi vuole una squadra diversa senza toccare il file."""
        engine = RoleEngine(roles={"coder": DEV_ROLES["coder"]})
        assert set(engine.roles) == {"coder"}

    def test_la_forma_serializzabile_non_contiene_tuple(self, config_isolata):
        for voce in role_registry.list_roles():
            assert isinstance(voce["tools"], list)
            assert isinstance(voce["focus_areas"], list)
            assert "model" in voce and "mcp" in voce
