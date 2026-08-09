# ==============================================================================
# tests/test_mcp_fast_intents.py — Corsia veloce e validazione delle entità
# ==============================================================================
"""Due difese contro lo stesso tracciato andato male.

Un modello locale, davanti a «spegni le luci dell'ufficio», ha scritto un
manuale d'uso e poi ha chiamato lo strumento con `ufficio_luce_1234567890`, un
identificativo inventato di sana pianta. Home Assistant ha rifiutato l'intera
richiesta con un 400 secco.

Qui si verificano le due risposte: il riconoscitore che esegue i comandi diretti
senza passare dal modello, e la validazione che ferma un id inventato prima che
faccia fallire anche le entità corrette dello stesso comando.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from core.mcp import governance, mcp_hub
from core.mcp.fast_intents import match_home_command
from tests.test_mcp_homeassistant import DEFAULT_AREAS, DEFAULT_STATES, FakeHomeAssistant


class FastIntentTestCase(unittest.TestCase):
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


class TestRecognisedCommands(FastIntentTestCase):
    def test_the_phrase_that_started_it_all(self):
        intent = match_home_command("Spegni le luci dell'ufficio")
        self.assertIsNotNone(intent, "il comando che ha motivato la corsia veloce")
        self.assertEqual(intent["tool"], "ha_light_set")
        self.assertEqual(intent["arguments"], {"state": "off", "area": "Ufficio"})

    def test_turning_on_is_recognised_too(self):
        intent = match_home_command("accendi le luci in cucina")
        self.assertEqual(intent["arguments"], {"state": "on", "area": "Cucina"})

    def test_a_single_lamp_by_its_friendly_name(self):
        intent = match_home_command("spegni la luce ufficio 2")
        self.assertEqual(intent["arguments"]["entity_id"], ["light.ufficio_2"])
        self.assertNotIn("area", intent["arguments"])

    def test_a_lamp_named_with_the_words_out_of_order(self):
        """«accendi luce 1 in ufficio» accendeva tutta la stanza."""
        intent = match_home_command("accendi luce 1 in ufficio")
        self.assertEqual(intent["arguments"]["entity_id"], ["light.ufficio_1"])
        self.assertNotIn("area", intent["arguments"])
        self.assertIn("ufficio 1", intent["summary"])

    def test_two_lamps_named_together_are_one_command(self):
        intent = match_home_command("accendi luce 1 e luce 3 in ufficio")
        self.assertEqual(intent["arguments"]["entity_id"],
                         ["light.ufficio_1", "light.ufficio_3"])

    def test_naming_the_room_alone_still_means_the_whole_room(self):
        intent = match_home_command("spegni le luci dell'ufficio")
        self.assertEqual(intent["arguments"]["area"], "Ufficio")
        self.assertNotIn("entity_id", intent["arguments"])

    def test_a_lamp_outside_the_named_room_is_never_commanded(self):
        """Nominare una stanza restringe il campo a quella stanza.

        «accendi luce cucina in ufficio» nomina due stanze e non ha una lettura
        sola: la corsia veloce si ferma invece di accendere quella sbagliata.
        """
        self.assertIsNone(match_home_command("accendi luce cucina in ufficio"))

    def test_a_single_lamp_can_be_dimmed(self):
        intent = match_home_command("accendi luce 1 in ufficio al 30%")
        self.assertEqual(intent["arguments"]["entity_id"], ["light.ufficio_1"])
        self.assertEqual(intent["arguments"]["brightness_pct"], 30)

    def test_switches_have_their_own_tool(self):
        intent = match_home_command("spegni la presa dell'ufficio")
        self.assertEqual(intent["tool"], "ha_switch_set")
        self.assertEqual(intent["arguments"]["state"], "off")

    def test_brightness_is_picked_up(self):
        intent = match_home_command("accendi le luci dell'ufficio al 40%")
        self.assertEqual(intent["arguments"]["brightness_pct"], 40)

    def test_a_colour_is_picked_up(self):
        intent = match_home_command("accendi le luci del salotto in rosso")
        # 'salotto' non esiste fra le aree: deve arrendersi, non inventare.
        self.assertIsNone(intent)

        intent = match_home_command("accendi le luci dell'ufficio in rosso")
        self.assertEqual(intent["arguments"]["color_name"], "red")

    def test_warm_and_cold_become_kelvin(self):
        self.assertEqual(
            match_home_command("accendi le luci dell'ufficio calda")["arguments"]["color_temp_kelvin"],
            2700)
        self.assertEqual(
            match_home_command("accendi le luci dell'ufficio fredda")["arguments"]["color_temp_kelvin"],
            6000)


class TestWhenItGivesUp(FastIntentTestCase):
    """Arrendersi è la funzione principale: nel dubbio decide l'agente."""

    def test_an_unknown_room_is_not_guessed(self):
        self.assertIsNone(match_home_command("spegni le luci della taverna"))

    def test_a_conditional_request_goes_to_the_agent(self):
        self.assertIsNone(match_home_command("spegni le luci dell'ufficio se il training è finito"))

    def test_a_question_is_not_a_command(self):
        self.assertIsNone(match_home_command("quali luci ci sono nell'ufficio?"))
        self.assertIsNone(match_home_command("come faccio a spegnere le luci dell'ufficio"))

    def test_a_long_sentence_goes_to_the_agent(self):
        self.assertIsNone(match_home_command(
            "per favore spegni le luci dell'ufficio e poi mandami una email di riepilogo "
            "con lo stato del training e la temperatura della GPU"))

    def test_a_bare_verb_without_a_target_is_refused(self):
        self.assertIsNone(match_home_command("spegni tutto"))
        self.assertIsNone(match_home_command("accendi"))

    def test_contradictory_verbs_are_refused(self):
        self.assertIsNone(match_home_command("accendi e spegni le luci dell'ufficio"))

    def test_nothing_happens_when_home_assistant_is_not_configured(self):
        governance.set_integration_config("home_assistant", {"base_url": "", "token": ""})
        self.assertIsNone(match_home_command("spegni le luci dell'ufficio"))

    def test_an_unrelated_message_is_untouched(self):
        self.assertIsNone(match_home_command("scrivi una funzione python che ordina una lista"))


