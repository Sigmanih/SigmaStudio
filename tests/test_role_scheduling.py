"""In che ordine eseguire i task, quando ogni ruolo ha il suo modello.

Il grafo delle dipendenze dice cosa *puo'* partire. Con un modello per ruolo
serve anche decidere in che ordine conviene, e la differenza non e' piccola:
eseguire i task nell'ordine in cui l'Architect li ha scritti — architect,
coder, tester, architect, coder, tester — costa un cambio di modello per ogni
task, e su hardware locale il cambio costa piu' del task.

Raggruppare per ruolo abbassa quel numero. Questi test lo misurano invece di
darlo per buono, e coprono il caso che il raggruppamento non deve rompere:
l'ordine delle dipendenze resta comunque vincolante.
"""

import pytest

from core.harness.pipeline import TaskNode, TaskPipeline, TaskStatus


def _pipeline(*definizioni):
    """definizioni: (id, role, depends_on...)"""
    p = TaskPipeline(goal="obiettivo di prova")
    for voce in definizioni:
        tid, role, *deps = voce
        p.add_task(TaskNode(id=tid, title=f"task {tid}", role=role,
                            description="x", depends_on=list(deps)))
    return p


def _esegui_tutto(pipeline, preferisci_corrente=True):
    """Simula l'esecuzione a blocchi e riporta l'ordine effettivo."""
    ordine, ruolo = [], None
    for _ in range(len(pipeline.nodes) + 5):
        blocco = pipeline.next_role_batch(ruolo if preferisci_corrente else None)
        if not blocco:
            break
        ruolo = blocco[0].role
        for nodo in blocco:
            ordine.append(nodo)
            pipeline.mark_running(nodo.id)
            pipeline.mark_done(nodo.id)
    return ordine


class TestRaggruppamento:
    def test_i_task_pronti_dello_stesso_ruolo_arrivano_insieme(self):
        p = _pipeline(("1", "coder"), ("2", "coder"), ("3", "tester"))
        blocco = p.next_role_batch()
        assert {n.id for n in blocco} == {"1", "2"}

    def test_il_ruolo_gia_caricato_viene_preferito(self):
        """Non cambiare nulla e' sempre la mossa piu' economica."""
        p = _pipeline(("1", "coder"), ("2", "tester"), ("3", "tester"))
        blocco = p.next_role_batch(preferred_role="coder")
        assert [n.id for n in blocco] == ["1"]

    def test_senza_preferenza_vince_il_gruppo_piu_numeroso(self):
        """Ammortizza il cambio su piu' lavoro."""
        p = _pipeline(("1", "coder"), ("2", "tester"), ("3", "tester"))
        assert {n.id for n in p.next_role_batch()} == {"2", "3"}

    def test_un_ruolo_preferito_senza_task_pronti_viene_ignorato(self):
        p = _pipeline(("1", "coder"), ("2", "coder"))
        assert {n.id for n in p.next_role_batch(preferred_role="devops")} == {"1", "2"}

    def test_niente_di_pronto_da_un_blocco_vuoto(self):
        p = _pipeline(("1", "coder"))
        p.mark_running("1")
        p.mark_done("1")
        assert p.next_role_batch() == []


class TestOrdineEffettivo:
    def test_il_raggruppamento_riduce_i_cambi_di_ruolo(self):
        """La misura che giustifica l'intera modifica."""
        definizioni = (
            ("a1", "architect"), ("c1", "coder"), ("t1", "tester"),
            ("a2", "architect"), ("c2", "coder"), ("t2", "tester"),
        )
        ingenuo = list(_pipeline(*definizioni).nodes.values())
        raggruppato = _esegui_tutto(_pipeline(*definizioni))

        cambi_ingenuo = TaskPipeline(goal="").role_switch_count(ingenuo)
        cambi_raggruppato = TaskPipeline(goal="").role_switch_count(raggruppato)

        assert cambi_ingenuo == 5
        assert cambi_raggruppato == 2
        assert len(raggruppato) == len(ingenuo)

    def test_le_dipendenze_restano_vincolanti(self):
        """Ottimizzare l'ordine non puo' significare eseguire prima del dovuto."""
        p = _pipeline(
            ("scrivi", "coder"),
            ("testa", "tester", "scrivi"),
            ("altro_test", "tester"),
        )
        ordine = [n.id for n in _esegui_tutto(p)]
        assert ordine.index("scrivi") < ordine.index("testa")

    def test_un_task_bloccato_da_un_fallimento_non_viene_eseguito(self):
        p = _pipeline(("scrivi", "coder"), ("testa", "tester", "scrivi"))
        p.mark_running("scrivi")
        p.mark_failed("scrivi", "errore")
        assert p.next_role_batch() == []
        assert p.nodes["testa"].status == TaskStatus.PENDING

    def test_ogni_task_viene_eseguito_una_volta_sola(self):
        p = _pipeline(("1", "coder"), ("2", "coder"), ("3", "tester"), ("4", "tester"))
        ordine = [n.id for n in _esegui_tutto(p)]
        assert sorted(ordine) == ["1", "2", "3", "4"]
        assert len(ordine) == len(set(ordine))


class TestConteggioCambi:
    def test_una_sequenza_omogenea_non_ha_cambi(self):
        p = _pipeline(("1", "coder"), ("2", "coder"))
        assert p.role_switch_count(list(p.nodes.values())) == 0

    def test_una_sequenza_vuota_non_ha_cambi(self):
        assert TaskPipeline(goal="").role_switch_count([]) == 0
