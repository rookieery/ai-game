// 缠魂塔碰撞表离线校验（模型侧）：按 lib_tower_sim 的语义走线、量通道、查漏（跑完建模脚本后执行）
// 用法: node scripts/verify_tower_colliders.mjs        （任一项 FAIL 则 exit 1）
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loadTower, makeSim, PR, STEP, HEAD, ROOT } from "./lib_tower_sim.mjs";

const man = loadTower();
const S = makeSim(man);
const { pol, walk, probe, liftState } = S;
const AZ = man.azimuths;
const HX = man.floors.find((f) => f.shape === "helix");
const DA = (HX.da * HX.dir * 180) / Math.PI;                 // 每级方位增量（度，负 = 方位递减）
const A0 = (HX.a0 * 180) / Math.PI;
const stepA = (k) => A0 + DA * k;
const stepH = (k) => (HX.h ? HX.h[k] : HX.rise * (k + 1));
const R = (v, n = 3) => +v.toFixed(n);
const res = [];
const check = (name, ok, info = "") => { res.push({ name, ok }); console.log(`${ok ? "ok  " : "FAIL"}: ${name}${info ? "  — " + info : ""}`); };
const seq = (a, b, d) => { const o = []; for (let v = a; (d > 0 ? v <= b : v >= b); v += d) o.push(v); return o; };
const azOf = (x, z) => (((Math.atan2(z - man.place.z, x - man.place.x) * 180) / Math.PI) + 360) % 360;
const dAz = (a, b) => Math.abs((((a - b) % 360) + 540) % 360 - 180);

// ---------- 1. 螺旋梯表 ----------
const turns = (HX.n * HX.da) / (2 * Math.PI);
const rises = HX.h.slice(1).map((h, i) => h - HX.h[i]);
check("螺旋梯: 242 级 / 每级高<=0.35 且>0 / 4.8 圈 / 到顶 40.0", HX.n === 242 && Math.max(...rises) <= STEP && Math.min(...rises) > 0.05 && Math.abs(turns - 4.8) < 1e-6 && Math.abs(HX.h[HX.n - 1] - 40) < 0.01,
  `n=${HX.n} 级高 ${R(Math.min(...rises), 4)}..${R(Math.max(...rises), 4)} turns=${R(turns, 3)} top=${R(HX.h[HX.n - 1], 4)}`);
check("方位: 门厅 90 / 顶门 270 / 梯口 58 / 到达 130", [AZ.doorBottom, AZ.doorTop, AZ.stairStart, AZ.stairArrive].every((v, i) => Math.abs((((v % 360) + 360) % 360) - [90, 270, 58, 130][i]) < 0.01),
  JSON.stringify(AZ));

// ---------- 2. 沿梯心线上到顶 ----------
const stairPts = seq(0.25, HX.n - 2.6, 0.25).map((u) => pol(stepA(0) + DA * u, 2.54));   // 到尽头护栏前
const wStair = walk(stairPts);
check("梯心线上行: 无阻挡 / 无坠落 / 到第 240 级 (39.67m)", !wStair.stopped && wStair.falls === 0 && Math.abs(wStair.feet - stepH(239)) < 0.02,
  `stop=${wStair.stopped} falls=${wStair.falls} feet=${R(wStair.feet)} ${wStair.stopped ? wStair.samples.at(-1).why : ""}`);

// ---------- 3. 到达口出梯带 ----------
const exOk = [];
for (let az = 124; az <= 158; az += 0.25) {
  const pts = seq(2.54, 4.9, 0.1).map((r) => pol(az, r));
  const w = walk(pts, { startFeet: 39.9 });
  if (!w.stopped && w.falls === 0 && w.feet > 39.99) exOk.push(az);
}
const exLo = Math.min(...exOk), exHi = Math.max(...exOk);
const exChord = 2 * 3.4 * Math.sin(((exHi - exLo) * Math.PI) / 360);
check("到达口出梯带 >= 0.65m (弦长 @r3.4; 靠外缘处约 0.85m)", exOk.length > 0 && exHi - exLo - exOk.length * 0.25 < 0.5 && exChord >= 0.65,
  `可出方位 ${R(exLo, 2)}°..${R(exHi, 2)}° = ${R(exChord, 2)}m`);
