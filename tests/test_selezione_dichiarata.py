"""Il contesto che non entra si sceglie: non si taglia a metà.

Il quarto passo del budget della chat usava `testo[:chars_avail]`. In Python una
fetta non spezza il carattere, ma spezza la riga e la parola: la frase resta
monca e una sequenza che appartiene a una lettera — un accento scritto come segno
combinante, che nei testi dei modelli capita — viene separata dal resto.

La regola che sostituisce quel taglio sta in `chat_runner._taglia_a_confine`:
scendere all'ultimo confine di riga, o all'ultima parola intera se la riga e'
una sola, e **dire** quanti caratteri restano fuori. Qui si verifica la regola e
l'aritmetica che la accompagna, perche' un contesto ridotto senza avviso viene
trattato come completo — e quella e' la parte che fa danni.

Si verifica: che non si fermi a meta' riga ne' a meta' parola, che l'aritmetica
torni (entrato + escluso = totale), che sotto il limite non tolga niente, e che
sotto zero non restituisca testo.
"""

from core.chat.chat_runner import _taglia_a_confine


class TestIlTaglioSaDoveFermarsi:
    def test_scende_all_ultima_riga_intera(self):
        testo = "una\n" * 10
        tagliato, esclusi = _taglia_a_confine(testo, 15)
        assert tagliato == "una\nuna\nuna", repr(tagliato)
        assert not tagliato.endswith("un"), "riga monca"
        assert len(tagliato) + esclusi == len(testo)

    def test_una_riga_sola_scende_all_ultima_parola(self):
        testo = "parola " * 10
        tagliato, esclusi = _taglia_a_confine(testo, 20)
        assert tagliato == "parola parola", repr(tagliato)
        assert not tagliato.endswith("par"), "parola monca"
        assert len(tagliato) + esclusi == len(testo)

    def test_sotto_il_limite_non_toglie_niente(self):
        testo = "breve riga"
        tagliato, esclusi = _taglia_a_confine(testo, 500)
        assert tagliato == testo
        assert esclusi == 0

    def test_l_aritmetica_torna_sempre(self):
        for testo in ("una riga sola molto lunga senza a capi", "a\nb\nc\nd\ne\nf\n",
                      "", "x"):
            for limite in (0, 1, 5, 12, 40):
                tagliato, esclusi = _taglia_a_confine(testo, limite)
                assert len(tagliato) + esclusi == len(testo), (testo, limite)
                assert len(tagliato) <= max(limite, 0), (testo, limite)

    def test_sotto_zero_non_restituisce_testo(self):
        tagliato, esclusi = _taglia_a_confine("qualcosa", 0)
        assert tagliato == ""
        assert esclusi == len("qualcosa")

    def test_un_accento_combinante_resta_attaccato_alla_sua_lettera(self):
        """Il caso che il taglio a meta' riga poteva rovinare.

        `é` come `e` + segno combinante: se il taglio cade fra i due, la lettera
        resta senza accento e il segno compare da solo. Fermi a un confine di
        parola, i due restano insieme.
        """
        parola = "perche\u0301"
        testo = (parola + " ") * 12
        tagliato, _ = _taglia_a_confine(testo, 20)
        assert "\u0301" not in tagliato.replace(parola, ""), repr(tagliato)
