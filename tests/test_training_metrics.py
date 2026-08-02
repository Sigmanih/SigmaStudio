# ==============================================================================
# tests/test_training_metrics.py — Serie storica delle metriche e sua diagnosi
# ==============================================================================
"""Copre core/training/metrics.py: lettura dal log, aggregati e verdetti.

Le serie sono costruite a mano perche' i casi che contano — overfitting,
memorizzazione, divergenza — richiederebbero altrimenti un training vero.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.training.metrics import (METRIC_PREFIX, METRIC_GUIDE, diagnose,
                                   read_metric_history, summarize)


def _codes(history):
    return {v["code"] for v in diagnose(history)}


def _descending(n=60, start=2.0, step=0.03):
    return [{"step": i, "loss": max(0.2, start - i * step)} for i in range(n)]


# =========================================================== lettura dal log

class TestMetricReading:

    def _log(self, tmp_path, lines):
        path = tmp_path / "train.log"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_metric_lines_are_extracted_and_ordered(self, tmp_path):
        path = self._log(tmp_path, [
            "[SIGMA] Avvio training",
            f'{METRIC_PREFIX} {{"step": 1, "loss": 2.5}}',
            "Qualche riga di rumore da transformers",
            f'{METRIC_PREFIX} {{"step": 2, "loss": 2.1}}',
        ])
        history = read_metric_history(path)
        assert [r["step"] for r in history] == [1, 2]
        assert history[0]["loss"] == 2.5

    def test_a_truncated_line_does_not_lose_the_rest(self, tmp_path):
        """Il log viene letto mentre il processo scrive: l'ultima riga puo'
        essere a meta'."""
        path = self._log(tmp_path, [
            f'{METRIC_PREFIX} {{"step": 1, "loss": 2.5}}',
            f'{METRIC_PREFIX} {{"step": 2, "los',
            f'{METRIC_PREFIX} {{"step": 3, "loss": 1.9}}',
        ])
        assert [r["step"] for r in read_metric_history(path)] == [1, 3]

    def test_a_missing_log_is_not_an_error(self, tmp_path):
        assert read_metric_history(tmp_path / "mai-scritto.log") == []

    def test_the_cache_follows_the_file(self, tmp_path):
        path = self._log(tmp_path, [f'{METRIC_PREFIX} {{"step": 1, "loss": 2.0}}'])
        assert len(read_metric_history(path)) == 1
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f'\n{METRIC_PREFIX} {{"step": 2, "loss": 1.5}}\n')
        assert len(read_metric_history(path)) == 2


# =============================================================== aggregati

class TestSummary:

    def test_aggregates_over_a_descending_run(self):
        history = _descending()
        history += [{"step": i, "eval_loss": 1.0} for i in (10, 20, 30)]
        summary = summarize(history)
        assert summary["points"] == 60 and summary["eval_points"] == 3
        assert summary["min_loss"] == pytest.approx(summary["last_loss"])
        assert summary["trend"] < 0                    # in discesa
        assert summary["perplexity"] == pytest.approx(2.718, rel=0.01)  # exp(1)

    def test_perplexity_is_capped_instead_of_overflowing(self):
        """exp(700) alzerebbe OverflowError e farebbe fallire tutta la chiamata."""
        summary = summarize([{"step": 1, "loss": 900.0}, {"step": 1, "eval_loss": 900.0}])
        assert summary["perplexity"] < 1e9

    def test_nan_values_are_skipped_by_the_aggregates(self):
        summary = summarize([{"step": 1, "loss": 2.0}, {"step": 2, "loss": float("nan")}])
        assert summary["last_loss"] == 2.0

    def test_an_empty_history_does_not_blow_up(self):
        summary = summarize([])
        assert summary["points"] == 0 and summary["last_loss"] is None


# ================================================================ diagnosi

