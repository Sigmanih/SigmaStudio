# ==============================================================================
# sigma_kicad_lab/tools.py — I tool con cui un agente progetta in KiCad
# ==============================================================================
"""Il vocabolario KiCad di un agente: aprire, leggere, scrivere, verificare.

Sta nel modulo perche' e' il modulo a possedere questi tool: il kernel sa
smistare una chiamata e applicare i permessi, non sa cosa sia una pista. Prima
del 25 settembre 2026 questo file viveva in `core/harness/kicad_tools.py` e
importava `core.modules.sigma_kicad_lab` — cioe' il kernel dipendeva da un
modulo opzionale, e con il modulo disinstallato restavano ventisette tool
dichiarati al modello e nessuno in grado di eseguirli.

Qui si chiama il motore direttamente — `bridge`, `kicad_cli`, `kicad_parser`,
`pcb_writer` — invece di passare da MCP. Con EasyEDA il giro era obbligato
perche' il progetto viveva dentro l'applicazione; un progetto KiCad e' fatto di
file sul disco, e interporre un protocollo fra noi e un file aggiungerebbe solo
i suoi modi di rompersi.

**I pad si indirizzano per riferimento e numero** — `{"part": "U1", "pad": "3"}`
— e le net per nome. Un agente non deve tenere a mente indici interni fra una
chiamata e l'altra: quelli si risolvono qui, in modo deterministico, con un
errore che elenca cosa c'era davvero quando il riferimento non torna.

**Ogni scrittura fa una copia prima.** Un layout e' lavoro che non si rifa' in
un pomeriggio.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from core.logger import get_logger

log = get_logger(__name__)

#: Il progetto su cui si sta lavorando: risolto una volta, poi implicito.
_progetto: Dict[str, Any] = {"pcb": None, "sch": None, "pro": None,
                             "root": None, "quando": 0.0}

#: L'ultima copia di sicurezza per file, per poter tornare indietro di un passo.
_ultimo_backup: Dict[str, str] = {}


class KicadToolError(RuntimeError):
    """La richiesta non si puo' soddisfare, e nulla e' stato scritto."""


def _esito(nome: str, riuscito: bool, **extra: Any) -> Dict[str, Any]:
    """Il risultato di un tool, nella forma che il loop sa leggere.

    Il parametro non si chiama `ok` perche' i payload che arrivano da
    `WriteResult.to_dict()` e dai report di `kicad-cli` contengono gia' una
    chiave `ok`: con quel nome Python la vedeva come un secondo valore per lo
    stesso argomento e sollevava `got multiple values`. Le scritture andavano a
    buon fine e solo il confezionamento del risultato falliva — un errore che
    riportava «KO» su operazioni riuscite, cioe' il modo peggiore di sbagliare.
    `ok` si scarta: la verita' sta in `success`, e due campi che dicono la
    stessa cosa prima o poi si contraddicono.
    """
    extra.pop("ok", None)
    return {"tool": nome, "success": riuscito, **extra}


def _esito_dal_ponte(nome: str, esito: Dict[str, Any]) -> Dict[str, Any]:
    """Il risultato di un tool che parla col ponte `pcbnew`.

    Il ponte dichiara il successo con `ok` e il motivo del fallimento con
    `errore`; il resto del sistema legge `success` e `error`. La traduzione sta
    qui, in un posto solo: sparsa nei sei tool ognuno l'avrebbe fatta a modo
    suo, e il rifiuto del lavoratore — «il riferimento e' gia' usato su questa
    scheda» — sarebbe arrivato a valle come un successo senza motivo. Un agente
    che legge un successo non riprova: crede di avere in scheda un componente
    che non c'e'.
    """
    esito = dict(esito)
    riuscito = bool(esito.pop("ok", True))
    if not riuscito and "errore" in esito and "error" not in esito:
        esito["error"] = esito.pop("errore")
    return _esito(nome, riuscito, **esito)


# --- contesto ------------------------------------------------------------------

def _pcb() -> Path:
    if not _progetto["pcb"]:
        raise KicadToolError(
            "Nessun progetto KiCad aperto. Chiama prima kicad_open indicando "
            "la cartella del progetto o un file .kicad_pro/.kicad_pcb."
        )
    return Path(_progetto["pcb"])


def _sch() -> Path:
    if not _progetto["sch"]:
        raise KicadToolError(
            "Il progetto aperto non ha uno schematico (.kicad_sch): ERC, BOM e "
            "netlist non sono disponibili finche' non esiste."
        )
    return Path(_progetto["sch"])


def kicad_open(path: str) -> Dict[str, Any]:
    """Apre un progetto KiCad e lo rende quello corrente per i tool seguenti."""
    try:
        from . import bridge
        trovati = bridge.find_project_files(Path(path))
        if not trovati.get("pcb") and not trovati.get("sch"):
            return _esito("kicad_open", False, path=path,
                          error=("In quel percorso non c'e' nessun file KiCad. "
                                 "Serve un .kicad_pcb o un .kicad_sch."))
        _progetto.update({
            "pcb": str(trovati["pcb"]) if trovati.get("pcb") else None,
            "sch": str(trovati["sch"]) if trovati.get("sch") else None,
            "pro": str(trovati["pro"]) if trovati.get("pro") else None,
            "root": str(Path(path)), "quando": time.time(),
        })
        return _esito("kicad_open", True, **{k: _progetto[k]
                                             for k in ("pcb", "sch", "pro")})
    except Exception as exc:
        return _esito("kicad_open", False, path=path, error=str(exc))


def kicad_status() -> Dict[str, Any]:
    """KiCad c'e'? Che versione? Che progetto e' aperto?"""
    try:
        from . import bridge
        stato = bridge.status()
        return _esito("kicad_status", bool(stato.get("ok")),
                      kicad_found=stato.get("kicad_found"),
                      version=stato.get("version"),
                      cli=stato.get("kicad_cli_path"),
                      error=stato.get("error", ""),
                      project={k: _progetto[k] for k in ("pcb", "sch", "pro")})
    except Exception as exc:
        return _esito("kicad_status", False, error=str(exc))


