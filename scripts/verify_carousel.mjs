// 显灵木马运行时回归验证
// 前置: npm run dev 已在 http://127.0.0.1:8765
// 断言:
//   资产加载无报错; CR_Spin 旋转 / 马位起伏(±0.22) / 座车不起伏
//   三级台阶逐级走上平台 (y: 0 -> 0.155 -> 0.31 -> 0.465 -> 0.62)
//   平台上静止站立会被经过的马推开 (动态碰撞圆生效)
//   提示与铭牌报坐骑名; 乘坐中键位条收起 (2026-11-26)
//   盘心祭坛南瓜灯打卡点: 收集 / 星图 1/12 / 打卡提示排在上马提示之前 (2026-11-26)
//   同款灵兽合批: 实例世界矩阵 = 原网格世界矩阵, draw call 降幅 >= 40 (2026-11-26)
// 截图: 场外远景 / 盘上第一人称 / 动态碰撞推挤取证 / 祭坛打卡提示
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const outDir = process.argv[2] ?? "shots/carousel";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));

const pos = () => page.evaluate(() => {
  const p = window.__game.player.pos;
  return { x: +p.x.toFixed(3), y: +p.y.toFixed(3), z: +p.z.toFixed(3) };
});

await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 60000 });
await page.click("#enter-btn");
await page.waitForTimeout(1200);

const fails = [];
const expect = async (name, cond, detail = "") => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"} : ${name}${detail ? "  " + detail : ""}`);
};

// T0 资产就位
const hasCarousel = await page.evaluate(() => !!window.__game.carousel?.spinRoot);
await expect("carousel 资产加载", hasCarousel);

// T1 机台旋转 (theta 前进)
const th0 = await page.evaluate(() => window.__game.carousel.state.theta);
await page.waitForTimeout(800);
const th1 = await page.evaluate(() => window.__game.carousel.state.theta);
await expect("机台旋转 theta 前进", th1 > th0, `${th0.toFixed(4)} -> ${th1.toFixed(4)}`);

// T2 马位起伏 ±0.22 / 座车静止
const b0 = await page.evaluate(() => window.__game.carousel.rideRoots[1].position.y);
await page.waitForTimeout(700);
const b1 = await page.evaluate(() => window.__game.carousel.rideRoots[1].position.y);
await expect("马位起伏变化", Math.abs(b1 - b0) > 0.05, `${b0.toFixed(3)} -> ${b1.toFixed(3)}`);
const c0 = await page.evaluate(() => window.__game.carousel.rideRoots[0].position.y);
await expect("座车不起伏 (i0)", Math.abs(c0 - 0.62) < 1e-4, `y=${c0}`);

// T3 三级台阶逐级上平台 (入口方位 azimuth 202° -> app 侧台阶在场地西南)
// 台阶圆: (37.27,-14.88,h.465) (36.66,-14.63,h.31) (36.04,-14.37,h.155), 朝平台走 +W
// yaw 换算: forward=(-sin yaw, -cos yaw) -> 面向 dir(dx,dz) 取 yaw=atan2(-dx,-dz)
await page.evaluate(() => {
  window.__game.player.teleport(34.5, -13.8);
  window.__game.player.setView(Math.atan2(-0.928, 0.371), 0); // 面向 (45,-18) 平台中心
});
await page.waitForTimeout(300);
const yStart = (await pos()).y;
await page.keyboard.down("KeyW");
await page.waitForTimeout(900);
const yS1 = (await pos()).y;
await page.waitForTimeout(700);
const yS2 = (await pos()).y;
await page.waitForTimeout(700);
const yS3 = (await pos()).y;
await page.keyboard.up("KeyW");
await page.waitForTimeout(600);
const yEnd = (await pos()).y;
await expect("从地面出发", yStart < 0.05, `y=${yStart}`);
await expect("走上平台顶 0.62", Math.abs(yEnd - 0.62) < 0.03, `${yStart} -> ${yEnd}`);
await page.screenshot({ path: `${outDir}/deck_first_person.png` });

