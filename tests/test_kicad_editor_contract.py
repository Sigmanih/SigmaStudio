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
import ast
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


# --- 3. gli endpoint nuovi del task #6 sono tutti registrati -----------------
# Ogni endpoint che la tab PCB Lab usa per le funzioni richieste (undo/redo,
# zone, netclass, rules, drc, erc, costruttori, bom, sync, 3d, export) deve
# avere una rotta nel modulo: se manca, il clic finisce in un 404.

_ENDPOINTI_NUOVI = [
    "/api/kicad/undo",
    "/api/kicad/redo",
    "/api/kicad/zone_add",
    "/api/kicad/netclass_set",
    "/api/kicad/rules_set",
    "/api/kicad/drc",
    "/api/kicad/erc",
    "/api/kicad/constructor_hole",
    "/api/kicad/constructor_fiducial",
    "/api/kicad/constructor_testpoint",
    "/api/kicad/constructor_silkscreen",
    "/api/kicad/constructor_outline",
    "/api/kicad/bom_export",
    "/api/kicad/sync_netlist",
    "/api/kicad/render_3d",
    "/api/kicad/export_gerbers",
    "/api/kicad/export_drill",
    "/api/kicad/export_pickplace",
]


def test_endpointi_nuovi_tutti_registrati():
    """Ogni endpoint del task #6 deve avere una rotta nel modulo.

    Il contratto e' che il backend esponga TUTTI gli endpoint che la UI
    chiama: un 404 al primo clic su 'Redo' o 'Zone' e' un bug, non una
    limitazione. Questo test fallisce se anche uno solo dei nuovi endpoint
    non ha una rotta registrata in handlers.ROUTES.
    """
    registrate = {percorso for percorso, _, _ in ROUTES}
    mancati = [ep for ep in _ENDPOINTI_NUOVI if ep not in registrate]
    print(f'SIGMA-CHECK {{"check": "endpointi-nuovi-task6", '
          f'"checked": {len(_ENDPOINTI_NUOVI)}, "problems": {len(mancati)}}}')
    assert len(_ENDPOINTI_NUOVI) >= 10, (
        "meno di 10 endpoint nuovi dichiarati: il controllo non copre il task"
    )
    assert not mancati, (
        f"{len(mancati)} endpoint del task #6 non hanno una rotta registrata "
        f"e risponderanno 404 al primo clic: {mancati}"
    )


# --- 4. gli endpoint nuovi hanno anche un tool che li esegue -----------------
# Una rotta registrata senza tool corrispondente risponde 404 al primo clic.
# Il test 1 copre ROUTE_MANUALI; qui copriamo gli endpoint del task #6 che
# devono essere risolti da ESECUTORI (o ROUTE_MANUALI) nel modulo.

def test_endpointi_nuovi_hanno_un_tool_esecutore():
    """Ogni endpoint del task #6 deve avere un tool in ESECUTORI o ROUTE_MANUALI."""
    manuali = {percorso: nome for percorso, nome in ROUTE_MANUALI}
    esaminate = 0
    orfane = {}
    for ep in _ENDPOINTI_NUOVI:
        esaminate += 1
        # estrai il nome tool dalla rotta: /api/kicad/undo -> kicad_undo
        nome_tool = "kicad_" + ep.rsplit("/", 1)[-1]
        if ep not in manuali and nome_tool not in tools.ESECUTORI:
            orfane[ep] = nome_tool
    print(f'SIGMA-CHECK {{"check": "endpointi-nuovi-tool", '
          f'"checked": {esaminate}, "problems": {len(orfane)}}}')
    assert esaminate >= 10, "meno di 10 endpoint esaminati: il controllo non copre il task"
    assert not orfane, (
        f"{len(orfane)} endpoint del task #6 non hanno un tool esecutore e "
        f"risponderanno 404: {orfane}"
    )


# --- 5. ogni chiave di ESECUTORI nomina una funzione che esiste nel file ------
# Il 26/09 il modulo e' rimasto ore impossibile da importare: `ESECUTORI` citava
# tredici funzioni che nessuno aveva scritto. Un nome senza `def` non fa fallire
# una prova — solleva `NameError` mentre il modulo si carica, e quel fallimento
# non e' una prova rossa: e' la raccolta che si ferma, ottantatre prove che non
# esistono piu'. Chi legge vede "collection error" e crede a un test sbagliato.
#
# Qui si guarda il sorgente invece del modulo vivo: cosi' il messaggio dice
# quale nome manca, che e' l'unica cosa che serve per ripararlo.

def _nomi_definiti(sorgente: str) -> set:
    """I nomi che il file definisce a livello di modulo: funzioni e costanti."""
    nomi = set()
    for nodo in ast.parse(sorgente).body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomi.add(nodo.name)
        elif isinstance(nodo, ast.Assign):
            nomi.update(bersaglio.id for bersaglio in nodo.targets
                        if isinstance(bersaglio, ast.Name))
    return nomi


def _nomi_citati_in_esecutori(sorgente: str) -> list:
    """I nomi che il dizionario `ESECUTORI` usa come propri valori."""
    for nodo in ast.parse(sorgente).body:
        if not isinstance(nodo, ast.Assign):
            continue
        if not any(isinstance(b, ast.Name) and b.id == "ESECUTORI"
                   for b in nodo.targets):
            continue
        if not isinstance(nodo.value, ast.Dict):
            return []
        return [valore.id for valore in nodo.value.values
                if isinstance(valore, ast.Name)]
    return []


def test_ogni_chiave_di_esecutori_nomina_una_funzione_esistente():
    """Ogni tool dichiarato in `ESECUTORI` deve avere un `def` nello stesso file.

    Senza questo controllo un nome sbagliato non e' un errore visibile: e' un
    import che non finisce, e il modulo intero smette di caricarsi.
    """
    sorgente = Path(tools.__file__).read_text(encoding="utf-8")
    citati = _nomi_citati_in_esecutori(sorgente)
    definiti = _nomi_definiti(sorgente)
    orfani = sorted({nome for nome in citati if nome not in definiti})
    # I nomi letti dal sorgente devono essere gli stessi che il modulo espone:
    # se un giorno il dizionario si costruisce altrove, questo lo dice invece di
    # dichiarare verde un controllo che sta guardando il vuoto.
    vivi = sorted(funzione.__name__ for funzione in tools.ESECUTORI.values())
    print(f'SIGMA-CHECK {{"check": "esecutori-definiti", "checked": {len(citati)}, '
          f'"problems": {len(orfani)}}}')
    assert citati, "nessun nome letto da ESECUTORI: il controllo non guarda il file"
    assert sorted(citati) == vivi, (
        f"il sorgente e il modulo dicono cose diverse: nel file {sorted(citati)}, "
        f"nel modulo {vivi}"
    )
    assert not orfani, (
        f"{len(orfani)} chiavi di ESECUTORI nominano funzioni che non esistono "
        f"in tools.py: il modulo non si importa. Aggiungi il `def` o togli la "
        f"chiave: {orfani}"
    )
