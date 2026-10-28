# ==============================================================================
# core/manifests_catalog.py — Il catalogo degli agenti di serie
#
# Questo file conteneva 1.824 righe, di cui 1.793 erano venti Modelfile
# incollati dentro liste Python come stringhe multilinea: 51 KB di contenuto
# testuale trattato come codice sorgente, in terza copia dopo il repository
# SigmaStudio-Manifesti e la cartella manifesti/ locale.
#
# Del catalogo il kernel tiene solo cio' che gli serve davvero: i **metadati**.
# Servono per disegnare la Galleria dei Manifesti e per dire a un utente che un
# agente esiste ma non e' installato — due cose che devono funzionare prima di
# aver scaricato qualsiasi cosa, quindi non possono dipendere dalla rete.
#
# I **corpi** dei Modelfile non ci sono piu'. Appartengono a
# SigmaStudio-Manifesti e arrivano da li' al momento dell'installazione,
# atterrando in manifesti/. La conseguenza e' voluta: un agente che non e'
# installato non ha un prompt di sistema, e chi lo invoca riceve l'invito a
# installarlo invece di un comportamento a meta' servito da una copia di
# riserva che nessuno teneva aggiornata.
# ==============================================================================
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

GITHUB_REPO_URL = "https://github.com/Sigmanih/SigmaStudio-Ruoli"
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Sigmanih/SigmaStudio-Ruoli/main"
GITHUB_API_CONTENTS_URL = "https://api.github.com/repos/Sigmanih/SigmaStudio-Ruoli/contents"
#: L'indice del repository dice quali risorse (foto, modello 3D) ha ogni ruolo
GITHUB_INDEX_URL = f"{GITHUB_RAW_BASE_URL}/manifests_index.json"

#: Nomi ammessi per le risorse di un ruolo: arrivano dalla rete e finiscono su
#: disco, quindi niente percorsi liberi.
RISORSE_AMMESSE = {"immagine.jpg", "immagine.png", "modello.glb", "modello.json", "personaggio.glb"}

#: L'indice viaggia con il kernel: e' cio' che deve poter essere mostrato
#: anche senza rete e senza nulla installato. Il modulo sta in core/agents/:
#: con il vecchio "agents/catalog" il catalogo risultava vuoto.
CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
CATALOG_INDEX = CATALOG_DIR / "catalog.json"

_LOCK = threading.Lock()
_cache: Optional[List[Dict[str, Any]]] = None


