// 烟花音色程序化合成器（纯 JS DSP → AudioBuffer + 实时节点，零音频素材）
// 分工: 本文件只管「烟花怎么响」; audio.js 负责把它接到 master、套设置项与静音
// 调参与试听: prototype/fw_sound/ 试听页 + scripts/probe_fw_audio.mjs 取证探针
//
// 爆裂音色分层（对照实录航弹的「裂 → 轰 → 滚」三段）:
//   crack    裂响    两阶高通的白噪 + 阻尼共振 + 毫秒级瞬态, 20ms 内衰完 —— 「啪」的那一下
//   crackle  碎裂    裂响之后 30-200ms 一串稀疏的高频微爆 —— 「噼里啪啦」(独立音色, 可开关)
//   body     轰鸣    晚裂响 14ms 进入; 白噪过快速下扫的低通, 幅度被「泊松微爆簇」调制(火星陆续点燃)
//   sub      低频冲击  80-100Hz 阻尼正弦, 音高只微降, ~0.15s 内衰完
//   tail     滚动尾音  淡入的低通噪声 + 快慢两层起伏 + 一串「涌动」(越远越稀越弱的反射簇)
// 升空: 管口闷响(音色库) + 实时合成的连续哨音（音高随高度上滑, 一直响到炸点; 见 createFwVoice.launch）
// 播放层: 距离 → 声延迟(343m/s) / 1/d 衰减 / 空气吸声低通; 方位 → 等功率声像
// 零外部素材, 参数表 FW_SOUND / FW_CRACKLE / FW_ASCENT / FW_SPACE 可整体重调
const TAU = Math.PI * 2;
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

function rng32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- 爆裂音色参数表（每发在表值上再做 ±15~25% 抖动） ----------
const BASE = {
  dur: 3.0,          // 音色总长（秒）
  hp: 28,            // 末级高通（Hz）: 切掉次声, 省动态余量
  crack: {           // 裂响
    hp: 1800,        //   高通截止（两阶: 只留「脆」的高频, 和轰鸣拉开距离）
    tau: 0.011,      //   衰减时间常数
    level: 1.7,      //   电平（相对 body）
    snapF: 3100, snapTau: 0.0045, snapLevel: 0.5,     // 阻尼共振: 「脆」的来处
    clickF: 5800, clickTau: 0.0014, clickLevel: 0.5,  // 毫秒级瞬态: 起振的「尖」
  },
  body: {            // 轰鸣
    fc0: 4000, fc1: 150, fcTau: 0.11,   // 低通截止 fc0 → fc1: 起振后约 100ms 就沉下去, 中频不拖泥带水
    comp: 0.35,      //   变暗的能量补偿指数（0.5 = 全补偿）
    tau: 0.19, attack: 0.014,           // 包络: 晚于裂响进入, 「啪」先出来「轰」跟在后面
    floor: 0.30,     //   微爆簇变疏后的幅度下限
    level: 1.0, drive: 1.25,            // 电平 / 软削波激励
    rate0: 1100, rateTau: 0.11, popTau: 0.0045,   // 泊松微爆簇: 起始速率 / 速率衰减 / 单颗衰减
  },
  sub: {             // 低频冲击
    f0: 104, f1: 82, glide: 0.09,        // 音高 f0 → f1（只微降; 真烟花可听能量峰在 125-500Hz, 太低小喇叭出不来）
    tau: 0.13, attack: 0.018, level: 0.34,
  },
  tail: {            // 滚动尾音
    tau: 0.80, level: 1.5, comp: 0.45,  // 包络 / 变暗的能量补偿指数（0.5 = 全补偿）
    attack: 0.09,                       // 淡入: 混响需要时间建立, 不糊住起振
    fc0: 1200, fc1: 120, fcTau: 0.85,   // 低通截止下扫: 先带中频的「隆隆」, 约半秒沉成纯低频
    resF: 170, resQ: 1.2, resDb: 6,     // 「滚」的胸腔共鸣
    lfoRate: 3, lfoDepth: 0.35,         // 慢起伏（一阵一阵）
    lfo2Rate: 13, lfo2Depth: 0.2,       // 快起伏（十几 Hz 的「噜噜」, 区别于风声的要点）
    swells: 7, swellMax: 0.9,           // 涌动(反射簇)个数上限 / 最大幅度
  },
};
const mix = (a, b) => ({
  ...a, ...b,
  crack: { ...a.crack, ...b.crack },
  body: { ...a.body, ...b.body },
  sub: { ...a.sub, ...b.sub },
  tail: { ...a.tail, ...b.tail },
});

export const FW_SOUND = {
  A: BASE,                                 // 牡丹: 标准航弹
  B: mix(BASE, {                           // 垂柳: 口径更大 —— 更低、更沉、尾音更长
    dur: 4.2,
    crack: { level: 1.9, hp: 1800 },
    body: { fc0: 3000, fc1: 130, fcTau: 0.16, tau: 0.22, drive: 1.4 },
    sub: { f0: 88, f1: 68, tau: 0.20, level: 0.30 },
    tail: { tau: 1.20, level: 1.6 },         // 尾音更长
  }),
  C: mix(BASE, {                           // 椰芯主爆: 小口径, 偏「啪」
    dur: 2.0,
    crack: { level: 1.7, hp: 2100, tau: 0.009 },
    body: { fc0: 5200, fc1: 220, fcTau: 0.08, tau: 0.11, drive: 1.1 },
    sub: { f0: 120, f1: 92, tau: 0.08, level: 0.26 },
    tail: { tau: 0.40, level: 1.0, fc0: 1200, fc1: 160, fcTau: 0.45, swells: 3 },
  }),
  crack: mix(BASE, {                       // 椰芯火星分裂: 一声脆响 + 园区短回响
    dur: 0.8, hp: 45,
    crack: { level: 2.2, tau: 0.013, hp: 1600, snapLevel: 0.6 },
    body: { fc0: 2800, fc1: 420, fcTau: 0.05, tau: 0.04, drive: 1.0, rate0: 1500, rateTau: 0.03 },
    sub: { f0: 150, f1: 120, tau: 0.05, level: 0.28 },
    tail: { tau: 0.20, level: 0.8, fc0: 1800, fc1: 260, fcTau: 0.3, swells: 1, lfoDepth: 0.3, resF: 220 },
  }),
};

