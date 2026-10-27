import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { roleInitials } from './roleIcons';

/**
 * CyberSpace3DCanvas — Spaceship Bridge & Command Deck 3D
 * 
 * Un autentico ambiente 3D all'interno di una navicella spaziale (Starship Command Deck):
 * - Ampia vetrata panoramica frontale (Cockpit Viewport) con vista sul cosmo e campo stellare in movimento
 * - Paratie strutturali e archi metallici (Bulkhead Ribs) che sovrastano la plancia con strisce LED
 * - Pavimento metallico con griglia prospettica, ring neon e canaline dati per ogni postazione
 * - Piattaforma tattica centrale (Holo-Table) con globo planetario olografico rotante
 * - Postazioni di comando individuali per ciascun agente con console di bordo, monitor curvi e tastiere laser
 * - Modelli 3D degli agenti in servizio (Ufficiali Mecha con reattore pulsante, visore luminoso e mani digitanti)
 * - Schede degli agenti essenziali (avatar, nome, ruolo) che scalano con la distanza
 * - Volo cinematico fluido della camera alla postazione dell'agente con lerp
 */
// Le GPU del Raspberry Pi (VideoCore/V3D) e i renderer software non reggono
// la plancia completa: lo si scopre prima di creare il renderer, perche'
// l'antialias non si puo' cambiare dopo.
const detectLowEndGpu = () => {
  try {
    const probe = document.createElement('canvas');
    const gl = probe.getContext('webgl2') || probe.getContext('webgl');
    if (!gl) return true;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    const name = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || '') : '';
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return /v3d|videocore|llvmpipe|swiftshader|softpipe|mali-4|adreno \(tm\) 3/i.test(name);
  } catch {
    return false;
  }
};

const prefersReducedMotion = () => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
};

// Testo che si restringe fino a stare nella larghezza della scheda invece di
// uscire dai bordi con i nomi lunghi dei ruoli.
const fitText = (ctx, text, maxWidth, startPx, minPx, weight, family) => {
  let size = startPx;
  ctx.font = `${weight} ${size}px ${family}`;
  while (size > minPx && ctx.measureText(text).width > maxWidth) {
    size -= 2;
    ctx.font = `${weight} ${size}px ${family}`;
  }
  if (ctx.measureText(text).width <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > maxWidth) cut = cut.slice(0, -1);
  return `${cut.trimEnd()}…`;
};

