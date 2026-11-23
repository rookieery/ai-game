// v11 三层折叠螺旋取证: 尾部重构 + 刹车相切 (只读)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = ".impeccable/v11";
mkdirSync(outDir, { recursive: true });
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";

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

const data = await page.evaluate(async () => {
  const j = await (await fetch("assets/models/roller_coaster_centerline.json")).json();
  const S = j.samples;
  const hx = S.filter((p) => p.zone === "helix");
  const brk = S.filter((p) => p.zone === "brake");
  return {
    helix_samples: hx.length,
    helix_zmin: Math.min(...hx.map((p) => p.p[2])).toFixed(2),
    helix_zmax: Math.max(...hx.map((p) => p.p[2])).toFixed(2),
    brake_len: Math.round(brk.length * 0.5),
    length: j.length,
  };
});
console.log("centerline(v11):", JSON.stringify(data));

// 1) 尾部全景: 短陡坡+平弧+三层螺旋 (对应你红框)
await page.evaluate(() => {
  window.__game.player.teleport(55, 25);
  window.__game.player.setView(0.34, 0.1);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v11_tail.png` });

// 2) 三层螺旋近景 (东南侧看折叠圈)
await page.evaluate(() => {
  window.__game.player.teleport(40, -30);
  window.__game.player.setView(2.67, 0.25);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v11_helix.png` });

// 3) 相切点: 螺旋出口->刹车线->站台
await page.evaluate(() => {
  window.__game.player.teleport(25, -25);
  window.__game.player.setView(0.63, -0.05);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v11_tangent.png` });

console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
console.log("written: .impeccable/v11/*.png");
