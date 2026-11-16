// 游戏内截图验证：多状态采集
// 用法: node scripts/screenshot.mjs [输出目录] [模式]
//   模式 "states" — UI 六态采集（默认，输出到 .impeccable/review/）
//   模式 "spin"   — 旧版：两帧验证轮体旋转
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? ".impeccable/review";
const mode = process.argv[3] ?? "states";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });

const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

// 延迟 glb 响应，让「加载中」态可被取证（真实加载过快）
// 注意：必须在 goto 前注册——module 脚本在 DOMContentLoaded 前就会发起请求
await page.route("**/ferris_wheel.glb", async (route) => {
  await new Promise((r) => setTimeout(r, 2500));
  await route.continue();
});

await page.goto("http://127.0.0.1:8765", { waitUntil: "domcontentloaded" });

if (mode === "spin") {
  await page.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 60000 });
  await page.click("#enter-btn");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${outDir}/02_scene_a.png` });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: `${outDir}/03_scene_b.png` });
} else {
  // —— UI 六态 ——
  // 1. 加载中（平滑进度进行时）
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}/state-loading.png` });

  // 2. 就绪（五芒星点亮）
  await page.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 60000 });
  await page.waitForTimeout(900); // 等进度内插到 100%
  await page.screenshot({ path: `${outDir}/desktop.png` });

  // 3. 入园后（键位条高亮期）
  await page.click("#enter-btn");
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${outDir}/state-entered.png` });

  // 4-6. 驱动 HUD 各组件状态
  await page.evaluate(() => window.__hud.showPrompt("乘坐摩天轮"));
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/state-prompt.png` });

  await page.evaluate(() => {
    window.__hud.hidePrompt();
    window.__hud.setStars(3, 5);
    window.__hud.showPlaque("幽眠摩天轮", "高空观光 · E 随时下乘");
  });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/state-stars-plaque.png` });
}

console.log("console-errors:", errors.length ? JSON.stringify(errors, null, 2) : "none");
await browser.close();
