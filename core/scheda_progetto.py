# ==============================================================================
# core/scheda_progetto.py — Cos'e' Sigma Studio, detto dal codice
# Sigma Studio v8
# ==============================================================================
"""Una scheda breve del progetto, generata leggendo il progetto stesso.

Chiedendo a un modello dentro Sigma Studio «cos'e' l'harness e come si
migliora», la risposta descriveva un sistema che non esiste: sette agenti su
undici erano inventati, la sandbox era indicata in `data/` — che e' quella
della chat, non quella dell'harness — e i trentacinque moduli del kernel non
comparivano affatto.

Non era un difetto del modello. Era che **nessuno gli aveva dato i fatti**: il
prompt di sistema descrive un assistente, non questo programma, e da li' un
modello puo' solo dedurre. Il risultato ha la forma di una diagnosi e il
contenuto di un'immaginazione, che e' il modo piu' costoso di sbagliare.

**La scheda si genera, non si scrive.** Un testo scritto a mano dice la verita'
il giorno in cui lo si scrive e comincia a mentire il giorno dopo: i ruoli
cambiano, i tool si aggiungono, i moduli nascono. Qui ogni riga viene letta dal
codice nel momento in cui serve, e non puo' divergere da cio' che descrive.

**E' corta apposta.** Sta nel prefisso stabile della chat, che e' anche il
prefisso riusabile della cache KV: paga una volta e vale per tutta la
conversazione. Dire tutto costerebbe migliaia di token a ogni sessione; dire
**cosa esiste e dove guardare** ne costa poche centinaia, e il resto si chiede
con `consulta_progetto` quando serve davvero.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import paths
from core.logger import get_logger

log = get_logger("scheda_progetto")

#: I documenti che rispondono alle domande vere su questo progetto. L'ordine e'
#: quello in cui conviene leggerli.
DOCUMENTI: Tuple[Tuple[str, str], ...] = (
    ("STATO_HARNESS.md",
     "Lo stato dell'harness: cosa regge, i difetti trovati e le loro misure, "
     "il voto del flusso di squadra, la sandbox Docker."),
    ("AGENTS.md",
     "Le regole di lavoro dentro questo repository: cosa non si tocca, come si "
     "scrive, come si verifica."),
    ("README.md",
     "Presentazione del progetto e avvio."),
)

#: Quanto testo restituisce al massimo una consultazione. Oltre, non si sta piu'
#: rispondendo a una domanda: si sta riversando un file nel contesto.
MAX_CARATTERI_RISPOSTA = 6000


def _radice() -> Path:
    return Path(paths.project_root())


def _ruoli_veri() -> List[str]:
    try:
        from core.harness.roles import DEV_ROLES
        return sorted(DEV_ROLES.keys())
    except Exception as exc:
        log.debug("[Scheda] ruoli non leggibili: %s", exc)
        return []


def _tool_veri() -> List[str]:
    try:
        from core.harness.tool_schema import TOOL_SCHEMAS
        return [s["function"]["name"] for s in TOOL_SCHEMAS]
    except Exception as exc:
        log.debug("[Scheda] tool non leggibili: %s", exc)
        return []


def _agenti_della_chat() -> List[str]:
    try:
        import json
        percorso = Path(paths.config_dir()) / "agents_meta.json"
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return sorted((dati.get("agents") or {}).keys())
    except Exception as exc:
        log.debug("[Scheda] agenti non leggibili: %s", exc)
        return []


def _moduli_del_kernel() -> List[str]:
    try:
        cartella = _radice() / "core" / "harness"
        return sorted(p.stem for p in cartella.glob("*.py")
                      if not p.stem.startswith("__"))
    except OSError:
        return []


def _moduli_installati() -> List[str]:
    try:
        import json
        percorso = Path(paths.config_dir()) / "marketplace_installed.json"
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return sorted(dati.keys()) if isinstance(dati, dict) else []
    except Exception:
        return []


@functools.lru_cache(maxsize=1)
def _scheda_grezza(impronta: str) -> str:
    """Il testo della scheda. `impronta` serve solo a invalidare la cache."""
    def _senza_rompere(sorgente):
        try:
            return sorgente()
        except Exception as exc:
            log.debug("[Scheda] '%s' non disponibile: %s", sorgente.__name__, exc)
            return []

    ruoli = _senza_rompere(_ruoli_veri)
    tool = _senza_rompere(_tool_veri)
    agenti = _senza_rompere(_agenti_della_chat)
    kernel = _senza_rompere(_moduli_del_kernel)
    moduli = _senza_rompere(_moduli_installati)

    righe = [
        "## QUESTO PROGETTO",
        "",
        "Sei dentro **Sigma Studio**, una postazione di lavoro AI locale. "
        "Quando ti si chiede di questo programma, rispondi dai fatti qui sotto "
        "e da `consulta_progetto`, mai a memoria: i nomi inventati sono il modo "
        "piu' comune di sbagliare, e qui si vedono subito.",
        "",
    ]

    if kernel:
        righe += [
            f"**L'harness dell'agente** sta in `core/harness/` ({len(kernel)} moduli). "
            "E' il ciclo che fa lavorare un modello sul codice: ledger della "
            "sessione, cancello di completamento con prove, isolamento in "
            "worktree git, revisione del diff, coda di lavoro persistente, "
            "ventaglio di run paralleli, sandbox Docker.",
            "  moduli: " + ", ".join(kernel),
            "",
        ]
    if ruoli:
        righe += [
            f"**I ruoli dell'harness** sono {len(ruoli)} e sono questi, non altri: "
            + ", ".join(ruoli) + ".",
            "",
        ]
    if tool:
        righe += [
            f"**I tool dell'agente** sono {len(tool)}: " + ", ".join(tool) + ".",
            "",
        ]
    if agenti:
        righe += [
            "**Gli agenti della chat** (un'altra cosa dai ruoli dell'harness) "
            "sono: " + ", ".join(agenti) + ".",
            "",
        ]
    if moduli:
        righe += ["**I moduli installati** sono: " + ", ".join(moduli) + ".", ""]

    righe += [
        "**Dove si scrive.** La chat lavora sotto `data/`. L'harness lavora su "
        "una cartella di progetto scelta dall'utente, confinata dal codice e, "
        "quando il progetto lo chiede, dentro un contenitore Docker.",
        "",
        "Per qualunque dettaglio usa `consulta_progetto`: i documenti "
        "disponibili sono " + ", ".join(n for n, _ in DOCUMENTI) + ".",
    ]
    return "\n".join(righe)


def _impronta() -> str:
    """Cambia quando cambia cio' che la scheda descrive.

    Non e' un hash del progetto intero — costerebbe piu' della scheda. Bastano
    i numeri che la scheda cita: se cambiano, il testo va rigenerato.

    Ogni pezzo e' isolato: se una sorgente non risponde, la scheda perde quella
    riga e tiene le altre. Prima un solo `config/` illeggibile faceva sparire
    la scheda intera, e il modello tornava a rispondere a memoria — cioe' il
    difetto che questa scheda esiste per evitare, riaperto dal caso piu'
    banale.
    """
    pezzi = []
    for sorgente in (_ruoli_veri, _tool_veri, _agenti_della_chat, _moduli_del_kernel):
        try:
            pezzi.append(len(sorgente()))
        except Exception as exc:
            log.debug("[Scheda] '%s' non disponibile: %s", sorgente.__name__, exc)
            pezzi.append(-1)
    return "-".join(str(n) for n in pezzi)


def scheda() -> str:
    """La scheda del progetto, breve e sempre vera."""
    try:
        return _scheda_grezza(_impronta())
    except Exception as exc:
        log.warning("[Scheda] non generata: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Consultazione su richiesta
# ---------------------------------------------------------------------------

def indice() -> List[Dict[str, str]]:
    """I documenti consultabili che esistono davvero su questo disco."""
    fuori = []
    for nome, descrizione in DOCUMENTI:
        percorso = _radice() / nome
        if percorso.is_file():
            fuori.append({"documento": nome, "descrizione": descrizione,
                          "caratteri": percorso.stat().st_size})
    return fuori


def _sezioni(testo: str) -> List[Tuple[str, str]]:
    """Spezza un Markdown nelle sue sezioni di primo e secondo livello."""
    parti: List[Tuple[str, str]] = []
    titolo, corpo = "(intestazione)", []
    for riga in testo.splitlines():
        if re.match(r"^#{1,3} ", riga):
            if corpo:
                parti.append((titolo, "\n".join(corpo)))
            titolo, corpo = riga.lstrip("# ").strip(), [riga]
        else:
            corpo.append(riga)
    if corpo:
        parti.append((titolo, "\n".join(corpo)))
    return parti


def consulta(argomento: str = "", documento: str = "") -> Dict[str, Any]:
    """Le sezioni del progetto che parlano di quell'argomento.

    Senza argomento ritorna l'indice: e' la risposta giusta a «cosa posso
    chiederti», e costa niente.

    La ricerca e' per parole nel titolo e nel corpo, e ritorna **sezioni
    intere**: mezza sezione risponde alla domanda e nasconde il motivo, che in
    questi documenti sta quasi sempre nel paragrafo dopo.
    """
    termine = str(argomento or "").strip().lower()
    voluto = str(documento or "").strip()

    if not termine and not voluto:
        return {"ok": True, "indice": indice(),
                "suggerimento": "Chiama di nuovo con `argomento` per leggere."}

    trovate: List[Dict[str, Any]] = []
    esaminate = 0
    for nome, _ in DOCUMENTI:
        if voluto and nome.lower() != voluto.lower():
            continue
        percorso = _radice() / nome
        if not percorso.is_file():
            continue
        try:
            testo = percorso.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.debug("[Scheda] '%s' non leggibile: %s", nome, exc)
            continue
        for titolo, corpo in _sezioni(testo):
            esaminate += 1
            if not termine:
                trovate.append({"documento": nome, "sezione": titolo, "testo": corpo})
                continue
            # Si cerca parola per parola, non la frase intera: «sandbox
            # docker» come frase compare solo dove qualcuno l'ha scritta
            # esattamente cosi', mentre le sezioni che servono parlano di
            # «sandbox» in un punto e di «Docker» in un altro. Le parole
            # cortissime si saltano: «di», «e», «la» pescano tutto.
            punteggio = 0
            titolo_b, corpo_b = titolo.lower(), corpo.lower()
            for parola in termine.split():
                if len(parola) < 3:
                    continue
                punteggio += 3 * titolo_b.count(parola) + corpo_b.count(parola)
            if punteggio:
                trovate.append({"documento": nome, "sezione": titolo,
                                "testo": corpo, "punteggio": punteggio})

    trovate.sort(key=lambda s: -s.get("punteggio", 0))
    risposta: List[Dict[str, Any]] = []
    caratteri = 0
    for sezione in trovate:
        if caratteri + len(sezione["testo"]) > MAX_CARATTERI_RISPOSTA and risposta:
            break
        caratteri += len(sezione["testo"])
        risposta.append(sezione)

    if not risposta:
        # Una ricerca a vuoto dice quanto ha guardato: senza, «non trovato»
        # non distingue «non c'e'» da «non ho cercato».
        return {
            "ok": True, "sezioni": [], "esaminate": esaminate,
            "messaggio": (
                f"Nessuna sezione parla di '{argomento}'. Esaminate "
                f"{esaminate} sezioni in {len(indice())} documenti. "
                "Prova una parola piu' corta, o chiama senza argomento per "
                "vedere l'indice."
            ),
        }
    return {
        "ok": True, "sezioni": risposta, "esaminate": esaminate,
        "messaggio": (f"{len(risposta)} sezioni su '{argomento}', "
                      f"da {esaminate} esaminate."),
    }
