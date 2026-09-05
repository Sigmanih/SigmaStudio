"""Cosa fare quando l'agente si inceppa, distinguendo tre stalli diversi.

Questi test nascono da un run reale, osservato dall'inizio alla fine. L'agente
doveva aggiungere una route al modulo di rete. Non ha guardato un solo file:
ha chiamato `edit_file` su un percorso inventato, il sistema l'ha giustamente
rifiutato («non hai ancora letto questo file»), e quel rifiuto e' stato contato
come turno improduttivo. Tre rifiuti e il recupero e' scattato — dicendogli
«STOP ESPLORAZIONE, hai gia' raccolto le informazioni che ti servono, scrivi il
file», mentre di informazioni non ne aveva raccolta nessuna.

Il risultato e' stato un Blueprint Flask dentro un progetto FastAPI, in un file
che non era mai esistito. Il recupero non ha corretto lo stallo: lo ha
consacrato.

Corretto quello, il run successivo ha esposto lo stallo simmetrico: l'agente
ha elencato la cartella, il sistema ha rifiutato il secondo elenco identico
(«nulla e' cambiato»), il recupero l'ha spinto a esplorare — cioe' a rielencare
— e cosi' per trenta turni. Spingere a esplorare chi sta gia' esplorando e'
sbagliato quanto spingere a scrivere chi non ha ancora guardato.

Da qui gli stadi: chi non ha visto nulla esplora, chi ha elencato senza aprire
niente legge, chi ha letto agisce. Piu' due correzioni minori emerse dagli
stessi run: un rifiuto che dice quale sia il passo mancante non e' uno stallo,
e l'output di un comando non deve spendere contesto in codici di colore.
"""

import pytest

from core.harness.ledger import DevSessionLedger
from core.harness.loop import (
    EXPLORATION_RECOVERY_TOOLS,
    READING_RECOVERY_TOOLS,
    RECOVERY_TOOLS,
    _recovery_directive,
    recovery_stage,
    recovery_tools,
    strip_ansi,
)

WS = "C:/progetto"


def _ledger_vergine():
    return DevSessionLedger(goal="Aggiungi una route al modulo di rete", workspace_root=WS)


def _ledger_che_ha_letto():
    led = _ledger_vergine()
    led.record_tool(
        "read_file", {"path": f"{WS}/core/handlers.py"},
        {"success": True, "path": f"{WS}/core/handlers.py", "offset": 1,
         "last_line": 40, "total_lines": 40, "content": "def esiste(): pass"},
    )
    return led


def _ledger_che_ha_elencato():
    led = _ledger_vergine()
    led.record_tool("list_dir", {"path": "core/modules/sigma_network_lab"},
                    {"success": True, "entries": ["handlers.py", "manifest.json"]})
    return led


class TestRiconoscimentoDelloStallo:
    """Tre stalli che si assomigliano e vogliono cure opposte."""

    def test_chi_non_ha_guardato_nulla_deve_esplorare(self):
        assert recovery_stage(_ledger_vergine()) == "explore"

    def test_chi_ha_elencato_ma_non_letto_deve_leggere(self):
        """Il secondo ciclo osservato: elenca, viene rifiutato, rielenca."""
        assert recovery_stage(_ledger_che_ha_elencato()) == "read"

    def test_chi_ha_letto_deve_agire(self):
        assert recovery_stage(_ledger_che_ha_letto()) == "act"

    def test_una_ricerca_vale_come_aver_guardato(self):
        led = _ledger_vergine()
        led.record_tool(
            "search_code", {"query": "fetch_page"},
            {"success": True, "query": "fetch_page", "results": [], "scanned_files": 12},
        )
        assert recovery_stage(led) == "read"

    def test_senza_ledger_non_si_pretende_nulla(self):
        assert recovery_stage(None) == "act"

    def test_un_ledger_rotto_non_fa_saltare_il_ciclo(self):
        class Rotto:
            def has_reads(self):
                raise RuntimeError("stato illeggibile")
        assert recovery_stage(Rotto()) == "act"

    def test_ogni_stadio_ha_i_suoi_tool(self):
        assert recovery_tools(_ledger_vergine()) == EXPLORATION_RECOVERY_TOOLS
        assert recovery_tools(_ledger_che_ha_elencato()) == READING_RECOVERY_TOOLS
        assert recovery_tools(_ledger_che_ha_letto()) == RECOVERY_TOOLS

    def test_lo_stadio_di_lettura_non_permette_di_rielencare(self):
        """La correzione del ciclo: se puo' solo leggere, smette di elencare."""
        ammessi = set(recovery_tools(_ledger_che_ha_elencato()))
        assert "list_dir" not in ammessi and "glob" not in ammessi


