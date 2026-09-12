"""Dove girano i comandi dell'agente, e cosa il contenitore deve garantire.

I tool di file hanno un recinto; il tool `terminal` non ne ha nessuno: esegue
una shell con l'ambiente intero del processo, e una `cwd` non e' un confine
perche' `cd ..` e' una riga. Il contenitore e' la meta' mancante.

Docker non e' installato su questa macchina, e questi test non lo richiedono:
la parte che si puo' e si deve verificare senza e' **come viene costruita la
riga di comando**. Sono tre proprieta', e sono esattamente quelle che
distinguono una sandbox da un modo complicato di eseguire un comando.
"""

import json
import os
from pathlib import Path

import pytest

from core.harness import esecutori as E


class TestLaRigaDiComandoDelContenitore:
    def test_monta_la_cartella_di_lavoro_e_ci_si_mette_dentro(self, tmp_path):
        argv = E.EsecutoreContenitore().argv("pytest -q", str(tmp_path))
        montaggio = f"{Path(tmp_path).resolve()}:{E.PUNTO_DI_MONTAGGIO}"
        assert "-v" in argv and montaggio in argv
        assert argv[argv.index("-w") + 1] == E.PUNTO_DI_MONTAGGIO

    def test_monta_il_worktree_e_non_il_repository(self, tmp_path):
        """Con l'isolamento acceso ogni run ha il suo albero: montare la radice
        del progetto rimetterebbe in comunicazione i lavoratori paralleli che
        l'isolamento serve a separare."""
        repository = tmp_path / "progetto"
        worktree = tmp_path / "sigma-run" / "w1"
        worktree.mkdir(parents=True)
        repository.mkdir()

        argv = E.EsecutoreContenitore().argv("pytest", str(worktree))
        montaggi = [argv[i + 1] for i, v in enumerate(argv) if v == "-v"]
        assert any(str(worktree.resolve()) in m for m in montaggi)
        assert not any(m.startswith(str(repository.resolve()) + ":") for m in montaggi)

    def test_la_rete_e_spenta_per_default(self, tmp_path):
        argv = E.EsecutoreContenitore().argv("pytest", str(tmp_path))
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"

    def test_la_rete_si_puo_accendere_apposta(self, tmp_path):
        """Senza deroga `npm install` non funziona, e la prima voce della coda
        fallirebbe facendo sembrare sbagliata l'idea invece che stretta la
        regola."""
        argv = E.EsecutoreContenitore(rete=True).argv("npm install", str(tmp_path))
        assert "none" not in argv

    def test_l_ambiente_e_una_lista_bianca(self, tmp_path, monkeypatch):
        """L'esecutore sull'host passa dict(os.environ). Qui no: ereditare
        l'ambiente e' comodo finche' non ci si accorge di cosa contiene."""
        monkeypatch.setenv("HF_TOKEN", "questo-non-deve-uscire")
        argv = E.EsecutoreContenitore().argv("env", str(tmp_path))
        intero = " ".join(argv)
        assert "HF_TOKEN" not in intero
        assert "questo-non-deve-uscire" not in intero
        assert "CI=1" in intero

    def test_il_contenitore_e_usa_e_getta(self, tmp_path):
        assert "--rm" in E.EsecutoreContenitore().argv("x", str(tmp_path))

    def test_i_limiti_di_macchina_ci_sono(self, tmp_path):
        argv = E.EsecutoreContenitore(memoria="2g", cpu="1").argv("x", str(tmp_path))
        assert argv[argv.index("--memory") + 1] == "2g"
        assert argv[argv.index("--cpus") + 1] == "1"

    def test_il_comando_arriva_intero(self, tmp_path):
        comando = "python -m pytest tests/ -q && echo fatto"
        argv = E.EsecutoreContenitore().argv(comando, str(tmp_path))
        assert argv[-1] == comando
        assert argv[-3:-1] == ["sh", "-lc"]


