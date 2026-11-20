// 停靠回归 (方案A): 过缝合点→crawl 爬行进站→sHead 停正→dwell
// 症状背景: 旧逻辑过缝就地驻留, 头车压站台门槛, 后5节留在 -24° 刹车坡 (头尾高差 1.353m)
// 契约: ①过缝后 phase=crawl 且 s 连续推进 (非瞬移) ②终态 phase=dwell 且 s=sHead ③6车全水平+逐车对齐 centerline
import { mkdirSync, readFileSync } from "node:fs";
import { chromium } from "playwright";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const OUT = ".impeccable/review-coaster";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

// node 侧复算 sHead (与 coaster.js 同语义: station 样本中位数 + 5.875)
const cl = JSON.parse(readFileSync("public/assets/models/roller_coaster_centerline.json", "utf8"));
const N = cl.samples.length, DS = cl.ds, L = (N - 1) * DS;
const st = cl.samples.map((s, i) => (s.zone === "station" ? i * DS : -1)).filter((v) => v >= 0).sort((a, b) => a - b);
const sHead = st[Math.floor(st.length / 2)] + (6 / 2 - 0.5) * 2.35;
console.log("sHead(expect) =", sHead);
function expect(s) {
  const f = (((s % L) + L) % L) / DS;
  const i0 = Math.min(N - 2, Math.floor(f)), u = f - i0;
  const a = cl.samples[i0].p, b = cl.samples[i0 + 1].p;
  return [a[0] + (b[0] - a[0]) * u, a[2] + (b[2] - a[2]) * u, -(a[1] + (b[1] - a[1]) * u)];
}

// 1) 过缝回归: seek 缝合点前 1m, 2.5s 后应处 crawl 且 s 已过缝推进中
const mid2 = await page.evaluate(async (SH) => {
  const c = window.__game.coaster;
  c.seek(502.5); // L=503.5, 缝合点前 1m
  await new Promise((r) => setTimeout(r, 2500));
  return { phase: c.state.phase, s: +c.state.s.toFixed(2), v: +c.state.v.toFixed(2), laps: c.state.laps, sHead: +SH.toFixed(3) };
}, sHead);
console.log("MID(过缝+2.5s)", JSON.stringify(mid2));

// 2) 轮询至 dwell, 断言停正位置 = sHead
const end = await page.evaluate(async (SH) => {
  const c = window.__game.coaster;
  for (let t = 0; t < 200; t++) {
    await new Promise((r) => setTimeout(r, 100));
    if (c.state.phase === "dwell" && t > 30) break; // 跳过 seek 后残留的旧 dwell 态
  }
  const s = c.state.s;
  // 逐车世界坐标
  const cars = c.cars.map((car, i) => {
    car.updateWorldMatrix(true, false);
    const p = car.getWorldPosition(car.position.clone());
    return { i, x: +p.x.toFixed(3), y: +p.y.toFixed(3), z: +p.z.toFixed(3) };
  });
  return { phase: c.state.phase, s: +s.toFixed(3), sHead: +SH.toFixed(3), v: c.state.v, cars };
}, sHead);

const GAP = 2.35;
const cmp = end.cars.map((c, i) => {
  const e = expect(end.s - i * GAP);
  const d = Math.hypot(c.x - e[0], c.y - e[1], c.z - e[2]);
  return { i, got: [c.x, c.y, c.z], want: e.map((v) => +v.toFixed(2)), delta: +d.toFixed(3) };
});
const ys = end.cars.map((c) => c.y);
const levelDiff = +(Math.max(...ys) - Math.min(...ys)).toFixed(3);

const PASS =
  mid2.phase === "crawl" && mid2.s > 0.5 && mid2.s < sHead &&
  end.phase === "dwell" && Math.abs(end.s - sHead) < 0.02 && end.v === 0 &&
  levelDiff < 0.05 && cmp.every((c) => c.delta < 0.05);

console.log("END", JSON.stringify({ phase: end.phase, s: end.s, sHead: +sHead.toFixed(3), levelDiff, lapParkOk: Math.abs(end.s - sHead) < 0.02 }));
console.log("CAR_CMP", JSON.stringify(cmp));
console.log("VERDICT", PASS ? "PASS ✅ (过缝→crawl→sHead 停正→dwell, 全列水平)" : "FAIL ❌");

// 3) 取证机位 (verify_chase 同款数值解: 目标点东侧 dist 米地面仰拍, 避开西侧迷宫围挡)
function frameAt(s) {
  const f = (((s % L) + L) % L) / DS;
  const i0 = Math.min(N - 2, Math.floor(f)), u = f - i0;
  const a = cl.samples[i0].p, b = cl.samples[i0 + 1].p;
  return [a[0] + (b[0] - a[0]) * u, a[2] + (b[2] - a[2]) * u, -(a[1] + (b[1] - a[1]) * u)];
}
function camFor(target, dist = 9, up = 1.2) {
  const cam = [target[0] + dist, up, target[2]];
  const dx = target[0] - cam[0], dy = target[1] + 1.0 - cam[1], dz = target[2] - cam[2];
  return { x: cam[0], z: cam[2], yaw: Math.atan2(-dx, -dz), pitch: Math.atan2(dy, Math.hypot(dx, dz)) };
}
async function shotAt(name, s, wait = 350) {
  const c = camFor(frameAt(s));
  await page.evaluate(([x, z, yaw, pitch]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(yaw, pitch);
  }, [c.x, c.z, c.yaw, c.pitch]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name);
}
await shotAt("p1_park_side", end.s);   // 停正列车侧视 (dwell 态实拍)
await shotAt("p4_brake_clear", 497);   // 刹车坡中段: 坡上应无车 (bug 症状对照)
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
process.exit(PASS && errors.length === 0 ? 0 : 1);
