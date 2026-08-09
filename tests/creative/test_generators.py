import asyncio
import os

import pytest
from PIL import Image

from core.creative.asset_graph import AssetType
from core.creative.editors.image_editor import ImageEditor
from core.creative.materials.material_system import MaterialSystem
from core.creative.materials.texture_generator import TextureGenerator
from core.creative.mesh.mesh_processor import MeshProcessor
from core.creative.params import normalize_params
from core.creative.three_d.model_generator import ModelGenerator3D


# ---------------------------------------------------------------- generatori

def test_text_to_image_scrive_il_file_e_la_thumbnail(graph, generator):
    asset = asyncio.run(generator.text_to_image("a cat", width=64, height=64))

    assert asset.type is AssetType.IMAGE
    assert os.path.exists(asset.files["image"])
    assert os.path.exists(asset.thumbnail)
    assert asset.metadata["generator"] == "pollinations"


def test_text_to_image_accetta_i_parametri_camelcase_della_ui(graph, generator):
    # La UI invia negativePrompt/cfg: prima della normalizzazione era un TypeError.
    params = normalize_params({
        "prompt": "a cat", "negativePrompt": "blurry", "cfg": 7, "steps": "30",
        "width": 64, "height": 64, "seed": -1,
    })
    prompt = params.pop("prompt")
    asset = asyncio.run(generator.text_to_image(prompt, backend=None, **params))

    assert asset.metadata["params"]["negative_prompt"] == "blurry"
    assert asset.metadata["params"]["cfg_scale"] == 7.0
    assert asset.metadata["params"]["steps"] == 30


def test_text_to_image_rifiuta_prompt_vuoto(generator):
    with pytest.raises(ValueError):
        asyncio.run(generator.text_to_image("   "))


def test_upscale_accetta_backend_e_raddoppia_la_risoluzione(graph, generator, image_asset):
    upscaled = asyncio.run(generator.upscale(image_asset.asset_id, scale=2, backend="pollinations"))

    assert Image.open(upscaled.files["image"]).size == (128, 128)
    assert upscaled.source_assets == [image_asset.asset_id]


def test_image_to_image_richiede_un_file_sorgente(graph, generator):
    orphan = graph.create_asset(AssetType.IMAGE, "senza_file")
    with pytest.raises(ValueError, match="file immagine"):
        asyncio.run(generator.image_to_image(orphan.asset_id, "prompt"))


def test_fallback_su_backend_che_non_implementa_l_operazione(graph, router, generator):
    class SoloTesto:
        async def text_to_image(self, prompt, params):
            from tests.creative.conftest import make_png
            return make_png()

    generator._get_adapter = lambda name: SoloTesto() if name == "rotto" else _pollinations()
    asset = asyncio.run(generator.text_to_image("x", width=64, height=64, backend="rotto"))
    assert asset.metadata["generator"] == "rotto"


def _pollinations():
    from core.creative.generators.adapters.pollinations_adapter import PollinationsAdapter
    return PollinationsAdapter()


# ------------------------------------------------------------------- editing

def test_remove_background_produce_rgba(graph, generator, image_asset):
    editor = ImageEditor(None, graph, generator)
    out = asyncio.run(editor.remove_background(image_asset.asset_id))

    assert Image.open(out.files["image"]).mode == "RGBA"
    assert out.metadata["method"] in ("rembg", "flood_fill")


def test_outpaint_allarga_la_tela(graph, router, generator, image_asset):
    editor = ImageEditor(router, graph, generator)
    out = asyncio.run(editor.outpaint(image_asset.asset_id, "right", 32, "extend"))

    assert Image.open(out.files["image"]).size == (96, 64)
    assert out.metadata["direction"] == "right"


def test_outpaint_rifiuta_direzioni_non_valide(graph, router, generator, image_asset):
    editor = ImageEditor(router, graph, generator)
    with pytest.raises(ValueError, match="Direzione"):
        asyncio.run(editor.outpaint(image_asset.asset_id, "diagonale", 32, "x"))


def test_inpaint_senza_maschera_fallisce(graph, router, generator, image_asset):
    editor = ImageEditor(router, graph, generator)
    with pytest.raises(ValueError, match="Maschera"):
        asyncio.run(editor.inpaint(image_asset.asset_id, "", "un cane"))


def test_inpaint_compone_la_patch_sulla_maschera(graph, router, generator, image_asset):
    import base64
    import io as _io
    from PIL import ImageDraw

    mask = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(mask).rectangle([10, 10, 40, 40], fill=(255, 0, 0, 128))
    buf = _io.BytesIO()
    mask.save(buf, "PNG")

    editor = ImageEditor(router, graph, generator)
    out = asyncio.run(editor.inpaint(
        image_asset.asset_id,
        "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        "un cane",
    ))

    assert out.metadata["method"] == "local_composite"
    assert os.path.exists(out.files["image"])
    assert out.source_assets == [image_asset.asset_id]


