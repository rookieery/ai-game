// 烟花系统 v2: 三型发射器 × 全弹道可见 × 6 站布点 + 自动秀编排 + F 点射
// 弹道五段全程可读: 管口点火闪光 → 亮彗星头 + 密集尾迹 → 顶点白热爆闪 → 花型展开 → 余烬闪烁熄灭
// 花型: A 牡丹(三层球壳) / B 垂柳(金瀑长垂+滴烬) / C 椰芯(大火星二次炸裂)
// 架构: 单 Points 池 ShaderMaterial 加色混合, CPU 积分; 彗星头占池首专用槽位, 其余粒子环形覆写
// 主题色板与品牌色一致; 零外部素材
import * as THREE from "three";

const MAX = 6144;        // 粒子池容量（终曲全开 ~2500 并发仍有裕量）
const HEAD_MAX = 16;     // 池首保留槽位: 彗星头专用（常规粒子从 HEAD_MAX 起环形覆写, 不会侵占头部）
const GRAV = 3.2;        // 余烬重力（远小于真实 g, 梦幻缓坠）
const DRAG_PER_S = 0.6;  // vel *= DRAG_PER_S^dt 的大气阻尼
const SHELL_G = 7.5;     // 壳体升空重力（v0y 由炸点高度反解: v0y = sqrt(2·SHELL_G·h)）

export const KIND_NAME = { A: "牡丹发射架", B: "垂柳塔", C: "椰芯连环炮" };

const PAL_A = ["#FFA53B", "#9B5BFF", "#8CFF4A", "#C43B3B", "#FFE9C4", "#8FE3D9"]; // 牡丹: 品牌六色
const PAL_B = ["#FFC46B", "#FFE9C4", "#FFA53B", "#FFD9A0"];                        // 垂柳: 金瀑系
const PAL_C = ["#8CFF4A", "#9B5BFF", "#8FE3D9", "#C4FF5A"];                        // 椰芯: 磷光系
const COL_TRAIL = "#FFD9A0";   // 尾迹暖金
const COL_WHITE = "#FFF6E0";   // 白热
// manifest 缺失时的兜底 6 站（与 model/park_env/park_env.py LAUNCHER_SITES 同步; dx/dz = 朝园心单位向量）
const FALLBACK = [
  { id: "L1", kind: "A", x: 22,   z: 22, dx: -0.707, dz: -0.707, mz: 1.63 },
  { id: "L2", kind: "A", x: 56,   z: -30, dx: -0.882, dz: 0.473, mz: 1.63 },
  { id: "L3", kind: "B", x: 43.5, z: 45,  dx: -0.695, dz: -0.719, mz: 2.92 },
  { id: "L4", kind: "B", x: -55,  z: -30, dx: 0.878,  dz: 0.479,  mz: 2.92 },
  { id: "L5", kind: "C", x: -30,  z: 24,  dx: 0.781,  dz: -0.625, mz: 1.28 },
  { id: "L6", kind: "C", x: 11,   z: 84,  dx: -0.13,  dz: -0.991, mz: 1.28 },
];

function makeGlowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 30);
  // 锐核光点: 颗粒分明的前提 (软晕会在大颗粒尺寸下糊成云)
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.55, "rgba(255,255,255,0.95)");
  grad.addColorStop(0.75, "rgba(255,255,255,0.5)");
  grad.addColorStop(0.9, "rgba(255,255,255,0.12)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

const _pal = {};
function pal(kind) {
  if (!_pal[kind]) _pal[kind] = { A: PAL_A, B: PAL_B, C: PAL_C }[kind].map((h) => new THREE.Color(h));
  return _pal[kind];
}

export function createFireworks(scene, { camera, audio, renderer }) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(MAX * 3).fill(-9999);
  const colA = new Float32Array(MAX * 3);
  const sizeA = new Float32Array(MAX);
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("aColor", new THREE.BufferAttribute(colA, 3));
  geo.setAttribute("aSize", new THREE.BufferAttribute(sizeA, 1));
  const points = new THREE.Points(
    geo,
    new THREE.ShaderMaterial({
      uniforms: { uMap: { value: makeGlowTexture() }, uScale: { value: 720 } },
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
    })
  );
  points.frustumCulled = false;
  scene.add(points);

  const vel = new Float32Array(MAX * 3);
  const life = new Float32Array(MAX);      // <=0 视为空闲（头部槽位不参与积分, 每帧直写）
  const life0 = new Float32Array(MAX);
  const base = new Float32Array(MAX * 3);  // 粒子本色（×2.2 提亮后写入 aColor）
  const gravA = new Float32Array(MAX);     // 每粒子重力（垂柳更强下垂）
  const twA = new Float32Array(MAX);       // 微闪烁幅度（0 = 不闪）
  const phA = new Float32Array(MAX);       // 微闪烁相位
  const splitA = new Float32Array(MAX);    // >0: 剩余寿命到达此值时二次炸裂（椰芯）
  let cursor = HEAD_MAX;

  // 爆裂闪光 + 管口点火闪光（强度指数衰减, 归零后无开销感知）
  const flash = new THREE.PointLight("#ffffff", 0, 240, 1.8);
  const mflash = new THREE.PointLight("#ffd9a0", 0, 30, 2.0);
  scene.add(flash, mflash);

  let launchers = FALLBACK;
  const cdUntil = new Float64Array(FALLBACK.length).fill(-1);
  const shells = [];    // 升空壳体 { p, v, kind, color, head, acc }
  const pending = [];   // 齐射队列 { at, lid }
  let period = 30;      // 自动秀间隔（秒, 0 = 关闭）
  let bright = 1;
  let height = 55;      // 炸点高度（米, 设置项; 花型内再叠 ±8% 自然变化）
  let nextShow = 8;     // 入园后 8s 首秀
  let showCount = 0;
  let now = 0;
  let headCursor = 0;

  const _c = new THREE.Color();
  const _c2 = new THREE.Color();
  const _v = new THREE.Vector3();
  const _tp = new THREE.Vector3();
  const _prev = new THREE.Vector3();

  function spawn(p, v, color, l, size, opt = {}) {
    const i = cursor;
    cursor = HEAD_MAX + ((cursor - HEAD_MAX + 1) % (MAX - HEAD_MAX));
    const i3 = i * 3;
    pos[i3] = p.x; pos[i3 + 1] = p.y; pos[i3 + 2] = p.z;
    vel[i3] = v.x; vel[i3 + 1] = v.y; vel[i3 + 2] = v.z;
    life[i] = l; life0[i] = l;
    sizeA[i] = size;
    gravA[i] = opt.g ?? GRAV;
    twA[i] = opt.tw ?? 0;
    phA[i] = Math.random() * Math.PI * 2;
    splitA[i] = opt.splitAt ?? 0;
    // 固有色提亮: 补 ACES 中调压缩, 重叠处推过 bloom 阈值; bvar = 亮度随机分层 (颗粒分明)
    const boost = (opt.boost ?? 2.2) * (opt.bvar ? 0.5 + Math.random() : 1);
    base[i3] = color.r * boost; base[i3 + 1] = color.g * boost; base[i3 + 2] = color.b * boost;
  }

  function kill(i) {
    life[i] = 0;
    const i3 = i * 3;
    colA[i3] = colA[i3 + 1] = colA[i3 + 2] = 0;
    pos[i3 + 1] = -9999;
  }

  // ---------- 发射 ----------
  function launchShell(lid) {
    const L = launchers[lid];
    if (!L) return;
    const kind = L.kind;
    const colors = pal(kind);
    const color = colors[(Math.random() * colors.length) | 0];
    // 炸点高度 -> 反解初速（v.y 降到 2.5 时爆, 高度补回 2.5²/2g）
    const h = Math.max(20, height * (1 + (Math.random() - 0.5) * 0.16));
    const v0y = Math.sqrt(2 * SHELL_G * (h + 0.42));
    // 管口点火: 迸火花 + 光脉冲 + 升空啸声
    _tp.set(L.x + (Math.random() - 0.5) * 0.24, L.mz, L.z + (Math.random() - 0.5) * 0.24);
    for (let k = 0; k < 10; k++) {
      _v.set((Math.random() - 0.5) * 3.4, 0.8 + Math.random() * 2.2, (Math.random() - 0.5) * 3.4);
      spawn(_tp, _v, _c.set(COL_TRAIL), 0.22 + Math.random() * 0.22, 1.5 + Math.random() * 0.5);
    }
    mflash.position.copy(_tp);
    mflash.intensity = 14 * bright;
    audio?.fireworkLaunch();
    // 壳体: 沿发射方向漂移 + 少量横向散布
    const hs = 2.0 + Math.random() * 2.0;
    const px = -L.dz, pz = L.dx; // 横向单位向量
    const v = new THREE.Vector3(
      L.dx * hs + px * (Math.random() - 0.5) * 1.4,
      v0y,
      L.dz * hs + pz * (Math.random() - 0.5) * 1.4
    );
    const p = _tp.clone();
    const head = headCursor;
    headCursor = (headCursor + 1) % HEAD_MAX;
    shells.push({ p, v, kind, color, head, acc: 0 });
  }

  // 白热爆闪帧: 数颗超大短命白粒子, 爆裂瞬间的"裂"感
  function flashFrame(p, n, size) {
    _c.set(COL_WHITE);
    for (let k = 0; k < n; k++) {
      _v.set((Math.random() - 0.5) * 2.4, (Math.random() - 0.5) * 2.4, (Math.random() - 0.5) * 2.4);
      spawn(p, _v, _c, 0.08 + Math.random() * 0.05, size * (0.8 + Math.random() * 0.5), { boost: 3.2 });
    }
  }

  function burstPeony(sh) {
    // 颗粒语言 (用户确认 2026-11-17): ~820 颗细粒锐利光点, 22% 型色 + 78% 金白, 亮度随机分层
    const n = 760 + ((Math.random() * 160) | 0);
    for (let k = 0; k < n; k++) {
      const u = Math.random() * 2 - 1;
      const phi = Math.random() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u);
      const r = Math.random();
      // 三层速度: 内芯 / 中层 / 外壳 —— 外壳 16-24 m/s 快速撑开
      const sp = r < 0.3 ? 5 + Math.random() * 3 : r < 0.7 ? 10 + Math.random() * 6 : 16 + Math.random() * 8;
      _v.set(s * Math.cos(phi) * sp, u * sp * 0.92, s * Math.sin(phi) * sp);
      const cr = Math.random();
      const c = cr < 0.22 ? sh.color : cr < 0.55 ? _c.set("#FFE9C4") : _c2.set(COL_WHITE);
      spawn(sh.p, _v, c, 1.4 + Math.random() * 0.8, 1.6 + Math.random() * 1.0,
        { bvar: true, tw: 0.25 + Math.random() * 0.2, boost: 5.5 });
    }
    flashFrame(sh.p, 3, 5);
  }

  function burstWillow(sh) {
    // 金瀑颗粒雨: ~420 颗金粒长寿命强重力下垂
    const n = 380 + ((Math.random() * 80) | 0);
    for (let k = 0; k < n; k++) {
      const u = Math.random() * 2 - 1;
      const phi = Math.random() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u);
      const sp = 6 + Math.random() * 5;
      _v.set(s * Math.cos(phi) * sp, u * sp, s * Math.sin(phi) * sp);
      const c = pal("B")[(Math.random() * 4) | 0];
      spawn(sh.p, _v, c, 3.0 + Math.random(), 1.25 + Math.random() * 0.85,
        { g: 5.0, bvar: true, tw: 0.35, boost: 5.8 });
    }
    flashFrame(sh.p, 3, 5);
  }

  function burstCrossette(sh) {
    // 16-20 颗大火星, 0.8-1.2s 后二次炸裂成微星簇
    const n = 16 + ((Math.random() * 5) | 0);
    for (let k = 0; k < n; k++) {
      const u = Math.random() * 2 - 1;
      const phi = Math.random() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u);
      const sp = 9 + Math.random() * 4;
      _v.set(s * Math.cos(phi) * sp, u * sp, s * Math.sin(phi) * sp);
      const splitAt = 0.8 + Math.random() * 0.4;
      // 星体寿命 = 分裂时刻, 到点让位给微星簇
      spawn(sh.p, _v, sh.color, splitAt + 0.05, 2.4 + Math.random() * 1.0,
        { bvar: true, tw: 0.3, splitAt, boost: 5.0 });
    }
    flashFrame(sh.p, 3, 5);
  }

  // 椰芯二次炸裂: 大火星裂为微星簇 + 微闪
  function splitStar(i) {
    _tp.set(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
    _c.setRGB(base[i * 3] / 2.2, base[i * 3 + 1] / 2.2, base[i * 3 + 2] / 2.2);
    const n = 24 + ((Math.random() * 8) | 0);
    for (let k = 0; k < n; k++) {
      const u = Math.random() * 2 - 1;
      const phi = Math.random() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u);
      const sp = 3 + Math.random() * 3;
      _v.set(s * Math.cos(phi) * sp, u * sp, s * Math.sin(phi) * sp);
      const c = Math.random() < 0.35 ? _c2.set(COL_WHITE) : _c;
      spawn(_tp, _v, c, 0.7 + Math.random() * 0.35, 1.35 + Math.random() * 0.75,
        { g: 4.2, bvar: true, tw: 0.25, boost: 6.0 });
    }
    flashFrame(_tp, 1, 8);
    kill(i);
  }

  function burstShell(sh) {
    kill(sh.head);
    if (sh.kind === "A") burstPeony(sh);
    else if (sh.kind === "B") burstWillow(sh);
    else burstCrossette(sh);
    flash.position.copy(sh.p);
    flash.color.copy(sh.color);
    flash.intensity = (sh.kind === "A" ? 60 : sh.kind === "B" ? 38 : 50) * bright;
    const d = camera ? camera.position.distanceTo(sh.p) : 60;
    audio?.fireworkBurst(Math.max(0.12, Math.min(1, 1 - d / 300)), sh.kind);
  }

  // ---------- 编排 ----------
  function scheduleShow() {
    if (!launchers.length) return;
    showCount++;
    if (showCount % 4 === 0) {
      // 终曲: 6 站全开 × 两波错落
      let t = 0.2;
      for (let w = 0; w < 2; w++) {
        for (let i = 0; i < launchers.length; i++) {
          pending.push({ at: t, lid: i });
          if (Math.random() < 0.5) pending.push({ at: t + 0.25 + Math.random() * 0.3, lid: i });
          t += 0.3 + Math.random() * 0.4;
        }
      }
    } else {
      // 常规场: 随机 2-3 台错落
      const idx = launchers.map((_, i) => i);
      for (let k = idx.length - 1; k > 0; k--) {
        const j = (Math.random() * (k + 1)) | 0;
        [idx[k], idx[j]] = [idx[j], idx[k]];
      }
      let t = 0.1;
      for (const i of idx.slice(0, 2 + ((Math.random() * 2) | 0))) {
        pending.push({ at: t, lid: i });
        if (Math.random() < 0.6) pending.push({ at: t + 0.3 + Math.random() * 0.4, lid: i });
        t += 0.5 + Math.random() * 0.7;
      }
    }
  }

  // F 点射: 单发, 每台独立 0.6s 装填
  function fire(lid) {
    if (now < cdUntil[lid] || !launchers[lid]) return false;
    cdUntil[lid] = now + 0.6;
    pending.push({ at: 0.02, lid });
    return true;
  }

  function isReady(lid) {
    return now >= (cdUntil[lid] ?? -1);
  }

  function setLaunchers(list) {
    if (Array.isArray(list) && list.length) {
      launchers = list;
      cdUntil.fill(-1, 0, list.length);
    }
  }

  function update(dt, elapsed) {
    now = elapsed;
    // 自动秀调度
    if (period > 0 && elapsed >= nextShow) {
      scheduleShow();
      nextShow = elapsed + period * (0.75 + Math.random() * 0.5);
    }
    // 齐射队列
    for (let k = pending.length - 1; k >= 0; k--) {
      pending[k].at -= dt;
      if (pending[k].at <= 0) {
        launchShell(pending[k].lid);
        pending.splice(k, 1);
      }
    }
    // 壳体升空: 彗星头直写 + 密集尾迹 + 顶点爆裂
    for (let k = shells.length - 1; k >= 0; k--) {
      const sh = shells[k];
      _prev.copy(sh.p);
      sh.v.y -= SHELL_G * dt;
      sh.p.addScaledVector(sh.v, dt);
      sh.acc += dt;
      // 彗星头（池首专用槽位, 每帧直写位置/亮度/尺寸闪烁）
      const hi3 = sh.head * 3;
      pos[hi3] = sh.p.x; pos[hi3 + 1] = sh.p.y; pos[hi3 + 2] = sh.p.z;
      sizeA[sh.head] = 1.6 + Math.random() * 0.7;
      const hf = 2.6 * bright * (0.85 + Math.random() * 0.5);
      colA[hi3] = hf; colA[hi3 + 1] = hf * 0.92; colA[hi3 + 2] = hf * 0.75;
      // 尾迹: 沿本帧运动线段插值撒星, 保证轨迹连续
      const n = Math.min(4, Math.max(1, Math.round(dt * 120)));
      for (let s = 1; s <= n; s++) {
        _tp.lerpVectors(_prev, sh.p, s / (n + 1));
        _v.set((Math.random() - 0.5) * 1.6 + sh.v.x * 0.12,
               (Math.random() - 0.5) * 1.6 + sh.v.y * 0.12,
               (Math.random() - 0.5) * 1.6 + sh.v.z * 0.12);
        spawn(_tp, _v, _c.set(COL_TRAIL), 0.3 + Math.random() * 0.3, 0.45 + Math.random() * 0.25);
      }
      if (sh.v.y < 2.5) {
        burstShell(sh);
        shells.splice(k, 1);
      }
    }
    // 粒子积分 + 花型特有行为 + 淡出着色
    const drag = Math.pow(DRAG_PER_S, dt);
    for (let i = HEAD_MAX; i < MAX; i++) {
      if (life[i] <= 0) continue;
      life[i] -= dt;
      const i3 = i * 3;
      if (splitA[i] > 0 && life[i] <= splitA[i]) { splitStar(i); continue; }
      vel[i3 + 1] -= gravA[i] * dt;
      vel[i3] *= drag; vel[i3 + 1] *= drag; vel[i3 + 2] *= drag;
      pos[i3] += vel[i3] * dt;
      pos[i3 + 1] += vel[i3 + 1] * dt;
      pos[i3 + 2] += vel[i3 + 2] * dt;
      let f = Math.max(0, life[i] / life0[i]);
      f = Math.pow(f, 1.35);   // 后段加速熄灭, 颗粒全程保持锐利
      if (twA[i] > 0) f *= 1 - twA[i] * (0.5 + 0.5 * Math.sin(now * 14 + phA[i]));
      const b = f * bright;
      colA[i3] = base[i3] * b;
      colA[i3 + 1] = base[i3 + 1] * b;
      colA[i3 + 2] = base[i3 + 2] * b;
      if (life[i] <= 0) kill(i);
    }
    // uScale = 画布半高(设备像素): gl_PointSize 公式与 three 内部 points 一致
    if (renderer) {
      points.material.uniforms.uScale.value = Math.max(1, renderer.domElement.height / (renderer.getPixelRatio() || 1) / 2); // CSS 像素基准, Hi-DPI 不放大
    }
    geo.attributes.position.needsUpdate = true;
    geo.attributes.aColor.needsUpdate = true;
    geo.attributes.aSize.needsUpdate = true;
    flash.intensity *= Math.exp(-dt * 7);
    if (flash.intensity < 0.05) flash.intensity = 0;
    mflash.intensity *= Math.exp(-dt * 10);
    if (mflash.intensity < 0.05) mflash.intensity = 0;
  }

  function applySettings(s) {
    period = Math.max(0, s.fireworkPeriod ?? 30);
    bright = Math.min(2, Math.max(0, s.fireworkBright ?? 100)) / 100;
    height = Math.min(90, Math.max(25, s.fireworkHeight ?? 55));
  }

  return {
    update, applySettings, fire, isReady, setLaunchers,
    getLaunchers: () => launchers,
  };
}
