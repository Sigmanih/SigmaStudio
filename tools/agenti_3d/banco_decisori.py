"""Confronta i modelli che decidono come si muove un agente nella plancia.

Ogni attivita' di attivita_campione.json ha la modalita' attesa; si misurano
accuratezza e latenza su CPU di ogni decisore, con tutti i thread e con 4
thread (come il Raspberry Pi 5). Il primo decisore e' la tabella fissa di
agentMotion.js: e' il metro, perche' i modelli costano memoria e millisecondi
e devono guadagnarseli.

    store/engine_runtime/decisori/venv/Scripts/python.exe tools/agenti_3d/banco_decisori.py
        [--modelli tabella,regole,regole+laya-ml,laya-ml,gliclass-edge] [--thread 4]
        [--campione attivita_verifica.json]

Gira nel venv dedicato (torch CPU, laya, gliclass): nel .venv del kernel laya
porterebbe con se' un torch diverso.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
ROOT = QUI.parents[1]
sys.path.insert(0, str(ROOT))

from core.logger import get_logger  # noqa: E402

log = get_logger("agenti_3d.decisori")

# Stessi significati della domanda a Laya in agentMotion.js, piu' "collega":
# e' la modalita' che la tabella non puo' riconoscere dallo stato
CRITERI = {
    "console": "The agent is reasoning, writing text or code, editing files or running a tool on its own work: it works seated at its own console",
    "olotavolo": "The agent is searching the web, reading external sources or documents, or exploring data and images: it studies the central holographic table",
    "presenta": "The agent has finished, delivers the answer, or hit an error, and reports to the user: it stands and faces the user",
    "posa": "The agent is idle and waiting for a request: it stands still in front of its station",
    "collega": "The agent hands work to another agent, asks a colleague or coordinates other agents: it walks to the colleague's station",
}
ISTRUZIONI = ("An AI agent is shown as a 3D avatar on the bridge of a starship. Given what the agent "
              "is doing right now, choose where its avatar should be and what it should do.")

TABELLA = {"idle": "posa", "thinking": "console", "tool": "console", "writing": "console",
           "browsing": "olotavolo", "done": "presenta", "error": "presenta"}


def descrivi(a: dict) -> str:
    parti = [f"Agent is {a['state']}."]
    if a.get("tool"):
        parti.append(f"Tool in use: {a['tool']}.")
    if a.get("detail"):
        parti.append(f"Detail: {a['detail']}.")
    return " ".join(parti)


def decisore_tabella():
    return lambda a: TABELLA.get(a["state"], "posa")


def decisore_laya(sottocartella: str | None, strutturato: bool = False):
    import laya

    agente = laya.load("convaiinnovations/laya", subfolder=sottocartella, device="cpu") if sottocartella \
        else laya.load("convaiinnovations/laya", device="cpu")
    domanda = {"movimento": {"type": "choice", "instructions": ISTRUZIONI, "criteria": CRITERI}}

    def decidi(a: dict) -> str:
        # Laya accetta anche lo stato come dizionario: niente frase da comporre
        stato = {k: a[k] for k in ("state", "tool", "detail") if a.get(k)} if strutturato else descrivi(a)
        return agente.decide(stato, questions=domanda)["movimento"]["choice"]
    return decidi


ETICHETTE_BREVI = {
    "console": "working at its own desk on code, text or tools",
    "olotavolo": "researching the web, sources, documents or data",
    "presenta": "finished or failed, reporting to the user",
    "posa": "idle, waiting",
    "collega": "delegating to or asking another agent",
}


def decisore_gliclass(modello: str, brevi: bool = False):
    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from transformers import AutoTokenizer

    m = GLiClassModel.from_pretrained(modello)
    tok = AutoTokenizer.from_pretrained(modello, add_prefix_space=True)
    pipe = ZeroShotClassificationPipeline(m, tok, classification_type="single-label", device="cpu")
    # GLiClass sceglie fra etichette in linguaggio naturale: si torna al nome della modalita'
    etichette = {v: k for k, v in (ETICHETTE_BREVI if brevi else CRITERI).items()}

    def decidi(a: dict) -> str:
        r = pipe(descrivi(a), list(etichette), threshold=0.0, prompt=ISTRUZIONI if brevi else None)[0]
        migliore = max(r, key=lambda x: x["score"])
        return etichette[migliore["label"]]
    return decidi


REGOLE_PATH = ROOT / "sigma_studio" / "src" / "components" / "common" / "agentMotionRules.json"


def applica_regole(a: dict, regole: dict) -> tuple[str, bool]:
    """Stessa logica di agentMotion.js. Ritorna (modalita', decisa_da_una_regola)."""
    import re

    if a["state"] in regole["stati_certi"]:
        return regole["stati_certi"][a["state"]], True
    dettaglio = a.get("detail") or ""
    for r in regole["dettaglio"]:
        if dettaglio and re.search(r["schema"], dettaglio, re.IGNORECASE):
            return r["modo"], True
    strumento = (a.get("tool") or "").lower()
    for r in regole["strumento"]:
        if strumento and re.search(r["schema"], strumento):
            return r["modo"], True
    return regole["stato"].get(a["state"], regole["predefinito"]), False


def decisore_regole():
    regole = json.loads(REGOLE_PATH.read_text(encoding="utf-8"))
    return lambda a: applica_regole(a, regole)[0]


def decisore_regole_e_modello(costruttore):
    """Il modello decide solo dove nessuna regola ha riconosciuto qualcosa."""
    regole = json.loads(REGOLE_PATH.read_text(encoding="utf-8"))
    modello = costruttore()

    def decidi(a: dict) -> str:
        modo, certo = applica_regole(a, regole)
        return modo if certo else modello(a)
    return decidi


#: Stati che dicono gia' tutto: il modello li sbagliava piu' della tabella
STATI_CERTI = {"idle", "done", "error", "browsing"}
#: Dove serve davvero un modello: lavora, studia o coinvolge un collega?
CRITERI_AMBIGUI = {k: CRITERI[k] for k in ("console", "olotavolo", "collega", "presenta")}


def decisore_ibrido(costruttore):
    """Tabella per gli stati certi, modello solo per strumento e dettaglio."""
    tabella = decisore_tabella()
    modello = costruttore()

    def decidi(a: dict) -> str:
        return tabella(a) if a["state"] in STATI_CERTI else modello(a)
    return decidi


def _laya_ambiguo(sottocartella: str | None):
    import laya

    agente = laya.load("convaiinnovations/laya", subfolder=sottocartella, device="cpu") if sottocartella \
        else laya.load("convaiinnovations/laya", device="cpu")
    domanda = {"movimento": {"type": "choice", "instructions": ISTRUZIONI, "criteria": CRITERI_AMBIGUI}}

    def decidi(a: dict) -> str:
        stato = {k: a[k] for k in ("state", "tool", "detail") if a.get(k)}
        return agente.decide(stato, questions=domanda)["movimento"]["choice"]
    return decidi


def _gliclass_ambiguo(modello: str):
    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from transformers import AutoTokenizer

    m = GLiClassModel.from_pretrained(modello)
    tok = AutoTokenizer.from_pretrained(modello, add_prefix_space=True)
    pipe = ZeroShotClassificationPipeline(m, tok, classification_type="single-label", device="cpu")
    etichette = {ETICHETTE_BREVI[k]: k for k in CRITERI_AMBIGUI}

    def decidi(a: dict) -> str:
        r = pipe(descrivi(a), list(etichette), threshold=0.0, prompt=ISTRUZIONI)[0]
        return etichette[max(r, key=lambda x: x["score"])["label"]]
    return decidi


DECISORI = {
    "tabella": decisore_tabella,
    "laya": lambda: decisore_laya(None),
    "laya-ml": lambda: decisore_laya("multilingual"),
    "gliclass-edge": lambda: decisore_gliclass("knowledgator/gliclass-edge-v3.0"),
    "gliclass-base": lambda: decisore_gliclass("knowledgator/gliclass-modern-base-v3.0"),
    "laya-dict": lambda: decisore_laya(None, strutturato=True),
    "laya-ml-dict": lambda: decisore_laya("multilingual", strutturato=True),
    "gliclass-edge-brevi": lambda: decisore_gliclass("knowledgator/gliclass-edge-v3.0", brevi=True),
    "gliclass-base-brevi": lambda: decisore_gliclass("knowledgator/gliclass-modern-base-v3.0", brevi=True),
    "ibrido-laya": lambda: decisore_ibrido(lambda: _laya_ambiguo(None)),
    "ibrido-laya-ml": lambda: decisore_ibrido(lambda: _laya_ambiguo("multilingual")),
    "ibrido-gliclass-edge": lambda: decisore_ibrido(lambda: _gliclass_ambiguo("knowledgator/gliclass-edge-v3.0")),
    "ibrido-gliclass-base": lambda: decisore_ibrido(lambda: _gliclass_ambiguo("knowledgator/gliclass-modern-base-v3.0")),
    "regole": decisore_regole,
    "regole+laya-ml": lambda: decisore_regole_e_modello(lambda: _laya_ambiguo("multilingual")),
    "regole+gliclass-edge": lambda: decisore_regole_e_modello(lambda: _gliclass_ambiguo("knowledgator/gliclass-edge-v3.0")),
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelli", default=",".join(DECISORI))
    p.add_argument("--thread", type=int, default=0, help="thread di torch (0 = tutti); 4 simula il Pi 5")
    p.add_argument("--uscita", type=Path, default=None, help="dove scrivere i risultati in JSON")
    p.add_argument("--campione", default="attivita_campione.json",
                   help="insieme di esempi; attivita_verifica.json e' scritto dopo le regole")
    args = p.parse_args()

    import torch
    if args.thread:
        torch.set_num_threads(args.thread)
    campione = json.loads((QUI / args.campione).read_text(encoding="utf-8"))

    risultati = {}
    for nome in args.modelli.split(","):
        try:
            t0 = time.perf_counter()
            decidi = DECISORI[nome]()
            carica = time.perf_counter() - t0
            decidi(campione[0])  # riscaldamento: la prima chiamata compila e alloca
            tempi, giuste, errori = [], 0, []
            for a in campione:
                t1 = time.perf_counter()
                scelta = decidi(a)
                tempi.append((time.perf_counter() - t1) * 1000)
                if scelta == a["atteso"]:
                    giuste += 1
                else:
                    errori.append(f"{a['state']}/{a['tool'] or '-'}: {scelta} invece di {a['atteso']}")
            risultati[nome] = {
                "accuratezza": round(giuste / len(campione), 3),
                "giuste": giuste,
                "totale": len(campione),
                "ms_mediana": round(statistics.median(tempi), 1),
                "ms_p95": round(sorted(tempi)[int(len(tempi) * 0.95) - 1], 1),
                "caricamento_s": round(carica, 1),
                "errori": errori,
            }
            log.info("%s: %d/%d, %.1f ms (p95 %.1f), caricamento %.1f s", nome, giuste, len(campione),
                     risultati[nome]["ms_mediana"], risultati[nome]["ms_p95"], carica)
        except Exception:
            log.exception("decisore %s non valutato", nome)
    testo = json.dumps({"thread": args.thread or torch.get_num_threads(), "risultati": risultati},
                       indent=2, ensure_ascii=False)
    if args.uscita:
        args.uscita.write_text(testo, encoding="utf-8")
    giuste = sum(r["giuste"] for r in risultati.values())
    totale = sum(r["totale"] for r in risultati.values())
    print(f'SIGMA-CHECK {{"check": "decisori_movimento", "checked": {totale}, "problems": {totale - giuste}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
