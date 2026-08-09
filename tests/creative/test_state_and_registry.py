import json

import pytest

from core.creative import model_state
from core.creative.backends import get_backend
from core.creative.backends.base import BackendJob
from core.creative.backends.comfyui_backend import ComfyUIBackend
from core.creative.model_state import ModelState, RuntimeTracker, build_inventory
from core.creative.workflow_registry import WorkflowRegistry, substitute


# ---------------------------------------------------------------- stato modelli

def _filesystem(**per_category):
    return {cat: {"label": cat, "folder": cat, "files": files}
            for cat, files in per_category.items()}


def test_file_su_disco_senza_backend_resta_installed():
    """Il caso che generava la contraddizione: file presente, pannello a zero."""
    fs = _filesystem(checkpoint=[{"filename": "sd_xl_base_1.0.safetensors", "size_gb": 6.46, "path": "/x"}])

    inv = build_inventory(fs, runtime=None, runtime_reachable=False, tracker=RuntimeTracker())
    record = inv["categories"]["checkpoint"]["models"][0]

    assert record["installed"] is True
    assert record["available"] is False
    assert record["state"] == ModelState.INSTALLED.value
    assert "non in esecuzione" in record["state_reason"]
    assert inv["totals"]["installed"] == 1 and inv["totals"]["available"] == 0


def test_backend_attivo_promuove_a_available():
    fs = _filesystem(checkpoint=[{"filename": "sd_xl_base_1.0.safetensors", "size_gb": 6.46, "path": "/x"}])
    runtime = {"checkpoints": ["sd_xl_base_1.0.safetensors"]}

    record = build_inventory(fs, runtime, runtime_reachable=True,
                             tracker=RuntimeTracker())["categories"]["checkpoint"]["models"][0]
    assert record["state"] == ModelState.AVAILABLE.value
    assert record["available"] is True and record["loaded"] is False


def test_installato_ma_non_indicizzato_ha_una_causa_diversa():
    """Backend acceso che però non elenca il file: serve un riavvio, non un download."""
    fs = _filesystem(checkpoint=[{"filename": "nuovo.safetensors", "size_gb": 2.0, "path": "/x"}])

    record = build_inventory(fs, {"checkpoints": []}, runtime_reachable=True,
                             tracker=RuntimeTracker())["categories"]["checkpoint"]["models"][0]
    assert record["state"] == ModelState.INSTALLED.value
    assert "non indicizzato" in record["state_reason"]


def test_loaded_e_active_derivano_dal_tracker():
    tracker = RuntimeTracker()
    fs = _filesystem(checkpoint=[{"filename": "m.safetensors", "size_gb": 6.0, "path": "/x"}])
    runtime = {"checkpoints": ["m.safetensors"]}

    tracker.mark_submitted("comfyui", ["m.safetensors"])
    record = build_inventory(fs, runtime, runtime_reachable=True, tracker=tracker)["categories"]["checkpoint"]["models"][0]
    assert record["state"] == ModelState.ACTIVE.value

    tracker.mark_finished("comfyui", ["m.safetensors"])
    record = build_inventory(fs, runtime, runtime_reachable=True, tracker=tracker)["categories"]["checkpoint"]["models"][0]
    assert record["state"] == ModelState.LOADED.value
    assert "VRAM" in record["state_reason"]


def test_backend_caduto_azzera_il_caricato():
    tracker = RuntimeTracker()
    tracker.mark_submitted("comfyui", ["m.safetensors"])
    tracker.clear_backend("comfyui")
    assert tracker.is_loaded("comfyui", "m.safetensors") is False


def test_modello_esposto_dal_backend_ma_fuori_cartella():
    fs = _filesystem(checkpoint=[])
    record = build_inventory(fs, {"checkpoints": ["altrove.safetensors"]}, runtime_reachable=True,
                             tracker=RuntimeTracker())["categories"]["checkpoint"]["models"][0]
    assert record["installed"] is False and record["available"] is True
    assert "fuori dalla cartella" in record["state_reason"]


def test_vram_stimata_dipende_dalla_categoria():
    assert model_state.estimate_vram_gb(6.0, "checkpoint") > 6.0     # pesi + attivazioni
    assert model_state.estimate_vram_gb(6.0, "upscaler") < 8.0       # lavora a tile
    assert model_state.estimate_vram_gb(0.2, "lora") < 1.0
    assert model_state.estimate_vram_gb(0, "checkpoint") == 0.0


def test_record_espone_le_capability_della_categoria():
    fs = _filesystem(checkpoint=[{"filename": "m.safetensors", "size_gb": 6.0, "path": "/x"}])
    record = build_inventory(fs, None, runtime_reachable=False)["categories"]["checkpoint"]["models"][0]
    assert set(record["capabilities"]) == {"text_to_image", "img_to_img", "inpaint"}


