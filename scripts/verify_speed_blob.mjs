// 回归验证: 园区步速设置项 + 门口视角天穹黑斑修复 (far 800->2000)
// 用法: GAME_URL=http://127.0.0.1:8769 node scripts/verify_speed_blob.mjs
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = "shots/verify-speed-blob";
mkdirSync(outDir, { recursive: true });
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 800 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const fails = [];
const expect = (name, cond) => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"} : ${name}`);
};

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

// ---- 1. 黑斑修复: 门口站位仰视北天 (原 100% 复现视角) ----
await page.evaluate(() => {
  window.__game.player.teleport(15, 146);
  window.__game.player.setView((-6 * Math.PI) / 180, (20 * Math.PI) / 180);
});
await page.waitForTimeout(600);
await page.screenshot({ path: `${outDir}/1_gate_sky.png` });
const camFar = await page.evaluate(() => window.__game.camera.far);
expect(`camera.far = 2000 (实际 ${camFar})`, camFar === 2000);

// ---- 2. 默认步速 4 m/s: 直走 2s ≈ 8m ----
await page.evaluate(() => {
  window.__game.player.teleport(0, 60);
  window.__game.player.setView(0, -0.04);
});
await page.waitForTimeout(400);
const p0 = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: p.x, z: p.z };
});
await page.keyboard.down("KeyW");
await page.waitForTimeout(2000);
await page.keyboard.up("KeyW");
const p1 = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) };
});
const dDef = Math.hypot(p1.x - p0.x, p1.z - p0.z);
expect(`默认 4m/s 直走 2s 位移 ${dDef.toFixed(1)}m (期望 7~9)`, dDef > 7 && dDef < 9);

// ---- 3. 步速 16 m/s: 直走 2s ≈ 32m ----
await page.evaluate(() => {
  window.__settings.store.set("walkSpeed", 16);
  window.__game.player.teleport(0, 60);
  window.__game.player.setView(0, -0.04);
});
await page.waitForTimeout(400);
const q0 = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: p.x, z: p.z };
});
await page.keyboard.down("KeyW");
await page.waitForTimeout(2000);
await page.keyboard.up("KeyW");
const q1 = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) };
});
const dFast = Math.hypot(q1.x - q0.x, q1.z - q0.z);
expect(`16m/s 直走 2s 位移 ${dFast.toFixed(1)}m (期望 30~34)`, dFast > 30 && dFast < 34);
expect(`设置生效后值 = 16`, (await page.evaluate(() => window.__settings.store.get("walkSpeed"))) === 16);

// ---- 4. 面板滑杆可见性截图 (O 开抽屉) ----
await page.keyboard.press("KeyO");
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/2_settings_panel.png` });
await page.keyboard.press("KeyO");
await page.waitForTimeout(300);

// ---- 5. 持久化: 重载后恢复 16 ----
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
const restored = await page.evaluate(() => window.__settings.store.get("walkSpeed"));
expect(`重载后恢复 walkSpeed = 16 (实际 ${restored})`, restored === 16);

// ---- 6. 恢复默认 4, 不留测试残留 ----
await page.evaluate(() => window.__settings.store.set("walkSpeed", 4));
await page.waitForTimeout(400); // 持久化去抖 250ms
const finalV = await page.evaluate(() => window.__settings.store.get("walkSpeed"));
expect(`测试后恢复默认 walkSpeed = 4`, finalV === 4);

console.log(fails.length ? `RESULT: FAILED x${fails.length}` : "RESULT: all passed");
console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
if (fails.length) process.exitCode = 1;
