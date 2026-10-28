import re
from pathlib import Path

p = Path("docs/ekf_derivation.md")
if not p.exists():
    print("ERRORE: file non