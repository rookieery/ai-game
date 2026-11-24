// 烟花音频取证探针: 离线渲染「旧实现(快照)」与「新合成器 fw_sound.js」, 出 WAV + 客观指标 before/after 对比
// 声音无法截图, 验收分两层: 这里的客观指标 + 人耳试听 (prototype/fw_sound/index.html)
// 用法 (render 需先 npm run dev):
//   node scripts/probe_fw_audio.mjs            render + compare
//   node scripts/probe_fw_audio.mjs raw        仅合成器裸音色(无距离处理), Node 直跑, 调参用
//   node scripts/probe_fw_audio.mjs render     Chrome 离线渲染 before_* / after_* → shots/fw_audio
//   node scripts/probe_fw_audio.mjs compare    读 WAV 出 before/after 指标对比
import { chromium } from "playwright";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import * as show from "../prototype/fw_sound/show.js";

const SR = 48000;
const OUT = "shots/fw_audio";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const mode = process.argv[2] ?? "all";
mkdirSync(OUT, { recursive: true });

// ---------- WAV 读写 (16-bit PCM) ----------
function writeWav(path, channels, sr) {
  const n = channels[0].length, ch = channels.length;
  const data = Buffer.alloc(n * ch * 2);
  for (let i = 0; i < n; i++) {
    for (let c = 0; c < ch; c++) {
      data.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(channels[c][i] * 32767))), (i * ch + c) * 2);
    }
  }
  const hdr = Buffer.alloc(44);
  hdr.write("RIFF", 0); hdr.writeUInt32LE(36 + data.length, 4); hdr.write("WAVE", 8); hdr.write("fmt ", 12);
  hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20); hdr.writeUInt16LE(ch, 22);
  hdr.writeUInt32LE(sr, 24); hdr.writeUInt32LE(sr * ch * 2, 28); hdr.writeUInt16LE(ch * 2, 32); hdr.writeUInt16LE(16, 34);
  hdr.write("data", 36); hdr.writeUInt32LE(data.length, 40);
  writeFileSync(path, Buffer.concat([hdr, data]));
}
function readWav(path) {
  const b = readFileSync(path);
  const ch = b.readUInt16LE(22), sr = b.readUInt32LE(24);
  const start = 44, n = (b.length - start) / (2 * ch);
  const c = [];
  for (let k = 0; k < ch; k++) {
    const f = new Float32Array(n);
    for (let i = 0; i < n; i++) f[i] = b.readInt16LE(start + (i * ch + k) * 2) / 32768;
    c.push(f);
  }
  return { sr, ch, L: c[0], R: c[1] ?? c[0] };
}

