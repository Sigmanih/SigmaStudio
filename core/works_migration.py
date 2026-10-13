# ==============================================================================
# core/works_migration.py — Le creazioni dei moduli traslocano da data/ a works/
# ==============================================================================
"""data/ e' lo spazio di studio; video, immagini, voci e progetti vanno in works/.

Il trasloco **copia** e non sposta: in data/ non si cancella niente (regola del
progetto), gli originali restano come copia di sicurezza e l'utente li rimuove
quando ha controllato che tutto si apre dal nuovo posto. Dopo la copia, i percorsi
salvati dentro i file copiati (JSON delle produzioni, schede dei personaggi, voci,
database degli asset) vengono riscritti verso la nuova posizione: senza questo una
produzione traslocata continuerebbe a leggere le clip dalla vecchia cartella.

Uso:  python -m core.works_migration            prova a vuoto: cosa e quanto
      python -m core.works_migration --esegui   copia e riscrive
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

from core import paths
from core.logger import get_logger

log = get_logger("works_migration")

#: (cartella storica dentro data/, destinazione relativa alla radice del progetto).
#: Solo nomi di cartelle: il kernel non sa a quale modulo appartengono.
TRASLOCHI: Tuple[Tuple[str, str], ...] = (
    ("creative", "works/creative"),
    ("characters", "works/creative/personaggi"),
    ("voices", "works/voci"),
    ("calibration", "store/calibration"),
)
# I progetti del Developer Studio (data/progetti) non traslocano da soli: contengono ambienti
# virtuali con collegamenti e percorsi assoluti, che copiati non funzionano piu'. Le installazioni
# nuove li creano gia' in works/progetti; chi li ha in data/ sceglie la radice dal Developer Studio.

#: File in cui stanno percorsi salvati da riscrivere.
TESTUALI = (".json",)
DATABASE = (".db", ".sqlite")


def _dimensione(cartella: Path) -> int:
    totale = 0
    for f in cartella.rglob("*"):
        try:
            if f.is_file():
                totale += f.stat().st_size
        except OSError:
            continue                 # collegamenti non leggibili: non contano per la stima
    return totale


def piano() -> List[Dict]:
    """Cosa traslocherebbe: sorgente, destinazione, byte, gia' fatto."""
    root = paths.project_root()
    voci = []
    for vecchio, nuovo in TRASLOCHI:
        src, dst = paths.workspace_dir() / vecchio, root / nuovo
        if not src.is_dir():
            continue
        voci.append({"da": str(src), "a": str(dst), "byte": _dimensione(src), "fatto": dst.exists()})
    return voci


def _sostituzioni() -> List[Tuple[str, str]]:
    """Coppie (vecchio, nuovo) per assoluti e relativi, con entrambi i separatori; prima le piu' lunghe."""
    root = paths.project_root().resolve()
    coppie = []
    for vecchio, nuovo in TRASLOCHI:
        abs_old, abs_new = root / "data" / vecchio, root / nuovo
        for a, b in ((str(abs_old), str(abs_new)), (abs_old.as_posix(), abs_new.as_posix()),
                     (f"data/{vecchio}", nuovo), (f"data\\{vecchio}", nuovo.replace("/", "\\"))):
            coppie.append((a, b))
    return sorted(set(coppie), key=lambda c: -len(c[0]))


def _riscrivi_testo(valore: str, coppie: List[Tuple[str, str]]) -> str:
    # Su Windows lo stesso percorso compare con maiuscole diverse ("C:\\Users" e "c:\\users"):
    # si confronta in minuscolo e si sostituisce solo il prefisso, il resto resta com'e'.
    basso = valore.lower()
    for vecchio, nuovo in coppie:
        i = basso.find(vecchio.lower())
        if i != -1:
            # Prefisso intero: "data/creative" non deve toccare "metadata/creativecommons".
            fine = i + len(vecchio)
            if (i == 0 or valore[i - 1] in "\\/:\" ") and (fine == len(valore) or valore[fine] in "\\/"):
                return valore[:i] + nuovo + valore[fine:]
    return valore


