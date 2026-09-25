# ==============================================================================
# tests/test_transformers_5_compat.py — Un checkpoint scritto per la 4.x su una
# transformers 5.x
#
# Nasce da una segnalazione reale, su `XHToken/Spark-X2.5-4B`:
#
#     SigmaEngine non ha potuto caricare XHToken--Spark-X2.5-4B
#     Fase: load
#     Causa: AttributeError: 'float' object has no attribute 'get'
#     Se e' un errore di memoria, riduci il contesto o forza una
#     quantizzazione piu' aggressiva dal Model Hub.
#
# Il modello non c'entrava nulla con la memoria. E' un checkpoint con codice
# proprio (`auto_map` nel config, letto con `trust_remote_code`), scritto per
# transformers 4.57.1, e tre API che usa sono cambiate nella 5.x:
#
#   1. `rope_parameters` e' diventato un dizionario per tipo di layer, e lo
#      scalare iniettato sul livello esterno fa esplodere `validate_rope`;
#   2. `_tied_weights_keys` e' passato da lista a dizionario;
#   3. `create_causal_mask` ha rinominato `input_embeds` e tolto
#      `cache_position`.
#
# Le prove qui sotto riproducono le tre forme con modelli minimi, senza
# scaricare niente: hanno la stessa struttura della config che si e' rotta. In
# coda c'e' la prova con il checkpoint vero, marcata lenta.
# ==============================================================================
import unittest

from torch import nn
from transformers import LlamaConfig, PreTrainedConfig, masking_utils
from transformers.modeling_utils import PreTrainedModel

from core.engine.transformers_compat import _cosa_tradurre, apply_runtime_shims


class _ConfigPerTipoDiLayer(PreTrainedConfig):
    """La forma della config di Spark-X2.5: RoPE diverso per tipo di layer.

    Nessun `rope_theta` piatto: gli angoli stanno dentro ai due dizionari, che
    e' esattamente la condizione che faceva iniettare il valore di default —
    un float — sul livello esterno.
    """

    model_type = "sigma_prova_per_tipo"

    def __init__(self, rope_parameters=None, layer_types=None, **kwargs):
        self.rope_parameters = rope_parameters
        self.layer_types = layer_types
        self.num_hidden_layers = len(layer_types or [])
        super().__init__(**kwargs)


class TestRoPEPerTipoDiLayer(unittest.TestCase):
    """Il primo dei tre guasti: `'float' object has no attribute 'get'`."""

    @classmethod
    def setUpClass(cls):
        apply_runtime_shims()

    def _config(self, rope_parameters, layer_types=None):
        return _ConfigPerTipoDiLayer(
            rope_parameters=rope_parameters,
            layer_types=layer_types,
            tie_word_embeddings=True,
        )

    def _due_tipi(self):
        return {
            "full_attention": {"rope_theta": 5_000_000, "partial_rotary_factor": 0.25},
            "sliding_attention": {"rope_theta": 10_000, "partial_rotary_factor": 1.0},
        }

    def test_un_theta_per_tipo_non_fa_esplodere_il_config(self):
        """Prima della impalcatura questa costruzione sollevava AttributeError."""
        config = self._config(self._due_tipi(), ["sliding_attention", "full_attention"])
        self.assertEqual(
            sorted(config.rope_parameters), ["full_attention", "sliding_attention"]
        )

    def test_nessuno_scalare_finisce_fra_i_dizionari_dei_layer(self):
        """Ogni valore esterno deve essere i parametri di un tipo, non un numero."""
        config = self._config(self._due_tipi(), ["sliding_attention"])
        for tipo, parametri in config.rope_parameters.items():
            with self.subTest(tipo=tipo):
                self.assertIsInstance(parametri, dict)

    def test_i_theta_dichiarati_restano_quelli(self):
        """L'impalcatura sposta uno scalare, non riscrive i valori veri."""
        config = self._config(self._due_tipi(), ["sliding_attention"])
        self.assertEqual(config.rope_parameters["full_attention"]["rope_theta"], 5_000_000)
        self.assertEqual(config.rope_parameters["sliding_attention"]["rope_theta"], 10_000)

    def test_il_valore_iniettato_resta_cercabile_come_attributo(self):
        """Chi lo cerca sull'attributo lo trova ancora, alla stessa cifra."""
        config = self._config(self._due_tipi(), ["sliding_attention"])
        self.assertNotIn("rope_theta", config.rope_parameters)
        self.assertEqual(getattr(config, "rope_theta", None), 10_000.0)

    def test_il_rope_piatto_non_viene_toccato(self):
        """Un modello senza `layer_types` tiene il dizionario che aveva."""
        config = self._config({"rope_theta": 12_345.0})
        self.assertEqual(config.rope_parameters["rope_theta"], 12_345.0)


