# ==============================================================================
# core/modules/sigma_model_hub/backend/hf_split.py
# Divisione dei GGUF troppo grandi per il limite per file di Hugging Face.
# ==============================================================================
"""
Hugging Face rifiuta i file singoli oltre i 50 GB, e lo fa dopo che il client
ha gia' hashato l'intero file: per un modello da 188 GB sono minuti buttati e
un 422 che non dice cosa fare. Qui il controllo si fa prima di parlare con la
rete, e il rimedio -- dividere in shard -- si applica da solo.

Il rimedio non copre tutto. `llama-gguf-split` taglia fra un tensore e
l'altro, mai dentro: se un singolo tensore sfora il limite non c'e' divisione
che salvi il file, e va riquantizzato piu' compatto quel tensore. I due casi
vanno distinti, perche' il primo si risolve qui e il secondo no.
"""
from __future__ import annotations
import os
import shutil
import subprocess
from typing import Any, Dict, Optional

from core.logger import get_logger

log = get_logger(__name__)

#: Il limite di Hugging Face per singolo file. Decimale, perche' e' cosi' che
#: lo conta il server: 50 GiB passerebbero il nostro controllo e non il suo.
LIMITE_FILE_HF = 50 * 10**9

#: Taglia richiesta per ogni shard. Il margine sotto il limite copre
#: l'intestazione che ogni shard si porta dietro.
TAGLIA_SHARD = "40G"

#: Spazio da lasciare libero sul volume oltre a quello degli shard.
_MARGINE_GB = 5.0


def _binario_split() -> Optional[str]:
    """L'eseguibile di split della build del motore, se installata."""
    try:
        from core.engine import llama_runtime
        info = llama_runtime.installed_build_info() or {}
    except Exception:
        return None
    cartella = info.get("cartella")
    if not cartella:
        return None
    for nome in ("llama-gguf-split.exe", "llama-gguf-split"):
        percorso = os.path.join(cartella, nome)
        if os.path.isfile(percorso):
            return percorso
    return None


def e_uno_shard(nome: str) -> bool:
    """Se il nome e' gia' una parte di un GGUF diviso."""
    corpo = os.path.basename(nome)
    return "-of-" in corpo and corpo.lower().endswith(".gguf")


def tensore_oltre_il_limite(percorso: str) -> Optional[Dict[str, Any]]:
    """Il primo tensore che da solo sfora il limite, se ce n'e' uno.

    E' il caso che la divisione non risolve, e va detto prima di iniziare.
    """
    try:
        from gguf.gguf_reader import GGUFReader
        lettore = GGUFReader(percorso)
    except Exception as err:
        log.warning("[hf_split] Impossibile leggere i tensori di %s: %s",
                    percorso, err)
        return None
    for tensore in getattr(lettore, "tensors", []):
        try:
            byte = int(tensore.n_bytes)
        except Exception:
            continue
        if byte > LIMITE_FILE_HF:
            return {"tensore": str(tensore.name), "bytes": byte,
                    "gb": round(byte / 10**9, 2)}
    return None


def serve_dividere(percorso: str) -> bool:
    """Se questo file va diviso prima di poter essere pubblicato."""
    if not percorso.lower().endswith(".gguf") or e_uno_shard(percorso):
        return False
    try:
        return os.path.getsize(percorso) > LIMITE_FILE_HF
    except OSError:
        return False


def dividi(percorso: str, destinazione: Optional[str] = None) -> Dict[str, Any]:
    """Divide un GGUF negli shard che Hugging Face accetta.

    Restituisce i percorsi prodotti, oppure il motivo per cui non si puo'.
    Gli shard finiscono in una cartella a parte accanto all'originale, cosi'
    che ripulirli dopo il caricamento sia una sola rimozione.
    """
    if not os.path.isfile(percorso):
        return {"success": False, "error": "File non trovato: " + str(percorso)}

    grosso = tensore_oltre_il_limite(percorso)
    if grosso:
        return {
            "success": False,
            "tensore_indivisibile": grosso,
            "error": (
                "Il tensore " + grosso["tensore"] + " occupa da solo "
                + str(grosso["gb"]) + " GB, oltre il limite di "
                + str(LIMITE_FILE_HF // 10**9) + " GB per file di Hugging Face. "
                "La divisione non aiuta: gli shard si tagliano fra un tensore e "
                "l'altro, mai dentro. Riconverti il modello: il convertitore "
                "riporta da solo i tensori fuori misura a un tipo piu' compatto."
            ),
        }

    binario = _binario_split()
    if not binario:
        return {"success": False,
                "error": "llama-gguf-split non disponibile: installa la build "
                         "del motore dal Model Hub."}

    if destinazione is None:
        base = os.path.splitext(os.path.basename(percorso))[0]
        destinazione = os.path.join(os.path.dirname(percorso), base + "-shards")

    servono_gb = os.path.getsize(percorso) / 2**30 + _MARGINE_GB
    try:
        radice = os.path.dirname(destinazione) or "."
        liberi_gb = shutil.disk_usage(radice).free / 2**30
    except Exception:
        liberi_gb = servono_gb            # senza il dato non si blocca
    if liberi_gb < servono_gb:
        return {
            "success": False,
            "error": (
                "Servono circa " + str(round(servono_gb)) + " GB liberi per "
                "scrivere gli shard e ce ne sono " + str(round(liberi_gb))
                + ". Libera spazio, oppure dividi il file a mano su un altro "
                "volume e pubblica quella cartella."
            ),
        }

    os.makedirs(destinazione, exist_ok=True)
    prefisso = os.path.join(
        destinazione, os.path.splitext(os.path.basename(percorso))[0]
    )
    comando = [binario, "--split", "--split-max-size", TAGLIA_SHARD,
               percorso, prefisso]
    log.info("[hf_split] Divido %s in %s", percorso, destinazione)
    esito = subprocess.run(comando, capture_output=True, text=True,
                           errors="replace", timeout=6 * 60 * 60)
    if esito.returncode != 0:
        uscita = (esito.stderr or "") + os.linesep + (esito.stdout or "")
        coda = [r.strip() for r in uscita.splitlines() if r.strip()][-3:]
        shutil.rmtree(destinazione, ignore_errors=True)
        return {"success": False,
                "error": "llama-gguf-split ha fallito: " + " | ".join(coda)}

    prodotti = sorted(
        os.path.join(destinazione, n) for n in os.listdir(destinazione)
        if n.lower().endswith(".gguf")
    )
    if not prodotti:
        shutil.rmtree(destinazione, ignore_errors=True)
        return {"success": False,
                "error": "la divisione non ha prodotto alcuno shard"}

    fuori_misura = [os.path.basename(p) for p in prodotti
                    if os.path.getsize(p) > LIMITE_FILE_HF]
    if fuori_misura:
        shutil.rmtree(destinazione, ignore_errors=True)
        return {"success": False,
                "error": ("Anche dopo la divisione questi shard restano oltre "
                          "il limite: " + ", ".join(fuori_misura))}

    return {"success": True, "shards": prodotti, "cartella": destinazione,
            "totale_bytes": sum(os.path.getsize(p) for p in prodotti)}
