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


class TestMetricGuide:

    @pytest.mark.parametrize("metric", ["loss", "eval_loss", "perplexity", "gap"])
    def test_every_metric_explains_itself(self, metric):
        """Il Monitor mostra queste voci in hover: se ne manca una, la UI resta
        muta proprio sul numero che l'utente non capisce."""
        entry = METRIC_GUIDE[metric]
        assert {"label", "what", "good", "bad", "optimal"} <= set(entry)
        assert all(entry[k].strip() for k in entry)
