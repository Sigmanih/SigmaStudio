"""L'indirizzo di sviluppo, e le radici che a un agente non si danno.

Il selettore dell'interfaccia offriva la radice di Sigma Studio, la cartella
utente e **ogni lettera di unita'**: scegliere `C:/` come cartella di lavoro di
un ventaglio era a un clic. Il confine dei percorsi non aiuta in quel caso —
con `C:/` come radice, «non uscire dalla radice» non vieta piu' niente.

Sono quindi due difese diverse per la stessa cosa: dove sta il lavoro
(`data/progetti/`) e quanto puo' essere larga una radice.
"""

import os
from pathlib import Path

import pytest

from core import paths, progetti


@pytest.fixture
def casa_finta(tmp_path, monkeypatch):
    """Radici isolate: questi test non devono scrivere in `data/` ne' in `config/`."""
    dati = tmp_path / "data"
    conf = tmp_path / "config"
    dati.mkdir()
    conf.mkdir()
    monkeypatch.setattr(paths, "workspace_dir", lambda: dati)
    monkeypatch.setattr(paths, "config_dir", lambda: conf)
    monkeypatch.setattr(progetti.paths, "workspace_dir", lambda: dati)
    monkeypatch.setattr(progetti.paths, "config_dir", lambda: conf)
    return tmp_path


class TestLIndirizzoDiSviluppo:
    def test_di_default_sta_dentro_data(self, casa_finta):
        radice = progetti.radice_progetti()
        assert radice.name == "progetti"
        assert radice.parent.name == "data"

    def test_viene_creato_se_non_c_e(self, casa_finta):
        assert progetti.radice_progetti().is_dir()

    def test_si_puo_spostare(self, casa_finta, tmp_path):
        altrove = tmp_path / "altro_disco" / "lavori"
        progetti.imposta_radice(str(altrove))
        assert progetti.radice_progetti() == altrove.resolve()

    def test_spostarlo_su_una_radice_pericolosa_viene_rifiutato(self, casa_finta):
        """Accettarla e poi impedire ogni run che la usa sarebbe dire di si'
        e poi di no."""
        with pytest.raises(ValueError):
            progetti.imposta_radice(str(Path.home()))

    def test_una_configurazione_illeggibile_non_rompe_niente(self, casa_finta):
        (Path(paths.config_dir()) / "progetti.json").write_text("{rotto",
                                                                encoding="utf-8")
        assert progetti.radice_progetti().name == "progetti"


class TestIProgetti:
    def test_crearne_uno_e_ritrovarlo(self, casa_finta):
        cartella = progetti.crea_progetto("biblioteca-digitale")
        assert cartella.is_dir()
        nomi = [p["name"] for p in progetti.elenca_progetti()]
        assert "biblioteca-digitale" in nomi

    def test_un_nome_impossibile_viene_rifiutato(self, casa_finta):
        with pytest.raises(ValueError):
            progetti.crea_progetto("   ")
        with pytest.raises(ValueError):
            progetti.crea_progetto("..")

    def test_i_caratteri_vietati_vengono_tolti(self, casa_finta):
        cartella = progetti.crea_progetto('app:di/prova')
        assert ":" not in cartella.name and "/" not in cartella.name

    def test_le_cartelle_nascoste_non_sono_progetti(self, casa_finta):
        (progetti.radice_progetti() / ".cache").mkdir()
        assert progetti.elenca_progetti() == []

    def test_dice_quali_sono_repository(self, casa_finta):
        cartella = progetti.crea_progetto("con-git")
        (cartella / ".git").mkdir()
        voce = [p for p in progetti.elenca_progetti() if p["name"] == "con-git"][0]
        assert voce["is_git"] is True


class TestLeRadiciCheNonSiDanno:
    def test_la_radice_di_un_disco(self):
        radice = "C:/" if os.name == "nt" else "/"
        assert "disco" in progetti.radice_pericolosa(radice)

    def test_la_cartella_utente(self):
        motivo = progetti.radice_pericolosa(str(Path.home()))
        assert "cartella utente" in motivo

    @pytest.mark.skipif(os.name != "nt", reason="cartelle di sistema Windows")
    def test_una_cartella_di_sistema(self):
        assert progetti.radice_pericolosa("C:/Windows/System32")

    def test_niente_non_e_una_radice(self):
        assert progetti.radice_pericolosa("")

    def test_la_cartella_di_un_progetto_va_benissimo(self, casa_finta):
        cartella = progetti.crea_progetto("app")
        assert progetti.radice_pericolosa(str(cartella)) == ""

    def test_sigma_studio_stesso_va_bene(self):
        from core.harness.fs_manager import get_default_workspace_root

        assert progetti.radice_pericolosa(get_default_workspace_root()) == ""


class TestIlVentaglioRifiutaUnaRadiceTroppoLarga:
    def test_non_parte_e_dice_perche(self, tmp_path, monkeypatch):
        """N agenti in parallelo su un disco intero e' lo scenario che nessuno
        vuole scoprire a cose fatte."""
        from core.harness import fanout, workqueue as WQ

        monkeypatch.setattr(WQ.paths, "var_dir", lambda: tmp_path)
        WQ._code.clear()
        radice = "C:/" if os.name == "nt" else "/"
        eventi = list(fanout.run_queue("vuota", workspace_root=radice))
        WQ._code.clear()

        assert len(eventi) == 1
        assert eventi[0]["type"] == "error"
        assert "disco" in eventi[0]["error"]

    def test_su_una_cartella_normale_parte(self, tmp_path, monkeypatch):
        from core.harness import fanout, workqueue as WQ

        monkeypatch.setattr(WQ.paths, "var_dir", lambda: tmp_path)
        WQ._code.clear()
        eventi = list(fanout.run_queue("vuota", workspace_root=str(tmp_path)))
        WQ._code.clear()

        tipi = [e["type"] for e in eventi]
        assert "fanout_started" in tipi


class TestLeRotteEsistono:
    def test_sono_registrate(self):
        from core.modules.sigma_developer_lab.handlers import ROUTES

        percorsi = {(r[0], tuple(r[2])) for r in ROUTES}
        assert ("/api/developer/projects", ("GET",)) in percorsi
        assert ("/api/developer/projects", ("POST",)) in percorsi
        assert ("/api/developer/projects/root", ("POST",)) in percorsi

    def test_il_selettore_segnala_le_radici_pericolose(self):
        """Chi sceglie deve vederlo scritto prima di scegliere, non dopo."""
        import asyncio

        from core.modules.sigma_developer_lab.handlers import handle_workspace_roots

        risposta = asyncio.run(handle_workspace_roots(None))
        import json as _json
        dati = _json.loads(risposta.body)
        assert dati["success"] is True
        generi = {r.get("kind") for r in dati["roots"]}
        assert "projects_root" in generi
        pericolose = [r for r in dati["roots"] if r.get("unsafe")]
        assert pericolose, "la cartella utente e i dischi devono essere segnalati"