// T4 动态碰撞: 站在马环上 (r6.2, 马位圆 r0.55+PR0.38=0.93) 被经过的马推开
await page.evaluate(() => {
  window.__game.player.teleport(45, -11.8);
  window.__game.player.setView(0, 0);
});
const p0 = await pos();
await page.waitForTimeout(4500);
const p1 = await pos();
const pushed = Math.hypot(p1.x - p0.x, p1.z - p0.z);
await expect("静止站立被马位推开 (动态碰撞)", pushed > 0.3, `dist=${pushed.toFixed(3)}`);
await page.screenshot({ path: `${outDir}/pushed_by_horse.png` });

// T5 骑乘: 盘面按 E 上马 (就近骑乘位) -> 相机随盘旋转 -> E 下马回平台
await page.evaluate(() => {
  window.__game.player.teleport(39.5, -14.5); // 盘面内, 靠近入口位南瓜马车
  window.__game.player.setView(0.9, 0);
});
await page.waitForTimeout(600); // 等 interact 提示生效
// DOM 读数: 灵摆提示 / 乘坐铭牌 / 键位条
const dom = () => page.evaluate(() => {
  const q = (s) => document.querySelector(`#hud ${s}`);
  const prompt = q(".spirit-prompt");
  const plaque = q(".ride-plaque");
  const keys = q(".keys-bar");
  return {
    prompt: prompt?.classList.contains("show") ? q(".prompt-text")?.textContent ?? "" : "",
    plaque: plaque?.classList.contains("show") ? q(".plaque-name")?.textContent ?? "" : "",
    plaqueHint: q(".plaque-hint")?.textContent ?? "",
    keysShown: !!keys && !keys.classList.contains("riding"),
    lit: document.querySelectorAll("#hud .star-map svg.lit").length,
  };
});
// T5a 提示报坐骑名 (旧版恒为「骑上显灵木马」)
const d0 = await dom();
await expect("盘面提示报出坐骑名", /^骑上(灵火幽灵马|象牙鎏金马|南瓜稻草马|南瓜马车|鎏金座车)$/.test(d0.prompt), `「${d0.prompt}」`);
await expect("未乘坐时键位条可见", d0.keysShown);
await page.keyboard.press("KeyE");
await page.waitForTimeout(900); // 等转场完成
const st = await page.evaluate(() => ({
  state: window.__game.state,
  ride: window.__game.ride,
  mounted: window.__game.carousel.mounted,
  cam: (() => {
    const c = window.__game.camera.position;
    return { x: +c.x.toFixed(2), y: +c.y.toFixed(2), z: +c.z.toFixed(2) };
  })(),
}));
await expect("E 上马进入 riding", st.state === "riding" && st.ride === "carousel" && st.mounted >= 0,
  JSON.stringify(st));
await expect("骑坐眼高在骑乘位上", st.cam.y > 1.8 && st.cam.y < 3.2, `cam.y=${st.cam.y}`);
// T5b 铭牌报坐骑名 (与上马的那一位一致); 乘坐中键位条收起 (条上的 WASD / Space / Shift 在座上不起作用)
const d1 = await dom();
const mountName = await page.evaluate((i) => window.__game.carousel.nameOf(i), st.mounted);
await expect("铭牌名 = 所骑坐骑名", d1.plaque === mountName, `铭牌「${d1.plaque}」/ 坐骑「${mountName}」`);
await expect("铭牌提示写明显灵木马与下乘键", /显灵木马/.test(d1.plaqueHint) && /E 随时下乘/.test(d1.plaqueHint), `「${d1.plaqueHint}」`);
await expect("乘坐中键位条收起", !d1.keysShown);
const cam0 = st.cam;
await page.waitForTimeout(2000);
const cam1 = await page.evaluate(() => {
  const c = window.__game.camera.position;
  return { x: +c.x.toFixed(2), z: +c.z.toFixed(2) };
});
const swung = Math.hypot(cam1.x - cam0.x, cam1.z - cam0.z);
await expect("随盘环游 (相机位移)", swung > 1.2, `dist=${swung.toFixed(2)}`);
await page.screenshot({ path: `${outDir}/mounted_view.png` });
await page.keyboard.press("KeyE");
await page.waitForTimeout(900);
const st2 = await page.evaluate(() => {
  const p = window.__game.player.pos;
  const d = Math.hypot(p.x - 45, p.z + 18);
  return { state: window.__game.state, y: +p.y.toFixed(3), r: +d.toFixed(2) };
});
await expect("E 下马回平台", st2.state === "walk" && Math.abs(st2.y - 0.62) < 0.03
  && Math.abs(st2.r - 7.6) < 0.8, JSON.stringify(st2));
