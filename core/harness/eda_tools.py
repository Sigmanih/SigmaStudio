# ==============================================================================
# core/harness/eda_tools.py — I tool con cui un agente disegna un circuito
# ==============================================================================
"""Il vocabolario EDA dell'harness: cercare, piazzare, collegare, verificare.

L'harness non sa parlare MCP — i tool di un agente sono la lista in
`tool_schema.py`, smistata in `loop.py`. Questi sono l'estensione EDA di quella
lista, e stanno in un file loro perche' `loop.py` e' gia' lungo quattromila
righe: la' dentro va una sola diramazione che delega qui.

**I pin si indirizzano per nome.** `{"part": "U3", "pin": "VOUT"}`, non
`{"pinNumber": "1"}`. E' la decisione che decide se un modello ce la fa: il
numero di pin di VOUT e' un dato che il modello dovrebbe ricordare fra due
chiamate, e ricordarlo sbagliato produce un circuito che sembra giusto. Il
nome invece sta scritto sul simbolo, e la risoluzione la fa questo file — in
modo deterministico, con un errore esplicito quando il nome non esiste.

Ogni tool passa dall'hub MCP, mai dal transport: e' li' che sta il cancello di
governance, e un modulo che lo scavalca e' un modulo che decide da solo cosa
puo' scrivere.
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

#: Il progetto EasyEDA a fuoco, risolto una volta e tenuto da parte. L'agente
#: non deve conoscere un uuid: e' rumore che occupa contesto e che sbaglierebbe.
_progetto: Dict[str, Any] = {"id": "", "nome": "", "quando": 0.0}
_CACHE_SECONDI = 120.0

#: Mappa pin per componente, ricostruita a ogni piazzamento.
_pin_cache: Dict[str, List[Dict[str, Any]]] = {}

#: Gli uuid che una ricerca ha davvero restituito in questa sessione. Piazzare
#: e' l'unico tool che crea qualcosa dal nulla, ed e' quindi l'unico dove un
#: identificativo sbagliato non produce un errore ma un componente estraneo sul
#: foglio. Un agente a cui la ricerca fallisce ripetutamente prova a procedere
#: comunque — e' successo al primo run: sono finiti sullo schematico un
#: microcontrollore e due regolatori che non c'entravano col compito, senza che
#: nessuna chiamata fallisse. Il vincolo e' che si piazza solo cio' che si e'
#: prima trovato.
_uuid_trovati: set = set()


class EdaError(RuntimeError):
    """Il bridge EasyEDA non ha potuto fare quel che era stato chiesto."""


def _esito(nome: str, ok: bool, **extra: Any) -> Dict[str, Any]:
    return {"tool": nome, "success": ok, **extra}


def _chiama(tool: str, args: Dict[str, Any] = None, scrittura: bool = False,
            tentativi: int = 1) -> Dict[str, Any]:
    """Un tool EasyEDA attraverso l'hub MCP.

    `tentativi` vale piu' di uno solo per le letture. Ritentare una scrittura
    dopo un errore di trasporto e' pericoloso: l'errore puo' essere arrivato
    *dopo* che EasyEDA ha applicato la modifica, e il secondo tentativo la
    applicherebbe una seconda volta. Un componente piazzato due volte e' un
    problema che si scopre in fase di montaggio.
    """
    from core.modules.sigma_eda_lab import bridge

    payload = dict(args or {})
    if scrittura:
        payload["confirmWrite"] = True
        tentativi = 1

    ultimo = None
    for i in range(max(1, tentativi)):
        try:
            return bridge.call(tool, payload)
        except Exception as exc:
            ultimo = exc
            if i + 1 < tentativi:
                time.sleep(1.0 + i)
    raise ultimo


def _project_id(force: bool = False) -> str:
    """L'uuid del progetto aperto, chiesto a EasyEDA e tenuto in cache."""
    if not force and _progetto["id"] and (time.time() - _progetto["quando"]) < _CACHE_SECONDI:
        return _progetto["id"]

    risposta = _chiama("easyeda_api_call",
                       {"path": "DMT_Project.getCurrentProjectInfo", "args": []},
                       scrittura=True)
    info = risposta.get("result") or {}
    if not info:
        raise EdaError(
            "Nessun progetto aperto in EasyEDA Pro. Aprine uno prima di disegnare."
        )
    _progetto.update({"id": info.get("uuid", ""),
                      "nome": info.get("friendlyName", ""),
                      "quando": time.time()})
    return _progetto["id"]


