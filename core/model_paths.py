# ==============================================================================
# core/model_paths.py — Come si trova un modello a partire dal suo nome
#
# Questo file e' nato per chiudere un problema di percorsi: la cartella dei
# modelli veniva derivata in cinque punti indipendenti, quattro dei quali da
# os.getcwd(). Quel problema ora e' risolto in modo generale da core/paths.py,
# che possiede tutte le radici dell'installazione.
#
# Qui resta la parte che e' davvero specifica dei modelli: riconoscere una
# cartella che contiene pesi, ed estrarre un modello dalle molte grafie con cui
# lo stesso nome circola nell'applicazione ('Qwen/Qwen3-27B', 'Qwen--Qwen3-27B',
# una cartella nuda, un percorso assoluto).
#
# Le funzioni di percorso restano esposte qui e restituiscono str, come hanno
# sempre fatto, perche' hanno una ventina di chiamanti che le compongono con
# os.path.join. Il codice nuovo chiami direttamente core.paths, che restituisce
# oggetti Path.
# ==============================================================================
import os
from typing import Optional, List

from core import paths as _paths
from core.logger import get_logger

log = get_logger(__name__)


def project_root() -> str:
    """La directory di installazione di Sigma Studio."""
    return str(_paths.project_root())


def hub_config_path() -> str:
    return str(_paths.model_hub_config_file())


def default_models_dir() -> str:
    return str(_paths.default_models_dir())


def models_dir(refresh: bool = False) -> str:
    """La cartella dei modelli attiva: quella configurata, o la predefinita."""
    return str(_paths.models_dir(refresh=refresh))


def set_models_dir(new_dir: str) -> str:
    """Punta ogni consumatore a una nuova cartella e invalida la cache."""
    return str(_paths.set_models_dir(new_dir))


def extra_models_dirs(refresh: bool = False) -> List[str]:
    """L'elenco delle cartelle modelli aggiuntive configurate."""
    return [str(p) for p in _paths.extra_models_dirs(refresh=refresh)]


def all_models_dirs(refresh: bool = False) -> List[str]:
    """Tutte le cartelle modelli attive (principale + aggiuntive)."""
    return [str(p) for p in _paths.all_models_dirs(refresh=refresh)]


def set_extra_models_dirs(dirs: List[str]) -> List[str]:
    """Aggiorna le cartelle modelli aggiuntive."""
    return [str(p) for p in _paths.set_extra_models_dirs(dirs)]


WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt")


def has_weights(path: str) -> bool:
    """Se un percorso (cartella o file) contiene davvero pesi di un modello."""
    if not path:
        return False
    if os.path.isfile(path):
        return path.lower().endswith(WEIGHT_SUFFIXES)
    if not os.path.isdir(path):
        return False
    try:
        entries = os.listdir(path)
    except OSError:
        return False
    if any(
        name.lower().endswith(WEIGHT_SUFFIXES) or name == "model.safetensors.index.json"
        for name in entries
    ):
        return True
    try:
        for _root, _dirs, files in os.walk(path):
            if any(name.lower().endswith(WEIGHT_SUFFIXES) or name == "model.safetensors.index.json" for name in files):
                return True
    except OSError:
        pass
    return False


def list_model_dirs() -> List[str]:
    """Ogni cartella o file modello presente in tutte le cartelle modelli attive."""
    results: List[str] = []
    seen = set()
    for base in all_models_dirs(refresh=True):
        if not os.path.isdir(base):
            continue
        try:
            entries = sorted(os.listdir(base))
        except OSError:
            continue
        for name in entries:
            full = os.path.join(base, name)
            if full in seen:
                continue
            if os.path.isdir(full) and has_weights(full):
                seen.add(full)
                results.append(full)
            elif os.path.isfile(full) and name.lower().endswith(WEIGHT_SUFFIXES):
                seen.add(full)
                results.append(full)
    return results


def resolve_model_dir(identifier: Optional[str]) -> Optional[str]:
    """
    Trova la cartella o file di un modello a partire da un riferimento, tollerando le
    grafie che circolano in questa applicazione: 'Qwen/Qwen3-27B',
    'Qwen--Qwen3-27B', un nome di cartella nudo, un file '.gguf', o un percorso assoluto.
    Cerca in modo dinamico in tutte le cartelle modelli configurate.
    """
    if not identifier:
        return None

    if os.path.isabs(identifier) and (has_weights(identifier) or (os.path.isfile(identifier) and identifier.lower().endswith(WEIGHT_SUFFIXES))):
        return identifier

    candidates_bases = all_models_dirs(refresh=True)

    clean_id = str(identifier).strip()
    raw_base = os.path.basename(clean_id)

    id_candidates = [
        clean_id,
        clean_id.replace("/", "--"),
        clean_id.replace("--", "/"),
        clean_id.replace(":", "-"),
        raw_base,
        clean_id.split("/")[-1],
        clean_id.split(":")[-1],
        clean_id.split(":")[0],
    ]
    if not clean_id.lower().endswith(".gguf"):
        id_candidates.extend([
            f"{clean_id}.gguf",
            f"{clean_id.replace('/', '--')}.gguf",
            f"{raw_base}.gguf",
        ])

    for base in candidates_bases:
        for candidate in id_candidates:
            path = os.path.join(base, candidate)
            if os.path.exists(path) and (has_weights(path) or (os.path.isfile(path) and path.lower().endswith(WEIGHT_SUFFIXES))):
                return path

    # Ultima risorsa: confronto ignorando i separatori, dando la precedenza alle
    # corrispondenze esatte e a quelle quantizzate GGUF.
    wanted = "".join(c for c in clean_id.lower() if c.isalnum())
    if not wanted:
        return None

    candidates = list_model_dirs()

    def _match_score(p: str) -> tuple:
        f = "".join(c for c in os.path.basename(p).lower() if c.isalnum())
        exact = 0 if f == wanted else 1
        is_sub = 0 if (wanted in f or f in wanted) else 1
        len_diff = abs(len(f) - len(wanted))
        is_quant = 0 if any(q in f for q in ("q4", "q5", "q8", "q6", "int4", "int8")) else 1
        return (is_sub, exact, len_diff, is_quant)

    ranked = sorted(candidates, key=_match_score)
    for path in ranked:
        folder = "".join(c for c in os.path.basename(path).lower() if c.isalnum())
        if wanted in folder or folder in wanted:
            return path

    return None

