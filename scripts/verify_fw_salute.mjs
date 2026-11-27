// 地标礼花验证 (2026-11-25): 三处地标炸点 (缠魂塔环廊 / 摩天轮顶舱 / 过山车提升顶) 的端到端取证
//   A 注册与资产   7 座发射架 / 3 处炸点 / 新垂柳塔 = 园内 L4 同款 / 炮口朝向 / 碰撞 / F 点射 / 地面常规弹不变
//   B 弹道         每处实放一发量落点与飞行时长 / 滑杆映射 / 齐射负载下落点不变 / 升空声参数
//   C 塔顶触发     在塔顶判定 / 登顶 2.5s 后首发 / 驻留每 18s 一发 / 离开再回来不连放
//   D 乘坐同步     摩天轮所乘舱到顶时炸 (连续两圈) / 过山车头车到平顶时炸 (含再上膛)
//   E 开关与编排   开关关 = 全停 / 常规秀 50% 穿插 / 终曲三处各一发
//   F 粒子池与帧率 终曲不溢出; 4K@150% (用户同款) 帧间隔
//   G 设置面板     滑杆与开关走 UI 路径生效
// 用法: GAME_URL=http://127.0.0.1:8767 node scripts/verify_fw_salute.mjs [输出目录]   (需 dev 服务器在跑; 8765 常是正在玩的实例)
//       ONLY=A,B,C 单块重跑; LONG=0 跳过摩天轮第二圈
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { installTools } from "./lib_tower_shots.mjs";

const outDir = process.argv[2] ?? "shots/fw_salute";
const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8767";
const ONLY = new Set((process.env.ONLY ?? "A,B,C,D,E,F,G").split(","));
const LONG = process.env.LONG !== "0";
mkdirSync(outDir, { recursive: true });

const results = [];
const check = (name, ok, detail = "") => {
  results.push(!!ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
};
const fstat = (dt) => {
  const s = [...dt].sort((a, b) => a - b);
  return { avg: dt.reduce((a, b) => a + b, 0) / dt.length, p95: s[Math.floor(s.length * 0.95)], max: s[s.length - 1], n: dt.length };
};
// 逐帧间隔抽样 (rAF), 可选每 100ms 记一次存活粒子峰值
const frames = (pg, ms, aliveToo = false) => pg.evaluate(([ms, aliveToo]) => new Promise((resolve) => {
  const dt = [];
  let maxAlive = 0, last = performance.now();
  const t0 = last;
  const tick = (now) => {
    dt.push(now - last);
    last = now;
    if (aliveToo) maxAlive = Math.max(maxAlive, window.__game.fireworks.stats().alive); // 逐帧采样, 不漏帧间尖峰
    if (now - t0 < ms) requestAnimationFrame(tick);
    else resolve({ dt, maxAlive });
  };
  requestAnimationFrame(tick);
}), [ms, aliveToo]);

const browser = await chromium.launch({ channel: "chrome" });
const errors = [];
async function openPage(ctxOpts) {
  const ctx = await browser.newContext(ctxOpts);
  const pg = await ctx.newPage();
  pg.on("console", (m) => { if (m.type() === "error" && !m.text().includes("favicon")) errors.push(m.text()); });
  pg.on("pageerror", (e) => errors.push(String(e)));
  await pg.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await pg.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 120000 });
  await pg.click("#enter-btn");
  await pg.waitForFunction(() => window.__game && window.__game.state === "walk", { timeout: 8000 }).catch(async () => {
    await pg.evaluate(() => document.getElementById("enter-btn").click());
    await pg.waitForFunction(() => window.__game && window.__game.state === "walk", { timeout: 8000 });
  });
  await pg.waitForTimeout(1500);
  await pg.evaluate(() => window.__settings.store.set("fireworkPeriod", 0)); // 关自动秀, 逐项取证
  return pg;
}

const page = await openPage({ viewport: { width: 1280, height: 720 } });
const sleep = (ms) => page.waitForTimeout(ms);
const store = (k, v) => page.evaluate(([k, v]) => window.__settings.store.set(k, v), [k, v]);
const ev = () => page.evaluate(() => window.__ev);
const waitForEv = async (pred, timeout, from = 0) => {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const hit = (await ev()).find((r, i) => i >= from && pred(r));
    if (hit) return hit;
    await sleep(50);
  }
  return null;
};
const drain = async (timeout = 30000) => { // 等队列 / 壳体 / 粒子全部清空
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const s = await page.evaluate(() => window.__game.fireworks.stats());
    if (s.pending === 0 && s.shells === 0 && s.alive === 0) return true;
    await sleep(150);
  }
  return false;
};
const snap = async (name, n = 1, gap = 450) => {
  for (let i = 0; i < n; i++) {
    await page.screenshot({ path: `${outDir}/${name}${i ? `_late${i}` : ""}.png` });
    if (i < n - 1) await sleep(gap);
  }
};
const distTo = (e, x, z) => Math.hypot(e.x - x, e.z - z);

