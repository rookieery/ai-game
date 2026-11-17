// Points 渲染隔离测试：借 fireworks 几何的死粒子槽位注入红色点阵 (相机前 12m)
import { chromium } from "playwright";

const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8767";
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on("pageerror", (e) => console.log("PAGEERROR:", String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(800);

// 先瞬移到开阔北望位, 等一帧让相机位姿落地, 再按新位姿注入
await page.evaluate(() => {
  window.__game.player.teleport(22, 62);
  window.__game.player.setView(0, 0.6);
});
await page.waitForTimeout(400);

const inj = await page.evaluate(() => {
  let fw = null;
  window.__game.scene.traverse((o) => { if (o.isPoints && o.geometry?.attributes?.aColor) fw = o; });
  if (!fw) return "no fireworks points found";
  const pos = fw.geometry.attributes.position.array;
  const col = fw.geometry.attributes.aColor.array;
  const m = window.__game.camera.matrixWorld.elements;
  const rx = m[0], ry = m[1], rz = m[2];      // right
  const ux = m[4], uy = m[5], uz = m[6];      // up
  const fx = -m[8], fy = -m[9], fz = -m[10];  // forward (camera -z)
  const cx = m[12], cy = m[13], cz = m[14];   // position
  let n = 0;
  const sizeA = fw.geometry.attributes.aSize?.array;
  for (let i = 0; i < 1600 && n < 21; i++) {
    if (col[i * 3] === 0 && col[i * 3 + 1] === 0 && col[i * 3 + 2] === 0 && pos[i * 3 + 1] === -9999) {
      const u = (n % 7 - 3) * 1.2;
      const v = (Math.floor(n / 7) - 1) * 1.2;
      const d = 12;
      pos[i * 3] = cx + fx * d + rx * u + ux * v;
      pos[i * 3 + 1] = cy + fy * d + ry * u + uy * v;
      pos[i * 3 + 2] = cz + fz * d + rz * u + uz * v;
      col[i * 3] = 1; col[i * 3 + 1] = 0.15; col[i * 3 + 2] = 0.15;
      if (sizeA) sizeA[i] = 40;   // 应渲染 ~450/12*40 → 巨大; 若仍小 => gl_PointSize 被钳
      n++;
    }
  }
  fw.geometry.attributes.position.needsUpdate = true;
  fw.geometry.attributes.aColor.needsUpdate = true;
  if (fw.geometry.attributes.aSize) fw.geometry.attributes.aSize.needsUpdate = true;
  return "injected " + n + " points, aSize=40, canvas.height=" +
    window.__game.renderer.domElement.height + " dpr=" + window.devicePixelRatio;
});
console.log("inject:", inj);
await page.waitForTimeout(600);
await page.screenshot({ path: "shots/v3/probe_inject.png" });
await page.waitForTimeout(9000);  // 再等自动烟花爆裂 (elapsed ~11-12s)
await page.screenshot({ path: "shots/v3/probe_autofire.png" });
console.log("done");
await browser.close();
