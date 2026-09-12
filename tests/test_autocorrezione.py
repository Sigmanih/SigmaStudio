"""Un fallimento deve produrre una mossa, non un vicolo cieco.

`TaskPipeline` sapeva gia' riprovare un task, inserirne uno di correzione e
bloccare cio' che dipendeva da quello caduto. Nessuno la chiamava:
`retry_task`, `insert_fix_task` e `reorder_after_failure` erano raggiunti solo
dai loro test. La pipeline sapeva correggersi, e nessuno gliene dava occasione
— la quinta volta che qualcosa in questo progetto e' scritto, testato e
scollegato.

La diagnosi si fa sui **fatti del ledger**, mai sul racconto del modello:
chiedere a un modello perche' ha fallito produce una spiegazione plausibile,
che e' un'altra cosa dalla spiegazione vera.
"""

import pytest

from core.harness import autocorrezione as AC
from core.harness.ledger import DevSessionLedger
from core.harness.pipeline import TaskNode, TaskPipeline, TaskStatus


def _task(tid="t1", titolo="Scrivi il modulo", role="coder", **extra):
    nodo = TaskNode(id=tid, title=titolo, role=role, description=titolo)
    for chiave, valore in extra.items():
        setattr(nodo, chiave, valore)
    return nodo


@pytest.fixture
def ledger(tmp_path):
    return DevSessionLedger(goal="obiettivo di prova",
                            workspace_root=str(tmp_path))


def _scrive(ledger, percorso, righe=30):
    ledger.record_tool("write_file", {"path": percorso}, {
        "tool": "write_file", "success": True, "path": percorso,
        "full_path": percorso, "created": True,
        "content": "x\n" * righe, "lines": righe})


def _comando(ledger, comando, rc=0, stdout="", stderr=""):
    ledger.record_tool("terminal", {"command": comando}, {
        "tool": "terminal", "success": rc == 0, "command": comando,
        "returncode": rc, "stdout": stdout, "stderr": stderr})


class TestLaDiagnosiGuardaIFatti:
    def test_un_file_che_non_compila_si_corregge_dov_e(self, ledger, tmp_path):
        """La causa piu' netta che esista: si sa il file, si sa l'errore, e si
        sa chi lo ripara."""
        percorso = tmp_path / "app.py"
        percorso.write_text("def rotta(:\n", encoding="utf-8")
        ledger.record_tool("write_file", {"path": str(percorso)}, {
            "tool": "write_file", "success": True, "path": str(percorso),
            "full_path": str(percorso), "content": "def rotta(:\n",
            # E' il campo che il tool di scrittura emette davvero: il ledger
            # registra l'errore di sintassi solo quando il controllo AST ha
            # detto di no.
            "ast_valid": False,
            "syntax_error": "SyntaxError: invalid syntax (riga 1)"})

        d = AC.diagnostica(_task(), ledger.snapshot(), AC.Bilancio())
        assert d.livello == AC.CORREGGI
        assert d.ruolo == "coder"
        assert "app.py" in d.istruzione
        assert d.prove, "la diagnosi deve dire su cosa si e' basata"

    def test_una_verifica_fallita_diventa_l_istruzione(self, ledger):
        _scrive(ledger, "app.py")
        _comando(ledger, "python -m pytest tests/ -q", rc=1,
                 stdout="2 failed, 5 passed")
        d = AC.diagnostica(_task(), ledger.snapshot(), AC.Bilancio())
        assert d.livello == AC.CORREGGI
        assert "pytest" in d.istruzione
        assert "non il test" in d.istruzione, (
            "correggere il test invece del codice e' il modo piu' rapido di "
            "far passare una suite che non dimostra piu' niente")

    def test_un_modulo_inesistente_e_un_errore_di_piano(self, ledger):
        """Correggere qui produrrebbe una correzione costruita sullo stesso
        malinteso: e' il piano che descriveva un mondo diverso."""
        _scrive(ledger, "app.py")
        _comando(ledger, "python app.py", rc=1,
                 stderr="ModuleNotFoundError: No module named 'validatore'")
        d = AC.diagnostica(_task(), ledger.snapshot(), AC.Bilancio())
        assert d.livello == AC.RIPIANIFICA
        assert d.ruolo == "architect"

    def test_un_guasto_transitorio_si_riprova_e_basta(self, ledger):
        _scrive(ledger, "app.py")
        _comando(ledger, "npm test", rc=1,
                 stderr="Error: EBUSY: resource busy or locked")
        d = AC.diagnostica(_task(), ledger.snapshot(), AC.Bilancio())
        assert d.livello == AC.RIPROVA
        assert d.istruzione == "", "riprovare non crea lavoro nuovo"

    def test_non_aver_scritto_niente_significa_task_troppo_grande(self, ledger):
        d = AC.diagnostica(_task(), ledger.snapshot(), AC.Bilancio())
        assert d.livello == AC.RIPIANIFICA
        assert "piu' piccoli" in d.istruzione

    def test_fallire_senza_causa_leggibile_viene_ammesso(self, ledger):
        """Fingere una diagnosi sarebbe peggio che ammettere di non averla."""
        _scrive(ledger, "app.py")
        d = AC.diagnostica(_task(error="qualcosa e' andato storto"),
                           ledger.snapshot(), AC.Bilancio())
        assert d.livello == AC.CORREGGI
        assert "non sa dire" in d.istruzione

    def test_il_file_rotto_vince_sulla_verifica_fallita(self, ledger, tmp_path):
        """Se il file non compila, il test fallito ne e' la conseguenza: la
        causa da riparare e' una sola."""
        percorso = tmp_path / "app.py"
        percorso.write_text("def x(:\n", encoding="utf-8")
        ledger.record_tool("write_file", {"path": str(percorso)}, {
            "tool": "write_file", "success": True, "path": str(percorso),
            "full_path": str(percorso), "content": "def x(:\n",
            "ast_valid": False, "syntax_error": "SyntaxError"})
        _comando(ledger, "python -m pytest -q", rc=1, stdout="3 failed")
        d = AC.diagnostica(_task(), ledger.snapshot(), AC.Bilancio())
        assert "non compila" in d.motivo


