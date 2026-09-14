"""`&&` non arriva alla shell di Windows, e un cancello che non parte non prova niente.

Il task `frontend` della Biblioteca Digitale e' fallito **tre volte di fila**,
ventisei turni ciascuna, su un lavoro che era gia' buono. Nel registro di
sessione si legge tutto:

    npm --prefix frontend install ... && npm --prefix frontend run build   rc=1
    npm --prefix frontend install ... ;  npm --prefix frontend run build   rc=0

Lo stesso lavoro, due volte, due esiti. La differenza non e' il codice: e' che
Windows PowerShell 5.1 non conosce `&&` e si ferma prima di eseguire, con
`Il token '&&' non e' un separatore di istruzioni valido in questa versione`.
Gli agenti l'avevano capito e usavano `;`; il cancello di verifica pero'
riesegue il testo scritto nella coda, e quel testo non era eseguibile.

E' il difetto peggiore che possa avere un harness che pretende prove: non
sbaglia la risposta, rende impossibile darne una.
"""

import sys

import pytest

from core.harness.terminal import adatta_alla_shell, spezza_la_catena

windows = pytest.mark.skipif(sys.platform != "win32", reason="la traduzione serve solo li'")

VERIFICA_FRONTEND = ("npm --prefix frontend install --no-audit --no-fund "
                     "&& npm --prefix frontend run build")

# Il cancello dello stack: la catena e' di primo livello, ma dentro il `node -e`
# c'e' un `&&` che appartiene a JavaScript e non va toccato.
VERIFICA_STACK = (
    'docker compose up -d --build && node -e "(async()=>{'
    "const a=await fetch('http://localhost:8080');"
    "const b=await fetch('http://localhost:8080/api/opere');"
    'if(a.status===200&&b.status===200){process.exit(0)}})()"'
)


class TestDoveSiSpezzaLaCatena:
    def test_una_catena_semplice(self):
        assert spezza_la_catena("uno && due") == [("", "uno"), ("&&", "due")]

    def test_un_comando_solo_resta_intero(self):
        assert spezza_la_catena("npm test") == [("", "npm test")]

    def test_i_due_operatori_si_distinguono(self):
        assert spezza_la_catena("a && b || c") == [("", "a"), ("&&", "b"), ("||", "c")]

    def test_fra_virgolette_non_si_tocca(self):
        """Il caso vero: `&&` di JavaScript dentro l'argomento di `node -e`."""
        pezzi = spezza_la_catena(VERIFICA_STACK)
        assert len(pezzi) == 2, "spezzato dentro le virgolette"
        assert "a.status===200&&b.status===200" in pezzi[1][1]

    def test_anche_fra_apici_singoli(self):
        pezzi = spezza_la_catena("echo 'a && b' && echo fatto")
        assert pezzi == [("", "echo 'a && b'"), ("&&", "echo fatto")]

    def test_l_accento_grave_protegge_la_virgoletta(self):
        pezzi = spezza_la_catena('echo "vir`"golette" && echo fatto')
        assert len(pezzi) == 2


@windows
class TestIlComandoDiventaEseguibile:
    def _esegui(self, comando):
        from core.harness.terminal import execute_shell_command_sync
        return execute_shell_command_sync(comando, timeout_seconds=60)

    def test_il_token_non_e_piu_un_errore_di_sintassi(self):
        """Il sintomo esatto letto nel registro."""
        esito = self._esegui("cmd /c exit 0 && cmd /c exit 0")
        assert "non � un separatore" not in esito["stderr"]
        assert "not a valid statement separator" not in esito["stderr"]
        assert esito["returncode"] == 0, esito

    def test_il_secondo_pezzo_gira_davvero(self):
        esito = self._esegui("cmd /c exit 0 && echo ARRIVATO")
        assert "ARRIVATO" in esito["stdout"]

    def test_se_il_primo_fallisce_il_secondo_non_parte(self):
        """E' tutto il senso di `&&`: senza, si «verifica» su un albero rotto."""
        esito = self._esegui("cmd /c exit 3 && echo NON_DEVE_USCIRE")
        assert "NON_DEVE_USCIRE" not in esito["stdout"]
        assert esito["returncode"] == 3, "il codice del pezzo fallito va riportato"

    def test_un_fallimento_non_diventa_un_successo(self):
        esito = self._esegui("cmd /c exit 1 && cmd /c exit 0")
        assert esito["returncode"] != 0, (
            "un cancello che torna zero dichiara fatto cio' che non e' fatto")

    def test_oppure_esegue_solo_dopo_un_fallimento(self):
        esito = self._esegui("cmd /c exit 1 || echo RIPIEGO")
        assert "RIPIEGO" in esito["stdout"]
        assert esito["returncode"] == 0

    def test_oppure_non_esegue_dopo_un_successo(self):
        esito = self._esegui("cmd /c exit 0 || echo NON_DEVE_USCIRE")
        assert "NON_DEVE_USCIRE" not in esito["stdout"]

    def test_la_catena_si_legge_da_sinistra_a_destra(self):
        esito = self._esegui("cmd /c exit 1 && echo A || echo B")
        assert "B" in esito["stdout"] and "A" not in esito["stdout"]

    def test_un_comando_senza_catena_non_viene_riscritto(self):
        assert adatta_alla_shell("npm test") == "npm test"

    def test_le_virgolette_sopravvivono_all_esecuzione(self):
        esito = self._esegui('cmd /c exit 0 && node -e "if(1===1&&2===2){console.log(\'DENTRO\')}"')
        assert "DENTRO" in esito["stdout"], esito


def test_passa_da_tutte_le_strade_verso_la_shell():
    """Una traduzione applicata in due punti su tre lascia in piedi il difetto."""
    import inspect

    from core.harness import terminal

    sorgente = inspect.getsource(terminal)
    assert "get_default_shell() + [command]" not in sorgente, (
        "un punto esegue ancora il comando grezzo")
    assert sorgente.count("comando_per_la_shell(command)") == 3
