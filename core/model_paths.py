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


WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt")


def has_weights(folder: str) -> bool:
    """Se una directory contiene davvero pesi di un modello."""
    if not os.path.isdir(folder):
        return False
    try:
        entries = os.listdir(folder)
    except OSError:
        return False
    return any(
        name.endswith(WEIGHT_SUFFIXES) or name == "model.safetensors.index.json"
        for name in entries
    )


def list_model_dirs() -> List[str]:
    """Ogni sottocartella della cartella modelli attiva che contiene pesi."""
    base = models_dir()
    if not os.path.isdir(base):
        return []
    try:
        entries = sorted(os.listdir(base))
    except OSError:
        return []
    return [
        os.path.join(base, name) for name in entries
        if has_weights(os.path.join(base, name))
    ]


def resolve_model_dir(identifier: Optional[str]) -> Optional[str]:
    """
    Trova la cartella di un modello a partire da un riferimento, tollerando le
    grafie che circolano in questa applicazione: 'Qwen/Qwen3-27B',
    'Qwen--Qwen3-27B', un nome di cartella nudo, o un percorso assoluto.
    """
    if not identifier:
        return None

    if os.path.isabs(identifier) and has_weights(identifier):
        return identifier

    base = models_dir()
    for candidate in (
        identifier,
        identifier.replace("/", "--"),
        identifier.replace("--", "/"),
        identifier.replace(":", "-"),
        identifier.split("/")[-1],
        identifier.split(":")[0],
    ):
        path = os.path.join(base, candidate)
        if has_weights(path):
            return path

    # Ultima risorsa: confronto ignorando i separatori, dando la precedenza alle
    # corrispondenze esatte e a quelle quantizzate GGUF.
    wanted = "".join(c for c in identifier.lower() if c.isalnum())
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
