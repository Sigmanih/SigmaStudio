# ==============================================================================
# core/harness/compaction.py — Compattazione con Sintesi Accanto al Ledger
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Compattazione progressiva della cronologia con distillazione delle motivazioni.

Il problema: quando una sessione si allunga (15-30+ turni), la compattazione
semplice elimina i turni piu vecchi dal transcript. Il ledger conserva lo stato
dei file e delle prove raccolte, ma la catena delle motivazioni — *perche* e stata
scelta una certa strada o scartata un'altra — viene perduta, causando amnesia
decisionale.

La soluzione: prima di ogni sfratto di messaggi dalla finestra attiva, questo
modulo analizza i turni in uscita ed estrae una sintesi delle decisioni, delle
ragioni e degli esiti. Questa sintesi viene aggiunta in modo duraturo alla
`session_memory` del ledger, che viene re-iniettata nello state block di ogni
turno successivo senza mai essere sfrattata.
"""

import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.logger import get_logger
from core.harness.ledger import DevSessionLedger

log = get_logger("harness_compaction")

# Pattern per rimuovere blocchi tool grezzi e focalizzarsi sul ragionamento dell'agente
_TOOL_BLOCK_RE = re.compile(r"```tool:\w+\s*\{.*?\}\s*```", re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*?\}")


def extract_reasoning_and_decisions(text: str) -> List[str]:
    """Estrae le frasi di spiegazione, motivazione e pianificazione da un messaggio."""
    # Rimuoviamo il blocco tool grezzo per isolare il testo discorsivo
    cleaned = _TOOL_BLOCK_RE.sub("", text or "").strip()
    if not cleaned:
        return []

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    meaningful: List[str] = []
    
    # Parole chiave che segnalano una decisione, motivazione o spiegazione
    signals = (
        "perch", "poich", "decis", "scelt", "invece di", "anzich", "proced",
        "individu", "modific", "implement", "risolt", "corregg", "fallit",
        "notat", "verific", "necessar", "evit", "prefer", "strategia",
    )

    for line in lines:
        # Ignora intestazioni markdown vuote o saluti banali
        if len(line) < 15 or line.startswith("#"):
            continue
        lower_line = line.lower()
        if any(sig in lower_line for sig in signals):
            # Normalizza punteggiatura
            clean_line = re.sub(r"\s+", " ", line)
            meaningful.append(clean_line)

    return meaningful


def heuristic_summarize_evicted(evicted_messages: List[Dict[str, str]]) -> Tuple[str, List[str]]:
    """Sintetizza in modo deterministico i turni sfrattati estraendone le motivazioni chiave.

    Funziona sempre, anche in assenza di LLM o durante test offline, catturando
    il filo logico delle azioni compiute nei messaggi da scartare.
    """
    if not evicted_messages:
        return "", []

    reasonings: List[str] = []
    actions_taken: List[str] = []
    key_decisions: List[str] = []

    for msg in evicted_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "assistant":
            # Estrazione del ragionamento espresso dall'agente
            extracted = extract_reasoning_and_decisions(content)
            for item in extracted:
                if item not in reasonings:
                    reasonings.append(item)

            # Rilevamento sintetico del tool invocato
            tool_match = re.search(r"```tool:(\w+)\s*(\{.*?\})?\s*```", content, re.DOTALL)
            if tool_match:
                t_name = tool_match.group(1)
                t_body = tool_match.group(2) or ""
                target = ""
                try:
                    params = json.loads(t_body)
                    target = params.get("path") or params.get("command") or params.get("pattern") or ""
                except Exception:
                    pass
                if target:
                    actions_taken.append(f"{t_name} su `{target[:60]}`")
                else:
                    actions_taken.append(t_name)

        elif role == "user":
            # Esito di un comando o tool (es. fallimento o successo)
            if "FALLITO" in content or "Error" in content or "error:" in content:
                # Estraiamo una riga significativa di errore
                err_lines = [l.strip() for l in content.splitlines() if "error" in l.lower() or "fallito" in l.lower()]
                if err_lines:
                    reasonings.append(f"Riscontrato intoppo: {err_lines[0][:120]}")

    # Costruiamo il sommario unificato
    parts: List[str] = []
    if reasonings:
        # Selezioniamo le motivazioni piu significative (massimo 3)
        sample = reasonings[:3]
        parts.append(". ".join(sample))
        for r in sample:
            if any(k in r.lower() for k in ("decis", "scelt", "prefer", "invece")):
                key_decisions.append(r[:100])

    if actions_taken and not parts:
        # Fallback sulle azioni se non c'erano motivazioni esplicite nel testo
        dedup_actions = list(dict.fromkeys(actions_taken))[:4]
        parts.append(f"Eseguite operazioni: {', '.join(dedup_actions)}")

    summary_text = " ".join(parts).strip()
    if summary_text and not summary_text.endswith("."):
        summary_text += "."

    return summary_text[:1200], key_decisions[:5]


def llm_summarize_evicted(
    evicted_messages: List[Dict[str, str]],
    stream_generator_fn: Optional[Callable] = None,
    model_name: Optional[str] = None,
) -> Optional[Tuple[str, List[str]]]:
    """Genera una sintesi semantica mirata usando il modello di inferenza."""
    if not stream_generator_fn or not evicted_messages:
        return None

    # Prepariamo un estratto compatto dei messaggi da riassumere
    transcript_snippets: List[str] = []
    for m in evicted_messages:
        role = m.get("role", "user").upper()
        text = _TOOL_BLOCK_RE.sub("[chiamata tool]", m.get("content", "")).strip()
        if text:
            transcript_snippets.append(f"{role}: {text[:300]}")

    if not transcript_snippets:
        return None

    raw_context = "\n".join(transcript_snippets[-8:])
    prompt = (
        "Sei un assistente che compila la memoria duratura di uno sviluppatore AI.\n"
        "Riassumi in 1 o 2 frasi concise in italiano le decisioni prese, le motivazioni "
        "delle scelte e gli intoppi incontrati nei turni seguenti, escludendo codice grezzo:\n\n"
        f"{raw_context}\n\n"
        "Sintesi:"
    )

    try:
        accumulated: List[str] = []
        gen = stream_generator_fn(
            messages=[{"role": "user", "content": prompt}],
            model_name=model_name,
            max_tokens=250,
            temperature=0.2,
        )
        for chunk in gen:
            if isinstance(chunk, dict) and chunk.get("token"):
                accumulated.append(chunk["token"])
        summary = "".join(accumulated).strip()
        if summary:
            return summary, []
    except Exception as exc:
        log.warning("Sintesi LLM dei turni sfrattati non riuscita, uso fallback euristico: %s", exc)

    return None


def summarize_and_record_eviction(
    evicted_messages: List[Dict[str, str]],
    ledger: Optional[DevSessionLedger],
    turn_range: str = "",
    stream_generator_fn: Optional[Callable] = None,
    model_name: Optional[str] = None,
) -> str:
    """Sintetizza i turni in uscita e li memorizza stabilmente nel ledger.

    La memoria di sessione non verra mai sfrattata e garantira continuita
    decisionale per tutta la durata del ciclo di sviluppo.
    """
    if not evicted_messages or ledger is None:
        return ""

    # Proviamo la sintesi LLM se disponibile
    result = llm_summarize_evicted(
        evicted_messages,
        stream_generator_fn=stream_generator_fn,
        model_name=model_name,
    )

    summary_text = ""
    decisions: List[str] = []

    if result and result[0]:
        summary_text, decisions = result
    else:
        # Fallback euristico robusto
        summary_text, decisions = heuristic_summarize_evicted(evicted_messages)

    if summary_text:
        ledger.add_session_memory(
            summary=summary_text,
            turn_range=turn_range,
            decisions=decisions,
        )
        log.info("[Compaction] Sfratto turni (%s): registrata memoria di sessione", turn_range or "storico")

    return summary_text


def compact_history_with_memory(
    messages: List[Dict[str, str]],
    ledger: Optional[DevSessionLedger],
    max_history_chars: int,
    max_recent_turns: int = 24,
    current_turn: int = 0,
    stream_generator_fn: Optional[Callable] = None,
    model_name: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Compattazione del transcript con preservazione della memoria decisionale.

    Mantiene il system prompt invariato e i messaggi recenti entro il budget.
    I messaggi che escono dal limite vengono analizzati, distillati e salvati
    nella memoria duratura del ledger prima della rimozione.
    """
    if len(messages) <= 3:
        return messages

    system_msg = messages[0]
    first_user_msg = messages[1]
    rest = list(messages[2:])

    to_evict: List[Dict[str, str]] = []

    # 1. Controllo limite di caratteri totali
    while len(rest) > 1 and sum(len(m.get("content", "")) for m in rest) > max_history_chars:
        to_evict.append(rest.pop(0))

    # 2. Controllo limite massimo di turni recenti
    while len(rest) > max_recent_turns:
        to_evict.append(rest.pop(0))

    if to_evict and ledger is not None:
        # Calcolo del range indicativo di turni sfrattati
        count_turns = max(1, len(to_evict) // 2)
        range_label = f"Turni precedenti (circa {count_turns} scambi fino a t={current_turn})"
        summarize_and_record_eviction(
            to_evict,
            ledger=ledger,
            turn_range=range_label,
            stream_generator_fn=stream_generator_fn,
            model_name=model_name,
        )

    return [system_msg, first_user_msg] + rest
