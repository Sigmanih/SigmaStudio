"""Un riferimento non certificato o un test inefficace non deve diventare supervisione."""

from collections import Counter

from core.modules.sigma_training_lab.verified_coding_data import coding_cases, verify_corpus, verify_solution


def test_riferimenti_e_mutanti_eseguibili():
    cases = coding_cases()
    assert len({c.id for c in cases}) == 16
    assert Counter(c.split for c in cases) == {"train": 6, "validation": 2, "confirmation": 8}
    results = verify_corpus()
    assert all(r["reference"]["passed"] for r in results)
    assert all(r["mutant"]["status"] == "failed" for r in results)


def test_uscita_prematura_non_certifica_il_codice():
    case = coding_cases()[0]
    result = verify_solution(case, "def merge_closed(intervals):\n    raise SystemExit(0)")
    assert not result["passed"]
    assert verify_solution(case, "import os\ndef merge_closed(intervals):\n    return []")["status"] == "invalid_code"


def test_codice_che_non_termina_ha_un_limite():
    result = verify_solution(coding_cases()[0], "def merge_closed(intervals):\n    while True:\n        x=1", timeout=.2)
    assert result["status"] == "timeout"
