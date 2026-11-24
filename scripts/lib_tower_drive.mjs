// 缠魂塔实机走线公共库: 页面内自动驾驶 (每帧按路线设视线 + 键盘事件驱动真实控制器) + 读数小工具
// 配合 scripts/verify_tower_game.mjs; 不改游戏源码。移动走的是 input → controller.updateWorld → tryMove 全链路,
// 与玩家真按键同一条路 (不用 teleport 代替走线 —— 栈桥封桥那次的教训)。
import { resolve } from "node:path";

export const ROOT = resolve(import.meta.dirname, "..");
const f = (v, n = 2) => +v.toFixed(n);

// 路线 (page 内 window.__routes):
//   line(pts, tol)  直线点列 [[x,z],...], 逐点走到 (tol 内或已越过) 再奔下一点; 走完返回 null
//   climb()         地面梯口外 → 螺旋梯 (按脚高反推所在级, 望向上方第 4 级) → 到达口 → 环廊
//   descend()       环廊到达口 → 螺旋梯下行 → 梯底 → 沿进梯带走出
export async function installDrive(page) {
  await page.evaluate(() => {
    const f = (v, n = 2) => +v.toFixed(n);
    const g = window.__game, pl = g.player;
    const man = window.__park.tower, HX = man.floors.find((o) => o.shape === "helix");
    const rad = (d) => (d * Math.PI) / 180;
    const pol = (az, r) => ({ x: HX.x + r * Math.cos(rad(az)), z: HX.z + r * Math.sin(rad(az)) });
    const azOf = (p) => ((((Math.atan2(p.z - HX.z, p.x - HX.x) * 180) / Math.PI) % 360) + 360) % 360;
    const stepPt = (k, r = 2.54) => pol(((HX.a0 + HX.da * HX.dir * k) * 180) / Math.PI, r);
    const kOf = (y) => {                         // 由脚高反推所在级 (踏面高单调递增, 每圈不重样)
      const H = HX.h;
      if (y < H[0] - 0.2) return -1;
      let lo = 0, hi = H.length - 1;
      while (lo < hi) { const m = (lo + hi + 1) >> 1; if (H[m] <= y + 0.09) lo = m; else hi = m - 1; }
      return lo;
    };
    const dist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
    const routes = (window.__routes = {
      line(pts, tol = 0.25) {
        let i = 0;
        return (p, prev) => {
          while (i < pts.length) {
            const dx = pts[i][0] - p.x, dz = pts[i][1] - p.z, d = Math.hypot(dx, dz);
            // 「已越过」只在路点就在近旁 (0.6m 内) 且本帧位移已朝它走过去时成立 ——
            // 低帧率一步跨过容差圈也算到; 贴墙滑行时位移被偏转、路点还在墙外, 不算 (否则撞墙会被当成走到)
            const passed = prev && d < 0.6 && (Math.abs(p.x - prev.x) + Math.abs(p.z - prev.z) > 1e-4) && dx * (p.x - prev.x) + dz * (p.z - prev.z) <= 0;
            if (d >= tol && !passed) break;
            i++;
          }
          return i < pts.length ? { x: pts[i][0], z: pts[i][1] } : null;
        };
      },
      climb() {
        return (p) => {
          const k = kOf(p.y);
          if (k >= 238) {                                      // 末两级: 沿第 240 级走到到达口方位再向外上环廊
            const gate = pol(141.5, 2.6);
            if (!(dist(p, gate) < 0.5 || azOf(p) < 142.5)) { const e = pol(144, 4.9); return dist(p, e) < 0.3 ? null : e; }
            return gate;
          }
          return stepPt(Math.min(HX.n - 1, k + 4));
        };
      },
      descend() {
        return (p) => {
          const r = Math.hypot(p.x - HX.x, p.z - HX.z);
          if (p.y > 39.9 && r > 3.7) return pol(141.5, 2.6);              // 环廊 → 经到达口走向末级
          if (p.y <= 0.2) {                                               // 梯底: 第 0/1 级方位在进梯带外侧, 先回到第 2 级再走出
            if (azOf(p) > 50.6) return stepPt(2);
            return r > 4.7 ? null : pol(43, 5.2);
          }
          return stepPt(Math.max(0, kOf(p.y) - 4));
        };
      },
    });

    const a = (window.__ap = { on: false, route: null, key: "KeyW" });
    const tick = () => {
      requestAnimationFrame(tick);
      if (!a.on) return;
      a.frames++;
      const p = pl.pos, prev = a._pp, t = a.route(p, prev), now = performance.now();
      a._pp = { x: p.x, z: p.z };
      if (!t) { a.on = false; a.end = { x: p.x, y: p.y, z: p.z }; return; }
      pl.setView(Math.atan2(-(t.x - p.x), -(t.z - p.z)), a.pitch ?? -0.04);
      if (pl.airborne && pl.airborne()) a.airFrames++;                    // 每帧看是否离地 (走梯途中应为 0)
      if (now - a._t > 100) {                                             // 每 100ms 采样: 卡住检测 + 每 ~400ms 记一个轨迹点
        a.maxDrop = Math.max(a.maxDrop, a._y - p.y);
        if (a.log && now - a._lt >= 400) { a.log.push([Math.round(now - a.t0), f(p.x), f(p.y), f(p.z)]); a._lt = now; }
        a._y = p.y; a._t = now;
        if (Math.hypot(p.x - a._mx, p.z - a._mz) > 0.05) { a._mx = p.x; a._mz = p.z; a._mt = now; }
        else if (now - a._mt > 3000) { a.stuck = true; a.on = false; a.end = { x: p.x, y: p.y, z: p.z }; }
      }
    };
    a.frames = 0;
    requestAnimationFrame(tick);

    // 驱动: 按下前进键直到路线走完 / 超时 / 卡住 3s。返回 { timedOut, stuck, airFrames(离地帧数), maxDrop, log, pos, fps }
    window.__drive = async ([name, arg, timeout, log]) => {
      const t0 = performance.now();
      Object.assign(a, { on: true, end: null, stuck: false, maxDrop: 0, airFrames: 0, frames: 0, log: log ? [] : null, t0, _t: 0, _lt: 0, _y: pl.pos.y,
        _pp: null, _mx: pl.pos.x, _mz: pl.pos.z, _mt: t0 });
      a.route = routes[name](arg);
      window.dispatchEvent(new KeyboardEvent("keydown", { code: a.key }));
      while (a.on && performance.now() - t0 < timeout) await new Promise((r) => setTimeout(r, 40));
      window.dispatchEvent(new KeyboardEvent("keyup", { code: a.key }));
      const timedOut = a.on;
      a.on = false;
      const ms = performance.now() - t0, p = pl.pos;
      return { timedOut, stuck: a.stuck, ms: Math.round(ms), fps: Math.round(a.frames / (ms / 1000)), maxDrop: f(a.maxDrop, 3), airFrames: a.airFrames,
        log: a.log, pos: { x: f(p.x), y: f(p.y), z: f(p.z) } };
    };
    // 微调: 朝目标点短促点按前进键直到进入 tol (闭包收敛, 不受帧率影响)
    window.__nudge = async ([x, z, tol, maxMs]) => {
      const t0 = performance.now();
      while (performance.now() - t0 < maxMs && Math.hypot(x - pl.pos.x, z - pl.pos.z) > tol) {
        pl.setView(Math.atan2(-(x - pl.pos.x), -(z - pl.pos.z)), 0);
        window.dispatchEvent(new KeyboardEvent("keydown", { code: "KeyW" }));
        await new Promise((r) => setTimeout(r, 25));
        window.dispatchEvent(new KeyboardEvent("keyup", { code: "KeyW" }));
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      }
      const p = pl.pos;
      return { x: f(p.x), y: f(p.y), z: f(p.z), d: f(Math.hypot(x - p.x, z - p.z)) };
    };
  });
}

