// 游戏内烟花音效验证（接入后的端到端取证）:
//   A 触发点传参: 升空/爆裂/火星分裂事件的距离、方位(声像)、升空时长、时序是否与画面几何一致
//   B 炸点高度设置 → 哨音时长随之变化
//   C 设置项 → 播放引擎: 音量 / 声延迟 / 升空哨音响量 / 裂响亮度 / 碎裂 (store 路径 + 面板 UI 路径)
//   D 节点不泄漏: 一轮之后在播事件数回到 0
//   E 实时录音: 把 master 实际输出录下来解码分析, 确认哨音贯穿升空段、爆裂落在「升空时长 + 声延迟」处
//   F 帧间隔抽样: 空闲 vs 多发齐射（含哨音叠加）
// 用法: node scripts/verify_fw_audio.mjs [输出目录]   (需 dev 服务器已在 8765 运行)
import { chromium } from "playwright";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/fw_audio";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  channel: "chrome",
  args: ["--autoplay-policy=no-user-gesture-required"], // 无头环境里让入园点击后的音频图照常运行
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("favicon")) errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

const results = [];
const check = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
};
const sleep = (ms) => page.waitForTimeout(ms);
const store = (k, v) => page.evaluate(([k, v]) => window.__settings.store.set(k, v), [k, v]);

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await sleep(1200);
await store("fireworkPeriod", 0); // 关自动秀, 逐项取证

// 音色库在入园后的空闲帧里切片生成
await page.waitForFunction(() => (window.__game.audio.fw?.bank.progress ?? 0) >= 1, { timeout: 30000 });

// 给播放引擎的三个入口套一层调用日志
await page.evaluate(() => {
  const fw = window.__game.audio.fw;
  window.__fwLog = [];
  for (const m of ["launch", "burst", "crack"]) {
    const orig = fw[m].bind(fw);
    fw[m] = (...args) => {
      const o = args[args.length - 1] || {};
      window.__fwLog.push({ m, kind: args[0], dist: o.dist, pan: o.pan, ascent: o.ascent, endDist: o.endDist, t: window.__game.audio.ctx.currentTime });
      return orig(...args);
    };
  }
});
const log = () => page.evaluate(() => window.__fwLog);
const clearLog = () => page.evaluate(() => { window.__fwLog = []; });
const standAt = (x, z, tx, tz) => page.evaluate(([x, z, tx, tz]) => {
  window.__game.player.teleport(x, z);
  window.__game.player.setView(Math.atan2(-(tx - x), -(tz - z)), 0.25);
}, [x, z, tx, tz]);
// 画面几何 → 期望的声学参数 (与 fireworks.js acoustics 同口径)
const expect = (lid) => page.evaluate((lid) => {
  const L = window.__game.fireworks.getLaunchers()[lid];
  const cam = window.__game.camera;
  const e = cam.matrixWorld.elements;
  const right = { x: e[0], y: e[1], z: e[2] };
  const tube = { x: L.x, y: L.mz, z: L.z };
  const d = Math.hypot(tube.x - cam.position.x, tube.y - cam.position.y, tube.z - cam.position.z);
  const pan = 0.85 * ((tube.x - cam.position.x) * right.x + (tube.z - cam.position.z) * right.z + (tube.y - cam.position.y) * right.y) / d;
  return { kind: L.kind, tubeDist: d, tubePan: pan, cam: { x: cam.position.x, y: cam.position.y, z: cam.position.z } };
}, lid);
const near = (a, b, tol) => Math.abs(a - b) <= tol;

// ---------- A: 触发点传参 ----------
// 站园心朝 +x 看: +z 一侧在右 (pan>0), -z 一侧在左 (pan<0)
await standAt(0, 40, 10, 40);
await sleep(400);
const sites = await page.evaluate(() => window.__game.fireworks.getLaunchers().map((l) => ({ id: l.id, kind: l.kind, x: l.x, z: l.z })));
const iC = sites.findIndex((s) => s.z > 50 && s.kind === "C");   // L6 椰芯 (11, 84): 右侧
const iA = sites.findIndex((s) => s.z < -10 && s.kind === "A");  // L2 牡丹 (56, -30): 左侧
const expC = await expect(iC);
await clearLog();
await page.evaluate((lid) => window.__game.fireworks.fire(lid), iC);
await sleep(6200);
const logC = await log();
const launchC = logC.filter((e) => e.m === "launch");
const burstC = logC.filter((e) => e.m === "burst");
const crackC = logC.filter((e) => e.m === "crack");
check("A1 椰芯: 1 次升空 + 1 次爆裂 + 16-20 次火星分裂",
  launchC.length === 1 && burstC.length === 1 && crackC.length >= 16 && crackC.length <= 20,
  `升空 ${launchC.length} / 爆裂 ${burstC.length} / 分裂 ${crackC.length}`);
