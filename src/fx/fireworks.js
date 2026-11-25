// 烟花系统 v2: 三型发射器 × 全弹道可见 × 6 站布点（+ 过山车顶旁第 7 座垂柳塔）+ 自动秀编排 + F 点射 + 地标礼花
// 弹道五段全程可读: 管口点火闪光 → 亮彗星头 + 密集尾迹 → 顶点白热爆闪 → 花型展开 → 余烬闪烁熄灭
// 花型: A 牡丹(三层球壳) / B 垂柳(金瀑长垂+滴烬) / C 椰芯(大火星二次炸裂)
// 架构: 单 Points 池 ShaderMaterial 加色混合, CPU 积分; 彗星头占池首专用槽位, 其余粒子环形覆写
// 声音: 升空 / 爆裂 / 火星分裂三个触发点把事件位置换算成「距离 + 方位」交给 audio;
//       音色合成、声延迟(343m/s)、距离衰减、声像都在 core/fw_sound.js
// 主题色板与品牌色一致; 零外部素材
// 火星画法 (2026-11-25 细锐化): 高斯亮核 + 屏幕尺寸上限 + 能量补偿, 亮度滑杆 100% = BRIGHT_BASE (见常量区)
// 地标礼花 (2026-11-25): 缠魂塔环廊 / 摩天轮顶舱 / 过山车提升顶 旁的三处定向炸点 —— 壳体飞满固定时长恰好落在炸点,
//       炸点高度 = 该处观景眼位 + 设置「地标炸点高度」(相对值); 发射架/炸点表/到顶触发见 fx/fw_director.js
import * as THREE from "three";

const MAX = 10240;       // 粒子池容量（7 站终曲 + 三处地标礼花逐帧实测峰值约 6400 并发; 留出与下一轮常规秀重叠的余量; stats().overflow 应为 0）
const HEAD_MAX = 16;     // 池首保留槽位: 彗星头专用（常规粒子从 HEAD_MAX 起环形覆写, 不会侵占头部）
const GRAV = 3.2;        // 余烬重力（远小于真实 g, 梦幻缓坠）
const DRAG_PER_S = 0.6;  // vel *= DRAG_PER_S^dt 的大气阻尼
const SHELL_G = 7.5;     // 壳体升空重力（v0y 由炸点高度反解: v0y = sqrt(2·SHELL_G·h)）
const V_BURST = 2.5;     // 壳体竖直速度降到此值即爆（常规弹; 定向弹按同一口径反解飞行时长, 到点时也是这个速度）
const PAN_SPREAD = 0.85; // 炸点在相机右侧 → pan = +0.85, 左侧 → -0.85（等功率声像的方位系数）

// ---- 火星画法: 把火星当「点光源」画——亮核很小、个头几乎不随距离变, 距离感靠亮度 ----
// 精灵尺寸 = 世界尺寸投影(随 1/距离) 再钳到屏幕上下限。没有上限时近看(缠魂塔上 26-46m)一颗火星
// 是 20-50px 的软圆片, 满屏散景; 11-17 的颗粒语言是按地面 47-57m 标定的, 当时没有这么近的机位。
const SIZE_CAP = 0.0157;  // 精灵屏幕上限 / uScale(画布 CSS 半高): 1271px 高的画布上, aSize=SIZE_REF 的火星约 10px
const SIZE_REF = 2.1;     // 「普通火星」的 aSize(牡丹均值); 上限按 sqrt(aSize/SIZE_REF) 浮动, 保住 大火星 > 火星 > 尾迹 的个头差
const SIZE_MIN = 1.5;     // 精灵屏幕下限(像素), 防远处亚像素闪烁
const CAP_BOOST = 0.25;   // 被上限截断时的能量补偿: vColor × (原尺寸/钳后尺寸)^(2×CAP_BOOST)。0 = 不补(近处不更亮); 0.5 = 按直径比补(近处炸点糊成光团)
const BRIGHT_BASE = 0.2;  // 亮度滑杆 100% 对应的系数: 与高斯亮核配套标定(0.6 时爆裂后 0.5s 内辉光会把炸点周围的天空冲灰)

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

