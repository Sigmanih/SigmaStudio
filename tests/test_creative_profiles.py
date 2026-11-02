"""Profili, contratti e scelte esplicite funzionano senza caricare modelli."""
import asyncio
import copy
import pytest

from core.modules.sigma_creative_lab.backends.comfyui_backend import ComfyUIBackend
from core.modules.sigma_creative_lab.model_profiles import prepare_profile, validate_profile
from core.modules.sigma_creative_lab.workflow_registry import WorkflowRegistry


DEFINITIONS = {
    "Weights": {"input": {"required": {"ckpt_name": [["paint.safetensors", "other.safetensors"]]}}, "output": ["MODEL"]},
    "Draw": {"input": {"required": {"model": ["MODEL"], "text": ["STRING"], "steps": ["INT", {"min": 1, "max": 100}]}}, "output": ["IMAGE"]},
    "Save": {"input": {"required": {"images": ["IMAGE"]}}, "output": [], "output_node": True},
}
GRAPH = {"1": {"class_type": "Weights", "inputs": {"ckpt_name": "{{ckpt}}"}},
         "2": {"class_type": "Draw", "inputs": {"model": ["1", 0], "text": "{{prompt}}", "steps": "{{steps}}"}},
         "3": {"class_type": "Save", "inputs": {"images": ["2", 0]}}}


@pytest.fixture
def setup_profile(tmp_path, monkeypatch):
    registry = WorkflowRegistry(tmp_path / "workflows")
    registry.save({"id": "my_template", "name": "Template immagine", "capability": "text_to_image", "defaults": {"steps": 8}}, GRAPH)
    backend = ComfyUIBackend()
    async def describe(name):
        return DEFINITIONS.get(name, {})
    monkeypatch.setattr(backend, "_object_info", describe)
    return registry, backend


def test_profilo_nuovo_diventa_un_modello_selezionabile(setup_profile, monkeypatch):
    registry, backend = setup_profile
    profile = prepare_profile({"label": "Modello Civitai", "workflow_id": "my_template", "checkpoint": "paint.safetensors"}, registry)
    check = asyncio.run(validate_profile(profile, backend))
    assert check["ok"] and check["checked_nodes"] == 3
    registry.save(profile.to_dict(), profile.workflow)
    from core.modules.sigma_creative_lab import workflow_registry, model_registry
    monkeypatch.setattr(workflow_registry, "registry", registry)
    model = model_registry.get_model(f"workflow:{profile.id}")
    assert model and model.tasks == ("text_to_image",)
    assert model in model_registry.models_for_task("text_to_image")


def test_adapter_conserva_il_file_e_i_componenti_del_profilo(setup_profile, monkeypatch):
    registry, _backend = setup_profile
    profile = prepare_profile({"label": "Modello HF", "workflow_id": "my_template", "checkpoint": "other.safetensors"}, registry)
    registry.save(profile.to_dict(), profile.workflow)
    from core.modules.sigma_creative_lab.generators.adapters import comfyui_adapter
    monkeypatch.setattr(comfyui_adapter, "workflow_registry", registry)
    graph, file = comfyui_adapter.ComfyUIAdapter(config={"checkpoints": {"sdxl": "wrong.safetensors"}})._resolve("text_to_image", {"workflow": profile.id, "prompt": "Un paesaggio"})
    assert file == "other.safetensors" and graph["1"]["inputs"]["ckpt_name"] == file
    assert graph["2"]["inputs"]["steps"] == 8


@pytest.mark.parametrize("change,expected", [
    ({"parameters": {"not_a_parameter": "x"}}, "non espone"),
    ({"label": ""}, "nome"),
    ({"workflow_id": "missing"}, "workflow"),
])
def test_profilo_rifiuta_configurazioni_non_governabili(setup_profile, change, expected):
    registry, _ = setup_profile
    with pytest.raises(ValueError, match=expected):
        prepare_profile({"label": "Modello", "workflow_id": "my_template", **change}, registry)


def test_file_assente_e_nodo_mancante_non_diventano_profili_pronti(setup_profile):
    registry, backend = setup_profile
    profile = prepare_profile({"label": "Test", "workflow_id": "my_template", "checkpoint": "missing.gguf"}, registry)
    assert not asyncio.run(validate_profile(profile, backend))["ok"]
    graph = copy.deepcopy(GRAPH)
    graph["1"]["class_type"] = "MissingGGUFLoader"
    graph["1"]["inputs"]["ckpt_name"] = "paint.gguf"
    result = asyncio.run(backend.validate_workflow(graph))
    assert not result["ok"] and any("non installato" in s for s in result["problems"])


@pytest.mark.parametrize("value", ["abc", -1, 101, True, 2.5])
def test_preflight_rifiuta_parametri_numerici_non_validi(setup_profile, value):
    _, backend = setup_profile
    graph = copy.deepcopy(GRAPH)
    graph["1"]["inputs"]["ckpt_name"] = "paint.safetensors"
    graph["2"]["inputs"].update(text="test", steps=value)
    assert not asyncio.run(backend.validate_workflow(graph))["ok"]


def test_preflight_rifiuta_collegamenti_tipo_e_uscite_errati(setup_profile):
    _, backend = setup_profile
    graph = copy.deepcopy(GRAPH)
    graph["1"]["inputs"]["ckpt_name"] = "paint.safetensors"
    graph["2"]["inputs"].update(text="test", steps=8)
    graph["3"]["inputs"]["images"] = ["1", 0]
    assert any("incompatibile" in p for p in asyncio.run(backend.validate_workflow(graph))["problems"])
    graph["3"]["inputs"]["images"] = ["2", 12]
    assert any("inesistente" in p for p in asyncio.run(backend.validate_workflow(graph))["problems"])


def test_modello_esplicito_invalido_non_viene_sostituito(monkeypatch):
    from core.modules.sigma_creative_lab import model_registry as reg
    monkeypatch.setattr(reg, "available_vram_gb", lambda: 16)
    assert reg.select_model("text_to_image", {"pollinations"}, forced_model="not-a-model") == (None, None)
    assert reg.select_model("text_to_image", {"comfyui"}, forced_model="sam2") == (None, None)


def test_scelta_esplicita_non_invia_la_richiesta_a_un_altro_servizio(monkeypatch):
    from core.modules.sigma_creative_lab.generators.image_generator import ImageGenerator
    gen = ImageGenerator(None, None)
    calls = []
    class Adapter:
        async def text_to_image(self, *args):
            raise RuntimeError("modello incompatibile")
    def adapter(name):
        calls.append(name)
        return Adapter()
    monkeypatch.setattr(gen, "_get_adapter", adapter)
    with pytest.raises(RuntimeError, match="incompatibile"):
        asyncio.run(gen._call_with_fallback("comfyui", "text_to_image", "test", {}, allow_fallback=False))
    assert calls == ["comfyui"]


def test_skill_documentate_usano_solo_tool_registrati():
    from core.modules.sigma_creative_lab.creative_skills import skill_catalog
    from core.modules.sigma_creative_lab.mcp_server import CreativeMCPServer
    server = CreativeMCPServer()
    tools = {tool["name"] for tool in server.list_tools()}
    skills = skill_catalog(True)
    assert len(skills) == 3
    assert all(set(skill["tools"]) <= tools and "\n---\n" in skill["instructions"] for skill in skills)
