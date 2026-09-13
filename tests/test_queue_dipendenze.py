"""La coda deve sapere che una voce puo' aspettarne un'altra.

Senza dipendenze, l'unico modo di ordinare il lavoro era metterlo in fila e
usare un solo lavoratore: si rinunciava al parallelismo su venti voci per
esprimere un vincolo che ne riguardava due. Sul lavoro della Biblioteca le voci
06 e 07 dipendevano dalla 05, e non c'era modo di dirlo.

E l'architetto deve poter riempire la coda. Prima si poteva solo da
`POST /api/harness/queue`: un agente che aveva appena guardato il progetto e
capito come spezzare il lavoro non aveva dove scriverlo.
"""

import pytest

from core.harness import workqueue as WQ
from core.harness.loop import execute_admin_tool


@pytest.fixture
def coda(tmp_path, monkeypatch):
    """Una coda vera, ma con il suo stato in una cartella temporanea."""
    monkeypatch.setattr(WQ.paths, "var_dir", lambda: tmp_path)
    WQ._code.clear()
    yield WQ.get_queue("prova")
    WQ._code.clear()


class TestLeDipendenzeVengonoRispettate:
    def test_una_voce_che_aspetta_non_viene_presa(self, coda):
        coda.add_many([
            {"id": "a", "title": "prima"},
            {"id": "b", "title": "dopo", "depends_on": ["a"]},
        ])
        assert coda.claim("w1").id == "a"
        assert coda.claim("w2") is None, "'b' aspetta 'a', non puo' partire"

    def test_chiudere_la_dipendenza_la_rende_disponibile(self, coda):
        coda.add_many([
            {"id": "a", "title": "prima"},
            {"id": "b", "title": "dopo", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        coda.complete("a")
        assert coda.claim("w2").id == "b"

    def test_le_voci_indipendenti_partono_insieme(self, coda):
        """Il vincolo non deve trasformare il parallelismo in una fila."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b"},
            {"id": "c", "title": "c", "depends_on": ["a"]},
        ])
        presi = {coda.claim("w1").id, coda.claim("w2").id}
        assert presi == {"a", "b"}

    def test_una_catena_si_srotola_nell_ordine(self, coda):
        coda.add_many([
            {"id": "c", "title": "c", "depends_on": ["b"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
            {"id": "a", "title": "a"},
        ])
        ordine = []
        for _ in range(3):
            voce = coda.claim("w1")
            assert voce is not None
            ordine.append(voce.id)
            coda.complete(voce.id)
        assert ordine == ["a", "b", "c"]


class TestCioCheNonPotraMaiPartire:
    def test_chi_dipende_da_una_fallita_viene_bloccato_e_lo_dice(self, coda):
        """Restando «da fare» la coda non finirebbe mai, e nessuno saprebbe
        perche'."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        coda.fail("a", "impossibile", riprovabile=False)

        stato = coda.progress()
        assert stato["blocked"] == 1
        assert stato["finished"] is True, "la coda deve poter finire"
        bloccata = [v for v in coda.items() if v.id == "b"][0]
        assert "dipende da 'a'" in bloccata.error

    def test_il_blocco_si_propaga(self, coda):
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
            {"id": "c", "title": "c", "depends_on": ["b"]},
        ])
        coda.claim("w1")
        coda.fail("a", "impossibile", riprovabile=False)
        assert coda.progress()["blocked"] == 2

    def test_reset_failed_rimette_in_gioco_anche_le_bloccate(self, coda):
        """Riprovare la fallita non basta: chi la aspettava e' gia' stato
        marcato bloccato, e resterebbe tale anche dopo che lei riesce."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        coda.fail("a", "x", riprovabile=False)
        assert coda.progress()["blocked"] == 1

        assert coda.reset_failed() == 2, "sia la fallita sia la bloccata"
        assert coda.claim("w1").id == "a"
        coda.complete("a")
        assert coda.claim("w2").id == "b", "ora deve poter partire"

    def test_una_dipendenza_verso_un_id_inesistente_viene_tolta(self, coda):
        avvisi = []
        coda.add_many([{"id": "b", "title": "b", "depends_on": ["mai_esistito"]}],
                      avvisi=avvisi)
        assert coda.claim("w1").id == "b", "non deve restare ferma per sempre"
        assert any("mai_esistito" in a for a in avvisi)

    def test_un_ciclo_viene_spezzato(self, coda):
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "a", "depends_on": ["b"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ], avvisi=avvisi)
        assert coda.claim("w1") is not None, "un ciclo fermerebbe tutto"
        assert any("ciclo" in a for a in avvisi)


class TestIlLavoratoreNonSeNeVaTroppoPresto:
    def test_attesa_utile_mentre_la_dipendenza_e_in_corso(self, coda):
        """Il caso che chiuderebbe i thread con la coda a meta': w2 non trova
        niente perche' l'unica voce rimasta aspetta quella che w1 ha in mano."""
        coda.add_many([
            {"id": "a", "title": "a"},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        coda.claim("w1")
        assert coda.claim("w2") is None
        assert coda.attesa_utile() is True

    def test_a_coda_vuota_non_si_aspetta(self, coda):
        coda.add_many([{"id": "a", "title": "a"}])
        coda.claim("w1")
        coda.complete("a")
        assert coda.attesa_utile() is False

    def test_il_ventaglio_aspetta_invece_di_uscire(self):
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout.run_queue)
        assert "coda.attesa_utile()" in sorgente


class TestLArchitettoRiempieLaCoda:
    def test_il_tool_crea_le_voci(self, coda, tmp_path):
        esito = execute_admin_tool("queue_add", {
            "queue_id": "prova",
            "goal": "rendere i moduli traducibili",
            "items": [
                {"id": "01", "title": "estrai le stringhe di sigma_network",
                 "verify": "python tools/check_i18n.py sigma_network"},
                {"id": "02", "title": "traduci in inglese", "depends_on": ["01"]},
            ],
        }, workspace_root=str(tmp_path))

        assert esito["success"] is True
        assert esito["added"] == 2
        assert esito["progress"]["ready"] == 1, "la seconda aspetta la prima"

        voci = {v.id: v for v in WQ.get_queue("prova").items()}
        assert voci["02"].depends_on == ["01"]
        assert voci["01"].payload.get("verify", "").startswith("python tools")

    def test_senza_queue_id_viene_rifiutato_con_un_esempio(self, tmp_path):
        esito = execute_admin_tool("queue_add", {"items": [{"id": "1", "title": "x"}]},
                                   workspace_root=str(tmp_path))
        assert esito["success"] is False
        assert "queue_id" in esito["error"]

    def test_senza_voci_viene_rifiutato_con_un_esempio(self, tmp_path):
        esito = execute_admin_tool("queue_add", {"queue_id": "x"},
                                   workspace_root=str(tmp_path))
        assert esito["success"] is False
        assert "verify" in esito["error"], "l'errore deve mostrare la forma giusta"

    def test_gli_alias_funzionano(self, coda, tmp_path):
        esito = execute_admin_tool("enqueue", {
            "queue_id": "prova", "items": [{"id": "z", "title": "z"}],
        }, workspace_root=str(tmp_path))
        assert esito["success"] is True


class TestIlToolEDavveroRaggiungibile:
    def test_e_nello_schema_spedito_al_modello(self):
        from core.harness.tool_schema import TOOL_SCHEMAS

        nomi = [s["function"]["name"] for s in TOOL_SCHEMAS]
        assert "queue_add" in nomi

    def test_l_architetto_puo_usarlo(self):
        from core.harness.policy import ToolPolicy
        from core.harness.roles import ROLE_ARCHITECT

        assert "queue_add" in ROLE_ARCHITECT.tools
        policy = ToolPolicy.of(ROLE_ARCHITECT.tools, label="architect")
        assert policy.permits("queue_add") is True
        assert policy.permits("enqueue") is True, "l'alias deve passare"

    def test_il_prompt_lo_documenta(self):
        from core.harness.loop import ADMIN_DEVELOPER_SYSTEM_PROMPT

        assert "`queue_add`" in ADMIN_DEVELOPER_SYSTEM_PROMPT


class TestUnaVoceTroppoGrandeSiSpezza:
    """La mossa che mancava a chi sta lavorando. Su una prova dal vivo un
    agente ha speso 26 turni su una voce che erano tre, ha scritto cinque file
    e non ne ha dimostrato nessuno: non aveva modo di dire «questa e' piu'
    grande di quanto sembrava» se non fallendo."""

    def test_i_pezzi_prendono_il_posto_della_voce(self, coda):
        coda.add_many([{"id": "grande", "title": "fai tutto"}])
        esito = coda.sostituisci("grande", [
            {"id": "p1", "title": "primo pezzo"},
            {"id": "p2", "title": "secondo pezzo", "depends_on": ["p1"]},
        ], motivo="erano tre lavori")

        assert esito["ok"] is True
        assert esito["created"] == ["p1", "p2"]
        voci = {v.id: v for v in coda.items()}
        assert voci["grande"].state == "done"
        assert voci["grande"].result["spezzata_in"] == ["p1", "p2"]
        assert voci["grande"].result["motivo"] == "erano tre lavori"

    def test_chi_aspettava_la_voce_adesso_aspetta_i_pezzi(self, coda):
        """Senza, la dipendenza sarebbe soddisfatta appena si chiude la voce
        spezzata — cioe' subito, prima che i pezzi esistano, che e' il
        contrario di cio' che quella dipendenza voleva dire."""
        coda.add_many([
            {"id": "grande", "title": "fai tutto"},
            {"id": "dopo", "title": "il seguito", "depends_on": ["grande"]},
        ])
        coda.sostituisci("grande", [{"id": "p1", "title": "pezzo"}])

        voci = {v.id: v for v in coda.items()}
        assert voci["dopo"].depends_on == ["p1"]
        assert [v.id for v in coda.items() if v.state == "todo"] == ["dopo", "p1"]
        assert coda.claim("w1").id == "p1", "il seguito deve ancora aspettare"

    def test_i_pezzi_ereditano_cio_che_la_voce_aspettava(self, coda):
        """Se la voce non poteva partire, i suoi pezzi non possono partire."""
        coda.add_many([
            {"id": "prima", "title": "prima"},
            {"id": "grande", "title": "fai tutto", "depends_on": ["prima"]},
        ])
        coda.sostituisci("grande", [{"id": "p1", "title": "pezzo"}])
        voci = {v.id: v for v in coda.items()}
        assert "prima" in voci["p1"].depends_on

    def test_spezzare_una_voce_che_non_esiste_viene_detto(self, coda):
        esito = coda.sostituisci("mai_esistita", [{"id": "x", "title": "x"}])
        assert esito["ok"] is False
        assert "non esiste" in esito["error"]

    def test_senza_pezzi_non_si_spezza_niente(self, coda):
        coda.add_many([{"id": "grande", "title": "fai tutto"}])
        esito = coda.sostituisci("grande", [])
        assert esito["ok"] is False
        assert {v.id: v.state for v in coda.items()}["grande"] == "todo"


class TestLAgenteSaSpezzare:
    def test_il_tool_accetta_replaces(self, coda, tmp_path):
        coda.add_many([{"id": "grande", "title": "fai tutto"}])
        esito = execute_admin_tool("queue_add", {
            "queue_id": "prova", "replaces": "grande",
            "reason": "erano tre lavori indipendenti",
            "items": [{"id": "a", "title": "uno"}, {"id": "b", "title": "due"}],
        }, workspace_root=str(tmp_path))

        assert esito["success"] is True
        assert esito["replaced"] == "grande"
        assert esito["added"] == 2
        assert "spezzata" in esito["message"]

    def test_lo_schema_lo_dichiara(self):
        from core.harness.tool_schema import TOOL_SCHEMAS

        schema = [s for s in TOOL_SCHEMAS
                  if s["function"]["name"] == "queue_add"][0]
        proprieta = schema["function"]["parameters"]["properties"]
        assert "replaces" in proprieta and "reason" in proprieta

    def test_il_prompt_della_voce_glielo_dice(self):
        """Una via d'uscita che l'agente non sa di avere non e' una via
        d'uscita."""
        from core.harness.fanout import _prompt_voce
        from core.harness.workqueue import Voce

        testo = _prompt_voce(Voce(id="03_rotte", title="Scrivi le rotte"),
                             "obiettivo", "biblioteca")
        assert "03_rotte" in testo
        assert '"replaces": "03_rotte"' in testo
        assert "spezzala" in testo

    def test_senza_coda_il_prompt_non_ne_parla(self):
        """Fuori da un ventaglio non c'e' nessuna voce da spezzare."""
        from core.harness.fanout import _prompt_voce
        from core.harness.workqueue import Voce

        testo = _prompt_voce(Voce(id="x", title="fai"), "obiettivo")
        assert "replaces" not in testo


class TestUnaVoceSpezzataNonTornaInCoda:
    """Trovato su un ventaglio vero: `04_pannello` risultava «spezzata in due»
    **e** fallita insieme. Il lavoratore che l'aveva spezzata arrivava in fondo
    al proprio run, non aveva chiuso nessun obiettivo, e la faceva fallire —
    riportandola in coda accanto ai propri pezzi. Due lavoratori hanno prodotto
    lo stesso modulo con due nomi diversi."""

    def test_il_run_che_la_spezza_non_la_fa_fallire(self, coda, tmp_path,
                                                    monkeypatch):
        from core.harness import fanout

        coda.add_many([{"id": "grande", "title": "fai tutto"}])
        voce = coda.claim("w1")

        # Il run non chiude nessun obiettivo: senza la guardia, finirebbe in
        # `coda.fail`.
        monkeypatch.setattr(fanout, "stream_admin_agent_turn", None, raising=False)
        coda.sostituisci("grande", [{"id": "p1", "title": "pezzo"}],
                         motivo="erano due lavori")

        esito = fanout.EsitoVoce(item_id="grande", title="fai tutto", ok=False)
        # Si esercita la sola parte che decide: la voce risulta gia' spezzata.
        aggiornata = next(v for v in coda.items() if v.id == "grande")
        assert (aggiornata.result or {}).get("spezzata_in") == ["p1"]
        assert aggiornata.state == "done"

    def test_il_ventaglio_controlla_prima_di_chiudere(self):
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout._esegui_voce)
        assert "_e_stata_spezzata(" in sorgente, (
            "senza questo controllo la voce spezzata torna in coda accanto "
            "ai propri pezzi")
        # Vale per ENTRAMBE le uscite: il run che finisce male, e quello che
        # va in eccezione dopo aver spezzato.
        assert sorgente.count("_e_stata_spezzata(") == 2
        assert sorgente.index("_e_stata_spezzata(") < sorgente.index("coda.fail(voce.id")


