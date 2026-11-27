// 舱内天花净空回归验证
// 前置: npm run dev 已在 http://127.0.0.1:8765
// v3 (2026-11-27 舱体重做): 舱 2.10×1.70, 地板顶相对舱根 -2.70, 净高 2.00 (天花底 -0.70), 没有中柱;
//   站姿眼高 1.65 (= 园区眼高), 坐姿眼高 1.20
// 断言: 站姿眼位(舱本地竖直分量)必须 <= -0.80 (= 天花底 -0.70 − 相机 near 0.1); 实际 -1.05, 余量 0.25
// 截图: 站姿抬头三个朝向 + 两张近观 + 坐姿对照 + 下乘后外观
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/ceil_fix";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

// 舱本地眼高（竖直分量）+ 水平位置
const eyeInfo = () => page.evaluate(() => {
  const g = window.__game;
  const fr = g.ferris.getRideFrame();
  if (!fr) return null;
  const local = g.camera.position.clone().sub(fr.pos).applyQuaternion(fr.quat.clone().invert());
  const loc = g.player.cabinLocal();
  return {
    eyeY: +local.y.toFixed(3),           // 舱本地竖直分量（天花板底 -0.70, near 0.1 -> 界 -0.80）
    x: +local.x.toFixed(3),
    depth: +local.z.toFixed(3),
    seated: loc ? loc.seated : null,
  };
});

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

// 登舱 (v3 第 2 批: 地面登舱点取消 —— 站台闸内等轮停稳后 E)
await page.evaluate(() => window.__game.player.teleport(0, 1.5, 1.55));
await page.waitForFunction(() => window.__game.ferris.isDocked(), { timeout: 15000 }); // 轮停稳、舱吸附到位才可登舱 (v3 第 2 批)
await page.keyboard.press("KeyE");
await page.waitForTimeout(1800);

const fails = [];
const expect = async (name, cond, detail = "") => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"} : ${name}${detail ? "  " + detail : ""}`);
};

let e = await eyeInfo();
await expect("登舱为站姿", e && e.seated === false, JSON.stringify(e));
await expect("站姿眼位 <= -0.80 (天花底 -0.70 − near 0.1)", e && e.eyeY <= -0.80, `eyeY=${e?.eyeY}`);
await expect("站姿眼位 ≈ -1.05 (地板顶 -2.70 + 眼高 1.65)", e && Math.abs(e.eyeY - -1.05) < 0.05, `eyeY=${e?.eyeY}`);

// 站姿抬头: 三个朝向（+x 侧窗 / 角落 / 长椅端墙）
for (const [tag, yaw] of [["window", -Math.PI / 2], ["corner", Math.PI / 4], ["bench", 0]]) {
  await page.evaluate((y) => window.__game.player.setView(y, 1.25), yaw);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}/s1_stand_up_${tag}.png` });
  e = await eyeInfo();
  await expect(`站姿抬头(${tag})眼位仍 <= -0.80`, e && e.eyeY <= -0.80, `eyeY=${e?.eyeY}`);
}

// 近观两张（v3 没有中柱）: 面向登舱门微仰视看天花顶灯 + 走到侧窗边后斜回看舱内
await page.evaluate(() => window.__game.player.setView(Math.PI, 0.55)); // 面向门侧 (+z) 微仰视
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s1b_ceiling_door.png` });
await page.evaluate(() => {
  window.__game.player.setView(-Math.PI / 2, -0.2); // 先面向 +x 走到窗边
});
await page.keyboard.down("KeyW");
await page.waitForTimeout(900);
await page.keyboard.up("KeyW");
await page.evaluate(() => window.__game.player.setView(Math.PI / 2 + 0.5, 0.45)); // 斜回看舱内仰视
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s1c_ceiling_diagonal.png` });

// 坐姿对照
await page.keyboard.press("KeyC");
await page.waitForTimeout(1200);
e = await eyeInfo();
await expect("坐姿生效", e && e.seated === true, JSON.stringify(e));
await expect("坐姿眼位 ≈ -1.50", e && Math.abs(e.eyeY - -1.50) < 0.05, `eyeY=${e?.eyeY}`);
for (const [tag, yaw] of [["window", -Math.PI / 2], ["bench", 0]]) {
  await page.evaluate((y) => window.__game.player.setView(y, 1.25), yaw);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}/s2_sit_up_${tag}.png` });
}

// 下乘 -> 外观复查（站台近观 + 全轮远景，确认舱体在位、没有悬空件）
await page.keyboard.press("KeyE");
await page.waitForTimeout(1600);
await page.evaluate(() => window.__game.player.setView(-Math.PI / 2, 0.35));
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s3_exterior_platform.png` });
await page.evaluate(() => {
  window.__game.player.teleport(0, 70);
  window.__game.player.setView(0, 0.5);
});
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s4_wheel_overview.png` });

console.log("result:", fails.length ? `FAILED x${fails.length}: ${fails.join("; ")}` : "all passed");
console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
if (fails.length) process.exitCode = 1;
