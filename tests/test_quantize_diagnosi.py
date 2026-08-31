"""Un fallimento di quantizzazione deve dire cosa fare.

Prima, quando Q2_K falliva, il Model Hub mostrava questo e nient'altro:

    RuntimeError: llama_model_quantize ha restituito 1

Il motivo llama.cpp lo scrive davvero, ma nel log della libreria, che finisce
sullo stderr del server. Chi guarda la conversione dalla UI vede un numero, e
un numero non dice se liberare spazio, cambiare tipo o rinunciare.
"""

import unittest

from core.engine.gguf_converter import GgufConverter


class TestMotivoDelFallimento(unittest.TestCase):

    def test_tensori_non_divisibili_suggeriscono_un_tipo_senza_quel_vincolo(self):
        """E' il fallimento tipico dei tipi K sui modelli con dimensioni strane."""
        righe = [
            "llama_model_quantize: failed to quantize",
            "ggml_validate_row_data: tensor blk.0.ffn_down.weight has 1536 "
            "elements, not divisible by 256",
        ]
        motivo = GgufConverter._motivo_quantizzazione(righe, "Q2_K")
        self.assertIn("256", motivo)
        # Deve nominare un tipo che quel vincolo non ce l'ha: dire solo "non si
        # puo'" lascia l'utente senza la mossa successiva.
        self.assertTrue("Q8_0" in motivo or "Q4_0" in motivo)

    def test_scrittura_interrotta_parla_di_spazio(self):
        righe = ["llama_model_quantize: failed to write tensor data"]
        motivo = GgufConverter._motivo_quantizzazione(righe, "Q6_K")
        self.assertIn("spazio", motivo.lower())

    def test_senza_indizi_noti_riporta_comunque_l_ultima_riga(self):
        """Meglio le parole di llama.cpp che un codice numerico."""
        righe = ["qualcosa di inatteso e' andato storto"]
        motivo = GgufConverter._motivo_quantizzazione(righe, "Q4_K_M")
        self.assertIn("qualcosa di inatteso", motivo)

    def test_senza_log_dice_le_cause_tipiche(self):
        motivo = GgufConverter._motivo_quantizzazione([], "Q2_K")
        self.assertIn("disco", motivo.lower())
        self.assertTrue(motivo.strip())

    def test_la_coda_del_log_e_limitata(self):
        """Un log intero in un messaggio di errore non e' un messaggio."""
        righe = [f"riga {i}" for i in range(5000)]
        motivo = GgufConverter._motivo_quantizzazione(righe, "Q4_K_M")
        self.assertLess(len(motivo), 500)


if __name__ == "__main__":
    unittest.main()


class TestSceltaDellaSorgente(unittest.TestCase):
    """Da quale file si riparte quando la cartella ne contiene piu' d'uno.

    Prima si prendeva il primo in ordine alfabetico. Con un Q8_0 e un Q4_K_M
    nella stessa cartella "Q4_K_M" viene prima, quindi si ripartiva dal piu'
    povero dei due: il risultato portava due arrotondamenti invece di uno, e
    nel file prodotto non si vedeva.
    """

    def test_fra_due_gguf_vince_il_piu_preciso(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            for nome in ("modello.Q4_K_M.gguf", "modello.Q8_0.gguf"):
                open(os.path.join(d, nome), "w").close()
            scelto = GgufConverter._existing_gguf(d)
        self.assertTrue(scelto.endswith("Q8_0.gguf"), scelto)

    def test_un_intermedio_a_16_bit_batte_ogni_quantizzato(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            for nome in ("m.Q8_0.gguf", "m-bf16.gguf", "m.Q2_K.gguf"):
                open(os.path.join(d, nome), "w").close()
            scelto = GgufConverter._existing_gguf(d)
        self.assertIn("bf16", scelto)

    def test_bf16_non_viene_letto_come_f16(self):
        """'F16' e' contenuto in 'BF16': l'ordine dei confronti conta."""
        self.assertEqual(GgufConverter._precisione_gguf("m-bf16.gguf"), 16.0)
        self.assertEqual(GgufConverter._precisione_gguf("m-f16.gguf"), 16.0)

    def test_un_nome_senza_tag_vale_come_intermedio(self):
        self.assertEqual(GgufConverter._precisione_gguf("modello.gguf"), 16.0)

    def test_i_tipi_quantizzati_stanno_sotto_i_16_bit(self):
        for nome in ("m.Q2_K.gguf", "m.Q4_K_M.gguf", "m.Q6_K.gguf"):
            self.assertLess(GgufConverter._precisione_gguf(nome), 16.0, nome)

    def test_una_cartella_senza_gguf_non_offre_niente(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(GgufConverter._existing_gguf(d))