# --- lettura -------------------------------------------------------------------

def kicad_board_read() -> Dict[str, Any]:
    """Contorno, pezzi e net della scheda aperta, con le misure in millimetri."""
    try:
        from . import bridge
        scheda = bridge.read_board(_pcb(),
                                   Path(_progetto["sch"]) if _progetto["sch"] else None)
        return _esito("kicad_board_read", True,
                      width_mm=round(scheda.width, 3),
                      height_mm=round(scheda.height, 3),
                      components=len(scheda.components),
                      nets=len(scheda.nets),
                      locked=sum(1 for c in scheda.components.values() if c.locked))
    except Exception as exc:
        return _esito("kicad_board_read", False, error=str(exc))


def kicad_list_parts() -> Dict[str, Any]:
    """I footprint sulla scheda: riferimento, valore, posizione, lato."""
    try:
        from . import kicad_parser as parser
        info = parser.read_pcb(_pcb())
        pezzi = [{"reference": f.reference, "value": f.value,
                  "footprint": f.footprint_lib,
                  "x": round(f.x, 3), "y": round(f.y, 3),
                  "rotation": f.rotation, "layer": f.layer,
                  "locked": f.locked, "pads": len(f.pads),
                  "width_mm": round(f.width_mm, 3),
                  "height_mm": round(f.height_mm, 3)}
                 for f in info.footprints]
        return _esito("kicad_list_parts", True, total=len(pezzi), parts=pezzi)
    except Exception as exc:
        return _esito("kicad_list_parts", False, error=str(exc))


def kicad_pads(part: str) -> Dict[str, Any]:
    """I pad di un footprint: numero, net, posizione assoluta.

    Va chiamato prima di instradare: e' cio' che rende una pista verificabile
    invece che una coppia di coordinate indovinate.
    """
    try:
        from . import kicad_parser as parser
        info = parser.read_pcb(_pcb())
        fp = next((f for f in info.footprints if f.reference == part), None)
        if fp is None:
            disponibili = ", ".join(sorted(f.reference for f in info.footprints))[:300]
            return _esito("kicad_pads", False, part=part,
                          error=f"Nessun pezzo '{part}' sulla scheda. Ci sono: {disponibili}")
        return _esito("kicad_pads", True, part=part, total=len(fp.pads),
                      pads=[{"number": p.number, "net": p.net_name,
                             "net_number": p.net_number, "layer": p.layer,
                             "x": round(p.x, 4), "y": round(p.y, 4)}
                            for p in fp.pads])
    except Exception as exc:
        return _esito("kicad_pads", False, part=part, error=str(exc))


def kicad_nets() -> Dict[str, Any]:
    """Le net della scheda, con quanti pad tocca ciascuna."""
    try:
        from . import kicad_parser as parser
        info = parser.read_pcb(_pcb())
        conteggio: Dict[str, int] = {}
        for f in info.footprints:
            for p in f.pads:
                if p.net_name:
                    conteggio[p.net_name] = conteggio.get(p.net_name, 0) + 1
        return _esito("kicad_nets", True, total=len(conteggio),
                      nets=[{"name": n, "pads": k}
                            for n, k in sorted(conteggio.items(),
                                               key=lambda kv: -kv[1])])
    except Exception as exc:
        return _esito("kicad_nets", False, error=str(exc))


# --- analisi -------------------------------------------------------------------