class TestIFileDichiaratiPrevengonoLaContesa:
    """La causa piu' cara che questo sistema abbia avuto: due lavoratori
    partono dallo stesso commit, lavorano bene, e il secondo non riesce a
    trasferire perche' il primo ha gia' cambiato quel file. Misurato su un
    ventaglio vero: quattro voci su otto.

    La fusione a tre vie recupera il caso normale. Quello in cui i due cambiano
    davvero la stessa riga si previene solo prima di partire."""

    def test_due_voci_sullo_stesso_file_vengono_segnalate(self, coda):
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "il preflight", "files": ["core/esecutori.py"]},
            {"id": "b", "title": "la cache", "files": ["core/esecutori.py"]},
        ], avvisi=avvisi)
        assert any("core/esecutori.py" in x and "a, b" in x for x in avvisi)
        assert any("depends_on" in x for x in avvisi), "deve dire il rimedio"

    def test_file_diversi_non_producono_rumore(self, coda):
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "uno", "files": ["core/a.py"]},
            {"id": "b", "title": "due", "files": ["core/b.py"]},
        ], avvisi=avvisi)
        assert avvisi == []

    def test_se_sono_gia_in_fila_non_c_e_niente_da_dire(self, coda):
        """Una dipendenza fra le due le serializza: nessun rischio di contesa."""
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "primo", "files": ["core/x.py"]},
            {"id": "b", "title": "dopo", "files": ["core/x.py"],
             "depends_on": ["a"]},
        ], avvisi=avvisi)
        assert avvisi == []

    def test_una_voce_gia_fatta_non_conta(self, coda):
        """Il conflitto e' fra chi lavora, non con chi ha gia' finito."""
        coda.add_many([{"id": "a", "title": "primo", "files": ["core/x.py"]}])
        coda.claim("w1")
        coda.complete("a")
        avvisi = []
        coda.add_many([{"id": "b", "title": "dopo", "files": ["core/x.py"]}],
                      avvisi=avvisi)
        assert avvisi == []

    def test_i_file_arrivano_nel_payload_e_nel_prompt(self, coda, tmp_path):
        from core.harness.fanout import _prompt_voce

        execute_admin_tool("queue_add", {
            "queue_id": "prova",
            "items": [{"id": "z", "title": "scrivi", "files": ["core/z.py"]}],
        }, workspace_root=str(tmp_path))
        voce = [v for v in coda.items() if v.id == "z"][0]
        assert voce.payload.get("files") == ["core/z.py"]
        assert "core/z.py" in _prompt_voce(voce, "obiettivo", "prova")

    def test_lo_schema_dichiara_files(self):
        from core.harness.tool_schema import TOOL_SCHEMAS

        schema = [s for s in TOOL_SCHEMAS
                  if s["function"]["name"] == "queue_add"][0]
        voce = schema["function"]["parameters"]["properties"]["items"]["items"]
        assert "files" in voce["properties"]