// 碎裂层: 排在裂响之后、稀疏的高频微爆（「少量噼里啪啦」）; 全程约 30 颗, 越来越稀
export const FW_CRACKLE = {
  dur: 0.45,
  hp: 2800,           // 高通（两阶）
  popTau: 0.0022,     // 单颗衰减
  t0: 0.035,          // 首颗相对爆点的时刻
  rate0: 260,         // 起始速率（颗/秒）, 按 rateTau 衰减 → 全程约 20 颗, 集中在前 150ms
  rateTau: 0.07,
  floorTau: 0.25,     // 零星拖尾的速率（25 颗/秒起）同样衰减, 0.45s 后不再出
  resF: 5200, resTau: 0.003, resLevel: 0.6,   // 约三分之一带一点金属共鸣
};

// 升空哨音（实时合成, 时长 = 实际升空时间）
export const FW_ASCENT = {
  f0: 900, f1: 2700,            // 音高: 随高度占比从 f0 上滑到 f1（实测升空哨音集中在 2-3kHz）
  endRatio: 0.09,               // 壳体末速/初速 → 按减速上升的轨迹走, 越近顶点滑得越慢
  vibRate: 5.5, vibDepth: 0.012,   // 轻微颤音
  breathQ: 18,                  // 跟随音高的窄带噪声「气声」带宽
  attack: 0.06, fade: 0.012,    // 起音 / 炸点处收尾（只防咔哒, 不做渐弱）
  holdDrop: 0.7,                // 到顶点前的自然渐弱（-3dB）, 之后一直响到炸点
  level: 0.141,                 // 80m 处哨音 A 计权有效值 ≈ 牡丹爆裂起振(最响 100ms) 的 −12dB（probe 多次抽样校准）
  capGain: 2.5,                 // 多发叠加: 在场哨音总功率封顶在单发的 2.5 倍（+4dB）, 终曲不糊成一片
};
// 升空音色预设: tone 三角波哨音 / breath 窄带气声 / hiss 宽带嘶声（相对电平）
export const FW_ASCENT_STYLES = {
  even: { tone: 0.8, breath: 1.0, hiss: 1.0 },     // 哨音 + 嘶声各半（默认, 用户试听选定 2026-11-23）
  whistle: { tone: 1.0, breath: 0.5, hiss: 0.25 }, // 哨音为主
  pure: { tone: 1.0, breath: 0.2, hiss: 0 },       // 纯哨音
  hiss: { tone: 0, breath: 0, hiss: 1.4 },         // 嘶声
};
export const FW_ASCENT_DEFAULT = "even";

export const FW_LAUNCH = {                  // 管口闷响 + 点火噼啪（升空哨音另由实时节点合成）
  dur: 0.7,
  hp: 30,
  thump: { fc0: 260, fc1: 70, fcTau: 0.06, tau: 0.05, attack: 0.0015, level: 1.0,
           toneF: 72, toneTau: 0.045, toneLevel: 0.45 },
  spit: { hp: 800, rate0: 700, rateTau: 0.05, popTau: 0.004, tau: 0.07, level: 0.15 },
};

// 空间/播放常量
export const FW_SPACE = {
  speed: 343,        // 音速 m/s（声延迟）
  refDist: 80,       // 参考距离: 此处牡丹单发峰值 ≈ -11 dBFS（音量 100%）
  level: 0.35,       // 参考距离处的单发电平（已扣除 Chrome 限幅器自带的约 +2.6dB, 见 createFwVoice）
  gainMax: 2.0,      // 近距增益上限（贴着发射架时 +6dB 封顶）
  // 空气吸声低通截止 = airTop / (1 + d/airDiv)（80m ≈ 8kHz, 170m ≈ 5.1kHz, 220m ≈ 4.3kHz）
  airTop: 16000, airDiv: 80,
  brightFc: 2600,    // 「裂响亮度」高架滤波器的转折频率
  KIND_GAIN: { A: 1.0, B: 1.06, C: 0.80, crack: 0.26, launch: 0.90 },
  KIND_CRACKLE: { A: 0.13, B: 0.11, C: 0.10 },   // 碎裂层相对爆裂峰值的电平
};
const PEAK = 0.891;  // 音色库归一化峰值（-1 dBFS）
const TRI_RMS = 1 / Math.sqrt(3);   // 满幅三角波的有效值（哨音电平校准用）

// RBJ peaking EQ（固定系数）: 给尾音加一点胸腔共鸣
function peq(sr, f, q, db) {
  const A = Math.pow(10, db / 40);
  const w = TAU * f / sr;
  const al = Math.sin(w) / (2 * q);
  const cs = Math.cos(w);
  const a0 = 1 + al / A;
  return [(1 + al * A) / a0, (-2 * cs) / a0, (1 - al * A) / a0, (-2 * cs) / a0, (1 - al / A) / a0];
}

function normalizeMono(L, n) {
  let pk = 0;
  for (let k = 0; k < n; k++) if (Math.abs(L[k]) > pk) pk = Math.abs(L[k]);
  if (pk > 0 && Number.isFinite(pk)) {
    const g = PEAK / pk;
    for (let k = 0; k < n; k++) L[k] *= g;
  }
}
function normalize(L, R, n) {
  let pk = 0;
  for (let k = 0; k < n; k++) {
    const a = Math.abs(L[k]), c2 = Math.abs(R[k]);
    if (a > pk) pk = a;
    if (c2 > pk) pk = c2;
  }
  if (pk > 0 && Number.isFinite(pk)) {
    const g = PEAK / pk;
    for (let k = 0; k < n; k++) { L[k] *= g; R[k] *= g; }
  }
}

