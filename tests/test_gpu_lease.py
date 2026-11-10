"""Lease delle GPU: un render lungo sposta l'LLM sulle schede libere."""

import pytest

from core.engine.gpu_lease import GpuLeases, apply_to_llama_command


def comando():
    return ["llama-server", "-m", "x.gguf", "-ngl", "-1", "-sm", "layer", "-mg", "0", "-ts", "16,8"]


def test_senza_lease_nulla_cambia():
    env, cmd = {}, comando()
    assert apply_to_llama_command(env, cmd, 2, reserved=set()) == ""
    assert cmd == comando() and "CUDA_VISIBLE_DEVICES" not in env


def test_llm_spostato_sulla_gpu_libera():
    env, cmd = {}, comando()
    nota = apply_to_llama_command(env, cmd, 2, reserved={0})
    assert env["CUDA_VISIBLE_DEVICES"] == "1"
    # Gli indici dei device ripartono da zero dopo il filtro, e la ripartizione
    # su due schede non ha piu' senso con una sola visibile.
    assert cmd[cmd.index("-mg") + 1] == "0"
    assert "-ts" not in cmd
    assert cmd[cmd.index("-sm") + 1] == "none"
    assert "GPU [1]" in nota


def test_tutte_riservate_porta_su_cpu():
    env, cmd = {}, comando()
    apply_to_llama_command(env, cmd, 2, reserved={0, 1})
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"
    assert cmd[cmd.index("-ngl") + 1] == "0"
    assert "-mg" not in cmd


def test_rispetta_la_visibilita_gia_ristretta():
    env, cmd = {"CUDA_VISIBLE_DEVICES": "1"}, comando()
    assert apply_to_llama_command(env, cmd, 2, reserved={0}) == ""
    assert env["CUDA_VISIBLE_DEVICES"] == "1"


def test_conflitto_fra_proprietari_diversi():
    leases = GpuLeases()
    lid = leases.acquire("produzione:a", [0], "render")
    with pytest.raises(RuntimeError):
        leases.acquire("produzione:b", [0, 1], "render")
    assert leases.reserved() == {0}
    assert leases.release(lid)
    assert leases.reserved() == set()


def test_lease_scaduto_non_blocca():
    leases = GpuLeases()
    lid = leases.acquire("produzione:a", [1], "render", ttl_s=0.01)
    import time
    time.sleep(0.05)
    assert leases.reserved() == set()
    assert not leases.renew(lid)


def test_llm_partito_in_ram_torna_in_vram_a_lease_finito(monkeypatch):
    """Collaudo del video lungo: il 27B partito su CPU durante il render ci restava anche dopo."""
    from core.engine import gpu_lease
    from core.engine.backends.llamaserver_backend import LlamaServerBackend
    from core.engine.unified_runtime import UniversalSigmaEngine

    registro = GpuLeases()
    monkeypatch.setattr(gpu_lease, "leases", registro)
    lease = registro.acquire("produzione:x", [0, 1], "render")

    class Vivo:
        def poll(self):
            return None

    backend = LlamaServerBackend()
    backend._processo = Vivo()
    backend._riservate_avvio = frozenset(registro.reserved())
    assert not backend.placement_stale              # GPU ancora riservate: resta dov'e'

    motore = UniversalSigmaEngine.__new__(UniversalSigmaEngine)
    motore.active_backend_instance = backend
    scaricati = []
    monkeypatch.setattr(UniversalSigmaEngine, "unload", lambda self: scaricati.append(True) or {})
    assert motore.refresh_placement() is False

    registro.release(lease)
    assert backend.placement_stale
    backend._in_volo = 1                             # sta generando: non si tocca
    assert motore.refresh_placement() is False
    backend._in_volo = 0
    assert motore.refresh_placement() is True and scaricati == [True]
