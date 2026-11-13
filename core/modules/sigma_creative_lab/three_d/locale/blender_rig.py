"""Scheletro e pesi per un agente a figura intera, con le animazioni CC0 di Quaternius.

Gira dentro Blender. Lo scheletro Quaternius viene adattato alla figura senza
alterare la posa naturale della superficie. Il runtime adatta le clip nello
spazio globale rispetto alla posa neutra: copiare le rotazioni locali di una
T-pose su un corpo rilassato deformava due volte le articolazioni.
I pesi seguono le superfici anatomiche separate e sono interpolati ai giunti.

    blender --background --factory-startup --python three_d/locale/blender_rig.py -- \
        --personaggio <cartella>/statico.glb \
        --libreria store/engine_runtime/image3d/animazioni/AnimationLibrary_Godot_Standard.glb \
        --uscita <cartella>/personaggio.glb \
        [--animazioni sigma_studio/public/models/animazioni_agenti.glb]

Di solito lo lancia agenti.py, che fa tutta la catena dal ritratto in poi.

--animazioni esporta anche le clip scelte, una volta per tutti i personaggi.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from core.logger import get_logger  # noqa: E402

log = get_logger("creative.blender_rig")

# Le clip che la plancia usa: stare in piedi, camminare, sedersi e parlare
CLIP = (
    "Idle_Loop", "Idle_Talking_Loop", "Walk_Loop", "Walk_Formal_Loop",
    "Sitting_Enter", "Sitting_Idle_Loop", "Sitting_Talking_Loop", "Sitting_Exit", "Interact",
)


def argomenti() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--personaggio", type=Path, required=True)
    p.add_argument("--libreria", type=Path, required=True)
    p.add_argument("--uscita", type=Path, required=True)
    p.add_argument("--animazioni", type=Path, default=None)
    return p.parse_args(argv)


def importa(percorso: Path) -> list[bpy.types.Object]:
    prima = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(percorso))
    return [o for o in bpy.data.objects if o not in prima]


def applica_trasformazioni(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def vertici_mondo(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def punta_della_mano(vertici: list[Vector], lato: float, spalla: Vector) -> Vector:
    """Il punto del braccio piu' lontano dalla spalla, fuori dal busto e sopra il bacino."""
    candidati = [v for v in vertici if v.x * lato > abs(spalla.x) * 1.2 and v.z > spalla.z * 0.45]
    return max(candidati, key=lambda v: (v - spalla).length)


def caviglia(vertici: list[Vector], lato: float, quota: float) -> Vector:
    fascia = [v for v in vertici if v.x * lato > 0.01 and abs(v.z - quota) < 0.03]
    n = len(fascia) or 1
    return Vector((sum(v.x for v in fascia) / n, sum(v.y for v in fascia) / n, quota))


def discendenti(osso: bpy.types.EditBone) -> list[bpy.types.EditBone]:
    out = [osso]
    for figlio in osso.children:
        out.extend(discendenti(figlio))
    return out


def allinea_catena(radice: bpy.types.EditBone, da_perno: Vector, da: Vector, a_perno: Vector, a: Vector) -> None:
    """Porta la catena dal segmento da_perno->da al segmento a_perno->a (sposta, ruota, scala)."""
    v_da, v_a = da - da_perno, a - a_perno
    rot = v_da.rotation_difference(v_a).to_matrix().to_4x4()
    scala = Matrix.Scale(v_a.length / v_da.length, 4)
    m = Matrix.Translation(a_perno) @ rot @ scala @ Matrix.Translation(-da_perno)
    for osso in discendenti(radice):
        osso.transform(m, scale=True, roll=True)


