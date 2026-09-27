"""Un modello MLX a 4 bit, riportato a 16 bit prima di convertirlo in GGUF.

Il convertitore di llama.cpp mappa i tensori di Hugging Face uno per uno: i
`lm_head.biases` di un checkpoint MLX non sono nella mappa, e la conversione
muore con "Can not map tensor" dopo aver gia' scritto mezzo file. Qui si prova
che quei pesi si rileggono, si dequantizzano con la formula giusta (nibble dai
bit bassi, `w * scale + offset`) e si riscrivono in un safetensors che il
convertitore sa leggere.

I checkpoint delle prove sono costruiti a mano: se li scrivesse il modulo in
prova, un errore di formato passerebbe inosservato da entrambe le parti.
"""

import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core.engine import mlx_weights as mlx


def _bf16_tronca(x) -> np.ndarray:
    """F32 -> uint16 nell'ordine del bf16: i suoi primi sedici bit."""
    return (np.asarray(x, dtype=np.float32).view(np.uint32) >> np.uint32(16)).astype(np.uint16)


def _bf16_estendi(u16: np.ndarray) -> np.ndarray:
    """uint16 bf16 -> F32: gli stessi sedici bit in cima."""
    return (np.asarray(u16, dtype=np.uint16).astype(np.uint32) << np.uint32(16)).view(np.float32)


def _scrivi_safetensors(path: Path, tensori) -> None:
    """Un safetensors scritto a mano: header JSON, padding a 8, poi i byte."""
    voci = {}
    posizione = 0
    pezzi = []
    for nome, (dtype, dati) in tensori.items():
        grezzo = np.ascontiguousarray(dati).tobytes()
        voci[nome] = {"dtype": dtype, "shape": list(np.shape(dati)),
                      "data_offsets": [posizione, posizione + len(grezzo)]}
        pezzi.append(grezzo)
        posizione += len(grezzo) + (-len(grezzo) % 8)
    header = json.dumps(voci, separators=(",", ":")).encode("utf-8")
    header += b" " * ((8 - len(header) % 8) % 8)
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(header)))
        f.write(header)
        for grezzo in pezzi:
            f.write(grezzo)
            f.write(b"\0" * (-len(grezzo) % 8))


