"""Logging centralizzato: console + file, con un run-dir per ogni esecuzione."""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

_LOGGER_NAME = "gradus"
_FMT = "%(asctime)s | %(levelname)-7s | %(message)s"
_DATEFMT = "%H:%M:%S"

# La GUI mette questo a True: i log gradus vanno solo al suo pannello (niente
# StreamHandler su stdout) per evitare righe duplicate.
SUPPRESS_CONSOLE = False


def new_run_dir(base: str | Path = "runs", tag: str | None = None) -> Path:
    """Crea e ritorna una cartella runs/<timestamp>[-tag]."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{tag}" if tag else stamp
    run_dir = Path(base) / name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def get_logger(run_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Logger 'gradus' con handler console (sempre) e file (se run_dir dato).

    Idempotente: chiamarlo più volte non duplica gli handler console.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    if not has_console and not SUPPRESS_CONSOLE:
        try:  # console Windows: evita UnicodeEncodeError (cp1252)
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setFormatter(logging.Formatter(_FMT, _DATEFMT))
        logger.addHandler(ch)

    if run_dir is not None:
        log_path = Path(run_dir) / "gradus.log"
        already = any(
            isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path.resolve()
            for h in logger.handlers
        )
        if not already:
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(logging.Formatter(_FMT, _DATEFMT))
            logger.addHandler(fh)
            logger.info("Log file: %s", log_path)

    return logger


def section(logger: logging.Logger, title: str) -> None:
    """Stampa un separatore visivo per fasi della pipeline."""
    bar = "-" * max(8, 60 - len(title))
    logger.info("== %s %s", title, bar)
