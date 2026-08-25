# ==============================================================================
# tests/test_llama_runtime.py — L'archivio giusto per ogni macchina
#
# Sbagliare qui non produce un errore leggibile: produce un binario che non si
# apre, o che si apre e poi esegue un'istruzione che la CPU non ha. E il posto
# dove si manifesta e' la macchina di qualcun altro, al primo avvio.
#
# La scelta e' quindi una funzione pura di (sistema, architettura,
# acceleratore), separata dal download apposta per poterla verificare qui.
# ==============================================================================
import unittest

from core.engine.llama_runtime import (
    _cuda_compatibile,
    asset_name,
    candidate_variants,
    select_asset,
)

#: Gli asset reali della build b10628, presi dalle release di ggml-org.
ASSETS = [
    "llama-b10628-bin-win-cpu-x64.zip",
    "llama-b10628-bin-win-cpu-arm64.zip",
    "llama-b10628-bin-win-cuda-12.4-x64.zip",
    "llama-b10628-bin-win-cuda-13.3-x64.zip",
    "llama-b10628-bin-win-vulkan-x64.zip",
    "llama-b10628-bin-win-rocm-7.14-x64.zip",
    "llama-b10628-bin-win-sycl-x64.zip",
    "llama-b10628-bin-ubuntu-sycl-fp16-x64.tar.gz",
    "llama-b10628-bin-ubuntu-sycl-fp32-x64.tar.gz",
    "llama-b10628-bin-ubuntu-x64.tar.gz",
    "llama-b10628-bin-ubuntu-arm64.tar.gz",
    "llama-b10628-bin-ubuntu-vulkan-x64.tar.gz",
    "llama-b10628-bin-ubuntu-vulkan-arm64.tar.gz",
    "llama-b10628-bin-ubuntu-rocm-7.14-x64.tar.gz",
    "llama-b10628-bin-macos-arm64.tar.gz",
    "llama-b10628-bin-macos-x64.tar.gz",
]
BUILD = "b10628"


class TestSceltaPerPiattaforma(unittest.TestCase):

    def _scegli(self, **macchina):
        return select_asset(ASSETS, BUILD, **macchina)

    def test_windows_nvidia(self):
        self.assertEqual(
            self._scegli(sistema="Windows", arch="AMD64", compute="cuda", cuda_version="12.4"),
            "llama-b10628-bin-win-cuda-12.4-x64.zip")

    def test_windows_amd_prende_rocm(self):
        self.assertEqual(
            self._scegli(sistema="Windows", arch="AMD64", compute="rocm", rocm_version="7.14"),
            "llama-b10628-bin-win-rocm-7.14-x64.zip")

    def test_windows_cpu(self):
        self.assertEqual(
            self._scegli(sistema="Windows", arch="AMD64", compute="cpu"),
            "llama-b10628-bin-win-cpu-x64.zip")

    def test_raspberry_pi(self):
        self.assertEqual(
            self._scegli(sistema="Linux", arch="aarch64", compute="cpu"),
            "llama-b10628-bin-ubuntu-arm64.tar.gz")

    def test_apple_silicon(self):
        self.assertEqual(
            self._scegli(sistema="Darwin", arch="arm64", compute="metal"),
            "llama-b10628-bin-macos-arm64.tar.gz")

    def test_ogni_macchina_ottiene_qualcosa(self):
        """Il requisito che rende Sigma Studio installabile ovunque.

        Qualunque combinazione deve atterrare su un archivio: se l'acceleratore
        non ha una build, si scende fino alla CPU, che c'e' sempre.
        """
        casi = [
            ("Windows", "AMD64"), ("Windows", "ARM64"),
            ("Linux", "x86_64"), ("Linux", "aarch64"),
            ("Darwin", "arm64"), ("Darwin", "x86_64"),
        ]
        for sistema, arch in casi:
            for compute in ("cuda", "rocm", "vulkan", "metal", "cpu", "sconosciuto"):
                with self.subTest(sistema=sistema, arch=arch, compute=compute):
                    scelto = self._scegli(sistema=sistema, arch=arch, compute=compute)
                    self.assertIsNotNone(
                        scelto, f"{sistema}/{arch}/{compute} resta senza runtime")
                    self.assertIn(scelto, ASSETS)

    def test_l_ultima_scelta_e_sempre_una_build_cpu(self):
        """Il ripiego non deve mai essere un acceleratore che potrebbe mancare."""
        for sistema, arch in (("Windows", "AMD64"), ("Linux", "x86_64"),
                              ("Linux", "aarch64")):
            with self.subTest(sistema=sistema, arch=arch):
                varianti = candidate_variants(sistema=sistema, arch=arch, compute="cuda")
                ultima = varianti[-1]
                self.assertTrue("cpu" in ultima or ultima in ("ubuntu-x64", "ubuntu-arm64"),
                                f"l'ultimo ripiego e' '{ultima}', non una build CPU")


