// Controllo delle vere ossa e clip GLB senza renderer, immagini o GPU.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from '../../sigma_studio/node_modules/three/build/three.module.js';
import { prepareAgentAnimationLibrary, retargetAgentClips } from '../../sigma_studio/src/components/common/agentRetarget.js';

function load(file) {
  const bytes = fs.readFileSync(file);
  assert.equal(bytes.readUInt32LE(0), 0x46546c67);
  const length = bytes.readUInt32LE(12);
  const document = JSON.parse(bytes.subarray(20, 20 + length).toString());
  const binary = bytes.subarray(28 + length);
  const components = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
  const formats = { 5121: [1, 'getUint8'], 5123: [2, 'getUint16'], 5125: [4, 'getUint32'], 5126: [4, 'getFloat32'] };
  const accessor = index => {
    const item = document.accessors[index], view = document.bufferViews[item.bufferView];
    const [size, method] = formats[item.componentType], width = components[item.type];
    const data = new DataView(binary.buffer, binary.byteOffset, binary.length);
    const offset = (view.byteOffset || 0) + (item.byteOffset || 0);
    return Float32Array.from({ length: item.count * width }, (_, i) => data[method](offset + Math.floor(i / width) * (view.byteStride || size * width) + (i % width) * size, true));
  };
  const joints = new Set((document.skins || []).flatMap(skin => skin.joints));
  const nodes = document.nodes.map((node, index) => {
    const result = joints.has(index) ? new THREE.Bone() : new THREE.Object3D();
    result.name = THREE.PropertyBinding.sanitizeNodeName(node.name || `node_${index}`);
    if (node.matrix) new THREE.Matrix4().fromArray(node.matrix).decompose(result.position, result.quaternion, result.scale);
    else {
      if (node.translation) result.position.fromArray(node.translation);
      if (node.rotation) result.quaternion.fromArray(node.rotation);
      if (node.scale) result.scale.fromArray(node.scale);
    }
    return result;
  });
  document.nodes.forEach((node, index) => (node.children || []).forEach(child => nodes[index].add(nodes[child])));
  const scene = new THREE.Group();
  document.scenes[document.scene || 0].nodes.forEach(index => scene.add(nodes[index]));
  scene.updateMatrixWorld(true);
  const animations = (document.animations || []).map(animation => new THREE.AnimationClip(animation.name, -1, animation.channels.map(channel => {
    const sampler = animation.samplers[channel.sampler];
    const name = THREE.PropertyBinding.sanitizeNodeName(document.nodes[channel.target.node].name);
    const field = { translation: 'position', rotation: 'quaternion', scale: 'scale' }[channel.target.path];
    const Track = field === 'quaternion' ? THREE.QuaternionKeyframeTrack : THREE.VectorKeyframeTrack;
    return new Track(`${name}.${field}`, accessor(sampler.input), accessor(sampler.output), sampler.interpolation === 'STEP' ? THREE.InterpolateDiscrete : THREE.InterpolateLinear);
  })));
  return { scene, animations, document, accessor, nodes, bytes, binary };
}

