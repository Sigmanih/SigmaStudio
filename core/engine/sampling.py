# ==============================================================================
# core/engine/sampling.py — One sampling contract for every backend
#
# Before this module each runtime invented its own: the transformers path had
# top_p = 0.95 written into the code and ignored everything else, llama.cpp
# received only temperature and max_tokens, and the top_k / repeat_penalty /
# seed the user had configured were read on the Ollama branch alone. The
# published sampling recipes for a model family were therefore not expressible
# at all, and every local answer came out on whatever the library happened to
# default to.
#
# SamplingParams is resolved once, high up, and adapted per backend at the last
# moment. It is deliberately dependency-free -- no torch, no numpy -- so it
# resolves identically on a CUDA desktop, an Apple laptop and a Raspberry Pi,
# including on hosts where neither inference runtime is installed.
# ==============================================================================
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Family recipes
# ---------------------------------------------------------------------------
# What the people who trained the model said to run it with. A checkpoint is
# tuned against a sampler, and drifting away from that sampler costs quality in
# a way no prompt fixes -- repetition and derailment on one side, flattened,
# hedging prose on the other.
#
# Only families with a published recipe belong here. Guessing a number and
# presenting it as the vendor's is worse than falling through to the generic
# entry, because it looks authoritative in the telemetry. Matching is by
# lowercase substring against the model identifier, longest key first, so
# "qwen3" also covers the qwen3.x point releases.
#
# Two variants per family where the family distinguishes them: a model that
# reasons before answering wants a wider, warmer sampler than the same model
# answering directly.

_GENERIC = {
    "direct":   {"temperature": 0.7, "top_p": 0.95, "top_k": 40, "min_p": 0.0,
                 "repeat_penalty": 1.1},
    "reasoning": {"temperature": 0.6, "top_p": 0.95, "top_k": 40, "min_p": 0.0,
                  "repeat_penalty": 1.05},
}

FAMILY_RECIPES: Dict[str, Dict[str, Dict[str, float]]] = {
    "qwen3": {
        "direct":    {"temperature": 0.7, "top_p": 0.80, "top_k": 20, "min_p": 0.0,
                      "repeat_penalty": 1.05},
        "reasoning": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                      "repeat_penalty": 1.05},
    },
    "qwen2.5": {
        "direct":    {"temperature": 0.7, "top_p": 0.80, "top_k": 20, "min_p": 0.0,
                      "repeat_penalty": 1.05},
        "reasoning": {"temperature": 0.7, "top_p": 0.80, "top_k": 20, "min_p": 0.0,
                      "repeat_penalty": 1.05},
    },
    "deepseek-r1": {
        "direct":    {"temperature": 0.6, "top_p": 0.95, "top_k": 40, "min_p": 0.0,
                      "repeat_penalty": 1.0},
        "reasoning": {"temperature": 0.6, "top_p": 0.95, "top_k": 40, "min_p": 0.0,
                      "repeat_penalty": 1.0},
    },
    "llama-3": {
        "direct":    {"temperature": 0.6, "top_p": 0.90, "top_k": 40, "min_p": 0.0,
                      "repeat_penalty": 1.1},
        "reasoning": {"temperature": 0.6, "top_p": 0.90, "top_k": 40, "min_p": 0.0,
                      "repeat_penalty": 1.1},
    },
    "gemma": {
        "direct":    {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.0,
                      "repeat_penalty": 1.0},
        "reasoning": {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.0,
                      "repeat_penalty": 1.0},
    },
}

# Aliases that point at the same recipe under a different naming convention.
_FAMILY_ALIASES = {
    "llama3": "llama-3",
    "llama4": "llama-3",
    "deepseek-reasoner": "deepseek-r1",
    "qwen3-coder": "qwen3",
    "qwen2.5-coder": "qwen2.5",
}


