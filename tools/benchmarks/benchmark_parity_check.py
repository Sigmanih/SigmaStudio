"""Parità end-to-end fra due esecuzioni del benchmark sullo stesso checkpoint.

I test unitari del kernel verificano i singoli pezzi; questo controllo guarda il
percorso intero (Studio -> kernel -> worker), dove il 7/11 sono comparse
risposte interrotte a metà senza alcun test fallito. A temperatura 0 lo stesso
checkpoint deve dare quasi sempre la stessa risposta: le divergenze residue
devono restare poche e nessuna risposta deve fermarsi prima del riferimento.

Uso:
    python -m tools.benchmarks.benchmark_parity_check RIFERIMENTO CANDIDATO
I due argomenti sono id di job (bm_...) presenti nello storico del Benchmark Lab.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

RUNS_DIR = Path(__file__).resolve().parents[2] / "store" / "training_lab" / "benchmark_runs"
RESULTS = RUNS_DIR.parent / "official_benchmark_results.json"


def load_entries(job_id: str) -> dict:
    path = RUNS_DIR / f"{job_id}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"Esecuzione non trovata: {path}")
    entries = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                log.warning("Riga illeggibile ignorata in %s", path.name)
                continue
            if isinstance(row, dict) and row.get("id"):
                entries[row["id"]] = row
    return entries


def load_job(job_id: str) -> dict:
    try:
        data = json.loads(RESULTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    return next((j for j in jobs if isinstance(j, dict) and j.get("id") == job_id), {})


def _checkpoint(job: dict):
    env = job.get("execution_environment") or {}
    return (env.get("checkpoint") or {}).get("sha256")


def premature_stop(reference: dict, candidate: dict) -> bool:
    """Interruzione: risposta più corta del riferimento e prefisso esatto, oppure blocco di codice lasciato aperto.

    Il secondo caso serve perché prima del taglio basta una parola diversa per perdere il prefisso.
    """
    ref, cand = reference.get("given_answer") or "", candidate.get("given_answer") or ""
    if not cand or len(cand) >= len(ref):
        return False
    unclosed = cand.count("```") % 2 == 1 and ref.count("```") % 2 == 0
    return unclosed or ref.startswith(cand.rstrip("`").rstrip())


def compare(reference_id: str, candidate_id: str, *, max_divergent_pct: float = 10.0,
            min_speed_ratio: float = 0.8) -> dict:
    ref, cand = load_entries(reference_id), load_entries(candidate_id)
    common = sorted(set(ref) & set(cand))
    if not common:
        raise ValueError("Nessun quesito in comune fra le due esecuzioni")
    divergent = [k for k in common if ref[k].get("given_answer") != cand[k].get("given_answer")]
    stopped = [k for k in divergent if premature_stop(ref[k], cand[k])]
    flips = [k for k in common if bool(ref[k].get("passed")) != bool(cand[k].get("passed"))]
    ref_job, cand_job = load_job(reference_id), load_job(candidate_id)
    speeds = [((j.get("metrics") or {}).get("tokens_per_sec") or 0) for j in (ref_job, cand_job)]
    ratio = speeds[1] / speeds[0] if speeds[0] else None
    same_checkpoint = _checkpoint(ref_job) is not None and _checkpoint(ref_job) == _checkpoint(cand_job)
    problems = []
    if not same_checkpoint:
        problems.append("checkpoint diverso o non verificato: la parità non è definita")
    if stopped:
        problems.append(f"{len(stopped)} risposte interrotte prima del riferimento")
    if 100 * len(divergent) / len(common) > max_divergent_pct:
        problems.append(f"{len(divergent)} risposte divergenti su {len(common)}")
    if ratio is not None and ratio < min_speed_ratio:
        problems.append(f"velocità al {ratio:.0%} del riferimento")
    return {
        "reference": reference_id, "candidate": candidate_id, "checked": len(common),
        "same_checkpoint": same_checkpoint, "divergent": len(divergent),
        "premature_stops": stopped, "pass_flips": flips,
        "passed": [sum(bool(r[k].get("passed")) for k in common) for r in (ref, cand)],
        "tokens_per_sec": speeds, "speed_ratio": round(ratio, 3) if ratio else None,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("reference")
    parser.add_argument("candidate")
    parser.add_argument("--max-divergent-pct", type=float, default=10.0)
    parser.add_argument("--min-speed-ratio", type=float, default=0.8)
    args = parser.parse_args()
    try:
        report = compare(args.reference, args.candidate, max_divergent_pct=args.max_divergent_pct,
                         min_speed_ratio=args.min_speed_ratio)
    except (OSError, ValueError) as exc:
        log.error("Parità non verificabile: %s", exc)
        print("SIGMA-CHECK " + json.dumps({"check": "benchmark_parity", "checked": 0, "problems": 1}))
        return 2
    for key, value in report.items():
        log.info("%s: %s", key, value)
    print("SIGMA-CHECK " + json.dumps({"check": "benchmark_parity", "checked": report["checked"],
                                        "problems": len(report["problems"])}))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
