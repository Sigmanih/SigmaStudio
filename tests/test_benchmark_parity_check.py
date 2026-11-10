"""Il controllo di parità deve accorgersi delle risposte interrotte anche quando il prefisso non coincide."""
import json

import pytest

from tools.benchmarks import benchmark_parity_check as parity

pytestmark = pytest.mark.motore


def _write(tmp_path, job_id, answers, tps, sha="a" * 64):
    (tmp_path / f"{job_id}.jsonl").write_text(
        "".join(json.dumps({"id": k, "given_answer": v, "passed": v.endswith("```")}) + "\n"
                for k, v in answers.items()), encoding="utf-8")
    return {"id": job_id, "metrics": {"tokens_per_sec": tps},
            "execution_environment": {"checkpoint": {"sha256": sha}}}


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(parity, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(parity, "RESULTS", tmp_path / "results.json")
    return tmp_path


def _save(runs, *jobs):
    (runs / "results.json").write_text(json.dumps(list(jobs)), encoding="utf-8")


def test_esecuzioni_identiche_non_hanno_problemi(runs):
    answers = {"q1": "```python\nreturn 1\n```", "q2": "```python\nreturn 2\n```"}
    _save(runs, _write(runs, "ref", answers, 29.0), _write(runs, "cand", answers, 28.0))
    report = parity.compare("ref", "cand")
    assert report["problems"] == [] and report["divergent"] == 0


def test_rileva_interruzione_con_parola_diversa_e_velocita(runs):
    ref = {"q1": "```python\ndef f():\n    \"\"\"Return True is sorted.\"\"\"\n    return 1\n```", "q2": "```x```"}
    cand = {"q1": "```python\ndef f():\n    \"\"\"Return True if", "q2": "```x```"}
    _save(runs, _write(runs, "ref", ref, 29.0), _write(runs, "cand", cand, 7.0))
    report = parity.compare("ref", "cand")
    assert report["premature_stops"] == ["q1"] and report["pass_flips"] == ["q1"]
    assert any("interrotte" in p for p in report["problems"])
    assert any("velocità" in p for p in report["problems"])


def test_checkpoint_diverso_rende_la_parita_indefinita(runs):
    answers = {"q1": "```a```"}
    _save(runs, _write(runs, "ref", answers, 1.0), _write(runs, "cand", answers, 1.0, sha="b" * 64))
    assert any("checkpoint" in p for p in parity.compare("ref", "cand")["problems"])
