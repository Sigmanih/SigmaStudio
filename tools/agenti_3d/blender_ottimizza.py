"""Riduce la mesh di un agente a un GLB leggero per la plancia (anche sul Pi 5).

Gira dentro Blender, che ha gia' decimazione, UV e bake senza dipendenze nuove:

    blender --background --factory-startup --python tools/agenti_3d/blender_ottimizza.py -- \
        --ingresso store/agenti_3d/medico_ai/alto_gauss.ply \
        --uscita sigma_studio/public/models/agenti/medico_ai.glb --triangoli 14000 --texture 1024

Passi: via i frammenti staccati, decimazione, UV automatiche, bake del colore
dei vertici della mesh alta su una texture della mesh bassa, GLB con JPEG.
Accanto al GLB aggiorna indice.json, che la plancia legge per sapere quali
agenti hanno un modello, e salva un'anteprima fronte/retro in --anteprima.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.logger import get_logger  # noqa: E402

log = get_logger("agenti_3d.blender")

# Altezza del modello in unita' glTF: la plancia lo riscala comunque, ma un
# valore fisso rende confrontabili le misure di collo e spalle nell'indice.
ALTEZZA = 1.0


def argomenti() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--ingresso", type=Path, required=True)
    p.add_argument("--uscita", type=Path, required=True)
    p.add_argument("--triangoli", type=int, default=14000)
    p.add_argument("--texture", type=int, default=1024)
    p.add_argument("--qualita-jpeg", type=int, default=85)
    p.add_argument("--anteprima", type=Path, default=None)
    p.add_argument("--ruota", type=float, default=0.0, help="gradi attorno a Y per portare il viso verso +Z")
    return p.parse_args(argv)


def scena_vuota() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def importa(percorso: Path) -> bpy.types.Object:
    bpy.ops.wm.ply_import(filepath=str(percorso))
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    return obj


def tieni_parte_maggiore(obj: bpy.types.Object, quota_minima: float = 0.02) -> None:
    """Toglie i frammenti volanti tipici della ricostruzione da singola foto.

    Si tengono le isole con almeno il 2% delle facce: occhiali o cuffie staccati
    dal corpo restano, la polvere di triangoli no.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    visti: set[int] = set()
    isole: list[list[bmesh.types.BMFace]] = []
    for f in bm.faces:
        if f.index in visti:
            continue
        pila, isola = [f], []
        visti.add(f.index)
        while pila:
            cur = pila.pop()
            isola.append(cur)
            for e in cur.edges:
                for g in e.link_faces:
                    if g.index not in visti:
                        visti.add(g.index)
                        pila.append(g)
        isole.append(isola)
    soglia = quota_minima * len(bm.faces)
    da_togliere = [f for isola in isole if len(isola) < soglia for f in isola]
    bmesh.ops.delete(bm, geom=da_togliere, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()


def normalizza(obj: bpy.types.Object, gradi: float) -> None:
    """Base al suolo, centro sull'asse Y, altezza fissa, viso verso +Z (glTF)."""
    obj.rotation_euler = (0.0, 0.0, 0.0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = obj.data
    if gradi:
        # In Blender l'alto e' Z: la rotazione "attorno a Y" del glTF e' attorno a Z qui
        a = math.radians(gradi)
        c, s = math.cos(a), math.sin(a)
        for v in me.vertices:
            x, y = v.co.x, v.co.y
            v.co.x, v.co.y = c * x - s * y, s * x + c * y
    zs = [v.co.z for v in me.vertices]
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    scala = ALTEZZA / (zmax - zmin)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for v in me.vertices:
        v.co = Vector(((v.co.x - cx) * scala, (v.co.y - cy) * scala, (v.co.z - zmin) * scala))
    me.update()


def misura_collo(obj: bpy.types.Object) -> dict:
    """Altezza del collo come sezione piu' stretta tra il 45% e l'88% dell'altezza.

    Serve alla plancia per ruotare solo la testa senza scheletro: i vertici
    sopra il collo girano, quelli sotto restano fermi.
    """
    fasce = 48
    larghezze = [[math.inf, -math.inf] for _ in range(fasce)]
    for v in obj.data.vertices:
        i = min(fasce - 1, int(v.co.z / ALTEZZA * fasce))
        larghezze[i][0] = min(larghezze[i][0], v.co.x)
        larghezze[i][1] = max(larghezze[i][1], v.co.x)
    misure = [(b - a) if b > a else math.inf for a, b in larghezze]
    da, a = int(fasce * 0.45), int(fasce * 0.88)
    i_collo = min(range(da, a), key=lambda i: misure[i])
    spalle = max(m for m in misure[:i_collo] if m != math.inf)
    return {
        "collo": round((i_collo + 0.5) / fasce * ALTEZZA, 3),
        "larghezza_spalle": round(spalle, 3),
    }


def decima(obj: bpy.types.Object, triangoli: int) -> bpy.types.Object:
    basso = obj.copy()
    basso.data = obj.data.copy()
    basso.name = "agente"
    bpy.context.collection.objects.link(basso)
    attuali = len(basso.data.polygons)
    if attuali > triangoli:
        mod = basso.modifiers.new("decima", "DECIMATE")
        mod.ratio = triangoli / attuali
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = basso
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in basso.data.polygons:
        p.use_smooth = True
    return basso


def uv_automatiche(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")


def materiale_colore_vertici(obj: bpy.types.Object) -> None:
    mat = bpy.data.materials.new("colori_alti")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = obj.data.color_attributes[0].name
    emis = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(attr.outputs["Color"], emis.inputs["Color"])
    nt.links.new(emis.outputs["Emission"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def materiale_texture(obj: bpy.types.Object, lato: int) -> bpy.types.Image:
    img = bpy.data.images.new("agente_colore", lato, lato, alpha=False)
    mat = bpy.data.materials.new("agente")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.75
    bsdf.inputs["Metallic"].default_value = 0.0
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    # Il bake scrive sul nodo immagine attivo
    nt.nodes.active = tex
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    # Il colore di vertice serve solo al bake: nel GLB peserebbe senza servire
    while obj.data.color_attributes:
        obj.data.color_attributes.remove(obj.data.color_attributes[0])
    return img


def cuoci(alto: bpy.types.Object, basso: bpy.types.Object) -> None:
    scena = bpy.context.scene
    scena.render.engine = "CYCLES"
    scena.cycles.samples = 1
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "CUDA"
        scena.cycles.device = "GPU"
    except Exception as exc:  # senza GPU il bake su CPU e' solo piu' lento
        log.warning("bake su CPU: %s", exc)
    bake = scena.render.bake
    bake.use_selected_to_active = True
    bake.cage_extrusion = 0.02
    bake.max_ray_distance = 0.05
    bake.margin = 8
    bpy.ops.object.select_all(action="DESELECT")
    alto.select_set(True)
    basso.select_set(True)
    bpy.context.view_layer.objects.active = basso
    bpy.ops.object.bake(type="EMIT")


def esporta(basso: bpy.types.Object, uscita: Path, qualita: int) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    basso.select_set(True)
    bpy.context.view_layer.objects.active = basso
    uscita.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(uscita),
        export_format="GLB",
        use_selection=True,
        export_image_format="JPEG",
        export_image_quality=qualita,
        export_yup=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_animations=False,
    )


def anteprima(basso: bpy.types.Object, percorso: Path) -> None:
    """Fronte (-Y di Blender = +Z glTF) e retro, per giudicare la qualita'."""
    scena = bpy.context.scene
    scena.render.engine = "BLENDER_WORKBENCH"
    scena.display.shading.light = "FLAT"
    scena.display.shading.color_type = "TEXTURE"
    scena.render.resolution_x = 512
    scena.render.resolution_y = 512
    scena.render.film_transparent = True
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 1.15 * ALTEZZA
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    scena.camera = cam
    for nome, y, rot in (("fronte", -3.0, 0.0), ("retro", 3.0, math.pi)):
        cam.location = (0.0, y, ALTEZZA / 2)
        cam.rotation_euler = (math.pi / 2, 0.0, rot)
        scena.render.filepath = str(percorso.with_name(f"{percorso.stem}_{nome}.png"))
        bpy.ops.render.render(write_still=True)


def aggiorna_indice(uscita: Path, voce: dict) -> None:
    indice_path = uscita.parent / "indice.json"
    try:
        indice = json.loads(indice_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        indice = {"versione": 1, "modelli": {}}
    indice["modelli"][uscita.stem] = voce
    indice_path.write_text(json.dumps(indice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = argomenti()
    scena_vuota()
    alto = importa(args.ingresso)
    tieni_parte_maggiore(alto)
    normalizza(alto, args.ruota)
    collo = misura_collo(alto)
    basso = decima(alto, args.triangoli)
    uv_automatiche(basso)
    materiale_colore_vertici(alto)
    materiale_texture(basso, args.texture)
    cuoci(alto, basso)
    bpy.data.objects.remove(alto, do_unlink=True)
    esporta(basso, args.uscita, args.qualita_jpeg)
    if args.anteprima:
        anteprima(basso, args.anteprima)

    triangoli = sum(len(p.vertices) - 2 for p in basso.data.polygons)
    voce = {
        "file": args.uscita.name,
        "triangoli": triangoli,
        "texture": args.texture,
        "kb": round(args.uscita.stat().st_size / 1024),
        **collo,
    }
    aggiorna_indice(args.uscita, voce)
    log.info("%s: %s", args.uscita.name, json.dumps(voce))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Blender in background esce con 0 anche se lo script fallisce
        log.exception("ottimizzazione fallita: %s", exc)
        sys.exit(1)