// 火星纹理: 高斯亮核 + 弱晕。片元按 alpha² 落地(加色混合写法见片元着色器), 所以这里画的是
// alpha = exp(-½(r/σ)²), σ = 0.52 个渐变半径 → 实际亮度半高全宽约为精灵直径的 41%。
// (旧纹理是 55% 半径内全亮的平顶圆片: 远看是光点, 近看就是一张软边圆片——没有亮核, 变暗时只剩灰色平圆片)
const GLOW_SIGMA = 0.52;
function makeGlowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 30);
  for (let i = 0; i < 24; i++) {
    const t = i / 24;
    grad.addColorStop(t, `rgba(255,255,255,${Math.exp(-0.5 * (t / GLOW_SIGMA) ** 2).toFixed(4)})`);
  }
  grad.addColorStop(1, "rgba(255,255,255,0)"); // 渐变圆外(精灵四角)取末档颜色, 末档必须归零, 否则四角带一层淡光
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
      uniforms: {
        uMap: { value: makeGlowTexture() }, uScale: { value: 720 },
        uMaxPx: { value: 720 }, uMinPx: { value: SIZE_MIN }, uBoostExp: { value: CAP_BOOST },
      },
      vertexShader: /* glsl */ `
        attribute vec3 aColor;
        attribute float aSize;
        uniform float uScale;
        uniform float uMaxPx;
        uniform float uMinPx;
        uniform float uBoostExp;
        varying vec3 vColor;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          // 世界尺寸投影(与 three 内置 points 同式) → 钳到屏幕上下限; 上下限随 aSize 浮动
          float s = aSize * (uScale / max(1.0, -mv.z));
          float rel = clamp(sqrt(aSize / ${SIZE_REF}), 0.5, 1.45);
          float px = clamp(s, uMinPx * rel, uMaxPx * rel);
          // 被钳掉的尺寸补成亮度: 近处的火星更亮, 而不是更大
          vColor = aColor * pow(s / px, 2.0 * uBoostExp);
          gl_PointSize = px;
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        uniform sampler2D uMap;
        varying vec3 vColor;
        void main() {
          float a = texture2D(uMap, gl_PointCoord).a;
          // 加色混合按 src×srcAlpha 累加, 而 rgb 已乘过一次 a → 实际落地的亮度按 a² 衰减
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
  let cdUntil = new Float64Array(FALLBACK.length).fill(-1);   // 各发射架的装填截止时刻（随 setLaunchers 重建）
  const shells = [];    // 升空壳体 { p, v, kind, color, head, acc, T?, p0?, aid? }; T>0 = 定向弹
  const pending = [];   // 齐射队列 { at, lid, aim? }; aim = 定向弹的炸点 { x, y, z, T, aid }
  let period = 30;      // 自动秀间隔（秒, 0 = 关闭）
  let bright = 1;
  let height = 55;      // 地面炸点高度（米, 设置项「地面炸点高度」; 花型内再叠 ±8% 自然变化）
  // 地标礼花: anchors = [{ id, lid, x, z, eye }] 由 fx/fw_director.js 按实际地标几何登记;
  // 炸点 = (x, eye + saluteDy, z), 设置项「到顶礼花」是总开关
  let anchors = [];
  let saluteOn = true;
  let saluteDy = 0;       // 「地标炸点高度」: 相对各处观景眼位的高度差（米, 0 = 平视）
  const saluteAt = {};    // 各炸点上一发的发射时刻（导演据此给塔顶驻留留间隔）
  let onBurst = null;     // 取证钩子: 每次爆裂回调 { kind, x, y, z, t, aimed, aid }
  let overflow = 0;       // 池子真满时覆写存活粒子的累计数（取证用, 正常为 0）
  let salutesQueued = 0;  // 已入列的地标礼花累计数（取证用: 每轮秀后排了几发）
  let nextShow = 8;     // 入园后 8s 首秀
  let showCount = 0;
  let now = 0;
  let headCursor = 0;

  const _c = new THREE.Color();
  const _c2 = new THREE.Color();
  const _v = new THREE.Vector3();
  const _tp = new THREE.Vector3();
  const _prev = new THREE.Vector3();
  const _right = new THREE.Vector3();
  const _bp = new THREE.Vector3();

  // 声学参数: 事件位置 → 到相机的距离 + 相对相机右方的方位（-1 左 .. 1 右）
  function acoustics(p) {
    if (!camera) return { dist: 60, pan: 0 };
    _v.set(p.x - camera.position.x, p.y - camera.position.y, p.z - camera.position.z);
    const d = _v.length() || 1;
    _right.setFromMatrixColumn(camera.matrixWorld, 0);
    return { dist: d, pan: PAN_SPREAD * Math.max(-1, Math.min(1, _v.dot(_right) / d)) };
  }

  function spawn(p, v, color, l, size, opt = {}) {
    let i = cursor;
    if (life[i] > 0) {
      // 环形的下一格还活着 → 往后找空位（扫完一整圈），池子真的满了才覆写。
      // 纯环形在终曲里会追上还没烧完的第一波火星（垂柳寿命 3–4s 比绕池一圈的时间长），让它们提前消失;
      // 同一场爆裂的几百颗火星在池里连成一片, 所以要扫到圈底, 不能只探一小段。
      // 常规秀下一格总是空的, 走不到这里, 与逐格环形完全一致
      const nMax = MAX - HEAD_MAX;
      let n = 0;
      do {
        i = HEAD_MAX + ((i - HEAD_MAX + 1) % nMax);
        n++;
      } while (life[i] > 0 && n < nMax);
      if (life[i] > 0) overflow++;   // 池子真满: 只能覆写（取证用, 正常为 0）
    }
    cursor = HEAD_MAX + ((i - HEAD_MAX + 1) % (MAX - HEAD_MAX));
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

  // 常规弹的升空秒数: 竖直速度从 v0y 降到 V_BURST。定向弹拿它当飞行时长 —— 到点时竖直速度恰为 V_BURST
  // (近顶点, 与常规弹同观感), 哨音长度也与常规弹同口径
  function ascentTime(dy) {
    const h = Math.max(3, dy);
    return Math.min(3.6, Math.max(1.6, (-V_BURST + Math.sqrt(V_BURST * V_BURST + 2 * SHELL_G * h)) / SHELL_G));
  }

  // ---------- 发射 ----------
  // aim 省略 = 常规弹（竖直上升 + 朝园心漂移, v.y 降到 V_BURST 即爆）
  // aim = { x, y, z, T } = 定向弹（地标礼花）: 飞满 T 秒恰好落在 (x, y, z)
  function launchShell(lid, aim) {
    const L = launchers[lid];
    if (!L) return;
    const kind = L.kind;
    const colors = pal(kind);
    const color = colors[(Math.random() * colors.length) | 0];
    // 常规弹: 炸点高度 -> 反解初速（v.y 降到 V_BURST 时爆, 高度补回 V_BURST²/2g）
    const h = Math.max(20, height * (1 + (Math.random() - 0.5) * 0.16));
    const v0y = Math.sqrt(2 * SHELL_G * (h + 0.42));
    // 管口点火: 迸火花 + 光脉冲（升空声在壳体入列后触发, 需要用到初速算升空时长）
    _tp.set(L.x + (Math.random() - 0.5) * 0.24, L.mz, L.z + (Math.random() - 0.5) * 0.24);
    for (let k = 0; k < 10; k++) {
      _v.set((Math.random() - 0.5) * 3.4, 0.8 + Math.random() * 2.2, (Math.random() - 0.5) * 3.4);
      spawn(_tp, _v, _c.set(COL_TRAIL), 0.22 + Math.random() * 0.22, 1.5 + Math.random() * 0.5);
    }
    mflash.position.copy(_tp);
    mflash.intensity = 14 * bright;
    const p = _tp.clone();
    let v, asc;
    if (aim) {
      // 定向: 炸点加少量散布（垂直于射向 ±1m / 高度 ±2%）;
      // p(T) = q → v = (q − o)/T + ½·g·T（竖直）; T 由 ascentTime 按炸点高度给出
      const T = aim.T ?? ascentTime(aim.y - L.mz);
      const ddx = aim.x - p.x, ddz = aim.z - p.z;
      const dl = Math.hypot(ddx, ddz) || 1;
      const lat = (Math.random() - 0.5) * 2;
      const q = new THREE.Vector3(
        aim.x + (-ddz / dl) * lat,
        aim.y * (1 + (Math.random() - 0.5) * 0.04),
        aim.z + (ddx / dl) * lat
      );
      _bp.copy(q);                                    // 炸点（升空声收尾用）
      v = q.sub(p).divideScalar(T);
      v.y += 0.5 * SHELL_G * T;
      asc = T;
    } else {
      // 壳体: 沿发射方向漂移 + 少量横向散布
      const hs = 2.0 + Math.random() * 2.0;
      const px = -L.dz, pz = L.dx; // 横向单位向量
      v = new THREE.Vector3(
        L.dx * hs + px * (Math.random() - 0.5) * 1.4,
        v0y,
        L.dz * hs + pz * (Math.random() - 0.5) * 1.4
      );
      asc = (v0y - V_BURST) / SHELL_G;
      _bp.copy(_tp).addScaledVector(v, asc);
      _bp.y = _tp.y + v0y * asc - 0.5 * SHELL_G * asc * asc;
    }
    const head = headCursor;
    headCursor = (headCursor + 1) % HEAD_MAX;
    shells.push(aim
      ? { p, v, kind, color, head, acc: 0, T: asc, p0: p.clone(), aid: aim.aid ?? null }
      : { p, v, kind, color, head, acc: 0, T: 0 });
    // 升空声: 管口闷响 + 连续哨音。哨音响到炸点为止, 时长 = 实际升空时间（与壳体积分同口径）;
    // endDist = 炸点到听者的距离, 哨音收尾落在「炸点时刻 + 炸点声延迟」
    if (audio) audio.fireworkLaunch({ ...acoustics(_tp), ascent: asc, endDist: acoustics(_bp).dist });
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
    // 分裂脆响: 按这颗火星自己的位置做声延迟 / 衰减 / 声像
    audio?.fireworkCrack(acoustics(_tp));
    kill(i);
  }

  function burstShell(sh) {
    onBurst?.({ kind: sh.kind, x: sh.p.x, y: sh.p.y, z: sh.p.z, t: now, aimed: sh.T > 0, aid: sh.aid }); // 取证钩子
    kill(sh.head);
    if (sh.kind === "A") burstPeony(sh);
    else if (sh.kind === "B") burstWillow(sh);
    else burstCrossette(sh);
    flash.position.copy(sh.p);
    flash.color.copy(sh.color);
    flash.intensity = (sh.kind === "A" ? 60 : sh.kind === "B" ? 38 : 50) * bright;
    // 爆裂声: 声延迟 / 距离衰减 / 空气吸声 / 声像由播放引擎按炸点位置处理
    audio?.fireworkBurst(sh.kind, acoustics(sh.p));
  }

  // ---------- 编排 ----------
  // 地标礼花入列: 常规秀穿插 / 终曲收尾用。开关关闭或炸点表为空时不排
  function queueSalute(at, a) {
    if (!saluteOn || !a) return;
    pending.push({ at, lid: a.lid, aim: { ...flightOf(a), aid: a.id } });
    saluteAt[a.id] = now + at;
    salutesQueued++;
  }

  function scheduleShow() {
    if (!launchers.length) return;
    showCount++;
    if (showCount % 4 === 0) {
      // 终曲: 全部发射架 × 两波错落, 收尾每处地标炸点各一发
      let t = 0.2;
      for (let w = 0; w < 2; w++) {
        for (let i = 0; i < launchers.length; i++) {
          pending.push({ at: t, lid: i });
          if (Math.random() < 0.5) pending.push({ at: t + 0.25 + Math.random() * 0.3, lid: i });
          t += 0.3 + Math.random() * 0.4;
        }
      }
      for (const a of anchors) queueSalute(t + Math.random() * 0.8, a);
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
      // 一半概率补一发地标礼花: 没人在顶上时, 地面也看得到地标烟花
      if (anchors.length && Math.random() < 0.5) {
        queueSalute(t + Math.random() * 0.8, anchors[(Math.random() * anchors.length) | 0]);
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
      cdUntil = new Float64Array(list.length).fill(-1);   // 装填冷却随发射架数量重建（原为按兜底 6 座定长, 加站会写不进）
    }
  }

  // ---------- 地标礼花 ----------
  const anchorById = (aid) => anchors.find((a) => a.id === aid);

  // 当前设置下某炸点的落点与飞行时长 { x, y, z, T }
  function flightOf(a) {
    const L = a && launchers[a.lid];
    if (!L || !Number.isFinite(a.eye)) return null;
    const y = a.eye + saluteDy;
    return { x: a.x, y, z: a.z, T: ascentTime(y - L.mz) };
  }

  // 朝炸点打一发（0.02s 后出膛）。返回是否已入列; 开关关闭 / 炸点或发射架缺失时为 false
  function salute(aid) {
    const a = saluteOn ? anchorById(aid) : null;
    const f = flightOf(a);
    if (!f) return false;
    pending.push({ at: 0.02, lid: a.lid, aim: { ...f, aid } });
    saluteAt[aid] = now;
    salutesQueued++;
    return true;
  }

  function setAnchors(list) {
    anchors = (Array.isArray(list) ? list : []).filter((a) => a && flightOf(a));
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
        launchShell(pending[k].lid, pending[k].aim);
        pending.splice(k, 1);
      }
    }
    // 壳体升空: 彗星头直写 + 密集尾迹 + 起爆
    for (let k = shells.length - 1; k >= 0; k--) {
      const sh = shells[k];
      _prev.copy(sh.p);
      let vy; // 本帧竖直速度（尾迹撒星用）
      if (sh.T > 0) {
        // 定向弹: 位置取闭式解 p(t) = p0 + v·t − ½g t²（半隐式欧拉的累计和会随帧率低 0.1–0.35m, 定点起爆不能用它）
        sh.acc = Math.min(sh.acc + dt, sh.T);
        sh.p.copy(sh.p0).addScaledVector(sh.v, sh.acc);
        sh.p.y -= 0.5 * SHELL_G * sh.acc * sh.acc;
        vy = sh.v.y - SHELL_G * sh.acc;
      } else {
        sh.v.y -= SHELL_G * dt;
        sh.p.addScaledVector(sh.v, dt);
        sh.acc += dt;
        vy = sh.v.y;
      }
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
               (Math.random() - 0.5) * 1.6 + vy * 0.12,
               (Math.random() - 0.5) * 1.6 + sh.v.z * 0.12);
        spawn(_tp, _v, _c.set(COL_TRAIL), 0.3 + Math.random() * 0.3, 0.45 + Math.random() * 0.25);
      }
      // 常规弹: 竖直速度降到 V_BURST 即爆; 定向弹: 飞满 T 秒起爆（时刻误差 ≤ 1 帧）
      if (sh.T > 0 ? sh.acc >= sh.T : vy < V_BURST) {
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
      // 椰芯大火星: 飞行 splitAt 秒后二次炸裂。寿命 = splitAt + 0.05, 余命降到那 0.05s 保险余量即到点
      // （原先拿余命直接比 splitAt, 结果爆裂后 0.05s 就分裂, 与注释和音效的 0.8-1.2s 都对不上）
      if (splitA[i] > 0 && life[i] <= life0[i] - splitA[i]) { splitStar(i); continue; }
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
    if (renderer) {
      // uScale = 画布 CSS 半高: 精灵尺寸与上限都以它为基准, 同一视场角下各分辨率/缩放的火星视角大小一致
      const u = points.material.uniforms;
      u.uScale.value = Math.max(1, renderer.domElement.height / (renderer.getPixelRatio() || 1) / 2); // CSS 像素基准, Hi-DPI 不放大
      u.uMaxPx.value = Math.max(3, u.uScale.value * SIZE_CAP);
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
    // 先除 100 再钳 0–2。旧写法 Math.min(2, Math.max(0, 值)) / 100 是先钳后除: 滑杆 5–200 一律得 0.02,
    // 亮度设置自 f2703d2 起实际失效, 火星一直按设计亮度的 2% 渲染(灰平片、从不过辉光阈值)
    bright = Math.min(2, Math.max(0, (s.fireworkBright ?? 100) / 100)) * BRIGHT_BASE;
    height = Math.min(90, Math.max(25, s.fireworkHeight ?? 55));
    // 地标礼花: 总开关 + 炸点相对各处观景眼位的高度差（米）
    saluteOn = s.fireworkSalute !== false;
    saluteDy = Math.min(40, Math.max(-20, s.fireworkSaluteHeight ?? 0));
  }

  // 存活粒子数（取证用, 按需遍历）
  function aliveCount() {
    let n = 0;
    for (let i = HEAD_MAX; i < MAX; i++) if (life[i] > 0) n++;
    return n;
  }

  return {
    update, applySettings, fire, isReady, setLaunchers,
    getLaunchers: () => launchers,
    // 地标礼花
    salute, setAnchors,
    saluteFlight: (aid) => flightOf(anchorById(aid)),   // { x, y, z, T }: 当前设置下的落点与飞行时长
    getAnchors: () => anchors,
    lastSalute: (aid) => saluteAt[aid] ?? -1e9,          // 某炸点上一发的发射时刻
    set onBurst(fn) { onBurst = fn; },
    // 取证辅助
    debugShow: scheduleShow,                             // 立即排一轮秀（终曲每 4 轮一次）
    stats: () => ({ overflow, salutesQueued, alive: aliveCount(), pending: pending.length, shells: shells.length }),
  };
}
