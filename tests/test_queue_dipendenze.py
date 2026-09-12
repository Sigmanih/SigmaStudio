"""La coda deve sapere che una voce puo' aspettarne un'altra.

Senza dipendenze, l'unico modo di ordinare il lavoro era metterlo in fila e
usare un solo lavoratore: si rinunciava al parallelismo su venti voci per
esprimere un vincolo che ne riguardava due. Sul lavoro della Biblioteca le voci
06 e 07 dipendevano dalla 05, e non c'era modo di dirlo.

E l'architetto deve poter riempire la coda. Prima si poteva solo da
`POST /api/harness/queue`: un agente che aveva appena guardato il progetto e
capito come spezzare il lavoro non aveva dove scriverlo.
"""

import pytest

from core.harness import workqueue as WQ
from core.harness.loop import execute_admin_tool


@pytest.fixture
def coda(tmp_path, monkeypatch):
    """Una coda vera, ma con il suo stato in una cartella temporanea."""
    monkeypatch.setattr(WQ.paths, "var_dir", lambda: tmp_path)
    WQ._code.clear()
    yield WQ.get_queue("prova")
    WQ._code.clear()


class TestLeDipendenzeVengonoRispettate:
    def test_una_voce_che_aspetta_non_viene_presa(self, coda):
        coda.add_many([
            {"id": "a", "title": "prima"},
            {"id": "b", "title": "dopo", "depends_on": ["a"]},
        ])
        assert coda.claim("w1").id == "a"
        assert coda.claim("w2") is None, "'b' aspetta 'a', non puo' partire"

    def test_chiudere_la_dipendenza_la_rende_disponibile(self, coda):
        coda.add_many([
            {"id": "a", "title": "prima"},
            {"id": "b", "title": "dopo", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        coda.complete("a")
        assert coda.claim("w2").id == "b"

    def test_le_voci_indipendenti_partono_insieme(self, coda):
        """Il vincolo non deve trasformare il parallelismo in una fila."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b"},
            {"id": "c", "title": "c", "depends_on": ["a"]},
        ])
        presi = {coda.claim("w1").id, coda.claim("w2").id}
        assert presi == {"a", "b"}

    def test_una_catena_si_srotola_nell_ordine(self, coda):
        coda.add_many([
            {"id": "c", "title": "c", "depends_on": ["b"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
            {"id": "a", "title": "a"},
        ])
        ordine = []
        for _ in range(3):
            voce = coda.claim("w1")
            assert voce is not None
            ordine.append(voce.id)
            coda.complete(voce.id)
        assert ordine == ["a", "b", "c"]


class TestCioCheNonPotraMaiPartire:
    def test_chi_dipende_da_una_fallita_viene_bloccato_e_lo_dice(self, coda):
        """Restando «da fare» la coda non finirebbe mai, e nessuno saprebbe
        perche'."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        coda.fail("a", "impossibile", riprovabile=False)

        stato = coda.progress()
        assert stato["blocked"] == 1
        assert stato["finished"] is True, "la coda deve poter finire"
        bloccata = [v for v in coda.items() if v.id == "b"][0]
        assert "dipende da 'a'" in bloccata.error

    def test_il_blocco_si_propaga(self, coda):
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
            {"id": "c", "title": "c", "depends_on": ["b"]},
        ])
        coda.claim("w1")
        coda.fail("a", "impossibile", riprovabile=False)
        assert coda.progress()["blocked"] == 2

    def test_reset_failed_rimette_in_gioco_anche_le_bloccate(self, coda):
        """Riprovare la fallita non basta: chi la aspettava e' gia' stato
        marcato bloccato, e resterebbe tale anche dopo che lei riesce."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        coda.fail("a", "x", riprovabile=False)
        assert coda.progress()["blocked"] == 1

        assert coda.reset_failed() == 2, "sia la fallita sia la bloccata"
        assert coda.claim("w1").id == "a"
        coda.complete("a")
        assert coda.claim("w2").id == "b", "ora deve poter partire"

    def test_una_dipendenza_verso_un_id_inesistente_viene_tolta(self, coda):
        avvisi = []
        coda.add_many([{"id": "b", "title": "b", "depends_on": ["mai_esistito"]}],
                      avvisi=avvisi)
        assert coda.claim("w1").id == "b", "non deve restare ferma per sempre"
        assert any("mai_esistito" in a for a in avvisi)

    def test_un_ciclo_viene_spezzato(self, coda):
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "a", "depends_on": ["b"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ], avvisi=avvisi)
        assert coda.claim("w1") is not None, "un ciclo fermerebbe tutto"
        assert any("ciclo" in a for a in avvisi)


class TestIlLavoratoreNonSeNeVaTroppoPresto:
    def test_attesa_utile_mentre_la_dipendenza_e_in_corso(self, coda):
        """Il caso che chiuderebbe i thread con la coda a meta': w2 non trova
        niente perche' l'unica voce rimasta aspetta quella che w1 ha in mano."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        assert coda.claim("w2") is None
        assert coda.attesa_utile() is True

    def test_a_coda_vuota_non_si_aspetta(self, coda):
        coda.add_many([{"id": "a", "title": "a"}])
        coda.claim("w1")
        coda.complete("a")
        assert coda.attesa_utile() is False

    def test_il_ventaglio_aspetta_invece_di_uscire(self):
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout.run_queue)
        assert "coda.attesa_utile()" in sorgente


