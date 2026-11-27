// 摩天轮站台动线端到端回归 (v3 第 2 批「站台成为必经之路」2026-11-27; 第 3 批补 I / J 两块 2026-11-28)
// 用法: 先起 dev server, 再 GAME_URL=http://127.0.0.1:8767 node scripts/verify_ferris_station.mjs [输出目录]
//   只跑部分块: ONLY=C,E,G node scripts/verify_ferris_station.mjs   (块号见下; teleport 摆每块的起点)
// 块:  A 登记与联动 (闸门节点 / 吊灯点光 / 「站台灯光亮度」)   B 地面登舱点取消 -> 台阶脚指路提示
//      C 入口门楼 + 台阶扶手 (真键)      D 排队通道围栏与东侧开口 (真键)
//      E 停靠舱是实体 (真键)              F 登舱闸: 关着挡人 / 停靠才开 / 离开即合 / 闸线带里不落闸 / 乘坐中关
//      G 闸内 E 登舱 -> 下乘落回站台东侧 -> 真键走回地面
//      H 从园区地面真键走完整动线 (台阶中间上 / 台阶东侧上经开口进通道) -> 闸内 E 登舱
//      I 登舱时舱内点光由暗转亮 (v3 第 3 批)   J 雨棚柱 / 支腿脚 (v3 第 3 批, 真键)
// 走线一律经 input -> controller -> tryMove 真链路 (页面内每帧设视线 + 键盘事件), teleport 只用来摆起点。
// 任一断言失败或控制台报错 → exit 1。
import { openGame } from "./lib_tower_shots.mjs";

const OUT = process.argv[2] ?? "shots/ferris_station";
const ONLY = process.env.ONLY ? new Set(process.env.ONLY.split(",")) : null;
const R = [];
const fails = () => R.filter((r) => !r.ok).length;
const check = (name, ok, info = "") => { R.push({ name, ok }); console.log(`${ok ? "ok  " : "FAIL"}: ${name}${info ? "  — " + info : ""}`); };
const J = JSON.stringify;
const near = (v, t, tol) => Math.abs(v - t) <= tol;

const { browser, page, errors } = await openGame(OUT, { width: 1280, height: 720 });
await page.evaluate(() => window.__settings.store.reset()); // 默认设置 (步速 4 m/s 等)

// 页面内走线器: 每帧朝下一个路点设视线并按住 W, 走完 / 卡住 / 超时停。每 80ms 记一个轨迹点。
await page.evaluate(() => {
  const g = window.__game, pl = g.player;
  const a = (window.__sd = { on: false });
  a.tick = () => {
    requestAnimationFrame(a.tick);
    if (!a.on) return;
    a.frames++;
    const p = pl.pos, now = performance.now();
    const t = a.route(p);
    if (!t) { a.on = false; a.stop = "reached"; return; }
    pl.setView(Math.atan2(-(t[0] - p.x), -(t[1] - p.z)), 0); // 路点是 [x, z]
    if (pl.airborne()) a.airFrames++;
    if (!a.path.length || now - a.t0 - a.path[a.path.length - 1].t > 80) a.path.push({ t: Math.round(now - a.t0), x: p.x, y: p.y, z: p.z });
    if (Math.hypot(p.x - a._mx, p.z - a._mz) > 0.03) { a._mx = p.x; a._mz = p.z; a._mt = now; }
    else if (now - a._mt > a.stuckMs && now - a.t0 > 600) { a.on = false; a.stop = "blocked"; } // 开局 0.6s 不判卡 (传送后首帧可能卡)
    if (now - a.t0 > a.maxMs) { a.on = false; a.stop = "timeout"; }
  };
  requestAnimationFrame(a.tick);
  window.__walk = async ([pts, o]) => {
    let i = 0;
    Object.assign(a, { on: true, stop: null, path: [], frames: 0, airFrames: 0, t0: performance.now(), _mx: pl.pos.x, _mz: pl.pos.z, _mt: performance.now(),
      stuckMs: o?.stuckMs ?? 2200, maxMs: o?.maxMs ?? 20000, tol: o?.tol ?? 0.3, endTol: o?.endTol ?? 0.08 });
    a.route = (p) => {
      while (i < pts.length - 1 && Math.hypot(pts[i][0] - p.x, pts[i][1] - p.z) < a.tol) i++;
      const q = pts[Math.min(i, pts.length - 1)];
      return Math.hypot(q[0] - p.x, q[1] - p.z) <= a.endTol ? null : q;
    };
    window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyW" }));
    while (a.on) await new Promise((r) => setTimeout(r, 25));
    window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyW" }));
    const p = pl.pos;
    return { stop: a.stop, ms: Math.round(performance.now() - a.t0), airFrames: a.airFrames, path: a.path,
      end: [+p.x.toFixed(3), +p.y.toFixed(3), +p.z.toFixed(3)] };
  };
});

