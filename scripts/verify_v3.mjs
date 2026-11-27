// 园区 v3 验证：r150 扩园定点取证 + 烟花释放器 + FPS/drawcall 抽样
// 用法: node scripts/verify_v3.mjs [输出目录]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/v3";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1500);

// 1. 新出生点 (0,144) 面向园区（大门 -> 主路 -> 二道门纵深）
await page.evaluate(() => window.__game.player.teleport(0, 144));
await page.waitForTimeout(600);
await page.screenshot({ path: `${outDir}/v1_spawn.png` });

// 2. 二道门牌楼 (0,-60 blender -> app (0,-60)? blender (0,-60) -> app (0,60))
await page.evaluate(() => {
  window.__game.player.teleport(0, 70);
  window.__game.player.setView(Math.PI, -0.05); // 面向 -z: 二道门+广场纵深
});
await page.waitForTimeout(600);
await page.screenshot({ path: `${outDir}/v2_midgate.png` });

// 3. 烟花发射器 L1 (22,22) + 提示 + F 点射 (南退 40m 仰拍北天)
await page.evaluate(() => {
  window.__game.player.teleport(20.4, 20.4);
  window.__game.player.setView(-2.4, -0.1);
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/v3_launcher.png` });
const promptText = await page.evaluate(() => document.body.innerText.match(/发射架 · F 点射|垂柳塔 · F 点射|连环炮 · F 点射|烟花装填中[^\n]*/)?.[0] ?? "(无提示)");
console.log("launcher prompt:", promptText);
await page.keyboard.press("KeyF");
await page.evaluate(() => {
  window.__game.player.teleport(22, 62);
  window.__game.player.setView(0, 0.72); // 北天 41° 仰角
});
await page.waitForTimeout(4100); // 抓首壳爆裂峰值 (3-4s 爆, +0.6s 内最亮)
const fwDump = await page.evaluate(() => {
  let alive = 0;
  let maxY = -9999;
  window.__game.scene.traverse((o) => {
    if (o.isPoints && o.geometry?.attributes?.aColor) {
      const c = o.geometry.attributes.aColor.array;
      const p = o.geometry.attributes.position.array;
      for (let i = 0; i < c.length; i += 3) {
        if (c[i] + c[i + 1] + c[i + 2] > 0.01) {
          alive++;
          if (p[i + 1] > maxY) maxY = p[i + 1];
        }
      }
    }
  });
  const cam = window.__game.camera;
  const p = window.__game.player.pos;
  return { alive, maxY: +maxY.toFixed(1), camPos: cam.position.toArray().map((v) => +v.toFixed(1)),
           pitch: +cam.rotation.x.toFixed(2), yaw: +cam.rotation.y.toFixed(2),
           player: [+p.x.toFixed(1), +p.z.toFixed(1)] };
});
console.log("fireworks dump:", JSON.stringify(fwDump));
await page.screenshot({ path: `${outDir}/v4_fireworks.png` });

// 4. 过山车预留区入口 (15,-68.5 app)
await page.evaluate(() => {
  window.__game.player.teleport(15, -64);
  window.__game.player.setView(Math.PI, -0.02);
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/v5_coaster_zone.png` });

// 5. 幽灵港入口 (-52,40 app)
await page.evaluate(() => {
  window.__game.player.teleport(-49, 40);
  window.__game.player.setView(-Math.PI / 2 - 0.4, -0.02);
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/v6_bay_zone.png` });

// 6. 墓园新址 (2026-11-26 南迁: 椭圆 36x24 心 app (37,58)); 从西侧支路上朝东看
await page.evaluate(() => {
  window.__game.player.teleport(20, 54.7);
  window.__game.player.setView(-Math.PI / 2, -0.06);
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/v7_graveyard.png` });

// 7. 外环西段 (r90) 看许愿池方向
await page.evaluate(() => {
  window.__game.player.teleport(-80, -20);
  window.__game.player.setView(-2.4, -0.05);
});
await page.waitForTimeout(500);
await page.screenshot({ path: `${outDir}/v8_outring.png` });