// ---------- 爆裂类音色生成器（可分块渲染: 游戏里空闲时切片生成, 不卡帧） ----------
function makeBurstGen(kind, seed, sr) {
  const r = rng32(seed);
  const jit = (v, k) => v * (1 + (r() * 2 - 1) * k);
  const P = FW_SOUND[kind] || FW_SOUND.A;
  const c = P.crack, b = P.body, s = P.sub, tl = P.tail;
  const n = Math.max(64, Math.round(P.dur * sr));
  const invSr = 1 / sr;
  const L = new Float32Array(n);
  const R = new Float32Array(n);

  const crDec = Math.exp(-1 / (jit(c.tau, 0.25) * sr));
  const crHp = 1 - Math.exp(-TAU * jit(c.hp, 0.15) / sr);
  const crLvl = jit(c.level, 0.08);           // 裂响电平抖动小一点: 发发都脆
  const snDec = Math.exp(-1 / (jit(c.snapTau, 0.2) * sr));
  const snW = TAU * jit(c.snapF, 0.15) * invSr;
  const snLvl = jit(c.snapLevel, 0.3);
  const ckDec = Math.exp(-1 / (jit(c.clickTau, 0.2) * sr));
  const ckW = TAU * jit(c.clickF, 0.12) * invSr;
  const ckLvl = jit(c.clickLevel, 0.3);

  const fc0 = jit(b.fc0, 0.15), fc1 = jit(b.fc1, 0.15), fcTau = jit(b.fcTau, 0.2);
  const bDec = Math.exp(-1 / (jit(b.tau, 0.2) * sr));
  const bAtk = 1 - Math.exp(-1 / (b.attack * sr));
  const popDec = Math.exp(-1 / (jit(b.popTau, 0.25) * sr));
  const rate0 = jit(b.rate0, 0.2), rateTau = b.rateTau;
  const kCl = 1 / (rate0 * b.popTau);          // 簇饱和系数: 起始时刻簇均值 ≈ 1
  const cmN = 1 / (1 - Math.exp(-1));
  const bLvl = b.level, bFloor = b.floor, drive = jit(b.drive, 0.15), comp = b.comp;

  const sDec = Math.exp(-1 / (jit(s.tau, 0.2) * sr));
  const sAtk = 1 - Math.exp(-1 / (s.attack * sr));
  const sLvl = jit(s.level, 0.10);            // 低频冲击同理, 不让某一发突然变闷

  const tDec = Math.exp(-1 / (jit(tl.tau, 0.2) * sr));
  const tAtk = 1 - Math.exp(-1 / (tl.attack * sr));
  const tfc0 = jit(tl.fc0, 0.15), tfc1 = jit(tl.fc1, 0.15), tfcTau = tl.fcTau;
  const tLvl = jit(tl.level, 0.15);
  const tComp = tl.comp ?? 0;
  const lfoC = 1 - Math.exp(-TAU * tl.lfoRate / sr);
  const lfo2C = 1 - Math.exp(-TAU * tl.lfo2Rate / sr);
  const lfoN = Math.sqrt(6 / lfoC);           // 平滑均匀噪声 → 单位方差
  const lfo2N = Math.sqrt(6 / lfo2C);
  const [pb0, pb1, pb2, pa1, pa2] = peq(sr, jit(tl.resF, 0.12), tl.resQ, tl.resDb);
  // 涌动(反射簇) = 一串越来越稀、越来越弱的回波: 约半数快起振(「闷回声」), 其余慢起振(「翻涌」)
  const swells = [];
  {
    const gapScale = P.dur / 3;
    let ts = 0.04 + 0.04 * r();
    for (let q = 0; q < Math.round(tl.swells); q++) {
      const fast = r() < 0.5;
      swells.push({
        t0: ts,
        ka: 1 - Math.exp(-1 / ((fast ? 0.002 + 0.008 * r() : 0.02 + 0.04 * r()) * sr)),
        kd: Math.exp(-1 / ((0.07 + 0.2 * r()) * (1 + ts) * sr)),
        amp: (fast ? 0.6 + 0.6 * r() : 0.35 + 0.65 * r()) * Math.exp(-ts / 0.6) * tl.swellMax,
        a: 0, d: 1,
      });
      ts += (0.06 + 0.05 * q) * (0.6 + 0.8 * r()) * gapScale;
      if (ts > P.dur * 0.85) break;
    }
  }

  const hpC = 1 - Math.exp(-TAU * P.hp / sr);
  const fadeN = Math.max(8, Math.round(0.03 * sr));
  const sJc = 1 - Math.exp(-TAU * 40 / sr);

  let i = 0;
  let crEnv = 1, crHpS = 0, crHpS2 = 0, snEnv = 1, snPh = 0, ckEnv = 1, ckPh = 0;
  let b1 = 0, b2 = 0, aB = 0, gB = 1, cl = 0, popNext = 0, rateNow = rate0, bEnv = 1, bAtkE = 0;
  let sPh = 0, sW = TAU * s.f0 * invSr, sEnv = 1, sAtkE = 0, sJ = 0;
  let lfo = 0, lfo2 = 0, swI = 0;
  const swOn = [];
  let tL1 = 0, tL2 = 0, tR1 = 0, tR2 = 0, aT = 1 - Math.exp(-TAU * tfc0 * invSr), aE = 0, gT = 1, tEnv = 1, tAtkE = 0;
  let px1L = 0, px2L = 0, py1L = 0, py2L = 0, px1R = 0, px2R = 0, py1R = 0, py2R = 0;
  let dcL = 0, dcR = 0;

  // 渲染 count 个样本到内部缓冲; 写满返回 true（并做峰值归一化）
  function run(count) {
    const end = Math.min(n, i + count);
    for (; i < end; i++) {
      const t = i * invSr;
      if ((i & 7) === 0) {   // 控制率(每 8 样本)更新慢变系数
        const fc = fc1 + (fc0 - fc1) * Math.exp(-t / fcTau);
        aB = 1 - Math.exp(-TAU * fc * invSr);
        gB = Math.pow(fc0 / fc, comp);
        sW = TAU * (s.f1 + (s.f0 - s.f1) * Math.exp(-t / s.glide)) * invSr;
        const ft = tfc1 + (tfc0 - tfc1) * Math.exp(-t / tfcTau);
        aT = 1 - Math.exp(-TAU * ft * invSr);
        gT = Math.pow(tfc0 / ft, tComp);
        rateNow = rate0 * Math.exp(-t / rateTau) + 30;
      }
      let dry = 0;
      // 裂响: 两阶高通的白噪 + 阻尼共振 + 毫秒级瞬态
      if (crEnv > 1e-4) {
        const w = r() * 2 - 1;
        crHpS += crHp * (w - crHpS);
        const hp1 = w - crHpS;
        crHpS2 += crHp * (hp1 - crHpS2);
        dry += (hp1 - crHpS2) * crEnv * crLvl;
        crEnv *= crDec;
      }
      if (snEnv > 1e-4) {
        dry += Math.sin(snPh) * snEnv * snLvl;
        snPh += snW;
        snEnv *= snDec;
      }
      if (ckEnv > 1e-4) {
        dry += Math.sin(ckPh) * ckEnv * ckLvl;
        ckPh += ckW;
        ckEnv *= ckDec;
      }
      // 轰鸣: 低通下扫 × 泊松微爆簇
      const wb = r() * 2 - 1;
      cl *= popDec;
      if (t >= popNext) {
        cl += 0.6 + 0.8 * r();
        popNext = t + -Math.log(1 - r()) / rateNow;
      }
      b1 += aB * (wb - b1);
      b2 += aB * (b1 - b2);
      bAtkE += (1 - bAtkE) * bAtk;
      const cm = (1 - Math.exp(-cl * kCl)) * cmN;
      const body = b2 * gB * bLvl * bAtkE * bEnv * (bFloor + (1 - bFloor) * (cm > 1.5 ? 1.5 : cm));
      bEnv *= bDec;
      // 低频冲击
      let sub = 0;
      if (sEnv > 1e-4) {
        sAtkE += (1 - sAtkE) * sAtk;
        sJ += sJc * ((r() * 2 - 1) - sJ);
        sub = Math.sin(sPh) * sEnv * sAtkE * sLvl * (1 + 4 * sJ);
        sPh += sW;
        sEnv *= sDec;
      }
      const sx = (body + sub) * drive;   // 软削波: 加谐波, 小喇叭上也有「冲击」
      dry += (sx / (1 + Math.abs(sx))) * 2;
      // 滚动尾音（淡入, 不糊住裂响）
      tEnv *= tDec;
      tAtkE += (1 - tAtkE) * tAtk;
      lfo += lfoC * ((r() * 2 - 1) - lfo);
      lfo2 += lfo2C * ((r() * 2 - 1) - lfo2);
      while (swI < swells.length && t >= swells[swI].t0) swOn.push(swells[swI++]);
      let sw = 0;
      for (let q = swOn.length - 1; q >= 0; q--) {
        const e = swOn[q];
        e.a += (1 - e.a) * e.ka;
        e.d *= e.kd;
        sw += e.amp * e.a * e.d;
        if (e.d < 2e-3) swOn.splice(q, 1);
      }
      let lm = (1 + tl.lfoDepth * lfo * lfoN) * (1 + tl.lfo2Depth * lfo2 * lfo2N);
      if (lm < 0.1) lm = 0.1;
      const amp = tEnv * tAtkE * tLvl * gT * (1 + sw) * lm;
      // 涌动来自绕远路的反射, 高频被吸收得更多 → 涌动时尾音更沉（截止频率随之下压）
      aE = aT * (1 - 0.65 * (sw > 1.2 ? 1.2 : sw));
      // 左右载波「部分」去相关: 相关度 ≈ 0.55 —— 尾音有宽度, 又不违背低频双耳相关的物理,
      // 单声道回放时尾音也不会相互抵消
      const nC = r() * 2 - 1;
      const inL = nC * 0.742 + (r() * 2 - 1) * 0.671;
      const inR = nC * 0.742 + (r() * 2 - 1) * 0.671;
      tL1 += aE * (inL - tL1);
      tL2 += aE * (tL1 - tL2);
      tR1 += aE * (inR - tR1);
      tR2 += aE * (tR1 - tR2);
      let oL = pb0 * tL2 + pb1 * px1L + pb2 * px2L - pa1 * py1L - pa2 * py2L;
      let oR = pb0 * tR2 + pb1 * px1R + pb2 * px2R - pa1 * py1R - pa2 * py2R;
      px2L = px1L; px1L = tL2; py2L = py1L; py1L = oL;
      px2R = px1R; px1R = tR2; py2R = py1R; py1R = oR;
      oL = dry + oL * amp;
      oR = dry + oR * amp;
      dcL += hpC * (oL - dcL);
      dcR += hpC * (oR - dcR);
      const fade = n - i < fadeN ? (n - i) / fadeN : 1;
      L[i] = (oL - dcL) * fade;
      R[i] = (oR - dcR) * fade;
    }
    if (i >= n) normalize(L, R, n);
    return i >= n;
  }
  return { kind, total: n, L, R, run };
}

