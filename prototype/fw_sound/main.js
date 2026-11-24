// 烟花音效试听页（独立原型, 不接入游戏）
// 用途: 烟花音色的调参试听台 —— 新合成器 vs 接入前旧版 A/B、距离 / 方位 / 真实声延迟、升空哨音、清脆度
// 播放路径与游戏一致: createFwVoice(ctx) → 输出; 旧版走 legacy.js 快照（接入前 audio.js 的那张图）
import { createFwVoice, FW_SPACE } from "../../src/core/fw_sound.js";
import { createLegacy, legacyVol } from "./legacy.js";
import * as show from "./show.js";

const KIND_COLOR = { A: "#FFA53B", B: "#FFE9C4", C: "#8CFF4A", launch: "#B48CFF" };
const el = {};
for (const id of ["stage", "info", "bank", "i-dist", "i-pan", "i-vol", "i-delay", "i-launch", "i-legacy",
  "i-ascent", "i-ascvol", "o-ascvol", "i-crackle", "i-bright", "o-dist", "o-pan", "o-vol"]) {
  el[id] = document.getElementById(id);
}

const st = {
  dist: 80, pan: 0, volume: 1, delay: true, launch: true, legacy: false,
  ascent: "even", ascDb: 0, crackle: true, bright: 0,   // 默认与游戏一致: 哨音 + 嘶声各半、各项 100%
};
let ctx = null;
let voice = null;
let analyser = null;
let legacy = null;
let meter = null;
const marks = [];    // 已排期事件 { tVis 画面时刻, arrive 声音到达, arriveEnd 持续声结束, type, kind, pan }
const levels = [];   // 实时电平 { t, v }

function ensureAudio() {
  if (ctx) {
    ctx.resume();
    return;
  }
  ctx = new AudioContext();
  voice = createFwVoice(ctx);
  analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  meter = new Float32Array(analyser.fftSize);
  voice.output.connect(analyser);
  analyser.connect(ctx.destination);
  voice.setVolume(st.volume);
  voice.setDelay(st.delay);
  voice.setAscentStyle(st.ascent);
  voice.setAscentLevel(st.ascDb);   // 相对基准的增减 dB, 同游戏设置「升空哨音响量」的 ±6dB
  voice.setCrackle(st.crackle);
  voice.setBrightness(st.bright);
  // 旧版: 与游戏一致直连输出级（只有总静音, 无音量/距离模型）, 这里只是借道 analyser 好画电平
  legacy = createLegacy(ctx, analyser);
}

const signed = (v) => (v >= 0 ? "+" : "") + v.toFixed(1);
function describe(e) {
  const d = e.dist;
  if (st.legacy) {
    return "旧版 · " + (e.type === "launch"
      ? "升空只有一声约 1 秒的扫频啸音，不随升空时间持续"
      : `距离 ${d.toFixed(0)} m → 音量系数 ${legacyVol(d).toFixed(2)}（只调音量: 无声延迟 / 无声像 / 音色不随距离变）`);
  }
  if (e.type === "launch") {
    return `新版 · 升空 ${e.ascent.toFixed(1)} 秒: 哨音 + 嘶声约 0.9 → 2.7 kHz 随高度上滑，一直响到炸点；响度 = 基准${st.ascDb ? ` ${st.ascDb > 0 ? "+" : ""}${st.ascDb} dB` : ""}；管口闷响 ${signed(20 * Math.log10(Math.min(FW_SPACE.gainMax, FW_SPACE.refDist / d)))} dB（相对 80 m）`;
  }
  const delay = st.delay ? d / FW_SPACE.speed : 0;
  const gainDb = 20 * Math.log10(Math.min(FW_SPACE.gainMax, FW_SPACE.refDist / d));
  const lp = FW_SPACE.airTop / (1 + d / FW_SPACE.airDiv);
  return `新版 · 爆裂 距离 ${d.toFixed(0)} m → 闪光后 ${delay.toFixed(2)} s 到达 · 增益 ${signed(gainDb)} dB（相对 80 m）· 空气吸声低通 ${(lp / 1000).toFixed(1)} kHz · 方位 ${e.pan.toFixed(2)}`;
}

