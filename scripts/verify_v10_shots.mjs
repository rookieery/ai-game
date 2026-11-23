// v10 紧凑化取证: 环->钻区间收紧 + 刹车段缩短 + 滚保留 (只读, 不改游戏状态)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = ".impeccable/v10";
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

// 1) 同步数据断言
const data = await page.evaluate(async () => {
  const j = await (await fetch("assets/models/roller_coaster_centerline.json")).json();
  const S = j.samples;
  const zog = S.filter((p) => p.zone === "zerog").map((p) => p.p[2]);
  const swp = S.filter((p) => p.zone === "sweep");
  const brk = S.filter((p) => p.zone === "brake");
  return {
    zerog_min: Math.min(...zog).toFixed(2),            // 滚直段高度 (保持 ~2.63)
    sweep_planar: Math.round(swp.length * 0.5),        // 连接直段采样数*0.5m
    brake_samples: Math.round(brk.length * 0.5),       // 刹车段长度
    length: j.length,
    vmax: j.vmax_ms,
  };
});
console.log("centerline(v10):", JSON.stringify(data));

// 2) 东南视角: 环->俯降->滚->爬升->双钻 全链 (对应你截图下方红框)
await page.evaluate(() => {
  window.__game.player.teleport(55, 5);
  window.__game.player.setView(-0.28, 0.15);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v10_span.png` });

// 3) 贴地滚近景 (保留的小凸起)
await page.evaluate(() => {
  window.__game.player.teleport(68, -55);
  window.__game.player.setView(-1.37, 0.05);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v10_roll.png` });

// 4) 刹车直线 (对应你截图上方红框: 站台左侧长直线)
await page.evaluate(() => {
  window.__game.player.teleport(2, -20);
  window.__game.player.setView(-1.57, -0.05);
});
await page.waitForTimeout(900);
await page.screenshot({ path: `${outDir}/v10_brake.png` });

console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
console.log("written: .impeccable/v10/*.png");
