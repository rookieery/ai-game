// 缠魂塔 · 游戏接入端到端取证 (M5)
// 用法: 先起 dev server, 再 GAME_URL=http://127.0.0.1:8767 node scripts/verify_tower_game.mjs [输出目录]
//   只跑部分块: ONLY=B,D,H node scripts/verify_tower_game.mjs   (块号见下; 没跑/没过的块, 下一块用 teleport 摆前置状态)
// 块:  A 加载与首帧 + 定点截图   B 出生点真键步行 108m 进轿厢   C 门洞防挟   D 乘梯上塔 + 出厢上环廊
//      E 环廊步行 + 塔顶打卡 + 摩天轮联锁   F 真键走螺旋梯下 / 上   G 乘梯下塔
//      H 顶层自动呼梯 (轿厢不在时门洞进不去)   I 底层自动呼梯   J 装饰灯设置联动   K 摩天轮联锁回归   L 真键撞栏杆不漏
// 走线一律经 input → controller → tryMove 真链路 (scripts/lib_tower_drive.mjs); teleport 只用来摆每块的起点。
// 任一断言失败或控制台报错 → exit 1。配套: verify_tower_colliders.mjs (离线碰撞表) / verify_tower_shots.mjs (机位截图)
import { mkdirSync, readFileSync } from "node:fs";
import { openGame } from "./lib_tower_shots.mjs";
import { installDrive, drive, nudge, pose, pos, towerState, promptText, promptKey, toastText } from "./lib_tower_drive.mjs";

const OUT = process.argv[2] ?? "shots/tower/game";
mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? new Set(process.env.ONLY.split(",")) : null;
const R = [];
const fails = () => R.filter((r) => !r.ok).length;
const check = (name, ok, info = "") => { R.push({ name, ok }); console.log(`${ok ? "ok  " : "FAIL"}: ${name}${info ? "  — " + info : ""}`); };
const J = JSON.stringify;
const man = JSON.parse(readFileSync(new URL("../model/lookout_tower/colliders_tower.json", import.meta.url), "utf8"));
const rad = (d) => (d * Math.PI) / 180;
const L = man.lift;
const CX = man.place.x, CZ = man.place.z;
const CAB_Y = L.zBottom + L.floorThk;        // 底层轿厢地面 0.14
const TOP_Y = L.zTop + L.floorThk;           // 顶层轿厢地面 40.0
const pt = (az, r) => [+(CX + r * Math.cos(rad(az))).toFixed(3), +(CZ + r * Math.sin(rad(az))).toFixed(3)]; // 塔周站点 [x,z]
const cam = (az, r, y) => [CX + r * Math.cos(rad(az)), y, CZ + r * Math.sin(rad(az))];                       // 机位 [x,y,z]
const rc = (p) => +Math.hypot(p.x - CX, p.z - CZ).toFixed(2);

// 出生点 → 塔南门廊的可行路径: 三张碰撞表离线泛洪 (scripts 外的一次性预检), 带 h 的圆按 controller 口径
// (没站上顶之前 r+0.38 推挤) 处理并留 0.2m 余量, 每约 2m 一点。verify_tower_colliders 只在塔周泛洪, 不覆盖这段来路。
const SPAWN_PATH = [[0, 60], [1.6, 58.8], [3.6, 58.2], [5.6, 57.4], [7.6, 57.4], [9.6, 57.4], [11, 55.8], [11, 53.8], [11, 51.8],
  [11, 49.8], [11, 47.8], [11, 45.8], [11, 43.8], [11, 41.8], [11, 39.8], [11, 37.8], [12.4, 36.2], [12.4, 34.2], [12.4, 32.2],
  [12.4, 30.2], [12.4, 28.2], [12.4, 26.2], [12.4, 24.2], [12.4, 22.2], [12.4, 20.2], [12.4, 18.2], [12.4, 16.2], [13.8, 14.6],
  [15.2, 13], [15.2, 11], [15.2, 9], [15.2, 7], [15.2, 5], [15.2, 3], [15.2, 1], [15.2, -1], [15.2, -3], [15.2, -5], [15.2, -7],
  [15.2, -9], [15.2, -11], [15.2, -13], [16.8, -14.2], [17.4, -16.2], [17.4, -18.2], [17.4, -20.2], [17.4, -22.2], [17.4, -24.2],
  [17.4, -26.2], [17.4, -27.8]];

