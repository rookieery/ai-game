// 原型抓拍: 指定花型 -> 爆裂尖峰后 0.3/0.9/1.8s 各截一帧
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
const outDir = "shots/proto";
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on("pageerror", (e) => console.log("PAGEERROR:", String(e)));
await page.goto("http://127.0.0.1:8768/prototype/fw_burst/", { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await page.evaluate(() => window.__fw.auto(false));

const TYPES = [
  ["peony", "#FFD9A0"],
  ["willow", "#FFD9A0"],
  ["crossette", "#8CFF4A"],
  ["peony", "#9B5BFF"],
];
for (const [type, color] of TYPES) {
  for (let i = 0; i < 40; i++) { await page.waitForTimeout(250); const a = await page.evaluate(() => window.__fw.alive()); if (a < 60) break; }
  await page.evaluate(([t, c]) => window.__fw.fire(t, c), [type, color]);
  let burst = false;
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(150);
    const alive = await page.evaluate(() => window.__fw.alive());
    if (alive > 250) { burst = true; break; }
  }
  if (!burst) { console.log(`${type}/${color}: NO BURST`); continue; }
  await page.screenshot({ path: `${outDir}/proto_${type}_${color.slice(1)}_t03.png` });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${outDir}/proto_${type}_${color.slice(1)}_t09.png` });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${outDir}/proto_${type}_${color.slice(1)}_t18.png` });
  console.log(`${type}/${color}: captured, alive=${await page.evaluate(() => window.__fw.alive())}`);
}
await browser.close();
console.log("PROTO_DONE");