def kicad_trace_width(current_a: float, delta_t_c: float = 10.0,
                      thickness_oz: float = 1.0,
                      layer: str = "external") -> Dict[str, Any]:
    """Larghezza minima di una pista per una corrente, secondo IPC-2221."""
    try:
        from core.modules.sigma_eda_lab import rules
        calcolo = rules.trace_width(current_a, delta_t_c, thickness_oz, layer)
        return _esito("kicad_trace_width", True, **calcolo.to_dict(),
                      recommended_mm=rules.suggest_width_mm(
                          current_a, layer, thickness_oz))
    except Exception as exc:
        return _esito("kicad_trace_width", False, error=str(exc))


def kicad_board_evaluate() -> Dict[str, Any]:
    """Giudica il piazzamento: sovrapposizioni, contorno, distanze, disaccoppiamento."""
    try:
        from . import bridge
        from core.modules.sigma_eda_lab import evaluate as valutatore
        scheda = bridge.read_board(_pcb(),
                                   Path(_progetto["sch"]) if _progetto["sch"] else None)
        referto = valutatore.evaluate(scheda)
        return _esito("kicad_board_evaluate", True, **referto.to_dict())
    except Exception as exc:
        return _esito("kicad_board_evaluate", False, error=str(exc))


def kicad_placement_optimize(iterations: int = 4000, seed: int = 20260920,
                             lock: Optional[List[str]] = None) -> Dict[str, Any]:
    """Calcola un piazzamento migliore. NON scrive: restituisce gli spostamenti."""
    try:
        from dataclasses import replace
        from . import bridge
        from core.modules.sigma_eda_lab import evaluate as valutatore, placement

        scheda = bridge.read_board(_pcb(),
                                   Path(_progetto["sch"]) if _progetto["sch"] else None)
        if lock:
            fissati = [replace(scheda.components[d], locked=True)
                       for d in lock if d in scheda.components]
            scheda = scheda.with_components(fissati)

        prima = valutatore.evaluate(scheda)
        esito = placement.optimize(scheda, iterations=iterations, seed=seed)
        dopo = valutatore.evaluate(esito.board)
        return _esito("kicad_placement_optimize", True,
                      summary=esito.summary(),
                      score_before=prima.score, score_after=dopo.score,
                      verdict_after=dopo.verdict,
                      moves=[{"reference": c.designator,
                              "x_mm": round(c.x, 3), "y_mm": round(c.y, 3),
                              "rotation": c.rotation}
                             for c in sorted(esito.board.components.values(),
                                             key=lambda c: c.designator)
                             if not c.locked])
    except Exception as exc:
        return _esito("kicad_placement_optimize", False, error=str(exc))


def kicad_placement_apply(moves: List[Dict[str, Any]],
                          dry_run: bool = True) -> Dict[str, Any]:
    """Riscrive nel .kicad_pcb le posizioni calcolate. `dry_run` non tocca nulla."""
    try:
        from . import bridge
        scheda = bridge.read_board(_pcb())
        voluti, ignoti = {}, []
        for m in (moves or []):
            rif = m.get("reference") or m.get("designator")
            pezzo = scheda.components.get(rif)
            if pezzo is None:
                ignoti.append(rif)
                continue
            voluti[rif] = pezzo.moved(float(m.get("x_mm", pezzo.x)),
                                      float(m.get("y_mm", pezzo.y)),
                                      int(m.get("rotation", pezzo.rotation)))
        if not voluti:
            return _esito("kicad_placement_apply", False,
                          unknown=ignoti,
                          error="Nessuno dei riferimenti indicati e' sulla scheda.")
        esito = bridge.apply_placement(scheda.with_components(voluti.values()),
                                       _pcb(), dry_run=dry_run,
                                       only=list(voluti))
        return _esito("kicad_placement_apply", True, unknown=ignoti,
                      **esito.to_dict())
    except Exception as exc:
        return _esito("kicad_placement_apply", False, error=str(exc))


# --- scrittura sul rame --------------------------------------------------------

def _ricorda(esito) -> Dict[str, Any]:
    if esito.backup:
        _ultimo_backup[str(_progetto["pcb"])] = esito.backup
    return esito.to_dict()


def kicad_add_track(start: Sequence[float], end: Sequence[float],
                    width_mm: float, layer: str = "F.Cu",
                    net: str = "") -> Dict[str, Any]:
    """Traccia un segmento di pista fra due punti, in millimetri."""
    try:
        from . import pcb_writer
        return _esito("kicad_add_track", True,
                      **_ricorda(pcb_writer.add_track(
                          _pcb(), start, end, width_mm, layer, net)))
    except Exception as exc:
        return _esito("kicad_add_track", False, error=str(exc))