// ---------- 分析 ----------
function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len, wr = Math.cos(ang), wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let j = 0; j < len / 2; j++) {
        const ur = re[i + j], ui = im[i + j], xr = re[i + j + len / 2], xi = im[i + j + len / 2];
        const vr = xr * cr - xi * ci, vi = xr * ci + xi * cr;
        re[i + j] = ur + vr; im[i + j] = ui + vi;
        re[i + j + len / 2] = ur - vr; im[i + j + len / 2] = ui - vi;
        const nc = cr * wi + ci * wr;
        cr = cr * wr - ci * wi; ci = nc;
      }
    }
  }
}
function aWeight(f) {   // A 计权功率比
  const f2 = f * f;
  const r = (12194 ** 2 * f2 * f2) / ((f2 + 20.6 ** 2) * Math.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194 ** 2));
  return 10 ** ((20 * Math.log10(r) + 2.0) / 10);
}
function cWeight(f) {   // C 计权功率比
  const f2 = f * f;
  const r = (12194 ** 2 * f2) / ((f2 + 20.6 ** 2) * (f2 + 12194 ** 2));
  return 10 ** ((20 * Math.log10(r) + 0.06) / 10);
}
// 「闷 / 脆」的客观尺子: C 与 A 计权电平之差。越小 = 中高频越足（脆）, 越大 = 越偏低频（闷）
// 真烟花实测参照（Kukulski 2018, 15-25m）: FAST 最大值之差 0.3-4.3dB, 全程暴露级之差 1.4-4.3dB
const BANDS6 = [[20, 150], [150, 500], [500, 2000], [2000, 6000], [6000, 12000], [12000, 24000]];
const HANN = {};
// 包络取样时刻（秒, 均为 0.1s 的整数倍 → 直接作 100ms 窗口下标）
const AWT = [0.1, 0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3];
const LINT = [0.1, 0.2, 0.5, 1, 2];
const hann = (n) => {
  if (!HANN[n]) { HANN[n] = new Float64Array(n); for (let i = 0; i < n; i++) HANN[n][i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / n); }
  return HANN[n];
};
// 区间平均功率谱 → 频带占比与重心（线性 / A 计权）
function spectrumStats(f, sr, t0, t1, n) {
  const P = new Float64Array(n / 2);
  const re = new Float64Array(n), im = new Float64Array(n), H = hann(n);
  const s0 = Math.max(0, Math.floor(t0 * sr)), s1 = Math.min(f.length, Math.floor(t1 * sr));
  let frames = 0;
  for (let s = s0; s + n <= s1; s += n / 4) {
    for (let i = 0; i < n; i++) { re[i] = f[s + i] * H[i]; im[i] = 0; }
    fft(re, im);
    frames++;
    for (let k = 0; k < n / 2; k++) P[k] += re[k] * re[k] + im[k] * im[k];
  }
  let tot = 0, hi = 0, totA = 0, sA = 0, hiA = 0, best = 0, low = 0;
  const bd = BANDS6.map(() => 0);
  for (let k = 1; k < n / 2; k++) {
    const fr = (k * sr) / n;
    tot += P[k];
    if (fr >= 2000 && fr < 20000) hi += P[k];
    const v = P[k] * aWeight(fr);
    totA += v; sA += fr * v;
    if (fr >= 2000 && fr < 20000) hiA += v;
    if (fr >= 20 && fr <= 200 && P[k] > best) { best = P[k]; low = fr; }
    for (let q = 0; q < BANDS6.length; q++) if (fr >= BANDS6[q][0] && fr < BANDS6[q][1]) bd[q] += P[k];
  }
  const d = (x, t) => (t ? (100 * x) / t : 0);
  // bands: [<150 | 150-500 | 500-2k | 2-6k | 6-12k | 12k+] 线性能量占比 %
  return { frames, hi: d(hi, tot), hiA: d(hiA, totA), cA: totA ? sA / totA : 0, low, bands: bd.map((x) => d(x, tot)) };
}
// 100ms 窗口包络: 线性 / A 计权 / C 计权功率。
// lin/aw 为相对各自最大窗的 dB（A 计权 ≈ 人耳响度, 低频轰不再淹没中频）; *Db 为绝对 dB（同尺度的任意基准）
function envelopes(f, sr, tOn, maxT) {
  const n = 1024, win = Math.round(0.1 * sr), H = hann(n);
  const re = new Float64Array(n), im = new Float64Array(n);
  const linDb = [], awDb = [], cwDb = [];
  const s0 = Math.max(0, Math.floor(tOn * sr));
  for (let s = s0; s + win <= f.length && (s - s0) / sr < maxT; s += win) {
    let e = 0, pa = 0, pc = 0, frames = 0;
    for (let q = s; q + n <= s + win; q += n / 2) {
      for (let k = 0; k < n; k++) { re[k] = f[q + k] * H[k]; im[k] = 0; }
      fft(re, im);
      frames++;
      for (let k = 1; k < n / 2; k++) {
        const p = (re[k] * re[k] + im[k] * im[k]), fr = (k * sr) / n;
        pa += p * aWeight(fr);
        pc += p * cWeight(fr);
      }
    }
    for (let k = s; k < s + win; k++) e += f[k] * f[k];
    linDb.push(10 * Math.log10(e / win + 1e-30));
    awDb.push(10 * Math.log10(pa / frames + 1e-30));
    cwDb.push(10 * Math.log10(pc / frames + 1e-30));
  }
  const mx = (a) => a.reduce((m, v) => Math.max(m, v), -1e9);
  const l0 = mx(linDb), a0 = mx(awDb);
  return { lin: linDb.map((v) => v - l0), aw: awDb.map((v) => v - a0), linDb, awDb, cwDb };
}
const sumPow = (a) => a.reduce((s, v) => s + 10 ** (v / 10), 0);
const meanPowDb = (a) => (a.length ? 10 * Math.log10(sumPow(a) / a.length) : NaN);
// FAST(125ms) 指数时间计权后的最大电平（输入为 100ms 窗口的 dB 序列）
const fastMax = (a) => {
  let e = 0, mx = -1e9;
  const k = 1 - Math.exp(-0.1 / 0.125);
  for (const v of a) { e += k * (10 ** (v / 10) - e); mx = Math.max(mx, 10 * Math.log10(e + 1e-30)); }
  return mx;
};
const fallTime = (arr, db) => {   // 包络越过峰值后首次跌破 -db 的时刻
  let pk = 0;
  for (let k = 1; k < arr.length; k++) if (arr[k] > arr[pk]) pk = k;
  for (let k = pk; k < arr.length; k++) if (arr[k] < -db) return k * 0.1;
  return null;
};
// 单发指标
function analyze({ sr, L, R }) {
  const f = new Float32Array(L.length);
  for (let i = 0; i < f.length; i++) f[i] = (L[i] + R[i]) * 0.5;
  let peak = 0;
  for (let i = 0; i < L.length; i++) { const a = Math.max(Math.abs(L[i]), Math.abs(R[i])); if (a > peak) peak = a; }
  // 起振点: 5ms 峰值包络首次超过全局峰值 -40dB
  const w5 = Math.round(sr * 0.005);
  let tOn = 0;
  for (let s = 0; s < f.length; s += w5) {
    let m = 0;
    for (let j = s; j < Math.min(f.length, s + w5); j++) m = Math.max(m, Math.abs(f[j]));
    if (m > peak * 0.01) { tOn = s / sr; break; }
  }
  const span = Math.min((f.length / sr) - tOn - 0.1, 4);
  const ev = envelopes(f, sr, tOn, span);
  const on = spectrumStats(f, sr, tOn, tOn + 0.05, 1024);
  const early = spectrumStats(f, sr, tOn + 0.05, tOn + 0.3, 2048);
  const late = spectrumStats(f, sr, tOn + 0.3, tOn + 1.0, 4096);
  let sl = 0, sd = 0;
  const a = Math.floor(tOn * sr), e = Math.min(f.length, a + 3 * sr);
  for (let i = a; i < e; i++) { const m = (L[i] + R[i]) * 0.5, d = (L[i] - R[i]) * 0.5; sl += m * m; sd += d * d; }
  return {
    peakDb: 20 * Math.log10(peak || 1e-9),
    tOn,
    lin: ev.lin, aw: ev.aw,
    linAt: LINT.map((dt) => ev.lin[dt * 10] ?? null),
    awAt: AWT.map((dt) => ev.aw[dt * 10] ?? null),
    tA30: fallTime(ev.aw, 30), tL40: fallTime(ev.lin, 40),
    hiOn: on.hi, hiOnA: on.hiA, cAOn: on.cA,
    lowEarly: early.low, lowLate: late.low, cALate: late.cA,
    width: sl ? Math.sqrt(sd / sl) : 0,
    dur: f.length / sr,
    // 闷/脆: C−A 计权差（起振 100ms 窗 / FAST 峰 / 全程）
    acOn: ev.cwDb[0] - ev.awDb[0],
    acFast: fastMax(ev.cwDb) - fastMax(ev.awDb),
    acAll: 10 * Math.log10(sumPow(ev.cwDb) / sumPow(ev.awDb)),
    // 起振头 30ms 的频带构成
    onBands: spectrumStats(f, sr, tOn, tOn + 0.03, 1024).bands,
  };
}
// 精确 A 计权: 整段信号 FFT × 理想 A 计权曲线 × IFFT（零相位, 无短窗泄漏）。
// 短窗 STFT 算 A 计权功率会把爆裂的强低频泄进邻近 bin、高估其 A 计权电平, 哨音/爆裂响度对比必须用这个
function aweightFFT(x, sr) {
  const n = 1 << Math.ceil(Math.log2(x.length * 2));
  const re = new Float64Array(n), im = new Float64Array(n);
  for (let i = 0; i < x.length; i++) re[i] = x[i];
  fft(re, im);
  for (let k = 0; k < n; k++) {
    const a = Math.sqrt(aWeight((k < n / 2 ? k : n - k) * sr / n));
    re[k] *= a;
    im[k] *= a;
  }
  for (let k = 0; k < n; k++) im[k] = -im[k];
  fft(re, im);
  const y = new Float64Array(x.length);
  for (let i = 0; i < x.length; i++) y[i] = re[i] / n;
  return y;
}
const rmsDbAt = (x, sr, t0, t1) => {
  let s = 0, c = 0;
  for (let i = Math.round(t0 * sr); i < Math.round(t1 * sr); i++) { s += x[i] * x[i]; c++; }
  return 10 * Math.log10(s / c + 1e-30);
};
// 升空段指标: 哨音（升空声到达 + 0.6s … 炸点声到达 − 0.3s）相对爆裂起振（炸点声到达起 100ms）的电平, 以及哨音的音高
function ascentMetrics(path, tLaunch, tBurst, dist) {
  const w = readWav(path);
  const f = new Float32Array(w.L.length);
  for (let i = 0; i < f.length; i++) f[i] = (w.L[i] + w.R[i]) * 0.5;
  const tL = tLaunch + dist / 343, tB = tBurst + dist / 343;
  const ax = aweightFFT(f, w.sr);
  const ev = envelopes(f, w.sr, 0, w.L.length / w.sr);
  const idx = (a, b) => ev.awDb.map((_, k) => k).filter((k) => k * 0.1 >= a - 1e-9 && k * 0.1 + 0.1 <= b + 1e-9);
  const wh = idx(tL + 0.6, tB - 0.3);          // 哨音段: 起音后 0.6s 到炸点声到达前 0.3s（整窗）
  const pre = idx(tB - 0.3, tB);
  // 哨音重心与最强谱线（取升空中段 1.5s 处）
  const s = Math.round((tL + 1.5) * w.sr), n = 8192, re = new Float64Array(n), im = new Float64Array(n), H = hann(n);
  for (let i = 0; i < n; i++) { re[i] = f[s + i] * H[i]; im[i] = 0; }
  fft(re, im);
  let pkF = 0, best = 0, tot = 0, sA = 0;
  for (let k = 1; k < n / 2; k++) {
    const p = re[k] * re[k] + im[k] * im[k], fr = (k * w.sr) / n;
    if (p > best) { best = p; pkF = fr; }
    tot += p * aWeight(fr); sA += fr * p * aWeight(fr);
  }
  return {
    relA: rmsDbAt(ax, w.sr, tL + 0.6, tB - 0.3) - rmsDbAt(ax, w.sr, tB, tB + 0.1),   // 精确 A 计权; 电平按「哨音为主」型校准在 -12dB, 默认「各半」型实测约 -10dB
    relL: rmsDbAt(f, w.sr, tL + 0.6, tB - 0.3) - rmsDbAt(f, w.sr, tB, tB + 0.1),
    preDb: meanPowDb(pre.map((k) => ev.awDb[k])) - meanPowDb(wh.map((k) => ev.awDb[k])),   // 炸点前 0.3s 相对哨音均值（应仍在线）
    peakF: pkF, cen: sA / tot,
  };
}
const db1 = (v) => (v === null || !Number.isFinite(v) ? "   - " : (v >= 0 ? "+" : "") + v.toFixed(1));
const f0 = (v) => (Number.isFinite(v) ? v.toFixed(0) : "-");

