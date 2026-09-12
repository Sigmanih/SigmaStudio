# ==============================================================================
# core/harness/autocorrezione.py — Cosa fare quando un task fallisce
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Un fallimento deve produrre una mossa successiva, non un vicolo cieco.

`TaskPipeline` sa gia' riprovare un task, inserirne uno di correzione e
bloccare cio' che dipendeva da quello caduto. Nessuno la chiamava: `retry_task`,
`insert_fix_task` e `reorder_after_failure` erano raggiunti solo dai loro test.
Quando un task falliva, l'orchestratore lo segnava fallito e proseguiva finche'
restava qualcosa di eseguibile — poi diceva «N task non eseguibili» e si
fermava li'.

Questo modulo e' la parte che mancava: **guardare cos'e' andato storto e
decidere il passo successivo**. Quattro mosse, in ordine di costo crescente.

**Riprova.** Il guasto non riguarda il lavoro: un comando scaduto, un file
occupato, la rete. Rifare la stessa cosa e' la risposta giusta, e costa poco.

**Correggi.** Il guasto ha una causa leggibile — un file che non compila, un
test che dice quale asserzione e' saltata. Si inserisce un task che ripara
quella cosa li', con dentro scritto **cosa** riparare.

**Ripianifica.** Il guasto dice che il piano era sbagliato: il task dava per
esistente un file che non c'e', oppure non ha prodotto niente in tutti i turni
che aveva. Continuare a correggere un piano sbagliato produce correzioni
sbagliate; si torna dall'Architetto con in mano cio' che e' gia' stato fatto.

**Rinuncia.** Il bilancio e' finito. Va detto, con quello che si sa: un sistema
che riprova per sempre non e' autonomo, e' bloccato.

**La diagnosi si fa sui fatti, non sul testo del modello.** Chiedere a un
modello perche' ha fallito produce una spiegazione plausibile, che e' un'altra
cosa dalla spiegazione vera. Qui si guardano il ledger — file che non
compilano, comandi eseguiti con il loro esito analizzato, scritture registrate
— e lo stato del task. Sono le stesse fonti su cui decide il cancello di
completamento, ed e' voluto: un sistema che giudica il successo e il fallimento
con due metri diversi finisce per contraddirsi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("autocorrezione")

RIPROVA = "riprova"
CORREGGI = "correggi"
RIPIANIFICA = "ripianifica"
RINUNCIA = "rinuncia"

#: Quante correzioni si concedono in un run. Oltre, non si sta piu' correggendo
#: un piano: se ne sta scrivendo un altro un pezzo per volta, e conviene dirlo.
CORREZIONI_MASSIME = 6

#: Quante volte si puo' tornare dall'Architetto. Due: la prima perche' il piano
#: era sbagliato, la seconda perche' lo era anche il rifacimento. Una terza
#: significa che il problema non e' il piano.
RIPIANIFICAZIONI_MASSIME = 2

#: Guasti che non parlano del lavoro. Rifare la stessa cosa e' sensato.
_TRANSITORI = (
    "timed out", "timeout", "interrotto dopo",
    "being used by another process", "resource busy", "text file busy",
    "permission denied", "accesso negato",
    "connection reset", "connection refused", "temporary failure",
    "einval", "eagain", "429", "503",
)

#: Guasti che dicono «cio' che credevi non c'e'». Non e' una svista del
#: lavoratore: e' il piano che descriveva un mondo diverso da quello reale.
_MONDO_DIVERSO = (
    "no such file or directory", "cannot find the path",
    "impossibile trovare il percorso", "non trova il percorso",
    "modulenotfounderror", "no module named",
    "importerror", "cannot find module",
    "command not found", "non e' riconosciuto come comando",
    "is not recognized as an internal or external command",
)


@dataclass
class Bilancio:
    """Quante mosse restano. Senza, l'autocorrezione non finisce mai."""

    correzioni: int = CORREZIONI_MASSIME
    ripianificazioni: int = RIPIANIFICAZIONI_MASSIME

    def puo_correggere(self) -> bool:
        return self.correzioni > 0

    def puo_ripianificare(self) -> bool:
        return self.ripianificazioni > 0

    def spendi(self, livello: str) -> None:
        if livello == CORREGGI:
            self.correzioni = max(0, self.correzioni - 1)
        elif livello == RIPIANIFICA:
            self.ripianificazioni = max(0, self.ripianificazioni - 1)

    def to_dict(self) -> Dict[str, Any]:
        return {"correzioni": self.correzioni,
                "ripianificazioni": self.ripianificazioni}