// 把一组声学事件排上去; e.t 为相对时刻（秒）, 0 = 现在
function fire(events) {
  ensureAudio();
  const base = ctx.currentTime + 0.3;
  let firstBurst = null;
  let firstLaunch = null;
  for (const e of events) {
    const tVis = base + e.t;
    let arrive = tVis;
    let arriveEnd = tVis;
    if (st.legacy) {
      if (e.type !== "crack") {   // 旧版没有火星分裂音
        setTimeout(() => {
          if (e.type === "burst") legacy.burst(legacyVol(e.dist), e.kind);
          else legacy.launch();
        }, Math.max(0, (tVis - ctx.currentTime) * 1000));
        if (e.type === "launch") arriveEnd = tVis + 1.2;
      }
    } else {
      const o = { dist: e.dist, pan: e.pan, at: tVis };
      if (e.type === "burst") arrive = voice.burst(e.kind, o) || tVis;
      else if (e.type === "crack") arrive = voice.crack(o) || tVis;
      else {
        const asc = e.ascent ?? 3.5;
        arrive = voice.launch({ ...o, ascent: asc, endDist: e.endDist }) || tVis;
        arriveEnd = tVis + asc + (st.delay ? (e.endDist ?? e.dist) / FW_SPACE.speed : 0);   // 哨音响到「炸点 + 炸点声延迟」
      }
    }
    marks.push({ tVis, arrive, arriveEnd, type: e.type, kind: e.kind, pan: e.pan, dist: e.dist, muted: st.legacy && e.type === "crack" });
    if (e.type === "burst" && !firstBurst) firstBurst = e;
    if (e.type === "launch" && !firstLaunch) firstLaunch = e;
  }
  if (firstLaunch) el.info.textContent = describe(firstLaunch) + (firstBurst ? ` ｜ ${firstBurst.dist.toFixed(0)} m 处炸点` : "");
  else if (firstBurst) el.info.textContent = describe(firstBurst);
}

function single(kind) {
  const lead = st.launch ? show.ascentSeconds() : 0;
  fire(show.singleEvents(kind, { dist: st.dist, pan: st.pan / 100, t: lead, withLaunch: st.launch }));
}

const ACT = {
  A: () => single("A"),
  B: () => single("B"),
  C: () => single("C"),
  regular: () => fire(show.regularEvents(7, { t0: 0, withLaunch: true })),
  finale: () => fire(show.finaleEvents(20261123, { t0: 0, withLaunch: true })),
  nearfar: () => fire(show.nearFarEvents()),
};
for (const b of document.querySelectorAll("button[data-act]")) {
  b.addEventListener("click", () => ACT[b.dataset.act]());
}
addEventListener("keydown", (e) => {
  // 滑杆聚焦时只把方向/翻页键让给它（调值）, 数字字母键仍是快捷键; 下拉框聚焦时不抢
  const t = e.target;
  const sliderKey = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(e.code);
  if (e.repeat || t.tagName === "SELECT" || (t.tagName === "INPUT" && t.type !== "checkbox" && sliderKey)) return;
  const map = { Digit1: "A", Digit2: "B", Digit3: "C", KeyR: "regular", KeyF: "finale", KeyN: "nearfar" };
  if (map[e.code]) ACT[map[e.code]]();
});

// ---------- 控件 ----------
const panName = (p) => (Math.abs(p) < 5 ? "中" : p < 0 ? `左 ${-p}` : `右 ${p}`);
el["i-dist"].addEventListener("input", (e) => {
  st.dist = +e.target.value;
  el["o-dist"].textContent = `${st.dist} m`;
});
el["i-pan"].addEventListener("input", (e) => {
  st.pan = +e.target.value;
  el["o-pan"].textContent = panName(st.pan);
});
el["i-vol"].addEventListener("input", (e) => {
  st.volume = +e.target.value / 100;
  el["o-vol"].textContent = `${e.target.value}%${st.legacy ? "（旧版不适用）" : ""}`;
  if (voice) voice.setVolume(st.volume);
});
el["i-delay"].addEventListener("change", (e) => {
  st.delay = e.target.checked;
  if (voice) voice.setDelay(st.delay);
});
el["i-launch"].addEventListener("change", (e) => { st.launch = e.target.checked; });
el["i-legacy"].addEventListener("change", (e) => {
  st.legacy = e.target.checked;
  el["o-vol"].textContent = `${Math.round(st.volume * 100)}%${st.legacy ? "（旧版不适用）" : ""}`;
  el.info.textContent = st.legacy
    ? "旧版：接入前的线上音效（audio.js 快照）。再点一次同一按钮即可 A/B；虚线框里的调整项对旧版不生效。"
    : "新版：游戏现用的合成器。再点一次同一按钮即可 A/B。";
});
// 本轮调整项
el["i-ascent"].addEventListener("change", (e) => {
  st.ascent = e.target.value;
  if (voice) voice.setAscentStyle(st.ascent);
});
el["i-ascvol"].addEventListener("input", (e) => {
  st.ascDb = +e.target.value;
  el["o-ascvol"].textContent = st.ascDb ? `基准 ${st.ascDb > 0 ? "+" : ""}${st.ascDb} dB` : "基准";
  if (voice) voice.setAscentLevel(st.ascDb);
});
el["i-crackle"].addEventListener("change", (e) => {
  st.crackle = e.target.checked;
  if (voice) voice.setCrackle(st.crackle);
});
el["i-bright"].addEventListener("change", (e) => {
  st.bright = +e.target.value;
  if (voice) voice.setBrightness(st.bright);
});