// ---------- 指标对比表 ----------
function compare() {
  for (const name of ["A", "B", "C"]) {
    const rows = [];
    for (const tag of ["before", "after"]) {
      try { rows.push([tag, analyze(readWav(`${OUT}/${tag}_${name}.wav`))]); } catch { /* 缺文件跳过 */ }
    }
    if (!rows.length) { console.log(`[${name}] 无 WAV`); continue; }
    console.log(`\n===== ${name} =====`);
    const line = (label, get) => console.log(label.padEnd(30) + rows.map(([, r]) => String(get(r)).padStart(12)).join(""));
    console.log("".padEnd(30) + rows.map(([t]) => t.padStart(12)).join(""));
    line("峰值 dBFS", (r) => db1(r.peakDb));
    AWT.forEach((dt, k) => line(`A计权包络 ${dt}s`, (r) => db1(r.awAt[k])));
    line("A计权降 -30dB 用时 s", (r) => (r.tA30 === null ? ">4" : r.tA30.toFixed(1)));
    LINT.forEach((dt, k) => line(`线性包络 ${dt}s`, (r) => db1(r.linAt[k])));
    line("线性降 -40dB 用时 s", (r) => (r.tL40 === null ? ">4" : r.tL40.toFixed(1)));
    line("起振 2kHz+ 线性占比 %", (r) => r.hiOn.toFixed(1));
    line("起振 2kHz+ A计权占比 %", (r) => r.hiOnA.toFixed(1));
    // 真烟花实测（Kukulski 2018, 15-25m）: FAST 峰之差 0.3-4.3dB / 全程之差 1.4-4.3dB
    line("C−A 计权差 起振100ms dB", (r) => r.acOn.toFixed(1));
    line("C−A 计权差 FAST峰 dB", (r) => r.acFast.toFixed(1));
    line("C−A 计权差 全程 dB", (r) => r.acAll.toFixed(1));
    line("起振30ms <150Hz 占比 %", (r) => r.onBands[0].toFixed(1));
    line("起振30ms 2-6kHz 占比 %", (r) => r.onBands[3].toFixed(1));
    line("起振30ms >6kHz 占比 %", (r) => (r.onBands[4] + r.onBands[5]).toFixed(1));
    line("低频最强谱线 早/晚 Hz", (r) => `${f0(r.lowEarly)}/${f0(r.lowLate)}`);
    line("立体声宽度 (0=单声道)", (r) => r.width.toFixed(2));
  }
  // 升空段: 80m 处发射 → 3.5s 升空哨音 → 炸点
  try {
    const a = ascentMetrics(`${OUT}/after_ascent.wav`, 0.3, 0.3 + ASC, 80);
    console.log(`\n===== 升空段 (80m, 发射→炸点 ${ASC.toFixed(2)}s) =====`);
    console.log(`升空声相对爆裂起振: A计权 ${db1(a.relA)} dB (默认「哨音+嘶声各半」约 -10dB; 单发随机性 ±2dB) / 线性 ${db1(a.relL)} dB`);
    console.log(`炸点前 0.3s 相对哨音均值: ${db1(a.preDb)} dB (应为 -3 左右: 一直响到炸点)`);
    console.log(`升空中段哨音: 最强谱线 ${a.peakF.toFixed(0)} Hz, 重心 ${a.cen.toFixed(0)} Hz`);
  } catch { console.log("\n(无 after_ascent.wav)"); }
  for (const name of ["finale", "show", "near_far", "ascent"]) {
    const rows = [];
    for (const tag of ["before", "after"]) {
      try {
        const w = readWav(`${OUT}/${tag}_${name}.wav`);
        let pk = 0, clip = 0, s = 0;
        for (let i = 0; i < w.L.length; i++) {
          const a = Math.max(Math.abs(w.L[i]), Math.abs(w.R[i]));
          if (a > pk) pk = a;
          if (a >= 0.999) clip++;
          s += w.L[i] * w.L[i] + w.R[i] * w.R[i];
        }
        rows.push([tag, { pk: 20 * Math.log10(pk || 1e-9), clip, rmsDb: 10 * Math.log10((s / (2 * w.L.length)) || 1e-18), dur: w.L.length / w.sr }]);
      } catch { /* 缺文件跳过 */ }
    }
    if (!rows.length) continue;
    console.log(`\n===== ${name} =====`);
    console.log("".padEnd(20) + rows.map(([t]) => t.padStart(12)).join(""));
    console.log("峰值 dBFS".padEnd(20) + rows.map(([, r]) => db1(r.pk).padStart(12)).join(""));
    console.log("全程 RMS dBFS".padEnd(20) + rows.map(([, r]) => db1(r.rmsDb).padStart(12)).join(""));
    console.log("削波样本数".padEnd(20) + rows.map(([, r]) => String(r.clip).padStart(12)).join(""));
    console.log("时长 s".padEnd(20) + rows.map(([, r]) => r.dur.toFixed(1).padStart(12)).join(""));
  }
}

