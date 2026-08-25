#!/usr/bin/env python3
# ==============================================================================
# scripts/sigma_repos.py — Un lavoro solo, repository diversi
#
# Sigma Studio, i moduli e i provider stanno in repository separati, ma si
# lavora in un posto solo. Finche' i moduli erano copie, una modifica fatta
# dentro Sigma Studio non arrivava mai al repository che la doveva ricevere;
# con i moduli collegati (core/module_links.py) il file e' lo stesso, quindi
# ogni repository vede le proprie modifiche e basta committare nel posto giusto.
#
# Questo comando mostra lo stato di tutti i repository coinvolti e permette di
# committare in uno o in tutti senza cambiare cartella a mano — che e' proprio
# il passaggio in cui si finisce per committare nel repository sbagliato.
#
#   python scripts/sigma_repos.py stato
#   python scripts/sigma_repos.py commit -m "messaggio"
#   python scripts/sigma_repos.py commit -m "messaggio" --repo moduli
#   python scripts/sigma_repos.py push
# ==============================================================================
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.module_links import repositories        # noqa: E402


def _git(radice: str, *argomenti: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", radice, *argomenti],
                          capture_output=True, text=True)


def _ramo(radice: str) -> str:
    return _git(radice, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "?"


def _modifiche(radice: str) -> list:
    righe = _git(radice, "status", "--porcelain").stdout.splitlines()
    return [r for r in righe if r.strip()]


def _elenco(filtro: str | None) -> list:
    repos = repositories()
    if filtro:
        f = filtro.lower()
        repos = [r for r in repos
                 if f in r["nome"].lower() or f in r["ruolo"].lower()]
        if not repos:
            print(f"Nessun repository corrisponde a '{filtro}'.", file=sys.stderr)
    return repos


def comando_stato(args) -> int:
    for repo in _elenco(args.repo):
        modifiche = _modifiche(repo["path"])
        moduli = f"  [{repo['moduli']}]" if repo.get("moduli") else ""
        print(f"\n{repo['nome']}  ({repo['ruolo']}{moduli})")
        print(f"  {repo['path']}")
        print(f"  ramo: {_ramo(repo['path'])} — {len(modifiche)} modifiche")
        for riga in modifiche[:20]:
            print(f"    {riga}")
        if len(modifiche) > 20:
            print(f"    ... e altre {len(modifiche) - 20}")
    print()
    return 0


def comando_commit(args) -> int:
    uscita = 0
    for repo in _elenco(args.repo):
        modifiche = _modifiche(repo["path"])
        if not modifiche:
            print(f"{repo['nome']}: niente da committare")
            continue

        print(f"\n{repo['nome']} ({repo['ruolo']}): {len(modifiche)} modifiche")
        for riga in modifiche[:20]:
            print(f"    {riga}")

        if not args.si:
            risposta = input(f"  committare in {repo['nome']}? [s/N] ").strip().lower()
            if risposta not in ("s", "si", "y", "yes"):
                print("  saltato")
                continue

        aggiunta = _git(repo["path"], "add", "-A")
        if aggiunta.returncode != 0:
            print(f"  errore in git add: {aggiunta.stderr.strip()}", file=sys.stderr)
            uscita = 1
            continue

        esito = _git(repo["path"], "commit", "-m", args.messaggio)
        if esito.returncode == 0:
            print(f"  {esito.stdout.strip().splitlines()[0]}")
        else:
            print(f"  errore: {esito.stderr.strip() or esito.stdout.strip()}",
                  file=sys.stderr)
            uscita = 1
    return uscita


def comando_push(args) -> int:
    uscita = 0
    for repo in _elenco(args.repo):
        radice = repo["path"]
        davanti = _git(radice, "rev-list", "--count", "@{upstream}..HEAD").stdout.strip()
        if davanti in ("", "0"):
            print(f"{repo['nome']}: niente da inviare")
            continue

        print(f"{repo['nome']}: {davanti} commit da inviare su {_ramo(radice)}")
        if not args.si:
            risposta = input(f"  push di {repo['nome']}? [s/N] ").strip().lower()
            if risposta not in ("s", "si", "y", "yes"):
                print("  saltato")
                continue

        esito = _git(radice, "push")
        if esito.returncode == 0:
            print("  inviato")
        else:
            print(f"  errore: {esito.stderr.strip()}", file=sys.stderr)
            uscita = 1
    return uscita


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stato e commit dei repository coinvolti in questa installazione.")
    sotto = parser.add_subparsers(dest="comando", required=True)

    p_stato = sotto.add_parser("stato", help="mostra lo stato di ogni repository")
    p_stato.add_argument("--repo", help="filtra per nome o ruolo")
    p_stato.set_defaults(funzione=comando_stato)

    p_commit = sotto.add_parser("commit", help="committa in ogni repository con modifiche")
    p_commit.add_argument("-m", "--messaggio", required=True)
    p_commit.add_argument("--repo", help="filtra per nome o ruolo")
    p_commit.add_argument("-s", "--si", action="store_true",
                          help="non chiedere conferma per ogni repository")
    p_commit.set_defaults(funzione=comando_commit)

    p_push = sotto.add_parser("push", help="invia i commit locali")
    p_push.add_argument("--repo", help="filtra per nome o ruolo")
    p_push.add_argument("-s", "--si", action="store_true")
    p_push.set_defaults(funzione=comando_push)

    args = parser.parse_args()
    return args.funzione(args)


if __name__ == "__main__":
    sys.exit(main())