await expect("下乘后键位条恢复", (await dom()).keysShown);

// T9 盘心打卡点: 祭坛南瓜灯 (colliders.json 的 pumpkin_carousel, 全园第 12 盏). 站在盘面内圈、面朝中柱 ——
//    这一点也在「上马」范围 (盘面 r<7.6) 里, 打卡提示必须排在前面; 收完以后提示变回「骑上…」
const poi = await page.evaluate(() => {
  const p = window.__park.pois.find((q) => q.label === "pumpkin_carousel");
  return { p, total: window.__game.interact.poiTotal(), got: window.__game.interact.collectedCount() };
});
await expect("打卡点 pumpkin_carousel 在表里, 总数 12", !!poi.p && poi.total === 12, JSON.stringify(poi));
await page.evaluate((p) => {
  const a = Math.atan2(-(p.x - 45), -(p.z + 18));          // 从中心指向南瓜灯的方位
  window.__game.player.teleport(45 + 2.4 * Math.cos(a), -18 + 2.4 * Math.sin(a), 0.62);
  window.__game.player.setView(Math.atan2(-(p.x - (45 + 2.4 * Math.cos(a))), -(p.z - (-18 + 2.4 * Math.sin(a)))), 0);
}, poi.p ?? { x: 44.28, z: -17.71 });
await page.waitForTimeout(700);
const dPoi = await dom();
await expect("祭坛旁出「收集南瓜灯（1/12）」而不是「骑上…」", dPoi.prompt.startsWith("收集南瓜灯（1/12）"), `「${dPoi.prompt}」`);
await page.screenshot({ path: `${outDir}/altar_poi_prompt.png` });
await page.keyboard.press("KeyE");
await page.waitForTimeout(500);
const got = await page.evaluate(() => ({ n: window.__game.interact.collectedCount(), total: window.__game.interact.poiTotal() }));
const dAfter = await dom();
await expect("按 E 收下祭坛南瓜灯, 星图点亮 1/12", got.n === 1 && got.total === 12 && dAfter.lit === 1, JSON.stringify({ ...got, lit: dAfter.lit }));
await expect("收完后同一位置提示变回上马", /^骑上/.test(dAfter.prompt), `「${dAfter.prompt}」`);