// ---------- 事件表 (before/after 共用同一份) ----------
const legacyVol = (d) => Math.max(0.12, Math.min(1, 1 - d / 300));
const ASC = show.ascentSeconds();   // 升空秒数（默认炸点高度 55m）
function buildSets() {
  const mk = (name, events, seconds, both = true) => ({ name, seconds, both, events: events.map((e) => ({ ...e, vol: legacyVol(e.dist) })) });
  const single = (kind) => {
    const rng = show.mulberry32(kind.charCodeAt(0) * 977);
    return show.singleEvents(kind, { dist: 80, pan: 0, t: 0.2, rng });
  };
  const finale = show.finaleEvents(20261123, { t0: 0.5, withLaunch: false });
  const full = show.showEvents(7);
  const nf = show.nearFarEvents();
  // 升空段: 80m 处发射 → 连续哨音 → 炸点（探指标用）
  const asc = [
    { t: 0.3, type: "launch", kind: "A", dist: 80, pan: 0, ascent: ASC, endDist: 80 },
    { t: 0.3 + ASC, type: "burst", kind: "A", dist: 80, pan: 0 },
  ];
  return [
    mk("A", single("A"), 5.5), mk("B", single("B"), 5.5), mk("C", single("C"), 5.5),
    mk("finale", finale, show.lastTime(finale) + 5),
    mk("show", full, show.lastTime(full) + 5, false),
    mk("near_far", nf, 20, false),
    mk("ascent", asc, 0.3 + ASC + 5.5, false),
  ];
}

