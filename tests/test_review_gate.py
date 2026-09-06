"""Una modifica dell'agente resta solo se qualcuno la conferma.

Finora l'agente scriveva e poi raccontava cosa aveva scritto. Su un run
autonomo — trenta turni, decine di scritture — questo significa che la prima
occasione per accorgersi di un errore arriva quando l'errore e' gia' sul disco,
e su un repository non proprio significa che non arriva affatto.

Il gate rovescia l'ordine: la modifica viene mostrata con il suo diff, il run si
ferma, e cio' che non viene approvato torna com'era. I test qui sotto tengono
ferme le tre proprieta' che lo rendono una garanzia invece di una formalita':

1. il diff mostrato e' quello vero;
2. un rifiuto riporta il file esattamente allo stato precedente, anche quando
   il file prima non esisteva;
3. il silenzio non vale come approvazione.
"""

import os
import threading
import time

import pytest

from core.harness import review
from core.harness.review import APPROVED, REJECTED, TIMEOUT, FileSnapshot, ReviewGate


# ---------------------------------------------------------------------------
# Il prima e il dopo
# ---------------------------------------------------------------------------


class TestIstantanea:
    def test_il_diff_e_quello_vero(self, tmp_path):
        f = tmp_path / "modulo.py"
        f.write_text("def somma(a, b):\n    return a + b\n", encoding="utf-8")
        istantanea = FileSnapshot.take(str(f))

        f.write_text("def somma(a, b):\n    return a - b\n", encoding="utf-8")

        diff = istantanea.diff()
        assert "-    return a + b" in diff
        assert "+    return a - b" in diff

    def test_un_file_nuovo_si_annulla_cancellandolo(self, tmp_path):
        f = tmp_path / "inventato.py"
        istantanea = FileSnapshot.take(str(f))
        assert not istantanea.existed

        f.write_text("print('ciao')\n", encoding="utf-8")
        assert istantanea.revert() is True
        assert not f.exists()

    def test_un_file_esistente_torna_al_byte_precedente(self, tmp_path):
        f = tmp_path / "config.py"
        originale = "SOGLIA = 10\n"
        f.write_text(originale, encoding="utf-8")
        istantanea = FileSnapshot.take(str(f))

        f.write_text("SOGLIA = 0\n", encoding="utf-8")
        assert istantanea.revert() is True
        assert f.read_text(encoding="utf-8") == originale

    def test_annullare_ricrea_un_file_cancellato(self, tmp_path):
        """`delete` e' fra i tool sottoposti a revisione: il rifiuto deve rimetterlo."""
        f = tmp_path / "importante.py"
        f.write_text("VALORE = 42\n", encoding="utf-8")
        istantanea = FileSnapshot.take(str(f))

        os.remove(str(f))
        assert istantanea.revert() is True
        assert f.read_text(encoding="utf-8") == "VALORE = 42\n"

    def test_un_diff_enorme_viene_troncato_ma_non_perde_l_inizio(self, tmp_path):
        f = tmp_path / "grande.txt"
        f.write_text("", encoding="utf-8")
        istantanea = FileSnapshot.take(str(f))
        f.write_text("\n".join("riga %d" % i for i in range(5000)), encoding="utf-8")

        diff = istantanea.diff(max_lines=50)
        assert "+riga 0" in diff
        assert "righe di diff omesse" in diff
        assert len(diff.splitlines()) < 60

    def test_un_file_binario_non_finge_un_diff(self, tmp_path):
        f = tmp_path / "immagine.bin"
        f.write_bytes(b"\x00\xff\xfe\x01binario")
        istantanea = FileSnapshot.take(str(f))
        assert istantanea.opaque
        assert "non testuale" in istantanea.diff()
        # E non prova ad annullare qualcosa che non sa ricostruire.
        assert istantanea.revert() is False

    def test_i_fine_riga_non_cambiano_annullando(self, tmp_path):
        """Un revert che normalizza i CRLF riscriverebbe il file di chi non ha chiesto niente."""
        f = tmp_path / "windows.txt"
        f.write_bytes(b"prima\r\nseconda\r\n")
        istantanea = FileSnapshot.take(str(f))

        f.write_bytes(b"stravolto\r\n")
        istantanea.revert()
        assert f.read_bytes() == b"prima\r\nseconda\r\n"


