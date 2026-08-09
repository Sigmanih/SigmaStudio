"""Normalizzazione dei parametri creativi.

La UI, le pipeline salvate e le API esterne usano nomi diversi per lo stesso
parametro (`negativePrompt` / `negative_prompt`, `cfg` / `cfg_scale`, ...).
I generatori accettano keyword esplicite: senza questo strato una richiesta
dalla UI arriva come `TypeError: unexpected keyword argument`.
"""

# alias in ingresso -> nome canonico usato dai generatori/adapter
_ALIASES = {
    "negativeprompt": "negative_prompt",
    "negative": "negative_prompt",
    "cfg": "cfg_scale",
    "cfgscale": "cfg_scale",
    "guidance": "cfg_scale",
    "guidance_scale": "cfg_scale",
    "samplername": "sampler",
    "sampler_name": "sampler",
    "denoise": "strength",
    "denoising_strength": "strength",
    "sourceassetid": "source_asset_id",
    "assetid": "asset_id",
    "num_steps": "steps",
    "numinferencesteps": "steps",
    "lightdirection": "light_direction",
    "styleprompt": "style_prompt",
    "maskdata": "mask_data",
}

_INT_KEYS = {"width", "height", "steps", "seed", "pixels", "iterations", "samples"}
_FLOAT_KEYS = {"cfg_scale", "strength", "ratio", "intensity", "scale"}


def canonical_key(key: str) -> str:
    lowered = str(key).strip()
    return _ALIASES.get(lowered.replace("_", "").lower(), _ALIASES.get(lowered.lower(), lowered))


def normalize_params(params: dict) -> dict:
    """Rinomina gli alias e converte i tipi numerici arrivati come stringa."""
    out = {}
    for key, value in (params or {}).items():
        ckey = canonical_key(key)
        if value is None:
            continue
        try:
            if ckey in _INT_KEYS and not isinstance(value, bool):
                value = int(float(value))
            elif ckey in _FLOAT_KEYS and not isinstance(value, bool):
                value = float(value)
        except (TypeError, ValueError):
            pass
        out[ckey] = value
    return out


def split_kwargs(params: dict, allowed: set, drop: set = frozenset()) -> dict:
    """Tiene solo le chiavi accettate dalla firma di destinazione.

    Le chiavi extra non vengono perse: restano nei `params` del CreativeTask e
    quindi nel metadata dell'asset, ma non fanno esplodere la chiamata.
    """
    return {k: v for k, v in normalize_params(params).items() if k in allowed and k not in drop}