const wFall = walk(seq(144, 118, -0.5).map((a) => pol(a, 2.4)), { startFeet: stepH(241) });   // 沿末级弧线走向井一侧
const stopAz = wFall.stopped ? azOf(wFall.samples.at(-1).x, wFall.samples.at(-1).z) : null;
check("到达口井一侧: 沿末级走过去在梯子尽头 (130°) 前被护栏挡住", wFall.stopped && wFall.falls === 0 && stopAz >= 137 && stopAz <= 141.5,
  wFall.stopped ? `挡在 ${R(stopAz, 1)}° — ${wFall.samples.at(-1).why}` : `掉下去 feet=${R(wFall.feet)}`);

// ---------- 4. 环廊成环 ----------
let ringMin = { d: Infinity };
for (const dir of [1, -1]) {
  const pts = (dir > 0 ? seq(0, 360, 1) : seq(0, -360, -1)).map((d) => pol(133.5 + d, 4.9));
  const w = walk(pts, { startFeet: 40.0 });
  let minC = Infinity, minAz = 0;
  for (const p of w.samples) {
    for (const c of man.circles) {
      if (40 < c.y0 || 40 > c.y1) continue;
      const d = Math.hypot(p.x - c.x, p.z - c.z) - (c.r + PR);
      if (d < minC) { minC = d; minAz = (Math.atan2(p.z - man.place.z, p.x - man.place.x) * 180) / Math.PI; }
    }
  }
  check(`环廊 r4.9 绕行一圈 (${dir > 0 ? "顺" : "逆"}向): 无阻挡`, !w.stopped && w.feet === 40.0, w.stopped ? w.samples.at(-1).why : `最小侧向余隙 ${R(minC)}m @${R(minAz, 1)}°`);
  if (minC < ringMin.d) ringMin = { d: minC, az: minAz };
}
let bandMin = Infinity, bandMinAz = 0, narrow = [];
for (let az = 0; az < 360; az += 2) {
  let lo = null, hi = null;
  for (let r = 3.0; r <= 6.3; r += 0.05) {
    const [x, z] = pol(az, r);
    const pp = probe(x, z, 40.0);
    if (!pp.blocked && pp.support >= 39.99) { if (lo === null) lo = r; hi = r; }
  }
  const wdt = hi - lo;
  if (wdt < bandMin) { bandMin = wdt; bandMinAz = az; }
  if (wdt < 0.6) narrow.push(az);
}
check("环廊全程可走带 >= 0.6m (每 2° 扫描 r3.0-6.3)", narrow.length === 0, `最窄 ${R(bandMin)}m @${bandMinAz}°${narrow.length ? "；窄于 0.6m: " + narrow.join(",") : ""}`);

// ---------- 5. 升降梯：底层进厢 / 顶层出厢 / 轿门宽 ----------
const liftB = liftState(man.lift.zBottom, { gateB: false, gateT: true, lgateB: false, lgateT: true });
const liftT = liftState(man.lift.zTop, { gateB: true, gateT: false, lgateB: true, lgateT: false });
const wIn = walk(seq(7.0, 0.0, -0.1).map((r) => pol(90, r)), { lift: liftB });
check("底层: 门厅外 (r7) 走进轿厢中心", !wIn.stopped && Math.abs(wIn.feet - (man.lift.zBottom + man.lift.floorThk)) < 0.01,
  `stop=${wIn.stopped} feet=${R(wIn.feet)} ${wIn.stopped ? wIn.samples.at(-1).why : ""}`);
