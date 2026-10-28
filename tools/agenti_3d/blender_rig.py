"""Scheletro e pesi per un agente a figura intera, con le animazioni CC0 di Quaternius.

Gira dentro Blender. Lo scheletro e' quello della Universal Animation Library
(CC0): adattato alle proporzioni del personaggio, le sue animazioni valgono
senza retargeting, perche' glTF e three.js le applicano come rotazioni locali
assolute per nome d'osso. Un braccio ruotato a riposo (A-pose invece di
T-pose) prende comunque la posa giusta: conta solo l'orientamento in posa.

I pesi arrivano dal manichino della libreria, messo nella posa dello scheletro
adattato: il calore delle ossa sulle mesh di TRELLIS lasciava lembi e schegge.

    blender --background --factory-startup --python tools/agenti_3d/blender_rig.py -- \
        --personaggio store/agenti_3d/sceneggiatore_intero/statico.glb \
        --libreria store/agenti_3d/_animazioni/AnimationLibrary_Godot_Standard.glb \
        --uscita store/agenti_3d/sceneggiatore_intero/personaggio.glb \
        [--animazioni sigma_studio/public/models/animazioni_agenti.glb]

--animazioni esporta anche le clip scelte, una volta per tutti i personaggi.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.logger import get_logger  # noqa: E402

log = get_logger("agenti_3d.rig")

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


def pesa_dal_manichino(corpo: bpy.types.Object, manichino: bpy.types.Object,
                       arm: bpy.types.Object, adattato: bpy.types.Object) -> None:
    """Travasa sul personaggio i pesi puliti del manichino Quaternius.

    Il calore delle ossa sulle mesh di TRELLIS (aperte, con superfici interne)
    lasciava schegge: il manichino invece e' pesato a mano per questo scheletro.
    Lo si mette nella posa e nelle proporzioni dello scheletro adattato, poi
    ogni vertice del personaggio prende i pesi della superficie piu' vicina.
    """
    def profondita(b: bpy.types.Bone) -> int:
        return 0 if b.parent is None else 1 + profondita(b.parent)

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for b in sorted(arm.data.bones, key=profondita):
        arm.pose.bones[b.name].matrix = adattato.data.bones[b.name].matrix_local.copy()
        bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")

    posato = manichino.copy()
    posato.data = manichino.data.copy()
    bpy.context.collection.objects.link(posato)
    bpy.ops.object.select_all(action="DESELECT")
    posato.select_set(True)
    bpy.context.view_layer.objects.active = posato
    for m in list(posato.modifiers):
        if m.type == "ARMATURE":
            bpy.ops.object.modifier_apply(modifier=m.name)

    corpo.vertex_groups.clear()
    for g in posato.vertex_groups:
        corpo.vertex_groups.new(name=g.name)
    trasf = corpo.modifiers.new("pesi", "DATA_TRANSFER")
    trasf.object = posato
    trasf.use_object_transform = True
    trasf.use_vert_data = True
    trasf.data_types_verts = {"VGROUP_WEIGHTS"}
    trasf.vert_mapping = "POLYINTERP_NEAREST"
    trasf.layers_vgroup_select_src = "ALL"
    trasf.layers_vgroup_select_dst = "NAME"
    bpy.ops.object.select_all(action="DESELECT")
    corpo.select_set(True)
    bpy.context.view_layer.objects.active = corpo
    bpy.ops.object.modifier_apply(modifier=trasf.name)
    bpy.data.objects.remove(posato, do_unlink=True)

    # Le dita non deformano (mani a blocco): il loro peso passa alla mano
    gruppi = {g.name: g for g in corpo.vertex_groups}
    for v in corpo.data.vertices:
        for s in ("L", "R"):
            dita = [g for g in v.groups if corpo.vertex_groups[g.group].name.endswith(f".{s}")
                    and ("f_" in corpo.vertex_groups[g.group].name or "thumb" in corpo.vertex_groups[g.group].name)]
            somma = sum(g.weight for g in dita)
            if somma > 0:
                gruppi[f"DEF-hand.{s}"].add([v.index], somma, "ADD")
    for nome in [n for n in gruppi if "f_" in n or "thumb" in n]:
        corpo.vertex_groups.remove(gruppi[nome])
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)

    corpo.parent = adattato
    mod = corpo.modifiers.new("Armature", "ARMATURE")
    mod.object = adattato
    for b in adattato.data.bones:
        if "f_" in b.name or "thumb" in b.name:
            b.use_deform = False


def taglia_ponti(corpo: bpy.types.Object, quota_spalla: float, lato_max: float = 0.05) -> int:
    """Toglie le membrane che TRELLIS lascia tra l'interno delle braccia e i fianchi.

    Da ferme non si vedono; appena il braccio si muove diventano lembi stirati.
    Una faccia e' una membrana se unisce vertici dominati dal braccio a vertici
    dominati da busto o gambe. Sotto la spalla le braccia a riposo sono staccate
    dal corpo, quindi ogni faccia mista e' una membrana; piu' su conta la
    lunghezza, perche' l'attacco della spalla ha facce corte e legittime.
    """
    import bmesh

    nomi = {g.index: g.name for g in corpo.vertex_groups}

    def catena(v) -> str:
        if not v.groups:
            return "altro"
        nome = nomi[max(v.groups, key=lambda g: g.weight).group]
        for s in ("L", "R"):
            if nome in (f"DEF-upper_arm.{s}", f"DEF-forearm.{s}", f"DEF-hand.{s}"):
                return f"braccio.{s}"
        return "altro"

    catene = [catena(v) for v in corpo.data.vertices]
    bm = bmesh.new()
    bm.from_mesh(corpo.data)
    bm.verts.ensure_lookup_table()
    via = []
    for f in bm.faces:
        tipi = {catene[v.index] for v in f.verts}
        if len(tipi) > 1 and any(t.startswith("braccio") for t in tipi):
            sotto = max(v.co.z for v in f.verts) < quota_spalla
            if sotto or max(e.calc_length() for e in f.edges) > lato_max:
                via.append(f)
    bmesh.ops.delete(bm, geom=via, context="FACES")
    bm.to_mesh(corpo.data)
    bm.free()
    return len(via)


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
    # Una copia da adattare: l'originale serve a mettere in posa il manichino
    adattato = arm.copy()
    adattato.data = arm.data.copy()
    bpy.context.collection.objects.link(adattato)
    adatta_scheletro(adattato, corpo)
    pesa_dal_manichino(corpo, manichino, arm, adattato)
    spalla_z = min((adattato.matrix_world @ adattato.data.bones[f"DEF-upper_arm.{s}"].head_local).z for s in "LR")
    log.info("membrane tolte: %d facce", taglia_ponti(corpo, spalla_z - 0.04))
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
