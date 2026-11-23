// M4-B4 E2E 乘坐取证 (真键模拟): 开闸→爬梯→站台→E 登车→POV 姿态/FOV→V 切追逐→排队→到站自动下客
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const OUT = ".impeccable/review-coaster";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

const R = {};
const ok = (name, cond, got) => { R[name] = cond ? "PASS" : `FAIL ${JSON.stringify(got)}`; };
async function walk(ms, key = "KeyW") {
  await page.keyboard.down(key);
  await page.waitForTimeout(ms);
  await page.keyboard.up(key);
  return page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
}
const pose = (x, z, yaw, pitch = 0) => page.evaluate(([x, z, yaw, pitch]) => {
  window.__game.player.teleport(x, z);
  window.__game.player.setView(yaw, pitch);
}, [x, z, yaw, pitch]);

// ① 开闸 (走廊内 E) → 过闸爬梯登站台
await pose(9.4, -39.6, 0);
await page.waitForTimeout(400);
await page.keyboard.press("KeyE"); // 开闸
await page.waitForTimeout(1200);
await walk(2600);
const t1 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
ok("board_flow_stairs", t1.y > 2.2 && t1.z < -44, t1);

// ② 走到登车点 → 座位提示 → E 登车
await pose(10.3, -60.5, -Math.PI / 2, 0); // 西站台面向列车 (车头在东南侧)
await walk(700, "KeyD"); // 面东时 D=南? 直接走到座位半径内: 用 teleport 兜位再靠提示
await page.evaluate(() => {
  const s = window.__game.coaster.getBoardSpot();
  // 落到座位半径 1.5m 内的站台可走点 (座位在西 deck 东缘 0.9m 外, 落西缘附近)
  window.__game.player.teleport(Math.max(10.3, s.x - 0.95), s.z);
});
await page.waitForTimeout(500);
const promptOn = await page.evaluate(() => {
  const el = document.querySelector("#hud-prompt, .hud-prompt");
  return el ? el.textContent : document.body.innerText.includes("登上幽冥回环");
});
await page.keyboard.press("KeyE");
await page.waitForTimeout(900);
const rideState = await page.evaluate(() => ({
  state: window.__game.state,
  ride: window.__game.ride,
  rideActive: window.__game.player.rideActive(),
}));
ok("board_prompt", !!promptOn, promptOn);
ok("riding_started", rideState.state === "riding" && rideState.ride === "coaster" && rideState.rideActive, rideState);

// ③ POV 姿态: 相机四元数应等于 POV 帧四元数 (夹角 < 2°) 且位置近 CamPov
await page.waitForTimeout(1000); // 压肩闭合期 (列车未动)
const pov = await page.evaluate(() => {
  const c = window.__game.coaster;
  const fr = c.getRideFrame("pov", 0.016);
  const cam = window.__game.camera;
  const dot = Math.abs(cam.quaternion.dot(fr.quat));
  const d = cam.position.distanceTo(fr.pos);
  return { dot: +dot.toFixed(4), dist: +d.toFixed(3) };
});
ok("pov_pose_aligned", pov.dot > 0.9994 && pov.dist < 0.3, pov);

// ③b 自由环视: 设偏移 → 2s 后不衰减 (移除自动回中的契约断言)
const freeLook = await page.evaluate(async () => {
  const pl = window.__game.player;
  pl.debugRideView(1.5, 0.3);
  await new Promise((r) => setTimeout(r, 2000));
  const v = pl.rideView();
  return { yaw: +v.yawOff.toFixed(3), pitch: +v.pitchOff.toFixed(3) };
});
ok("free_look_no_decay", Math.abs(freeLook.yaw - 1.5) < 0.01 && Math.abs(freeLook.pitch - 0.3) < 0.01, freeLook);

// ③c R 回正: 平滑归位 (120ms 时仍残留 >0.2 证明阻尼不瞬切; 1s 内 <0.02 归位)
await page.keyboard.press("KeyR");
await page.waitForTimeout(120);
const rMid = await page.evaluate(() => window.__game.player.rideView());
await page.waitForTimeout(900);
const rEnd = await page.evaluate(() => window.__game.player.rideView());
ok("r_reset_smooth", rMid.resetting && Math.abs(rMid.yawOff) > 0.2, { yaw: +Math.abs(rMid.yawOff).toFixed(3) });
ok("r_reset_settled", Math.abs(rEnd.yawOff) < 0.02 && Math.abs(rEnd.pitchOff) < 0.02, {
  yaw: +Math.abs(rEnd.yawOff).toFixed(3), pitch: +Math.abs(rEnd.pitchOff).toFixed(3),
});