await installTools(page);
await page.evaluate(() => {
  const g = window.__game;
  const hub = g.ferris.wheelRoot.getWorldPosition(g.ferris.wheelRoot.position.clone());
  const c0 = g.ferris.cabinRoots[0].getWorldPosition(g.ferris.cabinRoots[0].position.clone());
  const R = Math.hypot(c0.x - hub.x, c0.y - hub.y);
  // 爆裂钩子: 事件坐标之外, 同帧记下乘坐状态 (同步误差要和爆裂同一帧比, 跨帧读数会带上设施自身的运动)
  window.__ev = [];
  window.__hub = hub;
  g.fireworks.onBurst = (e) => {
    const rec = { ...e, perf: performance.now() };
    if (e.aid === "wheel" && g.ferris.state.riding) {
      const p = g.ferris.getRideFrame().pos;     // 爆裂这一帧所乘舱根的世界坐标
      // 舱位自正上方起的有符号角 (轮轴 +z, 顶点处舱向 -x 运动 → 过顶后 dx<0); arc = 离顶弧长, + = 已过顶
      rec.arc = -Math.atan2(p.x - hub.x, p.y - hub.y) * R;
      rec.cabTop = p.y - (hub.y + R);
    }
    if (e.aid === "coaster" && g.coaster.state.session?.active) rec.s = g.coaster.state.s;
    window.__ev.push(rec);
  };
  // 编排用: 把 Math.random 钉成定值再排一轮秀 —— 常规秀「50% 概率补一发」要确定性地验证
  window.__showWithRand = (v) => {
    const orig = Math.random;
    Math.random = () => v;
    try { window.__game.fireworks.debugShow(); } finally { Math.random = orig; }
  };
});

// ---------------------------------------------------------------------------------------------- A --
const info = await page.evaluate(() => ({
  launchers: window.__game.fireworks.getLaunchers(),
  anchors: window.__game.fireworks.getAnchors().map((a) => ({ ...a })),
  crest: window.__game.coaster.crest,
  place: window.__park.tower?.place, lift: window.__park.lift,
  nCircles: window.__park.circles.length, nLaunchers: window.__park.launchers.length,
}));
const L = info.launchers;
const A = Object.fromEntries(info.anchors.map((a) => [a.id, a]));
const cr = info.crest;
const l7 = L.find((l) => l.id === "L7");

