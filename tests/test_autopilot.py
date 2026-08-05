# ==============================================================================
# tests/test_autopilot.py — Le decisioni del ciclo automatico
# ==============================================================================
"""Copre core/training/autopilot.py.

Un ciclo che gira da solo per ore fa danni proporzionali agli errori del suo
criterio: accetta round che peggiorano il modello, o cancella artefatti che
servivano. Qui si verifica il criterio, non l'esecuzione.
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.training import autopilot
from core.training.autopilot import (
    ALPHA, CEILING, MIN_ITEMS_PER_SUITE, SKILL_MAP,
    compare, discardable_artifacts, mcnemar_p, pick_targets,
)


def scores(wins=0, losses=0, agree=100):
    """Due dizionari di esiti appaiati: chi vince cosa, e su cosa concordano."""
    candidate, champion = {}, {}
    for i in range(wins):
        candidate[f"w{i}"], champion[f"w{i}"] = True, False
    for i in range(losses):
        candidate[f"l{i}"], champion[f"l{i}"] = False, True
    for i in range(agree):
        candidate[f"a{i}"] = champion[f"a{i}"] = True
    return candidate, champion


# ============================================================ il criterio

class TestAcceptance:

    def test_a_clear_improvement_is_accepted(self):
        result = compare(*scores(wins=20, losses=2))
        assert result["accepted"] is True
        assert result["verdict"] == "migliora"

    def test_a_clear_regression_is_rejected(self):
        result = compare(*scores(wins=2, losses=20))
        assert result["accepted"] is False
        assert result["verdict"] == "peggiora"

    def test_a_small_edge_is_not_enough(self):
        """Vincere 5 e perdere 3 su 150 item è rumore, non un miglioramento."""
        result = compare(*scores(wins=5, losses=3))
        assert result["accepted"] is False
        assert result["verdict"] == "indistinguibile dal rumore"

    def test_identical_models_are_indistinguishable(self):
        result = compare(*scores(wins=0, losses=0))
        assert result["accepted"] is False
        assert result["p"] == 1.0

    @pytest.mark.parametrize("wins,losses", [(5, 12), (4, 19), (2, 18), (3, 16)])
    def test_the_hand_built_chain_would_have_been_rejected(self, wins, losses):
        """I quattro round costruiti a mano su questo progetto: nessuno passa.

        È la prova che il criterio non è decorativo — avrebbe fermato il
        lavoro al primo tentativo invece che al quarto.
        """
        assert compare(*scores(wins=wins, losses=losses))["accepted"] is False

    def test_only_the_disagreements_count(self):
        """Gli item su cui i due modelli concordano non dicono nulla sulla
        loro differenza: cambiarne il numero non deve cambiare il verdetto."""
        few = compare(*scores(wins=15, losses=2, agree=10))
        many = compare(*scores(wins=15, losses=2, agree=5000))
        assert few["p"] == many["p"]
        assert few["accepted"] == many["accepted"] is True

    def test_the_test_is_symmetric(self):
        assert mcnemar_p(12, 3) == mcnemar_p(3, 12)

    def test_only_shared_items_are_compared(self):
        """Se un modello ha risposto a quesiti che l'altro non ha visto, quelli
        non entrano nel confronto: non sarebbe più appaiato."""
        candidate = {"a": True, "b": True, "solo_suo": True}
        champion = {"a": True, "b": False}
        assert compare(candidate, champion)["items"] == 2


# =========================================================== i bersagli

class TestTargetChoice:

    PROFILE = {
        "gsm8k":     {"passed": 140, "total": 150},   # al soffitto
        "math":      {"passed": 5, "total": 17},      # debole, misurabile
        "mmlu_pro":  {"passed": 10, "total": 26},     # debole, ben misurato
        "mmlu":      {"passed": 22, "total": 26},     # quasi al soffitto
        "gpqa":      {"passed": 1, "total": 2},       # troppo pochi item
    }

    def test_a_suite_at_the_ceiling_is_not_a_target(self):
        """La lezione di GSM8K: al 93,3% non c'era nulla da guadagnare."""
        suites = [t["suite"] for t in pick_targets(self.PROFILE, done=[])]
        assert "gsm8k" not in suites

    def test_too_few_items_means_no_target(self):
        """Con 2 quesiti non si riesce nemmeno a stabilire se un round ha
        funzionato."""
        assert "gpqa" not in [t["suite"] for t in pick_targets(self.PROFILE, done=[])]

    def test_the_weakest_measurable_suite_comes_first(self):
        assert pick_targets(self.PROFILE, done=[])[0]["suite"] == "math"

    def test_a_well_measured_suite_outranks_a_barely_measured_one(self):
        """A parità di debolezza vince quella su cui il risultato si vedrà."""
        profile = {"a": {"passed": 4, "total": 10}, "b": {"passed": 16, "total": 40}}
        mapped = {**SKILL_MAP, "a": SKILL_MAP["math"], "b": SKILL_MAP["math"]}
        autopilot.SKILL_MAP = mapped
        try:
            assert pick_targets(profile, done=[])[0]["suite"] == "b"
        finally:
            autopilot.SKILL_MAP = SKILL_MAP

    def test_a_suite_already_attempted_is_not_repeated(self):
        suites = [t["suite"] for t in pick_targets(self.PROFILE, done=["math"])]
        assert "math" not in suites

    def test_every_target_carries_a_dataset_to_train_on(self):
        for target in pick_targets(self.PROFILE, done=[]):
            assert target["datasets"], f"{target['suite']} non ha dataset"

    def test_no_training_dataset_is_a_benchmark_dataset(self):
        """Allenare sul dataset che poi giudica produce un numero che non
        significa nulla fuori da quel benchmark.

        Il confronto è sugli id reali che le suite caricano, non su una
        somiglianza di nome: `nvidia/OpenMathInstruct-2` contiene "math" ma è
        dati sintetici, non lo split di MATH.
        """
        import re
        source = (Path(__file__).parent.parent
                  / "core" / "training" / "benchmarks.py").read_text(encoding="utf-8")
        benchmark_ids = {m.lower() for m in re.findall(r'load_dataset\("([^"]+)"', source)}
        assert benchmark_ids, "nessun dataset di benchmark trovato: il test è cieco"

        training_ids = {d.lower() for skill in SKILL_MAP.values() for d in skill["datasets"]}
        overlap = training_ids & benchmark_ids
        assert overlap == set(), f"dataset usati sia per allenare sia per giudicare: {overlap}"

    def test_an_empty_profile_offers_nothing(self):
        assert pick_targets({}, done=[]) == []


