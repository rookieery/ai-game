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
  return { upY: +e[4].toFixed(2) }; // 世界 Y 在相机局部 Y 的分量
});
ok("chase_switch", chase.headDist > 4 && chase.headDist < 12, chase);
// 不倒置判据: upY>0 (翻转=≈-1)。俯冲段近垂直跟拍 upY 会低 (俯仰非滚转), 螺丝钻段
// 靠 up 混合 (0.65 世界Y+0.35 帧up) 抑制整周滚转, 两处都应保持正值
const upDrop = chaseUp.upY;
await page.evaluate(() => window.__game.coaster.seek(300)); // 螺丝钻中段
await page.waitForTimeout(600);
const upCork = await page.evaluate(() => {
  const cam = window.__game.camera;
  return +cam.matrixWorld.elements[4].toFixed(2);
});
ok("chase_no_flip", upDrop > 0 && upCork > 0, { upDrop, upCork });
await page.screenshot({ path: `${OUT}/m4_chase_run.png` });

// ⑥ 排队下客: E → 到站停稳自动下客 → walk @ 东 deck
await page.keyboard.press("KeyE"); // 排队
await page.waitForTimeout(400);
const queued = await page.evaluate(() => window.__game.coaster.state.session.wantOff);
// seek 到刹车段, 让链路快速走完 (过缝→crawl→停→压肩开→转场)
await page.evaluate(() => window.__game.coaster.seek(496));
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
