"""Diagnostica locale dei pesi: nessun training e nessuna scrittura del checkpoint."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any, Sequence

from core.logger import get_logger

log = get_logger(__name__)


def reconstruction_error(reference: Any, candidate: Any, second_moment: Any,
                         *, bootstrap: int = 0, seed: int = 42) -> dict:
    """Proxy diagonale dell'errore di uscita, non della perdita finale del modello."""
    import numpy as np

    ref = np.asarray(reference)
    value = np.asarray(candidate)
    if ref.ndim != 2 or ref.shape != value.shape or not ref.size or ref.size > 4_000_000:
        raise ValueError("Matrici incompatibili, vuote o oltre quattro milioni di valori")
    ref, value = ref.astype(np.float64), value.astype(np.float64)
    moment = np.asarray(second_moment, dtype=np.float64)
    if moment.shape != (ref.shape[1],) or not np.all(np.isfinite(moment)) or np.any(moment < 0):
        raise ValueError("Secondi momenti non validi o incompatibili con le colonne")
    if not np.all(np.isfinite(ref)) or not np.all(np.isfinite(value)):
        raise ValueError("Pesi non finiti")
    if not 0 <= bootstrap <= 1000:
        raise ValueError("Numero di ricampionamenti non valido")
    delta = value - ref
    weighted = float(np.sum(delta * delta * moment))
    energy = float(np.sum(ref * ref * moment))
    plain_energy = float(np.sum(ref * ref))
    total_moment = float(np.sum(moment))
    interval = None
    if bootstrap and ref.shape[0] >= 8 and energy:
        if bootstrap * ref.shape[0] > 2_000_000:
            raise ValueError("Ricampionamento oltre il budget di memoria")
        # Si ricampionano le righe accoppiate, non singoli pesi correlati fra loro.
        per_row_error = np.sum(delta * delta * moment, axis=1)
        per_row_energy = np.sum(ref * ref * moment, axis=1)
        indices = np.random.default_rng(seed).integers(ref.shape[0], size=(bootstrap, ref.shape[0]))
        denominators = np.sum(per_row_energy[indices], axis=1)
        ratios = np.sum(per_row_error[indices], axis=1) / np.where(denominators > 0, denominators, np.nan)
        finite = ratios[np.isfinite(ratios)]
        if finite.size >= bootstrap * 0.9:
            interval = np.quantile(finite, [0.025, 0.975]).tolist()
    return {
        "relative_weighted_mse": weighted / energy if energy else None,
        "relative_mse": float(np.sum(delta * delta)) / plain_energy if plain_energy else None,
        "weighted_error_energy": weighted,
        "reference_energy": energy,
        "max_channel_energy_share": float(np.max(moment)) / total_moment if total_moment else None,
        "row_bootstrap_ci95": interval,
    }


def permute_swiglu_sample(gate: Any, up: Any, down: Any, order: Any) -> tuple:
    """Permutazione coordinata che preserva la funzione SwiGLU prima della quantizzazione."""
    import numpy as np

    gate, up, down = (np.asarray(value) for value in (gate, up, down))
    order = np.asarray(order)
    if any(value.ndim != 2 for value in (gate, up, down)):
        raise ValueError("Servono tre matrici bidimensionali")
    if gate.shape != up.shape or down.shape[1] != gate.shape[0]:
        raise ValueError("Dimensioni incompatibili per SwiGLU")
    if sum(value.size for value in (gate, up, down)) > 4_000_000:
        raise ValueError("Campione oltre quattro milioni di valori")
    if (not np.issubdtype(order.dtype, np.integer) or order.shape != (gate.shape[0],)
            or not np.array_equal(np.sort(order), np.arange(gate.shape[0]))):
        raise ValueError("L'ordine non e' una permutazione completa dei canali")
    return gate[order, :], up[order, :], down[:, order]