if (ONLY.has("A")) {
  check("A1 发射架 7 座: 地面 6 站 + 过山车顶旁垂柳塔 L7 (B 型, app (46,-125), 管口高 2.92)",
    L.length === 7 && info.nLaunchers === 7 && l7 && l7.kind === "B" && Math.abs(l7.x - 46) < 0.01 && Math.abs(l7.z + 125) < 0.01 && l7.mz === 2.92,
    L.map((l) => `${l.id}${l.kind}`).join(" "));
  const exp = {
    tower: [info.place.x + 16, info.place.z, info.lift.zTop + info.lift.floorThk + 1.65],
    wheel: [0, 18, 35.36],   // 顶舱眼位 = 轮心 20.41 + R 16 + 舱地板顶 -2.70 + 站姿眼高 1.65 (v2 舱是 35.16)
    coaster: [cr.x + cr.tx * 16, cr.z + cr.tz * 16, cr.y + cr.eye],
  };
  for (const id of Object.keys(exp)) {
    const a = A[id];
    check(`A2 ${a?.label ?? id}: 炸点 (${exp[id].map((v) => v.toFixed(2)).join(", ")}), 眼位 ${exp[id][2].toFixed(2)}m`,
      !!a && Math.hypot(a.x - exp[id][0], a.z - exp[id][1]) < 0.02 && Math.abs(a.eye - exp[id][2]) < 0.02,
      a ? `实测 (${a.x.toFixed(2)}, ${a.z.toFixed(2)}) 眼位 ${a.eye.toFixed(2)}m, 由 ${L[a.lid].id} 发射` : "未登记");
  }
  check("A2b 提升平顶 (crest): s≈90.25, app (33.33, 25.08, -120.96), 前进方向 (0.643, -0.766), 链速 3.2",
    Math.abs(cr.s - 90.25) < 0.3 && Math.abs(cr.x - 33.33) < 0.02 && Math.abs(cr.z + 120.96) < 0.02 && Math.abs(cr.tx - 0.643) < 0.002 && Math.abs(cr.tz + 0.766) < 0.002 && cr.v === 3.2,
    `s=${cr.s} (${cr.x.toFixed(2)}, ${cr.y}, ${cr.z.toFixed(2)}) t=(${cr.tx.toFixed(3)}, ${cr.tz.toFixed(3)}) v=${cr.v}`);
  // 新垂柳塔 vs 园内同款 L4: 半径 2m 内逐材质顶点数 (L4 = park_env.glb 合并网格里的一座; L7 = 新 glb)
  const cmp = await page.evaluate(() => {
    const scan = (cx, cz) => {
      const m = {};
      for (const c of window.__tl.vertexScan(window.__game.scene, cx, cz, 2.0, 1.0)) {
        const k = c.name.replace(/^PE_PE_|^FS_/, "");
        m[k] = (m[k] || 0) + c.verts;
      }
      return m;
    };
    return { L4: scan(-55, -30), L7: scan(46, -125) };
  });
  const mats = Object.keys(cmp.L7);
  check("A3 新垂柳塔 = 园内同款 L4 (半径 2m 内逐材质顶点数全同)", mats.length === 9 && mats.every((k) => cmp.L4[k] === cmp.L7[k]),
    mats.map((k) => `${k}:${cmp.L7[k]}`).join(" "));
  // 表里 dx/dz 保留三位小数 (与 colliders.json 同口径), 比夹角前要先归一化
  const adx = A.coaster.x - l7.x, adz = A.coaster.z - l7.z, adn = Math.hypot(adx, adz), l7n = Math.hypot(l7.dx, l7.dz);
  const aimAng = Math.acos(Math.min(1, (adx / adn) * (l7.dx / l7n) + (adz / adn) * (l7.dz / l7n))) * 180 / Math.PI;
  check("A4 L7 炮口朝向与过山车顶炸点一致 (夹角 < 1°)", aimAng < 1, `夹角 ${aimAng.toFixed(2)}°, 水平距 ${adn.toFixed(2)}m`);
  // 碰撞: 发射架正南 3.6m 起步朝它走, 应停在 阻挡圆 0.95 + 玩家半径 0.38 之外; 再退开不应被卡住
  await page.evaluate(() => { const p = window.__game.player; p.teleport(46, -121.4); p.setView(0, 0); });
  await sleep(600);
  await page.keyboard.down("KeyW"); await sleep(2200); await page.keyboard.up("KeyW");
  const d1 = await page.evaluate(() => { const p = window.__game.player.pos; return Math.hypot(p.x - 46, p.z + 125); });
  check("A5 新发射架有碰撞: 朝它走 2.2s 后停在阻挡圆外 (1.28–1.9m)", d1 >= 1.28 && d1 <= 1.9, `停在高 ${d1.toFixed(2)}m`);
  await page.keyboard.down("KeyS"); await sleep(800); await page.keyboard.up("KeyS");
  const d2 = await page.evaluate(() => { const p = window.__game.player.pos; return Math.hypot(p.x - 46, p.z + 125); });
  check("A5b 退开不被卡住", d2 > 2.4, `退到 ${d2.toFixed(2)}m`);
  // F 点射: 就近提示 + 常规弹 (非定向) 从 L7 出膛
  await page.evaluate(() => { const p = window.__game.player; p.teleport(46, -122.6); p.setView(0, 0.5); });
  await sleep(700);
  const prompt = await page.evaluate(() => document.querySelector(".spirit-prompt")?.innerText ?? "");
  check("A6 新发射架就近出「垂柳塔 · F 点射」提示", /垂柳塔/.test(prompt) && /F/.test(prompt), JSON.stringify(prompt));
  let m0 = (await ev()).length;
  await page.keyboard.press("KeyF");
  const eF = await waitForEv((r) => !r.aimed, 8000, m0);
  check("A6b 按 F 从 L7 打出常规弹 (垂柳, 非定向, 朝炸点方向漂移 ≤16m)", !!eF && eF.kind === "B" && distTo(eF, l7.x, l7.z) <= 16,
    eF ? `${eF.kind} 炸于 (${eF.x.toFixed(1)}, ${eF.y.toFixed(1)}, ${eF.z.toFixed(1)}), 离 L7 ${distTo(eF, l7.x, l7.z).toFixed(1)}m` : "未爆");
  // 地面常规弹不变: L1 (牡丹) F 点射仍是竖直上升、55m 附近炸
  await drain();
  await page.evaluate(() => { const p = window.__game.player; p.teleport(23.3, 23.3); p.setView(0, 0.8); });
  await sleep(700);
  m0 = (await ev()).length;
  await page.keyboard.press("KeyF");
  const eG = await waitForEv((r) => !r.aimed, 8000, m0);
  // 炸点标称 = 管口高 (L1 mz 1.63) + 设置高度 55: 常规弹的 v0y 是按「管口以上的升高」反解的 (fireworks.js launchShell),
  // 每发再叠 ±8% 自然变化, 所以实际炸点落在 52.1..61.0 m。旧写法按 55.42 ± 4.6 判, 高端的约 11% 发数会假失败
  // (2026-11-26 复现: 4 发里 2 发落在 60.1 / 60.5)。窗口改成覆盖整个设计范围: 标称 56.63 ± (8% + 0.6 m 余量)
  const hOk = eG && eG.kind === "A" && Math.abs(eG.y - (1.63 + 55)) <= 55 * 0.08 + 0.6 && distTo(eG, 22, 22) <= 15.5;
  check("A7 地面常规弹不变: L1 牡丹仍在 55m (±8%) 附近炸、朝园心漂移", !!hOk,
    eG ? `${eG.kind} 炸于 y=${eG.y.toFixed(1)}m, 离 L1 ${distTo(eG, 22, 22).toFixed(1)}m` : "未爆");
  await drain();
  await page.evaluate(() => { // 新垂柳塔外观: 玩家视角近景
    const p = window.__game.player;
    p.teleport(47.9, -122.3);
    p.setView(Math.atan2(-(46 - 47.9), -(-125 + 122.3)), 0.12);
  });
  await sleep(600);
  await snap("A_launcher_L7_close");
}

