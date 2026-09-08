# ==============================================================================
# core/i18n/translator.py — Tradurre un catalogo senza rompere il codice
# Sigma Studio v8
# ==============================================================================
"""Traduzione a lotti di un catalogo di stringhe, con i segnaposto protetti.

Tradurre un'interfaccia non e' tradurre delle frasi: dentro le frasi ci sono
pezzi che **non sono lingua**. `{nome}` viene sostituito a runtime, `%s` lo
riempie Python, `<0>` e' un elemento React che avvolge una parte del testo. Un
modello che traduce «Ciao {nome}» in «Hello {name}» ha prodotto una stringa
che a runtime mostra letteralmente `{name}`, e nessuno se ne accorge finche'
qualcuno non apre quella schermata.

Per questo i segnaposto vengono **mascherati prima** e **rimessi dopo**, e alla
fine si controlla che ci siano ancora tutti. Una traduzione che ha perso un
segnaposto viene scartata: meglio la stringa originale, che almeno funziona.

Il glossario serve alla seconda categoria di errori: i nomi propri. «Sigma
Studio», «GGUF», «worktree» non si traducono, e un modello lasciato libero li
traduce.

**Questo modulo non parla con un modello.** Riceve una funzione che traduce un
lotto di stringhe e si occupa di tutto il resto: mascherare, spezzare in lotti,
validare, riprovare cio' che non ha superato la validazione, riferire. Cosi' e'
verificabile senza un modello acceso, e funziona con qualunque provider.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from core.logger import get_logger

log = get_logger("i18n.translator")

#: Le forme che nei testi di questo progetto non sono lingua.
#:
#: L'ordine conta: `{{doppie}}` prima di `{singole}`, altrimenti la seconda
#: espressione spezzerebbe la prima a meta'.
_SEGNAPOSTO = re.compile(
    r"(\{\{[^{}]*\}\}"          # {{mustache}}
    r"|\{[^{}\s][^{}]*\}"       # {nome}, {count, plural, ...}
    r"|%\([^)]+\)[sdifr]"       # %(nome)s
    r"|%[sdifr]"                # %s
    r"|</?\d+>"                 # <0> </0>, interpolazione JSX/i18next
    r"|\$\d+"                   # $1
    r"|\{\{?\s*\w+\s*\}?\}"     # varianti con spazi
    r")"
)

#: Quante stringhe per chiamata. Lotti grandi risparmiano viaggi ma rendono piu'
#: probabile che il modello salti una voce o cambi l'ordine; venticinque e' il
#: punto in cui il controllo resta facile.
LOTTO_PREDEFINITO = 25


@dataclass
class Esito:
    """Il risultato di una traduzione, con cio' che non e' andato."""

    translations: Dict[str, str] = field(default_factory=dict)
    #: chiave -> perche' la traduzione e' stata scartata
    problems: Dict[str, str] = field(default_factory=dict)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    def to_dict(self) -> Dict[str, Any]:
        return {"translations": self.translations, "problems": self.problems,
                "checked": self.checked}

    def check_line(self, nome: str = "i18n-translate") -> str:
        """La riga che l'harness sa leggere come prova.

        `checked` non e' decorazione: una traduzione che non ha esaminato niente
        esce bene esattamente come una che ha esaminato tutto.
        """
        return "SIGMA-CHECK " + json.dumps(
            {"check": nome, "checked": self.checked, "problems": len(self.problems)},
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Segnaposto
# ---------------------------------------------------------------------------


def find_placeholders(testo: str) -> List[str]:
    """I pezzi di `testo` che non sono lingua."""
    return _SEGNAPOSTO.findall(str(testo or ""))


def protect(testo: str) -> Tuple[str, Dict[str, str]]:
    """Sostituisce i segnaposto con segni che un traduttore non tocca.

    I segni sono `⟦0⟧`, `⟦1⟧`… — caratteri che non appartengono a nessuna
    lingua naturale e che nessun modello prova a tradurre. Usare `__0__` o
    simili non basterebbe: capita che vengano riscritti come `_0_` o spaziati.
    """
    mappa: Dict[str, str] = {}
    contatore = {"n": 0}

    def sostituisci(m: "re.Match[str]") -> str:
        segno = f"⟦{contatore['n']}⟧"
        mappa[segno] = m.group(0)
        contatore["n"] += 1
        return segno

    return _SEGNAPOSTO.sub(sostituisci, str(testo or "")), mappa


def restore(testo: str, mappa: Dict[str, str]) -> str:
    """Rimette i segnaposto al posto dei segni."""
    risultato = str(testo or "")
    for segno, originale in mappa.items():
        risultato = risultato.replace(segno, originale)
    return risultato


def validate(originale: str, tradotto: str) -> str:
    """Perche' una traduzione non e' utilizzabile, o stringa vuota se lo e'.

    Si confrontano i segnaposto per **multinsieme**: uno perso rompe la
    schermata, e uno duplicato di solito significa che il modello ha ripetuto
    un pezzo di frase.
    """
    if not str(tradotto or "").strip():
        return "traduzione vuota"

    attesi = Counter(find_placeholders(originale))
    trovati = Counter(find_placeholders(tradotto))
    if attesi != trovati:
        # Per conteggio, non per appartenenza: un segnaposto ripetuto due volte
        # e' presente in entrambi gli insiemi, e un confronto per appartenenza
        # direbbe «alterati» senza saper dire cosa — un messaggio che non aiuta
        # nessuno a capire cosa e' andato storto.
        mancanti = attesi - trovati
        aggiunti = trovati - attesi
        pezzi = []
        if mancanti:
            pezzi.append("mancano " + ", ".join(sorted(mancanti.elements())))
        if aggiunti:
            pezzi.append("compaiono in piu' " + ", ".join(sorted(aggiunti.elements())))
        return "segnaposto alterati: " + "; ".join(pezzi)

    if "⟦" in tradotto or "⟧" in tradotto:
        return "segni di protezione rimasti nel testo"
    return ""


def check_glossary(tradotto: str, glossario: Iterable[str]) -> str:
    """Verifica che i termini che non si traducono siano ancora li'.

    Vale solo per i termini presenti nell'originale: chiedere che «GGUF»
    compaia in una frase che non lo conteneva sarebbe assurdo. Il controllo
    vero lo fa `translate_catalog`, che ha entrambi i testi.
    """
    mancanti = [t for t in glossario if t and t not in tradotto]
    return ("termini da non tradurre spariti: " + ", ".join(mancanti)) if mancanti else ""


# ---------------------------------------------------------------------------
# Traduzione di un catalogo
# ---------------------------------------------------------------------------

#: La funzione che parla col modello: riceve le stringhe mascherate e la lingua,
#: restituisce le traduzioni nello stesso ordine.
Traduttore = Callable[[List[str], str], List[str]]


def build_prompt(testi: Sequence[str], lingua: str,
                 glossario: Optional[Sequence[str]] = None) -> str:
    """Il messaggio per il modello. Sta qui perche' e' parte del contratto.

    Chiede JSON perche' un elenco numerato in testo libero si sfalsa alla prima
    stringa che contiene un a capo, e a quel punto ogni traduzione finisce sulla
    chiave sbagliata — un errore silenzioso e difficilissimo da vedere.
    """
    righe = [
        f"Traduci in {lingua} le stringhe di interfaccia qui sotto.",
        "",
        "Regole:",
        "- I segni come ⟦0⟧ sono segnaposto: riportali IDENTICI, nella "
        "posizione che ha senso nella lingua d'arrivo. Non tradurli, non "
        "cambiarne il numero, non aggiungerne.",
        "- Mantieni il registro di un'interfaccia: breve, diretto, senza punto "
        "finale se non ce l'ha l'originale.",
        "- Se una stringa e' gia' nella lingua d'arrivo, riportala uguale.",
    ]
    if glossario:
        righe.append(
            "- NON tradurre questi termini, lasciali come sono: "
            + ", ".join(glossario)
        )
    righe += [
        "",
        "Rispondi SOLO con un array JSON di stringhe, nello stesso ordine e "
        "della stessa lunghezza dell'elenco ricevuto.",
        "",
        json.dumps(list(testi), ensure_ascii=False, indent=1),
    ]
    return "\n".join(righe)


def parse_response(risposta: str, attese: int) -> List[str]:
    """Estrae l'array JSON dalla risposta del modello.

    Tollerante sul contorno — i modelli aggiungono volentieri un «Ecco:» o un
    blocco markdown — e rigido sulla lunghezza: un array piu' corto significa
    che le traduzioni successive finirebbero sulle chiavi sbagliate, ed e'
    meglio nessuna traduzione che tutte spostate di uno.
    """
    testo = str(risposta or "").strip()
    inizio, fine = testo.find("["), testo.rfind("]")
    if inizio < 0 or fine <= inizio:
        return []
    try:
        dati = json.loads(testo[inizio:fine + 1])
    except ValueError:
        return []
    if not isinstance(dati, list) or len(dati) != attese:
        return []
    return [str(v) for v in dati]


def translate_catalog(
    catalogo: Dict[str, str],
    lingua: str,
    traduttore: Traduttore,
    glossario: Optional[Sequence[str]] = None,
    lotto: int = LOTTO_PREDEFINITO,
    gia_tradotto: Optional[Dict[str, str]] = None,
) -> Esito:
    """Traduce un catalogo `chiave -> testo`, scartando cio' che non regge.

    `gia_tradotto` e' cio' che esiste dalla volta scorsa: le chiavi gia'
    presenti non vengono ritradotte. Su un catalogo di duemila voci e' la
    differenza fra un aggiornamento e una traduzione da capo.
    """
    esistenti = dict(gia_tradotto or {})
    da_fare = [(k, v) for k, v in catalogo.items()
               if k not in esistenti and str(v or "").strip()]

    esito = Esito(translations=dict(esistenti))
    termini = [t for t in (glossario or []) if t]

    for i in range(0, len(da_fare), max(1, int(lotto))):
        pezzo = da_fare[i:i + max(1, int(lotto))]
        chiavi = [k for k, _ in pezzo]
        originali = [v for _, v in pezzo]

        mascherati, mappe = [], []
        for testo in originali:
            m, mappa = protect(testo)
            mascherati.append(m)
            mappe.append(mappa)

        try:
            risposte = traduttore(mascherati, lingua)
        except Exception as exc:
            log.warning("[i18n] lotto non tradotto: %s", exc)
            for chiave in chiavi:
                esito.problems[chiave] = f"traduttore fallito: {exc}"
            esito.checked += len(chiavi)
            continue

        if len(risposte) != len(chiavi):
            # Un lotto disallineato metterebbe ogni traduzione sulla chiave
            # sbagliata: si scarta tutto il lotto, non si prova a indovinare.
            for chiave in chiavi:
                esito.problems[chiave] = "risposta del modello disallineata"
            esito.checked += len(chiavi)
            continue

        for chiave, originale, mappa, grezza in zip(chiavi, originali, mappe, risposte):
            esito.checked += 1
            tradotta = restore(grezza, mappa)
            motivo = validate(originale, tradotta)
            if not motivo and termini:
                presenti = [t for t in termini if t in originale]
                motivo = check_glossary(tradotta, presenti)
            if motivo:
                esito.problems[chiave] = motivo
                # Meglio l'originale, che almeno funziona, di una traduzione
                # che rompe la schermata.
                esito.translations[chiave] = originale
            else:
                esito.translations[chiave] = tradotta

    return esito


def make_model_translator(
    genera: Callable[[str], str],
    glossario: Optional[Sequence[str]] = None,
) -> Traduttore:
    """Un traduttore che usa un modello, da una funzione `prompt -> testo`.

    Tiene separato *cosa chiedere* da *a chi chiederlo*: il provider lo sceglie
    chi chiama, e questo modulo resta verificabile senza un modello acceso.
    """
    def traduttore(testi: List[str], lingua: str) -> List[str]:
        risposta = genera(build_prompt(testi, lingua, glossario))
        tradotte = parse_response(risposta, len(testi))
        if not tradotte:
            raise ValueError("il modello non ha restituito un array JSON valido")
        return tradotte

    return traduttore
