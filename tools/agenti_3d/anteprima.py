"""Render ripetibile di un personaggio e delle sue pose, eseguito dentro Blender."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.logger import get_logger

log = get_logger("agenti_3d.anteprima")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modello", type=Path, required=True)
    parser.add_argument("--libreria", type=Path, required=True)
    parser.add_argument("--uscita", type=Path, required=True)
    parser.add_argument("--clip", default="Idle_Loop")
    parser.add_argument("--tempo", type=float, default=0.4)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.libreria))
    source_objects = list(bpy.data.objects)
    source_arm = next(obj for obj in source_objects if obj.type == "ARMATURE")
    actions = list(bpy.data.actions)
    action = next(action for action in actions if action.name == args.clip)
    action.use_fake_user = True
    for obj in source_objects:
        if obj.type == "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(args.modello))
    arm = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE" and obj is not source_arm)
    scene = bpy.context.scene
    source_arm.animation_data_create()
    idle = next(item for item in actions if item.name == "Idle_Loop")
    source_arm.animation_data.action = idle
    if idle.slots:
        source_arm.animation_data.action_slot = idle.slots[0]
    scene.frame_set(int(idle.frame_range[0]))
    source_reference = {bone.name: (source_arm.matrix_world @ bone.matrix).to_quaternion() for bone in source_arm.pose.bones}
    reference_hip = source_arm.matrix_world @ source_arm.pose.bones["DEF-hips"].head
    target_reference = {bone.name: (arm.matrix_world @ bone.matrix).to_quaternion() for bone in arm.pose.bones}
    source_arm.animation_data.action = action
    if action.slots:
        source_arm.animation_data.action_slot = action.slots[0]
    scene.frame_set(int(action.frame_range[0] + args.tempo * scene.render.fps))
    def depth(bone):
        return 0 if bone.parent is None else depth(bone.parent) + 1
    for bone in sorted(arm.pose.bones, key=depth):
        source = source_arm.pose.bones.get(bone.name)
        if source is None:
            continue
        rotation = (source_arm.matrix_world @ source.matrix).to_quaternion() @ source_reference[bone.name].inverted() @ target_reference[bone.name]
        position = arm.matrix_world @ bone.head
        if bone.name == "DEF-hips":
            position += source_arm.matrix_world @ source.head - reference_hip
        bone.matrix = arm.matrix_world.inverted() @ Matrix.LocRotScale(position, rotation, Vector((1, 1, 1)))
        bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 640
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.055, 0.075, 0.11, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    for name, position, energy, size in [
        ("Key", (2.5, -3.5, 4), 450, 4),
        ("Fill", (-3, -2, 2.5), 260, 3),
        ("Rim", (1, 2.5, 3), 500, 3),
    ]:
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.shape, light.size = energy, "DISK", size
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0, 0, 1)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200)
    floor = bpy.context.object
    material = bpy.data.materials.new("Pavimento")
    material.diffuse_color = (0.025, 0.04, 0.065, 1)
    floor.data.materials.append(material)
    camera = bpy.data.cameras.new("Camera")
    obj = bpy.data.objects.new("Camera", camera)
    scene.collection.objects.link(obj)
    obj.location = (2.1, -4.2, 1.85)
    obj.rotation_euler = (Vector((0, 0, 0.95)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    camera.type, camera.ortho_scale = "ORTHO", 2.25
    scene.camera = obj
    args.uscita.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(args.uscita.resolve())
    bpy.ops.render.render(write_still=True)
    log.info("Anteprima %s: %s", args.clip, args.uscita)


if __name__ == "__main__":
    main()