const { browser, page, errors } = await openGame(OUT, { width: 1280, height: 720 });
await installDrive(page);
const setSpeed = (v) => page.evaluate((v) => window.__settings.store.set("walkSpeed", v), v);
const placeCab = (y, door) => page.evaluate(([y, d]) => window.__game.tower.debugPlace(y, d), [y, door]);
const hudVisible = (v) => page.evaluate((v) => {
  let s = document.getElementById("__hudcss");
  if (!s) { s = document.createElement("style"); s.id = "__hudcss"; document.head.appendChild(s); }
  s.textContent = v ? "" : "#hud, #hud *{visibility:hidden!important}";
}, v);
// 自由机位连拍 (冻结控制器对相机的写入; 玩家位置不动, 设施照常更新)
async function scenery(shots) {
  await page.evaluate(() => { const g = window.__game; if (!g.__pu) g.__pu = g.player.update; g.player.update = () => {}; });
  for (const [name, p, t, fov] of shots) {
    await page.evaluate(([p, t, fov]) => {
      const c = window.__game.camera;
      c.fov = fov; c.updateProjectionMatrix();
      c.position.set(p[0], p[1], p[2]);
      c.lookAt(t[0], t[1], t[2]);
    }, [p, t, fov]);
    await page.waitForTimeout(450);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log("shot", name);
  }
  await page.evaluate(() => { const g = window.__game; g.player.update = g.__pu; delete g.__pu; g.camera.fov = 60; g.camera.updateProjectionMatrix(); });
}
// 玩家视角截图: 从当前位置看向目标
async function view(name, target) {
  await page.evaluate((target) => {
    const g = window.__game, p = g.player.pos, d = Math.hypot(target[0] - p.x, target[2] - p.z);
    g.player.setView(Math.atan2(-(target[0] - p.x), -(target[2] - p.z)), Math.atan2(target[1] - (p.y + 1.65), d));
  }, target);
  await page.waitForTimeout(450);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("shot", name);
}
// 走线断言: 走完 (不超时不卡住) + 条件; 失败时打印完整诊断
async function walk(name, route, arg, cond, { timeout = 30000, log = false } = {}) {
  const w = await drive(page, route, arg, timeout, log);
  const info = J({ ...w.pos, r: rc(w.pos), timedOut: w.timedOut, stuck: w.stuck, ms: w.ms, fps: w.fps, air: w.airFrames });
  check(name, !w.timedOut && !w.stuck && cond(w), info);
  return w;
}
const waitDwell = async (station, ms = 45000) => {
  const t0 = Date.now();
  let s = await towerState(page);
  while (Date.now() - t0 < ms && !(s.phase === "dwell" && s.at === station)) { await page.waitForTimeout(200); s = await towerState(page); }
  return { ...s, ms: Date.now() - t0 };
};
const waitPhase = async (pred, ms = 5000) => {
  const t0 = Date.now();
  let s = await towerState(page);
  while (Date.now() - t0 < ms && !pred(s)) { await page.waitForTimeout(100); s = await towerState(page); }
  return s;
};
// 乘升降梯到站 (前提: 已在轿厢内, 轿厢停站门开): 按 E → 页面内逐帧监视 → 到站门开满才返回。
// 监视器在同一帧里原子地读轿厢高度与玩家脚高 (分两次 evaluate 会跨帧: 4.5m/s 下一帧就差 3cm, 截图还会拉大采样间隔)
async function rideTo(station, shotName) {
  const from = station === "T" ? "B" : "T";
  await page.evaluate((from) => {
    const g = window.__game;
    const m = (window.__mon = { on: true, maxErr: 0, maxExcess: 0, air: 0, frames: 0, orderOk: true, plaque: false, lastY: null, lastCab: null });
    const k = from === "B" ? ["doorB", "lgB", "doorT", "lgT"] : ["doorT", "lgT", "doorB", "lgB"]; // [出发站轿门, 出发站层门, 到达站轿门, 到达站层门]
    const thk = window.__park.lift.floorThk;
    m.tick = () => {
      if (!m.on) return;
      requestAnimationFrame(m.tick);                       // 注册在游戏主循环之后: 每帧读到的是同一帧更新后的状态
      const s = g.tower.state, p = g.player.pos;
      if (s.phase === "closing" && s[k[1]] < 1 - 1e-6 && s[k[0]] > 1e-6) m.orderOk = false;   // 轿门没关严, 层门不该先动
      if (s.phase === "opening" && s[k[2]] > 1e-6 && s[k[3]] < 1 - 1e-6) m.orderOk = false;   // 层门没开满, 轿门不该先开
      if (s.phase === "moving") {
        m.frames++;
        m.maxErr = Math.max(m.maxErr, Math.abs(p.y - (s.y + thk)));                           // 脚底偏离轿厢地面
        if (g.player.airborne()) m.air++;
        if (!m.plaque) m.plaque = document.querySelector(".ride-plaque.show .plaque-name")?.textContent === "缠魂塔";
      }
      if (m.lastY !== null) m.maxExcess = Math.max(m.maxExcess, Math.abs((p.y - m.lastY) - (s.y - m.lastCab))); // 脚底位移超出轿厢位移的部分 (抖动)
      m.lastY = p.y; m.lastCab = s.y;
    };
    requestAnimationFrame(m.tick);
  }, from);
  const laps0 = (await towerState(page)).laps;
  await page.keyboard.press("KeyE");
  const t0 = Date.now();
  let sawMoving = false, shot = false, s = await towerState(page);
  while (Date.now() - t0 < 45000) {
    s = await towerState(page);
    if (s.phase === "moving") {
      sawMoving = true;
      if (shotName && !shot && s.y > 18) { shot = true; await page.screenshot({ path: `${OUT}/${shotName}.png` }); console.log("shot", shotName); }
    }
    if (sawMoving && s.phase === "dwell" && s.at === station) break;
    await page.waitForTimeout(100);
  }
  const m = await page.evaluate(() => {
    const m = window.__mon;
    m.on = false;
    return { maxErr: +m.maxErr.toFixed(4), maxExcess: +m.maxExcess.toFixed(4), air: m.air, frames: m.frames, orderOk: m.orderOk, plaque: m.plaque };
  });
  return { ...s, ...m, sawMoving, lapsDelta: s.laps - laps0, ms: Date.now() - t0,
    plaqueHidden: await page.evaluate(() => !document.querySelector(".ride-plaque").classList.contains("show")) };
}