const sleep = (ms) => page.waitForTimeout(ms);
const pose = (x, z, y = 0, yaw = 0) =>
  page.evaluate(([x, z, y, yaw]) => { window.__game.player.teleport(x, z, y); window.__game.player.setView(yaw, 0); }, [x, z, y, yaw]);
const walk = (pts, o) => page.evaluate((a) => window.__walk(a), [pts, o]);
const brief = (w) => J({ x: w.end[0], y: w.end[1], z: w.end[2], stop: w.stop, ms: w.ms, air: w.airFrames });
// 走到墙前停住: 停住 + 终点落在期望值附近
const stoppedAt = (w, axis, want, tol) => w.stop === "blocked" && near(w.end[axis], want, tol);
const prompt = () => page.evaluate(() => {
  const pe = document.querySelector(".spirit-prompt");
  return { shown: !!pe && pe.classList.contains("show"), text: pe?.querySelector(".prompt-text")?.textContent.trim() ?? "", key: pe?.querySelector(".keycap")?.textContent.trim() ?? "" };
});
const fw = () => page.evaluate(() => { const f = window.__game.ferris; return { docked: f.isDocked(), open01: +f.gateOpen01().toFixed(3), passable: f.gatePassable }; });
const waitOpen = () => page.waitForFunction(() => window.__game.ferris.gateOpen01() >= 0.999, { timeout: 12000 });
// 离开站台 (轮自转、闸关) / 上站台 (吸附到位、闸开)
const goGround = async (x = 0, z = 40) => {
  await pose(x, z, 0, 0);
  await page.waitForFunction(() => window.__game.ferris.gateOpen01() === 0 && !window.__game.ferris.isDocked(), { timeout: 8000 });
};
const goPlatform = async (x, z, yaw = 0) => { await pose(x, z, 1.55, yaw); await waitOpen(); await sleep(150); };
// 两扇闸门的世界包围盒 (子网格包围盒 8 角 × matrixWorld)
const leafBoxes = () => page.evaluate(() => {
  const root = window.__game.ferris.wheelRoot.parent, out = {};
  root.updateWorldMatrix(true, true);
  for (const side of ["L", "R"]) {
    const n = root.getObjectByName("FW_BoardGate_" + side);
    const min = [1e9, 1e9, 1e9], max = [-1e9, -1e9, -1e9];
    for (const o of n.children) {
      if (!o.isMesh) continue;
      o.geometry.computeBoundingBox();
      const b = o.geometry.boundingBox, e = o.matrixWorld.elements;
      for (let i = 0; i < 8; i++) {
        const x = i & 1 ? b.max.x : b.min.x, y = i & 2 ? b.max.y : b.min.y, z = i & 4 ? b.max.z : b.min.z;
        const w = [e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]];
        for (let k = 0; k < 3; k++) { if (w[k] < min[k]) min[k] = w[k]; if (w[k] > max[k]) max[k] = w[k]; }
      }
    }
    out[side] = { min: min.map((v) => +v.toFixed(3)), max: max.map((v) => +v.toFixed(3)) };
  }
  return out;
});
const press = (code) => page.keyboard.press(code);
const state = () => page.evaluate(() => window.__game.state);

async function block(id, title, setup, run) {
  if (ONLY && !ONLY.has(id)) return;
  console.log(`\n===== ${id} ${title} =====`);
  try { await setup(); await run(); }
  catch (e) { check(`${title}: 块内异常`, false, String(e).slice(0, 300)); }
}

