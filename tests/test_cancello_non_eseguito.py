"""Un cancello rifiutato dalla shell non e' un cancello fallito.

Sono due esiti che si assomigliano — codice diverso da zero, un messaggio —
e chiedono due rimedi opposti. «Fallito» dice: il codice non va, riscrivilo.
«Non eseguito» dice: il codice non lo sappiamo, il comando e' sbagliato.

Confonderli e' costato tre run interi. Il task `frontend` della Biblioteca
Digitale e' stato rifatto tre volte, ventisei turni ciascuna, perche' il suo
`npm install && npm run build` non parte su Windows PowerShell 5.1. Ogni
tentativo leggeva «build fallita» e riscriveva del codice che era gia' giusto,
senza che nessuno l'avesse mai messo alla prova.
"""

import pytest

from core.harness.verification import parse_verification

# Il testo vero, copiato dal registro della sessione fallita. Il messaggio e'
# in italiano perche' la macchina lo e'; le sigle restano in inglese, ed e' su
# quelle che ci si appoggia.
RIFIUTO_POWERSHELL = (
    "Il token '&&' non e' un separatore di istruzioni valido in questa versione.\n"
    "    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordException\n"
    "    + FullyQualifiedErrorId : InvalidEndOfLine"
)

COMANDO_INESISTENTE = (
    "pnpm : Termine 'pnpm' non riconosciuto come nome di cmdlet.\n"
    "    + CategoryInfo          : ObjectNotFound: (pnpm:String) [], CommandNotFoundException\n"
    "    + FullyQualifiedErrorId : CommandNotFoundException"
)

BUILD_DAVVERO_ROTTA = """> frontend@0.0.0 build
> vite build

x Build failed in 412ms
error during build:
src/App.jsx:12:3: ERROR: Expected ")" but found "const"
"""


class TestIlRifiutoDellaShell:
    def test_il_caso_che_e_costato_tre_run(self):
        r = parse_verification("npm --prefix frontend install && npm run build",
                               1, "", RIFIUTO_POWERSHELL)
        assert r.kind == "non_eseguito"
        assert r.is_valid is False

    def test_il_verdetto_dice_dove_guardare(self):
        """«build fallita» mandava a riscrivere il codice. Il codice stava bene."""
        r = parse_verification("npm run build", 1, "", RIFIUTO_POWERSHELL)
        assert "non e' stato eseguito" in r.summary
        assert "non dimostra niente sul codice" in r.summary.lower()

    def test_un_comando_che_non_esiste_su_questa_macchina(self):
        r = parse_verification("pnpm install", 1, "", COMANDO_INESISTENTE)
        assert r.kind == "non_eseguito"

    def test_vale_anche_per_la_shell_posix(self):
        r = parse_verification("npm ci", 127, "", "sh: 1: npm: command not found")
        assert r.kind == "non_eseguito"

    def test_arriva_anche_dallo_stdout(self):
        """Non tutte le shell mettono il rifiuto su stderr."""
        r = parse_verification("npm run build", 1, RIFIUTO_POWERSHELL, "")
        assert r.kind == "non_eseguito"


class TestCioCheDeveRestareUnFallimento:
    """La guardia sta prima di tutti i parser: se prendesse troppo, spegnerebbe
    la verifica invece di renderla leggibile."""

    def test_una_build_rotta_resta_una_build_rotta(self):
        r = parse_verification("npm run build", 1, BUILD_DAVVERO_ROTTA, "")
        assert r.kind == "build"
        assert r.is_valid is False

    def test_un_test_fallito_resta_un_test_fallito(self):
        r = parse_verification("pytest tests/", 1, "collected 3 items\n\n1 failed, 2 passed", "")
        assert r.kind == "pytest"
        assert r.failed == 1

    def test_un_comando_riuscito_non_diventa_mai_non_eseguito(self):
        """Un programma puo' nominare «command not found» nel proprio output —
        un log, un test che verifica proprio quel messaggio — e aver girato."""
        r = parse_verification(
            "node --test backend/cli.test.js", 0,
            "ok 1 - segnala 'command not found' quando manca il binario\n# pass 1", "")
        assert r.kind != "non_eseguito"
        assert r.is_valid is True


def test_la_traduzione_della_catena_rende_la_guardia_quasi_inutile():
    """Le due correzioni lavorano insieme, e in quest'ordine: la traduzione fa
    partire il comando, la guardia raccoglie cio' che non parte lo stesso.
    Questo test esiste perche' la prima non basta da sola — un binario assente
    o una shell diversa restano fuori dalla sua portata."""
    from core.harness.terminal import adatta_alla_shell

    tradotto = adatta_alla_shell("npm install && npm run build")
    import sys
    if sys.platform == "win32":
        assert "&&" not in tradotto
