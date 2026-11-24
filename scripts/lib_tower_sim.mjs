// 缠魂塔碰撞表离线行走模拟器（模型侧校验用；与 controller.js 的塔语义须保持一致）
// 玩家 = 半径 PR 的圆；坐标 = app 坐标 (x, z)，高度 y。
// 语义（colliders_tower.json 的 note）：
//   floors  叠层地面：落点处只取「高度 <= 脚底+STEP」的最高一块为支撑；
//           存在高度落在 (脚底+STEP, 脚底+HEAD] 的地面 => 墙；更高的可从下方走过。
//   circles 带 y0/y1：仅脚底高度落在带内才推挤，推挤半径 = r + PR。
//   lift    轿厢地面 / 轿壁与轿门高度带随轿厢平移；层门 gateBottom/gateTop 在轿厢不在该站时闭合。
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export const PR = 0.38;
export const STEP = 0.35;
export const GRACE = 0.05;
export const HEAD = 1.8;
export const TAU = Math.PI * 2;
export const ROOT = resolve(import.meta.dirname, "..");

export function loadTower(file = "model/lookout_tower/colliders_tower.json") {
  return JSON.parse(readFileSync(resolve(ROOT, file), "utf8"));
}

export function makeSim(man) {
  const PLACE = man.place;
  const normA = (a) => ((a % TAU) + TAU) % TAU;
  const loc = (x, z) => [x - PLACE.x, z - PLACE.z];              // app -> 塔心相对
  const app = (lx, lz) => [PLACE.x + lx, PLACE.z + lz];
  const pol = (azDeg, r) => [PLACE.x + r * Math.cos((azDeg * Math.PI) / 180), PLACE.z + r * Math.sin((azDeg * Math.PI) / 180)];

  // 升降梯状态: y = 轿底高; gateB/gateT = 轿门关闭; lgateB/lgateT = 层门关闭
  function liftState(y = man.lift.zBottom, { gateB = false, gateT = false, lgateB = false, lgateT = true } = {}) {
    const L = man.lift;
    const dy = y - L.zBottom;
    const sh = (c, y0, y1) => ({ ...c, y0: y0 + dy, y1: y1 + dy });
    const discs = L.walls.map((c) => sh(c, ...L.wallBand));
    if (gateB) discs.push(sh(L.gateB.post, ...L.wallBand));
    if (gateT) discs.push(sh(L.gateT.post, ...L.wallBand));
    if (lgateB) discs.push(...L.gateBottom.map((c) => ({ ...c, y0: L.lgateB.closedBand[0], y1: L.lgateB.closedBand[1] })));
    if (lgateT) discs.push(...L.gateTop.map((c) => ({ ...c, y0: L.lgateT.closedBand[0], y1: L.lgateT.closedBand[1] })));
    return { y, floor: { x: L.floor.x, z: L.floor.z, r: L.floor.r, h: +(y + L.floorThk).toFixed(4) }, discs };
  }

  // 落点 (x,z) 的全部候选地面高度
  function floorHeights(x, z, lift = null, floors = man.floors) {
    const [lx, lz] = loc(x, z);
    const r = Math.hypot(lx, lz);
    const hs = [];
    for (const f of floors) {
      if (f.shape === "helix") {
        if (r < f.r0 - GRACE || r > f.r1 + GRACE) continue;
        const a = Math.atan2(lz, lx);
        const da = f.da * f.dir;                       // 每级方位增量（带符号）
        const per = TAU / Math.abs(da);                // 每圈级数
        let u0 = (a - f.a0) / da;
        u0 = ((((u0 / per) + 1e-9) % 1) + 1) % 1 * per;
        for (let n = 0; n <= Math.ceil((f.n - u0) / per); n++) {
          const u = u0 + n * per;
          if (u >= f.n) break;
          const k = Math.floor(u);
          if (k >= 0 && k < f.n) hs.push({ h: f.h ? f.h[k] : f.rise * (k + 1), src: `helix k=${k}` });
        }
      } else if (f.shape === "sector") {
        if (r < f.r0 - GRACE || r > f.r1 + GRACE) continue;
        const a = normA(Math.atan2(lz, lx));
        if (f.a1 - f.a0 >= TAU - 1e-9) hs.push({ h: f.h, src: "sector" });
        else {
          const a0 = normA(f.a0), a1 = normA(f.a1);
          const inA = a0 <= a1 ? a >= a0 && a <= a1 : a >= a0 || a <= a1;
          if (inA) hs.push({ h: f.h, src: "sector" });
        }
      } else if (f.shape === "rect") {
        if (Math.abs(x - f.x) <= f.hw + GRACE && Math.abs(z - f.z) <= f.hd + GRACE) hs.push({ h: f.h, src: `rect@${f.x},${f.z}` });
      } else if (f.shape === "circle") {
        if (Math.hypot(x - f.x, z - f.z) <= f.r + GRACE) hs.push({ h: f.h, src: "circle" });
      }
    }
    if (lift && Math.hypot(x - lift.floor.x, z - lift.floor.z) <= lift.floor.r + GRACE) hs.push({ h: lift.floor.h, src: "liftFloor" });
    return hs;
  }

  // 落点在脚底 feet 时的判定: {support, wall, discs, blocked, why}
  function probe(x, z, feet, lift = null, discs = man.circles, extra = null) {
    const hs = floorHeights(x, z, lift, extra?.floors);
    let support = 0;
    let wall = null;
    for (const { h, src } of hs) {
      if (h <= feet + STEP + 1e-9) { if (h > support) support = h; }
      else if (h <= feet + HEAD + 1e-9 && !wall) wall = { h, src };
    }
    const act = [];
    const all = lift ? [...discs, ...lift.discs] : discs;
    for (const c of all) {
      if (feet < c.y0 - 1e-9 || feet > c.y1 + 1e-9) continue;
      if (Math.hypot(x - c.x, z - c.z) <= c.r + PR + 1e-12) act.push(c);
    }
    const blocked = !!wall || act.length > 0;
    return { x, z, feet, support, wall, discs: act, blocked, why: wall ? `地面 h=${wall.h} (${wall.src}) 落在 (脚+${STEP}, 脚+${HEAD}]` : act.length ? `排斥盘 x${act.length} (r=${act[0].r})` : null };
  }

  // 沿折线逐点行走（贴地；每步允许 <=STEP 上下；下落 >FALL 记为坠落）
  const FALL = 0.5;
  function walk(points, { lift = null, startFeet = 0, discs = man.circles, extra = null } = {}) {
    const samples = [];
    let feet = startFeet;
    let stopped = false;
    let falls = 0;
    for (let i = 0; i < points.length; i++) {
      const [x, z] = points[i];
      const p = probe(x, z, feet, lift, discs, extra);
      if (p.blocked) { p.i = i; p.state = "blocked"; samples.push(p); stopped = true; break; }
      if (p.support > feet) { feet = p.support; p.state = "stepUp"; }
      else if (p.support < feet - STEP) { p.dropFrom = feet; if (feet - p.support > FALL) falls++; feet = p.support; p.state = "drop"; }
      else { p.state = feet === p.support ? "ok" : "stepDown"; feet = p.support; }
      p.i = i;
      p.feet = feet;
      samples.push(p);
    }
    return { samples, stopped, falls, feet };
  }

  return { man, PLACE, loc, app, pol, liftState, floorHeights, probe, walk };
}
