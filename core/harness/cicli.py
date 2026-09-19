# ==============================================================================
# core/harness/cicli.py — Riconoscere un ciclo di azioni, non solo una ripetizione
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""La guardia contro le azioni che si ripetono senza portare da nessuna parte.

Quella che c'era prima riconosceva una cosa sola: la **stessa identica
chiamata**, dopo che era gia' fallita. Tre buchi la rendevano aggirabile senza
farlo apposta.

**La firma era il JSON esatto.** Uno spazio in piu', una chiave riordinata, un
`./` davanti al percorso: firma diversa, e la stessa chiamata passava. Un
modello che riprova non riscrive mai due volte esattamente gli stessi byte.

**Il ciclo a due mosse non si vedeva.** `edit_file` fallisce, `read_file`
riesce, `edit_file` fallisce di nuovo: nessuna chiamata e' ripetuta *di
seguito*, e la guardia non diceva niente. E' la forma piu' comune di stallo,
perche' ogni giro sembra un tentativo nuovo.

**Una scrittura riuscita cancellava tutta la memoria.** Bastava un
`write_file` andato a buon fine per dimenticare ogni fallimento precedente,
compresi quelli su file che quella scrittura non aveva toccato.

Il discriminante resta quello giusto — **il workspace e' cambiato in mezzo?** —
perche' dopo una modifica vera riprovare non e' ripetersi: e' il ciclo
correggi-verifica, l'unico modo che l'agente ha di sapere se ha finito.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

#: Quante azioni tenere in finestra. Oltre, un ciclo lungo sarebbe comunque
#: piu' facile da leggere dal ledger che da qui.
FINESTRA_MASSIMA = 12

#: Lunghezze di sequenza che vengono cercate. 1 e' la ripetizione secca, 2 e 3
#: sono il ciclo a due e tre mosse.
LUNGHEZZE_CICLO = (2, 3)

#: I parametri che nominano un file. Vengono normalizzati come percorsi.
CHIAVI_PERCORSO = ("path", "file", "file_path", "percorso", "dir", "directory")


def _normalizza_percorso(valore: str, radice: str = "") -> str:
    """Lo stesso file scritto in modi diversi diventa la stessa stringa."""
    testo = str(valore).strip().strip("'\"`").replace("\\", "/")
    testo = re.sub(r"^\./+", "", testo)
    if radice:
        radice_norm = str(radice).replace("\\", "/").rstrip("/")
        if testo.lower().startswith(radice_norm.lower() + "/"):
            testo = testo[len(radice_norm) + 1:]
    return os.path.normpath(testo).replace("\\", "/").lower()


def _normalizza_valore(chiave: str, valore: Any, radice: str) -> Any:
    if isinstance(valore, str):
        if chiave.lower() in CHIAVI_PERCORSO:
            return _normalizza_percorso(valore, radice)
        # Gli spazi non cambiano cosa fa una chiamata, ma cambiavano la firma.
        return " ".join(valore.split())
    if isinstance(valore, dict):
        return {k: _normalizza_valore(k, v, radice) for k, v in sorted(valore.items())}
    if isinstance(valore, list):
        return [_normalizza_valore(chiave, v, radice) for v in valore]
    return valore


