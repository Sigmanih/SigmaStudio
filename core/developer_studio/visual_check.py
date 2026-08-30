# ==============================================================================
# core/developer_studio/visual_check.py — Verifica visiva delle modifiche
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Guardare la pagina, perche' nessun test testuale la guarda.

Il modulo Sigma Network ha superato ogni controllo automatico — nessuna
dipendenza vietata, tema chiaro e scuro gestiti, stati di caricamento ed errore
presenti, build verde, test verdi — ed era graficamente inaccettabile. Il
cancello di completamento non poteva accorgersene: misura che *una* verifica e'
passata, e nessuna delle verifiche disponibili guardava il risultato.

Uno screenshot chiude quella distanza in due modi. Un modello puo' rispondere
alle domande che contano di piu' e che nessun linter pone -- la pagina e'
vuota? c'e' uno stack trace a schermo? il testo esce dal contenitore? -- e una
persona vede in un secondo cio' che nessuna descrizione testuale trasmette.

Nessuna dipendenza nuova: si usa la modalita' headless del browser Chromium
gia' installato sulla macchina. Dove non ce n'e' uno la funzione lo dice e non
finge, perche' una verifica che fallisce in silenzio e' peggio di una assente.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("developer_visual")

#: Tempo massimo concesso al browser per aprire la pagina e scattare.
CAPTURE_TIMEOUT_S = 45
#: Dimensioni predefinite: un desktop comune, non lo schermo di chi sviluppa.
DEFAULT_WIDTH = 1440
DEFAULT_HEIGHT = 900
#: Sotto questa dimensione il PNG e' quasi certamente una pagina bianca.
SUSPICIOUSLY_SMALL_BYTES = 8_000


def _candidate_browsers() -> List[str]:
    """I percorsi dove puo' trovarsi un browser Chromium, per questo sistema.

    L'ordine e' deliberato: prima cio' che sta nel PATH, perche' su Linux e sul
    Raspberry e' li' che vive, poi le installazioni note di Windows e macOS.
    """
    dal_path = [
        shutil.which(nome)
        for nome in ("chrome", "chromium", "chromium-browser", "google-chrome", "msedge")
    ]
    candidati = [p for p in dal_path if p]

    sistema = platform.system()
    if sistema == "Windows":
        for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if not base:
                continue
            candidati += [
                str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
            ]
    elif sistema == "Darwin":
        candidati += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        candidati += [
            "/usr/bin/chromium-browser", "/usr/bin/chromium",
            "/usr/bin/google-chrome", "/snap/bin/chromium",
        ]
    return candidati


def find_browser() -> Optional[str]:
    """Il primo browser Chromium utilizzabile su questa macchina, o None."""
    for percorso in _candidate_browsers():
        if percorso and os.path.isfile(percorso):
            return percorso
    return None


def capture(
    url: str,
    output_path: Optional[str] = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    wait_ms: int = 1200,
) -> Dict[str, Any]:
    """Scatta una schermata della pagina e la salva come PNG.

    `wait_ms` esiste perche' una pagina React monta e poi carica: scattare
    all'evento di load fotografa lo scheletro, non il risultato. E' il tempo
    dato al primo render di completarsi, non un ritardo prudenziale.
    """
    browser = find_browser()
    if not browser:
        return {
            "success": False,
            "error": (
                "Nessun browser Chromium trovato su questa macchina. La verifica "
                "visiva richiede Chrome, Chromium o Edge; su Debian/Raspberry si "
                "installa con `apt install chromium-browser`."
            ),
        }

    if not output_path:
        output_path = str(Path(tempfile.gettempdir()) / f"sigma_shot_{int(time.time())}.png")
    # Il browser risolve --screenshot rispetto alla PROPRIA directory di lavoro,
    # non alla nostra: un percorso relativo finisce altrove, o da nessuna parte.
    output_path = str(Path(output_path).resolve())
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    comando = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        # Il profilo temporaneo evita di toccare quello dell'utente, che
        # potrebbe essere aperto: due processi sullo stesso profilo si
        # ostacolano e lo screenshot non arriva mai.
        f"--user-data-dir={tempfile.mkdtemp(prefix='sigma_shot_')}",
        f"--window-size={int(width)},{int(height)}",
        f"--virtual-time-budget={int(wait_ms)}",
        f"--screenshot={output_path}",
        url,
    ]

    try:
        esito = subprocess.run(
            comando, capture_output=True, text=True,
            timeout=CAPTURE_TIMEOUT_S, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Il browser non ha risposto entro {CAPTURE_TIMEOUT_S}s."}
    except OSError as exc:
        return {"success": False, "error": f"Impossibile avviare il browser: {exc}"}

    if not os.path.isfile(output_path):
        dettaglio = (esito.stderr or esito.stdout or "").strip()[-300:]
        return {
            "success": False,
            "error": f"Screenshot non prodotto (exit {esito.returncode}). {dettaglio}",
        }

    dimensione = os.path.getsize(output_path)
    return {
        "success": True,
        "path": str(Path(output_path)).replace("\\", "/"),
        "bytes": dimensione,
        "width": int(width),
        "height": int(height),
        "browser": os.path.basename(browser),
        # Un PNG minuscolo a queste dimensioni e' una pagina bianca: lo si dice
        # subito, perche' altrimenti l'agente conclude che ha verificato.
        "likely_blank": dimensione < SUSPICIOUSLY_SMALL_BYTES,
    }


def describe(result: Dict[str, Any]) -> str:
    """Il risultato in una riga, per l'osservazione che torna al modello."""
    if not result.get("success"):
        return f"Verifica visiva non riuscita: {result.get('error')}"

    riga = (
        f"Schermata salvata in {result['path']} "
        f"({result['width']}x{result['height']}, {result['bytes'] // 1024} KB, "
        f"{result['browser']})."
    )
    if result.get("likely_blank"):
        riga += (
            " ATTENZIONE: l'immagine e' molto piccola per queste dimensioni, "
            "quindi la pagina e probabilmente VUOTA o non montata. Controlla "
            "la console del browser e che il componente sia esportato e "
            "registrato."
        )
    return riga
