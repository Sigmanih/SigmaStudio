"""Cosa il Model Hub dice a chi ha appena scaricato un modello.

Due messaggi sbagliati mandano l'utente nella direzione opposta a quella utile.
Il primo dice "non entra in VRAM" per un modello a esperti, dove il peso
complessivo non e' il requisito della scheda. Il secondo dice "aggiorna gli
strumenti" per un'architettura che nessuno ha ancora implementato, mandando a
cercare una versione che non esiste.

Sono errori che non rompono nulla e costano ore a chi li legge.
"""

import unittest
from types import SimpleNamespace

from core.engine.gguf_converter import GgufConverter


def _facts(**kwargs):
    """Un ModelFacts abbastanza completo per i controlli di compatibilita'."""
    base = dict(
        name="modello",
        path="store/models/modello",
        model_type="qwen2",
        architectures=["Qwen2ForCausalLM"],
        num_hidden_layers=32,
        param_count=7_000_000_000,
        total_bytes=14_000_000_000,
        weight_format="safetensors",
        is_moe=False,
        num_experts=0,
        experts_used=0,
        is_multimodal=False,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestNotaModelliAEsperti(unittest.TestCase):
    """Un MoE non tiene tutti gli esperti sulla scheda."""

    def test_un_modello_denso_non_riceve_la_nota(self):
        self.assertIsNone(GgufConverter._moe_note(_facts()))

    def test_un_moe_riceve_la_nota_con_i_suoi_numeri(self):
        nota = GgufConverter._moe_note(
            _facts(is_moe=True, num_experts=288, experts_used=8)
        )
        self.assertIsNotNone(nota)
        self.assertEqual(nota["experts_total"], 288)
        self.assertEqual(nota["experts_used_per_token"], 8)
        self.assertIn("288", nota["note"])

    def test_la_nota_spiega_che_il_peso_non_e_il_requisito(self):
        """Il messaggio deve smentire la conclusione sbagliata, non solo informare."""
        nota = GgufConverter._moe_note(
            _facts(is_moe=True, num_experts=128, experts_used=4)
        )
        testo = nota["note"].lower()
        self.assertIn("ncmoe", testo)
        self.assertIn("ram", testo)

    def test_la_nota_nomina_il_vincolo_vero(self):
        """Per un MoE il limite e' la RAM libera, non la VRAM."""
        nota = GgufConverter._moe_note(
            _facts(is_moe=True, num_experts=64, experts_used=2)
        )
        self.assertIn("disco", nota["note"].lower())


class TestArchitetturaNonSupportata(unittest.TestCase):
    """Aggiornare aiuta solo se il supporto esiste da qualche parte."""

    def test_un_architettura_nota_non_e_bloccata(self):
        report = GgufConverter.check_compatibility(_facts())
        self.assertFalse(report.get("upstream_missing", False))
        self.assertEqual(report["blocked_by"], [])

    def test_un_architettura_ignota_al_writer_e_segnata_come_upstream(self):
        """Se il writer non la conosce, non la conosce nemmeno un runtime nuovo."""
        report = GgufConverter.check_compatibility(
            _facts(model_type="architettura_che_non_esiste_2099",
                   architectures=["FuturoForCausalLM"])
        )
        self.assertTrue(report.get("upstream_missing"))

    def test_il_messaggio_upstream_non_consiglia_di_aggiornare(self):
        """Consigliare un aggiornamento manda a cercare una versione inesistente."""
        report = GgufConverter.check_compatibility(
            _facts(model_type="architettura_che_non_esiste_2099",
                   architectures=["FuturoForCausalLM"])
        )
        sommario = report["summary"].lower()
        self.assertIn("non aiuta", sommario)
        self.assertIn("transformers", sommario)




class TestSpazioSuDisco(unittest.TestCase):
    """La conversione fallisce prima, non a meta'.

    Qwen3.8-Flash-Next e' morto dopo dieci minuti e 223 GB scritti con
    `OSError: 838860800 requested and 0 written` — disco pieno, detto in un
    modo che non lo dice. Le dimensioni erano note in partenza.
    """

    @staticmethod
    def _grande():
        # ~177B parametri: l'intermedio f16 pesa 354 GB, il q8_0 188 GB.
        return _facts(param_count=177_000_000_000, total_bytes=354_000_000_000)

    def test_intermedio_e_risultato_si_sommano(self):
        """Coesistono: il quantizzatore legge l'uno mentre scrive l'altro."""
        piano = GgufConverter._plan_conversion_space(
            self._grande(), "Q4_K_M", "C:/percorso/inesistente/xyz"
        )
        if not piano["ok"]:
            self.assertGreater(piano["needed_gb"],
                               max(piano["intermediate_gb"], piano["final_gb"]))
            self.assertAlmostEqual(
                piano["needed_gb"],
                piano["intermediate_gb"] + piano["final_gb"],
                delta=1.0,
            )

    def test_dice_quanti_gb_liberare(self):
        piano = GgufConverter._plan_conversion_space(
            self._grande(), "Q4_K_M", "C:/percorso/inesistente/xyz"
        )
        if not piano["ok"]:
            self.assertIn("missing_gb", piano)
            self.assertGreater(piano["missing_gb"], 0)

    def test_un_modello_piccolo_passa(self):
        piano = GgufConverter._plan_conversion_space(
            _facts(param_count=1_000_000_000), "Q4_K_M", "."
        )
        self.assertTrue(piano["ok"])
        # "auto" e non "f16": quando lo spazio non e' un problema si prende il
        # tipo a 16 bit piu' fedele al modello. I pesi di questi modelli sono
        # bf16, e forzarli a f16 butta via tre bit di esponente senza far
        # risparmiare un byte.
        self.assertEqual(piano["intermediate"], "auto")
        self.assertFalse(piano["downgraded"])

    def test_ripiegare_su_q8_0_e_dichiarato(self):
        """Chi legge deve poter sapere che l'intermedio non e' a piena fedelta'."""
        piano = GgufConverter._plan_conversion_space(
            self._grande(), "Q4_K_M", "."
        )
        if piano["ok"]:
            self.assertEqual(piano["downgraded"], piano["intermediate"] != "auto")

    def test_senza_conteggio_parametri_non_si_blocca(self):
        """Un'incertezza nostra non deve impedire un'operazione dell'utente."""
        piano = GgufConverter._plan_conversion_space(
            _facts(param_count=0), "Q4_K_M", "."
        )
        self.assertTrue(piano["ok"])


if __name__ == "__main__":
    unittest.main()