// ---------- 碎裂层: 裂响之后 30-200ms 内一串稀疏的高频微爆（「少量噼里啪啦」） ----------
function makeCrackleGen(seed, sr) {
  const r = rng32(seed);
  const jit = (v, k) => v * (1 + (r() * 2 - 1) * k);
  const P = FW_CRACKLE;
  const n = Math.max(64, Math.round(P.dur * sr));
  const invSr = 1 / sr;
  const L = new Float32Array(n);
  const hpC = 1 - Math.exp(-TAU * jit(P.hp, 0.15) / sr);
  const popDec = Math.exp(-1 / (jit(P.popTau, 0.25) * sr));
  const rate0 = jit(P.rate0, 0.2);
  const fadeN = Math.max(8, Math.round(0.03 * sr));
  let i = 0, h1 = 0, h2 = 0, env = 0, next = jit(P.t0, 0.3), snEnv = 0, snPh = 0, snW = 0, snDec = 1;

  function run(count) {
    const end = Math.min(n, i + count);
    for (; i < end; i++) {
      const t = i * invSr;
      if (t >= next && t < P.dur * 0.9) {   // 新的一颗: 幅度随机且随时间变轻; 约三分之一带金属共鸣
        env = (0.3 + 0.7 * r()) * (0.35 + 0.65 * Math.exp(-t / 0.12));
        next = t + -Math.log(1 - r() * 0.9995) / (rate0 * Math.exp(-t / P.rateTau) + 25 * Math.exp(-t / P.floorTau));
        if (r() < 0.35) {
          snEnv = env * P.resLevel * (0.6 + 0.8 * r());
          snPh = r() * TAU;
          snW = TAU * jit(P.resF, 0.2) * invSr;
          snDec = Math.exp(-1 / (jit(P.resTau, 0.3) * sr));
        }
      }
      const w = r() * 2 - 1;
      h1 += hpC * (w - h1);
      const hp1 = w - h1;
      h2 += hpC * (hp1 - h2);
      env *= popDec;
      let s = (hp1 - h2) * env * 2.4;
      if (snEnv > 1e-4) {
        s += Math.sin(snPh) * snEnv;
        snPh += snW;
        snEnv *= snDec;
      }
      L[i] = s * (n - i < fadeN ? (n - i) / fadeN : 1);
    }
    if (i >= n) normalizeMono(L, n);
    return i >= n;
  }
  return { kind: "crackle", total: n, L, R: L, run };
}

