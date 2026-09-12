"""Il piano dell'architetto deve arrivare intero a chi lo esegue.

Questi test partono dalla **chiamata del tool**, non da `TaskNode` costruiti a
mano. E' la differenza che conta: `tests/test_role_scheduling.py` provava che lo
scheduler rispetta ruoli e dipendenze costruendoli lui, e intanto il
normalizzatore del tool `pipeline` li stava scartando tutti e due. Lo scheduler
funzionava su un dato che non riceveva mai.
"""

import pytest

from core.harness.loop import execute_admin_tool
from core.harness.plan import canonical_role, descrivi_task, normalizza_piano


def _pipeline(task):
    """Il piano come lo vede il ciclo: passato dal tool, non costruito a mano."""
    return execute_admin_tool("pipeline", {"tasks": task}, workspace_root=".")


class TestIlPianoArrivaIntero:
    def test_ruolo_descrizione_e_dipendenze_sopravvivono_al_tool(self):
        """Il difetto originale: di cinque campi ne arrivavano tre."""
        esito = _pipeline([
            {"id": "t1", "title": "Mappa i moduli", "role": "architect",
             "description": "Elenca i 16 moduli e le loro stringhe"},
            {"id": "t2", "title": "Estrai", "role": "coder",
             "description": "Usa tools/estrai_stringhe.py", "depends_on": ["t1"]},
        ])
        per_id = {t["id"]: t for t in esito["tasks"]}
        assert per_id["t1"]["role"] == "architect"
        assert per_id["t2"]["role"] == "coder"
        assert per_id["t2"]["depends_on"] == ["t1"]
        assert "estrai_stringhe" in per_id["t2"]["description"]

    def test_ogni_task_ha_sempre_le_stesse_chiavi(self):
        """Chi consuma il piano non deve chiedersi se un campo c'e'."""
        esito = _pipeline(["fai una cosa"])
        atteso = {"id", "title", "status", "role", "description", "depends_on"}
        assert atteso <= set(esito["tasks"][0])

    def test_i_ruoli_scritti_in_italiano_valgono(self):
        """Il prompt e' in italiano: rifiutare 'programmatore' misurerebbe il
        vocabolario, non il piano."""
        esito = _pipeline([
            {"id": "a", "title": "x", "role": "architetto"},
            {"id": "b", "title": "y", "role": "programmatore"},
            {"id": "c", "title": "z", "role": "collaudo"},
        ])
        assert [t["role"] for t in esito["tasks"]] == ["architect", "coder", "tester"]

    def test_un_ruolo_inventato_finisce_al_coder_e_lo_dice(self):
        esito = _pipeline([{"id": "a", "title": "x", "role": "stregone"}])
        assert esito["tasks"][0]["role"] == "coder"
        assert any("stregone" in a for a in esito["warnings"])

    def test_file_e_verifica_del_piano_sopravvivono(self):
        esito = _pipeline([{
            "id": "a", "title": "x", "files": ["core/app.py", "tests/test_app.py"],
            "verify": "python -m pytest tests/test_app.py",
        }])
        t = esito["tasks"][0]
        assert t["files"] == ["core/app.py", "tests/test_app.py"]
        assert t["verify"].startswith("python -m pytest")


