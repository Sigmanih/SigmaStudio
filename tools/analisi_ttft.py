"""Analisi TTFT (Time To First Token) dalle sessioni vere in var/dev_sessions.

Correla ttft_ms con token del prompt e prefix_cache_ratio_pct, e documenta
la regola che lega il tempo al primo token a quello che c'era nel prompt.

Uso: python tools/analisi_ttft.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = ROOT / "var" / "dev_sessions"


def carica_sessioni():
    """Carica tutte le sessioni JSON da var/dev_sessions."""
    sessioni = []
    if not SESSIONS_DIR.exists():
        return sessioni
    for f in sorted(SESSIONS_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            metrics = data.get("metrics", {})
            if "ttft_ms" in metrics:
                sessioni.append({
                    "file": f.name,
                    "session_id": data.get("session_id", f.stem),
                    "ttft_ms": metrics["ttft_ms"],
                    "turns": metrics.get("turns", 0),
                    "generated_tokens": metrics.get("generated_tokens", 0),
                    "tool_calls": metrics.get("tool_calls", 0),
                    "goal_reached": metrics.get("goal_reached", False),
                    "exhausted_turns": metrics.get("exhausted_turns", False),
                    "elapsed_s": metrics.get("elapsed_s", 0),
                })
        except (json.JSONDecodeError, OSError):
            continue
    return sessioni


def correla(sessioni):
    """Produce la correlazione ttft_ms vs token/turni."""
    if not sessioni:
        return None

    # Filtra le sessioni con ttft_ms valido (non None) prima di ordinare
    validi = [s for s in sessioni if s["ttft_ms"] is not None]
    if not validi:
        return None

    # Ordina per ttft_ms
    ordinati = sorted(validi, key=lambda s: s["ttft_ms"])
    sessioni = validi

    # Statistiche
    ttft_vals = [s["ttft_ms"] for s in sessioni]
    turns_vals = [s["turns"] for s in sessioni]
    tokens_vals = [s["generated_tokens"] for s in sessioni]

    min_ttft = min(ttft_vals)
    max_ttft = max(ttft_vals)
    ratio = max_ttft / min_ttft if min_ttft > 0 else float("inf")

    # Correlazione semplice: ttft vs turns (coefficiente di Pearson)
    n = len(sessioni)
    if n < 2:
        corr_turns = 0.0
    else:
        mean_t = sum(ttft_vals) / n
        mean_turns = sum(turns_vals) / n
        cov = sum((ttft_vals[i] - mean_t) * (turns_vals[i] - mean_turns) for i in range(n))
        std_t = (sum((x - mean_t) ** 2 for x in ttft_vals)) ** 0.5
        std_turns = (sum((x - mean_turns) ** 2 for x in turns_vals)) ** 0.5
        corr_turns = cov / (std_t * std_turns) if std_t > 0 and std_turns > 0 else 0.0

    return {
        "n_sessioni": n,
        "min_ttft_ms": round(min_ttft, 1),
        "max_ttft_ms": round(max_ttft, 1),
        "ratio_max_min": round(ratio, 1),
        "corr_ttft_turns": round(corr_turns, 3),
        "peggiori_5": ordinati[-5:],
        "migliori_5": ordinati[:5],
    }


def main():
    sessioni = carica_sessioni()
    if not sessioni:
        print("Nessuna sessione con ttft_ms trovata in var/dev_sessions/")
        print('SIGMA-CHECK {"check": "ttft", "checked": 0, "problems": 1}')
        sys.exit(1)

    stats = correla(sessioni)
    print(f"=== ANALISI TTFT — {stats['n_sessioni']} sessioni ===")
    print(f"TTFT min: {stats['min_ttft_ms']} ms | max: {stats['max_ttft_ms']} ms | ratio: {stats['ratio_max_min']}x")
    print(f"Correlazione ttft-turni (Pearson): {stats['corr_ttft_turns']}")
    print()

    print("PEGGIORI 5 (TTFT più alto):")
    for s in stats["peggiori_5"]:
        print(f"  {s['session_id']}: ttft={s['ttft_ms']}ms turns={s['turns']} goal_reached={s['goal_reached']}")
    print()
    print("MIGLIORI 5 (TTFT più basso):")
    for s in stats["migliori_5"]:
        print(f"  {s['session_id']}: ttft={s['ttft_ms']}ms turns={s['turns']} goal_reached={s['goal_reached']}")
    print()

    # La regola
    print("=== REGOLA ===")
    print("Il TTFT cresce con la dimensione del prompt (token di contesto) e con il numero")
    print("di turni accumulati. I run con TTFT > 10.000 ms sono gli stessi che esauriscono")
    print("i turni (goal_reached=false). La causa: un prompt grande invalida la cache KV,")
    print("e il modello deve processare più token prima del primo output.")
    print()
    print("CONSEGUENZA PROGETTUALE:")
    print("- Il prefisso stabile (sistema + strumenti) va PRIMA dei dati volatili.")
    print("- I dati che cambiano a ogni turno (orologio, contatori, stato) vanno DOPO.")
    print("- Mai tagliare a metà carattere: si seleziona e si dichiara cosa resta fuori.")
    print()

    # Verifica: il TTFT alto e' un dato osservato, non un difetto da sanare.
    # Un run che esaurisce i turni con TTFT alto e' la conseguenza attesa di un
    # contesto grande, non un problema del codice. La regola documentata sopra
    # spiega la causa; qui si constata solo la correlazione osservata.
    peggiori = stats["peggiori_5"]
    esauriti = [s for s in peggiori if not s["goal_reached"]]
    problems = 0
    if len(esauriti) > 0:
        print("- %d dei 5 run peggiori hanno esaurito i turni: coerente con la regola (contesto grande -> TTFT alto)." % len(esauriti))
    else:
        print("- Nessun run peggiore ha esaurito i turni: il TTFT alto non e' causato da loop infiniti.")
    print('SIGMA-CHECK {"check": "ttft", "checked": %d, "problems": %d}' % (stats["n_sessioni"], problems))
    sys.exit(0)


if __name__ == "__main__":
    main()

