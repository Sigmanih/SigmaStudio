"""Un prefisso KV per ruolo, invece di uno solo per tutti.

Con un unico slot, un harness che alterna Architect e Coder sullo stesso
modello ottiene il caso peggiore: ogni cambio di ruolo sfratta il prefisso
dell'altro, e alternandoli non si riusa mai niente — proprio quando la cache
servirebbe di piu'. Gli slot lo risolvono, ma introducono due modi di
sbagliare che questi test fissano: sfrattare quello sbagliato, e riusare il KV
di un modello che nel frattempo e' cambiato.
"""

import pytest

from core.engine.prefix_cache import (
    MIN_REUSABLE_TOKENS,
    PrefixKVCache,
)

MODELLO = "qwen3-8b"


class CacheFinta:
    """Un KV cache quanto basta: sa dire dov'e' stato tagliato."""

    def __init__(self, nome="kv"):
        self.nome = nome
        self.cropped_to = None

    def crop(self, n):
        self.cropped_to = n


def _ids(n, seme=0):
    return [seme + i for i in range(n)]


@pytest.fixture
def cache():
    c = PrefixKVCache(max_tokens=0, max_slots=2)
    c.configure(MODELLO, 0)
    return c


class TestSlotIndipendenti:
    def test_due_ruoli_conservano_ciascuno_il_proprio_prefisso(self):
        """Il punto dell'intero modulo, in un test."""
        c = PrefixKVCache(max_slots=2)
        c.configure(MODELLO, 0)
        architect = _ids(200, seme=1000)
        coder = _ids(200, seme=5000)

        c.store(architect, CacheFinta("a"), MODELLO, slot="role:architect")
        c.store(coder, CacheFinta("c"), MODELLO, slot="role:coder")

        kv_a, n_a = c.take(architect + [999], MODELLO, slot="role:architect")
        assert kv_a is not None and n_a == 200
        kv_c, n_c = c.take(coder + [999], MODELLO, slot="role:coder")
        assert kv_c is not None and n_c == 200

    def test_uno_slot_non_risponde_per_un_altro(self):
        """Prefissi diversi: restituire quello sbagliato corromperebbe la risposta."""
        c = PrefixKVCache(max_slots=2)
        c.configure(MODELLO, 0)
        c.store(_ids(200, seme=1000), CacheFinta(), MODELLO, slot="role:architect")

        kv, n = c.take(_ids(200, seme=5000), MODELLO, slot="role:coder")
        assert kv is None and n == 0

    def test_lo_slot_assente_e_una_mancanza_non_un_errore(self, cache):
        assert cache.take(_ids(200), MODELLO, slot="mai_visto") == (None, 0)


class TestSfratto:
    def test_oltre_il_tetto_si_sfratta_il_meno_recente(self):
        c = PrefixKVCache(max_slots=2)
        c.configure(MODELLO, 0)
        for nome, seme in (("a", 1000), ("b", 2000), ("c", 3000)):
            c.store(_ids(200, seme=seme), CacheFinta(nome), MODELLO, slot=nome)

        assert c.take(_ids(200, seme=1000) + [1], MODELLO, slot="a") == (None, 0)
        assert c.take(_ids(200, seme=3000) + [1], MODELLO, slot="c")[0] is not None
        assert c.stats()["evictions"] == 1

    def test_usare_uno_slot_lo_rende_recente(self):
        """Chi lavora non deve essere sfrattato prima di chi e' fermo."""
        c = PrefixKVCache(max_slots=2)
        c.configure(MODELLO, 0)
        c.store(_ids(200, seme=1000), CacheFinta("a"), MODELLO, slot="a")
        c.store(_ids(200, seme=2000), CacheFinta("b"), MODELLO, slot="b")

        # 'a' viene usato e rimesso: ora il piu' vecchio e' 'b'
        c.take(_ids(200, seme=1000) + [1], MODELLO, slot="a")
        c.store(_ids(200, seme=1000), CacheFinta("a2"), MODELLO, slot="a")
        c.store(_ids(200, seme=3000), CacheFinta("c"), MODELLO, slot="c")

        assert c.take(_ids(200, seme=1000) + [1], MODELLO, slot="a")[0] is not None
        assert c.take(_ids(200, seme=2000) + [1], MODELLO, slot="b") == (None, 0)

    def test_il_tetto_si_rispetta_anche_con_un_solo_slot(self):
        c = PrefixKVCache(max_slots=1)
        c.configure(MODELLO, 0)
        c.store(_ids(200, seme=1000), CacheFinta(), MODELLO, slot="a")
        c.store(_ids(200, seme=2000), CacheFinta(), MODELLO, slot="b")
        assert c.stats()["slots_used"] == 1


