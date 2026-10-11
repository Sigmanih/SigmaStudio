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