const lc = launchC[0] || {}, bc = burstC[0] || {};
check("A2 升空声: 管口距离/方位与相机几何一致, 炸点在右侧 → pan>0",
  !!lc.dist && near(lc.dist, expC.tubeDist, 0.3) && near(lc.pan, expC.tubePan, 0.02) && lc.pan > 0.5,
  `dist ${lc.dist?.toFixed(2)} (期望 ${expC.tubeDist.toFixed(2)}) pan ${lc.pan?.toFixed(3)} (期望 ${expC.tubePan.toFixed(3)})`);
const ascExp = 3.5;
check("A3 哨音时长 = 实际升空时间(默认炸点高度 55m ≈ 3.3-3.7s), 炸点距离不小于管口距离",
  !!lc.ascent && lc.ascent > 3.3 && lc.ascent < 3.7 && lc.endDist >= lc.dist - 0.5,
  `ascent ${lc.ascent?.toFixed(3)}s  endDist ${lc.endDist?.toFixed(1)}m`);
check("A4 爆裂声在升空后 ascent 秒触发 (±0.12s), 声像同侧",
  !!bc.t && near(bc.t - lc.t, lc.ascent, 0.12) && bc.pan > 0.35 && bc.kind === "C",
  `Δt=${(bc.t - lc.t).toFixed(3)}s  burst pan ${bc.pan?.toFixed(3)}  dist ${bc.dist?.toFixed(1)}m`);
const crackDt = crackC.map((e) => e.t - bc.t);
check("A5 火星分裂脆响落在爆裂后 0.8-1.2s, 各带自己的声像",
  crackC.length > 0 && crackDt.every((d) => d >= 0.79 && d <= 1.21) && crackC.every((e) => e.pan > 0.3),
  `Δt ${Math.min(...crackDt).toFixed(2)}–${Math.max(...crackDt).toFixed(2)}s  pan ${Math.min(...crackC.map((e) => e.pan)).toFixed(2)}–${Math.max(...crackC.map((e) => e.pan)).toFixed(2)}`);

const expA = await expect(iA);
await clearLog();
await page.evaluate((lid) => window.__game.fireworks.fire(lid), iA);
await sleep(1200);
const logA = await log();
const la = logA.find((e) => e.m === "launch") || {};
check("A6 牡丹(另一侧): 炸点在左侧 → pan<0, 距离一致",
  !!la.dist && near(la.dist, expA.tubeDist, 0.3) && near(la.pan, expA.tubePan, 0.02) && la.pan < -0.3,
  `dist ${la.dist?.toFixed(2)} (期望 ${expA.tubeDist.toFixed(2)}) pan ${la.pan?.toFixed(3)} (期望 ${expA.tubePan.toFixed(3)})`);
await sleep(4800); // 等这发的尾音走完

// ---------- B: 炸点高度 → 哨音时长 ----------
const ascAt = async (h) => {
  await store("fireworkHeight", h);
  await clearLog();
  await page.evaluate((lid) => window.__game.fireworks.fire(lid), iA);
  await sleep(700);
  const l = (await log()).find((e) => e.m === "launch");
  await sleep(Math.ceil((l?.ascent ?? 3.5) * 1000) + 3600);
  return l?.ascent ?? 0;
};
const asc90 = await ascAt(90), asc25 = await ascAt(25);
await store("fireworkHeight", 55);
check("B 炸点高度 90m / 25m → 哨音时长 ≈ 4.6s / 2.3s", asc90 > 4.4 && asc90 < 4.8 && asc25 > 2.15 && asc25 < 2.4,
  `${asc90.toFixed(2)}s / ${asc25.toFixed(2)}s`);

