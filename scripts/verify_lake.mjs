// 迷魂湖 v4 验证：栈桥/灯海/反射水 定点取证 + 许愿脉冲 + 湖面守卫 + 湖灯亮度联动 + FPS/drawcall 遥测
// 用法: node scripts/verify_lake.mjs [输出目录]   (GAME_URL 默认 http://127.0.0.1:8765)
// 性能指标只记录不设限 (用户决策 2026-11-17: 未来遇到实际卡顿再优化)
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/lake";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });

const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

// 基础断言: 湖模块与节点就位
const boot = await page.evaluate(() => ({
  hasLake: !!window.__game.lake,
  lanterns: window.__game.lake?.lanternCount ?? -1,
  water: !!window.__game.lake?.water,
  parkLake: window.__park?.lake ?? null,
  pois: (window.__park?.pois ?? []).length,
}));
console.log("boot:", JSON.stringify(boot));

// ---------- 回归守卫 (2026-11-18 事故: 湖守卫丢 ed<1 前置, 全园被当水域携行) ----------
// a) 出生点站桩 1.5s: 位置漂移应 ≈ 0 (守卫对湖外必须零干扰)
await page.evaluate(() => window.__game.player.teleport(0, 164));
await page.waitForTimeout(300);
const stand1 = await page.evaluate(() => new Promise((res) => {
  const g = window.__game;
  const p0 = { x: g.player.pos.x, z: g.player.pos.z };
  setTimeout(() => {
    res({ dx: +(g.player.pos.x - p0.x).toFixed(2), dz: +(g.player.pos.z - p0.z).toFixed(2) });
  }, 1500);
}));
const drift1 = Math.hypot(stand1.dx, stand1.dz);
console.log("regress-stand:", JSON.stringify(stand1), drift1 < 0.05 ? "OK(站桩零漂移)" : `FAIL(被拉动 ${drift1.toFixed(2)}m)`);
// b) 旧振荡点 (82.7,88) 静置 1s: 不再往返
await page.evaluate(() => window.__game.player.teleport(82.7, 88.0));
await page.waitForTimeout(1000);
const stand2 = await page.evaluate(() => {
  const p2 = window.__game.player.pos;
  return { x: +p2.x.toFixed(1), z: +p2.z.toFixed(1) };
});
const drift2 = Math.hypot(stand2.x - 82.7, stand2.z - 88);
console.log("regress-oscillation:", JSON.stringify(stand2), drift2 < 0.5 ? "OK(岸线静止)" : `FAIL(仍振荡 漂移${drift2.toFixed(1)}m)`);

// 定点取证: (x, z=app 坐标, yaw[atan2(-dx,-dz)], 俯仰, 标签)
const stops = [
  [82.0, 51.8, -2.13, -0.15, "1_pier_deck"],      // 栈桥桥面朝尽头平台 (站位 h=0.5 桥面)
  [78.0, 47.0, -2.18, -0.1, "2_shore_west"],      // 西岸入口望湖心灯海
  [135.0, 72.0, 1.24, -0.12, "3_east_look"],      // 东岸回望 (灯群西密东疏构图)
  [30.0, 30.0, -2.03, -0.05, "4_far_view"],       // 广场远眺 (雾中湖面)
  [88.6, 56.0, 1.01, -0.02, "5_tip_plaque"],      // 平台回望栈桥 (灯柱+铭牌+栏杆)
  [88.6, 56.0, -2.70, -0.25, "6_tip_water"],      // 平台尽头俯瞰灯海+光柱
];
for (const [x, z, yaw, pitch, label] of stops) {
  await page.evaluate(([tx, tz, ty, tp]) => {
    window.__game.player.teleport(tx, tz);
    window.__game.player.setView(ty, tp);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/${label}.png` });
  console.log("shot", label);
}

// 许愿脉冲: 直接触发后连拍涟漪扩散
await page.evaluate(() => {
  window.__game.player.teleport(88.6, 56.0);
  window.__game.player.setView(-2.70, -0.25);
  window.__game.lake.pulse();
});
await page.waitForTimeout(650);
await page.screenshot({ path: `${outDir}/7_pulse_ring.png` });
const pulseOk = await page.evaluate(() => {
  const p = window.__game.lake;
  const again = p.pulse(); // 冷却期内应返回 false
  return { againRejected: again === false };
});
console.log("pulse:", JSON.stringify(pulseOk));

// 湖面守卫: 传进湖心应被水流携行, 1.1s 后浪推上岸 (落到椭圆外)
await page.evaluate(() => window.__game.player.teleport(105.0, 66.0));
await page.waitForTimeout(1600);
const guard = await page.evaluate(() => {
  const p = window.__game.player.pos;
  const L = window.__park.lake;
  const n = Math.hypot((p.x - L.cx) / L.rx, (p.z - L.cz) / L.rz);
  return { pos: { x: +p.x.toFixed(1), z: +p.z.toFixed(1), y: +p.y.toFixed(2) }, norm: +n.toFixed(3) };
});
console.log("guard:", JSON.stringify(guard), guard.norm >= 1.0 ? "OK(浪推上岸)" : "FAIL(仍在湖心)");
await page.screenshot({ path: `${outDir}/8_guard_pushed.png` });

// 湖灯亮度联动: 20% / 200% 各采一帧 (栈桥视角)
await page.evaluate(() => {
  window.__game.player.teleport(82.0, 51.8);
  window.__game.player.setView(-2.13, -0.15);
});
const setVal = (k, v) => page.evaluate(([k2, v2]) => window.__settings.store.set(k2, v2), [k, v]);
await setVal("lakeGlow", 20);
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/9_glow_low.png` });
await setVal("lakeGlow", 200);
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/10_glow_high.png` });
await setVal("lakeGlow", 100);

// 遥测: drawcall / 三角面 / FPS (只记录不设限)
async function sampleFrame(label, x, z, yaw, pitch) {
  await page.evaluate(([tx, tz, ty, tp]) => {
    window.__game.player.teleport(tx, tz);
    window.__game.player.setView(ty, tp);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(400);
  return page.evaluate((lb) => new Promise((resolve) => {
    const r = window.__game.renderer;
    r.info.autoReset = false;
    r.info.reset();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      resolve({ label: lb, calls: r.info.render.calls, tris: r.info.render.triangles });
      r.info.autoReset = true;
    }));
  }), label);
}
const samples = [];
samples.push(await sampleFrame("pier", 82.0, 51.8, -2.13, -0.15));
samples.push(await sampleFrame("east", 135.0, 72.0, 1.24, -0.12));
samples.push(await sampleFrame("far", 30.0, 30.0, -2.03, -0.05));
const fps = await page.evaluate(() => new Promise((resolve) => {
  let n = 0;
  const t0 = performance.now();
  const tick = () => {
    n += 1;
    if (performance.now() - t0 < 2000) requestAnimationFrame(tick);
    else resolve(+(n / ((performance.now() - t0) / 1000)).toFixed(1));
  };
  requestAnimationFrame(tick);
}));
console.log("telemetry:", JSON.stringify({ samples, fps }));
writeFileSync(`${outDir}/telemetry.json`, JSON.stringify({ samples, fps, boot, guard }, null, 1));

await browser.close();
console.log("console-errors:", errors.length ? errors.join("\n") : "none");