// ---------- Chrome 离线渲染 (after 走游戏同一条 WebAudio 路径; before 走 legacy 快照) ----------
async function render() {
  const sets = buildSets().map((s) => ({ ...s, events: s.events.map(({ type, kind, t, dist, pan, vol, ascent, endDist }) => ({ type, kind, t, dist, pan, vol, ascent, endDist })) }));
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.log("PAGEERROR:", String(e)));
  page.on("console", (m) => { if (m.type() === "error") console.log("CONSOLE:", m.text()); });
  // 同源空白页: 只为让 Vite 能按模块路径提供 fw_sound.js / legacy.js
  await page.route("**/__fw_blank.html", (route) => route.fulfill({ contentType: "text/html", body: "<!doctype html><title>fw audio probe</title>" }));
  await page.goto(`${BASE_URL}/__fw_blank.html`, { waitUntil: "domcontentloaded" });
  const res = await page.evaluate(async ({ SR, sets }) => {
    const fw = await import("/src/core/fw_sound.js");
    const { createLegacy } = await import("/prototype/fw_sound/legacy.js");
    const toWav = (buf) => {
      const L = buf.getChannelData(0), R = buf.getChannelData(1);
      const i16 = new Int16Array(L.length * 2);
      let clip = 0;
      for (let i = 0; i < L.length; i++) {
        const l = Math.max(-32768, Math.min(32767, Math.round(L[i] * 32767)));
        const r = Math.max(-32768, Math.min(32767, Math.round(R[i] * 32767)));
        if (Math.abs(L[i]) >= 0.999 || Math.abs(R[i]) >= 0.999) clip++;
        i16[i * 2] = l; i16[i * 2 + 1] = r;
      }
      const u8 = new Uint8Array(i16.buffer);
      let bin = "";
      for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
      return { wav: btoa(bin), clip };
    };
    const out = {};
    for (const s of sets) {
      if (s.both) {
        const off = new OfflineAudioContext(2, Math.ceil(SR * s.seconds), SR);
        const lg = createLegacy(off, off.destination);
        const byT = new Map();
        for (const e of s.events) {
          if (e.type !== "burst") continue;
          if (!byT.has(e.t)) byT.set(e.t, []);
          byT.get(e.t).push(e);
        }
        for (const t of [...byT.keys()].sort((a, b) => a - b)) {
          off.suspend(t).then(() => { for (const e of byT.get(t)) lg.burst(e.vol, e.kind); off.resume(); });
        }
        out[`before_${s.name}`] = toWav(await off.startRendering());
      }
      const off = new OfflineAudioContext(2, Math.ceil(SR * s.seconds), SR);
      const t0 = performance.now();
      const voice = fw.createFwVoice(off);
      voice.bank.sync();                       // 离线渲染不等空闲回调, 同步生成音色库
      const genMs = performance.now() - t0;
      voice.output.connect(off.destination);
      const cost = [];
      for (const e of s.events) {
        const o = { dist: e.dist, pan: e.pan, at: e.t, ascent: e.ascent, endDist: e.endDist };
        const c0 = performance.now();
        if (e.type === "burst") voice.burst(e.kind, o);
        else if (e.type === "crack") voice.crack(o);
        else voice.launch(o);
        cost.push(performance.now() - c0);
      }
      const r = toWav(await off.startRendering());
      out[`after_${s.name}`] = { ...r, genMs, costAvg: cost.reduce((a, b) => a + b, 0) / cost.length, costMax: Math.max(...cost) };
    }
    return out;
  }, { SR, sets });
  await browser.close();
  for (const [name, r] of Object.entries(res)) {
    const data = Buffer.from(r.wav, "base64");
    const n = data.length / 4;
    const L = new Float32Array(n), R = new Float32Array(n);
    for (let i = 0; i < n; i++) { L[i] = data.readInt16LE(i * 4) / 32768; R[i] = data.readInt16LE(i * 4 + 2) / 32768; }
    writeWav(`${OUT}/${name}.wav`, [L, R], SR);
    const extra = r.genMs !== undefined ? `  音色库生成 ${r.genMs.toFixed(1)}ms  单次触发 avg ${r.costAvg.toFixed(3)}ms / max ${r.costMax.toFixed(3)}ms` : "";
    console.log(`[${name}] ${(n / SR).toFixed(1)}s  写出 ${OUT}/${name}.wav${extra}`);
  }
}