// ---------- C: 设置项 → 播放引擎 ----------
const voice = () => page.evaluate(() => {
  const fw = window.__game.audio.fw;
  return { volume: fw.volume, delay: fw.delay, brightness: fw.brightness, crackle: fw.crackle, ascentDb: fw.ascentDb };
});
await store("fireworkVolume", 50); await store("fireworkSoundDelay", false); await store("fireworkAscentVolume", 200);
await store("fireworkCrisp", 150); await store("fireworkCrackle", false);
let v = await voice();
check("C1 store 路径: 音量 50% / 延迟关 / 哨音 200%(+6dB) / 亮度 150%(+4dB) / 碎裂关",
  near(v.volume, 0.5, 1e-3) && v.delay === false && near(v.ascentDb, 6.02, 0.05) && near(v.brightness, 4, 1e-3) && v.crackle === false,
  JSON.stringify(Object.fromEntries(Object.entries(v).map(([k, x]) => [k, typeof x === "number" ? +x.toFixed(2) : x]))));

// 面板 UI 路径: 开关点一下、滑杆拖一下
await page.keyboard.press("KeyO");
await sleep(700);
await page.evaluate(() => {
  const h = [...document.querySelectorAll(".set-group h3")].find((n) => n.textContent === "烟花");
  h?.scrollIntoView({ block: "start" });
});
await page.click('button.set-switch[aria-label="真实声延迟"]');
await page.evaluate(() => {
  const input = [...document.querySelectorAll(".set-slider")].find((i) => i.getAttribute("aria-label") === "裂响亮度");
  input.value = "50";
  input.dispatchEvent(new Event("input", { bubbles: true }));
});
await sleep(300);
await page.screenshot({ path: `${outDir}/ingame_settings_fireworks.png` });
v = await voice();
check("C2 面板 UI 路径: 点「真实声延迟」→ 开, 「裂响亮度」拖到 50% → -4dB",
  v.delay === true && near(v.brightness, -4, 1e-3), `delay ${v.delay} brightness ${v.brightness}`);
await page.keyboard.press("KeyO");
await sleep(400);
// 恢复默认 (也是持久化路径: 重载后应读到默认)
for (const [k, val] of [["fireworkVolume", 100], ["fireworkSoundDelay", true], ["fireworkAscentVolume", 100], ["fireworkCrisp", 100], ["fireworkCrackle", true]]) await store(k, val);
v = await voice();
check("C3 恢复默认后播放引擎回到 100% / 延迟开 / +0dB / +0dB / 碎裂开",
  near(v.volume, 1, 1e-3) && v.delay && near(v.ascentDb, 0, 1e-3) && near(v.brightness, 0, 1e-3) && v.crackle,
  JSON.stringify(Object.fromEntries(Object.entries(v).map(([k, x]) => [k, typeof x === "number" ? +x.toFixed(2) : x]))));

// ---------- E: 实时录音 (站在 L6 旁约 12m, 背景音乐保持开启) ----------
await standAt(sites[iC].x - 12, sites[iC].z + 2, sites[iC].x, sites[iC].z);
await sleep(400);
await page.evaluate((lid) => {
  const a = window.__game.audio;
  const dest = a.ctx.createMediaStreamDestination();
  a.master.connect(dest);
  const rec = new MediaRecorder(dest.stream, { mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 128000 });
  const chunks = [];
  window.__recDone = new Promise((resolve) => {
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      new Blob(chunks, { type: "audio/webm" }).arrayBuffer().then((buf) => {
        const u8 = new Uint8Array(buf);
        let bin = "";
        for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
        resolve(btoa(bin));
      });
    };
  });
  rec.start();
  window.__rec = rec;
  setTimeout(() => window.__game.fireworks.fire(lid), 500);   // 录 0.5s 底噪后发射
}, iC);
const nearDist = await expect(iC);
await sleep(7500);
const webmB64 = await page.evaluate(() => new Promise((resolve) => { window.__rec.stop(); window.__recDone.then(resolve); }));
writeFileSync(`${outDir}/ingame_capture.webm`, Buffer.from(webmB64, "base64"));
const pcm = await page.evaluate(async (b64) => {
  const bin = atob(b64);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const buf = await window.__game.audio.ctx.decodeAudioData(u8.buffer);
  const L = buf.getChannelData(0), R = buf.getChannelData(buf.numberOfChannels > 1 ? 1 : 0);
  const i16 = new Int16Array(L.length * 2);
  for (let i = 0; i < L.length; i++) {
    i16[i * 2] = Math.max(-32768, Math.min(32767, Math.round(L[i] * 32767)));
    i16[i * 2 + 1] = Math.max(-32768, Math.min(32767, Math.round(R[i] * 32767)));
  }
  const b = new Uint8Array(i16.buffer);
  let out = "";
  for (let i = 0; i < b.length; i += 0x8000) out += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
  return { sr: buf.sampleRate, b64: btoa(out) };
}, webmB64);
{
  const data = Buffer.from(pcm.b64, "base64");
  const hdr = Buffer.alloc(44);
  const ch = 2, sr = pcm.sr;
  hdr.write("RIFF", 0); hdr.writeUInt32LE(36 + data.length, 4); hdr.write("WAVE", 8); hdr.write("fmt ", 12);
  hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20); hdr.writeUInt16LE(ch, 22);
  hdr.writeUInt32LE(sr, 24); hdr.writeUInt32LE(sr * ch * 2, 28); hdr.writeUInt16LE(ch * 2, 32); hdr.writeUInt16LE(16, 34);
  hdr.write("data", 36); hdr.writeUInt32LE(data.length, 40);
  writeFileSync(`${outDir}/ingame_capture.wav`, Buffer.concat([hdr, data]));
}

