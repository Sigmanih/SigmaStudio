"""Verifiche dell'esplorazione filesystem e I/O per i container Docker."""

import json
from core.harness import docker_fs


class TestParseDockerUri:
    def test_parse_uri_con_subpath(self):
        cid, subpath = docker_fs.parse_docker_uri("docker://abc1234/app/src")
        assert cid == "abc1234"
        assert subpath == "/app/src"

    def test_parse_uri_senza_subpath(self):
        cid, subpath = docker_fs.parse_docker_uri("docker://abc1234")
        assert cid == "abc1234"
        assert subpath == "/"

    def test_parse_uri_non_docker(self):
        cid, path = docker_fs.parse_docker_uri("C:/Users/Sigma/Desktop")
        assert cid is None
        assert path == "C:/Users/Sigma/Desktop"


class TestContainerAttivi:
    def test_elenco_vuoto_se_docker_non_disponibile(self, monkeypatch):
        monkeypatch.setattr(docker_fs, "docker_disponibile", lambda: (False, "assente"))
        assert docker_fs.container_attivi() == []

    def test_parsing_container_attivi(self, monkeypatch):
        monkeypatch.setattr(docker_fs, "docker_disponibile", lambda: (True, "29.7.2"))
        monkeypatch.setattr(docker_fs, "trova_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(docker_fs, "_ambiente_per_docker", lambda: {})

        def falso_run(cmd, *args, **kwargs):
            class FalsoEsito:
                returncode = 0
                stdout = ""
                stderr = ""

            esito = FalsoEsito()
            if "ps" in cmd:
                esito.stdout = json.dumps({
                    "ID": "c1234567890a",
                    "Names": "app_backend",
                    "Image": "node:22",
                    "Status": "Up 2 hours",
                    "Ports": "0.0.0.0:5000->5000/tcp"
                })
            elif "inspect" in cmd:
                esito.stdout = json.dumps([
                    {"Source": "C:/progetti/app", "Destination": "/lavoro"}
                ])
            return esito

        monkeypatch.setattr(docker_fs.subprocess, "run", falso_run)
        risultati = docker_fs.container_attivi()
        assert len(risultati) == 1
        assert risultati[0]["name"] == "app_backend"
        assert risultati[0]["id"] == "c1234567890a"
        assert len(risultati[0]["mounts"]) == 1


class TestLifecycleContainer:
    def test_avvia_container(self, monkeypatch):
        monkeypatch.setattr(docker_fs, "docker_disponibile", lambda: (True, "29.7.2"))
        monkeypatch.setattr(docker_fs, "trova_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(docker_fs, "_ambiente_per_docker", lambda: {})

        chiamati = []
        def falso_run(cmd, *args, **kwargs):
            chiamati.append(cmd)
            class Res:
                returncode = 0
                stdout = "c12345\n"
                stderr = ""
            return Res()

        monkeypatch.setattr(docker_fs.subprocess, "run", falso_run)
        res = docker_fs.avvia_container("c12345")
        assert res["success"] is True
        assert res["id"] == "c12345"
        assert ["/usr/bin/docker", "start", "c12345"] in chiamati

    def test_ferma_container(self, monkeypatch):
        monkeypatch.setattr(docker_fs, "docker_disponibile", lambda: (True, "29.7.2"))
        monkeypatch.setattr(docker_fs, "trova_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(docker_fs, "_ambiente_per_docker", lambda: {})

        chiamati = []
        def falso_run(cmd, *args, **kwargs):
            chiamati.append(cmd)
            class Res:
                returncode = 0
                stdout = "c12345\n"
                stderr = ""
            return Res()

        monkeypatch.setattr(docker_fs.subprocess, "run", falso_run)
        res = docker_fs.ferma_container("c12345")
        assert res["success"] is True
        assert res["id"] == "c12345"
        assert ["/usr/bin/docker", "stop", "-t", "10", "c12345"] in chiamati

    def test_lancia_container(self, monkeypatch):
        monkeypatch.setattr(docker_fs, "docker_disponibile", lambda: (True, "29.7.2"))
        monkeypatch.setattr(docker_fs, "trova_docker", lambda: "/usr/bin/docker")
        monkeypatch.setattr(docker_fs, "_ambiente_per_docker", lambda: {})

        chiamati = []
        def falso_run(cmd, *args, **kwargs):
            chiamati.append(cmd)
            class Res:
                returncode = 0
                stdout = "abcdef1234567890\n"
                stderr = ""
            return Res()

        monkeypatch.setattr(docker_fs.subprocess, "run", falso_run)
        res = docker_fs.lancia_container(
            immagine="python:3.12-slim",
            nome="sigma_test_box",
            porte=["8000:8000"]
        )
        assert res["success"] is True
        assert res["id"] == "abcdef123456"
        assert res["name"] == "sigma_test_box"
        assert any("--name" in c and "sigma_test_box" in c for c in chiamati)