// ---------------------------------------------------------------------------------------------- B --
async function fireAndMeasure(aid) {
  await drain();
  const m = (await ev()).length;
  const tCall = await page.evaluate((id) => { const t = performance.now(); window.__game.fireworks.salute(id); return t; }, aid);
  const e = await waitForEv((r) => r.aimed && r.aid === aid, 9000, m);
  // 交叉核对: 爆裂后首批粒子的质心 (独立于事件坐标)
  const cen = await page.evaluate(() => {
    let n = 0, x = 0, y = 0, z = 0;
    window.__game.scene.traverse((o) => {
      if (!o.isPoints || !o.geometry?.attributes?.aColor) return;
      const c = o.geometry.attributes.aColor.array, p = o.geometry.attributes.position.array;
      for (let i = 0; i < c.length; i += 3) {
        if (c[i] + c[i + 1] + c[i + 2] > 0.01) { n++; x += p[i]; y += p[i + 1]; z += p[i + 2]; }
      }
    });
    return n ? { n, x: x / n, y: y / n, z: z / n } : null;
  });
  const f = await page.evaluate((id) => window.__game.fireworks.saluteFlight(id), aid);
  return { e, f, dt: e ? e.t - tCall / 1000 : NaN, cen };
}
if (ONLY.has("B")) {
  await store("fireworkSalute", true);
  await store("fireworkSaluteHeight", 0);
  for (const a of info.anchors) {
    const { e, f, dt, cen } = await fireAndMeasure(a.id);
    const lat = e ? Math.hypot(e.x - f.x, e.z - f.z) : NaN;
    const dy = e ? e.y - f.y : NaN;
    check(`B1 ${a.label}: 炸点落在目标处 (水平 ≤1.1m / 高度 ≤2%)`, !!e && lat <= 1.1 && Math.abs(dy) <= 0.02 * f.y + 0.05,
      e ? `目标 (${f.x.toFixed(2)}, ${f.y.toFixed(2)}, ${f.z.toFixed(2)}) 实炸 (${e.x.toFixed(2)}, ${e.y.toFixed(2)}, ${e.z.toFixed(2)})` : "未爆");
    check(`B2 ${a.label}: 飞行时长 = T ${f.T.toFixed(2)}s (入列 0.02s 后出膛, ±0.1s)`, !!e && Math.abs(dt - 0.02 - f.T) <= 0.1, e ? `实测 ${dt.toFixed(2)}s` : "未爆");
    check(`B3 ${a.label}: 爆裂后首批粒子质心与事件坐标一致 (≤1.5m)`, !!e && !!cen && Math.hypot(cen.x - e.x, cen.z - e.z) <= 1.5 && Math.abs(cen.y - e.y) <= 1.5,
      cen ? `${cen.n} 颗, 质心 (${cen.x.toFixed(2)}, ${cen.y.toFixed(2)}, ${cen.z.toFixed(2)})` : "无粒子");
  }
  // 滑杆映射: +40 三处都量, -20 量塔顶
  for (const [dy, ids] of [[40, ["tower", "wheel", "coaster"]], [-20, ["tower"]]]) {
    await store("fireworkSaluteHeight", dy);
    for (const id of ids) {
      const a = A[id];
      const { e, f } = await fireAndMeasure(id);
      const mapOk = Math.abs(f.y - (a.eye + dy)) < 1e-6;
      check(`B4 滑杆 ${dy > 0 ? "+" : ""}${dy}m · ${a.label}: 炸点 = 眼位 ${a.eye.toFixed(2)} ${dy > 0 ? "+" : "−"} ${Math.abs(dy)} = ${f.y.toFixed(2)}m (±2%)`,
        mapOk && !!e && Math.abs(e.y - (a.eye + dy)) <= 0.02 * f.y + 0.05, e ? `实炸 y=${e.y.toFixed(2)}m, T=${f.T.toFixed(2)}s` : "未爆");
    }
  }
  await store("fireworkSaluteHeight", 0);
  // 齐射负载下落点不变: 7 站 × 9 轮齐射进行到一半时打一发塔顶礼花
  await drain();
  let m0 = (await ev()).length;
  const idleFr = fstat((await frames(page, 1500)).dt);
  let saluteRet = null;
  const busyP = frames(page, 7500);
  for (let k = 0; k < 9; k++) {
    if (k === 4) saluteRet = await page.evaluate(() => window.__game.fireworks.salute("tower"));
    await page.evaluate(() => window.__game.fireworks.getLaunchers().forEach((_, i) => window.__game.fireworks.fire(i)));
    await sleep(750);
  }
  const busyFr = fstat((await busyP).dt);
  const eL = await waitForEv((r) => r.aimed && r.aid === "tower", 6000, m0);
  const fL = await page.evaluate(() => window.__game.fireworks.saluteFlight("tower"));
  const latL = eL ? Math.hypot(eL.x - fL.x, eL.z - fL.z) : NaN;
  check("B5 齐射负载下塔顶礼花落点不变 (水平 ≤1.1m / 高度 ≤2%)", !!eL && latL <= 1.1 && Math.abs(eL.y - fL.y) <= 0.02 * fL.y + 0.05,
    eL ? `水平偏差 ${latL.toFixed(2)}m 高度偏差 ${(eL.y - fL.y).toFixed(2)}m` : `未爆 (salute()=${saluteRet})`);
  console.log(`      帧间隔 空闲 avg ${idleFr.avg.toFixed(1)}ms → 齐射 avg ${busyFr.avg.toFixed(1)}ms / p95 ${busyFr.p95.toFixed(1)}ms (负载确实更重: ${busyFr.avg > idleFr.avg ? "是" : "否"})`);
  await drain();
}