# ---------------------------------------------------------------------------
# La decisione
# ---------------------------------------------------------------------------


class TestGate:
    def test_approvare_sblocca_il_run(self):
        gate = ReviewGate(timeout_s=5.0)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")

        threading.Timer(0.05, lambda: gate.decide(scheda["id"], "approved")).start()
        assert gate.wait(scheda["id"]) == APPROVED

    def test_rifiutare_sblocca_il_run(self):
        gate = ReviewGate(timeout_s=5.0)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")

        threading.Timer(0.05, lambda: gate.decide(scheda["id"], "rejected")).start()
        assert gate.wait(scheda["id"]) == REJECTED

    def test_il_silenzio_non_e_un_si(self):
        """La proprieta' che rende il gate una garanzia: in assenza di risposta
        la modifica viene annullata, non applicata."""
        gate = ReviewGate(timeout_s=0.15)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")
        inizio = time.time()
        assert gate.wait(scheda["id"]) == TIMEOUT
        assert time.time() - inizio >= 0.1

    def test_l_attesa_si_ferma_davvero(self):
        """Senza il blocco, il gate sarebbe un evento decorativo."""
        gate = ReviewGate(timeout_s=5.0)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")

        threading.Timer(0.2, lambda: gate.decide(scheda["id"], "approved")).start()
        inizio = time.time()
        gate.wait(scheda["id"])
        assert time.time() - inizio >= 0.15

    def test_una_decisione_arrivata_prima_dell_attesa_non_si_perde(self):
        """Fra `open` e `wait` c'e' l'invio dell'evento: se l'utente e' rapido,
        la risposta puo' precedere l'attesa. Perderla bloccherebbe il run fino
        al timeout su una modifica gia' approvata."""
        gate = ReviewGate(timeout_s=5.0)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")
        gate.decide(scheda["id"], "approved")
        assert gate.wait(scheda["id"]) == APPROVED

    def test_decidere_su_una_proposta_ignota_non_ha_effetto(self):
        gate = ReviewGate(timeout_s=1.0)
        assert gate.decide("rev_inesistente", "approved") is False

    def test_attendere_una_proposta_mai_aperta_non_la_approva(self):
        gate = ReviewGate(timeout_s=1.0)
        assert gate.wait("rev_inesistente") == REJECTED

    def test_le_proposte_in_attesa_sono_elencabili(self):
        gate = ReviewGate(timeout_s=5.0)
        scheda = gate.open(path="core/a.py", diff="+x", tool="edit_file")
        elenco = gate.pending()
        assert [p["id"] for p in elenco] == [scheda["id"]]
        assert elenco[0]["path"] == "core/a.py"
        # L'elenco resta leggero: il diff si chiede a parte.
        assert "diff" not in elenco[0]
        assert gate.pending_detail(scheda["id"])["diff"] == "+x"

    def test_fermare_il_run_sblocca_le_attese(self):
        """Chi preme stop non deve aspettare cinque minuti che scada un'attesa."""
        gate = ReviewGate(timeout_s=30.0)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")
        esiti = []

        t = threading.Thread(target=lambda: esiti.append(gate.wait(scheda["id"])))
        t.start()
        time.sleep(0.05)
        gate.cancel_all("test")
        t.join(timeout=2.0)

        assert esiti == [REJECTED]

    def test_una_proposta_decisa_non_resta_in_attesa(self):
        gate = ReviewGate(timeout_s=5.0)
        scheda = gate.open(path="a.py", diff="+x", tool="write_file")
        gate.decide(scheda["id"], "approved")
        gate.wait(scheda["id"])
        assert gate.pending() == []


