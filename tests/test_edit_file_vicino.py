# ==============================================================================
# tests/test_edit_file_vicino.py — Quando old_string non combacia
# ==============================================================================
"""Un rifiuto che non dice cosa cambiare produce un tentativo a caso.

`edit_file` rispondeva sempre la stessa riga — «il testo deve corrispondere
ESATTAMENTE, indentazione compresa» — e non diceva altro. Per un modello locale
che sbaglia il rientro e non sa di averlo sbagliato, quella riga non contiene
l'informazione che serve: STATO_HARNESS.md registra un run finito con ventitre
`edit_file` identici di fila.

Qui il rifiuto porta tre cose che prima non c'erano: **dove** si e' andati
vicino, **quanto**, e **in cosa** si differisce — con le righe vere del file da
ricopiare. E quando la differenza e' soltanto di spazi, la modifica viene
applicata riallineata invece di essere respinta, dicendolo.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.harness.fs_tools import edit_file_content

SORGENTE = """def calcola(valori):
    totale = 0
    for v in valori:
        totale += v
    return totale


def media(valori):
    if not valori:
        return 0
    return calcola(valori) / len(valori)
"""


class BaseConFile(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.radice = Path(self._tmp.name)
        self.file = self.radice / "calcoli.py"
        self.file.write_text(SORGENTE, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def modifica(self, vecchio, nuovo):
        return edit_file_content(str(self.file), vecchio, nuovo, root=str(self.radice))


class TestIlRifiutoDiceDoveSiEAndatiVicino(BaseConFile):

    def test_indentazione_sbagliata_viene_applicata_riallineata(self):
        """Il caso piu' frequente: il modello ricopia senza il rientro.

        Respingerlo costa due turni per uno spazio. Il blocco vero c'e', e' uno
        solo, e differisce soltanto per gli spazi davanti.
        """
        esito = self.modifica(
            "for v in valori:\n    totale += v",
            "for v in valori:\n    totale += int(v)",
        )
        self.assertTrue(esito["success"], esito.get("error"))
        self.assertTrue(esito["riallineato"],
                        "una modifica applicata diversamente da come e' stata chiesta va dichiarata")
        righe = self.file.read_text(encoding="utf-8").splitlines()
        self.assertIn("    for v in valori:", righe)
        self.assertIn("        totale += int(v)", righe)

    def test_il_rientro_della_sostituzione_segue_il_blocco_vero(self):
        """Se old_string arriva senza rientro, anche new_string ne e' senza:
        riapplicarla tale e quale rovinerebbe il file."""
        esito = self.modifica(
            "if not valori:\n    return 0",
            "if not valori:\n    return None",
        )
        self.assertTrue(esito["success"], esito.get("error"))
        self.assertTrue(esito["riallineato"])
        righe = self.file.read_text(encoding="utf-8").splitlines()
        self.assertIn("    if not valori:", righe)
        self.assertIn("        return None", righe)

    def test_differenza_di_contenuto_dice_la_riga_e_mostra_il_blocco(self):
        esito = self.modifica(
            "    for v in valori:\n        totale = totale + v",
            "    for v in valori:\n        totale += v * 2",
        )
        self.assertFalse(esito["success"])
        self.assertEqual(esito["riga_piu_simile"], 3)
        self.assertGreaterEqual(esito["somiglianza"], 70)
        # Il blocco vero deve essere nel messaggio, pronto da ricopiare.
        self.assertIn("totale += v", esito["error"])
        self.assertIn("NEL FILE c'e' esattamente questo", esito["error"])

    def test_il_messaggio_nomina_il_tipo_di_differenza(self):
        esito = self.modifica(
            "    for v  in  valori:\n        totale  +=  v",
            "    for v in valori:\n        totale += v + 1",
        )
        self.assertFalse(esito["success"])
        self.assertEqual(esito["differenza"], "solo spaziatura interna")

    def test_quando_non_somiglia_a_niente_lo_dice_e_non_inventa(self):
        """Una corrispondenza approssimata su un blocco che l'agente non
        intendeva e' peggio di un rifiuto: sotto la soglia non si propone."""
        esito = self.modifica(
            "class GestoreDelleConnessioniRemote:\n    def apri(self, host, porta):",
            "class Altro:\n    pass",
        )
        self.assertFalse(esito["success"])
        self.assertNotIn("riga_piu_simile", esito)
        self.assertIn("non c'e' niente che gli somigli", esito["error"])

    def test_la_corrispondenza_esatta_non_passa_dal_riallineamento(self):
        esito = self.modifica("    totale = 0\n", "    totale = 1\n")
        self.assertTrue(esito["success"])
        self.assertFalse(esito["riallineato"])

    def test_ambiguita_resta_un_rifiuto(self):
        """Il riallineamento non deve aprire una porta all'ambiguita'."""
        self.file.write_text("x = 1\nx = 1\n", encoding="utf-8")
        esito = self.modifica("x = 1", "x = 2")
        self.assertFalse(esito["success"])
        self.assertEqual(esito["occurrences"], 2)


class TestCostoSuFileGrande(BaseConFile):

    def test_il_confronto_non_e_proibitivo(self):
        """La ricerca del blocco piu' simile gira su ogni fallimento: se
        costasse secondi, la si toglierebbe al primo file grande."""
        import time

        grande = "\n".join(f"    riga_numero_{i} = {i} * 3" for i in range(6000))
        self.file.write_text(grande, encoding="utf-8")
        t0 = time.perf_counter()
        esito = self.modifica(
            "riga_numero_4242 = 4242 * 7",
            "riga_numero_4242 = 4242 * 9",
        )
        durata = time.perf_counter() - t0
        self.assertFalse(esito["success"])
        self.assertEqual(esito["riga_piu_simile"], 4243)
        self.assertLess(durata, 5.0, f"troppo lento su 6000 righe: {durata:.2f}s")


if __name__ == "__main__":
    unittest.main()
