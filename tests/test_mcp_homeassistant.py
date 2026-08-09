# ==============================================================================
# tests/test_mcp_homeassistant.py — Targeting, colore ed effetti delle luci
# ==============================================================================
"""Cosa arriva davvero a Home Assistant quando un agente comanda le luci.

Il caso che ha motivato questi test: «spegni le luci dell'ufficio» ne spegneva
una sola. Due cause distinte — lo strumento accettava una entità per volta, e il
ciclo degli strumenti buttava via le chiamate oltre la prima in attesa di
conferma — quindi qui si verificano entrambe.

Home Assistant è simulato: le chiamate vere accenderebbero le luci di chi lancia
la suite.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from core.mcp import governance, mcp_hub
from core.mcp.agent_loop import execute_calls


class FakeHomeAssistant:
    """Registra le richieste e risponde come farebbe l'istanza vera."""

    def __init__(self, states=None, areas=None):
        self.calls = []
        self.states = states if states is not None else DEFAULT_STATES
        self.areas = areas if areas is not None else DEFAULT_AREAS

    def __call__(self, method, path, payload=None, raw=False):
        self.calls.append({"method": method, "path": path, "payload": payload})

        if path == "states":
            return self.states
        if path.startswith("states/"):
            wanted = path.split("/", 1)[1]
            return next((s for s in self.states if s["entity_id"] == wanted), {})
        if path == "template":
            return self._render(payload.get("template", ""))
        if path.startswith("services/"):
            return []
        return {}

    def _render(self, template):
        """Solo i due template che il server usa davvero."""
        if "area_entities(a)" in template:
            return json.dumps([
                {"id": a["id"], "name": a["name"], "entities": a["entities"]}
                for a in self.areas
            ])
        if "area_entities(" in template:
            name = template.split("area_entities('")[1].split("')")[0]
            for area in self.areas:
                if name.lower() in (area["id"].lower(), area["name"].lower()):
                    return json.dumps(area["entities"])
            return json.dumps([])
        return "null"

    def service_payloads(self, service_suffix):
        return [c["payload"] for c in self.calls
                if c["path"].startswith("services/") and c["path"].endswith(service_suffix)]


DEFAULT_STATES = [
    {"entity_id": "light.ufficio_1", "state": "on",
     "attributes": {"friendly_name": "Luce ufficio 1",
                    "supported_color_modes": ["color_temp", "hs"],
                    "min_color_temp_kelvin": 2000, "max_color_temp_kelvin": 6535,
                    "brightness": 200, "color_mode": "hs",
                    "effect_list": ["Arcobaleno", "Respiro", "Festa"], "effect": "Respiro"}},
    {"entity_id": "light.ufficio_2", "state": "on",
     "attributes": {"friendly_name": "Luce ufficio 2", "supported_color_modes": ["onoff"]}},
    {"entity_id": "light.ufficio_3", "state": "on",
     "attributes": {"friendly_name": "Luce ufficio 3", "supported_color_modes": ["brightness"]}},
    {"entity_id": "light.cucina", "state": "off",
     "attributes": {"friendly_name": "Luce cucina", "supported_color_modes": ["onoff"]}},
    {"entity_id": "switch.stampante", "state": "off", "attributes": {"friendly_name": "Stampante"}},
]

DEFAULT_AREAS = [
    {"id": "ufficio", "name": "Ufficio",
     "entities": ["light.ufficio_1", "light.ufficio_2", "light.ufficio_3", "switch.stampante"]},
    {"id": "cucina", "name": "Cucina", "entities": ["light.cucina"]},
]


class HomeAssistantTestCase(unittest.TestCase):
    def setUp(self):
        handle, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        self._patch_cfg = mock.patch.object(governance, "CONFIG_PATH", self.config_path)
        self._patch_cfg.start()
        governance.reset_pending()
        governance.set_integration_config(
            "home_assistant", {"base_url": "http://ha.invalid:8123", "token": "t"})

        self.server = mcp_hub.get_server("HomeAssistant MCP")
        self.ha = FakeHomeAssistant()
        self._patch_req = mock.patch.object(self.server, "_request", self.ha)
        self._patch_req.start()

    def tearDown(self):
        self._patch_req.stop()
        self._patch_cfg.stop()
        governance.reset_pending()
        try:
            os.unlink(self.config_path)
        except OSError:
            pass

    def run_tool(self, name, args):
        governance.set_auto_approve(True)          # qui si verifica il comando, non il cancello
        outcome = mcp_hub.execute_tool(name, args)
        self.assertEqual(outcome["status"], "ok", outcome.get("error"))
        return json.loads(outcome["result"]["content"][0]["text"])