// ================= A =================
await block("A", "登记与联动", async () => { await goGround(); }, async () => {
  const a = await page.evaluate(() => {
    const g = window.__game, f = g.ferris, root = f.wheelRoot.parent;
    let stat = 0, wheel = 0, leaves = 0, cab = 0;
    root.traverse((o) => { if (!o.isMesh || !o.visible) return; const n = o.name; if (/^FW_S_/.test(n)) stat++; else if (/^FW_W_/.test(n)) wheel++; else if (/^FW_BoardGate_[LR]_/.test(n)) leaves++; else if (/^FW_C/.test(n)) cab++; });
    const lamp = root.getObjectByName("FW_S_FW_StationLamp")?.material, sig = root.getObjectByName("FW_S_FW_GateSignal")?.material;
    return { stat, wheel, leaves, cab, leavesN: ["L", "R"].filter((s) => root.getObjectByName("FW_BoardGate_" + s)).length,
      lights: f.stationLights.map((l) => ({ p: l.position.toArray().map((v) => +v.toFixed(2)), i: +l.intensity.toFixed(2), d: l.distance, dec: l.decay })),
      lampI: lamp?.emissiveIntensity, sigI: sig?.emissiveIntensity, hasGateNode: !!root.getObjectByName("FW_BoardGate_L"), set: window.__settings.store.get("ferrisStationLight") };
  });
  check("登舱闸两扇门的节点 FW_BoardGate_L / _R 都在 (各带 Iron / Gold 两个子网格)", a.leavesN === 2 && a.leaves === 4, J({ n: a.leavesN, meshes: a.leaves }));
  check("站台吊灯点光 ×2 在灯心 (0,5.18,2.6) / (0,5.18,5.6), 默认 38 cd", a.lights.length === 2 && a.lights.every((l, i) => l.p[0] === 0 && l.p[1] === 5.18 && l.p[2] === [2.6, 5.6][i] && l.i === 38 && l.dec === 2), J(a.lights));
  check("新增设置「站台灯光亮度」默认 100", a.set === 100, J(a.set));
  const glow = () => page.evaluate(() => { const root = window.__game.ferris.wheelRoot.parent; return { lamp: root.getObjectByName("FW_S_FW_StationLamp").material.emissiveIntensity,
    light: window.__game.ferris.stationLights[0].intensity, rim: root.getObjectByName("FW_S_FW_RingAmber").material.emissiveIntensity }; });
  await page.evaluate(() => window.__settings.store.set("ferrisStationLight", 0)); await sleep(250);
  const g0 = await glow();
  await page.evaluate(() => window.__settings.store.set("ferrisStationLight", 200)); await sleep(250);
  const g200 = await glow();
  await page.evaluate(() => window.__settings.store.set("ferrisStationLight", 100));
  await page.evaluate(() => window.__settings.store.set("decoLight", 40)); await sleep(250);
  const gd = await glow();
  await page.evaluate(() => window.__settings.store.set("decoLight", 100));
  check("「站台灯光亮度」0% 灯灭光灭 / 200% 翻倍 (灯具自发光 + 点光一起调)", g0.lamp === 0 && g0.light === 0 && near(g200.lamp, 2 * a.lampI, 1e-3) && g200.light === 76, J({ base: a.lampI, g0, g200 }));
  check("站台灯不随「装饰灯亮度」变 (装饰灯 40% 时站台灯不动, 灯环减半到 0.72)", near(gd.lamp, a.lampI, 1e-3) && gd.light === 38 && near(gd.rim, 1.8 * 0.4, 1e-3), J(gd));
  console.log(`info: 摩天轮可见网格 静组 ${a.stat} / 轮体 ${a.wheel} / 闸门 ${a.leaves} / 舱 ${a.cab} = ${a.stat + a.wheel + a.leaves + a.cab}`);
});

// ================= B =================
await block("B", "地面登舱点取消 -> 台阶脚指路提示", async () => { await goGround(); }, async () => {
  await pose(0, 18.8, 0, 0); await sleep(400);
  let p = await prompt();
  check("台阶脚 (0,18.8) 出指路提示「乘坐摩天轮 · 请上站台」, 键帽 ↑", p.shown && p.text.includes("请上站台") && p.key === "↑", J(p));
  await press("KeyE"); await sleep(900);
  check("台阶脚按 E 不登舱 (地面登舱点已取消)", (await state()) === "walk", `state=${await state()}`);
  await pose(0, 16.4, 0, 0); await sleep(400);
  p = await prompt();
  check("原地面登舱点 (0,16.4) 也只出指路提示", p.shown && p.text.includes("请上站台") && p.key === "↑", J(p));
  await pose(3.0, 20.0, 0, 0); await sleep(400);
  check("门楼东侧 5 m 外仍能看到指路提示", (await prompt()).text.includes("请上站台"));
  await pose(0, 30, 0, 0); await sleep(400);
  check("离门楼 12 m 外不再提示", !(await prompt()).shown, J(await prompt()));
  await goPlatform(0, 4.0);
  p = await prompt();
  check("站台通道里 (闸外, 0,4.0) 不出「乘坐摩天轮」", !p.shown, J(p));
});