# ------------------------------------------------------------- registro workflow

@pytest.fixture
def registry(tmp_path):
    return WorkflowRegistry(tmp_path / "workflows")


def test_builtin_sempre_presenti_nel_registro(registry):
    entries = registry.load(force=True)
    assert "sdxl_txt2img" in entries
    assert entries["sdxl_txt2img"].source == "builtin"
    assert entries["sdxl_txt2img"].capability == "text_to_image"
    assert entries["sdxl_txt2img"].requirements["checkpoint"] == "sdxl"


def test_manifest_utente_sovrascrive_il_builtin(registry):
    registry.directory.mkdir(parents=True, exist_ok=True)
    (registry.directory / "sdxl_txt2img.json").write_text(json.dumps({
        "id": "sdxl_txt2img", "name": "Mio SDXL", "capability": "text_to_image",
        "workflow": {"1": {"class_type": "Custom", "inputs": {"text": "{{prompt}}"}}},
    }), encoding="utf-8")

    entry = registry.load(force=True)["sdxl_txt2img"]
    assert entry.source == "user" and entry.name == "Mio SDXL"
    assert len(entry.workflow) == 1


def test_export_grezzo_senza_manifest_deduce_la_capability(registry):
    registry.directory.mkdir(parents=True, exist_ok=True)
    (registry.directory / "mio_flux_kontext.json").write_text(
        json.dumps({"1": {"class_type": "X", "inputs": {"p": "{{prompt}}"}}}), encoding="utf-8")

    entry = registry.load(force=True)["mio_flux_kontext"]
    assert entry.capability == "instruct_edit"      # dedotta dal nome file
    assert entry.placeholders == {"prompt"}


def test_manifest_affiancato_a_un_export_grezzo(registry):
    registry.directory.mkdir(parents=True, exist_ok=True)
    (registry.directory / "custom.json").write_text(
        json.dumps({"1": {"class_type": "X", "inputs": {}}}), encoding="utf-8")
    (registry.directory / "custom.manifest.json").write_text(json.dumps({
        "id": "custom", "name": "Custom", "capability": "image_to_3d",
        "requirements": {"vram_gb": 12},
    }), encoding="utf-8")

    entry = registry.load(force=True)["custom"]
    assert entry.capability == "image_to_3d" and entry.requirements["vram_gb"] == 12


def test_salvataggio_valida_il_manifest(registry):
    with pytest.raises(ValueError, match="capability"):
        registry.save({"id": "x"}, {"1": {}})
    with pytest.raises(ValueError, match="id"):
        registry.save({"capability": "text_to_image"}, {"1": {}})
    with pytest.raises(ValueError, match="grafo"):
        registry.save({"id": "x", "capability": "text_to_image"}, {})

    saved = registry.save({"id": "mio", "capability": "upscale"}, {"1": {"class_type": "Z", "inputs": {}}})
    assert saved.id == "mio" and (registry.directory / "mio.json").exists()


def test_builtin_non_eliminabile(registry):
    registry.load(force=True)
    assert registry.delete("sdxl_txt2img") is False


def test_status_segnala_cosa_manca(registry):
    installed = {"checkpoint": {"files": [{"filename": "sd_xl_base_1.0.safetensors"}]}}
    checkpoints = {"sdxl": "sd_xl_base_1.0.safetensors", "flux": "flux1-dev-fp8.safetensors"}

    entries = {e["id"]: e for e in registry.status(installed, checkpoints, vram_gb=16.0)}
    assert entries["sdxl_txt2img"]["ready"] is True
    assert entries["flux_txt2img"]["ready"] is False
    assert "checkpoint flux" in entries["flux_txt2img"]["missing"][0]


def test_status_avvisa_sulla_vram_senza_bloccare(registry):
    installed = {"checkpoint": {"files": [{"filename": "qwen_image_fp8.safetensors"}]}}
    entries = {e["id"]: e for e in registry.status(
        installed, {"qwen": "qwen_image_fp8.safetensors"}, vram_gb=8.0)}
    assert entries["qwen_txt2img"]["ready"] is True         # i pesi ci sono
    assert entries["qwen_txt2img"]["notes"]                 # ma la VRAM non basta


def test_resolve_preserva_i_tipi_json(registry):
    graph = registry.resolve("sdxl_txt2img", {
        "prompt": "gatto", "width": 768, "height": 512, "seed": 7, "steps": 20,
        "cfg_scale": 7.5, "ckpt": "m.safetensors", "sampler": "euler",
        "scheduler": "normal", "negative_prompt": "",
    })
    assert graph["6"]["inputs"]["text"] == "gatto"
    assert graph["5"]["inputs"]["width"] == 768 and isinstance(graph["5"]["inputs"]["width"], int)
    assert graph["3"]["inputs"]["cfg"] == 7.5