// ---------------------------------------------------------------------------------------------- C --
// 塔顶礼花的间隔从「该炸点上一发」起算 (前面 B5 刚打过一发塔顶, 所以期望时刻要把上一发算进去):
//   每次登顶的第一发 = max(登顶 + 2.5s, 上一发 + 6s); 驻留期间之后每 18s 一发
if (ONLY.has("C")) {
  await store("fireworkSalute", true);
  await store("fireworkSaluteHeight", 0);
  const T = await page.evaluate(() => window.__game.fireworks.saluteFlight("tower").T);
  const onTop = () => page.evaluate(() => window.__game.fwDirector.state.onTop);
  const lastLaunch = () => page.evaluate(() => window.__game.fireworks.lastSalute("tower"));
  const TOWER_SPOT = [21.6, -28.7]; // 环廊东侧长椅旁的空位 (避开长椅与栏杆柱), 脚高 40.1 → 落到环廊地面 40
  const gotoTop = () => page.evaluate(([x, z]) => {
    const p = window.__game.player;
    p.teleport(x, z, 40.1);
    p.setView(Math.atan2(-(33.5 - x), -(-30.5 - z)), 0); // 朝炸点平视
    return performance.now();
  }, TOWER_SPOT);
  const leaveTop = () => page.evaluate(() => window.__game.player.teleport(42, -30)); // 东草坪
  await page.evaluate(() => window.__game.player.teleport(22, -30.5)); // 塔底地面 (环廊正下方)
  await sleep(700);
  check("C1 塔底地面 (脚高 0) 不算在顶", (await onTop()) === false);
  await page.evaluate(() => window.__game.player.teleport(17.5, -30.5)); // 底层轿厢里 (轿底 0.06 + 地板 0.08)
  await sleep(900);
  const footY = await page.evaluate(() => +window.__game.player.pos.y.toFixed(2));
  check("C1b 底层轿厢里 (脚高 0.14) 不算在顶", (await onTop()) === false, `脚高 ${footY}`);
  // ---- 第一次登顶 ----
  await drain();
  const last0 = await lastLaunch();
  const tA = await gotoTop();
  await sleep(600);
  check("C2 站上环廊算在顶", (await onTop()) === true);
  let m0 = (await ev()).length;
  const e1 = await waitForEv((r) => r.aimed && r.aid === "tower", 16000, m0);
  await snap("C_tower_top", 3, 450);
  const exp1 = Math.max(tA / 1000 + 2.5, last0 + 6) + 0.02 + T;
  check("C3 登顶后 2.5s 放第一发 (6s 内刚有过一发则顺延到上一发 + 6s): 爆裂时刻 ±0.4s",
    !!e1 && Math.abs(e1.t - exp1) <= 0.4,
    e1 ? `登顶后 ${(e1.t - tA / 1000).toFixed(2)}s 爆裂 (期望 ${(exp1 - tA / 1000).toFixed(2)}s)` : "未爆");
  const m1 = (await ev()).length;
  const e2 = await waitForEv((r) => r.aimed && r.aid === "tower", 26000, m1);
  check("C4 驻留期间第二发在第一发爆裂后 18s (±0.4s)", !!e1 && !!e2 && Math.abs((e2.t - e1.t) - 18) <= 0.4,
    e1 && e2 ? `间隔 ${(e2.t - e1.t).toFixed(2)}s` : "未爆");
  // ---- 离开 1.5s 再回来: 仍放一发, 时刻 = max(回顶 + 2.5s, 上一发 + 6s) ----
  await leaveTop();
  await sleep(1500);
  check("C5 走下塔后不算在顶", (await onTop()) === false);
  const last2 = await lastLaunch();
  const tR = await gotoTop();
  m0 = (await ev()).length;
  const e3 = await waitForEv((r) => r.aimed && r.aid === "tower", 16000, m0);
  const exp3 = Math.max(tR / 1000 + 2.5, last2 + 6) + 0.02 + T;
  check("C6 离开 1.5s 后回塔顶: 再放一发, 时刻 = max(回顶 + 2.5s, 上一发 + 6s) (±0.4s)",
    !!e3 && Math.abs(e3.t - exp3) <= 0.4,
    e3 && e2 ? `回顶后 ${(e3.t - tR / 1000).toFixed(2)}s 爆裂, 距上一发爆裂 ${(e3.t - e2.t).toFixed(2)}s` : "未爆");
  // ---- 紧接着 (0.3s) 再进出一次: 发射时刻仍不早于上一发 + 6s (反复进出不会连放) ----
  await leaveTop();
  await sleep(300);
  const last3 = await lastLaunch();
  const tR2 = await gotoTop();
  m0 = (await ev()).length;
  const e4 = await waitForEv((r) => r.aimed && r.aid === "tower", 16000, m0);
  const last4 = await lastLaunch();
  const exp4 = Math.max(tR2 / 1000 + 2.5, last3 + 6) + 0.02 + T;
  check("C7 紧接着再进出一次: 发射不早于上一发 + 6s, 爆裂时刻 = max(回顶 + 2.5s, 上一发 + 6s) (±0.4s)",
    !!e4 && Math.abs(e4.t - exp4) <= 0.4 && last4 - last3 >= 5.95,
    e4 ? `两次发射间隔 ${(last4 - last3).toFixed(2)}s, 爆裂间隔 ${(e4.t - e3.t).toFixed(2)}s` : "未爆");
  await leaveTop(); // 后面编排统计 (E) 需要导演空闲: 人下塔
  await sleep(600);
  check("C8 人已下塔 (导演不再放塔顶礼花)", (await onTop()) === false);
  await drain();
}

