// M4-B2 闸机取证: E 开闸 → 转子 60° 扫动 + 闸线碰撞禁用 → 过闸爬梯 → 自动落锁恢复阻挡
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
const gateRot = () => page.evaluate(() => {
  const g = window.__game.coasterGate;
  let r0 = null;
  window.__game.scene.traverse((o) => { if (o.name === "NL_Gate_0") r0 = o.rotation.x; });
  return { state: g.getState(), rot: r0 == null ? null : +r0.toFixed(3) };
});
async function walk(ms) {
  await page.keyboard.down("KeyW");
  await page.waitForTimeout(ms);
  await page.keyboard.up("KeyW");
  return page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
}

// 0) 初始: closed + 转角 0
await page.evaluate(() => { window.__game.player.teleport(9.4, -39.6); window.__game.player.setView(0, 0); });
await page.waitForTimeout(400);
const s0 = await gateRot();
ok("initial_closed", s0.state === "closed" && Math.abs(s0.rot) < 0.01, s0);
await page.screenshot({ path: `${OUT}/m4_gate_closed.png` });

// 1) E 开闸: 转子扫到 ~60°
await page.keyboard.press("KeyE");
await page.waitForTimeout(500);
const sMid = await gateRot(); // 扫动中
await page.waitForTimeout(900);
const s1 = await gateRot();
ok("opening_sweep", sMid.state === "opening" && sMid.rot > s0.rot && sMid.rot < 1.05, sMid);
ok("opened_60deg", s1.state === "open" && Math.abs(s1.rot - Math.PI / 3) < 0.02, s1);
await page.screenshot({ path: `${OUT}/m4_gate_open.png` });

// 2) 过闸爬梯: 直行应穿闸线并登上台阶
await walk(2600);
const t2 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
ok("pass_and_climb", t2.z < -43 && t2.y > 1.0, t2);

// 3) 自动落锁: 玩家已离闸线带, 等 7.5s 后应 closed 并恢复碰撞
await page.waitForTimeout(7500);
const s3 = await gateRot();
ok("auto_closed", s3.state === "closed" && Math.abs(s3.rot) < 0.01, s3);

// 4) 落锁后阻挡: 回走廊直行, 应被挡在闸线以南
await page.evaluate(() => { window.__game.player.teleport(9.4, -39.6); window.__game.player.setView(0, 0); });
await page.waitForTimeout(300);
await walk(1500);
const t4 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) }; });
ok("relock_blocks", t4.z > -40.6, t4);

console.log(JSON.stringify(R, null, 1));
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
const pass = Object.values(R).every((v) => v === "PASS") && errors.length === 0;
process.exit(pass ? 0 : 1);
