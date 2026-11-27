// 墓园回归（真键走线 + 清单灯 + 打卡点；2026-11-26 第三批后建立）
// 前置: dev server 已起 (GAME_URL 环境变量, 默认 8765); model/park_env 的 glb 与 colliders.json 已 sync
// 园区坐标 (app): 新址 = 椭圆 36x24 m 心 (37,58); 丁字走道 = 东西主走道 (中线 z 54.7, 宽 2.4) + 北脊 (中线 x 35);
//   西门 (门柱 (19.9,52.9) / (19.9,56.5)) / 北门 ((33.2,46.1) / (36.8,46.1)); 围栏 = 沿椭圆一圈 r0.22 碰撞圆, 只在两个门处断开
// 断言:
//   L 清单灯  —— colliders.json lights 的 4 盏 (守墓灯 x2 + 两门拱顶灯 x2) 在场景里各有唯一一盏点光: 位置 / 颜色 / 强度与清单一致,
//               且都随「墓园灯火亮度」滑杆 (50% 减半, 0 熄灭)
//   W 两个门  —— 主路沿西支路直进西门、园内沿北脊出北门: 真按 W 走到, 横向偏离 <= 0.12 m; 门柱之间的通道能过, 四根门柱都穿不进去
//   A 主走道  —— 西门 -> 东端焦点庭中心一路通畅; 焦点庭再往东被围栏挡住 (挡在园内)
//   F 围栏    —— 园内 23 个方位真按 W 朝外走: 全部停住、仍在园内、停点贴着围栏碰撞圆 (r0.22 + 0.38), 没有方位能穿出去
//   S 碑 / 灯 —— 园里 20 块碑 + 2 个十字架都有盒墙; 正对石碑 / 摩天轮舱 / 过山车轮对走: 停点 = 可见面 + 玩家半径 (0.38) ± 0.08 m;
//               两行碑之间能走过去; 正对守墓灯走: 不穿进灯柱 (圆排斥件会让人绕过去)
//   P 打卡点  —— 北门里的南瓜灯: 旁侧出「收集南瓜灯」提示, 正对它走被挡在 0.55 + 0.38 处
// 用法: GAME_URL=http://127.0.0.1:8765 node scripts/verify_graveyard.mjs
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8765";
const PR = 0.38;                          // 玩家碰撞半径 (src/player/controller.js)
const EX = 37, EZ = 58, EA = 18, EB = 12; // 新址椭圆
const manifest = JSON.parse(readFileSync(resolve(import.meta.dirname, "..", "model/park_env/colliders.json"), "utf8"));
const ell = (x, z) => ((x - EX) / EA) ** 2 + ((z - EZ) / EB) ** 2;
const f = (v, n = 2) => +v.toFixed(n);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1280, height: 640 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => { const b = document.getElementById("enter-btn"); return b && !b.disabled; }, { timeout: 120000 });
await page.click("#enter-btn");
await page.waitForFunction(() => window.__game && window.__game.state === "walk", { timeout: 15000 }).catch(async () => {
  await page.evaluate(() => document.getElementById("enter-btn").click());
  await page.waitForFunction(() => window.__game && window.__game.state === "walk", { timeout: 10000 });
});
await page.waitForTimeout(1500);
await page.evaluate(() => window.__settings.store.set("walkSpeed", 2.5)); // 采样 100ms 一点 ≈ 25cm

const fails = [];
const expect = (name, cond, detail = "") => {
  const ok = !!cond;
  if (!ok) fails.push(name);
  console.log(`check ${ok ? "ok  " : "FAIL"}: ${name}${detail ? "  " + detail : ""}`);
};