# ============================================================== pulizia

class TestCleanup:

    def _state(self, tmp_path, rounds):
        for round_ in rounds:
            folder = tmp_path / "training" / "jobs" / round_["job_id"]
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "adapter.bin").write_bytes(b"x" * 2048)
        autopilot.BASE_DIR = tmp_path
        return {"rounds": rounds, "champion": {}}

    def test_rejected_rounds_are_offered_for_deletion(self, tmp_path):
        state = self._state(tmp_path, [
            {"job_id": "scartato", "suite": "math", "accepted": False, "verdict": "peggiora"},
        ])
        assert [d["job_id"] for d in discardable_artifacts(state)] == ["scartato"]

    def test_accepted_rounds_are_never_offered(self, tmp_path):
        state = self._state(tmp_path, [
            {"job_id": "buono", "suite": "math", "accepted": True},
            {"job_id": "scartato", "suite": "bbh", "accepted": False},
        ])
        assert [d["job_id"] for d in discardable_artifacts(state)] == ["scartato"]

    def test_the_champion_is_never_offered(self, tmp_path):
        state = self._state(tmp_path, [
            {"job_id": "campione", "suite": "math", "accepted": False},
        ])
        state["champion"] = {"job_id": "campione"}
        assert discardable_artifacts(state) == []

    def test_a_round_already_cleaned_is_not_offered_twice(self, tmp_path):
        state = self._state(tmp_path, [
            {"job_id": "vecchio", "suite": "math", "accepted": False, "cleaned": True},
        ])
        assert discardable_artifacts(state) == []

    def test_cleanup_reports_the_space_it_would_free(self, tmp_path):
        state = self._state(tmp_path, [
            {"job_id": "scartato", "suite": "math", "accepted": False},
        ])
        result = autopilot.cleanup(state, dry_run=True)
        assert result["dry_run"] is True
        assert (tmp_path / "training" / "jobs" / "scartato").exists()
        assert result["candidates"][0]["bytes"] == 2048

    def test_cleanup_actually_removes_and_marks(self, tmp_path):
        state = self._state(tmp_path, [
            {"job_id": "scartato", "suite": "math", "accepted": False},
        ])
        autopilot.STATE_FILE = tmp_path / "state.json"
        autopilot.cleanup(state, dry_run=False)
        assert not (tmp_path / "training" / "jobs" / "scartato").exists()
        assert state["rounds"][0]["cleaned"] is True
        assert discardable_artifacts(state) == []


class TestExecutorGuards:
    """Il ciclo gira per ore senza sorveglianza: i suoi rifiuti contano quanto
    le sue azioni."""

    def test_it_refuses_to_start_without_a_model(self):
        assert autopilot.start("")["success"] is False

    def test_it_refuses_to_start_without_room_to_work(self, monkeypatch):
        """Materializzare un candidato costa ~45 GB fra merge, GGUF e copia in
        Ollama: cominciare con il disco pieno significa fallire a metà."""
        monkeypatch.setattr(autopilot, "_free_gb", lambda: 10.0)
        result = autopilot.start("un/modello")
        assert result["success"] is False
        assert "GB liberi" in result["error"]

    def test_two_cycles_cannot_run_together(self, monkeypatch, tmp_path):
        monkeypatch.setattr(autopilot, "_free_gb", lambda: 999.0)
        autopilot.STATE_FILE = tmp_path / "state.json"

        class Alive:
            def is_alive(self): return True
        monkeypatch.setattr(autopilot, "_worker", Alive())
        assert autopilot.start("un/modello")["success"] is False


class TestModelPairing:
    """Un modello nel ciclo ha due identità, e confonderle costa un'ora.

    La valutazione passa da Ollama, l'addestramento dai pesi HuggingFace. Un
    modello pubblicato solo su Ollama si può misurare ma non specializzare, e
    va detto prima della profilazione — non dopo.
    """

    def test_an_ollama_only_model_is_refused(self, monkeypatch):
        monkeypatch.setattr(autopilot, "_hf_model_exists",
                            lambda repo: (False, "401 (privato o ad accesso ristretto)"))
        result = autopilot.resolve_pair("Alieno/ailo-340m-v4:latest")
        assert result["ok"] is False
        assert "non sono raggiungibili" in result["error"]

    def test_an_explicit_pairing_is_accepted(self, monkeypatch):
        monkeypatch.setattr(autopilot, "_hf_model_exists", lambda repo: (True, "200"))
        result = autopilot.resolve_pair("qwen3.5:0.8b", "Qwen/Qwen2.5-0.5B-Instruct")
        assert result["ok"] is True
        assert result["train_model"] == "Qwen/Qwen2.5-0.5B-Instruct"
        assert result["eval_model"] == "qwen3.5:0.8b"

    def test_the_tag_is_stripped_when_no_pairing_is_given(self, monkeypatch):
        monkeypatch.setattr(autopilot, "_hf_model_exists", lambda repo: (True, "200"))
        result = autopilot.resolve_pair("empero-ai/Qwythos-9B:latest")
        assert result["train_model"] == "empero-ai/Qwythos-9B"

    def test_a_well_formed_but_missing_repo_is_caught(self, monkeypatch):
        """`Alieno/ailo-340m-v4` è un id scritto benissimo e inesistente: il
        controllo di formato da solo lo lascerebbe passare."""
        monkeypatch.setattr(autopilot, "_hf_model_exists", lambda repo: (False, "404"))
        assert autopilot.resolve_pair("qualcuno/inventato:latest")["ok"] is False

    def test_a_local_folder_skips_the_remote_check(self, tmp_path, monkeypatch):
        def explode(repo):
            raise AssertionError("i pesi locali non vanno cercati su HuggingFace")
        monkeypatch.setattr(autopilot, "_hf_model_exists", explode)
        (tmp_path / "config.json").write_text("{}", encoding="utf-8")
        result = autopilot.resolve_pair("qualsiasi:latest", str(tmp_path))
        assert result["ok"] is True

    def test_a_network_failure_does_not_block_the_cycle(self, monkeypatch):
        """Meglio procedere e fallire chiaramente dopo, che rifiutare per un
        timeout di rete."""
        monkeypatch.setattr(autopilot, "_hf_model_exists",
                            lambda repo: (True, "non verificabile"))
        assert autopilot.resolve_pair("owner/modello:latest")["ok"] is True

    def test_the_cycle_refuses_to_start_on_an_untrainable_model(self, monkeypatch):
        monkeypatch.setattr(autopilot, "_free_gb", lambda: 999.0)
        monkeypatch.setattr(autopilot, "_hf_model_exists", lambda repo: (False, "401"))
        result = autopilot.start("Alieno/ailo-340m-v4:latest")
        assert result["success"] is False
        assert "raggiungibili" in result["error"]


