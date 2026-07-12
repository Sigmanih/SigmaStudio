# ==============================================================================
# core/logger.py — Structured Logging for Sigma Studio
# ==============================================================================
"""Centralized logging factory for all core modules.

Usage:
    from core.logger import get_logger
    log = get_logger(__name__)
    log.info("Server started on port %d", 8000)
    log.warning("Provider %s has no API key", provider)
    log.error("Failed to read file: %s", path, exc_info=True)
"""

import logging
import sys
import os

# Log level controlled via SIGMA_LOG_LEVEL env var (default: INFO)
_DEFAULT_LEVEL = os.environ.get("SIGMA_LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"
_DATE_FORMAT = "%H:%M:%S"

# Root logger for all Sigma modules — configured once
_root = logging.getLogger("sigma")
_root.propagate = False  # don't bubble up to Python root logger

if not _root.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    _root.addHandler(_handler)

try:
    _root.setLevel(getattr(logging, _DEFAULT_LEVEL))
except AttributeError:
    _root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'sigma' namespace.

    Args:
        name: Typically ``__name__`` from the calling module.
               e.g. 'core.chat_handler' → logger 'sigma.core.chat_handler'

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    # Strip redundant 'core.' prefix so names are shorter in output
    short = name.replace("core.", "", 1) if name.startswith("core.") else name
    return _root.getChild(short)