@dataclass
class Diagnosi:
    """La mossa successiva, e perche'."""

    livello: str
    motivo: str
    #: Chi dovrebbe fare la correzione, quando serve un task nuovo.
    ruolo: str = "coder"
    #: Cosa dirgli. Vuoto per `riprova` e `rinuncia`, che non creano lavoro.
    istruzione: str = ""
    #: I fatti su cui si e' deciso, per chi legge il resoconto.
    prove: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"livello": self.livello, "motivo": self.motivo,
                "ruolo": self.ruolo, "istruzione": self.istruzione,
                "prove": list(self.prove)}


def _testo_guasto(task: Any, snapshot: Dict[str, Any]) -> str:
    """Tutto cio' che si sa del guasto, in minuscolo, per cercarci dentro."""
    pezzi = [str(getattr(task, "error", "") or "")]
    for comando in (snapshot.get("commands") or [])[-4:]:
        if not comando.get("ok"):
            # `error` puo' essere il riassunto della verifica, che dice quanti
            # test sono falliti e non che il comando e' morto su un file
            # occupato: servono tutti e tre.
            pezzi.append(str(comando.get("error") or ""))
            pezzi.append(str(comando.get("stderr") or ""))
            pezzi.append(str(comando.get("stdout") or ""))
    return "\n".join(pezzi).lower()


def _file_del_task(task: Any) -> List[str]:
    dal_piano = (getattr(task, "metadata", None) or {}).get("files") or []
    modificati = list(getattr(task, "files_modified", None) or [])
    return [str(f) for f in list(dal_piano) + modificati if f]


def _comandi_falliti(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in (snapshot.get("commands") or []) if not c.get("ok")]


def _ha_prodotto_qualcosa(task: Any, snapshot: Dict[str, Any]) -> bool:
    if list(getattr(task, "files_modified", None) or []):
        return True
    return any(f.get("writes") or f.get("edits") or f.get("created")
               for f in (snapshot.get("files") or []))