def _pack_affine(pesi: np.ndarray, group_size: int, bits: int = 4):
    """Impacchetta come MLX, e torna anche quello che la dequant deve dire.

    L'atteso e' calcolato sulle scale gia' troncate a bf16, che sono quelle che
    finiscono nel file: cosi' il confronto e' esatto e non "circa".
    """
    righe, in_dim = pesi.shape
    gruppi = in_dim // group_size
    g = np.asarray(pesi, dtype=np.float32).reshape(righe, gruppi, group_size)
    minimo = g.min(axis=-1)
    massimo = g.max(axis=-1)
    livelli = (1 << bits) - 1
    scala = (massimo - minimo) / livelli
    scala[scala == 0] = 1.0
    q = np.rint((g - minimo[..., None]) / scala[..., None]).clip(0, livelli).astype(np.uint32)
    q = q.reshape(righe, in_dim)

    valori = 32 // bits
    packed = np.zeros((righe, in_dim // valori), dtype=np.uint32)
    for k in range(valori):
        packed |= q[:, k::valori] << np.uint32(bits * k)

    scala_u16 = _bf16_tronca(scala)
    bias_u16 = _bf16_tronca(minimo)
    atteso = (q.reshape(righe, gruppi, group_size).astype(np.float32)
              * _bf16_estendi(scala_u16)[..., None]
              + _bf16_estendi(bias_u16)[..., None]).reshape(righe, in_dim)
    return packed, atteso, scala_u16, bias_u16


def _cartella_mlx(tmp: str, *, bits: int = 4, group_size: int = 64,
                  mode: str = "affine", righe: int = 4, in_dim: int = 128,
                  nome: str = "modellino-mlx"):
    """Un checkpoint MLX in miniatura: un peso quantizzato, una norma in bf16."""
    radice = Path(tmp) / nome
    radice.mkdir(parents=True, exist_ok=True)
    pesi = np.random.default_rng(11).standard_normal((righe, in_dim)).astype(np.float32)
    packed, atteso, scala, bias = _pack_affine(pesi, group_size, bits)
    _scrivi_safetensors(radice / "model.safetensors", {
        "model.embed_tokens.weight": ("U32", packed),
        "model.embed_tokens.scales": ("BF16", scala),
        "model.embed_tokens.biases": ("BF16", bias),
        "model.norm.weight": ("BF16", _bf16_tronca(np.ones(in_dim, dtype=np.float32))),
    })
    with open(radice / "config.json", "w", encoding="utf-8") as f:
        json.dump({
            "model_type": "llama",
            "architectures": ["LlamaForCausalLM"],
            "hidden_size": in_dim,
            "quantization": {"group_size": group_size, "bits": bits, "mode": mode},
        }, f)
    with open(radice / "tokenizer.json", "w", encoding="utf-8") as f:
        f.write("{}")
    return radice, pesi, atteso, _bf16_estendi(scala).reshape(-1)


def _leggi_safetensors(path: Path):
    """Rilegge un safetensors senza passare dal modulo in prova."""
    with open(path, "rb") as f:
        lunghezza = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(lunghezza).decode("utf-8"))
        dati = f.read()
    return header, dati


class TestRiconoscimento(unittest.TestCase):
    """Chi decide se un modello va dequantizzato, e su quale prova."""

    def test_riconosce_un_checkpoint_mlx_e_ne_legge_i_parametri(self):
        with tempfile.TemporaryDirectory() as tmp:
            radice, _pesi, _atteso, _scala = _cartella_mlx(tmp)
            info = mlx.quantizzazione_mlx(str(radice))
            self.assertIsNotNone(info)
            self.assertEqual(info["bits"], 4)
            self.assertEqual(info["group_size"], 64)
            self.assertEqual(info["mode"], "affine")
            self.assertEqual(info["tensori_quantizzati"], 1)
            self.assertTrue(info["dequantizzabile"])
            self.assertTrue(mlx.e_quantizzato_mlx(str(radice)))

    def test_un_checkpoint_normale_non_e_mlx(self):
        """Senza scale accanto al peso non c'e' niente da dequantizzare."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp) / "normale"
            radice.mkdir()
            _scrivi_safetensors(radice / "model.safetensors", {
                "model.embed_tokens.weight": ("F32", np.zeros((4, 8), dtype=np.float32)),
            })
            self.assertIsNone(mlx.quantizzazione_mlx(str(radice)))
            self.assertFalse(mlx.e_quantizzato_mlx(str(radice)))

    def test_una_cartella_di_soli_gguf_non_e_mlx(self):
        """Un GGUF ha gia' i suoi pesi: dequantizzarlo non vuol dire niente."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            (radice / "model.safetensors").write_bytes(b"")
            (radice / "modello.q4_k_m.gguf").write_bytes(b"GGUF")
            self.assertIsNone(mlx.quantizzazione_mlx(str(radice)))

    def test_un_modo_che_non_sappiamo_disfare_viene_rifiutato(self):
        """mxfp4 tiene scale a 8 bit: disfarlo come l'affine darebbe numeri falsi."""
        with tempfile.TemporaryDirectory() as tmp:
            radice, _pesi, _atteso, _scala = _cartella_mlx(tmp, mode="mxfp4")
            info = mlx.quantizzazione_mlx(str(radice))
            self.assertFalse(info["dequantizzabile"])
            self.assertIn("mxfp4", info["motivo"])
            self.assertFalse(mlx.e_quantizzato_mlx(str(radice)))

    def test_un_config_che_dichiara_il_gruppo_sbagliato_viene_rifiutato(self):
        """Se il config mente sul gruppo, la dequantizzazione userebbe le scale sbagliate."""
        with tempfile.TemporaryDirectory() as tmp:
            radice, _pesi, _atteso, _scala = _cartella_mlx(tmp, in_dim=128, group_size=64)
            with open(radice / "config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["quantization"]["group_size"] = 32
            with open(radice / "config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            info = mlx.quantizzazione_mlx(str(radice))
            self.assertFalse(info["dequantizzabile"])
            self.assertIn("32", info["motivo"])
            self.assertIn("128", info["motivo"])
            with self.assertRaises(ValueError):
                mlx.dequantizza_verso_hf(str(radice), str(Path(tmp) / "hf"))

    def test_i_parametri_contati_sono_quelli_del_modello(self):
        """Contare gli uint32 del file direbbe un ottavo dei pesi veri."""
        with tempfile.TemporaryDirectory() as tmp:
            radice, _pesi, _atteso, _scala = _cartella_mlx(tmp, righe=4, in_dim=128)
            self.assertEqual(mlx.parametri_logici(str(radice)), 4 * 128 + 128)

    def test_i_parametri_non_si_contano_su_un_modello_non_mlx(self):
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp) / "normale"
            radice.mkdir()
            _scrivi_safetensors(radice / "model.safetensors", {
                "model.embed_tokens.weight": ("F32", np.zeros((4, 8), dtype=np.float32)),
            })
            self.assertIsNone(mlx.parametri_logici(str(radice)))


class TestDequantizzazione(unittest.TestCase):
    """La formula e l'ordine dei bit: sbagliarli non da' errore, da' pesi finti."""

    def test_il_nibble_esce_dai_bit_bassi(self):
        """Un uint32 = 15 e' un peso 15, non un peso altrove: e' l'ordine di MLX."""
        pesi = mlx._blocco_dequantizzato(
            np.array([[15]], dtype=np.uint32),
            np.array([[1.0]], dtype=np.float32),
            np.array([[0.0]], dtype=np.float32),
            4, 8,
        )
        self.assertEqual(pesi.tolist(), [[15.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])

    def test_il_secondo_nibble_sta_quattro_bit_piu_su(self):
        pesi = mlx._blocco_dequantizzato(
            np.array([[0x20]], dtype=np.uint32),
            np.array([[1.0]], dtype=np.float32),
            np.array([[0.0]], dtype=np.float32),
            4, 8,
        )
        self.assertEqual(pesi.tolist(), [[0.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])

    def test_scala_e_offset_cambiano_dentro_il_gruppo(self):
        """Ogni gruppo ha la sua scala: applicarla al gruppo sbagliato non da' errore."""
        packed = np.array([[1, 2]], dtype=np.uint32)     # primo peso a 1, nono peso a 2
        pesi = mlx._blocco_dequantizzato(
            packed,
            np.array([[10.0, 20.0, 30.0, 40.0]], dtype=np.float32),
            np.array([[1.0, 2.0, 3.0, 4.0]], dtype=np.float32),
            4, 4,
        )
        self.assertEqual(pesi.shape, (1, 16))
        self.assertEqual(pesi[0, 0], 1 * 10.0 + 1.0)
        self.assertEqual(pesi[0, 8], 2 * 30.0 + 3.0)
        self.assertEqual(pesi[0, 4], 0 * 20.0 + 2.0)

    def test_il_bf16_va_e_torna(self):
        valori = np.array([0.0, 1.0, -2.5, 1.5, 1024.0], dtype=np.float32)
        self.assertTrue(np.array_equal(mlx._bf16_a_f32(mlx._a_bf16(valori)), valori))

    def test_l_arrotondamento_bf16_e_al_piu_vicino(self):
        """Troncare invece di arrotondare allontanerebbe ogni peso di un ulp.

        Il bf16 tiene sette bit di mantissa: fra 1.0 e 1.0078125 la meta' sta a
        1.00390625, e chi sta sotto deve tornare indietro.
        """
        valori = np.array([1.0 + 2**-9, 1.0 + 2**-8 + 2**-12], dtype=np.float32)
        letti = mlx._bf16_a_f32(mlx._a_bf16(valori))
        self.assertEqual(float(letti[0]), 1.0)
        self.assertEqual(float(letti[1]), 1.0 + 2**-7)


class TestCheckpointScritto(unittest.TestCase):
    """Quello che esce deve essere un checkpoint HF, non un file qualunque."""

    def _convertito(self, tmp: str):
        radice, pesi, atteso, scala = _cartella_mlx(tmp)
        dest = Path(tmp) / "hf"
        riepilogo = mlx.dequantizza_verso_hf(str(radice), str(dest))
        header, dati = _leggi_safetensors(dest / "model.safetensors")
        return dest, riepilogo, header, dati, pesi, atteso, scala

    def test_esce_un_safetensors_senza_scales_ne_biases(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dest, riepilogo, header, _dati, _pesi, _atteso, _scala = self._convertito(tmp)
            self.assertNotIn("model.embed_tokens.scales", header)
            self.assertNotIn("model.embed_tokens.biases", header)
            self.assertEqual(riepilogo["dequantizzati"], 1)
            self.assertEqual(riepilogo["copiati"], 1)
            self.assertEqual(header["model.embed_tokens.weight"]["dtype"], "BF16")
            self.assertEqual(header["model.embed_tokens.weight"]["shape"], [4, 128])

    def test_i_pesi_riletti_sono_quelli_che_la_formula_promette(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dest, _r, header, dati, _pesi, atteso, _scala = self._convertito(tmp)
            inizio, fine = header["model.embed_tokens.weight"]["data_offsets"]
            letti = _bf16_estendi(
                np.frombuffer(dati[inizio:fine], dtype=np.uint16).reshape(4, 128))
            self.assertTrue(np.allclose(letti, atteso, rtol=2**-8, atol=1e-30))

    def test_i_pesi_riletti_sono_vicini_a_quelli_di_partenza(self):
        """L'errore deve stare dentro il passo della quantizzazione, non oltre."""
        with tempfile.TemporaryDirectory() as tmp:
            _dest, _r, header, dati, pesi, _atteso, scala = self._convertito(tmp)
            inizio, fine = header["model.embed_tokens.weight"]["data_offsets"]
            letti = _bf16_estendi(
                np.frombuffer(dati[inizio:fine], dtype=np.uint16).reshape(4, 128))
            self.assertLess(float(np.max(np.abs(letti - pesi))), float(np.max(scala)) * 0.55)

    def test_la_norma_non_quantizzata_si_copia_intatta(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dest, _r, header, dati, _pesi, _atteso, _scala = self._convertito(tmp)
            self.assertEqual(header["model.norm.weight"]["dtype"], "BF16")
            inizio, fine = header["model.norm.weight"]["data_offsets"]
            letti = _bf16_estendi(np.frombuffer(dati[inizio:fine], dtype=np.uint16))
            self.assertTrue(np.array_equal(letti, np.ones(128, dtype=np.float32)))

    def test_ogni_tensore_inizia_su_un_confine_di_otto_byte(self):
        """Senza allineamento il convertitore legge il tensore successivo sfasato."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp) / "strano"
            radice.mkdir()
            pesi = np.random.default_rng(3).standard_normal((2, 64)).astype(np.float32)
            packed, _atteso, scala, bias = _pack_affine(pesi, 64)
            _scrivi_safetensors(radice / "model.safetensors", {
                "primo.weight": ("U32", packed),
                "primo.scales": ("BF16", scala),
                "primo.biases": ("BF16", bias),
                "dispari.extra": ("I8", np.arange(5, dtype=np.int8)),
            })
            dest = Path(tmp) / "hf"
            mlx.dequantizza_verso_hf(str(radice), str(dest))
            header, dati = _leggi_safetensors(dest / "model.safetensors")
            fine_precedente = 0
            self.assertEqual(header["__metadata__"], {"format": "pt"})
            for nome, voce in header.items():
                if nome == "__metadata__":
                    continue
                inizio, fine = voce["data_offsets"]
                self.assertEqual(inizio % 8, 0, nome + " non allineato")
                self.assertGreaterEqual(inizio, fine_precedente)
                fine_precedente = fine
            self.assertEqual(len(dati), fine_precedente)
            self.assertEqual(header["dispari.extra"]["shape"], [5])

    def test_il_config_copiato_non_dichiara_piu_la_quantizzazione(self):
        """Un config che dichiara 4 bit accanto a pesi bf16 mente a chi lo legge."""
        with tempfile.TemporaryDirectory() as tmp:
            dest, riepilogo, _h, _d, _p, _a, _s = self._convertito(tmp)
            with open(dest / "config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertNotIn("quantization", cfg)
            self.assertNotIn("quantization_config", cfg)
            self.assertEqual(cfg["model_type"], "llama")
            self.assertIn("config.json", riepilogo["accessori"])
            self.assertTrue((dest / "tokenizer.json").is_file())

    def test_un_modello_che_non_e_mlx_non_si_converte(self):
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp) / "normale"
            radice.mkdir()
            _scrivi_safetensors(radice / "model.safetensors", {
                "model.embed_tokens.weight": ("F32", np.zeros((4, 8), dtype=np.float32)),
            })
            with self.assertRaises(ValueError):
                mlx.dequantizza_verso_hf(str(radice), str(Path(tmp) / "hf"))

    def test_un_modo_non_supportato_non_produce_un_file_a_meta(self):
        """Se non si sa disfare, non si scrive niente: mezzo checkpoint e' peggio di nessuno."""
        with tempfile.TemporaryDirectory() as tmp:
            radice, _pesi, _atteso, _scala = _cartella_mlx(tmp, mode="mxfp8")
            dest = Path(tmp) / "hf"
            with self.assertRaises(ValueError):
                mlx.dequantizza_verso_hf(str(radice), str(dest))
            self.assertFalse((dest / "model.safetensors").exists())
