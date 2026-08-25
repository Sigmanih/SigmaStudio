# ==============================================================================
# tests/test_server_startup.py — Che l'avvio non si rompa in silenzio
#
# La sequenza di avvio e' stata a lungo dentro `if __name__ == "__main__"`, e un
# blocco __main__ ha una proprieta' scomoda: non viene mai importato, quindi non
# viene mai eseguito da nulla che non sia l'avvio vero. Nessun test lo tocca,
# nessun import lo valida.
#
# E' costato esattamente quel che si immagina. Rimuovendo la pipeline HTTP
# legacy da sigma_server.py e' sparito anche l'import di `ensure_venv`, che
# viaggiava nello stesso blocco. Tutta la suite restava verde, `import
# sigma_server` funzionava, e il difetto e' comparso al primo avvio reale:
#
#     NameError: name 'ensure_venv' is not defined
#
# Ora la sequenza sta in funzioni importabili, e questi test le controllano
# senza avviare niente: si guardano i nomi globali che ogni funzione userebbe e
# si verifica che esistano davvero.
# ==============================================================================
import builtins
import dis
import types
import unittest

import sigma_server


def _nomi_globali_mancanti(funzione) -> list:
    """I nomi che la funzione cercherebbe fra i globali e che non ci sono.

    Si guardano gli opcode invece di `co_names`, che mescola globali e
    attributi: `sys.argv` ci finirebbe come "argv" e sembrerebbe un nome
    mancante. LOAD_GLOBAL e' esattamente e solo la ricerca fra i globali del
    modulo, cioe' quella che solleva NameError quando fallisce.
    """
    globali = vars(sigma_server)
    incorporati = vars(builtins)
    mancanti = []
    for istruzione in dis.get_instructions(funzione):
        if istruzione.opname != "LOAD_GLOBAL":
            continue
        nome = istruzione.argval
        if nome in globali or nome in incorporati:
            continue
        mancanti.append(nome)
    return sorted(set(mancanti))


class TestSequenzaDiAvvio(unittest.TestCase):

    #: Le funzioni che compongono l'avvio. Nessuna viene eseguita qui.
    FUNZIONI = ("main", "prepare_environment", "serve", "_build_frontend_if_needed",
                "_needs_frontend_rebuild", "_write_build_stamp", "_init_manifesti",
                "_apply_hardware_env", "graceful_shutdown")

    def test_la_sequenza_e_fatta_di_funzioni_importabili(self):
        """Se torna dentro __main__, torna a non essere verificabile."""
        for nome in self.FUNZIONI:
            with self.subTest(funzione=nome):
                self.assertTrue(hasattr(sigma_server, nome),
                                f"sigma_server.{nome} non esiste piu'")
                self.assertIsInstance(getattr(sigma_server, nome), types.FunctionType)

    def test_nessuna_funzione_usa_un_nome_che_non_esiste(self):
        """Il test che avrebbe fermato il NameError su ensure_venv."""
        for nome in self.FUNZIONI:
            funzione = getattr(sigma_server, nome, None)
            if funzione is None:
                continue
            with self.subTest(funzione=nome):
                mancanti = _nomi_globali_mancanti(funzione)
                self.assertEqual(
                    mancanti, [],
                    f"sigma_server.{nome}() userebbe nomi inesistenti: {mancanti}. "
                    f"Manca un import?")

    def test_ensure_venv_e_raggiungibile(self):
        """Il nome preciso che si e' perso, con il suo contratto."""
        self.assertTrue(hasattr(sigma_server, "ensure_venv"))
        self.assertTrue(callable(sigma_server.ensure_venv))

    def test_check_non_serve(self):
        """`--check` prepara e si ferma: e' il modo di esercitare l'avvio."""
        import inspect

        sorgente = inspect.getsource(sigma_server.main)
        self.assertIn("--check", sorgente)
        self.assertIn("prepare_environment", sorgente)
        # serve() viene chiamata dopo il ramo di verifica, non prima.
        self.assertLess(sorgente.index("--check"), sorgente.index("serve()"))


class TestPipelineUnica(unittest.TestCase):

    def test_nessuna_seconda_classe_handler(self):
        """121 handler montati a mano su una classe mai istanziata, tenuti
        allineati a mano e divergenti: non deve tornare."""
        self.assertFalse(hasattr(sigma_server, "SigmaAPIHandler"))
        self.assertFalse(hasattr(sigma_server, "ThreadedHTTPServer"))

    def test_il_server_resta_un_avviatore(self):
        """sigma_server.py prepara l'ambiente e avvia: se ricomincia a montare
        handler, e' ricomparsa la seconda pipeline."""
        montaggi = [n for n in dir(sigma_server) if n.startswith("handle_")]
        self.assertEqual(montaggi, [],
                         f"handler tornati dentro sigma_server: {montaggi}")


if __name__ == "__main__":
    unittest.main()
