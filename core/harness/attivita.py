# ==============================================================================
# core/harness/attivita.py — Cosa sta girando adesso, e chi lo ha chiesto
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Un posto solo dove sta scritto quali agenti stanno lavorando in questo momento.

Un ventaglio lanciato da riga di comando non compariva da nessuna parte nel
Developer Studio: chi guardava l'interfaccia vedeva un sistema fermo mentre due
agenti stavano riscrivendo il progetto. E la chat, se le si chiedeva qualcosa,
rispondeva come se nulla stesse accadendo — e poteva mettersi a modificare gli
stessi file.

La causa era che «cosa sta girando» non esisteva come dato. Ogni percorso
d'ingresso — la chat del Developer Studio, l'orchestratore, il ventaglio, una
curl — apriva il proprio run e lo teneva per se': lo stream degli eventi era
l'unica testimonianza, e vale solo per chi e' attaccato a quello stream.

**Il registro sta nel kernel e su disco.** Nel kernel perche' tutti e tre i
percorsi lo attraversano; su disco perche' la domanda «cosa sta girando» arriva
da una richiesta HTTP diversa da quella che sta lavorando, e spesso da una
scheda del browser aperta dopo.

**Una voce scaduta non e' una voce viva.** Un processo che muore non chiude la
propria riga. Senza una scadenza il registro direbbe per sempre che qualcosa
sta girando, e un registro che mente e' peggio di nessun registro: la chat
comincerebbe a rifiutarsi di lavorare per un agente che non c'e' piu'.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger("attivita")

#: Dopo quanto una voce senza battito viene considerata morta. Generoso: un
#: turno dell'agente su un modello locale puo' durare parecchio, e dichiarare
#: morto un run vivo e' l'errore peggiore dei due — farebbe sparire dalla UI
#: un lavoro che sta ancora scrivendo file.
SCADENZA_S = 300.0

#: Quante voci chiuse si conservano. Servono a rispondere «cosa e' appena
#: successo», che e' la seconda domanda che si fa chi apre la pagina.
STORICO_MASSIMO = 30

_lucchetto = threading.RLock()


def _percorso() -> Path:
    return Path(paths.var_dir()) / "attivita.json"


def _leggi() -> Dict[str, Any]:
    percorso = _percorso()
    if not percorso.is_file():
        return {"attive": {}, "storico": []}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"attive": {}, "storico": []}
    if not isinstance(dati, dict):
        return {"attive": {}, "storico": []}
    dati.setdefault("attive", {})
    dati.setdefault("storico", [])
    return dati


def _scrivi(dati: Dict[str, Any]) -> None:
    percorso = _percorso()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(percorso.parent),
            prefix=".attivita.", suffix=".tmp", delete=False,
        ) as f:
            json.dump(dati, f, indent=2, ensure_ascii=False)
            temporaneo = f.name
        os.replace(temporaneo, percorso)
    except OSError as exc:
        log.debug("[Attivita] salvataggio non riuscito: %s", exc)


def _viva(voce: Dict[str, Any], adesso: float) -> bool:
    return (adesso - float(voce.get("battito") or 0)) < SCADENZA_S


def apri(tipo: str, titolo: str, **dettagli: Any) -> str:
    """Dichiara che qualcosa e' partito. Ritorna l'id con cui aggiornarlo.

    `tipo` e' cio' che permette a chi legge di capire con chi ha a che fare:
    `chat`, `obiettivo` (i cinque ruoli), `ventaglio`, `voce` (un lavoratore
    del ventaglio).
    """
    identificatore = f"{tipo}_{uuid.uuid4().hex[:10]}"
    adesso = time.time()
    with _lucchetto:
        dati = _leggi()
        dati["attive"][identificatore] = {
            "id": identificatore,
            "tipo": str(tipo),
            "titolo": str(titolo or "")[:300],
            "iniziato": adesso,
            "battito": adesso,
            "pid": os.getpid(),
            **{k: v for k, v in dettagli.items() if v is not None},
        }
        _scrivi(dati)
    return identificatore


