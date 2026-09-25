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


#: Quante righe tenere in testa e in coda a un'osservazione compressa. L'inizio
#: dice cosa e' stato chiesto, la fine dice com'e' finita: sono le due posizioni
#: in cui un output di terminale mette l'informazione, e in mezzo c'e' il
#: rumore. Le righe in mezzo che contano davvero le salvano le ancore.
INTESTAZIONE_RIGHE = 8
CODA_RIGHE = 12

#: Sotto questa dimensione comprimere non conviene: si pagherebbe una nota di
#: omissione per risparmiare qualche riga.
MINIMO_COMPRIMIBILE = 1200

#: Le finestre di testa e coda, in ordine di generosita'. La prima e' quella
#: normale; le altre si aprono solo se il budget non si raggiunge con quella, e
#: servono a non dover buttare via un turno intero per venti righe di margine.
#: Sotto le tre righe non si scende: un'osservazione senza inizio ne' fine non
#: e' piu' riconoscibile come il risultato di quel comando.
FINESTRE = ((INTESTAZIONE_RIGHE, CODA_RIGHE), (5, 6), (3, 3))

#: Le righe che **non si perdono mai**. Un errore compresso via e' peggio di un
#: turno in piu' nella finestra: l'agente crede di aver capito e riscrive il
#: codice da capo. E' questo insieme che rende la compressione un'operazione
#: sicura invece di una scommessa.
PATRONI_ANCORA = re.compile(
    r"(error|errore|errori|exception|traceback|assert|failed|failure|fallit|fatal"
    r"|panic|denied|refus|impossibile|non trovato|not found|missing|manca"
    r"|exit_code|exit code|exit status|nonzero|returned non-zero|signal"
    r"|E[0-9]{3}\b|✗|✘|❌|FAILED|Traceback"
    # Le righe di cornice di un traceback Python («  File "x.py", line 12») non
    # contengono nessuno dei termini qui sopra, e senza di esse la traccia resta
    # senza il punto in cui il guasto e' avvenuto: e' la riga che l'agente
    # guarda per prima.
    r'|File "[^"]+", line \d+)',
    re.IGNORECASE,
)

#: Una riga di diff aggiunta o tolta vale come ancora: e' cio' che l'agente ha
#: appena scritto, e ricostruirlo dal riassunto non si puo'.
PATRONI_DIFF = re.compile(r"^[+-]{1,3} (?!\+\+|--)")


def _e_ancora(riga: str) -> bool:
    """Vero se questa riga va tenuta comunque."""
    return bool(PATRONI_ANCORA.search(riga)) or bool(PATRONI_DIFF.match(riga))


def _cuci(righe: List[str], testa: int, coda: int) -> str:
    """Riunisce testa, coda e ancore, dichiarando le righe saltate."""
    tenute = set(range(min(testa, len(righe))))
    tenute |= set(range(max(0, len(righe) - coda), len(righe)))
    tenute |= {i for i, riga in enumerate(righe) if _e_ancora(riga)}

    pezzi: List[str] = []
    saltate = 0
    for i, riga in enumerate(righe):
        if i in tenute:
            if saltate:
                pezzi.append(f"[... {saltate} righe omesse: nessun errore fra queste ...]")
                saltate = 0
            pezzi.append(riga)
        else:
            saltate += 1
    if saltate:
        pezzi.append(f"[... {saltate} righe omesse: nessun errore fra queste ...]")
    return "\n".join(pezzi)


