# ==============================================================================
# core/engine/mlx_weights.py — I pesi MLX a 4 bit, riportati a 16
#
# MLX salva i modelli quantizzati in affine: ogni uint32 impacchetta otto nibble
# e accanto al peso stanno due tensori, `scales` e `biases`, che coprono un
# gruppo di 64 pesi. convert_hf_to_gguf.py non conosce quel formato -- mappa i
# tensori di Hugging Face uno per uno, e `lm_head.biases` non e' nella mappa --
# quindi un `...-MLX` scaricato da Hugging Face muore con "Can not map tensor"
# pur dichiarando `model_type: llama`.
#
# Qui quei pesi si rileggono e si riscrivono in un checkpoint Hugging Face
# normale, in bf16, che il convertitore sa leggere. Lettura e scrittura sono
# fatte a mano, in numpy: `safetensors` non legge il bf16 senza ml_dtypes (che
# qui non e' installato), e il formato e' un header JSON seguito dai byte.
#
# La fedelta' ha un tetto dichiarato: il GGUF nasce da pesi che erano a 4 bit,
# quindi non puo' essere migliore del checkpoint di partenza. Per la massima
# qualita' serve la variante bf16 dello stesso modello, quando esiste.
# ==============================================================================
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from core.logger import get_logger

log = get_logger(__name__)

#: safetensors -> numpy. Il BF16 resta uint16: numpy non ha un tipo a 16 bit con
#: l'esponente dell'float32, e la conversione e' uno shift, poco piu' sotto.
_DTYPE_NUMPY: Dict[str, Any] = {
    "F64": np.float64, "I64": np.int64, "U64": np.uint64,
    "F32": np.float32, "I32": np.int32, "U32": np.uint32,
    "F16": np.float16, "BF16": np.uint16, "I16": np.int16, "U16": np.uint16,
    "I8": np.int8, "U8": np.uint8, "BOOL": np.bool_,
}

#: Byte per elemento, per calcolare gli offset del file che scriviamo.
_DTYPE_BYTE = {
    "F64": 8, "I64": 8, "U64": 8, "F32": 4, "I32": 4, "U32": 4,
    "F16": 2, "BF16": 2, "I16": 2, "U16": 2, "I8": 1, "U8": 1, "BOOL": 1,
}

#: Il checkpoint non e' solo pesi: senza questi il convertitore non ricostruisce
#: ne' il vocabolario ne' la chat template, e il GGUF esce muto.
_ACCESSORI = (
    "config.json", "generation_config.json", "tokenizer.json",
    "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json",
    "vocab.json", "merges.txt", "tokenizer.model", "chat_template.jinja",
)

#: I modi di quantizzazione di MLX che questo modulo sa disfare. Gli altri
#: (mxfp4, mxfp8, nvfp4) usano scale a 8 bit con un layout diverso: si
#: riconoscono e si rifiutano, invece di produrre pesi sbagliati.
_MODI_DECODIFICABILI = ("affine",)

#: Picco di memoria per blocco: si dequantizza a righe, non tutto insieme. Un
#: modello grande ha tensori da gigabyte, e una conversione che esaurisce la RAM
#: muore a meta' strada.
_BLOCCO_BYTE = 256 * 2**20


def _leggi_header(path: Path) -> Optional[Tuple[Dict[str, Any], int]]:
    """Header JSON di un safetensors e dove iniziano i dati (8 + lunghezza)."""
    try:
        with open(path, "rb") as f:
            grezzo = f.read(8)
            if len(grezzo) < 8:
                return None
            lunghezza = struct.unpack("<Q", grezzo)[0]
            if lunghezza <= 0 or lunghezza > 200 * 1024 * 1024:
                return None
            header = json.loads(f.read(lunghezza).decode("utf-8"))
        return header, 8 + lunghezza
    except Exception as exc:
        log.debug("[MlxWeights] Header illeggibile per %s: %s", path, exc)
        return None


