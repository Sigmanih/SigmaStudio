"""Controllo dei punti di riduzione del contesto in Sigma Studio.

Cammina i file che tagliano o riducono il contesto passato al modello e conta
quanti dichiarano esplicitamente cosa hanno lasciato fuori (selezione dichiarata,
dropped_notice, SELEZIONE DICHIARATA). Un punto di riduzione che taglia senza
dichiararlo e' un problema: il modello tratta il contesto ridotto come completo.

Emette una riga SIGMA-CHECK con checked/problems ed esce con codice != 0 se
problems > 0, cosi' il cancello di completamento la legge come prova.
"""
import json
import re
import sys
from pathlib import Path

# Ogni voce: (file, pattern_di_riduzione, pattern_di_dichiarazione)
# La dichiarazione deve comparire NELLA STESSA ZONA del taglio (finestra di righe).
# I pattern sono volutamente specifici: un [:40] in un log di debug non e' una
# riduzione del contesto passato al modello, e non va contato come taglio.
PUNTI = [
    {
        "file": "core/chat/chat_runner.py",
        # Solo i tagli che riducono il prompt/contesto passato al modello.
        "riduzione": re.compile(r"\[:chars_avail\]|trim_history|history\[-\d+:\]"),
        "dichiarazione": re.compile(r"SELEZIONE DICHIARATA|dropped_notice|notice_parts|non rientrano nella finestra|Se ti servono i contenuti esclusi"),
    },
    {
        "file": "core/assistant_orchestrator.py",
        "riduzione": re.compile(r"history\[-\d+:\]|trim_history"),
        "dichiarazione": re.compile(r"SELEZIONE DICHIARATA|Selezione dichiarata|dropped_notice|messaggi storici esclusi|Chiedi esplicitamente il contesto"),
    },
    {
        "file": "core/execute_loop.py",
        "riduzione": re.compile(r"history\[-\d+:\]|trim_history"),
        "dichiarazione": re.compile(r"SELEZIONE DICHIARATA|Selezione dichiarata|dropped_notice|messaggi storici esclusi"),
    },
    {
        "file": "core/chat/history.py",
        # trim_history e' il punto di riduzione; dropped_notice e' la sua dichiarazione.
        # La dichiarazione non e' una stringa vicina al taglio ma un'altra funzione
        # dello stesso modulo: si cerca su tutto il file, non in una finestra.
        "riduzione": re.compile(r"def trim_history"),
        "dichiarazione": re.compile(r"def dropped_notice|non rientrano nella finestra|chiedilo invece di darlo per scontato"),
        "intero_file": True,
    },
]

# Finestra di righe entro cui la dichiarazione deve comparire rispetto al taglio.
# Per i file che esportano la funzione di riduzione (history.py) la dichiarazione
# e' un'altra funzione dello stesso modulo, non una stringa vicina: si usa il
# flag 'intero_file' per cercare su tutto il testo invece che in una finestra.
FINESTRA = 40


def analizza_punto(punto: dict, root: Path) -> tuple[bool, str]:
    path = root / punto["file"]
    if not path.exists():
        return False, f"file mancante: {punto['file']}"

    righe = path.read_text(encoding="utf-8").splitlines()
    tagli = [i for i, r in enumerate(righe) if punto["riduzione"].search(r)]
    if not tagli:
        # Nessun punto di riduzione: non c'e' nulla da dichiarare. Va bene.
        return True, "nessun taglio rilevato (niente da dichiarare)"

    # Se il punto dichiara 'intero_file', la dichiarazione puo' stare in un'altra
    # funzione dello stesso modulo (es. trim_history e dropped_notice in history.py):
    # si cerca su tutto il testo, non in una finestra attorno al taglio.
    intero = punto.get("intero_file", False)
    for idx in tagli:
        if intero:
            zona = "\n".join(righe)
        else:
            inizio = max(0, idx - FINESTRA)
            fine = min(len(righe), idx + FINESTRA)
            zona = "\n".join(righe[inizio:fine])
        if not punto["dichiarazione"].search(zona):
            return False, (
                f"{punto['file']} riga {idx + 1}: taglio '{righe[idx].strip()}' "
                f"senza dichiarazione di cosa resta fuori"
            )
    return True, f"{len(tagli)} tagli, tutti dichiarati"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    checked = 0
    problemi = []

    for punto in PUNTI:
        checked += 1
        ok, dettaglio = analizza_punto(punto, root)
        if not ok:
            problemi.append(dettaglio)
            print(f"[KO] {dettaglio}")
        else:
            print(f"[OK] {punto['file']}: {dettaglio}")

    # Verifica che il parser di verification.py riconosca la riga SIGMA-CHECK.
    checked += 1
    try:
        sys.path.insert(0, str(root))
        from core.harness.verification import parse_verification
        riga = "SIGMA-CHECK " + json.dumps({"check": "contesto", "checked": checked, "problems": len(problemi)})
        report = parse_verification("python tools/verifica_contesto.py", 0, riga)
        if not (report.kind == "project_check" and report.is_valid == (len(problemi) == 0)):
            problemi.append(f"parser SIGMA-CHECK inatteso: {report.summary}")
    except Exception as e:
        problemi.append(f"impossibile importare verification.py: {e}")

    print()
    for p in problemi:
        print("PROBLEMA:", p)

    payload = {"check": "contesto", "checked": checked, "problems": len(problemi)}
    print("SIGMA-CHECK " + json.dumps(payload))
    return 1 if problemi else 0


if __name__ == "__main__":
    sys.exit(main())
