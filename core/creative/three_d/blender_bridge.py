import subprocess
import json
import tempfile
import asyncio
from pathlib import Path
from core.logger import get_logger

log = get_logger("blender_bridge")

class BlenderBridge:
    """Interfaccia a Blender headless tramite Python scripting."""
    
    def __init__(self, blender_path: str = ''):
        self.blender_path = blender_path or self._find_blender()
        
    def _find_blender(self) -> str:
        """Auto-detect Blender: PATH, poi le installazioni presenti sul sistema.

        Le versioni non sono elencate a mano — una lista fissa invecchia a ogni
        release e lascia inutilizzabile un Blender perfettamente installato.
        """
        import shutil
        found = shutil.which('blender')
        if found:
            return found

        roots = [
            Path('C:/Program Files/Blender Foundation'),
            Path('C:/Program Files (x86)/Blender Foundation'),
            Path.home() / 'AppData/Local/Programs/Blender Foundation',
            Path('/usr/share/blender'),
            Path('/Applications/Blender.app/Contents/MacOS'),
        ]
        versions = []
        for root in roots:
            if not root.is_dir():
                continue
            for exe in ('blender.exe', 'blender', 'Blender'):
                versions.extend(root.glob(f'*/{exe}'))
                direct = root / exe
                if direct.is_file():
                    versions.append(direct)

        # La più recente per ordinamento naturale del nome cartella (Blender 4.5 > 4.2)
        if versions:
            return str(sorted(versions, key=lambda p: p.parent.name, reverse=True)[0])
        return ''
    
    @property
    def available(self) -> bool:
        return bool(self.blender_path) and Path(self.blender_path).exists()

    @staticmethod
    def _import_snippet(input_path: str) -> str:
        """Snippet di import che rispetta l'estensione reale del file.

        Importare sempre come glTF fa fallire silenziosamente obj/fbx/stl.
        """
        ext = Path(input_path).suffix.lower().lstrip('.')
        ops = {
            'glb': 'bpy.ops.import_scene.gltf',
            'gltf': 'bpy.ops.import_scene.gltf',
            'fbx': 'bpy.ops.import_scene.fbx',
            'obj': 'bpy.ops.wm.obj_import',
            'stl': 'bpy.ops.wm.stl_import',
            'ply': 'bpy.ops.wm.ply_import',
        }
        op = ops.get(ext, 'bpy.ops.import_scene.gltf')
        return f'{op}(filepath=r"{input_path}")'


    async def import_mesh(self, file_path: str, format: str = 'glb') -> dict:
        """Importa mesh in Blender, ritorna info mesh."""
        script = f'''
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
# Import based on format
if '{format}' in ('glb', 'gltf'):
    bpy.ops.import_scene.gltf(filepath=r"{file_path}")
elif '{format}' == 'obj':
    bpy.ops.wm.obj_import(filepath=r"{file_path}")
elif '{format}' == 'fbx':
    bpy.ops.import_scene.fbx(filepath=r"{file_path}")

import json
result = {{}}
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        result[obj.name] = {{
            'vertices': len(obj.data.vertices),
            'faces': len(obj.data.polygons),
            'edges': len(obj.data.edges)
        }}
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)
    
    async def clean_mesh(self, input_path: str, output_path: str, params: dict = None) -> dict:
        """Pulisce mesh: rimuove duplicati, fix normals, merge by distance."""
        params = params or {}
        merge_dist = params.get('merge_distance', 0.001)
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold={merge_dist})
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format='GLB')
result = {{'vertices': len(bpy.data.objects[0].data.vertices) if bpy.data.objects else 0}}
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def uv_unwrap(self, input_path: str, output_path: str, method: str = 'smart_project') -> dict:
        """UV unwrap della mesh."""
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    if '{method}' == 'smart_project':
        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
    elif '{method}' == 'lightmap':
        bpy.ops.uv.lightmap_pack()
    else:
        bpy.ops.uv.unwrap(method='ANGLE_BASED')
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format='GLB')
result = {{'status': 'ok', 'method': '{method}'}}
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def decimate(self, input_path: str, output_path: str, ratio: float = 0.5) -> dict:
        """Riduce poligoni della mesh."""
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
result = {{'before_faces': 0, 'after_faces': 0, 'ratio': {ratio}}}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    bpy.context.view_layer.objects.active = obj
    before = len(obj.data.polygons)
    mod = obj.modifiers.new(name='Decimate', type='DECIMATE')
    mod.ratio = {ratio}
    bpy.ops.object.modifier_apply(modifier='Decimate')
    result['before_faces'] += before
    result['after_faces'] += len(obj.data.polygons)
bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format='GLB')
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def remesh(self, input_path: str, output_path: str, params: dict = None) -> dict:
        """Remesh voxel: topologia uniforme, utile prima di UV e sculpting."""
        params = params or {}
        voxel_size = params.get('voxel_size', 0.05)
        mode = params.get('mode', 'VOXEL')
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
result = {{'before_faces': 0, 'after_faces': 0, 'mode': '{mode}'}}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    bpy.context.view_layer.objects.active = obj
    result['before_faces'] += len(obj.data.polygons)
    mod = obj.modifiers.new(name='Remesh', type='REMESH')
    mod.mode = '{mode}'
    if '{mode}' == 'VOXEL':
        mod.voxel_size = {voxel_size}
    bpy.ops.object.modifier_apply(modifier='Remesh')
    result['after_faces'] += len(obj.data.polygons)
bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format='GLB')
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def smooth(self, input_path: str, output_path: str, iterations: int = 2) -> dict:
        """Laplacian smooth non distruttivo sui vertici."""
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
result = {{'iterations': {iterations}, 'objects': 0}}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name='Smooth', type='SMOOTH')
    mod.iterations = {iterations}
    bpy.ops.object.modifier_apply(modifier='Smooth')
    result['objects'] += 1
bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format='GLB')
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def apply_material(self, input_path: str, output_path: str, textures: dict) -> dict:
        """Applica texture PBR a una mesh."""
        albedo = textures.get('albedo', '')
        normal = textures.get('normal', '')
        roughness = textures.get('roughness', '')
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    mat = bpy.data.materials.new(name='SigmaPBR')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = nodes.get('Principled BSDF')
    if r"{albedo}":
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(r"{albedo}")
        links.new(tex.outputs['Color'], principled.inputs['Base Color'])
    if r"{normal}":
        nmap = nodes.new('ShaderNodeNormalMap')
        tex_n = nodes.new('ShaderNodeTexImage')
        tex_n.image = bpy.data.images.load(r"{normal}")
        tex_n.image.colorspace_settings.name = 'Non-Color'
        links.new(tex_n.outputs['Color'], nmap.inputs['Color'])
        links.new(nmap.outputs['Normal'], principled.inputs['Normal'])
    if r"{roughness}":
        tex_r = nodes.new('ShaderNodeTexImage')
        tex_r.image = bpy.data.images.load(r"{roughness}")
        tex_r.image.colorspace_settings.name = 'Non-Color'
        links.new(tex_r.outputs['Color'], principled.inputs['Roughness'])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format='GLB')
result = {{'status': 'ok', 'material': 'SigmaPBR'}}
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def render(self, input_path: str, output_path: str, engine: str = 'CYCLES',
                     resolution: tuple = (1920, 1080), samples: int = 128,
                     transparent: bool = False) -> dict:
        """Renderizza la scena con Cycles o Eevee, inquadrando automaticamente il soggetto."""
        w, h = resolution
        engine = (engine or 'CYCLES').upper()
        if engine not in ('CYCLES', 'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            engine = 'CYCLES'
        transparent = bool(transparent)
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
scene = bpy.context.scene
scene.render.engine = '{engine}'
scene.render.resolution_x = {w}
scene.render.resolution_y = {h}
if '{engine}' == 'CYCLES':
    scene.cycles.samples = {samples}
    scene.cycles.use_denoising = True
# Inquadratura calcolata sul bounding box: una camera fissa taglierebbe fuori
# qualunque mesh non normalizzata alla scala unitaria.
import mathutils
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if meshes:
    corners = [o.matrix_world @ mathutils.Vector(c) for o in meshes for c in o.bound_box]
    min_v = mathutils.Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    max_v = mathutils.Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
else:
    min_v = mathutils.Vector((-1, -1, -1))
    max_v = mathutils.Vector((1, 1, 1))
center = (min_v + max_v) / 2
radius = max((max_v - min_v).length / 2, 0.001)
dist = radius * 3.2

bpy.ops.object.camera_add(location=(center.x + dist * 0.7, center.y - dist * 0.9, center.z + dist * 0.55))
cam = bpy.context.object
cam.data.lens = 50
direction = center - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

# Three-point light scalata sul soggetto
bpy.ops.object.light_add(type='AREA', location=(center.x + dist, center.y - dist, center.z + dist))
key = bpy.context.object
key.data.energy = 800 * radius * radius + 200
key.data.size = radius * 2
bpy.ops.object.light_add(type='AREA', location=(center.x - dist, center.y - dist * 0.6, center.z + radius))
fill = bpy.context.object
fill.data.energy = 250 * radius * radius + 60
fill.data.size = radius * 3
bpy.ops.object.light_add(type='SUN', location=(center.x, center.y + dist, center.z + dist))
bpy.context.object.data.energy = 2

world = bpy.data.worlds.new(name='SigmaWorld')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.02, 0.02, 0.03, 1)
scene.world = world
scene.render.film_transparent = {transparent}
scene.render.filepath = r"{output_path}"
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
bpy.ops.render.render(write_still=True)
result = {{'status': 'ok', 'engine': '{engine}', 'resolution': [{w}, {h}], 'samples': {samples},
          'bounds': [list(min_v), list(max_v)]}}
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)

    async def export(self, input_path: str, output_path: str, format: str = 'glb') -> dict:
        """Esporta mesh in vari formati."""
        if format in ('glb', 'gltf'):
            export_op = f'bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format="GLB")'
        elif format == 'fbx':
            export_op = f'bpy.ops.export_scene.fbx(filepath=r"{output_path}")'
        elif format == 'obj':
            export_op = f'bpy.ops.wm.obj_export(filepath=r"{output_path}")'
        elif format == 'stl':
            export_op = f'bpy.ops.export_mesh.stl(filepath=r"{output_path}")'
        else:
            export_op = f'bpy.ops.export_scene.gltf(filepath=r"{output_path}", export_format="GLB")'
        
        script = f'''
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
{self._import_snippet(input_path)}
{export_op}
result = {{'status': 'ok', 'format': '{format}'}}
print('SIGMA_RESULT:' + json.dumps(result))
'''
        return await self._run_script(script)
    
    async def _run_script(self, script: str) -> dict:
        """Esegue script Python in Blender headless e parsa il risultato."""
        if not self.available:
            return {'status': 'error', 'error': 'Blender non trovato. Script saltato.'}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name
        
        try:
            proc = await asyncio.create_subprocess_exec(
                self.blender_path, '--background', '--python', script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            output = stdout.decode('utf-8', errors='replace')
            
            # Parse result from output
            for line in output.split('\n'):
                if line.startswith('SIGMA_RESULT:'):
                    return json.loads(line[13:])
            
            return {'status': 'ok', 'output': output[-500:] if output else ''}
        except asyncio.TimeoutError:
            return {'status': 'error', 'error': 'Blender timeout (300s)'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
        finally:
            Path(script_path).unlink(missing_ok=True)