// ---------- 管口闷响（升空哨音另由实时节点合成） ----------
function makeLaunchGen(seed, sr) {
  const r = rng32(seed);
  const jit = (v, k) => v * (1 + (r() * 2 - 1) * k);
  const P = FW_LAUNCH;
  const th = P.thump, sp = P.spit;
  const n = Math.max(64, Math.round(P.dur * sr));
  const invSr = 1 / sr;
  const L = new Float32Array(n);
  const R = new Float32Array(n);

  const tfc0 = jit(th.fc0, 0.15), tfc1 = jit(th.fc1, 0.15), tfcTau = th.fcTau;
  const thDec = Math.exp(-1 / (jit(th.tau, 0.25) * sr));
  const thAtk = 1 - Math.exp(-1 / (th.attack * sr));
  const toneDec = Math.exp(-1 / (jit(th.toneTau, 0.2) * sr));
  const toneW = TAU * jit(th.toneF, 0.15) * invSr;
  const spDec = Math.exp(-1 / (jit(sp.tau, 0.25) * sr));
  const spHp = 1 - Math.exp(-TAU * jit(sp.hp, 0.15) / sr);
  const popDec = Math.exp(-1 / (jit(sp.popTau, 0.25) * sr));
  const rate0 = jit(sp.rate0, 0.2);
  const kCl = 1 / (rate0 * sp.popTau);
  const cmN = 1 / (1 - Math.exp(-1));
  const hpC = 1 - Math.exp(-TAU * P.hp / sr);
  const fadeN = Math.max(8, Math.round(0.05 * sr));

  let i = 0;
  let t1 = 0, t2 = 0, aTh = 0, thEnv = 1, thAtkE = 0, tonePh = 0, toneEnv = 1;
  let spHpS = 0, spHpS2 = 0, cl = 0, popNext = 0, spEnv = 1;
  let dc = 0;

  function run(count) {
    const end = Math.min(n, i + count);
    for (; i < end; i++) {
      const t = i * invSr;
      if ((i & 7) === 0) {
        const fc = tfc1 + (tfc0 - tfc1) * Math.exp(-t / tfcTau);
        aTh = 1 - Math.exp(-TAU * fc * invSr);
      }
      let o = 0;
      // 管口闷响: 低通下扫的噪声 + 短促低频
      if (thEnv > 1e-4) {
        const w = r() * 2 - 1;
        t1 += aTh * (w - t1);
        t2 += aTh * (t1 - t2);
        thAtkE += (1 - thAtkE) * thAtk;
        o += t2 * 6 * th.level * thAtkE * thEnv;
        thEnv *= thDec;
        if (toneEnv > 1e-4) {
          o += Math.sin(tonePh) * toneEnv * th.toneLevel;
          tonePh += toneW;
          toneEnv *= toneDec;
        }
      }
      // 点火噼啪（两阶高通: 只留「嚓」的那一层, 不抢闷响）
      if (spEnv > 1e-4) {
        const ws = r() * 2 - 1;
        spHpS += spHp * (ws - spHpS);
        const hp1 = ws - spHpS;
        spHpS2 += spHp * (hp1 - spHpS2);
        cl *= popDec;
        if (t >= popNext) {
          cl += 0.6 + 0.8 * r();
          popNext = t + -Math.log(1 - r()) / (rate0 * Math.exp(-t / sp.rateTau) + 20);
        }
        o += (hp1 - spHpS2) * 3.2 * sp.level * spEnv * (1 - Math.exp(-cl * kCl)) * cmN;
        spEnv *= spDec;
      }
      const sx = o * 1.5;
      o = (sx / (1 + Math.abs(sx))) * 2;
      dc += hpC * (o - dc);
      const fade = n - i < fadeN ? (n - i) / fadeN : 1;
      L[i] = R[i] = (o - dc) * fade;
    }
    if (i >= n) normalize(L, R, n);
    return i >= n;
  }
  return { kind: "launch", total: n, L, R, run };
}

