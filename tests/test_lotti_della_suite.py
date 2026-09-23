"""Ogni file di prova appartiene a un lotto, e i lotti esistono davvero.

Un lotto a cui non appartiene nessun file e' un comando che non esegue niente;
un file che non appartiene a nessun lotto sono prove che nessuno esegue mai.
Sono due modi di perdere la rete di sicurezza senza che si veda, ed e' il motivo
per cui questo controllo esiste: dice quanti file ha esaminato, perche' un
controllo verde che non ha guardato niente e' verde come uno che ha guardato
tutto senza trovare nulla.
"""

from pathlib import Path

from tests.lotti import (LENTI, LENTI_PER_CLASSE, LOTTI, e_lento, lotto_di,
                         nome_di, tutti_i_file)

CARTELLA = Path(__file__).resolve().parent


def _file_di_prova():
    return sorted(p for p in CARTELLA.glob("test_*.py"))


def _righe_dei_lotti():
    """La tabella dei lotti, per chi legge l'output di una corsa fallita."""
    righe = []
    for lotto, file_del_lotto in LOTTI.items():
        presenti = [f for f in file_del_lotto
                    if (CARTELLA / ("test_%s.py" % f)).exists()]
        righe.append("%-8s %3d file  (%d mancanti)" % (lotto, len(presenti),
                                                       len(file_del_lotto) - len(presenti)))
    return righe


def test_ogni_file_di_prova_ha_il_suo_lotto():
    file_di_prova = _file_di_prova()
    assert file_di_prova, "nessun file di prova trovato: il controllo non ha guardato niente"
    print("\nlotti:")
    for riga in _righe_dei_lotti():
        print("   " + riga)
    print("   totale file di prova: %d | file in un lotto: %d"
          % (len(file_di_prova), len(tutti_i_file())))
    senza = [p.name for p in file_di_prova if lotto_di(p) is None]
    assert not senza, (
        "questi file non appartengono a nessun lotto, quindi nessun comando li "
        "esegue: %s. Aggiungerli a LOTTI in tests/lotti.py." % ", ".join(senza))


def test_nessun_file_sta_in_due_lotti():
    visti = {}
    doppi = []
    for lotto, file_del_lotto in LOTTI.items():
        for f in file_del_lotto:
            if f in visti:
                doppi.append("%s (%s e %s)" % (f, visti[f], lotto))
            visti[f] = lotto
    assert not doppi, "file in due lotti: %s" % ", ".join(doppi)


def test_ogni_lotto_ha_almeno_un_file_che_esiste():
    """Un lotto senza file e' un comando che non esegue niente."""
    vuoti = [lotto for lotto, file_del_lotto in LOTTI.items()
             if not any((CARTELLA / ("test_%s.py" % f)).exists()
                        for f in file_del_lotto)]
    assert not vuoti, "lotti senza file esistenti: %s" % ", ".join(vuoti)


def test_i_file_assegnati_esistono_tutti():
    """Un nome scritto male nella mappa non fa rumore: qui lo fa."""
    mancanti = [f for f in tutti_i_file()
                if not (CARTELLA / ("test_%s.py" % f)).exists()]
    assert not mancanti, (
        "in tests/lotti.py ci sono nomi che non hanno un file: %s"
        % ", ".join(mancanti))


def test_le_prove_lente_esistono_ancora():
    """Se una regola non trova piu' niente, il marcatore tace e nessuno se ne accorge."""
    for nome in LENTI:
        assert (CARTELLA / ("test_%s.py" % nome)).exists(), (
            "il file lento dichiarato non esiste: test_%s.py" % nome)

    contenuto = (CARTELLA / "test_objective_inference.py").read_text(encoding="utf-8")
    trovate = sum(1 for classe in LENTI_PER_CLASSE if "class %s" % classe in contenuto)
    assert trovate == len(LENTI_PER_CLASSE), (
        "una classe dichiarata lenta non esiste piu' in test_objective_inference.py: "
        "il marcatore non la troverebbe, e il file resterebbe escluso senza motivo")


def test_il_lotto_di_un_file_si_calcola_dalle_regole():
    """La regola, provata su tre nomi che contano."""
    assert lotto_di(CARTELLA / "test_mcp_fs_server.py") == "mcp"
    assert lotto_di(CARTELLA / "test_fanout.py") == "harness"
    assert lotto_di("percorso/assoluto/test_indice_fresco.py") == "harness"
    assert nome_di("test_indice_fresco.py") == "indice_fresco"
    assert not e_lento("tests/test_fanout.py::TestX::test_y")
    assert e_lento("tests/test_backend_parity.py::TestX::test_y")
    assert e_lento("tests/test_objective_inference.py::"
                   "TestBatchedGenerationAgainstRealModel::test_y")
