// v12 行进漂移螺旋取证: 爬坡+行进螺旋+相切刹车 (只读)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = ".impeccable/v12";
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
  const sp = S.filter((p) => p.zone === "helix" && p.t[2] < -0.02);
  return {
    spiral_len: Math.round(sp.length * 0.5),
    zmax: Math.max(...sp.map((p) => p.p[2])).toFixed(1),
    zmin: Math.min(...sp.map((p) => p.p[2])).toFixed(1),
    length: j.length,
  };
});
console.log("centerline(v12):", JSON.stringify(data));

// 1) 尾部全景 (对应你红框视角)
await page.evaluate(() => {
  window.__game.player.teleport(55, 25);
  window.__game.player.setView(0.34, 0.1);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v12_tail.png` });

// 2) 行进螺旋近景: 从东南看错位圈组
await page.evaluate(() => {
  window.__game.player.teleport(48, -28);
  window.__game.player.setView(2.9, 0.22);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v12_spiral.png` });

// 3) 相切出口->刹车->站台
await page.evaluate(() => {
  window.__game.player.teleport(25, -25);
  window.__game.player.setView(0.63, -0.02);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v12_tangent.png` });

console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
console.log("written: .impeccable/v12/*.png");
