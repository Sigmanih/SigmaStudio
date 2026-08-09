import asyncio

import pytest

from core.creative.asset_graph import AssetType
from core.creative.editors.image_editor import ImageEditor
from core.creative.materials.texture_generator import TextureGenerator
from core.creative.pipeline.creative_pipeline_engine import CreativePipelineEngine


@pytest.fixture
def engine(graph, router, generator, blender_off):
    pe = CreativePipelineEngine(graph, router, blender_off)
    # Il fake adapter sostituisce ogni chiamata di rete dei sotto-moduli.
    pe.image_gen = generator
    pe.image_ed = ImageEditor(router, graph, generator)
    pe.tex_gen = TextureGenerator(router, graph, generator)
    return pe


def _pipeline(nodes, connections):
    return {"nodes": nodes, "connections": connections}


def test_catena_prompt_generate_bgremove_upscale(engine, graph):
    events = []
    results = asyncio.run(engine.execute_pipeline(_pipeline(
        [
            {"node_id": "n1", "node_type": "prompt", "params": {"prompt": "a chair"}},
            {"node_id": "n2", "node_type": "image_generate", "params": {"width": 64, "height": 64}},
            {"node_id": "n3", "node_type": "bg_remove", "params": {}},
            {"node_id": "n4", "node_type": "upscale", "params": {"scale": 2}},
        ],
        [
            {"from_node": "n1", "from_port": "text", "to_node": "n2", "to_port": "prompt"},
            {"from_node": "n2", "from_port": "image", "to_node": "n3", "to_port": "image"},
            {"from_node": "n3", "from_port": "image", "to_node": "n4", "to_port": "image"},
        ],
    ), progress_callback=events.append))

    assert len(results) == 1
    assert results[0].type is AssetType.IMAGE
    # La lineage risale fino all'immagine generata dal primo nodo
    lineage = graph.get_lineage(results[0].asset_id)
    assert lineage["parents"][0]["parents"][0]["operation"] == "text_to_image"
    assert events[-1]["status"] == "complete"
    assert any(e.get("status") == "node_complete" for e in events)


def test_solo_i_nodi_foglia_finiscono_negli_output(engine):
    # n2 alimenta due rami: entrambi i rami sono output, n2 no.
    results = asyncio.run(engine.execute_pipeline(_pipeline(
        [
            {"node_id": "n1", "node_type": "prompt", "params": {"prompt": "x"}},
            {"node_id": "n2", "node_type": "image_generate", "params": {"width": 64, "height": 64}},
            {"node_id": "n3", "node_type": "bg_remove", "params": {}},
            {"node_id": "n4", "node_type": "relight", "params": {"light_direction": "top"}},
        ],
        [
            {"from_node": "n1", "from_port": "text", "to_node": "n2", "to_port": "prompt"},
            {"from_node": "n2", "from_port": "image", "to_node": "n3", "to_port": "image"},
            {"from_node": "n2", "from_port": "image", "to_node": "n4", "to_port": "image"},
        ],
    )))

    assert {a.metadata["operation"] for a in results} == {"remove_background", "relight"}


def test_ciclo_rilevato(engine):
    with pytest.raises(ValueError, match="Ciclo"):
        asyncio.run(engine.execute_pipeline(_pipeline(
            [
                {"node_id": "a", "node_type": "bg_remove", "params": {}},
                {"node_id": "b", "node_type": "bg_remove", "params": {}},
            ],
            [
                {"from_node": "a", "from_port": "image", "to_node": "b", "to_port": "image"},
                {"from_node": "b", "from_port": "image", "to_node": "a", "to_port": "image"},
            ],
        )))


def test_tipo_nodo_sconosciuto(engine):
    with pytest.raises(ValueError, match="Tipo nodo sconosciuto"):
        asyncio.run(engine.execute_pipeline(_pipeline(
            [{"node_id": "a", "node_type": "teletrasporto", "params": {}}], []
        )))


def test_input_non_collegato_produce_errore_leggibile(engine):
    with pytest.raises(RuntimeError, match="Input 'image' mancante"):
        asyncio.run(engine.execute_pipeline(_pipeline(
            [{"node_id": "a", "node_type": "bg_remove", "params": {}}], []
        )))


def test_connessione_verso_nodo_inesistente(engine):
    with pytest.raises(ValueError, match="inesistente"):
        asyncio.run(engine.execute_pipeline(_pipeline(
            [{"node_id": "a", "node_type": "bg_remove", "params": {}}],
            [{"from_node": "fantasma", "from_port": "image", "to_node": "a", "to_port": "image"}],
        )))


def test_errore_di_un_nodo_riporta_nodo_e_causa(engine, graph):
    mesh = graph.create_asset(AssetType.MESH, "mesh_senza_file")
    with pytest.raises(RuntimeError, match="Nodo 'm'"):
        asyncio.run(engine.execute_pipeline(_pipeline(
            [
                {"node_id": "src", "node_type": "asset_input", "params": {"asset_id": mesh.asset_id}},
                {"node_id": "m", "node_type": "mesh_cleanup", "params": {}},
            ],
            [{"from_node": "src", "from_port": "mesh", "to_node": "m", "to_port": "mesh"}],
        )))


def test_asset_input_carica_dal_vault(engine, image_asset):
    results = asyncio.run(engine.execute_pipeline(_pipeline(
        [
            {"node_id": "src", "node_type": "asset_input", "params": {"asset_id": image_asset.asset_id}},
            {"node_id": "up", "node_type": "upscale", "params": {"scale": 2}},
        ],
        [{"from_node": "src", "from_port": "image", "to_node": "up", "to_port": "image"}],
    )))

    assert results[0].source_assets == [image_asset.asset_id]


def test_texture_gen_da_immagine(engine, image_asset):
    results = asyncio.run(engine.execute_pipeline(_pipeline(
        [
            {"node_id": "src", "node_type": "asset_input", "params": {"asset_id": image_asset.asset_id}},
            {"node_id": "tex", "node_type": "texture_gen", "params": {"resolution": 64}},
        ],
        [{"from_node": "src", "from_port": "image", "to_node": "tex", "to_port": "image"}],
    )))

    assert results[0].type is AssetType.MATERIAL
    assert "normal" in results[0].files


def test_catalogo_nodi_allineato_agli_executor(engine):
    from core.creative.creative_router import NODE_CATALOG

    catalog_types = {n["type"] for n in NODE_CATALOG}
    assert catalog_types == set(engine.node_types)
