// 确定性追车取证: 相机位姿由 centerline 数值解出, 三状态各一帧
import { mkdirSync, readFileSync } from "node:fs";
import { chromium } from "playwright";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const OUT = ".impeccable/review-coaster";
mkdirSync(OUT, { recursive: true });
const cl = JSON.parse(readFileSync("public/assets/models/roller_coaster_centerline.json", "utf8"));
const N = cl.samples.length, DS = cl.ds, L = (N - 1) * DS;
function frameAt(s) { // -> app pos of heart line
  const f = ((s % L) + L) % L / DS;
  const i0 = Math.min(N - 2, Math.floor(f)), u = f - i0;
  const a = cl.samples[i0].p, b = cl.samples[i0 + 1].p;
  return [a[0] + (b[0] - a[0]) * u, a[2] + (b[2] - a[2]) * u, -(a[1] + (b[1] - a[1]) * u)];
}
// 相机: 目标点东侧地面上, 仰拍; yaw = atan2(-dx, -dz), pitch = atan2(dy, hypot(dx,dz)) (正=仰)
function camFor(target, dist = 10, up = 1.0) {
  const cam = [target[0] + dist, up, target[2]];
  const dx = target[0] - cam[0], dy = target[1] + 1.0 - cam[1], dz = target[2] - cam[2];
  return { x: cam[0], z: cam[2], yaw: Math.atan2(-dx, -dz), pitch: Math.atan2(dy, Math.hypot(dx, dz)) };
}
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("enter-btn") && !document.getElementById("enter-btn").disabled, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

async function chase(name, s, mode) {
  const t = frameAt(s);
  const c = camFor(t, 9, 1.2);
  await page.evaluate(([s, mode]) => {
    const co = window.__game.coaster;
    if (mode === "dwell") { co.state.phase = "dwell"; co.state.dwellT = 90; }
    co.state.s = s;
    co.update(0.016);
  }, [s, mode]);
  await page.evaluate(([x, z, yaw, pitch]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(yaw, pitch);
  }, [c.x, c.z, c.yaw, c.pitch]);
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name, "cam", c.x.toFixed(1), c.z.toFixed(1), "yaw", c.yaw.toFixed(2), "pitch", c.pitch.toFixed(2));
}

const st = []; for (let i = 0; i < N; i++) if (cl.samples[i].zone === "station") st.push(i * DS);
st.sort((a, b) => a - b);
const sHead = st[Math.floor(st.length / 2)] + 2.5 * 2.35;

await chase("e1_station_dwell", sHead, "dwell");   // 站台停驻 (中位修复后 = blender 61.0)
await chase("e2_lift_run", 100, "run");            // 提升段 (用户截图场景)
await chase("e3_loop_run", 176, "run");            // 回环中
console.log("ERRORS", JSON.stringify(errors.slice(0, 5)));
await browser.close();
