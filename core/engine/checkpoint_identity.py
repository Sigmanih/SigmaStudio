"""Identita' del checkpoint su disco, distinta dal nome pubblico del modello."""

import hashlib
from pathlib import Path
from time import monotonic

from core.logger import get_logger

log = get_logger(__name__)


def fingerprint_file(path: Path, *, seconds=60, max_bytes=64*2**30) -> dict:
    """Non usa cache: lo stesso nome puo' contenere pesi diversi tra due prove."""
    path = Path(path)
    if not 0 < seconds <= 180 or not 1 <= max_bytes <= 256*2**30:
        raise ValueError('Budget di identificazione non valido')
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= max_bytes:
        raise ValueError('Checkpoint assente o oltre il budget')
    deadline = monotonic()+seconds
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            if monotonic() > deadline:
                raise TimeoutError('Tempo di identificazione del checkpoint esaurito')
            chunk = stream.read(8*2**20)
            if not chunk:
                break
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('Checkpoint cambiato durante la lettura')
    return {'verified': True, 'sha256': digest.hexdigest(), 'bytes': after.st_size,
            'format': 'gguf', 'scope': 'single_file_on_disk'}


def current_checkpoint_identity(engine) -> dict:
    """Certifica solo il caso non ambiguo; i backend remoti restano non verificati."""
    try:
        from core.model_paths import resolve_model_dir

        if not engine.has_resident_model or not engine.loaded_model_name:
            return {'verified': False, 'reason': 'Nessun checkpoint residente'}
        folder = resolve_model_dir(engine.loaded_model_name)
        if not folder:
            return {'verified': False, 'reason': 'Checkpoint locale non risolto'}
        # Piu' GGUF possono includere shard, proiettori o LoRA: non indovinarne il ruolo.
        entries = []
        for i, path in enumerate(Path(folder).iterdir()):
            if i >= 1024:
                return {'verified': False, 'reason': 'Cartella oltre il budget di lettura'}
            if path.is_dir():
                return {'verified': False, 'reason': 'Checkpoint con sottocartelle: componenti non verificati'}
            if path.is_file() and path.suffix.lower() in ('.gguf', '.safetensors', '.bin'):
                entries.append(path)
        if len(entries) != 1 or entries[0].suffix.lower() != '.gguf':
            return {'verified': False, 'reason': 'Identita composta o formato non supportato'}
        return fingerprint_file(entries[0])
    except (OSError, ValueError, TypeError, TimeoutError) as exc:
        log.warning('Identita checkpoint non verificata: %s', exc)
        return {'verified': False, 'reason': str(exc)}
