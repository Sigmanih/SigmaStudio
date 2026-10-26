"""Finitura del colore dei film muti: le tecniche nate col Fantasma dell'Opera, su video sintetici.

Ogni prova costruisce il suo video con numpy e ffmpeg, cosi' non dipende dai film su disco:
- un riversamento a 30 fps con un fotogramma ripetuto ogni tre (20 fps veri dentro 30);
- una copia virata ambra con un'inquadratura "Technicolor" e una notte blu con il rosso dipinto a mano;
- la LUT che spegne il verde inventato da DDColor senza toccare la pelle.
"""
import subprocess
import unittest
from pathlib import Path
import tempfile

import numpy as np

from core.modules.sigma_creative_lab.video import color_finish as CF
from core.modules.sigma_creative_lab.video import restoration as R
from core.modules.sigma_creative_lab.video.production import ffmpeg_bin

W, H = 192, 144


def scrivi(frames: list[np.ndarray], path: Path, fps: str) -> Path:
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                    "-framerate", fps, "-i", "-", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(path)],
                   input=b"".join(f.astype(np.uint8).tobytes() for f in frames), check=True)
    return path


def scena(rng: np.random.Generator, n: int) -> list[np.ndarray]:
    """Grana che scorre: movimento vero, cosi' i doppioni si distinguono dai fotogrammi nuovi."""
    base = rng.integers(40, 200, (H, W + n)).astype(np.float32)
    return [np.repeat(base[:, i:i + W][..., None], 3, axis=2) for i in range(n)]


class TestDoppioni(unittest.TestCase):
    def test_venti_dentro_trenta(self):
        rng = np.random.default_rng(1)
        veri = scena(rng, 260)                                  # 13 s a 20 fps
        riversati = []
        for i in range(0, len(veri) - 1, 2):                     # ogni 2 veri: A, B, B -> 3 fotogrammi
            riversati += [veri[i], veri[i + 1], veri[i + 1]]
        with tempfile.TemporaryDirectory() as d:
            # Tre campioni da 12 s vogliono un film di almeno 30 s: si ripete la scena.
            p = scrivi(riversati * 4, Path(d) / "riv.mp4", "30000/1001")
            self.assertEqual(CF.repeat_cycle(p), 3)

    def test_nessun_doppione(self):
        rng = np.random.default_rng(2)
        with tempfile.TemporaryDirectory() as d:
            p = scrivi(scena(rng, 260) * 4, Path(d) / "pulito.mp4", "24000/1001")
            self.assertEqual(CF.repeat_cycle(p), 0)

    def test_velocita_dopo_il_filtro(self):
        self.assertAlmostEqual(R.ivtc_rate("decimate=cycle=3,"), 2 / 3)
        self.assertAlmostEqual(R.ivtc_rate("fieldmatch=order=auto,yadif,decimate,"), 4 / 5)
        self.assertEqual(R.ivtc_rate(""), 1.0)


def tinta(g: np.ndarray, rgb: tuple) -> np.ndarray:
    return g[..., None] * np.array(rgb, np.float32)[None, None, :]


class TestMappaTinte(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(3)
        # Una trama diversa per inquadratura: il taglio e' un salto netto della luminanza, come nel film.
        trama = lambda: rng.uniform(0.3, 0.9, (H, W)).astype(np.float32)  # noqa: E731

        def tech():                                             # rosso e verde-azzurro nello stesso quadro
            g = trama()
            f = tinta(g, (230, 80, 70))
            f[:, W // 2:] = tinta(g[:, W // 2:], (60, 190, 200))
            return [f] * 40

        def dipinto():
            f = tinta(trama(), (90, 120, 255))
            f[50:80, 80:110] = (220, 20, 20)                     # il mantello rosso dipinto a mano
            return [f] * 40

        ambra = [tinta(trama(), (255, 190, 120))] * 40
        blu = lambda: [tinta(trama(), (90, 120, 255))] * 40  # noqa: E731
        cls.tmp = tempfile.TemporaryDirectory()
        # Ambra, Technicolor, notte blu, notte blu col rosso, notte blu, Technicolor: 40 fotogrammi ciascuna.
        cls.film = scrivi(ambra + tech() + blu() + dipinto() + blu() + tech(), Path(cls.tmp.name) / "virato.mp4",
                          "20000/1001")
        cls.cmap = CF.color_map(cls.film)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_inquadrature_e_tinte(self):
        tinte = [s["tinta"] for s in self.cmap["shots"]]
        self.assertEqual(tinte, ["ambra", "colore", "blu", "blu", "blu", "colore"])

    def test_protette_e_blocco_esteso(self):
        prot = [s["protetta"] for s in self.cmap["shots"]]
        # Il Technicolor e il rosso dipinto si proteggono; le notti blu fra due protette entrano nel blocco.
        self.assertEqual(prot, [False, True, True, True, True, True])
        self.assertEqual(self.cmap["shots"][0]["grado"], "giorno")

    def test_correzione_a_mano(self):
        import copy
        cmap = CF.set_protection(copy.deepcopy(self.cmap), [{"start_s": 4.5, "end_s": 5.5, "protect": False}])
        notte = [s for s in cmap["shots"] if s["start"] == 80][0]
        self.assertFalse(notte["protetta"])
        self.assertTrue(notte["edited"])
        riassunto = CF.summary(cmap)
        self.assertGreater(riassunto["night_s"], 0)
        self.assertTrue(riassunto["protected"])


class TestLutVerde(unittest.TestCase):
    def test_spegne_il_verde_e_lascia_la_pelle(self):
        with tempfile.TemporaryDirectory() as d:
            lut = CF.green_lut(Path(d) / "verdi.cube")
            colori = np.array([[[90, 200, 60], [225, 170, 140], [60, 80, 200], [200, 60, 50]]], np.uint8)
            out = subprocess.run([ffmpeg_bin(), "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "4x1",
                                  "-i", "-", "-vf", f"lut3d=file='{lut.as_posix().replace(':', chr(92) + ':')}'",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], input=colori.tobytes(),
                                 capture_output=True, check=True).stdout
            dopo = np.frombuffer(out, np.uint8).reshape(4, 3).astype(int)
            prima = colori.reshape(4, 3).astype(int)
            sat = lambda c: (c.max() - c.min()) / max(1, c.max())  # noqa: E731
            self.assertLess(sat(dopo[0]), 0.4 * sat(prima[0]))          # verde acceso -> quasi grigio
            for i in (1, 2, 3):                                         # pelle, blu notte, rosso: intatti
                self.assertLess(np.abs(dopo[i] - prima[i]).max(), 12)


if __name__ == "__main__":
    unittest.main()
