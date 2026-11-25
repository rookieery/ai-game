// 显灵木马碰撞回归（真键走线，2026-11-25 评审后建立）
// 前置: dev server 已起 (GAME_URL 环境变量, 默认 8765); 碰撞表已由 patch_carousel_colliders.mjs 打补丁并 sync
// 断言:
//   F 围栏   —— 从 r12.4 真按 W 走向中心: 柱与跨中之间的方位 (±1–5°) 也必须被挡在围栏外。
//               旧版 (柱 r0.09 + 跨中 r0.30, 排斥盘只重叠 3cm) 在偏离圆心 >=1° 的方位被挤穿, 只测圆心方位会假通过
//   C 走廊   —— 入口轴 202°±8° 走进来: 恰好四次抬升, 每次都在可见踏步边缘 ±0.45m 内, 最终站上平台 0.62
//   C 侧壁   —— 202°±14° (踏步宽度之外) 走到台侧: 不抬升、被挡在平台外 (不能踩空气)
//   M 马位   —— 冻结转角后站进马头区 / 马尾区会被推出来; 站在内圈甲板不被推
//   B 骑乘   —— 盘面按 E 上马、E 下马回平台 (冒烟)
// 用法: GAME_URL=http://127.0.0.1:8765 node scripts/verify_carousel_colliders.mjs
import { chromium } from "playwright";

const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const CX = 45, CZ = -18;                 // 木马中心 (app 坐标)
const rad = (d) => (d * Math.PI) / 180;
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1280, height: 640 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => { const b = document.getElementById("enter-btn"); return b && !b.disabled; }, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForFunction(() => window.__game && window.__game.state === "walk", { timeout: 15000 }).catch(async () => {
  await page.evaluate(() => document.getElementById("enter-btn").click());
  await page.waitForFunction(() => window.__game && window.__game.state === "walk", { timeout: 10000 });
});
await page.waitForTimeout(1200);
await page.evaluate(() => window.__settings.store.set("walkSpeed", 2)); // 2 m/s: 40ms 采样 ≈ 8cm

const fails = [];
const expect = (name, cond, detail = "") => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"}: ${name}${detail ? "  " + detail : ""}`);
};
const rOf = (s) => Math.hypot(s[0] - CX, s[2] - CZ);

// 传到 (r, 方位角Blender) 朝中心, 按住 W 走 seconds 秒, 每 40ms 采一次 (r, y)
async function walk(az, r0, seconds, y = 0) {
  const x = CX + r0 * Math.cos(rad(az)), z = CZ - r0 * Math.sin(rad(az));
  const yaw = Math.atan2(-(CX - x), -(CZ - z));   // controller forward = (-sin yaw, -cos yaw)
  await page.evaluate(([x, z, y, yaw]) => {
    window.__game.player.teleport(x, z, y);
    window.__game.player.setView(yaw, 0);
  }, [x, z, y, yaw]);
  await page.waitForTimeout(250);
  const trace = [];
  await page.keyboard.down("KeyW");
  const t0 = Date.now();
  while (Date.now() - t0 < seconds * 1000) {
    await page.waitForTimeout(40);
    const s = await page.evaluate(() => { const p = window.__game.player.pos; return [p.x, p.y, p.z]; });
    trace.push({ r: rOf(s), y: s[1] });
  }
  await page.keyboard.up("KeyW");
  await page.waitForTimeout(150);
  const last = trace[trace.length - 1];
  return { trace, r: last.r, y: last.y, minR: Math.min(...trace.map((q) => q.r)) };
}

// ---------- F 围栏 ----------
const fenceAz = [];
// 基准方位取在入口走廊 (180°–228°) 之外: 走廊两端的端头圆会把斜着走来的人滑进走廊, 那是正常行为;
// 走廊是否开阔由下面「台侧」两项断言 (188° / 216° 必须一路走到平台侧壁, 不能被围栏截在 r≈11)
for (const base of [30, 138, 234, 306]) for (let d = -5; d <= 5; d++) fenceAz.push(base + d);
const through = [];
for (const az of fenceAz) {
  const w = await walk(az, 12.4, 1.7);
  if (!(w.r >= 11.0 && w.y === 0)) through.push(`${az}°(r${w.r.toFixed(2)},y${w.y})`);
}
expect("围栏 44 个方位全部挡住", through.length === 0,
  `挡住 ${fenceAz.length - through.length}/${fenceAz.length}${through.length ? "  穿透: " + through.join(" ") : ""}`);

