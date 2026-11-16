// 舱内天花穿模回归验证（v2.2 抬高舱顶）
// 前置: npm run dev 已在 http://127.0.0.1:8765
// 断言: 站姿眼位(舱本地竖直分量)必须 <= -0.82 (= 发光天花底 -0.72 − 相机 near 0.1)
// 截图: 站姿抬头三个朝向 + 坐姿对照 + 下乘后外观
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
    eyeY: +local.y.toFixed(3),           // 舱本地竖直分量（天花板底 -0.72, near 0.1 -> 界 -0.82）
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

// 登舱
await page.evaluate(() => window.__game.player.teleport(0, 18.8));
await page.waitForTimeout(400);
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
await expect("站姿眼位 <= -0.82 (天花底 -0.72 − near 0.1)", e && e.eyeY <= -0.82, `eyeY=${e?.eyeY}`);

// 站姿抬头: 三个朝向（+x 大窗 / 角落 / 长椅端墙）
for (const [tag, yaw] of [["window", -Math.PI / 2], ["corner", Math.PI / 4], ["bench", 0]]) {
  await page.evaluate((y) => window.__game.player.setView(y, 1.25), yaw);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}/s1_stand_up_${tag}.png` });
  e = await eyeInfo();
  await expect(`站姿抬头(${tag})眼位仍 <= -0.82`, e && e.eyeY <= -0.82, `eyeY=${e?.eyeY}`);
}

// 中柱-天花收口（v2.2b 柱贯通验证）: 正面近观 + 窗侧斜视
await page.evaluate(() => window.__game.player.setView(0, 0.55)); // 面向中柱微仰视
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s1b_pole_front.png` });
await page.evaluate(() => {
  window.__game.player.setView(-Math.PI / 2, -0.2); // 先面向 +x 走到窗边
});
await page.keyboard.down("KeyW");
await page.waitForTimeout(900);
await page.keyboard.up("KeyW");
await page.evaluate(() => window.__game.player.setView(Math.PI / 2 + 0.5, 0.45)); // 斜回中柱仰视
await page.waitForTimeout(400);
await page.screenshot({ path: `${outDir}/s1c_pole_diagonal.png` });

// 坐姿对照
await page.keyboard.press("KeyC");
await page.waitForTimeout(1200);
e = await eyeInfo();
await expect("坐姿生效", e && e.seated === true, JSON.stringify(e));
await expect("坐姿眼位 ≈ -1.16", e && Math.abs(e.eyeY - -1.16) < 0.05, `eyeY=${e?.eyeY}`);
for (const [tag, yaw] of [["window", -Math.PI / 2], ["bench", 0]]) {
  await page.evaluate((y) => window.__game.player.setView(y, 1.25), yaw);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}/s2_sit_up_${tag}.png` });
}

// 下乘 -> 外观复查（站台近观 + 全轮远景，确认舱顶抬高无悬空件）
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
