"""Protocollo limitato per replay e misure di attivazione, senza scrivere pesi."""

from __future__ import annotations

from pathlib import Path
import struct


def write_replay(path: Path, cases: list[dict]) -> None:
    """Accetta token gia' formattati dal runtime, senza ricostruire il template."""
    if not 1 <= len(cases) <= 16:
        raise ValueError("Sono ammessi da 1 a 16 casi")
    chunks = [b"SGAP0001", struct.pack("<I", len(cases))]
    for case in cases:
        prefix, answer = case["prefix_tokens"], case["answer_tokens"]
        if not prefix or not 1 <= len(answer) <= 512 or len(prefix)+len(answer) > 8192:
            raise ValueError("Numero di token fuori budget")
        tokens = list(prefix) + list(answer)
        if any(type(t) is not int or not 0 <= t < 2**31 for t in tokens):
            raise ValueError("Token non valido")
        chunks.append(struct.pack("<II", len(prefix), len(answer)))
        chunks.append(struct.pack(f"<{len(tokens)}i", *tokens))
    with Path(path).open("xb") as out:
        out.write(b"".join(chunks))


def read_capture(path: Path) -> list[dict]:
    """Rifiuta file parziali, sovradimensionati o statistiche incoerenti."""
    import numpy as np

    path = Path(path)
    if not 12 <= path.stat().st_size <= 512*2**20:
        raise ValueError("Dimensione della cattura fuori budget")
    with path.open("rb") as stream:
        def exact(size):
            value = stream.read(size)
            if len(value) != size:
                raise ValueError("Cattura troncata")
            return value

        def integer():
            return struct.unpack("<I", exact(4))[0]

        def array(dtype, count):
            return np.frombuffer(exact(np.dtype(dtype).itemsize*count), dtype=dtype).copy()

        version = exact(8)
        if version not in (b"SGAO0001", b"SGAO0002", b"SGAO0003", b"SGAO0004", b"SGAO0005"):
            raise ValueError("Protocollo della cattura non valido")
        count = integer()
        if not 1 <= count <= 16:
            raise ValueError("Numero di casi fuori budget")
        cases = []
        for _ in range(count):
            matches, predictions = integer(), integer()
            if not 1 <= predictions <= 512 or matches > predictions:
                raise ValueError("Conteggi delle predizioni non validi")
            size = integer()
            if not 1 <= size <= (64 if version == b"SGAO0005" else 10):
                raise ValueError("Numero di tensori fuori budget")
            tensors = {}
            for _ in range(size):
                length = integer()
                if not 1 <= length <= 64:
                    raise ValueError("Nome del tensore fuori budget")
                name = exact(length).decode("ascii")
                if name in tensors:
                    raise ValueError("Tensore duplicato")
                width, tokens, sampled = integer(), integer(), integer()
                valid_sample = sampled == 128 if version == b"SGAO0001" else sampled == width <= 8192
                if version == b"SGAO0005":
                    valid_sample = 1 <= sampled <= min(2048, width)
                if not 128 <= width <= 65536 or not 1 <= tokens <= 512 or not valid_sample:
                    raise ValueError("Forma della cattura fuori budget")
                if tokens != predictions:
                    raise ValueError("Numero di osservazioni diverso dalle predizioni")
                channels = array("<u4", sampled)
                sums, sums2 = array("<f8", width), array("<f8", width)
                features = array("<f4", tokens*sampled).reshape(tokens, sampled)
                if (len(set(channels)) != sampled or np.any(channels >= width)
                        or not np.all(np.isfinite(sums)) or not np.all(np.isfinite(sums2))
                        or not np.all(np.isfinite(features)) or np.any(sums2 < 0)):
                    raise ValueError("Statistiche della cattura non valide")
                if (not np.allclose(features.sum(axis=0, dtype=np.float64), sums[channels], atol=1e-6, rtol=1e-6)
                        or not np.allclose(np.square(features.astype(np.float64)).sum(axis=0),
                                           sums2[channels], atol=1e-6, rtol=1e-6)
                        or np.any(sums*sums > tokens*sums2 + 1e-6*np.maximum(1, tokens*sums2))):
                    raise ValueError("Statistiche non coerenti con i campioni")
                tensors[name] = {"width": width, "tokens": tokens, "channels": channels,
                                 "sum": sums, "sum2": sums2, "features": features}
            case = {"tensors": tensors, "greedy_matches": matches, "predictions": predictions}
            if version in (b"SGAO0003", b"SGAO0004"):
                first, second, margins = array("<i4", predictions), array("<i4", predictions), array("<f4", predictions)
                if (np.any(first < 0) or np.any(second < 0) or np.any(first == second)
                        or not np.isfinite(margins).all() or np.any(margins < 0)):
                    raise ValueError("Decisioni di calibrazione non valide")
                case["decisions"] = {"first": first, "second": second, "margins": margins}
            if version == b"SGAO0004":
                if len(tensors) != 1:
                    raise ValueError("La distillazione richiede una sola uscita FFN")
                item = next(iter(tensors.values()))
                hidden = array("<f4", predictions*item["width"]).reshape(predictions, item["width"])
                p1, p2 = array("<f4", predictions), array("<f4", predictions)
                if (not np.isfinite(hidden).all() or not np.isfinite(p1).all() or not np.isfinite(p2).all()
                        or np.any(p1 < 0) or np.any(p2 < 0) or np.any(p1+p2 > 1+1e-6)):
                    raise ValueError("Stati o probabilita' per la distillazione non validi")
                case.update({"hidden": hidden, "native_top_probabilities": np.stack([p1, p2], axis=1)})
            cases.append(case)
        if stream.read(1):
            raise ValueError("Dati in eccesso nella cattura")
        return cases


