"""I nodi del designer visuale eseguiti dall'harness, invece che simulati.

Il designer produceva nodi che non eseguivano niente. Al posto della risposta
di un modello metteva una stringa segnaposto — «Esecuzione nodo X per
l'obiettivo Y» — e la passava al nodo successivo come se fosse un risultato:
una pipeline intera poteva quindi risultare «completata» senza che nessun
modello avesse mai risposto, e senza che un solo file fosse stato toccato.

Questi test fissano le tre decisioni che rendono l'esecuzione vera utile invece
che soltanto presente: quali nodi hanno diritto agli strumenti, cosa vede un
nodo di cio' che e' successo a monte, e cosa succede quando un nodo fallisce.
"""

import pytest

from core.harness.node_runner import (
    MAX_CHARS_PER_UPSTREAM,
    build_node_prompt,
    is_agent_node,
    node_role,
)


def _nodo(ruolo="custom", prompt="", etichetta="Nodo", nid="n1"):
    return {
        "id": nid,
        "label": etichetta,
        "type": "agent",
        "config": {"role": ruolo, "prompt": prompt, "provider": "sigma_engine"},
    }


class TestChiHaDirittoAgliStrumenti:
    """Non ogni nodo deve poter toccare i file.

    Un nodo che riassume o traduce non ha bisogno di strumenti, e dargliene
    significherebbe offrirgli modi di sbagliare che il suo compito non prevede.
    """

    def test_un_ruolo_del_registro_e_un_nodo_agente(self):
        assert is_agent_node(_nodo("coder")) is True
        assert is_agent_node(_nodo("tester")) is True

    def test_un_ruolo_generico_no(self):
        for generico in ("custom", "", "generalist", "none"):
            assert is_agent_node(_nodo(generico)) is False, generico

    def test_un_ruolo_inventato_no(self):
        """Meglio una generazione semplice che strumenti su un ruolo che non esiste."""
        assert is_agent_node(_nodo("ruolo_mai_definito")) is False

    def test_il_ruolo_e_riconosciuto_a_prescindere_dal_maiuscolo(self):
        assert node_role(_nodo("  CODER ")) == "coder"
        assert is_agent_node(_nodo("  CODER ")) is True

    def test_un_nodo_senza_config_non_esplode(self):
        assert is_agent_node({"id": "x"}) is False
        assert node_role({"id": "x"}) == ""

    def test_aggiungere_un_ruolo_al_registro_lo_rende_eseguibile(self, monkeypatch):
        """La decisione sta nel registro, non in un elenco scritto nel modulo."""
        import core.harness.node_runner as nr
        from core.harness.roles import DEV_ROLES

        monkeypatch.setattr(
            "core.harness.role_registry.get_role",
            lambda rid: DEV_ROLES["coder"] if rid == "documentalista" else None,
        )
        assert nr.is_agent_node(_nodo("documentalista")) is True


class TestCosaVedeIlNodo:
    def test_l_obiettivo_apre_il_prompt(self):
        """E' la cosa che il nodo non deve perdere di vista."""
        testo = build_node_prompt(_nodo(prompt="Riassumi"), "Costruire il modulo X")
        assert testo.startswith("OBIETTIVO DELLA PIPELINE:")
        assert "Costruire il modulo X" in testo

    def test_le_istruzioni_del_nodo_ci_sono(self):
        testo = build_node_prompt(_nodo(prompt="Riassumi in tre righe"), "obiettivo")
        assert "Riassumi in tre righe" in testo

    def test_senza_istruzioni_vale_l_etichetta(self):
        testo = build_node_prompt(_nodo(etichetta="Revisione finale"), "obiettivo")
        assert "Revisione finale" in testo

    def test_i_risultati_di_monte_chiudono_il_prompt(self):
        """Sono la parte che cambia a ogni esecuzione: vanno letti per ultimi."""
        testo = build_node_prompt(
            _nodo(prompt="Verifica"), "obiettivo",
            {"analisi": "Il modulo ha tre funzioni."},
        )
        assert "Il modulo ha tre funzioni." in testo
        assert testo.index("Verifica") < testo.index("Il modulo ha tre funzioni.")

    def test_un_risultato_enorme_viene_troncato(self):
        """La finestra di chi deve ancora lavorare non si spende a rileggere."""
        testo = build_node_prompt(
            _nodo(), "obiettivo", {"monte": "x" * (MAX_CHARS_PER_UPSTREAM * 3)}
        )
        assert "[...troncato]" in testo
        assert len(testo) < MAX_CHARS_PER_UPSTREAM * 2

    def test_i_risultati_vuoti_non_occupano_spazio(self):
        testo = build_node_prompt(_nodo(), "obiettivo", {"vuoto": "", "altro": None})
        assert "RISULTATO DEL NODO" not in testo

    def test_piu_nodi_a_monte_sono_distinguibili(self):
        testo = build_node_prompt(
            _nodo(), "obiettivo",
            {"analisi": "prima cosa", "ricerca": "seconda cosa"},
        )
        assert "'analisi'" in testo and "'ricerca'" in testo


