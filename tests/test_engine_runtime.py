# ==============================================================================
# tests/test_engine_runtime.py — Istruzione illegale e impostazioni manuali
#
# Nasce da una segnalazione reale, al primo avvio dopo un download:
#
#     Causa: OSError: [WinError -1073741795] Windows Error 0xc000001d
#     Se e' un errore di memoria, riduci il contesto o forza una
#     quantizzazione piu' aggressiva dal Model Hub.
#
# 0xC000001D e' STATUS_ILLEGAL_INSTRUCTION: la ruota di llama-cpp-python era
# compilata con AVX2 e quella CPU non ce l'ha. Il consiglio dato all'utente era
# non solo inutile ma sviante, perche' nessuna quantita' di contesto in meno
# cambia le istruzioni che un processore supporta.
# ==============================================================================
import unittest

from core.engine.load_overrides import CAMPI, apply_to, clear, get_for, set_for
from core.engine.runtime_probe import (
    cpu_features,
    illegal_instruction_report,
    is_illegal_instruction,
)


class TestRiconoscimentoIstruzioneIllegale(unittest.TestCase):
    """Le tre forme in cui lo stesso guasto si presenta."""

    def test_da_winerror(self):
        errore = OSError("[WinError -1073741795] Windows Error 0xc000001d")
        errore.winerror = -1073741795
        self.assertTrue(is_illegal_instruction(exc=errore))

    def test_da_ntstatus_senza_segno(self):
        self.assertTrue(is_illegal_instruction(returncode=0xC000001D))

    def test_da_sigill_posix(self):
        """Su Linux e macOS il processo muore con SIGILL, cioe' -4."""
        self.assertTrue(is_illegal_instruction(returncode=-4))

    def test_dal_testo(self):
        for testo in ("Windows Error 0xc000001d", "Illegal instruction (core dumped)"):
            with self.subTest(testo=testo):
                self.assertTrue(is_illegal_instruction(testo=testo))

    def test_non_confonde_un_errore_di_memoria(self):
        """Il rischio opposto: chiamare 'CPU' quello che e' davvero memoria."""
        for testo in ("failed to allocate", "out of memory", "std::bad_alloc",
                      "unknown architecture 'qwen4'"):
            with self.subTest(testo=testo):
                self.assertFalse(is_illegal_instruction(testo=testo))
        self.assertFalse(is_illegal_instruction(exc=MemoryError("out of memory")))


class TestMessaggioAllUtente(unittest.TestCase):

    def test_dice_la_causa_vera_e_non_parla_di_memoria(self):
        testo = illegal_instruction_report()
        self.assertIn("istruzioni", testo.lower())
        self.assertIn("non e' un problema di memoria", testo.lower())

    def test_mostra_le_estensioni_della_cpu(self):
        """Senza sapere che cosa ha la CPU non si sceglie la build giusta."""
        cpu = {"modello": "Intel Core i5-2400", "arch": "amd64",
               "simd": ["SSE4.2", "SSE2"], "ha_avx2": False}
        testo = illegal_instruction_report(cpu)
        self.assertIn("Intel Core i5-2400", testo)
        self.assertIn("SSE4.2", testo)

    def test_da_un_comando_da_eseguire(self):
        testo = illegal_instruction_report({"modello": "x", "arch": "amd64", "simd": []})
        self.assertIn("GGML_AVX2=OFF", testo)
        self.assertIn("pip install", testo)

    def test_su_arm_il_rimedio_e_diverso(self):
        """Disattivare AVX2 su ARM non vuol dire niente."""
        testo = illegal_instruction_report({"modello": "Cortex-A76", "arch": "aarch64",
                                            "simd": ["ARM_NEON"]})
        self.assertNotIn("GGML_AVX2", testo)
        self.assertIn("--no-binary", testo)


class TestSondaCpu(unittest.TestCase):

    def test_riporta_qualcosa_di_sensato(self):
        cpu = cpu_features()
        self.assertTrue(cpu["modello"])
        self.assertIsInstance(cpu["simd"], list)
        self.assertEqual(cpu["ha_avx2"], "AVX2" in cpu["simd"])


