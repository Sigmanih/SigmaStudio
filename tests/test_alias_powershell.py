"""In PowerShell `curl` non e' curl, ed e' il modo peggiore di non esserlo.

Gli agenti si sono scritti da soli la coda di lavoro, e una delle voci portava
questa verifica:

    docker compose up -d && sleep 5 && curl -s http://localhost:8080/api/opere

Ragionevole ovunque, tranne qui. `curl` in PowerShell 5.1 e' un alias di
`Invoke-WebRequest`, che non conosce `-s`:

    Invoke-WebRequest : Uno o piu' parametri obbligatori risultano mancanti: Uri

Codice 1, nessuna richiesta partita. Il guaio non e' che fallisca: e' che
fallisce **come se il sito non rispondesse**, e manda a cercare un guasto in un
sito che sta benissimo. E' la stessa confusione fra la prova e il lavoro che e'
gia' costata tre run con `&&`.

Due difese, e servono entrambe: il vero `curl.exe` c'e' su Windows 10 e
successivi, quindi lo si chiama per nome intero e l'alias non entra in mezzo; e
se un comando muore comunque sugli argomenti di una cmdlet, il verificatore lo
chiama «non eseguito» invece di «fallito».
"""

import sys

import pytest

from core.harness.terminal import adatta_alla_shell
from core.harness.verification import parse_verification

windows = pytest.mark.skipif(sys.platform != "win32", reason="l'alias esiste solo li'")

ERRORE_ALIAS = (
    "Invoke-WebRequest : Impossibile elaborare il comando. Uno o piu' parametri "
    "obbligatori risultano mancanti: Uri.\n"
    "    + CategoryInfo          : InvalidArgument: (:) [Invoke-WebRequest], "
    "ParameterBindingException\n"
    "    + FullyQualifiedErrorId : MissingMandatoryParameter,"
    "Microsoft.PowerShell.Commands.InvokeWebRequestCommand"
)


@windows
class TestIlVeroProgrammaVincesullAlias:
    def test_curl_con_flag_posix_diventa_curl_exe(self):
        assert adatta_alla_shell("curl -s http://localhost:8080").startswith("curl.exe -s")

    def test_anche_dentro_una_catena(self):
        tradotto = adatta_alla_shell("docker compose up -d && curl -s http://localhost:8080")
        assert "curl.exe -s" in tradotto

    def test_senza_flag_si_lascia_stare(self):
        """`curl http://...` funziona anche come cmdlet, e chi scrive
        `curl -Uri ...` sta chiamando la cmdlet apposta."""
        assert adatta_alla_shell("curl http://localhost:8080") == "curl http://localhost:8080"

    def test_un_comando_che_nomina_curl_non_viene_toccato(self):
        """La riscrittura vale per il programma chiamato, non per la parola."""
        comando = 'node -e "console.log(\'usa curl -s\')"'
        assert adatta_alla_shell(comando) == comando

    def test_chiama_davvero_il_sito(self):
        """La prova che conta: dopo la traduzione la richiesta parte."""
        from core.harness.terminal import execute_shell_command_sync

        esito = execute_shell_command_sync(
            "curl -s -o NUL -w %{http_code} https://example.com", timeout_seconds=30)
        assert "Invoke-WebRequest" not in (esito["stderr"] or "")


class TestQuandoMuoreLoStessoSiCapisce:
    """Non tutti gli alias hanno un `.exe` dietro: `rm -rf`, `ls -la`, `ps aux`
    restano cmdlet. Li' non si puo' riscrivere niente, ma si puo' almeno dire
    che il comando non e' stato eseguito."""

    def test_l_errore_sugli_argomenti_e_un_comando_non_eseguito(self):
        rapporto = parse_verification("curl -s http://localhost:8080", 1, "", ERRORE_ALIAS)
        assert rapporto.kind == "non_eseguito"

    def test_e_lo_dice_a_chi_legge(self):
        rapporto = parse_verification("curl -s http://localhost:8080", 1, "", ERRORE_ALIAS)
        assert "non e' stato eseguito" in rapporto.summary

    def test_un_sito_che_davvero_non_risponde_resta_un_fallimento(self):
        """Se prendesse anche questo, spegnerebbe la verifica invece di
        renderla leggibile."""
        rapporto = parse_verification(
            "curl.exe -s http://localhost:8080", 7, "",
            "curl: (7) Failed to connect to localhost port 8080: Connection refused")
        assert rapporto.kind != "non_eseguito"
