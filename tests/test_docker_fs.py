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