class TestDirettivaDiRecupero:
    def test_a_chi_non_ha_esplorato_si_chiede_di_esplorare(self):
        """Il difetto originale: gli si diceva di scrivere, e inventava."""
        direttiva = _recovery_directive(_ledger_vergine())
        assert "list_dir" in direttiva
        assert "STOP ESPLORAZIONE" not in direttiva
        assert "write_file" not in direttiva

    def test_la_direttiva_cita_i_percorsi_dell_obiettivo(self):
        led = DevSessionLedger(
            goal="Aggiungi una route in core/modules/sigma_network_lab/handlers.py",
            workspace_root=WS,
        )
        direttiva = _recovery_directive(led)
        assert "core/modules/sigma_network_lab/handlers.py" in direttiva

    def test_senza_percorsi_si_parte_dalla_radice(self):
        direttiva = _recovery_directive(_ledger_vergine())
        assert 'list_dir' in direttiva and '"."' in direttiva

    def test_a_chi_ha_elencato_si_chiede_di_leggere(self):
        direttiva = _recovery_directive(_ledger_che_ha_elencato())
        assert "BASTA ELENCARE" in direttiva
        assert "read_file" in direttiva
        assert "core/modules/sigma_network_lab" in direttiva

    def test_a_chi_ha_gia_letto_si_chiede_di_agire(self):
        direttiva = _recovery_directive(_ledger_che_ha_letto())
        assert "STOP ESPLORAZIONE" in direttiva
        assert "write_file" in direttiva

    def test_un_errore_di_verifica_ha_la_precedenza(self):
        """Se un test ha gia' detto cosa correggere, si corregge quello."""
        led = _ledger_che_ha_letto()
        led.record_tool(
            "terminal", {"command": "python -m pytest"},
            {"success": True, "returncode": 1, "command": "python -m pytest",
             "stderr": "ImportError: cannot import name 'fetch_page'"},
        )
        direttiva = _recovery_directive(led)
        assert "pytest" in direttiva


class TestInsiemiDiRecupero:
    def test_gli_insiemi_servono_a_cose_diverse(self):
        assert set(EXPLORATION_RECOVERY_TOOLS) & {"write_file", "edit_file"} == set()
        assert set(READING_RECOVERY_TOOLS) == {"read_file"}
        assert set(RECOVERY_TOOLS) >= {"write_file", "edit_file"}

    def test_l_insieme_di_esplorazione_permette_di_guardare(self):
        assert {"list_dir", "glob", "search_code"} <= set(EXPLORATION_RECOVERY_TOOLS)


class TestOutputDelTerminale:
    def test_i_codici_di_colore_spariscono(self):
        grezzo = "\x1b[1m=== test session starts ===\x1b[0m\n\x1b[31mFAILED\x1b[0m"
        assert strip_ansi(grezzo) == "=== test session starts ===\nFAILED"

    def test_il_messaggio_d_errore_resta_intatto(self):
        """E' l'unica parte che serve davvero: non deve perdersi nella pulizia."""
        grezzo = "\x1b[31mE   ImportError: cannot import name 'url_quote'\x1b[0m"
        pulito = strip_ansi(grezzo)
        assert "ImportError: cannot import name 'url_quote'" in pulito
        assert "\x1b" not in pulito

    def test_un_testo_senza_colori_non_viene_toccato(self):
        assert strip_ansi("2 passed in 0.15s") == "2 passed in 0.15s"

    def test_regge_valori_vuoti(self):
        assert strip_ansi("") == ""
        assert strip_ansi(None) == ""


class TestModelloPredefinito:
    """La configurazione vince sull'euristica del nome file."""

    def test_la_chat_libera_eredita_il_binding_del_coder(self, monkeypatch):
        from dataclasses import replace
        import core.harness.role_registry as registry
        from core.harness.roles import DEV_ROLES

        monkeypatch.setattr(
            registry, "load_roles",
            lambda force=False: {"coder": replace(DEV_ROLES["coder"], model="modello-scelto")},
        )
        registry.invalidate()
        assert registry.get_role("coder").model == "modello-scelto"

    def test_gli_alias_generici_sono_quelli_attesi(self):
        """Se questo insieme diverge, il binding smette di applicarsi in silenzio."""
        from core.harness.roles import GENERIC_MODEL_ALIASES
        assert {"", "sigmaengine", "auto", "default", "native"} <= GENERIC_MODEL_ALIASES


