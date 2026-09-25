# ==============================================================================
# tests/test_kicad_editor_contract.py — L'editor e le rotte parlano la stessa lingua
# ==============================================================================
"""Il modo in cui un'interfaccia muore senza che nessuno se ne accorga.

L'editor TypeScript di `sigma_kicad_lab` chiamava quattro endpoint che non
esistevano — `/api/mcp/kicad_add_track`, `/api/mcp/kicad_add_via`,
`/api/mcp/kicad_update_footprint_position`, `/api/mcp/kicad_add_part` — e un tool
che non e' mai stato scritto. Non si vedeva da nessuna parte: i file si aprivano,
la build passava, e solo al primo clic vero il server rispondeva 404. Un editor
che non ha mai scritto un byte sulla scheda.

Questo file e' il controllo che mancava, e va nei due sensi:

- ogni endpoint che il frontend chiama dev'essere una rotta registrata;
- ogni rotta registrata dev'essere un tool che esiste, o rispondera' 404 a chi
  la chiama.

Il conteggio degli elementi esaminati finisce nell'ultima riga, nel formato che
l'harness legge: un controllo che non ha guardato niente non e' una prova.
"""
import re
from pathlib import Path

import pytest

from core import paths
from core.modules.sigma_kicad_lab import tools
from core.modules.sigma_kicad_lab.handlers import ROUTE_MANUALI, ROUTES

tools.registra()

#: La copia installata del frontend del modulo: quella che finisce nel bundle.
FRONTEND = Path(paths.frontend_modules_dir()) / "sigma_kicad_lab"

#: Un endpoint citato nel frontend: '/api/kicad/...' con o senza query string.
#: Le parti sono fatte di lettere, cifre, trattini e underscore: i puntini di
#: sospensione di un commento che dice «una rotta `/api/kicad/...`» non sono un
#: endpoint, e un controllo che li conta come tali si impara a ignorarlo.
_ENDPOINT = re.compile(r"['\"`](/api/kicad/[a-z0-9_\-]+(?:/[a-z0-9_\-]+)*)")


def _file_del_frontend() -> list:
    if not FRONTEND.is_dir():
        pytest.fail(
            f"Il frontend del modulo non e' installato in {FRONTEND}: "
            "reinstalla sigma_kicad_lab dal catalogo dei moduli."
        )
    return sorted(p for p in FRONTEND.rglob("*.js*")
                  if "__tests__" not in p.parts and "node_modules" not in p.parts)


def _endpoint_del_frontend() -> dict:
    """Endpoint chiamato -> file che lo chiama."""
    trovati = {}
    for percorso in _file_del_frontend():
        testo = percorso.read_text(encoding="utf-8", errors="replace")
        for voce in _ENDPOINT.findall(testo):
            trovati.setdefault(voce.rstrip("/"), percorso.name)
    return trovati


# --- 1. le rotte del modulo e i tool che eseguono ---------------------------

def test_ogni_rotta_del_modulo_punta_a_un_tool_che_esiste():
    esaminate = 0
    orfane = {}
    for percorso, nome_tool in ROUTE_MANUALI:
        esaminate += 1
        if nome_tool not in tools.ESECUTORI:
            orfane[percorso] = nome_tool
    print(f'SIGMA-CHECK {{"check": "rotte-come-tool", "checked": {esaminate}, '
          f'"problems": {len(orfane)}}}')
    assert esaminate > 0, "nessuna rotta esaminata"
    assert not orfane, (
        f"{len(orfane)} rotte chiamano un tool inesistente e risponderanno 404: "
        f"{orfane}"
    )


def test_nessuna_rotta_dichiarata_due_volte():
    """FastAPI accetta due volte lo stesso percorso e ne usa uno solo: la prima
    rotta resta, la seconda sparisce — e nessuno se ne accorge."""
    percorsi = [percorso for percorso, _, _ in ROUTES]
    ripetuti = {p for p in percorsi if percorsi.count(p) > 1}
    assert percorsi, "nessuna rotta registrata"
    assert not ripetuti, f"percorsi registrati due volte: {sorted(ripetuti)}"


# --- 2. il frontend chiama solo rotte registrate ----------------------------

def test_ogni_chiamata_del_frontend_ha_una_rotta():
    registrate = {percorso for percorso, _, _ in ROUTES}
    chiamate = _endpoint_del_frontend()
    inventate = {voce: dove for voce, dove in chiamate.items()
                 if voce not in registrate}
    print(f'SIGMA-CHECK {{"check": "endpoint-del-frontend", '
          f'"checked": {len(chiamate)}, "problems": {len(inventate)}}}')
    assert len(chiamate) >= 8, (
        f"solo {len(chiamate)} endpoint trovati nel frontend: il controllo non "
        "sta guardando l'editor"
    )
    assert not inventate, (
        f"Il frontend chiama endpoint che il modulo non registra, e il clic "
        f"finirebbe in un 404: {inventate}"
    )