def diagnostica(
    task: Any,
    snapshot: Optional[Dict[str, Any]] = None,
    bilancio: Optional[Bilancio] = None,
) -> Diagnosi:
    """La mossa successiva per un task fallito, decisa sui fatti.

    `task` e' un `TaskNode`; `snapshot` e' `DevSessionLedger.snapshot()`.
    L'ordine dei controlli e' l'ordine in cui le cause sono **riconoscibili**,
    non quello in cui sono probabili: un file che non compila e' un fatto, un
    comando andato storto per un percorso inesistente e' un fatto, e
    «l'agente non ha capito» e' un'ipotesi. Si decide sui fatti finche' ce ne
    sono, e solo dopo si ammette di non sapere.
    """
    snapshot = snapshot or {}
    bilancio = bilancio or Bilancio()
    guasto = _testo_guasto(task, snapshot)
    titolo = str(getattr(task, "title", "") or getattr(task, "id", ""))

    # 1. Un file scritto in questa sessione che non compila. E' la causa piu'
    #    netta che esista: si sa il file, si sa l'errore, e si sa chi lo ripara.
    #    E se un test e' fallito **per** quel file, riparare qui ripara anche
    #    quello: la causa da correggere e' una sola.
    rotti = [f for f in (snapshot.get("files") or [])
             if f.get("syntax_error") or f.get("last_error")]
    miei = set(_file_del_task(task))
    rotti_miei = [f for f in rotti if not miei or f.get("path") in miei] or rotti
    if rotti_miei:
        f = rotti_miei[0]
        errore = str(f.get("syntax_error") or f.get("last_error") or "")
        return Diagnosi(
            livello=CORREGGI if bilancio.puo_correggere() else RINUNCIA,
            motivo=f"«{f.get('path')}» non compila",
            ruolo="coder",
            istruzione=(
                f"Il file `{f.get('path')}` scritto per il task «{titolo}» "
                f"contiene un errore: {errore[:300]}\n"
                "Leggilo, correggi SOLO quell'errore e rileggilo per "
                "confermare. Non riscrivere il file da zero: il resto era "
                "giusto."
            ),
            prove=[f"{f.get('path')}: {errore[:160]}"],
        )

    # 2. Un guasto che non parla del lavoro: un comando scaduto, un file
    #    occupato, la rete. Va guardato PRIMA dell'esito della verifica, non
    #    dopo: `npm test` che muore su «resource busy» viene comunque
    #    classificato come test fallito dal parser, e correggere il codice per
    #    un file occupato significa cambiare cio' che funzionava.
    if any(segno in guasto for segno in _TRANSITORI):
        return Diagnosi(
            livello=RIPROVA,
            motivo="guasto transitorio: non riguarda il contenuto del lavoro",
            prove=[r for r in guasto.splitlines() if r.strip()][:2],
        )

    # 3. Una verifica eseguita che ha detto cosa non va. Il numero di test
    #    falliti e' un fatto, e il loro riassunto e' gia' stato estratto.
    for comando in reversed(_comandi_falliti(snapshot)):
        verifica = comando.get("verification") or {}
        if verifica.get("failed") or verifica.get("errors"):
            riassunto = str(verifica.get("summary")
                            or comando.get("error") or "")[:400]
            return Diagnosi(
                livello=CORREGGI if bilancio.puo_correggere() else RINUNCIA,
                motivo=(f"{verifica.get('failed', 0)} verifiche fallite su "
                        f"`{comando.get('command')}`"),
                ruolo="coder",
                istruzione=(
                    f"Il comando `{comando.get('command')}` fallisce dopo il "
                    f"task «{titolo}»:\n{riassunto}\n"
                    "Correggi il codice — non il test — finche' quel comando "
                    "non esce con 0. Rieseguilo per dimostrarlo."
                ),
                prove=[f"{comando.get('command')} -> {riassunto[:160]}"],
            )

    # 4. Il mondo non e' come il piano lo descriveva. Correggere qui
    #    produrrebbe una correzione costruita sullo stesso malinteso.
    if any(segno in guasto for segno in _MONDO_DIVERSO):
        motivo = "il task dava per esistente qualcosa che non c'e'"
        if bilancio.puo_ripianificare():
            return Diagnosi(
                livello=RIPIANIFICA, motivo=motivo, ruolo="architect",
                istruzione=(
                    f"Il task «{titolo}» e' fallito perche' cercava un file, "
                    "un modulo o un comando che non esiste. Guarda com'e' "
                    "fatto davvero il progetto e rifai la parte di piano che "
                    "resta. Cio' che e' gia' stato fatto non va rifatto."
                ),
                prove=[r for r in guasto.splitlines() if r.strip()][:2],
            )
        # Senza ripianificazioni resta il tentativo di correzione mirata: e'
        # meno probabile che funzioni, ma e' meglio del vicolo cieco.
        if bilancio.puo_correggere():
            return Diagnosi(
                livello=CORREGGI, motivo=motivo + " (ripianificazioni finite)",
                ruolo="coder",
                istruzione=(
                    f"Il task «{titolo}» cercava qualcosa che non esiste. "
                    "Prima di scrivere, ELENCA la cartella e LEGGI i file veri: "
                    "i nomi vanno presi da li', non dedotti."
                ),
                prove=[r for r in guasto.splitlines() if r.strip()][:2],
            )
        return Diagnosi(livello=RINUNCIA, motivo=motivo + ", e il bilancio e' finito")

    # 5. Tutti i turni spesi senza scrivere niente. Non e' un errore da
    #    correggere: e' un task che non si capiva, o che era troppo grande.
    if not _ha_prodotto_qualcosa(task, snapshot):
        motivo = "il task non ha prodotto nessuna modifica"
        if bilancio.puo_ripianificare():
            return Diagnosi(
                livello=RIPIANIFICA, motivo=motivo, ruolo="architect",
                istruzione=(
                    f"Il task «{titolo}» ha consumato i suoi turni senza "
                    "scrivere niente: era troppo grande o non abbastanza "
                    "preciso. Spezzalo in passi piu' piccoli, ognuno con i "
                    "file su cui lavorare e il comando che lo dimostra."
                ),
                prove=["nessuna scrittura registrata nel ledger"],
            )
        return Diagnosi(livello=RINUNCIA, motivo=motivo + ", e non si puo' ripianificare")

    # 6. Ha scritto qualcosa, e' fallito, e non si sa perche'. Si prova a
    #    correggere una volta dicendo esattamente questo: fingere una
    #    diagnosi sarebbe peggio che ammettere di non averla.
    if bilancio.puo_correggere():
        return Diagnosi(
            livello=CORREGGI,
            motivo="fallito senza una causa riconoscibile",
            ruolo="coder",
            istruzione=(
                f"Il task «{titolo}» e' fallito e il sistema non sa dire "
                "perche'. Rileggi i file che hai toccato, esegui la verifica "
                "del task e riporta cosa non torna prima di cambiare altro."
            ),
            prove=[r for r in guasto.splitlines() if r.strip()][:2],
        )
    return Diagnosi(livello=RINUNCIA,
                    motivo="fallito senza causa riconoscibile e senza bilancio")


