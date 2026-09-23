"""Lo stato si divide in due: cio' che non cambia in testa, cio' che cambia in coda.

Al 24 settembre 2026 lo stato del lavoro erano 11.501 caratteri a ogni turno —
9.000 di stato (al tetto: troncava) piu' 2.501 di mappa dei file — cioe' circa
2.875 token per turno, riscritti a ogni giro. Una parte di quelli non cambia mai
durante un run: l'obiettivo, i percorsi citati, quello che l'agente ha capito,
le cartelle che esistono. Se stanno in TESTA al prompt si pagano una volta e la
cache del prefisso li copre; se stanno in coda si ripagano a ogni turno.

La proprieta' che questi test bloccano e' una sola e vale piu' delle altre: il
blocco stabile deve restare identico quando il lavoro avanza. Un blocco in testa
che cambia — un contatore, un criterio che diventa soddisfatto, un comando
recente — invalida tutto cio' che viene dopo, cioe' la cronologia, e allora il
prefill si ripaga per intero.
"""

from core.harness.ledger import DevSessionLedger


def _ledger(radice, goal="Sistemare il contesto"):
    return DevSessionLedger(goal=goal, workspace_root=str(radice))


class TestLaParteStabile:
    """Quello che sta in testa al prompt: identico a ogni turno, o e' un danno."""

    def test_non_cambia_quando_il_lavoro_avanza(self, tmp_path):
        (tmp_path / "core").mkdir()
        (tmp_path / "sigma_studio").mkdir()
        ledger = _ledger(tmp_path)
        ledger.set_spec("va sistemato il contesto",
                        ["il riuso si misura", "il t/s non mente"])
        ledger.set_pipeline([{"id": "1", "title": "misurare", "status": "pending"}])
        prima = ledger.render_stable_block()

        # Il lavoro avanza: criterio soddisfatto, decisione, memoria, pipeline.
        ledger.mark_requirement("1", "tests/test_numeri_del_provider.py")
        ledger.add_decision("il blocco volatile va in coda")
        ledger.add_session_memory("fatto il primo passo", "[1-2]")
        ledger.set_pipeline([{"id": "1", "title": "misurare", "status": "done"}])
        dopo = ledger.render_stable_block()

        assert prima == dopo, (
            "il blocco stabile e' cambiato mentre il lavoro avanzava: sta in testa "
            "al prompt, quindi ogni cambiamento invalida la cronologia che segue")
        assert prima, "il blocco stabile e' vuoto: obiettivo e percorsi sono spariti"

    def test_i_criteri_e_i_contatori_non_stanno_qui(self, tmp_path):
        """Si muovono durante il run: il loro posto e' la coda."""
        ledger = _ledger(tmp_path)
        ledger.set_spec("capito", ["un criterio"])
        stabile = ledger.render_stable_block()
        assert "Criteri di accettazione" not in stabile
        assert "**Turni:**" not in stabile
        assert "Comandi eseguiti" not in stabile

    def test_dice_quali_cartelle_esistono(self, tmp_path):
        """Contro i nomi vecchi: 28 comandi falliti su 826 li nominavano."""
        (tmp_path / "core").mkdir()
        (tmp_path / "tests").mkdir()
        testo = _ledger(tmp_path).render_stable_block()
        assert "`core/`" in testo
        assert "`tests/`" in testo
        assert "`sigma_studio/`" not in testo, (
            "una cartella che non esiste in questa radice non va promessa")
        assert "frontend/" in testo, "l'avviso sui nomi vecchi deve esserci"

    def test_porta_obiettivo_e_percorsi(self, tmp_path):
        ledger = _ledger(tmp_path, goal="Rendere misurabile il riuso")
        ledger.set_spec("va misurato il riuso del prefisso", ["un criterio"])
        ledger.goal_paths = ["core/harness/loop.py"]
        testo = ledger.render_stable_block()
        assert "Rendere misurabile il riuso" in testo
        assert "core/harness/loop.py" in testo
        assert "va misurato il riuso del prefisso" in testo


class TestLaParteVolatile:
    """Quello che sta in coda all'ultimo messaggio: cambia, e non deve invadere."""

    def test_il_contatore_dei_turni_sta_qui(self, tmp_path):
        assert "**Turni:** 3 di 9" in _ledger(tmp_path).render_volatile_block(3, 9)

    def test_i_tetti_tengono_corta_la_parte_volatile(self, tmp_path):
        ledger = _ledger(tmp_path)
        ledger.set_spec("capito", ["uno", "due"])
        for i in range(20):
            ledger.add_decision(f"decisione numero {i}")
            ledger.add_session_memory(f"memoria numero {i}", "[%d]" % i)
        testo = ledger.render_volatile_block(5, 10)
        assert "decisione numero 19" in testo
        assert "decisione numero 12" not in testo, "le decisioni sono le ultime tre"
        assert "memoria numero 19" in testo
        assert "memoria numero 12" not in testo, "la memoria sono le ultime tre"

    def test_lo_stato_intero_e_le_due_parti(self, tmp_path):
        """`render_state_block` resta per chi le vuole tutte insieme."""
        ledger = _ledger(tmp_path, goal="obiettivo di prova")
        ledger.set_spec("capito", ["criterio uno"])
        intero = ledger.render_state_block(2, 8)
        assert "obiettivo di prova" in intero
        assert "Criteri di accettazione" in intero
        assert "**Turni:** 2 di 8" in intero
        assert intero.count("## STATO DEL LAVORO") == 1
