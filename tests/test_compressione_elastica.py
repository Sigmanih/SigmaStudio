# ==============================================================================
# tests/test_compressione_elastica.py — Comprimere prima di sfrattare
# ==============================================================================
"""Il turno si toglie solo se rimpicciolirlo non basta.

La prova che conta e' una sola e non e' «il testo si accorcia»: e' «gli errori
sono ancora tutti li'». Un'osservazione compressa che perde la riga con la
traccia dello stack e' peggio di un turno in piu' nella finestra, perche'
l'agente crede di aver capito e riscrive il codice da capo.
"""
from core.harness.compaction import (
    MINIMO_COMPRIMIBILE,
    comprimi_osservazioni,
    comprimi_testo,
    compact_history_with_memory,
)

RUMORE = "\n".join(
    f"riga di rumore numero {i} che non dice niente di utile al modello" for i in range(60)
)
ERRORI = (
    "Traceback (most recent call last):\n"
    '  File "core/x.py", line 12, in <module>\n'
    "ERRORE: la chiave 'target' manca nel dizionario\n"
    "FAILED tests/test_x.py::test_y - AssertionError: 3 != 4\n"
)
OSSERVAZIONE = f"terminale: pytest -q\n{RUMORE}\n{ERRORI}\n{RUMORE}"


class TestComprimiTesto:
    def test_gli_errori_sopravvivono_tutti(self):
        compresso, risparmio = comprimi_testo(OSSERVAZIONE, 800)
        assert risparmio > 0, "non ha compresso niente"
        for riga in ERRORI.strip().splitlines():
            assert riga in compresso, f"persa la riga: {riga}"

    def test_dice_quante_righe_ha_omesso(self):
        compresso, _ = comprimi_testo(OSSERVAZIONE, 800)
        assert "righe omesse" in compresso, (
            "le righe tolte devono essere dichiarate: un'omissione silenziosa "
            "si legge come un output completo"
        )
        assert len(compresso) < len(OSSERVAZIONE)

    def test_un_testo_corto_non_si_tocca(self):
        breve = "output breve\nsenza niente da comprimere"
        assert comprimi_testo(breve, 10) == (breve, 0)

    def test_sotto_la_soglia_non_si_tocca(self):
        medio = ("riga\n" * 40)[:MINIMO_COMPRIMIBILE - 1]
        assert comprimi_testo(medio, 50)[1] == 0

    def test_un_testo_fatto_di_soli_errori_non_si_comprime(self):
        """Se ogni riga e' un'ancora non c'e' niente da buttare, e non si finge."""
        tutto_errori = "\n".join(f"ERRORE riga {i}" for i in range(80))
        compresso, risparmio = comprimi_testo(tutto_errori, 100)
        assert risparmio == 0, "ha omesso righe che erano tutte segnalazioni"
        assert compresso == tutto_errori

    def test_le_righe_di_diff_sono_ancore(self):
        corpo = "\n".join(f"contesto {i}" for i in range(50))
        diff = "--- a/f.py\n+++ b/f.py\n-    vecchia_riga()\n+    nuova_riga()\n"
        compresso, risparmio = comprimi_testo(f"{corpo}\n{diff}\n{corpo}", 600)
        assert risparmio > 0
        assert "+    nuova_riga()" in compresso


class TestComprimiOsservazioni:
    def test_sotto_budget_non_tocca_nulla(self):
        messaggi = [{"role": "user", "content": OSSERVAZIONE}]
        uguali, risparmio = comprimi_osservazioni(messaggi, 100_000)
        assert risparmio == 0
        assert uguali[0]["content"] == OSSERVAZIONE

    def test_comprime_il_piu_grosso_e_lascia_stare_il_resto(self):
        piccolo = {"role": "user", "content": "nota breve"}
        messaggi = [piccolo, {"role": "user", "content": OSSERVAZIONE}]
        dopo, risparmio = comprimi_osservazioni(messaggi, len(piccolo["content"]) + 900)
        assert risparmio > 0
        assert dopo[0] == piccolo, "ha toccato il messaggio che non era il problema"
        totale = sum(len(m["content"]) for m in dopo)
        assert totale <= len(piccolo["content"]) + 900


class TestIlTurnoNonSiSfratta:
    def _storia(self):
        return [
            {"role": "system", "content": "Sei l'agente."},
            {"role": "user", "content": "Sistema il test che fallisce."},
            {"role": "assistant", "content": "Eseguo la suite."},
            {"role": "user", "content": OSSERVAZIONE},
            {"role": "assistant", "content": "Correggo x.py."},
        ]

    def test_con_la_compressione_nessun_turno_esce(self):
        storia = self._storia()
        budget = 2000
        assert sum(len(m["content"]) for m in storia[2:]) > budget, (
            "la prova non prova niente: senza compressione la finestra stava dentro"
        )
        dopo = compact_history_with_memory(list(storia), None, max_history_chars=budget)
        assert len(dopo) == len(storia), (
            f"un turno e' stato sfrattato comunque: {len(dopo)} messaggi invece di "
            f"{len(storia)}"
        )
        testo = "\n".join(m["content"] for m in dopo)
        assert "AssertionError: 3 != 4" in testo, (
            "la prova del fallimento e' andata persa nella compressione: l'agente "
            "non sapra' piu' cosa stava correggendo"
        )

    def test_quando_comprimere_non_basta_si_sfratta_comunque(self):
        """Il secondo stadio resta: due osservazioni enormi non stanno in un budget."""
        enorme = "\n".join(f"riga {i} " + "x" * 200 for i in range(600))
        storia = [
            {"role": "system", "content": "Sei l'agente."},
            {"role": "user", "content": "Obiettivo."},
            {"role": "assistant", "content": enorme},
            {"role": "user", "content": enorme},
        ]
        dopo = compact_history_with_memory(list(storia), None, max_history_chars=1500)
        assert len(dopo) < len(storia), "non ha sfrattato niente e la finestra e' piena"