export default function CyberSpace3DCanvas({
  isLight = false,
  roles = [],
  selectedAgentId = '',
  onSelectAgent,
  interactive = true,
  quality = 'auto',
  throttled = false,
  onQualityResolved,
  className = '',
  style = {}
}) {
  const mountRef = useRef(null);
  const [hoveredAgent, setHoveredAgent] = useState(null);

  const rolesRef = useRef(roles);
  rolesRef.current = roles;

  const onSelectAgentRef = useRef(onSelectAgent);
  onSelectAgentRef.current = onSelectAgent;

  const selectedAgentIdRef = useRef(selectedAgentId);
  selectedAgentIdRef.current = selectedAgentId;

  const flyToStationRef = useRef(null);

  const onQualityResolvedRef = useRef(onQualityResolved);
  onQualityResolvedRef.current = onQualityResolved;

  // Letto dal loop senza ricostruire la scena: cambia a ogni risposta dell'LLM
  const throttledRef = useRef(throttled);
  throttledRef.current = throttled;

  // Chiave reattiva dei ruoli per ricostruire dinamicamente la plancia quando i ruoli vengono caricati dal backend
  const rolesKey = (roles || []).map(r => r.id).join('|');

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    let width = container.clientWidth || window.innerWidth;
    let height = container.clientHeight || window.innerHeight;

    // 'lite' riduce risoluzione, frequenza e aggiornamento degli schermi:
    // e' la modalita' che tiene la plancia fluida sul Raspberry Pi 5.
    let lite = quality === 'lite' || (quality === 'auto' && detectLowEndGpu());
    const reducedMotion = prefersReducedMotion();
    const basePixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    const litePixelRatio = Math.min(window.devicePixelRatio || 1, 1) * 0.75;

    // Con finestre strette il FOV verticale fisso tagliava i lati della plancia:
    // lo si allarga per mantenere circa la stessa apertura orizzontale.
    const fovForAspect = (aspect) => (aspect >= 1.35 ? 46 : Math.min(72, 46 * Math.pow(1.35 / aspect, 0.75)));

    // =========================================================================
    // 1. Scena, Camera e WebGL Renderer ad Alte Prestazioni
    // =========================================================================
    let scene, camera, renderer;
    try {
      scene = new THREE.Scene();
      // Nebbia lineare che mantiene perfettamente visibile la volta stellare e le galassie all'esterno
      scene.fog = new THREE.Fog(isLight ? 0xe2e8f0 : 0x01020a, 40, 220);

      camera = new THREE.PerspectiveCamera(fovForAspect(width / height), width / height, 0.1, 1000);
      // Si parte gia' dentro la plancia: da fuori le vetrate si vedeva il retro
      // di un montante come un grande rettangolo nero finche' la camera non rientrava.
      camera.position.set(0, 5.0, 16.5);

      renderer = new THREE.WebGLRenderer({
        antialias: !lite,
        alpha: true,
        powerPreference: 'high-performance'
      });
      renderer.setSize(width, height);
      renderer.setPixelRatio(lite ? litePixelRatio : basePixelRatio);
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = isLight ? 1.15 : 1.4;
      container.appendChild(renderer.domElement);
    } catch (e) {
      console.warn('Errore inizializzazione WebGL:', e);
      return;
    }

    // =========================================================================
    // 2. Sistema di Illuminazione Plancia Navicella
    // =========================================================================
    const ambientLight = new THREE.AmbientLight(isLight ? 0xffffff : 0x0c1530, isLight ? 1.7 : 1.35);
    scene.add(ambientLight);

    const bridgeMainLight = new THREE.DirectionalLight(0xdbeafe, isLight ? 1.4 : 1.9);
    bridgeMainLight.position.set(8, 18, 12);
    scene.add(bridgeMainLight);

    const holotableLight = new THREE.PointLight(0x00f0ff, isLight ? 2.8 : 5.0, 48, 1.2);
    holotableLight.position.set(0, 8.5, 0);
    scene.add(holotableLight);

    const sternAccentLight = new THREE.PointLight(0xff007a, isLight ? 1.5 : 3.8, 42, 1.3);
    sternAccentLight.position.set(0, 6.5, -16);
    scene.add(sternAccentLight);

    const starboardLight = new THREE.PointLight(0x38bdf8, 2.4, 38, 1.4);
    starboardLight.position.set(16, 5.5, 6);
    scene.add(starboardLight);

    // =========================================================================
    // 3. Architettura Navicella Spaziale (Starship Command Deck)
    // =========================================================================
    const shipGroup = new THREE.Group();
    scene.add(shipGroup);

    // A. Pavimento Deck Metallico Rigorosamente Limitato a Cerchio (Non sborda all'esterno)
    const floorRadius = 20.45; // Coincide esattamente con il perimetro interno delle vetrate a raggio 20.5
    const floorGeo = new THREE.CircleGeometry(floorRadius, 64);

    // Texture circolare cibernetica ad alta definizione per la pavimentazione della navicella
    const makeFloorTexture = () => {
      const fCanvas = document.createElement('canvas');
      fCanvas.width = 1024;
      fCanvas.height = 1024;
      const fctx = fCanvas.getContext('2d');
      if (!fctx) return new THREE.Texture();

      const cx = 512;
      const cy = 512;
      const r = 508;

      // Base circolare metallica spazzolata
      const bgGrad = fctx.createRadialGradient(cx, cy, 50, cx, cy, r);
      bgGrad.addColorStop(0, isLight ? '#f1f5f9' : '#0c152a');
      bgGrad.addColorStop(0.65, isLight ? '#e2e8f0' : '#070b18');
      bgGrad.addColorStop(1, isLight ? '#cbd5e1' : '#03050d');
      fctx.fillStyle = bgGrad;
      fctx.beginPath();
      fctx.arc(cx, cy, r, 0, Math.PI * 2);
      fctx.fill();

      // Clipping circolare per garantire che nessun disegno fuoriesca dal perimetro
      fctx.save();
      fctx.beginPath();
      fctx.arc(cx, cy, r, 0, Math.PI * 2);
      fctx.clip();

      // Cerchi concentrici tattici della plancia
      const rings = [100, 180, 260, 340, 420, 490];
      rings.forEach((ringR, idx) => {
        fctx.strokeStyle = idx % 2 === 0 ? 'rgba(0, 240, 255, 0.35)' : 'rgba(124, 91, 240, 0.25)';
        fctx.lineWidth = idx === rings.length - 1 ? 4 : 2;
        fctx.beginPath();
        fctx.arc(cx, cy, ringR, 0, Math.PI * 2);
        fctx.stroke();
      });

      // 16 raggi radiali che collegano il centro ai 16 montanti e alle postazioni
      for (let i = 0; i < 16; i++) {
        const radAngle = (i / 16) * Math.PI * 2;
        const x2 = cx + Math.cos(radAngle) * r;
        const y2 = cy + Math.sin(radAngle) * r;
        fctx.strokeStyle = i % 2 === 0 ? 'rgba(0, 240, 255, 0.28)' : 'rgba(124, 91, 240, 0.18)';
        fctx.lineWidth = 1.5;
        fctx.beginPath();
        fctx.moveTo(cx, cy);
        fctx.lineTo(x2, y2);
        fctx.stroke();
      }

      // Finitura metallica circolare spazzolata pulita (nessuna griglia a quadretti)
      const ringGlow = fctx.createRadialGradient(cx, cy, 320, cx, cy, 480);
      ringGlow.addColorStop(0, 'rgba(0, 240, 255, 0)');
      ringGlow.addColorStop(0.5, isLight ? 'rgba(0, 210, 255, 0.06)' : 'rgba(0, 210, 255, 0.08)');
      ringGlow.addColorStop(1, 'rgba(0, 240, 255, 0)');
      fctx.fillStyle = ringGlow;
      fctx.beginPath();
      fctx.arc(cx, cy, 480, 0, Math.PI * 2);
      fctx.fill();

      fctx.restore();

      const tex = new THREE.CanvasTexture(fCanvas);
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      return tex;
    };

    const floorTex = makeFloorTexture();
    const floorMat = new THREE.MeshStandardMaterial({
      map: floorTex,
      roughness: 0.32,
      metalness: 0.68,
      side: THREE.DoubleSide
    });
    const floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.y = -2.0;
    shipGroup.add(floorMesh);

    // Bordo circolare perimetrale di sicurezza della plancia (perfettamente aderente alle vetrate)
    const deckPerimeterGeo = new THREE.RingGeometry(floorRadius - 0.55, floorRadius, 64);
    const deckPerimeterMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    const deckPerimeter = new THREE.Mesh(deckPerimeterGeo, deckPerimeterMat);
    deckPerimeter.rotation.x = -Math.PI / 2;
    deckPerimeter.position.y = -1.97;
    shipGroup.add(deckPerimeter);

    // B. Finestre Panoramiche a 360° della Navicella (Starship Panoramic Observation Bay)
    // Ampia campata vetrata che circonda la plancia da cui ammirare lo spazio profondo e le galassie
    const windowRadius = 20.5;
    const windowHeight = 7.6;
    const windowGeo = new THREE.CylinderGeometry(windowRadius, windowRadius, windowHeight, 48, 1, true);
    const windowMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.025,
      depthWrite: false, // Massima trasparenza ottica pura senza alcuna sfocatura dello spazio esterno
      side: THREE.DoubleSide
    });
    const cockpitWindow = new THREE.Mesh(windowGeo, windowMat);
    cockpitWindow.position.set(0, 2.2, 0);
    shipGroup.add(cockpitWindow);

    // Cornice superiore e inferiore della vetrata
    const roofRingGeo = new THREE.RingGeometry(windowRadius - 0.45, windowRadius + 0.5, 48);
    const windowFrameMat = new THREE.MeshStandardMaterial({
      color: isLight ? 0x94a3b8 : 0x111c38,
      metalness: 0.85,
      roughness: 0.25,
      side: THREE.DoubleSide
    });
    const roofRing = new THREE.Mesh(roofRingGeo, windowFrameMat);
    roofRing.rotation.x = -Math.PI / 2;
    roofRing.position.y = 2.2 + windowHeight / 2;
    shipGroup.add(roofRing);

    const sillRingGeo = new THREE.RingGeometry(windowRadius - 0.45, windowRadius + 0.5, 48);
    const sillRing = new THREE.Mesh(sillRingGeo, windowFrameMat);
    sillRing.rotation.x = -Math.PI / 2;
    sillRing.position.y = 2.2 - windowHeight / 2;
    shipGroup.add(sillRing);

    // Montanti verticali della vetrata (16 pilastri strutturali distribuiti lungo il perimetro)
    const mullionCount = 16;
    for (let m = 0; m < mullionCount; m++) {
      const mAngle = (m / mullionCount) * Math.PI * 2;
      const mx = Math.cos(mAngle) * windowRadius;
      const mz = Math.sin(mAngle) * windowRadius;

      const mGeo = new THREE.BoxGeometry(0.38, windowHeight + 0.4, 0.42);
      const mMat = new THREE.MeshStandardMaterial({
        color: isLight ? 0x64748b : 0x1e293b,
        metalness: 0.8,
        roughness: 0.25
      });
      const mullion = new THREE.Mesh(mGeo, mMat);
      mullion.position.set(mx, 2.2, mz);
      mullion.rotation.y = -mAngle + Math.PI / 2;
      shipGroup.add(mullion);

      // Profilo LED ciano/magenta sul montante della finestra
      const neonStripGeo = new THREE.BoxGeometry(0.08, windowHeight, 0.08);
      const neonStripMat = new THREE.MeshBasicMaterial({
        color: m % 2 === 0 ? 0x00f0ff : 0xff007a,
        blending: THREE.AdditiveBlending
      });
      const neonStrip = new THREE.Mesh(neonStripGeo, neonStripMat);
      neonStrip.position.set(mx * 0.985, 2.2, mz * 0.985);
      neonStrip.rotation.y = -mAngle + Math.PI / 2;
      shipGroup.add(neonStrip);
    }

    // C. Cupola Emisferica Panoramica (Observation Dome with Intersecting Vault Arches)
    // 8 archi strutturali maestosi che partono sopra il confine delle finestre (y = 6.0)
    // e salgono incurvandosi creando una mezza sfera che si incrocia esattamente in alto al centro allo zenit
    const domeGroup = new THREE.Group();
    const baseDomeY = 2.2 + windowHeight / 2; // Quota superiore esatta delle finestre (y = 6.0)
    const domeHeight = 10.5; // Altezza zenitale della mezza sfera
    const archCount = 8; // 8 diametri che collegano i 16 montanti perimetrali

    const ribMat = new THREE.MeshStandardMaterial({
      color: isLight ? 0x94a3b8 : 0x111c35,
      metalness: 0.85,
      roughness: 0.22
    });

    const ribNeonMatCyan = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      blending: THREE.AdditiveBlending
    });

    const ribNeonMatPurple = new THREE.MeshBasicMaterial({
      color: 0x7c5bf0,
      blending: THREE.AdditiveBlending
    });

    // Costruzione degli 8 archi a mezza sfera che si incrociano al centro in alto
    for (let a = 0; a < archCount; a++) {
      const archAngle = (a / archCount) * Math.PI; // Da 0 a PI (copre tutti i 16 montanti)
      const points = [];
      const samples = 36;
      for (let s = 0; s <= samples; s++) {
        const t = (s / samples) * Math.PI; // parametro da 0 a PI
        const u = Math.cos(t) * windowRadius; // varia da +windowRadius a -windowRadius
        const y = baseDomeY + Math.sin(t) * domeHeight; // sale da baseDomeY fino a zenit e riscende
        const x = Math.cos(archAngle) * u;
        const z = Math.sin(archAngle) * u;
        points.push(new THREE.Vector3(x, y, z));
      }

      const archCurve = new THREE.CatmullRomCurve3(points);

      // Costolone strutturale metallico dell'arco
      const archGeo = new THREE.TubeGeometry(archCurve, 36, 0.24, 10, false);
      const archMesh = new THREE.Mesh(archGeo, ribMat);
      domeGroup.add(archMesh);

      // Profilo LED luminescente lungo l'arco
      const neonGeo = new THREE.TubeGeometry(archCurve, 36, 0.055, 8, false);
      const neonMat = a % 2 === 0 ? ribNeonMatCyan : ribNeonMatPurple;
      const neonMesh = new THREE.Mesh(neonGeo, neonMat);
      domeGroup.add(neonMesh);
    }

    // Mozzo Centrale di Incrocio allo Zenit (Keystone Oculus Hub)
    const zenithY = baseDomeY + domeHeight;
    const oculusGeo = new THREE.TorusGeometry(1.9, 0.26, 16, 48);
    const oculusMesh = new THREE.Mesh(oculusGeo, ribMat);
    oculusMesh.rotation.x = Math.PI / 2;
    oculusMesh.position.set(0, zenithY, 0);
    domeGroup.add(oculusMesh);

    // Anello neon dell'oculo centrale
    const oculusNeonGeo = new THREE.TorusGeometry(1.5, 0.065, 12, 36);
    const oculusNeon = new THREE.Mesh(oculusNeonGeo, ribNeonMatCyan);
    oculusNeon.rotation.x = Math.PI / 2;
    oculusNeon.position.set(0, zenithY, 0);
    domeGroup.add(oculusNeon);

    // Emettitore di energia olografica al centro dello zenit
    const zenithCoreGeo = new THREE.SphereGeometry(0.85, 24, 16);
    const zenithCoreMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    const zenithCore = new THREE.Mesh(zenithCoreGeo, zenithCoreMat);
    zenithCore.position.set(0, zenithY, 0);
    domeGroup.add(zenithCore);

    // Faretto zenitale rivolto verso il basso (illumina il tappeto centrale della nave)
    const zenithSpotLight = new THREE.SpotLight(0x00f0ff, isLight ? 2.5 : 4.8, 36, Math.PI / 5.5, 0.45, 1.2);
    zenithSpotLight.position.set(0, zenithY - 0.2, 0);
    zenithSpotLight.target.position.set(0, -1.8, 0);
    scene.add(zenithSpotLight);
    scene.add(zenithSpotLight.target);

    // Anelli Orizzontali di Rinforzo della Mezza Sfera (Purlin Hoops)
    // Primo anello orizzontale a quota intermedia
    const hoop1Radius = windowRadius * Math.cos(Math.PI / 4); // ~14.5
    const hoop1Y = baseDomeY + domeHeight * Math.sin(Math.PI / 4); // ~13.4
    const hoop1Geo = new THREE.TorusGeometry(hoop1Radius, 0.12, 10, 64);
    const hoop1Mesh = new THREE.Mesh(hoop1Geo, ribMat);
    hoop1Mesh.rotation.x = Math.PI / 2;
    hoop1Mesh.position.set(0, hoop1Y, 0);
    domeGroup.add(hoop1Mesh);

    const hoop1NeonGeo = new THREE.TorusGeometry(hoop1Radius, 0.04, 8, 64);
    const hoop1Neon = new THREE.Mesh(hoop1NeonGeo, ribNeonMatCyan);
    hoop1Neon.rotation.x = Math.PI / 2;
    hoop1Neon.position.set(0, hoop1Y, 0);
    domeGroup.add(hoop1Neon);

    // Secondo anello orizzontale a quota superiore
    const hoop2Radius = windowRadius * Math.cos(Math.PI / 3); // ~10.25
    const hoop2Y = baseDomeY + domeHeight * Math.sin(Math.PI / 3); // ~15.1
    const hoop2Geo = new THREE.TorusGeometry(hoop2Radius, 0.11, 10, 64);
    const hoop2Mesh = new THREE.Mesh(hoop2Geo, ribMat);
    hoop2Mesh.rotation.x = Math.PI / 2;
    hoop2Mesh.position.set(0, hoop2Y, 0);
    domeGroup.add(hoop2Mesh);

    const hoop2NeonGeo = new THREE.TorusGeometry(hoop2Radius, 0.035, 8, 64);
    const hoop2Neon = new THREE.Mesh(hoop2NeonGeo, ribNeonMatPurple);
    hoop2Neon.rotation.x = Math.PI / 2;
    hoop2Neon.position.set(0, hoop2Y, 0);
    domeGroup.add(hoop2Neon);

    // Calotta Vetrata Trasparente Semisferica Superiore
    const domeGlassGeo = new THREE.SphereGeometry(windowRadius, 48, 20, 0, Math.PI * 2, 0, Math.PI / 2);
    const domeGlassMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.02,
      depthWrite: false, // Massima nitidezza verso lo zenit astronomico
      side: THREE.DoubleSide
    });
    const domeGlass = new THREE.Mesh(domeGlassGeo, domeGlassMat);
    domeGlass.scale.set(1, domeHeight / windowRadius, 1);
    domeGlass.position.set(0, baseDomeY, 0);
    domeGroup.add(domeGlass);

    shipGroup.add(domeGroup);

    // D. Piattaforma Centrale con Tappeto Olografico Logo Sigma Studio
    const centerPlatformGeo = new THREE.CylinderGeometry(4.2, 4.5, 0.2, 64);
    const centerPlatformMat = new THREE.MeshStandardMaterial({
      color: isLight ? 0xf1f5f9 : 0x090f20,
      metalness: 0.8,
      roughness: 0.3
    });
    const centerPlatform = new THREE.Mesh(centerPlatformGeo, centerPlatformMat);
    centerPlatform.position.y = -1.89;
    shipGroup.add(centerPlatform);

    // Tappeto / Medaglione con Logo Sigma Studio perfettamente circolare ad alta fedeltà
    const carpetGeo = new THREE.CircleGeometry(3.6, 64);
    const carpetCanvas = document.createElement('canvas');
    carpetCanvas.width = 1024;
    carpetCanvas.height = 1024;
    const cctx = carpetCanvas.getContext('2d');

    // Funzione di disegno base tappeto cibernetico
    const renderBaseCarpet = () => {
      if (!cctx) return;
      const size = 1024;
      const cx = size / 2;
      const cy = size / 2;
      const r = size * 0.465;

      cctx.clearRect(0, 0, size, size);

      // Fondo scuro titanio della pedana del tappeto
      const bgGrad = cctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      bgGrad.addColorStop(0, '#0c152e');
      bgGrad.addColorStop(0.7, '#070c1b');
      bgGrad.addColorStop(0.96, '#030610');
      bgGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      cctx.fillStyle = bgGrad;
      cctx.beginPath();
      cctx.arc(cx, cy, r, 0, Math.PI * 2);
      cctx.fill();

      // Cerchi concentrici tattici
      cctx.strokeStyle = 'rgba(0, 240, 255, 0.45)';
      cctx.lineWidth = 4;
      cctx.beginPath();
      cctx.arc(cx, cy, r * 0.94, 0, Math.PI * 2);
      cctx.stroke();

      cctx.strokeStyle = 'rgba(124, 91, 240, 0.35)';
      cctx.lineWidth = 2;
      cctx.beginPath();
      cctx.arc(cx, cy, r * 0.72, 0, Math.PI * 2);
      cctx.stroke();

      // Monogramma "Σ" stilizzato al centro
      cctx.fillStyle = '#00f0ff';
      cctx.shadowColor = '#00f0ff';
      cctx.shadowBlur = 24;
      cctx.font = 'bold 260px "Inter", "Segoe UI", sans-serif';
      cctx.textAlign = 'center';
      cctx.textBaseline = 'middle';
      cctx.fillText('Σ', cx, cy - 10);
      cctx.shadowBlur = 0;

      // Scritte tecniche perimetrali
      cctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
      cctx.font = 'bold 22px monospace';
      cctx.fillText('SIGMA STUDIO // COMMAND BRIDGE // CORE 0.9.0', cx, cy + 180);
    };

    renderBaseCarpet();

    const carpetTex = new THREE.CanvasTexture(carpetCanvas);
    carpetTex.minFilter = THREE.LinearFilter;
    carpetTex.magFilter = THREE.LinearFilter;
    const carpetMat = new THREE.MeshStandardMaterial({
      map: carpetTex,
      transparent: true,
      roughness: 0.38,
      metalness: 0.28,
      depthWrite: true,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -4,
      fog: false, // Massima nitidezza e brillantezza costante a qualsiasi distanza
      side: THREE.DoubleSide
    });
    const carpetMesh = new THREE.Mesh(carpetGeo, carpetMat);
    carpetMesh.renderOrder = 2;
    carpetMesh.rotation.x = -Math.PI / 2;
    carpetMesh.position.y = -1.78;
    shipGroup.add(carpetMesh);

    // Caricamento dell'immagine ufficiale del logo con maschera circolare antialiased
    const carpetImg = new Image();
    carpetImg.crossOrigin = 'anonymous';
    carpetImg.src = '/images/SigmaStudio.png';
    carpetImg.onload = () => {
      try {
        if (!cctx) return;
        const size = 1024;
        const cx = size / 2;
        const cy = size / 2;
        const r = size * 0.465;

        cctx.clearRect(0, 0, size, size);

        // Salvataggio stato per clipping circolare
        cctx.save();
        cctx.beginPath();
        cctx.arc(cx, cy, r, 0, Math.PI * 2);
        cctx.closePath();
        cctx.clip();

        // Disegno del logo al centro del cerchio
        cctx.drawImage(carpetImg, 0, 0, size, size);

        // Sfumatura di bordo radiale morbida (feathering) per fondere il tappeto con la pedana
        const featherGrad = cctx.createRadialGradient(cx, cy, r * 0.91, cx, cy, r);
        featherGrad.addColorStop(0, 'rgba(7, 12, 27, 0)');
        featherGrad.addColorStop(1, 'rgba(7, 12, 27, 0.98)');
        cctx.fillStyle = featherGrad;
        cctx.fill();

        cctx.restore();

        // Anello metallico dorato / azzurro di rifinitura interna del tappeto
        cctx.strokeStyle = 'rgba(0, 240, 255, 0.75)';
        cctx.lineWidth = 6;
        cctx.beginPath();
        cctx.arc(cx, cy, r - 3, 0, Math.PI * 2);
        cctx.stroke();

        carpetTex.needsUpdate = true;
      } catch (err) {
        console.warn('Errore rendering texture tappeto:', err);
      }
    };

    // Bordo circolare neon del tappeto
    const carpetRimGeo = new THREE.RingGeometry(3.58, 3.74, 64);
    const carpetRimMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.92,
      blending: THREE.AdditiveBlending
    });
    const carpetRim = new THREE.Mesh(carpetRimGeo, carpetRimMat);
    carpetRim.rotation.x = -Math.PI / 2;
    carpetRim.position.y = -1.77;
    shipGroup.add(carpetRim);

    // Anello concentrico esterno del tappeto di comando
    const outerCarpetRingGeo = new THREE.RingGeometry(3.9, 4.06, 64);
    const outerCarpetRingMat = new THREE.MeshBasicMaterial({
      color: 0x7c5bf0,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    const outerCarpetRing = new THREE.Mesh(outerCarpetRingGeo, outerCarpetRingMat);
    outerCarpetRing.rotation.x = -Math.PI / 2;
    outerCarpetRing.position.y = -1.76;
    shipGroup.add(outerCarpetRing);

    // =========================================================================
    // 4. Background Cosmico Profondo: Vuoto Stellare Nero Assoluto, Luci, Costellazioni e Sistema Planetario
    // =========================================================================
    // Realismo astronomico fedele all'universo reale:
    // - Nero inchiostro assoluto del vuoto spaziale (#000000 / #000103)
    // - Eliminato qualsiasi alone artificiale o nebbia sgranata: solo una finissima starlight diffusa argentea
    // - Campo stellare multi-tier con sfumature di temperatura spettrale e baffi di diffrazione ottica
    // - Ammasso aperto delle Pleiadi (Sette Sorelle azzurre)
    // - Costellazioni reali riconoscibili con linee geometriche e cartigli olografici
    //   (Orione, Orsa Maggiore / Grande Carro, Cassiopea a 'W', Cigno / Croce del Nord, Toro & Iadi)
    // - Sistema planetario visibile attraverso le ampie vetrate panoramiche:
    //   1. Terra Nova: Blue Marble con oceani, masse continentali, nuvole cicloniche rotanti, atmosfera di Rayleigh e Luna
    //   2. Kronos: Gigante gassoso dorato con spettacolari anelli ghiacciati e divisione di Cassini
    //   3. Ares: Pianeta rosso marziano con canyon e calotte polari di ghiaccio
    //   4. Luna / Selene: Satellite craterizzato ad alto contrasto nella volta celeste superiore
    const cosmosVertexShader = `
      varying vec3 vWorldDirection;
      void main() {
        vec4 worldPos = modelMatrix * vec4(position, 1.0);
        vWorldDirection = normalize(worldPos.xyz);
        gl_Position = projectionMatrix * viewMatrix * worldPos;
      }
    `;

    const cosmosFragmentShader = `
      uniform float uTime;
      varying vec3 vWorldDirection;

      void main() {
        vec3 dir = normalize(vWorldDirection);

        // Nero siderale assoluto dello spazio profondo
        vec3 color = vec3(0.0002, 0.0004, 0.0008);

        // Debolissimo velo stellare della Via Lattea (polvere argentea impercettibile lungo l'equatore galattico)
        vec3 galacticPole = normalize(vec3(0.38, 0.78, 0.49));
        float sinLat = dot(dir, galacticPole);
        float discDensity = exp(-pow(sinLat * 5.4, 2.0));
        vec3 starlightVeil = vec3(0.012, 0.015, 0.022) * discDensity;
        color += starlightVeil;

        gl_FragColor = vec4(color, 1.0);
      }
    `;

    const cosmosGeo = new THREE.SphereGeometry(150, 48, 32);
    const cosmosMat = new THREE.ShaderMaterial({
      vertexShader: cosmosVertexShader,
      fragmentShader: cosmosFragmentShader,
      uniforms: {
        uTime: { value: 0 }
      },
      side: THREE.BackSide,
      depthWrite: false,
      fog: false
    });
    const cosmosDome = new THREE.Mesh(cosmosGeo, cosmosMat);
    scene.add(cosmosDome);

    // Generatore di sprite stellari a punta di diamante ultra-definiti (zero sfocatura)
    const makeSharpStarSprite = (hasDiffraction = false) => {
      const sCanvas = document.createElement('canvas');
      sCanvas.width = 64;
      sCanvas.height = 64;
      const sctx = sCanvas.getContext('2d');
      if (!sctx) return new THREE.Texture();

      sctx.clearRect(0, 0, 64, 64);
      const cx = 32;
      const cy = 32;

      if (hasDiffraction) {
        // Baffi di diffrazione ottica a croce da telescopio spaziale
        const spikeH = sctx.createLinearGradient(0, cy, 64, cy);
        spikeH.addColorStop(0, 'rgba(255, 255, 255, 0)');
        spikeH.addColorStop(0.35, 'rgba(255, 255, 255, 0.20)');
        spikeH.addColorStop(0.5, 'rgba(255, 255, 255, 1.0)');
        spikeH.addColorStop(0.65, 'rgba(255, 255, 255, 0.20)');
        spikeH.addColorStop(1, 'rgba(255, 255, 255, 0)');
        sctx.fillStyle = spikeH;
        sctx.fillRect(0, cy - 0.75, 64, 1.5);

        const spikeV = sctx.createLinearGradient(cx, 0, cx, 64);
        spikeV.addColorStop(0, 'rgba(255, 255, 255, 0)');
        spikeV.addColorStop(0.35, 'rgba(255, 255, 255, 0.20)');
        spikeV.addColorStop(0.5, 'rgba(255, 255, 255, 1.0)');
        spikeV.addColorStop(0.65, 'rgba(255, 255, 255, 0.20)');
        spikeV.addColorStop(1, 'rgba(255, 255, 255, 0)');
        sctx.fillStyle = spikeV;
        sctx.fillRect(cx - 0.75, 0, 1.5, 64);
      }

      // Nucleo compatto e brillante
      const grad = sctx.createRadialGradient(cx, cy, 0, cx, cy, 14);
      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.18, 'rgba(255, 255, 255, 0.95)');
      grad.addColorStop(0.35, 'rgba(225, 240, 255, 0.50)');
      grad.addColorStop(0.65, 'rgba(160, 200, 255, 0.12)');
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      sctx.fillStyle = grad;
      sctx.beginPath();
      sctx.arc(cx, cy, 14, 0, Math.PI * 2);
      sctx.fill();

      // Micro-punto centrale puro
      sctx.fillStyle = '#ffffff';
      sctx.beginPath();
      sctx.arc(cx, cy, 2.0, 0, Math.PI * 2);
      sctx.fill();

      const tex = new THREE.CanvasTexture(sCanvas);
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      return tex;
    };

    const sharpStarTex = makeSharpStarSprite(false);
    const diffractionStarTex = makeSharpStarSprite(true);

    // 1. Velo di stelle di fondo (5.500 micro-punti nitidissimi)
    const bgStarCount = 5500;
    const bgStarPositions = new Float32Array(bgStarCount * 3);
    const bgStarColors = new Float32Array(bgStarCount * 3);
    for (let i = 0; i < bgStarCount; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 132 + Math.random() * 15;

      bgStarPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      bgStarPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      bgStarPositions[i * 3 + 2] = r * Math.cos(phi);

      const ct = Math.random();
      if (ct > 0.86) {
        // Stelle calde bianco-azzurre
        bgStarColors[i * 3] = 0.75; bgStarColors[i * 3 + 1] = 0.90; bgStarColors[i * 3 + 2] = 1.0;
      } else if (ct > 0.72) {
        // Stelle solari oro
        bgStarColors[i * 3] = 1.0; bgStarColors[i * 3 + 1] = 0.95; bgStarColors[i * 3 + 2] = 0.82;
      } else if (ct > 0.62) {
        // Nane arancio/rosse
        bgStarColors[i * 3] = 1.0; bgStarColors[i * 3 + 1] = 0.72; bgStarColors[i * 3 + 2] = 0.60;
      } else {
        // Bianco puro
        bgStarColors[i * 3] = 1.0; bgStarColors[i * 3 + 1] = 1.0; bgStarColors[i * 3 + 2] = 1.0;
      }
    }
    const bgStarGeo = new THREE.BufferGeometry();
    bgStarGeo.setAttribute('position', new THREE.BufferAttribute(bgStarPositions, 3));
    bgStarGeo.setAttribute('color', new THREE.BufferAttribute(bgStarColors, 3));
    const bgStarMat = new THREE.PointsMaterial({
      size: 0.85,
      map: sharpStarTex,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false
    });
    const bgStarPoints = new THREE.Points(bgStarGeo, bgStarMat);
    scene.add(bgStarPoints);

    // 2. Stelle brillanti di primo piano (520 stelle con magnitudine maggiore)
    const fgStarCount = 520;
    const fgStarPositions = new Float32Array(fgStarCount * 3);
    const fgStarColors = new Float32Array(fgStarCount * 3);
    for (let i = 0; i < fgStarCount; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 126 + Math.random() * 12;

      fgStarPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      fgStarPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      fgStarPositions[i * 3 + 2] = r * Math.cos(phi);

      const ct = Math.random();
      if (ct > 0.7) {
        fgStarColors[i * 3] = 0.82; fgStarColors[i * 3 + 1] = 0.94; fgStarColors[i * 3 + 2] = 1.0;
      } else if (ct > 0.4) {
        fgStarColors[i * 3] = 1.0; fgStarColors[i * 3 + 1] = 0.92; fgStarColors[i * 3 + 2] = 0.75;
      } else {
        fgStarColors[i * 3] = 1.0; fgStarColors[i * 3 + 1] = 1.0; fgStarColors[i * 3 + 2] = 1.0;
      }
    }
    const fgStarGeo = new THREE.BufferGeometry();
    fgStarGeo.setAttribute('position', new THREE.BufferAttribute(fgStarPositions, 3));
    fgStarGeo.setAttribute('color', new THREE.BufferAttribute(fgStarColors, 3));
    const fgStarMat = new THREE.PointsMaterial({
      size: 1.6,
      map: sharpStarTex,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false
    });
    const fgStarPoints = new THREE.Points(fgStarGeo, fgStarMat);
    scene.add(fgStarPoints);

    // 3. Fari celesti con diffrazione ottica a croce (42 stelle guida maggiori)
    const beaconCount = 42;
    const beaconPositions = new Float32Array(beaconCount * 3);
    const beaconColors = new Float32Array(beaconCount * 3);
    for (let i = 0; i < beaconCount; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const r = 120 + Math.random() * 10;

      beaconPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      beaconPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      beaconPositions[i * 3 + 2] = r * Math.cos(phi);

      const ct = Math.random();
      if (ct > 0.5) {
        beaconColors[i * 3] = 0.88; beaconColors[i * 3 + 1] = 0.96; beaconColors[i * 3 + 2] = 1.0;
      } else {
        beaconColors[i * 3] = 1.0; beaconColors[i * 3 + 1] = 0.88; beaconColors[i * 3 + 2] = 0.72;
      }
    }
    const beaconGeo = new THREE.BufferGeometry();
    beaconGeo.setAttribute('position', new THREE.BufferAttribute(beaconPositions, 3));
    beaconGeo.setAttribute('color', new THREE.BufferAttribute(beaconColors, 3));
    const beaconMat = new THREE.PointsMaterial({
      size: 3.8,
      map: diffractionStarTex,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false
    });
    const beaconPoints = new THREE.Points(beaconGeo, beaconMat);
    scene.add(beaconPoints);

    // 4. Ammasso Aperto delle Pleiadi (Le 7 Sorelle azzurre concentrate)
    const pleiadesPositions = [
      [-69.5, 23.2, 122],
      [-70.2, 23.8, 122],
      [-70.8, 22.9, 122],
      [-71.5, 23.5, 122],
      [-72.1, 24.1, 122],
      [-69.0, 24.0, 122],
      [-70.0, 22.4, 122],
      [-71.1, 24.6, 122],
      [-72.8, 23.0, 122]
    ];
    const pleiadesPosArray = new Float32Array(pleiadesPositions.length * 3);
    const pleiadesColArray = new Float32Array(pleiadesPositions.length * 3);
    pleiadesPositions.forEach((pos, idx) => {
      const yaw = (pos[0] * Math.PI) / 180;
      const pitch = (pos[1] * Math.PI) / 180;
      const r = pos[2];
      pleiadesPosArray[idx * 3] = r * Math.cos(pitch) * Math.sin(yaw);
      pleiadesPosArray[idx * 3 + 1] = r * Math.sin(pitch);
      pleiadesPosArray[idx * 3 + 2] = r * Math.cos(pitch) * Math.cos(yaw);
      pleiadesColArray[idx * 3] = 0.70;
      pleiadesColArray[idx * 3 + 1] = 0.88;
      pleiadesColArray[idx * 3 + 2] = 1.0;
    });
    const pleiadesGeo = new THREE.BufferGeometry();
    pleiadesGeo.setAttribute('position', new THREE.BufferAttribute(pleiadesPosArray, 3));
    pleiadesGeo.setAttribute('color', new THREE.BufferAttribute(pleiadesColArray, 3));
    const pleiadesMat = new THREE.PointsMaterial({
      size: 2.8,
      map: diffractionStarTex,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false
    });
    const pleiadesPoints = new THREE.Points(pleiadesGeo, pleiadesMat);
    scene.add(pleiadesPoints);

    // =========================================================================
    // 4B. Costellazioni Astronomiche Reali con Linee Geometriche e Cartigli HUD
    // =========================================================================
    const constellationsGroup = new THREE.Group();
    const constellationLabels = [];

    // Helper per conversione da coordinate astronomiche sferiche (yaw/azimuth, pitch/altitudine) a Vector3
    const toSkyCoord = (yawDeg, pitchDeg, r = 124) => {
      const yaw = (yawDeg * Math.PI) / 180;
      const pitch = (pitchDeg * Math.PI) / 180;
      return new THREE.Vector3(
        r * Math.cos(pitch) * Math.sin(yaw),
        r * Math.sin(pitch),
        r * Math.cos(pitch) * Math.cos(yaw)
      );
    };

    // Generatore di cartiglio olografico per nome costellazione
    const createConstellationTag = (label, yawDeg, pitchDeg) => {
      const tCanvas = document.createElement('canvas');
      tCanvas.width = 320;
      tCanvas.height = 72;
      const tctx = tCanvas.getContext('2d');
      if (tctx) {
        tctx.clearRect(0, 0, 320, 72);
        // Box di sfondo semitrasparente
        tctx.fillStyle = 'rgba(3, 8, 18, 0.75)';
        tctx.strokeStyle = 'rgba(79, 195, 247, 0.50)';
        tctx.lineWidth = 1.8;
        tctx.strokeRect(8, 8, 304, 56);
        tctx.fillRect(8, 8, 304, 56);

        // Angoli futuristici
        tctx.strokeStyle = '#81d4fa';
        tctx.lineWidth = 3.0;
        tctx.beginPath();
        tctx.moveTo(8, 20); tctx.lineTo(8, 8); tctx.lineTo(20, 8);
        tctx.moveTo(292, 8); tctx.lineTo(304, 8); tctx.lineTo(304, 20);
        tctx.moveTo(8, 52); tctx.lineTo(8, 64); tctx.lineTo(20, 64);
        tctx.moveTo(292, 64); tctx.lineTo(304, 64); tctx.lineTo(304, 52);
        tctx.stroke();

        // Tipografia monogrammata
        tctx.font = '700 20px "Courier New", monospace';
        tctx.textAlign = 'center';
        tctx.textBaseline = 'middle';
        tctx.fillStyle = '#b3e5fc';
        tctx.fillText(label, 160, 36);
      }
      const tTex = new THREE.CanvasTexture(tCanvas);
      const tMat = new THREE.SpriteMaterial({
        map: tTex,
        transparent: true,
        opacity: 0.88,
        depthWrite: false,
        fog: false
      });
      const sprite = new THREE.Sprite(tMat);
      sprite.position.copy(toSkyCoord(yawDeg, pitchDeg, 118));
      sprite.scale.set(13.5, 3.0, 1);
      constellationsGroup.add(sprite);
      constellationLabels.push({ sprite, texture: tTex, material: tMat });
    };

    // 1. ORIONE (Orion / Il Cacciatore)
    const orionStars = {
      betelgeuse: { pt: toSkyCoord(-23.5, 15.0), col: [1.0, 0.45, 0.22], sz: 3.2 },
      bellatrix: { pt: toSkyCoord(-32.5, 13.5), col: [0.82, 0.92, 1.0], sz: 2.5 },
      rigel: { pt: toSkyCoord(-31.0, -3.5), col: [0.75, 0.90, 1.0], sz: 3.4 },
      saiph: { pt: toSkyCoord(-22.0, -2.5), col: [0.95, 0.95, 1.0], sz: 2.3 },
      meissa: { pt: toSkyCoord(-28.0, 20.0), col: [0.9, 0.95, 1.0], sz: 2.1 },
      alnitak: { pt: toSkyCoord(-24.5, 6.2), col: [0.85, 0.95, 1.0], sz: 2.4 },
      alnilam: { pt: toSkyCoord(-27.5, 6.0), col: [0.9, 0.95, 1.0], sz: 2.5 },
      mintaka: { pt: toSkyCoord(-30.5, 5.8), col: [0.85, 0.95, 1.0], sz: 2.4 }
    };
    const orionLines = [
      [orionStars.betelgeuse.pt, orionStars.bellatrix.pt],
      [orionStars.bellatrix.pt, orionStars.rigel.pt],
      [orionStars.rigel.pt, orionStars.saiph.pt],
      [orionStars.saiph.pt, orionStars.betelgeuse.pt],
      [orionStars.betelgeuse.pt, orionStars.meissa.pt],
      [orionStars.bellatrix.pt, orionStars.meissa.pt],
      [orionStars.alnitak.pt, orionStars.alnilam.pt],
      [orionStars.alnilam.pt, orionStars.mintaka.pt],
      [orionStars.betelgeuse.pt, orionStars.alnitak.pt],
      [orionStars.rigel.pt, orionStars.mintaka.pt]
    ];
    createConstellationTag('[ ✦ ORIONE ]', -27.5, -8.0);

    // 2. ORSA MAGGIORE (Ursa Major / Grande Carro)
    const ursaStars = {
      dubhe: { pt: toSkyCoord(41.5, 36.0), col: [1.0, 0.92, 0.80], sz: 2.7 },
      merak: { pt: toSkyCoord(39.5, 30.0), col: [0.9, 0.95, 1.0], sz: 2.5 },
      phecda: { pt: toSkyCoord(47.5, 27.5), col: [0.9, 0.95, 1.0], sz: 2.4 },
      megrez: { pt: toSkyCoord(49.5, 33.5), col: [0.9, 0.95, 1.0], sz: 2.2 },
      alioth: { pt: toSkyCoord(57.5, 32.5), col: [0.9, 0.95, 1.0], sz: 2.7 },
      mizar: { pt: toSkyCoord(64.5, 30.5), col: [0.9, 0.95, 1.0], sz: 2.5 },
      alkaid: { pt: toSkyCoord(71.5, 26.5), col: [0.85, 0.95, 1.0], sz: 2.7 }
    };
    const ursaLines = [
      [ursaStars.merak.pt, ursaStars.dubhe.pt],
      [ursaStars.dubhe.pt, ursaStars.megrez.pt],
      [ursaStars.megrez.pt, ursaStars.phecda.pt],
      [ursaStars.phecda.pt, ursaStars.merak.pt],
      [ursaStars.megrez.pt, ursaStars.alioth.pt],
      [ursaStars.alioth.pt, ursaStars.mizar.pt],
      [ursaStars.mizar.pt, ursaStars.alkaid.pt]
    ];
    createConstellationTag('[ ✦ ORSA MAGGIORE ]', 45.0, 41.0);

    // 3. CASSIOPEA (Cassiopeia / La 'W' Celeste)
    const cassioStars = {
      caph: { pt: toSkyCoord(-136.0, 39.0), col: [1.0, 0.95, 0.9], sz: 2.5 },
      schedar: { pt: toSkyCoord(-142.0, 35.0), col: [1.0, 0.85, 0.7], sz: 2.6 },
      navi: { pt: toSkyCoord(-148.0, 40.0), col: [0.85, 0.95, 1.0], sz: 2.7 },
      ruchbah: { pt: toSkyCoord(-154.0, 36.0), col: [0.9, 0.95, 1.0], sz: 2.4 },
      segin: { pt: toSkyCoord(-160.0, 39.0), col: [0.9, 0.95, 1.0], sz: 2.3 }
    };
    const cassioLines = [
      [cassioStars.caph.pt, cassioStars.schedar.pt],
      [cassioStars.schedar.pt, cassioStars.navi.pt],
      [cassioStars.navi.pt, cassioStars.ruchbah.pt],
      [cassioStars.ruchbah.pt, cassioStars.segin.pt]
    ];
    createConstellationTag('[ ✦ CASSIOPEA ]', -148.0, 31.0);

    // 4. CIGNO (Cygnus / Croce del Nord)
    const cygnusStars = {
      deneb: { pt: toSkyCoord(3.5, 45.0), col: [0.95, 0.98, 1.0], sz: 3.1 },
      sadr: { pt: toSkyCoord(5.5, 36.0), col: [1.0, 0.95, 0.88], sz: 2.6 },
      albireo: { pt: toSkyCoord(7.5, 24.0), col: [1.0, 0.85, 0.62], sz: 2.4 },
      gienah: { pt: toSkyCoord(-5.0, 35.0), col: [1.0, 0.95, 1.0], sz: 2.5 },
      deltaCygni: { pt: toSkyCoord(15.5, 37.0), col: [0.9, 0.95, 1.0], sz: 2.4 }
    };
    const cygnusLines = [
      [cygnusStars.albireo.pt, cygnusStars.sadr.pt],
      [cygnusStars.sadr.pt, cygnusStars.deneb.pt],
      [cygnusStars.gienah.pt, cygnusStars.sadr.pt],
      [cygnusStars.sadr.pt, cygnusStars.deltaCygni.pt]
    ];
    createConstellationTag('[ ✦ CIGNO ]', 5.5, 50.0);

    // 5. TORO & PLEIADI (Taurus)
    const taurusStars = {
      aldebaran: { pt: toSkyCoord(-58.0, 17.0), col: [1.0, 0.48, 0.22], sz: 3.4 },
      elnath: { pt: toSkyCoord(-53.0, 28.0), col: [0.9, 0.95, 1.0], sz: 2.5 },
      tianguan: { pt: toSkyCoord(-49.0, 19.0), col: [0.9, 0.95, 1.0], sz: 2.3 },
      hyades1: { pt: toSkyCoord(-62.0, 15.0), col: [1.0, 0.92, 0.80], sz: 2.1 },
      hyades2: { pt: toSkyCoord(-64.0, 19.0), col: [1.0, 0.92, 0.80], sz: 2.1 }
    };
    const taurusLines = [
      [taurusStars.hyades1.pt, taurusStars.aldebaran.pt],
      [taurusStars.hyades2.pt, taurusStars.aldebaran.pt],
      [taurusStars.aldebaran.pt, taurusStars.elnath.pt],
      [taurusStars.aldebaran.pt, taurusStars.tianguan.pt]
    ];
    createConstellationTag('[ ✦ TORO & PLEIADI ]', -60.0, 11.0);

    // Assemblaggio vertici linee delle costellazioni
    const allConstLines = [
      ...orionLines,
      ...ursaLines,
      ...cassioLines,
      ...cygnusLines,
      ...taurusLines
    ];
    const constLinePositions = new Float32Array(allConstLines.length * 6);
    allConstLines.forEach((pair, idx) => {
      constLinePositions[idx * 6] = pair[0].x;
      constLinePositions[idx * 6 + 1] = pair[0].y;
      constLinePositions[idx * 6 + 2] = pair[0].z;
      constLinePositions[idx * 6 + 3] = pair[1].x;
      constLinePositions[idx * 6 + 4] = pair[1].y;
      constLinePositions[idx * 6 + 5] = pair[1].z;
    });
    const constLineGeo = new THREE.BufferGeometry();
    constLineGeo.setAttribute('position', new THREE.BufferAttribute(constLinePositions, 3));
    const constLineMat = new THREE.LineBasicMaterial({
      color: 0x4fc3f7,
      transparent: true,
      opacity: 0.40,
      depthWrite: false,
      fog: false
    });
    const constLineSegments = new THREE.LineSegments(constLineGeo, constLineMat);
    constellationsGroup.add(constLineSegments);

    // Assemblaggio stelle delle costellazioni (Punti luminosi dedicati)
    const allConstStars = [
      ...Object.values(orionStars),
      ...Object.values(ursaStars),
      ...Object.values(cassioStars),
      ...Object.values(cygnusStars),
      ...Object.values(taurusStars)
    ];
    const constStarPositions = new Float32Array(allConstStars.length * 3);
    const constStarColors = new Float32Array(allConstStars.length * 3);
    allConstStars.forEach((st, idx) => {
      constStarPositions[idx * 3] = st.pt.x;
      constStarPositions[idx * 3 + 1] = st.pt.y;
      constStarPositions[idx * 3 + 2] = st.pt.z;
      constStarColors[idx * 3] = st.col[0];
      constStarColors[idx * 3 + 1] = st.col[1];
      constStarColors[idx * 3 + 2] = st.col[2];
    });
    const constStarGeo = new THREE.BufferGeometry();
    constStarGeo.setAttribute('position', new THREE.BufferAttribute(constStarPositions, 3));
    constStarGeo.setAttribute('color', new THREE.BufferAttribute(constStarColors, 3));
    const constStarMat = new THREE.PointsMaterial({
      size: 2.8,
      map: diffractionStarTex,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false
    });
    const constStarPoints = new THREE.Points(constStarGeo, constStarMat);
    constellationsGroup.add(constStarPoints);

    scene.add(constellationsGroup);

    // =========================================================================
    // 4C. Sistema Planetario Realistico Visibile dall'Osservatorio della Navicella
    // =========================================================================
    const celestialGroup = new THREE.Group();

    // Illuminazione solare radente per i pianeti (Giorno / Notte planetaria)
    const planetSunLight = new THREE.DirectionalLight(0xfff6ea, 2.2);
    planetSunLight.position.set(-70, 45, -45);
    celestialGroup.add(planetSunLight);

    const planetAmbientLight = new THREE.AmbientLight(0x0a1224, 0.45);
    celestialGroup.add(planetAmbientLight);

    // -------------------------------------------------------------------------
    // PIANETA 1: TERRA NOVA (Blue Marble con oceani, vegetazione, nubi e Luna)
    // -------------------------------------------------------------------------
    const terraGroup = new THREE.Group();
    terraGroup.position.set(-78, 14, -86);

    const terraCanvas = document.createElement('canvas');
    terraCanvas.width = 2048;
    terraCanvas.height = 1024;
    const tctx = terraCanvas.getContext('2d');
    if (tctx) {
      // Oceani profondi blu zaffiro con gradiente batimetrico
      const seaGrad = tctx.createLinearGradient(0, 0, 0, 1024);
      seaGrad.addColorStop(0, '#0a1d3b');
      seaGrad.addColorStop(0.35, '#0e2954');
      seaGrad.addColorStop(0.50, '#11356b');
      seaGrad.addColorStop(0.65, '#0e2954');
      seaGrad.addColorStop(1, '#0a1d3b');
      tctx.fillStyle = seaGrad;
      tctx.fillRect(0, 0, 2048, 1024);

      // Coste e barriere coralline turchesi
      tctx.fillStyle = '#1e6f96';
      tctx.beginPath();
      tctx.ellipse(540, 480, 260, 180, 0.2, 0, Math.PI * 2);
      tctx.ellipse(1280, 420, 310, 210, -0.15, 0, Math.PI * 2);
      tctx.ellipse(1560, 680, 180, 140, 0.1, 0, Math.PI * 2);
      tctx.fill();

      // Masse continentali verdi, savane e catene montuose
      tctx.fillStyle = '#2d6335';
      tctx.beginPath();
      tctx.ellipse(530, 470, 240, 160, 0.2, 0, Math.PI * 2);
      tctx.ellipse(1270, 410, 290, 190, -0.15, 0, Math.PI * 2);
      tctx.ellipse(1550, 670, 160, 120, 0.1, 0, Math.PI * 2);
      tctx.fill();

      // Rilievi montuosi e terre alte dorate/ambrate
      tctx.fillStyle = '#857348';
      tctx.beginPath();
      tctx.ellipse(510, 450, 160, 90, 0.2, 0, Math.PI * 2);
      tctx.ellipse(1290, 390, 200, 110, -0.1, 0, Math.PI * 2);
      tctx.fill();

      // Calotta polare artica e antartica di ghiaccio candido
      tctx.fillStyle = '#f8fbff';
      tctx.beginPath();
      tctx.ellipse(1024, 40, 1024, 70, 0, 0, Math.PI * 2);
      tctx.ellipse(1024, 984, 1024, 80, 0, 0, Math.PI * 2);
      tctx.fill();
    }
    const terraTex = new THREE.CanvasTexture(terraCanvas);
    terraTex.minFilter = THREE.LinearFilter;
    terraTex.magFilter = THREE.LinearFilter;

    const terraGeo = new THREE.SphereGeometry(12.5, 48, 36);
    const terraMat = new THREE.MeshStandardMaterial({
      map: terraTex,
      roughness: 0.70,
      metalness: 0.05
    });
    const terraMesh = new THREE.Mesh(terraGeo, terraMat);
    terraGroup.add(terraMesh);

    // Secondo strato: Nubi meteorologiche cicloniche rotanti
    const cloudCanvas = document.createElement('canvas');
    cloudCanvas.width = 2048;
    cloudCanvas.height = 1024;
    const cloudCtx = cloudCanvas.getContext('2d');
    if (cloudCtx) {
      cloudCtx.clearRect(0, 0, 2048, 1024);
      cloudCtx.fillStyle = 'rgba(255, 255, 255, 0.75)';
      // Spirali cicloniche e bande nuvolose equatoriali
      for (let i = 0; i < 28; i++) {
        const cx = (i * 74 + 80) % 2048;
        const cy = 200 + ((i * 127) % 624);
        const rx = 80 + (i % 5) * 22;
        const ry = 28 + (i % 3) * 16;
        cloudCtx.beginPath();
        cloudCtx.ellipse(cx, cy, rx, ry, (i * 0.35), 0, Math.PI * 2);
        cloudCtx.fill();
      }
    }
    const cloudTex = new THREE.CanvasTexture(cloudCanvas);
    const terraCloudsGeo = new THREE.SphereGeometry(12.72, 48, 36);
    const terraCloudsMat = new THREE.MeshStandardMaterial({
      map: cloudTex,
      transparent: true,
      opacity: 0.70,
      depthWrite: false
    });
    const terraCloudsMesh = new THREE.Mesh(terraCloudsGeo, terraCloudsMat);
    terraGroup.add(terraCloudsMesh);

    // Guscio di scattering atmosferico di Rayleigh (Cyan/Azzurro luminescente)
    const terraAtmoGeo = new THREE.SphereGeometry(13.15, 48, 36);
    const terraAtmoMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          vNormal = normalize(normalMatrix * normal);
          vViewDir = normalize(-mvPosition.xyz);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          float rim = 1.0 - max(dot(vViewDir, vNormal), 0.0);
          float alpha = pow(rim, 3.0);
          vec3 atmoColor = mix(vec3(0.0, 0.65, 1.0), vec3(0.85, 0.95, 1.0), rim);
          gl_FragColor = vec4(atmoColor, alpha * 0.92);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false
    });
    const terraAtmoMesh = new THREE.Mesh(terraAtmoGeo, terraAtmoMat);
    terraGroup.add(terraAtmoMesh);

    // Luna in orbita a Terra Nova
    const lunaTerraCanvas = document.createElement('canvas');
    lunaTerraCanvas.width = 512;
    lunaTerraCanvas.height = 256;
    const ltctx = lunaTerraCanvas.getContext('2d');
    if (ltctx) {
      ltctx.fillStyle = '#b5bac2';
      ltctx.fillRect(0, 0, 512, 256);
      ltctx.fillStyle = '#677180';
      // Mari lunari basaltici
      ltctx.beginPath();
      ltctx.ellipse(160, 110, 65, 45, 0.3, 0, Math.PI * 2);
      ltctx.ellipse(280, 150, 75, 55, -0.2, 0, Math.PI * 2);
      ltctx.ellipse(390, 95, 50, 35, 0.1, 0, Math.PI * 2);
      ltctx.fill();
    }
    const lunaTerraTex = new THREE.CanvasTexture(lunaTerraCanvas);
    const lunaTerraGeo = new THREE.SphereGeometry(2.7, 32, 24);
    const lunaTerraMat = new THREE.MeshStandardMaterial({
      map: lunaTerraTex,
      roughness: 0.88,
      metalness: 0.02
    });
    const lunaTerraMesh = new THREE.Mesh(lunaTerraGeo, lunaTerraMat);
    lunaTerraMesh.position.set(24, 7, -12);
    terraGroup.add(lunaTerraMesh);

    celestialGroup.add(terraGroup);

    // -------------------------------------------------------------------------
    // PIANETA 2: KRONOS (Gigante gassoso dorato con ampi anelli ghiacciati)
    // -------------------------------------------------------------------------
    const kronosGroup = new THREE.Group();
    kronosGroup.position.set(82, 12, -92);

    const kronosCanvas = document.createElement('canvas');
    kronosCanvas.width = 2048;
    kronosCanvas.height = 1024;
    const kctx = kronosCanvas.getContext('2d');
    if (kctx) {
      const kGrad = kctx.createLinearGradient(0, 0, 0, 1024);
      kGrad.addColorStop(0, '#1a1f33');
      kGrad.addColorStop(0.18, '#3d4463');
      kGrad.addColorStop(0.35, '#c7925e');
      kGrad.addColorStop(0.48, '#f3d9b8');
      kGrad.addColorStop(0.52, '#a6643c');
      kGrad.addColorStop(0.68, '#ebd0a5');
      kGrad.addColorStop(0.85, '#3e4668');
      kGrad.addColorStop(1, '#161a2d');
      kctx.fillStyle = kGrad;
      kctx.fillRect(0, 0, 2048, 1024);

      // Micro-bande atmosferiche
      for (let y = 50; y < 980; y += 14) {
        kctx.fillStyle = y % 28 === 0 ? 'rgba(255, 240, 220, 0.14)' : 'rgba(12, 18, 36, 0.16)';
        kctx.fillRect(0, y, 2048, 6);
      }

      // Grande Macchia Ovale di ammoniaca e idrogeno
      kctx.fillStyle = '#b34d2c';
      kctx.beginPath();
      kctx.ellipse(820, 560, 120, 58, 0.1, 0, Math.PI * 2);
      kctx.fill();
    }
    const kronosTex = new THREE.CanvasTexture(kronosCanvas);
    kronosTex.minFilter = THREE.LinearFilter;
    kronosTex.magFilter = THREE.LinearFilter;

    const kronosGeo = new THREE.SphereGeometry(14.5, 48, 36);
    const kronosMat = new THREE.MeshStandardMaterial({
      map: kronosTex,
      roughness: 0.65,
      metalness: 0.05
    });
    const kronosMesh = new THREE.Mesh(kronosGeo, kronosMat);
    kronosGroup.add(kronosMesh);

    // Sistema di Anelli Ghiacciati con Divisione di Cassini
    const ringCanvas = document.createElement('canvas');
    ringCanvas.width = 1024;
    ringCanvas.height = 64;
    const rctx = ringCanvas.getContext('2d');
    if (rctx) {
      const rGrad = rctx.createLinearGradient(0, 0, 1024, 0);
      rGrad.addColorStop(0, 'rgba(0, 0, 0, 0)');
      rGrad.addColorStop(0.10, 'rgba(215, 205, 190, 0.75)');
      rGrad.addColorStop(0.40, 'rgba(240, 230, 215, 0.92)');
      rGrad.addColorStop(0.54, 'rgba(6, 10, 18, 0.05)'); // Divisione di Cassini netta
      rGrad.addColorStop(0.60, 'rgba(205, 195, 180, 0.78)');
      rGrad.addColorStop(0.88, 'rgba(175, 168, 155, 0.42)');
      rGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      rctx.fillStyle = rGrad;
      rctx.fillRect(0, 0, 1024, 64);
    }
    const ringTex = new THREE.CanvasTexture(ringCanvas);
    const ringGeo = new THREE.RingGeometry(18.0, 33.5, 96);
    const ringMat = new THREE.MeshBasicMaterial({
      map: ringTex,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.90,
      depthWrite: false
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = Math.PI / 2.35;
    ringMesh.rotation.z = -0.32;
    kronosGroup.add(ringMesh);

    celestialGroup.add(kronosGroup);

    // -------------------------------------------------------------------------
    // PIANETA 3: ARES (Pianeta Rosso / Marte con canyon e calotta polare)
    // -------------------------------------------------------------------------
    const aresCanvas = document.createElement('canvas');
    aresCanvas.width = 1024;
    aresCanvas.height = 512;
    const actx = aresCanvas.getContext('2d');
    if (actx) {
      actx.fillStyle = '#9c4323';
      actx.fillRect(0, 0, 1024, 512);

      // Terre alte di regolite ferrosa e canyon scuri (Valles Marineris)
      actx.fillStyle = '#521d0d';
      actx.beginPath();
      actx.ellipse(450, 260, 280, 80, -0.15, 0, Math.PI * 2);
      actx.ellipse(780, 310, 190, 60, 0.2, 0, Math.PI * 2);
      actx.fill();

      // Calotta polare di ghiaccio candido brillante
      actx.fillStyle = '#f4f8ff';
      actx.beginPath();
      actx.ellipse(512, 18, 512, 38, 0, 0, Math.PI * 2);
      actx.fill();
    }
    const aresTex = new THREE.CanvasTexture(aresCanvas);
    const aresGeo = new THREE.SphereGeometry(7.5, 40, 28);
    const aresMat = new THREE.MeshStandardMaterial({
      map: aresTex,
      roughness: 0.85,
      metalness: 0.05
    });
    const aresMesh = new THREE.Mesh(aresGeo, aresMat);
    aresMesh.position.set(92, -8, 64);
    celestialGroup.add(aresMesh);

    // -------------------------------------------------------------------------
    // PIANETA 4: LUNA / SELENE (Satellite craterizzato ad alto contrasto nello Zenith)
    // -------------------------------------------------------------------------
    const lunaZenithCanvas = document.createElement('canvas');
    lunaZenithCanvas.width = 1024;
    lunaZenithCanvas.height = 512;
    const lzctx = lunaZenithCanvas.getContext('2d');
    if (lzctx) {
      lzctx.fillStyle = '#c5ccd6';
      lzctx.fillRect(0, 0, 1024, 512);

      // Mari basaltici scuri ad alto contrasto
      lzctx.fillStyle = '#4c5563';
      lzctx.beginPath();
      lzctx.ellipse(320, 220, 130, 90, 0.2, 0, Math.PI * 2);
      lzctx.ellipse(560, 290, 150, 110, -0.15, 0, Math.PI * 2);
      lzctx.ellipse(780, 200, 110, 75, 0.1, 0, Math.PI * 2);
      lzctx.fill();

      // Raggi di crateri da impatto (Tycho)
      lzctx.fillStyle = '#ffffff';
      lzctx.beginPath();
      lzctx.arc(420, 380, 16, 0, Math.PI * 2);
      lzctx.fill();
    }
    const lunaZenithTex = new THREE.CanvasTexture(lunaZenithCanvas);
    const lunaZenithGeo = new THREE.SphereGeometry(5.5, 36, 24);
    const lunaZenithMat = new THREE.MeshStandardMaterial({
      map: lunaZenithTex,
      roughness: 0.90,
      metalness: 0.02
    });
    const lunaZenithMesh = new THREE.Mesh(lunaZenithGeo, lunaZenithMat);
    lunaZenithMesh.position.set(-26, 44, -94);
    celestialGroup.add(lunaZenithMesh);

    scene.add(celestialGroup);

    // =========================================================================
    // 5. Texture Dinamiche per gli Schermi della Navicella
    // =========================================================================
    const animatedDisplays = [];

    const createBridgeScreenTexture = (roleColorHex, screenType = 'code') => {
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 320;
      const ctx = canvas.getContext('2d');
      const texture = new THREE.CanvasTexture(canvas);

      const updateScreen = (time) => {
        if (!ctx) return;
        ctx.fillStyle = '#060a17';
        ctx.fillRect(0, 0, 512, 320);

        // Griglia radar di sfondo
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        for (let x = 0; x < 512; x += 32) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, 320);
          ctx.stroke();
        }
        for (let y = 0; y < 320; y += 32) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(512, y);
          ctx.stroke();
        }

        // Bordo schermo HUD
        ctx.strokeStyle = roleColorHex || '#00d2ff';
        ctx.lineWidth = 4;
        ctx.strokeRect(4, 4, 504, 312);

        // Header postazione di bordo
        ctx.fillStyle = roleColorHex || '#00d2ff';
        ctx.fillRect(4, 4, 504, 28);
        ctx.fillStyle = '#060a17';
        ctx.font = 'bold 14px monospace';
        ctx.fillText('STARSHIP BRIDGE // STATION TERMINAL', 14, 23);

        if (screenType === 'code') {
          ctx.fillStyle = roleColorHex || '#00d2ff';
          ctx.font = '12px monospace';
          const lineOffset = Math.floor(time * 6) % 8;
          const codeSnippets = [
            'BRIDGE_STATUS: WARP_DRIVE_ONLINE (100%)',
            'COMM_ARRAY: MULTI-AGENT SWARM ACTIVE',
            'NAV_COMPUTER: VECTOR [X: +14.2, Y: 0.0, Z: -22.8]',
            'LIFE_SUPPORT: OPTIMAL // PRESSURE 1.0 ATM',
            'DEFLECTOR_SHIELDS: HARMONIC 99.4%',
            'KERNEL_CORE: KICAD & RUST BUS SYNCED',
            'TELEMETRY: ALL STATIONS ONLINE // NO ERRORS',
            'DISPATCH: READY FOR USER DIRECTIVES'
          ];
          for (let i = 0; i < 11; i++) {
            const codeIndex = (i + lineOffset) % codeSnippets.length;
            ctx.fillStyle = i === 10 ? '#ffffff' : 'rgba(0, 210, 255, 0.88)';
            ctx.fillText(`> ${codeSnippets[codeIndex]}`, 16, 58 + i * 24);
          }
        } else {
          // Onde e frequenze della console
          ctx.strokeStyle = roleColorHex || '#ff007a';
          ctx.lineWidth = 3;
          ctx.beginPath();
          for (let x = 16; x < 496; x += 4) {
            const wave = Math.sin(x * 0.03 + time * 5) * 45 + Math.cos(x * 0.08 - time * 3) * 20;
            const y = 160 + wave;
            if (x === 16) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.stroke();

          for (let b = 0; b < 18; b++) {
            const barH = Math.abs(Math.sin(time * 4 + b * 0.6)) * 60 + 10;
            ctx.fillStyle = roleColorHex || '#ff007a';
            ctx.fillRect(30 + b * 26, 280 - barH, 16, barH);
          }
        }

        texture.needsUpdate = true;
      };

      animatedDisplays.push(updateScreen);
      return texture;
    };

    // =========================================================================
    // 6. Postazioni di Comando degli Agenti (Bridge Officer Workstations)
    // =========================================================================
    // Generazione al 100% dinamica: supporta tutti i ruoli installati (15+ ufficiali)
    const activeRoles = roles || [];
    const stationsCount = activeRoles.length;
    const stationRadius = stationsCount > 10 ? 13.5 : 12.0;

    const interactiveMeshes = [];
    const stationDataList = [];
    const createdBadges = [];

    for (let i = 0; i < stationsCount; i++) {
      const role = activeRoles[i];
      const angle = (i / stationsCount) * Math.PI * 2 - Math.PI / 2;

      const posX = Math.cos(angle) * stationRadius;
      const posZ = Math.sin(angle) * stationRadius;
      const posY = -2.0;

      const stationGroup = new THREE.Group();
      stationGroup.position.set(posX, posY, posZ);
      stationGroup.rotation.y = -angle - Math.PI / 2;

      const roleColorHex = role.color || '#00d2ff';
      const roleThreeColor = new THREE.Color(roleColorHex);

      // Canaline luminose che collegano il tavolo tattico centrale alla postazione
      const conduitGeo = new THREE.BoxGeometry(0.14, 0.04, stationRadius - 4.2);
      const conduitMat = new THREE.MeshBasicMaterial({
        color: roleThreeColor,
        blending: THREE.AdditiveBlending
      });
      const conduit = new THREE.Mesh(conduitGeo, conduitMat);
      conduit.position.set(
        Math.cos(angle) * ((stationRadius + 4.2) / 2),
        -1.96,
        Math.sin(angle) * ((stationRadius + 4.2) / 2)
      );
      conduit.rotation.y = -angle + Math.PI / 2;
      shipGroup.add(conduit);

      // Pedana circolare della postazione
      const podGeo = new THREE.CylinderGeometry(2.4, 2.6, 0.22, 32);
      const podMat = new THREE.MeshStandardMaterial({
        color: isLight ? 0xe2e8f0 : 0x0f172a,
        metalness: 0.75,
        roughness: 0.3
      });
      const podMesh = new THREE.Mesh(podGeo, podMat);
      podMesh.position.y = 0.11;
      stationGroup.add(podMesh);

      // Sotto-scocca neon della postazione
      const podGlowGeo = new THREE.RingGeometry(2.4, 2.55, 32);
      const podGlowMat = new THREE.MeshBasicMaterial({
        color: roleThreeColor,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      });
      const podGlow = new THREE.Mesh(podGlowGeo, podGlowMat);
      podGlow.rotation.x = -Math.PI / 2;
      podGlow.position.y = 0.23;
      stationGroup.add(podGlow);

      // Scrivania / Console Curva di Bordo
      const deskGeo = new THREE.BoxGeometry(2.8, 0.95, 1.2);
      const deskMat = new THREE.MeshStandardMaterial({
        color: isLight ? 0xf8fafc : 0x111c38,
        metalness: 0.65,
        roughness: 0.35
      });
      const desk = new THREE.Mesh(deskGeo, deskMat);
      desk.position.set(0, 0.58, -0.45);
      stationGroup.add(desk);

      // Trim neon perimetrale della console
      const deskTrimGeo = new THREE.BoxGeometry(2.86, 0.05, 1.26);
      const deskTrimMat = new THREE.MeshBasicMaterial({ color: roleThreeColor });
      const deskTrim = new THREE.Mesh(deskTrimGeo, deskTrimMat);
      deskTrim.position.set(0, 1.05, -0.45);
      stationGroup.add(deskTrim);

      // Tastiera laser olografica
      const keyboardCanvas = document.createElement('canvas');
      keyboardCanvas.width = 256;
      keyboardCanvas.height = 128;
      const kctx = keyboardCanvas.getContext('2d');
      if (kctx) {
        kctx.fillStyle = '#060914';
        kctx.fillRect(0, 0, 256, 128);
        kctx.strokeStyle = roleColorHex;
        kctx.lineWidth = 2;
        kctx.strokeRect(4, 4, 248, 120);
        for (let r = 0; r < 4; r++) {
          for (let k = 0; k < 12; k++) {
            kctx.fillStyle = (r + k) % 3 === 0 ? roleColorHex : 'rgba(0, 210, 255, 0.35)';
            kctx.fillRect(14 + k * 19, 14 + r * 25, 15, 18);
          }
        }
      }
      const keyboardTex = new THREE.CanvasTexture(keyboardCanvas);
      const keyboardMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(1.2, 0.6),
        new THREE.MeshBasicMaterial({ map: keyboardTex, side: THREE.DoubleSide })
      );
      keyboardMesh.rotation.x = -Math.PI / 2;
      keyboardMesh.position.set(0, 1.08, -0.2);
      stationGroup.add(keyboardMesh);

      // Monitor Olografici Multipli ad Alta Definizione
      const mainScreenTex = createBridgeScreenTexture(roleColorHex, 'code');
      const sideScreenTex = createBridgeScreenTexture(roleColorHex, 'wave');

      // Stand metallico monitor
      const mainStand = new THREE.Mesh(
        new THREE.CylinderGeometry(0.06, 0.06, 0.6, 8),
        new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.9, roughness: 0.2 })
      );
      mainStand.position.set(0, 1.35, -0.6);
      stationGroup.add(mainStand);

      // Monitor Centrale Principale
      const mainMon = new THREE.Mesh(
        new THREE.PlaneGeometry(1.5, 0.95),
        new THREE.MeshBasicMaterial({ map: mainScreenTex, side: THREE.DoubleSide })
      );
      mainMon.position.set(0, 1.82, -0.58);
      stationGroup.add(mainMon);

      // Monitor Laterale Sinistro a 28°
      const leftMon = new THREE.Mesh(
        new THREE.PlaneGeometry(0.95, 0.8),
        new THREE.MeshBasicMaterial({ map: sideScreenTex, side: THREE.DoubleSide })
      );
      leftMon.position.set(-1.25, 1.76, -0.42);
      leftMon.rotation.y = Math.PI / 6.5;
      stationGroup.add(leftMon);

      // Monitor Laterale Destro a -28°
      const rightMon = new THREE.Mesh(
        new THREE.PlaneGeometry(0.95, 0.8),
        new THREE.MeshBasicMaterial({ map: sideScreenTex, side: THREE.DoubleSide })
      );
      rightMon.position.set(1.25, 1.76, -0.42);
      rightMon.rotation.y = -Math.PI / 6.5;
      stationGroup.add(rightMon);

      // Poltrona di Comando Gaming
      const chairGroup = new THREE.Group();
      chairGroup.position.set(0, 0, 0.65);

      const chairMat = new THREE.MeshStandardMaterial({
        color: isLight ? 0x94a3b8 : 0x090e1c,
        metalness: 0.5,
        roughness: 0.5
      });
      const seat = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.14, 0.8), chairMat);
      seat.position.y = 0.65;
      chairGroup.add(seat);

      const back = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.25, 0.14), chairMat);
      back.position.set(0, 1.28, 0.38);
      chairGroup.add(back);

      const spineLight = new THREE.Mesh(
        new THREE.BoxGeometry(0.12, 1.15, 0.05),
        new THREE.MeshBasicMaterial({ color: roleThreeColor, blending: THREE.AdditiveBlending })
      );
      spineLight.position.set(0, 1.28, 0.46);
      chairGroup.add(spineLight);

      stationGroup.add(chairGroup);

      // Modello 3D dell'Agente / Ufficiale di Bordo (Cyber-Mecha Officer)
      const agentFigureGroup = new THREE.Group();
      agentFigureGroup.position.set(0, 0.65, 0.5);

      const torso = new THREE.Mesh(
        new THREE.CylinderGeometry(0.38, 0.3, 0.85, 16),
        new THREE.MeshStandardMaterial({
          color: isLight ? 0x64748b : 0x141e33,
          metalness: 0.7,
          roughness: 0.3
        })
      );
      torso.position.y = 0.6;
      agentFigureGroup.add(torso);

      // Reattore toracico pulsante
      const coreReactor = new THREE.Mesh(
        new THREE.SphereGeometry(0.12, 16, 16),
        new THREE.MeshBasicMaterial({ color: roleThreeColor, blending: THREE.AdditiveBlending })
      );
      coreReactor.position.set(0, 0.72, -0.28);
      agentFigureGroup.add(coreReactor);

      // Braccia e mani mecha rivolte verso la console
      const armMat = new THREE.MeshStandardMaterial({ color: isLight ? 0x94a3b8 : 0x0f182c, metalness: 0.6 });
      const leftArm = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.07, 0.75, 8), armMat);
      leftArm.position.set(-0.42, 0.6, -0.32);
      leftArm.rotation.x = Math.PI / 2.8;
      agentFigureGroup.add(leftArm);

      const rightArm = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.07, 0.75, 8), armMat);
      rightArm.position.set(0.42, 0.6, -0.32);
      rightArm.rotation.x = Math.PI / 2.8;
      agentFigureGroup.add(rightArm);

      const leftHand = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.06, 0.14), new THREE.MeshBasicMaterial({ color: roleThreeColor }));
      leftHand.position.set(-0.35, 0.44, -0.6);
      agentFigureGroup.add(leftHand);

      const rightHand = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.06, 0.14), new THREE.MeshBasicMaterial({ color: roleThreeColor }));
      rightHand.position.set(0.35, 0.44, -0.6);
      agentFigureGroup.add(rightHand);

      // Casco con visore olografico
      const headGroup = new THREE.Group();
      headGroup.position.set(0, 1.25, 0);

      const helmet = new THREE.Mesh(
        new THREE.SphereGeometry(0.26, 20, 20),
        new THREE.MeshStandardMaterial({
          color: isLight ? 0xf8fafc : 0x1e293b,
          metalness: 0.8,
          roughness: 0.25
        })
      );
      headGroup.add(helmet);

      const visor = new THREE.Mesh(
        new THREE.BoxGeometry(0.36, 0.12, 0.18),
        new THREE.MeshBasicMaterial({ color: roleThreeColor, blending: THREE.AdditiveBlending })
      );
      visor.position.set(0, 0.02, -0.2);
      headGroup.add(visor);

      agentFigureGroup.add(headGroup);
      stationGroup.add(agentFigureGroup);

      // =======================================================================
      // 7. SCHEDA OLOGRAFICA DELL'AGENTE AD ALTA VISIBILITÀ (Grande & Ben Leggibile)
      // =======================================================================
      // Scheda essenziale: avatar, nome e ruolo grandi. Le righe piccole
      // (categoria, stato, invito) da lontano diventavano solo rumore.
      const BADGE_W = 512;
      const BADGE_H = 560;
      const badgeCanvas = document.createElement('canvas');
      badgeCanvas.width = BADGE_W;
      badgeCanvas.height = BADGE_H;
      const bctx = badgeCanvas.getContext('2d');
      const avatarCx = BADGE_W / 2;
      const avatarCy = 168;
      const avatarR = 104;
      const textFamily = 'Inter, "Segoe UI", system-ui, sans-serif';

      const drawAvatarRing = () => {
        bctx.save();
        bctx.strokeStyle = roleColorHex;
        bctx.lineWidth = 6;
        bctx.shadowColor = roleColorHex;
        bctx.shadowBlur = 16;
        bctx.beginPath();
        bctx.arc(avatarCx, avatarCy, avatarR, 0, Math.PI * 2);
        bctx.stroke();
        bctx.restore();
      };

      if (bctx) {
        bctx.fillStyle = 'rgba(6, 11, 24, 0.92)';
        bctx.beginPath();
        bctx.roundRect(8, 8, BADGE_W - 16, BADGE_H - 16, 32);
        bctx.fill();

        bctx.save();
        bctx.strokeStyle = roleColorHex;
        bctx.lineWidth = 5;
        bctx.shadowColor = roleColorHex;
        bctx.shadowBlur = 20;
        bctx.stroke();
        bctx.restore();

        // Fascia colorata in alto: identifica la stazione anche quando il testo non si legge
        bctx.save();
        bctx.beginPath();
        bctx.roundRect(8, 8, BADGE_W - 16, BADGE_H - 16, 32);
        bctx.clip();
        const band = bctx.createLinearGradient(0, 0, 0, 120);
        band.addColorStop(0, roleColorHex);
        band.addColorStop(1, 'rgba(6, 11, 24, 0)');
        bctx.globalAlpha = 0.35;
        bctx.fillStyle = band;
        bctx.fillRect(0, 0, BADGE_W, 120);
        bctx.restore();

        bctx.fillStyle = 'rgba(255, 255, 255, 0.06)';
        bctx.beginPath();
        bctx.arc(avatarCx, avatarCy, avatarR, 0, Math.PI * 2);
        bctx.fill();

        bctx.font = `800 84px ${textFamily}`;
        bctx.fillStyle = roleColorHex;
        bctx.textAlign = 'center';
        bctx.textBaseline = 'middle';
        bctx.fillText(roleInitials(role.name), avatarCx, avatarCy + 4);
        drawAvatarRing();

        bctx.textBaseline = 'alphabetic';
        bctx.fillStyle = '#ffffff';
        const nameText = fitText(bctx, role.name || 'Agente', BADGE_W - 64, 56, 34, 800, textFamily);
        bctx.fillText(nameText, avatarCx, 362);

        bctx.fillStyle = roleColorHex;
        const roleText = fitText(bctx, role.title || '', BADGE_W - 64, 32, 24, 700, textFamily);
        bctx.fillText(roleText, avatarCx, 414);

        // Indicatore discreto di interattivita' al posto del grande bottone finto
        bctx.font = `700 24px ${textFamily}`;
        bctx.fillStyle = 'rgba(226, 232, 240, 0.7)';
        bctx.fillText('Clicca per parlare', avatarCx, 490);
      }

      const badgeTex = new THREE.CanvasTexture(badgeCanvas);
      badgeTex.colorSpace = THREE.SRGBColorSpace;
      if (role.image && role.image !== '/images/default.png') {
        const rImg = new Image();
        rImg.crossOrigin = 'anonymous';
        rImg.src = role.image;
        rImg.onload = () => {
          if (!bctx) return;
          bctx.save();
          bctx.beginPath();
          bctx.arc(avatarCx, avatarCy, avatarR, 0, Math.PI * 2);
          bctx.closePath();
          bctx.clip();
          // Ritaglio quadrato centrato: le foto dei ruoli non sono tutte quadrate
          const side = Math.min(rImg.naturalWidth, rImg.naturalHeight);
          const sx = (rImg.naturalWidth - side) / 2;
          const sy = (rImg.naturalHeight - side) / 2;
          bctx.drawImage(rImg, sx, sy, side, side, avatarCx - avatarR, avatarCy - avatarR, avatarR * 2, avatarR * 2);
          bctx.restore();
          drawAvatarRing();
          badgeTex.needsUpdate = true;
        };
      }

      // Calcola le coordinate mondo della scheda per eliminare ogni distorsione da rotazione genitore
      stationGroup.updateMatrixWorld(true);
      const badgeWorldPos = new THREE.Vector3(0, 3.8, -0.4);
      stationGroup.localToWorld(badgeWorldPos);

      badgeTex.minFilter = THREE.LinearMipmapLinearFilter;
      badgeTex.magFilter = THREE.LinearFilter;
      badgeTex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      const badgeGeo = new THREE.PlaneGeometry(2.6, 2.6 * (BADGE_H / BADGE_W));
      const badgeMat = new THREE.MeshBasicMaterial({
        map: badgeTex,
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false,
        // Fuori da nebbia e tone mapping: i colori della scheda restano quelli disegnati
        fog: false,
        toneMapped: false
      });
      const badgeMesh = new THREE.Mesh(badgeGeo, badgeMat);
      badgeMesh.position.copy(badgeWorldPos);
      badgeMesh.renderOrder = 10;
      badgeMesh.userData = { role, stationGroup, posX, posZ, angle };

      // Aggiunta direttamente alla scena (coordinate mondo) per un perfetto allineamento con la vista dell'utente
      scene.add(badgeMesh);
      interactiveMeshes.push(badgeMesh);
      createdBadges.push(badgeMesh);

      // Hitbox interattiva cliccabile per l'intera postazione
      const hitBoxGeo = new THREE.BoxGeometry(3.6, 4.4, 3.2);
      const hitBoxMat = new THREE.MeshBasicMaterial({ visible: false });
      const hitBox = new THREE.Mesh(hitBoxGeo, hitBoxMat);
      hitBox.position.set(0, 2.0, 0.2);
      hitBox.userData = { role, stationGroup, posX, posZ, angle };
      stationGroup.add(hitBox);
      interactiveMeshes.push(hitBox);

      // Prop 3D Tematico Fluttuante sopra la Scheda
      const propGroup = new THREE.Group();
      propGroup.position.set(0, 5.8, -0.4);
      stationGroup.add(propGroup);

      const idLower = (role.id || '').toLowerCase();
      if (idLower.includes('regis') || idLower.includes('dop')) {
        const cam = new THREE.Mesh(
          new THREE.BoxGeometry(0.5, 0.4, 0.35),
          new THREE.MeshStandardMaterial({ color: 0xff007a, metalness: 0.8, roughness: 0.2 })
        );
        const lens = new THREE.Mesh(
          new THREE.CylinderGeometry(0.14, 0.14, 0.3, 16),
          new THREE.MeshBasicMaterial({ color: 0x00f0ff })
        );
        lens.rotation.x = Math.PI / 2;
        lens.position.z = -0.3;
        cam.add(lens);
        propGroup.add(cam);
      } else if (idLower.includes('medic')) {
        const dnaGroup = new THREE.Group();
        for (let j = 0; j < 10; j++) {
          const dy = (j - 5) * 0.11;
          const da = j * 0.65;
          const sA = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 8), new THREE.MeshBasicMaterial({ color: 0x10b981 }));
          sA.position.set(Math.cos(da) * 0.24, dy, Math.sin(da) * 0.24);
          const sB = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 8), new THREE.MeshBasicMaterial({ color: 0x00d2ff }));
          sB.position.set(-Math.cos(da) * 0.24, dy, -Math.sin(da) * 0.24);
          dnaGroup.add(sA);
          dnaGroup.add(sB);
        }
        propGroup.add(dnaGroup);
      } else if (idLower.includes('math') || idLower.includes('professor')) {
        const gyroGroup = new THREE.Group();
        gyroGroup.add(new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), new THREE.MeshBasicMaterial({ color: 0x10b981 })));
        gyroGroup.add(new THREE.Mesh(new THREE.TorusGeometry(0.35, 0.02, 12, 32), new THREE.MeshBasicMaterial({ color: 0x00f0ff })));
        propGroup.add(gyroGroup);
      } else if (idLower.includes('hardware') || idLower.includes('kicad')) {
        const chip = new THREE.Mesh(
          new THREE.BoxGeometry(0.48, 0.1, 0.48),
          new THREE.MeshStandardMaterial({ color: 0x064e3b, metalness: 0.6, roughness: 0.3 })
        );
        propGroup.add(chip);
      } else {
        const tesseractGroup = new THREE.Group();
        tesseractGroup.add(new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.42, 0.42), new THREE.MeshBasicMaterial({ color: roleThreeColor, wireframe: true })));
        tesseractGroup.add(new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.24, 0.24), new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true })));
        propGroup.add(tesseractGroup);
      }

      shipGroup.add(stationGroup);

      stationDataList.push({
        stationGroup,
        headGroup,
        coreReactor,
        leftHand,
        rightHand,
        propGroup,
        badgeMesh,
        hitBox,
        role,
        posX,
        posZ,
        angle
      });
    }

    // =========================================================================
    // 8. Navigazione Telecamera e Volo Fluido (Fly to Agent Station)
    // =========================================================================
    // La telecamera orbita all'interno della plancia (raggio 16.5, finestre a 20.5)
    // garantendo visibilità panoramica totale senza mai uscire dalle pareti della nave
    const defaultCamPos = new THREE.Vector3(0, 5.0, 16.5);
    const defaultLookAt = new THREE.Vector3(0, 0.6, 0);

    let targetCamPos = defaultCamPos.clone();
    let currentLookAt = defaultLookAt.clone();
    let targetLookAt = defaultLookAt.clone();

    // silent: la selezione arriva gia' dal genitore, richiamarlo creerebbe un ciclo
    const flyToAgent = (station, { silent = false } = {}) => {
      if (!station) {
        targetCamPos.copy(defaultCamPos);
        targetLookAt.copy(defaultLookAt);
        if (!silent && onSelectAgentRef.current) onSelectAgentRef.current(null);
        return;
      }

      const offsetDist = 5.4;
      const camX = station.posX - Math.cos(station.angle) * offsetDist;
      const camZ = station.posZ - Math.sin(station.angle) * offsetDist;

      // Camera un po' piu' alta del busto: scheda e ufficiale restano sopra il pannello di dialogo
      targetCamPos.set(camX, 1.3, camZ);
      targetLookAt.set(station.posX, 1.1, station.posZ);

      if (!silent && onSelectAgentRef.current) {
        onSelectAgentRef.current(station.role);
      }
    };

    // Le selezioni esterne (chip, menu, radar) arrivano come id: prima venivano
    // tradotte in una stazione fittizia all'origine e la camera puntava il centro.
    flyToStationRef.current = (roleId) => {
      const match = roleId ? stationDataList.find(st => st.role.id === roleId) : null;
      flyToAgent(match || null, { silent: true });
    };

    if (selectedAgentIdRef.current) {
      const match = stationDataList.find(st => st.role.id === selectedAgentIdRef.current);
      if (match) flyToAgent(match, { silent: true });
    }

    // =========================================================================
    // 9. Mouse Orbit & Zoom a 360° All'Interno del Command Bridge
    // =========================================================================
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let orbitAngle = 0;
    let orbitElevation = 5.0;
    let orbitDist = 16.5;

    const onMouseDown = (e) => {
      if (!interactive) return;
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const raycaster = new THREE.Raycaster();
    const mouseNorm = new THREE.Vector2(-1000, -1000);
    let hoveredHitBox = null;

    const onMouseMove = (e) => {
      if (!interactive) return;
      const rect = container.getBoundingClientRect();
      mouseNorm.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseNorm.y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);

      if (isDragging) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;

        orbitAngle -= deltaX * 0.005;
        // Elevazione contenuta entro i limiti della mezza sfera
        orbitElevation = Math.max(1.2, Math.min(11.0, orbitElevation + deltaY * 0.02));

        targetCamPos.set(
          Math.sin(orbitAngle) * orbitDist,
          orbitElevation,
          Math.cos(orbitAngle) * orbitDist
        );
        targetLookAt.set(0, 0.6, 0);
      }

      raycaster.setFromCamera(mouseNorm, camera);
      const intersects = raycaster.intersectObjects(interactiveMeshes).filter(hit => hit.object.visible);

      if (intersects.length > 0) {
        const hit = intersects[0].object;
        if (hoveredHitBox !== hit) {
          hoveredHitBox = hit;
          const r = hit.userData?.role;
          if (r) setHoveredAgent(r);
          container.style.cursor = 'pointer';
        }
      } else {
        if (hoveredHitBox) {
          hoveredHitBox = null;
          setHoveredAgent(null);
          container.style.cursor = isDragging ? 'grabbing' : 'default';
        }
      }
    };

    const onClick = (e) => {
      if (!interactive) return;
      raycaster.setFromCamera(mouseNorm, camera);
      const intersects = raycaster.intersectObjects(interactiveMeshes).filter(hit => hit.object.visible);
      if (intersects.length > 0) {
        const hit = intersects[0].object;
        const r = hit.userData?.role;
        const matchedStation = stationDataList.find(s => s.role.id === r.id);
        if (matchedStation) {
          flyToAgent(matchedStation);
        }
      }
    };

    const onWheel = (e) => {
      if (!interactive) return;
      // Limite zoom: min 6.5 (primo piano plancia), max 18.0 (panoramica totale all'interno delle vetrate a 20.5)
      orbitDist = Math.max(6.5, Math.min(18.0, orbitDist + e.deltaY * 0.012));
      if (!selectedAgentIdRef.current) {
        targetCamPos.set(
          Math.sin(orbitAngle) * orbitDist,
          orbitElevation,
          Math.cos(orbitAngle) * orbitDist
        );
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mouseup', onMouseUp);
    container.addEventListener('click', onClick);
    container.addEventListener('wheel', onWheel, { passive: true });

    const onResize = () => {
      if (!container) return;
      width = container.clientWidth || window.innerWidth;
      height = container.clientHeight || window.innerHeight;
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.fov = fovForAspect(camera.aspect);
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    // Il contenitore cambia larghezza anche senza resize della finestra
    // (sidebar aperta o chiusa, pannelli affiancati): serve osservarlo direttamente.
    let resizeObserver = null;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(onResize);
      resizeObserver.observe(container);
    }
    window.addEventListener('resize', onResize);

    // =========================================================================
    // 10. Loop di Rendering con Animazioni Navicella
    // =========================================================================
    let animationFrameId;
    const clock = new THREE.Clock();
    const motionClock = new THREE.Clock();
    let lastFrameAt = 0;
    let lastScreensAt = -1;
    const badgeTmp = new THREE.Vector3();

    // Controllo automatico: se nei primi secondi la plancia non arriva a ~28 fps
    // si passa alla modalita' leggera invece di lasciare l'interfaccia a scatti.
    let probeFrames = 0;
    let probeStart = 0;
    let probeDone = quality !== 'auto' || lite;

    const switchToLite = (reason) => {
      if (lite) return;
      lite = true;
      renderer.setPixelRatio(litePixelRatio);
      renderer.setSize(width, height);
      if (onQualityResolvedRef.current) onQualityResolvedRef.current('lite', reason);
    };

    if (onQualityResolvedRef.current) {
      onQualityResolvedRef.current(lite ? 'lite' : 'high', lite && quality === 'auto' ? 'gpu' : 'scelta');
    }

    const smoothstep = (a, b, x) => {
      const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
      return t * t * (3 - 2 * t);
    };

    const animate = (now = 0) => {
      animationFrameId = requestAnimationFrame(animate);

      // In modalita' leggera si disegna a 30 fps: sul Pi meta' dei frame bastano
      if (lite && now - lastFrameAt < 32) return;
      // Mentre l'LLM genera la GPU serve a lui: la plancia scende a ~12 fps
      if (throttledRef.current && now - lastFrameAt < 80) return;
      lastFrameAt = now;

      const dt = Math.min(clock.getDelta(), 0.1);
      // Con prefers-reduced-motion la scena resta ferma; si muove solo la camera richiesta dall'utente
      const elapsedTime = reducedMotion ? 0 : motionClock.getElapsedTime();

      // Il rallentamento voluto non va scambiato per una GPU debole: la misura riparte
      if (!probeDone && throttledRef.current) {
        probeStart = 0;
        probeFrames = 0;
      } else if (!probeDone) {
        if (probeStart === 0) probeStart = now;
        probeFrames++;
        const span = now - probeStart;
        if (span > 4000) {
          probeDone = true;
          if ((probeFrames * 1000) / span < 28) switchToLite('fps');
        }
      }

      // Smorzamento legato al tempo e non ai frame: il volo dura uguale a 30 o 144 Hz
      const camEase = 1 - Math.exp(-dt * 2.6);
      const lookEase = 1 - Math.exp(-dt * 3.0);
      camera.position.lerp(targetCamPos, camEase);
      currentLookAt.lerp(targetLookAt, lookEase);
      camera.lookAt(currentLookAt);

      if (!reducedMotion) {
        // Rotazione anelli decorativi del tappeto di comando centrale
        carpetRim.rotation.z += 0.11 * dt;
        outerCarpetRing.rotation.z -= 0.085 * dt;

        // Movimento lento e maestoso della volta cosmica reale e parallasse stellare 3D
        if (cosmosMat.uniforms?.uTime) cosmosMat.uniforms.uTime.value = elapsedTime;
        cosmosDome.rotation.y = elapsedTime * 0.0002;
        cosmosDome.rotation.x = Math.sin(elapsedTime * 0.0001) * 0.004;
        bgStarPoints.rotation.y = elapsedTime * 0.0004;
        fgStarPoints.rotation.y = elapsedTime * 0.0005;
        beaconPoints.rotation.y = elapsedTime * 0.0005;
        pleiadesPoints.rotation.y = elapsedTime * 0.0004;
        constellationsGroup.rotation.y = elapsedTime * 0.0003;
        terraMesh.rotation.y = elapsedTime * 0.0007;
        terraCloudsMesh.rotation.y = elapsedTime * 0.0013;
        kronosMesh.rotation.y = elapsedTime * 0.0005;
        aresMesh.rotation.y = elapsedTime * 0.0006;
        lunaZenithMesh.rotation.y = elapsedTime * 0.0003;
        celestialGroup.position.y = Math.sin(elapsedTime * 0.1) * 0.3;
      }

      // Gli schermi delle console sono 30 canvas 2D: ridisegnarli a ogni frame era
      // il costo piu' alto della scena. 10 Hz bastano, 4 Hz in modalita' leggera.
      const screensInterval = lite ? 0.25 : 0.1;
      if (lastScreensAt < 0 || (!reducedMotion && elapsedTime - lastScreensAt >= screensInterval)) {
        lastScreensAt = elapsedTime;
        animatedDisplays.forEach(updateFn => updateFn(elapsedTime));
      }

      const focusedId = selectedAgentIdRef.current;
      stationDataList.forEach((st, idx) => {
        if (!reducedMotion) {
          const breath = Math.sin(elapsedTime * 2.2 + idx) * 0.025;
          st.headGroup.position.y = 1.25 + breath;

          const reactorPulse = 0.8 + Math.abs(Math.sin(elapsedTime * 3.5 + idx)) * 0.4;
          st.coreReactor.scale.set(reactorPulse, reactorPulse, reactorPulse);

          st.leftHand.position.y = 0.44 + Math.sin(elapsedTime * 8 + idx) * 0.015;
          st.rightHand.position.y = 0.44 + Math.cos(elapsedTime * 8 + idx) * 0.015;

          st.propGroup.rotation.y = elapsedTime * 1.3 + idx;
          st.propGroup.position.y = 5.8 + Math.sin(elapsedTime * 2.0 + idx) * 0.1;
        }

        st.badgeMesh.position.y = -2.0 + 3.8 + Math.sin(elapsedTime * 1.8 + idx) * 0.05;
        st.badgeMesh.quaternion.copy(camera.quaternion);

        // Le schede lontane crescono per restare leggibili, quelle troppo vicine
        // svaniscono: in vista generale coprivano dock e barra dei comandi.
        const dist = camera.position.distanceTo(badgeTmp.copy(st.badgeMesh.position));
        const isFocused = focusedId && st.role.id === focusedId;
        // Con un agente in primo piano niente ingrandimento: i vicini, piu' lontani,
        // sarebbero risultati piu' grandi della scheda selezionata.
        const scale = focusedId ? 1 : Math.max(0.9, Math.min(1.75, dist / 10));
        const opacity = isFocused ? 1 : smoothstep(4.8, 8.5, dist);
        st.badgeMesh.scale.setScalar(scale);
        st.badgeMesh.material.opacity = opacity;
        st.badgeMesh.visible = opacity > 0.04;
      });

      holotableLight.intensity = (isLight ? 2.8 : 5.0) + Math.sin(elapsedTime * 2.8) * 0.6;

      renderer.render(scene, camera);
    };

    animationFrameId = requestAnimationFrame(animate);

    // =========================================================================
    // 11. Pulizia Risorse WebGL
    // =========================================================================
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mouseup', onMouseUp);
      container.removeEventListener('click', onClick);
      container.removeEventListener('wheel', onWheel);
      window.removeEventListener('resize', onResize);
      if (resizeObserver) resizeObserver.disconnect();

      createdBadges.forEach(b => {
        scene.remove(b);
        b.geometry?.dispose();
        b.material?.map?.dispose();
        b.material?.dispose();
      });
      // Le postazioni si ricostruiscono a ogni cambio di ruoli o qualita':
      // senza liberarle le texture degli schermi restavano in VRAM.
      shipGroup.traverse(o => {
        if (o.geometry) o.geometry.dispose();
        const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
        mats.forEach(m => { m.map?.dispose(); m.dispose(); });
      });

      if (floorTex) floorTex.dispose();
      if (carpetTex) carpetTex.dispose();
      if (sharpStarTex) sharpStarTex.dispose();
      if (diffractionStarTex) diffractionStarTex.dispose();
      if (terraTex) terraTex.dispose();
      if (cloudTex) cloudTex.dispose();
      if (lunaTerraTex) lunaTerraTex.dispose();
      if (kronosTex) kronosTex.dispose();
      if (ringTex) ringTex.dispose();
      if (aresTex) aresTex.dispose();
      if (lunaZenithTex) lunaZenithTex.dispose();
      constellationLabels.forEach(l => {
        if (l.texture) l.texture.dispose();
        if (l.material) l.material.dispose();
      });
      if (constellationsGroup) {
        constellationsGroup.traverse(o => {
          if (o.geometry) o.geometry.dispose();
          if (o.material) o.material.dispose();
        });
      }
      if (domeGroup) {
        domeGroup.traverse(o => {
          if (o.geometry) o.geometry.dispose();
          if (o.material) o.material.dispose();
        });
      }
      if (celestialGroup) {
        celestialGroup.traverse(o => {
          if (o.geometry) o.geometry.dispose();
          if (o.material) o.material.dispose();
        });
      }
      [
        floorGeo,
        floorMat,
        centerPlatformGeo,
        centerPlatformMat,
        carpetGeo,
        carpetMat,
        carpetRimGeo,
        carpetRimMat,
        outerCarpetRingGeo,
        outerCarpetRingMat,
        cosmosGeo,
        cosmosMat,
        bgStarGeo,
        bgStarMat,
        fgStarGeo,
        fgStarMat,
        beaconGeo,
        beaconMat,
        pleiadesGeo,
        pleiadesMat,
        constLineGeo,
        constLineMat,
        constStarGeo,
        constStarMat
      ].forEach(o => o && o.dispose && o.dispose());

      if (renderer) {
        renderer.dispose();
        if (renderer.domElement && renderer.domElement.parentElement) {
          renderer.domElement.parentElement.removeChild(renderer.domElement);
        }
      }
    };
  }, [isLight, interactive, rolesKey, quality]);

  // Gestione selezioni esterne, compreso il ritorno alla vista generale
  useEffect(() => {
    if (flyToStationRef.current) flyToStationRef.current(selectedAgentId || null);
  }, [selectedAgentId]);

  return (
    <div
      ref={mountRef}
      className={`cyber-3d-canvas-container ${className}`}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        pointerEvents: interactive ? 'auto' : 'none',
        zIndex: 0,
        ...style
      }}
    >
      {/* Tooltip fluttuante di puntamento postazione 3D */}
      {hoveredAgent && hoveredAgent.id !== selectedAgentId && (
        <div className="holodeck-3d-node-lens" style={{ '--agent-glow': hoveredAgent.color || 'var(--sigma-primary)' }}>
          <div className="lens-header">
            <span className="lens-avatar">
              {hoveredAgent.image && hoveredAgent.image !== '/images/default.png'
                ? <img src={hoveredAgent.image} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                : roleInitials(hoveredAgent.name)}
            </span>
            <div className="lens-titles">
              <span className="lens-name">{hoveredAgent.name}</span>
              <span className="lens-category">{hoveredAgent.title}</span>
            </div>
            <span className="lens-launch-tag">Clicca per parlare</span>
          </div>
          {hoveredAgent.desc && <p className="lens-desc">{hoveredAgent.desc}</p>}
        </div>
      )}
    </div>
  );
}
