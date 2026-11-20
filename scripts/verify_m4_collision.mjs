// M4-B1 碰撞基建取证: 闸线 tag 开关 / 东槽单向墙(逆爬+跳跃) / 东阶下行 / 站台防坠墙
import { chromium } from "playwright";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

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
const R = {};
const ok = (name, cond, got) => { R[name] = cond ? "PASS" : `FAIL ${JSON.stringify(got)}`; };

// ① 开闸禁用: 走廊内面北直行, 应穿过闸线爬上西槽台阶 (起点在走廊内部, 真实动线经迷宫缺口抵达)
await pose(9.4, -39.9, 0);
await page.evaluate(() => window.__game.player.setRectDisabled("coasterGate", true));
await walk(2000);
const t1 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
ok("gate_open_pass", t1.z < -43 && t1.y > 1.0, t1);

// ② 恢复闸线: 同起点直行, 应被挡在闸线以南
await pose(9.4, -39.9, 0);
await page.evaluate(() => window.__game.player.setRectDisabled("coasterGate", false));
await walk(2000);
const t2 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) }; });
ok("gate_closed_block", t2.z > -40.6, t2);

// ③ 东槽单向墙: 走廊面北直行 + 跳跃, 应全部被挡
await pose(13.6, -39.4, 0);
await page.keyboard.down("KeyW");
for (let i = 0; i < 3; i++) { await page.keyboard.press("Space"); await page.waitForTimeout(500); }
await page.waitForTimeout(1000);
await page.keyboard.up("KeyW");
const t3 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), z: +p.z.toFixed(2), y: +p.y.toFixed(2) }; });
ok("east_oneway_block", t3.z > -40.75, t3);

// ④ 东阶下行: 站台上面向南直行, 应经槽步行落到地面
await pose(13.6, -44.5, Math.PI);
await walk(4000);
const t4 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
ok("east_descend_ok", t4.z > -40.5 && t4.y < 0.6, t4);

// ⑤ 防坠墙: 西站台面向东直行, 应停在凹坑西缘之外
await pose(9.6, -60, -Math.PI / 2);
await walk(2000);
const t5 = await page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2) }; });
ok("pit_wall_block", t5.x < 10.62 && t5.y > 2.2, t5);

console.log(JSON.stringify(R, null, 1));
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
const pass = Object.values(R).every((v) => v === "PASS") && errors.length === 0;
process.exit(pass ? 0 : 1);
