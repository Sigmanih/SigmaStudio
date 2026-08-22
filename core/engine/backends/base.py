# ==============================================================================
# core/engine/backends/base.py — Inference backend contract
#
# A backend pairs a weight format with a runtime. Which one is right depends on
# the machine as much as the model: the same GGUF should run on llama.cpp CUDA
# kernels on a desktop, Metal on Apple silicon and NEON on a Raspberry Pi, while
# safetensors on a CUDA box wants transformers plus bitsandbytes.
#
# Every backend must be able to say whether it can actually run here, before
# being asked to. Reporting a backend whose dependency is missing produces a
# plan that cannot execute, which is worse than reporting none.
# ==============================================================================
from abc import ABC, abstractmethod
from typing import Dict, Any, Generator, Optional, Tuple

from core.engine.model_inspector import ModelFacts
from core.engine.sampling import SamplingParams


class InferenceBackend(ABC):
    """One way of running a model. Selected per model and per machine."""

    #: Stable identifier used in logs, telemetry and the API.
    name: str = "abstract"

    #: Weight formats this backend can load, as reported by ModelInspector.
    supported_formats: Tuple[str, ...] = ()

    # --------------------------------------------------------- capabilities

    @classmethod
    @abstractmethod
    def availability(cls) -> Tuple[bool, str]:
        """
        Whether this backend can run on this machine right now.

        Returns (available, reason). The reason is shown to the user when no
        backend can serve a model, so it must name the missing piece rather
        than merely saying no.
        """

    @classmethod
    def supports(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> bool:
        """Whether this backend can load this particular checkpoint."""
        return facts.weight_format in cls.supported_formats

    @classmethod
    @abstractmethod
    def score(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> int:
        """
        Preference for this model on this hardware; highest wins.

        Scores are compared only among backends that are both available and
        support the format, so they express speed and quality, not capability.
        """

    # -------------------------------------------------------------- runtime

    @abstractmethod
    def load(self, facts: ModelFacts, hardware: Dict[str, Any], **options) -> Dict[str, Any]:
        """
        Loads the model. Returns a structured result carrying at least
        ``success``; failures carry ``error`` with the real cause.
        """

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        messages: Optional[list] = None,
        params: Optional["SamplingParams"] = None,
        cancel: Any = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Yields token chunks shaped like the engine's streaming contract.

        `messages` carries the full conversation when the caller has one;
        prompt/system_prompt remain for single-turn callers.

        `params` is the resolved sampler, identical across backends; each one
        adapts it to its own runtime rather than inventing its own defaults.
        A backend that receives None builds one from temperature and
        max_tokens, so older callers keep working.

        `cancel` is a CancellationToken, checked between tokens so an
        abandoned request stops costing compute.
        """

    @abstractmethod
    def unload(self) -> Dict[str, Any]:
        """Releases the model and returns the memory it held."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Whether a model is currently resident in this backend."""

    def describe_placement(self) -> Dict[str, Any]:
        """Where the weights actually ended up, for reporting against the plan."""
        return {}

    def telemetry(self) -> Dict[str, Any]:
        """Backend-specific settings that are genuinely in effect."""
        return {}

    def benchmark(self, prompt_tokens: int = 128, decode_tokens: int = 24) -> Dict[str, Any]:
        """
        Measures prefill and decode speed on this backend, or says it cannot.

        The default answer is an honest refusal rather than silence: a backend
        that does not implement this is a backend the tuning loop is blind on,
        and the caller has to be able to say so. Every backend that serves real
        traffic should override it -- otherwise the fastest path in the product
        is the one nobody can measure.
        """
        return {
            "success": False,
            "error": f"Il backend '{self.name}' non espone ancora un benchmark.",
            "backend": self.name,
        }


def module_available(name: str) -> bool:
    """Whether an import would succeed, without paying for the import."""
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False