class _ModelloConPesiCondivisi(PreTrainedModel):
    """Il secondo guasto: la lista dei pesi condivisi della 4.x."""

    _tied_weights_keys = ["lm_head.weight"]

    def __init__(self, config):
        super().__init__(config)
        self.model = nn.Module()
        self.model.embedding = nn.Embedding(config.vocab_size, config.hidden_size)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.post_init()

    def get_input_embeddings(self):
        return self.model.embedding

    def get_output_embeddings(self):
        return self.lm_head


class _ModelloSenzaIngresso(_ModelloConPesiCondivisi):
    """Dichiara il legame ma non dice da dove prendere il peso."""

    def get_input_embeddings(self):
        return None


class TestPesiCondivisiDichiaratiComeLista(unittest.TestCase):
    """`'list' object has no attribute 'keys'`, e il legame vero da rifare."""

    @classmethod
    def setUpClass(cls):
        apply_runtime_shims()

    def _config(self):
        # Con `tie_word_embeddings` a False la libreria non espande niente, ed e'
        # giusto cosi': un modello che dichiara di non condividere i pesi non li
        # condivide.
        return PreTrainedConfig(vocab_size=32, hidden_size=8, tie_word_embeddings=True)

    def test_la_lista_diventa_la_mappa_della_5x(self):
        modello = _ModelloConPesiCondivisi(self._config())
        self.assertEqual(
            modello.all_tied_weights_keys,
            {"lm_head.weight": "model.embedding.weight"},
        )

    def test_il_peso_e_davvero_condiviso(self):
        """La mappa non basta: i due nomi devono puntare allo stesso tensore."""
        modello = _ModelloConPesiCondivisi(self._config())
        self.assertIs(modello.lm_head.weight, modello.model.embedding.weight)

    def test_senza_embedding_di_ingresso_non_si_inventa_il_legame(self):
        """Vuoto e' onesto: si vedra' come chiave mancante, non come risposta storta."""
        modello = _ModelloSenzaIngresso(self._config())
        self.assertEqual(modello.all_tied_weights_keys, {})


class TestMaschereConIKwargDella4x(unittest.TestCase):
    """Il terzo guasto: `unexpected keyword argument 'input_embeds'`."""

    @classmethod
    def setUpClass(cls):
        apply_runtime_shims()
        cls.config = LlamaConfig(
            hidden_size=32, num_attention_heads=4, num_key_value_heads=2,
            num_hidden_layers=2, vocab_size=64,
        )

    def _embeds(self):
        import torch

        return torch.zeros(1, 3, 32)

    def _posizioni(self):
        import torch

        return torch.arange(3).unsqueeze(0)

    def test_i_due_nomi_vecchi_adesso_passano(self):
        """Prima della impalcatura questa chiamata sollevava TypeError."""
        maschera = masking_utils.create_causal_mask(
            config=self.config,
            input_embeds=self._embeds(),
            attention_mask=None,
            cache_position=self._posizioni()[0],
            past_key_values=None,
            position_ids=self._posizioni(),
        )
        self.assertIsNone(maschera)

    def test_stesso_risultato_della_chiamata_con_i_nomi_nuovi(self):
        import torch

        attenzione = torch.tensor([[[[True]]]])
        vecchia = masking_utils.create_causal_mask(
            config=self.config, input_embeds=self._embeds(), attention_mask=attenzione,
            cache_position=self._posizioni()[0], past_key_values=None,
            position_ids=self._posizioni(),
        )
        nuova = masking_utils.create_causal_mask(
            config=self.config, inputs_embeds=self._embeds(), attention_mask=attenzione,
            past_key_values=None, position_ids=self._posizioni(),
        )
        torch.testing.assert_close(vecchia, nuova)

    def test_vale_anche_per_la_maschera_a_finestra(self):
        maschera = masking_utils.create_sliding_window_causal_mask(
            config=self.config,
            input_embeds=self._embeds(),
            attention_mask=None,
            cache_position=self._posizioni()[0],
            past_key_values=None,
            position_ids=self._posizioni(),
        )
        self.assertIsNone(maschera)


class TestDecisioneSuiKwargDaTradurre(unittest.TestCase):
    """La decisione e' separata dall'impalcatura, cosi' si puo' provare."""

    def test_la_firma_attuale_chiede_entrambe_le_traduzioni(self):
        """E' la firma vera di `create_causal_mask`: nome nuovo, niente cache."""
        nomi = {"config", "inputs_embeds", "attention_mask", "past_key_values", "position_ids"}
        self.assertEqual(_cosa_tradurre(nomi), (True, True))

    def test_una_firma_che_accetta_ancora_i_nomi_vecchi_non_si_tocca(self):
        """Se `input_embeds` e `cache_position` esistono, non c'e' niente da fare."""
        nomi = {"config", "input_embeds", "inputs_embeds", "attention_mask", "cache_position"}
        self.assertEqual(_cosa_tradurre(nomi), (False, False))

    def test_una_firma_che_accetta_la_cache_la_riceve(self):
        nomi = {"config", "inputs_embeds", "cache_position"}
        self.assertEqual(_cosa_tradurre(nomi), (True, False))

    def test_una_firma_che_assorbe_tutto_non_si_tocca(self):
        nomi = {"config", "inputs_embeds", "**kwargs"}
        self.assertEqual(_cosa_tradurre(nomi), (False, False))

    def test_un_insieme_vuoto_vuol_dire_non_lo_so(self):
        self.assertEqual(_cosa_tradurre(set()), (False, False))