class TestLArchitettoRiempieLaCoda:
    def test_il_tool_crea_le_voci(self, coda, tmp_path):
        esito = execute_admin_tool("queue_add", {
            "queue_id": "prova",
            "goal": "rendere i moduli traducibili",
            "items": [
                {"id": "01", "title": "estrai le stringhe di sigma_network",
                 "verify": "python tools/check_i18n.py sigma_network"},
                {"id": "02", "title": "traduci in inglese", "depends_on": ["01"]},
            ],
        }, workspace_root=str(tmp_path))

        assert esito["success"] is True
        assert esito["added"] == 2
        assert esito["progress"]["ready"] == 1, "la seconda aspetta la prima"

        voci = {v.id: v for v in WQ.get_queue("prova").items()}
        assert voci["02"].depends_on == ["01"]
        assert voci["01"].payload.get("verify", "").startswith("python tools")

    def test_senza_queue_id_viene_rifiutato_con_un_esempio(self, tmp_path):
        esito = execute_admin_tool("queue_add", {"items": [{"id": "1", "title": "x"}]},
                                   workspace_root=str(tmp_path))
        assert esito["success"] is False
        assert "queue_id" in esito["error"]

    def test_senza_voci_viene_rifiutato_con_un_esempio(self, tmp_path):
        esito = execute_admin_tool("queue_add", {"queue_id": "x"},
                                   workspace_root=str(tmp_path))
        assert esito["success"] is False
        assert "verify" in esito["error"], "l'errore deve mostrare la forma giusta"

    def test_gli_alias_funzionano(self, coda, tmp_path):
        esito = execute_admin_tool("enqueue", {
            "queue_id": "prova", "items": [{"id": "z", "title": "z"}],
        }, workspace_root=str(tmp_path))
        assert esito["success"] is True


class TestIlToolEDavveroRaggiungibile:
    def test_e_nello_schema_spedito_al_modello(self):
        from core.harness.tool_schema import TOOL_SCHEMAS

        nomi = [s["function"]["name"] for s in TOOL_SCHEMAS]
        assert "queue_add" in nomi

    def test_l_architetto_puo_usarlo(self):
        from core.harness.policy import ToolPolicy
        from core.harness.roles import ROLE_ARCHITECT

        assert "queue_add" in ROLE_ARCHITECT.tools
        policy = ToolPolicy.of(ROLE_ARCHITECT.tools, label="architect")
        assert policy.permits("queue_add") is True
        assert policy.permits("enqueue") is True, "l'alias deve passare"

    def test_il_prompt_lo_documenta(self):
        from core.harness.loop import ADMIN_DEVELOPER_SYSTEM_PROMPT

        assert "`queue_add`" in ADMIN_DEVELOPER_SYSTEM_PROMPT
