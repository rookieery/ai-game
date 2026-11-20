// M3 过山车实机取证: 定点截图 + FPS/drawcall 采样 + 列车运行状态断言
// 用法: 先 npm run dev (端口 8765 顺延可 GAME_URL 覆盖), 再 node scripts/verify_coaster.mjs
import { mkdirSync } from "node:fs";
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
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

const report = {};

// 0) 资产与节点完整性断言
report.nodes = await page.evaluate(() => {
  const c = window.__game.coaster;
  if (!c) return { ok: false, why: "coaster 模块缺失" };
  return {
    ok: true,
    cars: c.cars.filter(Boolean).length,
    phase: c.state.phase,
    v: +c.state.v.toFixed(2),
    s: +c.state.s.toFixed(1),
  };
});

// 定点截图 helper: teleport + setView(yaw,pitch) yaw 0=北(-z)
async function shot(name, x, z, yaw, pitch, wait = 400) {
  await page.evaluate(([x, z, yaw, pitch]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(yaw, pitch);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name);
}

// 1) 排队口看迷宫+闸机+阶梯 (blender 5.5,26 -> app 5.5,-26; 面北 yaw0)
await shot("01_queue_mouth", 5.5, -26, 0, -0.05);
// 2) 站台面看列车停泊 (上台阶后: 台面 z -55; 面北看列车) — teleport 到 deck x9.4 z-55
await shot("02_platform_train", 9.4, -55, Math.PI, -0.1); // 面南看闸机与来车
// 3) 33m 站名 (blender 11.5,34 -> app 11.5,-34 面北)
await shot("03_sign_33m", 11.5, -34, 0, 0.12);
// 4) 100m 南侧远景 (blender 11.5,137 -> app 11.5,-137 面北抬头)
await shot("04_silhouette_100m", 11.5, -137, 0, 0.25);
// 5) 回环骨爪地面视角 (blender 62,88 -> app 62,-88 看向环心 80.6,-101: yaw=atan2(dx? ) )
await shot("05_loop_claws", 60, -85, -0.42, 0.35);
// 6) 南瓜田+螺丝钻 (blender 72,13 -> app 72,-13 看北)
await shot("06_pumpkin_field", 72, -13, -1.2, 0.15);
// 7) 观景塔楼梯 (blender 88,101 -> app 88,-101 看西)
await shot("07_tower_stairs", 88.5, -101, Math.PI / 2, 0.0);

// 8) 列车运行: seek 到提升段中段 + 等车到回环
report.run = await page.evaluate(async () => {
  const c = window.__game.coaster;
  const t0 = c.state.s;
  c.seek(60); // 提升段
  await new Promise((r) => setTimeout(r, 3500));
  return { s: +c.state.s.toFixed(1), v: +c.state.v.toFixed(2), phase: c.state.phase, dS: +(c.state.s - 60).toFixed(1) };
});
await shot("08_train_lift", 30, -95, -1.0, 0.3, 100);
await page.evaluate(() => window.__game.coaster.seek(175)); // 回环中
await page.waitForTimeout(600);
await shot("09_train_loop", 60, -85, -0.42, 0.35, 100);

// 9) 驻留回归: seek 到缝合点前, 应进 dwell
report.dwell = await page.evaluate(async () => {
  const c = window.__game.coaster;
  c.seek(c.state.L ? c.state.L - 2 : 500);
  await new Promise((r) => setTimeout(r, 1500));
  return { phase: c.state.phase, laps: c.state.laps };
});

// 10) FPS / draw call 采样: 广场 + 站台 + 回环下
report.perf = await page.evaluate(async () => {
  const { renderer, player } = window.__game;
  const spots = [["plaza", 0, 20], ["station", 9.4, -55], ["loop", 65, -95]];
  const out = {};
  for (const [name, x, z] of spots) {
    player.teleport(x, z);
    player.setView(0, -0.05);
    await new Promise((r) => setTimeout(r, 500));
    // 手动统计 60 帧
    let frames = 0;
    const t0 = performance.now();
    renderer.info.autoReset = false;
    renderer.info.reset();
    await new Promise((r) => setTimeout(r, 1000));
    frames = renderer.info.render.frame; // 一秒内帧计数
    out[name] = { fps: frames, drawCalls: renderer.info.render.calls, tris: renderer.info.render.triangles };
    renderer.info.autoReset = true;
  }
  return out;
});

report.consoleErrors = errors.slice(0, 6);
console.log(JSON.stringify(report, null, 1));
await browser.close();
