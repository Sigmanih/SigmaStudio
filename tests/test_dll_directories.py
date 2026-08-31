r"""Gli handle di directory DLL sono una risorsa finita, e si esaurivano.

Windows ne concede a un processo poche centinaia. `os.add_dll_directory` non
riusa quello di una directory gia' registrata: due chiamate sullo stesso
percorso consumano due handle. La telemetria GPU ne registrava una per ogni
voce del PATH -- una cinquantina -- a ogni poll del frontend, quindi il server
li esauriva dopo un'ottantina di poll.

Il sintomo non nominava nulla di tutto questo. La prima registrazione a cadere
era quella che llama_cpp esegue quando la quantizzazione lo importa:

    FileNotFoundError: [WinError 206] Nome del file o estensione troppo lunga:
    '...\site-packages\llama_cpp\lib'

Un percorso di 70 caratteri descritto come troppo lungo. La quantizzazione
funzionava a server appena avviato e falliva dopo qualche minuto, a parita' di
modello e di comando: la variabile vera era l'uptime.
"""

import os
import unittest

from core.engine import llama_runtime


class TestRegistrazioneIdempotente(unittest.TestCase):
    """Chiamarla mille volte deve costare quanto chiamarla una."""

    def setUp(self):
        self._salvato = dict(llama_runtime._dll_dirs_registrate)

    def tearDown(self):
        llama_runtime._dll_dirs_registrate.clear()
        llama_runtime._dll_dirs_registrate.update(self._salvato)

    def test_le_chiamate_ripetute_non_consumano_handle(self):
        """E' la proprieta' che impediva al server di degradare con l'uptime."""
        llama_runtime.setup_dll_directories()
        dopo_la_prima = len(llama_runtime._dll_dirs_registrate)

        for _ in range(500):
            llama_runtime.setup_dll_directories()

        self.assertEqual(len(llama_runtime._dll_dirs_registrate), dopo_la_prima)

    def test_una_directory_rifiutata_non_viene_ritentata(self):
        """Senza memoria del rifiuto, ogni poll ripaga il costo dell'errore."""
        if os.name != "nt":
            self.skipTest("registrazione DLL solo su Windows")

        tentativi = []
        vero = os.add_dll_directory

        def conta(p):
            tentativi.append(p)
            raise OSError(206, "troppo lunga")

        llama_runtime._dll_dirs_registrate.clear()
        os.add_dll_directory = conta
        try:
            llama_runtime.setup_dll_directories()
            primo_giro = len(tentativi)
            llama_runtime.setup_dll_directories()
            self.assertEqual(len(tentativi), primo_giro)
        finally:
            os.add_dll_directory = vero

    def test_un_errore_di_registrazione_non_interrompe_le_altre(self):
        """Una directory rotta non deve far perdere quelle valide che seguono."""
        if os.name != "nt":
            self.skipTest("registrazione DLL solo su Windows")
        llama_runtime._dll_dirs_registrate.clear()
        llama_runtime.setup_dll_directories()
        valide = [k for k, v in llama_runtime._dll_dirs_registrate.items()
                  if v is not None]
        self.assertGreater(len(valide), 0)


if __name__ == "__main__":
    unittest.main()