// ---------- 裸音色 (Node 直跑, 调参用; 各型全部变体求平均) ----------
async function raw() {
  const { synthesize, FW_VARIANTS } = await import("../src/core/fw_sound.js");
  for (const [kind, seeds] of Object.entries(FW_VARIANTS)) {
    const t0 = performance.now();
    const bufs = seeds.map((seed) => synthesize(kind, seed, SR));
    const ms = (performance.now() - t0) / seeds.length;
    let bad = 0, pk = 0;
    for (const { L, R } of bufs) for (let i = 0; i < L.length; i++) {
      if (!Number.isFinite(L[i]) || !Number.isFinite(R[i])) bad++;
      pk = Math.max(pk, Math.abs(L[i]), Math.abs(R[i]));
    }
    writeWav(`${OUT}/raw_${kind}.wav`, [bufs[0].L, bufs[0].R], SR);
    const as = bufs.map((b) => analyze({ sr: SR, ...b }));
    const avg = (get) => as.map((r) => get(r)).reduce((a, v) => a + v, 0) / as.length;
    const series = (get) => as[0][get].map((_, k) => avg((r) => r[get][k]).toFixed(0));
    console.log(`[${kind}] ${(bufs[0].L.length / SR).toFixed(1)}s  合成 ${ms.toFixed(1)}ms/发  NaN=${bad}  峰值 ${db1(20 * Math.log10(pk))} dBFS`);
    console.log(`   A计权包络(0.1s 步, 0-3s): ${series("aw").join(" ")}`);
    console.log(`   线性包络(0.1s 步, 0-2s): ${series("lin").slice(0, 20).join(" ")}`);
    const secs = (v) => (v === null ? ">4" : v.toFixed(1));
    console.log(`   A计权 -30dB @ ${as.map((r) => secs(r.tA30)).join("/")}s  线性 -40dB @ ${as.map((r) => secs(r.tL40)).join("/")}s  起振 2kHz+ 线性 ${avg((r) => r.hiOn).toFixed(1)}% / A计权 ${avg((r) => r.hiOnA).toFixed(1)}%  起振重心 ${f0(avg((r) => r.cAOn))}Hz  低频谱线 ${f0(avg((r) => r.lowEarly))}→${f0(avg((r) => r.lowLate))}Hz  宽度 ${avg((r) => r.width).toFixed(2)}`);
    console.log(`   C−A 计权差 起振100ms ${avg((r) => r.acOn).toFixed(1)} / FAST峰 ${avg((r) => r.acFast).toFixed(1)} / 全程 ${avg((r) => r.acAll).toFixed(1)} dB (真烟花 0.3-4.3 / 1.4-4.3)  起振30ms 占比 [<150|150-500|500-2k|2-6k|6-12k|12k+] ${[0, 1, 2, 3, 4, 5].map((q) => avg((r) => r.onBands[q]).toFixed(1)).join("|")}`);
  }
}

if (mode === "raw") {
  await raw();
} else {
  if (mode === "all" || mode === "render") await render();
  if (mode === "all" || mode === "compare") compare();
}
console.log("PROBE_DONE");
