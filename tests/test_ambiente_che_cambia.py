"""La sandbox si accende a meta' di un run, e cio' che l'agente aveva costruito sparisce.

Successo dal vivo su un task che stava scrivendo una cassa per bar. Fino alle
18:55 l'agente lavorava sull'host e andava tutto:

    cd .../backend; python -m venv .venv                      rc=0
    Start-Process .\\.venv\\Scripts\\python.exe                  rc=0

Poi la sandbox e' stata accesa. `carica_config()` rilegge il file a ogni
comando, quindi il cambio e' entrato in vigore subito — ed era cio' che chi
l'ha acceso voleva. Da li' in avanti:

    .\\.venv\\Scripts\\python.exe -c ...                        127
    Invoke-WebRequest -Uri ...                               127
    pip install fastapi uvicorn                                1

Dentro un contenitore Linux quel `.venv` di Windows non esiste, PowerShell non
esiste, e il processo avviato prima e' rimasto sull'host. **Nessuno gliel'ha
detto.** Dal suo punto di vista comandi che funzionavano cinque minuti prima
avevano smesso, e l'unica spiegazione a disposizione era «ho sbagliato io».

E il `pip install` non poteva riuscire in nessun caso: quel contenitore aveva
`network: false`. L'agente leggeva un errore DNS in fondo a trecento righe di
ritentativi, che somiglia a un guasto e non lo e'.
"""

import pytest

from core.harness.esecutori import EsecutoreContenitore, _installa_qualcosa
from core.harness.ledger import DevSessionLedger


def _comando(ledger, cmd, dove, rc=0):
    ledger.record_tool("terminal", {"command": cmd},
                       {"tool": "terminal", "success": rc == 0, "returncode": rc,
                        "command": cmd, "dove": dove})


class TestIlCambioSiVede:
    def test_quando_i_comandi_cambiano_casa_lo_si_dice(self, tmp_path):
        ledger = DevSessionLedger(goal="fai una cassa", workspace_root=str(tmp_path))
        _comando(ledger, "python -m venv .venv", "host")
        _comando(ledger, ".venv/bin/python -c 'import main'", "container", rc=127)
        assert "cambiato casa" in ledger.render_state_block()

    def test_e_si_dice_da_dove_a_dove(self, tmp_path):
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        _comando(ledger, "python -m venv .venv", "host")
        _comando(ledger, "pip install x", "container", rc=1)
        stato = ledger.render_state_block()
        assert "«host»" in stato and "«container»" in stato

    def test_si_dice_cosa_e_andato_perduto(self, tmp_path):
        """Senza questo l'agente cerca il difetto nel proprio codice."""
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        _comando(ledger, "python -m venv .venv", "host")
        _comando(ledger, "pip install x", "container", rc=1)
        stato = ledger.render_state_block()
        assert "ambienti virtuali" in stato
        assert "Non e' un tuo errore" in stato

    def test_un_run_che_non_cambia_casa_non_paga_niente(self, tmp_path):
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        _comando(ledger, "pytest", "host")
        _comando(ledger, "npm run build", "host")
        assert "cambiato casa" not in ledger.render_state_block()

    def test_ne_un_run_senza_comandi(self, tmp_path):
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        assert "cambiato casa" not in ledger.render_state_block()

    def test_tornare_dov_era_non_e_un_cambio(self, tmp_path):
        """Host, contenitore, host: alla fine si e' dove si era partiti, e
        cio' che c'era e' di nuovo li'."""
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        _comando(ledger, "a", "host")
        _comando(ledger, "b", "container")
        _comando(ledger, "c", "host")
        assert "cambiato casa" not in ledger.render_state_block()


class TestSenzaReteNonSiInstalla:
    @pytest.mark.parametrize("comando", [
        "pip install fastapi uvicorn",
        "npm ci",
        "cd backend && pip install -r requirements.txt",
        "apt-get install -y curl",
        "poetry install",
    ])
    def test_questi_hanno_bisogno_della_rete(self, comando):
        assert _installa_qualcosa(comando) is True

    @pytest.mark.parametrize("comando", [
        "npm run build",
        "pytest tests/",
        "node --test backend/index.test.js",
        # Nomina un installatore e non installa niente: bloccarlo sarebbe
        # rifiutare un comando che sarebbe riuscito.
        "echo pip install",
    ])
    def test_questi_no(self, comando):
        assert _installa_qualcosa(comando) is False

    def test_il_contenitore_senza_rete_lo_dice_prima_di_provare(self):
        esecutore = EsecutoreContenitore(immagine="python:3.12-slim", rete=False)
        esito = esecutore.esegui("pip install fastapi", cwd=".", timeout_s=30)
        assert esito.success is False
        assert "non ha rete" in esito.stderr

    def test_e_dice_cosa_si_puo_fare(self):
        """Un rifiuto senza alternativa lascia l'agente a ritentare identico."""
        esecutore = EsecutoreContenitore(immagine="python:3.12-slim", rete=False)
        esito = esecutore.esegui("pip install fastapi", cwd=".", timeout_s=30)
        assert "un'immagine che contenga" in esito.stderr
        assert "Ritentare identico" in esito.stderr

    def test_e_dice_che_non_e_colpa_del_codice(self):
        esecutore = EsecutoreContenitore(immagine="python:3.12-slim", rete=False)
        esito = esecutore.esegui("npm ci", cwd=".", timeout_s=30)
        assert "non e' un difetto di cio' che hai scritto" in esito.stderr

    def test_con_la_rete_accesa_non_si_blocca_niente(self):
        """Il guardiano deve sparire quando la ragione per cui esiste non c'e'."""
        esecutore = EsecutoreContenitore(immagine="python:3.12-slim", rete=True)
        argv = esecutore.argv("pip install fastapi", cwd=".")
        assert "--network" not in argv or "none" not in argv
