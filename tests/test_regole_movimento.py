"""Le regole che decidono come si muove un agente nella plancia 3D e 2D.

Le regole stanno in agentMotionRules.json e le applica agentMotion.js; qui si
controlla che ogni strumento dichiarato dall'harness abbia una regola scelta
apposta (altrimenti uno strumento nuovo finirebbe in silenzio alla console) e
che gli esempi etichettati diano la modalita' attesa.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGOLE = json.loads((ROOT / "sigma_studio/src/components/common/agentMotionRules.json").read_text(encoding="utf-8"))
ESEMPI = ROOT / "tools" / "agenti_3d"


def applica(a: dict) -> str:
    # Stessa logica di motionFor() in agentMotion.js
    if a["state"] in REGOLE["stati_certi"]:
        return REGOLE["stati_certi"][a["state"]]
    for r in REGOLE["dettaglio"]:
        if a.get("detail") and re.search(r["schema"], a["detail"], re.IGNORECASE):
            return r["modo"]
    for r in REGOLE["strumento"]:
        if a.get("tool") and re.search(r["schema"], a["tool"].lower()):
            return r["modo"]
    return REGOLE["stato"].get(a["state"], REGOLE["predefinito"])


class TestRegoleMovimento(unittest.TestCase):
    def test_gli_schemi_compilano(self):
        for gruppo in ("dettaglio", "strumento"):
            for r in REGOLE[gruppo]:
                re.compile(r["schema"])

    def test_ogni_strumento_dell_harness_ha_una_regola(self):
        from core.harness.tool_schema import declared_tools

        strumenti = sorted(declared_tools())
        self.assertTrue(strumenti, "nessuno strumento dichiarato: il controllo non ha guardato niente")
        senza = [t for t in strumenti if not any(re.search(r["schema"], t.lower()) for r in REGOLE["strumento"])]
        self.assertEqual(senza, [], "strumenti senza regola di movimento: aggiungerli a agentMotionRules.json")

    def test_esempi_etichettati(self):
        for nome in ("attivita_campione.json", "attivita_verifica.json"):
            with self.subTest(nome=nome):
                esempi = json.loads((ESEMPI / nome).read_text(encoding="utf-8"))
                sbagliati = [f"{a['state']}/{a['tool'] or '-'}/{a['detail'][:40]}: {applica(a)} invece di {a['atteso']}"
                             for a in esempi if applica(a) != a["atteso"]]
                self.assertEqual(sbagliati, [])


if __name__ == "__main__":
    unittest.main()