class TestScoreHandling:

    def test_the_suite_is_read_from_the_item_id(self):
        profile = autopilot._suite_profile(
            {"gsm8k_1": True, "gsm8k_2": False, "mmlu_pro_7": True})
        assert profile["gsm8k"] == {"passed": 1, "total": 2}
        assert profile["mmlu_pro"] == {"passed": 1, "total": 1}

    def test_the_split_is_decided_once_and_then_reused(self, tmp_path):
        """Cambiare la partizione a ciclo iniziato renderebbe i round non
        confrontabili fra loro."""
        autopilot.STATE_FILE = tmp_path / "state.json"
        state = autopilot._blank_state()
        scores = {f"gsm8k_{i}": i % 2 == 0 for i in range(40)}
        first_sel, _ = autopilot._split_scores(scores, state)
        fixed = list(state["selection_ids"])
        # un secondo giro con esiti diversi non deve spostare la partizione
        other = {k: not v for k, v in scores.items()}
        second_sel, _ = autopilot._split_scores(other, state)
        assert state["selection_ids"] == fixed
        assert set(first_sel) == set(second_sel)

    def test_selection_and_holdout_never_overlap(self, tmp_path):
        autopilot.STATE_FILE = tmp_path / "state.json"
        state = autopilot._blank_state()
        scores = {f"math_{i}": True for i in range(30)}
        selection, holdout = autopilot._split_scores(scores, state)
        assert set(selection) & set(holdout) == set()
        assert len(selection) + len(holdout) == 30

    def test_accuracy_of_an_empty_run_is_zero_not_a_crash(self):
        assert autopilot._accuracy({}) == 0.0


class TestState:

    @pytest.fixture(autouse=True)
    def stato_isolato(self, tmp_path, monkeypatch):
        """Ogni modello ha il suo file: i test devono isolare la cartella,
        non solo il file storico."""
        monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path / "cicli")
        monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "cicli" / "_attivo.json")
        monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")

    def test_a_missing_state_file_reads_as_idle(self, tmp_path):
        autopilot.STATE_FILE = tmp_path / "mai-scritto.json"
        assert autopilot.load_state()["status"] == "idle"

    def test_a_corrupt_state_file_does_not_crash(self, tmp_path):
        autopilot.STATE_FILE = tmp_path / "rotto.json"
        autopilot.STATE_FILE.write_text("{ non json", encoding="utf-8")
        assert autopilot.load_state()["status"] == "idle"

    def test_the_diary_does_not_grow_without_bound(self, tmp_path):
        autopilot.STATE_FILE = tmp_path / "state.json"
        state = autopilot.load_state()
        for i in range(600):
            autopilot.note(state, "info", f"riga {i}")
        assert len(state["log"]) == 400
        assert state["log"][-1]["message"] == "riga 599"

    def test_the_state_survives_a_round_trip(self):
        state = autopilot.load_state()
        state["base_model"] = "empero-ai/Qwythos-9B"
        autopilot.save_state(state)
        assert autopilot.load_state("empero-ai/Qwythos-9B")["base_model"]             == "empero-ai/Qwythos-9B"


# ==============================================================================
# I CONTRATTI DELLE FUNZIONI CHE IL CICLO CHIAMA
# ==============================================================================
# Il ciclo orchestra codice scritto altrove, e ogni chiamata attraversa un
# confine di modulo. Un contratto letto male non si vede in nessun test di
# unita': si vede alle 19:28, quando il ciclo muore al primo passo dicendo
# "benchmark non avviato: None".

def test_il_benchmark_restituisce_un_job_non_un_esito(monkeypatch):
    """`start_benchmark_run` torna il job. Cercarci dentro "success" dava
    sempre None e fermava il ciclo prima ancora di profilare il modello."""
    import types

    finto = types.ModuleType("core.training.benchmarks")
    finto.start_benchmark_run = lambda *a, **k: {
        "id": "bm_20260802_192837_ab12", "model": a[0] if a else k.get("model_name"),
        "status": "preparing", "concurrency": 4,
    }
    monkeypatch.setitem(sys.modules, "core.training.benchmarks", finto)
    monkeypatch.setattr(autopilot, "_wait_for_job", lambda *a, **k: "completed")
    monkeypatch.setattr(autopilot, "_benchmark_scores", lambda jid, only=None: {"q1": True})
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)

    state = autopilot._blank_state()
    job_id, scores = autopilot._run_benchmark("qwen2.5:0.5b-instruct", state, 300)
    assert job_id == "bm_20260802_192837_ab12"
    assert scores == {"q1": True}


def test_un_benchmark_senza_job_lo_dice(monkeypatch):
    """Se davvero non parte, il messaggio deve dire qualcosa: 'None' non e'
    una diagnosi."""
    import types

    finto = types.ModuleType("core.training.benchmarks")
    finto.start_benchmark_run = lambda *a, **k: {"error": "Ollama non raggiungibile"}
    monkeypatch.setitem(sys.modules, "core.training.benchmarks", finto)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)

    with pytest.raises(RuntimeError, match="Ollama non raggiungibile"):
        autopilot._run_benchmark("qualcosa", autopilot._blank_state(), 300)


