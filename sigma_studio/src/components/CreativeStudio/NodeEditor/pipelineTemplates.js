// Pipeline pronte all'uso: i node_type e le porte devono combaciare con
// NODE_CATALOG lato server (core/creative/creative_router.py).

let seq = 0;
const uid = (prefix = 'n') => `${prefix}${Date.now().toString(36)}${(seq++).toString(36)}`;

function build(defs, links) {
  const ids = {};
  const nodes = defs.map(d => {
    const id = uid();
    ids[d.key] = id;
    return { id, type: d.type, x: d.x, y: d.y, params: d.params || {} };
  });
  const connections = links.map(l => ({
    id: uid('c'),
    from: ids[l.from], fromPort: l.fromPort,
    to: ids[l.to], toPort: l.toPort,
  }));
  return { nodes, connections };
}

export const PIPELINE_TEMPLATES = {
  blank: { label: 'Blank Canvas', create: () => ({ nodes: [], connections: [] }) },

  concept: {
    label: 'Concept Art',
    description: 'Prompt → immagine → upscale',
    create: () => build([
      { key: 'p', type: 'prompt', x: 60, y: 140, params: { prompt: 'concept art of a futuristic vehicle' } },
      { key: 'g', type: 'image_generate', x: 340, y: 120, params: { width: 1024, height: 1024, steps: 30, cfg_scale: 7 } },
      { key: 'u', type: 'upscale', x: 640, y: 140, params: { scale: 2 } },
    ], [
      { from: 'p', fromPort: 'text', to: 'g', toPort: 'prompt' },
      { from: 'g', fromPort: 'image', to: 'u', toPort: 'image' },
    ]),
  },

  productShot: {
    label: 'Product Shot',
    description: 'Prompt → immagine → scontorno → relight',
    create: () => build([
      { key: 'p', type: 'prompt', x: 40, y: 160, params: { prompt: 'studio product photo of a ceramic mug' } },
      { key: 'g', type: 'image_generate', x: 300, y: 140, params: { width: 1024, height: 1024 } },
      { key: 'b', type: 'bg_remove', x: 580, y: 100, params: {} },
      { key: 'r', type: 'relight', x: 840, y: 160, params: { light_direction: 'left', intensity: 1.2 } },
    ], [
      { from: 'p', fromPort: 'text', to: 'g', toPort: 'prompt' },
      { from: 'g', fromPort: 'image', to: 'b', toPort: 'image' },
      { from: 'b', fromPort: 'image', to: 'r', toPort: 'image' },
    ]),
  },

  gameAsset: {
    label: 'Game Asset (3D)',
    description: 'Prompt → immagine → 3D → cleanup → decimate → texture → render',
    create: () => build([
      { key: 'p', type: 'prompt', x: 20, y: 200, params: { prompt: 'stylized wooden barrel, game asset' } },
      { key: 'g', type: 'image_generate', x: 250, y: 180, params: { width: 1024, height: 1024 } },
      { key: 'b', type: 'bg_remove', x: 480, y: 180, params: {} },
      { key: 'm', type: 'image_to_3d', x: 700, y: 180, params: {} },
      { key: 'c', type: 'mesh_cleanup', x: 920, y: 120, params: { merge_distance: 0.001 } },
      { key: 'd', type: 'decimate', x: 920, y: 280, params: { ratio: 0.5 } },
      { key: 'r', type: 'render', x: 1160, y: 200, params: { engine: 'cycles', width: 1280, height: 720, samples: 96 } },
    ], [
      { from: 'p', fromPort: 'text', to: 'g', toPort: 'prompt' },
      { from: 'g', fromPort: 'image', to: 'b', toPort: 'image' },
      { from: 'b', fromPort: 'image', to: 'm', toPort: 'image' },
      { from: 'm', fromPort: 'mesh', to: 'c', toPort: 'mesh' },
      { from: 'c', fromPort: 'mesh', to: 'd', toPort: 'mesh' },
      { from: 'd', fromPort: 'mesh', to: 'r', toPort: 'scene' },
    ]),
  },

  materialLab: {
    label: 'Material Lab',
    description: 'Prompt → texture PBR applicata a una mesh del vault',
    create: () => build([
      { key: 'p', type: 'prompt', x: 40, y: 120, params: { prompt: 'weathered oak wood planks' } },
      { key: 't', type: 'texture_gen', x: 300, y: 100, params: { resolution: 1024 } },
      { key: 'a', type: 'asset_input', x: 300, y: 280, params: { asset_id: '' } },
      { key: 'm', type: 'material', x: 600, y: 180, params: {} },
      { key: 'r', type: 'render', x: 860, y: 180, params: { engine: 'cycles', samples: 128 } },
    ], [
      { from: 'p', fromPort: 'text', to: 't', toPort: 'prompt' },
      { from: 't', fromPort: 'material', to: 'm', toPort: 'material' },
      { from: 'a', fromPort: 'mesh', to: 'm', toPort: 'mesh' },
      { from: 'm', fromPort: 'mesh', to: 'r', toPort: 'scene' },
    ]),
  },
};

export const newNodeId = uid;
