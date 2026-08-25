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


if __name__ == "__main__":
    unittest.main()