def kicad_add_route(points: List[Sequence[float]], width_mm: float,
                    layer: str = "F.Cu", net: str = "") -> Dict[str, Any]:
    """Instrada una spezzata: il modo normale di collegare due pad."""
    try:
        from . import pcb_writer
        return _esito("kicad_add_route", True,
                      **_ricorda(pcb_writer.add_route(
                          _pcb(), points, width_mm, layer, net)))
    except Exception as exc:
        return _esito("kicad_add_route", False, error=str(exc))


def kicad_add_via(at: Sequence[float], size_mm: float = 0.8,
                  drill_mm: float = 0.4, net: str = "",
                  layers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Mette un via passante fra due layer di rame."""
    try:
        from . import pcb_writer
        coppia = tuple(layers or ("F.Cu", "B.Cu"))
        return _esito("kicad_add_via", True,
                      **_ricorda(pcb_writer.add_via(
                          _pcb(), at, size_mm, drill_mm, coppia, net)))
    except Exception as exc:
        return _esito("kicad_add_via", False, error=str(exc))


def kicad_add_footprint(library_id: str, reference: str, value: str,
                        x_mm: float, y_mm: float, rotation: float = 0.0,
                        layer: str = "F.Cu",
                        pads: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Mette un footprint sulla scheda (fori, fiducial, schermature, prove)."""
    try:
        from . import pcb_writer
        return _esito("kicad_add_footprint", True,
                      **_ricorda(pcb_writer.add_footprint(
                          _pcb(), library_id, reference, value,
                          (x_mm, y_mm), rotation, layer, pads)))
    except Exception as exc:
        return _esito("kicad_add_footprint", False, error=str(exc))


def kicad_remove_footprint(reference: str) -> Dict[str, Any]:
    """Toglie un footprint dalla scheda. Il rame che lo raggiungeva resta."""
    try:
        from . import pcb_writer
        return _esito("kicad_remove_footprint", True,
                      **_ricorda(pcb_writer.remove_footprint(_pcb(), reference)))
    except Exception as exc:
        return _esito("kicad_remove_footprint", False, reference=reference,
                      error=str(exc))


# --- modifica di cio' che c'e' gia' ---------------------------------------------
#
# Le primitive qui sotto correggono una scheda invece di popolarla: spostare,
# rinominare, cancellare. Servono all'utente che trascina un pezzo sulla canvas
# e all'agente che si accorge di averlo messo nel posto sbagliato. Senza,
# l'unica correzione possibile era togliere il pezzo e rimetterlo, e per una
# pista tracciata male non c'era rimedio affatto.

def kicad_move_footprint(reference: str, x_mm: float, y_mm: float,
                         rotation: Optional[float] = None) -> Dict[str, Any]:
    """Sposta un pezzo, e se serve lo ruota. Senza `rotation` la lascia com'era."""
    try:
        from . import pcb_writer
        return _esito("kicad_move_footprint", True,
                      **_ricorda(pcb_writer.move_footprint(
                          _pcb(), reference, x_mm, y_mm, rotation)))
    except Exception as exc:
        return _esito("kicad_move_footprint", False, reference=reference,
                      error=str(exc))


def kicad_rename_footprint(reference: str, new_reference: str = "",
                           value: str = "") -> Dict[str, Any]:
    """Cambia il riferimento e/o il valore di un pezzo."""
    try:
        from . import pcb_writer
        return _esito("kicad_rename_footprint", True,
                      **_ricorda(pcb_writer.rename_footprint(
                          _pcb(), reference, new_reference, value)))
    except Exception as exc:
        return _esito("kicad_rename_footprint", False, reference=reference,
                      error=str(exc))


def kicad_delete_track(start: Sequence[float], end: Sequence[float],
                       layer: str = "") -> Dict[str, Any]:
    """Toglie la pista che unisce due punti: gli estremi la identificano."""
    try:
        from . import pcb_writer
        return _esito("kicad_delete_track", True,
                      **_ricorda(pcb_writer.delete_track(
                          _pcb(), start, end, layer)))
    except Exception as exc:
        return _esito("kicad_delete_track", False, error=str(exc))


def kicad_delete_via(at: Sequence[float]) -> Dict[str, Any]:
    """Toglie il via che sta in un punto."""
    try:
        from . import pcb_writer
        return _esito("kicad_delete_via", True,
                      **_ricorda(pcb_writer.delete_via(_pcb(), at)))
    except Exception as exc:
        return _esito("kicad_delete_via", False, error=str(exc))


def kicad_set_board_outline(width_mm: float, height_mm: float) -> Dict[str, Any]:
    """Sostituisce il contorno scheda con un rettangolo con un angolo in (0, 0)."""
    try:
        from . import pcb_writer
        return _esito("kicad_set_board_outline", True,
                      **_ricorda(pcb_writer.set_board_outline(
                          _pcb(), width_mm, height_mm)))
    except Exception as exc:
        return _esito("kicad_set_board_outline", False, error=str(exc))


def kicad_set_pad_net(reference: str, pad: str, net: str) -> Dict[str, Any]:
    """Assegna una net al pad di un pezzo, creando la net se non esiste."""
    try:
        from . import pcb_writer
        return _esito("kicad_set_pad_net", True,
                      **_ricorda(pcb_writer.set_pad_net(
                          _pcb(), reference, pad, net)))
    except Exception as exc:
        return _esito("kicad_set_pad_net", False, reference=reference,
                      error=str(exc))


def kicad_undo() -> Dict[str, Any]:
    """Annulla l'ultima scrittura sul PCB, dalla copia fatta prima di applicarla."""
    try:
        from . import pcb_writer
        chiave = str(_pcb())
        copia = _ultimo_backup.get(chiave)
        if not copia:
            return _esito("kicad_undo", False,
                          error="Nessuna scrittura da annullare in questa sessione.")
        # Sposta la copia corrente nella pila redo prima di sovrascriverla
        if not hasattr(kicad_redo, "_pila_redo"):
            kicad_redo._pila_redo = {}
        pila_redo = kicad_redo._pila_redo.setdefault(chiave, [])
        pila_redo.append(copia)
        esito = pcb_writer.restore_backup(_pcb(), copia)
        _ultimo_backup.pop(chiave, None)
        return _esito("kicad_undo", True, **esito.to_dict())
    except Exception as exc:
        return _esito("kicad_undo", False, error=str(exc))


def kicad_redo() -> Dict[str, Any]:
    """Riapplica l'ultima operazione annullata con `kicad_undo`.

    La cronologia redo e' una pila separata: ogni `undo` sposta la copia
    corrente nella pila redo, e ogni `redo` la riporta indietro. Se la pila
    redo e' vuota, l'operazione fallisce con un messaggio esplicito.
    """
    try:
        from . import pcb_writer
        chiave = str(_pcb())
        # La pila redo e' mantenuta a livello di modulo: una lista di backup
        # in ordine cronologico (ultimo in fondo).
        if not hasattr(kicad_redo, "_pila_redo"):
            kicad_redo._pila_redo = {}  # chiave -> list[backup]
        pila = kicad_redo._pila_redo.get(chiave)
        if not pila:
            return _esito("kicad_redo", False,
                          error="Nessuna operazione da riapplicare in questa sessione.")
        copia = pila.pop()
        esito = pcb_writer.restore_backup(_pcb(), copia)
        return _esito("kicad_redo", True, **esito.to_dict())
    except Exception as exc:
        return _esito("kicad_redo", False, error=str(exc))


# --- verifica ------------------------------------------------------------------

def kicad_drc() -> Dict[str, Any]:
    """Design Rule Check di KiCad sul PCB. E' la prova che il rame sta in piedi."""
    try:
        from . import kicad_cli as cli
        report = cli.run_drc(_pcb())
        # Due cose diverse che il report chiama quasi allo stesso modo: `ok` e'
        # «il comando e' girato», `success` e' «la scheda passa». Fuse in un
        # campo solo, un agente non distingue un DRC che non parte da un DRC
        # che boccia, e sono situazioni opposte: la prima si riprova, la
        # seconda si corregge.
        passato = bool(report.pop("success", False))
        return _esito("kicad_drc", True, drc_passed=passato, **report)
    except Exception as exc:
        return _esito("kicad_drc", False, error=str(exc))


def kicad_erc() -> Dict[str, Any]:
    """Electrical Rule Check sullo schematico."""
    try:
        from . import kicad_cli as cli
        report = cli.run_erc(_sch())
        passato = bool(report.pop("success", False))
        return _esito("kicad_erc", True, erc_passed=passato, **report)
    except Exception as exc:
        return _esito("kicad_erc", False, error=str(exc))


# --- export --------------------------------------------------------------------

def kicad_export_gerbers(output_dir: str = "") -> Dict[str, Any]:
    """Gerber e file di foratura, il pacchetto che si manda in fabbrica."""
    try:
        from . import kicad_cli as cli
        out = Path(output_dir) if output_dir else None
        gerbers = cli.export_gerbers(_pcb(), out)
        drill = cli.export_drill(_pcb(), out or _pcb().parent / "gerbers")
        return _esito("kicad_export_gerbers", True, gerbers=gerbers, drill=drill)
    except Exception as exc:
        return _esito("kicad_export_gerbers", False, error=str(exc))


def kicad_export_bom(output_path: str = "") -> Dict[str, Any]:
    """La distinta base, dallo schematico."""
    try:
        from . import kicad_cli as cli
        out = Path(output_path) if output_path else None
        return _esito("kicad_export_bom", True, **cli.export_bom(_sch(), out))
    except Exception as exc:
        return _esito("kicad_export_bom", False, error=str(exc))


def kicad_render(output_path: str = "", mode: str = "3d") -> Dict[str, Any]:
    """Un'immagine della scheda, cosi' il lavoro si puo' guardare."""
    try:
        from . import kicad_cli as cli
        if mode == "svg":
            out = Path(output_path) if output_path else None
            return _esito("kicad_render", True, **cli.export_svg(_pcb(), out))
        destinazione = Path(output_path) if output_path else (
            Path("var") / "kicad" / f"board-{int(time.time())}.png")
        Destinazione.parent.mkdir(parents=True, exist_ok=True)
        return _esito("kicad_render", True,
                      **cli.render_3d(_pcb(), Destinazione))
    except Exception as exc:
        return _esito("kicad_render", False, error=str(exc))


# --- pcbnew bridge: creazione e ispezione diretta via API pcbnew -------------

def kicad_pcbnew_status() -> Dict[str, Any]:
    """Stato del ponte pcbnew: versione e percorsi trovati."""
    try:
        from . import pcbnew_bridge as ponte
        return _esito_dal_ponte("kicad_pcbnew_status", ponte.disponibile())
    except Exception as exc:
        return _esito("kicad_pcbnew_status", False, error=str(exc))


def kicad_libraries() -> Dict[str, Any]:
    """Elenco delle librerie di footprint disponibili."""
    try:
        from . import pcbnew_bridge as ponte
        return _esito_dal_ponte("kicad_libraries", ponte.elenca_librerie())
    except Exception as exc:
        return _esito("kicad_libraries", False, error=str(exc))


def kicad_search_footprint(query: str = "", limite: int = 20,
                            libreria: str = "") -> Dict[str, Any]:
    """Cerca footprint nelle librerie KiCad."""
    try:
        from . import pcbnew_bridge as ponte
        return _esito_dal_ponte(
            "kicad_search_footprint",
            ponte.cerca_footprint(query, limite=limite, libreria=libreria))
    except Exception as exc:
        return _esito("kicad_search_footprint", False, error=str(exc))


def kicad_new_board(percorso: str = "", larghezza_mm: float = 100.0,
                    altezza_mm: float = 80.0, net: Optional[List[str]] = None,
                    sovrascrivi: bool = False) -> Dict[str, Any]:
    """Crea una nuova scheda KiCad vuota."""
    try:
        from . import pcbnew_bridge as ponte
        return _esito_dal_ponte(
            "kicad_new_board",
            ponte.crea_scheda(percorso, larghezza_mm=larghezza_mm,
                              altezza_mm=altezza_mm,
                              net=net or [], sovrascrivi=sovrascrivi))
    except Exception as exc:
        return _esito("kicad_new_board", False, error=str(exc))


def kicad_add_part(percorso: str = "", libreria: str = "", footprint: str = "",
                   riferimento: str = "", valore: str = "",
                   x_mm: float = 0.0, y_mm: float = 0.0,
                   rotazione: float = 0.0,
                   net_per_pad: Optional[Dict[str, str]] = None,
                   lato: str = "") -> Dict[str, Any]:
    """Aggiunge un componente (footprint) a una scheda esistente."""
    try:
        from . import pcbnew_bridge as ponte
        return _esito_dal_ponte(
            "kicad_add_part",
            ponte.aggiungi_componente(
                percorso, libreria=libreria, footprint=footprint,
                riferimento=riferimento, valore=valore,
                x_mm=x_mm, y_mm=y_mm, rotazione=rotazione,
                net_per_pad=net_per_pad or {"1": "GND"}, lato=lato))
    except Exception as exc:
        return _esito("kicad_add_part", False, error=str(exc))


def kicad_read_board_full(percorso: str = "") -> Dict[str, Any]:
    """Legge lo stato completo di una scheda KiCad."""
    try:
        from . import pcbnew_bridge as ponte
        if not percorso:
            raise KicadToolError("percorso obbligatorio per leggere una scheda")
        return _esito_dal_ponte("kicad_read_board_full", ponte.leggi_scheda(percorso))
    except Exception as exc:
        return _esito("kicad_read_board_full", False, error=str(exc))


#: Nome canonico -> funzione. Il provider espone `esegui`, che li smista tutti.
ESECUTORI = {
    "kicad_status": kicad_status,
    "kicad_open": kicad_open,
    "kicad_board_read": kicad_board_read,
    "kicad_list_parts": kicad_list_parts,
    "kicad_pads": kicad_pads,
    "kicad_nets": kicad_nets,
    "kicad_trace_width": kicad_trace_width,
    "kicad_board_evaluate": kicad_board_evaluate,
    "kicad_placement_optimize": kicad_placement_optimize,
    "kicad_placement_apply": kicad_placement_apply,
    "kicad_add_track": kicad_add_track,
    "kicad_add_route": kicad_add_route,
    "kicad_add_via": kicad_add_via,
    "kicad_add_footprint": kicad_add_footprint,
    "kicad_remove_footprint": kicad_remove_footprint,
    # correzione di una scheda che c'e' gia'
    "kicad_move_footprint": kicad_move_footprint,
    "kicad_rename_footprint": kicad_rename_footprint,
    "kicad_delete_track": kicad_delete_track,
    "kicad_delete_via": kicad_delete_via,
    "kicad_set_board_outline": kicad_set_board_outline,
    "kicad_set_pad_net": kicad_set_pad_net,
    "kicad_undo": kicad_undo,
    "kicad_drc": kicad_drc,
    "kicad_erc": kicad_erc,
    "kicad_export_gerbers": kicad_export_gerbers,
    "kicad_export_bom": kicad_export_bom,
    "kicad_render": kicad_render,
    # pcbnew bridge: creazione e ispezione diretta via API pcbnew
    "kicad_pcbnew_status": kicad_pcbnew_status,
    "kicad_libraries": kicad_libraries,
    "kicad_search_footprint": kicad_search_footprint,
    "kicad_new_board": kicad_new_board,
    "kicad_add_part": kicad_add_part,
    "kicad_read_board_full": kicad_read_board_full,
    # task #6, la parte conclusa: l'annullamento bidirezionale.
    #
    # Gli altri endpoint chiesti dalla stessa UI (zone, netclass, rules,
    # costruttori, bom, sync netlist, render 3d, export drill e pick&place)
    # restano fuori di qui finche' non hanno una funzione che li esegue: il
    # ponte pcbnew non offre ancora quelle primitive. Un nome citato in questo
    # dizionario senza un `def` che lo definisca non e' un tool mancante, e'
    # un `NameError` a livello di modulo: il modulo non si importa piu' e le
    # prove che lo importano non si raccolgono nemmeno. Il controllo che lo
    # impedisce sta in `tests/test_kicad_editor_contract.py`.
    "kicad_redo": kicad_redo,
}

#: Cosa tocca i file del progetto. Serve a `policy` per il cancello: le
#: scritture non entrano mai fra i permessi di lettura, e un profilo in sola
#: lettura puo' guardare una scheda senza poterla rovinare.
WRITE_TOOLS = {
    "kicad_placement_apply", "kicad_add_track", "kicad_add_route",
    "kicad_add_via", "kicad_add_footprint", "kicad_remove_footprint",
    "kicad_move_footprint", "kicad_rename_footprint", "kicad_delete_track",
    "kicad_delete_via", "kicad_set_board_outline", "kicad_set_pad_net",
    "kicad_undo", "kicad_redo", "kicad_export_gerbers", "kicad_export_bom", "kicad_render",
    # pcbnew bridge: questi due scrivono file di progetto
    "kicad_new_board", "kicad_add_part",
}
READ_TOOLS = set(ESECUTORI) - WRITE_TOOLS


#: Nomi che un modello usa al posto di quelli dichiarati, e perche'.
#:
#: Non sono gentilezze: sono i nomi che i NOSTRI tool restituiscono. Chi legge
#: `kicad_list_parts` riceve un campo `reference`, e alla chiamata dopo passa
#: `reference` a `kicad_pads` — che pero' dichiara `part`. E' successo al primo
#: run vero: l'agente non poteva leggere un pad, e senza pad non si instrada
#: niente. La coerenza fra cio' che un tool restituisce e cio' che il tool
#: dopo accetta e' responsabilita' di chi li progetta, non del modello.
_SINONIMI: Dict[str, Dict[str, str]] = {
    "kicad_pads": {"reference": "part", "designator": "part", "ref": "part"},
    "kicad_remove_footprint": {"part": "reference", "designator": "reference"},
    "kicad_add_footprint": {"ref": "reference", "designator": "reference",
                            "x": "x_mm", "y": "y_mm", "footprint": "library_id"},
    "kicad_add_track": {"width": "width_mm", "from": "start", "to": "end"},
    "kicad_add_route": {"width": "width_mm", "path": "points"},
    "kicad_add_via": {"position": "at", "size": "size_mm", "drill": "drill_mm"},
    "kicad_open": {"project": "path", "project_path": "path"},
    # Visto dal vivo: il modello scrive `current`, che e' il nome naturale in
    # italiano e in inglese. Il suffisso `_a` dichiara l'unita' ed e' utile a
    # chi legge lo schema, ma non e' il nome a cui si pensa scrivendo.
    "kicad_trace_width": {"current": "current_a", "amps": "current_a",
                          "corrente": "current_a", "delta_t": "delta_t_c",
                          "thickness": "thickness_oz"},
    "kicad_placement_apply": {"positions": "moves", "placements": "moves"},
    "kicad_render": {"path": "output_path", "format": "mode"},
    "kicad_export_gerbers": {"output": "output_dir", "dir": "output_dir"},
    "kicad_export_bom": {"output": "output_path", "path": "output_path"},
    # pcbnew bridge: il modello usa i nomi di campo che gli altri tool
    # restituiscono (reference, x, y, width, height, path, lib), non quelli
    # dichiarati qui. Senza queste voci ogni chiamata fallisce.
    "kicad_new_board": {"path": "percorso", "width": "larghezza_mm",
                        "height": "altezza_mm", "w": "larghezza_mm",
                        "h": "altezza_mm"},
    "kicad_add_part": {"nome": "riferimento", "ref": "riferimento",
                       "reference": "riferimento", "designator": "riferimento",
                       "x": "x_mm", "y": "y_mm", "lib": "libreria",
                       "library": "libreria", "value": "valore",
                       "side": "lato", "layer": "lato"},
    "kicad_read_board_full": {"path": "percorso"},
    "kicad_search_footprint": {"lib": "libreria", "library": "libreria",
                               "limit": "limite", "q": "query"},
}


def _normalizza(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Traduce i sinonimi noti nei nomi dichiarati dallo schema."""
    mappa = _SINONIMI.get(tool_name)
    if not mappa or not args:
        return args or {}
    tradotti = dict(args)
    for alias, canonico in mappa.items():
        if alias in tradotti and canonico not in tradotti:
            tradotti[canonico] = tradotti.pop(alias)
    return tradotti


def esegui(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Il punto d'ingresso che `loop.py` chiama. None se il tool non e' KiCad."""
    nome = str(tool_name or "").strip().lower()
    funzione = ESECUTORI.get(nome)
    if funzione is None:
        return None
    try:
        return funzione(**_normalizza(nome, args))
    except TypeError as exc:
        # L'errore elenca i parametri veri: dire solo «argomenti sbagliati»
        # lascia il modello a indovinare, e indovinare costa un turno per
        # tentativo.
        import inspect
        try:
            attesi = [p for p in inspect.signature(funzione).parameters]
        except (TypeError, ValueError):
            attesi = []
        return _esito(nome, False,
                      error=(f"Argomenti sbagliati per '{nome}': {exc}. "
                             f"I parametri accettati sono: {', '.join(attesi) or 'nessuno'}."),
                      accepted_parameters=attesi)
    except Exception as exc:
        log.exception("[tools] '%s' fallito", nome)
        return _esito(nome, False, error=str(exc))


# --- aggancio al kernel --------------------------------------------------------

#: Come un modello puo' chiamare un tool, quando non usa il nome dichiarato.
#: I sinonimi dei *parametri* stanno in `_SINONIMI`: questi sono i nomi del
#: tool, e sono le parole che un modello scrive pensando all'operazione.
#:
#: `pista` non c'e' di proposito: per EDA quella parola e' un filo di rame fra i
#: pin (`eda_wire`), e qui sarebbe una traccia sul PCB. Due provider che la
#: rivendicano lasciano vincere chi si registra prima, e l'altro cambia parola
#: sotto i piedi: `policy.registra_provider` rifiuta il secondo e lo dice nel log.
_ALIAS_TOOL: Dict[str, str] = {
    "instrada": "kicad_add_route",
    "verifica_pcb": "kicad_drc",
    "traccia": "kicad_add_track",
    "via": "kicad_add_via",
    "cerca_footprint": "kicad_search_footprint",
}


def provider() -> "ToolProvider":
    """Questi tool come li vede il kernel: schemi, esecutore, permessi, ruolo."""
    from core.harness.tool_providers import ToolProvider

    from . import roles as hw_roles
    from .tool_schemas import SCHEMI

    alias = {nome: nome for nome in ESECUTORI}
    alias.update({k: v for k, v in _ALIAS_TOOL.items() if v in ESECUTORI})
    return ToolProvider(
        id="sigma_kicad_lab",
        label="KiCad",
        schemas=tuple(SCHEMI),
        execute=esegui,
        read_only=frozenset(READ_TOOLS),
        write=frozenset(WRITE_TOOLS),
        aliases=alias,
        roles=(hw_roles.ROLE_KICAD_ENGINEER,),
    )


def registra() -> List[str]:
    """Aggancia tool e ruolo al kernel. Idempotente: si puo' richiamare.

    La chiama `handlers.register_harness_tools()` all'avvio, che e' l'hook con
    cui il module loader fa registrare un modulo. Chiamarla due volte sostituisce
    la registrazione precedente invece di duplicarla.
    """
    from core.harness import tool_providers
    return tool_providers.register(provider())

