import asyncio
import json

import pytest

from core.creative import model_registry as reg
from core.creative.generators.adapters import comfy_workflows as cw
from core.creative.model_router import CreativeTask, ModelRouter


@pytest.fixture(autouse=True)
def no_user_workflows(tmp_path, monkeypatch):
    """Isola i test dai workflow presenti sulla macchina.

    Il registro è ora l'unica fonte di verità: si punta la sua directory su una
    cartella temporanea e si invalida la cache prima e dopo ogni test.
    """
    from core.creative.workflow_registry import registry

    directory = tmp_path / "workflows"
    monkeypatch.setattr(cw, "WORKFLOW_DIR", directory)
    monkeypatch.setattr(registry, "directory", directory)
    registry.load(force=True)
    yield directory
    monkeypatch.undo()
    registry.load(force=True)


def _write_workflow(directory, workflow_id: str, capability: str):
    """Simula un workflow esportato dall'utente e registrato in Sigma."""
    from core.creative.workflow_registry import registry

    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{workflow_id}.json").write_text(json.dumps({
        "id": workflow_id, "name": workflow_id, "capability": capability,
        "backend": "comfyui", "workflow": {"1": {"class_type": "X", "inputs": {}}},
    }), encoding="utf-8")
    registry.load(force=True)


@pytest.fixture
def big_gpu(monkeypatch):
    monkeypatch.setattr(reg, "available_vram_gb", lambda: 24.0)


@pytest.fixture
def small_gpu(monkeypatch):
    monkeypatch.setattr(reg, "available_vram_gb", lambda: 6.0)


# ------------------------------------------------------------------ selezione

def test_priorita_qualita_e_velocita_scelgono_modelli_diversi(big_gpu):
    fast, _ = reg.select_model("text_to_image", {"fal_ai"}, priority="speed")
    best, _ = reg.select_model("text_to_image", {"fal_ai"}, priority="quality")
    assert fast.speed > best.speed
    assert best.quality >= fast.quality


def test_vram_insufficiente_penalizza_i_modelli_locali(small_gpu):
    model, backend = reg.select_model("text_to_image", {"comfyui"}, priority="quality")
    # Su 6 GB nessun modello da 12-16 GB deve vincere.
    assert model.vram_gb <= 8.0, f"scelto {model.id} da {model.vram_gb} GB su 6 GB liberi"


def test_backend_remoto_ignora_il_vincolo_vram(small_gpu):
    model, backend = reg.select_model("image_to_3d", {"stability"}, priority="quality")
    assert backend == "stability"
    assert model.vram_gb == 0.0


def test_upscale_normale_usa_esrgan_restauro_usa_supir(big_gpu, no_user_workflows):
    # SUPIR richiede nodi custom: senza il suo workflow non sarebbe selezionabile.
    _write_workflow(no_user_workflows, "supir_upscale", "upscale")

    # Le tuple `prefer` sono quelle che ImageGenerator.upscale passa davvero.
    plain, _ = reg.select_model("upscale", {"comfyui"}, priority="balanced",
                                prefer=("veloce", "affidabile"))
    restore, _ = reg.select_model("upscale", {"comfyui"}, priority="quality",
                                  prefer=("ricostruzione_dettagli", "restauro"))
    assert plain.id == "real-esrgan"
    assert restore.id == "supir"


def test_modello_forzato_vince_sulla_selezione(big_gpu):
    model, backend = reg.select_model("text_to_image", {"comfyui", "fal_ai"},
                                      forced_model="sdxl")
    assert model.id == "sdxl"


def test_nessun_backend_nessun_modello():
    model, backend = reg.select_model("text_to_image", set())
    assert model is None and backend is None


def test_comfyui_escluso_se_manca_il_workflow_custom(big_gpu):
    # flux-kontext esiste solo con nodi custom: senza workflow non è selezionabile.
    model, backend = reg.select_model("instruct_edit", {"comfyui"})
    assert model is None and backend is None


def test_workflow_utente_riabilita_il_modello(big_gpu, no_user_workflows):
    _write_workflow(no_user_workflows, "flux_kontext", "instruct_edit")
    model, backend = reg.select_model("instruct_edit", {"comfyui"})
    assert model is not None and backend == "comfyui"


def test_catalogo_marca_disponibilita_e_workflow_mancanti(big_gpu):
    entries = {e["id"]: e for e in reg.catalog({"comfyui", "local"})}
    assert entries["sdxl"]["available"] is True            # workflow built-in
    assert entries["flux-kontext"]["workflow_missing"] is True
    assert entries["flux-kontext"]["available"] is False
    assert entries["pbr-derive"]["available"] is True      # backend "local"


# -------------------------------------------------------------------- router

def test_router_inietta_workflow_e_modello_remoto():
    router = ModelRouter({"creative": {"backends": {}}})
    spec = reg.get_model("flux.1-schnell")
    params = router.apply_model({"prompt": "x"}, spec, "fal_ai")
    assert params["model"] == "fal-ai/flux/schnell"
    assert params["workflow"] == "flux_txt2img"
    assert params["family"] == "flux"