class TestVersioneCuda(unittest.TestCase):
    """CUDA e' compatibile in avanti nei minori, non fra maggiori."""

    DISPONIBILI = ["13.3", "12.4"]

    def test_stessa_versione(self):
        self.assertEqual(_cuda_compatibile("12.4", self.DISPONIBILI), "12.4")

    def test_minore_piu_alto_non_superiore(self):
        """Con CUDA 13.5 va bene una build 13.3: i minori sono compatibili."""
        self.assertEqual(_cuda_compatibile("13.5", self.DISPONIBILI), "13.3")

    def test_mai_un_maggiore_diverso(self):
        """Il caso che conta: CUDA 13 non deve prendere una build 12.

        Non darebbe un errore chiaro, darebbe un caricamento che fallisce
        all'apertura della libreria. Meglio nessuna build CUDA e ripiegare su
        Vulkan o CPU, che funzionano.
        """
        self.assertIsNone(_cuda_compatibile("13.0", ["12.4"]))
        self.assertIsNone(_cuda_compatibile("11.8", ["12.4", "13.3"]))

    def test_driver_piu_vecchio_di_ogni_build_dello_stesso_maggiore(self):
        self.assertEqual(_cuda_compatibile("12.1", ["12.4", "12.8"]), "12.4")

    def test_senza_versione_nota_non_si_indovina(self):
        self.assertIsNone(_cuda_compatibile(None, self.DISPONIBILI))

    def test_cuda13_ripiega_su_vulkan_non_su_cuda12(self):
        """Verifica end-to-end del caso sopra, attraverso select_asset."""
        senza_13 = [a for a in ASSETS if "cuda-13" not in a]
        scelto = select_asset(senza_13, BUILD, sistema="Windows", arch="AMD64",
                              compute="cuda", cuda_version="13.0")
        self.assertEqual(scelto, "llama-b10628-bin-win-vulkan-x64.zip")


class TestNomiDegliArchivi(unittest.TestCase):

    def test_estensione_per_sistema(self):
        self.assertTrue(asset_name("b1", "win-cpu-x64").endswith(".zip"))
        self.assertTrue(asset_name("b1", "ubuntu-x64").endswith(".tar.gz"))
        self.assertTrue(asset_name("b1", "macos-arm64").endswith(".tar.gz"))


class TestIntel(unittest.TestCase):
    """Intel ha due strade, e quale si prende dipende da cosa e' installato."""

    def test_con_oneapi_prende_sycl(self):
        self.assertEqual(
            select_asset(ASSETS, BUILD, sistema="Windows", arch="AMD64", compute="sycl"),
            "llama-b10628-bin-win-sycl-x64.zip")

    def test_su_linux_preferisce_la_variante_fp16(self):
        self.assertEqual(
            select_asset(ASSETS, BUILD, sistema="Linux", arch="x86_64", compute="sycl"),
            "llama-b10628-bin-ubuntu-sycl-fp16-x64.tar.gz")

    def test_senza_oneapi_resta_vulkan(self):
        """Le Xe integrate e le Arc funzionano con il solo driver grafico."""
        self.assertEqual(
            select_asset(ASSETS, BUILD, sistema="Windows", arch="AMD64", compute="vulkan"),
            "llama-b10628-bin-win-vulkan-x64.zip")

    def test_sycl_ripiega_se_la_build_non_c_e(self):
        senza_sycl = [a for a in ASSETS if "sycl" not in a]
        self.assertEqual(
            select_asset(senza_sycl, BUILD, sistema="Windows", arch="AMD64", compute="sycl"),
            "llama-b10628-bin-win-vulkan-x64.zip")


class TestSceltaDellAcceleratore(unittest.TestCase):
    """Un runtime che non si apre non deve entrare nella scelta.

    E' la regola che separa "questa macchina ha una scheda AMD" da "questa
    macchina puo' avviare una build ROCm". Confonderle da' un binario che non
    apre le proprie librerie al primo avvio.
    """

    def _scegli(self, gpu, runtimes):
        import core.engine.gpu_vendors as gv
        originali = (gv.gpu_vendors, gv.available_runtimes)
        gv.gpu_vendors = lambda: list(gpu)
        gv.available_runtimes = lambda: dict(runtimes)
        try:
            return gv.preferred_compute()
        finally:
            gv.gpu_vendors, gv.available_runtimes = originali

    SPENTI = {"cuda": False, "vulkan": False, "hip": False, "sycl": False, "metal": False}

    def test_amd_senza_hip_non_prende_rocm(self):
        scelto = self._scegli(["amd"], dict(self.SPENTI, vulkan=True))
        self.assertEqual(scelto, "vulkan")

    def test_amd_con_hip_prende_rocm(self):
        scelto = self._scegli(["amd"], dict(self.SPENTI, hip=True, vulkan=True))
        self.assertEqual(scelto, "rocm")

    def test_intel_senza_oneapi_prende_vulkan(self):
        scelto = self._scegli(["intel"], dict(self.SPENTI, vulkan=True))
        self.assertEqual(scelto, "vulkan")

    def test_intel_con_oneapi_prende_sycl(self):
        scelto = self._scegli(["intel"], dict(self.SPENTI, sycl=True, vulkan=True))
        self.assertEqual(scelto, "sycl")

    def test_apu_amd_piu_scheda_nvidia_prende_cuda(self):
        """Il caso di questa macchina, e fra i piu' comuni in circolazione.

        L'enumerazione restituisce ['amd', 'nvidia'] perche' la Radeon
        integrata nell'APU viene elencata per prima: seguire l'ordine di
        scoperta sceglieva ROCm su una grafica integrata invece di CUDA su due
        schede discrete.
        """
        scelto = self._scegli(["amd", "nvidia"],
                              dict(self.SPENTI, cuda=True, hip=True, vulkan=True))
        self.assertEqual(scelto, "cuda")

    def test_senza_niente_resta_la_cpu(self):
        self.assertEqual(self._scegli([], dict(self.SPENTI)), "cpu")

    def test_una_scheda_senza_alcun_runtime_non_impedisce_l_avvio(self):
        """Il requisito: su qualunque hardware Sigma Studio deve partire."""
        self.assertEqual(self._scegli(["nvidia", "amd", "intel"], dict(self.SPENTI)), "cpu")


if __name__ == "__main__":
    unittest.main()