// ---------- 块机制: 上一块没过 (或没跑) 时, 本块先按 teleport 摆前置状态 ----------
let lastOk = false;
async function block(id, title, setup, body) {
  if (ONLY && !ONLY.has(id)) return;
  const before = fails();
  if (!lastOk) { await setup(); await page.waitForTimeout(500); }
  console.log(`\n—— ${id} · ${title} ——`);
  try { await body(); } catch (e) { check(`${id} 块内中断`, false, String(e?.message ?? e).slice(0, 400)); }
  lastOk = fails() === before;
}

try {
  // ================= A =================
  await block("A", "加载与首帧", async () => {}, async () => {
    if (!(await page.evaluate(() => !!window.__game?.tower))) throw new Error("__game.tower 不存在: 塔模块未接入或加载失败");
    await setSpeed(6);
    const t = await towerState(page);
    check("加载: 轿厢停底层, 南侧层门+轿门开、北侧闭", t.phase === "dwell" && t.at === "B" && Math.abs(t.y - L.zBottom) < 1e-3 &&
      t.doorB === 1 && t.lgB === 1 && t.doorT === 0 && t.lgT === 0, J(t));
    const info = await page.evaluate(() => {
      const mats = new Set();
      window.__game.tower.root.traverse((o) => { if (o.isMesh) mats.add(o.material?.name); });
      const P = window.__park;
      return { mats: mats.size, floors: P.floors.length, pumpkins: P.pois.filter((p) => String(p.label).startsWith("pumpkin")).length,
        towers: P.steps.filter((s) => s.z === -118).length, steps: P.steps.length };
    });
    check("加载: 塔 glb 材质齐全 (26 种 TW_*)", info.mats === 26, `${info.mats} 种`);
    check("加载: 碰撞表已并入 park (叠层地面 8 / 南瓜灯打卡点 11), 旧塔台阶已不在", info.floors === 8 && info.pumpkins === 11 &&
      info.towers === 0 && info.steps === 16, J(info));

    await hudVisible(false);
    await scenery([
      ["g01_south_approach", [CX, 1.65, CZ + 11], [CX, 9, CZ], 75],
      ["g02_lobby_gate_cab_here", [CX, 1.65, CZ + 1.9], [CX, 1.6, CZ], 75],
      ["g03_call_lamp_green", [CX, 2.85, CZ + 3.2], [CX, 2.85, CZ + 1.77], 40],
      ["g04_old_tower_site", [20, 1.65, -104], [20, 5, -118], 60],
      ["g05_east_lawn", [42, 1.65, CZ], [CX, 21, CZ], 80],
    ]);
    await hudVisible(true);
    // 塔顶打卡点带高度: 西侧第二入口走廊就在它下方 (水平距 1.75m < 打卡半径 2.2m), 人在地面时不得出打卡提示
    await pose(page, 14.0, CZ - 0.1);
    await page.waitForTimeout(500);
    const gp = await promptText(page);
    check("打卡点带高度: 人在塔底西侧走廊 (水平距塔顶南瓜灯 1.75m) 不出打卡提示", gp === "" &&
      (await page.evaluate(() => window.__game.interact.collectedCount())) === 0, `prompt=「${gp}」`);
  });

  // ================= B =================
  await block("B", "出生点真键步行进轿厢", async () => { await pose(page, 0, 60); }, async () => {
    await pose(page, 0, 60);
    const w = await walk("出生点真键步行约 108m → 塔底门厅 → 走进轿厢 (脚高 0.14)", "line",
      [...SPAWN_PATH, [CX, CZ + 1.9], [CX, CZ + 0.15]], (w) => rc(w.pos) < 0.5 && Math.abs(w.pos.y - CAB_Y) < 0.02, { timeout: 70000 });
    await page.waitForTimeout(600);
    const pr = await promptText(page);
    check("轿厢内出「乘升降梯 · 登上塔顶」(键帽 E)", pr === "乘升降梯 · 登上塔顶" && (await promptKey(page)) === "E", `${pr} [${await promptKey(page)}]`);
    await view("g06_in_cab_bottom", [CX, 1.5, CZ + 4]);
  });

  // ================= C =================
  await block("C", "门洞防挟", async () => { await placeCab(L.zBottom, 1); await pose(page, CX, CZ + 0.2, CAB_Y); }, async () => {
    await setSpeed(2);
    const lean = await nudge(page, CX, CZ + 0.83, 0.03);           // 门口内侧, 离轿心 0.83m
    const pr = await promptText(page);
    check("门口内侧 (离轿心约 0.83m) 仍算在轿厢内, 可按 E", pr.startsWith("乘升降梯") && lean.d < 0.06, `${pr} dc=${rc(lean)} d=${lean.d}`);
    await page.keyboard.press("KeyE");
    await page.waitForTimeout(1500);
    let h = await towerState(page);
    check("门洞防挟: 人贴着门口时轿门不关 (停在 closing)", h.phase === "closing" && h.doorB === 1, J(h));
    await page.waitForTimeout(2600);
    h = await towerState(page);
    const hp = await pos(page);
    check("挡门超时 3s: 放弃本次运行, 回到停站且轿厢未动", h.phase === "dwell" && h.doorB === 1 && h.laps === 0 && Math.abs(hp.y - CAB_Y) < 0.02, J(h));
    check("挡门超时出提示", (await toastText(page)).includes("被挡住"), await toastText(page));
    await setSpeed(6);
  });

  // ================= D =================
  await block("D", "乘梯上塔 + 出厢上环廊", async () => { await placeCab(L.zBottom, 1); await pose(page, CX, CZ + 0.2, CAB_Y); }, async () => {
    await nudge(page, CX, CZ + 0.2, 0.06);
    await page.waitForTimeout(400);
    await page.keyboard.press("Space");
    await page.waitForTimeout(400);
    const jy = (await pos(page)).y;
    check("轿厢内禁跳 (净高 2.6m 不够眼高 + 跳高): 按空格脚底不动", Math.abs(jy - CAB_Y) < 0.02, `y=${jy}`);
    await page.keyboard.press("KeyE");
    const ride = await rideTo("T", "g07_ride_up_mid");
    check("乘梯上塔: 关门 → 升降 → 到站门开 (脚底全程贴着轿厢地面, 全程不离地, 无跳动)", ride.phase === "dwell" && ride.at === "T" &&
      ride.sawMoving && ride.maxErr < 1e-3 && ride.maxExcess < 1e-3 && ride.air === 0 && ride.lapsDelta === 1,
      J({ maxErr: ride.maxErr, maxExcess: ride.maxExcess, air: ride.air, frames: ride.frames, ms: ride.ms, lapsDelta: ride.lapsDelta }));
    check("门序: 先关轿门后关层门, 到站先开层门后开轿门", ride.orderOk, "");
    check("乘坐中出铭牌「缠魂塔」, 到站收起", ride.plaque && ride.plaqueHidden, J({ plaque: ride.plaque, hidden: ride.plaqueHidden }));
    check("到站提示", (await toastText(page)).includes("已到塔顶"), await toastText(page));
    const pp = await pos(page);
    check("到站: 玩家脚高 40.0", Math.abs(pp.y - TOP_Y) < 0.02, J(pp));
    await walk("顶层出厢: 经栈桥走上环廊", "line", [[CX, CZ - 1.6], [CX, CZ - 3.0], [CX, CZ - 4.6]], (w) => Math.abs(w.pos.y - 40) < 0.02 && rc(w.pos) > 3.6);
  });

  // ================= E =================
  await block("E", "环廊步行 + 塔顶打卡 + 摩天轮联锁", async () => { await placeCab(L.zTop, 1); await pose(page, CX, CZ - 4.6, 40); }, async () => {
    await walk("环廊逆时针绕行到打卡点 (沿环廊; 直线会穿梯井)", "line",
      [pt(240, 4.75), pt(210, 4.75), pt(180, 4.75), pt(168, 4.85), pt(163.5, 4.8)], (w) => Math.abs(w.pos.y - 40) < 0.02 && w.airFrames === 0, { timeout: 30000 });
    await page.waitForTimeout(400);
    const pr = await promptText(page);
    check("塔顶打卡点: 环廊上出「收集南瓜灯（1/11）」", pr.startsWith("收集南瓜灯（1/"), pr);
    await view("g08_deck_poi", [man.pois[0].x, 40.4, man.pois[0].z]);
    await page.keyboard.press("KeyE");
    await page.waitForTimeout(400);
    const got = await page.evaluate(() => ({ n: window.__game.interact.collectedCount(), total: window.__game.interact.poiTotal(),
      lit: document.querySelectorAll("#hud .star-map svg.lit").length }));
    check("按 E 收下塔顶南瓜灯, 星图点亮 1/11", got.n === 1 && got.total === 11 && got.lit === 1, J(got));
    await walk("环廊继续绕行到东南角", "line", [pt(150, 4.8), pt(120, 4.75), pt(60, 4.8), pt(45, 4.8)], (w) => Math.abs(w.pos.y - 40) < 0.02 && w.airFrames === 0,
      { timeout: 30000 });
    const dTheta = await page.evaluate(async () => { const s = window.__game.ferris.state; const a = s.theta; await new Promise((r) => setTimeout(r, 1500)); return Math.abs(s.theta - a); });
    check("站在塔顶环廊时摩天轮照常转 (联锁不再只看脚高)", dTheta > 0.15, `Δθ=${dTheta.toFixed(3)} rad / 1.5s · 脚高 ${(await pos(page)).y}`);
    await view("g09_deck_view", [0, 22, 0]);
  });

  // ================= F =================
  await block("F", "真键走螺旋梯下 / 上", async () => { await placeCab(L.zTop, 1); await pose(page, ...pt(145, 4.9), 40); }, async () => {
    await pose(page, ...pt(145, 4.9), 40);
    let w = await walk("真键走螺旋梯下行: 环廊 → 242 级 → 梯口外地面 (全程贴地)", "descend", null,
      (w) => w.pos.y < 0.2 && rc(w.pos) > 4.5 && w.airFrames === 0, { timeout: 90000, log: true });
    console.log("   下梯轨迹 (ms, x, y, z):", JSON.stringify(w.log));
    const fs = await towerState(page);
    check("走楼梯下到梯底后轿厢仍停在顶层 (梯口离底层停站点 3.6m, 不触发呼梯)", fs.phase === "dwell" && fs.at === "T", J(fs));
    await pose(page, ...pt(43, 5.0));
    w = await walk("真键走螺旋梯上行: 梯口 → 242 级 → 到达口 → 环廊 (脚高 40.0, 全程贴地)", "climb", null,
      (w) => w.pos.y > 39.99 && rc(w.pos) > 4.3 && w.airFrames === 0, { timeout: 90000, log: true });
    console.log("   上梯轨迹 (ms, x, y, z):", JSON.stringify(w.log));
  });

  // ================= G =================
  await block("G", "乘梯下塔", async () => { await placeCab(L.zTop, 1); await pose(page, ...pt(145, 4.9), 40); }, async () => { // 起点同 F 块终点 (到达口)
    await walk("环廊绕行到栈桥 (沿环廊经东侧)", "line", [pt(110, 4.75), pt(70, 4.75), pt(30, 4.75), pt(340, 4.75), pt(305, 4.8), pt(275, 4.8), [CX, CZ - 1.6], [CX, CZ - 0.15]],
      (w) => rc(w.pos) < 0.5 && Math.abs(w.pos.y - TOP_Y) < 0.02 && w.airFrames === 0, { timeout: 40000 });
    await page.waitForTimeout(600);
    const pr = await promptText(page);
    check("走进顶层轿厢: 出「乘升降梯 · 下到塔底」", pr === "乘升降梯 · 下到塔底", pr);
    await page.keyboard.press("KeyE");
    const ride = await rideTo("B", "g10_ride_down_mid");
    check("乘梯下塔: 到站门开, 脚底全程贴着轿厢地面, 全程不离地", ride.phase === "dwell" && ride.at === "B" && ride.sawMoving &&
      ride.maxErr < 1e-3 && ride.maxExcess < 1e-3 && ride.air === 0 && ride.lapsDelta === 1, J({ maxErr: ride.maxErr, maxExcess: ride.maxExcess, air: ride.air, frames: ride.frames, ms: ride.ms }));
    check("门序 (下行): 先关轿门后关层门, 到站先开层门后开轿门", ride.orderOk, "");
    await walk("底层出厢: 走回南门廊", "line", [[CX, CZ + 1.9], [CX, CZ + 3.4]], (w) => w.pos.y < 0.2 && rc(w.pos) > 2.5);
  });

  // ================= H =================
  await block("H", "顶层自动呼梯", async () => { await placeCab(L.zBottom, 1); await pose(page, CX, CZ - 4.1, 40); }, async () => {
    await pose(page, CX, CZ - 4.1, 40);                                  // 栈桥南端 (离停站点 1.1m)
    let h = await waitPhase((s) => s.phase !== "dwell", 3000);
    check("走近顶层停站点: 轿厢自动从底层出发", h.phase === "closing" || h.phase === "moving", J(h));
    await page.waitForTimeout(500);
    const pr = await promptText(page);
    check("等梯时出指引「升降梯正在赶来」(键帽 ↓)", pr === "升降梯正在赶来" && (await promptKey(page)) === "↓", `${pr} [${await promptKey(page)}]`);
    check("呼梯出提示", (await toastText(page)).includes("正在赶来"), await toastText(page));
    await view("g11_waiting_at_top", [CX, 40.8, CZ]);
    const w = await drive(page, "line", [[CX, CZ]], 8000);
    check("轿厢不在顶层: 栈桥上走不进门洞 (层门挡住)", w.stuck && w.pos.z <= CZ - 2.2 && Math.abs(w.pos.y - 40) < 0.02, J({ ...w.pos, r: rc(w.pos), stuck: w.stuck, timedOut: w.timedOut }));
    h = await waitDwell("T");
    check("轿厢到顶层: 层门 + 轿门开满", h.phase === "dwell" && h.at === "T" && h.doorT === 1 && h.lgT === 1, J(h));
    check("到站提示", (await toastText(page)).includes("已到站"), await toastText(page));
    check("轿厢在站、人在栈桥: 出指引「走进轿厢 · 按 E 升降」(非 E 动作)", (await promptText(page)) === "走进轿厢 · 按 E 升降", await promptText(page));
    await hudVisible(false);
    await scenery([
      ["g12_cab_top_open", cam(270, 4.4, 41.65), cam(270, 1.7, 41.2), 70],
      ["g13_deck_to_lantern", cam(45, 4.8, 41.65), [CX, 44.3, CZ], 60],
      ["g14_crown", [30, 52, CZ + 18.5], [CX, 43, CZ], 45],
    ]);
    await hudVisible(true);
  });

  // ================= I =================
  await block("I", "底层自动呼梯", async () => { await placeCab(L.zTop, 1); await pose(page, CX, CZ + 3.4); }, async () => {
    await pose(page, ...pt(43, 5.0));                                      // 先站到螺旋梯梯口外 (方位 43°, 离停站点 3.6m)
    await page.waitForTimeout(1500);
    const q = await towerState(page);
    check("站在梯口外 (南门扇区之外) 不呼梯: 轿厢仍停顶层", q.phase === "dwell" && q.at === "T" && q.doorT === 1, J(q));
    await pose(page, CX, CZ + 3.4);                                      // 南门廊上 (正对南门) → 自动呼梯
    let h = await waitPhase((s) => s.phase !== "dwell", 3000);
    check("走近底层停站点: 轿厢自动从顶层出发", h.phase === "closing" || h.phase === "moving", J(h));
    await page.waitForTimeout(2500);                                     // 等顶层门关完、轿厢离站
    const w = await drive(page, "line", [[CX, CZ]], 8000);
    check("轿厢不在底层: 门厅里走不进门洞 (层门挡住)", w.stuck && w.pos.z >= CZ + 2.2 && w.pos.y < 0.3, J({ ...w.pos, r: rc(w.pos), stuck: w.stuck }));
    await hudVisible(false);
    await scenery([["g15_gate_closed_cab_away", [CX, 1.65, CZ + 2.1], [CX, 1.8, CZ], 70]]);
    await hudVisible(true);
    h = await waitDwell("B");
    check("轿厢回底层: 门开满", h.phase === "dwell" && h.at === "B" && h.doorB === 1 && h.lgB === 1, J(h));
    await walk("轿厢到站后: 门厅走进轿厢", "line", [[CX, CZ + 0.15]], (w) => rc(w.pos) < 0.5 && Math.abs(w.pos.y - CAB_Y) < 0.02);
  });

  // ================= J =================
  await block("J", "装饰灯设置联动", async () => {}, async () => {
    const glow = async (k) => { await page.evaluate((k) => window.__settings.store.set("towerDecoLight", k), k); await page.waitForTimeout(250);
      return page.evaluate(() => { const m = {}; window.__game.tower.root.traverse((o) => { if (o.isMesh && o.material?.emissive) m[o.material.name] = o.material.emissiveIntensity; });
        return { ribbon: m.TW_Ribbon, rail: m.TW_Rail, glow: m.TW_Glow, lampB: m.TW_CallLamp_B }; }); };
    const g100 = await glow(100), g0 = await glow(0), g200 = await glow(200);
    check("「缠魂塔 · 装饰灯亮度」100% = 资产档位", Math.abs(g100.ribbon - 1.6) < 1e-3 && Math.abs(g100.rail - 1) < 1e-3 && Math.abs(g100.glow - 2.6) < 1e-3, J(g100));
    check("装饰灯 0% 全灭 / 200% 翻倍", g0.ribbon === 0 && g0.rail === 0 && Math.abs(g200.ribbon - 3.2) < 1e-3 && Math.abs(g200.glow - 5.2) < 1e-3, J({ g0, g200 }));
    check("呼梯灯亮度随装饰灯档位", g0.lampB === 0 && g200.lampB > g100.lampB * 1.5, J({ a: g100.lampB, b: g0.lampB, c: g200.lampB }));
    await page.evaluate(() => window.__settings.store.set("towerDecoLight", 100));
  });

  // ================= K =================
  await block("K", "摩天轮联锁回归", async () => {}, async () => {
    await pose(page, 0, 1.6, 1.55);
    await page.waitForTimeout(4500);
    const dTheta = await page.evaluate(async () => { const s = window.__game.ferris.state; const a = s.theta; await new Promise((r) => setTimeout(r, 1500)); return Math.abs(s.theta - a); });
    check("站在摩天轮登舱站台: 轮体刹停吸附 (联锁回归)", dTheta < 0.01, `Δθ=${dTheta.toFixed(4)} rad / 1.5s · ${await promptText(page)}`);
  });

  // ================= L =================
  await block("L", "栏杆不漏 (真键撞栏杆)", async () => {}, async () => {
    const HX = man.floors.find((f) => f.shape === "helix");
    const stepPt = (k, r) => { const a = HX.a0 + HX.da * HX.dir * (k + 0.5); return [+(CX + r * Math.cos(a)).toFixed(3), +(CZ + r * Math.sin(a)).toFixed(3)]; };
    const ram = async (name, start, y, target, cond) => {        // 传送到起点, 朝目标一直走: 应卡住 (stuck) 且高度只差不超过一级 (0.17m) —— 没掉下去
      await pose(page, ...start, y);
      const w = await drive(page, "line", [target], 7000);
      check(name, w.stuck && Math.abs(w.pos.y - y) < 0.21 && cond(w), J({ ...w.pos, r: rc(w.pos), stuck: w.stuck, timedOut: w.timedOut }));
    };
    await ram("环廊外栏杆: 朝外撞不出去", pt(60, 4.4), 40, pt(60, 8), (w) => rc(w.pos) < 5.4);
    await ram("环廊内栏杆 (200° 处无开口): 朝梯井撞不进去", pt(200, 4.6), 40, [CX, CZ], (w) => rc(w.pos) > 3.5);
    await ram("梯上第 120 级: 朝外撞不出去 (外栏杆)", stepPt(120, 2.54), HX.h[120], stepPt(120, 6), (w) => rc(w.pos) < 3.3);
    await ram("梯上第 120 级: 朝内撞不进梯井 (核心笼)", stepPt(120, 2.54), HX.h[120], stepPt(120, 0.3), (w) => rc(w.pos) > 1.5);
  });
} catch (e) {
  check("脚本执行中断", false, String(e?.message ?? e).slice(0, 400));
}

// ---------- 汇总 ----------
check("控制台无报错", errors.length === 0, errors.slice(0, 5).join(" | "));
console.log(`\ntower-game: ${R.length - fails()}/${R.length} passed`);
await browser.close();
process.exit(fails() ? 1 : 0);
