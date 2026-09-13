from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import paths
from core.harness import esecutori as E
from core.harness.immagini import descrivi, immagine_per

NODE = "node:22-slim"
PYTHON = "python:3.12-slim"
MISTO = "nikolaik/python-nodejs:python3.12-nodejs22"


def _crea_progetto(
    tmp_path: Path,
    nome: str,
    *,
    node: bool = False,
    python_file: str | None = None,
    sandbox_image: str | None = None,
) -> Path:
    radice = tmp_path / nome
    radice.mkdir()
    if node:
        (radice / "package.json").write_text("{}", encoding="utf-8")
    if python_file is not None:
        (radice / python_file).write_text("# progetto reale\n", encoding="utf-8")
    if sandbox_image is not None:
        (radice / "sandbox.json").write_text(
            json.dumps({"image": sandbox_image}), encoding="utf-8"
        )
    return radice


def test_immagine_per_rileva_python(tmp_path: Path) -> None:
    radice = _crea_progetto(tmp_path, "python", python_file="requirements.txt")

    assert immagine_per(radice) == PYTHON
    assert descrivi(radice) == {"immagine": PYTHON, "perche": "requirements.txt"}


def test_immagine_per_rileva_python_sul_pyproject(tmp_path: Path) -> None:
    radice = _crea_progetto(tmp_path, "pyproject", python_file="pyproject.toml")

    assert immagine_per(radice) == PYTHON
    assert descrivi(radice)["perche"] == "pyproject.toml"


def test_immagine_per_rileva_node(tmp_path: Path) -> None:
    radice = _crea_progetto(tmp_path, "node", node=True)

    assert immagine_per(radice) == NODE
    assert descrivi(radice) == {"immagine": NODE, "perche": "package.json"}


def test_immagine_per_rileva_progetto_misto(tmp_path: Path) -> None:
    radice = _crea_progetto(
        tmp_path,
        "misto",
        node=True,
        python_file="requirements.txt",
    )

    assert immagine_per(radice) == MISTO
    assert descrivi(radice) == {
        "immagine": MISTO,
        "perche": "package.json + requirements.txt",
    }


def test_sandbox_del_progetto_prevede_su_tutti_i_segnali(tmp_path: Path) -> None:
    radice = _crea_progetto(
        tmp_path,
        "sandbox-precede",
        node=True,
        python_file="requirements.txt",
        sandbox_image="progetto:immagine-esplicita",
    )

    assert immagine_per(radice) == "progetto:immagine-esplicita"
    assert descrivi(radice) == {
        "immagine": "progetto:immagine-esplicita",
        "perche": "sandbox.json",
    }


def test_sandbox_globale_fornisce_l_immagine_se_non_ci_sono_segnali(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    radice = _crea_progetto(tmp_path, "vuoto")
    (tmp_path / "sandbox.json").write_text(
        json.dumps({"image": "configurazione:fallback"}), encoding="utf-8"
    )
    monkeypatch.setattr(paths, "config_dir", lambda: str(tmp_path))

    assert immagine_per(radice) == "configurazione:fallback"
    assert descrivi(radice) == {
        "immagine": "configurazione:fallback",
        "perche": "config/sandbox.json",
    }


def test_scegli_esecutore_usa_l_immagine_del_progetto(tmp_path: Path) -> None:
    radice = _crea_progetto(
        tmp_path,
        "esecutore",
        node=True,
        python_file="requirements.txt",
    )
    configurazione = {
        "mode": "container",
        "network": False,
        "memory": "",
        "cpus": "",
    }

    esecutore = E.scegli_esecutore(configurazione, radice=radice)

    assert isinstance(esecutore, E.EsecutoreContenitore)
    assert esecutore.immagine == MISTO


def test_scegli_esecutore_mantiene_l_immagine_di_configurazione_senza_radice(
    tmp_path: Path,
) -> None:
    configurazione = {
        "mode": "container",
        "image": "configurazione:legacy",
        "network": False,
        "memory": "",
        "cpus": "",
    }

    esecutore = E.scegli_esecutore(configurazione)

    assert isinstance(esecutore, E.EsecutoreContenitore)
    assert esecutore.immagine == configurazione["image"]
