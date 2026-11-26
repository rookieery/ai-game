// 雾潭回归验证：地面机位 / 灯染 / 滑杆三档 / 25s 稳态
// 用法: node scripts/verify_mist.mjs [输出目录]（默认 .impeccable/review/mist）
// 需要 npm run dev 运行中；GAME_URL 可覆盖端口（默认 8765）
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const OUT = process.argv[2] ?? ".impeccable/review/mist";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

const shot = async (name) => {
  await page.screenshot({ path: `${OUT}/${name}.png` });
};

// 机位1：入口径东侧雾潭（12.5,58），站北侧向南看
await page.evaluate(() => window.__game.player.teleport(12.5, 70));
await page.waitForTimeout(1200);
await shot("m1_entrance_east");

// 机位2：墓园新址雾潭（37,58；2026-11-26 南迁，椭圆 36x24）——验证守墓灯暖染，站南向北看
await page.evaluate(() => window.__game.player.teleport(36, 76));
await page.waitForTimeout(1200);
await shot("m2_grave_tint");

// draw calls
const info = await page.evaluate(() => {
  const r = window.__game.renderer;
  return { calls: r.info.render.calls, tris: r.info.render.triangles };
});
console.log("render:", JSON.stringify(info));

// 滑杆三档：mistDensity 0 / 100 / 200
for (const v of [0, 100, 200]) {
  await page.evaluate((vv) => window.__settings.store.set("mistDensity", vv), v);
  await page.waitForTimeout(600);
  await shot(`m3_mist_${v}`);
}
await page.evaluate(() => window.__settings.store.set("mistDensity", 100));
await page.waitForTimeout(400);

// 长跑稳定性快照：25s 后同机位（回绕生效则潭形不变）
await page.evaluate(() => window.__game.player.teleport(12.5, 70));
await page.waitForTimeout(25000);
await shot("m4_stability_25s");

console.log("errors:", errors.length ? errors : "none");
await browser.close();
