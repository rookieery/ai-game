// 烟花试听/取证共用的事件脚本 —— 复刻 src/fx/fireworks.js 的站点、升空时长与编排
// 输出「声学事件」表: { t 画面时刻(s), type: launch|burst|crack, kind: A|B|C, dist 距离(m), pan 方位(-1 左..1 右) }
// 声延迟由 createFwVoice 按 dist 叠加, 这里的 t 永远是「看见」的时刻
// 听者默认站园心 (0, 1.6, 0), 面朝 -z, 右方 +x
export const HEIGHT = 55;      // 炸点高度（设置项默认值）
const SHELL_G = 7.5;           // 与 fireworks.js 一致

// 与 fireworks.js FALLBACK / park_env.py LAUNCHER_SITES 同步
export const SITES = [
  { id: "L1", kind: "A", x: 22,   z: 22,  dx: -0.707, dz: -0.707, mz: 1.63 },
  { id: "L2", kind: "A", x: 56,   z: -30, dx: -0.882, dz: 0.473,  mz: 1.63 },
  { id: "L3", kind: "B", x: 43.5, z: 45,  dx: -0.695, dz: -0.719, mz: 2.92 },
  { id: "L4", kind: "B", x: -55,  z: -30, dx: 0.878,  dz: 0.479,  mz: 2.92 },
  { id: "L5", kind: "C", x: -30,  z: 24,  dx: 0.781,  dz: -0.625, mz: 1.28 },
  { id: "L6", kind: "C", x: 11,   z: 84,  dx: -0.13,  dz: -0.991, mz: 1.28 },
];
export const LISTENER = { x: 0, y: 1.6, z: 0 };
export const PAN_SPREAD = 0.85; // 方位系数（与接入游戏时一致）

export function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 壳体升空时长: v.y 降到 2.5 时爆（同 fireworks.js）
export function ascentSeconds(h = HEIGHT) {
  return (Math.sqrt(2 * SHELL_G * (h + 0.42)) - 2.5) / SHELL_G;
}

// 画面方位 → 声学参数
export function spatial(p, listener = LISTENER) {
  const dx = p.x - listener.x, dy = p.y - listener.y, dz = p.z - listener.z;
  const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
  const pan = PAN_SPREAD * Math.max(-1, Math.min(1, dx / (dist || 1)));
  return { dist, pan };
}

// 椰芯火星分裂: 16-20 颗, 爆后 0.8-1.2s 内各自炸开, 位置散在 ~10m 球内
function pushCracks(out, p, tBurst, rng) {
  const n = 16 + ((rng() * 5) | 0);
  for (let k = 0; k < n; k++) {
    const q = { x: p.x + (rng() - 0.5) * 20, y: p.y + (rng() - 0.5) * 20, z: p.z + (rng() - 0.5) * 20 };
    const s = spatial(q);
    out.push({ t: tBurst + 0.8 + rng() * 0.4, type: "crack", kind: "C", dist: s.dist, pan: s.pan });
  }
}

// 单发（试听页滑杆）: 固定距离/方位; withLaunch 时提前一个升空时长给出「管口闷响 + 连续哨音」
// 升空事件带 ascent（升空秒数）与 endDist（炸点到听者的距离）: 哨音据此响到炸点为止
export function singleEvents(kind, { dist = 80, pan = 0, t = 0, withLaunch = false, rng = Math.random } = {}) {
  const out = [];
  if (withLaunch) out.push({ t: t - ascentSeconds(), type: "launch", kind, dist, pan, ascent: ascentSeconds(), endDist: dist });
  out.push({ t, type: "burst", kind, dist, pan });
  if (kind === "C") {
    const n = 16 + ((rng() * 5) | 0);
    for (let k = 0; k < n; k++) {
      out.push({
        t: t + 0.8 + rng() * 0.4, type: "crack", kind: "C",
        dist: dist + (rng() - 0.5) * 22,
        pan: Math.max(-1, Math.min(1, pan + (rng() - 0.5) * 0.3)),
      });
    }
  }
  return out;
}