class TestQuandoDockerNonCE:
    def test_non_si_ripiega_in_silenzio_sull_host(self, tmp_path, monkeypatch):
        """E' la regola piu' importante di tutte: chi ha acceso la sandbox
        crederebbe di essere protetto senza esserlo."""
        monkeypatch.setattr(E, "docker_disponibile", lambda: (False, "non installato"))
        traccia = []
        monkeypatch.setattr(E.subprocess, "run",
                            lambda *a, **k: traccia.append(a) or None)

        esito = E.EsecutoreContenitore().esegui("rm -rf /", cwd=str(tmp_path))
        assert esito.success is False
        assert traccia == [], "il comando non deve essere stato eseguito"
        assert "NON e' stato eseguito" in esito.stderr

    def test_l_errore_dice_cosa_manca(self, tmp_path, monkeypatch):
        monkeypatch.setattr(E, "docker_disponibile",
                            lambda: (False, "Docker non e' installato"))
        esito = E.EsecutoreContenitore().esegui("ls", cwd=str(tmp_path))
        assert "non e' installato" in esito.stderr

    def test_docker_disponibile_distingue_assente_da_spento(self, monkeypatch):
        monkeypatch.setattr(E.shutil, "which", lambda _: None)
        # Anche i posti noti vanno svuotati: da quando `trova_docker` li
        # guarda, togliere Docker dal PATH non basta piu' a farlo sparire —
        # ed e' proprio il punto di quella ricerca.
        monkeypatch.setattr(E, "_posti_noti", list)
        ok, motivo = E.docker_disponibile()
        assert ok is False
        assert "non e' installato" in motivo

    def test_lo_trova_anche_fuori_dal_PATH(self, tmp_path, monkeypatch):
        """Su Windows Docker Desktop si installa per utente e aggiunge la sua
        cartella al PATH **dell'utente**: un server gia' avviato ha ereditato
        il PATH di prima e non lo vedra' mai. E' successo davvero, e la
        risposta «Docker non e' installato» era sbagliata, non incompleta."""
        finto = tmp_path / "docker.exe"
        finto.write_text("", encoding="utf-8")
        monkeypatch.setattr(E.shutil, "which", lambda _: None)
        monkeypatch.setattr(E, "_posti_noti", lambda: [finto])
        assert E.trova_docker() == str(finto)

    def test_il_contenitore_usa_l_eseguibile_trovato(self, tmp_path, monkeypatch):
        """Passare la parola «docker» quando non e' nel PATH farebbe fallire il
        contenitore per una ragione che non c'entra col comando dell'agente."""
        finto = tmp_path / "docker.exe"
        finto.write_text("", encoding="utf-8")
        monkeypatch.setattr(E, "trova_docker", lambda: str(finto))
        argv = E.EsecutoreContenitore().argv("pytest", str(tmp_path))
        assert argv[0] == str(finto)


class TestLaScelta:
    def test_senza_configurazione_si_resta_sull_host(self, tmp_path, monkeypatch):
        """Accendere una sandbox di nascosto cambierebbe il comportamento di
        run gia' scritti."""
        monkeypatch.setattr(E.paths, "config_dir", lambda: tmp_path)
        assert isinstance(E.scegli_esecutore(), E.EsecutoreHost)

    def test_la_configurazione_accende_il_contenitore(self, tmp_path, monkeypatch):
        monkeypatch.setattr(E.paths, "config_dir", lambda: tmp_path)
        (tmp_path / "sandbox.json").write_text(
            json.dumps({"mode": "container", "image": "node:22", "network": True}),
            encoding="utf-8")
        esecutore = E.scegli_esecutore()
        assert isinstance(esecutore, E.EsecutoreContenitore)
        assert esecutore.immagine == "node:22"
        assert esecutore.rete is True

    def test_una_configurazione_rotta_non_accende_niente(self, tmp_path, monkeypatch):
        monkeypatch.setattr(E.paths, "config_dir", lambda: tmp_path)
        (tmp_path / "sandbox.json").write_text("{rotto", encoding="utf-8")
        assert isinstance(E.scegli_esecutore(), E.EsecutoreHost)

    def test_le_chiavi_sconosciute_non_entrano(self, tmp_path, monkeypatch):
        monkeypatch.setattr(E.paths, "config_dir", lambda: tmp_path)
        (tmp_path / "sandbox.json").write_text(
            json.dumps({"mode": "host", "privileged": True}), encoding="utf-8")
        assert "privileged" not in E.carica_config()


class TestLEsecutoreHostNonHaCambiatoNiente:
    def test_un_comando_semplice_gira(self, tmp_path):
        esito = E.EsecutoreHost().esegui("echo ciao", cwd=str(tmp_path))
        assert esito.returncode == 0
        assert "ciao" in esito.stdout
        assert esito.dove == "host"


class TestIlToolTerminalePassaDaLi:
    def test_il_ramo_del_tool_usa_l_esecutore(self):
        """Il difetto piu' frequente di questo progetto e' la cucitura scritta
        e mai percorsa: qui si verifica che il tool ci passi davvero."""
        import inspect

        from core.harness.loop import _execute_admin_tool_impl

        sorgente = inspect.getsource(_execute_admin_tool_impl)
        assert "scegli_esecutore(" in sorgente
        assert "radice=workspace_root" in sorgente, (
            "senza la radice ogni contenitore userebbe l'immagine generale, e "
            "un frontend Vite dentro python:3.12-slim non ha node")

    def test_il_risultato_dice_dove_e_girato(self, tmp_path):
        from core.harness.loop import execute_admin_tool

        esito = execute_admin_tool("terminal", {"command": "echo ciao"},
                                   str(tmp_path))
        assert esito["success"] is True
        assert esito["dove"] == "host"


def test_lo_stato_per_l_interfaccia_e_onesto(tmp_path, monkeypatch):
    """`active` deve essere vero solo se la sandbox e' chiesta **e** possibile:
    dire «accesa» quando Docker non c'e' sarebbe la bugia peggiore."""
    monkeypatch.setattr(E.paths, "config_dir", lambda: tmp_path)
    (tmp_path / "sandbox.json").write_text(json.dumps({"mode": "container"}),
                                           encoding="utf-8")
    monkeypatch.setattr(E, "docker_disponibile", lambda: (False, "assente"))
    stato = E.stato_sandbox()
    assert stato["mode"] == "container"
    assert stato["docker_available"] is False
    assert stato["active"] is False