class TestImpostazioniManuali(unittest.TestCase):
    """Il pianificatore decide, ma deve potersi scavalcare a mano."""

    def setUp(self):
        clear()

    def tearDown(self):
        clear()

    def test_un_valore_per_un_modello_solo(self):
        set_for("modello-a", {"n_gpu_layers": 0})
        self.assertEqual(get_for("modello-a"), {"n_gpu_layers": 0})
        self.assertEqual(get_for("modello-b"), {})

    def test_il_globale_vale_per_tutti_ma_il_modello_ha_la_precedenza(self):
        set_for(None, {"n_ctx": 4096})
        set_for("modello-a", {"n_ctx": 1024})
        self.assertEqual(get_for("modello-b")["n_ctx"], 4096)
        self.assertEqual(get_for("modello-a")["n_ctx"], 1024)

    def test_null_restituisce_la_scelta_al_pianificatore(self):
        set_for("modello-a", {"n_ctx": 1024})
        set_for("modello-a", {"n_ctx": None})
        self.assertEqual(get_for("modello-a"), {})

    def test_il_piano_viene_scavalcato_e_lo_dice(self):
        set_for("modello-a", {"n_gpu_layers": 0, "n_ctx": 2048})
        piano = {"n_gpu_layers": 28, "n_ctx": 8192, "n_batch": 512}
        nuovo = apply_to(dict(piano), "modello-a")

        self.assertEqual(nuovo["n_gpu_layers"], 0)
        self.assertEqual(nuovo["n_ctx"], 2048)
        # Cio' che non e' stato imposto resta come lo aveva calcolato il piano.
        self.assertEqual(nuovo["n_batch"], 512)
        # E resta scritto che quel numero non l'ha scelto il pianificatore.
        self.assertEqual(nuovo["overridden"]["n_gpu_layers"],
                         {"pianificato": 28, "imposto": 0})

    def test_senza_override_il_piano_non_viene_toccato(self):
        piano = {"n_gpu_layers": 28, "n_ctx": 8192}
        self.assertEqual(apply_to(dict(piano), "modello-a"), piano)

    def test_un_valore_non_valido_viene_rifiutato_spiegando(self):
        with self.assertRaises(ValueError) as ctx:
            set_for(None, {"n_ctx": "abc"})
        self.assertIn("intero", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            set_for(None, {"n_gpu_layers": -1})
        self.assertIn("minore", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            set_for(None, {"parametro_inventato": 1})
        self.assertIn("sconosciuto", str(ctx.exception))

    def test_ogni_campo_esposto_e_uno_che_il_backend_legge(self):
        """Un parametro che il piano non produce sarebbe un'impostazione finta.

        Le chiavi ammesse devono corrispondere a quelle che il pianificatore di
        llama.cpp mette nel dizionario delle impostazioni: dichiararne una in
        piu' darebbe all'utente una manopola scollegata.
        """
        from pathlib import Path

        from core.paths import project_root

        sorgente = (project_root() / "core" / "engine" / "backends"
                    / "llamacpp_backend.py").read_text(encoding="utf-8", errors="ignore")
        for nome in CAMPI:
            with self.subTest(campo=nome):
                self.assertIn(f'"{nome}"', sorgente,
                              f"'{nome}' non compare fra le impostazioni del backend")


def _solleva_da(percorso_finto: str, sorgente: str) -> BaseException:
    """L'eccezione sollevata da un frame che dichiara di stare in `percorso_finto`.

    `compile` accetta un nome di file arbitrario, quindi la prova puo' mettersi
    nei panni di un frame dentro transformers senza aspettare che quella
    libreria si rompa davvero: quale riga esplode cambia a ogni versione, il
    posto in cui esplode no.
    """
    codice = compile(sorgente, percorso_finto, "exec")
    try:
        exec(codice, {})
    except BaseException as exc:
        return exc
    raise AssertionError("il frammento non ha sollevato niente")


class TestDiagnosiDelCodiceDelCheckpoint(unittest.TestCase):
    """Un guasto nato nella libreria non e' un problema di memoria.

    Stessa origine della prova qui sopra, un giro di versioni dopo: un
    checkpoint con codice proprio, scritto per transformers 4.57.1, esplode
    dentro `site-packages/transformers` prima che i pesi entrino in gioco. Il
    messaggio che l'utente riceveva consigliava di ridurre il contesto.
    """

    @staticmethod
    def _percorso_in_transformers(nome_file: str) -> str:
        from pathlib import Path

        import transformers

        return str(Path(transformers.__file__).parent / nome_file)

    def test_un_errore_dentro_transformers_e_del_runtime(self):
        """La forma vera: AttributeError sollevato da `validate_rope`."""
        from core.engine.unified_runtime import _errore_nel_codice_del_runtime

        errore = _solleva_da(
            self._percorso_in_transformers("modeling_rope_utils.py"),
            "raise AttributeError(\"'float' object has no attribute 'get'\")",
        )
        self.assertTrue(_errore_nel_codice_del_runtime(errore))

    def test_un_errore_nel_codice_del_checkpoint_e_del_runtime(self):
        """Il `modeling_x.py` del checkpoint, importato dalla cache dei moduli."""
        from core.engine.unified_runtime import _errore_nel_codice_del_runtime

        errore = _solleva_da(
            "C:/utente/.cache/huggingface/modules/transformers_modules/"
            "XHToken--Spark-X2.5-4B/modeling_spark.py",
            "raise TypeError('create_causal_mask() got an unexpected keyword argument')",
        )
        self.assertTrue(_errore_nel_codice_del_runtime(errore))

    def test_un_errore_di_memoria_dentro_transformers_resta_di_memoria(self):
        """Il posto conta meno della causa: un OOM e' un OOM anche dentro la libreria."""
        from core.engine.unified_runtime import _errore_nel_codice_del_runtime

        for sorgente in (
            "raise MemoryError('CUDA out of memory. Tried to allocate 230.00 MiB')",
            "raise RuntimeError('CUDA out of memory. Tried to allocate 230.00 MiB')",
        ):
            with self.subTest(sorgente=sorgente):
                errore = _solleva_da(
                    self._percorso_in_transformers("modeling_utils.py"), sorgente
                )
                self.assertFalse(_errore_nel_codice_del_runtime(errore))

    def test_un_guasto_di_collocazione_resta_del_piano(self):
        """accelerate che non sa dove mettere i pesi non e' un guasto di codice."""
        from core.engine.unified_runtime import _errore_nel_codice_del_runtime

        errore = _solleva_da(__file__, "raise RuntimeError('nessun dispositivo con spazio')")
        self.assertFalse(_errore_nel_codice_del_runtime(errore))

    def test_il_messaggio_nomina_le_due_versioni_e_non_la_memoria(self):
        import json
        import tempfile
        from pathlib import Path

        from core.engine.unified_runtime import sigma_engine

        with tempfile.TemporaryDirectory() as cartella:
            Path(cartella, "config.json").write_text(
                json.dumps({"transformers_version": "4.57.1"}), encoding="utf-8"
            )
            messaggio = sigma_engine._format_load_failure(
                "XHToken--Spark-X2.5-4B",
                {
                    "stage": "runtime",
                    "origine": "codice_modello",
                    "error": "AttributeError: 'float' object has no attribute 'get'",
                    "facts": {"path": cartella},
                },
            )
        self.assertIn("Non e' un problema di memoria", messaggio)
        self.assertIn("4.57.1", messaggio)
        self.assertNotIn("riduci il contesto", messaggio)

    def test_un_guasto_di_collocazione_riceve_ancora_il_consiglio_sulla_memoria(self):
        from core.engine.unified_runtime import sigma_engine

        messaggio = sigma_engine._format_load_failure(
            "un-modello",
            {"stage": "load",
             "error": "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 230.00 MiB"},
        )
        self.assertIn("riduci il contesto", messaggio)

    def test_il_tentativo_di_caricamento_segna_da_dove_viene_il_guasto(self):
        """Il posto del frame decide lo stage, e il caricatore lo registra."""
        import types

        from core.engine.unified_runtime import sigma_engine

        percorso = self._percorso_in_transformers("modeling_utils.py")

        class ModelloCheEsplode:
            @staticmethod
            def from_pretrained(*_args, **_kwargs):
                # `_solleva_da` restituisce l'eccezione con la sua traccia: qui
                # va rilanciata, perche' e' il caricatore a doverla classificare.
                raise _solleva_da(percorso, "raise AttributeError('boom')")

        precedente = sigma_engine.last_load_origin
        modello, errore = sigma_engine._attempt_load(
            ModelloCheEsplode, "percorso-finto",
            types.SimpleNamespace(offload_folder=None, quantization="bf16"),
            "float32", False,
        )
        self.assertIsNone(modello)
        self.assertIn("AttributeError", errore)
        self.assertEqual(sigma_engine.last_load_origin, "codice_modello")
        sigma_engine.last_load_origin = precedente


if __name__ == "__main__":
    unittest.main()
