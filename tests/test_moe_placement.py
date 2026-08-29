# ==============================================================================
# tests/test_moe_placement.py — Dove finiscono i pesi di un modello a esperti
#
# Un MoE non si colloca come un modello denso. Qwen3.8-Flash-Next pesa 111 GiB
# ma la sua parte densa e' 3,2: attenzione, norme, esperti condivisi. Il resto
# sono 512 esperti per layer di cui un token ne accende dieci, piu' una tabella
# di embedding per layer da 33 GiB che llama.cpp tiene in RAM comunque.
#
# Contarli tutti come "pesi da mettere in VRAM" e' quello che faceva dire
# "impossibile" a un modello che invece gira: e' il caso che questi test
# fissano.
# ==============================================================================
import unittest

from core.engine.model_inspector import ModelFacts
from core.engine import gguf_planner
from core.engine.backends.llamaserver_backend import plan_to_args


def _flash_next() -> ModelFacts:
    """Le misure vere di Qwen3.8-Flash-Next Q4_K_M, prese dai suoi 9 shard."""
    return ModelFacts(
        path="", name="flash-next", model_type="qwen4exp",
        weight_format="gguf",
        num_hidden_layers=48, hidden_size=2560, head_dim=256,
        num_attention_heads=24, num_key_value_heads=2,
        vocab_size=248320, max_position_embeddings=262144,
        is_moe=True, num_experts=512, experts_used=10,
        total_bytes=int(111.0 * 2**30),
        expert_bytes=int(75.0 * 2**30),
        host_only_bytes=int(32.78 * 2**30),
    )


def _macchina(vram_gb, ram_gb=73.0):
    return {
        "accelerators": [
            {"type": "NVIDIA_CUDA", "name": f"GPU{i}", "free_vram_gb": v,
             "multi_processor_count": 60 - i}
            for i, v in enumerate(vram_gb)
        ],
        "cpu": {"cores_physical": 12},
        "ram": {"available_gb": ram_gb},
        "system": {},
    }


class TestQuantiEspertiRestanoInRam(unittest.TestCase):

    def test_la_parte_densa_sta_sulla_scheda(self):
        """3,2 GiB di dense entrano in 15: il piano non deve rinunciarci."""
        facts = _flash_next()
        su_host = gguf_planner._experts_on_host(facts, usable_gb=15.0, kv_gb=0.75)
        self.assertIsNotNone(su_host)
        self.assertLess(su_host, facts.num_hidden_layers,
                        "con 15 GB liberi qualche layer di esperti ci sta")

    def test_la_tabella_per_layer_non_conta_come_vram(self):
        """33 dei 111 GiB non vanno su nessun acceleratore.

        Contandoli la parte densa diventa 36 GiB, non entra in nessuna scheda
        in commercio, e il pianificatore dichiara incollocabile un modello che
        invece si carica e risponde. Senza, la parte densa e' 3,2 GiB.
        """
        facts = _flash_next()
        self.assertIsNotNone(
            gguf_planner._experts_on_host(facts, usable_gb=15.0, kv_gb=0.75))

        facts.host_only_bytes = 0
        self.assertIsNone(
            gguf_planner._experts_on_host(facts, usable_gb=15.0, kv_gb=0.75),
            "contata come VRAM, la tabella per layer fa rinunciare al modello")

    PESO = dict(dense_per_layer=3.19 / 48, expert_per_layer=75.0 / 48,
                kv_per_layer=0.75 / 48)

    def test_una_scheda_piccola_non_riceve_la_coda_pesante(self):
        """I layer con gli esperti sono gli ultimi e pesano venti volte gli altri.

        Una divisione proporzionale alla VRAM darebbe alla 5060 un terzo dei
        layer -- cioe' tutta la coda con gli esperti dentro, 15 GB su una
        scheda da 8. Qui la seconda scheda prende solo quello che regge.
        """
        conteggi = gguf_planner._moe_layers_per_device(
            usable=[13.0, 5.5], layers=48, n_cpu_moe=42, **self.PESO)
        self.assertIsNotNone(conteggi)
        self.assertEqual(sum(conteggi), 48)
        pesanti_sulla_piccola = min(conteggi[1], 48 - 42)
        self.assertLessEqual(pesanti_sulla_piccola * (75.0 / 48) * 1.2, 5.5,
                             "la scheda piccola riceve piu' byte di quanti ne ha")

    def test_troppi_esperti_in_vram_non_si_collocano(self):
        """Con gli stessi budget e due layer di esperti in piu' non ci sta.

        E' il caso che il ciclo del pianificatore risolve spostando un altro
        layer sulla CPU: qui si verifica che venga davvero segnalato.
        """
        self.assertIsNone(gguf_planner._moe_layers_per_device(
            usable=[13.0, 5.5], layers=48, n_cpu_moe=40, **self.PESO))

    def test_se_non_ci_stanno_lo_dice(self):
        """Nessuna scheda regge un layer di esperti: la risposta e' None."""
        self.assertIsNone(gguf_planner._moe_layers_per_device(
            usable=[0.5], layers=48, n_cpu_moe=0,
            dense_per_layer=3.19 / 48, expert_per_layer=75.0 / 48,
            kv_per_layer=0.75 / 48,
        ))


class TestIlPianoCheNeEsce(unittest.TestCase):

    def test_una_scheda_sola_niente_ripartizione(self):
        piano = gguf_planner._plan_settings(_flash_next(), _macchina([15.0]), 32768)
        self.assertEqual(piano["n_gpu_layers"], -1)
        self.assertGreater(piano["n_cpu_moe"], 0)
        self.assertIsNone(piano["tensor_split"])
        self.assertIn("-ncmoe", " ".join(plan_to_args(piano)))

    def test_due_schede_ripartizione_a_byte_non_a_layer(self):
        """Con una 5060 accanto a una 5070 Ti la divisione non e' 2:1."""
        piano = gguf_planner._plan_settings(
            _flash_next(), _macchina([14.68, 6.87]), 32768)
        split = piano["tensor_split"]
        self.assertIsNotNone(split)
        self.assertGreater(split[0], 0.8,
                           "quasi tutti i layer vanno sulla scheda grande")

    def test_la_previsione_conta_gli_esperti_accesi_non_tutti(self):
        """Dieci esperti su 512: il traffico per token e' quella frazione."""
        piano = gguf_planner._plan_settings(
            _flash_next(), _macchina([14.68, 6.87]), 32768)
        previsione = piano["forecast"]
        self.assertEqual(previsione["placement"], "moe_split")
        self.assertLess(previsione["host_gb_per_token"],
                        previsione["experts_on_host_gb"] / 10,
                        "leggere tutti gli esperti a ogni token e' il conto sbagliato")
        self.assertGreater(previsione["estimated_tokens_per_second"], 0)

    def test_un_modello_denso_non_passa_di_qui(self):
        """La strada dei MoE si applica solo a chi ha esperti misurati."""
        denso = ModelFacts(
            path="", name="denso", model_type="qwen3", weight_format="gguf",
            num_hidden_layers=48, hidden_size=5120, num_attention_heads=40,
            num_key_value_heads=8, head_dim=128, vocab_size=151936,
            total_bytes=int(18.0 * 2**30),
        )
        piano = gguf_planner._plan_settings(denso, _macchina([14.68, 6.87]), 8192)
        self.assertIsNone(piano.get("n_cpu_moe"))


if __name__ == "__main__":
    unittest.main()
