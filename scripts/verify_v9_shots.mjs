// v9 定线改版取证: 俯冲连续弧线 + 贴地段短柱 + 同步数据断言 (只读, 不改游戏状态)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = ".impeccable/v9";
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

// 1) 同步数据断言: 游戏加载的 centerline 就是 v9 (贴地段 z=2.63, 谷底 5.1)
const data = await page.evaluate(async () => {
  const j = await (await fetch("assets/models/roller_coaster_centerline.json")).json();
  const S = j.samples;
  const zog = S.filter((p) => p.zone === "zerog").map((p) => p.p[2]);
  const drp = S.filter((p) => p.zone === "drop");
  return {
    zerog_min: Math.min(...zog).toFixed(3),
    zerog_max: Math.max(...zog).toFixed(3),
    valley_end: drp[drp.length - 1].p[2].toFixed(2),
    drop_straight_80: drp.filter((p) => Math.abs(p.t[2]) > 0.98).length * 0.5, // pitch≈-80° 采样数
    length: j.length,
    vmax: j.vmax_ms,
  };
});
console.log("centerline(v9):", JSON.stringify(data));

// 2) 俯冲全景: 站在东南高位看 提升顶->连续俯冲->谷底->环
await page.evaluate(() => {
  window.__game.player.teleport(50, -95);
  window.__game.player.setView(0.58, 0.38);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v9_dive.png` });

// 3) 贴地段短柱: 看零重力滚直段 (轨面 2.63) 下的立柱
await page.evaluate(() => {
  window.__game.player.teleport(63, -50);
  window.__game.player.setView(-1.12, -0.08);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v9_lowrun.png` });

// 4) 谷底近景: 俯冲拉平->uturn->环入口 全在贴地高度
await page.evaluate(() => {
  window.__game.player.teleport(28, -105);
  window.__game.player.setView(-0.36, 0.12);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v9_valley.png` });

console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
console.log("written: .impeccable/v9/{v9_dive,v9_lowrun,v9_valley}.png");
