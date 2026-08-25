# ==============================================================================
# core/engine/load_overrides.py — Quando il pianificatore va scavalcato a mano
#
# SigmaEngine calcola da se' come caricare un modello: quanti layer sulla GPU,
# quanto contesto, che batch, se quantizzare la cache KV. Il calcolo e' buono e
# nella grande maggioranza dei casi va lasciato fare.
#
# Ma il calcolo parte da cio' che la macchina *dichiara*, e a volte la macchina
# mente o il caso e' particolare: una GPU condivisa con un altro programma, un
# driver che riporta VRAM che non e' davvero disponibile, una scheda che a
# pieno carico va in throttling, un modello che si vuole tenere apposta su CPU
# per lasciare la GPU libera. In quei casi l'unico modo di andare avanti e'
# dire il numero a mano, come si fa in LM Studio.
#
# Un override e' un valore singolo, non un profilo: si scavalca il contesto e
# si lascia decidere tutto il resto al pianificatore. Cosi' una macchina che ha
# bisogno di una sola correzione non perde le altre decisioni, e chi legge il
# log vede esattamente che cosa e' stato imposto e da chi.
#
# Sta in config/ perche' descrive questa macchina, non lo stato di un lavoro:
# sopravvive a una pulizia di var/ e a una reinstallazione dei moduli.
# ==============================================================================
from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

_LOCK = threading.Lock()
_cache: Optional[Dict[str, Any]] = None


#: I parametri che si possono imporre, con il tipo atteso e cosa significano.
#: Sono esattamente quelli che il pianificatore produce e che il backend passa
#: a llama.cpp: dichiararne uno che il backend ignora darebbe un'impostazione
#: che sembra applicata e non lo e'.
CAMPI: Dict[str, Dict[str, Any]] = {
    "n_gpu_layers": {
        "tipo": int, "min": 0,
        "etichetta": "Layer sulla GPU",
        "aiuto": "0 tiene tutto sulla CPU. Ridurlo libera VRAM al costo di velocita'.",
    },
    "n_ctx": {
        "tipo": int, "min": 128,
        "etichetta": "Finestra di contesto",
        "aiuto": "Token che il modello puo' tenere davanti a se'. Pesa sulla cache KV.",
    },
    "n_batch": {
        "tipo": int, "min": 1,
        "etichetta": "Batch di prefill",
        "aiuto": "Token elaborati insieme nella lettura del prompt.",
    },
    "n_threads": {
        "tipo": int, "min": 1,
        "etichetta": "Thread CPU",
        "aiuto": "Quanti core usare per i layer che restano sulla CPU.",
    },
    "flash_attn": {
        "tipo": bool,
        "etichetta": "Flash Attention",
        "aiuto": "Piu' veloce dove e' supportata; su alcune schede va disattivata.",
    },
    "kv_quant": {
        "tipo": str, "valori": ["f16", "q8_0", "q4_0"],
        "etichetta": "Quantizzazione cache KV",
        "aiuto": "q8_0 dimezza la cache; costa circa il 10% di velocita' su CPU.",
    },
    "use_mmap": {
        "tipo": bool,
        "etichetta": "Memory mapping",
        "aiuto": "Disattivalo su filesystem di rete o quando il caricamento fallisce a meta'.",
    },
    "use_mlock": {
        "tipo": bool,
        "etichetta": "Blocca in RAM",
        "aiuto": "Impedisce lo swap del modello. Serve RAM sufficiente a tenerlo tutto.",
    },
}


def overrides_file():
    return paths.config_dir() / "engine_overrides.json"


# ==============================================================================
# LETTURA E SCRITTURA
# ==============================================================================

def _vuoto() -> Dict[str, Any]:
    return {"globale": {}, "modelli": {}}


def _leggi() -> Dict[str, Any]:
    percorso = overrides_file()
    if not percorso.exists():
        return _vuoto()
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("[LoadOverrides] File illeggibile, ignorato: %s", exc)
        return _vuoto()

    return {
        "globale": dati.get("globale") or {},
        "modelli": dati.get("modelli") or {},
    }


