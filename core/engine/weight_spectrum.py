"""Analisi spettrale con budget: checkpoint immutato, una matrice alla volta."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Callable, Sequence

from core.logger import get_logger

log = get_logger(__name__)


def streamed_spectrum(shape: tuple[int, int], read_rows: Callable, *,
                      second_moment=None, ranks=(16, 32, 64), oversampling=8,
                      seed=42, block_rows=128, seconds=60,
                      max_working_mib=256) -> dict:
    """Misura una proiezione casuale; l'errore non e' quello della SVD ottimale."""
    import numpy as np

    m, n = map(int, shape)
    ranks = tuple(ranks)
    if (not ranks or any(not isinstance(r, int) or r < 1 for r in ranks)
            or sorted(set(ranks)) != list(ranks) or max(ranks) > min(m, n, 256)):
        raise ValueError("Ranghi non validi o oltre il limite di 256")
    if (not 0 < m <= 65536 or not 0 < n <= 65536 or m*n > 100_000_000
            or not 0 <= oversampling <= 32 or not 1 <= block_rows <= 512
            or not 0 < seconds <= 120 or not 16 <= max_working_mib <= 512):
        raise ValueError("Dimensioni o budget non validi")
    width = min(max(ranks) + oversampling, m, n)
    block_rows = min(block_rows, max(1, 2_000_000 // n))
    estimated = 8 * (6*(m+n)*width + 8*width*width + 4*block_rows*n)
    if estimated > max_working_mib * 2**20:
        raise ValueError("La proiezione supera il budget di memoria di lavoro")
    moment = None
    if second_moment is not None:
        moment = np.asarray(second_moment, dtype=np.float64)
        if moment.shape != (n,) or not np.all(np.isfinite(moment)) or np.any(moment < 0):
            raise ValueError("Secondi momenti incompatibili o non validi")
    deadline = monotonic() + seconds

    def check_time():
        if monotonic() >= deadline:
            raise TimeoutError("Budget temporale della mappa spettrale esaurito")

    def block(start):
        check_time()
        stop = min(m, start + block_rows)
        value = np.asarray(read_rows(start, stop), dtype=np.float32)
        if value.shape != (stop-start, n) or not np.all(np.isfinite(value)):
            raise ValueError("Blocco di pesi non valido")
        return stop, value

    omega = np.random.default_rng(seed).standard_normal((n, width), dtype=np.float32)
    scale = np.sqrt(moment).astype(np.float32) if moment is not None else None
    if scale is not None and not np.all(np.isfinite(scale)):
        raise ValueError("Secondi momenti fuori dall'intervallo numerico")
    modes = {"unweighted": {"y": np.empty((m, width), dtype=np.float32), "energy": 0.0}}
    if scale is not None:
        modes["diagonal_weighted"] = {"y": np.empty((m, width), dtype=np.float32), "energy": 0.0}
    weighted_omega = omega * scale[:, None] if scale is not None else None
    for start in range(0, m, block_rows):
        stop, value = block(start)
        column_energy = np.einsum("ij,ij->j", value, value, dtype=np.float64)
        modes["unweighted"]["energy"] += float(np.sum(column_energy))
        modes["unweighted"]["y"][start:stop] = value @ omega
        if scale is not None:
            modes["diagonal_weighted"]["energy"] += float(column_energy @ moment)
            modes["diagonal_weighted"]["y"][start:stop] = value @ weighted_omega
    del omega, weighted_omega
    for mode in modes.values():
        check_time()
        mode["q"], _ = np.linalg.qr(mode.pop("y"), mode="reduced")
        mode["b"] = np.zeros((width, n), dtype=np.float64)
    for start in range(0, m, block_rows):
        stop, value = block(start)
        modes["unweighted"]["b"] += modes["unweighted"]["q"][start:stop].T @ value
        if scale is not None:
            modes["diagonal_weighted"]["b"] += modes["diagonal_weighted"]["q"][start:stop].T @ (value * scale)
    result = {}
    for key, mode in modes.items():
        check_time()
        singular = np.linalg.svd(mode.pop("b"), compute_uv=False)
        squared = np.cumsum(singular.astype(np.float64)**2)
        energy = mode["energy"]
        curves = []
        for rank in ranks:
            fraction = float(squared[rank-1] / energy) if energy else None
            if fraction is not None and fraction > 1.0001:
                raise ArithmeticError("Energia proiettata incoerente con l'energia totale")
            fraction = min(1.0, max(0.0, fraction)) if fraction is not None else None
            curves.append({"rank": rank, "retained_energy": fraction,
                           "relative_reconstruction_mse": 1-fraction if fraction is not None else None,
                           "factor_parameters": rank*(m+n),
                           "parameter_ratio": rank*(m+n)/(m*n)})
        result[key] = {"energy": energy, "projected_singular_values": singular.tolist(), "curves": curves}
    check_time()
    return {"shape": [m, n], "seed": seed, "sketch_width": width,
            "estimated_working_mib": estimated/2**20, "modes": result,
            "method": "randomized range projection; two passes; no power iterations",
            "scope": "constructed approximation, not optimal rank or task accuracy"}


def full_gram_spectrum(shape: tuple[int, int], read_rows: Callable, *,
                       second_moment=None, ranks=(16, 32, 64), block_rows=128,
                       device="cpu", seconds=120, max_working_mib=2048) -> dict:
    """Spettro del Gram completo; il budget temporale e' cooperativo fra operazioni BLAS."""
    import numpy as np

    m, n = map(int, shape)
    ranks = tuple(ranks)
    if (not ranks or any(not isinstance(r, int) or r < 1 for r in ranks)
            or sorted(set(ranks)) != list(ranks) or max(ranks) > min(m, n)):
        raise ValueError("Ranghi non validi")
    estimated = 4*m*n + 32*min(m, n)**2 + 64*2**20
    if (not 0 < m <= 65536 or not 0 < n <= 65536 or m*n > 100_000_000
            or min(m, n) > 8192 or not 1 <= block_rows <= 512
            or not 0 < seconds <= 120 or not 64 <= max_working_mib <= 4096
            or estimated > max_working_mib*2**20):
        raise ValueError("Dimensioni o budget del Gram completo non validi")
    moment = None if second_moment is None else np.asarray(second_moment, dtype=np.float64)
    if moment is not None and (moment.shape != (n,) or not np.all(np.isfinite(moment)) or np.any(moment < 0)):
        raise ValueError("Secondi momenti incompatibili")
    deadline = monotonic() + seconds

    def check_time():
        if monotonic() >= deadline:
            raise TimeoutError("Budget temporale del Gram completo esaurito")

    cuda = str(device).startswith("cuda:")
    if device != "cpu" and not cuda:
        raise ValueError("Dispositivo non supportato")
    if cuda:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA non disponibile: usare il metodo CPU o proiettato")
        precision = getattr(torch.backends.cuda.matmul, "fp32_precision", None)
        reduced_precision = (precision != "ieee" if precision is not None
                             else torch.backends.cuda.matmul.allow_tf32)
        if reduced_precision:
            raise ValueError("Per la misura spettrale disabilitare TF32 nel processo di analisi")
        free, _ = torch.cuda.mem_get_info(device)
        reusable = max(0, torch.cuda.memory_reserved(device)-torch.cuda.memory_allocated(device))
        if free + reusable < estimated + 256*2**20:
            raise MemoryError("Memoria GPU insufficiente per il budget spettrale")
        weight = torch.empty((m, n), dtype=torch.float32, device=device)
    else:
        weight = np.empty((m, n), dtype=np.float32)
    raw_energy, weighted_energy = 0.0, 0.0
    block_rows = min(block_rows, max(1, 2_000_000 // n))
    for start in range(0, m, block_rows):
        check_time()
        stop = min(m, start+block_rows)
        value = np.asarray(read_rows(start, stop), dtype=np.float32)
        if value.shape != (stop-start, n) or not np.all(np.isfinite(value)):
            raise ValueError("Blocco non valido")
        column_energy = np.einsum("ij,ij->j", value, value, dtype=np.float64)
        raw_energy += float(np.sum(column_energy))
        if moment is not None:
            weighted_energy += float(column_energy @ moment)
        if cuda:
            weight[start:stop].copy_(torch.from_numpy(value.copy()).to(device))
        else:
            weight[start:stop] = value
    check_time()
    gram = weight.T @ weight if m >= n else weight @ weight.T
    result = {}

    def measure(key, matrix, energy):
        check_time()
        eigen = (torch.linalg.eigvalsh(matrix).detach().cpu().numpy() if cuda
                 else np.linalg.eigvalsh(matrix)).astype(np.float64)[::-1]
        if not np.all(np.isfinite(eigen)):
            raise ArithmeticError("Autovalori non finiti")
        trace_error = abs(float(np.sum(eigen))-energy)/energy if energy else 0.0
        negative_mass = float(-np.sum(eigen[eigen < 0]))/energy if energy else 0.0
        positive = np.maximum(eigen, 0)
        cumulative = np.cumsum(positive)
        total = float(cumulative[-1])
        curves = []
        for rank in ranks:
            fraction = min(1.0, max(0.0, float(cumulative[rank-1]/energy))) if energy else None
            curves.append({"rank": rank, "retained_energy": fraction,
                           "relative_reconstruction_mse": 1-fraction if fraction is not None else None,
                           "factor_parameters": rank*(m+n), "parameter_ratio": rank*(m+n)/(m*n)})
        result[key] = {"energy": energy, "projected_singular_values": np.sqrt(positive).tolist(),
                       "trace_relative_error": trace_error, "negative_eigen_mass_ratio": negative_mass,
                       "numerically_reliable": trace_error < 1e-3 and negative_mass < 1e-3,
                       "ranks_for_energy": {str(p): int(np.searchsorted(cumulative, p*total)+1)
                                            if total else None for p in (0.9, 0.95, 0.99, 0.999)},
                       "curves": curves}

    measure("unweighted", gram, raw_energy)
    if moment is not None:
        scale_np = np.sqrt(moment).astype(np.float32)
        if not np.all(np.isfinite(scale_np)):
            raise ValueError("Scala di attivazione fuori dall'intervallo numerico")
        scale = torch.from_numpy(scale_np).to(device) if cuda else scale_np
        if m >= n:
            gram = gram * scale[:, None] * scale[None, :]
        else:
            weight *= scale[None, :]
            gram = weight @ weight.T
        measure("diagonal_weighted", gram, weighted_energy)
    check_time()
    return {"shape": [m, n], "estimated_working_mib": estimated/2**20, "modes": result,
            "method": "full Gram spectrum, float32; float64 energy sums", "device": device,
            "scope": "matrix approximation; diagonal moments omit input correlations"}


def map_gguf_spectra(path: Path, imatrix: Path, names: Sequence[str], *,
                     ranks=(16, 32, 64), seconds=600, progress=None,
                     method="projected", device="cpu") -> dict:
    """Legge al massimo 192 matrici e restituisce misure parziali se scade il tempo."""
    import numpy as np
    from gguf import GGUFReader
    from gguf.quants import dequantize

    if (not 0 < seconds <= 600 or not 1 <= len(names) <= 192 or len(set(names)) != len(names)
            or method not in ("projected", "gram")):
        raise ValueError("Budget o elenco delle matrici non valido")
    readers, entries, skipped = [], [], []
    deadline = monotonic() + seconds
    processed = 0
    reason = ""
    try:
        readers = [GGUFReader(str(path), mode="r")]
        readers.append(GGUFReader(str(imatrix), mode="r"))
        tensors, stats = ({t.name: t for t in reader.tensors} for reader in readers)
        for name in names:
            remaining = deadline - monotonic()
            if remaining <= 0:
                reason = "time_budget"
                break
            try:
                tensor = tensors[name]
                if len(tensor.shape) != 2:
                    raise ValueError("Matrice non bidimensionale")
                n, m = map(int, tensor.shape)
                processed += 2*m*n
                if processed > 40_000_000_000:
                    reason = "value_budget"
                    break
                count_tensor = stats[name + ".counts"]
                if count_tensor.data.size != 1:
                    raise ValueError("Conteggi di calibrazione non supportati")
                count = float(count_tensor.data.flat[0])
                if not np.isfinite(count) or count <= 0:
                    raise ValueError("Conteggio di calibrazione non valido")
                moment = np.asarray(stats[name + ".in_sum2"].data).reshape(-1) / count

                def read_rows(start, stop):
                    return dequantize(tensor.data[start:stop], tensor.tensor_type).reshape(stop-start, n)

                analyze = full_gram_spectrum if method == "gram" else streamed_spectrum
                extra = {"device": device} if method == "gram" else {}
                measured = analyze((m, n), read_rows, second_moment=moment,
                                   ranks=ranks, seconds=min(120, remaining), **extra)
                entries.append({"name": name, "tensor_type": tensor.tensor_type.name,
                                "weight_bytes": tensor.n_bytes, "calibration_count": count, **measured})
            except TimeoutError:
                reason = "time_budget"
                break
            except (KeyError, ValueError, ArithmeticError, MemoryError, np.linalg.LinAlgError) as exc:
                skipped.append({"name": name, "reason": str(exc)})
                log.debug("Mappa spettrale: %s non analizzabile: %s", name, exc)
            if progress:
                progress({"processed": len(entries)+len(skipped), "total": len(names), "name": name})
        return {"entries": entries, "skipped": skipped, "stop_reason": reason,
                "complete": not reason and not skipped, "ranks": list(ranks)}
    finally:
        for reader in readers:
            mapping = getattr(reader.data, "_mmap", None)
            if mapping is not None:
                try:
                    mapping.close()
                except (OSError, BufferError) as exc:
                    log.debug("Chiusura della mappa GGUF non riuscita: %s", exc)
