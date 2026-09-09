# ==============================================================================
# core/harness/protocol_bench.py — Quanto un modello sa stare dentro il protocollo
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Un banco di prova per l'aderenza al protocollo dei tool.

I benchmark che abbiamo misurano domande e risposte: un modello prende 80 su 100
e non sa emettere un blocco `tool:` senza scriverci intorno mezza pagina di
spiegazioni. Sono due abilita' diverse, e quella che serve all'harness e' la
seconda — su questa macchina un modello da 8B con un punteggio rispettabile
copiava `PERCORSO` e `TESTO_ESATTO_DA_SOSTITUIRE` **come valori**, cioe' leggeva
gli esempi del prompt e li ripeteva alla lettera.

Qui si misura quello. Ogni prova e' uno scenario deterministico: un workspace
preparato, un obiettivo, e un punteggio calcolato leggendo cio' che il modello
ha davvero fatto. Nessun giudizio umano, nessun modello giudice — solo fatti
osservabili nel transcript.

**Cosa non e'.** Non misura se il codice scritto sia buono: quello lo dicono i
test del progetto. Misura se il modello e' *pilotabile* — se il ciclo puo'
fidarsi di lui per venti turni senza che si perda.

**Perche' conta il numero di turni.** Un modello che arriva in fondo in
venticinque turni non e' utilizzabile in un ventaglio da duecento voci: costa
dieci volte uno che ci arriva in otto. L'efficienza fa parte dell'aderenza.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger

log = get_logger("protocol_bench")

#: I segnaposto che il prompt usa negli esempi. Un modello che li copia come
#: valori non ha capito che sono esempi: e' il modo di fallire piu' netto che
#: si sia visto, e il piu' facile da riconoscere.
SEGNAPOSTO_DEL_PROMPT = (
    "PERCORSO", "TESTO_ESATTO_DA_SOSTITUIRE", "TESTO_NUOVO", "NOME_DEL_TOOL",
    "CONTENUTO_COMPLETO", "TESTO_DA_AGGIUNGERE", "PRIMA_RIGA", "QUANTE_RIGHE",
)

#: Quanto tempo concedere a uno scenario prima di dichiararlo perso.
#:
#: Serve a misurare, non a essere gentili. Un banco che aspetta all'infinito
#: non distingue «lento» da «bloccato», e proprio la lentezza e' cio' che si
#: vuole misurare: un modello che impiega venti minuti su un file di tre
#: righe non e' utilizzabile in un ventaglio, e va detto in cinque.
TETTO_SECONDI_SCENARIO = 300.0

#: Comandi che creano un file dalla riga di comando invece che con i tool: il
#: risultato non ha backup, non passa dal controllo di sintassi e non risulta
#: fra le modifiche.
SCRITTURA_INLINE = re.compile(
    r"(write_text|writelines|>\s*\S+\.(py|json|jsx|md)|set-content|out-file)",
    re.IGNORECASE,
)


@dataclass
class Prova:
    """Una proprieta' del protocollo, e se il modello l'ha rispettata."""

    id: str
    descrizione: str
    superata: bool = False
    dettaglio: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "descrizione": self.descrizione,
                "superata": self.superata, "dettaglio": self.dettaglio}


@dataclass
class EsitoScenario:
    """Com'e' andato un modello su uno scenario."""

    scenario: str
    model: str
    prove: List[Prova] = field(default_factory=list)
    turni: int = 0
    obiettivo_raggiunto: bool = False
    secondi: float = 0.0
    errore: str = ""
    #: Dove sono rimasti i file, quando qualcosa non e' andato.
    sandbox: str = ""
    #: True se e' stato fermato perche' ci metteva troppo.
    scaduto: bool = False

    @property
    def superate(self) -> int:
        return sum(1 for p in self.prove if p.superata)

    @property
    def punteggio(self) -> float:
        return round(100.0 * self.superate / len(self.prove), 1) if self.prove else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario, "model": self.model,
            "punteggio": self.punteggio, "superate": self.superate,
            "totali": len(self.prove), "turni": self.turni,
            "obiettivo_raggiunto": self.obiettivo_raggiunto,
            "secondi": round(self.secondi, 1), "errore": self.errore,
            "sandbox": self.sandbox, "scaduto": self.scaduto,
            "prove": [p.to_dict() for p in self.prove],
        }