class TestEsecuzione:
    """Il nodo emette eventi e chiude con il testo prodotto."""

    def test_un_nodo_di_prompt_produce_il_testo_generato(self, monkeypatch):
        import core.harness.providers as providers

        monkeypatch.setattr(
            providers, "stream_dev_generation",
            lambda **kwargs: iter([{"token": "risultato "}, {"token": "del nodo"}]),
        )
        from core.harness.node_runner import run_node

        eventi = list(run_node(_nodo("custom", "Riassumi"), "obiettivo"))
        finale = [e for e in eventi if e["type"] == "node_output"]
        assert len(finale) == 1
        assert finale[0]["output"] == "risultato del nodo"

    def test_ogni_evento_porta_l_identificativo_del_nodo(self, monkeypatch):
        """Il frontend deve poter dire quale nodo sta parlando."""
        import core.harness.providers as providers
        monkeypatch.setattr(
            providers, "stream_dev_generation",
            lambda **kwargs: iter([{"token": "x"}]),
        )
        from core.harness.node_runner import run_node

        for evento in run_node(_nodo(nid="analisi"), "obiettivo"):
            assert evento.get("node_id") == "analisi"

    def test_un_errore_di_generazione_diventa_un_fallimento_del_nodo(self, monkeypatch):
        import core.harness.providers as providers
        monkeypatch.setattr(
            providers, "stream_dev_generation",
            lambda **kwargs: iter([{"error": True, "message": "provider irraggiungibile"}]),
        )
        from core.harness.node_runner import run_node

        eventi = list(run_node(_nodo(), "obiettivo"))
        falliti = [e for e in eventi if e["type"] == "node_failed"]
        assert len(falliti) == 1
        assert "provider irraggiungibile" in falliti[0]["error"]

    def test_un_eccezione_non_porta_giu_la_pipeline(self, monkeypatch):
        """Un nodo che esplode deve fermare se stesso, non il processo."""
        import core.harness.providers as providers

        def esplodi(**kwargs):
            raise RuntimeError("motore assente")

        monkeypatch.setattr(providers, "stream_dev_generation", esplodi)
        from core.harness.node_runner import run_node

        eventi = list(run_node(_nodo(), "obiettivo"))
        assert any(e["type"] == "node_failed" for e in eventi)

    def test_un_nodo_agente_passa_dal_motore_dei_ruoli(self, monkeypatch):
        """Il punto della modifica: tool, ledger e cancello, non una generazione nuda."""
        import core.harness.roles as roles

        visto = {}

        class MotoreFinto:
            def generate_with_role(self, ruolo, prompt, **kwargs):
                visto["ruolo"] = ruolo
                visto["ledger"] = kwargs.get("ledger")
                visto["workspace_root"] = kwargs.get("workspace_root")
                yield {"type": "token", "token": "fatto"}

        monkeypatch.setattr(roles, "RoleEngine", MotoreFinto)
        from core.harness.node_runner import run_node

        sentinella = object()
        eventi = list(run_node(
            _nodo("coder", "Implementa"), "obiettivo",
            ledger=sentinella, workspace_root="C:/progetto",
        ))

        assert visto["ruolo"] == "coder"
        assert visto["ledger"] is sentinella
        assert visto["workspace_root"] == "C:/progetto"
        assert [e for e in eventi if e["type"] == "node_output"][0]["output"] == "fatto"


class TestIlRunnerNonSimulaPiu:
    """La regressione da cui nasce tutto: il segnaposto non deve tornare."""

    def test_il_runner_non_contiene_piu_la_simulazione(self):
        import inspect
        from core.pipeline.runner import run_pipeline

        sorgente = inspect.getsource(run_pipeline)
        assert "Esecuzione nodo" not in sorgente
        assert "run_node(" in sorgente

    def test_il_runner_condivide_un_ledger_fra_i_nodi(self):
        import inspect
        from core.pipeline.runner import run_pipeline

        sorgente = inspect.getsource(run_pipeline)
        assert "DevSessionLedger" in sorgente
        assert "ledger=ledger" in sorgente


class TestNomeDelModello:
    """«sigmaengine» non e' un modello: e' il modo di dire che non se ne e' scelto uno.

    Il designer lo manda quando l'utente non ha toccato il selettore, e il
    motore lo riceveva come nome di checkpoint: lo cercava, non lo trovava, e
    il nodo falliva con «Nessun modello con pesi». E' emerso alla prima
    esecuzione vera di una pipeline, non da un test.
    """

    def test_gli_alias_generici_diventano_nessuna_scelta(self):
        from core.harness.node_runner import concrete_model
        for generico in ("sigmaengine", "sigma_engine", "auto", "default",
                         "native", "", "  ", None):
            assert concrete_model(generico) is None, generico

    def test_un_nome_vero_passa_intatto(self):
        from core.harness.node_runner import concrete_model
        assert concrete_model("Qwen--Qwen3.8-27B-GGUF-Q4_K_S") == "Qwen--Qwen3.8-27B-GGUF-Q4_K_S"

    def test_il_nodo_di_prompt_non_inoltra_un_alias(self, monkeypatch):
        import core.harness.providers as providers
        visto = {}

        def cattura(**kwargs):
            visto["model_name"] = kwargs.get("model_name")
            return iter([{"token": "x"}])

        monkeypatch.setattr(providers, "stream_dev_generation", cattura)
        from core.harness.node_runner import run_node

        list(run_node(_nodo(), "obiettivo", model_override="sigmaengine"))
        assert visto["model_name"] is None

    def test_il_nodo_agente_non_inoltra_un_alias(self, monkeypatch):
        import core.harness.roles as roles
        visto = {}

        class MotoreFinto:
            def generate_with_role(self, ruolo, prompt, **kwargs):
                visto["model_name"] = kwargs.get("model_name")
                yield {"type": "token", "token": "x"}

        monkeypatch.setattr(roles, "RoleEngine", MotoreFinto)
        from core.harness.node_runner import run_node

        list(run_node(_nodo("coder"), "obiettivo", model_override="auto"))
        assert visto["model_name"] is None