function makeGen(kind, seed, sr) {
  if (kind === "launch") return makeLaunchGen(seed, sr);
  if (kind === "crackle") return makeCrackleGen(seed, sr);
  return makeBurstGen(kind, seed, sr);
}

// 一次性整段合成（调参/取证用; 游戏内走 createFwBank 的分块渲染）
export function synthesize(kind, seed = 1, sr = 48000) {
  const g = makeGen(kind, seed, sr);
  g.run(Infinity);
  return { L: g.L, R: g.R, sr };
}

// ---------- 音色库: 入园后空闲时切片生成, 每型多个变体（配合播放时 ±8% 变速, 发发不同） ----------
// 总时长 ≈ 23s 音频, 生成约 200ms 主线程 (Chrome 实测 160-240ms), 按 ≤5ms 切片摊到入园后的空闲帧里
export const FW_VARIANTS = {
  launch: [11, 29], crackle: [71, 83, 97], crack: [131, 149], A: [101, 202], B: [404, 505], C: [606, 707],
};
const FIRST = ["launch", "A", "B", "C", "crack", "crackle"];   // 首轮每型先出一发（首秀最先用到）

function makePlan() {
  const plan = [];
  const maxV = Math.max(...Object.values(FW_VARIANTS).map((s) => s.length));
  for (let v = 0; v < maxV; v++) {
    for (const k of FIRST) if (FW_VARIANTS[k][v] !== undefined) plan.push([k, FW_VARIANTS[k][v]]);
  }
  return plan;
}
function renderToBuffer(ctx, kind, seed, sr) {
  const g = makeGen(kind, seed, sr);
  g.run(Infinity);
  const buf = ctx.createBuffer(2, g.total, sr);
  buf.copyToChannel(g.L, 0);
  buf.copyToChannel(g.R, 1);
  return buf;
}

export function createFwBank(ctx, sr = ctx.sampleRate) {
  const plan = makePlan();
  const ready = { launch: [], crackle: [], crack: [], A: [], B: [], C: [] };
  let idx = 0;
  let gen = null;
  let timer = 0;

  // 每次最多占 budgetMs 毫秒主线程
  function pump(budgetMs = 5) {
    const deadline = now() + budgetMs;
    while (now() < deadline) {
      if (!gen) {
        if (idx >= plan.length) return true;
        const [k, seed] = plan[idx];
        gen = makeGen(k, seed, sr);
      }
      if (gen.run(2048)) {
        const buf = ctx.createBuffer(2, gen.total, sr);
        buf.copyToChannel(gen.L, 0);
        buf.copyToChannel(gen.R, 1);
        ready[gen.kind].push(buf);
        gen = null;
        idx++;
      }
    }
    return idx >= plan.length;
  }
  // 空闲回调驱动（无 requestIdleCallback 时退化为宏任务切片）; 以回调给出的剩余时间为准, 不侵占帧预算
  function start() {
    if (timer) return;
    const ric = typeof requestIdleCallback === "function"
      ? (fn) => requestIdleCallback(fn, { timeout: 500 })
      : (fn) => setTimeout(() => fn({ timeRemaining: () => 4 }), 0);
    const tick = (dl) => {
      timer = 0;
      const left = typeof dl?.timeRemaining === "function" ? dl.timeRemaining() : 3;
      if (pump(Math.max(0.5, Math.min(5, left)))) return;
      timer = ric(tick);
    };
    timer = ric(tick);
  }
  function pick(kind, rng = Math.random) {
    const list = ready[kind];
    if (!list) return null;
    if (!list.length) {   // 极早期触发而首变体尚未生成: 同步补一发, 宁可卡 1-2ms 也不哑火
      const v = plan.find(([k]) => k === kind) ?? plan[0];
      list.push(renderToBuffer(ctx, v[0], (rng() * 4294967296) >>> 0, sr));
    }
    return list[(rng() * list.length) | 0];
  }
  return {
    pick, pump, start,
    // 同步生成完毕（离线渲染/取证用）
    sync() { while (!pump(1e9)) { /* 直到 plan 走完 */ } },
    get progress() { return plan.length ? idx / plan.length : 1; },
    get counts() { return Object.fromEntries(Object.entries(ready).map(([k, v]) => [k, v.length])); },
  };
}