// 某站一发: 管口升空 → 炸点爆裂（→ 椰芯分裂）
export function shellEvents(site, t0, rng, withLaunch = true) {
  const out = [];
  const tube = { x: site.x, y: site.mz, z: site.z };
  const h = HEIGHT * (1 + (rng() - 0.5) * 0.16);
  const asc = ascentSeconds(h);
  const hs = 2 + rng() * 2;                               // 沿发射方向的漂移速度
  const px = -site.dz, pz = site.dx;                      // 横向单位向量
  const lat = (rng() - 0.5) * 1.4;
  const burst = { x: site.x + (site.dx * hs + px * lat) * asc, y: site.mz + h, z: site.z + (site.dz * hs + pz * lat) * asc };
  if (withLaunch) out.push({ t: t0, type: "launch", kind: site.kind, ...spatial(tube), ascent: asc, endDist: spatial(burst).dist });
  out.push({ t: t0 + asc, type: "burst", kind: site.kind, ...spatial(burst) });
  if (site.kind === "C") pushCracks(out, burst, t0 + asc, rng);
  return out;
}

// 终曲（复刻 scheduleShow 的 showCount % 4 === 0 分支）: 6 站全开 × 两波错落, 约一半再加一发
export function finaleEvents(seed = 20261123, { t0 = 0.5, withLaunch = false } = {}) {
  const rng = mulberry32(seed);
  const out = [];
  let t = t0 + 0.2;
  for (let w = 0; w < 2; w++) {
    for (let i = 0; i < SITES.length; i++) {
      out.push(...shellEvents(SITES[i], t, rng, withLaunch));
      if (rng() < 0.5) out.push(...shellEvents(SITES[i], t + 0.25 + rng() * 0.3, rng, withLaunch));
      t += 0.3 + rng() * 0.4;
    }
  }
  out.sort((a, b) => a.t - b.t);
  return out;
}

// 常规场（复刻 scheduleShow 的常规分支）: 随机 2-3 台错落
export function regularEvents(seed = 7, { t0 = 0.5, withLaunch = true } = {}) {
  const rng = mulberry32(seed);
  const idx = SITES.map((_, i) => i);
  for (let k = idx.length - 1; k > 0; k--) {
    const j = (rng() * (k + 1)) | 0;
    [idx[k], idx[j]] = [idx[j], idx[k]];
  }
  const out = [];
  let t = t0 + 0.1;
  for (const i of idx.slice(0, 2 + ((rng() * 2) | 0))) {
    out.push(...shellEvents(SITES[i], t, rng, withLaunch));
    if (rng() < 0.6) out.push(...shellEvents(SITES[i], t + 0.3 + rng() * 0.4, rng, withLaunch));
    t += 0.5 + rng() * 0.7;
  }
  out.sort((a, b) => a.t - b.t);
  return out;
}

// 远近对比: 同一牡丹 40m(左前) 与 195m(右前), 再来一发 80m 的垂柳（含近处管口升空 + 全程哨音）
export function nearFarEvents() {
  const b = spatial({ x: 0, y: 56, z: -80 });
  const asc = ascentSeconds();
  return [
    { t: 0.5, type: "burst", kind: "A", ...spatial({ x: -18, y: 30, z: -24 }) },
    { t: 6.5, type: "burst", kind: "A", ...spatial({ x: 120, y: 55, z: -150 }) },
    { t: 13, type: "launch", kind: "B", dist: 25, pan: 0.2, ascent: asc, endDist: b.dist },
    { t: 13 + asc, type: "burst", kind: "B", ...b },
  ];
}

// 整场试听: 常规场 → 间隔 → 终曲
export function showEvents(seed = 7) {
  const a = regularEvents(seed, { t0: 0.5 });
  const b = finaleEvents(20261123, { t0: 14, withLaunch: true });
  return [...a, ...b];
}

export const lastTime = (events) => events.reduce((m, e) => Math.max(m, e.t), 0);