def test_la_firma_vera_del_benchmark_non_promette_success():
    """Il test qui sopra usa un finto: questo controlla che il vero non abbia
    cambiato idea, altrimenti il finto proteggerebbe un contratto morto."""
    import ast
    import inspect

    from core.training.benchmarks import start_benchmark_run

    sorgente = inspect.getsource(start_benchmark_run)
    chiavi = set()
    for nodo in ast.walk(ast.parse(sorgente.lstrip())):
        if isinstance(nodo, ast.Return) and isinstance(nodo.value, ast.Name):
            chiavi.add(nodo.value.id)
    assert "job" in chiavi, "restituisce il job: il ciclo deve leggerne l'id"


def test_l_elenco_dei_benchmark_e_una_lista(monkeypatch):
    """`list_benchmark_jobs` torna la lista, non un involucro con "jobs":
    chiamarci .get() sopra sollevava AttributeError alla prima attesa."""
    import types

    finto = types.ModuleType("core.training.benchmarks")
    finto.list_benchmark_jobs = lambda: [{"id": "bm_1", "status": "completed"}]
    monkeypatch.setitem(sys.modules, "core.training.benchmarks", finto)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)

    esito = autopilot._wait_for_job("bm_1", "benchmark", autopilot._blank_state())
    assert esito == "completed"


def test_un_training_che_non_parte_non_blocca_il_ciclo(monkeypatch):
    """Un job che non si avvia resta "ready", che non e' terminale: senza il
    controllo sull'esito dell'avvio il ciclo aspetterebbe per sempre."""
    import types

    jobs = types.ModuleType("core.training.jobs")
    jobs.create_training_job = lambda d: {"success": True, "job_id": "j1"}
    jobs.start_training_job = lambda jid: {"success": False, "error": "CUDA occupata"}
    jobs.merge_job_adapter = lambda *a, **k: {"success": True, "job_id": "m1"}
    datasets = types.ModuleType("core.training.datasets")
    datasets.register_hf_dataset = lambda d: {"success": True, "dataset": {"id": "d1"}}
    monkeypatch.setitem(sys.modules, "core.training.jobs", jobs)
    monkeypatch.setitem(sys.modules, "core.training.datasets", datasets)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "_wait_for_job",
                        lambda *a, **k: pytest.fail("non deve mettersi in attesa"))

    state = autopilot._blank_state()
    state["base_model"] = "m:latest"
    round_ = autopilot._phase_round(
        state, {"suite": "gsm8k", "label": "Aritmetica", "datasets": ["ds/x"]}, 300)
    assert "non avviato" in round_["verdict"] and "CUDA occupata" in round_["verdict"]


# ==============================================================================
# GUASTI CONTRO VERDETTI
# ==============================================================================
# Un round puo' finire in due modi diversissimi: con una misura che dice
# "questo adapter non migliora", oppure senza misura affatto perche' qualcosa
# si e' rotto. Trattarli allo stesso modo ha fatto dichiarare al ciclo di aver
# concluso il lavoro dopo quattro training falliti di fila sullo stesso errore.

def test_un_round_rotto_non_consuma_il_bersaglio():
    """Il bersaglio resta da provare: la competenza non e' stata misurata."""
    rotti = [{"suite": "mmlu", "broken": True, "verdict": "training fallito"}]
    profilo = {"mmlu": {"passed": 10, "total": 40}}
    done = [r.get("suite") for r in rotti if not r.get("broken")]
    assert pick_targets(profilo, done), "mmlu deve restare fra i bersagli"


def test_un_round_misurato_consuma_il_bersaglio():
    misurati = [{"suite": "mmlu", "accepted": False, "verdict": "peggiora"}]
    profilo = {"mmlu": {"passed": 10, "total": 40}}
    done = [r.get("suite") for r in misurati if not r.get("broken")]
    assert not pick_targets(profilo, done)


def test_ogni_uscita_anticipata_marca_il_round_come_rotto():
    """Le vie d'uscita di `_phase_round` sono sette e crescono: se una scorda
    di marcare il round, il ciclo torna a bruciare bersagli in silenzio."""
    import ast
    import inspect

    sorgente = inspect.getsource(autopilot._phase_round)
    albero = ast.parse(sorgente.lstrip())
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.Assign):
            continue
        bersaglio = nodo.targets[0]
        if not (isinstance(bersaglio, ast.Subscript)
                and getattr(bersaglio.value, "id", "") == "round_"
                and getattr(bersaglio.slice, "value", "") == "verdict"):
            continue
        # Dopo ogni assegnazione di un verdetto d'errore deve comparire il
        # marchio: cerchiamo nella riga successiva del sorgente.
        righe = sorgente.lstrip().splitlines()
        seguente = righe[nodo.lineno] if nodo.lineno < len(righe) else ""
        assert 'round_["broken"]' in seguente, (
            f"riga {nodo.lineno}: verdetto d'errore senza marchio di guasto")


def test_due_guasti_di_fila_fermano_il_ciclo(monkeypatch):
    """Alla seconda caduta identica il problema e' sistematico: continuare
    vuol dire solo rifare lo stesso errore su ogni competenza."""
    chiamate = []

    def finto_round(state, target, items):
        chiamate.append(target["suite"])
        return {"suite": target["suite"], "broken": True,
                "verdict": "training terminato come 'failed'"}

    monkeypatch.setattr(autopilot, "_phase_round", finto_round)
    monkeypatch.setattr(autopilot, "_ensure_eval_identity", lambda s: None)
    monkeypatch.setattr(autopilot, "_free_gb", lambda: 999)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)

    state = autopilot._blank_state()
    state["profile"] = {"mmlu": {"passed": 10, "total": 40},
                        "gsm8k": {"passed": 8, "total": 40}}
    autopilot._cycle(state, 300)

    assert len(chiamate) == autopilot.MAX_GUASTI
    assert "failed" in state["stop_reason"]


def test_i_round_salvati_prima_del_marchio_restano_riconoscibili():
    """Lo stato su disco e' piu' vecchio del codice che lo legge: quattro round
    falliti scritti senza `broken` continuavano a consumare i bersagli, e il
    ciclo si dichiarava concluso a ogni ripresa senza fare niente."""
    vecchio = {"suite": "mmlu", "verdict": "training terminato come 'failed'"}
    misurato = {"suite": "math", "wins": 3, "losses": 5, "verdict": "peggiora"}
    assert autopilot.senza_misura(vecchio)
    assert not autopilot.senza_misura(misurato)


