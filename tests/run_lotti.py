"""Esegue solo i file dei lotti scelti, senza importare gli altri laboratori."""
import argparse
from pathlib import Path

import pytest

from tests.lotti import LOTTI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lotti", nargs="+", choices=tuple(LOTTI))
    options = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    files = sorted({root / f"test_{name}.py" for group in options.lotti for name in LOTTI[group]})
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        parser.error("File di prova mancanti: " + ", ".join(missing))
    return pytest.main([*(str(path) for path in files), "-q", "--tb=short"])


if __name__ == "__main__":
    raise SystemExit(main())