class TestCoerenzaColModello:
    def test_cambiare_modello_invalida_ogni_slot(self, cache):
        """Un KV nato da altri pesi non e' lento da riusare: e' sbagliato."""
        cache.store(_ids(200), CacheFinta(), MODELLO, slot="a")
        cache.configure("qwen-coder-2.5", 0)
        assert cache.take(_ids(200) + [1], "qwen-coder-2.5", slot="a") == (None, 0)

    def test_un_modello_diverso_nella_take_non_risponde(self, cache):
        cache.store(_ids(200), CacheFinta(), MODELLO, slot="a")
        assert cache.take(_ids(200) + [1], "altro-modello", slot="a") == (None, 0)

    def test_uno_store_con_modello_nuovo_ripulisce_i_vecchi(self, cache):
        cache.store(_ids(200, seme=1), CacheFinta(), MODELLO, slot="a")
        cache.store(_ids(200, seme=2), CacheFinta(), "modello-nuovo", slot="b")
        assert cache.take(_ids(200, seme=1) + [1], "modello-nuovo", slot="a") == (None, 0)
        assert cache.stats()["slots_used"] == 1


class TestSogliaDiRiuso:
    def test_un_prefisso_troppo_corto_non_vale_la_pena(self, cache):
        corto = _ids(MIN_REUSABLE_TOKENS - 10)
        cache.store(corto, CacheFinta(), MODELLO, slot="a")
        assert cache.take(corto + [1], MODELLO, slot="a") == (None, 0)

    def test_la_cache_non_copre_mai_tutto_il_prompt(self, cache):
        """Serve almeno un token da elaborare, o generate() non ha nulla da fare."""
        ids = _ids(200)
        cache.store(ids, CacheFinta(), MODELLO, slot="a")
        kv, n = cache.take(ids, MODELLO, slot="a")
        assert n == len(ids) - 1
        assert kv.cropped_to == len(ids) - 1

    def test_una_cache_senza_crop_ricade_sul_prefill_completo(self, cache):
        class SenzaCrop:
            def crop(self, n):
                raise NotImplementedError

        cache.store(_ids(200), SenzaCrop(), MODELLO, slot="a")
        assert cache.take(_ids(200) + [1], MODELLO, slot="a") == (None, 0)


class TestCompatibilita:
    def test_chi_non_chiede_uno_slot_ne_ottiene_uno_solo(self, cache):
        """La chat normale non sa nulla di slot e deve continuare a funzionare."""
        ids = _ids(200)
        cache.store(ids, CacheFinta(), MODELLO)
        kv, n = cache.take(ids + [1], MODELLO)
        assert kv is not None and n == 200

    def test_le_statistiche_dicono_quanti_slot_sono_in_uso(self, cache):
        cache.store(_ids(200, seme=1), CacheFinta(), MODELLO, slot="a")
        cache.store(_ids(300, seme=2), CacheFinta(), MODELLO, slot="b")
        st = cache.stats()
        assert st["slots_used"] == 2
        assert st["cached_tokens"] == 500
        assert set(st["slots"]) == {"a", "b"}
