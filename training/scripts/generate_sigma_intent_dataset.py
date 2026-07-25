#!/usr/bin/env python3
"""
generate_sigma_intent_dataset.py — Sigma Router Intent Dataset Generator
=========================================================================
Generates a rich, balanced JSONL dataset for fine-tuning Ailo-152M as a
lightweight intent classifier for Sigma Studio.

Output format (each line):
  {"messages": [
    {"role": "system", "content": "<router system prompt>"},
    {"role": "user",   "content": "<user request>"},
    {"role": "assistant", "content": "<json intent>"}
  ]}

Output JSON schema:
  {
    "mode":    "LOOP" | "INFO" | "PLAN",
    "agent":   "math_researcher" | "code_architect" | "viz_designer" |
               "test_engineer" | "proof_reviewer" | "sigma_architect" |
               "sigma_assistant",
    "intent":  "create_topic_file" | "edit_code" | "run_test" |
               "explain_concept" | "create_viz" | "create_module" |
               "plan_roadmap" | "general_chat" | "review_proof" |
               "debug_code" | "delete_file" | "rename_file",
    "actions": ["create_module", "create_file"] | ["read_file", "edit_file"] | []
  }

Usage:
  python training/scripts/generate_sigma_intent_dataset.py
  python training/scripts/generate_sigma_intent_dataset.py --output training/datasets/custom.jsonl
  python training/scripts/generate_sigma_intent_dataset.py --augment  # adds paraphrase variants
"""

import json
import os
import random
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_PATH = Path("training/datasets/sigma_intent_dataset.jsonl")

SYSTEM_PROMPT = (
    "Sei il Router Intelligente di Sigma Studio. "
    "Analizza la richiesta dell'utente e rispondi ESCLUSIVAMENTE con un oggetto JSON valido "
    "con i seguenti campi:\n"
    '- "mode": "LOOP" (esegui azioni su file/sistema), "INFO" (risposta testuale), '
    '  "PLAN" (pianifica tasks)\n'
    '- "agent": ID dell\'agente da attivare\n'
    '- "intent": tipo di azione ad alto livello\n'
    '- "actions": lista di azioni concrete da eseguire (vuota se INFO)\n'
    "Agenti disponibili: math_researcher, code_architect, viz_designer, "
    "test_engineer, proof_reviewer, sigma_architect, sigma_assistant.\n"
    "Rispondi SOLO con JSON. Nessun altro testo."
)