def _leggi_catalogo() -> List[Dict[str, Any]]:
    """I metadati dei venti agenti di serie. Senza i corpi: quelli si scaricano."""
    try:
        indice = json.loads(CATALOG_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.error("[Manifesti] Catalogo non leggibile in %s: %s", CATALOG_INDEX, exc)
        return []

    return [dict(meta) for meta in indice]


def get_catalog() -> List[Dict[str, Any]]:
    """Il catalogo completo, caricato una volta sola."""
    global _cache
    with _LOCK:
        if _cache is None:
            _cache = _leggi_catalogo()
            log.info("[Manifesti] Catalogo caricato: %d agenti di serie.", len(_cache))
        return _cache


def reload_catalog() -> List[Dict[str, Any]]:
    """Rilegge l indice dal disco. Serve dopo aver modificato catalog.json."""
    global _cache
    with _LOCK:
        _cache = None
    return get_catalog()


class _CatalogoPigro(list):
    """`MANIFESTS_CATALOG` era una lista: per i chiamanti deve restarlo.

    Una lista vera caricata all'import costerebbe la lettura di ventuno file a
    ogni avvio, anche a chi il catalogo non lo guarda mai. Questa si riempie
    alla prima lettura e da quel momento e' una lista come le altre.
    """

    def _assicura(self) -> None:
        if not list.__len__(self):
            self.extend(get_catalog())

    def __iter__(self):
        self._assicura()
        return list.__iter__(self)

    def __len__(self):
        self._assicura()
        return list.__len__(self)

    def __getitem__(self, indice):
        self._assicura()
        return list.__getitem__(self, indice)

    def __contains__(self, elemento):
        self._assicura()
        return list.__contains__(self, elemento)

    def __bool__(self):
        self._assicura()
        return list.__len__(self) > 0

    def __repr__(self):
        self._assicura()
        return list.__repr__(self)


MANIFESTS_CATALOG = _CatalogoPigro()


def get_catalog_map() -> Dict[str, Dict[str, Any]]:
    """Un agente cercabile per id, per nome file, e per nome file minuscolo."""
    mappa: Dict[str, Dict[str, Any]] = {}
    for voce in get_catalog():
        mappa[voce["id"]] = voce
        mappa[voce["filename"]] = voce
        mappa[voce["filename"].lower()] = voce
    return mappa


def get_manifesto_by_id_or_filename(identifier: str) -> Optional[Dict[str, Any]]:
    """Trova un agente dal suo id o dal nome del suo file."""
    if not identifier:
        return None
    mappa = get_catalog_map()
    pulito = identifier.lower().strip()
    if pulito in mappa:
        return mappa[pulito]
    con_md = pulito if pulito.endswith(".md") else f"{pulito}.md"
    return mappa.get(con_md)


def _indice_del_repository() -> Optional[Dict[str, Dict[str, str]]]:
    """Risorse di ogni ruolo secondo l'indice online: piu' fresche del catalogo."""
    import urllib.request

    try:
        req = urllib.request.Request(GITHUB_INDEX_URL, headers={"User-Agent": "SigmaStudio/8.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            indice = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("[Ruoli] Indice del repository non raggiungibile: %s", exc)
        return None
    return {voce.get("id"): (voce.get("risorse") or {}) for voce in indice.get("manifests", [])}


def _risorse_dal_repository(ruolo_id: str) -> Optional[Dict[str, str]]:
    indice = _indice_del_repository()
    return None if indice is None else indice.get(ruolo_id, {})


def installa_risorse(ruolo_id: str, cartella_ruoli: Path, voce_catalogo: Optional[Dict[str, Any]] = None,
                     risorse: Optional[Dict[str, str]] = None) -> List[str]:
    """Scarica foto, modello 3D e dettagli del ruolo in <ruoli>/<id>/.

    Le risorse sono facoltative: un ruolo senza modello si installa lo stesso
    e la plancia gli lascia l'ufficiale procedurale. Ritorna i file scritti.
    `risorse` evita di rileggere l'indice online quando lo si e' gia' letto.
    """
    import urllib.request

    if risorse is None:
        risorse = _risorse_dal_repository(ruolo_id)
    if risorse is None:
        risorse = (voce_catalogo or {}).get("risorse") or {}
    if not risorse:
        return []

    dest = cartella_ruoli / ruolo_id
    scritti: List[str] = []
    for relativo in risorse.values():
        nome = Path(str(relativo)).name
        if nome not in RISORSE_AMMESSE or str(relativo) != f"{ruolo_id}/{nome}":
            log.warning("[Ruoli] Risorsa ignorata per %s: %s", ruolo_id, relativo)
            continue
        try:
            req = urllib.request.Request(f"{GITHUB_RAW_BASE_URL}/{relativo}", headers={"User-Agent": "SigmaStudio/8.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                dati = resp.read()
        except OSError as exc:
            log.warning("[Ruoli] %s non scaricata: %s", relativo, exc)
            continue
        dest.mkdir(parents=True, exist_ok=True)
        (dest / nome).write_bytes(dati)
        scritti.append(nome)
    return scritti


def rimuovi_risorse(ruolo_id: str, cartella_ruoli: Path) -> None:
    """Toglie la cartella delle risorse: un ruolo disinstallato non lascia il modello."""
    import shutil

    dest = cartella_ruoli / ruolo_id
    # Private/ contiene i ruoli personali: non e' mai la cartella di un ruolo
    if not ruolo_id or ruolo_id.lower() == "private" or not dest.is_dir():
        return
    if any(f.name not in RISORSE_AMMESSE for f in dest.iterdir()):
        log.warning("[Ruoli] %s contiene file non suoi: la cartella resta", dest)
        return
    shutil.rmtree(dest)


def aggiorna_risorse_installate(cartella_ruoli: Path, solo_mancanti: bool = True) -> Dict[str, List[str]]:
    """Porta foto e modelli ai ruoli gia' installati, senza reinstallarli.

    I ruoli installati prima che il repository avesse le risorse ne restano
    senza: la plancia mostrerebbe solo ufficiali procedurali. Con
    `solo_mancanti` non si riscarica cio' che c'e' gia'.
    """
    indice = _indice_del_repository()
    mappa = get_catalog_map()
    esito: Dict[str, List[str]] = {}
    for md in sorted(cartella_ruoli.glob("*.md")):
        ruolo_id = md.stem
        voce = mappa.get(ruolo_id) or mappa.get(md.name.lower())
        risorse = (indice or {}).get(ruolo_id) if indice is not None else (voce or {}).get("risorse")
        if not risorse:
            continue
        if solo_mancanti:
            risorse = {k: v for k, v in risorse.items()
                       if not (cartella_ruoli / ruolo_id / Path(str(v)).name).is_file()}
            if not risorse:
                continue
        scritti = installa_risorse(ruolo_id, cartella_ruoli, voce, risorse=risorse)
        if scritti:
            esito[ruolo_id] = scritti
            log.info("[Ruoli] %s: risorse aggiornate %s", ruolo_id, scritti)
    return esito


if __name__ == "__main__":
    # python -m core.agents.manifests_catalog: scarica le risorse mancanti dei ruoli installati
    from core import paths

    risultato = aggiorna_risorse_installate(paths.roles_dir())
    log.info("[Ruoli] risorse scaricate per %d ruoli", len(risultato))