def asse_del_braccio(vertici: list[Vector], lato: float, da_z: float, a_z: float) -> tuple[Vector, Vector] | None:
    """Retta del braccio dai centri delle sue sezioni: (punto, direzione verso l'alto).

    In A-pose una fetta orizzontale tra polso e meta' braccio taglia busto e
    braccio in due gruppi di vertici separati: il gruppo piu' esterno e' il
    braccio. Piu' in alto no: spallacci e maniche si confondono con il busto.
    """
    centri = []
    z = da_z
    while z < a_z:
        fetta = sorted((v for v in vertici if v.x * lato > 0 and abs(v.z - z) < 0.008), key=lambda v: v.x * lato)
        if len(fetta) > 6:
            gruppi = [[fetta[0]]]
            for v in fetta[1:]:
                if (v.x - gruppi[-1][-1].x) * lato > 0.02:
                    gruppi.append([])
                gruppi[-1].append(v)
            if len(gruppi) >= 2 and len(gruppi[-1]) > 3:
                g = gruppi[-1]
                centri.append(Vector((sum(v.x for v in g) / len(g), sum(v.y for v in g) / len(g), z)))
        z += 0.015
    if len(centri) < 5:
        return None
    # Minimi quadrati di x(z) e y(z): la retta passa per il baricentro dei centri
    n = len(centri)
    mz = sum(c.z for c in centri) / n
    mx = sum(c.x for c in centri) / n
    my = sum(c.y for c in centri) / n
    szz = sum((c.z - mz) ** 2 for c in centri) or 1e-6
    kx = sum((c.z - mz) * (c.x - mx) for c in centri) / szz
    ky = sum((c.z - mz) * (c.y - my) for c in centri) / szz
    return Vector((mx, my, mz)), Vector((kx, ky, 1.0)).normalized()


def adatta_scheletro(arm: bpy.types.Object, corpo: bpy.types.Object) -> None:
    vertici = vertici_mondo(corpo)
    altezza = max(v.z for v in vertici)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for lato, s in ((1.0, "L"), (-1.0, "R")):
        braccio = eb[f"DEF-upper_arm.{s}"]
        spalla = braccio.head.copy()
        dito = max((eb[n].tail for n in (f"DEF-f_middle.03.{s}", f"DEF-f_index.03.{s}")), key=lambda t: abs(t.x))
        mano = punta_della_mano(vertici, lato, spalla)
        nuova_spalla = spalla
        asse = asse_del_braccio(vertici, lato, mano.z + 0.15, altezza * 0.72)
        if asse:
            # L'articolazione resta alla quota del manichino (stessa altezza del
            # personaggio), ma sulla retta del braccio vero
            punto, direzione = asse
            nuova_spalla = punto + direzione * ((spalla.z - punto.z) / direzione.z)
            # In A-pose il braccio pende in un piano frontale: la profondita' giusta
            # e' quella media delle sue sezioni. Estrapolata dava una spalla dietro
            # il busto e una mano davanti, con l'osso di traverso nel corpo e i
            # pesi del manichino finiti sulle superfici sbagliate.
            nuova_spalla.y = punto.y
            mano = Vector((mano.x, punto.y, mano.z))
        log.info("braccio %s: spalla %s -> %s, mano %s", s, tuple(round(c, 3) for c in spalla),
                 tuple(round(c, 3) for c in nuova_spalla), tuple(round(c, 3) for c in mano))
        allinea_catena(braccio, spalla, dito.copy(), nuova_spalla, mano)

        coscia = eb[f"DEF-thigh.{s}"]
        anca = coscia.head.copy()
        piede = eb[f"DEF-foot.{s}"].head.copy()
        allinea_catena(coscia, anca, piede, anca, caviglia(vertici, lato, piede.z))
    bpy.ops.object.mode_set(mode="OBJECT")


def esporta(oggetti: list[bpy.types.Object], uscita: Path, animazioni: bool) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in oggetti:
        o.select_set(True)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(uscita),
        export_format="GLB",
        use_selection=True,
        export_image_format="JPEG",
        export_image_quality=85,
        export_yup=True,
        export_skins=True,
        export_animations=animazioni,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_def_bones=False,
    )


def regolarizza_pesi(corpo: bpy.types.Object) -> None:
    """I pesi devono variare sulla superficie senza aperture artificiali nelle ascelle."""
    bpy.ops.object.select_all(action="DESELECT")
    corpo.select_set(True)
    bpy.context.view_layer.objects.active = corpo
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    bpy.ops.object.vertex_group_smooth(group_select_mode="ALL", factor=0.45, repeat=4)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)


