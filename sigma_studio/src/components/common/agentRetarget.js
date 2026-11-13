import * as THREE from 'three';

const bindingName = node => THREE.PropertyBinding.sanitizeNodeName(node.name);
const boneKey = name => THREE.PropertyBinding.sanitizeNodeName(name);
const rotationOf = node => new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().extractRotation(node.matrixWorld));

export function prepareAgentAnimationLibrary(gltf) {
  const clips = gltf.animations.map(clip => new THREE.AnimationClip(clip.name, clip.duration,
    clip.tracks.filter(track => track.name.endsWith('.quaternion') || track.name === 'DEF-hips.position').map(track => track.clone())));
  return { scene: gltf.scene, clips };
}

export function retargetAgentClips(library, targetBody) {
  const source = library.scene.clone(true);
  const sourceBones = new Map();
  const targetBones = [];
  source.updateMatrixWorld(true);
  targetBody.updateMatrixWorld(true);
  source.traverse(node => { if (node.isBone) sourceBones.set(bindingName(node), node); });
  targetBody.traverse(node => { if (node.isBone && sourceBones.has(bindingName(node))) targetBones.push(node); });
  if (!targetBones.length) return [];
  const targetRest = new Map(targetBones.map(node => [bindingName(node), rotationOf(node)]));
  const sourceBind = new Map([...sourceBones].map(([name, node]) => [name, rotationOf(node)]));
  const targetParentRest = new Map(targetBones.filter(node => node.parent).map(node => [node.parent, rotationOf(node.parent)]));
  const mixer = new THREE.AnimationMixer(source);
  const idle = library.clips.find(clip => clip.name === 'Idle_Loop');
  const targetArm = targetBones.find(node => bindingName(node) === boneKey('DEF-upper_arm.L'));
  const targetElbow = targetBones.find(node => bindingName(node) === boneKey('DEF-forearm.L'));
  const armDirection = targetArm && targetElbow
    ? targetElbow.getWorldPosition(new THREE.Vector3()).sub(targetArm.getWorldPosition(new THREE.Vector3())).normalize() : new THREE.Vector3(1, 0, 0);
  const relaxedBind = armDirection.y < -0.65;
  if (relaxedBind && idle) { mixer.clipAction(idle).play(); mixer.update(0); source.updateMatrixWorld(true); }
  // Il riferimento anatomico è la posa neutra, non la T-pose del manichino:
  // applicare due volte l'abbassamento delle braccia strappava giacca e spalle.
  const reference = relaxedBind && idle
    ? new Map([...sourceBones].map(([name, node]) => [name, rotationOf(node)])) : sourceBind;
  const inverseReference = new Map([...reference].map(([name, rotation]) => [name, rotation.clone().invert()]));
  const sourceHip = sourceBones.get('DEF-hips');
  const sourceHipPosition = sourceHip?.position.clone();
  const targetHip = targetBones.find(node => bindingName(node) === 'DEF-hips');
  const targetHipPosition = targetHip?.position.clone();
  const segmentLength = (bones, a, b) => {
    const first = bones.get(boneKey(a)), second = bones.get(boneKey(b));
    return first && second ? first.getWorldPosition(new THREE.Vector3()).distanceTo(second.getWorldPosition(new THREE.Vector3())) : 1;
  };
  const targetMap = new Map(targetBones.map(node => [bindingName(node), node]));
  const translationScale = segmentLength(targetMap, 'DEF-thigh.L', 'DEF-foot.L') / segmentLength(sourceBones, 'DEF-thigh.L', 'DEF-foot.L');
  const desired = new Map();
  const parentInverse = new THREE.Quaternion();
  const result = library.clips.map(clip => {
    mixer.stopAllAction();
    const action = mixer.clipAction(clip).reset().play();
    const count = Math.max(2, Math.ceil(clip.duration * 30) + 1);
    const times = Float32Array.from({ length: count }, (_, index) => Math.min(clip.duration, index * clip.duration / (count - 1)));
    const values = new Map(targetBones.map(node => [bindingName(node), new Float32Array(count * 4)]));
    const hipValues = new Float32Array(count * 3);
    let previous = 0;
    for (let index = 0; index < count; index++) {
      // I one-shot devono includere l'ultimo fotogramma, senza riavvolgere.
      action.setLoop(THREE.LoopOnce, 1); action.clampWhenFinished = true;
      mixer.update(times[index] - previous);
      previous = times[index];
      source.updateMatrixWorld(true);
      desired.clear();
      for (const target of targetBones) {
        const name = bindingName(target);
        const world = rotationOf(sourceBones.get(name)).multiply(inverseReference.get(name)).multiply(targetRest.get(name)).normalize();
        desired.set(target, world);
        const parentWorld = desired.get(target.parent) || targetParentRest.get(target.parent);
        const local = parentWorld ? parentInverse.copy(parentWorld).invert().multiply(world) : world;
        local.normalize().toArray(values.get(name), index * 4);
      }
      if (sourceHip && targetHip) sourceHip.position.clone().sub(sourceHipPosition).multiplyScalar(translationScale).add(targetHipPosition).toArray(hipValues, index * 3);
    }
    const tracks = targetBones.map(node => new THREE.QuaternionKeyframeTrack(`${bindingName(node)}.quaternion`, times, values.get(bindingName(node))));
    if (sourceHip && targetHip) tracks.push(new THREE.VectorKeyframeTrack('DEF-hips.position', times, hipValues));
    return new THREE.AnimationClip(clip.name, clip.duration, tracks);
  });
  mixer.stopAllAction(); mixer.uncacheRoot(source);
  return result;
}