def _j(mode, agent, intent, actions):
    return json.dumps({
        "mode": mode,
        "agent": agent,
        "intent": intent,
        "actions": actions,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Seed examples — (user_text, intent_json_string)
# ---------------------------------------------------------------------------

SEED_EXAMPLES = [

    # =========================================================
    # MATH RESEARCHER — LOOP (create topic / module / file)
    # =========================================================
    ("scrivimi un argomento sugli esponenziali",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("scrivi un argomento su analisi 1",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("crea un argomento sulle funzioni reali",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("creami un modulo sulle serie di Taylor",
     _j("LOOP","math_researcher","create_module",["create_module","create_file"])),
    ("genera un modulo completo sulla teoria dei gruppi",
     _j("LOOP","math_researcher","create_module",["create_module","create_file"])),
    ("scrivi la trattazione formale sul teorema di Cauchy",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("crea un documento sulla convergenza delle serie numeriche",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("scrivi un file markdown sulle equazioni differenziali ordinarie",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("genera un argomento completo sul calcolo vettoriale",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("crea l'argomento sulla topologia degli spazi metrici",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("scrivi la teoria degli esponenziali e logaritmi",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("crea il documento sul teorema dei valori intermedi",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("scrivi un whitepaper sulla distribuzione normale",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("genera la struttura completa per il corso di probabilità",
     _j("LOOP","math_researcher","create_module",["create_module","create_file"])),
    ("crea un modulo su algebra lineare con esempi",
     _j("LOOP","math_researcher","create_module",["create_module","create_file"])),

    # MATH RESEARCHER — INFO (explain / answer)
    ("cos'è la derivata?",
     _j("INFO","math_researcher","explain_concept",[])),
    ("spiegami il teorema di Pitagora",
     _j("INFO","math_researcher","explain_concept",[])),
    ("cosa sono i numeri complessi?",
     _j("INFO","math_researcher","explain_concept",[])),
    ("qual è la formula di Eulero?",
     _j("INFO","math_researcher","explain_concept",[])),
    ("dimmi la definizione formale di limite",
     _j("INFO","math_researcher","explain_concept",[])),
    ("spiega la differenza tra convergenza puntuale e uniforme",
     _j("INFO","math_researcher","explain_concept",[])),
    ("cosa significa che una funzione è integrabile secondo Riemann?",
     _j("INFO","math_researcher","explain_concept",[])),
    ("illustra il principio di induzione matematica",
     _j("INFO","math_researcher","explain_concept",[])),
    ("qual è la differenza tra varianza e deviazione standard?",
     _j("INFO","math_researcher","explain_concept",[])),
    ("riassumimi la teoria degli insiemi di Cantor",
     _j("INFO","math_researcher","explain_concept",[])),
    ("descrivi il teorema di Bolzano-Weierstrass",
     _j("INFO","math_researcher","explain_concept",[])),
    ("come si calcola l'integrale di una funzione continua?",
     _j("INFO","math_researcher","explain_concept",[])),

    # =========================================================
    # CODE ARCHITECT — LOOP
    # =========================================================
    ("scrivi uno script python per ordinare una lista con quicksort",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    ("crea un componente React per mostrare una tabella dati",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    ("modifica il file chat_handler.py per aggiungere il logging",
     _j("LOOP","code_architect","edit_code",["read_file","edit_file"])),
    ("correggi il bug nel file api_router.py",
     _j("LOOP","code_architect","debug_code",["read_file","edit_file"])),
    ("refactorizza la funzione handle_chat per separare le responsabilità",
     _j("LOOP","code_architect","edit_code",["read_file","edit_file"])),
    ("aggiungi la gestione degli errori al server.py",
     _j("LOOP","code_architect","edit_code",["read_file","edit_file"])),
    ("crea un file di configurazione JSON per il progetto",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    ("implementa il pattern singleton per la connessione al database",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    ("sostituisci i print con il logging strutturato in core/logger.py",
     _j("LOOP","code_architect","edit_code",["read_file","edit_file"])),
    ("rinomina la funzione process_data in transform_data in utils.py",
     _j("LOOP","code_architect","rename_file",["read_file","edit_file"])),
    ("crea la classe DataManager con metodi CRUD",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    ("scrivi un middleware per l'autenticazione JWT",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    ("elimina il file obsoleto old_handler.py",
     _j("LOOP","code_architect","delete_file",["delete_file"])),

    # CODE ARCHITECT — INFO
    ("cosa fa il decoratore @property in Python?",
     _j("INFO","code_architect","explain_concept",[])),
    ("spiegami la differenza tra list e tuple in Python",
     _j("INFO","code_architect","explain_concept",[])),
    ("come funziona il garbage collector di Python?",
     _j("INFO","code_architect","explain_concept",[])),
    ("cosa significa async/await in JavaScript?",
     _j("INFO","code_architect","explain_concept",[])),
    ("spiega il pattern MVC",
     _j("INFO","code_architect","explain_concept",[])),

    # =========================================================
    # VIZ DESIGNER — LOOP
    # =========================================================
    ("crea un grafico D3 interattivo per la distribuzione normale",
     _j("LOOP","viz_designer","create_viz",["create_module","create_file"])),
    ("genera una visualizzazione HTML interattiva delle serie di Fourier",
     _j("LOOP","viz_designer","create_viz",["create_module","create_file"])),
    ("scrivi un file HTML con canvas per animare il pendolo",
     _j("LOOP","viz_designer","create_viz",["create_file"])),
    ("crea un diagramma SVG della struttura dei moduli",
     _j("LOOP","viz_designer","create_viz",["create_file"])),
    ("disegna un grafico a barre con D3.js per i dati di training",
     _j("LOOP","viz_designer","create_viz",["create_file"])),
    ("genera una mappa concettuale visiva in HTML e CSS",
     _j("LOOP","viz_designer","create_viz",["create_file"])),
    ("crea un visualizzatore 3D con Three.js per i vettori",
     _j("LOOP","viz_designer","create_viz",["create_file"])),
    ("modifica il file 01_S_analyzer.html per cambiare i colori del tema",
     _j("LOOP","viz_designer","edit_code",["read_file","edit_file"])),

    # VIZ DESIGNER — INFO
    ("come funziona la scala logaritmica in D3.js?",
     _j("INFO","viz_designer","explain_concept",[])),
    ("spiega la differenza tra SVG e Canvas",
     _j("INFO","viz_designer","explain_concept",[])),

    # =========================================================
    # TEST ENGINEER — LOOP
    # =========================================================
    ("scrivi i test pytest per la classe data_handler",
     _j("LOOP","test_engineer","run_test",["create_file","run_test"])),
    ("crea unit test per la funzione _normalize_data_path",
     _j("LOOP","test_engineer","run_test",["create_file","run_test"])),
    ("esegui i test esistenti nel file test_api.py",
     _j("LOOP","test_engineer","run_test",["run_test"])),
    ("aggiungi asserzioni al test test_chat_handler.py",
     _j("LOOP","test_engineer","run_test",["read_file","edit_file","run_test"])),
    ("scrivi integration test per l'endpoint /api/chat",
     _j("LOOP","test_engineer","run_test",["create_file","run_test"])),

    # TEST ENGINEER — INFO
    ("spiega la differenza tra unit test e integration test",
     _j("INFO","test_engineer","explain_concept",[])),
    ("cos'è il mocking in pytest?",
     _j("INFO","test_engineer","explain_concept",[])),

    # =========================================================
    # PROOF REVIEWER — LOOP
    # =========================================================
    ("rivedi la dimostrazione del teorema di compattezza nel file teoria/compattezza.md",
     _j("LOOP","proof_reviewer","review_proof",["read_file","edit_file"])),
    ("analizza e annota il whitepaper nella cartella docs",
     _j("LOOP","proof_reviewer","review_proof",["read_file","edit_file"])),
    ("confuta la dimostrazione nel file lemma_01.md",
     _j("LOOP","proof_reviewer","review_proof",["read_file","edit_file"])),

    # PROOF REVIEWER — INFO
    ("esamina logicamente questa dimostrazione: se A allora B...",
     _j("INFO","proof_reviewer","review_proof",[])),
    ("c'è un errore in questa dimostrazione per assurdo?",
     _j("INFO","proof_reviewer","review_proof",[])),
    ("fa' una peer review di questa dimostrazione del lemma di Zorn",
     _j("INFO","proof_reviewer","review_proof",[])),

    # =========================================================
    # SIGMA ARCHITECT — PLAN
    # =========================================================
    ("pianifica la roadmap per il modulo di analisi 2",
     _j("PLAN","sigma_architect","plan_roadmap",[])),
    ("crea un piano di sviluppo per il training pipeline",
     _j("PLAN","sigma_architect","plan_roadmap",[])),
    ("organizza i task per completare il corso di topologia",
     _j("PLAN","sigma_architect","plan_roadmap",[])),
    ("definisci l'architettura dei moduli per la nuova feature",
     _j("PLAN","sigma_architect","plan_roadmap",[])),

    # SIGMA ARCHITECT — LOOP
    ("crea il modulo 01_base per il topic analisi_funzionale",
     _j("LOOP","sigma_architect","create_module",["create_module"])),
    ("struttura i sottomoduli del corso di fisica matematica",
     _j("LOOP","sigma_architect","create_module",["create_module","create_file"])),

    # =========================================================
    # SIGMA ASSISTANT — INFO (greetings, general)
    # =========================================================
    ("ciao, chi sei?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("buongiorno!",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("cosa puoi fare?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("come funziona sigma studio?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("ciao, come stai?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("aiutami a capire come usare il sistema",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("qual è la differenza tra loop mode e ask mode?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("chi ha creato sigma studio?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("hello, what can you do?",
     _j("INFO","sigma_assistant","general_chat",[])),
    ("good morning, introduce yourself",
     _j("INFO","sigma_assistant","general_chat",[])),

    # =========================================================
    # EDGE CASES — ambiguous requests that require smart routing
    # =========================================================
    # "argomento" without write intent → INFO
    ("dimmi qualcosa sull'argomento degli esponenziali",
     _j("INFO","math_researcher","explain_concept",[])),
    # "spiega" + "crea" → LOOP wins
    ("spiega e poi crea un file sul teorema di Fermat",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    # "modifica" + code file → LOOP code_architect
    ("modifica execute_loop.py per aggiungere un timeout",
     _j("LOOP","code_architect","edit_code",["read_file","edit_file"])),
    # "teoria" alone → INFO
    ("parliamo di teoria dei gruppi",
     _j("INFO","math_researcher","explain_concept",[])),
    # Long complex request — still LOOP
    ("voglio che tu crei una serie di file markdown per il corso di analisi matematica 1 con tutti gli argomenti principali",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    # English LOOP
    ("write a markdown file about exponential functions",
     _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])),
    ("create a python script for data preprocessing",
     _j("LOOP","code_architect","edit_code",["create_file"])),
    # English INFO
    ("what is a derivative?",
     _j("INFO","math_researcher","explain_concept",[])),
    ("explain the concept of recursion",
     _j("INFO","code_architect","explain_concept",[])),
    # Delete / rename
    ("elimina il file vecchio.md dalla cartella docs",
     _j("LOOP","sigma_architect","delete_file",["delete_file"])),
    ("sposta il file teoria.md in docs/teoria.md",
     _j("LOOP","sigma_architect","rename_file",["rename_file"])),
]


# ---------------------------------------------------------------------------
# Paraphrase variants (add natural variation to trigger better generalization)
# ---------------------------------------------------------------------------

PARAPHRASE_PREFIXES = [
    "", "", "",  # original (weight 3x)
    "per favore, ",
    "potresti ",
    "ho bisogno che tu ",
    "voglio che tu ",
    "ti chiedo di ",
    "puoi ",
    "per piacere ",
    "mi serve che tu ",
]

PARAPHRASE_MATH_WRITE = [
    "scrivi un argomento su {topic}",
    "crea un documento formale su {topic}",
    "genera la trattazione teorica di {topic}",
    "scrivi la teoria di {topic} in un file markdown",
    "prepara un modulo accademico su {topic}",
    "crea il materiale didattico su {topic}",
    "sviluppa un documento scientifico su {topic}",
    "scrivi in modo rigoroso l'argomento {topic}",
    "write a topic file about {topic}",
    "create academic notes on {topic}",
]

MATH_TOPICS = [
    "gli esponenziali", "i logaritmi", "le derivate", "gli integrali",
    "le serie numeriche", "la topologia", "l'algebra lineare",
    "le equazioni differenziali", "la probabilità", "la statistica",
    "il calcolo vettoriale", "la teoria dei gruppi", "l'analisi complessa",
    "le trasformate di Fourier", "le equazioni alle derivate parziali",
    "la geometria differenziale", "la teoria dei grafi", "la combinatoria",
    "la teoria degli insiemi", "la logica matematica",
]

PARAPHRASE_CODE_WRITE = [
    "scrivi uno script {lang} per {task}",
    "crea un file {lang} che {task}",
    "implementa in {lang} {task}",
    "sviluppa un programma {lang} per {task}",
    "write a {lang} script to {task}",
    "create a {lang} function that {task}",
]

CODE_LANGS = ["python", "JavaScript", "TypeScript", "Python"]
CODE_TASKS = [
    "parsare file JSON", "ordinare una lista", "fare richieste HTTP",
    "leggere file CSV", "gestire eccezioni", "implementare un cache LRU",
    "validare input utente", "connettersi a un database SQLite",
]


def _augment_math_write():
    examples = []
    for topic in MATH_TOPICS:
        for template in PARAPHRASE_MATH_WRITE:
            text = template.format(topic=topic)
            prefix = random.choice(PARAPHRASE_PREFIXES)
            examples.append((
                prefix + text,
                _j("LOOP","math_researcher","create_topic_file",["create_module","create_file"])
            ))
    return examples


def _augment_code_write():
    examples = []
    for lang in CODE_LANGS:
        for task in CODE_TASKS:
            for template in PARAPHRASE_CODE_WRITE:
                text = template.format(lang=lang, task=task)
                examples.append((
                    text,
                    _j("LOOP","code_architect","edit_code",["create_file"])
                ))
    return examples


def _augment_info():
    """Generate informational query variants."""
    topics = [
        "la derivata", "l'integrale", "la probabilità bayesiana",
        "il teorema di Bayes", "la trasformata di Laplace",
        "l'algebra booleana", "i numeri complessi",
        "il metodo dei minimi quadrati", "la regressione lineare",
    ]
    templates = [
        "cos'è {topic}?",
        "spiega {topic}",
        "dimmi qualcosa su {topic}",
        "descrivi {topic}",
        "illustra {topic}",
        "cosa si intende per {topic}?",
        "what is {topic}?",
        "explain {topic}",
    ]
    examples = []
    for t in topics:
        for tmpl in templates:
            examples.append((
                tmpl.format(topic=t),
                _j("INFO","math_researcher","explain_concept",[])
            ))
    return examples


# ---------------------------------------------------------------------------
# Build dataset
# ---------------------------------------------------------------------------

def build_dataset(augment: bool = True) -> list[dict]:
    """Build final dataset from seed + optional augmentation."""
    all_examples = list(SEED_EXAMPLES)

    if augment:
        all_examples.extend(_augment_math_write())
        all_examples.extend(_augment_code_write())
        all_examples.extend(_augment_info())

    # Shuffle for balanced training
    random.seed(42)
    random.shuffle(all_examples)

    records = []
    for user_text, assistant_json in all_examples:
        records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_text.strip()},
                {"role": "assistant", "content": assistant_json},
            ]
        })
    return records


def save_dataset(records: list[dict], output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def print_stats(records: list[dict]):
    from collections import Counter
    modes = Counter()
    agents = Counter()
    intents = Counter()
    for r in records:
        try:
            d = json.loads(r["messages"][2]["content"])
            modes[d["mode"]] += 1
            agents[d["agent"]] += 1
            intents[d["intent"]] += 1
        except Exception:
            pass
    print("\n" + "="*50)
    print("  DATASET STATS -- %d total examples" % len(records))
    print("="*50)
    print("\nMODES:")
    for k, v in modes.most_common():
        bar = "|" * (v // 5)
        print("  %-10s %4d %s" % (k, v, bar))
    print("\nAGENTS:")
    for k, v in agents.most_common():
        bar = "|" * (v // 5)
        print("  %-20s %4d %s" % (k, v, bar))
    print("\nINTENTS:")
    for k, v in intents.most_common():
        print("  %-25s %4d" % (k, v))
    print()



# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Sigma Router intent dataset")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH), help="Output JSONL path")
    parser.add_argument("--augment", action="store_true", default=True, help="Enable paraphrase augmentation (default: True)")
    parser.add_argument("--no-augment", dest="augment", action="store_false", help="Disable augmentation")
    parser.add_argument("--preview", type=int, default=0, help="Print N example records and exit")
    args = parser.parse_args()

    print("[*] Sigma Router -- Intent Dataset Generator")
    print("   Augmentation: %s" % ("ON" if args.augment else "OFF"))
    print("   Output: %s" % args.output)

    records = build_dataset(augment=args.augment)

    if args.preview > 0:
        for r in records[:args.preview]:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        print_stats(records)
    else:
        n = save_dataset(records, Path(args.output))
        print_stats(records)
        print("[OK] Saved %d examples -> %s" % (n, args.output))