def pesa_anatomia(corpo: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Separa le superfici degli arti prima di interpolare i pesi delle articolazioni.

    La sola superficie più vicina del manichino assegnava lembi di giacca al
    polso: un errore invisibile a riposo, distruttivo durante la rotazione.
    """
    from mathutils.kdtree import KDTree

    vertices = vertici_mondo(corpo)
    height = max(v.z for v in vertices)
    split_z = height * 0.66
    parents = list(range(len(vertices)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for edge in corpo.data.edges:
        a, b = edge.vertices
        if vertices[a].z < split_z and vertices[b].z < split_z:
            ra, rb = root(a), root(b)
            if ra != rb:
                parents[rb] = ra
    components = {}
    for i, vertex in enumerate(vertices):
        if vertex.z < split_z:
            components.setdefault(root(i), []).append(i)
    labels = {}
    anchors = []
    for indices in components.values():
        if len(indices) < 80:
            continue
        minimum = min(vertices[i].z for i in indices)
        center_x = sum(vertices[i].x for i in indices) / len(indices)
        label = ("L" if center_x > 0 else "R") if minimum > height * 0.32 and abs(center_x) > height * 0.095 else "body"
        for index in indices:
            labels[index] = label
            anchors.append(index)
    tree = KDTree(len(anchors))
    for index in anchors:
        tree.insert(vertices[index], index)
    tree.balance()
    axial = ["DEF-hips", "DEF-spine.001", "DEF-spine.002", "DEF-spine.003", "DEF-neck", "DEF-head"]
    axial = [name for name in axial if name in arm.data.bones]
    arms = {side: [f"DEF-{name}.{side}" for name in ("upper_arm", "forearm", "hand")] for side in "LR"}
    legs = {side: [f"DEF-{name}.{side}" for name in ("thigh", "shin", "foot", "toe")] for side in "LR"}
    bones = {bone.name: (arm.matrix_world @ bone.head_local, arm.matrix_world @ bone.tail_local)
             for bone in arm.data.bones if bone.name in axial + sum(arms.values(), []) + sum(legs.values(), [])}
    corpo.vertex_groups.clear()
    groups = {name: corpo.vertex_groups.new(name=name) for name in bones}
    hip_z = bones["DEF-hips"][0].z

    def distance(point, segment):
        a, b = segment
        delta = b - a
        fraction = max(0, min(1, (point - a).dot(delta) / max(delta.length_squared, 1e-10)))
        return (point - a - delta * fraction).length

    for index, vertex in enumerate(vertices):
        label = labels.get(index)
        if label is None and vertex.z < split_z and anchors:
            _, nearest, _ = tree.find(vertex)
            label = labels[nearest]
        side = "L" if vertex.x >= 0 else "R"
        if label in arms and vertex.z < split_z - 0.035:
            candidates = arms[label]
        elif vertex.z < hip_z - 0.12:
            candidates = ["DEF-hips", *legs[side]]
        elif label == "body" and vertex.z < split_z - 0.035:
            candidates = [*axial, *legs[side][:1]]
        else:
            candidates = axial + ([*arms[side], *legs[side][:1]] if vertex.z < height * 0.84 else [])
        scored = []
        for name in candidates:
            if name not in bones:
                continue
            radius = height * (0.072 if name in axial else 0.027)
            d = max(0, distance(vertex, bones[name]) - radius)
            scored.append((name, d))
        scored.sort(key=lambda item: item[1])
        nearest_distance = scored[0][1]
        weights = [(name, math.exp(-min(60, (d * d - nearest_distance ** 2) / (height * 0.026) ** 2))) for name, d in scored[:4]]
        total = sum(value for _, value in weights)
        for name, value in weights:
            if value / total > 0.0001:
                groups[name].add([index], value / total, "REPLACE")
    corpo.parent = arm
    modifier = corpo.modifiers.new("Armature", "ARMATURE")
    modifier.object = arm
    log.info("Pesi anatomici: %d superfici, %d vertici di ancoraggio", len(components), len(anchors))


def ripara_microfori(corpo: bpy.types.Object) -> None:
    """Chiude soltanto contorni piccoli e chiusi, mantenendo UV e aperture anatomiche."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(corpo.data)
    uv = bm.loops.layers.uv.active
    pending = {edge for edge in bm.edges if edge.is_boundary}
    selected_edges = []
    while pending:
        edges, stack = set(), [pending.pop()]
        while stack:
            edge = stack.pop()
            edges.add(edge)
            for vertex in edge.verts:
                for adjacent in vertex.link_edges:
                    if adjacent in pending:
                        pending.remove(adjacent)
                        stack.append(adjacent)
        vertices = {vertex for edge in edges for vertex in edge.verts}
        if len(edges) > 48 or any(sum(edge in edges for edge in vertex.link_edges) != 2 for vertex in vertices):
            continue
        extent = max((max(v.co[axis] for v in vertices) - min(v.co[axis] for v in vertices)) for axis in range(3))
        if extent > 0.055:
            continue
        selected_edges.extend(edges)
    original_faces = set(bm.faces)
    coordinates = {vertex: next((loop[uv].uv.copy() for loop in vertex.link_loops), None) for edge in selected_edges for vertex in edge.verts} if uv else {}
    materials = {vertex: next((face.material_index for face in vertex.link_faces), 0) for edge in selected_edges for vertex in edge.verts}
    faces = bmesh.ops.holes_fill(bm, edges=selected_edges, sides=48).get("faces", []) if selected_edges else []
    for face in faces:
        if face in original_faces:
            continue
        face.material_index = materials.get(face.verts[0], 0)
        face.smooth = True
        if uv:
            for loop in face.loops:
                if coordinates.get(loop.vert) is not None:
                    loop[uv].uv = coordinates[loop.vert]
    repaired = len(faces)
    bm.to_mesh(corpo.data)
    bm.free()
    log.info("Microfori riparati: %d superfici", repaired)


def main() -> int:
    args = argomenti()
    bpy.ops.wm.read_factory_settings(use_empty=True)

    libreria = importa(args.libreria)
    arm = next(o for o in libreria if o.type == "ARMATURE")
    manichino = next(o for o in libreria if o.type == "MESH" and o.parent == arm)
    altezza = manichino.dimensions.z

    if args.animazioni:
        # Solo lo scheletro originale con le clip scelte: a riposo e' quello del
        # manichino, quindi le rotazioni esportate sono quelle della libreria.
        for a in list(bpy.data.actions):
            if a.name not in CLIP:
                bpy.data.actions.remove(a)
        esporta([arm], args.animazioni, animazioni=True)
        log.info("animazioni: %s (%d clip)", args.animazioni.name, len(bpy.data.actions))

    for o in libreria:
        if o.type == "MESH" and o is not manichino:
            bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    arm.animation_data_clear()

    corpo = next(o for o in importa(args.personaggio) if o.type == "MESH")
    corpo.parent = None
    applica_trasformazioni(corpo)
    s = altezza / corpo.dimensions.z
    corpo.scale = (s, s, s)
    applica_trasformazioni(corpo)
    # L'originale conserva la base della libreria, la copia segue il personaggio.
    ripara_microfori(corpo)
    adattato = arm.copy()
    adattato.data = arm.data.copy()
    bpy.context.collection.objects.link(adattato)
    adatta_scheletro(adattato, corpo)
    pesa_anatomia(corpo, adattato)
    regolarizza_pesi(corpo)
    adattato["sigma_rig_version"] = 4
    adattato["sigma_reference_pose"] = "idle"
    bpy.data.objects.remove(manichino, do_unlink=True)
    bpy.data.objects.remove(arm, do_unlink=True)
    esporta([adattato, corpo], args.uscita, animazioni=False)
    log.info("%s: %d vertici pesati su %d, altezza %.2f m", args.uscita.name,
             sum(1 for v in corpo.data.vertices if v.groups), len(corpo.data.vertices), altezza)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log.exception("rig fallito: %s", exc)
        sys.exit(1)
