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

GITHUB_REPO_URL = "https://github.com/Sigmanih/SigmaStudio-Manifesti"
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/Sigmanih/SigmaStudio-Manifesti/main"
GITHUB_API_CONTENTS_URL = "https://api.github.com/repos/Sigmanih/SigmaStudio-Manifesti/contents"

#: L'indice viaggia con il kernel: e' cio' che deve poter essere mostrato
#: anche senza rete e senza nulla installato.
CATALOG_DIR = Path(__file__).resolve().parent / "agents" / "catalog"
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
