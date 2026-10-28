"""Misura il triage di Laya nella chat prima di accenderlo.

Il router (core/harness/laya_router.py) classifica intento e complessita' di
ogni messaggio; se l'intento e' "chat" la chat non passa gli strumenti al
modello. Un errore costoso e' quindi una richiesta di codice, ricerca o sistema
presa per chat: qui lo si conta a parte. Le domande sono quelle del kernel.

    store/engine_runtime/decisori/venv/Scripts/python.exe tools/banco_laya_router.py
        [--modelli laya,laya-ml] [--thread 4] [--inglese]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.harness.laya_router import ROUTER_QUESTIONS  # noqa: E402
from core.logger import get_logger  # noqa: E402

log = get_logger("banco_laya_router")

CHECKPOINT = {"laya": None, "laya-ml": "multilingual"}

# Le stesse domande del kernel in inglese, la lingua in cui Laya e' addestrato:
# per non bocciarlo a causa delle istruzioni in italiano
DOMANDE_EN = {
    "intent": {"type": "choice", "instructions": "What is the main intent of the user's request?", "criteria": {
        "code": "Write, debug, modify or explain code or project files",
        "chat": "Casual conversation, greetings, thanks, opinions or general knowledge questions that need no files, web or system access",
        "search": "Look up information on the internet: news, documentation, prices, weather, papers",
        "system": "Operate the computer: run commands, start or stop services, delete or back up files, inspect processes or hardware",
    }},
    "complexity": {"type": "choice", "instructions": "How much reasoning does the request need?", "criteria": {
        "low": "Simple, direct request that can be done without multi-step reasoning",
        "high": "Complex problem: architecture, large refactoring, multi-step research or articulated logic",
    }},
}


def classificatore_qwen(modello: str):
    """Un LLM piccolo usato come classificatore: risponde con una parola sola."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(modello)
    lm = AutoModelForCausalLM.from_pretrained(modello)
    lm.eval()
    voci = DOMANDE_EN["intent"]["criteria"]
    elenco = "\n".join(f"- {k}: {v}" for k, v in voci.items())

    def decidi(testo: str) -> dict:
        import torch

        msg = [{"role": "system", "content": "Classify the user's request. Answer with exactly one word among: "
                + ", ".join(voci) + ".\n" + elenco},
               {"role": "user", "content": testo}]
        enc = tok.apply_chat_template(msg, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        with torch.no_grad():
            out = lm.generate(**enc, max_new_tokens=3, do_sample=False)
        risposta = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip().lower()
        scelta = next((k for k in voci if risposta.startswith(k)), "code")
        return {"intent": {"choice": scelta}, "complexity": {"choice": "low"}}
    return decidi


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelli", default="laya,laya-ml")
    p.add_argument("--thread", type=int, default=0)
    p.add_argument("--inglese", action="store_true", help="domande tradotte in inglese invece di quelle del kernel")
    args = p.parse_args()

    import laya
    import torch
    if args.thread:
        torch.set_num_threads(args.thread)
    campione = json.loads((ROOT / "tools" / "laya_router_campione.json").read_text(encoding="utf-8"))
    domande = DOMANDE_EN if args.inglese else {"intent": ROUTER_QUESTIONS["intent"],
                                               "complexity": ROUTER_QUESTIONS["complexity"]}

    problemi = 0
    for nome in args.modelli.split(","):
        if nome.startswith("qwen"):
            qwen = classificatore_qwen("Qwen/Qwen2.5-0.5B-Instruct")
            decidi = lambda testo, questions=None: qwen(testo)  # noqa: E731
        else:
            sotto = CHECKPOINT[nome]
            agente = laya.load("convaiinnovations/laya", subfolder=sotto, device="cpu") if sotto \
                else laya.load("convaiinnovations/laya", device="cpu")
            decidi = agente.decide
        decidi(campione[0]["testo"], questions=domande)
        intenti = complessita = tolti = 0
        tempi, errori = [], []
        for c in campione:
            t0 = time.perf_counter()
            r = decidi(c["testo"], questions=domande)
            tempi.append((time.perf_counter() - t0) * 1000)
            i, k = r["intent"]["choice"], r["complexity"]["choice"]
            intenti += i == c["intent"]
            complessita += k == c["complexity"]
            if i == "chat" and c["intent"] != "chat":
                tolti += 1
            if i != c["intent"]:
                errori.append(f"{c['testo'][:45]}: {i} invece di {c['intent']}")
        problemi += len(campione) - intenti
        log.info("%s: intento %d/%d, complessita' %d/%d, strumenti tolti per errore %d, %.0f ms (p95 %.0f)",
                 nome, intenti, len(campione), complessita, len(campione), tolti,
                 statistics.median(tempi), sorted(tempi)[int(len(tempi) * 0.95) - 1])
        for e in errori:
            log.info("  %s", e)
    print(f'SIGMA-CHECK {{"check": "laya_router", "checked": {len(campione) * len(args.modelli.split(","))}, "problems": {problemi}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
