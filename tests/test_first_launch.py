# ==============================================================================
# tests/test_first_launch.py — Una copia appena clonata deve partire
#
# Il caso che ha motivato questo file: `git clone`, `sigma_studio.bat`, e un
# server che muore su `ModuleNotFoundError: No module named 'uvicorn'` dopo aver
# stampato tre avvisi su moduli diversi e un errore di build che nominava
# "vite". Quattro sintomi, una causa sola: lo script di avvio di Windows creava
# il virtualenv, lo attivava e lanciava subito il server, senza installare
# niente. La versione POSIX delegava al launcher e installava; quella Windows no,
# e la differenza non era scritta da nessuna parte.
#
# Qui si verifica il contratto, non l'implementazione: qualunque cosa facciano
# gli script, su ogni sistema operativo devono passare dallo stesso punto di
# installazione, e il server deve rifiutarsi di partire spiegando cosa manca.
# ==============================================================================
import io
import os
import re
import unittest

from core import paths

ROOT = str(paths.project_root())


def _executable_lines(script: str) -> str:
    """Lo script senza i commenti: `::` e `rem` non fanno niente a runtime."""
    righe = []
    for riga in script.splitlines():
        spoglia = riga.strip()
        if spoglia.startswith("::") or spoglia.lower().startswith("rem "):
            continue
        righe.append(riga)
    return "\n".join(righe)


def _read(name: str) -> str:
    with io.open(os.path.join(ROOT, name), "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


class TestLaunchersDelegate(unittest.TestCase):
    """Un solo posto dove sta la procedura di installazione."""

    def test_windows_launcher_delegates_to_the_installer(self):
        script = _read("sigma_studio.bat")
        self.assertIn("sigma_launcher.py", script)

    def test_windows_launcher_does_not_start_the_server_itself(self):
        script = _read("sigma_studio.bat")
        # `python sigma_server.py` senza passare dal launcher e' esattamente il
        # difetto: parte un server dentro un virtualenv vuoto.
        self.assertIsNone(
            re.search(r"^\s*[^:@\r\n]*python\s+sigma_server\.py", script,
                      re.MULTILINE | re.IGNORECASE),
            "sigma_studio.bat avvia il server senza installare le dipendenze",
        )

    def test_posix_launcher_delegates_to_the_same_installer(self):
        self.assertIn("sigma_launcher.py", _read("sigma_studio.sh"))

    def test_the_installer_script_does_not_keep_its_own_procedure(self):
        script = _read("install_dependencies.bat")
        self.assertIn("sigma_launcher.py --install", script)
        # requirements.txt e' lo stack completo: su una macchina senza NVIDIA
        # sono gigabyte di CUDA che non serviranno. Il launcher sceglie il file
        # giusto per l'acceleratore trovato.
        self.assertNotIn("pip install -r requirements.txt", script)

    def test_no_launcher_hardcodes_the_hardware(self):
        for name in ("sigma_studio.bat", "install_dependencies.bat"):
            # Solo le righe eseguite: nei commenti quei nomi compaiono per
            # spiegare perche' sono stati tolti.
            eseguite = _executable_lines(_read(name))
            # `CUDA_VISIBLE_DEVICES=0,1` su una macchina con una scheda sola, e
            # dodici thread su qualunque processore: il launcher li ricava
            # dall'hardware vero e da config.json.
            self.assertNotIn("CUDA_VISIBLE_DEVICES", eseguite, name)
            self.assertNotIn("OMP_NUM_THREADS", eseguite, name)

    def test_windows_launcher_prefers_the_official_python_launcher(self):
        # `python` su Windows puo' essere l'alias del Microsoft Store, che non
        # e' un interprete: apre il negozio e restituisce zero.
        self.assertIn("py -3", _read("sigma_studio.bat"))


class TestServerRefusesAnEmptyEnvironment(unittest.TestCase):
    """Il server non deve partire a meta' e morire dopo."""

    def _namespace(self):
        source = _read("sigma_server.py")
        start = source.index("_DIPENDENZE_ESSENZIALI")
        end = source.index("# --- Core modules ---")
        namespace = {"os": os}
        exec(source[start:end], namespace)
        return namespace

    def test_the_essential_modules_are_the_ones_that_failed(self):
        names = {m for m, _ in self._namespace()["_DIPENDENZE_ESSENZIALI"]}
        # Esattamente i quattro che si erano presentati uno alla volta.
        self.assertLessEqual({"uvicorn", "fastapi", "requests", "psutil"}, names)

    def test_the_message_says_what_to_run(self):
        namespace = self._namespace()
        message = namespace["_spiega_ambiente_incompleto"](
            [("uvicorn", "il server ASGI")])
        self.assertIn("uvicorn", message)
        self.assertIn("--install", message)
        # Il nome dello script cambia col sistema operativo: dire quello
        # sbagliato manda l'utente a cercare un file che non ha.
        atteso = "sigma_studio.bat" if os.name == "nt" else "./sigma_studio.sh"
        self.assertIn(atteso, message)

    def test_a_complete_environment_reports_nothing_missing(self):
        # Questo test gira dentro l'ambiente installato: se dice il contrario,
        # e' il controllo a essere rotto, non l'ambiente.
        self.assertEqual(self._namespace()["_dipendenze_mancanti"](), [])


class TestFrontendBuild(unittest.TestCase):
    """"vite non e' riconosciuto" nomina lo strumento, non la causa."""

    def test_dependencies_are_installed_before_the_build_runs(self):
        source = _read("sigma_server.py")
        build = source[source.index("def _build_frontend_if_needed"):]
        build = build[:build.index("def ", 10)]
        self.assertIn("node_modules", build)
        self.assertIn("install", build)
        # L'ordine conta: installare dopo aver fallito la build non aiuta.
        self.assertLess(build.index("node_modules"), build.index('"run", "build"'))

    def test_npm_is_found_under_its_windows_name_too(self):
        source = _read("sigma_server.py")
        self.assertIn("npm.cmd", source)


if __name__ == "__main__":
    unittest.main()