# --- lettura -------------------------------------------------------------------

def eda_status() -> Dict[str, Any]:
    """Il bridge e' vivo? Che progetto e' aperto? Quanti pezzi ci sono?"""
    try:
        salute = _chiama("easyeda_health_check")
        if not salute.get("bridge_connected"):
            return _esito("eda_status", False,
                          error="Il bridge EasyEDA non e' collegato: apri EasyEDA Pro, "
                                "estensione MCP Bridge, Connect.",
                          bridge_connected=False)
        pid = _project_id(force=True)
        pezzi = _chiama("easyeda_schematic_components", {"projectId": pid})
        return _esito("eda_status", True,
                      bridge_connected=True,
                      project=_progetto["nome"], project_id=pid,
                      components=pezzi.get("total", 0),
                      profile=salute.get("profile"))
    except Exception as exc:
        return _esito("eda_status", False, error=str(exc))


def eda_search_part(query: str, limit: int = 6) -> Dict[str, Any]:
    """Cerca un componente in libreria. Restituisce cio' che serve per piazzarlo."""
    try:
        pid = _project_id()
        # La prima ricerca dopo una connessione cade sempre: il canale va
        # scaldato. E' un difetto noto del server, non della richiesta.
        try:
            _chiama("easyeda_health_check")
        except Exception:
            pass
        # La prima ricerca di ogni processo cade con un flusso SSE troncato. E'
        # un difetto del server, non della richiesta: si ritenta.
        risposta = _chiama("easyeda_schematic_search_device",
                           {"key": str(query), "itemsOfPage": max(1, min(int(limit), 20))},
                           tentativi=3)
        for d in (risposta.get("devices") or []):
            if d.get("uuid"):
                _uuid_trovati.add(str(d["uuid"]))
        trovati = [{
            "name": d.get("name"),
            "uuid": d.get("uuid"),
            "library_uuid": d.get("libraryUuid"),
            "footprint": d.get("footprintName"),
            "description": (d.get("description") or "")[:140],
        } for d in (risposta.get("devices") or [])]
        return _esito("eda_search_part", True, query=query,
                      total=risposta.get("total", len(trovati)), results=trovati,
                      project_id=pid)
    except Exception as exc:
        messaggio = str(exc)
        if "SSE" in messaggio or "Stream" in messaggio:
            # Verificato dal vivo: alcune query rompono la serializzazione della
            # risposta lato server, sempre le stesse, a qualunque dimensione di
            # pagina. Non e' un guasto del bridge e ritentare non serve.
            messaggio = (
                f"La libreria non riesce a restituire i risultati per '{query}' "
                "(difetto del server, dipendente dalla query). Riprova con un "
                "altro termine: il codice esatto del produttore, o una sigla "
                "piu' corta. Altre ricerche continuano a funzionare."
            )
        return _esito("eda_search_part", False, query=query, error=messaggio)


def eda_list_parts() -> Dict[str, Any]:
    """I pezzi gia' sul foglio, col loro identificativo e la loro posizione."""
    try:
        pid = _project_id()
        risposta = _chiama("easyeda_schematic_components", {"projectId": pid})
        pezzi = [{"id": c.get("primitiveId"), "device": c.get("deviceName"),
                  "designator": c.get("designator") or "", "x": c.get("x"), "y": c.get("y")}
                 for c in (risposta.get("components") or [])]
        return _esito("eda_list_parts", True, total=len(pezzi), parts=pezzi)
    except Exception as exc:
        return _esito("eda_list_parts", False, error=str(exc))