export const drive = (page, route, arg, timeout = 40000, log = false) =>
  page.evaluate((args) => window.__drive(args), [route, arg, timeout, log]);
export const nudge = (page, x, z, tol = 0.03, maxMs = 5000) =>
  page.evaluate((args) => window.__nudge(args), [x, z, tol, maxMs]);
export const pose = (page, x, z, y = 0, yaw = 0, pitch = 0) =>
  page.evaluate(([x, z, y, yaw, pitch]) => { window.__game.player.teleport(x, z, y); window.__game.player.setView(yaw, pitch); }, [x, z, y, yaw, pitch]);
export const pos = (page) => page.evaluate(() => { const p = window.__game.player.pos; return { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) }; });
export const towerState = (page) => page.evaluate(() => {
  const s = window.__game.tower.state;
  return { phase: s.phase, at: s.at, y: +s.y.toFixed(2), doorB: +s.door.B.toFixed(2), doorT: +s.door.T.toFixed(2),
    lgB: +s.lgate.B.toFixed(2), lgT: +s.lgate.T.toFixed(2), laps: s.laps, aboard: s.aboard };
});
export const promptText = (page) => page.evaluate(() =>
  document.querySelector(".spirit-prompt").classList.contains("show") ? document.querySelector(".prompt-text").textContent : "");
export const promptKey = (page) => page.evaluate(() => document.querySelector(".spirit-prompt .keycap").textContent);
export const toastText = (page) => page.evaluate(() => document.querySelector(".toast").textContent);