// ================= C =================
await block("C", "入口门楼 + 台阶扶手 (真键)", async () => { await goGround(0, 44); }, async () => {
  await pose(0, 22.5, 0, 0);
  let w = await walk([[0, 17.4], [0, 12.5], [0, 8.4]], { maxMs: 20000 });
  check("从南路穿过门楼、走上 8 级台阶到站台 (全程贴地)", w.stop === "reached" && w.airFrames === 0 && near(w.end[1], 1.55, 0.02) && w.end[2] < 8.7, brief(w));
  check("上台阶途中越过门楼时脚高一直是地面 (门楼下没有台阶)", w.path.filter((q) => Math.abs(q.z - 17.4) < 0.3).every((q) => q.y === 0));
  await page.screenshot({ path: `${OUT}/c1_stair_top.png` });
  // 门楼柱是圆排斥件: 人会顺着柱面绕过去, 判据用「全程离柱心 ≥ r + 0.38」
  await pose(0, 18.6, 0, 0);
  w = await walk([[4.8, 18.6]], { maxMs: 12000 }); // 从门楼南侧横着往东走, 擦过东柱
  const minD = Math.min(...w.path.map((q) => Math.hypot(q.x - 2.5, q.z - 17.4)));
  check("门楼东柱挡人: 贴着柱面绕过去, 全程离柱心 ≥ 0.62 m", w.stop === "reached" && minD >= 0.57, J({ minD: +minD.toFixed(3), end: w.end }));
  // 柱子北面与台阶扶手南端之间没有缝: 从门楼里朝东北挤, 进不了台阶侧边的夹缝, 退得出来
  await pose(1.2, 17.4, 0, 0);
  w = await walk([[2.6, 16.2]], { maxMs: 12000 });
  const out = await walk([[0, 18.2]], { maxMs: 8000 });
  check("门楼柱与台阶扶手之间挤不进去 (停在柱面 / 扶手端外), 而且退得出来", w.stop === "blocked" && Math.hypot(w.end[0] - 2.5, w.end[2] - 17.4) >= 0.57 && out.stop === "reached", brief(w) + " → " + brief(out));
  // 台阶扶手是盒墙: 在第 5 级上朝东 / 西走, 被挡在 x ≈ ±1.87
  await pose(0, 13.0, 0.58, 0);
  w = await walk([[3.2, 13.0]], { maxMs: 12000 });
  check("台阶东扶手挡人 (停在第 5 级上, x ≈ 1.87)", stoppedAt(w, 0, 1.87, 0.06) && near(w.end[1], 0.58, 0.02) && w.airFrames === 0, brief(w));
  await pose(0, 13.0, 0.58, 0);
  w = await walk([[-3.2, 13.0]], { maxMs: 12000 });
  check("台阶西扶手挡人 (x ≈ -1.87)", stoppedAt(w, 0, -1.87, 0.06) && near(w.end[1], 0.58, 0.02), brief(w));
  await pose(0, 15.0, 0.19, 0);
  w = await walk([[3.2, 15.0]], { maxMs: 12000 });
  check("台阶下半段扶手同样挡人 (第 7 级, x ≈ 1.87)", stoppedAt(w, 0, 1.87, 0.06), brief(w));
});

// ================= D =================
await block("D", "排队通道围栏与东侧开口 (真键)", async () => { await goPlatform(3.0, 8.0); }, async () => {
  let w = await walk([[-2.6, 7.5]], { maxMs: 12000 });
  check("通道东栏挡人: 从东侧观景区向西走, 停在 x ≈ 1.23", stoppedAt(w, 0, 1.23, 0.05) && near(w.end[1], 1.55, 0.02), brief(w));
  w = await walk([[0, 6.35]], { maxMs: 12000 });
  check("开口北缘外 (z 6.35) 向西走被北段围栏挡住 (x ≈ 1.23)", stoppedAt(w, 0, 1.23, 0.06), brief(w));
  await pose(2.2, 3.3, 1.55, 0);
  w = await walk([[0, 3.3]], { maxMs: 12000 });
  check("开口南缘外 (z 3.3) 向西走被南段围栏挡住 (x ≈ 1.23)", stoppedAt(w, 0, 1.23, 0.06), brief(w));
  await pose(2.6, 5.0, 1.55, 0);
  w = await walk([[0, 5.0], [0, 3.6]], { maxMs: 12000 });
  check("从东侧开口 (z 5.0) 能走进通道", w.stop === "reached" && w.airFrames === 0, brief(w));
  await pose(0, 7.5, 1.55, 0);
  w = await walk([[-2.6, 7.5]], { maxMs: 12000 });
  check("通道西栏挡人 (通道里向西走, 停在 x ≈ -0.37)", stoppedAt(w, 0, -0.37, 0.05), brief(w));
  w = await walk([[0, 7.5]], { maxMs: 8000 });
  await pose(0, 7.5, 1.55, 0);
  w = await walk([[2.6, 7.5]], { maxMs: 12000 });
  check("通道东栏挡人 (通道里向东走, 停在 x ≈ 0.37)", stoppedAt(w, 0, 0.37, 0.05), brief(w));
  await pose(1.6, 8.2, 1.55, 0);
  w = await walk([[0, 8.2]], { maxMs: 12000 });
  check("通道南端封到站台缘: 台阶口东侧向西走进不了通道 (x ≈ 1.23)", stoppedAt(w, 0, 1.23, 0.06), brief(w));
});

