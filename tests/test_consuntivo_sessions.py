"""Il consuntivo che mancava: quante sessioni rendono, e a che prezzo.

Per rispondere a "a che punto siamo" bisognava aprire a mano i ledger in
`var/dev_sessions/`: centottantasei file. Il resoconto di un run racconta un run,
e la domanda vera e un altra ? su cento sessioni, quante hanno prodotto
qualcosa, quanto e costato, e quale modello rende.

Il controllo dichiara quanti elementi ha esaminato, e conta come problemi solo i
file che non e riuscito a leggere: un buco nei dati (una sessione senza modello,
una con turni e zero token) si dice ma non fa fallire il controllo, perche non e
un difetto di chi misura.
"""

import importlib.util
import json
from pathlib import Path


def _modulo():
    """Il consuntivo, caricato per percorso: `tools/` non e un pacchetto."""
    percorso = Path(__file__).resolve().parent.parent / "tools" / "consuntivo_sessions.py"
    spec = importlib.util.spec_from_file_location("consuntivo_sessions", percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


CONSUNTIVO = _modulo()


def _sessione(path, nome, modello, turni, scritture, chiamate, falliti, generati=0, contesto=0):
    dati = {
        "session_id": nome,
        "model": modello,
        "status": "stopped",
        "updated_at": 1000.0,
        "metrics": {
            "turns": turni, "tool_calls": chiamate, "tool_failures": falliti,
            "generated_tokens": generati, "prompt_tokens": contesto,
            "started_at": 800.0,
        },
        "ledger": {
            "files": [{"path": "a.py", "writes": 1}] * scritture,
            "requirements": [{"id": "1", "met": True}],
        },
    }
    (path / (nome + ".json")).write_text(json.dumps(dati), encoding="utf-8")


class TestINumeri:
    def test_la_media_di_un_gruppo(self):
        righe = [
            {"turni": 10, "chiamate": 10, "fallimenti": 1, "generati": 100,
             "durata_s": 50.0, "scritti": 2, "contesto": 5000, "riusati": 0},
            {"turni": 20, "chiamate": 10, "fallimenti": 3, "generati": 300,
             "durata_s": 150.0, "scritti": 0, "contesto": 3000, "riusati": 0},
        ]
        r = CONSUNTIVO.riassunto(righe)
        assert r["sessioni"] == 2
        assert r["turni_medi"] == 15.0 and r["turni_max"] == 20
        assert r["senza_scritture_pct"] == 50
        assert r["fallimenti_pct"] == 20.0
        assert r["tok_s"] == 2.0
        # Il contesto e per turno: 5000/10 e 3000/20, media 325. Un totale
        # per sessione non dice quanto costa un turno, che e la domanda.
        assert r["contesto_medio"] == 325

    def test_un_gruppo_vuoto_non_divide_per_zero(self):
        r = CONSUNTIVO.riassunto([])
        assert r["sessioni"] == 0 and r["tok_s"] == 0.0

    def test_una_sessione_si_legge_dal_file(self, tmp_path):
        _sessione(tmp_path, "s1", "modello-a", 12, 2, 12, 1, generati=1200, contesto=48000)
        voce = CONSUNTIVO.carica_sessione(tmp_path / "s1.json")
        assert voce["model"] == "modello-a"
        assert voce["turni"] == 12 and voce["scritti"] == 2
        assert voce["durata_s"] == 200.0

    def test_un_file_rotto_e_un_errore_non_un_crash(self, tmp_path):
        (tmp_path / "rotto.json").write_text("{non-json", encoding="utf-8")
        voce = CONSUNTIVO.carica_sessione(tmp_path / "rotto.json")
        assert "errore" in voce


class TestIlControllo:
    def test_una_cartella_pulita_esce_zero(self, tmp_path, capsys):
        _sessione(tmp_path, "s1", "modello-a", 10, 1, 10, 0, generati=500)
        _sessione(tmp_path, "s2", "modello-a", 5, 0, 5, 1)
        codice = CONSUNTIVO.main(["--dir", str(tmp_path)])
        uscita = capsys.readouterr().out
        assert codice == 0
        assert "SIGMA-CHECK" in uscita
        assert '"checked": 2' in uscita and '"problems": 0' in uscita

    def test_il_conteggio_delle_vuote_si_vede(self, tmp_path, capsys):
        _sessione(tmp_path, "s1", "modello-a", 10, 1, 10, 0)
        _sessione(tmp_path, "s2", "modello-a", 5, 0, 5, 0)
        CONSUNTIVO.main(["--dir", str(tmp_path)])
        uscita = capsys.readouterr().out
        assert "TUTTE" in uscita
        assert "50%" in uscita, uscita

    def test_un_file_illeggibile_e_un_problema(self, tmp_path, capsys):
        _sessione(tmp_path, "s1", "modello-a", 10, 1, 10, 0)
        (tmp_path / "rotto.json").write_text("{rotto", encoding="utf-8")
        codice = CONSUNTIVO.main(["--dir", str(tmp_path)])
        uscita = capsys.readouterr().out
        assert codice == 1
        assert "PROBLEMA" in uscita
        assert '"checked": 2' in uscita and '"problems": 1' in uscita

    def test_una_cartella_assente_non_finge_di_aver_guardato(self, tmp_path, capsys):
        codice = CONSUNTIVO.main(["--dir", str(tmp_path / "assente")])
        uscita = capsys.readouterr().out
        assert codice == 1
        assert '"checked": 0' in uscita and '"problems": 1' in uscita

    def test_un_buco_nei_dati_si_dice_e_non_fa_fallire(self, tmp_path, capsys):
        _sessione(tmp_path, "s1", "", 10, 1, 10, 0, generati=0)
        codice = CONSUNTIVO.main(["--dir", str(tmp_path)])
        uscita = capsys.readouterr().out
        assert codice == 0
        assert "Buchi nella misura" in uscita
        assert "(modello non registrato)" in uscita

    def test_le_peggiori_si_elencano(self, tmp_path, capsys):
        _sessione(tmp_path, "s1", "m", 30, 0, 30, 0)
        _sessione(tmp_path, "s2", "m", 5, 0, 5, 0)
        CONSUNTIVO.main(["--dir", str(tmp_path)])
        uscita = capsys.readouterr().out
        assert "senza scrivere un file" in uscita
        assert uscita.index("s1") < uscita.index("s2")