class TestGateStillApplies(FastIntentTestCase):
    """La corsia veloce accorcia il percorso, non salta i controlli."""

    def test_a_direct_command_still_asks_for_confirmation(self):
        intent = match_home_command("spegni le luci dell'ufficio")
        outcome = mcp_hub.execute_tool(intent["tool"], intent["arguments"])
        self.assertEqual(outcome["status"], "confirmation_required")

    def test_with_auto_approve_it_runs_straight_away(self):
        governance.set_auto_approve(True)
        intent = match_home_command("spegni le luci dell'ufficio")
        outcome = mcp_hub.execute_tool(intent["tool"], intent["arguments"])
        self.assertEqual(outcome["status"], "ok")
        payloads = self.ha.service_payloads("light/turn_off")
        self.assertEqual(len(payloads), 1)
        self.assertEqual(len(payloads[0]["entity_id"]), 3)

    def test_a_disabled_tool_is_refused_even_on_the_fast_path(self):
        governance.set_auto_approve(True)
        governance.set_tool_enabled("ha_light_set", False)
        intent = match_home_command("spegni le luci dell'ufficio")
        outcome = mcp_hub.execute_tool(intent["tool"], intent["arguments"])
        self.assertEqual(outcome["status"], "error")


class TestInventedEntityIds(FastIntentTestCase):
    """Il guasto vero del tracciato: un id inventato che affonda tutto."""

    def setUp(self):
        super().setUp()
        governance.set_auto_approve(True)

    def test_an_invented_id_never_reaches_home_assistant(self):
        outcome = mcp_hub.execute_tool(
            "ha_light_set", {"entity_id": "ufficio_luce_1234567890", "state": "off"})
        self.assertEqual(outcome["status"], "error")
        self.assertEqual(self.ha.service_payloads("light/turn_off"), [],
                         "nessuna richiesta deve partire con un id inesistente")

    def test_the_error_lists_the_ids_that_exist(self):
        outcome = mcp_hub.execute_tool(
            "ha_light_set", {"entity_id": "ufficio_luce_1234567890", "state": "off"})
        self.assertIn("light.ufficio_1", outcome["error"])
        self.assertIn("inesistenti", outcome["error"].lower())

    def test_one_bad_id_does_not_sink_the_valid_ones_silently(self):
        """Prima l'intero lotto falliva con un 400 e nessuno sapeva perché."""
        outcome = mcp_hub.execute_tool("ha_light_set", {
            "entity_id": ["light.ufficio_1", "inventata_999"], "state": "off"})
        self.assertEqual(outcome["status"], "error")
        self.assertIn("inventata_999", outcome["error"])

    def test_an_id_without_its_domain_prefix_is_accepted(self):
        """I modelli scrivono spesso 'ufficio_1' invece di 'light.ufficio_1'."""
        result = mcp_hub.execute_tool("ha_light_set", {"entity_id": "ufficio_1", "state": "off"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.ha.service_payloads("light/turn_off")[0]["entity_id"],
                         ["light.ufficio_1"])

    def test_a_friendly_name_is_accepted(self):
        result = mcp_hub.execute_tool("ha_light_set", {"entity_id": "Luce ufficio 3", "state": "off"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.ha.service_payloads("light/turn_off")[0]["entity_id"],
                         ["light.ufficio_3"])


class TestChatShortCircuit(FastIntentTestCase):
    """Il punto in cui la chat decide se scomodare il modello."""

    def test_a_direct_command_never_reaches_the_model(self):
        from core.chat.chat_runner import _try_fast_command

        governance.set_auto_approve(True)
        response = _try_fast_command("Spegni le luci dell'ufficio")

        self.assertIsNotNone(response, "il comando doveva essere servito dalla corsia veloce")
        self.assertIn("Spengo le luci", response["response"])
        self.assertEqual(response["tool_calls"][0]["tool"], "ha_light_set")
        self.assertEqual(len(self.ha.service_payloads("light/turn_off")), 1)

    def test_a_confirmation_still_reaches_the_user(self):
        from core.chat.chat_runner import _try_fast_command

        response = _try_fast_command("Spegni le luci dell'ufficio")
        self.assertEqual(len(response["tool_approvals"]), 1)
        self.assertEqual(self.ha.service_payloads("light/turn_off"), [],
                         "senza assenso non deve partire nulla")

    def test_anything_else_falls_through_to_the_agent(self):
        from core.chat.chat_runner import _try_fast_command

        self.assertIsNone(_try_fast_command("scrivi un test per il modulo di parsing"))
        self.assertIsNone(_try_fast_command("come spengo le luci dell'ufficio?"))

    def test_a_failing_command_falls_through_instead_of_answering_wrong(self):
        """Se lo strumento fallisce, la frase torna all'agente che ci ragiona."""
        from core.chat.chat_runner import _try_fast_command

        governance.set_auto_approve(True)
        governance.set_tool_enabled("ha_light_set", False)
        self.assertIsNone(_try_fast_command("Spegni le luci dell'ufficio"))


class TestToolDescriptionsStayShort(unittest.TestCase):
    def test_no_description_is_long_enough_to_be_recited(self):
        """Una descrizione lunga viene riprodotta come documentazione.

        È successo davvero: l'agente ha incollato in chat la descrizione di
        ha_light_set invece di chiamarlo.
        """
        too_long = [t["name"] for t in mcp_hub.get_aggregated_tools()
                    if len(t.get("description", "")) > 320]
        self.assertEqual(too_long, [], f"descrizioni troppo lunghe: {too_long}")


if __name__ == "__main__":
    unittest.main()