class TestRegistroPerSessione:
    """Chi decide arriva su un'altra richiesta HTTP: senza registro non
    troverebbe il thread da sbloccare."""

    def test_la_stessa_sessione_ritrova_il_suo_gate(self):
        try:
            uno = review.gate_for("sess-registro")
            due = review.gate_for("sess-registro")
            assert uno is due
        finally:
            review.release_gate("sess-registro")

    def test_sessioni_diverse_non_si_scambiano_le_proposte(self):
        try:
            a = review.gate_for("sess-a")
            b = review.gate_for("sess-b")
            scheda = a.open(path="x.py", diff="+x", tool="write_file")
            assert review.decide("sess-b", scheda["id"], "approved") is False
            assert review.decide("sess-a", scheda["id"], "approved") is True
        finally:
            review.release_gate("sess-a")
            review.release_gate("sess-b")

    def test_chiudere_la_sessione_sblocca_cio_che_resta(self):
        gate = review.gate_for("sess-chiusa")
        scheda = gate.open(path="x.py", diff="+x", tool="write_file")
        esiti = []
        t = threading.Thread(target=lambda: esiti.append(gate.wait(scheda["id"])))
        t.start()
        time.sleep(0.05)
        review.release_gate("sess-chiusa")
        t.join(timeout=2.0)
        assert esiti == [REJECTED]


class TestMessaggioDiRifiuto:
    def test_dice_all_agente_che_il_file_e_tornato_indietro(self):
        msg = review.rejection_message("core/a.py", REJECTED, reverted=True)
        assert "core/a.py" in msg
        assert "tornato com'era" in msg
        assert "Non riproporre la stessa identica modifica" in msg

    def test_avvisa_quando_l_annullamento_non_e_riuscito(self):
        """Tacere qui lascerebbe l'agente convinto che il disco sia pulito."""
        msg = review.rejection_message("core/a.py", REJECTED, reverted=False)
        assert "ATTENZIONE" in msg

    def test_distingue_il_rifiuto_dalla_scadenza(self):
        assert "tempo previsto" in review.rejection_message("a.py", TIMEOUT, True)
        assert "rifiutata" in review.rejection_message("a.py", REJECTED, True)


# ---------------------------------------------------------------------------
# Il ciclo dell'agente
# ---------------------------------------------------------------------------


def _finto_modello(risposte):
    """Un generatore che recita le risposte del modello, una per turno."""
    stato = {"turno": 0}

    def stream(**kwargs):
        i = min(stato["turno"], len(risposte) - 1)
        stato["turno"] += 1
        yield {"token": risposte[i]}

    return stream


def _esegui_run(monkeypatch, tmp_path, risposte, session_id, decisione=None):
    """Fa girare un turno dell'agente rispondendo alla prima proposta."""
    from core.harness import loop as modulo_loop

    monkeypatch.setattr(modulo_loop, "stream_dev_generation", _finto_modello(risposte))

    eventi = []
    gen = modulo_loop.stream_admin_agent_turn(
        messages=[{"role": "user", "content": "scrivi nota.py"}],
        workspace_root=str(tmp_path),
        model_name="finto",
        max_turns=2,
        session_id=session_id,
        review_writes=True,
    )
    for evento in gen:
        eventi.append(evento)
        if evento.get("type") == "write_proposed" and decisione:
            # La decisione deve partire da un altro thread: il generatore si
            # bloccera' alla prossima iterazione, esattamente come in
            # produzione, dove la risposta arriva su un'altra richiesta HTTP.
            threading.Timer(
                0.05,
                lambda pid=evento["id"]: review.decide(session_id, pid, decisione),
            ).start()
    return eventi


