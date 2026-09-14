"""Una prova che passa in una cartella temporanea vale finche' dura la cartella.

Il task `compose` della Biblioteca Digitale doveva tirare su lo stack Docker, e
il suo cancello non era compiacente: interrogava il sito e pretendeva 200 sulla
pagina **e** 200 sulle opere. E' passato. Tutto vero.

Cinque minuti dopo la pagina rispondeva 200 e l'API 500. Il motivo sta in una
riga di `docker inspect`:

    working_dir = ...\var\dev_worktrees\fanout_biblioteca_stack_compose_9eda5b

Il run lavora in un worktree isolato — e' cio' che permette a piu' agenti di
scrivere nello stesso momento — e il `docker compose up` l'ha acceso li'
dentro, con `dati.json` montato da quella cartella. Quando il worktree e' stato
rimosso, il volume ha smesso di puntare a qualcosa.

Il cancello non aveva mentito: aveva detto la verita' su un mondo che e' durato
quanto il run. L'isolamento rende sicuro lo scrivere e rende falsa la prova
dell'accendere, e sono due facce della stessa scelta.

Il rimedio non e' rinunciare all'isolamento: e' rifare la stessa domanda dove
il lavoro vive.
"""

import pytest

from core.harness import fanout


class TestQualiProveVannoRifatte:
    """Rifare tutto raddoppierebbe il costo di ogni voce. Si rifa' cio' che
    lascia dietro di se' qualcosa che dovrebbe sopravvivere al run."""

    @pytest.mark.parametrize("comando", [
        "docker compose up -d --build",
        "docker-compose up -d",
        "docker run -d -p 8080:80 sito",
        "npm start",
        "pm2 start server.js",
    ])
    def test_cio_che_accende_qualcosa(self, comando):
        assert fanout._puo_lasciare_tracce(comando) is True

    @pytest.mark.parametrize("comando", [
        "npm run build",
        "pytest tests/",
        "node --test backend/index.test.js",
        "docker build -t sito ./frontend",
        "ruff check .",
    ])
    def test_cio_che_si_limita_a_guardare(self, comando):
        """Una build o un test leggono l'albero e finiscono: dove girano non
        cambia il verdetto, e rifarli e' solo tempo."""
        assert fanout._puo_lasciare_tracce(comando) is False

    def test_il_caso_vero_col_suo_cancello_intero(self):
        verifica = ("docker compose up -d --build && node -e \"fetch('http://localhost:8080')\"")
        assert fanout._puo_lasciare_tracce(verifica) is True


class TestLaRiprova:
    def test_senza_comando_non_si_riprova_niente(self):
        assert fanout.riprova_nell_albero("", ".") is None

    def test_una_build_non_viene_rifatta(self):
        assert fanout.riprova_nell_albero("npm run build", ".") is None

    def test_gira_nell_albero_vero_non_nel_worktree(self, monkeypatch):
        """E' tutto il punto: la stessa domanda, posta dove il lavoro vive."""
        visto = {}

        class EsecutoreFinto:
            def esegui(self, comando, cwd, timeout_s=300, should_cancel=None):
                visto["comando"] = comando
                visto["cwd"] = cwd
                class E:
                    returncode = 0
                    stdout = "SITO SU: pagina 200 api 200"
                    stderr = ""
                return E()

        monkeypatch.setattr("core.harness.esecutori.scegli_esecutore",
                            lambda radice=None: EsecutoreFinto())
        esito = fanout.riprova_nell_albero("docker compose up -d", "/casa/progetto")
        assert visto["cwd"] == "/casa/progetto"
        assert esito["ok"] is True

    def test_una_riprova_fallita_toglie_il_fatto(self, monkeypatch):
        """E' il caso vero: nel worktree 200, nell'albero 500."""
        class EsecutoreFinto:
            def esegui(self, comando, cwd, timeout_s=300, should_cancel=None):
                class E:
                    returncode = 1
                    stdout = ""
                    stderr = "il sito non risponde dopo 60s"
                return E()

        monkeypatch.setattr("core.harness.esecutori.scegli_esecutore",
                            lambda radice=None: EsecutoreFinto())
        esito = fanout.riprova_nell_albero("docker compose up -d", ".")
        assert esito["ok"] is False
        assert esito["returncode"] == 1


class TestEDavveroCollegata:
    """Il difetto ricorrente di questo progetto e' la capacita' scritta e mai
    raggiunta: qui e' costata un «fatto» che non lo era."""

    def test_il_percorso_del_successo_la_chiama(self):
        import inspect

        sorgente = inspect.getsource(fanout._esegui_voce)
        assert "riprova_nell_albero(verifica, workspace_root" in sorgente

    def test_una_riprova_fallita_fa_fallire_la_voce(self):
        import inspect

        sorgente = inspect.getsource(fanout._esegui_voce)
        i = sorgente.index("riprova_nell_albero")
        dopo = sorgente[i:i + 900]
        assert "esito.ok = False" in dopo
        assert "coda.fail" in dopo, "senza questo la coda la segna fatta lo stesso"

    def test_l_esito_porta_con_se_com_e_andata(self):
        assert "riprova" in fanout.EsitoVoce("x", "y", True).to_dict()