const free = [];
for (let o = -0.75; o <= 0.75; o += 0.02) {
  const a = (90 * Math.PI) / 180;
  const x = pol(90, 1.45)[0] + -Math.sin(a) * o, z = pol(90, 1.45)[1] + Math.cos(a) * o;
  if (!probe(x, z, man.lift.zBottom + man.lift.floorThk, liftB).blocked) free.push(o);
}
const doorW = Math.max(...free) - Math.min(...free);
check("轿厢门洞: 玩家圆心可走宽 >= 0.40m", doorW >= 0.4, `${R(doorW)}m`);
const wTop = walk(seq(4.9, 0.0, -0.1).map((r) => pol(270, r)), { lift: liftT, startFeet: 40.0 });
check("顶层: 环廊 (r4.9) 经栈桥走进轿厢中心 (门槛有地面)", !wTop.stopped && wTop.feet === 40.0, `stop=${wTop.stopped} feet=${R(wTop.feet)} ${wTop.stopped ? wTop.samples.at(-1).why : ""}`);
const wOut = walk(seq(0.0, 4.9, 0.1).map((r) => pol(270, r)), { lift: liftT, startFeet: 40.0 });
check("顶层: 轿厢中心走出到环廊", !wOut.stopped && wOut.feet === 40.0, wOut.stopped ? wOut.samples.at(-1).why : "");
const wSill = walk(seq(0.0, 4.9, 0.1).map((r) => pol(270, r)), { lift: liftState(man.lift.zBottom), startFeet: 40.0 });
check("顶层门槛: 轿厢不在顶层时不能跨出 (层门闭合)", wSill.stopped, wSill.stopped ? wSill.samples.at(-1).why : `feet=${R(wSill.feet)}`);
// 轿厢行进中 (轿门全关): 泛洪不许漏出轿厢 —— 立梃之间是玻璃板, 碰撞盘必须连成墙
const midY = +(man.lift.zBottom + 15).toFixed(4);
const cabLeak = gridFlood([man.place.x, man.place.z, +(midY + man.lift.floorThk).toFixed(2)],
  { lift: liftState(midY, { gateB: true, gateT: true, lgateB: true, lgateT: true }), step: 0.05, rMax: 2.2,
    leak: (x, z) => Math.hypot(x - man.place.x, z - man.place.z) > man.lift.cabR + 0.01 });
check("轿厢行进中 (轿门全关): 泛洪漏不出轿厢", cabLeak.leaks === 0, `${cabLeak.states} 态, 漏点 ${cabLeak.leaks}`);

// ---------- 6. 地面层：第二入口 / 梯口来路 / 封闭开间 ----------
const wWest = walk([...seq(7.0, 2.6, -0.1).map((r) => pol(180, r)), ...seq(178, 92, -2).map((a) => pol(a, 2.6)), ...seq(2.6, 0.0, -0.1).map((r) => pol(90, r))], { lift: liftB });
check("西侧第二入口: 进塔底、绕到门厅、进轿厢", !wWest.stopped && Math.abs(wIn.feet - wWest.feet) < 0.01, wWest.stopped ? wWest.samples.at(-1).why : "");
const wEnt = walk(seq(7.0, 2.54, -0.1).map((r) => pol(43, r)));
check("东南梯口: 从草坪沿开间中线 (33°) 走到第 0 级", !wEnt.stopped && wEnt.feet > 0.1, wEnt.stopped ? wEnt.samples.at(-1).why : `feet=${R(wEnt.feet)}`);
let entryBand = [];
for (let az = 30; az <= 56; az += 0.25) { const w = walk(seq(6.5, 2.9, -0.1).map((r) => pol(az, r))); if (!w.stopped && w.feet > 0.1) entryBand.push(az); }
check("梯口进梯带 >= 0.8m (弦长 @r3.4)", entryBand.length > 0 && 2 * 3.4 * Math.sin(((Math.max(...entryBand) - Math.min(...entryBand)) * Math.PI) / 360) >= 0.8,
  `${R(Math.min(...entryBand), 2)}°..${R(Math.max(...entryBand), 2)}° = ${R(2 * 3.4 * Math.sin(((Math.max(...entryBand) - Math.min(...entryBand)) * Math.PI) / 360), 2)}m`);
let closedOk = 0;
const openMid = [45, 90, 180];
for (let a1 = 0; a1 < 360; a1 += 22.5) {
  const mid = a1 + 11.25;
  if (openMid.some((o) => Math.abs(mid - o) < 12)) continue;
  if (walk(seq(5.5, 3.0, -0.1).map((r) => pol(mid, r))).stopped) closedOk++;
}
check("首层 10 个封闭开间: 全部进不去", closedOk === 10, `${closedOk}/10`);
const lobbyMid = walk(seq(5.5, 3.0, -0.1).map((r) => pol(90, r)));
const westMid = walk(seq(5.5, 3.0, -0.1).map((r) => pol(180, r)));
check("首层 3 个入口开间 (45/90/180°): 全部进得去", !lobbyMid.stopped && !westMid.stopped && !wEnt.stopped);

