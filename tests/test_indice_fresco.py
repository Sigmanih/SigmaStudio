"""L'indice semantico deve sapere di essere vecchio.

Il difetto: `index_status` rispondeva «esiste, creato il ...», senza nessuna
nozione di freschezza. Dopo una scrittura - interna o di un client esterno -
`semantic_search` continuava a servire la mappa di prima, e l'indice si
dichiarava aggiornato per sempre. Un agente che scrive e poi cerca lavorava su
una mappa sbagliata **senza saperlo**: il modo peggiore di sbagliare, perche'
non lascia indizi.

Si verifica: che i file cambiati, nuovi e spariti vengano contati, che l'indice
si dichiari indietro quando lo e', che un risultato che viene da un file vecchio
se lo porti scritto addosso, e che un indice costruito prima di questo campo
esista comunque (con la data del file come ripiego).
"""

import json
import os
import time
from pathlib import Path

import pytest

from core.modules.sigma_developer_lab.mcp_tools.semantic_server import SemanticMCPServer

RADICE_SERVER = "core.modules.sigma_developer_lab.mcp_tools.semantic_server.resolve_root"


def _aspetta_un_istante():
    """Le date su disco hanno una granularita' grossa.

    Un file riscritto nello stesso istante della costruzione puo' risultare
    *anteriore* ad essa di qualche millisecondo, e allora «cambiato dopo
    l'indice» diventa falso: il test passava da solo e falliva nella corsa
    piena, dove il disco e' piu' occupato. L'assunzione che va corretta e'
    questa, non il confronto nel codice.
    """
    time.sleep(0.05)


@pytest.fixture
def radice(tmp_path, monkeypatch):
    monkeypatch.setattr(RADICE_SERVER, lambda *a, **kw: str(tmp_path))
    (tmp_path / "rete.py").write_text(
        "import socket\ndef connetti(host, porta):\n    s = socket.socket()\n"
        "    s.connect((host, porta))\n", encoding="utf-8")
    return tmp_path


def _stato(server):
    return json.loads(server.call_tool("index_status", {})["content"][0]["text"])


class TestQuantoEIndietro:
    def test_timestamp_futuro_e_modifica_retrodatata(self, radice):
        # Riproduce lo scarto fra clock Windows e filesystem senza attese.
        sorgente = radice / "rete.py"
        futuro = time.time() + 60
        os.utime(sorgente, (futuro, futuro))
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        assert _stato(server)["aggiornato"] is True
        assert not any(r.get("stale") for r in server._semantic_search("socket"))
        contenuto = sorgente.read_text(encoding="utf-8")
        sorgente.write_text(contenuto.replace("porta", "porte"), encoding="utf-8")
        passato = time.time() - 60
        os.utime(sorgente, (passato, passato))
        assert _stato(server)["modificati"] == 1
        assert any(r.get("stale") for r in server._semantic_search("socket"))

    def test_appena_costruito_e_aggiornato(self, radice):
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        stato = _stato(server)
        assert stato["aggiornato"] is True
        assert stato["modificati"] == 0 and stato["nuovi"] == 0
        assert stato["esaminati"] >= 1, "non ha guardato niente"
        assert stato["costruito_il"] > 0

    def test_un_file_cambiato_lo_rende_vecchio(self, radice):
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        _aspetta_un_istante()
        (radice / "rete.py").write_text(
            "import socket\ndef connetti(host, porta):\n    return None\n",
            encoding="utf-8")
        stato = _stato(server)
        assert stato["aggiornato"] is False
        assert stato["modificati"] == 1, stato
        assert "index_codebase" in stato["message"], stato

    def test_un_file_nuovo_lo_rende_vecchio(self, radice):
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        (radice / "nuovo.py").write_text("def altra_cosa():\n    pass\n",
                                         encoding="utf-8")
        stato = _stato(server)
        assert stato["nuovi"] == 1, stato
        assert stato["aggiornato"] is False

    def test_un_file_sparito_lo_rende_vecchio(self, radice):
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        (radice / "rete.py").unlink()
        stato = _stato(server)
        assert stato["spariti"] == 1, stato

    def test_la_ricerca_segna_i_risultati_vecchi(self, radice):
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        freschi = server._semantic_search("socket connection", top_k=5)
        assert freschi and not any(r.get("stale") for r in freschi)
        _aspetta_un_istante()

        (radice / "rete.py").write_text(
            "import socket\ndef connetti(host, porta):\n    s = socket.socket()\n"
            "    s.connect((host, porta))\n# cambiato\n", encoding="utf-8")
        vecchi = server._semantic_search("socket connection", top_k=5)
        assert any(r.get("stale") for r in vecchi), vecchi

    def test_un_risultato_di_un_file_sparito_lo_dice(self, radice):
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        (radice / "rete.py").unlink()
        risultati = server._semantic_search("socket connection", top_k=5)
        assert any(r.get("mancante") for r in risultati), risultati


class TestGliIndiciVecchi:
    def test_un_indice_senza_data_numerica_usa_il_file(self, radice):
        """Costruito prima che `built_at` esistesse: deve funzionare lo stesso."""
        server = SemanticMCPServer()
        server.call_tool("index_codebase", {})
        server._index.pop("built_at", None)
        for doc in server._index["documents"]:
            doc.pop("mtime_ns", None)
            doc.pop("byte_size", None)
        server._save_index()
        ricaricato = SemanticMCPServer()
        stato = _stato(ricaricato)
        assert stato["costruito_il"] > 0, "senza data un indice e' fresco per sempre"
        assert stato["aggiornato"] is True
