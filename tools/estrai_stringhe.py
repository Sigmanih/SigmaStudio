#!/usr/bin/env python3
"""Estrae le stringhe visibili all'utente dai file .jsx e produce un catalogo JSON."""
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

ATTRIBUTI_VISIBILI = {"title", "placeholder", "aria-label", "label", "alt"}
ATTRIBUTI_ESCLUSI = {"className", "style", "key", "id", "type", "href", "src"}


def _chiave_stabile(testo: str) -> str:
    """Deriva una chiave stabile dal testo stesso (hash SHA-256, primi 12 hex)."""
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:12]


def _e_visibile(testo: str) -> bool:
    """True se il testo e una stringa visibile all'utente."""
    t = testo.strip()
    if not t:
        return False
    # Una sola parola, tutta minuscole o maiuscole, senza spazi: identificatore
    if re.fullmatch(r"[a-zA-Z_]+", t):
        return False
    # Percorsi di file o import
    if t.startswith(("./", "../", "/", "@")) or ".js" in t or ".jsx" in t:
        return False
    # Contiene solo caratteri tipici di classi CSS (minuscole, trattini, numeri)
    if re.fullmatch(r"[a-z0-9\-_ ]+", t) and " " not in t:
        return False
    # Codice JSX/JS: parentesi, frecce, operatori, virgole, punti, backtick
    if re.search(r"[{}()=;<>]|=>|\bconst\b|\breturn\b|\bimport\b", t):
        return False
    # Frasi che iniziano con un operatore o un simbolo di codice
    if re.match(r"^[)\s]*[?:]", t) or t.startswith((") :", ") :", "0 &&", "0 ?")):
        return False
    # Contiene newline: e' codice, non testo visibile
    if "\n" in t:
        return False
    return True


def _estratti_dal_file(testo: str) -> list[str]:
    """Estrae le stringhe visibili da un singolo file .jsx."""
    risultati: list[str] = []

    # 1. Testo tra due tag JSX: <tag>testo</tag>
    for m in re.finditer(r">([^<{}]+)<", testo):
        s = m.group(1).strip()
        if s and _e_visibile(s):
            risultati.append(s)

    # 2. Attributi visibili: title="...", placeholder="...", aria-label="...", label="...", alt="..."
    for attr in ATTRIBUTI_VISIBILI:
        for m in re.finditer(rf'{attr}=["\']([^"\']+)["\']', testo):
            s = m.group(1).strip()
            if s and _e_visibile(s):
                risultati.append(s)

    # 2b. Attributi con apostrofo interno: placeholder="Inserisci l'indirizzo"
    for attr in ATTRIBUTI_VISIBILI:
        for m in re.finditer(rf'{attr}="([^"]+)"', testo):
            s = m.group(1).strip()
            if s and _e_visibile(s) and s not in risultati:
                risultati.append(s)

    # 3. alert("...") e confirm("...")
    for m in re.finditer(r'(?:alert|confirm)\(["\']([^"\']+)["\']\)', testo):
        s = m.group(1).strip()
        if s and _e_visibile(s):
            risultati.append(s)

    return risultati


def costruisci_catalogo(cartella: Path) -> dict[str, str]:
    """Scandaglia i .jsx sotto cartella e ritorna {chiave: testo}."""
    catalogo: dict[str, str] = {}
    for p in sorted(cartella.rglob("*.jsx")):
        if not p.is_file():
            continue
        try:
            contenuto = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for s in _estratti_dal_file(contenuto):
            catalogo[_chiave_stabile(s)] = s
    return catalogo


def _autotest() -> int:
    """Crea un .jsx di prova, estrae, verifica e stampa SIGMA-CHECK."""
    problemi = 0
    controllati = 0

    jsx_prova = '''import React from "react";
import { useState } from "react";

export default function Demo() {
  const [msg, setMsg] = useState("");
  return (
    <div className="flex center">
      <span>Connetti al peer</span>
      <input placeholder="Inserisci l'indirizzo" title="Indirizzo del peer" />
      <button aria-label="Chiudi la finestra" onClick={() => alert("Operazione completata")}>OK</button>
      <img alt="Logo del progetto" src="/logo.png" />
      <p className="text-small">flex</p>
    </div>
  );
}
'''

    con_visibili = ["Connetti al peer", "Inserisci l'indirizzo", "Indirizzo del peer"]
    con_non_visibili = ["flex center", "react", "flex"]

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "Demo.jsx"
        p.write_text(jsx_prova, encoding="utf-8")

        cat1 = costruisci_catalogo(Path(tmp))
        cat2 = costruisci_catalogo(Path(tmp))

    # 3. Le tre stringhe visibili devono essere nel catalogo
    for s in con_visibili:
        controllati += 1
        if s not in cat1.values():
            problemi += 1
            print(f"MANCA: {s!r}", file=sys.stderr)

    # 3b. Le tre non-visibili NON devono essere nel catalogo
    for s in con_non_visibili:
        controllati += 1
        if s in cat1.values():
            problemi += 1
            print(f"NON DOVREBBE ESSERE: {s!r}", file=sys.stderr)

    # 4. Stabilita: due esecuzioni -> stesse chiavi
    controllati += 1
    if set(cat1.keys()) != set(cat2.keys()):
        problemi += 1
        print("CHIAVI DIVERSE tra le due esecuzioni", file=sys.stderr)

    print(f'SIGMA-CHECK {{"check": "estrai-stringhe", "checked": {controllati}, "problems": {problemi}}}')
    return 0 if problemi == 0 else 1


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    if sys.argv[1] == "--autotest":
        sys.exit(_autotest())

    cartella = Path(sys.argv[1])
    if not cartella.is_dir():
        print(f"Cartella non trovata: {cartella}", file=sys.stderr)
        sys.exit(2)

    catalogo = costruisci_catalogo(cartella)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(catalogo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
