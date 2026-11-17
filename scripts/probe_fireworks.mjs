// 烟花粒子系统探针：按 F 后采样 Points 几何的活性粒子数与最高高度
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
await page.waitForTimeout(1200);

const pointsInfo = await page.evaluate(() => {
  const pts = [];
  window.__game.scene.traverse((o) => {
    if (o.isPoints && o.geometry?.attributes?.color) pts.push(o);
  });
  return pts.map((p) => ({
    max: p.geometry.attributes.position.count,
    material: { size: p.material.size, blending: p.material.blending, vertexColors: p.material.vertexColors },
    frustumCulled: p.frustumCulled,
  }));
});
console.log("points objects:", JSON.stringify(pointsInfo));

await page.evaluate(() => {
  window.__game.player.teleport(20.4, 20.4);   // 释放器旁 (nearLauncher < 3.2)
  window.__game.player.setView(0, 0.5);
});
await page.waitForTimeout(500);   // 与 verify 同时序: 等 interact.update 把 nearLauncher 置真
const promptBefore = await page.evaluate(() =>
  document.querySelector(".spirit-prompt")?.innerText ?? "(无)");
console.log("prompt before F:", JSON.stringify(promptBefore));
await page.keyboard.press("KeyF");
const promptAfter = await page.evaluate(() =>
  document.querySelector(".spirit-prompt")?.innerText ?? "(无)");
console.log("prompt right after F:", JSON.stringify(promptAfter));

for (let k = 0; k < 20; k++) {
  await page.waitForTimeout(500);
  if (k === 9) {   // t=5s: 首爆后 1s, 粒子最多
    await page.screenshot({ path: "shots/v3/probe_burst.png" });
    const rel = await page.evaluate(() => {
      const cam = window.__game.camera;
      let out = [];
      window.__game.scene.traverse((o) => {
        if (o.isPoints && o.geometry?.attributes?.color) {
          const c = o.geometry.attributes.color.array;
          const p = o.geometry.attributes.position.array;
          const m = o.matrixWorld.elements;
          for (let i = 0; i < c.length && out.length < 6; i += 3) {
            if (c[i] + c[i + 1] + c[i + 2] > 0.5) {
              // 世界坐标 -> 相机空间
              const v = new (p.constructor)([p[i], p[i + 1], p[i + 2]]);
              out.push([+p[i].toFixed(1), +p[i + 1].toFixed(1), +p[i + 2].toFixed(1),
                        +c[i].toFixed(2), +c[i + 1].toFixed(2), +c[i + 2].toFixed(2)]);
            }
          }
          out.push("camDir", [+cam.getWorldDirection(new (window.__game.camera.position.constructor)()).x.toFixed(2),
                              +cam.getWorldDirection(new (window.__game.camera.position.constructor)()).y.toFixed(2),
                              +cam.getWorldDirection(new (window.__game.camera.position.constructor)()).z.toFixed(2)]);
        }
      });
      return out;
    });
    console.log("sample particles:", JSON.stringify(rel));
  }
  const s = await page.evaluate(() => {
    let alive = 0;
    let maxY = -9999;
    let maxA = 0;
    window.__game.scene.traverse((o) => {
      if (o.isPoints && o.geometry?.attributes?.color) {
        const c = o.geometry.attributes.color.array;
        const p = o.geometry.attributes.position.array;
        for (let i = 0; i < c.length; i += 3) {
          if (c[i] + c[i + 1] + c[i + 2] > 0.01) {
            alive++;
            if (p[i + 1] > maxY) maxY = p[i + 1];
          }
        }
      }
    });
    const flash = [];
    window.__game.scene.traverse((o) => {
      if (o.isPointLight && o.intensity > 0.05 && o.distance < 300) flash.push(+o.intensity.toFixed(1));
    });
    return { alive, maxY: +maxY.toFixed(1), flash };
  });
  console.log(`t=${(k + 1) * 0.5}s`, JSON.stringify(s));
}
await browser.close();