def summarize_capture(cases: list[dict], outcomes: list[bool]) -> dict:
    """Confronto descrittivo, con uguale peso per caso: non identifica cause."""
    import numpy as np

    if (not cases or len(cases) != len(outcomes) or any(type(x) is not bool for x in outcomes)
            or not any(outcomes) or all(outcomes)):
        raise ValueError("Occorrono casi riusciti e falliti con verdetto esplicito")
    names = sorted(cases[0]["tensors"])
    if not names or any(sorted(case["tensors"]) != names for case in cases):
        raise ValueError("Tensori acquisiti diversi tra i casi")
    result = []
    for name in names:
        reference = cases[0]["tensors"][name]
        values = []
        for case in cases:
            item = case["tensors"][name]
            if item["width"] != reference["width"] or not np.array_equal(item["channels"], reference["channels"]):
                raise ValueError("Canali diversi tra i casi")
            features = item["features"].astype(np.float64)
            if features.shape[1] > 128:
                raise ValueError("La covarianza descrittiva richiede al massimo 128 canali")
            centered = features - features.mean(axis=0)
            covariance = centered.T @ centered / len(features)
            eigen = np.maximum(np.linalg.eigvalsh(covariance), 0)[::-1]
            energy = float(eigen.sum())
            values.append({"mean_square": float(item["sum2"].sum()/item["tokens"]/item["width"]),
                           "sample_rank95": int(np.searchsorted(np.cumsum(eigen), .95*energy)+1) if energy else None,
                           "sample_participation_rank": float(energy**2/np.square(eigen).sum()) if energy else None})
        groups = {}
        for label, flag in (("passed", True), ("failed", False)):
            selected = [v for v, outcome in zip(values, outcomes) if outcome == flag]
            groups[label] = {"cases": len(selected)}
            for key in values[0]:
                valid = [v[key] for v in selected if v[key] is not None]
                groups[label][key+"_median"] = float(np.median(valid)) if valid else None
        result.append({"name": name, "input_width": reference["width"], "sampled_channels": len(reference["channels"]),
                       "groups": groups, "per_case": values})
    return {"tensors": result, "scope": "observational replay; 128 sampled channels; equal case weights; no causal or accuracy guarantee"}


