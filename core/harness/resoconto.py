# ==============================================================================
# core/harness/resoconto.py — Raccontare il lavoro con i fatti registrati
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Cosa e' stato fatto, come funziona, come e' stato verificato — dai fatti.

Chi guarda un run vedeva solo eventi tecnici: `tool_start`, `tool_result`,
`ledger`. Alla fine restava un riassunto scritto dal modello, e il corpo della
pull request elencava l'obiettivo e i nomi dei file. Nessuna delle tre domande
che uno si fa davvero — **cosa e' stato fatto, come funziona, come lo so** —
trovava risposta in un posto solo.

Il materiale c'era gia' tutto nel ledger: i criteri accettati con cio' che li
dimostra, i comandi eseguiti con il loro esito analizzato, i file toccati con
quante volte. Mancava chi lo mettesse in fila.

**Il resoconto si costruisce dai fatti, non dal modello.** E' la differenza che
conta: un modello sa scrivere «ho verificato tutto» senza aver eseguito niente,
e su questo progetto lo ha gia' fatto. Qui ogni riga viene da qualcosa che e'
successo davvero e che qualcuno ha registrato mentre succedeva. Se il resoconto
e' vuoto, e' perche' non e' stato fatto nulla — e dirlo e' proprio il punto.

Due usi, un solo testo: il consuntivo di fine run (verso l'interfaccia e verso
il corpo della pull request) e il diario, che e' lo stesso racconto ma un pezzo
per volta, mentre succede.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Oltre questo numero l'elenco dei file smette di informare e comincia a
#: nascondere: si dice quanti sono e se ne mostrano i primi.
MAX_FILE_ELENCATI = 40


def _riga_file(f: Dict[str, Any]) -> str:
    percorso = f.get("path", "")
    if f.get("created"):
        che_cosa = "creato"
    elif f.get("writes"):
        che_cosa = "riscritto"
    elif f.get("edits"):
        che_cosa = "modificato"
    else:
        che_cosa = "letto"
    righe = f.get("total_lines")
    coda = f", {righe} righe" if righe else ""
    return f"- `{percorso}` — {che_cosa}{coda}"