def comprimi_testo(testo: str, max_chars: int) -> Tuple[str, int]:
    """Riduce un'osservazione al suo significato. Restituisce (testo, risparmio).

    Il risparmio e' zero quando comprimere non conviene: testo gia' corto, o
    un'osservazione fatta quasi solo di ancore — un diff enorme, un log in cui
    ogni riga e' un errore. In quel caso non si tocca niente e decide lo stadio
    successivo, lo sfratto. Non comprimere e' sempre una risposta valida:
    l'alternativa, perdere righe, non lo e'.

    Si prova prima con la finestra generosa, poi con finestre piu' strette solo
    se il budget non e' ancora rispettato. E' la differenza fra comprimere e
    comprimere abbastanza: un tentativo solo lascerebbe la finestra sopra il
    limite, lo sfratto scatterebbe lo stesso, e il turno perso sarebbe stato
    pagato con una compressione inutile.
    """
    if max_chars <= 0 or len(testo) <= max_chars or len(testo) < MINIMO_COMPRIMIBILE:
        return testo, 0
    righe = testo.splitlines()
    if len(righe) < INTESTAZIONE_RIGHE + CODA_RIGHE + 4:
        return testo, 0

    migliore: Optional[str] = None
    for testa, coda in FINESTRE:
        compresso = _cuci(righe, testa, coda)
        if len(compresso) >= len(testo):
            continue
        if migliore is None or len(compresso) < len(migliore):
            migliore = compresso
        if len(compresso) <= max_chars:
            break
    if migliore is None:
        return testo, 0
    return migliore, len(testo) - len(migliore)


def comprimi_osservazioni(messaggi: List[Dict[str, str]],
                          max_chars: int) -> Tuple[List[Dict[str, str]], int]:
    """Comprime i messaggi piu' grossi finche' il totale sta nel budget.

    Si parte dal piu' grosso perche' e' quello che rende di piu' a parita' di
    righe; fermarsi appena il totale rientra evita di comprimere anche cio' che
    non serviva. Restituisce la lista nuova e i caratteri risparmiati.
    """
    totale = sum(len(m.get("content", "")) for m in messaggi)
    if totale <= max_chars:
        return list(messaggi), 0

    lavoro = list(messaggi)
    risparmiati = 0
    indici = sorted(range(len(lavoro)),
                    key=lambda i: -len(lavoro[i].get("content", "")))
    for i in indici:
        eccedenza = totale - risparmiati - max_chars
        if eccedenza <= 0:
            break
        contenuto = lavoro[i].get("content", "")
        if len(contenuto) < MINIMO_COMPRIMIBILE:
            continue
        # L'obiettivo e' scendere esattamente di quanto eccede. Non c'e' un
        # pavimento: il pavimento e' la struttura del testo — testa, coda e
        # ancore — e `comprimi_testo` non scende sotto quella. Un tetto
        # artificiale («non oltre la meta'») avrebbe l'effetto opposto a quello
        # voluto: la finestra non rientrerebbe, lo sfratto scatterebbe lo
        # stesso, e si sarebbe perso un turno *dopo* averlo comprato con una
        # compressione.
        nuovo, risparmio = comprimi_testo(contenuto, len(contenuto) - eccedenza)
        if risparmio > 0:
            aggiornato = dict(lavoro[i])
            aggiornato["content"] = nuovo
            lavoro[i] = aggiornato
            risparmiati += risparmio
    return lavoro, risparmiati


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

    # Prima di togliere turni si prova a rimpicciolirli. Sono due operazioni
    # diverse e finora ce n'era una sola: sfrattare butta via un turno intero —
    # la richiesta, la risposta, gli errori — mentre comprimere toglie le righe
    # che nessuno rileggera' e tiene quelle che servono. Su un run di
    # esplorazione la maggior parte del transcript e' output di terminale, e la
    # parte che vale e' una frazione: buttarne il turno intero era la scelta
    # piu' costosa fra le due. Lo sfratto resta, ma diventa il secondo stadio.
    rest, risparmiati = comprimi_osservazioni(rest, max_history_chars)
    if risparmiati:
        # Nel log perche' e' l'unico posto dove si vede la differenza fra «la
        # finestra stava dentro» e «e' stata fatta stare».
        log.info("[Compaction] osservazioni compresse: %d caratteri risparmiati "
                 "senza sfrattare nessun turno", risparmiati)

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
