// 跳跃/台阶/站台联动回归验证
// 前置: npm run dev 已在 http://127.0.0.1:8765
// 断言:
//   跳上长椅(0.665)/木桶(0.955)/旋转木马平台(0.555), 走出台缘下落归零
//   8 级登舱台阶逐级走上 1.55 站台; 站台占用轮体缓停吸附(theta 不再变化)
//   站台 E 登舱 -> E 下乘后回到地面登舱点 (y=0, z=16.4)
// 截图: 长椅/木桶/旋转木马/站台/舱内
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/jump";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

const pos = () => page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(3), y: +p.y.toFixed(3), z: +p.z.toFixed(3) };
});
const theta = () => page.evaluate(() => +window.__game.ferris.state.theta.toFixed(5));

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

const fails = [];
const expect = async (name, cond, detail = "") => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"} : ${name}${detail ? "  " + detail : ""}`);
};
// 面向 +Z 起跳并前推: 空中越过平台侧壁(低空被挡) 后落上顶面
const jumpOnto = async (tpx, tpz, holdMs) => {
  await page.evaluate(([x, z]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(Math.PI, 0);
  }, [tpx, tpz]);
  await page.waitForTimeout(300);
  await page.keyboard.press("Space");
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(holdMs);
  await page.keyboard.up("KeyW");
  await page.waitForTimeout(1400);
  return pos();
};

// T1 跳上长椅 (5.6,31 顶 0.665) —— 前推时长须在落顶前收键, 防止走过窄顶面
let p = await jumpOnto(5.6, 29.5, 480);
await expect("跳上长椅 y≈0.665", Math.abs(p.y - 0.665) < 0.02, JSON.stringify(p));
await page.screenshot({ path: `${outDir}/j1_bench.png` });

// T2 走出台缘 -> 下落归零
await page.keyboard.down("KeyS");
await page.waitForTimeout(400);
await page.keyboard.up("KeyS");
await page.waitForTimeout(1000);
p = await pos();
await expect("长椅走缘下落 y=0", p.y === 0, JSON.stringify(p));

// T3 跳上木桶 (-23,26.9 顶 0.955, 顶面仅 1.3m 宽)
p = await jumpOnto(-23.0, 25.8, 450);
await expect("跳上木桶 y≈0.955", Math.abs(p.y - 0.955) < 0.02, JSON.stringify(p));
await page.screenshot({ path: `${outDir}/j2_barrel.png` });

// T4 跳上旋转木马平台 (45,-18 r4.5 顶 0.555), 再走东缘下落
p = await jumpOnto(45.0, -23.5, 450);
await expect("跳上旋转木马平台 y≈0.555", Math.abs(p.y - 0.555) < 0.02, JSON.stringify(p));
await page.screenshot({ path: `${outDir}/j3_carousel.png` });
await page.keyboard.down("KeyS");
await page.waitForTimeout(700);
await page.keyboard.up("KeyS");
await page.waitForTimeout(1000);
p = await pos();
await expect("平台走缘下落 y=0", p.y === 0, JSON.stringify(p));

// T5 8 级台阶走上 1.55 站台 (南向走廊 z17.5 -> 直行 -Z)
await page.evaluate(() => {
  window.__game.player.teleport(0, 17.5);
  window.__game.player.setView(0, 0);
});
await page.waitForTimeout(300);
await page.keyboard.down("KeyW");
await page.waitForTimeout(2600);
await page.keyboard.up("KeyW");
await page.waitForTimeout(2200); // 等轮体缓停吸附收敛
p = await pos();
await expect("走完 8 级台阶上站台 y≈1.55", Math.abs(p.y - 1.55) < 0.02, JSON.stringify(p));
const t1 = await theta();
await page.waitForTimeout(500);
const t2 = await theta();
await expect("站台占用 -> 轮体停驻 (theta 不变)", Math.abs(t1 - t2) < 1e-4, `θ=${t1}→${t2}`);
await page.screenshot({ path: `${outDir}/j4_platform.png` });

// T6 站台停靠舱旁 E 登舱
await page.keyboard.down("KeyW");
await page.waitForTimeout(1300);
await page.keyboard.up("KeyW");
await page.waitForTimeout(300);
await page.keyboard.press("KeyE");
await page.waitForTimeout(1800);
const riding = await page.evaluate(() => ({
  state: window.__game.state,
  local: window.__game.player.cabinLocal(),
}));
await expect("站台 E 登舱成功", riding.state === "riding" && riding.local !== null, JSON.stringify(riding));
await page.screenshot({ path: `${outDir}/j5_cabin.png` });

// T7 E 下乘 -> 回地面登舱点
await page.keyboard.press("KeyE");
await page.waitForTimeout(1600);
p = await pos();
const st = await page.evaluate(() => window.__game.state);
await expect("下乘回到地面登舱点 (y=0, z≈16.4)", st === "walk" && p.y === 0 && Math.abs(p.z - 16.4) < 0.05, `state=${st} ${JSON.stringify(p)}`);

console.log("result:", fails.length ? `FAILED x${fails.length}: ${fails.join("; ")}` : "all passed");
console.log("console-errors:", errors.length ? JSON.stringify(errors) : "none");
await browser.close();
if (fails.length) process.exitCode = 1;
