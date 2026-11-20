// M3 取证补测: 站名可读性(正确仰角) / 性能(正确采样) / 驻留回归
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
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

async function shot(name, x, z, yaw, pitch, wait = 400) {
  await page.evaluate(([x, z, yaw, pitch]) => {
    window.__game.player.teleport(x, z);
    window.__game.player.setView(yaw, pitch);
  }, [x, z, yaw, pitch]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name);
}

// 站名: 33m 正对 + 仰角 0.24 / 50m 中距 / 100m 远景(4 号已拍, 补仰角版)
await shot("10_sign_33m_up", 11.5, -34, 0, 0.24);
await shot("11_sign_50m", 11.5, -17, 0, 0.16);

// 性能: rAF 计帧 2s + 单帧 drawCalls (autoReset=false, reset, 等一帧, 读)
const perf = await page.evaluate(async () => {
  const { renderer, player } = window.__game;
  const spots = [["plaza", 0, 20, 0, -0.05], ["station", 9.4, -55, 0, -0.05], ["loopGround", 65, -95, -0.5, 0.2]];
  const out = {};
  for (const [name, x, z, yaw, pitch] of spots) {
    player.teleport(x, z);
    player.setView(yaw, pitch);
    await new Promise((r) => setTimeout(r, 600));
    // fps: rAF 计数 2 秒
    const fps = await new Promise((resolve) => {
      let n = 0;
      const t0 = performance.now();
      const tick = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(tick); else resolve(n / 2); };
      requestAnimationFrame(tick);
    });
    // 单帧 draw calls: 重置后恰好等一帧
    renderer.info.autoReset = false;
    renderer.info.reset();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const calls = renderer.info.render.calls;
    const tris = renderer.info.render.triangles;
    renderer.info.autoReset = true;
    out[name] = { fps: Math.round(fps), drawCalls: calls, tris: tris };
  }
  return out;
});

// 驻留回归: 直接跳到缝合样本前一米, 高速区间验证 wrap
const dwell = await page.evaluate(async () => {
  const c = window.__game.coaster;
  c.seek(1.0);              // 缝合点后 1m (v≈2 的进场段), 一圈 503m @均速~10 → 太久; 改为直接测 wrap: seek(L-0.5)
  c.seek(502.5);
  await new Promise((r) => setTimeout(r, 2000));
  return { phase: c.state.phase, laps: c.state.laps, v: +c.state.v.toFixed(2) };
});

console.log(JSON.stringify({ perf, dwell, consoleErrors: errors.slice(0, 6) }, null, 1));
await browser.close();
