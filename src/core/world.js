// 世界氛围：极光天穹 / 星空 / 月亮 / 雾 / 地面雾片 / 广场暖光
import * as THREE from "three";

const AURORA_FRAG = /* glsl */ `
  varying vec3 vDir;
  uniform float uTime;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) { v += a * vnoise(p); p *= 2.1; a *= 0.5; }
    return v;
  }

  void main() {
    vec3 d = normalize(vDir);
    float h = clamp(d.y, 0.0, 1.0);
    // 夜空渐变: 地平线微亮 -> 天顶深黑
    vec3 col = mix(vec3(0.055, 0.065, 0.13), vec3(0.012, 0.015, 0.045), pow(h, 0.6));
    // 极光带 (中天区域, 沿方位角流动的帘状光)
    float band = smoothstep(0.28, 0.5, h) * smoothstep(0.95, 0.6, h);
    float n = fbm(vec2(atan(d.z, d.x) * 2.2 + uTime * 0.05, d.y * 5.5 - uTime * 0.03));
    float curtain = smoothstep(0.42, 0.85, n) * band;
    vec3 aurora = mix(vec3(0.18, 0.75, 0.52), vec3(0.45, 0.30, 0.85),
                      fbm(vec2(uTime * 0.04, d.y * 3.0)));
    col += aurora * curtain * 0.85;
    gl_FragColor = vec4(col, 1.0);
  }
`;

const AURORA_VERT = /* glsl */ `
  varying vec3 vDir;
  void main() {
    vDir = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

function makeMistTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(64, 64, 4, 64, 64, 62);
  grad.addColorStop(0, "rgba(180,190,220,0.55)");
  grad.addColorStop(1, "rgba(180,190,220,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  return tex;
}

export function createWorld(scene) {
  scene.background = new THREE.Color("#060812");
  scene.fog = new THREE.FogExp2("#0a0c1e", 0.0085);

  // 月光 + 环境
  const moon = new THREE.DirectionalLight("#b4c7ff", 0.85);
  moon.position.set(60, 80, -40);
  scene.add(moon);
  const hemi = new THREE.HemisphereLight("#2a3050", "#141024", 0.55);
  scene.add(hemi);

  // 广场暖光（灯串/南瓜的"实际照明"）
  const plaza1 = new THREE.PointLight("#ff9a5c", 90, 80, 1.7);
  plaza1.position.set(12, 7, 12);
  scene.add(plaza1);
  const plaza2 = new THREE.PointLight("#ff9a5c", 70, 70, 1.7);
  plaza2.position.set(-12, 7, -14);
  scene.add(plaza2);
  const gate = new THREE.PointLight("#ffc46b", 55, 60, 1.7);
  gate.position.set(0, 7, 66);
  scene.add(gate);

  // 极光天穹
  const skyUniforms = { uTime: { value: 0 } };
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(460, 32, 18),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: skyUniforms,
      vertexShader: AURORA_VERT,
      fragmentShader: AURORA_FRAG,
    })
  );
  scene.add(sky);

  // 星空
  const starGeo = new THREE.BufferGeometry();
  const starPos = [];
  for (let i = 0; i < 1400; i++) {
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(Math.random() * 0.92); // 上半球
    const r = 440;
    starPos.push(r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) + 4, r * Math.sin(ph) * Math.sin(th));
  }
  starGeo.setAttribute("position", new THREE.Float32BufferAttribute(starPos, 3));
  const stars = new THREE.Points(
    starGeo,
    new THREE.PointsMaterial({ color: "#dfe6ff", size: 1.9, sizeAttenuation: true, transparent: true, opacity: 0.9, fog: false })
  );
  scene.add(stars);

  // 月亮 + 光晕
  const moonDisc = new THREE.Mesh(
    new THREE.CircleGeometry(13, 32),
    new THREE.MeshBasicMaterial({ color: "#f4efd8", fog: false })
  );
  moonDisc.position.set(-190, 165, -330);
  moonDisc.lookAt(0, 0, 0);
  scene.add(moonDisc);
  const glowTex = makeMistTexture();
  const moonGlow = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: glowTex, color: "#d9dcff", transparent: true, opacity: 0.4, fog: false })
  );
  moonGlow.scale.set(110, 110, 1);
  moonGlow.position.copy(moonDisc.position);
  scene.add(moonGlow);

  // 地面雾片（缓慢漂移）
  const mists = [];
  for (let i = 0; i < 9; i++) {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(55, 20),
      new THREE.MeshBasicMaterial({
        map: glowTex, transparent: true, opacity: 0.10,
        depthWrite: false, side: THREE.DoubleSide,
      })
    );
    const th = (i / 9) * Math.PI * 2;
    const rr = 18 + (i % 4) * 14;
    m.position.set(rr * Math.cos(th), 1.0 + (i % 3) * 0.5, rr * Math.sin(th));
    m.rotation.y = Math.random() * Math.PI;
    m.rotation.x = Math.random() * 0.2 - 0.1;
    mists.push(m);
    scene.add(m);
  }

  function update(dt, elapsed) {
    skyUniforms.uTime.value = elapsed;
    for (let i = 0; i < mists.length; i++) {
      const m = mists[i];
      m.position.x += Math.sin(elapsed * 0.05 + i * 2.1) * dt * 0.6;
      m.position.z += Math.cos(elapsed * 0.04 + i * 1.7) * dt * 0.6;
    }
  }

  return { update, moon };
}