def applica(pipeline: Any, task: Any, diagnosi: Diagnosi,
            bilancio: Optional[Bilancio] = None) -> Dict[str, Any]:
    """Esegue la mossa sulla pipeline. Ritorna cosa e' cambiato.

    Sta qui e non dentro `diagnostica` perche' sono due responsabilita'
    diverse: decidere e agire. Separate, la decisione si puo' verificare senza
    costruire una pipeline, ed e' quello che rende questi test leggibili.
    """
    bilancio = bilancio or Bilancio()
    esito: Dict[str, Any] = {"livello": diagnosi.livello, "motivo": diagnosi.motivo}

    if diagnosi.livello == RIPROVA:
        riprovato = pipeline.retry_task(task.id)
        esito["applicato"] = bool(riprovato)
        if not riprovato:
            # I tentativi del task erano finiti: bloccare cio' che ne dipende
            # e' l'unica cosa onesta da fare.
            pipeline.reorder_after_failure(task.id)
            esito["motivo"] = diagnosi.motivo + ", ma i tentativi erano finiti"
        return esito

    if diagnosi.livello == CORREGGI:
        nodo = pipeline.insert_fix_task(task.id, diagnosi.istruzione,
                                        role=diagnosi.ruolo)
        bilancio.spendi(CORREGGI)
        esito.update({"applicato": True, "fix_id": nodo.id, "ruolo": nodo.role})
        return esito

    if diagnosi.livello == RIPIANIFICA:
        bilancio.spendi(RIPIANIFICA)
        esito["applicato"] = True
        return esito

    # Rinuncia: si blocca cio' che dipendeva, perche' fingere che possa ancora
    # partire terrebbe il ventaglio ad aspettare qualcosa che non arrivera'.
    pipeline.reorder_after_failure(task.id)
    esito["applicato"] = False
    return esito


def contesto_per_ripianificare(pipeline: Any, diagnosi: Diagnosi,
                               obiettivo: str = "") -> str:
    """Cosa dire all'Architetto quando lo si richiama a meta' lavoro.

    Il punto delicato e' **non far rifare cio' che e' fatto**. Un piano nuovo
    scritto senza sapere cosa e' gia' successo riparte da zero, e il lavoro
    buono viene sovrascritto da lavoro identico o peggiore.
    """
    fatti, falliti, restanti = [], [], []
    for nodo in getattr(pipeline, "nodes", {}).values():
        stato = getattr(nodo.status, "value", str(nodo.status))
        riga = f"- {nodo.id}: {nodo.title}"
        if stato == "done":
            file_toccati = list(getattr(nodo, "files_modified", None) or [])
            if file_toccati:
                riga += " (" + ", ".join(file_toccati[:4]) + ")"
            fatti.append(riga)
        elif stato == "failed":
            falliti.append(riga + f" — {nodo.error or 'fallito'}")
        elif stato not in ("skipped",):
            restanti.append(riga)

    righe = [diagnosi.istruzione or "Il piano va rifatto."]
    if obiettivo.strip():
        righe += ["", f"OBIETTIVO: {obiettivo.strip()}"]
    if fatti:
        righe += ["", "GIA' FATTO — non rifarlo, e non riscrivere questi file:"] + fatti
    if falliti:
        righe += ["", "FALLITO:"] + falliti
    if restanti:
        righe += ["", "NON ANCORA ESEGUITO — e' questa la parte da ripensare:"] + restanti
    righe += [
        "",
        "Emetti un `pipeline` NUOVO con i soli task che restano da fare, "
        "ognuno con `role`, `description` e `depends_on`. Non includere i task "
        "gia' fatti: verrebbero eseguiti una seconda volta.",
    ]
    return "\n".join(righe)
