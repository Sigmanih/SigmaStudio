# ==============================================================================
# core/first_run.py — Che Sigma Studio funzioni appena installato
#
# La promessa e' che chi scarica Sigma Studio, su qualunque hardware, apra la
# chat e ottenga una risposta. Finora non era cosi': l'installazione portava
# llama-cpp-python e basta, e una persona con una CPU senza AVX2 ha aperto la
# chat e ha letto uno STATUS_ILLEGAL_INSTRUCTION travestito da errore di
# memoria.
#
# Servono tre cose, in quest'ordine, e l'ordine e' la parte importante:
#
#   1. un runtime che parta su questa macchina
#   2. la verifica che parta davvero
#   3. un modello da eseguirci
#
# Scaricare prima il modello significa far scaricare mezzo giga a una macchina
# che poi non riesce a eseguirlo — cioe' ripetere l'esperienza che questo
# modulo esiste per togliere. Il runtime costa 44 MB nel caso peggiore, il
# modello dieci volte tanto: si paga prima il poco che dice se il molto ha
# senso.
#
# Il modello predefinito e' un dato, non codice: cambiarlo quando Sigma sara'
# pronto e' modificare un file JSON.
# ==============================================================================
from __future__ import annotations

import json
import os
import threading
from typing import Any, Callable, Dict, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

_LOCK = threading.Lock()

#: Chi non vuole che il primo avvio scarichi niente lo dice qui. Vale anche per
#: le installazioni automatiche e per le macchine a consumo misurato.
_ENV_SALTA = "SIGMA_SKIP_FIRST_RUN"


def stato_file():
    return paths.var_dir() / "first_run.json"


def modello_predefinito_file():
    return paths.config_dir() / "default_model.json"


#: Cosa scaricare se nessuno ha detto altro. Piccolo di proposito: deve girare
#: su una scheda da 8 GB senza GPU come su una workstation, e il primo contatto
#: con l'applicazione non puo' essere un'attesa di venti minuti.
MODELLO_PREDEFINITO = {
    "repo": "sigmanih/Qwen3-0.6B-GGUF-Q4_K_S",
    "nome_locale": "sigmanih--Qwen3-0.6B-GGUF-Q4_K_S",
    "quantizzazione": "Q4_K_S",
    "dimensione_mb": 460,
    "descrizione": "Assistente di partenza: piccolo, veloce, gira ovunque.",
}


# ==============================================================================
# STATO
# ==============================================================================