def test_la_ui_e_il_ciclo_contano_gli_stessi_bersagli(monkeypatch, tmp_path):
    """`status` mostrava 0 bersagli mentre il ciclo ne aveva quattro: due
    conteggi diversi della stessa cosa, e quello sbagliato era in vista."""
    stato = autopilot._blank_state()
    stato["profile"] = {"mmlu": {"passed": 10, "total": 40},
                        "math": {"passed": 8, "total": 40}}
    stato["rounds"] = [{"suite": "mmlu", "verdict": "training fallito"}]
    monkeypatch.setattr(autopilot, "load_state", lambda model="": stato)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "discardable_artifacts", lambda s: [])

    dalla_ui = {t["suite"] for t in autopilot.status()["targets"]}
    dal_ciclo = {t["suite"] for t in pick_targets(
        stato["profile"], [r["suite"] for r in stato["rounds"]
                           if not autopilot.senza_misura(r)])}
    assert dalla_ui == dal_ciclo == {"mmlu", "math"}


# ==============================================================================
# VIVO O MORTO
# ==============================================================================

def test_un_ciclo_vivo_altrove_non_viene_dichiarato_interrotto(monkeypatch):
    """`_worker` e' una variabile del processo che ha avviato il ciclo. Chi
    risponde alla UI puo' essere un altro processo, e li' il thread non c'e':
    dichiarava interrotto — e lo *scriveva su disco* — un ciclo che stava
    lavorando. Il battito e' l'unico segnale che attraversa i processi."""
    stato = autopilot._blank_state()
    stato["status"] = "running"
    stato["heartbeat"] = time.time()
    scritti = []
    monkeypatch.setattr(autopilot, "load_state", lambda model="": stato)
    monkeypatch.setattr(autopilot, "save_state", lambda s: scritti.append(s["status"]))
    monkeypatch.setattr(autopilot, "discardable_artifacts", lambda s: [])
    monkeypatch.setattr(autopilot, "_worker", None)

    out = autopilot.status()
    assert out["running"], "il battito e' fresco: il ciclo e' vivo"
    assert out["state"]["status"] == "running"
    assert "interrupted" not in scritti


def test_un_battito_vecchio_significa_davvero_interrotto(monkeypatch):
    """Sigma riavviato mentre il ciclo girava: senza questo la UI aspetterebbe
    per sempre un lavoro che non riprendera' da solo."""
    stato = autopilot._blank_state()
    stato["status"] = "running"
    stato["heartbeat"] = time.time() - autopilot.HEARTBEAT_TIMEOUT - 10
    monkeypatch.setattr(autopilot, "load_state", lambda model="": stato)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "discardable_artifacts", lambda s: [])
    monkeypatch.setattr(autopilot, "_worker", None)

    out = autopilot.status()
    assert not out["running"]
    assert out["state"]["status"] == "interrupted"


def test_non_si_avviano_due_cicli_sullo_stesso_stato(monkeypatch):
    """Due cicli che scrivono lo stesso file di stato si sovrascrivono a
    vicenda: il secondo avvio va rifiutato anche quando il primo gira altrove."""
    stato = autopilot._blank_state()
    stato["heartbeat"] = time.time()
    monkeypatch.setattr(autopilot, "load_state", lambda model="": stato)
    monkeypatch.setattr(autopilot, "_worker", None)
    monkeypatch.setattr(autopilot, "_free_gb", lambda: 999)

    out = autopilot.start("m:latest", train_model="org/m")
    assert not out["success"] and "già in esecuzione" in out["error"]


def test_il_round_in_corso_non_resta_fantasma(monkeypatch):
    """Se il ciclo muore, il round che stava lavorando resta "in corso" in
    cima alla lista e non finira' mai: non c'e' piu' nessuno a farlo finire."""
    stato = autopilot._blank_state()
    stato["status"] = "running"
    stato["heartbeat"] = 0
    stato["current_job"] = {"id": "j1", "kind": "training"}
    stato["rounds"] = [{"suite": "mmlu", "verdict": "in corso"}]
    monkeypatch.setattr(autopilot, "load_state", lambda model="": stato)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "discardable_artifacts", lambda s: [])
    monkeypatch.setattr(autopilot, "_worker", None)

    fuori = autopilot.status()["state"]
    assert fuori["rounds"][0]["broken"]
    assert "interrotto" in fuori["rounds"][0]["verdict"]
    assert fuori["current_job"] == {}


def test_leggere_lo_stato_non_lo_modifica(monkeypatch):
    """`status` e' una lettura, e una lettura non scrive.

    Bastava un processo Sigma vecchio, con il modulo caricato prima del
    battito, per riscrivere "interrupted" sopra un training in corso ogni tre
    secondi. Il file lo tocca solo chi sta lavorando.
    """
    stato = autopilot._blank_state()
    stato["status"] = "running"
    stato["heartbeat"] = 0
    stato["rounds"] = [{"suite": "mmlu", "verdict": "in corso"}]
    scritture = []
    monkeypatch.setattr(autopilot, "load_state", lambda model="": stato)
    monkeypatch.setattr(autopilot, "save_state", lambda s: scritture.append(s))
    monkeypatch.setattr(autopilot, "discardable_artifacts", lambda s: [])
    monkeypatch.setattr(autopilot, "_worker", None)

    fuori = autopilot.status()["state"]
    assert not scritture, "nessuna scrittura durante una lettura"
    assert fuori["status"] == "interrupted", "ma il racconto e' corretto"
    assert stato["status"] == "running", "e l'originale resta intatto"
    assert stato["rounds"][0]["verdict"] == "in corso"


# ==============================================================================
# UN CICLO PER MODELLO
# ==============================================================================

def test_ogni_modello_ha_il_suo_file(monkeypatch, tmp_path):
    """Il profilo di un modello non dice niente su un altro, e un round
    accettato sull'uno non e' un round dell'altro."""
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    a = autopilot.state_path("Alieno/ailo-340m-v4:latest")
    b = autopilot.state_path("qwen2.5:0.5b-instruct")
    assert a != b
    assert a.parent == tmp_path and a.suffix == ".json"
    # I caratteri che non stanno in un nome di file non devono sparire in
    # silenzio facendo collidere due modelli diversi.
    assert ":" not in a.name and "/" not in a.name