// ---------------------------------------------------------------------------------------------- E --
if (ONLY.has("E")) {
  await drain();
  const q = () => page.evaluate(() => window.__game.fireworks.stats().salutesQueued);
  await store("fireworkSalute", false);
  const r = await page.evaluate(() => ["tower", "wheel", "coaster"].map((id) => window.__game.fireworks.salute(id)));
  check("E1 开关关: 三处 salute() 全部拒绝", r.every((x) => x === false), JSON.stringify(r));
  const deltas = [];
  for (let k = 0; k < 4; k++) { // 第 4 轮是终曲 (每 4 轮一次)
    const q0 = await q();
    await page.evaluate(() => window.__showWithRand(0.49));
    deltas.push((await q()) - q0);
    await drain(40000);
  }
  check("E2 开关关: 3 轮常规秀 + 1 轮终曲都不排地标礼花", deltas.every((d) => d === 0), `每轮排入 ${deltas.join("/")} 发`);
  await store("fireworkSalute", true);
  const row = [];
  for (const rnd of [0.51, 0.49, 0.51]) { // 常规秀: 随机数 0.51 → 不补; 0.49 → 补 1 发
    const q0 = await q();
    const m0 = (await ev()).length;
    await page.evaluate((v) => window.__showWithRand(v), rnd);
    await drain(40000);
    const aimed = (await ev()).filter((x, i) => i >= m0 && x.aimed);
    row.push({ queued: (await q()) - q0, bursts: aimed.length, aid: aimed.map((x) => x.aid).join() });
  }
  check("E3 开关开 · 常规秀穿插是 50% 概率: 随机数 0.51 不补 (0 发), 0.49 补 1 发",
    row[0].queued === 0 && row[0].bursts === 0 && row[1].queued === 1 && row[1].bursts === 1 && row[2].queued === 0 && row[2].bursts === 0,
    JSON.stringify(row));
  const q0 = await q();
  const m0 = (await ev()).length;
  await page.evaluate(() => window.__showWithRand(0.51)); // 第 8 轮 = 终曲
  await drain(45000);
  const fin = (await ev()).filter((x, i) => i >= m0 && x.aimed);
  const aids = fin.map((x) => x.aid).sort().join(",");
  check("E4 终曲收尾: 三处炸点各一发 (与随机数无关)", (await q()) - q0 === 3 && fin.length === 3 && aids === "coaster,tower,wheel",
    `排入 ${(await q()) - q0} 发, 爆裂 ${aids}`);
}

