# ==============================================================================
# core/engine/transformers_compat.py — Compatibility Layer for Novel/Unified Models
#
# Bridges newly released model architectures (e.g. Gemma 4, GLM-4, DeepSeek V3,
# Qwen 3, multimodal unified checkpoints) with the installed version of Hugging Face
# Transformers by registering aliases in CONFIG_MAPPING and resolving model classes.
# ==============================================================================
import os
import json
from typing import Optional, Any, Dict, Type

from core.logger import get_logger

log = get_logger(__name__)

_COMPAT_INITIALIZED = False


def ensure_transformers_compatibility():
    """
    Registers model type aliases and architecture mappings in Transformers AutoConfig.
    Ensures checkpoints with unified/novel model types (e.g. gemma4_unified) load seamlessly.
    """
    global _COMPAT_INITIALIZED
    if _COMPAT_INITIALIZED:
        return

    # Le impalcature sul runtime vengono prima di tutto il resto: devono essere
    # in piedi prima che transformers importi il `modeling_x.py` di un
    # checkpoint, perche' quel file lega i nomi all'import. Questa funzione e'
    # l'ingresso di ogni caricamento, quindi e' qui che l'ordine e' garantito.
    apply_runtime_shims()

    try:
        import transformers
        from transformers.models.auto.configuration_auto import CONFIG_MAPPING

        # `hasattr` is not safe on this object. Transformers exposes its model
        # classes through a lazy module, so reading an attribute triggers an
        # import -- and when that import fails for a reason other than a
        # missing name (a broken torch, a partially initialised submodule) it
        # raises ModuleNotFoundError, which `hasattr` does not swallow. One such
        # failure used to abort every registration below it, leaving the whole
        # alias table empty and a checkpoint that would have loaded reporting
        # "Transformers does not recognize this architecture".
        def has(name: str) -> bool:
            return _safe_getattr(transformers, name, None) is not None

        # 1. Gemma 4 family aliases
        if has("Gemma4Config"):
            for alias in ("gemma4_unified", "gemma4_it", "gemma_4", "gemma4_text"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.Gemma4Config)
                    except Exception as e:
                        log.debug(f"[TransformersCompat] Registration notice for {alias}: {e}")

        if has("Gemma4TextConfig") and "gemma4_unified_text" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("gemma4_unified_text", transformers.Gemma4TextConfig)
            except Exception:
                pass

        if has("Gemma4VisionConfig") and "gemma4_unified_vision" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("gemma4_unified_vision", transformers.Gemma4VisionConfig)
            except Exception:
                pass

        if has("Gemma4AudioConfig") and "gemma4_unified_audio" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("gemma4_unified_audio", transformers.Gemma4AudioConfig)
            except Exception:
                pass

        # 2. Gemma 3 family aliases
        if has("Gemma3Config"):
            for alias in ("gemma3_unified", "gemma_3"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.Gemma3Config)
                    except Exception:
                        pass

        # 3. Qwen family aliases
        if has("Qwen2Config"):
            for alias in ("qwen3", "qwen3_moe", "qwen2_5", "qwen2.5", "qwen_3"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.Qwen2Config)
                    except Exception:
                        pass

        # 4. GLM / ChatGLM aliases
        if has("ChatGLMConfig") and "glm4" not in CONFIG_MAPPING:
            try:
                CONFIG_MAPPING.register("glm4", transformers.ChatGLMConfig)
                CONFIG_MAPPING.register("glm4_unified", transformers.ChatGLMConfig)
            except Exception:
                pass

        # 5. DeepSeek aliases
        if has("DeepseekV2Config"):
            for alias in ("deepseek_v3", "deepseek_v2_5", "deepseekv3"):
                if alias not in CONFIG_MAPPING:
                    try:
                        CONFIG_MAPPING.register(alias, transformers.DeepseekV2Config)
                    except Exception:
                        pass

        _COMPAT_INITIALIZED = True
        log.info("[TransformersCompat] Architecture compatibility mappings successfully registered.")
    except Exception as exc:
        log.warning(f"[TransformersCompat] Could not register architecture mappings: {exc}")


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Safely gets attribute from an object, guarding against LazyModule import errors."""
    try:
        val = getattr(obj, name, default)
        return val if val is not None else default
    except Exception:
        return default


def resolve_model_architecture_class(arch_name: str, is_multimodal: bool = False) -> Optional[Any]:
    """
    Finds the exact or closest matching PyTorch model class for a given architecture string.
    Handles unified naming differences like 'Gemma4UnifiedForConditionalGeneration' -> 'Gemma4ForConditionalGeneration'.
    """
    ensure_transformers_compatibility()
    try:
        import transformers

        # Direct lookup
        cls = _safe_getattr(transformers, arch_name, None)
        if cls is not None:
            return cls

        # Canonical normalization candidates
        candidates = []

        # Strip 'Unified' e.g. Gemma4UnifiedForConditionalGeneration -> Gemma4ForConditionalGeneration
        if "Unified" in arch_name:
            candidates.append(arch_name.replace("Unified", ""))

        # Check specific family aliases
        if "Gemma4" in arch_name:
            candidates.extend([
                "Gemma4ForConditionalGeneration",
                "Gemma4ForCausalLM",
                "Gemma4Model"
            ])
        elif "Gemma3" in arch_name:
            candidates.extend([
                "Gemma3ForConditionalGeneration",
                "Gemma3ForCausalLM",
                "Gemma3Model"
            ])
        elif "Qwen3" in arch_name:
            candidates.extend([
                "Qwen2ForCausalLM",
                "Qwen2MoeForCausalLM"
            ])
        elif "DeepseekV3" in arch_name:
            candidates.extend([
                "DeepseekV2ForCausalLM",
                "LlamaForCausalLM"
            ])
        elif "Glm" in arch_name or "GLM" in arch_name:
            candidates.extend([
                "ChatGLMForConditionalGeneration",
                "ChatGLMModel"
            ])

        if is_multimodal:
            candidates.extend([
                "AutoModelForImageTextToText",
                "AutoModelForVision2Seq",
                "AutoModelForConditionalGeneration"
            ])
        else:
            candidates.append("AutoModelForCausalLM")

        for cand in candidates:
            cand_cls = _safe_getattr(transformers, cand, None)
            if cand_cls is not None:
                log.info(f"[TransformersCompat] Resolved '{arch_name}' -> '{cand}'")
                return cand_cls

        return _safe_getattr(transformers, "AutoModelForCausalLM", None)
    except Exception as exc:
        log.warning(f"[TransformersCompat] Error resolving architecture class for '{arch_name}': {exc}")
        return None


# ==============================================================================
# Impalcature sul runtime installato
#
# Un checkpoint con codice proprio (`auto_map` + `trust_remote_code`) porta con
# se' le API della transformers con cui e' stato scritto, non quelle installate
# qui. Spark-X2.5 e' scritto per la 4.57.1 e su questa 5.17 non si caricava
# nemmeno, prima ancora di toccare i pesi:
#
#     AttributeError: 'float' object has no attribute 'get'
#
# Tre cose sono cambiate, tutte e tre verificate sul campo:
#
#   1. `rope_parameters` e' passato da dizionario piatto a dizionario per tipo
#      di layer (gemma3, spark2_5). `convert_rope_params_to_dict` continua a
#      scrivere `rope_theta` sul livello esterno, e `validate_rope` scorre i
#      valori dando per scontato che siano dizionari: il primo scalare lo fa
#      esplodere. Gemma 3 si salva per caso, perche' il suo `default_theta` e'
#      gia' un dizionario.
#   2. `_tied_weights_keys` e' passato da lista a dizionario, e il percorso che
#      espande i pesi condivisi fa `keys() | values()` su quello che trova.
#   3. `create_causal_mask` ha rinominato `input_embeds` in `inputs_embeds` e
#      non accetta piu' `cache_position`, che ora si ricava da `position_ids`.
#
# Ogni impalcatura e' stretta: non dichiara nulla sulla versione, riconosce la
# forma rotta e cambia solo quella. Il giorno che la libreria si corregge da
# sola diventano inerti, senza che nessuno debba ricordarsi di spegnerle.
# ==============================================================================

#: Marchio sulle funzioni avvolte. Serve a non impilare due giri di impalcatura
#: quando `apply_runtime_shims()` viene chiamato piu' di una volta.
_IMPALCATURA = "_sigma_impalcatura_runtime"

#: Nomi applicati, o None se non si e' ancora provato.
_SHIM_APPLICATI: Optional[tuple] = None


def apply_runtime_shims() -> tuple:
    """Installa una volta sola le impalcature di compatibilita' sul runtime.

    Restituisce i nomi applicati: serve al log e alle prove, che devono poter
    dire *quante* impalcature sono attive e non solo che la chiamata e' andata
    a buon fine. Una impalcatura che non si applica non e' un errore da
    propagare: e' una libreria che ha gia' la forma giusta.
    """
    global _SHIM_APPLICATI
    if _SHIM_APPLICATI is not None:
        return _SHIM_APPLICATI

    applicati = []
    for nome, installa in (
        ("rope_parameters", _shim_rope_parameters),
        ("tied_weights_keys", _shim_tied_weights_keys),
        ("mask_kwargs", _shim_mask_kwargs),
    ):
        try:
            if installa():
                applicati.append(nome)
        except Exception as exc:
            log.warning(
                "[TransformersCompat] Impalcatura '%s' non applicata: %s", nome, exc
            )
    _SHIM_APPLICATI = tuple(applicati)
    log.info(
        "[TransformersCompat] Impalcature attive: %s",
        ", ".join(applicati) if applicati else "nessuna",
    )
    return _SHIM_APPLICATI


def _nomi_parametri(func) -> Optional[set]:
    """I nomi che questa funzione accetta, o None se non si riesce a leggerli.

    None non e' l'insieme vuoto: significa "non lo so", e chi impalca deve
    lasciar perdere invece di riscrivere i kwarg di una funzione che non ha
    saputo leggere. Un `**kwargs` finale conta come nome speciale, perche'
    assorbe tutto e non c'e' niente da tradurre.
    """
    try:
        import inspect

        parametri = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return None
    nomi = set(parametri)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parametri.values()):
        nomi.add("**kwargs")
    return nomi


def _shim_rope_parameters() -> bool:
    """RoPE per tipo di layer: lo scalare iniettato sul livello sbagliato.

    `convert_rope_params_to_dict` scrive `rope_theta` sul dizionario esterno,
    che per un modello con `layer_types` e' un contenitore di dizionari. Con
    `layer_types` presente la scrittura corretta e' quella per tipo, che la
    funzione fa gia' piu' avanti; questa impalcatura toglie l'altra e la
    conserva come attributo, cosi' chi la cerca la trova ancora.
    """
    from transformers.modeling_rope_utils import RotaryEmbeddingConfigMixin

    originale = RotaryEmbeddingConfigMixin.convert_rope_params_to_dict
    if getattr(originale, _IMPALCATURA, False):
        return False

    def convert_rope_params_to_dict(self, **kwargs):
        prima = getattr(self, "rope_parameters", None)
        tipi = getattr(self, "layer_types", None)
        annidato = (
            isinstance(prima, dict)
            and bool(prima)
            and isinstance(tipi, (list, tuple))
            and any(chiave in tipi for chiave in prima)
        )
        kwargs = originale(self, **kwargs)
        if not annidato:
            return kwargs

        for chiave in list(self.rope_parameters.keys()):
            valore = self.rope_parameters[chiave]
            if chiave in tipi or isinstance(valore, dict):
                continue
            if valore is not None and getattr(self, chiave, None) is None:
                setattr(self, chiave, valore)
            del self.rope_parameters[chiave]
        return kwargs

    setattr(convert_rope_params_to_dict, _IMPALCATURA, True)
    RotaryEmbeddingConfigMixin.convert_rope_params_to_dict = convert_rope_params_to_dict
    return True


def _shim_tied_weights_keys() -> bool:
    """Pesi condivisi: la lista della 4.x dove la 5.x legge un dizionario.

    La lista diceva "questi pesi sono legati al loro omologo di input", e il
    legame vero lo faceva `tie_weights()` prendendolo da
    `get_input_embeddings()`. Qui quel nome si ricava una volta sola, e la mappa
    diventa quella che il modello avrebbe dichiarato nella 5.x.
    """
    from transformers.modeling_utils import PreTrainedModel

    originale = PreTrainedModel.get_expanded_tied_weights_keys
    if getattr(originale, _IMPALCATURA, False):
        return False

    def get_expanded_tied_weights_keys(self, all_submodels: bool = False) -> dict:
        legacy = getattr(self, "_tied_weights_keys", None)
        if isinstance(legacy, (list, tuple, set)):
            self._tied_weights_keys = _mappa_pesi_condivisi(self, legacy)
        return originale(self, all_submodels=all_submodels)

    setattr(get_expanded_tied_weights_keys, _IMPALCATURA, True)
    PreTrainedModel.get_expanded_tied_weights_keys = get_expanded_tied_weights_keys
    return True


def _mappa_pesi_condivisi(modello, chiavi) -> dict:
    """La lista dei pesi condivisi tradotta nella mappa, o {} se non si puo'.

    Vuoto vuol dire "il legame non si e' potuto ricostruire": il caricamento lo
    dira' come chiave mancante, e una chiave mancante si vede. Una mappa
    inventata, invece, lascerebbe una testa di output inizializzata a caso e un
    modello che risponde a vanvera senza che niente lo segnali.
    """
    peso = None
    try:
        peso = getattr(modello.get_input_embeddings(), "weight", None)
    except Exception:
        peso = None

    sorgente = None
    if peso is not None:
        for nome, parametro in modello.named_parameters():
            if parametro is peso:
                sorgente = nome
                break
    if not sorgente:
        log.warning(
            "[TransformersCompat] '%s' dichiara i pesi condivisi nella forma "
            "vecchia (%s) ma non espone un embedding di input: il legame resta "
            "da fare, e il caricamento lo segnalera' come chiave mancante.",
            type(modello).__name__, list(chiavi),
        )
        return {}
    return {str(chiave): sorgente for chiave in chiavi}


def _cosa_tradurre(nomi: set) -> tuple:
    """Cosa tradurre dei kwarg 4.x, dato l'insieme dei nomi accettati.

    Restituisce (rinomina_input_embeds, scarta_cache_position). Falso su
    entrambi quando non c'e' niente da tradurre: o la funzione accetta gia' i
    nomi nuovi, o assorbe tutto con un `**kwargs`, e in quel caso resta quella
    originale. Insieme vuoto vuol dire "non lo so", e anche li' non si tocca.
    """
    if not nomi:
        return False, False
    assorbe = "**kwargs" in nomi
    rinomina = not assorbe and "inputs_embeds" in nomi and "input_embeds" not in nomi
    scarta = not assorbe and "cache_position" not in nomi
    return rinomina, scarta


def _shim_mask_kwargs() -> bool:
    """Maschere: i kwarg che la libreria ha rinominato e tolto.

    L'impalcatura traduce e scarta solo cio' che la firma installata non
    accetta, e solo per le funzioni che lo richiedono: per tutte le altre resta
    la funzione originale, chiamata con gli stessi argomenti di prima.
    """
    from transformers import masking_utils

    applicata = False
    for nome in ("create_causal_mask", "create_sliding_window_causal_mask"):
        originale = getattr(masking_utils, nome, None)
        if originale is None or getattr(originale, _IMPALCATURA, False):
            continue
        rinomina, scarta_cache = _cosa_tradurre(_nomi_parametri(originale))
        if not (rinomina or scarta_cache):
            continue

        # Le due decisioni si legano come argomenti di default: dentro al ciclo
        # le variabili cambiano, e un riferimento libero farebbe usare a tutte
        # le impalcature i valori dell'ultimo giro.
        def impalcatura(*args, _originale=originale, _rinomina=rinomina,
                        _scarta_cache=scarta_cache, **kwargs):
            if _rinomina and "input_embeds" in kwargs and "inputs_embeds" not in kwargs:
                kwargs["inputs_embeds"] = kwargs.pop("input_embeds")
            if _scarta_cache:
                kwargs.pop("cache_position", None)
            return _originale(*args, **kwargs)

        setattr(impalcatura, _IMPALCATURA, True)
        impalcatura.__doc__ = originale.__doc__
        setattr(masking_utils, nome, impalcatura)
        applicata = True
    return applicata