def _vista(mappa, base: int, info: Dict[str, Any], dtype) -> np.ndarray:
    """Una vista sui byte del file: nessuna copia finche' non la si legge."""
    inizio, fine = info["data_offsets"]
    piatto = np.frombuffer(mappa[base + inizio: base + fine], dtype=dtype)
    return piatto.reshape(tuple(int(d) for d in info["shape"]))


def _bf16_a_f32(u16: np.ndarray) -> np.ndarray:
    """BF16 -> F32: sono i suoi primi 16 bit, quindi basta uno shift."""
    u = np.ascontiguousarray(u16, dtype=np.uint16).astype(np.uint32)
    return (u << np.uint32(16)).view(np.float32)


def _a_bf16(f32: np.ndarray) -> np.ndarray:
    """F32 -> BF16 arrotondando al pari piu' vicino.

    L'originale era bf16: questo passaggio non aggiunge errore, toglie il
    rumore del float32 che la dequantizzazione ha richiesto.
    """
    u = np.ascontiguousarray(f32, dtype=np.float32).view(np.uint32).copy()
    pari = (u >> np.uint32(16)) & np.uint32(1)
    u += np.uint32(0x7FFF) + pari
    return (u >> np.uint32(16)).astype(np.uint16)


def _leggi_config(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            dato = json.load(f)
        return dato if isinstance(dato, dict) else {}
    except Exception:
        return {}


def _mappa_tensori(cartella: Path) -> Dict[str, Tuple[str, Dict[str, Any]]]:
    """tensore -> (file, voce d'header). L'index decide, quando c'e'."""
    mappa: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    indice = cartella / "model.safetensors.index.json"
    file_shard: List[str] = []
    if indice.exists():
        try:
            with open(indice, "r", encoding="utf-8") as f:
                peso_map = json.load(f).get("weight_map", {})
            for nome, shard in peso_map.items():
                if (cartella / shard).exists():
                    mappa[str(nome)] = (str(shard), {})
            file_shard = sorted({shard for shard, _i in mappa.values()})
        except Exception as exc:
            log.warning("[MlxWeights] Index illeggibile in %s: %s", cartella, exc)
            mappa = {}
    if not mappa:
        file_shard = sorted(p.name for p in cartella.glob("*.safetensors"))

    for shard in file_shard:
        letto = _leggi_header(cartella / shard)
        if not letto:
            continue
        header, _base = letto
        for nome, info in header.items():
            if nome == "__metadata__" or not isinstance(info, dict):
                continue
            if not info.get("shape"):
                continue
            mappa[nome] = (shard, info)
    return mappa


def quantizzazione_mlx(path: str) -> Optional[Dict[str, Any]]:
    """Com'e' quantizzato questo checkpoint MLX, o None se non lo e'.

    Non basta il config: un `quantization_config` in stile bitsandbytes e' un'
    altra cosa. La prova sono i tensori -- un `*.weight` uint32 con accanto il
    suo `*.scales` -- perche' e' quello su cui il convertitore inciampa.
    """
    cartella = Path(str(path))
    if not cartella.is_dir():
        return None
    if any(cartella.glob("*.gguf")):
        return None

    mappa = _mappa_tensori(cartella)
    if not mappa:
        return None
    impacchettati: List[str] = []
    for nome, (_shard, info) in mappa.items():
        if not nome.endswith(".weight") or info.get("dtype") != "U32":
            continue
        base = nome[: -len(".weight")]
        if base + ".scales" in mappa and base + ".biases" in mappa:
            impacchettati.append(nome)
    if not impacchettati:
        return None

    cfg = _leggi_config(cartella / "config.json")
    quant = cfg.get("quantization")
    sorgente = "config"
    if not isinstance(quant, dict):
        quant = cfg.get("quantization_config")
    if not isinstance(quant, dict):
        quant = {}
        sorgente = "tensori"
    modo = str(quant.get("mode") or "affine")
    bits = int(quant.get("bits") or 0) or 4
    gruppo = int(quant.get("group_size") or 0) or 64

    esempio = mappa[impacchettati[0]][1]["shape"]
    valori = (32 // bits) if (bits > 0 and 32 % bits == 0) else 8
    in_dim = int(esempio[-1]) * valori

    problemi: List[str] = []
    if modo not in _MODI_DECODIFICABILI:
        problemi.append("modalita' MLX non supportata: " + modo)
    if bits <= 0 or 32 % bits:
        problemi.append("larghezza in bit non gestibile: " + str(bits))
    if gruppo <= 0 or in_dim % gruppo:
        problemi.append("gruppo " + str(gruppo) + " non divide la riga " + str(in_dim))
    else:
        # Il config puo' dichiarare un gruppo che non e' quello dei pesi: la
        # prova sta nel file, e la dequantizzazione non deve partire a vuoto.
        base = impacchettati[0][: -len(".weight")]
        forma_scale = mappa[base + ".scales"][1].get("shape") or []
        if forma_scale and int(forma_scale[-1]) != in_dim // gruppo:
            problemi.append(
                "il config dichiara gruppi di " + str(gruppo) + ", ma le scale ne hanno "
                + str(int(forma_scale[-1])) + " per una riga di " + str(in_dim)
            )
    return {
        "mode": modo,
        "bits": bits,
        "group_size": gruppo,
        "tensori_quantizzati": len(impacchettati),
        "sorgente": sorgente,
        "dequantizzabile": not problemi,
        "motivo": "; ".join(problemi) if problemi else None,
    }


def e_quantizzato_mlx(path: str) -> bool:
    """Vero se questo checkpoint e' un MLX che sappiamo riportare a 16 bit."""
    info = quantizzazione_mlx(path)
    return bool(info and info["dequantizzabile"])


def basi_quantizzate(path: str) -> Dict[str, int]:
    """I pesi compressi del checkpoint, come `modulo -> pesi per elemento`.

    Il numero dice quanti pesi veri stanno in un elemento del file: un 4 bit ne
    impacchetta otto in un uint32. Serve a chi conta i parametri del modello
    (che sono i pesi, non le scale) e a chi salta `scales`/`biases`, che sono
    l'impalcatura della compressione e non pesi.
    """
    info = quantizzazione_mlx(path)
    if not info:
        return {}
    mappa = _mappa_tensori(Path(str(path)))
    if not mappa:
        return {}
    fattore = 32 // int(info["bits"])
    basi: Dict[str, int] = {}
    for nome, (_shard, voce) in mappa.items():
        if not nome.endswith(".weight") or voce.get("dtype") != "U32":
            continue
        base = nome[: -len(".weight")]
        if base + ".scales" in mappa and base + ".biases" in mappa:
            basi[base] = fattore
    return basi


def parametri_logici(path: str) -> Optional[int]:
    """Quanti parametri ha il modello, non quanti numeri ha il file.

    Un 4-bit impacchetta otto pesi in un uint32 e accanto tiene scale e offset:
    contare gli elementi del file dice un ottavo del vero, e chi pianifica disco
    e VRAM su quel numero sbaglia di quasi sette volte.
    """
    if not quantizzazione_mlx(path):
        return None
    basi = basi_quantizzate(path)
    mappa = _mappa_tensori(Path(str(path)))
    if not mappa:
        return None
    totale = 0
    for nome, (_shard, voce) in mappa.items():
        coda = nome[: nome.rfind(".")] if "." in nome else nome
        fattore = basi.get(coda)
        if fattore and not nome.endswith(".weight"):
            continue        # scale e offset: non sono parametri del modello
        numel = 1
        for dim in voce.get("shape") or []:
            numel *= int(dim)
        if fattore and nome.endswith(".weight"):
            numel *= fattore
        totale += numel
    return totale or None


def _blocco_dequantizzato(packed: np.ndarray, scales: np.ndarray,
                          biases: np.ndarray, bits: int,
                          gruppo: int) -> np.ndarray:
    """Un blocco di righe torna ai suoi pesi: w * scale + offset.

    E' la formula dell'affine di MLX, e l'ordine dei nibble e' quello dei suoi
    kernel: il valore k-esimo di un uint32 sta nei bit `bits * k`, partendo dai
    piu' bassi (`>> 4`, `>> 8`, `>> 12` nel kernel a 4 bit).
    """
    valori = 32 // bits
    righe, colonne = packed.shape
    in_dim = colonne * valori
    if in_dim % gruppo:
        raise ValueError("la riga " + str(in_dim) + " non e' multipla del gruppo " + str(gruppo))
    if scales.shape[-1] != in_dim // gruppo:
        raise ValueError(
            "scale di forma " + str(tuple(scales.shape)) + " per una riga "
            + str(in_dim) + " a gruppi di " + str(gruppo)
        )
    maschera = np.uint32((1 << bits) - 1)
    u = np.empty((righe, colonne, valori), dtype=np.uint8)
    for k in range(valori):
        u[..., k] = (packed >> np.uint32(bits * k)) & maschera
    pesi = u.reshape(righe, in_dim).reshape(righe, -1, gruppo).astype(np.float32)
    pesi *= np.asarray(scales, dtype=np.float32)[:, :, None]
    pesi += np.asarray(biases, dtype=np.float32)[:, :, None]
    return pesi.reshape(righe, in_dim)


def _righe_per_blocco(in_dim: int) -> int:
    """Quante righe si dequantizzano insieme: memoria limitata, non tempo."""
    return max(1, _BLOCCO_BYTE // max(1, in_dim * 10))


def _voci_di_uscita(cartella: Path, mappa: Dict[str, Tuple[str, Dict[str, Any]]],
                    bits: int, compatto: str, byte_out: int):
    """Cosa scrivere nel checkpoint nuovo: (nome, shard, voce, tipo, forma, dtype).

    I `*.scales` e i `*.biases` spariscono -- sono il modo in cui i pesi erano
    compressi, non pesi -- e i loro `*.weight` escono dequantizzati. Tutto il
    resto si copia com'e', comprese le norme in bf16 che MLX non tocca.
    """
    valori = 32 // bits
    quantizzati = {n[: -len(".weight")] for n, (_s, i) in mappa.items()
                   if n.endswith(".weight") and i.get("dtype") == "U32"}
    voci = []
    for nome in sorted(mappa):
        shard, voce = mappa[nome]
        coda = nome[: nome.rfind(".")] if "." in nome else nome
        if coda in quantizzati and not nome.endswith(".weight"):
            continue                     # scale o offset, non un peso
        forma = [int(d) for d in voce["shape"]]
        if nome.endswith(".weight") and coda in quantizzati:
            if len(forma) == 1:
                forma_out = [forma[0] * valori]
            else:
                forma_out = forma[:-1] + [forma[-1] * valori]
            voci.append((nome, shard, voce, "dequant", forma_out, compatto))
        else:
            voci.append((nome, shard, voce, "copia", forma, str(voce["dtype"])))
    return voci


def _allinea(pos: int, byte: int) -> int:
    """Il prossimo tensore inizia su un confine di 8 byte, come vuole il formato."""
    resto = pos % 8
    return pos if not resto else pos + (8 - resto)


def _copia_accessori(origine: Path, destinazione: Path) -> List[str]:
    """Config e tokenizer: al convertitore servono quanto i pesi.

    Il `config.json` si riscrive senza il blocco della quantizzazione: i pesi
    che gli stanno accanto adesso sono a 16 bit, e un config che dichiara 4 bit
    mente a chiunque lo legga dopo.
    """
    copiati: List[str] = []
    for nome in _ACCESSORI:
        sorgente = origine / nome
        if not sorgente.is_file():
            continue
        if nome == "config.json":
            cfg = _leggi_config(sorgente)
            if not cfg:
                continue
            cfg.pop("quantization", None)
            qc = cfg.get("quantization_config")
            if isinstance(qc, dict) and str(qc.get("mode") or "affine") in _MODI_DECODIFICABILI:
                cfg.pop("quantization_config", None)
            with open(destinazione / nome, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            copiati.append(nome)
            continue
        shutil.copy2(sorgente, destinazione / nome)
        copiati.append(nome)
    return copiati


def _a_f32(t: np.ndarray, dtype: str) -> np.ndarray:
    """Scale e offset di MLX sono bf16; il conto si fa in float32."""
    if dtype == "BF16":
        return _bf16_a_f32(t)
    return np.asarray(t, dtype=np.float32)


def dequantizza_verso_hf(source: str, dest: str, *, dtype: str = "bf16",
                         on_progress: Optional[Callable[[int, int], None]] = None
                         ) -> Dict[str, Any]:
    """Riscrive un checkpoint MLX quantizzato come checkpoint Hugging Face.

    Un file solo, in bf16 (o f32 su richiesta), con i pesi riportati a 16 bit e
    gli accessori copiati: da li' in poi e' un modello come gli altri, e
    convert_hf_to_gguf.py non ha piu' niente da ridire.
    """
    info = quantizzazione_mlx(source)
    if not info:
        raise ValueError(
            "Non e' un checkpoint quantizzato MLX: " + str(source)
        )
    if not info["dequantizzabile"]:
        raise ValueError(
            "Quantizzazione MLX non supportata (" + str(info["motivo"]) + "): " + str(source)
        )
    cartella = Path(str(source))
    destinazione = Path(str(dest))
    destinazione.mkdir(parents=True, exist_ok=True)

    mappa = _mappa_tensori(cartella)
    if not mappa:
        raise ValueError("Nessun tensore leggibile in " + str(source))

    bits = int(info["bits"])
    gruppo = int(info["group_size"])
    compatto = "BF16" if str(dtype).lower() in ("bf16", "bfloat16") else "F32"
    byte_out = 2 if compatto == "BF16" else 4
    voci = _voci_di_uscita(cartella, mappa, bits, compatto, byte_out)

    # Gli offset si calcolano tutti prima: l'header li dichiara, e i dati
    # vengono scritti nella stessa sequenza.
    posizione = 0
    file_voci = []
    for nome, shard, voce, tipo, forma, dtype_out in voci:
        numel = 1
        for dim in forma:
            numel *= int(dim)
        byte = numel * _DTYPE_BYTE[dtype_out]
        inizio = _allinea(posizione, 8)
        file_voci.append((nome, shard, voce, tipo, forma, dtype_out, inizio, byte))
        posizione = inizio + byte

    header: Dict[str, Any] = {"__metadata__": {"format": "pt"}}
    for nome, _s, _v, _t, forma, dtype_out, inizio, byte in file_voci:
        header[nome] = {"dtype": dtype_out, "shape": forma,
                        "data_offsets": [inizio, inizio + byte]}
    blob = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    blob += b" " * ((8 - len(blob) % 8) % 8)

    file_out = destinazione / "model.safetensors"
    aperti: Dict[str, Tuple[Any, int]] = {}
    dequantizzati = 0
    copiati = 0
    scritti = 0
    try:
        with open(file_out, "wb") as f:
            f.write(struct.pack("<Q", len(blob)))
            f.write(blob)
            for i, (nome, shard, voce, tipo, forma, dtype_out, inizio, byte) in enumerate(file_voci):
                if scritti < inizio:
                    f.write(b"\0" * (inizio - scritti))
                    scritti = inizio
                if shard not in aperti:
                    percorso = cartella / shard
                    letto = _leggi_header(percorso)
                    if not letto:
                        raise RuntimeError("Header illeggibile in " + str(percorso))
                    _h, base_shard = letto
                    aperti[shard] = (np.memmap(percorso, dtype=np.uint8, mode="r"), base_shard)
                mm, base_shard = aperti[shard]

                if tipo == "copia":
                    dati = _vista(mm, base_shard, voce, _DTYPE_NUMPY[str(voce["dtype"])])
                    f.write(np.ascontiguousarray(dati).tobytes())
                    copiati += 1
                else:
                    coda = nome[: nome.rfind(".")]
                    packed = _vista(mm, base_shard, voce, np.uint32)
                    s_info = mappa[coda + ".scales"][1]
                    b_info = mappa[coda + ".biases"][1]
                    s_shard = mappa[coda + ".scales"][0]
                    b_shard = mappa[coda + ".biases"][0]
                    if s_shard not in aperti:
                        letto = _leggi_header(cartella / s_shard)
                        if not letto:
                            raise RuntimeError("Header illeggibile in " + str(cartella / s_shard))
                        aperti[s_shard] = (
                            np.memmap(cartella / s_shard, dtype=np.uint8, mode="r"), letto[1])
                    if b_shard not in aperti:
                        letto = _leggi_header(cartella / b_shard)
                        if not letto:
                            raise RuntimeError("Header illeggibile in " + str(cartella / b_shard))
                        aperti[b_shard] = (
                            np.memmap(cartella / b_shard, dtype=np.uint8, mode="r"), letto[1])
                    scales = _vista(aperti[s_shard][0], aperti[s_shard][1], s_info,
                                    _DTYPE_NUMPY[str(s_info["dtype"])])
                    biases = _vista(aperti[b_shard][0], aperti[b_shard][1], b_info,
                                    _DTYPE_NUMPY[str(b_info["dtype"])])
                    s_dtype = str(s_info["dtype"])
                    b_dtype = str(b_info["dtype"])

                    vettore = packed.ndim == 1
                    p2 = packed.reshape(1, -1) if vettore else packed
                    s2 = scales.reshape(1, -1) if scales.ndim == 1 else scales
                    b2 = biases.reshape(1, -1) if biases.ndim == 1 else biases
                    righe = int(p2.shape[0])
                    in_dim = int(p2.shape[-1]) * (32 // bits)
                    passo = _righe_per_blocco(in_dim)
                    for r0 in range(0, righe, passo):
                        r1 = min(righe, r0 + passo)
                        pesi = _blocco_dequantizzato(
                            np.ascontiguousarray(p2[r0:r1]),
                            _a_f32(np.ascontiguousarray(s2[r0:r1]), s_dtype),
                            _a_f32(np.ascontiguousarray(b2[r0:r1]), b_dtype),
                            bits, gruppo,
                        )
                        if vettore:
                            pesi = pesi.reshape(-1)
                        f.write((_a_bf16(pesi) if compatto == "BF16" else
                                 np.ascontiguousarray(pesi, dtype=np.float32)).tobytes())
                    dequantizzati += 1

                scritti += byte
                if on_progress is not None:
                    try:
                        on_progress(i + 1, len(file_voci))
                    except Exception:
                        pass
    finally:
        for mm, _base in aperti.values():
            try:
                mm._mmap.close()
            except Exception:
                pass

    if scritti != posizione:
        raise RuntimeError(
            "Checkpoint incompleto: scritti " + str(scritti) + " byte su " + str(posizione)
        )

    accessori = _copia_accessori(cartella, destinazione)
    riepilogo = {
        "dest": str(file_out),
        "accessori": accessori,
        "tensori": len(file_voci),
        "dequantizzati": dequantizzati,
        "copiati": copiati,
        "byte": scritti,
        "dtype": compatto,
        "bits": bits,
        "group_size": gruppo,
    }
    log.info(
        "[MlxWeights] %s: %d tensori (%d dequantizzati) in %s, %.2f GB",
        cartella.name, riepilogo["tensori"], dequantizzati, file_out,
        scritti / 2**30,
    )
    return riepilogo