// ④ FOV 拉伸: seek 俯冲高速段 → fov 应 > 63 (feel 默认 60)
await page.evaluate(() => window.__game.coaster.seek(120));
await page.waitForTimeout(700);
const fovHi = await page.evaluate(() => +window.__game.camera.fov.toFixed(2));
ok("fov_stretch", fovHi > 63, fovHi);
await page.screenshot({ path: `${OUT}/m4_pov_drop.png` });

// ⑤ V 切追逐: 追逐机位在头车后方 4-12m 且相机不倒挂 (世界 Y 在相机局部 Y 分量 > 0.5)
await page.keyboard.press("KeyV");
await page.waitForTimeout(600);
const chase = await page.evaluate(() => {
  const c = window.__game.coaster;
  const fr = c.getRideFrame("chase", 0.016);
  const head = c.cars[0].position;
  return {
    headDist: +fr.pos.distanceTo(head).toFixed(1),
    pos: [fr.pos.x.toFixed(1), fr.pos.y.toFixed(1), fr.pos.z.toFixed(1)],
    headPos: [head.x.toFixed(1), head.y.toFixed(1), head.z.toFixed(1)],
  };
});
const chaseUp = await page.evaluate(() => {
  const cam = window.__game.camera;
  const e = cam.matrixWorld.elements;
  // 列主序: elements[4..6] = 相机局部 Y 轴的世界向量 (x,y,z)。
  // 「不倒挂」看的是该轴的**世界 Y 分量 = e[5]**; e[4] 是其 X 分量,
  // 随 crane/追逐视线水平朝向合法地在 ±1 摆动, 与倒挂无关 (v5.1 勘误)
  return { upY: +e[5].toFixed(2) };
});
ok("chase_switch", chase.headDist > 4 && chase.headDist < 12, chase);
// 不倒置判据 (v5.1 重写): 不 seek 打断、连续骑过螺丝钻全程逐帧采样相机 upY。
//   单点测量混入 seek 跳变的阻尼瞬态 (相机滞后数米时的读数不可信); 真实不变量 =
//   连续乘坐中相机永不倒翻 (upY 最小值 > -0.6, 完全翻转 ≈ -1)。
//   布局侧防御: coaster.js 陡视时 up 取世界 Y 在视平面的投影 (crane 连续滚转)。
await page.evaluate(() => {
  window.__game.coaster.seek(266);            // 螺丝钻 #2 入口
  window.__game.coaster.setRideCam("chase");  // 重吸附追逐位
});
await page.waitForTimeout(150);
const corkSweep = await page.evaluate(async () => {
  const cam = window.__game.camera;
  const c = window.__game.coaster;
  const vals = [];
  for (let k = 0; k < 90; k++) {              // ~1.5s, 覆盖螺丝钻全程 (42m @ ~13m/s)
    await new Promise(r => setTimeout(r, 16));
    vals.push(+cam.matrixWorld.elements[5].toFixed(2)); // Y 轴世界 Y 分量 (勘误: 原 e[4] 是 X 分量)
    if (c.state.s > 320) break;               // 已出钻
  }
  return { min: Math.min(...vals), vals: vals.filter((v, i) => i % 8 === 0) };
});
const upCork = corkSweep.min;
const upDrop = chaseUp.upY;
ok("chase_no_flip", upDrop > -0.3 && upCork > -0.3, { upDrop, upCork, corkMin: corkSweep.min });
await page.screenshot({ path: `${OUT}/m4_chase_run.png` });

// ⑥ 排队下客: E → 到站停稳自动下客 → walk @ 东 deck
await page.keyboard.press("KeyE"); // 排队
await page.waitForTimeout(400);
const queued = await page.evaluate(() => window.__game.coaster.state.session.wantOff);
// seek 到刹车段 (v7 弧长, v6.3 为 496), 让链路快速走完 (过缝→crawl→停→压肩开→转场)
await page.evaluate(() => window.__game.coaster.seek(560));
const walked = await page.evaluate(async () => {
  const t0 = Date.now();
  while (Date.now() - t0 < 30000) {
    await new Promise((r) => setTimeout(r, 400));
    if (window.__game.state === "walk") break;
  }
  const p = window.__game.player.pos;
  return { state: window.__game.state, x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) };
});
ok("queue_accepted", queued === true, queued);
ok("auto_disembark", walked.state === "walk" && walked.y > 2.0 && Math.abs(walked.z - (-60.2)) < 0.5 && Math.abs(walked.x - 13.2) < 0.5, walked);

console.log(JSON.stringify(R, null, 1));
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
const pass = Object.values(R).every((v) => v === "PASS") && errors.length === 0;
process.exit(pass ? 0 : 1);