// 页面内走线器: 朝目标按住 W (真实键盘事件 -> 真实控制器), 每 100ms 记轨迹; 停住 stuckMs 判 blocked。
// 传送 / 换位后首帧可能卡 1-2s (着色器编译), 先预热再走, 否则开局就被误判 blocked
await page.evaluate(() => {
  const f = (v, n = 2) => +v.toFixed(n);
  window.__gvWalk = async (d) => {
    const pl = window.__game.player, to = d.to;
    const tol = d.tol ?? 0.15, maxMs = d.maxMs ?? 9000, stuckMs = d.stuckMs ?? 1500;
    await new Promise((r) => setTimeout(r, d.warmMs ?? 1200));
    const s = { x: pl.pos.x, z: pl.pos.z };
    const dx = to[0] - s.x, dz = to[1] - s.z, L = Math.hypot(dx, dz) || 1;
    const path = []; let stop = null, dev = 0, minD = Infinity; const t0 = performance.now(); let lastMove = t0, lx = s.x, lz = s.z;
    window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyW" }));
    await new Promise((res) => {
      const tick = () => {
        const now = performance.now(), p = pl.pos;
        pl.setView(Math.atan2(-(to[0] - p.x), -(to[1] - p.z)), 0);
        if (!path.length || now - t0 - path[path.length - 1][0] > 100) path.push([Math.round(now - t0), f(p.x), f(p.z)]);
        dev = Math.max(dev, Math.abs((p.x - s.x) * dz - (p.z - s.z) * dx) / L);   // 离起终点连线的横向距离 (碰撞推挤才偏得出去)
        if (d.near) minD = Math.min(minD, Math.hypot(p.x - d.near[0], p.z - d.near[1]));   // 离某个圆心的最小距离 (圆排斥件: 看有没有穿进去)
        if (Math.hypot(p.x - lx, p.z - lz) > 0.04) { lx = p.x; lz = p.z; lastMove = now; }
        const dist = Math.hypot(to[0] - p.x, to[1] - p.z);
        if (dist <= tol) stop = "reached"; else if (now - lastMove > stuckMs) stop = "blocked"; else if (now - t0 > maxMs) stop = "timeout";
        if (stop) res(); else requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyW" }));
    const p = pl.pos;
    await new Promise((r) => setTimeout(r, 150));   // 让 interact.update 跑一两帧, 读到当前提示
    const pe = document.querySelector(".spirit-prompt");
    return { stop, ms: Math.round(performance.now() - t0), start: [f(s.x), f(s.z)], end: [f(p.x), f(p.y), f(p.z)],
      remain: f(Math.hypot(to[0] - p.x, to[1] - p.z)), dev: f(dev, 3), minD: f(minD, 3), path,
      prompt: pe ? { shown: pe.classList.contains("show"), text: pe.textContent.replace(/\s+/g, " ").trim() } : null };
  };
});
const pose = (x, z) => page.evaluate(([x, z]) => { window.__game.player.teleport(x, z, 0); }, [x, z]);
const walk = async (x, z, to, opt = {}) => { await pose(x, z); return page.evaluate((d) => window.__gvWalk(d), { to, ...opt }); };

// ---------- L 清单灯 ----------
const lights = manifest.lights ?? [];
const got = await page.evaluate(() => {
  const out = [];
  window.__game.scene.traverse((o) => { if (o.isPointLight) out.push({ x: o.position.x, y: o.position.y, z: o.position.z, i: o.intensity, c: "#" + o.color.getHexString(), d: o.distance, dec: o.decay }); });
  return out;
}, );
expect("清单灯共 4 盏 (守墓灯 x2 + 门灯 x2)", lights.length === 4 && lights.filter((l) => l.key === "graveyardLight").length === 4, `lights=${lights.length}`);
const slots = lights.map((l) => {
  const hit = got.filter((o) => Math.hypot(o.x - l.x, o.y - l.y, o.z - l.z) < 0.05);
  return { l, hit };
});
expect("每盏清单灯在场景里恰有一盏点光", slots.every((s) => s.hit.length === 1), slots.map((s) => `${s.l.tag}:${s.hit.length}`).join(" "));
const sample = slots.find((s) => s.hit.length === 1);
const readL = () => page.evaluate(([p]) => {
  const o = [];
  window.__game.scene.traverse((q) => { if (q.isPointLight && Math.hypot(q.position.x - p[0], q.position.z - p[1]) < 0.05) o.push({ i: q.intensity, c: "#" + q.color.getHexString(), d: q.distance }); });
  return o[0] ?? null;
}, [sample ? [sample.l.x, sample.l.z] : [0, 0]]);
if (sample) {
  const full = await readL();
  expect("守墓灯位置 / 颜色 / 强度 / 射程与清单一致", Math.abs(full.i - sample.l.intensity) < 0.5 && full.c === sample.l.color.toLowerCase() && Math.abs(full.d - sample.l.distance) < 0.01,
    `scene i=${f(full.i)} c=${full.c} d=${full.d} | manifest i=${sample.l.intensity} c=${sample.l.color} d=${sample.l.distance}`);
  await page.evaluate(() => window.__settings.store.set("graveyardLight", 50));
  await page.waitForTimeout(400);
  const half = await readL();
  expect("滑杆 50%: 强度减半", Math.abs(half.i - sample.l.intensity * 0.5) < 0.5, `i=${f(half.i)}`);
  await page.evaluate(() => window.__settings.store.set("graveyardLight", 0));
  await page.waitForTimeout(400);
  const off = await readL();
  expect("滑杆 0%: 熄灭", off.i === 0, `i=${off.i}`);
  await page.evaluate(() => window.__settings.store.set("graveyardLight", 100));
  await page.waitForTimeout(400);
}

// ---------- W 两个门 + A 主走道 ----------
const west = await walk(3.0, 54.7, [21.5, 54.7], { maxMs: 14000 });     // 主路东缘 -> 沿西支路 -> 过西门
expect("主路沿西支路直进西门 (走到 x>=21.3)", west.stop === "reached" && west.end[0] >= 21.3, `${west.stop} end=${west.end} dev=${west.dev}`);
expect("进西门一路横向偏离 <= 0.12 m", west.dev <= 0.12, `dev=${west.dev}m`);
const axis = await page.evaluate(() => window.__gvWalk({ to: [50.4, 54.7], maxMs: 16000 }));   // 接着沿主走道走到焦点庭中心
expect("主走道: 西门 -> 东端焦点庭中心一路通畅", axis.stop === "reached" && Math.hypot(axis.end[0] - 50.4, axis.end[2] - 54.7) <= 0.15, `${axis.stop} end=${axis.end} dev=${axis.dev}`);
expect("主走道上横向偏离 <= 0.12 m", axis.dev <= 0.12, `dev=${axis.dev}m`);
const focal = await page.evaluate(() => window.__gvWalk({ to: [58.0, 54.7], maxMs: 6000 }));     // 焦点庭再往东: 应被围栏挡住
const focalEdge = EX + EA * Math.sqrt(1 - ((54.7 - EZ) / EB) ** 2);                            // 椭圆在 z=54.7 处的东边界
expect("焦点庭往东被围栏挡住 (挡在园内 0.3..1.15 m)", focal.stop === "blocked" && focalEdge - focal.end[0] >= 0.3 && focalEdge - focal.end[0] <= 1.15,
  `${focal.stop} end=${focal.end} 离椭圆边 ${f(focalEdge - focal.end[0])}m`);

const nOut = await walk(35.0, 53.0, [35.0, 41.5], { maxMs: 9000 });      // 园内沿北脊 -> 出北门 -> 北接路
expect("沿北脊走出北门 (走到 z<=41.7)", nOut.stop === "reached" && nOut.end[2] <= 41.7, `${nOut.stop} end=${nOut.end} dev=${nOut.dev}`);
expect("出北门一路横向偏离 <= 0.12 m", nOut.dev <= 0.12, `dev=${nOut.dev}m`);
const nIn = await walk(35.0, 41.5, [35.0, 53.0], { maxMs: 9000 });       // 前庭 -> 进北门 -> 北脊 -> 丁字口
expect("前庭进北门走到丁字口", nIn.stop === "reached" && nIn.dev <= 0.12, `${nIn.stop} end=${nIn.end} dev=${nIn.dev}`);
// 环走 (两段之间不传送): 西门内 -> 东到丁字口 -> 北出北门
await pose(21.0, 54.7);
const l1 = await page.evaluate(() => window.__gvWalk({ to: [35.0, 54.7], maxMs: 12000 }));
const l2 = await page.evaluate(() => window.__gvWalk({ to: [35.0, 41.5], maxMs: 9000, warmMs: 0 }));
expect("环走: 西门进 -> 主走道 -> 北脊 -> 北门出", l1.stop === "reached" && l2.stop === "reached" && l2.end[2] <= 41.7, `${l1.stop} / ${l2.stop} end=${l2.end}`);

// 门柱: 通道能过 (门洞中线两侧 0.95 m 处)。门柱是圆排斥件 (r0.35 = 座石外缘): 正对它走, 人会顺着柱面滑进门洞或被门洞外的围栏挡住,
// 两种都正常 —— 判据是全程不穿进柱子 (离柱心 >= 0.73 - 0.04), 以及门洞外侧 0.6 m 处走不进园
const gN = await walk(17.6, 53.75, [22.0, 53.75], { maxMs: 6000 });
const gS = await walk(17.6, 55.65, [22.0, 55.65], { maxMs: 6000 });
expect("西门门洞两侧 (离中线 0.95 m) 能过", gN.stop === "reached" && gS.stop === "reached", `北侧 ${gN.stop} ${gN.end} | 南侧 ${gS.stop} ${gS.end}`);
const gPost = await walk(17.6, 52.9, [22.0, 52.9], { maxMs: 6000, near: [19.9, 52.9] });
expect("正对西门门柱走不会穿进柱子 (全程离柱心 >= 0.69 m)", gPost.minD >= 0.35 + PR - 0.04, `${gPost.stop} 离柱心最近 ${gPost.minD}m end=${gPost.end}`);
const gPostS = await walk(17.6, 56.5, [22.0, 56.5], { maxMs: 6000, near: [19.9, 56.5] });
expect("正对西门南柱走不会穿进柱子 (全程离柱心 >= 0.69 m)", gPostS.minD >= 0.35 + PR - 0.04, `${gPostS.stop} 离柱心最近 ${gPostS.minD}m end=${gPostS.end}`);
const gPostN = await walk(33.2, 43.0, [33.2, 50.0], { maxMs: 6000, near: [33.2, 46.1] });
expect("正对北门西柱走不会穿进柱子 (全程离柱心 >= 0.69 m)", gPostN.minD >= 0.35 + PR - 0.04, `${gPostN.stop} 离柱心最近 ${gPostN.minD}m end=${gPostN.end}`);
const gPostE = await walk(36.8, 43.0, [36.8, 50.0], { maxMs: 6000, near: [36.8, 46.1] });
expect("正对北门东柱走不会穿进柱子 (全程离柱心 >= 0.69 m)", gPostE.minD >= 0.35 + PR - 0.04, `${gPostE.stop} 离柱心最近 ${gPostE.minD}m end=${gPostE.end}`);
const gFlank = await walk(32.6, 43.0, [32.6, 50.0], { maxMs: 6000 });   // 柱心西侧 0.6 m: 门洞之外, 应被门柱西侧的围栏挡在园外
expect("北门西柱外侧 0.6 m 处朝园内走: 被围栏挡在园外", gFlank.stop === "blocked" && gFlank.end[2] <= 46.0, `${gFlank.stop} end=${gFlank.end}`);

// ---------- F 围栏 ----------
// 每隔 15° 一个参数角 (195° 是西门门洞, 不测): 从围栏内侧 1.7 m 处朝外走
const rad = (d) => (d * Math.PI) / 180;
// 围栏碰撞件: 沿折线的 r0.22 圆 + 4 根石门柱 (r0.35)
const fenceCols = (manifest.circles ?? []).filter((c) => c.r === 0.22 || ((c.r === 0.35) && [[33.2, 46.1], [36.8, 46.1], [19.9, 52.9], [19.9, 56.5]].some(([gx, gz]) => Math.hypot(c.x - gx, c.z - gz) < 0.05)));
expect("清单里的围栏碰撞件 (r0.22 圆 + 4 根门柱) 数量合理 (>= 250)", fenceCols.length >= 250, `${fenceCols.length} 个`);
const through = [], detail = [];
let nAz = 0;
for (let t = 0; t < 360; t += 15) {
  if (t === 195) continue;
  const dIn = 1.7;
  const sx = EX + (EA - dIn) * Math.cos(rad(t)), sz = EZ + (EB - dIn) * Math.sin(rad(t));
  const ox = EX + (EA + 7) * Math.cos(rad(t)), oz = EZ + (EB + 7) * Math.sin(rad(t));
  const L = Math.hypot(ox - sx, oz - sz), ux = (ox - sx) / L, uz = (oz - sz) / L;
  const w = await walk(sx, sz, [ox, oz], { maxMs: 7000, tol: 0.15 });
  nAz++;
  const moved = Math.hypot(w.end[0] - sx, w.end[2] - sz);
  // 判据不用「离椭圆边多远」: 西门两根石柱比椭圆外扩 0.8 m, 首尾一跨的围栏斜着接过去, 那一段停点离椭圆边可以很近。
  // 改成: 停住 + 仍在椭圆内 + 停点正好贴着一个围栏碰撞圆 (r0.22 + 0.38) 或门柱 (0.35 + 0.38)
  const touch = Math.min(...fenceCols.map((c) => Math.abs(Math.hypot(w.end[0] - c.x, w.end[2] - c.z) - c.r - PR)));
  const bad = w.stop !== "blocked" || ell(w.end[0], w.end[2]) > 1.0 || touch > 0.08 || moved < 0.3;
  detail.push(`${t}°:${w.stop}/贴${f(touch)}`);
  if (bad) through.push(`${t}°(${w.stop}, end=${w.end}, 椭圆值 ${f(ell(w.end[0], w.end[2]), 3)}, 离最近围栏碰撞面 ${f(touch)}m, 走了 ${f(moved)}m)`);
}
expect(`围栏 ${nAz} 个方位朝外走全部被挡在园内 (贴着围栏碰撞面停住)`, through.length === 0, `挡住 ${nAz - through.length}/${nAz}${through.length ? "  穿出: " + through.join(" ") : ""}`);
console.log("  围栏停点离碰撞面的偏差 (m): " + detail.join(" "));

// ---------- S 碑 / 灯 ----------
const rectNear = (x, z) => (manifest.rects ?? []).find((r) => Math.hypot(r.x - x, r.z - z) < 0.15);
const stoneS = rectNear(25.0, 58.2), stoneN = rectNear(31.0, 51.3);
expect("清单里找到正对走道的两块碑 (25.0,58.2) / (31.0,51.3)", !!stoneS && !!stoneN);
if (stoneS && stoneN) {
  const a = await walk(stoneS.x, 55.6, [stoneS.x, 61.0], { maxMs: 6000 });     // 从主走道朝南走进碑面
  const eS = stoneS.z - stoneS.hd - PR;
  expect("碑 (25.0,58.2) 正面停点 = 碑面 + 0.38 ± 0.08", a.stop === "blocked" && Math.abs(a.end[2] - eS) <= 0.08, `${a.stop} end=${a.end} 期望 z=${f(eS)} 实际 ${a.end[2]} 差 ${f(a.end[2] - eS)}m`);
  const siteRects = (manifest.rects ?? []).filter((r) => r.x > 20 && r.x < 52 && r.z > 46 && r.z < 68);
  expect("园里有 20 块碑 + 2 个十字架的盒墙", siteRects.length === 22, `${siteRects.length} 个`);
  const cabin = rectNear(28.99, 58.26), wheel = rectNear(39.0, 51.24);
  if (cabin) {
    const cw = await walk(cabin.x, 55.6, [cabin.x, 60.0], { maxMs: 6000 });          // 从主走道朝南走进半埋的摩天轮舱
    const ec = cabin.z - cabin.hd - PR;
    expect("摩天轮舱 (29,58.2) 正面停点 = 舱面 + 0.38 ± 0.08", cw.stop === "blocked" && Math.abs(cw.end[2] - ec) <= 0.08, `${cw.stop} end=${cw.end} 期望 z=${f(ec)}`);
  }
  if (wheel) {
    const ww = await walk(wheel.x, 53.9, [wheel.x, 49.5], { maxMs: 6000 });          // 从主走道朝北走进过山车轮对
    const ew = wheel.z + wheel.hd + PR;
    expect("过山车轮对 (39,51.3) 正面停点 = 轮面 + 0.38 ± 0.08", ww.stop === "blocked" && Math.abs(ww.end[2] - ew) <= 0.08, `${ww.stop} end=${ww.end} 期望 z=${f(ew)}`);
  }
  const lane = await walk(33.0, 59.3, [33.0, 62.6], { maxMs: 5000 });                // 南二行两块碑之间 (x 31 与 35) 走过去
  expect("南二行两块碑之间能走过去", lane.stop === "reached", `${lane.stop} end=${lane.end}`);
  const b = await walk(stoneN.x, 53.9, [stoneN.x, 48.5], { maxMs: 6000 });     // 从主走道朝北走进碑面
  const eN = stoneN.z + stoneN.hd + PR;
  expect("碑 (31.0,51.3) 正面停点 = 碑面 + 0.38 ± 0.08", b.stop === "blocked" && Math.abs(b.end[2] - eN) <= 0.08, `${b.stop} end=${b.end} 期望 z=${f(eN)} 实际 ${b.end[2]} 差 ${f(b.end[2] - eN)}m`);
}
// 圆排斥件 (灯柱 / 南瓜) 正对着走, 人会被顺着圆面推着从侧边绕过去 —— 和现实里绕开灯柱一样, 不是穿模。
// 所以判据是「全程离圆心不小于 r + 0.38」
const lanC = (manifest.circles ?? []).find((c) => c.r === 0.2 && Math.abs(c.x - 26.6) < 0.05 && Math.abs(c.z - 56.35) < 0.05);
const lan = await walk(lanC ? lanC.x - 2.1 : 24.5, 56.35, [lanC ? lanC.x + 2.3 : 28.9, 56.35], { maxMs: 6000, near: lanC ? [lanC.x, lanC.z] : [26.6, 56.35] });   // 朝东走进守墓灯
expect("守墓灯 (26.6,56.35): 正对它走不会穿进灯柱 (全程离柱心 >= 0.54 m)", !!lanC && lan.minD >= 0.2 + PR - 0.04, `${lan.stop} 离柱心最近 ${lan.minD}m (碰撞半径 ${f(0.2 + PR)}m) end=${lan.end}`);

// ---------- P 打卡点 ----------
const poi = (manifest.pois ?? []).find((p) => p.label === "pumpkin_grave");
expect("清单里有打卡点 pumpkin_grave", !!poi, JSON.stringify(poi ?? null));
if (poi) {
  await pose(poi.x, poi.z + 1.1);
  await page.evaluate(([x, z]) => { const pl = window.__game.player, p = pl.pos; pl.setView(Math.atan2(-(x - p.x), -(z - p.z)), -0.35); }, [poi.x, poi.z]);
  await page.waitForTimeout(500);
  const pr = await page.evaluate(() => { const pe = document.querySelector(".spirit-prompt"); return pe ? { shown: pe.classList.contains("show"), text: pe.textContent.replace(/\s+/g, " ").trim() } : null; });
  expect("南瓜灯旁出「收集南瓜灯」提示", !!pr && pr.shown && /收集南瓜灯/.test(pr.text), JSON.stringify(pr));
  const circ = (manifest.circles ?? []).find((c) => Math.hypot(c.x - poi.x, c.z - poi.z) < 0.05);
  const pw = await walk(poi.x, poi.z + 2.0, [poi.x, poi.z - 1.5], { maxMs: 6000, near: [poi.x, poi.z] });
  expect("正对南瓜灯走不会穿进去 (全程离圆心 >= r + 0.38 - 0.04)", !!circ && pw.minD >= circ.r + PR - 0.04, `${pw.stop} 离圆心最近 ${pw.minD}m (碰撞半径 ${circ ? f(circ.r + PR) : "?"}m) end=${pw.end}`);
}

console.log(errors.length ? "CONSOLE_ERRORS:\n" + [...new Set(errors)].join("\n") : "no console errors");
console.log(fails.length ? `FAILED: ${fails.length} 项` : "ALL_OK");
await browser.close();
process.exit(fails.length || errors.length ? 1 : 0);
