"""Motore di esecuzione della pipeline creativa a nodi.

Un DAG di nodi (`prompt → image_generate → image_to_3d → mesh_cleanup → render`)
viene ordinato topologicamente ed eseguito nodo per nodo. Ogni nodo produce
output tipizzati che diventano input dei successivi; ogni asset generato resta
collegato ai suoi genitori nell'asset graph.
"""

from typing import Dict

from core.creative.asset_graph import AssetGraph, Asset
from core.creative.model_router import ModelRouter
from core.creative.params import normalize_params
from core.creative.three_d.blender_bridge import BlenderBridge
from core.logger import get_logger

log = get_logger("creative_pipeline_engine")


class CreativeNode:
    """Nodo nella pipeline creativa visuale."""
    def __init__(self, node_id: str, node_type: str, params: dict, inputs: dict):
        self.node_id = node_id
        self.node_type = node_type
        self.params = params
        self.inputs = inputs   # {port_name: {source_node_id, source_port}}
        self.outputs = {}  # {port_name: value}


class CreativePipelineEngine:
    """Esegue DAG di nodi creativi."""

    def __init__(self, asset_graph: AssetGraph, model_router: ModelRouter, blender_bridge: BlenderBridge):
        self.asset_graph = asset_graph
        self.model_router = model_router
        self.blender_bridge = blender_bridge

        from core.creative.generators import ImageGenerator
        from core.creative.editors import ImageEditor
        from core.creative.three_d import ModelGenerator3D
        from core.creative.three_d.render_service import SceneRenderer
        from core.creative.mesh import MeshProcessor
        from core.creative.materials import TextureGenerator, MaterialSystem
        from core.creative.video import VideoGenerator
        from core.creative.agents.vision_agent import VisionAgent

        self.image_gen = ImageGenerator(model_router, asset_graph)
        self.image_ed = ImageEditor(model_router, asset_graph, self.image_gen)
        self.model_gen = ModelGenerator3D(model_router, asset_graph, self.image_gen)
        self.mesh_proc = MeshProcessor(asset_graph, blender_bridge)
        self.tex_gen = TextureGenerator(model_router, asset_graph, self.image_gen)
        self.mat_sys = MaterialSystem(asset_graph, blender_bridge)
        self.renderer = SceneRenderer(asset_graph, blender_bridge)
        self.video_gen = VideoGenerator(model_router, asset_graph, self.image_gen)
        self.vision = VisionAgent(asset_graph, model_router.get_config())

        self._node_executors = {}
        self._register_executors()

    def _register_executors(self):
        """Registra gli executor per ogni tipo di nodo."""
        self._node_executors = {
            'prompt': self._exec_prompt,
            'asset_input': self._exec_asset_input,
            'image_generate': self._exec_image_generate,
            'image_to_image': self._exec_image_to_image,
            'image_edit': self._exec_image_edit,
            'instruct_edit': self._exec_instruct_edit,
            'bg_remove': self._exec_bg_remove,
            'bg_replace': self._exec_bg_replace,
            'segment': self._exec_segment,
            'relight': self._exec_relight,
            'vision_analyze': self._exec_vision_analyze,
            'quality_gate': self._exec_quality_gate,
            'text_to_video': self._exec_text_to_video,
            'image_to_video': self._exec_image_to_video,
            'upscale': self._exec_upscale,
            'image_to_3d': self._exec_image_to_3d,
            'text_to_3d': self._exec_text_to_3d,
            'multiview_to_3d': self._exec_multiview_to_3d,
            'mesh_cleanup': self._exec_mesh_cleanup,
            'decimate': self._exec_decimate,
            'uv_unwrap': self._exec_uv_unwrap,
            'texture_gen': self._exec_texture_gen,
            'material': self._exec_material,
            'render': self._exec_render,
            'export': self._exec_export,
        }

    @property
    def node_types(self) -> list:
        return sorted(self._node_executors.keys())

    # ------------------------------------------------------------------
    # Esecuzione
    # ------------------------------------------------------------------

    async def execute_pipeline(self, pipeline_def: dict, progress_callback=None) -> list:
        """Esegue un'intera pipeline DAG.

        pipeline_def = {
            'nodes': [{node_id, node_type, params}],
            'connections': [{from_node, from_port, to_node, to_port}]
        }
        Ritorna gli asset prodotti dai nodi foglia (nessun consumatore a valle).
        """
        nodes_def = pipeline_def.get('nodes', [])
        connections = pipeline_def.get('connections', [])
        if not nodes_def:
            raise ValueError("Pipeline vuota: aggiungi almeno un nodo")

        nodes: Dict[str, CreativeNode] = {}
        for nd in nodes_def:
            node_id = nd.get('node_id') or nd.get('id')
            node_type = nd.get('node_type') or nd.get('type')
            if not node_id or not node_type:
                raise ValueError(f"Nodo senza node_id/node_type: {nd}")
            if node_type not in self._node_executors:
                raise ValueError(f"Tipo nodo sconosciuto: {node_type}")
            inputs = {}
            for conn in connections:
                if conn.get('to_node') == node_id:
                    inputs[conn.get('to_port', 'input')] = {
                        'source_node_id': conn.get('from_node'),
                        'source_port': conn.get('from_port', 'output'),
                    }
            nodes[node_id] = CreativeNode(node_id, node_type, nd.get('params', {}) or {}, inputs)

        # Ordinamento topologico (Kahn)
        in_degree = {nid: 0 for nid in nodes}
        adj = {nid: [] for nid in nodes}
        for nid, node in nodes.items():
            for _port, source in node.inputs.items():
                src_id = source['source_node_id']
                if src_id not in nodes:
                    raise ValueError(f"Connessione verso '{nid}' da nodo inesistente '{src_id}'")
                adj[src_id].append(nid)
                in_degree[nid] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        sorted_nodes = []
        while queue:
            curr = queue.pop(0)
            sorted_nodes.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(nodes):
            raise ValueError("Ciclo rilevato nella pipeline")

        has_consumer = {nid: bool(adj[nid]) for nid in nodes}
        produced = []
        total = len(sorted_nodes)

        for i, nid in enumerate(sorted_nodes):
            node = nodes[nid]
            resolved_inputs = {}
            for port, source in node.inputs.items():
                src_node = nodes[source['source_node_id']]
                resolved_inputs[port] = src_node.outputs.get(source['source_port'])

            if progress_callback:
                progress_callback({
                    "status": "executing", "node_id": nid, "node_type": node.node_type,
                    "progress": int((i / total) * 100), "step": i + 1, "total": total,
                })

            try:
                out = await self.execute_node(node, resolved_inputs)
            except Exception as e:
                log.error(f"Nodo {nid} ({node.node_type}) fallito: {e}")
                if progress_callback:
                    progress_callback({"status": "error", "node_id": nid,
                                       "node_type": node.node_type, "error": str(e)})
                raise RuntimeError(f"Nodo '{nid}' ({node.node_type}): {e}") from e

            node.outputs = out or {}
            if progress_callback:
                asset = node.outputs.get('asset')
                progress_callback({
                    "status": "node_complete", "node_id": nid, "node_type": node.node_type,
                    "progress": int(((i + 1) / total) * 100),
                    "asset": asset.to_dict() if isinstance(asset, Asset) else None,
                })

            asset = node.outputs.get('asset')
            if isinstance(asset, Asset) and not has_consumer[nid]:
                produced.append(asset)

        if progress_callback:
            progress_callback({"status": "complete", "progress": 100})

        return produced

    async def execute_node(self, node: CreativeNode, inputs: dict) -> dict:
        """Esegue un singolo nodo."""
        executor = self._node_executors.get(node.node_type)
        if not executor:
            raise ValueError(f"Tipo nodo sconosciuto: {node.node_type}")
        return await executor(node, inputs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _asset_id(value, label: str) -> str:
        """Estrae un asset_id da una porta che può portare id, dict o Asset."""
        if isinstance(value, Asset):
            return value.asset_id
        if isinstance(value, dict):
            return value.get('asset_id') or value.get('id')
        if isinstance(value, str) and value:
            return value
        raise ValueError(f"Input '{label}' mancante o non collegato")

    @staticmethod
    def _result(asset: Asset) -> dict:
        return {'asset_id': asset.asset_id, 'asset': asset, 'image': asset.asset_id, 'mesh': asset.asset_id}

    def _text_of(self, inputs: dict, node: CreativeNode, key: str = 'prompt') -> str:
        value = inputs.get(key)
        if isinstance(value, dict):
            value = value.get('text')
        return value or node.params.get(key, '')

    # ------------------------------------------------------------------
    # Executor dei nodi
    # ------------------------------------------------------------------

    async def _exec_prompt(self, node: CreativeNode, inputs: dict) -> dict:
        return {'text': node.params.get('prompt', ''), 'output': node.params.get('prompt', '')}

    async def _exec_asset_input(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = node.params.get('asset_id')
        asset = self.asset_graph.get_asset(asset_id) if asset_id else None
        if not asset:
            raise ValueError(f"Asset '{asset_id}' non trovato nel vault")
        return self._result(asset)

    async def _exec_image_generate(self, node: CreativeNode, inputs: dict) -> dict:
        params = normalize_params(node.params)
        prompt = self._text_of(inputs, node)
        params.pop('prompt', None)
        asset = await self.image_gen.text_to_image(prompt, **params)
        return self._result(asset)

    async def _exec_image_to_image(self, node: CreativeNode, inputs: dict) -> dict:
        params = normalize_params(node.params)
        prompt = self._text_of(inputs, node)
        params.pop('prompt', None)
        asset_id = self._asset_id(inputs.get('image'), 'image')
        asset = await self.image_gen.image_to_image(asset_id, prompt, **params)
        return self._result(asset)

    async def _exec_image_edit(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        params = normalize_params(node.params)
        operation = params.pop('operation', 'inpaint')
        prompt = self._text_of(inputs, node)

        if operation == 'inpaint':
            asset = await self.image_ed.inpaint(asset_id, params.pop('mask_data', ''), prompt, **params)
        elif operation == 'outpaint':
            asset = await self.image_ed.outpaint(
                asset_id, params.pop('direction', 'all'), params.pop('pixels', 128), prompt, **params
            )
        elif operation == 'replace_object':
            asset = await self.image_ed.replace_object(asset_id, params.pop('mask_data', ''), prompt, **params)
        else:
            asset = await self.image_ed.style_transfer(
                asset_id, params.pop('style_prompt', prompt), params.pop('strength', 0.7)
            )
        return self._result(asset)

    async def _exec_instruct_edit(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        params = normalize_params(node.params)
        instruction = self._text_of(inputs, node, 'instruction') or params.pop('prompt', '')
        params.pop('instruction', None)
        params.pop('prompt', None)
        return self._result(await self.image_gen.instruct_edit(asset_id, instruction, **params))

    async def _exec_bg_remove(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        return self._result(await self.image_ed.remove_background(asset_id))

    async def _exec_bg_replace(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        params = normalize_params(node.params)
        prompt = self._text_of(inputs, node)
        params.pop('prompt', None)
        return self._result(await self.image_ed.replace_background(asset_id, prompt, **params))

    async def _exec_segment(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        asset = await self.image_ed.segment(asset_id, node.params.get('prompt', ''))
        return {'asset_id': asset.asset_id, 'asset': asset, 'mask': asset.asset_id, 'image': asset.asset_id}

    async def _exec_vision_analyze(self, node: CreativeNode, inputs: dict) -> dict:
        """Analisi VLM: passa oltre l'asset e aggiunge la lettura come testo."""
        asset_id = self._asset_id(inputs.get('image'), 'image')
        analysis = await self.vision.analyze(asset_id)
        asset = self.asset_graph.get_asset(asset_id)
        return {'asset_id': asset_id, 'asset': asset, 'image': asset_id,
                'analysis': analysis, 'text': analysis.get('subject') or analysis.get('raw', '')}

    async def _exec_quality_gate(self, node: CreativeNode, inputs: dict) -> dict:
        """Quality Agent: blocca la pipeline se l'output non regge la soglia.

        È il punto in cui un errore diventa visibile subito invece di propagarsi
        fino al render finale.
        """
        asset_id = self._asset_id(inputs.get('image'), 'image')
        intent = self._text_of(inputs, node, 'intent') or node.params.get('intent', '')
        threshold = float(node.params.get('threshold', 0.6))

        verdict = await self.vision.score(asset_id, intent or 'output creativo di qualità')
        score = verdict.get('quality_score')
        if score is not None and float(score) < threshold and node.params.get('strict', True):
            issues = ", ".join(verdict.get('issues') or []) or 'nessun dettaglio'
            raise RuntimeError(
                f"Quality gate non superato: score {float(score):.2f} < {threshold} ({issues})"
            )
        asset = self.asset_graph.get_asset(asset_id)
        return {'asset_id': asset_id, 'asset': asset, 'image': asset_id,
                'quality_score': score, 'verdict': verdict}

    async def _exec_text_to_video(self, node: CreativeNode, inputs: dict) -> dict:
        params = normalize_params(node.params)
        prompt = self._text_of(inputs, node)
        params.pop('prompt', None)
        return self._result(await self.video_gen.text_to_video(prompt, **params))

    async def _exec_image_to_video(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        params = normalize_params(node.params)
        prompt = self._text_of(inputs, node)
        params.pop('prompt', None)
        return self._result(await self.video_gen.image_to_video(asset_id, prompt, **params))

    async def _exec_relight(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        params = normalize_params(node.params)
        asset = await self.image_ed.relight(
            asset_id, params.get('light_direction', 'front'), params.get('intensity', 1.0)
        )
        return self._result(asset)

    async def _exec_upscale(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        params = normalize_params(node.params)
        asset = await self.image_gen.upscale(asset_id, **params)
        return self._result(asset)

    async def _exec_image_to_3d(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('image'), 'image')
        asset = await self.model_gen.image_to_3d(asset_id, **normalize_params(node.params))
        return self._result(asset)

    async def _exec_text_to_3d(self, node: CreativeNode, inputs: dict) -> dict:
        prompt = self._text_of(inputs, node)
        params = normalize_params(node.params)
        params.pop('prompt', None)
        return self._result(await self.model_gen.text_to_3d(prompt, **params))

    async def _exec_multiview_to_3d(self, node: CreativeNode, inputs: dict) -> dict:
        asset_ids = [self._asset_id(v, port) for port, v in sorted(inputs.items()) if v is not None]
        asset_ids += node.params.get('asset_ids', [])
        params = {k: v for k, v in normalize_params(node.params).items() if k != 'asset_ids'}
        return self._result(await self.model_gen.multiview_to_3d(asset_ids, **params))

    async def _exec_mesh_cleanup(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('mesh'), 'mesh')
        return self._result(await self.mesh_proc.cleanup(asset_id, node.params))

    async def _exec_decimate(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('mesh'), 'mesh')
        return self._result(await self.mesh_proc.decimate(asset_id, node.params.get('ratio', 0.5)))

    async def _exec_uv_unwrap(self, node: CreativeNode, inputs: dict) -> dict:
        asset_id = self._asset_id(inputs.get('mesh'), 'mesh')
        method = node.params.get('method', 'smart_project')
        return self._result(await self.mesh_proc.uv_unwrap(asset_id, method))

    async def _exec_texture_gen(self, node: CreativeNode, inputs: dict) -> dict:
        params = normalize_params(node.params)
        params.pop('prompt', None)
        image_input = inputs.get('image')
        if image_input is not None:
            asset = await self.tex_gen.generate_from_image(self._asset_id(image_input, 'image'), **params)
        else:
            asset = await self.tex_gen.generate_pbr(self._text_of(inputs, node), **params)
        return {'asset_id': asset.asset_id, 'asset': asset, 'material': asset.asset_id}

    async def _exec_material(self, node: CreativeNode, inputs: dict) -> dict:
        mesh_input = inputs.get('mesh')
        mat_input = inputs.get('material')

        mat_id = None
        if mat_input is not None:
            mat_id = self._asset_id(mat_input, 'material')
        elif node.params.get('textures'):
            mat_id = (await self.mat_sys.create_pbr_material(
                node.params['textures'], node.params.get('name', 'SigmaPBR')
            )).asset_id
        if not mat_id:
            raise ValueError("Nodo material: collega una texture o indica 'textures' nei parametri")

        if mesh_input is None:
            asset = self.asset_graph.get_asset(mat_id)
            return {'asset_id': mat_id, 'asset': asset, 'material': mat_id}

        asset = await self.mat_sys.apply_to_mesh(self._asset_id(mesh_input, 'mesh'), mat_id)
        return self._result(asset)

    async def _exec_render(self, node: CreativeNode, inputs: dict) -> dict:
        source = inputs.get('scene') or inputs.get('mesh')
        asset_id = self._asset_id(source, 'scene')
        return self._result(await self.renderer.render(asset_id, normalize_params(node.params)))

    async def _exec_export(self, node: CreativeNode, inputs: dict) -> dict:
        source = inputs.get('asset') or inputs.get('mesh') or inputs.get('image')
        asset_id = self._asset_id(source, 'asset')
        fmt = node.params.get('format')
        asset = self.asset_graph.get_asset(asset_id)

        # Un export verso un formato diverso passa da Blender; altrimenti l'asset
        # è già scaricabile dal vault e il nodo si limita a marcarlo come output.
        if fmt and fmt != 'keep':
            asset = await self.mesh_proc.export(asset_id, fmt)
        return {'asset_id': asset.asset_id, 'asset': asset, 'status': 'exported',
                'files': asset.to_dict().get('file_urls', {})}
