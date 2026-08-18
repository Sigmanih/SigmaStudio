# ==============================================================================
# tests/conftest.py — Shared test fixtures
# ==============================================================================
import pytest


@pytest.fixture(autouse=True, scope="module")
def release_engine_vram():
    """
    Frees any model the shared SigmaEngine singleton is holding, after each
    test module.

    Several code paths load a model as a side effect -- agent routing calls
    call_ai_model, which with the sigma_engine provider pulls the full model
    into VRAM. A module that does that leaves ~17GB resident, and the next
    module's engine tests then plan against a machine that looks out of memory
    and fail for reasons unrelated to what they assert.
    """
    yield

    try:
        from core.engine.unified_runtime import sigma_engine
        if sigma_engine.model_instance is not None:
            sigma_engine.unload()
    except Exception:
        # Never let cleanup mask a real test failure.
        pass
