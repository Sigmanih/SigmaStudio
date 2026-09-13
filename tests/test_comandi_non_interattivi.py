"""Un comando che fa una domanda non deve fermare il run.

Difetto trovato su un run vero dell'utente, rimasto appeso cinquanta minuti.
L'agente ha eseguito `npx create-react-app .` e npx ha risposto:

    Need to install the following packages: create-react-app@5.1.0
    Ok to proceed? (y)

Nessuno risponde mai a quella domanda. `stdin` non era redirezionato, quindi il
comando restava in attesa fino al timeout, e l'agente aspettava con lui — senza
un errore da leggere, senza un modo di capire.

Due rimedi, nell'ordine giusto:

1. **stdin chiuso**, cosi' una domanda fallisce subito invece di appendere;
2. **l'ambiente che disinnesca le domande**, perche' fallire non era cio' che
   l'agente voleva: npx e npm hanno un modo dichiarato di non chiedere, e
   usarlo trasforma «si blocca» in «funziona».
"""

import os

from core.harness.terminal import _ambiente_non_interattivo, execute_shell_command_sync


class TestStdinChiuso:
    def test_un_comando_che_legge_stdin_non_resta_appeso(self, tmp_path):
        """Legge EOF e finisce: e' la differenza fra un errore e un'attesa."""
        esito = execute_shell_command_sync(
            'python -c "import sys; d=sys.stdin.read(); print(len(d))"',
            cwd=str(tmp_path), timeout_seconds=20,
        )
        assert esito.get("returncode") == 0
        assert "0" in str(esito.get("stdout") or "")
        assert not esito.get("timed_out")

    def test_un_comando_normale_continua_a_funzionare(self, tmp_path):
        esito = execute_shell_command_sync(
            'python -c "print(2+2)"', cwd=str(tmp_path), timeout_seconds=20)
        assert "4" in str(esito.get("stdout") or "")


class TestLeDomandeDisinnescate:
    def test_le_variabili_che_gli_strumenti_node_rispettano(self):
        a = _ambiente_non_interattivo()
        assert a["CI"] == "1"
        assert a["npm_config_yes"] == "true"

    def test_non_si_cancella_l_ambiente_esistente(self, monkeypatch):
        """Il comando deve trovare il PATH e tutto il resto: si aggiunge, non
        si sostituisce."""
        monkeypatch.setenv("UNA_MIA_VARIABILE", "valore")
        a = _ambiente_non_interattivo()
        assert a.get("UNA_MIA_VARIABILE") == "valore"
        assert "PATH" in a or "Path" in a

    def test_una_scelta_gia_fatta_dall_utente_non_viene_scavalcata(self, monkeypatch):
        monkeypatch.setenv("CI", "0")
        assert _ambiente_non_interattivo()["CI"] == "0"

    def test_l_ambiente_arriva_davvero_al_comando(self, tmp_path):
        esito = execute_shell_command_sync(
            'python -c "import os; print(os.environ.get(\'npm_config_yes\'))"',
            cwd=str(tmp_path), timeout_seconds=20,
        )
        assert "true" in str(esito.get("stdout") or "")
