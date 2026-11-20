// A 修复复验: frameAt 基修正后, 列车在 4 个关键弧长的姿态取证
// 冻结点: 站台驻留 / 提升段 s=100 / 回环入口 s=160 / 回环顶 s=176
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

const STOPS = [
  { s: 17.4, name: "a1_station", dist: 9, lift: 1.6 },
  { s: 100, name: "a2_lift", dist: 24, lift: 1.6 },
  { s: 160, name: "a3_loop_entry", dist: 16, lift: 1.6 },
  { s: 176, name: "a4_loop_apex", dist: 18, lift: 1.6 },
];
for (const st of STOPS) {
  const info = await page.evaluate(([s, dist, lift]) => {
    const c = window.__game.coaster;
    c.state.s = ((s % 504) + 504) % 504;
    c.state.phase = "dwell"; c.state.dwellT = 999;
    c.update(0.016); // 单步摆位
    const car = c.cars[0];
    car.updateWorldMatrix(true, false);
    const p = car.getWorldPosition(new window.__game_coaster_vec());
    return { x: p.x, y: p.y, z: p.z };
  }, [st.s, st.dist, st.lift]).catch(async () => {
    // Vector3 类不可用时退化为 seek+近似
    return null;
  });
  // __game 未暴露 Vector3 -> 在页面里就地取
  const pos = await page.evaluate(([s, dist, lift]) => {
    const c = window.__game.coaster;
    c.state.s = ((s % 504) + 504) % 504;
    c.state.phase = "dwell"; c.state.dwellT = 999;
    c.update(0.016);
    const v = c.cars[0].getWorldPosition(c.cars[0].position.clone());
    return { x: +v.x.toFixed(2), y: +v.y.toFixed(2), z: +v.z.toFixed(2) };
  }, [st.s, st.dist, st.lift]);
  await page.evaluate(([p, dist, lift]) => {
    // 站在头车南侧 dist 米, 地面身高 1.6, 回看头车
    const px = p.x, pz = p.z + dist;
    const dx = p.x - px, dz = p.z - pz, dy = p.y - lift;
    const yaw = Math.atan2(dx, -dz);
    const pitch = Math.atan2(dy, Math.hypot(dx, dz));
    window.__game.player.teleport(px, pz);
    window.__game.player.setView(yaw, pitch);
  }, [pos, st.dist, st.lift]);
  await page.waitForTimeout(350);
  await page.screenshot({ path: `${OUT}/${st.name}.png` });
  console.log("shot", st.name, "head@", JSON.stringify(pos));
}
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