// ---------- 7. 漏点检查（泛洪） ----------
function gridFlood(seed, { lift = null, step = 0.05, rMax = 6.3, leak }) {
  const seen = new Set();
  const leakLog = [];
  const [sx, sz, sf] = seed;
  const q = [[Math.round((sx - man.place.x) / step), Math.round((sz - man.place.z) / step), sf]];
  seen.add(`${q[0][0]}|${q[0][1]}|${sf.toFixed(2)}`);
  let leaks = 0;
  let n = 0;
  while (q.length) {
    const [i, j, feet] = q.pop();
    n++;
    const x = man.place.x + i * step, z = man.place.z + j * step;
    const rr = Math.hypot(x - man.place.x, z - man.place.z);
    if (leak(x, z, feet, rr)) { leaks++; if (leakLog.length < 6) leakLog.push(`(${R(x, 2)},${R(z, 2)}) r=${R(rr)} az=${R(azOf(x, z), 1)} feet=${feet}`); continue; }
    for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const ii = i + di, jj = j + dj;
      const xx = man.place.x + ii * step, zz = man.place.z + jj * step;
      if (Math.hypot(xx - man.place.x, zz - man.place.z) > rMax) continue;
      const p = probe(xx, zz, feet, lift);
      if (p.blocked) continue;
      if (feet - p.support > 0.6) {                              // 坠落
        leaks++;
        if (leakLog.length < 6) leakLog.push(`坠落 (${R(xx, 2)},${R(zz, 2)}) r=${R(Math.hypot(xx - man.place.x, zz - man.place.z))} az=${R(azOf(xx, zz), 1)} ${feet}->${R(p.support)} 落点地面=${p.support > 0 ? "有" : "无"}`);
        continue;
      }
      const nf = +p.support.toFixed(2);
      const k = `${ii}|${jj}|${nf}`;
      if (seen.has(k)) continue;
      seen.add(k);
      q.push([ii, jj, nf]);
    }
  }
  return { states: seen.size, leaks, n, leakLog };
}
const deckLeak = gridFlood([...pol(200, 4.9), 40.0], {
  lift: liftT,
  leak: (x, z, feet, rr) => {
    const a = azOf(x, z);
    const arr0 = (((AZ.stairArrive - 0.5) % 360) + 360) % 360, arr1 = (arr0 + DA * -1 + 1.0) % 360;   // 末级扇区
    const onLast = a > arr0 - 0.5 && a < arr1 + 0.5;
    return (rr > 5.66 && feet >= 39.3) || (rr < 3.28 && rr > 1.40 && feet >= 39.99 && dAz(a, 270) > 15 && !(rr < 1.80 && dAz(a, 270) <= 34) && !onLast);
  },
});
check("环廊泛洪: 漏不出外栏杆、不掉进梯井 (栈桥口/到达口除外)", deckLeak.leaks === 0, `${deckLeak.states} 态, 漏点 ${deckLeak.leaks} ${deckLeak.leakLog.join(" | ")}`);
const liftClosed = liftState(man.lift.zBottom, { gateB: true, gateT: true, lgateB: true, lgateT: true });
const stairLeak = gridFlood([...pol(stepA(40) + DA * 0.5, 2.54), stepH(40)], {
  rMax: 6.3, lift: liftClosed,
  leak: (x, z, feet, rr) => rr < 1.62 || (feet >= 1.0 && feet < 39.3 && rr > 3.82),
});
check("梯上泛洪 (第 40 级起): 漏不出外栏杆 (到环廊为止)", stairLeak.leaks === 0, `${stairLeak.states} 态, 漏点 ${stairLeak.leaks} ${stairLeak.leakLog.join(" | ")}`);