def eda_pins(part: str) -> Dict[str, Any]:
    """La mappa dei pin di un pezzo: nome, numero, coordinate.

    Va chiamato prima di collegare: e' cio' che rende `eda_connect` verificabile
    invece che una scommessa sui numeri.
    """
    try:
        pid = _project_id()
        risposta = _chiama("easyeda_schematic_component_pins",
                           {"projectId": pid, "primitiveId": str(part)})
        pins = risposta.get("pins") or []
        _pin_cache[str(part)] = pins
        return _esito("eda_pins", True, part=part, total=len(pins),
                      pins=[{"number": p.get("pinNumber"), "name": p.get("pinName"),
                             "x": p.get("x"), "y": p.get("y")} for p in pins])
    except Exception as exc:
        return _esito("eda_pins", False, part=part, error=str(exc))


def eda_verify() -> Dict[str, Any]:
    """Netlist ed ERC nativo. E' la prova che un collegamento e' davvero tale."""
    try:
        pid = _project_id()
        d = _chiama("easyeda_schematic_validate_netlist", {"projectId": pid})
        erc = d.get("native_erc") or {}
        aperti = d.get("floating_pins") or []
        return _esito("eda_verify", True,
                      valid=bool(d.get("valid")),
                      nets=d.get("total_nets", 0),
                      floating_pins=len(aperti),
                      floating_detail=[{"part": p.get("designator") or p.get("primitiveId"),
                                        "pin": p.get("pinNumber")} for p in aperti[:40]],
                      wires_without_net=len(d.get("wires_without_netlist") or []),
                      erc_errors=erc.get("error_count", 0),
                      erc_warnings=erc.get("warning_count", 0))
    except Exception as exc:
        return _esito("eda_verify", False, error=str(exc))


def eda_capture(path: str = "") -> Dict[str, Any]:
    """Salva un'immagine del foglio, cosi' il lavoro si puo' guardare."""
    try:
        pid = _project_id()
        from core.mcp.mcp_hub import mcp_hub
        esito = mcp_hub.execute_tool("easyeda_canvas_capture", {})
        if esito.get("status") != "ok":
            return _esito("eda_capture", False,
                          error=esito.get("error") or esito.get("status"))
        for parte in (esito.get("result") or {}).get("content", []):
            if parte.get("type") == "image":
                destinazione = path or os.path.join("var", "eda", f"foglio-{int(time.time())}.png")
                os.makedirs(os.path.dirname(destinazione) or ".", exist_ok=True)
                dati = base64.b64decode(parte["data"])
                with open(destinazione, "wb") as fh:
                    fh.write(dati)
                return _esito("eda_capture", True, path=destinazione,
                              bytes=len(dati), project_id=pid)
        return _esito("eda_capture", False, error="Il bridge non ha restituito un'immagine.")
    except Exception as exc:
        return _esito("eda_capture", False, error=str(exc))


# --- scrittura -----------------------------------------------------------------