def firma(tool: str, params: Any, radice: str = "", limite: int = 600) -> Tuple[str, str]:
    """La firma di una chiamata, insensibile a cio' che non cambia il suo effetto."""
    nome = str(tool or "").strip().lower()
    if isinstance(params, dict):
        normalizzati = {k: _normalizza_valore(k, v, radice)
                        for k, v in sorted(params.items())}
    else:
        normalizzati = _normalizza_valore("", params, radice)
    try:
        testo = json.dumps(normalizzati, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        testo = str(normalizzati)
    return nome, testo[:limite]


def _percorso_toccato(params: Any, radice: str) -> Optional[str]:
    if not isinstance(params, dict):
        return None
    for chiave in CHIAVI_PERCORSO:
        if chiave in params and isinstance(params[chiave], str):
            return _normalizza_percorso(params[chiave], radice)
    return None


class RilevatoreCicli:
    """Tiene la finestra delle azioni e dice quando si sta girando in tondo.

    La finestra si azzera quando il workspace cambia: e' il solo momento in cui
    una chiamata gia' vista puo' dare un risultato diverso.
    """

    def __init__(self, radice: str = "") -> None:
        self.radice = radice
        self._finestra: List[Tuple[str, str, bool]] = []
        #: Firme che hanno gia' fallito, con il file che nominavano. Il file
        #: serve a cancellare solo cio' che una scrittura ha davvero reso
        #: ritentabile.
        self._fallite: Dict[Tuple[str, str], Optional[str]] = {}
        #: Elenchi gia' ottenuti: rieseguirli non puo' insegnare niente.
        self._inerti: set = set()

    # -- registrazione ------------------------------------------------------

    def registra(self, tool: str, params: Any, riuscito: bool,
                 workspace_cambiato: bool = False) -> None:
        chiave = firma(tool, params, self.radice)
        self._finestra.append((chiave[0], chiave[1], riuscito))
        del self._finestra[:-FINESTRA_MASSIMA]

        if riuscito:
            self._fallite.pop(chiave, None)
        else:
            self._fallite[chiave] = _percorso_toccato(params, self.radice)

        if workspace_cambiato:
            self.workspace_cambiato(_percorso_toccato(params, self.radice))

    def workspace_cambiato(self, percorso: Optional[str] = None) -> None:
        """Il disco e' cambiato: la finestra non descrive piu' il presente.

        Delle firme fallite si dimenticano solo quelle che nominavano il file
        toccato. Cancellarle tutte — com'era prima — significava che un
        `write_file` riuscito riabilitava anche i tentativi su file che non
        c'entravano, e il ciclo ricominciava da capo.
        """
        self._finestra.clear()
        self._inerti.clear()
        if percorso is None:
            self._fallite.clear()
            return
        self._fallite = {k: v for k, v in self._fallite.items() if v != percorso}

    def registra_inerte(self, tool: str, params: Any) -> None:
        self._inerti.add(firma(tool, params, self.radice))

    # -- interrogazione -----------------------------------------------------

    def gia_fallita(self, tool: str, params: Any) -> bool:
        return firma(tool, params, self.radice) in self._fallite

    def gia_inerte(self, tool: str, params: Any) -> bool:
        return firma(tool, params, self.radice) in self._inerti

    def ciclo_in_corso(self, tool: str, params: Any) -> Optional[str]:
        """La descrizione del ciclo che questa chiamata chiuderebbe, o `None`.

        Guarda la finestra **con in coda la chiamata proposta**: serve a
        fermarla prima che venga eseguita, non a constatarla dopo.
        """
        nome, corpo = firma(tool, params, self.radice)
        sequenza = [(t, c) for t, c, _ in self._finestra] + [(nome, corpo)]

        for k in LUNGHEZZE_CICLO:
            if len(sequenza) < 2 * k:
                continue
            coda = sequenza[-2 * k:]
            if coda[:k] == coda[k:]:
                passi = " -> ".join(t for t, _ in coda[:k])
                return (
                    f"la sequenza {passi} si e' gia' ripetuta identica e nel "
                    f"frattempo nessun file e' cambiato"
                )
        return None

    @property
    def finestra(self) -> List[Tuple[str, str, bool]]:
        return list(self._finestra)


def comando_bloccato_in_ciclo(ledger: Any, soglia: int = 2) -> Optional[Dict[str, str]]:
    """Il comando che si ripete identico senza che niente cambi.

    La guardia precedente scattava **solo se l'ultima esecuzione era andata
    bene**, e il caso frequente e' l'opposto: `pytest` che fallisce identico
    cinque volte di fila perche' fra un tentativo e l'altro non e' stato
    corretto niente. Il contatore del ledger si azzera a ogni scrittura
    riuscita, quindi arrivare a due vuol dire davvero «due volte di seguito,
    stesso comando, nessuna modifica in mezzo».

    Ritorna `{"esito": "ok"|"fallito", "comando": ..., "volte": ...}` o `None`.
    """
    try:
        volte = int(getattr(ledger, "_consecutive_dup_commands", 0) or 0)
        comandi = list(getattr(ledger, "_commands", []) or [])
    except Exception:
        return None

    if volte < soglia or not comandi:
        return None

    ultimo = comandi[-1]
    return {
        "esito": "ok" if ultimo.get("ok") else "fallito",
        "comando": str(ultimo.get("command") or ""),
        "errore": str(ultimo.get("error") or "")[:400],
        "volte": str(volte),
    }