class TestLeDipendenzeImpossibili:
    def test_una_dipendenza_verso_un_id_inesistente_viene_tolta(self):
        """`get_ready_tasks` pretende che il nodo esista **e sia done**: un id
        inventato non diventa mai done, e chi lo nomina non parte mai."""
        esito = _pipeline([
            {"id": "t1", "title": "x"},
            {"id": "t2", "title": "y", "depends_on": ["t1", "t99"]},
        ])
        t2 = [t for t in esito["tasks"] if t["id"] == "t2"][0]
        assert t2["depends_on"] == ["t1"]
        assert any("t99" in a for a in esito["warnings"])

    def test_un_ciclo_viene_spezzato_e_dichiarato(self):
        task, avvisi = normalizza_piano([
            {"id": "a", "title": "a", "depends_on": ["b"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        archi = sum(len(t["depends_on"]) for t in task)
        assert archi == 1, "uno dei due archi doveva cadere"
        assert any("ciclo" in a for a in avvisi)

    def test_un_ciclo_lungo_viene_spezzato(self):
        task, avvisi = normalizza_piano([
            {"id": "a", "title": "a", "depends_on": ["c"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
            {"id": "c", "title": "c", "depends_on": ["b"]},
        ])
        assert sum(len(t["depends_on"]) for t in task) == 2
        assert any("ciclo" in a for a in avvisi)

    def test_dipendere_da_se_stessi_viene_tolto(self):
        task, avvisi = normalizza_piano([{"id": "a", "title": "a", "depends_on": ["a"]}])
        assert task[0]["depends_on"] == []
        assert any("se stesso" in a for a in avvisi)

    def test_due_task_con_lo_stesso_id_vengono_distinti(self):
        """Con due 't1' una dipendenza verso 't1' non saprebbe chi aspettare."""
        task, avvisi = normalizza_piano([
            {"id": "t1", "title": "primo"},
            {"id": "t1", "title": "secondo"},
        ])
        assert len({t["id"] for t in task}) == 2
        assert any("due volte" in a for a in avvisi)

    def test_un_piano_sano_non_produce_avvisi(self):
        _, avvisi = normalizza_piano([
            {"id": "a", "title": "a", "role": "coder"},
            {"id": "b", "title": "b", "role": "tester", "depends_on": ["a"]},
        ])
        assert avvisi == []


class TestFormeInCuiIlPianoArrivaDavvero:
    def test_un_elenco_di_stringhe(self):
        task, _ = normalizza_piano(["prima cosa", "seconda cosa"])
        assert [t["title"] for t in task] == ["prima cosa", "seconda cosa"]
        assert all(t["role"] == "coder" for t in task)

    def test_un_elenco_puntato_dentro_una_stringa(self):
        task, _ = normalizza_piano("- prima cosa\n- seconda cosa")
        assert [t["title"] for t in task] == ["prima cosa", "seconda cosa"]

    def test_un_json_dentro_una_stringa(self):
        task, _ = normalizza_piano('[{"id": "a", "title": "x", "role": "tester"}]')
        assert task[0]["role"] == "tester"

    def test_le_dipendenze_scritte_come_stringa_con_virgole(self):
        task, _ = normalizza_piano([
            {"id": "a", "title": "a"}, {"id": "b", "title": "b"},
            {"id": "c", "title": "c", "depends_on": "a, b"},
        ])
        assert task[2]["depends_on"] == ["a", "b"]

    def test_un_oggetto_con_la_chiave_tasks(self):
        task, _ = normalizza_piano({"tasks": [{"id": "a", "title": "x"}]})
        assert len(task) == 1


class TestIlTestoConsegnatoAChiEsegue:
    def test_il_titolo_da_solo_non_e_l_istruzione(self):
        testo = descrivi_task({
            "title": "Traduci sigma_network",
            "description": "Sposta le 34 stringhe in locales/it.json",
            "files": ["sigma_studio/src/modules/sigma_network/index.jsx"],
            "verify": "python tools/check_i18n.py sigma_network",
        }, obiettivo="rendere Sigma Studio multilingua")
        assert "34 stringhe" in testo
        assert "index.jsx" in testo
        assert "check_i18n" in testo
        assert "multilingua" in testo

    def test_una_descrizione_uguale_al_titolo_non_viene_ripetuta(self):
        testo = descrivi_task({"title": "fai x", "description": "fai x"})
        assert testo.count("fai x") == 1


class TestIlGrafoArrivaAllOrchestratore:
    def test_il_piano_del_tool_diventa_un_grafo_con_archi_e_ruoli(self):
        """La prova che chiude il difetto: dalla chiamata del tool fino al
        grafo che viene davvero eseguito, senza costruire niente a mano."""
        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        esito = _pipeline([
            {"id": "t1", "title": "Progetta", "role": "architetto",
             "description": "guarda il codice"},
            {"id": "t2", "title": "Scrivi", "role": "coder", "depends_on": ["t1"]},
            {"id": "t3", "title": "Collauda", "role": "tester", "depends_on": ["t2"]},
        ])
        orch = DevOrchestrator(workspace_root=".")
        orch._build_pipeline_from_architect(esito["tasks"], "obiettivo di prova")

        nodi = orch.pipeline.nodes
        assert {n.role for n in nodi.values()} == {"architect", "coder", "tester"}
        assert nodi["t2"].depends_on == ["t1"]
        assert nodi["t3"].depends_on == ["t2"]

        # E il grafo vincola davvero: all'inizio e' pronto solo il primo.
        pronti = orch.pipeline.get_ready_tasks()
        assert [n.id for n in pronti] == ["t1"]

    def test_senza_dipendenze_partono_tutti(self):
        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        esito = _pipeline([{"id": "a", "title": "a"}, {"id": "b", "title": "b"}])
        orch = DevOrchestrator(workspace_root=".")
        orch._build_pipeline_from_architect(esito["tasks"], "x")
        assert len(orch.pipeline.get_ready_tasks()) == 2


def test_canonical_role_non_inventa_ruoli():
    assert canonical_role("") == "coder"
    assert canonical_role(None) == "coder"
    assert canonical_role("DevOps") == "devops"
