// M3 入口立牌实机取证: 玩家沿支路北行的真实接近视角
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
await page.waitForTimeout(1200);

async function shot(name, x, z, yaw, pitch, wait = 400) {
  await page.evaluate(([x, z, yaw, pitch]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(yaw, pitch);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name);
}

// 支路接近视角: 玩家从广场沿 78° 支路向北走向排队口 (spoke 内端 (6.2,29.3))
await shot("12_entry_sign_20m", 6.2, -9, 0.35, 0.02);   // 20m 外沿支路望牌
await shot("13_entry_sign_8m", 6.2, -21, 0.30, 0.06);   // 8m 近距
await shot("14_platform_deck", 11.5, -52, Math.PI, -0.05); // 站台面上南望(登台视角)
console.log(JSON.stringify({ errors: errors.slice(0, 4) }));
await browser.close();