def audit_gguf(candidate: Path, reference: Path, imatrix: Path,
               names: Sequence[str], *, rows: int = 8,
               max_values: int = 32_000_000, seconds: float = 60,
               row_seed: int | None = None, bootstrap: int = 0) -> dict:
    """Campiona righe in GGUF di sola lettura, con limiti di memoria e tempo."""
    import numpy as np
    from gguf import GGUFReader
    from gguf.quants import dequantize

    if (not 1 <= len(names) <= 256 or not 1 <= rows <= 512
            or not 1 <= max_values <= 32_000_000 or not 0 < seconds <= 120
            or not 0 <= bootstrap <= 1000):
        raise ValueError("Budget di analisi non valido")
    if len(set(names)) != len(names):
        raise ValueError("Nomi dei tensori duplicati")
    readers = []
    entries, skipped = [], []
    count = 0
    stop_reason = ""
    deadline = monotonic() + seconds
    rng = np.random.default_rng(row_seed) if row_seed is not None else None
    try:
        for path in (candidate, reference, imatrix):
            readers.append(GGUFReader(str(Path(path)), mode="r"))
        cand, ref, stats = ({tensor.name: tensor for tensor in reader.tensors} for reader in readers)
        for name in names:
            if monotonic() >= deadline:
                stop_reason = "time_budget"
                break
            if name not in cand or name not in ref or name + ".in_sum2" not in stats:
                skipped.append({"name": name, "reason": "pesi o momenti assenti"})
                continue
            left, right = cand[name], ref[name]
            if len(left.shape) != 2 or not np.array_equal(left.shape, right.shape):
                skipped.append({"name": name, "reason": "forme incompatibili"})
                continue
            columns, row_count = map(int, left.shape)
            if not 0 < columns <= 65536 or not row_count:
                skipped.append({"name": name, "reason": "dimensioni fuori budget"})
                continue
            sample_count = min(rows, row_count, 4_000_000 // columns)
            indices = (np.sort(rng.choice(row_count, size=sample_count, replace=False)) if rng is not None
                       else np.linspace(0, row_count - 1, sample_count, dtype=np.int64))
            values = columns * len(indices)
            if count + values > max_values:
                stop_reason = "value_budget"
                break
            counts = stats.get(name + ".counts")
            if counts is None or counts.data.size != 1 or not float(counts.data.flat[0]) > 0:
                skipped.append({"name": name, "reason": "conteggio calibrazione non valido"})
                continue
            moment = np.asarray(stats[name + ".in_sum2"].data).reshape(-1) / float(counts.data.flat[0])
            if moment.shape != (columns,):
                skipped.append({"name": name, "reason": "momenti incompatibili"})
                continue
            samples = []
            for tensor in (right, left):
                sample = []
                for index in indices:
                    if monotonic() >= deadline:
                        stop_reason = "time_budget"
                        break
                    sample.append(dequantize(tensor.data[index:index + 1], tensor.tensor_type).reshape(columns).copy())
                if stop_reason:
                    break
                samples.append(np.stack(sample))
            if stop_reason:
                break
            result = reconstruction_error(samples[0], samples[1], moment, bootstrap=bootstrap)
            count += values
            entries.append({"name": name, "sample_rows": len(indices), "total_rows": row_count,
                            "row_indices": indices.tolist(),
                            "candidate_type": left.tensor_type.name, "reference_type": right.tensor_type.name,
                            "restore_weight_mib": (right.n_bytes - left.n_bytes) / 2**20, **result})
        return {"entries": entries, "skipped": skipped, "sampled_values": count,
                "stop_reason": stop_reason, "complete": not stop_reason and not skipped,
                "row_seed": row_seed, "bootstrap": bootstrap,
                "metric": "diagonal input-second-moment proxy; sampled output rows"}
    finally:
        for reader in readers:
            mapping = getattr(reader.data, "_mmap", None)
            if mapping is not None:
                try:
                    mapping.close()
                except (OSError, BufferError) as exc:
                    log.debug("Chiusura della mappa GGUF non riuscita: %s", exc)