// ---------- 8. 与过山车碰撞表合并: 地面可达性 ----------
function world(lift) {
  const rd = (f) => JSON.parse(readFileSync(resolve(ROOT, f), "utf8"));
  const cc = rd("model/roller_coaster/colliders_coaster.json");
  const park = rd("model/park_env/colliders.json");
  const walls = [...cc.rects.filter((r) => !r.blockFrom), ...(park.rects ?? [])];
  const oc = [...cc.circles, ...(park.circles ?? [])];
  return (x, z, feet) => {
    if (Math.hypot(x, z) > park.boundaryR - PR) return null;
    for (const w of walls) if (Math.abs(x - w.x) <= w.hw + PR && Math.abs(z - w.z) <= w.hd + PR) return null;
    let support = 0, wall = false;
    for (const { h } of S.floorHeights(x, z, lift)) { if (h <= feet + STEP + 1e-9) support = Math.max(support, h); else if (h <= feet + HEAD + 1e-9) wall = true; }
    for (const s of [...(cc.steps ?? []), ...(oc.filter((c) => c.h !== undefined))]) {
      const inside = s.hw !== undefined ? Math.abs(x - s.x) <= s.hw + 0.05 && Math.abs(z - s.z) <= s.hd + 0.05 : Math.hypot(x - s.x, z - s.z) <= s.r + 0.05;
      if (!inside) continue;
      if (feet < s.h - STEP - 1e-9) return null;
      if (s.h <= feet + STEP + 1e-9) support = Math.max(support, s.h);
    }
    if (wall) return null;
    const all = [...man.circles, ...oc.filter((c) => c.h === undefined), ...(lift ? lift.discs : [])];
    for (const c of all) { if (support < c.y0 - 1e-9 || support > c.y1 + 1e-9) continue; if (Math.hypot(x - c.x, z - c.z) <= c.r + PR + 1e-12) return null; }
    return support;
  };
}
function reach(seeds, lift, X0 = 7.5, X1 = 26.0, Z0 = -42.5, Z1 = -19.5, h = 0.1) {
  const enter = world(lift);
  const NX = Math.round((X1 - X0) / h) + 1, NZ = Math.round((Z1 - Z0) / h) + 1;
  const dist = new Map();
  let frontier = [];
  for (const [x, z, f] of seeds) {
    const i = Math.round((x - X0) / h), j = Math.round((z - Z0) / h);
    const s = enter(X0 + i * h, Z0 + j * h, f);
    if (s === null) { console.log("  (种子点不可站:", x, z, ")"); continue; }
    const k = `${i}|${j}|${s.toFixed(2)}`; dist.set(k, 0); frontier.push([i, j, s]);
  }
  let d = 0;
  while (frontier.length) {
    const nxt = [];
    for (const [i, j, s] of frontier) for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const ii = i + di, jj = j + dj;
      if (ii < 0 || jj < 0 || ii >= NX || jj >= NZ) continue;
      const ns = enter(X0 + ii * h, Z0 + jj * h, s);
      if (ns === null) continue;
      const k = `${ii}|${jj}|${ns.toFixed(2)}`;
      if (dist.has(k)) continue;
      dist.set(k, d + 1);
      nxt.push([ii, jj, ns]);
    }
    frontier = nxt; d++;
  }
  return (x, z, feet) => {
    let best = Infinity;
    for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) {
      const v = dist.get(`${Math.round((x - X0) / h) + dx}|${Math.round((z - Z0) / h) + dz}|${feet.toFixed(2)}`);
      if (v !== undefined && v < best) best = v;
    }
    return best;
  };
}
const seeds = [[17.5, -23.5, 0], [9.5, -30.5, 0], [13.6, -40.2, 0]];
const at = reach(seeds, liftB);
const targets = [["门厅前 (r4.6@90°)", pol(90, 4.6), 0.1], ["梯口 (r4.0@45°)", pol(45, 4.0), 0], ["底层轿厢中心", [17.5, -30.5], 0.14],
  ["第 0 级", pol(stepA(0) + DA * 0.5, 2.54), stepH(0)], ["第 120 级", pol(stepA(120) + DA * 0.5, 2.54), stepH(120)],
  ["第 240 级", pol(stepA(240) + DA * 0.5, 2.54), R(HX.rise * 241, 2)], ["环廊到达点 (145°)", pol(145, 4.2), 40.0], ["环廊 200°", pol(200, 4.9), 40.0], ["环廊 0°", pol(0, 4.9), 40.0], ["环廊 330°", pol(330, 4.9), 40.0]];
for (const [n, [x, z], f] of targets) check(`可达: ${n}`, at(x, z, f) < Infinity, at(x, z, f) < Infinity ? `${at(x, z, f)} 步` : "不可达");
const atT = reach([[17.5, -30.5, 40.0]], liftT);
check("可达: 顶层轿厢中心 (自环廊出发, 轿厢在顶层)", atT(17.5, -30.5, 40.0) < Infinity);

// ---------- 汇总 ----------
const fails = res.filter((r) => !r.ok);
console.log(`\n tower-colliders: ${res.length - fails.length}/${res.length} passed${fails.length ? "  FAILED x" + fails.length : ""}`);
if (fails.length) process.exitCode = 1;
