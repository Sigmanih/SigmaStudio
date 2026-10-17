# ==============================================================================
# tests/test_chiusure_e_specialisti.py — Chiusure vuote, specialisti, ruoli dei moduli
# ==============================================================================
"""Tre difetti trovati nel collaudo Mx0, in cui Sigma doveva trasporre un manga da solo.

1. Il cancello di completamento ha accettato come VERIFICATA la chiusura
   «ho letto il file, attendo istruzioni».
2. Il pianificatore riportava a `coder` ogni ruolo fuori dai cinque di base:
   un task video finiva a chi non ha tool video.
3. La procedura dello specialista non arrivava mai all'agente generico.
"""
import pytest

from core.harness import plan, specialisti
from core.harness.ledger import chiusura_vuota
from core.harness.roles import DEV_ROLES, DevRole


class TestChiusuraVuota:

    @pytest.mark.parametrize("summary", [
        "",
        "Ho letto il file cap01_analisi.json. Attendo istruzioni su cosa fare con questi dati.",
        "Fatto un primo controllo. Fammi sapere cosa vuoi che faccia adesso.",
        "Read the file. Awaiting your instructions.",
    ])
    def test_rinvio_rifiutato(self, summary):
        assert chiusura_vuota(summary)

    @pytest.mark.parametrize("summary", [
        "Storyboard pronto: 310 inquadrature, fotogrammi chiave delle prime 5 generati e controllati.",
        "## Fatto\n" + "Creati 4 personaggi dalle tavole a colori e lo storyboard completo. " * 8
        + "Fammi sapere cosa ne pensi.",
    ])
    def test_risultato_accettato(self, summary):
        assert chiusura_vuota(summary) is None


@pytest.fixture
def ruolo_di_modulo():
    ruolo = DevRole(id="prova_specialista", name="Specialista di prova", icon="*",
                    system_prompt="Procedura: fai A, poi B.", tools=("read_file",),
                    focus_areas=("la prova",))
    DEV_ROLES[ruolo.id] = ruolo
    yield ruolo
    DEV_ROLES.pop(ruolo.id, None)


class TestRuoliDeiModuli:

    def test_il_pianificatore_non_li_manda_al_coder(self, ruolo_di_modulo):
        assert plan.canonical_role("prova_specialista") == "prova_specialista"
        assert plan.role_is_known("prova_specialista")

    def test_i_nomi_inventati_restano_coder(self):
        assert plan.canonical_role("ruolo_inesistente") == "coder"
        assert plan.canonical_role("programmatore") == "coder"


class TestSpecialisti:

    def test_consult_role_restituisce_la_procedura(self, ruolo_di_modulo):
        esito = specialisti.esegui("consult_role", {"id": "prova_specialista"})
        assert esito["success"]
        assert "fai A, poi B" in specialisti.descrivi(esito)

    def test_ruolo_sconosciuto_elenca_i_disponibili(self, ruolo_di_modulo):
        esito = specialisti.consult_role("nessuno")
        assert not esito["success"] and "prova_specialista" in esito["error"]

    def test_la_sezione_del_prompt_li_elenca(self, ruolo_di_modulo):
        sezione = specialisti.sezione_prompt()
        assert "consult_role" in sezione and "`prova_specialista`" in sezione
        assert "`coder`" not in sezione

    def test_ignora_gli_altri_tool(self):
        assert specialisti.esegui("read_file", {}) is None