def test_router_select_senza_backend_ritorna_pollinations():
    router = ModelRouter({"creative": {"backends": {}}})
    backend = asyncio.run(router.route(CreativeTask("image_to_3d", {})))
    assert backend == "pollinations"   # nessun modello 3D: fallback dichiarato


def test_router_cache_evita_ping_ripetuti(monkeypatch):
    router = ModelRouter({"creative": {"backends": {"comfyui": {"enabled": True, "url": "http://x"}}}})
    calls = []

    async def fake_ping(url):
        calls.append(url)
        return False

    monkeypatch.setattr(router, "_ping_comfyui", fake_ping)
    asyncio.run(router.get_available_backends())
    asyncio.run(router.get_available_backends())
    assert len(calls) == 1

    router.invalidate_status()
    asyncio.run(router.get_available_backends())
    assert len(calls) == 2


# ----------------------------------------------------------------- workflows

def test_build_sdxl_produce_un_grafo_coerente():
    wf = cw.build("sdxl_txt2img", {"ckpt": "m.safetensors", "prompt": "gatto",
                                   "negative_prompt": "sfocato", "width": 768, "height": 512, "seed": 42})
    assert wf["6"]["inputs"]["text"] == "gatto"
    assert wf["7"]["inputs"]["text"] == "sfocato"
    assert wf["5"]["inputs"]["width"] == 768
    assert wf["3"]["inputs"]["seed"] == 42
    assert wf["9"]["class_type"] == "SaveImage"


def test_build_inpaint_collega_maschera_e_latente():
    wf = cw.build("sdxl_inpaint", {"ckpt": "m.safetensors", "prompt": "p",
                                   "input_image": "a.png", "mask_image": "m.png"})
    assert wf["12"]["inputs"]["image"] == "m.png"
    assert wf["3"]["inputs"]["latent_image"] == ["13", 0]
    assert "5" not in wf   # niente latente vuoto in inpaint


def test_seed_casuale_quando_non_specificato():
    a = cw.build("sdxl_txt2img", {"ckpt": "m", "prompt": "x", "seed": -1})
    b = cw.build("sdxl_txt2img", {"ckpt": "m", "prompt": "x", "seed": -1})
    assert a["3"]["inputs"]["seed"] != b["3"]["inputs"]["seed"]


def test_workflow_custom_mancante_spiega_come_ottenerlo():
    with pytest.raises(cw.WorkflowNotAvailable, match="Save \\(API format\\)"):
        cw.build("hunyuan3d_image_to_3d", {"input_image": "x.png"})


def test_placeholder_utente_sostituiti_e_json_safe(no_user_workflows):
    no_user_workflows.mkdir(parents=True, exist_ok=True)
    (no_user_workflows / "custom.json").write_text(
        '{"1": {"class_type": "T", "inputs": {"text": "{{prompt}}", "w": {{width}}}}}', encoding="utf-8")

    wf = cw.build("custom", {"prompt": 'un "gatto"\nnero', "width": 640})
    assert wf["1"]["inputs"]["text"] == 'un "gatto"\nnero'   # virgolette non rompono il JSON
    assert wf["1"]["inputs"]["w"] == 640


# ------------------------------------------- inventario ComfyUI (pesi reali)

@pytest.fixture
def comfy_inventory():
    """Imposta e ripulisce l'inventario ComfyUI globale del registro."""
    def _set(inv):
        reg.set_comfy_inventory(inv)
    yield _set
    reg.set_comfy_inventory(None)


def _inventory(**kwargs):
    base = {
        "checkpoints": [], "unets": [], "upscale_models": [],
        "configured_checkpoints": {"sdxl": "sd_xl_base_1.0.safetensors",
                                   "flux": "flux1-dev-fp8.safetensors",
                                   "upscaler": "RealESRGAN_x4plus.pth"},
    }
    base.update(kwargs)
    return base


def test_comfyui_senza_pesi_non_viene_scelto(big_gpu, comfy_inventory):
    comfy_inventory(_inventory())
    model, backend = reg.select_model("text_to_image", {"comfyui"})
    assert model is None and backend is None


def test_conta_il_checkpoint_giusto_non_uno_qualsiasi(big_gpu, comfy_inventory):
    # C'è un modello, ma non è quello che il workflow FLUX/SDXL caricherebbe.
    comfy_inventory(_inventory(unets=["minimax_h3_video.safetensors"]))
    model, _ = reg.select_model("text_to_image", {"comfyui"})
    assert model is None

    comfy_inventory(_inventory(checkpoints=["sd_xl_base_1.0.safetensors"]))
    model, backend = reg.select_model("text_to_image", {"comfyui"})
    assert model.id == "sdxl" and backend == "comfyui"


