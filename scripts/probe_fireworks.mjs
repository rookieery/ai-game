// 烟花系统 v2 探针: 三型发射器提示/近景 + 分型全弹道三连拍 (升空/爆裂/余烬) + 自动秀与终曲采样 + 性能抽样
// 用法: GAME_URL=http://127.0.0.1:8768 node scripts/probe_fireworks.mjs [输出目录]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/fw2";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on("pageerror", (e) => console.log("PAGEERROR:", String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

// 关自动秀, 分型取证不受污染
await page.evaluate(() => window.__settings.store.set("fireworkPeriod", 0));

const sample = () => page.evaluate(() => {
  let alive = 0;
  let maxY = -9999;
  window.__game.scene.traverse((o) => {
    if (o.isPoints && o.geometry?.attributes?.aColor) {
      const c = o.geometry.attributes.aColor.array;
      const p = o.geometry.attributes.position.array;
      for (let i = 0; i < c.length; i += 3) {
        if (c[i] + c[i + 1] + c[i + 2] > 0.01) {
          alive++;
          if (p[i + 1] > maxY) maxY = p[i + 1];
        }
      }
    }
  });
  return { alive, maxY: +maxY.toFixed(1) };
});

const yawTo = (px, pz, tx, tz) => Math.atan2(-(tx - px), -(tz - pz));

// ---- 分型取证: 就近提示 + F 点射 + 全弹道三连拍 ----
// burst ≈ 炮位 + dir*11m; 远景机位保证 发射器+炸点 同框 (炸点仰角 ~50°, 太近会出画)
const CASES = [
  { tag: "A_peony_L1", L: [22, 22], near: [23.3, 23.3], nearPitch: 0.28,
    vantage: [48.2, -5.6], vx: 14.2, vz: 14.2, vpitch: 0.72, label: /牡丹发射架/ },
  { tag: "B_willow_L3", L: [43.5, 45], near: [43.4, 47.2], nearPitch: 0.42,
    vantage: [68.4, 5.7], vx: 36, vz: 37, vpitch: 0.6, label: /垂柳塔/ },
  { tag: "C_crossette_L5", L: [-30, 24], near: [-28.2, 24], nearPitch: 0.22,
    vantage: [6.7, 52.4], vx: -21.4, vz: 17.3, vpitch: 0.6, label: /椰芯连环炮/ },
];
for (const c of CASES) {
  await page.evaluate(([nx, nz, yaw, pitch]) => {
    window.__game.player.teleport(nx, nz);
    window.__game.player.setView(yaw, pitch);
  }, [c.near[0], c.near[1], yawTo(c.near[0], c.near[1], c.L[0], c.L[1]), c.nearPitch]);
  await page.waitForTimeout(600); // interact.update 置 nearLauncher
  const prompt = await page.evaluate(() =>
    document.querySelector(".spirit-prompt")?.innerText ?? "(无)");
  console.log(`prompt ${c.tag}:`, JSON.stringify(prompt));
  await page.screenshot({ path: `${outDir}/fw_${c.tag}_close.png` });
  await page.keyboard.press("KeyF");
  // 升空段: 原地仰望弹道
  await page.evaluate(([yaw, pitch]) => window.__game.player.setView(yaw, pitch),
    [yawTo(c.near[0], c.near[1], c.vx, c.vz), 0.9]);
  await page.waitForTimeout(1200);
  const sAscent = await sample();
  console.log(`ascent ${c.tag}:`, JSON.stringify(sAscent));
  await page.screenshot({ path: `${outDir}/fw_${c.tag}_ascent.png` });
  // 爆裂段: 移步远景; 截图由粒子尖峰触发 (Playwright 截图停帧会拖慢模拟时钟, 固定等待不可靠)
  await page.evaluate(([px, pz, yaw, pitch]) => {
    window.__game.player.teleport(px, pz);
    window.__game.player.setView(yaw, pitch);
  }, [c.vantage[0], c.vantage[1], yawTo(c.vantage[0], c.vantage[1], c.vx, c.vz), c.vpitch]);
  let sBurst = null;
  for (let i = 0; i < 36; i++) {
    await page.waitForTimeout(250);
    const s = await sample();
    if (s.alive > 60) { sBurst = s; break; }
  }
  if (!sBurst) sBurst = await sample();
  console.log(`burst ${c.tag}:`, JSON.stringify(sBurst));
  // 尖峰即连拍: 截图自身停帧 ~0.4s 恰好充当帧间隔, 第一张 = 爆裂亮态
  await page.screenshot({ path: `${outDir}/fw_${c.tag}_burst.png` });
  await page.screenshot({ path: `${outDir}/fw_${c.tag}_burst2.png` });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${outDir}/fw_${c.tag}_split.png` });   // 椰芯分裂窗口
  await page.waitForTimeout(1000);  // 余烬段
  const sEmber = await sample();
  console.log(`ember ${c.tag}:`, JSON.stringify(sEmber));
  await page.screenshot({ path: `${outDir}/fw_${c.tag}_ember.png` });
}

// ---- 自动秀 + 终曲 (每 4 场一次 6 站全开) ----
await page.evaluate(() => {
  window.__game.player.teleport(0, 40);
  window.__game.player.setView(0, 0.55);
  window.__settings.store.set("fireworkPeriod", 12);
});
let finaleShot = false;
let peak = { alive: 0, maxY: 0 };
for (let k = 0; k < 26; k++) {
  await page.waitForTimeout(2500);
  const s = await sample();
  if (s.alive > peak.alive) peak = s;
  if (s.alive > 900 && !finaleShot) {
    finaleShot = true;
    await page.screenshot({ path: `${outDir}/fw_finale.png` });
    console.log("finale candidate:", JSON.stringify(s));
  }
}
console.log("show peak:", JSON.stringify(peak), "finaleCaptured:", finaleShot);

await browser.close();
console.log("PROBE_DONE");