def eda_place_part(uuid: str, library_uuid: str, x: float, y: float,
                   rotation: int = 0) -> Dict[str, Any]:
    """Piazza sul foglio un componente trovato con `eda_search_part`."""
    try:
        if str(uuid) not in _uuid_trovati:
            return _esito(
                "eda_place_part", False,
                error=(f"L'uuid '{uuid}' non proviene da nessuna ricerca di questa "
                       "sessione. Chiama prima eda_search_part e usa l'uuid che "
                       "ti restituisce. Se la ricerca continua a fallire, fermati "
                       "e dillo: non si piazza un componente che non si e' trovato."),
                hint="eda_search_part")
        pid = _project_id()
        _chiama("easyeda_schematic_place_component", {
            "projectId": pid,
            "deviceItem": {"uuid": str(uuid), "libraryUuid": str(library_uuid)},
            "x": float(x), "y": float(y), "rotation": int(rotation),
            "addIntoBom": True, "addIntoPcb": True,
            "checkPlacementCollision": True, "collisionRadius": 15,
        }, scrittura=True)

        # Si rilegge subito: il piazzamento non restituisce l'identificativo, e
        # senza quello l'agente non potrebbe collegare cio' che ha appena messo.
        elenco = _chiama("easyeda_schematic_components", {"projectId": pid})
        messo = None
        for c in (elenco.get("components") or []):
            if abs((c.get("x") or 0) - float(x)) < 1 and abs((c.get("y") or 0) - float(y)) < 1:
                messo = c
                break
        if messo is None:
            return _esito("eda_place_part", False,
                          error="Piazzato ma non ritrovato alla posizione chiesta: "
                                "controlla con eda_list_parts.")
        return _esito("eda_place_part", True, id=messo.get("primitiveId"),
                      device=messo.get("deviceName"), x=messo.get("x"), y=messo.get("y"),
                      total_on_sheet=elenco.get("total"))
    except Exception as exc:
        return _esito("eda_place_part", False, error=str(exc))


def _risolvi(part: str, riferimento: str) -> str:
    """Da nome o numero di pin al numero vero. Solleva se il nome non esiste."""
    riferimento = str(riferimento).strip()
    pins = _pin_cache.get(str(part))
    if pins is None:
        pid = _project_id()
        pins = (_chiama("easyeda_schematic_component_pins",
                        {"projectId": pid, "primitiveId": str(part)}).get("pins") or [])
        _pin_cache[str(part)] = pins

    for p in pins:
        if str(p.get("pinNumber")) == riferimento:
            return riferimento
    for p in pins:
        if (p.get("pinName") or "").upper() == riferimento.upper():
            return str(p.get("pinNumber"))

    disponibili = ", ".join(sorted({(p.get("pinName") or "?") for p in pins}))[:300]
    raise EdaError(f"Il pezzo '{part}' non ha un pin '{riferimento}'. Disponibili: {disponibili}")