class TestDiagnostics:

    def test_a_run_still_descending_is_reported_as_learning(self):
        assert "learning" in _codes(_descending())

    def test_a_flat_run_is_reported_as_a_plateau(self):
        assert "plateau" in _codes([{"step": i, "loss": 1.0} for i in range(40)])

    def test_a_rising_validation_loss_is_flagged_as_overfitting(self):
        history = _descending()
        # eval al minimo allo step 20, poi in risalita netta
        history += [{"step": s, "eval_loss": loss} for s, loss in
                    ((10, 1.30), (20, 1.20), (30, 1.45), (40, 1.60), (50, 1.75))]
        codes = _codes(history)
        assert "overfitting" in codes
        # ...e il verdetto ottimista non deve comparire accanto all'avviso
        assert "learning" not in codes

    def test_the_overfitting_verdict_names_the_best_checkpoint(self):
        history = _descending()
        history += [{"step": s, "eval_loss": loss} for s, loss in
                    ((10, 1.30), (20, 1.20), (30, 1.45), (40, 1.60), (50, 1.75))]
        verdict = next(v for v in diagnose(history) if v["code"] == "overfitting")
        assert "step 20" in verdict["detail"]

    def test_a_wide_train_validation_gap_is_flagged_as_memorization(self):
        history = [{"step": i, "loss": 0.05} for i in range(40)]
        history += [{"step": s, "eval_loss": 2.0} for s in (10, 20, 30)]
        assert "memorizing" in _codes(history)

    def test_a_nan_loss_is_critical_and_stops_every_other_verdict(self):
        history = _descending(30) + [{"step": 31, "loss": float("nan")}]
        verdicts = diagnose(history)
        assert len(verdicts) == 1
        assert verdicts[0]["code"] == "diverged" and verdicts[0]["level"] == "critical"

    def test_too_few_evaluations_is_said_out_loud(self):
        history = _descending()
        history += [{"step": 10, "eval_loss": 1.0}]
        assert "warming_up" in _codes(history)

    def test_two_evaluations_are_not_enough_to_cry_overfitting(self):
        """Due punti in salita sono rumore: servono almeno tre valutazioni."""
        history = _descending()
        history += [{"step": 10, "eval_loss": 1.0}, {"step": 20, "eval_loss": 1.9}]
        assert "overfitting" not in _codes(history)

    def test_an_empty_history_says_so_instead_of_guessing(self):
        assert _codes([]) == {"no_data"}

    def test_the_most_serious_verdict_comes_first(self):
        history = [{"step": i, "loss": 0.05} for i in range(40)]
        history += [{"step": s, "eval_loss": 2.0 + s * 0.01} for s in (10, 20, 30, 40)]
        levels = [v["level"] for v in diagnose(history)]
        assert levels == sorted(levels, key=lambda l: {"critical": 0, "warning": 1,
                                                       "good": 2, "info": 3}[l])


class TestRunSeparation:
    """Un job fermato e ripreso scrive nello stesso log.

    Senza tagliare sugli avvii la serie incolla run diversi di fila: la loss
    "risale" di colpo al valore iniziale del giro nuovo, e tendenza e media
    finiscono per descrivere una cosa che non è mai successa.
    """

    def _log(self, tmp_path, runs):
        from core.training.metrics import RUN_HEADER
        lines = []
        for run in runs:
            lines.append(RUN_HEADER)
            lines += [f'{METRIC_PREFIX} {json.dumps(r)}' for r in run]
        path = tmp_path / "train.log"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_runs_are_split_on_the_start_header(self, tmp_path):
        from core.training.metrics import split_runs
        path = self._log(tmp_path, [
            [{"step": 1, "loss": 8.0}, {"step": 2, "loss": 4.0}],
            [{"step": 1, "loss": 0.4}, {"step": 2, "loss": 0.3}],
        ])
        runs = split_runs(path)
        assert [len(r) for r in runs] == [2, 2]
        assert runs[-1][0]["loss"] == 0.4

    def test_only_the_last_run_drives_the_verdict(self, tmp_path):
        """Il caso reale: 815 punti di un tentativo precedente falsavano la
        tendenza del run in corso."""
        from core.training.metrics import job_metrics
        noisy = [{"step": i, "loss": 8.0 - i * 0.01} for i in range(1, 300)]
        calm = [{"step": i, "loss": 0.33} for i in range(1, 60)]
        path = self._log(tmp_path, [noisy, calm])
        payload = job_metrics({"id": "x", "log_path": str(path)})
        assert payload["run_count"] == 2
        assert payload["previous_points"] == len(noisy)
        assert payload["summary"]["points"] == len(calm)
        assert payload["summary"]["last_loss"] == 0.33

    def test_a_log_without_headers_counts_as_one_run(self, tmp_path):
        from core.training.metrics import split_runs
        path = tmp_path / "train.log"
        path.write_text(f'{METRIC_PREFIX} {{"step": 1, "loss": 2.0}}', encoding="utf-8")
        assert len(split_runs(path)) == 1