// 8. 摩天轮顶俯瞰全园（雾/远景校准）
await page.evaluate(() => {
  window.__game.player.teleport(0, 1.5, 1.55); // v3 第 2 批: 站台闸内登舱 (地面登舱点取消)
});
await page.waitForFunction(() => window.__game.ferris.isDocked(), { timeout: 15000 });
await page.waitForTimeout(200);
await page.keyboard.press("KeyE");
await page.waitForTimeout(1600);
await page.evaluate(() => {
  window.__game.ferris.state.theta = Math.PI;
  window.__game.player.setView(Math.PI, -0.62);
});
await page.waitForTimeout(700);
await page.screenshot({ path: `${outDir}/v9_aerial.png` });
await page.keyboard.press("KeyE"); // 下乘
await page.waitForTimeout(1600);

// 9. 碰撞断言: 边界钳制 + 预留区围挡不可穿 (缺口可穿)
const checks = await page.evaluate(() => ({
  boundaryR: window.__park?.boundaryR,
  spawn: window.__park?.spawn,
}));
console.log("park meta:", JSON.stringify(checks));
// 真实按键冲刺 3s 验证边界 (yaw π = 面向 +z 南, 朝大门)
await page.evaluate(() => {
  window.__game.player.teleport(0, 130);
  window.__game.player.setView(Math.PI, 0);
});
await page.keyboard.down("KeyW");
await page.keyboard.down("ShiftLeft");
await page.waitForTimeout(3000);
await page.keyboard.up("ShiftLeft");
await page.keyboard.up("KeyW");
const southPos = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(2), z: +p.z.toFixed(2), r: +Math.hypot(p.x, p.z).toFixed(2) };
});
console.log("boundary clamp pos:", JSON.stringify(southPos), "(r 应 <= 144.2)");
// 围挡阻挡: 幽灵港东缘 x=-52 缺口 z∈[37,43], 在 z=45 (墙段) 往 -x 冲应被挡
await page.evaluate(() => {
  window.__game.player.teleport(-45, 45);
  window.__game.player.setView(Math.PI / 2, 0); // yaw +π/2 = 面向 -x
});
await page.keyboard.down("KeyW");
await page.waitForTimeout(2500);
await page.keyboard.up("KeyW");
const bayPos = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) };
});
console.log("bay fence block pos:", JSON.stringify(bayPos), "(x 应 > -53)");
await page.screenshot({ path: `${outDir}/v10_bay_block.png` });
// 围挡缺口可穿: z=40 (缺口内) 往 -x 走应能进入预留区
await page.evaluate(() => {
  window.__game.player.teleport(-45, 40);
  window.__game.player.setView(Math.PI / 2, 0);
});
await page.keyboard.down("KeyW");
await page.waitForTimeout(2500);
await page.keyboard.up("KeyW");
const bayGapPos = await page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(2), z: +p.z.toFixed(2) };
});
console.log("bay gap pass pos:", JSON.stringify(bayGapPos), "(x 应 < -53, 走进预留区)");

// 10. 性能抽样: 单帧 draw calls/tris (info.reset 后读一帧) + FPS
function sampleFrame(label) {
  return page.evaluate((lb) => new Promise((resolve) => {
    const r = window.__game.renderer;
    r.info.autoReset = false;
    r.info.reset();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      resolve({ label: lb, calls: r.info.render.calls, tris: r.info.render.triangles });
      r.info.autoReset = true;
    }));
  }), label);
}
await page.evaluate(() => window.__game.player.teleport(0, 24));
await page.waitForTimeout(1500);
console.log("perf idle:", JSON.stringify(await sampleFrame("idle")));
// 对照组: 面向摩天轮 (轮体入画, 验证 +calls 来自轮体而非烟花)
await page.evaluate(() => {
  window.__game.player.teleport(0, 24);
  window.__game.player.setView(0, -0.1); // yaw 0 = 面向 -z 北 (摩天轮在原点)
});
await page.waitForTimeout(800);
console.log("perf wheel-view:", JSON.stringify(await sampleFrame("wheel")));
await page.evaluate(() => window.__game.player.teleport(20.4, 20.4));
await page.keyboard.press("KeyF");
await page.waitForTimeout(3300); // 等首轮爆裂 (3-4s 升空)
const frames = await page.evaluate(async () => {
  let n = 0;
  const t0 = performance.now();
  await new Promise((res) => {
    const cb = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(cb); else res(); };
    requestAnimationFrame(cb);
  });
  return +(n / 2).toFixed(1);
});
console.log("perf fireworks:", JSON.stringify({ ...(await sampleFrame("fireworks")), fps: frames }));

console.log("console-errors:", errors.length ? JSON.stringify(errors, null, 2) : "none");
await browser.close();
