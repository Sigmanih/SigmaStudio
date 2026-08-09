"""Verifiche di disponibilità per la segmentazione (isolate per testabilità)."""

from core.creative.generators.adapters.comfy_workflows import user_workflow_path


def sam2_ready() -> bool:
    """SAM 2 richiede nodi custom: è utilizzabile solo con workflow fornito."""
    return user_workflow_path("sam2_segment").exists()