def _riscrivi_json(dato, coppie):
    if isinstance(dato, str):
        return _riscrivi_testo(dato, coppie)
    if isinstance(dato, list):
        return [_riscrivi_json(x, coppie) for x in dato]
    if isinstance(dato, dict):
        return {k: _riscrivi_json(v, coppie) for k, v in dato.items()}
    return dato


def _riscrivi_stringa_composta(testo: str, coppie) -> str:
    """Testo che contiene JSON (colonne del database): si riscrivono le stringhe al suo interno."""
    try:
        return json.dumps(_riscrivi_json(json.loads(testo), coppie), ensure_ascii=False)
    except (ValueError, TypeError):
        return _riscrivi_testo(testo, coppie)


def riscrivi_percorsi(cartella: Path) -> Dict[str, int]:
    """Riscrive i percorsi storici nei JSON e nei database sotto `cartella`."""
    coppie = _sostituzioni()
    conteggio = {"json": 0, "db_righe": 0}
    for f in cartella.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() in TESTUALI:
            try:
                prima = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            dopo = _riscrivi_json(prima, coppie)
            if dopo != prima:
                f.write_text(json.dumps(dopo, ensure_ascii=False, indent=2), encoding="utf-8")
                conteggio["json"] += 1
        elif f.suffix.lower() in DATABASE:
            conteggio["db_righe"] += _riscrivi_database(f, coppie)
    return conteggio


def _riscrivi_database(db: Path, coppie) -> int:
    cambiate = 0
    try:
        with sqlite3.connect(db) as conn:
            tabelle = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for t in tabelle:
                colonne = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
                for riga in conn.execute(f'SELECT rowid, * FROM "{t}"').fetchall():
                    nuovi = {}
                    for nome, valore in zip(colonne, riga[1:]):
                        if isinstance(valore, str) and ("data" in valore.lower()):
                            dopo = _riscrivi_stringa_composta(valore, coppie)
                            if dopo != valore:
                                nuovi[nome] = dopo
                    if nuovi:
                        assegna = ", ".join(f'"{c}" = ?' for c in nuovi)
                        conn.execute(f'UPDATE "{t}" SET {assegna} WHERE rowid = ?', (*nuovi.values(), riga[0]))
                        cambiate += 1
    except sqlite3.Error as exc:
        log.warning("[Works] database %s non riscritto: %s", db, exc)
    return cambiate


def esegui() -> Dict:
    """Copia ogni area storica nella nuova posizione (se non c'e' gia') e riscrive i percorsi."""
    root = paths.project_root()
    esito = {"copiate": [], "saltate": [], "riscritture": {}}
    for vecchio, nuovo in TRASLOCHI:
        src, dst = paths.workspace_dir() / vecchio, root / nuovo
        if not src.is_dir():
            continue
        if dst.exists():
            esito["saltate"].append(str(dst))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        # personaggi sta dentro creative: se creative e' appena stato copiato, la cartella esiste gia'
        shutil.copytree(src, dst, dirs_exist_ok=False)
        esito["copiate"].append({"da": str(src), "a": str(dst)})
        log.info("[Works] copiato %s -> %s", src, dst)
    for base in (root / "works", root / "store" / "calibration"):
        if base.is_dir():
            esito["riscritture"][str(base)] = riscrivi_percorsi(base)
    return esito


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Copia le creazioni dei moduli da data/ a works/.")
    parser.add_argument("--esegui", action="store_true", help="copia e riscrive (senza: prova a vuoto)")
    args = parser.parse_args(argv)
    for v in piano():
        stato = "gia' presente" if v["fatto"] else f"{v['byte'] / 1e6:.1f} MB"
        print(f"{v['da']}  ->  {v['a']}   [{stato}]")
    if not args.esegui:
        print("\nProva a vuoto. Con --esegui copia (gli originali in data/ restano) e riscrive i percorsi.")
        return 0
    esito = esegui()
    print(json.dumps(esito, ensure_ascii=False, indent=2))
    print("\nFatto. Controlla che tutto si apra, poi puoi rimuovere a mano le cartelle originali in data/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