class TestIlCicloPassaDalGate:
    def test_una_scrittura_approvata_resta_sul_disco(self, monkeypatch, tmp_path):
        risposte = [
            '```tool:write_file\n{"path": "nota.py", "content": "VALORE = 1\\n"}\n```',
            "Fatto.",
        ]
        eventi = _esegui_run(monkeypatch, tmp_path, risposte, "sess-approva", "approved")
        try:
            proposte = [e for e in eventi if e.get("type") == "write_proposed"]
            assert len(proposte) == 1
            assert proposte[0]["path"].endswith("nota.py")
            assert "+VALORE = 1" in proposte[0]["diff"]
            assert (tmp_path / "nota.py").read_text(encoding="utf-8") == "VALORE = 1\n"
        finally:
            review.release_gate("sess-approva")

    def test_una_scrittura_rifiutata_non_resta(self, monkeypatch, tmp_path):
        risposte = [
            '```tool:write_file\n{"path": "nota.py", "content": "VALORE = 1\\n"}\n```',
            "Va bene, non la scrivo.",
        ]
        eventi = _esegui_run(monkeypatch, tmp_path, risposte, "sess-rifiuta", "rejected")
        try:
            annullamenti = [e for e in eventi if e.get("type") == "write_reverted"]
            assert len(annullamenti) == 1
            assert annullamenti[0]["reverted"] is True
            assert not (tmp_path / "nota.py").exists()
        finally:
            review.release_gate("sess-rifiuta")

    def test_l_agente_viene_informato_del_rifiuto(self, monkeypatch, tmp_path):
        """Senza saperlo, riproverebbe la stessa scrittura fino a esaurire i turni."""
        risposte = [
            '```tool:write_file\n{"path": "nota.py", "content": "VALORE = 1\\n"}\n```',
            "Capito.",
        ]
        eventi = _esegui_run(monkeypatch, tmp_path, risposte, "sess-informa", "rejected")
        try:
            risultati = [e for e in eventi if e.get("type") == "tool_result"]
            fallito = [r for r in risultati if not r.get("result", {}).get("success")]
            assert fallito, "il rifiuto deve arrivare all'agente come tool fallito"
            assert "NON applicata" in fallito[0]["result"]["error"]
        finally:
            review.release_gate("sess-informa")

    def test_senza_revisione_la_scrittura_non_si_ferma(self, monkeypatch, tmp_path):
        """Il comportamento storico resta intatto quando il gate e' spento:
        un run senza nessuno che guarda non deve bloccarsi alla prima riga."""
        from core.harness import loop as modulo_loop

        risposte = [
            '```tool:write_file\n{"path": "nota.py", "content": "VALORE = 1\\n"}\n```',
            "Fatto.",
        ]
        monkeypatch.setattr(modulo_loop, "stream_dev_generation", _finto_modello(risposte))

        eventi = list(modulo_loop.stream_admin_agent_turn(
            messages=[{"role": "user", "content": "scrivi nota.py"}],
            workspace_root=str(tmp_path),
            model_name="finto",
            max_turns=2,
            session_id="sess-senza-gate",
        ))
        assert not [e for e in eventi if e.get("type") == "write_proposed"]
        assert (tmp_path / "nota.py").read_text(encoding="utf-8") == "VALORE = 1\n"

    def test_la_lettura_non_passa_dal_gate(self, monkeypatch, tmp_path):
        """Solo cio' che tocca il disco va rivisto: fermare anche `read_file`
        renderebbe la revisione un ostacolo invece di un controllo."""
        (tmp_path / "esistente.py").write_text("X = 1\n", encoding="utf-8")
        risposte = [
            '```tool:read_file\n{"path": "esistente.py"}\n```',
            "Letto.",
        ]
        eventi = _esegui_run(monkeypatch, tmp_path, risposte, "sess-lettura")
        try:
            assert not [e for e in eventi if e.get("type") == "write_proposed"]
        finally:
            review.release_gate("sess-lettura")


class TestRotte:
    """La decisione arriva via HTTP: senza rotta, il gate blocca e basta."""

    def test_le_rotte_di_revisione_sono_registrate(self):
        from core.modules.sigma_developer_lab.handlers import ROUTES

        percorsi = {(p, tuple(m)) for p, _, m in ROUTES}
        assert ("/api/developer/review/decide", ("POST",)) in percorsi
        assert ("/api/developer/review/pending", ("GET",)) in percorsi
