"""Foto e modelli 3D che viaggiano con i ruoli (pacchetti di SigmaStudio-Ruoli).

Un ruolo installato porta con se' immagine, busto, dettagli e personaggio in
roles/<id>/; disinstallato li porta via. Il server li espone sotto /ruoli/<id>/
ma solo con i nomi ammessi: i manifesti e i ruoli privati restano fuori.
La rete e' simulata: nessuna prova tocca GitHub.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.agents import manifests_catalog as MC


class _Risposta:
    def __init__(self, dati: bytes):
        self._dati = dati

    def read(self) -> bytes:
        return self._dati

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


INDICE = {"manifests": [{"id": "medico", "risorse": {
    "immagine": "medico/immagine.jpg", "modello3d": "medico/modello.glb",
    "dettagli": "medico/modello.json", "personaggio": "medico/personaggio.glb"}}]}


def _rete_finta(file_remoti: dict):
    def urlopen(req, timeout=0):
        url = req.full_url
        if url.endswith("manifests_index.json"):
            return _Risposta(json.dumps(INDICE).encode())
        nome = url.rsplit("/main/", 1)[1]
        if nome not in file_remoti:
            raise OSError(f"404 {nome}")
        return _Risposta(file_remoti[nome])
    return urlopen


class TestCatalogo(unittest.TestCase):
    def test_il_catalogo_offline_e_trovato(self):
        # Il percorso puntava a core/agents/agents/catalog: catalogo vuoto, hub muto
        self.assertTrue(MC.CATALOG_INDEX.exists(), MC.CATALOG_INDEX)
        self.assertGreater(len(MC.reload_catalog()), 0)


class TestRisorse(unittest.TestCase):
    def setUp(self):
        self.ruoli = Path(tempfile.mkdtemp())
        (self.ruoli / "medico.md").write_text("FROM sigma\n", encoding="utf-8")
        self.remoti = {"medico/immagine.jpg": b"jpg", "medico/modello.glb": b"glb",
                       "medico/modello.json": b'{"collo": 0.5}', "medico/personaggio.glb": b"rig"}

    def tearDown(self):
        shutil.rmtree(self.ruoli, ignore_errors=True)

    def test_installa_scarica_le_risorse_dichiarate(self):
        with mock.patch("urllib.request.urlopen", _rete_finta(self.remoti)):
            scritti = MC.installa_risorse("medico", self.ruoli)
        self.assertEqual(sorted(scritti), ["immagine.jpg", "modello.glb", "modello.json", "personaggio.glb"])
        self.assertEqual((self.ruoli / "medico" / "personaggio.glb").read_bytes(), b"rig")

    def test_una_risorsa_mancante_non_ferma_le_altre(self):
        del self.remoti["medico/personaggio.glb"]
        with mock.patch("urllib.request.urlopen", _rete_finta(self.remoti)):
            scritti = MC.installa_risorse("medico", self.ruoli)
        self.assertNotIn("personaggio.glb", scritti)
        self.assertIn("modello.glb", scritti)

    def test_percorsi_fuori_dal_ruolo_sono_ignorati(self):
        risorse = {"x": "../config/segreti.json", "y": "altro/modello.glb", "z": "medico/script.js"}
        with mock.patch("urllib.request.urlopen", _rete_finta(self.remoti)):
            self.assertEqual(MC.installa_risorse("medico", self.ruoli, risorse=risorse), [])
        self.assertFalse((self.ruoli / "medico").exists())

    def test_aggiorna_scarica_solo_cio_che_manca(self):
        (self.ruoli / "medico").mkdir()
        (self.ruoli / "medico" / "modello.glb").write_bytes(b"locale")
        with mock.patch("urllib.request.urlopen", _rete_finta(self.remoti)):
            esito = MC.aggiorna_risorse_installate(self.ruoli)
        self.assertEqual(sorted(esito["medico"]), ["immagine.jpg", "modello.json", "personaggio.glb"])
        self.assertEqual((self.ruoli / "medico" / "modello.glb").read_bytes(), b"locale")

    def test_rimuovi_toglie_la_cartella_ma_non_file_estranei(self):
        cartella = self.ruoli / "medico"
        cartella.mkdir()
        (cartella / "modello.glb").write_bytes(b"glb")
        MC.rimuovi_risorse("medico", self.ruoli)
        self.assertFalse(cartella.exists())
        cartella.mkdir()
        (cartella / "appunti.txt").write_text("mio", encoding="utf-8")
        MC.rimuovi_risorse("medico", self.ruoli)
        self.assertTrue((cartella / "appunti.txt").exists())

    def test_private_non_e_mai_un_ruolo(self):
        (self.ruoli / "Private").mkdir()
        MC.rimuovi_risorse("Private", self.ruoli)
        self.assertTrue((self.ruoli / "Private").exists())


class TestElencoEServer(unittest.TestCase):
    def setUp(self):
        self.ruoli = Path(tempfile.mkdtemp())
        (self.ruoli / "medico.md").write_text("FROM sigma\n# Role: Medico\n", encoding="utf-8")
        (self.ruoli / "medico").mkdir()
        for nome, dati in (("modello.glb", b"glb"), ("modello.json", b'{"collo": 0.47}'),
                           ("personaggio.glb", b"rig"), ("immagine.jpg", b"jpg")):
            (self.ruoli / "medico" / nome).write_bytes(dati)

    def tearDown(self):
        shutil.rmtree(self.ruoli, ignore_errors=True)

    def test_list_manifesti_espone_busto_personaggio_e_immagine(self):
        from core.handlers.data_handler import _parse_manifesto_file
        voce = _parse_manifesto_file(str(self.ruoli / "medico.md"), "medico.md", {}, {})
        self.assertEqual(voce["model3d"], {"url": "/ruoli/medico/modello.glb", "collo": 0.47})
        self.assertEqual(voce["character3d"], {"url": "/ruoli/medico/personaggio.glb"})
        self.assertEqual(voce["image"], "/ruoli/medico/immagine.jpg")
        self.assertTrue(voce["active"])

    def test_agente_sospeso_non_e_attivo(self):
        from core.handlers.data_handler import _parse_manifesto_file
        meta = {"agents": {"m": {"manifesto": "roles/medico.md", "status": "paused"}}}
        voce = _parse_manifesto_file(str(self.ruoli / "medico.md"), "medico.md", meta, {})
        self.assertFalse(voce["active"])

    def test_il_server_espone_solo_le_risorse(self):
        from fastapi.testclient import TestClient
        from core import fastapi_app
        with mock.patch("core.paths.roles_dir", return_value=self.ruoli):
            client = TestClient(fastapi_app.app)
            self.assertEqual(client.get("/ruoli/medico/personaggio.glb").content, b"rig")
            # Il manifesto c'e' su disco ma non e' una risorsa: non esce da /ruoli/,
            # nemmeno risalendo di cartella (a quel punto risponde la pagina della SPA)
            manifesto = (self.ruoli / "medico.md").read_bytes()
            self.assertNotEqual(client.get("/ruoli/medico.md").content, manifesto)
            self.assertNotEqual(client.get("/ruoli/medico/../medico.md").content, manifesto)
            self.assertNotEqual(client.get("/ruoli/%2e%2e/medico.md").content, manifesto)


if __name__ == "__main__":
    unittest.main()