def aggiorna(identificatore: str, **campi: Any) -> None:
    """Batte il colpo e aggiorna cio' che e' cambiato.

    Il battito e' la parte che conta: senza, la voce scade mentre il lavoro
    prosegue e sparisce dall'interfaccia proprio quando c'e' piu' da vedere.
    """
    if not identificatore:
        return
    with _lucchetto:
        dati = _leggi()
        voce = dati["attive"].get(identificatore)
        if voce is None:
            return
        voce.update({k: v for k, v in campi.items() if v is not None})
        voce["battito"] = time.time()
        _scrivi(dati)


def chiudi(identificatore: str, esito: str = "", **campi: Any) -> None:
    """Toglie la voce dalle attive e ne conserva la traccia."""
    if not identificatore:
        return
    with _lucchetto:
        dati = _leggi()
        voce = dati["attive"].pop(identificatore, None)
        if voce is None:
            return
        voce.update({k: v for k, v in campi.items() if v is not None})
        voce["finito"] = time.time()
        voce["esito"] = str(esito or "")
        dati["storico"].insert(0, voce)
        del dati["storico"][STORICO_MASSIMO:]
        _scrivi(dati)


def attive() -> List[Dict[str, Any]]:
    """Cio' che sta girando davvero adesso, dal piu' recente.

    Le voci scadute vengono tolte qui e non da un processo a parte: chi
    domanda e' anche chi ha interesse a una risposta vera, e un registro che
    si pulisce solo quando qualcuno guarda e' esattamente sufficiente.
    """
    adesso = time.time()
    with _lucchetto:
        dati = _leggi()
        vive: Dict[str, Any] = {}
        morte: List[Dict[str, Any]] = []
        for identificatore, voce in dati["attive"].items():
            if _viva(voce, adesso):
                vive[identificatore] = voce
            else:
                morte.append(voce)
        if morte:
            for voce in morte:
                voce["finito"] = adesso
                voce["esito"] = "interrotto: nessun battito"
                dati["storico"].insert(0, voce)
            del dati["storico"][STORICO_MASSIMO:]
            dati["attive"] = vive
            _scrivi(dati)
        return sorted(vive.values(), key=lambda v: -float(v.get("iniziato") or 0))


def storico(limite: int = 10) -> List[Dict[str, Any]]:
    with _lucchetto:
        return list(_leggi()["storico"])[:max(0, int(limite))]


def stato() -> Dict[str, Any]:
    """La risposta completa per l'interfaccia e per la chat."""
    correnti = attive()
    return {
        "busy": bool(correnti),
        "count": len(correnti),
        "running": correnti,
        "recent": storico(10),
    }


def riga_per_la_chat() -> str:
    """Una riga da mettere nel contesto della chat, o stringa vuota.

    Serve a una cosa sola, e importante: la chat e gli agenti scrivono negli
    stessi file. Se la chat non sa che qualcuno sta lavorando, propone
    modifiche su un albero che sta cambiando sotto — e l'utente si ritrova due
    versioni diverse dello stesso file senza capire perche'.
    """
    correnti = attive()
    if not correnti:
        return ""
    righe = ["**Attenzione: in questo momento il Developer Studio sta lavorando.**"]
    for voce in correnti[:5]:
        durata = int(time.time() - float(voce.get("iniziato") or time.time()))
        descrizione = voce.get("titolo") or voce.get("tipo")
        pezzi = [f"- {voce.get('tipo')}: {descrizione} (da {durata}s"]
        if voce.get("workspace_root"):
            pezzi.append(f", su {voce['workspace_root']}")
        if voce.get("progress"):
            pezzi.append(f", {voce['progress']}")
        pezzi.append(")")
        righe.append("".join(pezzi))
    righe.append(
        "Prima di modificare file, tienine conto: un agente potrebbe stare "
        "scrivendo negli stessi. Se l'utente chiede una modifica, dillo."
    )
    return "\n".join(righe)