// ---------------------------------------------------------------------------------------------- G --
if (ONLY.has("G")) {
  await drain();
  await page.keyboard.press("KeyO");
  await sleep(700);
  await page.evaluate(() => {
    [...document.querySelectorAll(".set-group h3")].find((n) => n.textContent === "烟花")?.scrollIntoView({ block: "start" });
  });
  const labels = await page.evaluate(() => [...document.querySelectorAll(".set-label")].map((n) => n.textContent).filter((t) => /炸点高度|到顶礼花/.test(t)));
  check("G1 设置面板「烟花」组有: 地面炸点高度 / 到顶礼花 / 地标炸点高度",
    labels.includes("地面炸点高度") && labels.includes("到顶礼花") && labels.includes("地标炸点高度"), labels.join(" | "));
  const setSlider = (v) => page.evaluate((v) => {
    const input = [...document.querySelectorAll(".set-slider")].find((i) => i.getAttribute("aria-label") === "地标炸点高度");
    input.value = String(v);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, v);
  const readG = () => page.evaluate(() => ({
    val: window.__settings.store.get("fireworkSaluteHeight"),
    txt: [...document.querySelectorAll(".set-row")].find((r) => r.querySelector('[aria-label="地标炸点高度"]'))?.querySelector(".set-val")?.textContent,
    dys: window.__game.fireworks.getAnchors().map((a) => +(window.__game.fireworks.saluteFlight(a.id).y - a.eye).toFixed(6)),
  }));
  await setSlider(15); await sleep(300);
  const g15 = await readG();
  check("G2 滑杆拖到 +15: 三处炸点 = 眼位 +15, 显示「+15 米」", g15.val === 15 && g15.txt === "+15 米" && g15.dys.every((d) => d === 15), JSON.stringify(g15));
  await setSlider(-20); await sleep(300);
  const gm = await readG();
  check("G2b 滑杆拖到 -20: 三处炸点 = 眼位 −20, 显示「-20 米」", gm.val === -20 && gm.txt === "-20 米" && gm.dys.every((d) => d === -20), JSON.stringify(gm));
  await page.click('button.set-switch[aria-label="到顶礼花"]'); await sleep(250);
  const off = await page.evaluate(() => [window.__settings.store.get("fireworkSalute"), window.__game.fireworks.salute("tower")]);
  await page.click('button.set-switch[aria-label="到顶礼花"]'); await sleep(250);
  const on = await page.evaluate(() => [window.__settings.store.get("fireworkSalute"), window.__game.fireworks.salute("tower")]);
  check("G3 开关点一下关 (salute 被拒), 再点一下开", off[0] === false && off[1] === false && on[0] === true && on[1] === true,
    `关 ${JSON.stringify(off)} / 开 ${JSON.stringify(on)}`);
  await setSlider(0); await sleep(300);
  const g0 = await readG();
  check("G2c 滑杆回 0: 显示「眼位同高」", g0.val === 0 && g0.txt === "眼位同高" && g0.dys.every((d) => d === 0), JSON.stringify(g0));
  await sleep(500);
  await page.screenshot({ path: `${outDir}/G_settings_fireworks.png` });
  await page.keyboard.press("KeyO");
  await sleep(400);
  await drain();
}

// ---------------------------------------------------------------------------------------------- D --
// 同步误差在爆裂钩子里同帧记下 (所乘舱离顶弧长 / 头车弧长); 截图会停帧, 所以先取数再拍
if (ONLY.has("D")) {
  await store("fireworkSalute", true);
  await store("fireworkSaluteHeight", 0);
  // ---- 摩天轮: 真键登舱 → 坐到长椅 (面朝 +z 窗) ----
  await page.evaluate(() => window.__game.player.teleport(0, 1.5, 1.55)); // v3 第 2 批: 站台闸内登舱 (地面登舱点取消)
  await page.waitForFunction(() => window.__game.ferris.isDocked(), { timeout: 15000 });
  await sleep(200);
  await page.keyboard.press("KeyE");
  await page.waitForFunction(() => window.__game.state === "riding" && window.__game.ride === "ferris", { timeout: 10000 });
  await sleep(700);
  await page.keyboard.press("KeyC");
  await page.evaluate(() => window.__game.player.setView(Math.PI, 0));
  const period = await page.evaluate(() => window.__game.ferris.state.ridePeriod);
  let m0 = (await ev()).length;
  const w1 = await waitForEv((r) => r.aimed && r.aid === "wheel" && r.arc !== undefined, 60000, m0);
  await snap("D_wheel_top", 3, 450);
  check("D1 摩天轮: 所乘舱到顶那一刻炸 (离顶弧长 ≤0.5m, 舱根离最高点 ≤0.3m)",
    !!w1 && Math.abs(w1.arc) <= 0.5 && Math.abs(w1.cabTop) <= 0.3,
    w1 ? `离顶弧长 ${w1.arc.toFixed(2)}m (正 = 已过顶), 舱根离最高点 ${w1.cabTop.toFixed(2)}m` : "一圈内未炸");
  if (LONG) {
    const m1 = (await ev()).length;
    const w2 = await waitForEv((r) => r.aimed && r.aid === "wheel" && r.arc !== undefined, 95000, m1);
    check(`D2 转一圈再到顶时再炸 (两发间隔 ≈ 乘坐转速 ${period}s ±1.5, 离顶弧长 ≤0.5m)`,
      !!w1 && !!w2 && Math.abs((w2.t - w1.t) - period) <= 1.5 && Math.abs(w2.arc) <= 0.5,
      w1 && w2 ? `间隔 ${(w2.t - w1.t).toFixed(2)}s, 离顶弧长 ${w2.arc.toFixed(2)}m` : "第二圈未炸");
  }
  await page.keyboard.press("KeyE"); // 下乘
  await page.waitForFunction(() => window.__game.state === "walk", { timeout: 10000 });
  await drain();
  // ---- 过山车: 列车回站 → 真键登车 ----
  await page.evaluate(() => { const c = window.__game.coaster; if (c.state.phase !== "dwell") c.seek(590); });
  await page.waitForFunction(() => window.__game.coaster.state.phase === "dwell", { timeout: 40000 });
  const bs = await page.evaluate(() => window.__game.coaster.getBoardSpot());
  await page.evaluate(([x, z]) => window.__game.player.teleport(Math.max(10.3, x - 0.95), z), [bs.x, bs.z]);
  await sleep(800);
  await page.keyboard.press("KeyE");
  await page.waitForFunction(() => window.__game.state === "riding" && window.__game.ride === "coaster", { timeout: 10000 });
  m0 = (await ev()).length;
  const c1 = await waitForEv((r) => r.aimed && r.aid === "coaster" && r.s !== undefined, 90000, m0);
  await snap("D_coaster_crest", 3, 450);
  check("D3 过山车: 头车到提升平顶中点那一刻炸 (弧长差 ≤1.2m)", !!c1 && Math.abs(c1.s - cr.s) <= 1.2,
    c1 ? `爆裂时头车 s=${c1.s.toFixed(2)} (平顶中点 s=${cr.s})` : "未炸");
  // 再上膛: 列车送回提升段中途 (跳变本身不触发), 再到顶应再炸
  await page.evaluate((s) => window.__game.coaster.seek(s), cr.s - 45);
  await sleep(400);
  m0 = (await ev()).length;
  const c2 = await waitForEv((r) => r.aimed && r.aid === "coaster" && r.s !== undefined, 40000, m0);
  check("D4 过山车再上膛: 再次到顶时再炸 (弧长差 ≤1.2m)", !!c2 && Math.abs(c2.s - cr.s) <= 1.2,
    c2 ? `爆裂时头车 s=${c2.s.toFixed(2)}` : "未炸");
}

// ---------------------------------------------------------------------------------------------- F --
if (ONLY.has("F")) {
  // 用户同款分辨率: 2560×1271 CSS @ 150% = 3840×1907 物理
  const p2 = await openPage({ viewport: { width: 2560, height: 1271 }, deviceScaleFactor: 1.5 });
  await p2.evaluate(() => { const g = window.__game; g.player.teleport(0, 70); g.player.setView(0, 0.35); });
  await p2.waitForTimeout(1500);
  const idle = fstat((await frames(p2, 3000)).dt);
  for (let k = 0; k < 3; k++) { // 先排 3 轮常规秀, 让下一轮是终曲
    await p2.evaluate(() => window.__game.fireworks.debugShow());
    await p2.waitForFunction(() => { const s = window.__game.fireworks.stats(); return s.pending === 0 && s.shells === 0 && s.alive === 0; }, { timeout: 40000 });
  }
  const before = await p2.evaluate(() => window.__game.fireworks.stats()); // 终曲前读数: 常规秀有 50% 概率自己补礼花, 终曲的贡献要取差值
  const runP = frames(p2, 13000, true);
  await p2.evaluate(() => window.__game.fireworks.debugShow());
  await p2.waitForTimeout(5200);
  await p2.screenshot({ path: `${outDir}/F_finale_4k.png` });
  const fin = await runP;
  const st = await p2.evaluate(() => window.__game.fireworks.stats());
  const f = fstat(fin.dt);
  check("F1 终曲粒子池不溢出 (overflow 增量 = 0), 终曲自己入列 3 发礼花", st.overflow === before.overflow && st.salutesQueued - before.salutesQueued === 3,
    `峰值并发 ${fin.maxAlive} / 10240, overflow ${st.overflow}, 终曲礼花 ${st.salutesQueued - before.salutesQueued} 发`);
  check("F2 4K@150% 终曲帧率: 平均帧间隔 ≤ 空闲 + 8ms", f.avg <= idle.avg + 8,
    `空闲 avg ${idle.avg.toFixed(1)}ms (p95 ${idle.p95.toFixed(1)}) → 终曲 avg ${f.avg.toFixed(1)}ms ≈ ${(1000 / f.avg).toFixed(0)} fps (p95 ${f.p95.toFixed(1)}, max ${f.max.toFixed(1)}; 截图那一帧会计入 max)`);
  await p2.context().close();
}

check("全程无控制台报错 / 页面异常", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();
const failed = results.filter((r) => !r).length;
console.log(`\nVERIFY_DONE  ${results.length - failed}/${results.length} 通过`);
process.exit(failed ? 1 : 0);