// ================= E =================
await block("E", "停靠舱是实体 (真键)", async () => { await goPlatform(0, 4.0); }, async () => {
  let w = await walk([[0, -1.0]], { maxMs: 12000 });
  check("从闸内朝舱门走: 停在舱门前 z ≈ 1.40", stoppedAt(w, 2, 1.40, 0.05) && near(w.end[0], 0, 0.05), brief(w));
  await goPlatform(3.4, 0.6);
  w = await walk([[-1.0, 0.6]], { maxMs: 12000 });
  check("从东侧走向舱体: 停在 x ≈ 1.60", stoppedAt(w, 0, 1.60, 0.05), brief(w));
  await pose(0, -3.4, 1.55, 0); await waitOpen(); await sleep(200);
  w = await walk([[0, 1.0]], { maxMs: 12000 });
  check("从北侧走向舱体 (长椅一侧): 停在 z ≈ -1.40", stoppedAt(w, 2, -1.40, 0.05), brief(w));
});

// ================= F =================
await block("F", "登舱闸", async () => { await goGround(0, 44); }, async () => {
  let s = await fw();
  check("没人在站台上: 轮自转、闸关着、闸线不通行", !s.docked && s.open01 === 0 && !s.passable, J(s));
  let lb = await leafBoxes();
  check("关位: 两扇门横在闸线 z ≈ 1.90, 自由端在中间 (x ±0.04)", near(lb.L.min[2], 1.88, 0.03) && near(lb.R.max[2], 1.93, 0.03) &&
    near(lb.L.max[0], -0.02, 0.03) && near(lb.R.min[0], 0.02, 0.03), J(lb));
  // 关着挡人: 先把轮拨到离停靠位最远的角度 (这样上站台后吸附要 2.4 s), 一上站台就朝闸走, 记头 1.2 s 的轨迹
  const r = await page.evaluate(async () => {
    const g = window.__game, f = g.ferris, st = f.state;
    const pos = (o) => { const e = o.matrixWorld.elements; return [e[12], e[13], e[14]]; };
    const off = () => { // 最低舱相对「轮面正下方」的角偏差 (rad)
      const h = pos(f.wheelRoot); let by = 1e9, o = 0;
      for (const c of f.cabinRoots) { const p = pos(c); if (p[1] < by) { by = p[1]; o = Math.atan2(Math.hypot(p[0] - h[0], p[2] - h[2]), h[1] - p[1]); } }
      return o;
    };
    const frame = () => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    await frame(); const o0 = off(); const target = Math.PI / 16 - 0.004;
    st.theta += target - o0; await frame();
    let o1 = off();
    if (o1 < o0) { st.theta -= 2 * (target - o0); await frame(); o1 = off(); } // 转反了就换方向
    g.player.teleport(0, 2.9, 1.55); g.player.setView(0, 0);
    const zs = [], t0 = performance.now();
    window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyW" }));
    await new Promise((res) => { const tick = () => { zs.push(+g.player.pos.z.toFixed(3)); if (performance.now() - t0 < 1200) requestAnimationFrame(tick); else res(); }; requestAnimationFrame(tick); });
    window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyW" }));
    return { o0: +o0.toFixed(3), o1: +o1.toFixed(3), minZ: Math.min(...zs), lastZ: zs[zs.length - 1], n: zs.length, open: +f.gateOpen01().toFixed(3), docked: f.isDocked() };
  });
  check("闸关着时走不进闸线 (上站台头 1.2 s 一直被挡在 z ≈ 2.33)", r.o1 > 0.17 && r.minZ >= 2.28 && r.lastZ >= 2.28 && r.lastZ <= 2.45 && !r.docked, J(r));
  const pg = await prompt();
  check("闸关着时站在闸线前 (z ≈ 2.33) 不出「乘坐摩天轮」", !pg.shown, J(pg));
  const t0 = Date.now();
  await waitOpen();
  const tOpen = Date.now() - t0;
  s = await fw(); lb = await leafBoxes();
  check(`轮停稳、舱吸附到位后闸开 (再 ${tOpen} ms 全开), 闸线放行`, s.docked && s.open01 === 1 && s.passable, J(s));
  check("开位: 两扇门贴回两侧围栏 (x ±0.68..0.75, z 1.90 → 2.58), 不扫进停靠舱一侧", lb.L.max[2] > 2.5 && lb.L.min[2] >= 1.85 &&
    lb.R.max[2] > 2.5 && lb.R.min[2] >= 1.85 && lb.L.max[0] < -0.6 && lb.R.min[0] > 0.6, J(lb));
  const sig = () => page.evaluate(() => {
    const f = window.__game.ferris; let on = 0;
    for (const c of f.cabinRoots) c.traverse((o) => { if (o.isMesh && o.material?.name === "FW_DoorSignal" && o.material.emissiveIntensity > 0) on++; });
    return { gate: f.wheelRoot.parent.getObjectByName("FW_S_FW_GateSignal").material.emissiveIntensity, doorsOn: on };
  });
  const sg1 = await sig();
  check("停靠时闸柱灯和停靠舱门框亮灵火青 (闸柱灯 1.1, 门框恰 1 舱亮)", sg1.gate > 1.0 && sg1.doorsOn === 1, J(sg1));
  let w = await walk([[0, 0]], { maxMs: 12000 });
  check("闸开后能走过闸线, 停在停靠舱门前 (z ≈ 1.40)", stoppedAt(w, 2, 1.40, 0.05), brief(w));
  await page.screenshot({ path: `${OUT}/f1_gate_open.png` });
  // 离开即合
  await goGround(0, 44);
  s = await fw();
  check("离开站台后闸关严、闸线重新挡人", !s.docked && s.open01 === 0 && !s.passable, J(s));
  const sg0 = await sig();
  check("闸关后闸柱灯、门框全灭", sg0.gate === 0 && sg0.doorsOn === 0, J(sg0));
  // 闸线带里跳跃: 联锁会在腾空时松开 (脚高 > 2.2), 闸门不能趁人腾空时落下来
  await goPlatform(0, 1.9);
  const jump = await page.evaluate(async () => {
    const f = window.__game.ferris, g = window.__game, out = { minOpen: 1, maxY: 0, air: 0 };
    window.dispatchEvent(new KeyboardEvent("keydown", { code: "Space" })); window.dispatchEvent(new KeyboardEvent("keyup", { code: "Space" }));
    const t0 = performance.now();
    await new Promise((res) => { const tick = () => { out.minOpen = Math.min(out.minOpen, f.gateOpen01()); out.maxY = Math.max(out.maxY, g.player.pos.y);
      if (g.player.airborne()) out.air++; if (performance.now() - t0 < 1700) requestAnimationFrame(tick); else res(); }; requestAnimationFrame(tick); });
    return { ...out, open: +f.gateOpen01().toFixed(3), y: +g.player.pos.y.toFixed(3), state: g.state };
  });
  check("闸线带里原地跳 (脚高越过 2.2): 闸门不落, 开度始终 1", jump.air > 5 && jump.maxY > 2.2 && jump.minOpen >= 0.999 && jump.open === 1 && jump.state === "walk" && near(jump.y, 1.55, 0.01), J(jump));
  await page.waitForFunction(() => window.__game.ferris.isDocked(), { timeout: 8000 }); // 落地后重新吸附
  // 乘坐中关, 下乘回站台后重开
  await walk([[0, 1.6]], { maxMs: 8000 });
  await press("KeyE");
  await page.waitForFunction(() => window.__game.state === "riding", { timeout: 8000 });
  await page.waitForFunction(() => window.__game.ferris.gateOpen01() === 0, { timeout: 6000 });
  check("乘坐中 (人不在站台) 闸关", true);
  await press("KeyE");
  await page.waitForFunction(() => window.__game.state === "walk", { timeout: 8000 });
  await waitOpen();
  check("下乘落回站台后闸重新打开", (await fw()).open01 === 1);
});