class TestIlBilancioFermaIlCiclo:
    def test_finite_le_correzioni_si_rinuncia(self, ledger):
        _scrive(ledger, "app.py")
        _comando(ledger, "python -m pytest -q", rc=1, stdout="1 failed")
        d = AC.diagnostica(_task(), ledger.snapshot(),
                           AC.Bilancio(correzioni=0))
        assert d.livello == AC.RINUNCIA

    def test_finite_le_ripianificazioni_si_prova_a_correggere(self, ledger):
        """Meno probabile che funzioni, ma meglio del vicolo cieco."""
        _scrive(ledger, "app.py")
        _comando(ledger, "python app.py", rc=1,
                 stderr="No module named 'x'")
        d = AC.diagnostica(_task(), ledger.snapshot(),
                           AC.Bilancio(ripianificazioni=0))
        assert d.livello == AC.CORREGGI
        assert "ELENCA" in d.istruzione

    def test_senza_niente_si_rinuncia_dicendo_perche(self, ledger):
        _scrive(ledger, "app.py")
        _comando(ledger, "python app.py", rc=1, stderr="No module named 'x'")
        d = AC.diagnostica(_task(), ledger.snapshot(),
                           AC.Bilancio(correzioni=0, ripianificazioni=0))
        assert d.livello == AC.RINUNCIA
        assert d.motivo

    def test_spendere_consuma_il_bilancio(self):
        b = AC.Bilancio(correzioni=1, ripianificazioni=1)
        b.spendi(AC.CORREGGI)
        assert b.puo_correggere() is False
        b.spendi(AC.RIPIANIFICA)
        assert b.puo_ripianificare() is False

    def test_il_bilancio_non_va_sotto_zero(self):
        b = AC.Bilancio(correzioni=0)
        b.spendi(AC.CORREGGI)
        assert b.correzioni == 0


class TestApplicareLaMossa:
    def _pipeline_con_fallito(self):
        p = TaskPipeline(goal="x")
        p.add_task(_task("t1"))
        p.add_task(TaskNode(id="t2", title="dopo", role="tester",
                            depends_on=["t1"]))
        p.mark_running("t1")
        p.mark_failed("t1", "errore")
        return p

    def test_riprova_rimette_il_task_in_coda(self):
        p = self._pipeline_con_fallito()
        esito = AC.applica(p, p.nodes["t1"],
                           AC.Diagnosi(AC.RIPROVA, "transitorio"))
        assert esito["applicato"] is True
        assert p.nodes["t1"].status == TaskStatus.PENDING

    def test_riprova_senza_tentativi_blocca_cio_che_dipendeva(self):
        p = self._pipeline_con_fallito()
        p.nodes["t1"].retry_count = p.nodes["t1"].max_retries
        esito = AC.applica(p, p.nodes["t1"],
                           AC.Diagnosi(AC.RIPROVA, "transitorio"))
        assert esito["applicato"] is False
        assert p.nodes["t2"].status == TaskStatus.BLOCKED

    def test_correggi_inserisce_un_task_che_sblocca_il_seguito(self):
        p = self._pipeline_con_fallito()
        b = AC.Bilancio()
        esito = AC.applica(p, p.nodes["t1"], AC.Diagnosi(
            AC.CORREGGI, "file rotto", ruolo="coder",
            istruzione="Correggi app.py"), b)

        fix = p.nodes[esito["fix_id"]]
        assert fix.role == "coder"
        assert "app.py" in fix.description
        assert esito["fix_id"] in p.nodes["t2"].depends_on, (
            "chi aspettava il task fallito deve ora aspettare la correzione")
        assert b.correzioni == AC.CORREZIONI_MASSIME - 1

    def test_la_correzione_e_subito_eseguibile(self):
        p = self._pipeline_con_fallito()
        esito = AC.applica(p, p.nodes["t1"],
                           AC.Diagnosi(AC.CORREGGI, "x", istruzione="ripara"))
        pronti = [n.id for n in p.get_ready_tasks()]
        assert esito["fix_id"] in pronti

    def test_rinuncia_blocca_il_seguito(self):
        p = self._pipeline_con_fallito()
        AC.applica(p, p.nodes["t1"], AC.Diagnosi(AC.RINUNCIA, "basta"))
        assert p.nodes["t2"].status == TaskStatus.BLOCKED