def _match_family(model_name: str) -> Optional[str]:
    """Longest matching family key for a model identifier, or None."""
    lower = (model_name or "").lower()
    if not lower:
        return None
    for alias, target in sorted(_FAMILY_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in lower:
            return target
    for key in sorted(FAMILY_RECIPES, key=len, reverse=True):
        if key in lower:
            return key
    return None


# ---------------------------------------------------------------------------
# The parameters themselves
# ---------------------------------------------------------------------------

#: Keys a caller may override. Anything outside this set is ignored rather
#: than silently forwarded to a runtime that would reject it.
TUNABLE = (
    "temperature", "top_p", "top_k", "min_p",
    "repeat_penalty", "max_tokens", "num_ctx", "seed",
)


@dataclass(frozen=True)
class SamplingParams:
    """How to sample, independent of which runtime will do the sampling."""

    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    min_p: float = 0.0
    repeat_penalty: float = 1.1
    max_tokens: int = 4096

    # Requested context window. Carried for reporting and for the Ollama path,
    # which accepts it per request. It is deliberately NOT forwarded to the
    # local load: context is fixed when the weights are placed, and re-placing
    # a resident model because one message asked for a different window costs
    # far more than the window is worth. Changing it there is a measured
    # decision, not a side effect of picking a profile.
    num_ctx: int = 0

    seed: Optional[int] = None
    stop: Tuple[str, ...] = ()

    # A GBNF grammar, as text. Carried rather than compiled, because compiling
    # it needs llama.cpp and this module must stay importable without it. The
    # backend that can use it compiles it at the last moment; every other
    # backend ignores it, which is the correct behaviour rather than a gap --
    # a cloud endpoint has its own structured-output mechanism, and a
    # transformers model has none built in.
    grammar: Optional[str] = None

    #: Where each value came from, for telemetry that can be trusted.
    source: str = "default"

    # ------------------------------------------------------------- building

    @classmethod
    def resolve(
        cls,
        model_name: str = "",
        provider_key: str = "",
        provider_cfg: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
        reasoning: bool = False,
    ) -> "SamplingParams":
        """
        Builds the sampler for one request, in three layers.

        1. The family recipe sets the *shape* -- top_p, top_k, min_p and the
           repetition penalty. This is what the model was tuned against.
        2. The provider config wins wherever the user actually changed a value
           from the one Sigma Studio ships. An untouched 0.7 in the config is
           not an opinion, so it must not override a vendor recipe; a 0.15 the
           user typed is, so it must.
        3. The execution profile has the last word on the three knobs that are
           a property of *this message* rather than of the setup: temperature,
           the token budget and the context request. Those are what make a
           greeting cost a greeting and a proof cost a proof, and a single
           global number in the config cannot express both. A user who wants
           their numbers regardless sets ``"sampling_locked": true`` on the
           provider, which skips this layer entirely.
        """
        family = _match_family(model_name)
        mode = "reasoning" if reasoning else "direct"
        base = dict((FAMILY_RECIPES.get(family) or _GENERIC)[mode])
        origin = [f"family:{family}" if family else "family:generic"]

        overrides = explicit_overrides(provider_key, provider_cfg or {})
        if overrides:
            base.update(overrides)
            origin.append("config:" + ",".join(sorted(overrides)))

        locked = bool((provider_cfg or {}).get("sampling_locked"))
        if profile and not locked:
            for key in ("temperature", "max_tokens", "num_ctx"):
                if profile.get(key) is not None:
                    base[key] = profile[key]
            if profile.get("label"):
                origin.append(f"profile:{profile['label']}")
        elif locked:
            origin.append("locked")

        stop = provider_cfg.get("stop") if provider_cfg else None
        if isinstance(stop, str):
            stop = [stop]

        return cls(
            temperature=float(base.get("temperature", 0.7)),
            top_p=float(base.get("top_p", 0.95)),
            top_k=int(base.get("top_k", 40)),
            min_p=float(base.get("min_p", 0.0)),
            repeat_penalty=float(base.get("repeat_penalty", 1.1)),
            max_tokens=int(base.get("max_tokens", 4096) or 4096),
            num_ctx=int(base.get("num_ctx", 0) or 0),
            seed=_coerce_seed(base.get("seed")),
            stop=tuple(s for s in (stop or []) if isinstance(s, str) and s),
            source=" | ".join(origin),
        )

    def with_grammar(self, gbnf: Optional[str]) -> "SamplingParams":
        """A copy that constrains the decode to this grammar."""
        return replace(self, grammar=gbnf or None)

    def with_overrides(self, **kwargs: Any) -> "SamplingParams":
        """A copy with specific knobs replaced; unknown keys are dropped."""
        clean = {k: v for k, v in kwargs.items()
                 if k in TUNABLE and v is not None}
        if not clean:
            return self
        if "seed" in clean:
            clean["seed"] = _coerce_seed(clean["seed"])
        return replace(self, **clean)

    # ------------------------------------------------------------- adapters

    @property
    def do_sample(self) -> bool:
        """Greedy decoding when the temperature is zero, sampling otherwise."""
        return self.temperature is not None and self.temperature > 0

    def for_transformers(self, tokenizer=None) -> Dict[str, Any]:
        """
        Keyword arguments for ``model.generate``.

        Sampling knobs are invalid without sampling and make transformers emit
        a warning per call, so greedy decoding passes none of them.
        """
        kwargs: Dict[str, Any] = {
            "max_new_tokens": self.max_tokens,
            "do_sample": self.do_sample,
        }
        if self.do_sample:
            kwargs["temperature"] = self.temperature
            kwargs["top_p"] = self.top_p
            if self.top_k > 0:
                kwargs["top_k"] = self.top_k
            if self.min_p > 0:
                kwargs["min_p"] = self.min_p
        if self.repeat_penalty and self.repeat_penalty != 1.0:
            kwargs["repetition_penalty"] = self.repeat_penalty
        # stop_strings needs the tokenizer to know where the strings end.
        if self.stop and tokenizer is not None:
            kwargs["stop_strings"] = list(self.stop)
            kwargs["tokenizer"] = tokenizer
        return kwargs

    def for_llama_cpp(self) -> Dict[str, Any]:
        """Keyword arguments for ``Llama.create_chat_completion``."""
        kwargs: Dict[str, Any] = {
            "temperature": max(self.temperature, 0.0),
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k if self.top_k > 0 else 0,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
        }
        if self.seed is not None:
            kwargs["seed"] = self.seed
        if self.stop:
            kwargs["stop"] = list(self.stop)
        return kwargs

    def for_ollama_options(self) -> Dict[str, Any]:
        """The ``options`` block of an Ollama chat request."""
        options: Dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "num_predict": self.max_tokens,
        }
        if self.min_p > 0:
            options["min_p"] = self.min_p
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx
        if self.seed is not None:
            options["seed"] = self.seed
        if self.stop:
            options["stop"] = list(self.stop)
        return options

    def for_openai(self) -> Dict[str, Any]:
        """
        Body fields for an OpenAI-compatible endpoint.

        top_k, min_p and repeat_penalty have no place in that schema and are
        left out rather than sent and rejected.
        """
        body: Dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            body["seed"] = self.seed
        if self.stop:
            body["stop"] = list(self.stop)
        return body

    def to_dict(self) -> Dict[str, Any]:
        """Telemetry shape: what was actually used, and where it came from."""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "max_tokens": self.max_tokens,
            "num_ctx": self.num_ctx or None,
            "seed": self.seed,
            "stop": list(self.stop),
            "grammar": bool(self.grammar),
            "source": self.source,
        }

    def summary(self) -> str:
        return (
            f"T={self.temperature} top_p={self.top_p} top_k={self.top_k} "
            f"min_p={self.min_p} rep={self.repeat_penalty} "
            f"max={self.max_tokens}"
            f"{' grammar' if self.grammar else ''} [{self.source}]"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_seed(value: Any) -> Optional[int]:
    """
    Zero and empty mean "no seed".

    The shipped provider config carries ``"seed": 0``, which Ollama treats as
    unset. Forwarding a literal 0 to a runtime that treats it as a real seed
    would silently pin every answer to the same sample.
    """
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def explicit_overrides(provider_key: str, provider_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    The tunables the user genuinely changed, relative to what Sigma Studio ships.

    A value equal to the shipped default carries no intent: it is there because
    the config file has to contain something. Treating it as an override is how
    a vendor recipe ends up overwritten by a number nobody chose.
    """
    if not provider_cfg:
        return {}

    try:
        from core.ai_providers import DEFAULT_AI_CONFIG
        shipped = DEFAULT_AI_CONFIG.get("providers", {}).get(provider_key, {})
    except Exception:                       # import cycle or missing table
        shipped = {}

    overrides: Dict[str, Any] = {}
    for key in TUNABLE:
        if key not in provider_cfg:
            continue
        value = provider_cfg[key]
        if value is None or value == "":
            continue
        if key in shipped and shipped[key] == value:
            continue                        # untouched default, not an opinion
        overrides[key] = value
    return overrides