def fit_output_basis(cases: list[dict], name: str, rank: int, *, protect_last=False, protect_first=False,
                     protected_directions=None):
    """PCA lineare senza bias, con uguale peso ai casi e budget di 16M valori."""
    import numpy as np

    if not 1 <= len(cases) <= 16 or type(rank) is not int or not 1 <= rank <= 512:
        raise ValueError("Casi o rango fuori budget")
    items = [case["tensors"][name] for case in cases]
    width = items[0]["width"]
    if not 128 <= width <= 8192 or sum(x["tokens"] for x in items)*width > 16_000_000:
        raise ValueError("Matrice di calibrazione fuori budget")
    for item in items:
        if (item["width"] != width or not np.array_equal(item["channels"], np.arange(width))
                or item["features"].shape != (item["tokens"], width)
                or not np.all(np.isfinite(item["features"]))):
            raise ValueError("Servono uscite complete, coerenti e finite")
    training = np.concatenate([x["features"].astype(np.float64)/np.sqrt(x["tokens"]) for x in items])
    if rank > min(training.shape):
        raise ValueError("Rango maggiore delle osservazioni disponibili")
    protected_count = 0
    if protect_last or protect_first or protected_directions is not None:
        # Il chiamante deve includere lo stato di fine risposta nel replay.
        positions = ([0] if protect_first else []) + ([-1] if protect_last else [])
        anchors = [x["features"][p] for x in items for p in positions]
        if protected_directions is not None:
            directions = np.asarray(protected_directions, dtype=np.float64)
            if (directions.ndim != 2 or directions.shape[1] != width or not 1 <= len(directions) <= 128
                    or not np.isfinite(directions).all()):
                raise ValueError("Direzioni protette non valide")
            norms = np.linalg.norm(directions, axis=1)
            if not np.isfinite(norms).all() or np.any(norms <= 0):
                raise ValueError("Direzioni protette nulle o fuori intervallo")
            anchors.extend(directions/norms[:, None])
        last = np.stack(anchors).astype(np.float64)
        _, singular_last, vt_last = np.linalg.svd(last, full_matrices=False)
        threshold = (singular_last[0] * max(last.shape) * np.finfo(np.float64).eps
                     if len(singular_last) else 0)
        protected_count = int(np.sum(singular_last > threshold))
        if protected_count > rank:
            raise ValueError("Il rango non contiene tutti gli stati protetti")
        protected = vt_last[:protected_count]
        residual = training - (training @ protected.T) @ protected
        _, _, vt = np.linalg.svd(residual, full_matrices=False)
        combined = np.concatenate([protected, vt[:rank-protected_count]])
        basis = np.linalg.qr(combined.T, mode="reduced")[0].T.astype(np.float32)
    else:
        _, _, vt = np.linalg.svd(training, full_matrices=False)
        basis = vt[:rank].astype(np.float32)
    total = float(np.square(training).sum())
    retained = float(np.square(training @ basis.T.astype(np.float64)).sum()/total) if total else None
    return basis, {"rank": rank, "width": width, "cases": len(cases),
                   "observations": len(training),
                   "training_retained_energy": retained,
                   "protected_state_rank": protected_count,
                   "protect_first": bool(protect_first), "protect_last": bool(protect_last),
                   "scope": "uncentered output PCA; equal case weights; calibration energy only"}


def write_projection_basis(path: Path, basis) -> None:
    """Conserva l'orientamento delle righe e verifica che la base sia ortonormale."""
    import numpy as np

    basis = np.asarray(basis, dtype="<f4")
    if (basis.ndim != 2 or not 1 <= basis.shape[0] <= min(512, basis.shape[1])
            or not 128 <= basis.shape[1] <= 8192 or not np.all(np.isfinite(basis))):
        raise ValueError("Forma o valori della base non validi")
    if not np.allclose(basis.astype(np.float64) @ basis.T, np.eye(len(basis)), atol=1e-5, rtol=1e-5):
        raise ValueError("La base non e' ortonormale")
    with Path(path).open("xb") as out:
        out.write(b"SGAB0001")
        out.write(struct.pack("<II", basis.shape[1], basis.shape[0]))
        out.write(basis.tobytes(order="C"))