# ---------------------------------------------------------------------------
# Lettura del transcript
# ---------------------------------------------------------------------------


@dataclass
class Traccia:
    """Cio' che si e' visto passare durante un run, in forma interrogabile."""

    chiamate: List[Dict[str, Any]] = field(default_factory=list)
    testo: str = ""
    turni: int = 0
    #: Quanti ne sono stati visti passare, anche senza consuntivo finale.
    turni_visti: int = 0
    #: Perche' il motore non ha prodotto niente, se e' successo.
    errore_motore: str = ""
    obiettivo_raggiunto: bool = False

    def nomi(self) -> List[str]:
        return [c["tool"] for c in self.chiamate]

    def riuscite(self) -> List[Dict[str, Any]]:
        return [c for c in self.chiamate if c.get("ok")]

    def primo(self, *nomi: str) -> int:
        """La posizione della prima chiamata a uno di questi tool, o -1."""
        for i, c in enumerate(self.chiamate):
            if c["tool"] in nomi:
                return i
        return -1


def osserva(eventi) -> Traccia:
    """Trasforma il flusso di eventi di un run in qualcosa su cui ragionare."""
    traccia = Traccia()
    for evento in eventi:
        tipo = evento.get("type")
        if tipo == "tool_result":
            risultato = evento.get("result") or {}
            traccia.chiamate.append({
                "tool": str(evento.get("tool") or ""),
                "params": evento.get("params") or risultato,
                "ok": bool(risultato.get("success")),
                "error": str(risultato.get("error") or ""),
            })
        elif tipo == "tool_call":
            # Alcune emissioni portano i parametri qui e il risultato dopo.
            if traccia.chiamate and not traccia.chiamate[-1].get("params"):
                traccia.chiamate[-1]["params"] = evento.get("params") or {}
        elif tipo == "turn_start":
            # Contati mentre passano, non solo dal consuntivo finale: un run
            # fermato per tempo scaduto non emette `run_metrics`, e dire
            # «fermo dopo 0 turni» su un modello che ne ha fatti dodici e'
            # un resoconto che mente.
            traccia.turni_visti += 1
        elif tipo == "run_metrics":
            traccia.turni = int(evento.get("turns") or 0)
            traccia.obiettivo_raggiunto = bool(evento.get("goal_reached"))
        elif tipo in ("token", "text"):
            traccia.testo += str(evento.get("text") or evento.get("token") or "")
        elif tipo == "error" or evento.get("error"):
            motivo = evento.get("error") or evento.get("message")
            traccia.errore_motore = str(motivo or "errore del motore")[:300]
    return traccia


# ---------------------------------------------------------------------------
# Le prove
# ---------------------------------------------------------------------------