class TestTargeting(HomeAssistantTestCase):
    def test_an_area_turns_off_every_light_in_one_call(self):
        """Il caso che ha motivato tutto: una richiesta, una chiamata, tre luci."""
        result = self.run_tool("ha_light_set", {"area": "ufficio", "state": "off"})

        self.assertEqual(result["count"], 3)
        payloads = self.ha.service_payloads("light/turn_off")
        self.assertEqual(len(payloads), 1, "una sola chiamata di servizio, non una per lampada")
        self.assertEqual(sorted(payloads[0]["entity_id"]),
                         ["light.ufficio_1", "light.ufficio_2", "light.ufficio_3"])

    def test_the_area_does_not_drag_in_other_domains(self):
        """Nell'ufficio c'è anche una presa: spegnere le luci non la tocca."""
        result = self.run_tool("ha_light_set", {"area": "ufficio", "state": "off"})
        self.assertNotIn("switch.stampante", result["entities"])

    def test_a_list_of_entities_is_one_call(self):
        result = self.run_tool("ha_light_set",
                               {"entity_id": ["light.ufficio_1", "light.cucina"], "state": "on"})
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(self.ha.service_payloads("light/turn_on")), 1)

    def test_a_comma_separated_string_is_accepted(self):
        """I modelli scrivono spesso un elenco come stringa unica."""
        result = self.run_tool("ha_light_set",
                               {"entity_id": "light.ufficio_1, light.ufficio_2", "state": "off"})
        self.assertEqual(result["count"], 2)

    def test_an_unknown_area_says_which_ones_exist(self):
        governance.set_auto_approve(True)
        outcome = mcp_hub.execute_tool("ha_light_set", {"area": "taverna", "state": "off"})
        self.assertEqual(outcome["status"], "error")
        self.assertIn("Ufficio", outcome["error"])

    def test_a_target_is_required(self):
        governance.set_auto_approve(True)
        outcome = mcp_hub.execute_tool("ha_light_set", {"state": "off"})
        self.assertEqual(outcome["status"], "error")
        self.assertIn("entity_id", outcome["error"])

    def test_switches_take_areas_too(self):
        result = self.run_tool("ha_switch_set", {"area": "ufficio", "state": "on"})
        self.assertEqual(result["entities"], ["switch.stampante"])


class TestLightFeatures(HomeAssistantTestCase):
    def test_colour_brightness_and_effect_travel_together(self):
        self.run_tool("ha_light_set", {
            "entity_id": "light.ufficio_1", "state": "on",
            "rgb_color": [255, 120, 0], "brightness_pct": 80,
            "effect": "Arcobaleno", "transition": 2,
        })
        sent = self.ha.service_payloads("light/turn_on")[0]
        self.assertEqual(sent["rgb_color"], [255, 120, 0])
        self.assertEqual(sent["brightness_pct"], 80)
        self.assertEqual(sent["effect"], "Arcobaleno")
        self.assertEqual(sent["transition"], 2)

    def test_only_the_most_specific_colour_is_sent(self):
        """Tre modi di dire il colore insieme fanno vincere l'ultimo a caso."""
        self.run_tool("ha_light_set", {
            "entity_id": "light.ufficio_1", "state": "on",
            "rgb_color": [10, 20, 30], "color_name": "red", "color_temp_kelvin": 4000,
        })
        sent = self.ha.service_payloads("light/turn_on")[0]
        self.assertIn("rgb_color", sent)
        self.assertNotIn("color_name", sent)
        self.assertNotIn("color_temp_kelvin", sent)

    def test_a_fade_applies_to_switching_off(self):
        self.run_tool("ha_light_set",
                      {"entity_id": "light.ufficio_1", "state": "off", "transition": 3})
        self.assertEqual(self.ha.service_payloads("light/turn_off")[0]["transition"], 3)

    def test_colour_is_not_sent_when_switching_off(self):
        self.run_tool("ha_light_set",
                      {"entity_id": "light.ufficio_1", "state": "off", "rgb_color": [1, 2, 3]})
        self.assertNotIn("rgb_color", self.ha.service_payloads("light/turn_off")[0])

    def test_rgb_values_are_clamped(self):
        self.run_tool("ha_light_set",
                      {"entity_id": "light.ufficio_1", "state": "on", "rgb_color": [999, -5, 128]})
        self.assertEqual(self.ha.service_payloads("light/turn_on")[0]["rgb_color"], [255, 0, 128])

    def test_percentage_beats_raw_brightness(self):
        self.run_tool("ha_light_set", {"entity_id": "light.ufficio_1", "state": "on",
                                       "brightness": 10, "brightness_pct": 50})
        sent = self.ha.service_payloads("light/turn_on")[0]
        self.assertEqual(sent["brightness_pct"], 50)
        self.assertNotIn("brightness", sent)


