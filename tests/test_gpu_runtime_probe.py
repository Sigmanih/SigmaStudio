"""Il driver CUDA non dice che la build CUDA partira'.

`nvcuda.dll` arriva col driver grafico: c'e' su ogni macchina con una scheda
NVIDIA. Ma `ggml-cuda.dll` si lega a `cudart64_*.dll`, che arriva col CUDA
Toolkit o dentro torch e che moltissime installazioni non hanno. Leggere il
primo come prova del secondo fa scaricare una build che poi non apre le proprie
librerie: il primo avvio fallisce su un clone fresco, e l'errore non nomina cio'
che manca.

Escluderlo fa scegliere Vulkan, che con quel driver e' gia' installato.
"""

import platform
import unittest
from unittest import mock

from core.engine import gpu_vendors


class TestRuntimeCudaDistintoDalDriver(unittest.TestCase):

    def setUp(self):
        gpu_vendors.reset_cache()

    def tearDown(self):
        gpu_vendors.reset_cache()

    @staticmethod
    def _sonda(apribili):
        """Finge un sistema in cui si aprono solo le librerie elencate."""
        def _apre(nomi):
            return any(n in apribili for n in nomi)
        return _apre

    def test_driver_senza_runtime_esclude_cuda(self):
        """E' il caso del PC senza Toolkit: la build CUDA non partirebbe."""
        with mock.patch.object(gpu_vendors, "_libreria_apribile",
                               self._sonda({"nvcuda.dll", "vulkan-1.dll"})), \
             mock.patch.object(gpu_vendors.platform, "system", lambda: "Windows"):
            esiti = gpu_vendors.available_runtimes()
        self.assertFalse(esiti["cuda"])
        self.assertTrue(esiti["vulkan"])

    def test_driver_con_runtime_mantiene_cuda(self):
        with mock.patch.object(gpu_vendors, "_libreria_apribile",
                               self._sonda({"nvcuda.dll", "cudart64_12.dll"})), \
             mock.patch.object(gpu_vendors.platform, "system", lambda: "Windows"):
            esiti = gpu_vendors.available_runtimes()
        self.assertTrue(esiti["cuda"])

    def test_senza_runtime_la_scelta_cade_su_vulkan(self):
        """La proprieta' che conta: si sceglie qualcosa che parte davvero."""
        with mock.patch.object(gpu_vendors, "_libreria_apribile",
                               self._sonda({"nvcuda.dll", "vulkan-1.dll"})), \
             mock.patch.object(gpu_vendors.platform, "system", lambda: "Windows"), \
             mock.patch.object(gpu_vendors, "gpu_vendors", lambda: ["nvidia"]):
            self.assertEqual(gpu_vendors.preferred_compute(), "vulkan")


class TestMisuraUnaVoltaSola(unittest.TestCase):
    """describe() chiamava la coppia di sonde due volte di fila.

    Su Windows ogni `gpu_vendors()` lancia PowerShell con timeout di venti
    secondi. Le schede installate non cambiano mentre il processo gira.
    """

    def setUp(self):
        gpu_vendors.reset_cache()

    def tearDown(self):
        gpu_vendors.reset_cache()

    def test_la_seconda_chiamata_non_risonda(self):
        giri = []

        def _conta(nomi):
            giri.append(nomi)
            return False

        with mock.patch.object(gpu_vendors, "_libreria_apribile", _conta):
            gpu_vendors.available_runtimes()
            dopo_la_prima = len(giri)
            gpu_vendors.available_runtimes()
            self.assertEqual(len(giri), dopo_la_prima)

    def test_reset_cache_rifa_la_misura(self):
        giri = []
        with mock.patch.object(gpu_vendors, "_libreria_apribile",
                               lambda nomi: giri.append(nomi) or False):
            gpu_vendors.available_runtimes()
            dopo_la_prima = len(giri)
            gpu_vendors.reset_cache()
            gpu_vendors.available_runtimes()
            self.assertGreater(len(giri), dopo_la_prima)

    def test_il_chiamante_non_puo_alterare_la_misura_per_tutti(self):
        primo = gpu_vendors.available_runtimes()
        primo["cuda"] = not primo["cuda"]
        self.assertNotEqual(primo["cuda"], gpu_vendors.available_runtimes()["cuda"])

    def test_le_schede_si_enumerano_una_volta_sola(self):
        if platform.system() != "Windows":
            self.skipTest("l'enumerazione costosa e' quella di Windows")
        giri = []
        with mock.patch.object(gpu_vendors, "_vendor_windows",
                               lambda: giri.append(1) or ["nvidia"]):
            gpu_vendors.gpu_vendors()
            gpu_vendors.gpu_vendors()
        self.assertEqual(len(giri), 1)


if __name__ == "__main__":
    unittest.main()