class TestImpalcatureInstallate(unittest.TestCase):

    def test_si_installano_una_volta_sola(self):
        """Due giri non devono impilare due avvolgimenti."""
        from transformers.masking_utils import create_causal_mask
        from transformers.modeling_rope_utils import RotaryEmbeddingConfigMixin
        from transformers.modeling_utils import PreTrainedModel

        primo = apply_runtime_shims()
        secondo = apply_runtime_shims()
        self.assertEqual(primo, secondo)
        for bersaglio in (RotaryEmbeddingConfigMixin.convert_rope_params_to_dict,
                          PreTrainedModel.get_expanded_tied_weights_keys,
                          create_causal_mask):
            with self.subTest(bersaglio=getattr(bersaglio, "__name__", bersaglio)):
                self.assertTrue(getattr(bersaglio, "_sigma_impalcatura_runtime", False))

    def test_le_tre_impalcature_sono_tutte_attive(self):
        self.assertEqual(
            sorted(apply_runtime_shims()),
            ["mask_kwargs", "rope_parameters", "tied_weights_keys"],
        )


def _trova_checkpoint_con_codice(frammento: str) -> str:
    """La cartella di un checkpoint il cui nome contiene `frammento`, se c'e'.

    Si guarda in tutte le cartelle modelli attive, non in un percorso scritto a
    mano: la stessa installazione puo' tenere i pesi su un altro disco, e una
    prova che pretende di sapere dove sono fallisce su ogni macchina tranne una.
    """
    try:
        from core import paths

        cartelle = paths.all_models_dirs()
    except Exception:
        return ""
    for cartella in cartelle:
        try:
            voci = list(cartella.iterdir())
        except OSError:
            continue
        for voce in voci:
            try:
                if not voce.is_dir() or frammento.lower() not in voce.name.lower():
                    continue
                if (voce / "config.json").is_file() and list(voce.glob("*.safetensors")):
                    return str(voce)
            except OSError:
                continue
    return ""


class TestCheckpointReale(unittest.TestCase):
    """Spark-X2.5 vero, pesi compresi: si salta da solo se non e' installato.

    E' la prova che le tre impalcature servono tutte e tre, e che insieme
    portano il modello fino al primo token: il caricamento non deve avere una
    chiave mancante — un `lm_head` rimasto a caso non lo dice nessuno — e la
    risposta deve essere testo, non vuoto. Costa quanto il modello, per questo
    e' marcata lenta e la corsa veloce non la esegue.
    """

    @classmethod
    def setUpClass(cls):
        cls.percorso = _trova_checkpoint_con_codice("Spark-X2.5")
        if not cls.percorso:
            raise unittest.SkipTest(
                "nessun checkpoint Spark-X2.5 fra le cartelle modelli: prova saltata"
            )
        apply_runtime_shims()

    def test_i_pesi_entrano_tutti_e_il_modello_risponde(self):
        import gc

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizzatore = AutoTokenizer.from_pretrained(
            self.percorso, trust_remote_code=True
        )
        modello, info = AutoModelForCausalLM.from_pretrained(
            self.percorso,
            trust_remote_code=True,
            dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
            output_loading_info=True,
        )
        try:
            self.assertEqual(sorted(info.get("missing_keys") or []), [],
                             "pesi mancanti: il checkpoint non e' entrato tutto")
            self.assertEqual(sorted(info.get("unexpected_keys") or []), [],
                             "pesi inattesi: il modello non li ha")

            modello.eval()
            testo = tokenizzatore.apply_chat_template(
                [{"role": "user", "content": "Di' solo: pronto."}],
                tokenize=False, add_generation_prompt=True,
            )
            ingressi = tokenizzatore(testo, return_tensors="pt")
            with torch.no_grad():
                uscita = modello.generate(**ingressi, max_new_tokens=8, do_sample=False)
            risposta = tokenizzatore.decode(
                uscita[0][ingressi["input_ids"].shape[1]:], skip_special_tokens=True
            )
            self.assertTrue(risposta.strip(), "il modello non ha scritto niente")
        finally:
            del modello
            gc.collect()