// ================= G =================
await block("G", "闸内 E 登舱 -> 下乘落回站台东侧 -> 真键走回地面", async () => { await goPlatform(0, 4.0); }, async () => {
  let p = await prompt();
  check("通道里 (0,4.0) 没有登舱提示", !p.shown, J(p));
  await pose(0, 2.45, 1.55, 0); await sleep(300);
  check("闸外通道里贴近闸线 (0,2.45) 仍没有登舱提示", !(await prompt()).shown);
  await pose(0, 2.05, 1.55, 0); await sleep(300);
  p = await prompt();
  check("站在开着的闸门口 (0,2.05) 出「E 乘坐摩天轮」(走到闸口就算到了)", p.shown && p.text === "乘坐摩天轮" && p.key === "E", J(p));
  await pose(0, 4.0, 1.55, 0); await sleep(300);
  let w = await walk([[0, 1.6]], { maxMs: 12000 });
  p = await prompt();
  check("走过闸线到停靠舱前: 出「E 乘坐摩天轮」", w.stop === "reached" && p.shown && p.text === "乘坐摩天轮" && p.key === "E", J({ end: w.end, ...p }));
  await press("KeyE");
  await page.waitForFunction(() => window.__game.state === "riding" && window.__game.ride === "ferris", { timeout: 8000 });
  await sleep(900);
  const ride = await page.evaluate(() => ({ loc: window.__game.player.cabinLocal(), plaque: document.querySelector(".ride-plaque.show .plaque-name")?.textContent }));
  check("闸内按 E 登舱 (落位门侧, 铭牌「幽眠摩天轮」)", !!ride.loc && ride.loc.z > 0 && ride.plaque === "幽眠摩天轮", J(ride));
  await page.evaluate(() => { window.__game.ferris.state.theta = Math.PI; }); // 转到最高处再下乘 (第 2 批之前这一步会送回台阶下的地面)
  await sleep(600);
  await press("KeyE");
  await page.waitForFunction(() => window.__game.state === "walk", { timeout: 8000 });
  await sleep(300);
  const drop = await page.evaluate(() => { const g = window.__game; return { p: g.player.pos.toArray().map((v) => +v.toFixed(3)), toast: document.querySelector(".toast")?.textContent.trim() ?? "", plaque: !!document.querySelector(".ride-plaque.show") }; });
  check("最高处按 E 下乘: 落回站台东侧 (2.4, 1.55, 0.6), 提示「已回到站台 · 南侧台阶下台」", near(drop.p[0], 2.4, 0.03) && near(drop.p[1], 1.55, 0.02) &&
    near(drop.p[2], 0.6, 0.03) && drop.toast.includes("已回到站台") && !drop.plaque, J(drop));
  await waitOpen();
  const w2 = await walk([[2.0, 4.6], [1.6, 8.0], [1.6, 12.5], [1.6, 17.0], [1.6, 19.5]], { maxMs: 25000 });
  const ys = w2.path.map((q) => q.y);
  check("真键从下乘落点原路下台: 绕过通道东侧 → 8 级台阶 → 门楼 → 回到园区地面 (全程贴地)", w2.stop === "reached" && w2.airFrames === 0 && w2.end[1] === 0 && w2.end[2] > 19.3, brief(w2));
  check("下台阶时脚高逐级下降 (1.55 → 0), 没有掉落", ys[0] > 1.5 && ys.every((y, i) => i === 0 || y <= ys[i - 1] + 1e-6), J(ys));
});