class TestCapabilityDiscovery(HomeAssistantTestCase):
    def test_lights_report_what_they_can_do(self):
        """Senza questo l'agente prova effetti che la lampada non ha."""
        result = self.run_tool("ha_list_entities", {"domain": "light"})
        by_id = {e["entity_id"]: e for e in result["entities"]}

        rich = by_id["light.ufficio_1"]["capabilities"]
        self.assertEqual(rich["effects"], ["Arcobaleno", "Respiro", "Festa"])
        self.assertEqual(rich["kelvin_range"], [2000, 6535])
        self.assertIn("hs", rich["color_modes"])

        plain = by_id["light.ufficio_2"]["capabilities"]
        self.assertNotIn("effects", plain, "una lampada onoff non deve dichiarare effetti")

    def test_a_huge_effect_list_is_capped(self):
        self.ha.states = [{
            "entity_id": "light.striscia", "state": "on",
            "attributes": {"friendly_name": "Striscia LED", "supported_color_modes": ["rgb"],
                           "effect_list": [f"Effetto {i}" for i in range(300)]},
        }]
        result = self.run_tool("ha_list_entities", {"domain": "light"})
        caps = result["entities"][0]["capabilities"]
        self.assertEqual(len(caps["effects"]), 25)
        self.assertEqual(caps["effects_total"], 300)

    def test_areas_are_listable(self):
        result = self.run_tool("ha_list_areas", {"domain": "light"})
        ufficio = next(a for a in result["areas"] if a["id"] == "ufficio")
        self.assertEqual(len(ufficio["entities"]), 3)
        self.assertNotIn("switch.stampante", ufficio["entities"])


class TestBatchApproval(HomeAssistantTestCase):
    def test_every_pending_call_is_shown_not_just_the_first(self):
        """La regressione vera: l'agente ne chiedeva tre, ne compariva una."""
        outcomes, approvals = execute_calls([
            {"tool": "ha_light_set", "arguments": {"entity_id": "light.ufficio_1", "state": "off"}},
            {"tool": "ha_light_set", "arguments": {"entity_id": "light.ufficio_2", "state": "off"}},
            {"tool": "ha_light_set", "arguments": {"entity_id": "light.ufficio_3", "state": "off"}},
        ])
        self.assertEqual(len(approvals), 3)
        self.assertEqual([a["arguments"]["entity_id"] for a in approvals],
                         ["light.ufficio_1", "light.ufficio_2", "light.ufficio_3"])
        self.assertEqual(outcomes, [])

    def test_a_read_after_a_pending_call_is_declared_not_dropped(self):
        outcomes, approvals = execute_calls([
            {"tool": "ha_light_set", "arguments": {"entity_id": "light.ufficio_1", "state": "off"}},
            {"tool": "ha_list_entities", "arguments": {"domain": "light"}},
        ])
        self.assertEqual(len(approvals), 1)
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0]["deferred"])
        self.assertIn("in attesa", outcomes[0]["output"])

    def test_reads_before_a_pending_call_still_run(self):
        outcomes, approvals = execute_calls([
            {"tool": "ha_list_entities", "arguments": {"domain": "light"}},
            {"tool": "ha_light_set", "arguments": {"area": "ufficio", "state": "off"}},
        ])
        self.assertTrue(outcomes[0]["ok"])
        self.assertEqual(len(approvals), 1)


if __name__ == "__main__":
    unittest.main()