def _file_toccati(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Solo i file cambiati: leggerne uno non e' averci fatto qualcosa."""
    return [f for f in snapshot.get("files") or []
            if f.get("writes") or f.get("edits") or f.get("created")]


def _verifiche(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """I comandi che il sistema ha riconosciuto come verifiche.

    Si guarda la chiave `verification`, che il ledger aggiunge solo quando il
    comando e' stato analizzato da `parse_verification`. Un `echo fatto` non
    ce l'ha, e non deve comparire come prova.
    """
    return [c for c in snapshot.get("commands") or [] if c.get("verification")]


def _descrivi_verifica(cmd: Dict[str, Any]) -> str:
    v = cmd.get("verification") or {}
    esito = "passata" if cmd.get("ok") else "FALLITA"
    pezzi = [f"`{cmd.get('command', '')}` — {esito}"]
    numeri = []
    for chiave, etichetta in (("passed", "passati"), ("failed", "falliti"),
                              ("errors", "errori"), ("skipped", "saltati")):
        if v.get(chiave):
            numeri.append(f"{v[chiave]} {etichetta}")
    if numeri:
        pezzi.append("(" + ", ".join(numeri) + ")")
    elif v.get("summary"):
        pezzi.append(f"({v['summary'][:120]})")
    else:
        pezzi.append(f"(uscita {cmd.get('returncode')})")
    return "- " + " ".join(pezzi)


def resoconto(
    snapshot: Optional[Dict[str, Any]],
    *,
    obiettivo: str = "",
    branch: str = "",
    raggiunto: Optional[bool] = None,
) -> str:
    """Il consuntivo del lavoro, in Markdown, costruito dai fatti registrati.

    `snapshot` e' `DevSessionLedger.snapshot()`. Non serve il ledger vivo: il
    resoconto deve poter essere scritto anche dopo, da uno stato salvato.
    """
    snapshot = snapshot or {}
    righe: List[str] = []

    scopo = (obiettivo or snapshot.get("goal") or "").strip()
    if scopo:
        righe += [f"**Obiettivo:** {scopo}", ""]

    capito = str(snapshot.get("intake") or "").strip()
    if capito:
        righe += ["**Cosa ha capito che andava fatto**", "", capito, ""]

    criteri = snapshot.get("requirements") or []
    if criteri:
        soddisfatti = sum(1 for c in criteri if c.get("met"))
        righe += [f"**Criteri di accettazione** ({soddisfatti} su {len(criteri)})", ""]
        for c in criteri:
            segno = "x" if c.get("met") else " "
            riga = f"- [{segno}] {c.get('text', '')}"
            prova = str(c.get("evidence") or "").strip()
            if prova:
                riga += f" — _{prova}_"
            righe.append(riga)
        righe.append("")

    toccati = _file_toccati(snapshot)
    if toccati:
        creati = sum(1 for f in toccati if f.get("created"))
        righe += [
            f"**Cosa e' stato fatto** ({len(toccati)} file toccati, "
            f"{creati} creati)",
            "",
        ]
        righe += [_riga_file(f) for f in toccati[:MAX_FILE_ELENCATI]]
        if len(toccati) > MAX_FILE_ELENCATI:
            righe.append(f"- … e altri {len(toccati) - MAX_FILE_ELENCATI}")
        righe.append("")

    prove = _verifiche(snapshot)
    if prove:
        righe += ["**Come e' stato verificato**", ""]
        righe += [_descrivi_verifica(c) for c in prove]
        righe.append("")
    elif toccati:
        # Il caso che il cancello di completamento esiste per impedire. Se
        # arriva fin qui, dirlo vale piu' che tacerlo.
        righe += [
            "**Come e' stato verificato**", "",
            "Nessun comando di verifica riconosciuto. Il lavoro non e' dimostrato.",
            "",
        ]

    guasti = [c for c in snapshot.get("commands") or [] if not c.get("ok")]
    fallimenti = snapshot.get("failures") or []
    if guasti or fallimenti:
        righe += ["**Cosa non ha funzionato**", ""]
        for c in guasti[-5:]:
            motivo = str(c.get("error") or "").strip().replace("\n", " ")[:160]
            righe.append(f"- `{c.get('command', '')}` — {motivo or 'uscita diversa da 0'}")
        for f in fallimenti[-5:]:
            testo = f if isinstance(f, str) else str(f.get("error") or f)
            righe.append(f"- {testo[:160]}")
        righe.append("")

    coda: List[str] = []
    if branch:
        coda.append(f"Branch del run: `{branch}`.")
    durata = snapshot.get("elapsed_s")
    if durata:
        coda.append(f"Durata: {durata} s.")
    if raggiunto is False:
        coda.append("L'obiettivo **non** e' stato chiuso: il lavoro resta sul branch.")
    if coda:
        righe += [" ".join(coda)]

    testo = "\n".join(righe).strip()
    return testo or "Nessun lavoro registrato in questo run."


# ---------------------------------------------------------------------------
# Il diario: lo stesso racconto, un pezzo per volta
# ---------------------------------------------------------------------------
# Chi guarda mentre gira non puo' aspettare il consuntivo. Ma nemmeno leggere
# `tool_result` grezzi: sono il formato giusto per il pannello tecnico e quello
# sbagliato per capire a che punto siamo.

def _nome_corto(percorso: Any) -> str:
    testo = str(percorso or "").replace("\\", "/").strip()
    return testo.rsplit("/", 1)[-1] if testo else ""


def narra(evento: Dict[str, Any]) -> Optional[str]:
    """Una riga di diario per un evento del ciclo, o None se non ne merita una.

    Il filtro e' la parte utile: raccontare ogni evento produce un elenco che
    nessuno legge. Si raccontano i fatti che cambiano lo stato del lavoro —
    cosa e' stato scritto, cosa e' stato eseguito e com'e' andata, cosa e'
    stato rifiutato e perche' — e si tace su tutto il resto.
    """
    tipo = evento.get("type")

    if tipo == "spec_registered":
        criteri = evento.get("criteria") or []
        return f"Ha dichiarato cosa va fatto e {len(criteri)} criteri di accettazione."

    if tipo == "pipeline_update":
        task = evento.get("tasks") or []
        if not task:
            return None
        ruoli = sorted({t.get("role", "") for t in task if t.get("role")})
        coda = f" ({', '.join(ruoli)})" if ruoli else ""
        return f"Ha registrato un piano di {len(task)} task{coda}."

    if tipo == "tool_result":
        return _narra_tool(evento.get("tool", ""), evento.get("result") or {})

    if tipo == "completion_rejected":
        return f"Chiusura rifiutata: {str(evento.get('reason') or evento.get('error') or '')[:200]}"

    if tipo == "evidence_rejected":
        return f"Prova rifiutata: {str(evento.get('reason') or evento.get('error') or '')[:200]}"

    if tipo == "goal_complete":
        return f"Obiettivo chiuso: {str(evento.get('summary') or '')[:300]}"

    if tipo == "apply_failed":
        return ("L'obiettivo era chiuso ma la modifica non e' arrivata "
                f"nell'albero principale: {str(evento.get('error') or '')[:200]}")

    if tipo == "run_delivered":
        return f"Consegnato su `{evento.get('branch', 'dev')}`. {evento.get('pr_url', '')}".strip()

    if tipo == "worktree_preserved":
        return f"Lavoro conservato sul branch `{evento.get('branch', '')}`."

    return None


def _narra_tool(nome: str, risultato: Dict[str, Any]) -> Optional[str]:
    tool = str(risultato.get("tool") or nome or "").lower()
    ok = bool(risultato.get("success"))
    percorso = _nome_corto(risultato.get("path") or risultato.get("full_path"))

    if tool in ("write_file", "append_file"):
        if not ok:
            return f"Scrittura di `{percorso}` non riuscita: {str(risultato.get('error'))[:140]}"
        verbo = "Creato" if risultato.get("created") else "Scritto"
        return f"{verbo} `{percorso}`."

    if tool == "edit_file":
        if not ok:
            return f"Modifica di `{percorso}` non riuscita: {str(risultato.get('error'))[:140]}"
        return f"Modificato `{percorso}`."

    if tool == "delete":
        return f"Eliminato `{percorso}`." if ok else None

    if tool == "terminal":
        comando = str(risultato.get("command") or "").strip()
        if not comando:
            return None
        rc = risultato.get("returncode")
        if ok and rc == 0:
            return f"Eseguito `{comando[:120]}` — uscita 0."
        motivo = str(risultato.get("error") or "").strip().replace("\n", " ")[:140]
        return f"Eseguito `{comando[:120]}` — uscita {rc}. {motivo}".strip()

    # Leggere, elencare e cercare sono come ci si arriva, non cosa si e' fatto.
    return None