def test_lo_stato_di_un_modello_non_e_quello_di_un_altro(monkeypatch, tmp_path):
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")

    uno = autopilot._blank_state()
    uno.update(base_model="modello/uno", rounds=[{"suite": "mmlu", "wins": 4, "losses": 1}])
    autopilot.save_state(uno)
    due = autopilot._blank_state()
    due.update(base_model="modello/due")
    autopilot.save_state(due)

    assert len(autopilot.load_state("modello/uno")["rounds"]) == 1
    assert autopilot.load_state("modello/due")["rounds"] == []


def test_un_modello_mai_visto_parte_da_zero(monkeypatch, tmp_path):
    """Scegliere un modello nuovo non deve ereditare le statistiche di quello
    di prima: comincia mai addestrato, con le sue misure."""
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    vecchio = autopilot._blank_state()
    vecchio.update(base_model="vecchio/modello", profile={"mmlu": {"passed": 30, "total": 34}})
    autopilot.save_state(vecchio)
    autopilot.set_active_model("vecchio/modello")

    nuovo = autopilot.load_state("nuovo/modello")
    assert nuovo["profile"] == {} and nuovo["rounds"] == []


def test_il_vecchio_stato_unico_non_va_perso(monkeypatch, tmp_path):
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path / "cicli")
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "cicli" / "_attivo.json")
    storico = tmp_path / "storico.json"
    monkeypatch.setattr(autopilot, "STATE_FILE", storico)
    storico.write_text(json.dumps({"base_model": "vecchio/modello",
                                   "rounds": [{"suite": "mmlu", "wins": 2, "losses": 0}]}),
                       encoding="utf-8")

    assert autopilot.migrate_legacy_state() == "vecchio/modello"
    assert len(autopilot.load_state("vecchio/modello")["rounds"]) == 1
    assert autopilot.migrate_legacy_state() == "", "una volta sola, non a ogni lettura"


def test_due_processi_non_si_contendono_lo_stesso_temporaneo(monkeypatch, tmp_path):
    """Con un solo `.tmp` condiviso, due Sigma che salvano insieme muoiono su
    *[WinError 5] Accesso negato* durante la sostituzione."""
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    visti = []
    vero_write = Path.write_text

    def spia(self, *a, **k):
        if self.suffix == ".tmp":
            visti.append(self.name)
        return vero_write(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", spia)
    autopilot._atomic_write(tmp_path / "x.json", {"a": 1})
    assert visti and str(os.getpid()) in visti[0], "il temporaneo porta il pid"


def test_la_sostituzione_si_riprova(monkeypatch, tmp_path):
    """Un antivirus che tiene aperto il file per un istante non e' un buon
    motivo per ammazzare un ciclo che sta lavorando da ore."""
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    tentativi = {"n": 0}
    vero_replace = Path.replace

    def traballante(self, target):
        tentativi["n"] += 1
        if tentativi["n"] < 3:
            raise PermissionError("[WinError 5] Accesso negato")
        return vero_replace(self, target)

    monkeypatch.setattr(Path, "replace", traballante)
    autopilot._atomic_write(tmp_path / "y.json", {"b": 2})
    assert tentativi["n"] == 3
    assert json.loads((tmp_path / "y.json").read_text(encoding="utf-8")) == {"b": 2}


# ==============================================================================
# CANCELLARE UN ROUND SCARTATO
# ==============================================================================
# Un round scartato lascia tre cose, non una: l'adapter del training, il modello
# fuso — che e' il piu' pesante — e la copia dentro Ollama. La pulizia ne
# cancellava solo la prima, lasciando indietro quasi tutto lo spazio che si
# voleva liberare, e un modello inutile in mezzo a quelli scegliibili.

def _stato_con_round(tmp_path, monkeypatch, accettato=False):
    monkeypatch.setattr(autopilot, "BASE_DIR", tmp_path)
    for jid in ("j-train", "j-merge"):
        cartella = tmp_path / "training" / "jobs" / jid
        cartella.mkdir(parents=True)
        (cartella / "peso.bin").write_bytes(b"x" * 1024)
    stato = autopilot._blank_state()
    stato["rounds"] = [{"suite": "mmlu", "job_id": "j-train", "merge_job_id": "j-merge",
                        "ollama_model": "sigma-cand-j-train", "accepted": accettato,
                        "verdict": "peggiora", "wins": 1, "losses": 9}]
    return stato


def test_si_cancellano_anche_il_merge_e_il_modello_ollama(tmp_path, monkeypatch):
    stato = _stato_con_round(tmp_path, monkeypatch)
    scarti = autopilot.discardable_artifacts(stato)
    assert len(scarti) == 1
    assert scarti[0]["merge_job_id"] == "j-merge"
    assert scarti[0]["ollama_model"] == "sigma-cand-j-train"
    # Il peso deve contare entrambe le cartelle, altrimenti la UI promette
    # meta' dello spazio che libera.
    assert scarti[0]["bytes"] == 2048


def test_un_round_accettato_non_si_tocca(tmp_path, monkeypatch):
    stato = _stato_con_round(tmp_path, monkeypatch, accettato=True)
    assert autopilot.discardable_artifacts(stato) == []


def test_il_modello_del_campione_resta_installato(tmp_path, monkeypatch):
    """Anche se il round che lo ha prodotto non e' fra gli accettati: e' il
    modello che qualcuno sta usando."""
    stato = _stato_con_round(tmp_path, monkeypatch)
    stato["champion"] = {"model": "sigma-cand-j-train", "job_id": "altro"}
    scarti = autopilot.discardable_artifacts(stato)
    assert scarti[0]["ollama_model"] is None


def test_la_pulizia_rimuove_tutto_e_lo_segna(tmp_path, monkeypatch):
    stato = _stato_con_round(tmp_path, monkeypatch)
    rimossi = []
    monkeypatch.setattr(autopilot, "_rimuovi_da_ollama",
                        lambda nome: rimossi.append(nome) or True)
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)

    esito = autopilot.cleanup(stato)
    assert esito["success"]
    assert not (tmp_path / "training" / "jobs" / "j-train").exists()
    assert not (tmp_path / "training" / "jobs" / "j-merge").exists()
    assert rimossi == ["sigma-cand-j-train"]
    assert stato["rounds"][0]["cleaned"] is True