// ---------- C 走廊台阶 ----------
// 可见踏步径向外缘 (app r) 与对应高度: 10.005 / 9.335 / 8.665, 平台边 8.0
const EDGES = [10.005, 9.335, 8.665, 8.0];
for (const az of [194, 202, 210]) {
  const w = await walk(az, 12.4, 6.0);
  const rises = [];
  for (let i = 1; i < w.trace.length; i++) {
    const a = w.trace[i - 1], b = w.trace[i];
    if (Math.abs(b.y - a.y) > 0.03) rises.push({ to: b.y, r: (a.r + b.r) / 2 });
  }
  const detail = rises.map((q) => `${q.to.toFixed(3)}@r${q.r.toFixed(2)}`).join(" ");
  expect(`走廊 ${az}° 恰好四次抬升`, rises.length === 4, detail);
  let maxErr = 0;
  if (rises.length === 4) rises.forEach((q, k) => { maxErr = Math.max(maxErr, Math.abs(q.r - EDGES[k])); });
  else maxErr = Infinity;
  expect(`走廊 ${az}° 抬升点贴可见踏步边 (误差 <=0.45m)`, maxErr <= 0.45, `最大误差 ${maxErr.toFixed(2)}m`);
  expect(`走廊 ${az}° 站上平台`, Math.abs(w.y - 0.62) < 0.03, `y=${w.y.toFixed(3)}`);
}
// 侧壁: 踏步宽度之外 (±14°) 走到台侧, 不抬升
for (const az of [188, 216]) {
  const w = await walk(az, 12.4, 3.5);
  const maxY = Math.max(...w.trace.map((q) => q.y));
  expect(`台侧 ${az}° 不踩空气且被挡在平台外`, maxY === 0 && w.r >= 8.3, `y=${w.y} r=${w.r.toFixed(2)}`);
}

// ---------- M 马位 (冻结转角) ----------
await page.evaluate(() => {
  const c = window.__game.carousel;
  if (!c.__upd) c.__upd = c.update;
  c.__upd.call(c, 0);
  c.update = () => {};
  window.__game.scene.updateMatrixWorld(true);
});
const m = await page.evaluate(async ([CX, CZ]) => {
  const g = window.__game, out = {};
  const root = g.carousel.rideRoots[2];           // 象牙马 (马头在本地 +X = 行进方向)
  root.updateWorldMatrix(true, false);
  const e = root.matrixWorld.elements;
  const px = e[12], pz = e[14], tx = e[0], tz = e[2];
  const drop = async (x, z) => {
    g.player.teleport(x, z, 0.62);
    await new Promise((res) => setTimeout(res, 700));
    const p = g.player.pos;
    return { d: Math.hypot(p.x - x, p.z - z), y: p.y };
  };
  out.head = await drop(px + 1.5 * tx, pz + 1.5 * tz);   // 鼻尖下方 (旧版允许站进马头)
  out.tail = await drop(px - 1.1 * tx, pz - 1.1 * tz);   // 尾梢下方
  out.inner = await drop(CX + 4.6, CZ);                   // 内圈甲板 (马环内侧 1.6m)
  return out;
}, [CX, CZ]).catch((err) => ({ error: String(err) }));
console.log("measure 马位推移:", JSON.stringify(m));
// 头圈: 圆心 +1.05、r0.40 → 排斥半径 0.78; 站在 +1.5 处被推到距圈心 0.78 (位移 0.33), 落点在鼻尖 (1.74) 之外
expect("站进马头区会被推出 (落到鼻尖之外)", !m.error && m.head.d >= 0.3, `位移 ${m.error ? m.error : m.head.d.toFixed(2)}m`);
expect("站进马尾区会被推出", !m.error && m.tail.d > 0.5, `位移 ${m.error ? m.error : m.tail.d.toFixed(2)}m`);
expect("内圈甲板站立不动", !m.error && m.inner.d < 0.1, `位移 ${m.error ? m.error : m.inner.d.toFixed(2)}m`);

// ---------- B 骑乘冒烟 ----------
await page.evaluate(() => {
  const g = window.__game, c = g.carousel;
  c.update = c.__upd; delete c.__upd;
  g.player.teleport(39.5, -14.5, 0.62);
  g.player.setView(0.9, 0);
});
await page.waitForTimeout(600);
await page.keyboard.press("KeyE");
await page.waitForTimeout(1200);
const riding = await page.evaluate(() => window.__game.state);
expect("盘面按 E 上马", riding === "riding", `state=${riding}`);
await page.keyboard.press("KeyE");
await page.waitForTimeout(1100);
const back = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { s: window.__game.state, y: p.y, r: Math.hypot(p.x - 45, p.z + 18) };
});
expect("E 下马回平台", back.s === "walk" && Math.abs(back.y - 0.62) < 0.03 && Math.abs(back.r - 7.6) < 0.8, JSON.stringify(back));

console.log(errors.length ? "CONSOLE_ERRORS:\n" + [...new Set(errors)].join("\n") : "no console errors");
console.log(fails.length ? `FAILED: ${fails.length} 项` : "ALL_OK");
await browser.close();
process.exit(fails.length || errors.length ? 1 : 0);
