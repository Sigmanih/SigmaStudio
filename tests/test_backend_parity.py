# ==============================================================================
# tests/test_backend_parity.py — I due backend devono restare la stessa cosa
#
# Sigma Studio esegue i GGUF in due modi: con il binario ufficiale di llama.cpp
# in un processo separato, e con la ruota llama-cpp-python in processo. E' lo
# stesso motore procurato in due modi, e va tenuto vero.
#
# Questa sessione ha rimosso cinque duplicazioni che erano tutte divergute in
# silenzio — due pipeline HTTP, cinque copie del writer SSE, tre dei manifesti,
# cinque sonde hardware, i requisiti dei moduli — e ognuna e' costata un difetto
# vero. Due backend sono una duplicazione accettabile solo finche' qualcosa
# verifica che facciano la stessa cosa. Questo file e' quel qualcosa.
#
# La verifica piu' importante e' l'ultima: ogni flag che traduciamo deve esistere
# davvero nel binario. Un flag rinominato a monte non da' un errore di Python,
# da' un llama-server che rifiuta di partire sulla macchina di qualcun altro.
# ==============================================================================
import subprocess
import unittest

from core.engine import gguf_planner
from core.engine.backends.llamacpp_backend import LlamaCppBackend
from core.engine.backends.llamaserver_backend import LlamaServerBackend, plan_to_args
from core.engine.backends.registry import all_backends
from core.engine.llama_runtime import installed_server


class TestStessoContratto(unittest.TestCase):

    def test_leggono_gli_stessi_formati(self):
        self.assertEqual(set(LlamaCppBackend.supported_formats),
                         set(LlamaServerBackend.supported_formats))

    def test_entrambi_sono_registrati(self):
        nomi = {b.name for b in all_backends()}
        self.assertIn("llama_cpp", nomi)
        self.assertIn("llama_server", nomi)

    def test_il_processo_separato_e_preferito(self):
        """A parita' di motore vince quello che non si porta via il server.

        Un'istruzione illegale, un OOM del driver o un bug del kernel uccidono
        il processo del modello invece dell'applicazione, e il percorso in
        processo serializza le generazioni su un lock mentre il server ne serve
        piu' d'una sullo stesso modello caricato una volta.
        """
        self.assertGreater(LlamaServerBackend.score(None, {}),
                           LlamaCppBackend.score(None, {"accelerators": []}))

    def test_nessuno_dei_due_inventa_un_piano(self):
        """La matematica sta in gguf_planner: due copie divergono sempre."""
        import inspect

        for backend in (LlamaCppBackend, LlamaServerBackend):
            with self.subTest(backend=backend.name):
                sorgente = inspect.getsource(backend)
                self.assertIn("gguf_planner", sorgente,
                              f"{backend.name} non usa il pianificatore condiviso")


class TestTraduzioneDelPiano(unittest.TestCase):
    """Il piano e' uno; ogni backend lo rende nella propria forma."""

    PIANO = {
        "n_gpu_layers": 28, "n_ctx": 8192, "n_batch": 512,
        "n_threads": 12, "n_threads_batch": 24, "flash_attn": True,
        "kv_quant": "q8_0", "tensor_split": [0.7, 0.3],
        "use_mmap": False, "use_mlock": True,
    }

    def test_ogni_decisione_del_piano_arriva_alla_riga_di_comando(self):
        argomenti = plan_to_args(self.PIANO)
        testo = " ".join(argomenti)
        for flag, atteso in (("-ngl", "28"), ("-c", "8192"), ("-b", "512"),
                             ("-t", "12"), ("-tb", "24"), ("-ctk", "q8_0"),
                             ("-ctv", "q8_0")):
            with self.subTest(flag=flag):
                self.assertIn(f"{flag} {atteso}", testo)
        self.assertIn("-fa on", testo)
        self.assertIn("-ts 0.7,0.3", testo)
        self.assertIn("--no-mmap", testo)
        self.assertIn("--mlock", testo)

    def test_flash_attention_disattivata_si_dice_esplicitamente(self):
        """Il binario vuole on/off/auto: un booleano Python non basta."""
        self.assertIn("-fa off", " ".join(plan_to_args({"flash_attn": False})))

    def test_una_cache_f16_non_passa_flag_di_quantizzazione(self):
        self.assertNotIn("-ctk", " ".join(plan_to_args({"kv_quant": "f16"})))

    def test_un_piano_vuoto_non_produce_argomenti(self):
        """Cio' che il piano non decide lo decide llama.cpp con i suoi default."""
        self.assertEqual(plan_to_args({}), [])

    def test_nessuna_chiave_del_piano_viene_persa_in_silenzio(self):
        """Se il pianificatore impara a decidere qualcosa, va tradotto.

        La lista e' quella dei parametri di caricamento: le altre chiavi che il
        piano porta sono diagnostiche (previsioni, avvisi, note) e non
        descrivono come avviare il modello.
        """
        import inspect

        traduttore = inspect.getsource(plan_to_args)
        parametri_di_caricamento = {
            "n_gpu_layers", "n_ctx", "n_batch", "n_threads", "n_threads_batch",
            "flash_attn", "kv_quant", "tensor_split", "use_mmap", "use_mlock",
        }
        for chiave in parametri_di_caricamento:
            with self.subTest(chiave=chiave):
                self.assertIn(f'"{chiave}"', traduttore,
                              f"'{chiave}' non viene tradotto in un argomento")


class TestFlagRealmenteEsistenti(unittest.TestCase):
    """Ogni flag che emettiamo deve esistere nel binario installato.

    E' la verifica che non si puo' fare a mente: llama.cpp rinomina e deprecara
    argomenti, e un flag sbagliato non da' un errore di Python — da' un
    llama-server che rifiuta di partire sulla macchina di qualcun altro.
    """

    @classmethod
    def setUpClass(cls):
        server = installed_server()
        if server is None:
            raise unittest.SkipTest("runtime GGUF non installato su questa macchina")
        esito = subprocess.run([str(server), "--help"], capture_output=True,
                               text=True, timeout=60, encoding="utf-8", errors="replace")
        cls.aiuto = (esito.stdout or "") + (esito.stderr or "")

    def test_i_flag_tradotti_esistono(self):
        piano = {
            "n_gpu_layers": 1, "n_ctx": 1, "n_batch": 1, "n_threads": 1,
            "n_threads_batch": 1, "flash_attn": True, "kv_quant": "q8_0",
            "tensor_split": [1.0], "use_mmap": False, "use_mlock": True,
        }
        for argomento in plan_to_args(piano):
            if not argomento.startswith("-"):
                continue
            with self.subTest(flag=argomento):
                self.assertIn(argomento, self.aiuto,
                              f"'{argomento}' non compare fra gli argomenti del binario")

    def test_gli_argomenti_fissi_esistono(self):
        """Quelli che il backend passa sempre, non solo quelli del piano."""
        for argomento in ("--host", "--port", "--jinja", "-np", "-cb", "-m"):
            with self.subTest(flag=argomento):
                self.assertIn(argomento, self.aiuto)


if __name__ == "__main__":
    unittest.main()
