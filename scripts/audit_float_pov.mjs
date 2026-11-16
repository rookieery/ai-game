// 悬空建筑排查取证：定点传送 + 截图
// 用法: node scripts/audit_float_pov.mjs [输出目录]  (GAME_URL 覆盖端口)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/float_audit";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

// 视点定义: app 坐标 (摩天轮在原点, 站台 r9 顶 1.55, 台阶 z 9→16.2,
// 售票亭 (7.6, 8.2), 矮柱灯 r10.4, 排队围栏 x±1.5 z10.2-14, 登舱点 z16.4)
// look: 由 pos->target 反解 yaw (yaw=0 面 -Z), pitch 手工下调看地面
const POVS = [
  { name: "01_steps_front", pos: [0, 26], target: [0, 10], pitch: -0.12 },
  { name: "02_booth_close", pos: [13, 16], target: [7.6, 8.2], pitch: -0.18 },
  { name: "03_bollard_east", pos: [19, 7], target: [10.4, 0.5], pitch: -0.12 },
  { name: "04_overview_south", pos: [0, 48], target: [0, 5], pitch: -0.06 },
  { name: "05_north_side", pos: [0, -26], target: [0, -5], pitch: -0.08 },
  { name: "06_queue_rail", pos: [-6, 22], target: [-1.5, 12], pitch: -0.15 },
  { name: "07_sw_quarter", pos: [-16, 16], target: [-4, 4], pitch: -0.1 },
  { name: "08_se_quarter", pos: [16, 16], target: [4, 4], pitch: -0.1 },
];

const yawFor = (px, pz, tx, tz) => Math.atan2(-(tx - px), -(tz - pz));

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

for (const p of POVS) {
  await page.evaluate(([x, z, tx, tz, pitch]) => {
    const g = window.__game;
    g.player.teleport(x, z);
    const yaw = Math.atan2(-(tx - x), -(tz - z));
    g.player.setView(yaw, pitch);
  }, [p.pos[0], p.pos[1], p.target[0], p.target[1], p.pitch]);
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${outDir}/${p.name}.png` });
  console.log("shot", p.name);
}

// 额外: 汇总场景里 minY>0.3 且在地面活动区的 mesh(运行时确认)
const floats = await page.evaluate(() => {
  const root = window.__game.scene;
  const out = [];
  root.traverse((o) => {
    if (!o.isMesh || !o.geometry?.boundingBox) return;
    o.geometry.computeBoundingBox();
    o.updateWorldMatrix(true, false);
    const b = o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld);
    if (b.min.y > 0.3 && b.max.y < 8 && Math.hypot(o.getWorldPosition(new (o.position.constructor)()).x || 0, 0) < 90) {
      // 只统计世界包围盒整体离地的(排除轮体高空件与灯串)
      const size = b.getSize(new (b.min.constructor)());
      if (b.min.y < 2.8 && size.y < 3) {
        out.push({ name: o.name, minY: +b.min.y.toFixed(2), maxY: +b.max.y.toFixed(2),
                   x: +(((b.min.x + b.max.x) / 2)).toFixed(1), z: +(((b.min.z + b.max.z) / 2)).toFixed(1) });
      }
    }
  });
  return out;
});
console.log("低空悬浮 mesh(0.3<minY<2.8):", JSON.stringify(floats, null, 0));

if (errors.length) console.log("PAGE_ERRORS:", errors.join("\n"));
await browser.close();
