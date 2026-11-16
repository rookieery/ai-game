// 游戏内截图验证：多状态采集
// 用法: node scripts/screenshot.mjs [输出目录] [模式]
//   模式 "states" — UI 六态采集（默认，输出到 .impeccable/review/）
//   模式 "spin"   — 两帧验证轮体旋转
//   模式 "game"   — P3 游玩流程取证（走动/提示/乘坐/打卡）
//   模式 "cabin"  — 舱内走动取证 + 碰撞断言（长椅/中柱/外墙/坐站切换）
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? ".impeccable/review";
const mode = process.argv[3] ?? "states";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765"; // dev 端口被占时会顺延, 可用 GAME_URL 覆盖
mkdirSync(outDir, { recursive: true });

// 延迟 glb 响应，让「加载中」态可被取证（真实加载过快）
// 注意：必须在 goto 前注册——module 脚本在 DOMContentLoaded 前就会发起请求
const slowRoute = async (route) => {
  await new Promise((r) => setTimeout(r, 2500));
  await route.continue();
};

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });

const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

if (mode === "states") {
  await page.route("**/ferris_wheel.glb", slowRoute);
  await page.route("**/park_env.glb", slowRoute);
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });

  // 1. 加载中（平滑进度进行时）
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${outDir}/state-loading.png` });

  // 2. 就绪（五芒星点亮）
  await page.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 60000 });
  await page.waitForTimeout(900); // 等进度内插到 100%
  await page.screenshot({ path: `${outDir}/desktop.png` });

  // 3. 入园后（键位条高亮期）
  await page.click("#enter-btn");
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${outDir}/state-entered.png` });

  // 4-6. 驱动 HUD 各组件状态
  await page.evaluate(() => window.__hud.showPrompt("乘坐摩天轮"));
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/state-prompt.png` });

  await page.evaluate(() => {
    window.__hud.hidePrompt();
    window.__hud.setStars(3, 5);
    window.__hud.showPlaque("幽眠摩天轮", "高空观光 · E 随时下乘");
  });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/state-stars-plaque.png` });
} else if (mode === "spin") {
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 60000 });
  await page.click("#enter-btn");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${outDir}/02_scene_a.png` });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: `${outDir}/03_scene_b.png` });
} else if (mode === "game") {
  // —— P3 游玩流程取证 ——
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 60000 });
  await page.click("#enter-btn");
  await page.waitForTimeout(1200);

  // 1. 出生点面向园区（大门 -> 主路 -> 摩天轮）
  await page.evaluate(() => window.__game.player.teleport(0, 78));
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${outDir}/g1_spawn.png` });

  // 2. 真实按键走两秒（W 前进）验证移动+碰撞
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(2000);
  await page.keyboard.up("KeyW");
  const posAfterWalk = await page.evaluate(() => {
    const p = window.__game.player.pos;
    return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) };
  });
  console.log("walk-smoke pos:", JSON.stringify(posAfterWalk));
  await page.screenshot({ path: `${outDir}/g2_walked.png` });

  // 3. 传送到登舱点 -> 交互提示
  await page.evaluate(() => window.__game.player.teleport(0, 18.8));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${outDir}/g3_board_prompt.png` });

  // 4. E 登舱 -> 乘坐在最低点
  await page.keyboard.press("KeyE");
  await page.waitForTimeout(1600);
  await page.screenshot({ path: `${outDir}/g4_ride_boarding.png` });

  // 5. 拨轮半圈 -> 乘坐舱到正上方, 斜下俯瞰广场与大门
  await page.evaluate(() => {
    window.__game.ferris.state.theta = Math.PI;
    window.__game.player.setView(Math.PI, -0.42);
  });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/g5_ride_high.png` });

  // 6. E 下客 -> 回到站台, 顺路收集 3 颗星
  await page.keyboard.press("KeyE");
  await page.waitForTimeout(1600);
  await page.evaluate(() => window.__game.interact.debugCollect(3));
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${outDir}/g6_stars.png` });

  const state = await page.evaluate(() => window.__game.state);
  console.log("game-state:", state);
} else if (mode === "cabin") {
  // —— 舱内走动取证 + 碰撞断言 ——
  const fails = [];
  const expect = async (name, cond) => {
    const ok = !!cond;
    if (!ok) fails.push(name);
    console.log(`cabin-check ${ok ? "ok  " : "FAIL"} : ${name}`);
  };
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
  await page.screenshot({ path: `${outDir}/c1_board_stand.png` });
  let loc = await page.evaluate(() => window.__game.player.cabinLocal());
  await expect(`登舱后为站姿且落位在走道内 ${JSON.stringify(loc)}`,
    loc && !loc.seated && Math.abs(loc.x) <= 0.63 && loc.z >= 0.03 && loc.z <= 0.37);

  // 前行 0.9s：确认真的在走动（面向 +x 走长边，出生朝向 -z 正对长椅走不远）
  await page.evaluate(() => window.__game.player.setView(-Math.PI / 2, -0.2)); // 面向 +x
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(900);
  await page.keyboard.up("KeyW");
  const loc2 = await page.evaluate(() => window.__game.player.cabinLocal());
  await page.screenshot({ path: `${outDir}/c2_walked.png` });
  await expect(`走动改变了舱内位置 ${JSON.stringify(loc2)}`,
    Math.hypot(loc2.x - loc.x, loc2.z - loc.z) > 0.4);

  // 冲刺长椅墙（面向 -z 顶墙走）：不得穿入长椅
  await page.evaluate(() => window.__game.player.setView(0, -0.3)); // yaw 0 = 面向 -z(长椅)
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(1800);
  await page.keyboard.up("KeyW");
  const bench = await page.evaluate(() => window.__game.player.cabinLocal());
  await page.screenshot({ path: `${outDir}/c3_bench_block.png` });
  await expect(`长椅阻挡 z >= 0.03 ${JSON.stringify(bench)}`, bench.z >= 0.03);

  // 走向 -x 大窗贴墙：不得穿出玻璃
  await page.evaluate(() => window.__game.player.setView(Math.PI / 2, -0.2)); // 面向 -x
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(1800);
  await page.keyboard.up("KeyW");
  const wall = await page.evaluate(() => window.__game.player.cabinLocal());
  await page.screenshot({ path: `${outDir}/c4_window_wall.png` });
  await expect(`外墙阻挡 |x| <= 0.63 ${JSON.stringify(wall)}`, Math.abs(wall.x) <= 0.63);

  // C 坐下 -> 移动键起身
  await page.keyboard.press("KeyC");
  await page.waitForTimeout(900);
  const sit = await page.evaluate(() => window.__game.player.cabinLocal());
  await page.screenshot({ path: `${outDir}/c5_seated.png` });
  await expect(`C 坐下生效 ${JSON.stringify(sit)}`, sit.seated === true);

  await page.keyboard.down("KeyW");
  await page.waitForTimeout(700);
  await page.keyboard.up("KeyW");
  const stood = await page.evaluate(() => window.__game.player.cabinLocal());
  await page.screenshot({ path: `${outDir}/c6_stood_up.png` });
  await expect(`移动键起身 ${JSON.stringify(stood)}`, stood.seated === false);

  // 冲向中柱：从 -x 墙边面向 +x 直走，距柱心不得小于 0.19
  await page.evaluate(() => window.__game.player.setView(-Math.PI / 2, -0.35)); // 面向 +x
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(2600);
  await page.keyboard.up("KeyW");
  const pole = await page.evaluate(() => window.__game.player.cabinLocal());
  await page.screenshot({ path: `${outDir}/c7_pole_block.png` });
  await expect(`中柱阻挡距柱心 >= 0.19 ${JSON.stringify(pole)}`,
    Math.hypot(pole.x, pole.z) >= 0.19);

  // E 下乘回站台
  await page.keyboard.press("KeyE");
  await page.waitForTimeout(1600);
  const state = await page.evaluate(() => window.__game.state);
  await page.screenshot({ path: `${outDir}/c8_disembark.png` });
  await expect(`下乘回到 walk 态 (state=${state})`, state === "walk");

  console.log("cabin-check result:", fails.length ? `FAILED x${fails.length}` : "all passed");
  if (fails.length) process.exitCode = 1;
}

console.log("console-errors:", errors.length ? JSON.stringify(errors, null, 2) : "none");
await browser.close();
