"""Controllo del parlato parola per parola: parole rovinate da sintesi o conversione vocale."""

from core.modules.sigma_creative_lab.video import speech_qa


def _w(word, start, end, p):
    return {"word": word, "start": start, "end": end, "p": p}


ORIGINALE = [_w("La", 1.44, 1.88, 0.99), _w("luce", 1.88, 2.30, 1.0), _w("vi", 2.30, 2.56, 1.0),
             _w("guiderà", 2.56, 3.22, 0.99), _w("fino", 3.22, 3.62, 1.0)]


def test_parola_rovinata_dalla_conversione():
    # Il caso reale del faro: dopo la conversione "guiderà" scende da 0,99 a 0,66.
    convertito = [_w("La", 1.44, 1.86, 1.0), _w("luce", 1.86, 2.28, 1.0), _w("vi", 2.28, 2.52, 1.0),
                  _w("guiderà", 2.52, 3.20, 0.66), _w("fino", 3.20, 3.60, 1.0)]
    bad = speech_qa.damaged_words(convertito, ORIGINALE)
    assert [w["word"] for w in bad] == ["guiderà"] and bad[0]["ref_p"] == 0.99


def test_parola_gia_incerta_all_origine_non_e_colpa_della_conversione():
    originale = [_w("Cinzia", 0.0, 0.5, 0.62)]
    assert speech_qa.damaged_words([_w("Cinzia", 0.0, 0.5, 0.60)], originale) == []
    # Senza riferimento conta solo la soglia assoluta.
    assert len(speech_qa.damaged_words([_w("Cinzia", 0.0, 0.5, 0.60)])) == 1


def test_tratti_con_margine_e_uniti_se_vicini():
    bad = [_w("a", 1.0, 1.2, 0.5), _w("b", 1.3, 1.5, 0.5), _w("c", 3.0, 3.2, 0.5)]
    assert speech_qa.regions(bad, pad=0.05, merge_gap=0.12) == [[0.95, 1.55], [2.95, 3.25]]


def test_ordine_fra_tentativi():
    pulito = [_w("x", 0, 1, 0.97)]
    rovinato = [_w("x", 0, 1, 0.5)]
    assert speech_qa.rank(pulito, []) > speech_qa.rank(rovinato, speech_qa.damaged_words(rovinato))


def test_punteggiatura_ignorata():
    assert speech_qa.damaged_words([_w("!", 0, 0.1, 0.1), _w("...", 0.1, 0.2, 0.2)]) == []