def write_lowrank_map(path: Path, encoder, decoder) -> None:
    """Fattori indipendenti: nessuna ortogonalita' implicita dopo la distillazione."""
    import numpy as np

    encoder, decoder = (np.asarray(x, dtype="<f4") for x in (encoder, decoder))
    if (encoder.ndim != 2 or decoder.shape != encoder.shape
            or not 128 <= encoder.shape[1] <= 8192
            or not 1 <= encoder.shape[0] <= min(512, encoder.shape[1])
            or not np.isfinite(encoder).all() or not np.isfinite(decoder).all()):
        raise ValueError("Fattori non validi")
    with Path(path).open("xb") as out:
        out.write(b"SGAF0001")
        out.write(struct.pack("<II", encoder.shape[1], encoder.shape[0]))
        out.write(encoder.tobytes(order="C"));out.write(decoder.tobytes(order="C"))


def write_channel_reconstruction(path: Path, removed, anchors, coefficients, *, width: int) -> None:
    """La mappa non richiede le attivazioni eliminate: usa soltanto canali conservati."""
    import numpy as np

    removed, anchors = np.asarray(removed), np.asarray(anchors)
    values = np.asarray(coefficients, dtype='<f4')
    if (type(width) is not int or not 128 <= width <= 65536 or removed.ndim != 2 or anchors.ndim != 2
            or not 1 <= len(removed) == len(anchors) <= 64 or removed.shape[1] > 512
            or anchors.shape[1] > 1024 or removed.shape[1]+anchors.shape[1] > width
            or bool(removed.shape[1]) != bool(anchors.shape[1])
            or removed.dtype.kind not in 'iu' or anchors.dtype.kind not in 'iu'
            or values.shape != (len(removed), removed.shape[1], anchors.shape[1])
            or values.size > 16777216 or not np.isfinite(values).all() or np.any(np.abs(values) > 10000)):
        raise ValueError('Mappa di ricostruzione non valida')
    chunks = [b'SGCR0001', struct.pack('<IIII', len(removed), width, removed.shape[1], anchors.shape[1])]
    for drop, keep, matrix in zip(removed, anchors, values):
        for row in (drop, keep):
            if np.any(row < 0) or np.any(row >= width) or np.any(row[1:] <= row[:-1]):
                raise ValueError('Indici di ricostruzione non validi')
        if set(drop) & set(keep):
            raise ValueError('Canali rimossi e conservati sovrapposti')
        chunks.extend([drop.astype('<u4').tobytes(), keep.astype('<u4').tobytes(), matrix.tobytes()])
    with Path(path).open('xb') as stream:
        stream.write(b''.join(chunks))


def write_channel_plan(path: Path, channels, *, width: int) -> None:
    """Seleziona campioni di ingresso FFN senza acquisire ogni canale di ogni layer."""
    if (type(width) is not int or not 128 <= width <= 65536 or not 1 <= len(channels) <= 64
            or not 1 <= len(channels[0]) <= min(2048, width)):
        raise ValueError("Piano fuori budget")
    sampled = len(channels[0])
    chunks = [b"SGCP0001", struct.pack("<III", len(channels), width, sampled)]
    for row in channels:
        if (len(row) != sampled or any(type(i) is not int or not 0 <= i < width for i in row)
                or any(a >= b for a, b in zip(row, row[1:]))):
            raise ValueError("Canali del piano non validi")
        chunks.append(struct.pack(f"<{sampled}I", *row))
    with Path(path).open("xb") as stream:
        stream.write(b"".join(chunks))


def write_channel_mask(path: Path, channels, *, width: int) -> None:
    """Maschera uniforme per layer, con identita' esplicita se non elimina canali."""
    if (type(width) is not int or not 128 <= width <= 65536
            or not 1 <= len(channels) <= 256):
        raise ValueError("Maschera fuori budget")
    removed = len(channels[0])
    if not 0 <= removed <= min(4096, width-1) or len(channels)*removed > 1048576:
        raise ValueError("Canali fuori budget")
    chunks = [b"SGCM0001", struct.pack("<III", len(channels), width, removed)]
    for row in channels:
        if len(row) != removed or any(type(i) is not int or not 0 <= i < width for i in row):
            raise ValueError("Canali non validi")
        if any(a >= b for a, b in zip(row, row[1:])):
            raise ValueError("Canali duplicati o non ordinati")
        chunks.append(struct.pack(f"<{removed}I", *row))
    with Path(path).open("xb") as stream:
        stream.write(b"".join(chunks))