// 录音分析: 每 100ms 的 线性电平 / 25ms 内峰值 / 950-3600kHz 频带功率与最强谱线
// (频带避开八音盒 BGM 的基音 523-880Hz —— 哨音在升空段应当是这个频带里的最强谱线, 且一路下不来地往上滑)
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
{
  const w = readWav(`${outDir}/ingame_capture.wav`);
  const N = 4096, hop = Math.round(w.sr * 0.1);
  const re = new Float64Array(N), im = new Float64Array(N), H = new Float64Array(N);
  for (let i = 0; i < N; i++) H[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / N);
  const rows = [];
  let gpk = 0;
  for (let s = 0; s + N <= w.L.length; s += hop) {
    let e = 0, pk = 0;
    const e1 = Math.min(w.L.length, s + hop);   // 末窗可能不足 100ms
    for (let i = s; i < e1; i++) {
      e += (w.L[i] * w.L[i] + w.R[i] * w.R[i]) / 2;
      pk = Math.max(pk, Math.abs(w.L[i]), Math.abs(w.R[i]));
    }
    gpk = Math.max(gpk, pk);
    for (let i = 0; i < N; i++) { re[i] = ((w.L[s + i] + w.R[s + i]) / 2) * H[i]; im[i] = 0; }
    fft(re, im);
    let best = 0, bf = 0, band = 0;
    for (let k = 1; k < N / 2; k++) {
      const f = (k * w.sr) / N;
      if (f < 950 || f > 3600) continue;
      const p = re[k] * re[k] + im[k] * im[k];
      band += p;
      if (p > best) { best = p; bf = f; }
    }
    rows.push({ t: s / w.sr, db: 10 * Math.log10(e / (e1 - s) + 1e-30), pk: 20 * Math.log10(pk + 1e-9), band: 10 * Math.log10(band + 1e-30), f: bf });
  }
  const inWin = (a, b) => rows.filter((r) => r.t >= a && r.t <= b);
  const maxIn = (a, b, key) => inWin(a, b).reduce((m, r) => (r[key] > m[key] ? r : m));
  const med = (arr) => { const b = [...arr].sort((x, y) => x - y); return b[b.length >> 1]; };
  // 时间线: 发射在录音 0.5s 处。近处管口闷响比远处爆裂更响, 不能拿「全程最响」当爆裂 ——
  // 先取 1.3s 内最响的窗 = 闷响, 再取其后 2.9-4.6s 内峰值最大的窗 = 爆裂
  const thump = maxIn(0.3, 1.3, "db");
  const burst = maxIn(thump.t + 2.9, thump.t + 4.6, "pk");
  const asc = inWin(thump.t + 0.4, burst.t - 0.3);
  const fEarly = med(asc.slice(0, 5).map((r) => r.f));
  const fLate = med(asc.slice(-10).map((r) => r.f));
  const bgBand = med(inWin(0, 0.45).map((r) => r.band));
  const ascBand = med(asc.map((r) => r.band));
  const bg = inWin(0, 0.45);
  console.log(`录音 ${(w.L.length / w.sr).toFixed(1)}s @${w.sr}Hz, 站在发射架旁 ${nearDist.tubeDist.toFixed(1)}m, 全局峰值 ${(20 * Math.log10(gpk)).toFixed(2)} dBFS`);
  console.log(`发射前底噪(音乐+环境): 峰值 ${Math.max(...bg.map((r) => r.pk)).toFixed(1)} dBFS; 管口闷响 @${thump.t.toFixed(1)}s: 峰值 ${thump.pk.toFixed(1)} dBFS; 爆裂 @${burst.t.toFixed(1)}s: 峰值 ${burst.pk.toFixed(1)} dBFS`);
  console.log("升空段每 100ms (距闷响秒: 电平dBFS / 950-3.6kHz 最强谱线Hz):");
  console.log(asc.map((r) => `${(r.t - thump.t).toFixed(1)}:${r.db.toFixed(0)}/${r.f.toFixed(0)}`).join("  "));
  check("E0 爆裂落在发射后「升空时长 + 声延迟」处 (3.3-4.1s)", burst.t - thump.t > 3.3 && burst.t - thump.t < 4.1, `间隔 ${(burst.t - thump.t).toFixed(1)}s`);
  check("E1 升空段有持续的哨音: 频带内最强谱线一路从 1.5kHz 以下上滑到 1.8kHz 以上", asc.length > 15 && fEarly < 1500 && fLate > 1800 && fLate - fEarly > 400 && asc.slice(1).filter((r, k) => r.f < asc[k].f - 150).length <= 2,
    `早段中位 ${fEarly.toFixed(0)}Hz → 晚段中位 ${fLate.toFixed(0)}Hz, 共 ${asc.length} 个窗`);
  check("E2 哨音频带能量高于发射前底噪 6dB 以上", ascBand - bgBand > 6, `${ascBand.toFixed(1)} vs ${bgBand.toFixed(1)} dB (带内)`);
  writeFileSync(`${outDir}/ingame_capture_rows.json`, JSON.stringify(rows.map((r) => Object.fromEntries(Object.entries(r).map(([k, x]) => [k, +x.toFixed(2)])))));
}

