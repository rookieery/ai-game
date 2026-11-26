// 世界氛围：极光天穹 / 星空 / 月亮 / 场景雾 / 广场暖光（地面雾潭在 fx/mist.js）
import * as THREE from "three";

const AURORA_FRAG = /* glsl */ `
  varying vec3 vDir;
  uniform float uTime;
  uniform float uAurora;

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
    col += aurora * curtain * uAurora;
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
  scene.fog = new THREE.FogExp2("#0a0c1e", 0.0055); // v3 扩园 r150: 降密度保摩天轮顶俯瞰全园

  // 亮度基准（applySettings 以此换算百分比）
  const BASE = {
    moon: 0.85, hemi: 0.55,
    plaza1: 90, plaza2: 70, gate: 55,
    bay: 30, north: 42, east: 26,   // v3 分区灯: 幽灵港 / 北过山车 / 东南秘境
    fog: 0.0055, aurora: 0.85,
    starOpacity: 0.9,
  };

  // 月光 + 环境
  const moon = new THREE.DirectionalLight("#b4c7ff", BASE.moon);
  moon.position.set(60, 80, -40);
  scene.add(moon);
  const hemi = new THREE.HemisphereLight("#2a3050", "#141024", BASE.hemi);
  scene.add(hemi);

  // 广场暖光（灯串/南瓜的"实际照明"）+ 三盏分区灯（随扩园外推的光域）
  const plaza1 = new THREE.PointLight("#ff9a5c", BASE.plaza1, 130, 1.7);
  plaza1.position.set(12, 7, 12);
  scene.add(plaza1);
  const plaza2 = new THREE.PointLight("#ff9a5c", BASE.plaza2, 120, 1.7);
  plaza2.position.set(-12, 7, -14);
  scene.add(plaza2);
  const gate = new THREE.PointLight("#ffc46b", BASE.gate, 70, 1.7);
  gate.position.set(0, 7, 146); // 大门随围栏外移 r146
  scene.add(gate);
  const bay = new THREE.PointLight("#7fd8c8", BASE.bay, 95, 1.7);   // 幽灵港: 灵绿
  bay.position.set(-70, 9, 45);
  scene.add(bay);
  const north = new THREE.PointLight("#ff9a5c", BASE.north, 110, 1.7); // 过山车预留区: 暖橙
  north.position.set(15, 9, -100);
  scene.add(north);
  const east = new THREE.PointLight("#9b5bff", BASE.east, 90, 1.7);  // 秘境预留区: 暗紫
  east.position.set(95, 9, 60);
  scene.add(east);
  const plazaLights = [plaza1, plaza2, gate, bay, north, east];

  // 清单灯位：园区脚本 (model/park_env/park_env.py 的 park_light) 登记的真实点光，如墓园守墓灯 ×2。
  // 位置 / 颜色 / 强度来自 colliders.json 的 lights（与模型同源）。灯在这里一次建好、常驻，清单到位后只改参数、
  // 不增删 —— three r187 下运行时增删灯光会让当帧渲染抛错（2026-11-26 实测）。
  // 每盏灯挂在这个数组尾部，所以 plazaLights[6] 起就是它们（漂雾灯染按 tag 取用，不依赖下标）。
  const LIGHT_SLOTS = 2;   // 清单灯数超过槽位时多出的被忽略并在控制台告警
  const parkLights = [];   // { light, base, key, tag }
  for (let i = 0; i < LIGHT_SLOTS; i++) {
    const l = new THREE.PointLight("#ffd9a8", 0, 22, 2);
    scene.add(l);
    plazaLights.push(l);
    parkLights.push({ light: l, base: 0, key: "parkLampLight", tag: "" });
  }
  function setParkLights(list) {
    const items = Array.isArray(list) ? list : [];
    if (items.length > parkLights.length) {
      console.warn(`[park] colliders.json 的 lights 有 ${items.length} 盏, 超出槽位 ${parkLights.length}, 多出的未建灯`);
    }
    parkLights.forEach((slot, i) => {
      const d = items[i];
      if (!d) {
        slot.base = 0;
        slot.tag = "";
        slot.light.intensity = 0;
        return;
      }
      slot.light.color.set(d.color ?? "#ffd9a8");
      slot.light.position.set(d.x, d.y ?? 2, d.z);
      slot.light.distance = d.distance ?? 22;
      slot.light.decay = d.decay ?? 2;
      slot.base = d.intensity ?? 0;
      slot.key = d.key ?? "parkLampLight";
      slot.tag = d.tag ?? "";
    });
  }

  // 极光天穹（r150 园区 + 420+ 远景: 半径 700）
  const skyUniforms = { uTime: { value: 0 }, uAurora: { value: BASE.aurora } };
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(700, 32, 18),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: skyUniforms,
      vertexShader: AURORA_VERT,
      fragmentShader: AURORA_FRAG,
    })
  );
  scene.add(sky);

  // 星空（数量可重建：设置面板 200-3000 颗）
  function makeStarGeo(count) {
    const pos = [];
    for (let i = 0; i < count; i++) {
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(Math.random() * 0.92); // 上半球
      const r = 680;
      pos.push(r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) + 4, r * Math.sin(ph) * Math.sin(th));
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    return geo;
  }
  const starMat = new THREE.PointsMaterial({ color: "#dfe6ff", size: 1.9, sizeAttenuation: true, transparent: true, opacity: BASE.starOpacity, fog: false });
  const stars = new THREE.Points(makeStarGeo(1400), starMat);
  let curStarCount = 1400;
  scene.add(stars);

  // 月亮 + 光晕（随天穹放大同步外推）
  const moonDisc = new THREE.Mesh(
    new THREE.CircleGeometry(20, 32),
    new THREE.MeshBasicMaterial({ color: "#f4efd8", fog: false })
  );
  moonDisc.position.set(-295, 255, -510);
  moonDisc.lookAt(0, 0, 0);
  scene.add(moonDisc);
  const glowTex = makeMistTexture();
  const moonGlow = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: glowTex, color: "#d9dcff", transparent: true, opacity: 0.4, fog: false })
  );
  moonGlow.scale.set(170, 170, 1);
  moonGlow.position.copy(moonDisc.position);
  scene.add(moonGlow);

  function update(dt, elapsed) {
    skyUniforms.uTime.value = elapsed;
  }

  // 应用设置面板（百分比 -> 实际参数）
  function applySettings(s) {
    const pct = (k) => Math.min(200, Math.max(0, s[k] ?? 100)) / 100;
    moon.intensity = BASE.moon * pct("moonLight");
    hemi.intensity = BASE.hemi * pct("moonLight");
    plaza1.intensity = BASE.plaza1 * pct("parkLampLight");
    plaza2.intensity = BASE.plaza2 * pct("parkLampLight");
    gate.intensity = BASE.gate * pct("parkLampLight");
    bay.intensity = BASE.bay * pct("parkLampLight");
    north.intensity = BASE.north * pct("parkLampLight");
    east.intensity = BASE.east * pct("parkLampLight");
    for (const slot of parkLights) slot.light.intensity = slot.base * pct(slot.key); // 清单灯各随自己的滑杆 (墓园守墓灯: graveyardLight)
    scene.fog.density = BASE.fog * pct("fogDensity");
    skyUniforms.uAurora.value = BASE.aurora * pct("auroraLight");
    starMat.opacity = Math.min(1, BASE.starOpacity * pct("starBrightness"));
    const n = Math.round(Math.min(3000, Math.max(200, s.starCount)));
    if (n !== curStarCount) {
      const old = stars.geometry;
      stars.geometry = makeStarGeo(n);
      old.dispose();
      curStarCount = n;
    }
  }

  return { update, moon, applySettings, plazaLights, parkLights, setParkLights };
}