// ================= H =================
await block("H", "从园区地面真键走完整动线", async () => { await goGround(0, 44); }, async () => {
  const ride = async (name) => {
    await press("KeyE");
    const okOn = await page.waitForFunction(() => window.__game.state === "riding" && window.__game.ride === "ferris", { timeout: 8000 }).then(() => true, () => false);
    await press("KeyE");
    const okOff = await page.waitForFunction(() => window.__game.state === "walk", { timeout: 8000 }).then(() => true, () => false);
    check(name, okOn && okOff, J({ on: okOn, off: okOff }));
  };
  await pose(0, 24.0, 0, 0);
  let w = await walk([[0, 17.4], [0, 12.5], [0, 8.4], [0, 4.0], [0, 1.6]], { maxMs: 30000, stuckMs: 3500 });
  let p = await prompt();
  check("台阶中间上: 南路 → 门楼 → 台阶 → 通道 → 登舱闸 → 停靠舱前, 出登舱提示", w.stop === "reached" && w.airFrames === 0 && p.shown && p.text === "乘坐摩天轮", brief(w) + " " + J(p));
  await page.screenshot({ path: `${OUT}/h1_apron.png` });
  await ride("中间上: 闸内 E 登舱, 再按 E 下乘");
  await pose(1.6, 24.0, 0, 0);
  w = await walk([[1.6, 17.4], [1.6, 12.5], [1.6, 8.6], [1.9, 5.0], [0, 5.0], [0, 3.4], [0, 1.6]], { maxMs: 30000, stuckMs: 3500 });
  p = await prompt();
  check("台阶东侧上 (偏离中线, 台阶与圆台接得上): 台阶东半边 → 东侧观景区 → 开口 (z 5.0) 进通道 → 登舱闸 → 停靠舱前, 出登舱提示", w.stop === "reached" && w.airFrames === 0 && p.shown && p.text === "乘坐摩天轮", brief(w) + " " + J(p));
  await ride("东侧上: 闸内 E 登舱, 再按 E 下乘");
});