def _scrivi(dati: Dict[str, Any]) -> None:
    percorso = overrides_file()
    paths.ensure(percorso.parent)
    da_salvare = {
        "_commento": [
            "Impostazioni di caricamento imposte a mano, che scavalcano il",
            "pianificatore di SigmaEngine. Un campo assente o null lascia",
            "decidere lui. 'globale' vale per ogni modello, 'modelli' per uno",
            "solo e ha la precedenza.",
        ],
        "globale": dati.get("globale") or {},
        "modelli": dati.get("modelli") or {},
    }
    percorso.write_text(json.dumps(da_salvare, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def _carica() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _leggi()
    return _cache


def invalidate() -> None:
    global _cache
    with _LOCK:
        _cache = None


# ==============================================================================
# VALIDAZIONE
# ==============================================================================

def _valida(nome: str, valore: Any) -> Any:
    """Converte e controlla un valore, o solleva ValueError spiegando cosa manca."""
    campo = CAMPI.get(nome)
    if campo is None:
        raise ValueError(f"Parametro sconosciuto: '{nome}'. "
                         f"Ammessi: {', '.join(sorted(CAMPI))}")
    if valore is None:
        return None

    tipo = campo["tipo"]
    if tipo is bool:
        if isinstance(valore, bool):
            return valore
        if isinstance(valore, str):
            return valore.strip().lower() in ("1", "true", "si", "sì", "yes", "on")
        return bool(valore)

    if tipo is int:
        try:
            numero = int(valore)
        except (TypeError, ValueError):
            raise ValueError(f"'{nome}' vuole un numero intero, ricevuto {valore!r}")
        minimo = campo.get("min")
        if minimo is not None and numero < minimo:
            raise ValueError(f"'{nome}' non puo' essere minore di {minimo}")
        return numero

    testo = str(valore).strip()
    ammessi = campo.get("valori")
    if ammessi and testo not in ammessi:
        raise ValueError(f"'{nome}' ammette {', '.join(ammessi)}, ricevuto {testo!r}")
    return testo


# ==============================================================================
# API
# ==============================================================================

def get_all() -> Dict[str, Any]:
    """Tutti gli override, piu' la descrizione dei campi per la UI."""
    with _LOCK:
        dati = _carica()
        return {
            "globale": dict(dati["globale"]),
            "modelli": {k: dict(v) for k, v in dati["modelli"].items()},
            "campi": {
                nome: {
                    "etichetta": c["etichetta"],
                    "aiuto": c["aiuto"],
                    "tipo": c["tipo"].__name__,
                    "valori": c.get("valori"),
                    "min": c.get("min"),
                }
                for nome, c in CAMPI.items()
            },
        }


def get_for(model_name: str) -> Dict[str, Any]:
    """Gli override che si applicano a un modello: globali piu' i suoi."""
    with _LOCK:
        dati = _carica()
        effettivi = dict(dati["globale"])
        effettivi.update(dati["modelli"].get(model_name or "", {}))
        return {k: v for k, v in effettivi.items() if v is not None}


def set_for(model_name: Optional[str], valori: Dict[str, Any]) -> Dict[str, Any]:
    """Imposta o cancella override. Un valore None cancella quel campo.

    `model_name` vuoto o None scrive sugli override globali.
    """
    puliti: Dict[str, Any] = {}
    for nome, valore in (valori or {}).items():
        puliti[nome] = _valida(nome, valore)

    with _LOCK:
        dati = _leggi()
        chiave = "globale" if not model_name else "modelli"
        if chiave == "globale":
            sezione = dati["globale"]
        else:
            sezione = dati["modelli"].setdefault(model_name, {})

        for nome, valore in puliti.items():
            if valore is None:
                sezione.pop(nome, None)
            else:
                sezione[nome] = valore

        if chiave == "modelli" and not sezione:
            dati["modelli"].pop(model_name, None)

        _scrivi(dati)
        global _cache
        _cache = None

    log.info("[LoadOverrides] Impostazioni manuali per '%s': %s",
             model_name or "(tutti i modelli)", puliti)
    return get_all()


def clear(model_name: Optional[str] = None) -> Dict[str, Any]:
    """Toglie gli override di un modello, o tutti se non se ne indica uno."""
    with _LOCK:
        dati = _leggi()
        if model_name:
            dati["modelli"].pop(model_name, None)
        else:
            dati = _vuoto()
        _scrivi(dati)
        global _cache
        _cache = None
    log.info("[LoadOverrides] Impostazioni manuali rimosse per '%s'",
             model_name or "(tutto)")
    return get_all()


def apply_to(settings: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """Sovrascrive nel piano i valori imposti a mano.

    Restituisce il piano modificato. Cio' che e' stato imposto finisce in
    `settings["overridden"]`, cosi' chi legge un log o una diagnosi vede subito
    che quel numero non l'ha scelto il pianificatore.
    """
    imposti = get_for(model_name)
    if not imposti:
        return settings

    applicati = {}
    for nome, valore in imposti.items():
        if nome not in settings:
            # Il pianificatore non produce questa chiave in questo percorso:
            # imporla comunque creerebbe un'impostazione che nessuno legge.
            log.debug("[LoadOverrides] '%s' non presente nel piano, ignorato", nome)
            continue
        if settings[nome] != valore:
            applicati[nome] = {"pianificato": settings[nome], "imposto": valore}
            settings[nome] = valore

    if applicati:
        settings["overridden"] = applicati
        log.info("[LoadOverrides] Piano per '%s' scavalcato a mano: %s",
                 model_name, ", ".join(f"{k} {v['pianificato']}->{v['imposto']}"
                                       for k, v in applicati.items()))
    return settings