class TestRipianificareSenzaRifare:
    def test_cio_che_e_fatto_resta_fatto(self):
        """Un piano nuovo che riparte da zero sovrascrive lavoro buono con
        lavoro identico o peggiore, e lo paga due volte in turni."""
        p = TaskPipeline(goal="x")
        p.add_task(_task("fatto", "gia' fatto"))
        p.add_task(_task("caduto", "fallito"))
        p.add_task(_task("mai", "non ancora"))
        p.mark_running("fatto")
        p.mark_done("fatto", "ok", ["app.py"])
        p.mark_running("caduto")
        p.mark_failed("caduto", "errore")

        conteggi = p.replan([_task("nuovo1", "passo nuovo"),
                             _task("nuovo2", "altro passo")])

        assert conteggi == {"kept": 1, "replaced": 2, "added": 2}
        assert set(p.nodes) == {"fatto", "nuovo1", "nuovo2"}
        assert p.nodes["fatto"].status == TaskStatus.DONE
        assert p.nodes["fatto"].files_modified == ["app.py"]

    def test_una_dipendenza_verso_un_task_sparito_viene_tolta(self):
        """Altrimenti il task nuovo aspetterebbe per sempre qualcosa che il
        piano precedente ha portato via."""
        p = TaskPipeline(goal="x")
        p.add_task(_task("vecchio"))
        p.mark_running("vecchio")
        p.mark_failed("vecchio", "errore")

        nuovo = _task("n1")
        nuovo.depends_on = ["vecchio", "inesistente"]
        p.replan([nuovo])
        assert p.nodes["n1"].depends_on == []
        assert [n.id for n in p.get_ready_tasks()] == ["n1"]

    def test_una_dipendenza_verso_un_task_fatto_resta(self):
        p = TaskPipeline(goal="x")
        p.add_task(_task("fatto"))
        p.mark_running("fatto")
        p.mark_done("fatto")

        nuovo = _task("n1")
        nuovo.depends_on = ["fatto"]
        p.replan([nuovo])
        assert p.nodes["n1"].depends_on == ["fatto"]
        assert [n.id for n in p.get_ready_tasks()] == ["n1"]

    def test_un_id_riusato_non_sovrascrive_la_storia(self):
        p = TaskPipeline(goal="x")
        p.add_task(_task("t1", "l'originale"))
        p.mark_running("t1")
        p.mark_done("t1", "ok", ["vero.py"])

        p.replan([_task("t1", "un altro lavoro")])
        assert p.nodes["t1"].title == "l'originale"
        assert "t1-bis" in p.nodes

    def test_il_contesto_dice_cosa_non_rifare(self):
        p = TaskPipeline(goal="x")
        p.add_task(_task("fatto", "Ha scritto il parser"))
        p.add_task(_task("resta", "Da fare: le rotte"))
        p.mark_running("fatto")
        p.mark_done("fatto", "ok", ["parser.py"])

        testo = AC.contesto_per_ripianificare(
            p, AC.Diagnosi(AC.RIPIANIFICA, "x", istruzione="Rifai il piano."),
            obiettivo="costruire la biblioteca")

        assert "GIA' FATTO" in testo
        assert "parser.py" in testo
        assert "Da fare: le rotte" in testo
        assert "costruire la biblioteca" in testo
        assert "Non includere i task" in testo


