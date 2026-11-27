// 设置面板端到端验证：开合/滑杆/亮度对比/持久化
// 用法: node scripts/verify_settings.mjs [输出目录]   (需 dev 服务器已在 8765 运行)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/settings";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });

const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto("http://127.0.0.1:8765", { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

// 1. O 键开面板（走真实键盘路径）
await page.keyboard.press("KeyO");
await page.waitForTimeout(700);
const lockState = await page.evaluate(() => !!document.pointerLockElement);
await page.screenshot({ path: `${outDir}/s1_drawer_open.png` });

// 2. UI 滑杆路径：舱内灯光拉到 200% 再回 40%（验证 set->apply 链路）
const setSlider = (label, v) => page.evaluate(([l, val]) => {
  const input = [...document.querySelectorAll(".set-slider")]
    .find((i) => i.getAttribute("aria-label") === l);
  input.value = String(val);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}, [label, v]);
await setSlider("舱内灯光亮度", 200);
await page.waitForTimeout(300);
await setSlider("舱内灯光亮度", 40);
await page.keyboard.press("KeyO"); // 关面板
await page.waitForTimeout(500);

// 3. 登舱看舱内默认 40% 亮度（本轮优化主角）
await page.evaluate(() => window.__game.player.teleport(0, 1.5, 1.55));
await page.waitForFunction(() => window.__game.ferris.isDocked(), { timeout: 15000 }); // 轮停稳、舱吸附到位才可登舱 (v3 第 2 批)
await page.waitForTimeout(200);
await page.keyboard.press("KeyE");
await page.waitForTimeout(1600);
await page.evaluate(() => {
  window.__game.ferris.state.theta = Math.PI;
  window.__game.player.setView(Math.PI, -0.1);
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/s2_cabin_default40.png` });

// 4. 100% 对比（旧观感，应明显过亮）—— store 直调路径，验证 applySettings 链路
await page.evaluate(() => window.__settings.store.set("cabinLight", 100));
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s3_cabin_100.png` });
await page.evaluate(() => window.__settings.store.set("cabinLight", 40));

// 5. 乘坐中开面板（键盘链路 + 抽屉叠加渲染）
await page.keyboard.press("KeyO");
await page.waitForTimeout(700);
await page.screenshot({ path: `${outDir}/s4_ride_drawer.png` });
await page.keyboard.press("KeyO");

// 6. 下客 -> 园区全景调暗试验（园区照明 20% + Bloom 关）
await page.keyboard.press("KeyE");
await page.waitForTimeout(1600);
await page.evaluate(() => window.__game.player.setView(-0.6, -0.06));
await page.evaluate(() => {
  const s = window.__settings.store;
  s.set("parkLampLight", 20);
  s.set("bloomStrength", 0);
});
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s5_park_dim.png` });

// 7. 恢复默认 + 持久化验证（写入 55 -> 重载 -> 应读到 55）
await page.evaluate(() => {
  window.__settings.store.reset();
  window.__settings.store.set("parkLampLight", 55);
});
await page.waitForTimeout(500); // 等 persistSoon 落盘
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForFunction(() => window.__settings !== undefined, { timeout: 60000 });
const persisted = await page.evaluate(() => ({
  parkLampLight: window.__settings.store.get("parkLampLight"),
  cabinLight: window.__settings.store.get("cabinLight"),
}));
console.log("persisted-after-reload:", JSON.stringify(persisted));

console.log("pointer-lock-during-open:", lockState);
console.log("console-errors:", errors.length ? JSON.stringify(errors, null, 2) : "none");
await browser.close();