def test_la_prova_a_vuoto_non_cancella_niente(tmp_path, monkeypatch):
    """Serve alla UI per mostrare cosa sparirebbe prima di confermare."""
    stato = _stato_con_round(tmp_path, monkeypatch)
    monkeypatch.setattr(autopilot, "_rimuovi_da_ollama",
                        lambda nome: pytest.fail("non deve toccare Ollama"))
    esito = autopilot.cleanup(stato, dry_run=True)
    assert esito["dry_run"] and len(esito["candidates"]) == 1
    assert (tmp_path / "training" / "jobs" / "j-train").exists()
    assert not stato["rounds"][0].get("cleaned")


# ==============================================================================
# LE IMPOSTAZIONI DEL CICLO
# ==============================================================================

def test_le_impostazioni_restano_nello_stato(monkeypatch, tmp_path):
    """Riprendendo, il ciclo deve rifare quello che stava facendo, non tornare
    ai valori di fabbrica perche' chi lo riprende non li ha ridigitati."""
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    monkeypatch.setattr(autopilot, "_free_gb", lambda: 999)
    monkeypatch.setattr(autopilot, "resolve_pair",
                        lambda e, t="": {"ok": True, "eval_model": e, "train_model": t})
    monkeypatch.setattr(autopilot, "_cycle", lambda s, i: None)

    autopilot.start("m:latest", items=120, max_examples=5000,
                    train_model="org/m", max_seq_length=512)
    salvato = autopilot.load_state("m:latest")
    assert salvato["items"] == 120
    assert salvato["max_examples"] == 5000
    assert salvato["max_seq_length"] == 512


def test_il_contesto_scelto_arriva_al_training(monkeypatch):
    """Se la manopola non raggiunge gli iperparametri del job non serve a
    niente: e' la voce che pesa di piu' sulla memoria."""
    import types

    creati = []
    jobs = types.ModuleType("core.training.jobs")
    jobs.create_training_job = lambda d: creati.append(d) or {"success": False, "error": "stop"}
    jobs.start_training_job = lambda j: {"success": True}
    jobs.merge_job_adapter = lambda *a, **k: {"success": True}
    datasets = types.ModuleType("core.training.datasets")
    datasets.register_hf_dataset = lambda d: {"success": True, "dataset": {"id": "d1"}}
    monkeypatch.setitem(sys.modules, "core.training.jobs", jobs)
    monkeypatch.setitem(sys.modules, "core.training.datasets", datasets)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)

    stato = autopilot._blank_state()
    stato.update(base_model="m:latest", max_seq_length=512, max_examples=4000)
    autopilot._phase_round(stato, {"suite": "mmlu", "label": "x", "datasets": ["d/s"]}, 100)
    assert creati[0]["hyperparams"]["max_seq_length"] == 512
    assert creati[0]["hyperparams"]["max_examples"] == 4000


def test_uno_stato_vuoto_porta_i_valori_di_fabbrica():
    """La UI deve avere sempre qualcosa da mostrare nelle caselle."""
    b = autopilot._blank_state()
    assert b["items"] == autopilot.DEFAULT_ITEMS
    assert b["max_examples"] == 30000 and b["max_seq_length"] == 1024


# ==============================================================================
# RIAPRIRE UN BERSAGLIO
# ==============================================================================

def _stato_con_verdetti(tmp_path, monkeypatch):
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)
    stato = autopilot._blank_state()
    stato["base_model"] = "m:latest"
    stato["rounds"] = [
        {"suite": "mmlu", "wins": 0, "losses": 9, "accepted": False, "verdict": "peggiora"},
        {"suite": "math", "wins": 7, "losses": 1, "accepted": True, "verdict": "migliora"},
        {"suite": "gsm8k", "broken": True, "verdict": "training fallito"},
    ]
    autopilot.save_state(stato)
    return stato


def test_riaprire_libera_solo_i_round_misurati_e_scartati(tmp_path, monkeypatch):
    """Un verdetto viziato non deve consumare un bersaglio per sempre. Ma i
    round accettati restano: il campione e' fatto di quelli."""
    _stato_con_verdetti(tmp_path, monkeypatch)
    esito = autopilot.reopen_targets("m:latest")
    assert esito["success"] and esito["riaperti"] == ["mmlu"]

    dopo = autopilot.load_state("m:latest")
    per_suite = {r["suite"]: r for r in dopo["rounds"]}
    assert autopilot.senza_misura(per_suite["mmlu"]), "mmlu torna disponibile"
    assert not autopilot.senza_misura(per_suite["math"]), "math resta accettato"
    assert per_suite["math"]["accepted"] is True


def test_il_bersaglio_riaperto_torna_fra_quelli_scegliibili(tmp_path, monkeypatch):
    _stato_con_verdetti(tmp_path, monkeypatch)
    profilo = {"mmlu": {"passed": 10, "total": 40}}
    prima = [t["suite"] for t in pick_targets(
        profilo, [r["suite"] for r in autopilot.load_state("m:latest")["rounds"]
                  if not autopilot.senza_misura(r)])]
    autopilot.reopen_targets("m:latest")
    dopo = [t["suite"] for t in pick_targets(
        profilo, [r["suite"] for r in autopilot.load_state("m:latest")["rounds"]
                  if not autopilot.senza_misura(r)])]
    assert "mmlu" not in prima and "mmlu" in dopo


def test_il_verdetto_originale_resta_leggibile(tmp_path, monkeypatch):
    """Cancellarlo nasconderebbe cos'era successo: si annota, non si sostituisce."""
    _stato_con_verdetti(tmp_path, monkeypatch)
    autopilot.reopen_targets("m:latest")
    mmlu = next(r for r in autopilot.load_state("m:latest")["rounds"]
                if r["suite"] == "mmlu")
    assert "peggiora" in mmlu["verdict"] and "riaperto" in mmlu["verdict"]


def test_senza_niente_da_riaprire_lo_dice(tmp_path, monkeypatch):
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    stato = autopilot._blank_state()
    stato["base_model"] = "vuoto:latest"
    autopilot.save_state(stato)
    assert not autopilot.reopen_targets("vuoto:latest")["success"]