class TestRisingLoss:
    """Una loss che risale è la cosa più importante da dire, e il verdetto
    restava muto: la pendenza positiva non rientrava né in 'plateau' né in
    'sta ancora imparando'."""

    def test_a_rising_loss_is_reported(self):
        history = [{"step": i, "loss": 0.3 + i * 0.02} for i in range(40)]
        verdict = next(v for v in diagnose(history) if v["code"] == "rising")
        assert verdict["level"] == "warning"
        assert "learning rate" in verdict["action"]

    def test_small_wobbles_are_not_called_a_problem(self):
        """La loss oscilla sempre: sotto la soglia resta un plateau."""
        history = [{"step": i, "loss": 1.0 + (0.002 if i % 2 else 0)} for i in range(40)]
        assert "rising" not in _codes(history)

    def test_a_descending_run_is_never_called_rising(self):
        assert "rising" not in _codes(_descending())


class TestHardwareTrouble:
    """La scheda satura non da' errore: rallenta e basta.

    Su Windows una VRAM richiesta oltre quella fisica viene riversata in
    memoria di sistema. Il training continua, dieci o venti volte più lento, e
    l'unico segnale è un ETA che cresce. È successo davvero: un run a batch 8 è
    passato da 5 a 80 secondi per step senza che nulla lo dicesse.
    """

    def _timed(self, n, early=5.0, late=None):
        """Serie con `elapsed_s` cumulativo, opzionalmente più lenta in coda."""
        late = late if late is not None else early
        history, clock = [], 0.0
        for step in range(1, n + 1):
            clock += early if step <= n // 2 else late
            history.append({"step": step, "loss": 1.0, "elapsed_s": round(clock, 2)})
        return history

    def test_a_collapse_in_throughput_is_reported(self):
        codes = _codes(self._timed(80, early=5.0, late=80.0))
        assert "slowdown" in codes

    def test_a_steady_run_is_not_called_slow(self):
        assert "slowdown" not in _codes(self._timed(80, early=5.0))

    def test_normal_jitter_is_not_a_collapse(self):
        """Un run oscilla sempre un po': il doppio non basta a gridare."""
        assert "slowdown" not in _codes(self._timed(80, early=5.0, late=9.0))

    def test_a_short_run_says_nothing_about_speed(self):
        """Con pochi step la mediana iniziale è rumore."""
        assert "slowdown" not in _codes(self._timed(10, early=5.0, late=90.0))

    def test_asking_for_more_vram_than_the_card_has_is_critical(self):
        history = [{"step": i, "loss": 1.0, "vram_gb": 18.9, "vram_total_gb": 15.9}
                   for i in range(30)]
        verdict = next(v for v in diagnose(history) if v["code"] == "vram_overcommit")
        assert verdict["level"] == "critical"
        assert "batch" in verdict["action"]

    def test_fitting_inside_the_card_raises_nothing(self):
        history = [{"step": i, "loss": 1.0, "vram_gb": 12.0, "vram_total_gb": 15.9}
                   for i in range(30)]
        assert "vram_overcommit" not in _codes(history)

    def test_a_run_without_vram_data_is_not_judged_on_it(self):
        """I run precedenti al campo `vram_gb` non devono essere accusati."""
        assert "vram_overcommit" not in _codes(_descending())


class TestMetricGuide:

    @pytest.mark.parametrize("metric", ["loss", "eval_loss", "perplexity", "gap"])
    def test_every_metric_explains_itself(self, metric):
        """Il Monitor mostra queste voci in hover: se ne manca una, la UI resta
        muta proprio sul numero che l'utente non capisce."""
        entry = METRIC_GUIDE[metric]
        assert {"label", "what", "good", "bad", "optimal"} <= set(entry)
        assert all(entry[k].strip() for k in entry)
