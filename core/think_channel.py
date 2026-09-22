# ==============================================================================
# core/think_channel.py — Dove finisce il ragionamento e comincia la risposta
# Sigma Studio v8
# ==============================================================================
"""Separare pensiero e risposta senza farsi ingannare da chi ne parla.

Il difetto, visto dal vivo il 22 settembre 2026 e riprodotto qui sotto: la chat
faceva il ragionamento e **non rispondeva**. Non era il modello.

Chi separava i due canali cercava i tag come sottostringhe, ovunque. Quando il
modello **ragionava sui tag** — cosa che fa spesso, perche' gli si chiede di
diagnosticare un output rotto — scriveva nel proprio ragionamento frasi come::

    Il modello ha dimenticato di emettere </think> e il testo si e' rotto.

e succedevano tre cose insieme:

1. **Il tag veniva cancellato dal testo.** Il ragionamento arrivava all'utente
   come «ho visto tag `` sparsi nel mezzo»: due backtick vuoti, e da li' in poi
   il markdown si rompeva perche' il primo backtick restava aperto.
2. **Il canale si ribaltava a meta' frase.** Quel `</think>` citato chiudeva il
   blocco, e tutto il ragionamento rimanente finiva nella bolla della risposta.
3. **La risposta vera spariva.** Se piu' avanti il ragionamento nominava di
   nuovo un tag di apertura, il canale tornava «pensiero» e la risposta finiva
   li' dentro: l'utente vedeva ragionare e non vedeva rispondere.

La regola che chiude tutti e tre i casi e' strutturale, non linguistica:

    **Un tag e' un comando solo se sta all'inizio della sua riga.**

I modelli emettono i tag da soli — ``<think>\\n…\\n</think>\\n`` — mentre chi li
*nomina* li mette in mezzo a una frase, o fra backtick. Se davanti al tag, sulla
stessa riga, c'e' del testo, quel tag e' testo anche lui: **si lascia dov'e'**,
non si cancella.

In piu': il blocco di ragionamento si chiude **una volta sola**. Dopo la
chiusura ogni altro tag e' testo, qualunque cosa dica — perche' un modello che
ha iniziato a rispondere non torna a pensare, e sbagliare in quella direzione
significa perdere la risposta.

Questo modulo e' uno solo perche' i canali erano due: la chat e il ciclo
dell'agente separavano pensiero e risposta con due implementazioni diverse, e
divergevano. Ora chi cambia la regola la cambia per entrambi.
"""

from __future__ import annotations

import re
from typing import List, Tuple

#: I tag che i modelli usano per delimitare il ragionamento.
TAG_PENSIERO = re.compile(
    r"</?(?:think|thinking|reasoning|rationale|scratchpad|thought)>"
    r"|<\|channel\>thought"
    r"|<\|channel\|\>thought"
    r"|<channel\|>"
    r"|<\|channel\|\>"
    r"|</?\|?thought\|?>",
    re.IGNORECASE,
)

#: Quanto tenere in sospeso in coda al buffer per non spezzare un tag a meta'
#: fra due pacchetti dello stream. `<|channel|>thought` e' il piu' lungo.
CODA_SOSPESA = 20

CANALE_RISPOSTA = "token"
CANALE_PENSIERO = "thinking"


def _e_chiusura(tag: str) -> bool:
    t = tag.lower()
    return (
        t.startswith("</")
        or "channel|" in t
        or "/thought" in t
        or t.startswith("<response")
        or t.startswith("<output")
        or t.startswith("<answer")
    )


