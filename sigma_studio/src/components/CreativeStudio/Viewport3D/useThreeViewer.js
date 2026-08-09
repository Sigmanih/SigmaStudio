import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const ENVIRONMENTS = {
  Studio: { key: 0xffffff, keyI: 3.0, fill: 0xbcd4ff, fillI: 1.2, bg: 0x0a0a12 },
  Cyberpunk: { key: 0xff3cac, keyI: 3.4, fill: 0x00d2ff, fillI: 2.0, bg: 0x05000f },
  Sunset: { key: 0xffb36b, keyI: 3.2, fill: 0x4a6bff, fillI: 1.0, bg: 0x140a08 },
  Soft: { key: 0xffffff, keyI: 1.6, fill: 0xffffff, fillI: 1.2, bg: 0x14141c },
};

/**
 * Viewer three.js per gli asset 3D del vault.
 *
 * Carica il GLB reale servito da /data/creative/assets/... e ne ricava le
 * statistiche di geometria dalla scena caricata (non da valori inventati).
 */
export function useThreeViewer({ url, wireframe, environment = 'Studio' }) {
  const containerRef = useRef(null);
  const stateRef = useRef(null);
  const [status, setStatus] = useState('idle');   // idle | loading | ready | error
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);

  // Setup una tantum: scena, camera, controlli, loop di render.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.01, 1000);
    camera.position.set(2, 1.6, 2.8);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    const key = new THREE.DirectionalLight(0xffffff, 3);
    key.position.set(3, 4, 2);
    const fill = new THREE.DirectionalLight(0xbcd4ff, 1.2);
    fill.position.set(-3, 1, -2);
    const ambient = new THREE.AmbientLight(0xffffff, 0.35);
    const grid = new THREE.GridHelper(10, 20, 0x2a2a3a, 0x1a1a24);
    scene.add(key, fill, ambient, grid);

    let frame;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      if (!container.clientWidth || !container.clientHeight) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    const observer = new ResizeObserver(onResize);
    observer.observe(container);

    stateRef.current = { renderer, scene, camera, controls, key, fill, grid, model: null };

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
      stateRef.current = null;
    };
  }, []);

  // Caricamento del modello quando cambia l'URL.
  useEffect(() => {
    const state = stateRef.current;
    if (!state) return undefined;

    if (state.model) {
      state.scene.remove(state.model);
      state.model.traverse(o => {
        o.geometry?.dispose?.();
        if (Array.isArray(o.material)) o.material.forEach(m => m.dispose?.());
        else o.material?.dispose?.();
      });
      state.model = null;
    }
    setStats(null);

    if (!url) { setStatus('idle'); return undefined; }

    setStatus('loading');
    setError(null);
    let cancelled = false;

    new GLTFLoader().load(
      url,
      (gltf) => {
        if (cancelled || !stateRef.current) return;
        const { scene, camera, controls } = stateRef.current;
        const model = gltf.scene;

        // Normalizza scala e posizione: i generatori 3D non concordano su unità
        // né su origine, senza questo passaggio metà dei modelli è fuori campo.
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        model.scale.setScalar(1.6 / maxDim);
        model.position.sub(center.multiplyScalar(1.6 / maxDim));

        let vertices = 0, triangles = 0, meshes = 0;
        const materials = new Set();
        model.traverse(o => {
          if (!o.isMesh) return;
          meshes += 1;
          const g = o.geometry;
          vertices += g.attributes.position?.count || 0;
          triangles += g.index ? g.index.count / 3 : (g.attributes.position?.count || 0) / 3;
          (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => m && materials.add(m.uuid));
        });

        scene.add(model);
        stateRef.current.model = model;
        camera.position.set(2, 1.4, 2.6);
        controls.target.set(0, 0, 0);
        controls.update();

        setStats({
          vertices,
          triangles: Math.round(triangles),
          meshes,
          materials: materials.size,
          hasUV: !!model.getObjectByProperty('isMesh', true)?.geometry?.attributes?.uv,
        });
        setStatus('ready');
      },
      undefined,
      (err) => {
        if (cancelled) return;
        setError(err?.message || 'Modello non caricabile');
        setStatus('error');
      },
    );

    return () => { cancelled = true; };
  }, [url]);

  // Wireframe e ambiente luci.
  useEffect(() => {
    const state = stateRef.current;
    if (!state?.model) return;
    state.model.traverse(o => {
      if (!o.isMesh) return;
      (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { if (m) m.wireframe = !!wireframe; });
    });
  }, [wireframe, status]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    const env = ENVIRONMENTS[environment] || ENVIRONMENTS.Studio;
    state.key.color.setHex(env.key);
    state.key.intensity = env.keyI;
    state.fill.color.setHex(env.fill);
    state.fill.intensity = env.fillI;
  }, [environment]);

  return { containerRef, status, error, stats, environments: Object.keys(ENVIRONMENTS) };
}
