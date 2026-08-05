# ==============================================================================
# tests/test_endpoints_parallelo.py — Quando conviene usare piu' schede
# ==============================================================================
"""Copre la decisione sul parallelismo in core/training/endpoints.py.

Avere due GPU non basta a rendere parallelo un benchmark: serve che il modello
stia nella scheda in piu', che quella scheda sia libera, e che il run sia
abbastanza lungo da ripagare i venti secondi di avvio del secondo servitore.
Sbagliare la decisione non da' un errore — da' un run piu' lento di prima, o
un modello che pagina, cioe' esattamente il contrario di quel che si voleva.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.training import endpoints as ep


@pytest.fixture
def macchina(monkeypatch):
    """Sostituisce hardware, catalogo e servitori attivi."""
    def configura(schede=(), peso=0.0, attivi=()):
        monkeypatch.setattr("core.training.capacity.cuda_devices", lambda: list(schede))
        monkeypatch.setattr(ep, "_peso_modello_gb", lambda m: peso)
        monkeypatch.setattr(ep, "active_endpoints",
                            lambda refresh=True: [{"url": u, "healthy": True} for u in attivi])
    return configura


def scheda(index, nome, libera):
    return {"index": index, "name": nome, "backend": "cuda",
            "vram_total_gb": libera + 1, "vram_free_gb": libera}


def test_una_scheda_sola_non_si_parallelizza(macchina):
    macchina(schede=[scheda(0, "RTX 5070 Ti", 15.0)], peso=0.5)
    v = ep.valuta_parallelo("m:latest", 300)
    assert not v["parallelo"] and "una sola scheda" in v["motivo"]


def test_due_schede_e_modello_piccolo_si_parallelizza(macchina):
    macchina(schede=[scheda(0, "RTX 5070 Ti", 15.0), scheda(1, "RTX 5060", 7.7)], peso=0.5)
    v = ep.valuta_parallelo("m:latest", 300)
    assert v["parallelo"] and v["gpu"]["index"] == 1


def test_un_modello_che_non_ci_sta_resta_su_una_scheda(macchina):
    """Caricarlo comunque significherebbe farlo paginare: piu' lento, non meno."""
    macchina(schede=[scheda(0, "RTX 5070 Ti", 15.0), scheda(1, "RTX 5060", 7.7)], peso=40.0)
    v = ep.valuta_parallelo("grosso:70b", 300)
    assert not v["parallelo"]
    assert "non li hanno" in v["motivo"] and "RTX 5060" in v["motivo"]


def test_il_margine_copre_contesto_e_cache(macchina):
    """Il peso dei pesi non e' quanto occupa: contesto e cache KV stanno sopra.
    Un modello che entra al millimetro non entra."""
    macchina(schede=[scheda(0, "A", 15.0), scheda(1, "B", 8.0)], peso=7.0)
    assert not ep.valuta_parallelo("giusto:7b", 300)["parallelo"], \
        "7 GB di pesi su 8 GB liberi: senza margine si pagina"
    macchina(schede=[scheda(0, "A", 15.0), scheda(1, "B", 8.0)], peso=5.0)
    assert ep.valuta_parallelo("comodo:5b", 300)["parallelo"]


def test_un_run_corto_non_ripaga_l_avvio(macchina):
    macchina(schede=[scheda(0, "A", 15.0), scheda(1, "B", 7.7)], peso=0.5)
    v = ep.valuta_parallelo("m:latest", 10)
    assert not v["parallelo"] and "costerebbe" in v["motivo"]


def test_un_peso_sconosciuto_non_si_indovina(macchina):
    """Senza sapere quanto occupa, avviarlo sulla scheda piccola e' una scommessa."""
    macchina(schede=[scheda(0, "A", 15.0), scheda(1, "B", 7.7)], peso=0.0)
    v = ep.valuta_parallelo("mai-visto:1b", 300)
    assert not v["parallelo"] and "sconosciuto" in v["motivo"]