// T10 同款灵兽合批 (K 组): 同一种灵兽的网格换成 InstancedMesh (22 个 / 58 个实例 = 幽灵 3x6 + 象牙 3x8 + 南瓜 2x8)。
//     逐实例核对「实例的世界矩阵」与「关掉合批后原网格的世界矩阵」一致, (材质, 几何) 是同一对象; 再量 draw call 降幅。
//     全程冻结玩家控制器 (否则相机每帧被写回玩家视角) 和机台 (否则等帧的间隙盘会转)
const inst = await page.evaluate(async () => {
  const g = window.__game, c = g.carousel;
  const M = g.camera.matrix.constructor;             // Matrix4
  const pu = g.player.update, cu = c.update;
  g.player.update = () => {};
  c.update = () => {};
  const res = {};
  try {
    const aim = () => { g.camera.position.set(33.5, 2.4, -9.5); g.camera.lookAt(45, 2.2, -18); };
    const calls = async (n) => {
      const info = g.renderer.info;
      info.autoReset = false; info.reset();
      await new Promise((ok) => { let f = 0; const tick = () => (++f >= n ? ok() : requestAnimationFrame(tick)); requestAnimationFrame(tick); });
      info.autoReset = true;
      return info.render.calls / n;
    };
    aim();
    g.scene.updateMatrixWorld(true);
    const ims = [];
    // 只数木马自己的合批: v3 (2026-11-27) 摩天轮舱体也合成了 11 个 InstancedMesh (名字 FW_CabinInst_*),
    // 全场景无差别地数会把它们算进来 (33 个 / 234 个实例, 176 个「未匹配」)
    g.scene.traverse((o) => { if (o.isInstancedMesh && !o.name.startsWith("FW_")) ims.push(o); });
    res.count = c.instancedCount;
    res.found = ims.length;
    res.instances = ims.reduce((a, m) => a + m.count, 0);
    const instWorld = [];
    const tmp = new M();
    for (const im of ims) {
      for (let k = 0; k < im.count; k++) {
        im.getMatrixAt(k, tmp);
        instWorld.push(new M().multiplyMatrices(im.matrixWorld, tmp).elements.slice());
      }
    }
    aim();
    res.callsOn = await calls(8);
    c.setInstanced(false);
    aim();
    g.scene.updateMatrixWorld(true);
    const srcs = [];
    c.spinRoot.traverse((o) => { if (o.isMesh && /^CR_R[1-9]_/.test(o.name) && !/^CR_R5_/.test(o.name)) srcs.push(o); });
    res.srcMeshes = srcs.length;
    const pairKey = (o) => `${o.material.uuid}|${o.geometry.uuid}`;
    const imPairs = new Set(ims.map(pairKey));
    res.srcNotCovered = srcs.filter((o) => !imPairs.has(pairKey(o))).length;   // 原网格的 (材质, 几何) 都该在合批里
    let maxErr = 0, unmatched = 0;
    for (const e of instWorld) {
      let best = Infinity;
      for (const o of srcs) {
        const w = o.matrixWorld.elements;
        let d = 0;
        for (let i = 0; i < 16; i++) { const dd = Math.abs(w[i] - e[i]); if (dd > d) d = dd; }
        if (d < best) best = d;
      }
      if (best > 1e-4) unmatched++; else if (best > maxErr) maxErr = best;
    }
    res.maxErr = maxErr; res.unmatched = unmatched;
    res.callsOff = await calls(8);
  } finally {
    c.setInstanced(true);
    g.scene.updateMatrixWorld(true);
    g.player.update = pu;
    c.update = cu;
  }
  return JSON.parse(JSON.stringify(res));
});
await expect("同款灵兽合批生效 (22 个 InstancedMesh / 58 个实例)", inst.found === 22 && inst.instances === 58, JSON.stringify(inst));
await expect("原网格的材质与几何都在合批里", inst.srcNotCovered === 0 && inst.srcMeshes === 58, `原网格 ${inst.srcMeshes}, 未覆盖 ${inst.srcNotCovered}`);
await expect("实例世界矩阵与原网格逐个一致 (最大误差 < 1e-4)", inst.unmatched === 0 && inst.maxErr < 1e-4, `最大误差 ${inst.maxErr.toExponential(2)}, 未匹配 ${inst.unmatched}`);
await expect("合批降低 draw call (>= 30)", inst.callsOff - inst.callsOn >= 30, `关 ${inst.callsOff.toFixed(0)} -> 开 ${inst.callsOn.toFixed(0)}`);

// T5 场外远景截图 (氛围核对)
await page.evaluate(() => {
  window.__game.player.teleport(26, -4);
  window.__game.player.setView(-0.9, -0.02);
});
await page.waitForTimeout(700);
await page.screenshot({ path: `${outDir}/venue_far.png` });

console.log(errors.length ? "CONSOLE_ERRORS:\n" + errors.join("\n") : "no console errors");
console.log(fails.length ? `FAILED: ${fails.join(", ")}` : "ALL_OK");
await browser.close();
process.exit(fails.length || errors.length ? 1 : 0);