const revision = path.resolve(process.argv[2] || 'works/creative/agenti_3d/revisione_rig_v4/roles');
const source = load('sigma_studio/public/models/animazioni_agenti.glb');
const library = prepareAgentAnimationLibrary(source);
const repair = process.argv.includes('--ripara-membrane');
let checked = 0;
for (const role of fs.readdirSync(revision)) {
  const file = path.join(revision, role, 'personaggio.glb');
  if (!fs.existsSync(file)) continue;
  const target = load(file);
  const bones = new Map(); target.scene.traverse(node => { if (node.isBone) bones.set(node.name, node); });
  const reference = new Map([...bones].map(([name, bone]) => [name, bone.getWorldQuaternion(new THREE.Quaternion())]));
  const lengths = new Map([...bones].filter(([name, bone]) => name !== 'DEF-hips' && bone.parent?.isBone).map(([name, bone]) => [name, bone.position.length()]));
  const clips = retargetAgentClips(library, target.scene);
  assert.equal(clips.length, 9, `${role}: clip mancanti`);
  const mixer = new THREE.AnimationMixer(target.scene);
  let maximumStretch = 1;
  let extremeEdges = 0;
  let maximumExcess = 0;
  const damagedTriangles = new Set();
  const skin = target.document.skins[0];
  const inverses = target.accessor(skin.inverseBindMatrices);
  const skinMatrices = skin.joints.map((node, index) => ({ node: target.nodes[node], inverse: new THREE.Matrix4().fromArray(inverses, index * 16), matrix: new THREE.Matrix4() }));
  const primitive = target.document.meshes[0].primitives[0];
  const positions = target.accessor(primitive.attributes.POSITION);
  const skinJoints = target.accessor(primitive.attributes.JOINTS_0);
  const skinWeights = target.accessor(primitive.attributes.WEIGHTS_0);
  const indices = target.accessor(primitive.indices);
  for (let index = 0; index < positions.length / 3; index++) {
    let sum = 0;
    for (let component = 0; component < 4; component++) {
      const weight = skinWeights[index * 4 + component];
      assert.ok(Number.isFinite(weight) && weight >= 0, `${role}: peso non valido`);
      sum += weight;
      if (weight) assert.ok(skinJoints[index * 4 + component] < skinMatrices.length, `${role}: indice osso non valido`);
    }
    assert.ok(Math.abs(sum - 1) < 0.002, `${role}: pesi non normalizzati`);
  }
  const surface = () => {
    const output = new Float32Array(positions.length);
    for (let vertex = 0; vertex < positions.length / 3; vertex++) {
      const x = positions[vertex * 3], y = positions[vertex * 3 + 1], z = positions[vertex * 3 + 2];
      for (let component = 0; component < 4; component++) {
        const weight = skinWeights[vertex * 4 + component];
        if (!weight) continue;
        const matrix = skinMatrices[skinJoints[vertex * 4 + component]].matrix.elements;
        output[vertex * 3] += (matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]) * weight;
        output[vertex * 3 + 1] += (matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]) * weight;
        output[vertex * 3 + 2] += (matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]) * weight;
      }
      assert.ok(Number.isFinite(output[vertex * 3]) && Number.isFinite(output[vertex * 3 + 1]) && Number.isFinite(output[vertex * 3 + 2]) && Math.hypot(output[vertex * 3], output[vertex * 3 + 1], output[vertex * 3 + 2]) < 5, `${role}: superficie esplosa`);
    }
    return output;
  };
  const edgeLength = (array, a, b) => Math.hypot(array[a * 3] - array[b * 3], array[a * 3 + 1] - array[b * 3 + 1], array[a * 3 + 2] - array[b * 3 + 2]);
  for (const clip of clips) {
    mixer.stopAllAction();
    mixer.clipAction(clip).reset().setLoop(THREE.LoopOnce, 1).play();
    for (let frame = 0; frame <= 12; frame++) {
      mixer.setTime(clip.duration * frame / 12);
      target.scene.updateMatrixWorld(true);
      for (const [name, bone] of bones) {
        assert.ok(Number.isFinite(bone.quaternion.length()) && Math.abs(bone.quaternion.length() - 1) < 0.0001, `${role}/${clip.name}: rotazione invalida ${name}`);
        if (lengths.has(name)) assert.ok(Math.abs(bone.position.length() - lengths.get(name)) < 0.00001, `${role}: articolazione disconnessa ${name}`);
        if (clip.name === 'Idle_Loop' && frame === 0) assert.ok(bone.getWorldQuaternion(new THREE.Quaternion()).angleTo(reference.get(name)) < 0.001, `${role}: posa neutra alterata ${name}`);
      }
      checked++;
      if ([3, 6, 9].includes(frame) && ['Walk_Loop', 'Idle_Talking_Loop', 'Sitting_Idle_Loop', 'Interact'].includes(clip.name)) {
        skinMatrices.forEach(item => item.matrix.multiplyMatrices(item.node.matrixWorld, item.inverse));
        const posed = surface();
        for (let triangle = 0; triangle < indices.length; triangle += 3) {
          if (damagedTriangles.has(triangle)) continue;
          for (let edge = 0; edge < 3; edge++) {
          const a = indices[triangle + edge], b = indices[triangle + (edge + 1) % 3];
          const rest = edgeLength(positions, a, b);
          if (rest < 0.0001) continue;
          const length = edgeLength(posed, a, b);
          const ratio = length / rest;
          maximumStretch = Math.max(maximumStretch, ratio);
          maximumExcess = Math.max(maximumExcess, length - rest);
          if (ratio > 8 && length - rest > 0.04) { extremeEdges++; damagedTriangles.add(triangle); break; }
          }
        }
      }
    }
  }
  mixer.stopAllAction(); mixer.uncacheRoot(target.scene);
  if (damagedTriangles.size && repair) {
    // Le membrane spurie tra superfici indipendenti non devono trascinare
    // lembi di giacca insieme alla mano. Si rimuovono solo i triangoli che
    // esplodono nelle vere clip, mai un'intera fascia anatomica.
    const item = target.document.accessors[primitive.indices];
    const view = target.document.bufferViews[item.bufferView];
    const width = item.componentType === 5125 ? 4 : item.componentType === 5123 ? 2 : 1;
    const data = new DataView(target.binary.buffer, target.binary.byteOffset, target.binary.length);
    const method = { 1: 'setUint8', 2: 'setUint16', 4: 'setUint32' }[width];
    const offset = (view.byteOffset || 0) + (item.byteOffset || 0);
    for (const triangle of damagedTriangles) for (let edge = 1; edge < 3; edge++) data[method](offset + (triangle + edge) * width, indices[triangle], true);
    fs.writeFileSync(file, target.bytes);
  } else assert.equal(damagedTriangles.size, 0, `${role}: membrane stirate da correggere`);
  process.stdout.write(`${role}: 9 clip; deformazione massima ${maximumStretch.toFixed(2)}, allungamento ${(maximumExcess * 100).toFixed(1)} cm, bordi anomali ${extremeEdges}\n`);
}
process.stdout.write(`SIGMA-CHECK ${JSON.stringify({ check: 'agent-animation-rigs', checked, problems: 0 })}\n`);
