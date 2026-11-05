"""Direzioni dei margini del classificatore finale, con letture GGUF limitate."""

from pathlib import Path
import math


def select_margin_pairs(cases: list[dict], max_pairs: int = 64) -> list[tuple[int, int]]:
    """Priorita' agli estremi; poi alle scelte piu' incerte della calibrazione."""
    import numpy as np

    if not 1 <= len(cases) <= 16 or not 1 <= max_pairs <= 128:
        raise ValueError("Casi o coppie fuori budget")
    boundaries, margins = [], {}
    for case in cases:
        decisions = case["decisions"]
        first, second, gap = (np.asarray(decisions[k]) for k in ("first", "second", "margins"))
        if (first.ndim != 1 or not 1 <= len(first) <= 512 or second.shape != first.shape
                or gap.shape != first.shape or not np.isfinite(gap).all() or np.any(gap < 0)
                or first.dtype.kind not in "iu" or second.dtype.kind not in "iu"
                or np.any(first < 0) or np.any(second < 0) or np.any(first == second)):
            raise ValueError("Decisioni non valide")
        for index, (a, b, value) in enumerate(zip(first, second, gap)):
            pair = tuple(sorted((int(a), int(b))))
            margins[pair] = min(float(value), margins.get(pair, float("inf")))
            if index in (0, len(first)-1) and pair not in boundaries:
                boundaries.append(pair)
    ordered = boundaries + [p for p in sorted(margins, key=lambda p: (margins[p], p)) if p not in boundaries]
    return ordered[:max_pairs]


def read_head_directions(path: Path, pairs: list[tuple[int, int]]):
    """C_a-C_b con C=W_output diag(gamma); non include il fattore RMS scalare."""
    import numpy as np
    from gguf import GGUFReader
    from gguf.quants import dequantize

    if not 1 <= len(pairs) <= 128 or any(len(p) != 2 or p[0] == p[1] for p in pairs):
        raise ValueError("Coppie non valide o fuori budget")
    reader = GGUFReader(str(path), mode="r")
    try:
        tensors = {t.name: t for t in reader.tensors}
        if (any(k.startswith("output.") and k != "output.weight" for k in tensors)
                or "output_norm.bias" in tensors):
            raise ValueError("Scale o bias aggiuntivi del classificatore non supportati")
        head, norm = tensors["output.weight"], tensors["output_norm.weight"]
        if len(head.shape) != 2:
            raise ValueError("Classificatore finale non matriciale")
        width, vocabulary = map(int, head.shape)
        ids = {t for pair in pairs for t in pair}
        if (not 128 <= width <= 8192 or len(ids)*width > 4_000_000
                or any(type(t) is not int or not 0 <= t < vocabulary for t in ids)):
            raise ValueError("Righe del classificatore fuori budget")
        gamma = dequantize(norm.data, norm.tensor_type).astype(np.float64).reshape(-1)
        if gamma.shape != (width,) or not np.isfinite(gamma).all():
            raise ValueError("Normalizzazione finale non valida")
        rows = {i: dequantize(head.data[i:i+1], head.tensor_type).astype(np.float64).reshape(width)
                for i in ids}
        directions = np.stack([(rows[a]-rows[b])*gamma for a, b in pairs])
        lengths = np.linalg.norm(directions, axis=1)
        if not np.isfinite(lengths).all() or np.any(lengths <= 0):
            raise ValueError("Direzioni dei margini nulle o non finite")
        return directions / lengths[:, None]
    finally:
        mapping = getattr(reader.data, "_mmap", None)
        if mapping is not None:
            mapping.close()


def compare_outcomes(baseline: list[dict], candidate: list[dict]) -> dict:
    """Confronto appaiato: il conteggio aggregato non nasconde regressioni."""
    def index(rows):
        if not 1 <= len(rows) <= 64:
            raise ValueError("Esiti fuori budget")
        result = {}
        for row in rows:
            key = row.get("id")
            if (not isinstance(key, str) or not 1 <= len(key) <= 128 or key in result
                    or type(row.get("passed")) is not bool or type(row.get("ended")) is not bool):
                raise ValueError("Esiti non validi o identificativi duplicati")
            result[key] = row
        return result

    left, right = index(baseline), index(candidate)
    if left.keys() != right.keys():
        raise ValueError("I compiti confrontati non coincidono")
    wins = [key for key in left if not left[key]["passed"] and right[key]["passed"]]
    losses = [key for key in left if left[key]["passed"] and not right[key]["passed"]]
    new_limits = [key for key in left if left[key]["ended"] and not right[key]["ended"]]
    discordant = len(wins)+len(losses)
    probability = (min(1.0, 2*sum(math.comb(discordant, k) for k in range(min(len(wins), len(losses))+1))/2**discordant)
                   if discordant else 1.0)
    n = len(left)

    def interval(passed):
        z = 1.959963984540054
        p = passed/n
        denominator = 1+z*z/n
        center = (p+z*z/(2*n))/denominator
        radius = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
        return [max(0.0, center-radius), min(1.0, center+radius)]

    a, b = sum(x["passed"] for x in left.values()), sum(x["passed"] for x in right.values())
    return {"cases": n, "baseline_passed": a, "candidate_passed": b,
            "wins": wins, "regressions": losses, "new_length_limits": new_limits,
            "baseline_length_limits": sum(not x["ended"] for x in left.values()),
            "candidate_length_limits": sum(not x["ended"] for x in right.values()),
            "mcnemar_exact_two_sided_p": probability,
            "baseline_wilson95": interval(a), "candidate_wilson95": interval(b),
            "observed_nonregression": not losses and not new_limits}
