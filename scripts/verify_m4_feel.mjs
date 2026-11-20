// M4-B5 体感设置取证: feel=0 → FOV 恒 60; feel=100 → FOV>72 + 相机震动; 持久化; 设置面板渲染
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
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

const R = {};
const ok = (name, cond, got) => { R[name] = cond ? "PASS" : `FAIL ${JSON.stringify(got)}`; };

// 登上列车 (直调 board + enterRide, 与 B4 E2E 等价的快速路径)
await page.evaluate(() => {
  const c = window.__game.coaster;
  c.board();
  window.__game.player.enterRide((dt) => c.getRideFrame("pov", dt));
});

// ① feel=0: 高速段 FOV 应恒 60 且无震动
await page.evaluate(() => { window.__settings.store.set("coasterFeel", 0); window.__game.coaster.seek(120); });
await page.waitForTimeout(800);
const f0 = await page.evaluate(() => +window.__game.camera.fov.toFixed(2));
ok("feel0_fov_60", Math.abs(f0 - 60) < 0.05, f0);

// ② feel=100: FOV > 72 (v≈20 @120 段), 帧间位置抖动 > 0
await page.evaluate(() => window.__settings.store.set("coasterFeel", 100));
await page.waitForTimeout(800);
const f100 = await page.evaluate(() => +window.__game.camera.fov.toFixed(2));
const shake = await page.evaluate(() => new Promise((resolve) => {
  const cam = window.__game.camera;
  const p1 = cam.position.clone();
  setTimeout(() => resolve(+p1.distanceTo(cam.position).toFixed(4)), 100);
}));
ok("feel100_fov_up", f100 > 72, f100);
ok("feel100_shake", shake > 0.001, shake);

// ③ 持久化: reload 后 values 恢复 100
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);
const persisted = await page.evaluate(() => window.__settings.store.get("coasterFeel"));
ok("persisted", persisted === 100, persisted);

// ④ 设置面板渲染过山车分组
await page.keyboard.press("KeyO");
await page.waitForTimeout(500);
const panel = await page.evaluate(() => {
  const txt = document.body.innerText;
  return { hasGroup: txt.includes("过山车"), hasItem: txt.includes("乘坐体感强度") };
});
ok("panel_render", panel.hasGroup && panel.hasItem, panel);
await page.evaluate(() => window.__settings.store.set("coasterFeel", 60)); // 收尾还原默认
await page.screenshot({ path: `${OUT}/m4_settings_panel.png` });

console.log(JSON.stringify(R, null, 1));
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
const pass = Object.values(R).every((v) => v === "PASS") && errors.length === 0;
process.exit(pass ? 0 : 1);
