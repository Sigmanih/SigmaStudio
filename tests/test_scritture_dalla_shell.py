"""Un file scritto dalla shell non deve restare invisibile.

Il 23 settembre un agente ha estratto dieci metodi di `core/engine/gguf_converter.py`
in `tools/*_src.txt` con comandi cosi:

    python -c "import inspect; ...; print(inspect.getsource(G._run))" > tools/run_src.txt

Dieci file in sei minuti, tutti in UTF-16 (la firma del redirect di PowerShell),
tutti illeggibili al suo stesso lettore, e **nessuno** comparso nel ledger: le
scritture che passano dalla shell non entrano nel registro, quindi il cancello di
completamento non le vede e l agente non puo dimostrare di averle fatte. Il file
intanto sta su disco, senza backup, senza controllo di sintassi e senza diff.

Il guard conosceva `echo > file`, `Set-Content` e `Out-File`, ma non la
redirezione generica da qualunque comando: ed e li che passavano quei dieci.

Qui si verifica che la redirezione venga riconosciuta, che un file scritto dentro
l albero venga rifiutato (e non finisca su disco), che `var/` resti la zona di
servizio, e che i comandi legittimi continuino a passare.
"""

from core.harness.loop import (
    authors_a_file_inline,
    execute_admin_tool,
    percorsi_scritti_dal_comando,
    scrittura_consentita,
)


class TestLaRedirezioneSiRiconosce:
    def test_il_comando_dei_dieci_estratti(self):
        comando = ("python -c " + chr(34) + "import inspect; print(inspect.getsource(G._run))"
                   + chr(34) + " > tools/run_src.txt")
        assert authors_a_file_inline(comando) is True
        assert percorsi_scritti_dal_comando(comando) == ["tools/run_src.txt"]

    def test_una_redirezione_in_coda_a_una_verifica(self):
        assert authors_a_file_inline("python -m pytest tests/ -q > esito.txt") is True

    def test_scrivere_nel_null_non_e_scrivere(self):
        assert authors_a_file_inline("python -m pytest tests/ -q > $null") is False
        assert authors_a_file_inline("python -m pytest tests/ -q > NUL") is False

    def test_le_redirezioni_di_descrittore_non_contano(self):
        assert authors_a_file_inline("python -m pytest tests/ -q 2>&1 | Select-Object -Last 3") is False

    def test_i_comandi_legittimi_passano(self):
        for comando in ("npm run build", "git status", "python -m py_compile core/x.py",
                        "python -c " + chr(34) + "import core.harness.loop" + chr(34),
                        "ruff check core/", "cargo check --workspace"):
            assert authors_a_file_inline(comando) is False, comando

    def test_i_percorsi_si_prendono_dove_si_vedono(self):
        assert percorsi_scritti_dal_comando('Set-Content -Path prove.txt -Value 1') == ["prove.txt"]
        assert percorsi_scritti_dal_comando("Out-File -FilePath out.log") == ["out.log"]


class TestLaZonaFranca:
    def test_dentro_l_albero_non_si_scrive(self):
        assert scrittura_consentita("tools/x.txt", "C:/progetto") is False
        assert scrittura_consentita("core/modulo.py", "C:/progetto") is False

    def test_var_e_la_zona_di_servizio(self):
        assert scrittura_consentita("var/scratch/x.txt", "C:/progetto") is True
        assert scrittura_consentita("./var/prova.txt", "C:/progetto") is True

    def test_fuori_e_in_cartella_temporanea_si_puo(self):
        assert scrittura_consentita("$env:TEMP/x.txt", "C:/progetto") is True
        assert scrittura_consentita("C:/altrove/x.txt", "C:/progetto") is True
        assert scrittura_consentita("C:/progetto/core/x.py", "C:/progetto") is False


class TestIlGuardBloccaDavvero:
    def test_il_file_non_finisce_su_disco(self, tmp_path):
        comando = ("python -c " + chr(34) + "print(1)" + chr(34) + " > prova.txt")
        esito = execute_admin_tool("terminal", {"command": comando},
                                   workspace_root=str(tmp_path),
                                   active_cwd=str(tmp_path))
        assert esito["success"] is False, esito
        assert "write_file" in esito["error"]
        assert not (tmp_path / "prova.txt").exists(), "il file e finito su disco lo stesso"

    def test_un_file_in_var_invece_si_scrive(self, tmp_path):
        (tmp_path / "var").mkdir()
        comando = ("python -c " + chr(34) + "print(1)" + chr(34) + " > var/prova.txt")
        esito = execute_admin_tool("terminal", {"command": comando},
                                   workspace_root=str(tmp_path),
                                   active_cwd=str(tmp_path))
        assert esito["success"] is True, esito
        assert (tmp_path / "var" / "prova.txt").exists()