def read_generation(path: Path) -> list[dict]:
    """Legge esiti di generazione libera; i verdetti richiedono test separati."""
    import math

    path = Path(path)
    if not 12 <= path.stat().st_size <= 64*1024:
        raise ValueError("File di generazione fuori budget")
    with path.open("rb") as stream:
        def exact(size):
            value = stream.read(size)
            if len(value) != size:
                raise ValueError("Generazione troncata")
            return value

        if exact(8) != b"SGAG0001":
            raise ValueError("Protocollo di generazione non valido")
        count = struct.unpack("<I", exact(4))[0]
        if not 1 <= count <= 16:
            raise ValueError("Numero di generazioni fuori budget")
        results = []
        for _ in range(count):
            tokens, ended, calls, seconds = struct.unpack("<IIId", exact(20))
            if (tokens > 512 or ended not in (0, 1) or not 1 <= calls <= 2**18
                    or not math.isfinite(seconds) or not 0 < seconds <= 1000):
                raise ValueError("Misure di generazione non valide")
            ids = list(struct.unpack(f"<{tokens}i", exact(tokens*4)))
            if any(t < 0 for t in ids):
                raise ValueError("Token generato non valido")
            results.append({"tokens": ids, "ended": bool(ended), "intervention_calls": calls, "seconds": seconds})
        if stream.read(1):
            raise ValueError("Dati in eccesso nella generazione")
        return results


def decode_gguf_tokens(path: Path, sequences: list[list[int]]) -> list[str]:
    """Decodifica byte-BPE GPT-2 dal vocabolario GGUF senza caricare i pesi."""
    from gguf import GGUFReader

    if not 1 <= len(sequences) <= 32 or any(len(x) > 512 for x in sequences):
        raise ValueError("Sequenze fuori budget")
    ids = {t for sequence in sequences for t in sequence}
    if any(type(t) is not int or t < 0 for t in ids):
        raise ValueError("Token non valido")
    reader = GGUFReader(str(path), mode="r")
    try:
        kind = reader.fields["tokenizer.ggml.model"]
        if bytes(kind.parts[kind.data[0]]).decode("utf-8") != "gpt2":
            raise ValueError("La decodifica richiede un vocabolario byte-BPE GPT-2")
        field = reader.fields["tokenizer.ggml.tokens"]
        if ids and max(ids) >= len(field.data):
            raise ValueError("Token fuori vocabolario")
        byte_values = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
        characters = byte_values.copy()
        next_codepoint = 256
        for value in range(256):
            if value not in byte_values:
                byte_values.append(value)
                characters.append(next_codepoint)
                next_codepoint += 1
        decoder = {chr(char): byte for byte, char in zip(byte_values, characters)}
        pieces = {}
        total = 0
        for token in ids:
            raw = bytes(field.parts[field.data[token]])
            total += len(raw)
            if total > 16*2**20:
                raise ValueError("Vocabolario richiesto fuori budget")
            pieces[token] = bytes(decoder[char] for char in raw.decode("utf-8"))
        return [b"".join(pieces[t] for t in sequence).decode("utf-8", errors="replace")
                for sequence in sequences]
    finally:
        mapping = getattr(reader.data, "_mmap", None)
        if mapping is not None:
            mapping.close()