def eda_connect(net: str, pins: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Collega dei pin sulla stessa net. I pin si indicano per nome o per numero.

    Esempio: net "VCC", pins [{"part": "<id>", "pin": "VDD"}, {"part": "<id>", "pin": "1"}].
    """
    try:
        pid = _project_id()
        risolti, errori = [], []
        for voce in (pins or []):
            part = str(voce.get("part") or voce.get("primitiveId") or "")
            rif = voce.get("pin") or voce.get("pinNumber") or voce.get("pinName")
            if not part or rif is None:
                errori.append(f"voce incompleta: {voce}")
                continue
            try:
                risolti.append({"primitiveId": part, "pinNumber": _risolvi(part, rif)})
            except EdaError as exc:
                errori.append(str(exc))
        if errori:
            return _esito("eda_connect", False, net=net, error=" | ".join(errori[:4]))
        if not risolti:
            return _esito("eda_connect", False, net=net, error="Nessun pin indicato.")

        _chiama("easyeda_schematic_connect_pins_by_net",
                {"projectId": pid, "netName": str(net), "pins": risolti}, scrittura=True)
        return _esito("eda_connect", True, net=net, pins=len(risolti))
    except Exception as exc:
        return _esito("eda_connect", False, net=net, error=str(exc))


def eda_wire(net: str, points: List[Dict[str, float]],
             color: str = "") -> Dict[str, Any]:
    """Disegna una pista come spezzata fra due o piu' punti, taggata con la net."""
    try:
        pid = _project_id()
        pts = [{"x": float(p["x"]), "y": float(p["y"])} for p in (points or [])]
        if len(pts) < 2:
            return _esito("eda_wire", False, net=net,
                          error="Servono almeno due punti per una pista.")
        args = {"projectId": pid, "netName": str(net), "points": pts, "lineWidth": 1.5}
        if color:
            args["color"] = color
        _chiama("easyeda_schematic_add_wire", args, scrittura=True)
        return _esito("eda_wire", True, net=net, points=len(pts))
    except Exception as exc:
        return _esito("eda_wire", False, net=net, error=str(exc))


def eda_note(text: str, x: float, y: float, size: float = 10,
             color: str = "#475569") -> Dict[str, Any]:
    """Scrive una nota sul foglio. Serve a lasciare per iscritto una decisione."""
    try:
        pid = _project_id()
        _chiama("easyeda_schematic_add_text",
                {"projectId": pid, "x": float(x), "y": float(y),
                 "content": str(text)[:400], "fontSize": float(size), "color": color},
                scrittura=True)
        return _esito("eda_note", True, x=x, y=y)
    except Exception as exc:
        return _esito("eda_note", False, error=str(exc))


def eda_save() -> Dict[str, Any]:
    """Salva il progetto. Da chiamare quando un pezzo di lavoro e' concluso."""
    try:
        pid = _project_id()
        d = _chiama("easyeda_project_save", {"projectId": pid}, scrittura=True)
        return _esito("eda_save", bool(d.get("success")), saved_at=d.get("saved_at"))
    except Exception as exc:
        return _esito("eda_save", False, error=str(exc))


# --- strumenti PCB ------------------------------------------------------------

def eda_pcb_drc() -> Dict[str, Any]:
    """DRC nativo sul PCB: verifica piste disconnesse, cortocircuiti e distanze."""
    try:
        pid = _project_id()
        from core.modules.sigma_eda_lab import routing
        report = routing.run_drc_inspection(pid)
        return _esito("eda_pcb_drc", report["success"], **report)
    except Exception as exc:
        return _esito("eda_pcb_drc", False, error=str(exc))


def eda_pcb_unrouted() -> Dict[str, Any]:
    """Elenca tutte le net e i pad ancora da sbroccare sul PCB."""
    try:
        pid = _project_id()
        from core.modules.sigma_eda_lab import routing
        summary = routing.get_unrouted_summary(pid)
        return _esito("eda_pcb_unrouted", True, **summary)
    except Exception as exc:
        return _esito("eda_pcb_unrouted", False, error=str(exc))


def eda_pcb_route_net(net: str, width_mil: float = 10.0, layer: int = 1) -> Dict[str, Any]:
    """Traccia le piste di rame a 45 gradi fra tutti i pad di una net."""
    try:
        pid = _project_id()
        from core.modules.sigma_eda_lab import routing
        res = routing.route_pads_of_net(pid, str(net), width_mil=float(width_mil), layer=int(layer))
        return _esito("eda_pcb_route_net", res.get("success", False), **res)
    except Exception as exc:
        return _esito("eda_pcb_route_net", False, error=str(exc))


def eda_pcb_add_via(x: float, y: float, net: str = "AGND", hole_mil: float = 12.0,
                    diameter_mil: float = 24.0) -> Dict[str, Any]:
    """Piazza un via di rame per cambiare layer o connettere il piano di massa."""
    try:
        pid = _project_id()
        res = _chiama("easyeda_pcb_add_via", {
            "projectId": pid,
            "x": float(x),
            "y": float(y),
            "holeSize": float(hole_mil),
            "outerDiameter": float(diameter_mil),
            "netName": str(net),
        }, scrittura=True)
        return _esito("eda_pcb_add_via", res.get("success", True),
                      primitive_id=res.get("primitiveId"), net=net, x=x, y=y)
    except Exception as exc:
        return _esito("eda_pcb_add_via", False, error=str(exc))


def eda_pcb_outline(width_mm: float = 100.0, height_mm: float = 80.0) -> Dict[str, Any]:
    """Crea o assicura il contorno scheda rettangolare chiuso sul layer Board Outline (11)."""
    try:
        pid = _project_id()
        from core.modules.sigma_eda_lab import bridge
        res = bridge.create_board_outline(pid, width_mm=float(width_mm), height_mm=float(height_mm))
        return _esito("eda_pcb_outline", res.get("success", False), **res)
    except Exception as exc:
        return _esito("eda_pcb_outline", False, error=str(exc))


def eda_pcb_route_all(default_width_mil: float = 10.0, power_width_mil: float = 20.0) -> Dict[str, Any]:
    """Instrada automaticamente a 45 gradi tutte le net non ancora collegate sul PCB."""
    try:
        pid = _project_id()
        from core.modules.sigma_eda_lab import routing
        res = routing.route_all_unrouted(pid, default_width_mil=float(default_width_mil),
                                         power_width_mil=float(power_width_mil))
        return _esito("eda_pcb_route_all", res.get("success", False), **res)
    except Exception as exc:
        return _esito("eda_pcb_route_all", False, error=str(exc))


def eda_pcb_mounting_holes(margin_mm: float = 5.0, hole_dia_mm: float = 3.2,
                           pad_dia_mm: float = 6.0) -> Dict[str, Any]:
    """Posiziona 4 fori di fissaggio M3 nei quattro angoli della scheda."""
    try:
        pid = _project_id()
        from core.modules.sigma_eda_lab import routing
        res = routing.add_mounting_holes(pid, margin_mm=float(margin_mm),
                                         hole_dia_mm=float(hole_dia_mm),
                                         pad_dia_mm=float(pad_dia_mm))
        return _esito("eda_pcb_mounting_holes", res.get("success", False), **res)
    except Exception as exc:
        return _esito("eda_pcb_mounting_holes", False, error=str(exc))


def eda_export_gerbers() -> Dict[str, Any]:
    """Esporta i file Gerber per la produzione e fabbricazione JLCPCB del PCB."""
    try:
        pid = _project_id()
        res = _chiama("easyeda_export_gerbers", {"projectId": pid})
        return _esito("eda_export_gerbers", res.get("success", True), **res)
    except Exception as exc:
        return _esito("eda_export_gerbers", False, error=str(exc))


#: Nome canonico -> funzione. `loop.py` importa solo questo.
ESECUTORI = {
    "eda_status": eda_status,
    "eda_search_part": eda_search_part,
    "eda_list_parts": eda_list_parts,
    "eda_pins": eda_pins,
    "eda_verify": eda_verify,
    "eda_capture": eda_capture,
    "eda_place_part": eda_place_part,
    "eda_connect": eda_connect,
    "eda_wire": eda_wire,
    "eda_note": eda_note,
    "eda_save": eda_save,
    "eda_pcb_drc": eda_pcb_drc,
    "eda_pcb_unrouted": eda_pcb_unrouted,
    "eda_pcb_route_net": eda_pcb_route_net,
    "eda_pcb_route_all": eda_pcb_route_all,
    "eda_pcb_add_via": eda_pcb_add_via,
    "eda_pcb_outline": eda_pcb_outline,
    "eda_pcb_mounting_holes": eda_pcb_mounting_holes,
    "eda_export_gerbers": eda_export_gerbers,
}

#: Quelli che toccano il progetto. Servono a `policy` per sapere cosa e' scrittura.
EDA_WRITE_TOOLS = {
    "eda_place_part", "eda_connect", "eda_wire", "eda_note", "eda_save",
    "eda_pcb_route_net", "eda_pcb_route_all", "eda_pcb_add_via",
    "eda_pcb_outline", "eda_pcb_mounting_holes",
}
EDA_READ_TOOLS = set(ESECUTORI) - EDA_WRITE_TOOLS


def esegui(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Il punto d'ingresso che `loop.py` chiama. None se il tool non e' EDA."""
    funzione = ESECUTORI.get(str(tool_name or "").strip().lower())
    if funzione is None:
        return None
    try:
        return funzione(**(args or {}))
    except TypeError as exc:
        return _esito(tool_name, False,
                      error=f"Argomenti sbagliati per '{tool_name}': {exc}")
    except Exception as exc:
        log.exception("[eda_tools] '%s' fallito", tool_name)
        return _esito(tool_name, False, error=str(exc))