def test_se_i_servitori_ci_sono_gia_non_se_ne_avviano_altri(macchina):
    macchina(schede=[scheda(0, "A", 15.0), scheda(1, "B", 7.7)], peso=0.5,
             attivi=("http://127.0.0.1:11434", "http://127.0.0.1:11435"))
    v = ep.valuta_parallelo("m:latest", 300)
    assert v["parallelo"] and v["gia_pronto"]


def test_ogni_verdetto_porta_una_spiegazione(macchina):
    """E' quella che finisce nel diario: senza, la seconda scheda ferma sembra
    una svista invece di una scelta."""
    for schede, peso, quesiti in (
        ([scheda(0, "A", 15.0)], 0.5, 300),
        ([scheda(0, "A", 15.0), scheda(1, "B", 7.7)], 40.0, 300),
        ([scheda(0, "A", 15.0), scheda(1, "B", 7.7)], 0.5, 5),
        ([scheda(0, "A", 15.0), scheda(1, "B", 7.7)], 0.5, 300),
    ):
        macchina(schede=schede, peso=peso)
        v = ep.valuta_parallelo("m:latest", quesiti)
        assert v["motivo"].strip(), "un verdetto senza motivo non aiuta nessuno"


def test_un_avvio_fallito_non_ferma_il_benchmark(macchina, monkeypatch):
    """Non riuscire ad andare piu' veloce non e' un motivo per non partire."""
    macchina(schede=[scheda(0, "A", 15.0), scheda(1, "B", 7.7)], peso=0.5)
    monkeypatch.setattr(ep, "start_instance",
                        lambda idx, **k: {"success": False, "error": "porta occupata"})
    out = ep.prepara_parallelo("m:latest", 300)
    assert not out["parallelo"] and not out["avviato"]
    assert "porta occupata" in out["motivo"]


# ==============================================================================
# COME SI DIVIDE IL LAVORO FRA SCHEDE DIVERSE
# ==============================================================================

def test_a_parita_di_coda_vince_il_primo():
    """Con una scheda sola il comportamento non deve cambiare."""
    pool = ep.EndpointPool(["http://a", "http://b"])
    assert pool.next() == "http://a"


def test_chi_ha_meno_lavoro_riceve_il_prossimo():
    """Il giro in tondo presuppone schede uguali. Con una 5070 Ti e una 5060,
    alternare significa dare meta' del lavoro alla scheda lenta: la veloce
    finisce e aspetta. Misurato su 48 richieste a un modello da 4B: in tondo
    1,15x, a coda piu' corta 1,42x."""
    pool = ep.EndpointPool(["http://veloce", "http://lento"])
    with pool.lease() as primo:
        assert primo == "http://veloce"
        with pool.lease() as secondo:
            assert secondo == "http://lento", "il secondo va dove non c'e' coda"
            with pool.lease() as terzo:
                assert terzo in ("http://veloce", "http://lento")
    # Tutto rilasciato: si riparte dal primo.
    assert pool.next() == "http://veloce"


def test_una_richiesta_esplosa_non_spegne_la_scheda():
    """Se il conteggio non si rilascia, quell'endpoint sembra occupato per
    sempre e smette di ricevere lavoro: un errore di rete basterebbe a
    spegnere una scheda per il resto del run."""
    pool = ep.EndpointPool(["http://a", "http://b"])
    with pytest.raises(ValueError):
        with pool.lease() as url:
            assert url == "http://a"
            raise ValueError("rete giu'")
    assert pool.next() == "http://a", "il posto e' stato liberato"


def test_il_lavoro_si_distribuisce_su_tutte_le_schede():
    pool = ep.EndpointPool(["http://a", "http://b", "http://c"])
    import contextlib
    with contextlib.ExitStack() as stack:
        presi = [stack.enter_context(pool.lease()) for _ in range(3)]
    assert sorted(presi) == ["http://a", "http://b", "http://c"]
