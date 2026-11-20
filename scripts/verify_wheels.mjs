// 轮心枢轴修复验证: ①数值断言(转角变化不移动轮心) ②真跑6s提升段近摄 ③回环顶任意冻结相位
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
const OUT = ".impeccable/review-coaster";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto("http://127.0.0.1:8765", { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

// ① 数值断言: 站台冻结, 轮 geometry bbox 中心的世界坐标在 rotation.x=0 与 1.2345 下应重合
const pivot = await page.evaluate(() => {
  const c = window.__game.coaster;
  c.state.s = 17.4; c.state.phase = "dwell"; c.state.dwellT = 999; c.update(0.016);
  const wheels = [];
  c.trainRoot.traverse((o) => { if (o.name && o.name.startsWith("NL_Wheel_")) wheels.push(o); });
  const centerAt = (theta) => {
    wheels.forEach((w) => { w.rotation.x = theta; });
    c.trainRoot.updateMatrixWorld(true);
    return wheels.map((w) => {
      w.updateWorldMatrix(true, false);
      if (!w.geometry.boundingBox) w.geometry.computeBoundingBox();
      const b = w.geometry.boundingBox;
      const cx = (b.min.x + b.max.x) / 2, cy = (b.min.y + b.max.y) / 2, cz = (b.min.z + b.max.z) / 2;
      const e = w.matrixWorld.elements;
      return [e[0]*cx + e[4]*cy + e[8]*cz + e[12], e[1]*cx + e[5]*cy + e[9]*cz + e[13], e[2]*cx + e[6]*cy + e[10]*cz + e[14]];
    });
  };
  const a = centerAt(0), b = centerAt(1.2345);
  let maxDrift = 0;
  a.forEach((p, i) => {
    const d = Math.hypot(p[0]-b[i][0], p[1]-b[i][1], p[2]-b[i][2]);
    if (d > maxDrift) maxDrift = d;
  });
  return { wheels: wheels.length, maxDrift: +maxDrift.toFixed(3) };
});
console.log("PIVOT_CHECK", JSON.stringify(pivot), "(maxDrift 应≈0, 修复前≈2.1)");

// ② 真跑 6 秒: seek 到提升段起步, 实时运行后冻结
await page.evaluate(() => { window.__game.coaster.seek(100); });
await page.waitForTimeout(6000);
await page.evaluate(() => {
  const c = window.__game.coaster;
  c.state.phase = "dwell"; c.state.dwellT = 999;
  window.__game.player.teleport(50, -108);
  window.__game.player.setView(-0.45, 0.75);
});
await page.waitForTimeout(350);
await page.screenshot({ path: `${OUT}/w1_run_lift.png` });
console.log("shot w1_run_lift");

// ③ 回环顶 + 全轮任意冻结相位 5.7rad: 倒挂姿态下轮组应贴轨不散落
await page.evaluate(() => {
  const c = window.__game.coaster;
  c.state.s = 176; c.state.phase = "dwell"; c.state.dwellT = 999; c.update(0.016);
  c.trainRoot.traverse((o) => { if (o.name && o.name.startsWith("NL_Wheel_")) o.rotation.x = 5.7; });
  c.trainRoot.updateMatrixWorld(true);
  window.__game.player.teleport(90.7, -101.8);
  window.__game.player.setView(1.57, 1.10);
});
await page.waitForTimeout(350);
await page.screenshot({ path: `${OUT}/w2_loop_frozen.png` });
console.log("shot w2_loop_frozen");
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