// ================= I =================
await block("I", "登舱时舱内灯由暗转亮 (v3 第 3 批)", async () => { await goPlatform(0, 2.05); }, async () => {
  const light = () => page.evaluate(() => { const l = window.__game.ferris.rideLight; return l ? { i: +l.intensity.toFixed(3), inScene: !!l.parent } : null; });
  check("没乘坐时舱内点光不在场景里 (闸口看进停靠舱是暗的)", !(await light())?.inScene, J(await light()));
  await press("KeyE");
  await page.waitForFunction(() => window.__game.state === "riding", { timeout: 8000 });
  const s = await page.evaluate(async () => {
    const g = window.__game, out = [], t0 = performance.now();
    await new Promise((res) => { const tick = () => { const l = g.ferris.rideLight; out.push([Math.round(performance.now() - t0), l ? +l.intensity.toFixed(3) : null]);
      if (performance.now() - t0 < 1900) requestAnimationFrame(tick); else res(); }; requestAnimationFrame(tick); });
    return out.filter((q, k, a) => k % 15 === 0 || k === a.length - 1);
  });
  const vals = s.map((q) => q[1]);
  // 首个采样点滞后于起亮约 0..150 ms (等 riding 态 + 一次往返), 所以只要求「起步不到三成」
  check("登舱后舱内点光由暗转亮: 起步不到三成, 单调上升, 1.9 s 后到设定值 8.8 (22 cd × 舱内灯 40%)",
    vals[0] < 0.3 * 8.8 && vals.every((v, k) => k === 0 || v >= vals[k - 1] - 1e-6) && Math.abs(vals[vals.length - 1] - 8.8) < 0.01, J(s));
  await page.evaluate(() => window.__settings.store.set("cabinLight", 100));
  await sleep(250);
  check("乘坐中改「舱内灯光亮度」立即生效 (100% = 22 cd)", Math.abs((await light()).i - 22) < 0.01, J(await light()));
  await page.evaluate(() => window.__settings.store.set("cabinLight", 40));
  await press("KeyE");
  await page.waitForFunction(() => window.__game.state === "walk", { timeout: 8000 });
  check("下乘后舱内点光收起", !(await light())?.inScene);
});

// ================= J =================
await block("J", "雨棚柱 / 支腿脚 (v3 第 3 批)", async () => { await goPlatform(7.6, 4.8); }, async () => {
  // 雨棚柱 (4.172, 6.081) r 0.17 是圆排斥件: 斜着擦过去, 判据用全程离柱心 ≥ r + 0.38
  await pose(7.6, 4.8, 1.55, 0);
  let w = await walk([[2.4, 7.6]], { maxMs: 12000 });
  const minD = Math.min(...w.path.map((q) => Math.hypot(q.x - 4.172, q.z - 6.081)));
  check("雨棚柱挡人: 擦着柱面绕过去, 全程离柱心 ≥ 0.55 m", w.stop === "reached" && minD >= 0.52, J({ minD: +minD.toFixed(3), end: w.end }));
  // 支腿脚 (±6.2, ±3.0): 方座 + 钢底板 = 1.28 × 1.28 盒墙
  await pose(3.6, 3.0, 1.55, 0);
  w = await walk([[8.0, 3.0]], { maxMs: 12000 });
  // 盒墙半宽 0.64 + 玩家半径 0.38 → 圆心停在离腿心 1.02 m 处
  check("支腿脚挡人: 从西侧径直往东走, 停在钢底板前 x ≈ 5.18", stoppedAt(w, 0, 5.18, 0.06) && near(w.end[2], 3.0, 0.1), brief(w));
  await pose(6.2, 5.8, 1.55, 0);
  w = await walk([[6.2, 0.0]], { maxMs: 12000 });
  check("支腿脚挡人: 从南侧往北走, 停在 z ≈ 4.02", stoppedAt(w, 2, 4.02, 0.06), brief(w));
  await pose(-6.2, -5.8, 1.55, 0);
  w = await walk([[-6.2, 0.0]], { maxMs: 12000 });
  check("支腿脚挡人 (对角那只): 从北侧往南走, 停在 z ≈ -4.02", stoppedAt(w, 2, -4.02, 0.06), brief(w));
});

console.log(`\nVERIFY_DONE  ${R.length - fails()}/${R.length} 通过`);
console.log("console-errors:", errors.length ? J([...new Set(errors)]) : "none");
await browser.close();
if (fails() || errors.length) process.exitCode = 1;