def test_upscaler_richiede_la_sua_cartella(big_gpu, comfy_inventory):
    comfy_inventory(_inventory(checkpoints=["sd_xl_base_1.0.safetensors"]))
    model, _ = reg.select_model("upscale", {"comfyui"})
    assert model is None            # nessun upscale model installato

    comfy_inventory(_inventory(checkpoints=["sd_xl_base_1.0.safetensors"],
                               upscale_models=["RealESRGAN_x4plus.pth"]))
    model, _ = reg.select_model("upscale", {"comfyui"}, prefer=("veloce", "affidabile"))
    assert model.id == "real-esrgan"


def test_checkpoint_key_risolve_la_famiglia_di_pesi():
    assert reg.get_model("flux.1-schnell").checkpoint_key == "flux"
    assert reg.get_model("sd3.5-large").checkpoint_key == "sd3"
    assert reg.get_model("supir").checkpoint_key == "supir"   # nessun ckpt_key: usa family


# ------------------------------------------------ parsing object_info ComfyUI

def test_options_legge_entrambi_gli_schemi_comfyui():
    """ComfyUI 0.31 ha cambiato formato: leggerne uno solo nasconde i modelli."""
    from core.creative.generators.adapters.comfyui_adapter import ComfyUIAdapter

    storico = {"input": {"required": {"ckpt_name": [["a.safetensors", "b.safetensors"], {"tooltip": "x"}]}}}
    nuovo = {"input": {"required": {"model_name": ["COMBO", {"multiselect": False,
                                                             "options": ["RealESRGAN_x4plus.pth"]}]}}}
    vuoto = {"input": {"required": {"ckpt_name": [[], {"tooltip": "x"}]}}}
    tipo_semplice = {"input": {"required": {"seed": ["INT", {"default": 0}]}}}

    assert ComfyUIAdapter._options(storico, "ckpt_name") == ["a.safetensors", "b.safetensors"]
    assert ComfyUIAdapter._options(nuovo, "model_name") == ["RealESRGAN_x4plus.pth"]
    assert ComfyUIAdapter._options(vuoto, "ckpt_name") == []
    assert ComfyUIAdapter._options(tipo_semplice, "seed") == []
    assert ComfyUIAdapter._options({}, "qualsiasi") == []


# ------------------------------------------------- compatibilità dei sampler

def test_sampler_a1111_tradotto_per_comfyui():
    """`euler_a` è il nome SD WebUI: ComfyUI lo rifiuta con value_not_in_list."""
    wf = cw.build("sdxl_txt2img", {"ckpt": "m", "prompt": "x", "sampler": "euler_a"})
    assert wf["3"]["inputs"]["sampler_name"] == "euler_ancestral"

    wf = cw.build("sdxl_txt2img", {"ckpt": "m", "prompt": "x", "sampler": "DPM++ 2M Karras"})
    assert wf["3"]["inputs"]["sampler_name"] == "dpmpp_2m"


def test_sampler_gia_valido_resta_invariato():
    wf = cw.build("sdxl_txt2img", {"ckpt": "m", "prompt": "x", "sampler": "dpmpp_3m_sde"})
    assert wf["3"]["inputs"]["sampler_name"] == "dpmpp_3m_sde"


def test_senza_sampler_si_usa_il_default_del_backend():
    assert cw.build("sdxl_txt2img", {"ckpt": "m", "prompt": "x"})["3"]["inputs"]["sampler_name"] == "euler"
    assert cw.build("flux_txt2img", {"ckpt": "m", "prompt": "x"})["7"]["inputs"]["scheduler"] == "simple"


def test_vram_e_capacita_non_memoria_libera(monkeypatch):
    """Usare la VRAM libera farebbe smettere di scegliere un backend che funziona."""
    fake = {"gpus": [{"vram_total_gb": 16.0, "vram_free_gb": 1.2},
                     {"vram_total_gb": 8.0, "vram_free_gb": 7.9}]}
    monkeypatch.setattr("core.training.gpu.get_accelerator_report", lambda refresh=False: fake)
    assert reg.available_vram_gb() == 16.0
    assert reg.free_vram_gb() == 7.9


# ----------------------------------------------- validazione download esterni

def test_download_esterno_rifiuta_cartelle_e_percorsi_arbitrari():
    from core.creative.model_downloader import custom_asset

    valido = custom_asset({"folder": "loras", "filename": "stile.safetensors",
                           "url": "https://civitai.com/api/download/models/1", "source": "civitai"})
    assert valido.folder == "loras"

    with pytest.raises(ValueError, match="Cartella"):
        custom_asset({"folder": "../../windows/system32", "filename": "x.safetensors",
                      "url": "https://huggingface.co/a/resolve/main/x.safetensors"})

    with pytest.raises(ValueError, match="Hugging Face o Civitai"):
        custom_asset({"folder": "loras", "filename": "x.safetensors", "url": "http://evil.example/x"})


def test_download_esterno_normalizza_il_nome_file():
    from core.creative.model_downloader import custom_asset
    asset = custom_asset({"folder": "checkpoints", "filename": "../../../evil.safetensors",
                          "url": "https://huggingface.co/a/resolve/main/x.safetensors"})
    assert asset.filename == "evil.safetensors"