// ---------- D: 节点不泄漏 ----------
await page.waitForFunction(() => window.__game.audio.fw.active === 0, { timeout: 20000 }).catch(() => {});
const active = await page.evaluate(() => window.__game.audio.fw.active);
check("D 一轮之后在播事件数回到 0", active === 0, `active=${active}`);

// ---------- F: 帧间隔抽样: 空闲 vs 齐射 ----------
const sampleFrames = (ms) => page.evaluate((ms) => new Promise((resolve) => {
  const dt = [];
  let last = performance.now();
  const t0 = last;
  const tick = (now) => {
    dt.push(now - last);
    last = now;
    if (now - t0 < ms) requestAnimationFrame(tick); else resolve(dt);
  };
  requestAnimationFrame(tick);
}), ms);
const stat = (dt) => {
  const s = [...dt].sort((a, b) => a - b);
  return { avg: dt.reduce((a, b) => a + b, 0) / dt.length, p95: s[Math.floor(s.length * 0.95)], max: s[s.length - 1], n: dt.length };
};
await standAt(0, 40, 0, 0);
const idle = stat(await sampleFrames(3000));
const busyPromise = sampleFrames(7000);
for (let k = 0; k < 9; k++) {
  await page.evaluate(() => window.__game.fireworks.getLaunchers().forEach((_, i) => window.__game.fireworks.fire(i)));
  await sleep(750);
}
const busy = stat(await busyPromise);
console.log(`帧间隔 空闲: avg ${idle.avg.toFixed(1)}ms p95 ${idle.p95.toFixed(1)} max ${idle.max.toFixed(1)}  |  齐射(6 站 × 9 轮): avg ${busy.avg.toFixed(1)}ms p95 ${busy.p95.toFixed(1)}ms max ${busy.max.toFixed(1)}ms  (无头软渲染, 只看相对差)`);
check("F 齐射时帧间隔没有明显恶化 (p95 增幅 < 30%)", busy.p95 < idle.p95 * 1.3 + 4, `p95 ${idle.p95.toFixed(1)} → ${busy.p95.toFixed(1)}ms`);

check("全程无控制台报错 / 页面异常", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();

function readWav(path) {
  const b = readFileSync(path);
  const ch = b.readUInt16LE(22), sr = b.readUInt32LE(24);
  const n = (b.length - 44) / (2 * ch);
  const c = [];
  for (let k = 0; k < ch; k++) {
    const f = new Float32Array(n);
    for (let i = 0; i < n; i++) f[i] = b.readInt16LE(44 + (i * ch + k) * 2) / 32768;
    c.push(f);
  }
  return { sr, L: c[0], R: c[1] ?? c[0] };
}

const failed = results.filter((r) => !r).length;
console.log(`\nVERIFY_DONE  ${results.length - failed}/${results.length} 通过`);
process.exit(failed ? 1 : 0);