class TestLeRotteDellaSandbox:
    def test_sono_registrate(self):
        from core.modules.sigma_developer_lab.handlers import ROUTES

        percorsi = {(r[0], tuple(r[2])) for r in ROUTES}
        assert ("/api/developer/sandbox", ("GET",)) in percorsi
        assert ("/api/developer/sandbox", ("POST",)) in percorsi

    def test_lo_stato_arriva_all_interfaccia(self):
        import asyncio
        import json as _json

        from core.modules.sigma_developer_lab.handlers import handle_sandbox

        dati = _json.loads(asyncio.run(handle_sandbox(None)).body)
        assert dati["success"] is True
        assert "docker_available" in dati and "active" in dati


class TestLaModalitaEDelProgetto:
    """La domanda «host o contenitore» non ha una risposta sola: dipende da
    dove stanno gli strumenti con cui quel lavoro si dimostra.

    Misurato accendendo la sandbox su Sigma Studio stesso: dentro
    `python:3.12-slim` non ci sono ne' pytest ne' fastapi, e OGNI verifica
    falliva con «No module named pytest». Le dipendenze di questo progetto
    stanno nel .venv dell'host, e un worktree non se le porta.
    """

    GENERALE = {"mode": "host", "image": "python:3.12-slim", "network": False,
                "memory": "4g", "cpus": "2"}

    def test_senza_sandbox_json_vale_la_configurazione_generale(self, tmp_path):
        assert isinstance(E.scegli_esecutore(self.GENERALE, radice=str(tmp_path)),
                          E.EsecutoreHost)

    def test_il_progetto_puo_chiedere_il_contenitore(self, tmp_path):
        (tmp_path / "sandbox.json").write_text(
            json.dumps({"mode": "container"}), encoding="utf-8")
        assert isinstance(E.scegli_esecutore(self.GENERALE, radice=str(tmp_path)),
                          E.EsecutoreContenitore)

    def test_il_progetto_puo_restare_sull_host_quando_il_generale_dice_contenitore(
            self, tmp_path):
        """E' il caso di Sigma Studio: il suo ambiente e' sull'host."""
        (tmp_path / "sandbox.json").write_text(
            json.dumps({"mode": "host"}), encoding="utf-8")
        generale = dict(self.GENERALE, mode="container")
        assert isinstance(E.scegli_esecutore(generale, radice=str(tmp_path)),
                          E.EsecutoreHost)

    def test_un_sandbox_json_rotto_non_cambia_niente(self, tmp_path):
        (tmp_path / "sandbox.json").write_text("{rotto", encoding="utf-8")
        generale = dict(self.GENERALE, mode="container")
        assert isinstance(E.scegli_esecutore(generale, radice=str(tmp_path)),
                          E.EsecutoreContenitore), "si ricade sul generale"

    def test_senza_radice_decide_la_configurazione_generale(self):
        assert isinstance(E.scegli_esecutore(self.GENERALE), E.EsecutoreHost)


class TestLaCacheDelleDipendenze:
    def test_i_volumi_ci_sono_e_hanno_nomi_stabili(self, tmp_path):
        """Una cache con un nome diverso ogni volta non e' una cache."""
        primo = E.EsecutoreContenitore().argv("npm install", str(tmp_path))
        secondo = E.EsecutoreContenitore().argv("npm install", str(tmp_path))
        volumi = [primo[i + 1] for i, v in enumerate(primo) if v == "-v"]
        assert any(v.startswith("sigma-cache-npm:") for v in volumi)
        assert primo == secondo

    def test_le_cache_non_finiscono_nel_workspace(self, tmp_path):
        """Dentro /lavoro, node_modules comparirebbe nel diff del run e chi
        rivede si troverebbe diecimila file al posto delle tre che contano."""
        argv = E.EsecutoreContenitore().argv("npm install", str(tmp_path))
        montaggi = [argv[i + 1] for i, v in enumerate(argv) if v == "-v"]
        for montaggio in montaggi:
            dentro = montaggio.rsplit(":", 1)[-1]
            if dentro == E.PUNTO_DI_MONTAGGIO:
                continue
            assert not dentro.startswith(E.PUNTO_DI_MONTAGGIO + "/"), dentro

    def test_home_non_e_il_workspace(self):
        """Con HOME in /lavoro npm ci scrive dentro la propria cache, e va
        persa a ogni run perche' il worktree di un run isolato e' nuovo."""
        assert E.AMBIENTE_CONTENITORE["HOME"] != E.PUNTO_DI_MONTAGGIO

    def test_ogni_gestore_punta_alla_propria_cache_per_nome(self):
        """Dedurla da HOME funziona finche' qualcuno non cambia HOME, e allora
        il volume resta montato e inutilizzato: sembra a posto e non lo e'."""
        ambiente = E.AMBIENTE_CONTENITORE
        montati = set(E.CACHE_DIPENDENZE.values())
        assert ambiente["npm_config_cache"] in montati
        assert ambiente["PIP_CACHE_DIR"] in montati
