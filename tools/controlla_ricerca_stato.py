"""Il controllo che la ricerca non consegni all agente la propria contabilita.

Non e un test: e la misura su questo workspace, adesso, con i numeri. Per ogni
termine cercato dice quanti risultati vengono dal codice e quanti ? devono
essere zero ? dalle cartelle di stato del programma.

Un controllo che non ha esaminato niente esce con codice zero esattamente come
uno che ha guardato tutto senza trovare nulla: per questo conta anche le copie
di codice che vivono dentro `var/` e pretende che ce ne sia almeno una. Se non
ce ne fosse, il controllo non starebbe misurando niente e lo direbbe.

Ultima riga dell output, sempre: SIGMA-CHECK.
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE_PROGETTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE_PROGETTO))

from core.harness.fs_manager import (  # noqa: E402
    SEARCH_IGNORE_RUNTIME_DIRS,
    cartelle_di_stato_saltate,
    get_default_workspace_root,
    search_workspace_files,
)

#: I termini che hanno bruciato i turni del run del 23 settembre 2026.
TERMINI = (
    "def _esegui_voce",
    "def stream_admin_agent_turn",
    "SEARCH_IGNORE_RUNTIME_DIRS",
)


def _dentro_lo_stato(percorso: str, cartelle) -> bool:
    testo = "/" + percorso.replace("\\", "/") + "/"
    return any(f"/{nome}/" in testo for nome in cartelle)


def main() -> int:
    radice = get_default_workspace_root()
    saltate = cartelle_di_stato_saltate(radice)
    esaminati = 0
    problemi = 0

    # Prova di non-vacuita: si scrive nel posto che il divieto esclude, e si
    # verifica che la ricerca non lo veda. Un controllo che non ha escluso
    # niente esce con codice zero esattamente come uno che ha escluso tutto.
    prova = Path(radice) / "var" / ".prova_ricerca_stato.txt"
    try:
        prova.parent.mkdir(parents=True, exist_ok=True)
        prova.write_text(TERMINI[0], encoding="utf-8")
    except OSError as exc:
        problemi += 1
        print("PROBLEMA: impossibile preparare la prova dentro var/: %s" % exc)
    esito_prova = search_workspace_files(radice, TERMINI[0], max_results=50)
    esaminati += 1 + len(esito_prova.get("results") or [])
    visti = [r for r in (esito_prova.get("results") or [])
             if ".prova_ricerca_stato.txt" in str(r.get("path") or "")]
    if visti:
        problemi += 1
        print("PROBLEMA: la ricerca vede un file scritto dentro var/ ? "
              "il divieto non sta escludendo niente.")
    else:
        print("prova di non-vacuita: un file scritto in var/ resta invisibile "
              "alla ricerca")
    try:
        prova.unlink()
    except OSError:
        pass

    for termine in TERMINI:
        esito = search_workspace_files(radice, termine, max_results=30,
                                       timeout_seconds=20.0)
        percorsi = [str(r.get("path") or "") for r in esito.get("results") or []]
        esaminati += 1 + len(percorsi)
        dentro = [p for p in percorsi if _dentro_lo_stato(p, SEARCH_IGNORE_RUNTIME_DIRS)]
        if dentro:
            problemi += 1
            print("PROBLEMA %r: %d risultati dentro lo stato ? %s"
                  % (termine, len(dentro), dentro[:3]))
        print("  %r: %d risultati, %d file esaminati, troncato=%s"
              % (termine, len(percorsi), esito.get("scanned_files") or 0,
                 bool(esito.get("capped"))))

    if not saltate:
        problemi += 1
        print("PROBLEMA: nessuna cartella di stato da saltare in questo workspace")
    else:
        print("cartelle di stato saltate dalla scansione: " + ", ".join(saltate))

    print(
        'SIGMA-CHECK {"check": "ricerca", "checked": %d, "problems": %d}'
        % (esaminati, problemi)
    )
    return 1 if problemi else 0


if __name__ == "__main__":
    raise SystemExit(main())

