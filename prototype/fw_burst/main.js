// 烟花颗粒原型 (独立页, 不接入游戏): 验证「颗粒分明」爆裂语言
// 与游戏同管线: ACES 0.95 + UnrealBloom 0.30/0.55/0.85 + 加色混合 Points
// 看齐参考图的要点: 单发 ~800 颗细粒 / 每粒屏幕 4-8px 锐利核心 / 亮度随机分层 / 微闪烁
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";

const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;

const scene = new THREE.Scene();
scene.background = new THREE.Color("#060913");

const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 500);
camera.position.set(0, 14, 46);
camera.lookAt(0, 26, 0);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.3, 0.55, 0.85);
composer.addPass(bloom);
composer.addPass(new OutputPass());

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
});

// ------------------------------------------------ 纹理: 锐核光点 (对比游戏版 0.55 处还有 0.28, 这里收窄到 0.42/0.08) ---
function makeGrainTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 30);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.18, "rgba(255,255,255,0.95)");
  grad.addColorStop(0.42, "rgba(255,255,255,0.35)");
  grad.addColorStop(0.7, "rgba(255,255,255,0.08)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

// ------------------------------------------------ 粒子池 ---
const MAX = 20000;
const geo = new THREE.BufferGeometry();
const pos = new Float32Array(MAX * 3).fill(-9999);
const colA = new Float32Array(MAX * 3);
const sizeA = new Float32Array(MAX);
geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
geo.setAttribute("aColor", new THREE.BufferAttribute(colA, 3));
geo.setAttribute("aSize", new THREE.BufferAttribute(sizeA, 1));
const points = new THREE.Points(geo, new THREE.ShaderMaterial({
  uniforms: { uMap: { value: makeGrainTexture() }, uScale: { value: 450 } },
  vertexShader: /* glsl */ `
    attribute vec3 aColor;
    attribute float aSize;
    uniform float uScale;
    varying vec3 vColor;
    void main() {
      vColor = aColor;
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = aSize * (uScale / max(1.0, -mv.z));
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D uMap;
    varying vec3 vColor;
    void main() {
      float a = texture2D(uMap, gl_PointCoord).a;
      gl_FragColor = vec4(vColor * a, a);
    }`,
  blending: THREE.AdditiveBlending,
  transparent: true,
  depthWrite: false,
}));
points.frustumCulled = false;
scene.add(points);

const vel = new Float32Array(MAX * 3);
const life = new Float32Array(MAX);
const life0 = new Float32Array(MAX);
const base = new Float32Array(MAX * 3);
const gravA = new Float32Array(MAX);
const twA = new Float32Array(MAX);   // 闪烁幅度 0 = 不闪
const phA = new Float32Array(MAX);   // 闪烁相位
let cursor = 0;
const _c = new THREE.Color();
const _v = new THREE.Vector3();

function spawn(p, v, color, l, size, opt = {}) {
  const i = cursor;
  cursor = (cursor + 1) % MAX;
  const i3 = i * 3;
  pos[i3] = p.x; pos[i3 + 1] = p.y; pos[i3 + 2] = p.z;
  vel[i3] = v.x; vel[i3 + 1] = v.y; vel[i3 + 2] = v.z;
  life[i] = l; life0[i] = l;
  sizeA[i] = size;
  gravA[i] = opt.g ?? 3.2;
  twA[i] = opt.tw ?? 0;
  phA[i] = Math.random() * Math.PI * 2;
  const boost = (opt.boost ?? 2.2) * (opt.bvar ? 0.5 + Math.random() : 1); // 亮度随机分层
  base[i3] = color.r * boost; base[i3 + 1] = color.g * boost; base[i3 + 2] = color.b * boost;
}

const PAL_GOLD = ["#FFE9C4", "#FFD9A0", "#FFF6E0", "#FFC46B"];
const _P = new THREE.Vector3();
function ringPos() { _P.set((Math.random() - 0.5) * 26, 26 + Math.random() * 12, (Math.random() - 0.5) * 12); return _P; }

function flashFrame(p, n, size) {
  _c.set("#FFF6E0");
  for (let k = 0; k < n; k++) {
    _v.set((Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2);
    spawn(p, _v, _c, 0.08 + Math.random() * 0.05, size * (0.8 + Math.random() * 0.4), { boost: 3 });
  }
}

// 牡丹: ~820 颗三层球壳, 每颗 0.7-1.5 世界尺寸 (50-65m 外约 5-11px), 外壳 16-24 m/s 快速撑开
function burstPeony(p, color) {
  const n = 760 + ((Math.random() * 160) | 0);
  for (let k = 0; k < n; k++) {
    const u = Math.random() * 2 - 1;
    const phi = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = Math.random();
    const sp = r < 0.3 ? 5 + Math.random() * 3 : r < 0.7 ? 10 + Math.random() * 6 : 16 + Math.random() * 8;
    _v.set(s * Math.cos(phi) * sp, u * sp * 0.92, s * Math.sin(phi) * sp);
    const cr = Math.random();
    const c = cr < 0.22 ? _c.set(color) : cr < 0.55 ? _c.set("#FFE9C4") : _c.set("#FFF6E0");
    spawn(p, _v, c, 1.4 + Math.random() * 0.8, 0.85 + Math.random() * 0.8,
      { bvar: true, tw: 0.25 + Math.random() * 0.2, boost: 2.4 });
  }
  flashFrame(p, 3, 5);
}

// 垂柳: ~420 颗金粒长寿命下垂 (颗粒雨)
function burstWillow(p) {
  const n = 380 + ((Math.random() * 80) | 0);
  for (let k = 0; k < n; k++) {
    const u = Math.random() * 2 - 1;
    const phi = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const sp = 6 + Math.random() * 5;
    _v.set(s * Math.cos(phi) * sp, u * sp, s * Math.sin(phi) * sp);
    const c = _c.set(PAL_GOLD[(Math.random() * PAL_GOLD.length) | 0]);
    spawn(p, _v, c, 3.0 + Math.random() * 1.0, 0.7 + Math.random() * 0.55,
      { g: 5.0, bvar: true, tw: 0.35, boost: 2.6 });
  }
  flashFrame(p, 3, 5);
}

// 椰芯: 18 颗星 0.8-1.2s 后各裂成 ~28 微粒
const stars = []; // {p, v, splitAt, color}
function burstCrossette(p, color) {
  stars.length = 0;
  for (let k = 0; k < 18; k++) {
    const u = Math.random() * 2 - 1;
    const phi = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const sp = 9 + Math.random() * 4;
    _v.set(s * Math.cos(phi) * sp, u * sp, s * Math.sin(phi) * sp);
    stars.push({ p: p.clone(), v: _v.clone(), splitAt: 0.8 + Math.random() * 0.4, age: 0, color });
    _c.copy(color);
    spawn(p, _v, _c, 0.8 + Math.random() * 0.4, 1.4 + Math.random() * 0.6, { bvar: true, tw: 0.3 });
  }
  flashFrame(p, 3, 5);
}
function splitStars(dt) {
  for (let k = stars.length - 1; k >= 0; k--) {
    const st = stars[k];
    st.age += dt;
    st.v.y -= 4.5 * dt;
    st.p.addScaledVector(st.v, dt);
    if (st.age >= st.splitAt) {
      const n = 24 + ((Math.random() * 8) | 0);
      for (let j = 0; j < n; j++) {
        const u = Math.random() * 2 - 1;
        const phi = Math.random() * Math.PI * 2;
        const s = Math.sqrt(1 - u * u);
        const sp = 3 + Math.random() * 3;
        _v.set(s * Math.cos(phi) * sp, u * sp, s * Math.sin(phi) * sp);
        const c = Math.random() < 0.35 ? _c.set("#FFF6E0") : _c.copy(st.color);
        spawn(st.p, _v, c, 0.7 + Math.random() * 0.35, 0.8 + Math.random() * 0.5,
          { g: 4.2, bvar: true, tw: 0.25, boost: 3.0 });
      }
      stars.splice(k, 1);
    }
  }
}

// 壳体升空 + 细碎尾迹
const shells = [];
const SHELL_G = 7.5;
function fire(type, color) {
  const p = ringPos().clone();
  const h = 26 - p.y + 26 + Math.random() * 6; // 顶点 ~52-58
  const v0y = Math.sqrt(2 * SHELL_G * (h + 0.4));
  shells.push({ p: new THREE.Vector3(p.x, 1, p.z), v: new THREE.Vector3((Math.random() - 0.5) * 2, v0y, (Math.random() - 0.5) * 2), type, color });
}
function updateShells(dt) {
  for (let k = shells.length - 1; k >= 0; k--) {
    const sh = shells[k];
    sh.v.y -= SHELL_G * dt;
    sh.p.addScaledVector(sh.v, dt);
    for (let s = 0; s < 2; s++) {
      _v.set((Math.random() - 0.5) * 1.2 + sh.v.x * 0.1,
             (Math.random() - 0.5) * 1.2 + sh.v.y * 0.1,
             (Math.random() - 0.5) * 1.2 + sh.v.z * 0.1);
      spawn(sh.p, _v, _c.set("#FFD9A0"), 0.35 + Math.random() * 0.3, 0.3 + Math.random() * 0.2);
    }
    if (sh.v.y < 2.5) {
      if (sh.type === "peony") burstPeony(sh.p, sh.color);
      else if (sh.type === "willow") burstWillow(sh.p);
      else burstCrossette(sh.p, sh.color);
      shells.splice(k, 1);
    }
  }
}

let aliveCount = 0;
const clock = { last: performance.now() };
let t = 0;
renderer.setAnimationLoop(() => {
  const now = performance.now();
  const dt = Math.min((now - clock.last) / 1000, 0.1);
  clock.last = now;
  t += dt;
  updateShells(dt);
  splitStars(dt);
  aliveCount = 0;
  const drag = Math.pow(0.55, dt);
  for (let i = 0; i < MAX; i++) {
    if (life[i] <= 0) continue;
    life[i] -= dt;
    const i3 = i * 3;
    vel[i3 + 1] -= gravA[i] * dt;
    vel[i3] *= drag; vel[i3 + 1] *= drag; vel[i3 + 2] *= drag;
    pos[i3] += vel[i3] * dt;
    pos[i3 + 1] += vel[i3 + 1] * dt;
    pos[i3 + 2] += vel[i3 + 2] * dt;
    let f = Math.max(0, life[i] / life0[i]);
    f = Math.pow(f, 1.35);
    if (twA[i] > 0) f *= 1 - twA[i] * (0.5 + 0.5 * Math.sin(t * 14 + phA[i]));
    const b = f * 1.0;
    colA[i3] = base[i3] * b;
    colA[i3 + 1] = base[i3 + 1] * b;
    colA[i3 + 2] = base[i3 + 2] * b;
    if (life[i] <= 0) {
      colA[i3] = colA[i3 + 1] = colA[i3 + 2] = 0;
      pos[i3 + 1] = -9999;
    } else aliveCount++;
  }
  geo.attributes.position.needsUpdate = true;
  geo.attributes.aColor.needsUpdate = true;
  geo.attributes.aSize.needsUpdate = true;
  composer.render();
});

// 自动循环演示 (可关) + 手动触发钩子
const COLORS = ["#FFA53B", "#9B5BFF", "#8CFF4A", "#8FE3D9", "#FF7B6B"];
const TYPES = ["peony", "willow", "crossette"];
let autoIdx = 0;
let autoEnabled = true;
setInterval(() => {
  if (!autoEnabled) return;
  const type = TYPES[autoIdx % TYPES.length];
  fire(type, new THREE.Color(COLORS[autoIdx % COLORS.length]));
  autoIdx++;
}, 2600);

window.__fw = {
  fire(type = "peony", color = "#FFD9A0") {
    fire(type, new THREE.Color(color));
  },
  auto(on) { autoEnabled = on; },
  alive: () => aliveCount,
};