class RouterPensiero:
    """Instrada uno stream di token nei due canali, un pezzo alla volta.

    Si usa chiamando `feed()` su ogni pacchetto e `flush()` alla fine. Ritorna
    una lista di `(canale, testo)` dove canale e' `"token"` o `"thinking"`.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._in_pensiero = False
        #: Vero dopo il primo tag di chiusura vero. Da li' in poi nessun tag e'
        #: piu' un comando: il blocco di ragionamento e' uno solo.
        self._blocco_chiuso = False
        #: Vero se sulla riga in corso e' gia' stato emesso del testo. E' cio'
        #: che distingue un tag emesso da un tag citato.
        self._riga_sporca = False
        #: Quanto testo non bianco e' finito nel canale risposta. Serve a chi
        #: chiama per sapere se una risposta c'e' stata davvero.
        self.caratteri_risposta = 0

    # -- stato ---------------------------------------------------------------

    @property
    def in_pensiero(self) -> bool:
        return self._in_pensiero

    def inizia_nel_pensiero(self) -> None:
        """Parte come se un tag di apertura fosse gia' arrivato.

        Serve al prefill: quando si inietta `<think>` come inizio del turno
        dell'assistente, il modello continua **dentro** il blocco e non emette
        nessun tag di apertura. Senza questo il ragionamento finirebbe tutto
        nella risposta.

        Esiste come metodo e non come attributo da scrivere dall'esterno
        perche' era gia' successo: chi prefillava toccava `_in_thinking` a
        mano, e al primo cambio di nome quella riga ha smesso di fare
        qualcosa senza che nessun test se ne accorgesse.
        """
        self._in_pensiero = True

    @property
    def risposta_vuota(self) -> bool:
        """Nessun testo utile e' arrivato nel canale della risposta."""
        return self.caratteri_risposta == 0

    # -- interni -------------------------------------------------------------

    def _canale(self) -> str:
        return CANALE_PENSIERO if self._in_pensiero else CANALE_RISPOSTA

    def _aggiorna_riga(self, testo: str) -> None:
        """Ricorda se la riga in corso ha gia' del testo davanti."""
        if not testo:
            return
        ultimo_a_capo = testo.rfind("\n")
        if ultimo_a_capo == -1:
            self._riga_sporca = self._riga_sporca or bool(testo.strip())
        else:
            self._riga_sporca = bool(testo[ultimo_a_capo + 1:].strip())

    def _emetti(self, fuori: List[Tuple[str, str]], testo: str) -> None:
        if not testo:
            return
        canale = self._canale()
        if canale == CANALE_RISPOSTA:
            self.caratteri_risposta += len(testo.strip())
        fuori.append((canale, testo))
        self._aggiorna_riga(testo)

    # -- uso -----------------------------------------------------------------

    def feed(self, testo: str) -> List[Tuple[str, str]]:
        self._buffer += testo
        fuori: List[Tuple[str, str]] = []

        while True:
            trovato = TAG_PENSIERO.search(self._buffer)
            if not trovato:
                break

            prima = self._buffer[: trovato.start()]
            tag = trovato.group()
            self._buffer = self._buffer[trovato.end():]

            # `prima` decide se il tag apre la riga: se contiene un a capo,
            # conta solo quello che viene dopo; altrimenti vale lo stato che
            # avevamo gia'.
            if "\n" in prima:
                coda_riga = prima[prima.rfind("\n") + 1:]
                apre_la_riga = not coda_riga.strip()
            else:
                coda_riga = prima
                apre_la_riga = not (self._riga_sporca or prima.strip())

            # Il carattere subito prima del tag distingue un tag **emesso** da
            # un tag **nominato**. Chi lo emette lo attacca al testo —
            # `Rifletto.</think>Ciao` — chi lo nomina ci mette uno spazio
            # davanti, o lo chiude fra backtick: `il tag </think> serve a…`.
            #
            # Con la sola regola «deve aprire la riga» il blocco compatto su
            # una riga sola non si sarebbe mai chiuso.
            ultimo_carattere = coda_riga[-1:] if coda_riga else ""
            attaccato = bool(ultimo_carattere) and ultimo_carattere not in " \t`*_\"'("

            self._emetti(fuori, prima)

            e_comando = (apre_la_riga or attaccato) and not self._blocco_chiuso
            # Un tag di apertura deve aprire la riga: nessun modello comincia a
            # ragionare a meta' frase, mentre chi ne parla lo fa sempre.
            if e_comando and not _e_chiusura(tag) and not apre_la_riga:
                e_comando = False
            if not e_comando:
                # Testo, non comando: va lasciato dov'e'. Cancellarlo e' cio'
                # che spezzava i backtick e rompeva il markdown a valle.
                self._emetti(fuori, tag)
                continue

            if _e_chiusura(tag):
                self._in_pensiero = False
                self._blocco_chiuso = True
            else:
                self._in_pensiero = True

        # Un tag puo' essere arrivato a meta': si trattiene la coda finche' non
        # si sa se e' un tag o solo un minore.
        taglio = self._buffer.rfind("<")
        if taglio != -1 and len(self._buffer) - taglio <= CODA_SOSPESA:
            da_emettere, self._buffer = self._buffer[:taglio], self._buffer[taglio:]
        else:
            da_emettere, self._buffer = self._buffer, ""

        self._emetti(fuori, da_emettere)
        return fuori

    def flush(self) -> List[Tuple[str, str]]:
        """Cio' che resta quando lo stream e' finito.

        Se il modello non ha mai chiuso il blocco, quello che resta **non** e'
        ragionamento: e' tutto quello che l'utente avrebbe dovuto leggere. Una
        risposta vuota e' il guasto peggiore, e qui si evita.
        """
        if not self._buffer:
            return []
        resto, self._buffer = self._buffer, ""
        canale = self._canale()
        if canale == CANALE_PENSIERO and self.risposta_vuota and resto.strip():
            canale = CANALE_RISPOSTA
            self.caratteri_risposta += len(resto.strip())
        return [(canale, resto)]


def separa(testo: str) -> Tuple[str, str]:
    """Divide un testo gia' completo in `(risposta, ragionamento)`.

    Serve a chi riceve la generazione tutta insieme invece che a pacchetti.
    """
    router = RouterPensiero()
    pezzi = router.feed(testo) + router.flush()
    risposta = "".join(t for c, t in pezzi if c == CANALE_RISPOSTA)
    pensiero = "".join(t for c, t in pezzi if c == CANALE_PENSIERO)
    return risposta, pensiero