class TestDeadlockDelRecupero:
    """Il ciclo che ha bloccato il terzo run, e le quattro cose che lo creavano.

    L'agente aveva elencato la cartella, poi chiamato `read_file` sulla
    cartella stessa. Quel risultato veniva registrato come lettura di un file,
    lo stadio saltava ad "agisci", la grammatica gli vietava `read_file` e gli
    imponeva di scrivere — ma ogni scrittura veniva rifiutata perche' il file
    vero non l'aveva mai letto. Ventitre `edit_file` identici di fila, tutti
    respinti, fino a esaurire i turni.
    """

    def test_leggere_una_cartella_non_e_leggere_un_file(self):
        led = _ledger_vergine()
        led.record_tool(
            "read_file", {"path": "core/modules/x"},
            {"success": True, "path": f"{WS}/core/modules/x",
             "message": "'core/modules/x' e una cartella con 4 elementi.",
             "content": "'core/modules/x' e una cartella contenente:\nhandlers.py"},
        )
        assert led.has_reads() is False
        assert led.has_listings() is True
        assert recovery_stage(led) == "read"

    def test_il_recupero_lascia_sempre_una_via_di_lettura(self):
        """Vietare `read_file` a chi viene rifiutato per non aver letto e' un vicolo cieco."""
        assert "read_file" in RECOVERY_TOOLS

    def test_leggere_un_file_vero_porta_allo_stadio_di_azione(self):
        led = _ledger_vergine()
        led.record_tool(
            "read_file", {"path": "core/x.py"},
            {"success": True, "path": f"{WS}/core/x.py", "offset": 1,
             "last_line": 20, "total_lines": 20, "content": "def f(): pass"},
        )
        assert recovery_stage(led) == "act"


class TestProduttivitaDelTurno:
    """Quali turni contano come progresso.

    Contare solo scritture e comandi faceva scattare il recupero al terzo
    turno di ogni run: `spec` e `pipeline` sono passi obbligatori del ciclo di
    lavoro ed esplorare e' cio' che si deve fare prima di scrivere, eppure
    tutti e tre venivano contati contro l'agente.
    """

    def test_i_passi_obbligatori_non_sono_scritture(self):
        """Il fatto da cui nasceva il difetto, reso esplicito."""
        from core.harness.loop import PRODUCTIVE_TOOLS
        assert "spec" not in PRODUCTIVE_TOOLS
        assert "pipeline" not in PRODUCTIVE_TOOLS
        assert "list_dir" not in PRODUCTIVE_TOOLS
        assert "read_file" not in PRODUCTIVE_TOOLS

    def test_le_scritture_e_i_comandi_restano_produttivi(self):
        """PRODUCTIVE_TOOLS serve ancora, ma solo a decidere quando forzare l'azione."""
        from core.harness.loop import PRODUCTIVE_TOOLS
        assert {"write_file", "edit_file", "terminal"} <= set(PRODUCTIVE_TOOLS)


class TestCosaContaComeVerifica:
    """Un comando che scrive non e' una verifica, per quanti indizi contenga.

    Quando una tool call viene troncata, l'agente ripiega su
    `python -c "import pathlib; ...write_text(...)"` per creare il file. Quel
    comando contiene `import `, quindi passava per una verifica: se falliva,
    il cancello di completamento restava chiuso per sempre. Su un run reale ha
    bruciato dieci turni a inseguire una verifica che non era mai stata tale.
    """

    def test_un_test_e_una_verifica(self):
        from core.harness.ledger import looks_like_verification
        for cmd in ("python -m pytest tests/ -q",
                    "npm run build",
                    "python -c \"import core.harness.loop\"",
                    "ruff check core/"):
            assert looks_like_verification(cmd) is True, cmd

    def test_una_scrittura_non_lo_e(self):
        from core.harness.ledger import looks_like_verification
        for cmd in ("python -c \"import pathlib; pathlib.Path('x.py').write_text('a')\"",
                    "echo ciao > file.txt",
                    "python -c \"import shutil; shutil.copy('a','b')\"",
                    "Set-Content -Path x.py -Value 'a'"):
            assert looks_like_verification(cmd) is False, cmd

    def test_una_verifica_fallita_che_era_una_scrittura_non_blocca(self):
        """Il difetto in una riga: il cancello restava chiuso per sempre."""
        from core.harness.ledger import check_completion_allowed
        led = _ledger_vergine()
        led.record_tool(
            "write_file", {"path": f"{WS}/core/x.py"},
            {"success": True, "path": f"{WS}/core/x.py", "lines_after": 10},
        )
        scrittura = "python -c \"import pathlib; pathlib.Path('t.py').write_text('x')\""
        led.record_tool("terminal", {"command": scrittura},
                        {"success": True, "returncode": 1, "command": scrittura,
                         "stderr": "SyntaxError"})
        led.record_tool("terminal", {"command": "python -m pytest -q"},
                        {"success": True, "returncode": 0, "command": "python -m pytest -q"})
        assert check_completion_allowed(led)["allowed"] is True