def _leggi_stato() -> Dict[str, Any]:
    percorso = stato_file()
    if not percorso.exists():
        return {}
    try:
        return json.loads(percorso.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _scrivi_stato(stato: Dict[str, Any]) -> None:
    percorso = stato_file()
    paths.ensure(percorso.parent)
    percorso.write_text(json.dumps(stato, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def modello_predefinito() -> Dict[str, Any]:
    """Il modello di partenza, sovrascrivibile senza toccare il codice."""
    percorso = modello_predefinito_file()
    if percorso.exists():
        try:
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            if isinstance(dati, dict) and dati.get("repo"):
                return {**MODELLO_PREDEFINITO, **dati}
        except (OSError, ValueError) as exc:
            log.warning("[FirstRun] default_model.json illeggibile: %s", exc)
    return dict(MODELLO_PREDEFINITO)


def gia_fatto() -> bool:
    return bool(_leggi_stato().get("completato"))


# ==============================================================================
# I TRE PASSI
# ==============================================================================

def _runtime_pronto(avvisa: Callable[[str], None], scarica: bool) -> Dict[str, Any]:
    """Passo 1 e 2: un runtime installato, e che parta davvero su questa CPU."""
    from core.engine.llama_runtime import install, installed_server
    from core.engine.runtime_probe import check_runtime, illegal_instruction_report

    if installed_server() is None:
        if not scarica:
            return {"ok": False, "motivo": "runtime_assente",
                    "dettaglio": "Runtime GGUF non installato."}
        avvisa("Installo il runtime GGUF (una volta sola, ~44 MB)...")
        esito = install(progress=avvisa)
        if not esito.get("success"):
            return {"ok": False, "motivo": "runtime_non_installabile",
                    "dettaglio": esito.get("error", "")}

    # La verifica e' separata dall'installazione perche' risponde a un'altra
    # domanda: non "c'e' il file" ma "questo processore esegue quel codice".
    prova = check_runtime(refresh=True)
    if not prova.get("ok"):
        if prova.get("motivo") == "istruzione_illegale":
            return {"ok": False, "motivo": "istruzione_illegale",
                    "dettaglio": illegal_instruction_report(prova.get("cpu"))}
        return {"ok": False, "motivo": prova.get("motivo"),
                "dettaglio": prova.get("dettaglio", "")}

    return {"ok": True}


def _modello_pronto(avvisa: Callable[[str], None], scarica: bool) -> Dict[str, Any]:
    """Passo 3: un modello da eseguire, se non ce n'e' gia' uno."""
    from core.model_paths import list_model_dirs

    presenti = list_model_dirs()
    if presenti:
        return {"ok": True, "gia_presente": True, "modelli": len(presenti)}

    if not scarica:
        return {"ok": False, "motivo": "nessun_modello",
                "dettaglio": "Nessun modello installato."}

    scelto = modello_predefinito()
    avvisa(f"Scarico il modello di partenza {scelto['repo']} "
           f"(~{scelto['dimensione_mb']} MB)...")
    # Il download lo fa il Model Hub, che e' un modulo: se non e' installato
    # non si scarica niente e lo si dice, invece di riscrivere qui un
    # downloader che sarebbe la seconda copia dello stesso lavoro.
    try:
        from core.modules.sigma_model_hub.backend.downloader_engine import (
            downloader_manager)
    except Exception as exc:
        return {"ok": False, "motivo": "hub_assente",
                "dettaglio": f"Model Hub non disponibile: {exc}"}

    try:
        esito = downloader_manager.start_repo_download(scelto["repo"])
    except Exception as exc:
        return {"ok": False, "motivo": "download_fallito", "dettaglio": str(exc)}

    return {"ok": True, "avviato": esito if isinstance(esito, dict) else True,
            "repo": scelto["repo"]}


# ==============================================================================
# INGRESSO
# ==============================================================================

def prepare(progress: Optional[Callable[[str], None]] = None,
            scarica: bool = True, forza: bool = False) -> Dict[str, Any]:
    """Porta questa installazione allo stato "apri la chat e funziona".

    `scarica=False` non scarica niente e si limita a dire a che punto siamo:
    e' cio' che serve a `sigma_server.py --check` e a una diagnosi.
    """
    def avvisa(testo: str) -> None:
        log.info("[FirstRun] %s", testo)
        if progress:
            progress(testo)

    if os.environ.get(_ENV_SALTA, "").strip():
        return {"saltato": True, "motivo": f"{_ENV_SALTA} impostata"}

    with _LOCK:
        stato = _leggi_stato()
        if stato.get("completato") and not forza:
            return {"gia_completato": True, **stato}

        passi: Dict[str, Any] = {}

        passi["runtime"] = _runtime_pronto(avvisa, scarica)
        if not passi["runtime"]["ok"]:
            # Senza runtime non ha senso scaricare mezzo giga di pesi: e'
            # l'ordine che questo modulo esiste per rispettare.
            avvisa(f"Runtime non pronto: {passi['runtime'].get('motivo')}. "
                   "Il modello non viene scaricato.")
            return {"completato": False, "passi": passi}

        passi["modello"] = _modello_pronto(avvisa, scarica)

        completato = all(p.get("ok") for p in passi.values())
        if completato and scarica:
            _scrivi_stato({"completato": True, "passi": passi})
            avvisa("Primo avvio completato.")

        return {"completato": completato, "passi": passi}


def stato() -> Dict[str, Any]:
    """A che punto e' questa installazione, senza toccare niente."""
    return prepare(scarica=False, forza=True)
