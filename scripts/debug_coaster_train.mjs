// 列车异常实证调试: 逐车世界坐标 vs centerline 期望 / NaN 扫描 / 静止与运动近摄
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

// 期望值在 node 侧算: 读同步的 centerline.json
import { readFileSync } from "node:fs";
const cl = JSON.parse(readFileSync("public/assets/models/roller_coaster_centerline.json", "utf8"));
const N = cl.samples.length, DS = cl.ds, L = (N - 1) * DS;
function expect(s) {
  const f = ((s % L) + L) % L / DS;
  const i0 = Math.min(N - 2, Math.floor(f)), u = f - i0;
  const a = cl.samples[i0].p, b = cl.samples[i0 + 1].p;
  return [a[0] + (b[0] - a[0]) * u, a[2] + (b[2] - a[2]) * u, -(a[1] + (b[1] - a[1]) * u)];
}

// 1) 定点 seek s=100 (提升段) 冻结检查: 逐车 pos/quat/NaN
const probe = await page.evaluate(() => {
  const c = window.__game.coaster;
  c.seek(100);
  c.update(0.0001); // 单步摆位
  const out = [];
  c.cars.forEach((car, i) => {
    if (!car) return out.push({ i, missing: true });
    car.updateWorldMatrix(true, false);
    const p = car.getWorldPosition(car.position.clone());
    const q = car.quaternion;
    out.push({
      i,
      pos: [+p.x.toFixed(2), +p.y.toFixed(2), +p.z.toFixed(2)],
      nan: !isFinite(p.x + p.y + p.z + q.x + q.y + q.z + q.w),
      qy: +q.y.toFixed(2), qw: +q.w.toFixed(2),
    });
  });
  return out;
});
const GAP = 2.35;
const cmp = probe.map((c, i) => {
  if (!c || c.missing || c.nan) return { i, ...c };
  const e = expect(100 - i * GAP);
  const d = Math.hypot(c.pos[0] - e[0], c.pos[1] - e[1], c.pos[2] - e[2]);
  return { i, got: c.pos, want: e.map((v) => +v.toFixed(2)), delta: +d.toFixed(2) };
});
console.log("CAR_PROBE", JSON.stringify(cmp, null, 1));

// 2) 静止(驻留)近摄: 站台侧前方 8m
async function shot(name, x, z, yaw, pitch, wait = 350) {
  await page.evaluate(([x, z, yaw, pitch]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(yaw, pitch);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name);
}
// 站台停驻列车近摄 (dwell 态)
await page.evaluate(() => { const c = window.__game.coaster; c.state.phase = "dwell"; c.state.dwellT = 60; c.update(0.016); });
await shot("d1_train_dwell_close", 6.5, -57, -0.9, -0.05);
await shot("d2_train_dwell_side", 9.4, -49, Math.PI, -0.06);

// 3) 运动近摄: seek 到站台出口低速段, 连拍两帧看轮子/碎片
await page.evaluate(() => { window.__game.coaster.seek(24); });
await shot("d3_train_moving_a", 8.0, -52, -1.2, -0.08, 250);
await shot("d4_train_moving_b", 8.0, -52, -1.2, -0.08, 250);

console.log("CONSOLE_ERRORS", JSON.stringify(errors.slice(0, 8)));
await browser.close();