def _serializza(params: Any) -> str:
    try:
        return json.dumps(params, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(params)


def prova_nomi_veri(traccia: Traccia, noti: set) -> Prova:
    inventati = sorted({n for n in traccia.nomi() if n and n not in noti})
    return Prova(
        "nomi_veri", "Usa solo tool che esistono",
        superata=not inventati,
        dettaglio=("inventati: " + ", ".join(inventati)) if inventati else "",
    )


def prova_niente_segnaposto(traccia: Traccia) -> Prova:
    """Il modo di fallire piu' netto: leggere gli esempi del prompt come valori."""
    copiati = []
    for c in traccia.chiamate:
        testo = _serializza(c.get("params"))
        for segno in SEGNAPOSTO_DEL_PROMPT:
            if segno in testo:
                copiati.append(f"{c['tool']}:{segno}")
    return Prova(
        "niente_segnaposto", "Non copia i segnaposto del prompt come valori",
        superata=not copiati,
        dettaglio=("copiati: " + ", ".join(sorted(set(copiati))[:4])) if copiati else "",
    )


def prova_spec_per_prima(traccia: Traccia) -> Prova:
    posizione = traccia.primo("spec")
    return Prova(
        "spec_per_prima", "Dichiara i criteri prima di guardare i file",
        superata=posizione == 0,
        dettaglio=("mai chiamata" if posizione < 0
                   else (f"chiamata al posto {posizione + 1}" if posizione else "")),
    )


def prova_legge_prima_di_modificare(traccia: Traccia) -> Prova:
    """Modificare un file senza averlo letto significa inventare l'ancora."""
    letti = set()
    violazioni = []
    for c in traccia.chiamate:
        percorso = str((c.get("params") or {}).get("path") or "")
        base = Path(percorso).name if percorso else ""
        if c["tool"] == "read_file" and c.get("ok"):
            letti.add(base)
        elif c["tool"] == "edit_file" and base and base not in letti:
            violazioni.append(base)
    return Prova(
        "legge_prima_di_modificare", "Legge un file prima di modificarlo",
        superata=not violazioni,
        dettaglio=("modificati senza leggere: " + ", ".join(sorted(set(violazioni)))) if violazioni else "",
    )


def prova_verifica_prima_di_chiudere(traccia: Traccia) -> Prova:
    posizione_chiusura = traccia.primo("complete_goal")
    if posizione_chiusura < 0:
        return Prova("verifica_prima_di_chiudere",
                     "Esegue una verifica prima di dichiarare finito",
                     superata=False, dettaglio="non ha mai provato a chiudere")
    prima = traccia.chiamate[:posizione_chiusura]
    ha_verificato = any(c["tool"] == "terminal" and c.get("ok") for c in prima)
    return Prova(
        "verifica_prima_di_chiudere", "Esegue una verifica prima di dichiarare finito",
        superata=ha_verificato,
        dettaglio="" if ha_verificato else "ha chiuso senza eseguire nulla",
    )


def prova_reagisce_al_rifiuto(traccia: Traccia) -> Prova:
    """Dopo un rifiuto, ripetere identico e' il segno che non l'ha letto."""
    ripetizioni = 0
    precedente = None
    for c in traccia.chiamate:
        firma = (c["tool"], _serializza(c.get("params"))[:300])
        if precedente and firma == precedente[0] and not precedente[1]:
            ripetizioni += 1
        precedente = (firma, c.get("ok"))
    return Prova(
        "reagisce_al_rifiuto", "Dopo un rifiuto cambia approccio invece di ripetere",
        superata=ripetizioni == 0,
        dettaglio=f"{ripetizioni} ripetizioni identiche dopo un fallimento" if ripetizioni else "",
    )


def prova_non_scrive_da_terminale(traccia: Traccia) -> Prova:
    """Un file scritto cosi' non ha backup, non passa dal controllo di sintassi
    e non risulta fra le modifiche: l'agente non potrebbe dimostrarlo."""
    colpevoli = [
        c for c in traccia.chiamate
        if c["tool"] == "terminal"
        and SCRITTURA_INLINE.search(str((c.get("params") or {}).get("command") or ""))
    ]
    return Prova(
        "non_scrive_da_terminale", "Non crea file dalla riga di comando",
        superata=not colpevoli,
        dettaglio=f"{len(colpevoli)} comandi di scrittura inline" if colpevoli else "",
    )


def prova_chiude_con_prove(traccia: Traccia, criteri: List[str]) -> Prova:
    chiusure = [c for c in traccia.chiamate if c["tool"] == "complete_goal"]
    if not chiusure:
        return Prova("chiude_con_prove", "Chiude dichiarando la prova di ogni criterio",
                     superata=False, dettaglio="non ha mai chiuso")
    testo = _serializza(chiusure[-1].get("params")).lower()
    mancanti = [c for c in criteri
                if not any(p in testo for p in c.lower().split() if len(p) > 4)]
    return Prova(
        "chiude_con_prove", "Chiude dichiarando la prova di ogni criterio",
        superata=traccia.obiettivo_raggiunto and not mancanti,
        dettaglio=("criteri senza prova: " + "; ".join(mancanti[:2])) if mancanti else "",
    )


def prova_arriva_in_fondo(traccia: Traccia, tetto_turni: int) -> Prova:
    """L'efficienza fa parte dell'aderenza: un modello che ci arriva in
    venticinque turni non e' utilizzabile in un ventaglio da duecento voci."""
    return Prova(
        "arriva_in_fondo", f"Chiude l'obiettivo entro {tetto_turni} turni",
        superata=traccia.obiettivo_raggiunto,
        dettaglio="" if traccia.obiettivo_raggiunto else f"fermo dopo {traccia.turni} turni",
    )


# ---------------------------------------------------------------------------
# Gli scenari
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    """Un compito piccolo con una risposta verificabile."""

    id: str
    descrizione: str
    #: Cosa mettere nel workspace prima di cominciare.
    file: Dict[str, str]
    obiettivo: str
    criteri: List[str]
    tetto_turni: int = 14
    #: Il tempo massimo concesso, in secondi.
    tetto_secondi: float = TETTO_SECONDI_SCENARIO
    #: Il comando che dimostra il lavoro, dichiarato in anticipo.
    verifica: str = ""
    #: Cosa deve essere vero sul disco alla fine.
    controllo: Optional[Callable[[Path], str]] = None


def _controlla_json(percorso: str, chiave: str, valore: str) -> Callable[[Path], str]:
    def controlla(radice: Path) -> str:
        f = radice / percorso
        if not f.is_file():
            return f"{percorso} non esiste"
        try:
            dati = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as exc:
            return f"{percorso} non e' JSON valido: {exc}"
        if str(dati.get(chiave)) != valore:
            return f"{percorso}: '{chiave}' vale {dati.get(chiave)!r} invece di {valore!r}"
        return ""
    return controlla


def _controlla_contiene(percorso: str, atteso: str) -> Callable[[Path], str]:
    def controlla(radice: Path) -> str:
        f = radice / percorso
        if not f.is_file():
            return f"{percorso} non esiste"
        return "" if atteso in f.read_text(encoding="utf-8") else f"{percorso} non contiene {atteso!r}"
    return controlla


SCENARI: List[Scenario] = [
    Scenario(
        id="file_nuovo",
        descrizione="Creare un file da zero e dimostrarlo",
        file={"app.py": "TITOLO = 'Ciao'\n"},
        obiettivo=(
            'Crea il file locales/it.json con dentro esattamente {"titolo": "Ciao"}.'
        ),
        criteri=["il file locales/it.json esiste ed e' JSON valido"],
        verifica="python -m json.tool locales/it.json",
        controllo=_controlla_json("locales/it.json", "titolo", "Ciao"),
    ),
    Scenario(
        id="modifica_mirata",
        descrizione="Cambiare una riga dentro un file esistente",
        file={
            "config.py": (
                "# Impostazioni del progetto\n"
                "LINGUA = 'it'\n"
                "DEBUG = False\n"
                "TIMEOUT = 30\n"
            ),
        },
        obiettivo="In config.py cambia il valore di TIMEOUT da 30 a 60. Non toccare altro.",
        criteri=["TIMEOUT vale 60 in config.py", "le altre impostazioni sono invariate"],
        verifica="python -c \"import ast,io; ast.parse(io.open('config.py',encoding='utf-8').read())\"",
        controllo=_controlla_contiene("config.py", "TIMEOUT = 60"),
    ),
]


# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------


def pulisci(radice: Path) -> None:
    """Cancella una sandbox, anche quando git l'ha resa ostinata.

    Su Windows gli oggetti dentro `.git` sono in sola lettura, e `rmtree` si
    ferma sul primo: restano cartelle a meta' che nessuno rimuovera' mai. Ogni
    esecuzione del banco ne lascerebbe una, e su una macchina che gira da mesi
    diventano gigabyte di repository morti nella cartella temporanea.
    """
    import shutil
    import stat

    def insisti(funzione, percorso, _info):
        try:
            os.chmod(percorso, stat.S_IWRITE)
            funzione(percorso)
        except OSError:
            pass

    shutil.rmtree(radice, onerror=insisti)


def _prepara(scenario: Scenario) -> Path:
    radice = Path(tempfile.mkdtemp(prefix=f"protobench_{scenario.id}_"))
    for percorso, contenuto in scenario.file.items():
        f = radice / percorso
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(contenuto, encoding="utf-8")
    for args in (["init", "-b", "main"], ["config", "user.email", "bench@sigma.local"],
                 ["config", "user.name", "Bench"], ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git"] + args, cwd=str(radice), capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(radice), capture_output=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=str(radice), capture_output=True)
    return radice


def esegui_scenario(scenario: Scenario, model_name: str,
                    should_cancel: Optional[Callable[[], bool]] = None) -> EsitoScenario:
    """Fa girare il ciclo vero su uno scenario e legge cosa ha fatto il modello."""
    import time

    from core.harness.loop import stream_admin_agent_turn
    from core.harness.policy import ALIASES

    esito = EsitoScenario(scenario=scenario.id, model=model_name)
    radice = _prepara(scenario)
    inizio = time.time()

    # Il tempo e' una delle cose misurate, quindi va anche fatto rispettare:
    # senza un tetto, un modello prolisso tiene occupata la macchina finche'
    # qualcuno non se ne accorge, e il banco non produce un numero ma
    # un'attesa.
    scaduto = {"si": False}

    def basta() -> bool:
        if should_cancel and should_cancel():
            return True
        if time.time() - inizio > scenario.tetto_secondi:
            scaduto["si"] = True
            return True
        return False

    try:
        traccia = osserva(stream_admin_agent_turn(
            messages=[{"role": "user", "content": scenario.obiettivo}],
            workspace_root=str(radice),
            model_name=model_name,
            max_turns=scenario.tetto_turni,
            session_id=f"bench_{scenario.id}",
            verify_command=scenario.verifica,
            should_cancel=basta,
        ))
    except Exception as exc:
        esito.errore = str(exc)
        log.warning("[ProtocolBench] scenario '%s' interrotto: %s", scenario.id, exc)
        return esito
    finally:
        esito.secondi = time.time() - inizio

    esito.turni = traccia.turni or traccia.turni_visti
    esito.obiettivo_raggiunto = traccia.obiettivo_raggiunto

    # Un modello che non si e' caricato non ha un punteggio: ha un errore.
    # Dargli 50 su 100 perche' meta' delle prove sono negative e' un numero
    # che sembra una misura e non lo e'. E' successo davvero, con il Qwen 27B
    # che non partiva: il banco ha stampato 50.0 e nessuno se ne sarebbe
    # accorto senza leggere le righe di llama-server sopra il rapporto.
    if not traccia.chiamate and not traccia.testo.strip():
        esito.errore = (
            traccia.errore_motore
            or "il modello non ha prodotto nulla: probabilmente non si e' caricato"
        )
        pulisci(radice)
        return esito
    esito.scaduto = scaduto["si"]
    if esito.scaduto:
        esito.errore = (
            "fermato dopo %.0fs: oltre il tempo concesso" % scenario.tetto_secondi
        )
    esito.prove = [
        # I nomi veri sono quelli che la policy sa tradurre: alias compresi,
        # perche' `write` e `write_file` sono lo stesso tool e rifiutare il
        # primo misurerebbe il vocabolario, non l'aderenza.
        prova_nomi_veri(traccia, set(ALIASES) | set(ALIASES.values())),
        prova_niente_segnaposto(traccia),
        prova_spec_per_prima(traccia),
        prova_legge_prima_di_modificare(traccia),
        prova_verifica_prima_di_chiudere(traccia),
        prova_reagisce_al_rifiuto(traccia),
        prova_non_scrive_da_terminale(traccia),
        prova_chiude_con_prove(traccia, scenario.criteri),
        prova_arriva_in_fondo(traccia, scenario.tetto_turni),
    ]

    if scenario.controllo is not None:
        motivo = scenario.controllo(radice)
        esito.prove.append(Prova(
            "risultato_giusto", "Il file finale e' quello richiesto",
            superata=not motivo, dettaglio=motivo,
        ))

    # La sandbox si butta se e' andato tutto bene, si tiene se no: quando una
    # prova fallisce, cio' che il modello ha davvero scritto e' l'unica cosa
    # che spiega perche'. Tenerle tutte riempirebbe il disco, buttarle tutte
    # toglierebbe l'unico modo di capire.
    if esito.superate == len(esito.prove):
        pulisci(radice)
    else:
        esito.sandbox = str(radice)
        log.info("[ProtocolBench] '%s': sandbox conservata in %s",
                 scenario.id, radice)
    return esito


def esegui(model_name: str, scenari: Optional[List[str]] = None,
           should_cancel: Optional[Callable[[], bool]] = None,
           progresso: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    """Il banco completo su un modello. Ritorna un rapporto leggibile."""
    voluti = set(scenari) if scenari else None
    da_fare = [s for s in SCENARI if voluti is None or s.id in voluti]
    esiti = []
    for numero, scenario in enumerate(da_fare, 1):
        # Si dice cosa sta per succedere, non solo com'e' andato: un banco che
        # tace per venti minuti non distingue «lento» da «bloccato», e chi
        # guarda non sa se convenga aspettare.
        log.info("[ProtocolBench] %s (%d/%d) su '%s'...",
                 scenario.id, numero, len(da_fare), model_name)
        if progresso:
            progresso({"fase": "inizio", "scenario": scenario.id,
                       "numero": numero, "totale": len(da_fare)})
        esito = esegui_scenario(scenario, model_name, should_cancel)
        esiti.append(esito)
        log.info("[ProtocolBench] %s: %s/%s prove in %ss%s",
                 scenario.id, esito.superate, len(esito.prove),
                 round(esito.secondi), " (scaduto)" if esito.scaduto else "")
        if progresso:
            progresso({"fase": "fine", **esito.to_dict()})
    # Gli scenari senza misura non entrano nella media: un modello che non si
    # carica trascinerebbe il punteggio verso il basso come se avesse provato e
    # sbagliato, che e' un'altra cosa.
    misurati = [e for e in esiti if e.prove]
    prove_totali = sum(len(e.prove) for e in misurati)
    superate = sum(e.superate for e in misurati)
    non_misurati = [e.scenario for e in esiti if not e.prove]
    return {
        "model": model_name,
        "punteggio": round(100.0 * superate / prove_totali, 1) if prove_totali else 0.0,
        "superate": superate,
        "totali": prove_totali,
        "turni_totali": sum(e.turni for e in esiti),
        "secondi": round(sum(e.secondi for e in esiti), 1),
        "scenari": [e.to_dict() for e in esiti],
        "non_misurati": non_misurati,
        # Il rapporto che il cancello di completamento sa leggere.
        "check_line": "SIGMA-CHECK " + json.dumps(
            {"check": "protocollo-tool", "checked": prove_totali,
             "problems": prove_totali - superate}, ensure_ascii=False),
    }


# ---------------------------------------------------------------------------
# Uso da riga di comando
# ---------------------------------------------------------------------------
#     python -m core.harness.protocol_bench <modello> [--scenario file_nuovo]


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Misura quanto un modello sta dentro il protocollo dei tool.")
    parser.add_argument("model", help="nome del modello da mettere alla prova")
    parser.add_argument("--scenario", action="append", dest="scenari",
                        help="limita a uno scenario; ripetibile")
    parser.add_argument("--json", action="store_true", help="rapporto grezzo")
    args = parser.parse_args(argv)

    rapporto = esegui(args.model, args.scenari)

    if args.json:
        print(json.dumps(rapporto, indent=2, ensure_ascii=False))
        return 0 if rapporto["superate"] == rapporto["totali"] else 1

    print("\n%s" % rapporto["model"])
    print("=" * 72)
    for scenario in rapporto["scenari"]:
        print("\n%s — %s/%s prove, %s turni, %ss" % (
            scenario["scenario"], scenario["superate"], scenario["totali"],
            scenario["turni"], scenario["secondi"]))
        if scenario["errore"]:
            print("  interrotto: %s" % scenario["errore"])
        for prova in scenario["prove"]:
            segno = "OK" if prova["superata"] else "KO"
            riga = "  %s  %-28s %s" % (segno, prova["id"], prova["descrizione"])
            if prova["dettaglio"]:
                riga += "  <- " + prova["dettaglio"]
            print(riga)
    print("\n" + "-" * 72)
    print("PUNTEGGIO %.1f  (%d prove su %d, %d turni in totale, %ss)" % (
        rapporto["punteggio"], rapporto["superate"], rapporto["totali"],
        rapporto["turni_totali"], rapporto["secondi"]))
    print(rapporto["check_line"])
    return 0 if rapporto["superate"] == rapporto["totali"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