def test_relight_produce_un_asset_derivato(graph, router, generator, image_asset):
    editor = ImageEditor(router, graph, generator)
    out = asyncio.run(editor.relight(image_asset.asset_id, "left", 1.5))

    assert out.metadata["light_direction"] == "left"
    assert os.path.exists(out.files["image"])


# ------------------------------------------------------------------ materiali

def test_generate_pbr_crea_tutte_le_mappe(graph, router, generator):
    tg = TextureGenerator(router, graph, generator)
    material = asyncio.run(tg.generate_pbr("oak wood", resolution=64))

    assert material.type is AssetType.MATERIAL
    assert set(material.files) == {"albedo", "normal", "roughness", "metallic", "height", "ao"}
    assert all(os.path.exists(p) for p in material.files.values())


def test_generate_from_image_riusa_un_asset_esistente(graph, router, generator, image_asset):
    tg = TextureGenerator(router, graph, generator)
    material = asyncio.run(tg.generate_from_image(image_asset.asset_id, resolution=64))

    assert material.source_assets == [image_asset.asset_id]
    assert Image.open(material.files["normal"]).size == (64, 64)


def test_create_pbr_material_risolve_gli_asset_id(graph, blender_off, image_asset):
    ms = MaterialSystem(graph, blender_off)
    material = asyncio.run(ms.create_pbr_material({"albedo": image_asset.asset_id}, "mio_materiale"))

    assert material.type is AssetType.MATERIAL
    assert os.path.exists(material.files["albedo"])


def test_apply_to_mesh_senza_blender_spiega_il_problema(graph, blender_off, image_asset):
    ms = MaterialSystem(graph, blender_off)
    material = asyncio.run(ms.create_pbr_material({"albedo": image_asset.asset_id}))
    mesh = graph.create_asset(AssetType.MESH, "mesh_finta")
    graph.save_file(mesh.asset_id, "model.glb", b"glTF-fake")
    graph.update_asset(mesh.asset_id, files={"model": (graph.asset_dir(mesh.asset_id) / "model.glb").as_posix()})

    with pytest.raises(RuntimeError, match="Blender"):
        asyncio.run(ms.apply_to_mesh(mesh.asset_id, material.asset_id))


# ----------------------------------------------------------------------- mesh

def test_mesh_op_senza_file_non_crea_asset_vuoti(graph, blender_off):
    mp = MeshProcessor(graph, blender_off)
    mesh = graph.create_asset(AssetType.MESH, "mesh_senza_file")

    with pytest.raises(ValueError, match="file mesh"):
        asyncio.run(mp.cleanup(mesh.asset_id))
    assert len(graph.list_assets()) == 1  # nessun derivato fantasma


def test_mesh_op_senza_blender_indica_la_configurazione(graph, blender_off):
    mp = MeshProcessor(graph, blender_off)
    mesh = graph.create_asset(AssetType.MESH, "mesh")
    path = graph.save_file(mesh.asset_id, "model.glb", b"glTF-fake")
    graph.update_asset(mesh.asset_id, files={"model": path})

    with pytest.raises(RuntimeError, match="Blender"):
        asyncio.run(mp.decimate(mesh.asset_id, 0.5))


def test_get_mesh_info_legge_il_glb(graph, blender_off):
    mp = MeshProcessor(graph, blender_off)
    mesh = graph.create_asset(AssetType.MESH, "cubo")
    path = graph.save_file(mesh.asset_id, "model.glb", _minimal_glb())
    graph.update_asset(mesh.asset_id, files={"model": path})

    info = asyncio.run(mp.get_mesh_info(mesh.asset_id))
    assert info["status"] == "ok"
    assert info["vertices"] == 8
    assert info["faces"] == 4
    assert info["source"] == "gltf_parser"


def _minimal_glb() -> bytes:
    """Un .glb valido quanto basta per il parser degli accessor."""
    import json
    import struct

    doc = {
        "asset": {"version": "2.0"},
        "accessors": [{"count": 8, "type": "VEC3"}, {"count": 12, "type": "SCALAR"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 0}, "indices": 1}]}],
        "materials": [{"name": "m"}],
    }
    payload = json.dumps(doc).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    header = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(payload))
    chunk = struct.pack("<II", len(payload), 0x4E4F534A)
    return header + chunk + payload


# ------------------------------------------------------------------------- 3D

def test_image_to_3d_senza_backend_spiega_cosa_configurare(graph, router, generator, image_asset):
    mg = ModelGenerator3D(router, graph, generator)
    with pytest.raises(RuntimeError, match="backend 3D"):
        asyncio.run(mg.image_to_3d(image_asset.asset_id))


def test_asset_3d_ha_un_tipo_valido(graph):
    # 'model_3d' non esisteva nell'enum: rileggere l'asset sollevava ValueError.
    asset = graph.create_asset("model_3d", "modello")
    assert graph.get_asset(asset.asset_id).type is AssetType.MODEL_3D
