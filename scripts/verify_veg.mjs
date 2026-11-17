// 植被 v3 验证：草/南瓜/树/花/蘑菇/干草堆 定点取证 + 风摆/南瓜灯设置联动 + FPS/drawcall 抽样
// 用法: node scripts/verify_veg.mjs [输出目录]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/veg";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

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

// 定点取证: (x, z=app 坐标, yaw, 俯仰, 标签)
const stops = [
  // app 坐标 (x, z=-blender_y); yaw 0 = 面向 -z
  [14.0, 91.6, -1.57, -0.22, "1_pumpkin_field"],   // 南瓜田主瓜特写 (blender (16.2,-91.6))
  [0.0, 30.0, 0.0, -0.15, "2_path_grass"],          // 主路南段: 草丛+路侧南瓜, 面北看广场
  [30.0, 41.0, 0.0, -0.12, "3_grave_tree"],         // 墓园: 枯树+彼岸花+墓碑 (blender (34,-41) 朝西)
  [3.5, 50.0, 3.14, -0.28, "4_flower_bed"],         // 主路花带 (blender (3.5,-50), 朝 +z 看花列)
  [26.0, 36.0, 2.2, -0.15, "5_haystack"],           // 干草堆 (blender (26,-36))
  [24.0, 43.0, -0.6, -0.3, "6_mushroom_ring"],      // 发光蘑菇圈 (blender (30,-38) 圈缘)
  [17.2, -8.4, 2.6, -0.05, "7_plaza_pine"],         // 广场外圈缠灯松 (blender (19.8,8.4))
  [60.0, -20.0, 4.2, -0.05, "8_willow"],            // 垂柳 (blender (60,20))
  [5.6, 32.0, 3.6, -0.45, "9_grass_close"],          // 路缘草丛贴脸 (灯照范围内)
  [1.3, 21.0, -1.57, -0.18, "10_pump_face_a"],       // 路侧南瓜特写 A (blender (2.9,-21))
  [4.5, 21.0, 1.57, -0.18, "11_pump_face_b"],        // 路侧南瓜特写 B (对面)
];
for (const [x, z, yaw, pitch, label] of stops) {
  await page.evaluate(([tx, tz, ty, tp]) => {
    window.__game.player.teleport(tx, tz);
    window.__game.player.setView(ty, tp);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/${label}.png` });
  console.log("shot", label);
}

// 风摆/南瓜灯设置联动: 调到 0 / 200 各采一帧 (画面亮度与位置微差)
const setVals = async (wind, glow) => {
  await page.evaluate(([w, g]) => {
    window.__settings.store.set("windStrength", w);
    window.__settings.store.set("pumpkinGlow", g);
  }, [wind, glow]);
  await page.waitForTimeout(300);
};
const dir = await page.evaluate(() => {
  const r = window.__game.renderer;
  return { has: !!r };
});
console.log("renderer ok:", JSON.stringify(dir));
await setVals(0, 20);
await page.evaluate(() => window.__game.player.teleport(16.2, 91.6));
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/9_pumpkin_glow_low.png` });
await setVals(200, 200);
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/10_pumpkin_glow_high.png` });
await setVals(100, 100);

// 性能抽样: 南瓜田 (草+瓜簇密集) / 主路 (花带+草) / 垂柳特写
function sampleFrame(label) {
  return page.evaluate((lb) => new Promise((resolve) => {
    const r = window.__game.renderer;
    r.info.autoReset = false;
    r.info.reset();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      resolve({ label: lb, calls: r.info.render.calls, tris: r.info.render.triangles });
      r.info.autoReset = true;
    }));
  }), label);
}
const fps = await page.evaluate(async () => {
  let n = 0;
  const t0 = performance.now();
  await new Promise((res) => {
    const cb = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(cb); else res(); };
    requestAnimationFrame(cb);
  });
  return +(n / 2).toFixed(1);
});
console.log("perf field:", JSON.stringify({ ...(await sampleFrame("field")), fps }));
await page.evaluate(() => window.__game.player.teleport(0, -30));
await page.waitForTimeout(700);
console.log("perf path:", JSON.stringify(await sampleFrame("path")));

console.log("console-errors:", errors.length ? JSON.stringify(errors, null, 2) : "none");
await browser.close();