class TestLOrchestratoreCiPassaDavvero:
    def test_il_ciclo_reagisce_ai_fallimenti(self):
        """La quinta volta che qualcosa e' scritto, testato e scollegato: qui
        si verifica che il percorso di produzione esista."""
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        sorgente = inspect.getsource(DevOrchestrator._phase_implement)
        assert "_reagisci_al_fallimento" in sorgente

        reazione = inspect.getsource(DevOrchestrator._reagisci_al_fallimento)
        assert "autocorrezione.diagnostica" in reazione
        assert "autocorrezione.applica" in reazione
        assert "self_correction" in reazione

    def test_la_ripianificazione_richiama_l_architetto(self):
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        sorgente = inspect.getsource(DevOrchestrator._ripianifica)
        assert 'generate_with_role(\n            "architect"' in sorgente
        assert "self.pipeline.replan" in sorgente
        assert "contesto_per_ripianificare" in sorgente

    def test_il_bilancio_vive_per_tutto_l_obiettivo(self):
        """Un tetto per task non impedirebbe a dieci task di correggersi tre
        volte ciascuno."""
        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        orch = DevOrchestrator(workspace_root=".")
        assert isinstance(orch.bilancio, AC.Bilancio)
        assert orch.bilancio.correzioni == AC.CORREZIONI_MASSIME


class TestSiVedeMentreSuccede:
    """In un flusso autonomo la mossa dopo un fallimento e' la cosa piu'
    importante da vedere: e' li' che si distingue un sistema che si corregge
    da uno che gira a vuoto."""

    def test_la_correzione_diventa_una_riga_di_diario(self):
        from core.harness.resoconto import narra

        riga = narra({
            "type": "self_correction", "task_id": "t1", "title": "Scrivi il parser",
            "livello": AC.CORREGGI, "motivo": "«parser.py» non compila",
            "prove": ["parser.py: SyntaxError riga 12"],
        })
        assert riga and "Correzione inserita" in riga
        assert "parser.py" in riga

    def test_la_ripianificazione_dice_cosa_e_stato_tenuto(self):
        from core.harness.resoconto import narra

        riga = narra({"type": "replanned", "kept": 3, "replaced": 4, "added": 5})
        assert riga and "3 task tenuti" in riga and "5 nuovi" in riga

    def test_anche_la_rinuncia_si_racconta(self):
        from core.harness.resoconto import narra

        riga = narra({"type": "self_correction", "title": "x",
                      "livello": AC.RINUNCIA, "motivo": "bilancio finito"})
        assert riga and "Rinuncia" in riga


class TestUnSoloSistemaDiCorrezione:
    """`_feedback_loop` era nato prima dell'autocorrezione e faceva la stessa
    cosa in modo piu' grezzo. Convivendo erano due sistemi che non si parlano:
    uno contava le proprie mosse, l'altro no, e insieme potevano spendere molto
    piu' del tetto che il primo credeva di far rispettare."""

    def test_il_ciclo_di_correzione_passa_dalla_diagnosi(self):
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        sorgente = inspect.getsource(DevOrchestrator._feedback_loop)
        assert "autocorrezione.diagnostica" in sorgente
        assert "self.bilancio" in sorgente

    def test_non_passa_piu_la_prosa_del_tester_al_coder(self):
        """Erano i fatti del ledger travestiti da racconto di un modello."""
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        sorgente = inspect.getsource(DevOrchestrator._feedback_loop)
        assert 'upstream_outputs={\n                    "tester"' not in sorgente
        assert "tester_feedback" not in sorgente

    def test_con_il_bilancio_finito_si_ferma_invece_di_riprovare(self):
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        sorgente = inspect.getsource(DevOrchestrator._feedback_loop)
        assert "puo_correggere()" in sorgente

    def test_una_verifica_mai_eseguita_non_e_una_verifica_superata(self):
        """E' la distinzione che il cancello di completamento fa da sempre, e
        vale anche qui: nessun comando eseguito significa che la prova non ha
        avuto luogo."""
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        sorgente = inspect.getsource(DevOrchestrator._riesegui_la_verifica)
        assert "superata and visto" in sorgente

    def test_la_prova_del_piano_viene_riusata(self):
        """Il primo task che dichiara un `verify` vale per l'obiettivo."""
        from core.harness.pipeline import TaskNode, TaskPipeline
        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        orch = DevOrchestrator(workspace_root=".")
        assert orch._comando_di_verifica() == ""

        orch.pipeline = TaskPipeline(goal="x")
        orch.pipeline.add_task(TaskNode(id="a", title="a", role="coder"))
        orch.pipeline.add_task(TaskNode(
            id="b", title="b", role="coder",
            metadata={"verify": "python tools/check_i18n.py sigma_network"}))
        assert orch._comando_di_verifica().startswith("python tools/check_i18n")