// ---------- 时间线绘制 ----------
// 上半「天空」: 横轴 = 方位; 紫线 = 上升弹道（减速上升）, 闪光在炸点方位亮起, 声音到达时描一圈边
// 下半「时间线」: 横轴 = 时间; 三角 = 看见的时刻, 圆点 = 听到的时刻, 青色横条 = 持续中的声音, 亮柱 = 实时电平
const g = el.stage.getContext("2d");
const WINDOW = 4;
const stars = Array.from({ length: 70 }, () => [Math.random(), Math.random() * 0.38, Math.random()]);
const END_RATIO = 0.09;   // 壳体末速/初速: 弹道高度占比 = (2−k)p − (1−k)p²

function draw() {
  const dpr = Math.min(2, devicePixelRatio || 1);
  const W = el.stage.clientWidth, H = el.stage.clientHeight;
  if (W < 10) return;
  if (el.stage.width !== Math.round(W * dpr)) { el.stage.width = Math.round(W * dpr); el.stage.height = Math.round(H * dpr); }
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  const now = ctx ? ctx.currentTime : performance.now() / 1000;
  const skyH = H * 0.42;
  const X = (t) => ((t - (now - WINDOW)) / WINDOW) * W;

  g.fillStyle = "rgba(237,227,203,0.35)";
  for (const [sx, sy, sb] of stars) g.fillRect(sx * W, sy * H, sb > 0.8 ? 1.5 : 1, sb > 0.8 ? 1.5 : 1);

  // 持续中的声音（升空哨音）: 时间线上的青色横条
  const my = skyH + (H - skyH) * 0.3;
  g.fillStyle = "rgba(143,227,217,0.75)";
  for (const m of marks) {
    if (m.arriveEnd <= m.arrive || m.arrive > now) continue;
    const a = Math.max(0, X(m.arrive)), b = X(Math.min(m.arriveEnd, now));
    g.fillRect(a, my + 4, Math.max(0, b - a), 3);
  }

  // 事件: 天空弹道/闪光 + 时间线标记
  for (let k = marks.length - 1; k >= 0; k--) {
    const m = marks[k];
    if (m.arriveEnd < now - WINDOW) { marks.splice(k, 1); continue; }
    const col = KIND_COLOR[m.kind] || "#fff";
    const x = W * (0.5 + m.pan * 0.46);
    const age = now - m.tVis;
    const asc = Math.max(0.3, m.arriveEnd - m.arrive);
    if (m.type === "launch") {
      // 弹道: 从地面减速升到顶部, 到达炸点高度后隐去
      if (age >= 0 && age < asc + 0.3) {
        const p = Math.min(1, age / asc);
        const h = (2 - END_RATIO) * p - (1 - END_RATIO) * p * p;
        const y = skyH - 6 - h * skyH * 0.62;
        g.strokeStyle = `rgba(180,140,255,${(1 - Math.max(0, age - asc) / 0.3) * 0.9})`;
        g.lineWidth = 2;
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(x, Math.min(skyH - 6, y + 14 + 26 * (1 - p)));
        g.stroke();
      }
    } else if (age >= 0) {
      const life = m.type === "crack" ? 0.5 : 1.1;
      const p = age / life;
      if (p < 1) {
        const R = (m.type === "crack" ? 7 : 26) * (1 - Math.pow(1 - Math.min(1, p * 3), 2)) + 2;
        const grd = g.createRadialGradient(x, skyH * 0.38, 0, x, skyH * 0.38, R);
        grd.addColorStop(0, `rgba(255,255,255,${(1 - p) * 0.95})`);
        grd.addColorStop(0.5, col);
        grd.addColorStop(1, "rgba(0,0,0,0)");
        g.globalAlpha = 1 - p;
        g.fillStyle = grd;
        g.fillRect(x - R, skyH * 0.38 - R, R * 2, R * 2);
        g.globalAlpha = 1;
      }
      // 声音到达: 描一圈边 (0.35s)
      const sa = now - m.arrive;
      if (sa >= 0 && sa < 0.35 && !m.muted) {
        g.strokeStyle = `rgba(227,185,62,${1 - sa / 0.35})`;
        g.lineWidth = 2;
        g.beginPath();
        g.arc(x, skyH * 0.38, 8 + sa * 60, 0, Math.PI * 2);
        g.stroke();
      }
    }
    // 时间线
    const tx = X(m.tVis), ax = X(m.arrive);
    if (tx > -10 && tx < W + 10) {
      g.fillStyle = m.tVis > now ? "rgba(237,227,203,0.35)" : col;
      g.beginPath();
      g.moveTo(tx, my - 6); g.lineTo(tx - 4, my + 1); g.lineTo(tx + 4, my + 1); g.closePath();
      g.fill();
    }
    if (m.arrive <= now && ax > -10 && ax < W + 10 && !m.muted) {
      g.strokeStyle = "rgba(143,227,217,0.55)";
      g.lineWidth = 1;
      g.beginPath(); g.moveTo(tx, my); g.lineTo(ax, my); g.stroke();
      g.fillStyle = "#8fe3d9";
      g.beginPath(); g.arc(ax, my, m.type === "crack" ? 2 : 3.5, 0, Math.PI * 2); g.fill();
    }
  }

  // 电平
  if (analyser) {
    analyser.getFloatTimeDomainData(meter);
    let pk = 0;
    for (let i = 0; i < meter.length; i++) pk = Math.max(pk, Math.abs(meter[i]));
    levels.push({ t: now, v: Math.min(1, pk) });
  }
  const lb = H - 6, lt = skyH + (H - skyH) * 0.52;
  g.fillStyle = "rgba(143,227,217,0.85)";
  for (let k = levels.length - 1; k >= 0; k--) {
    const l = levels[k];
    const x = X(l.t);
    if (x < -2) { levels.splice(0, k + 1); break; }
    const h = Math.pow(l.v, 0.5) * (lb - lt);
    g.fillRect(x, lb - h, 2, h);
  }
  g.fillStyle = "rgba(237,227,203,0.4)";
  g.font = '11px Consolas, "Cascadia Mono", monospace';
  g.fillText("画面 · 横轴 = 方位", 8, 14);
  g.fillText(`时间线 · 最近 ${WINDOW} 秒`, 8, skyH + 13);
  g.fillStyle = "rgba(237,227,203,0.5)";
  for (let s = WINDOW - 1; s >= 0; s--) {
    g.fillText(s ? `-${s}s` : "现在", X(now - s) - (s ? 22 : 26), my + 16);
  }
  g.strokeStyle = "rgba(237,227,203,0.22)";
  g.beginPath(); g.moveTo(W - 0.5, skyH); g.lineTo(W - 0.5, H); g.stroke();

  if (voice) {
    const p = voice.bank.progress;
    el.bank.textContent = p >= 1 ? "音色库就绪" : `音色库生成中 ${(p * 100).toFixed(0)}%`;
  }
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

// 调试钩子（无头浏览器自检用: 确认音频真的在走）
window.__fwAudition = {
  st,
  get levels() { return levels.map((l) => +l.v.toFixed(3)); },
  get marks() { return marks.map((m) => ({ type: m.type, arrive: +m.arrive.toFixed(3), arriveEnd: +m.arriveEnd.toFixed(3) })); },
  get audio() {
    return ctx ? {
      state: ctx.state, t: ctx.currentTime, bank: voice.bank.progress, counts: voice.bank.counts,
      active: voice.active, ascentStyle: voice.ascentStyle, crackle: voice.crackle, brightness: voice.brightness,
    } : null;
  },
};