def read_token_scores(path: Path) -> list[dict]:
    """Probabilita' confrontate sull'identica storia, con KL su tutto il vocabolario."""
    import numpy as np

    dtype = np.dtype([(key, "<i4") for key in ("reference", "baseline_top", "candidate_top")]
                     + [("terminal", "<u4")]
                     + [(key, "<f8") for key in ("kl", "tv", "baseline_nll", "candidate_nll",
                         "baseline_eog_probability", "candidate_eog_probability",
                         "baseline_eog_margin", "candidate_eog_margin")])
    path = Path(path)
    if not 12 <= path.stat().st_size <= 1024*1024:
        raise ValueError("File di probabilita' fuori budget")
    with path.open("rb") as stream:
        def exact(size):
            value = stream.read(size)
            if len(value) != size:
                raise ValueError("Misure probabilistiche troncate")
            return value

        if exact(8) != b"SGAS0001":
            raise ValueError("Protocollo probabilistico non valido")
        count = struct.unpack("<I", exact(4))[0]
        if not 1 <= count <= 16:
            raise ValueError("Numero di casi fuori budget")
        cases = []
        for _ in range(count):
            n = struct.unpack("<I", exact(4))[0]
            if not 1 <= n <= 512:
                raise ValueError("Numero di posizioni fuori budget")
            rows = np.frombuffer(exact(n*dtype.itemsize), dtype=dtype).copy()
            candidate_calls, baseline_calls, seconds = struct.unpack("<IId", exact(16))
            if (not 1 <= candidate_calls <= 2**18 or not 1 <= baseline_calls <= 2**18
                    or not np.isfinite(seconds) or not 0 < seconds <= 1000
                    or any(np.any(rows[key] < 0) for key in dtype.names[:3])
                    or np.any(rows["terminal"][:-1]) or rows["terminal"][-1] != 1
                    or any(not np.isfinite(rows[key]).all() for key in dtype.names[4:])
                    or np.any(rows["kl"] < -1e-10) or np.any(rows["tv"] < 0)
                    or np.any(rows["tv"] > 1+1e-10)
                    or any(np.any(rows[key] < -1e-8) for key in ("baseline_nll", "candidate_nll"))
                    or any(np.any((rows[key] < 0) | (rows[key] > 1+1e-10))
                           for key in ("baseline_eog_probability", "candidate_eog_probability"))):
                raise ValueError("Misure probabilistiche non valide")
            cases.append({"rows": rows, "candidate_calls": candidate_calls,
                          "baseline_calls": baseline_calls, "seconds": seconds})
        if stream.read(1):
            raise ValueError("Dati in eccesso nelle misure probabilistiche")
        return cases


def summarize_token_scores(cases: list[dict], *, reference_kind="original") -> dict:
    """Le medie pesano i casi allo stesso modo; i riferimenti misurano fedelta'."""
    import numpy as np

    if not 1 <= len(cases) <= 16 or reference_kind not in ("original", "verified"):
        raise ValueError("Numero di casi fuori budget")
    per_case = []
    for case in cases:
        rows = case["rows"]
        last = rows[-1]
        per_case.append({
            "positions": len(rows), "kl_mean": float(rows["kl"].mean()),
            "kl_p95": float(np.quantile(rows["kl"], .95)),
            "tv_mean": float(rows["tv"].mean()),
            "argmax_agreement": float(np.mean(rows["baseline_top"] == rows["candidate_top"])),
            "baseline_reference_agreement": float(np.mean(rows["baseline_top"] == rows["reference"])),
            "reference_nll_delta_mean": float((rows["candidate_nll"]-rows["baseline_nll"]).mean()),
            "terminal_kl": float(last["kl"]),
            "terminal_baseline_eog_probability": float(last["baseline_eog_probability"]),
            "terminal_candidate_eog_probability": float(last["candidate_eog_probability"]),
            "terminal_baseline_eog_margin": float(last["baseline_eog_margin"]),
            "terminal_candidate_eog_margin": float(last["candidate_eog_margin"]),
            "terminal_stop_lost": bool(last["baseline_eog_margin"] >= 0 and last["candidate_eog_margin"] < 0),
        })
    return {"cases": len(cases), "positions": sum(x["positions"] for x in per_case),
            "equal_case_mean_kl": float(np.mean([x["kl_mean"] for x in per_case])),
            "equal_case_argmax_agreement": float(np.mean([x["argmax_agreement"] for x in per_case])),
            "terminal_stop_lost_count": sum(x["terminal_stop_lost"] for x in per_case),
            "per_case": per_case,
            "scope": ("conditional fidelity to original completions; identical histories; not task accuracy or free-generation termination"
                      if reference_kind == "original" else
                      "conditional scores on verified reference continuations; identical histories; correctness requires execution")}