# ==============================================================================
# FERMARE VUOL DIRE FERMARE
# ==============================================================================

def test_lo_stop_chiude_il_lavoro_in_corso(monkeypatch):
    """Il docstring diceva che lo stop era onorato nell'attesa, ma il ciclo non
    lo controllava mai: chi premeva Ferma aspettava la fine del training — ore
    — mentre il pannello diceva "fermato"."""
    import types

    chiusi = []
    jobs = types.ModuleType("core.training.jobs")
    jobs.get_job_status = lambda j: {"job": {"status": "running"}}
    jobs.stop_training_job = lambda j: chiusi.append(j) or {"success": True}
    monkeypatch.setitem(sys.modules, "core.training.jobs", jobs)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)
    monkeypatch.setattr(autopilot.time, "sleep",
                        lambda s: pytest.fail("non deve mettersi ad aspettare"))

    autopilot._stop_requested.set()
    try:
        esito = autopilot._wait_for_job("j1", "training", autopilot._blank_state())
    finally:
        autopilot._stop_requested.clear()
    assert esito == "stopped"
    assert chiusi == ["j1"], "il processo va chiuso, non lasciato correre"


def test_lo_stop_chiude_anche_una_valutazione(monkeypatch):
    import types

    annullati = []
    bench = types.ModuleType("core.training.benchmarks")
    bench.list_benchmark_jobs = lambda: [{"id": "bm1", "status": "running"}]
    bench.cancel_benchmark_job = lambda j: annullati.append(j) or True
    monkeypatch.setitem(sys.modules, "core.training.benchmarks", bench)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)

    autopilot._stop_requested.set()
    try:
        esito = autopilot._wait_for_job("bm1", "benchmark", autopilot._blank_state())
    finally:
        autopilot._stop_requested.clear()
    assert esito == "stopped" and annullati == ["bm1"]


def test_senza_stop_si_continua_ad_aspettare(monkeypatch):
    """Chiudere un job che nessuno ha chiesto di fermare butterebbe ore."""
    import types

    stati = iter(["running", "completed"])
    jobs = types.ModuleType("core.training.jobs")
    jobs.get_job_status = lambda j: {"job": {"status": next(stati)}}
    jobs.stop_training_job = lambda j: pytest.fail("non deve chiudere niente")
    monkeypatch.setitem(sys.modules, "core.training.jobs", jobs)
    monkeypatch.setattr(autopilot, "save_state", lambda s: None)
    monkeypatch.setattr(autopilot.time, "sleep", lambda s: None)

    autopilot._stop_requested.clear()
    assert autopilot._wait_for_job("j1", "training", autopilot._blank_state()) == "completed"


# ==============================================================================
# CANCELLARE I ROUND
# ==============================================================================

def _stato_con_storia(tmp_path, monkeypatch):
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path / "cicli")
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "cicli" / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    monkeypatch.setattr(autopilot, "BASE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "note", lambda s, l, m: None)
    monkeypatch.setattr(autopilot, "_rimuovi_da_ollama", lambda n: True)
    for jid in ("j1", "j2", "j3"):
        cartella = tmp_path / "training" / "jobs" / jid
        cartella.mkdir(parents=True)
        (cartella / "peso.bin").write_bytes(b"x" * 512)
    stato = autopilot._blank_state()
    stato["base_model"] = "m:latest"
    stato["profile"] = {"mmlu": {"passed": 10, "total": 40}}
    stato["rounds"] = [
        {"suite": "mmlu", "job_id": "j1", "accepted": True, "wins": 9, "losses": 1},
        {"suite": "math", "job_id": "j2", "accepted": False, "wins": 0, "losses": 9},
        {"suite": "arc", "job_id": "j3", "accepted": False, "wins": 1, "losses": 2},
    ]
    stato["champion"] = {"label": "round mmlu", "model": "sigma-cand-j1", "job_id": "j1"}
    autopilot.save_state(stato)
    return stato


def test_si_cancellano_solo_gli_ultimi_round(tmp_path, monkeypatch):
    _stato_con_storia(tmp_path, monkeypatch)
    esito = autopilot.drop_rounds("m:latest", quanti=2)
    assert esito["success"] and esito["cancellati"] == 2 and esito["restano"] == 1
    dopo = autopilot.load_state("m:latest")
    assert [r["suite"] for r in dopo["rounds"]] == ["mmlu"]


def test_gli_artefatti_se_ne_vanno_con_i_round(tmp_path, monkeypatch):
    """Tenerli occuperebbe disco per una storia che non c'e' piu'."""
    _stato_con_storia(tmp_path, monkeypatch)
    autopilot.drop_rounds("m:latest", quanti=2)
    assert not (tmp_path / "training" / "jobs" / "j3").exists()
    assert (tmp_path / "training" / "jobs" / "j1").exists(), "il round tenuto resta intero"


def test_il_profilo_non_si_tocca(tmp_path, monkeypatch):
    """Cancellare i round non e' un reset: il profilo del modello di partenza
    resta valido, e rifarlo costerebbe una valutazione intera."""
    _stato_con_storia(tmp_path, monkeypatch)
    autopilot.drop_rounds("m:latest")
    assert autopilot.load_state("m:latest")["profile"] == {"mmlu": {"passed": 10, "total": 40}}


def test_il_campione_torna_indietro_se_veniva_da_un_round_cancellato(tmp_path, monkeypatch):
    """Non si puo' tenere per campione qualcosa la cui storia non esiste piu'."""
    _stato_con_storia(tmp_path, monkeypatch)
    autopilot.drop_rounds("m:latest")
    campione = autopilot.load_state("m:latest")["champion"]
    assert campione["job_id"] is None
    assert campione["model"] == "m:latest"


def test_senza_round_lo_dice(tmp_path, monkeypatch):
    monkeypatch.setattr(autopilot, "STATE_DIR", tmp_path)
    monkeypatch.setattr(autopilot, "ACTIVE_FILE", tmp_path / "_attivo.json")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "storico.json")
    stato = autopilot._blank_state()
    stato["base_model"] = "vuoto:latest"
    autopilot.save_state(stato)
    assert not autopilot.drop_rounds("vuoto:latest")["success"]