// ---------- 播放引擎: 接任意 BaseAudioContext（实时 / 离线取证 / 试听页共用同一条路径） ----------
export function createFwVoice(ctx) {
  const S = FW_SPACE;
  const bus = ctx.createGain();                 // 音量总线
  bus.gain.value = 1;
  // 限幅: 终曲叠加。注意 Chrome 的 DynamicsCompressor 对门限以下信号也固定放大约 +2.6dB,
  // FW_SPACE.level 已按此校准（Firefox 无此增益时烟花仅略轻, 无碍）
  const limiter = ctx.createDynamicsCompressor();
  limiter.threshold.value = -6;
  limiter.knee.value = 4;
  limiter.ratio.value = 14;
  limiter.attack.value = 0.001;
  limiter.release.value = 0.25;
  // 末级软削波封顶: 压缩器 1ms 起控拦不住裂响的头一下, 终曲里多发瞬态叠加仍可能顶到 -1dBFS 以上;
  // -6dBFS 以下完全线性, 之上平滑压到 -1dBFS。逐样本生效, 不依赖各浏览器压缩器的实现差异
  const safety = ctx.createWaveShaper();
  {
    const N = 8192, K = 0.5, C = 0.891;
    const curve = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const x = (i / (N - 1)) * 2 - 1;
      const a = Math.abs(x);
      curve[i] = a <= K ? x : Math.sign(x) * (K + (C - K) * Math.tanh((a - K) / (C - K)));
    }
    safety.curve = curve;
    safety.oversample = "2x";
  }
  bus.connect(limiter);
  limiter.connect(safety);
  // 升空总线: 终曲里十几发哨音同时在场。不用压缩器限幅 —— Chrome 的 DynamicsCompressor 会按门限
  // 自动加补偿增益（低门限时高达十几 dB）且各浏览器不一; 改为按在场哨音数量回拉每发电平（见 rebalance）
  const ascentMix = ctx.createGain();
  ascentMix.connect(bus);
  const ascents = [];                           // 在场哨音 { bal, base, end }
  function rebalanceAscents() {
    const n = ascents.length;
    const k = n > FW_ASCENT.capGain ? Math.sqrt(FW_ASCENT.capGain / n) : 1;   // 总功率封顶在单发 +4dB
    for (const a of ascents) a.bal.gain.setTargetAtTime(a.base * k, ctx.currentTime, 0.08);
  }
  const bank = createFwBank(ctx);
  bank.start();                                 // 实时上下文: 空闲切片生成; 离线取证另调 bank.sync()

  let volume = 1;
  let delay = true;
  let active = 0;                               // 在播事件数（泄漏自查用）
  let brightness = 0;                           // 裂响亮度: 2.6kHz 以上高架增益（dB）
  let crackleOn = true;
  let ascentStyle = FW_ASCENT_DEFAULT;
  let ascentDb = 0;                             // 升空哨音相对 FW_ASCENT.level 的增减（dB）
  let noiseBuf = null;

  // 距离 + 方位处理链: 输入节点 → 四阶低通(近似空气吸声) → 等功率声像 → 输出节点
  function makeChain(d, pan, g) {
    const fc = Math.min(S.airTop, S.airTop / (1 + d / S.airDiv));
    const f1 = ctx.createBiquadFilter();
    const f2 = ctx.createBiquadFilter();
    f1.type = f2.type = "lowpass";
    f1.Q.value = 0.5412;
    f2.Q.value = 1.3066;
    f1.frequency.value = f2.frequency.value = fc;
    const th = (Math.max(-1, Math.min(1, pan || 0)) + 1) * (Math.PI / 4);
    const split = ctx.createChannelSplitter(2);
    const gl = ctx.createGain();
    const gr = ctx.createGain();
    const merge = ctx.createChannelMerger(2);
    gl.gain.value = Math.cos(th) * g;
    gr.gain.value = Math.sin(th) * g;
    f1.connect(f2);
    f2.connect(split);
    split.connect(gl, 0, 0);
    split.connect(gr, 1, 0);
    gl.connect(merge, 0, 0);
    gr.connect(merge, 0, 1);
    return { input: f1, output: merge, nodes: [f1, f2, split, gl, gr, merge] };
  }
  function dispose(nodes) {
    for (const nd of nodes) { try { nd.disconnect(); } catch { /* 已断开 */ } }
  }
  function noise() {
    if (!noiseBuf) {
      noiseBuf = ctx.createBuffer(1, Math.round(2 * ctx.sampleRate), ctx.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    const s = ctx.createBufferSource();
    s.buffer = noiseBuf;
    s.loop = true;
    return s;
  }
  // 哨音滑音曲线: 音高按「高度占比」上滑; 壳体减速上升 → 越近顶点滑得越慢
  function glide(f0, f1, T) {
    const k = FW_ASCENT.endRatio;
    const c = new Float32Array(64);
    for (let i = 0; i < 64; i++) {
      const x = i / 63;
      const p = (2 - k) * x - (1 - k) * x * x;
      c[i] = f0 * Math.pow(f1 / f0, p);
    }
    return c;
  }
  const eventGain = (d, kind) => Math.min(S.gainMax, S.refDist / d) * (S.KIND_GAIN[kind] ?? 1) * S.level
    * (0.85 + Math.random() * 0.3);

  // 播一个音色库事件（爆裂 / 火星分裂 / 管口闷响）: { dist, pan, at 画面事件时刻 }
  // 返回声音到达时刻（= at + dist/音速）; 音色库为空时返回 0
  function oneShot(kind, { dist = S.refDist, pan = 0, at = ctx.currentTime } = {}) {
    const d = Math.max(1, dist || S.refDist);
    const when = Math.max(ctx.currentTime, at) + (delay ? d / S.speed : 0);
    const buf = bank.pick(kind);
    if (!buf) return 0;
    const rate = 0.92 + Math.random() * 0.16;    // ±8% 变速: 同一变体也发发不同
    const ch = makeChain(d, pan, eventGain(d, kind));
    ch.output.connect(bus);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = rate;
    src.start(when);
    src.stop(when + buf.duration / rate + 0.1);
    const extra = [];
    // 裂响亮度高架（0dB 时透明）; 碎裂层也走它
    const shelf = ctx.createBiquadFilter();
    shelf.type = "highshelf";
    shelf.frequency.value = S.brightFc;
    shelf.gain.value = brightness;
    src.connect(shelf);
    shelf.connect(ch.input);
    extra.push(shelf);
    const cgain = S.KIND_CRACKLE[kind];
    if (crackleOn && cgain) {                    // 碎裂层: 与爆裂同刻、同变速起播
      const cb = bank.pick("crackle");
      if (cb) {
        const cs = ctx.createBufferSource();
        const cg = ctx.createGain();
        cs.buffer = cb;
        cs.playbackRate.value = rate;
        cg.gain.value = cgain;
        cs.connect(cg);
        cg.connect(shelf);
        cs.start(when);
        cs.stop(when + cb.duration / rate + 0.05);
        extra.push(cg);
      }
    }
    active++;
    src.onended = () => {
      active--;
      dispose(ch.nodes.concat(extra));
    };
    return when;
  }

  // 升空: 管口闷响 + 连续哨音。ascent = 升空秒数; endDist = 炸点到听者的距离（默认同 dist）
  // 哨音从发射声到达起, 按减速上升的轨迹上滑, 一直响到「炸点时刻 + 炸点声延迟」
  function launch({ dist = S.refDist, pan = 0, at = ctx.currentTime, ascent = 3.5, endDist } = {}) {
    const A = FW_ASCENT;
    const st = FW_ASCENT_STYLES[ascentStyle] || FW_ASCENT_STYLES[FW_ASCENT_DEFAULT];
    const d = Math.max(1, dist || S.refDist);
    const t0 = Math.max(ctx.currentTime, at);
    const start = t0 + (delay ? d / S.speed : 0);
    const end = Math.max(start + 0.3, t0 + Math.max(0.3, ascent || 3.5) + (delay ? Math.max(1, endDist || d) / S.speed : 0));
    const T = end - start;
    oneShot("launch", { dist: d, pan, at });     // 管口闷响走普通事件链
    if (!(st.tone > 0 || st.breath > 0 || st.hiss > 0)) return start;

    const ch = makeChain(d, pan, eventGain(d, "launch"));
    ch.output.connect(ascentMix);
    const f0 = A.f0 * (0.88 + Math.random() * 0.24);
    const f1 = A.f1 * (0.9 + Math.random() * 0.2);
    const W = A.level * Math.pow(10, ascentDb / 20);
    // 包络: 起音 → 到顶点前自然渐弱 → 炸点处收尾（只防咔哒）
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, start);
    env.gain.linearRampToValueAtTime(W, start + A.attack);
    env.gain.linearRampToValueAtTime(W * A.holdDrop, end - A.fade);
    env.gain.linearRampToValueAtTime(0, end);
    const mix = ctx.createGain();               // 各层混合
    const bal = ctx.createGain();               // 多发叠加时的回拉（与包络分开, 互不抢参数）
    bal.gain.value = 1;
    mix.connect(env);
    env.connect(bal);
    bal.connect(ch.input);
    const nodes = ch.nodes.concat([mix, env, bal]);
    const stopAt = end + 0.03;
    let last = null;
    const layer = (v) => { const n = ctx.createGain(); n.gain.value = v; n.connect(mix); nodes.push(n); return n; };
    if (st.tone > 0) {
      // 哨音: 三角波, 音高随高度上滑, 带轻微颤音
      const osc = ctx.createOscillator();
      osc.type = "triangle";
      osc.frequency.setValueCurveAtTime(glide(f0, f1, T), start, T);
      const vib = ctx.createOscillator();
      vib.frequency.value = A.vibRate * (0.8 + Math.random() * 0.4);
      const vibG = ctx.createGain();
      vibG.gain.value = f0 * A.vibDepth;
      vib.connect(vibG);
      vibG.connect(osc.frequency);
      osc.connect(layer(st.tone));
      osc.start(start);
      vib.start(start);
      osc.stop(stopAt);
      vib.stop(stopAt);
      nodes.push(vib, vibG);
      last = osc;
    }
    if (st.breath > 0 || st.hiss > 0) {
      // 噪声层: 窄带「气声」跟随哨音乐高; 宽带「嘶声」在较低频段同样上滑
      const nz = noise();
      if (st.breath > 0) {
        const nb = ctx.createBiquadFilter();
        nb.type = "bandpass";
        nb.Q.value = A.breathQ;
        nb.frequency.setValueCurveAtTime(glide(f0, f1, T), start, T);
        nz.connect(nb);
        nb.connect(layer(8 * st.breath));        // 窄带白噪幅度很小, 补偿到哨音的 -10dB 左右
        nodes.push(nb);
      }
      if (st.hiss > 0) {
        const hb = ctx.createBiquadFilter();
        hb.type = "bandpass";
        hb.Q.value = 1.0;
        hb.frequency.setValueCurveAtTime(glide(f0 * 0.55, f1 * 0.5, T), start, T);
        nz.connect(hb);
        hb.connect(layer(0.5 * st.hiss));        // 补偿到哨音的 -14dB 左右
        nodes.push(hb);
      }
      nz.start(start);
      nz.stop(stopAt);
      last = nz;
    }
    active++;
    ascents.push({ bal, base: 1, end });
    rebalanceAscents();
    last.onended = () => {
      active--;
      const q = ascents.findIndex((a) => a.bal === bal);
      if (q >= 0) ascents.splice(q, 1);
      rebalanceAscents();
      dispose(nodes);
    };
    return start;
  }

  return {
    output: safety,                             // 接 master
    bank,
    burst: (kind, o) => oneShot(FW_SOUND[kind] ? kind : "A", o),
    crack: (o) => oneShot("crack", o),
    launch,
    setVolume(v) {
      volume = Math.max(0, Math.min(4, v));
      bus.gain.setTargetAtTime(volume, ctx.currentTime, 0.03);
    },
    setDelay(on) { delay = !!on; },
    setBrightness(db) { brightness = Math.max(-12, Math.min(12, db)); },
    setCrackle(on) { crackleOn = !!on; },
    setAscentStyle(name) { if (FW_ASCENT_STYLES[name]) ascentStyle = name; },
    setAscentLevel(db) { ascentDb = Math.max(-12, Math.min(12, db)); },
    get active() { return active; },
    get volume() { return volume; },
    get delay() { return delay; },
    get brightness() { return brightness; },
    get crackle() { return crackleOn; },
    get ascentStyle() { return ascentStyle; },
    get ascentDb() { return ascentDb; },
  };
}
