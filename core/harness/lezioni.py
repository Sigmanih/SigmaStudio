# ==============================================================================
# core/harness/lezioni.py — Cosa ha imparato il tentativo prima
# ==============================================================================
"""Un secondo tentativo che ricomincia da zero ripaga la stessa scoperta.

Il task `frontend` della Biblioteca Digitale e' stato tentato tre volte, ventisei
turni ciascuna. In tutte e tre il modello ha capito il problema — la prova
dichiarata usava `&&`, che Windows PowerShell 5.1 non sa leggere — e in tutte e
tre ha scritto da solo la forma giusta:

    cd frontend; npm install --no-audit --no-fund; if ($LASTEXITCODE -eq 0) { npm run build }

che e' esattamente la traduzione finita poi in `adatta_alla_shell`. Poi il run
finiva, il tentativo dopo partiva con la memoria vuota, e la stessa scoperta
veniva rifatta da capo. Ottanta turni per sapere tre volte la stessa cosa.

Noi non ricominciamo un debug con l'amnesia: la prima domanda e' «l'altra volta
dove eravamo arrivati?». Questo modulo prepara quella risposta.

Due cose, e la seconda e' quella che un umano fa senza accorgersene:

- **cosa e' successo**: file scritti, comandi riusciti, comandi falliti col
  loro errore, criteri soddisfatti, come e' finita;
- **cosa non torna**: lo stesso comando che due volte ha dato esiti diversi.
  E' la firma di un guasto che non sta nel codice — l'ambiente, un test che
  dipende da uno stato condiviso, una corsa fra processi. Il registro quei
  fatti li ha gia' tutti; nessuno calcolava la differenza. Sulla Biblioteca
  `node --test a.test.js b.test.js` dava zero e uno a giorni alterni, perche'
  i due file giravano in processi paralleli sullo stesso archivio: cinque test
  su dieci fallivano, mai gli stessi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Quanti comandi si riportano per parte. La lezione va nel prompt del
#: tentativo dopo: deve stare in una schermata, o smette di essere letta.
MAX_COMANDI = 4

#: Quante lezioni si conservano per voce. Oltre la seconda, il problema non e'
#: piu' la memoria.
MAX_LEZIONI = 3

#: Quanto di un errore si conserva. Abbastanza per riconoscerlo.
MAX_ERRORE = 220


@dataclass
class Lezione:
    """Cosa ha imparato un tentativo, per quello dopo."""

    tentativo: int = 0
    turni: int = 0
    esito: str = ""
    file: List[str] = field(default_factory=list)
    riusciti: List[str] = field(default_factory=list)
    falliti: List[Dict[str, str]] = field(default_factory=list)
    criteri_ok: int = 0
    criteri_totali: int = 0
    #: Lo stesso comando con esiti diversi: non e' il codice.
    incoerenze: List[str] = field(default_factory=list)
    #: La prova che il tentativo aveva contestato, se accettata.
    prova_sostituita: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tentativo": self.tentativo, "turni": self.turni,
            "esito": self.esito, "file": list(self.file),
            "riusciti": list(self.riusciti), "falliti": list(self.falliti),
            "criteri_ok": self.criteri_ok, "criteri_totali": self.criteri_totali,
            "incoerenze": list(self.incoerenze),
            "prova_sostituita": self.prova_sostituita,
        }

    @staticmethod
    def from_dict(dati: Dict[str, Any]) -> "Lezione":
        return Lezione(
            tentativo=int(dati.get("tentativo") or 0),
            turni=int(dati.get("turni") or 0),
            esito=str(dati.get("esito") or ""),
            file=list(dati.get("file") or []),
            riusciti=list(dati.get("riusciti") or []),
            falliti=list(dati.get("falliti") or []),
            criteri_ok=int(dati.get("criteri_ok") or 0),
            criteri_totali=int(dati.get("criteri_totali") or 0),
            incoerenze=list(dati.get("incoerenze") or []),
            prova_sostituita=str(dati.get("prova_sostituita") or ""),
        )


def incoerenze(comandi: List[Dict[str, Any]]) -> List[str]:
    """Gli stessi comandi che hanno dato esiti diversi nello stesso run.

    E' il ragionamento che un umano fa per primo e che nessuno qui faceva:
    *stesso comando, risposte diverse — allora non e' il codice*. Le cause
    possibili sono poche e tutte fuori dal sorgente: uno stato condiviso su
    disco, due processi che si pestano, la rete, un file ancora aperto.

    Si guarda il codice di uscita e non `ok`, perche' due fallimenti diversi
    fra loro dicono qualcosa che due fallimenti uguali non dicono.
    """
    per_comando: Dict[str, List[Any]] = {}
    for voce in comandi or []:
        testo = str(voce.get("command") or "").strip()
        if not testo:
            continue
        per_comando.setdefault(testo, []).append(voce.get("returncode"))

    fuori: List[str] = []
    for testo, codici in per_comando.items():
        distinti = {c for c in codici if c is not None}
        if len(distinti) < 2:
            continue
        elenco = ", ".join(str(c) for c in sorted(distinti, key=lambda x: str(x)))
        fuori.append(
            f"`{testo[:100]}` ha dato esiti diversi ({elenco}) nello stesso run: "
            "se il codice non e' cambiato fra una volta e l'altra, la causa non "
            "sta nel codice — guarda lo stato condiviso, i processi in parallelo, "
            "l'ambiente."
        )
    return fuori


def estrai(tentativo: int, snapshot: Optional[Dict[str, Any]],
           esito: str = "", turni: int = 0) -> Lezione:
    """La lezione di un tentativo, dai fatti che ha lasciato nel registro."""
    lezione = Lezione(tentativo=int(tentativo or 0), turni=int(turni or 0),
                      esito=str(esito or "")[:300])
    dati = snapshot or {}

    lezione.file = [str(f.get("path") or "") for f in (dati.get("files") or [])
                    if (f.get("writes") or f.get("edits"))][:8]

    comandi = list(dati.get("commands") or [])
    riusciti, falliti = [], []
    for voce in comandi:
        testo = str(voce.get("command") or "").strip()
        if not testo:
            continue
        if voce.get("ok"):
            if testo not in riusciti:
                riusciti.append(testo)
        else:
            errore = str(voce.get("error") or voce.get("stderr") or "").strip()
            falliti.append({"comando": testo[:160],
                            "errore": " ".join(errore.split())[:MAX_ERRORE]})
    # I piu' recenti: cio' che si e' provato per ultimo e' cio' a cui si era
    # arrivati, e la lezione serve a riprendere da li'.
    lezione.riusciti = riusciti[-MAX_COMANDI:]
    lezione.falliti = falliti[-MAX_COMANDI:]
    lezione.incoerenze = incoerenze(comandi)

    requisiti = dati.get("requirements") or []
    if isinstance(requisiti, dict):
        requisiti = list(requisiti.values())
    lezione.criteri_totali = len(requisiti)
    lezione.criteri_ok = sum(1 for r in requisiti if r.get("met"))

    for proposta in (dati.get("proposte_verifica") or []):
        if proposta.get("accettata"):
            lezione.prova_sostituita = str(proposta.get("comando") or "")
    return lezione


def racconta(lezioni: List[Any]) -> str:
    """Le lezioni, come le legge il tentativo dopo. Vuoto quando non ce ne sono.

    Scritto come lo direbbe un collega che ha appena lasciato il posto: cosa ha
    provato, cosa ha funzionato, dove si e' fermato. Non un verbale.
    """
    voci = [l if isinstance(l, Lezione) else Lezione.from_dict(l or {})
            for l in (lezioni or [])][-MAX_LEZIONI:]
    if not voci:
        return ""

    righe = ["QUESTA VOCE E' GIA' STATA TENTATA. Non ricominciare da zero: "
             "qui sotto c'e' cosa aveva gia' scoperto chi ci ha provato prima."]
    for l in voci:
        righe.append("")
        testa = f"— Tentativo {l.tentativo}"
        if l.turni:
            testa += f" ({l.turni} turni)"
        if l.criteri_totali:
            testa += f", criteri soddisfatti {l.criteri_ok}/{l.criteri_totali}"
        righe.append(testa + (f": {l.esito}" if l.esito else ""))
        if l.file:
            righe.append("  file gia' scritti: " + ", ".join(l.file))
        if l.riusciti:
            righe.append("  comandi che hanno funzionato:")
            righe += [f"    {c}" for c in l.riusciti]
        if l.falliti:
            righe.append("  comandi che sono falliti:")
            for f in l.falliti:
                riga = f"    {f.get('comando')}"
                if f.get("errore"):
                    riga += f"\n      -> {f['errore']}"
                righe.append(riga)
        if l.prova_sostituita:
            righe.append("  la prova dichiarata era ineseguibile; quella buona e': "
                         + l.prova_sostituita)
        for nota in l.incoerenze:
            righe.append("  ATTENZIONE: " + nota)

    righe += [
        "",
        "Parti da qui. Se un comando ha gia' funzionato, riusalo invece di "
        "cercarne un altro; se uno e' gia' fallito due volte allo stesso modo, "
        "non e' rifacendolo che cambiera'.",
    ]
    return "\n".join(righe)