def test_substitute_dentro_una_stringa_composita():
    out = substitute({"a": "prefisso {{x}} suffisso", "b": "{{n}}"}, {"x": "valore", "n": 42})
    assert out["a"] == "prefisso valore suffisso"
    assert out["b"] == 42        # placeholder isolato: tipo preservato


def test_resolve_workflow_inesistente(registry):
    with pytest.raises(KeyError, match="non presente"):
        registry.resolve("inesistente", {})


# --------------------------------------------------------------------- backend

def test_backend_factory():
    backend = get_backend("comfyui", {"url": "http://x:8188"})
    assert isinstance(backend, ComfyUIBackend) and backend.base_url == "http://x:8188"
    assert get_backend("motore_inesistente") is None


def test_job_finished_solo_negli_stati_terminali():
    assert BackendJob("1", "running").finished is False
    assert BackendJob("1", "done").finished is True
    assert BackendJob("1", "error").finished is True
    assert BackendJob("1", "cancelled").finished is True


def test_backend_legge_entrambi_gli_schemi_object_info():
    storico = {"input": {"required": {"ckpt_name": [["a.safetensors"], {}]}}}
    nuovo = {"input": {"required": {"model_name": ["COMBO", {"options": ["b.pth"]}]}}}
    assert ComfyUIBackend._options(storico, "ckpt_name") == ["a.safetensors"]
    assert ComfyUIBackend._options(nuovo, "model_name") == ["b.pth"]


def test_outputs_raccolti_da_tutti_i_tipi_di_nodo():
    history = {"outputs": {
        "9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]},
        "12": {"meshes": [{"filename": "m.glb", "subfolder": "3d", "type": "output"}]},
        "15": {"altro": [{"filename": "ignorato.txt"}]},
    }}
    files = ComfyUIBackend._collect_outputs(history)
    assert [f["filename"] for f in files] == ["a.png", "m.glb"]
    assert files[1]["subfolder"] == "3d"


# --------------------------------------------- default e normalizzazione input

def test_default_del_workflow_applicati_quando_il_chiamante_tace(registry):
    """Senza default, `scheduler: None` finiva al backend e il job veniva rifiutato."""
    graph = registry.resolve("sdxl_txt2img", {"prompt": "x", "ckpt": "m.safetensors"})
    assert graph["3"]["inputs"]["scheduler"] == "normal"
    assert graph["3"]["inputs"]["sampler_name"] == "euler"
    assert graph["5"]["inputs"]["width"] == 1024


def test_parametro_esplicito_vince_sul_default(registry):
    graph = registry.resolve("sdxl_txt2img", {
        "prompt": "x", "ckpt": "m", "scheduler": "karras", "width": 640})
    assert graph["3"]["inputs"]["scheduler"] == "karras"
    assert graph["5"]["inputs"]["width"] == 640


def test_none_non_sovrascrive_il_default(registry):
    graph = registry.resolve("sdxl_txt2img", {"prompt": "x", "ckpt": "m", "scheduler": None})
    assert graph["3"]["inputs"]["scheduler"] == "normal"


def test_seed_negativo_diventa_casuale_alla_risoluzione(registry):
    a = registry.resolve("sdxl_txt2img", {"prompt": "x", "ckpt": "m", "seed": -1})
    b = registry.resolve("sdxl_txt2img", {"prompt": "x", "ckpt": "m", "seed": -1})
    assert a["3"]["inputs"]["seed"] != b["3"]["inputs"]["seed"]
    assert isinstance(a["3"]["inputs"]["seed"], int) and a["3"]["inputs"]["seed"] >= 0


def test_alias_sampler_applicato_alla_risoluzione(registry):
    graph = registry.resolve("sdxl_txt2img", {"prompt": "x", "ckpt": "m", "sampler": "euler_a"})
    assert graph["3"]["inputs"]["sampler_name"] == "euler_ancestral"


def test_parametro_obbligatorio_mancante_e_dichiarato(registry):
    with pytest.raises(ValueError, match="ckpt"):
        registry.resolve("sdxl_txt2img", {"prompt": "x"})


def test_flux_ha_default_propri(registry):
    graph = registry.resolve("flux_txt2img", {"prompt": "x", "ckpt": "flux.safetensors"})
    assert graph["7"]["inputs"]["scheduler"] == "simple"     # non "normal" come SDXL
    assert graph["5"]["inputs"]["guidance"] == 3.5
