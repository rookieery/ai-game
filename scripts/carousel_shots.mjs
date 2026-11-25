// 显灵木马取证机位工具（只读：不改游戏源码 / 资产；2026-11-25 建模评审时沉淀）
// 用法（在仓库 cwd 下跑，需本机 ffmpeg 做像素统计；dev server 默认 8765，GAME_URL 可覆盖）:
//   node scripts/carousel_shots.mjs <spec.json>              # ONLY=<完整机位名,逗号分隔> 可只拍指定机位
//   node scripts/carousel_shots.mjs --stats <目录>           # 只重算目录内 PNG 的像素统计 -> stats.json
// spec.json:
// {
//   "out": "<输出目录>",                               // 必填
//   "width": 1920, "height": 953, "dpr": 1,             // dpr=2 复现高密度屏真机
//   "hideHud": true,
//   "theta": 0,                                        // 冻结机台转角(rad)。0 = 南瓜马车(i0)在入口位；"live" = 不冻结
//   "settings": { "decoLight": 100, "carouselCanopyLight": 100 },   // 可选，按设置面板键名覆盖
//   "dumpScene": true, "perf": true,                   // 可选：写 scene.json（木马全部网格/材质/灯光）/ perf.json
//   "shots": [ ... ]                                   // 见下
// }
// 机位种类（公共可选项: fov | lens(等效 36mm 全画幅焦距) | crop:[x,y,w,h] CSS px | pick:[[u,v],...] 归一化屏幕坐标射线拾取
//             | hide:["正则"] 按物体名隐藏(拍完恢复) | wait:ms | burst:{n, interval} 连拍 | hud:true 保留界面层）
//   free: { name, pos:[x,y,z], target:[x,y,z] }          app 坐标，y=高度。木马中心 (45,0,-18)，平台顶 0.62
//         或 bpos:[x,y,z] / bpolar:[r,方位角deg,z]        Blender 本地坐标(Z 向上, 入口方位 202°; 骑乘位 i 在 202°+36°·i)
//   fp:   { name, walk:[x,z], y?:脚高(默认 0; 站平台用 0.62), target:[x,y,z] }   第一人称站姿机位(眼高 1.65+脚高)
//   ride: { name, ride:<0..9>, target?:[x,y,z] | yaw?/pitch? }  传到该骑乘位内侧 1m、按 E 上乘、拍骑坐视角、按 E 下乘
//         骑乘位: 0 南瓜马车 / 5 鎏金座车 / 1,4,8 幽灵马 / 2,6,9 象牙马 / 3,7 南瓜马
// 产物: <out>/<name>.png + <out>/stats.json（每张: 纯白占比 / 近白(亮度>=230)占比 / 中央60%近黑占比 / 平均亮度 / 拾取结果）
// 注意: ACES 色调映射下「纯白」几乎恒为 0，判断过曝看「近白」；新 profile 用的是默认设置，
//       用户的实机设置可能很不一样（辉光 0 等），对比前先同机位对位。
import { chromium } from "playwright";
import { mkdirSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

// 只重算像素统计（不重拍）: node scripts/carousel_shots.mjs --stats <目录>
if (process.argv[2] === "--stats") {
  const dir = process.argv[3];
  const prev = (() => { try { return JSON.parse(readFileSync(path.join(dir, "stats.json"), "utf8")); } catch { return []; } })();
  const byFile = new Map(prev.map((p) => [p.file, p]));
  const rows = readdirSync(dir).filter((f) => f.endsWith(".png")).sort().map((f) => ({ file: f, ...pngStatsFile(path.join(dir, f)), ...(byFile.get(f)?.picks ? { picks: byFile.get(f).picks } : {}) }));
  writeFileSync(path.join(dir, "stats.json"), JSON.stringify(rows, null, 1));
  for (const r of rows) console.log(r.file.padEnd(30), r.error ? r.error : `纯白 ${r.whitePct}%  近白(>=230) ${r.brightPct}%  中央近黑 ${r.centerBlackPct}%  均亮 ${r.meanLuma}`);
  process.exit(0);
}
const specPath = process.argv[2];
if (!specPath) { console.error("usage: node scripts/carousel_shots.mjs <spec.json> | --stats <dir>"); process.exit(2); }
const spec = JSON.parse(readFileSync(specPath, "utf8"));
const URL_ = spec.url ?? process.env.GAME_URL ?? "http://127.0.0.1:8765";
const OUT = spec.out;
if (!OUT) { console.error("spec.out 必填"); process.exit(2); }
mkdirSync(OUT, { recursive: true });
const W = spec.width ?? 1920, H = spec.height ?? 953, DPR = spec.dpr ?? 1;
const only = process.env.ONLY ? new Set(process.env.ONLY.split(",")) : null;
const CX = 45, CZ = -18; // 木马中心（app 坐标）

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: DPR });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(URL_, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => {
  const b = document.getElementById("enter-btn");
  return b && !b.disabled;
}, { timeout: 120000 });
await page.click("#enter-btn");
const entered = () => window.__game && window.__game.state === "walk";
await page.waitForFunction(entered, { timeout: 8000 }).catch(async () => {
  console.log("enter: retry click");
  await page.evaluate(() => document.getElementById("enter-btn").click());
  await page.waitForFunction(entered, { timeout: 10000 });
});
await page.waitForTimeout(1500);

// ---------- 页面内工具 window.__cr ----------
await page.evaluate(async () => {
  if (window.__cr) return;
  const g = window.__game;
  let T = null;
  try { T = await import("/node_modules/three/build/three.module.js"); } catch (e) { console.warn("__cr: three import failed", String(e)); }
  const cr = (window.__cr = {
    THREE: T, hidden: [], hudSaved: [],
    freeze(theta) {
      const c = g.carousel;
      if (!c) return "no carousel";
      if (!c.__upd) c.__upd = c.update;
      if (theta === "live") { c.update = c.__upd; return "live"; }
      c.state.theta = theta;
      c.__upd.call(c, 0);
      g.scene.updateMatrixWorld(true);
      c.update = () => {};
      return "frozen@" + theta;
    },
    hideHud(on) {
      if (on) {
        this.hudSaved = [];
        const cv = document.getElementById("game-canvas");
        for (const el of document.body.querySelectorAll("*")) {
          if (el === cv || el.contains(cv)) continue;   // 画布及其祖先必须保留(visibility 会继承)
          if (/^(SCRIPT|STYLE|LINK|META|TITLE)$/.test(el.tagName)) continue;
          this.hudSaved.push([el, el.style.visibility]);
          el.style.visibility = "hidden";
        }
      } else { for (const [el, v] of this.hudSaved) el.style.visibility = v; this.hudSaved = []; }
    },
    setCam(pos, target, fov) {
      if (!g.__pu) g.__pu = g.player.update;
      g.player.update = () => {};
      if (fov) { g.camera.fov = fov; g.camera.updateProjectionMatrix(); }
      g.camera.position.set(pos[0], pos[1], pos[2]);
      g.camera.lookAt(target[0], target[1], target[2]);
      return g.camera.position.toArray().map((n) => +n.toFixed(2));
    },
    fp(x, z, y, target, fov) {
      if (g.__pu) { g.player.update = g.__pu; delete g.__pu; }
      g.player.teleport(x, z, y);
      const eye = 1.65 + g.player.pos.y;
      const dx = target[0] - x, dz = target[2] - z, d = Math.hypot(dx, dz);
      g.player.setView(Math.atan2(-dx, -dz), Math.atan2(target[1] - eye, d));
      if (fov) { g.camera.fov = fov; g.camera.updateProjectionMatrix(); }
      return { eye: +eye.toFixed(2) };
    },
    aim(target, yaw, pitch, fov) {
      if (fov) { g.camera.fov = fov; g.camera.updateProjectionMatrix(); }
      if (!target && yaw === undefined && pitch === undefined) return { kept: true };
      const c = g.camera.position;
      if (target) {
        const dx = target[0] - c.x, dz = target[2] - c.z, d = Math.hypot(dx, dz);
        g.player.setView(Math.atan2(-dx, -dz), Math.atan2(target[1] - c.y, d));
      } else g.player.setView(yaw ?? 0, pitch ?? 0);
      return { cam: c.toArray().map((n) => +n.toFixed(2)) };
    },
    rideSpot(i) {
      const r = g.carousel.rideRoots[i];
      r.updateWorldMatrix(true, false);
      const e = r.matrixWorld.elements;
      const px = e[12], pz = e[14];
      const dx = CXW - px, dz = CZW - pz, d = Math.hypot(dx, dz);
      return { x: px, z: pz, sx: px + (dx / d) * 1.0, sz: pz + (dz / d) * 1.0 };
    },
    hide(rx) {
      this.unhide();
      const names = [];
      for (const s of rx) {
        const re = new RegExp(s);
        g.scene.traverse((o) => {
          if (re.test(o.name) && o.visible) { this.hidden.push([o, true]); o.visible = false; names.push(o.name); }
        });
      }
      return names;
    },
    unhide() { for (const [o] of this.hidden) o.visible = true; this.hidden = []; },
    pick(list) {
      if (!T) return list.map(() => ({ error: "no three" }));
      const rc = new T.Raycaster();
      const meshes = [];
      const objs = [];
      g.scene.traverse((o) => {
        if (!(o.isMesh || o.isLine || o.isLineSegments) || !o.visible) return;
        let p = o.parent, vis = true;
        while (p) { if (!p.visible) { vis = false; break; } p = p.parent; }
        if (vis) objs.push(o);
      });
      rc.params.Line.threshold = 0.03;
      return list.map(([u, v]) => {
        rc.setFromCamera(new T.Vector2(u * 2 - 1, -(v * 2 - 1)), g.camera);
        let hits = [];
        try { hits = rc.intersectObjects(objs, false); } catch (e) { return { u, v, error: String(e).slice(0, 80) }; }
        return hits.length
          ? { u, v, name: hits[0].object.name, type: hits[0].object.type, dist: +hits[0].distance.toFixed(2),
              point: hits[0].point.toArray().map((n) => +n.toFixed(2)), hits: hits.length }
          : { u, v, name: null };
      });
    },
    dump() {
      if (!T) return { error: "three import failed" };
      const root = g.carousel.spinRoot;
      let r = root; while (r.parent && r.parent !== g.scene) r = r.parent;
      const out = { root: r.name || "(gltf scene)", rootPos: r.position.toArray(),
                    spin: {}, rides: [], meshes: [], lights: [] };
      root.updateWorldMatrix(true, true);
      const q = root.getWorldQuaternion(new T.Quaternion());
      out.spin = { name: root.name, pos: root.getWorldPosition(new T.Vector3()).toArray().map((n) => +n.toFixed(3)),
                   quat: q.toArray().map((n) => +n.toFixed(4)), theta: g.carousel.state.theta };
      g.carousel.rideRoots.forEach((o, i) => {
        if (!o) return;
        const p = o.getWorldPosition(new T.Vector3());
        const e = o.matrixWorld.elements;
        out.rides.push({ i, name: o.name, world: p.toArray().map((n) => +n.toFixed(3)),
          localY: +o.position.y.toFixed(3), xAxis: [e[0], e[1], e[2]].map((n) => +n.toFixed(3)) });
      });
      const hex = (c) => (c ? "#" + c.getHexString() : null);
      r.traverse((o) => {
        if (o.isMesh) {
          if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
          const b = o.geometry.boundingBox, e = o.matrixWorld.elements;
          const mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
          for (let i = 0; i < 8; i++) {
            const x = i & 1 ? b.max.x : b.min.x, y = i & 2 ? b.max.y : b.min.y, z = i & 4 ? b.max.z : b.min.z;
            const wx = e[0] * x + e[4] * y + e[8] * z + e[12];
            const wy = e[1] * x + e[5] * y + e[9] * z + e[13];
            const wz = e[2] * x + e[6] * y + e[10] * z + e[14];
            mn[0] = Math.min(mn[0], wx); mn[1] = Math.min(mn[1], wy); mn[2] = Math.min(mn[2], wz);
            mx[0] = Math.max(mx[0], wx); mx[1] = Math.max(mx[1], wy); mx[2] = Math.max(mx[2], wz);
          }
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          const idx = o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count;
          out.meshes.push({
            name: o.name, visible: o.visible,
            verts: o.geometry.attributes.position.count, tris: idx / 3,
            worldMin: mn.map((n) => +n.toFixed(3)), worldMax: mx.map((n) => +n.toFixed(3)),
            mats: mats.map((m) => ({ name: m.name, type: m.type, color: hex(m.color), emissive: hex(m.emissive),
              emissiveIntensity: m.emissiveIntensity, transparent: m.transparent, opacity: m.opacity,
              alphaTest: m.alphaTest, depthWrite: m.depthWrite, metalness: m.metalness, roughness: m.roughness,
              side: m.side, flatShading: !!m.flatShading, map: !!m.map, vertexColors: !!m.vertexColors })),
          });
        }
      });
      g.scene.traverse((o) => {
        if (o.isLight) {
          const p = o.getWorldPosition(new T.Vector3());
          const d = Math.hypot(p.x - CXW, p.z - CZW);
          out.lights.push({ type: o.type, name: o.name, color: hex(o.color), intensity: o.intensity,
            distance: o.distance ?? null, decay: o.decay ?? null,
            pos: p.toArray().map((n) => +n.toFixed(2)), dToCarousel: +d.toFixed(1) });
        }
      });
      const info = g.renderer.info;
      out.renderer = { toneMapping: g.renderer.toneMapping, exposure: g.renderer.toneMappingExposure,
        calls: info.render.calls, triangles: info.render.triangles, pixelRatio: g.renderer.getPixelRatio(),
        fov: g.camera.fov, aspect: +g.camera.aspect.toFixed(3) };
      out.settings = JSON.parse(JSON.stringify(window.__settings.store.values));
      return out;
    },
  });
  const CXW = 45, CZW = -18;
});

if (spec.settings) {
  await page.evaluate((s) => { for (const [k, v] of Object.entries(s)) window.__settings.store.set(k, v); }, spec.settings);
  await page.waitForTimeout(400);
}
const freezeMsg = await page.evaluate((t) => (t === undefined ? "untouched" : window.__cr.freeze(t)), spec.theta);
if (spec.hideHud !== false) await page.evaluate(() => window.__cr.hideHud(true));
console.log("freeze:", freezeMsg, "| viewport", W, "x", H, "@", DPR);

if (spec.dumpScene) {
  const dump = await page.evaluate(() => window.__cr.dump());
  writeFileSync(path.join(OUT, "scene.json"), JSON.stringify(dump, null, 1));
  console.log(`scene.json: ${dump.meshes.length} meshes, ${dump.lights.length} lights`);
}

if (spec.perf) {
  const perf = await page.evaluate(async () => {
    const g = window.__game, info = g.renderer.info;
    info.autoReset = false;
    const sample = async (n) => {
      info.reset();
      const t0 = performance.now();
      await new Promise((res) => { let f = 0; const tick = () => { if (++f >= n) res(); else requestAnimationFrame(tick); }; requestAnimationFrame(tick); });
      const ms = (performance.now() - t0) / n;
      return { frames: n, callsPerFrame: +(info.render.calls / n).toFixed(1), trisPerFrame: Math.round(info.render.triangles / n), msPerFrame: +ms.toFixed(2) };
    };
    const full = await sample(40);
    const hidden = window.__cr.hide(["^CR_"]);
    const noCarousel = await sample(40);
    window.__cr.unhide();
    info.autoReset = true;
    return { full, carouselHidden: { ...noCarousel, hiddenMeshes: hidden.length },
             carouselCost: { calls: +(full.callsPerFrame - noCarousel.callsPerFrame).toFixed(1), tris: full.trisPerFrame - noCarousel.trisPerFrame } };
  });
  writeFileSync(path.join(OUT, "perf.json"), JSON.stringify(perf, null, 1));
  console.log("perf:", JSON.stringify(perf));
}

// ---------- 机位换算 ----------
const toApp = (s) => {
  if (s.pos) return s.pos;
  if (s.bpos) return [CX + s.bpos[0], s.bpos[2], CZ - s.bpos[1]];
  if (s.bpolar) { const a = (s.bpolar[1] * Math.PI) / 180; return [CX + s.bpolar[0] * Math.cos(a), s.bpolar[2], CZ - s.bpolar[0] * Math.sin(a)]; }
  throw new Error(`shot ${s.name}: 缺 pos / bpos / bpolar`);
};
const toFov = (s) => {
  if (s.fov) return s.fov;
  if (s.lens) return (2 * Math.atan(Math.tan(Math.atan(18 / s.lens)) / (W / H)) * 180) / Math.PI;
  return 60;
};

// ---------- 像素统计 ----------
const pngStats = pngStatsFile;
function pngStatsFile(file) {
  const buf = readFileSync(file);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const ff = spawnSync("ffmpeg", ["-v", "error", "-i", file, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], { maxBuffer: 256 * 1024 * 1024 });
  if (ff.status !== 0) return { error: String(ff.stderr).slice(0, 120) };
  const b = ff.stdout, n = w * h;
  let white = 0, cBlack = 0, cN = 0, sum = 0, bright = 0;
  const x0 = Math.floor(w * 0.2), x1 = Math.ceil(w * 0.8), y0 = Math.floor(h * 0.2), y1 = Math.ceil(h * 0.8);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const o = (y * w + x) * 3, r = b[o], g = b[o + 1], bl = b[o + 2];
    const l = 0.2126 * r + 0.7152 * g + 0.0722 * bl;
    sum += l;
    if (r >= 250 && g >= 250 && bl >= 250) white++;
    if (l >= 230) bright++;
    if (x >= x0 && x < x1 && y >= y0 && y < y1) { cN++; if (l < 12) cBlack++; }
  }
  return { w, h, whitePct: +(100 * white / n).toFixed(3), brightPct: +(100 * bright / n).toFixed(2), centerBlackPct: +(100 * cBlack / cN).toFixed(2), meanLuma: +(sum / n).toFixed(1) };
}

const stats = [];
const capture = async (s, suffix, picks) => {
  const file = path.join(OUT, `${s.name}${suffix}.png`);
  const opt = { path: file };
  if (s.crop) opt.clip = { x: s.crop[0], y: s.crop[1], width: s.crop[2], height: s.crop[3] };
  await page.screenshot(opt);
  const st = pngStats(file);
  stats.push({ file: path.basename(file), ...st, ...(picks ? { picks } : {}) });
  console.log("shot", path.basename(file), JSON.stringify(st));
};
const doPick = (s) => (s.pick ? page.evaluate((l) => window.__cr.pick(l), s.pick) : null);

for (const s of spec.shots ?? []) {
  if (only && !only.has(s.name)) continue;
  try {
    if (s.hud) await page.evaluate(() => window.__cr.hideHud(false));
    if (s.ride !== undefined) {
      // 骑坐视角: 传到骑乘位内侧 1m → E 上乘 → 瞄准 → 拍 → E 下乘
      const spot = await page.evaluate((i) => window.__cr.rideSpot(i), s.ride);
      await page.evaluate(([sp, y]) => window.__cr.fp(sp.sx, sp.sz, y, [sp.x, 2.0, sp.z]), [spot, s.y ?? 0.62]);
      await page.waitForTimeout(500);
      await page.keyboard.press("KeyE");
      await page.waitForTimeout(1400);
      const st = await page.evaluate(() => ({ state: window.__game.state, mounted: window.__game.carousel.mounted }));
      if (s.hide) await page.evaluate((rx) => window.__cr.hide(rx), s.hide);
      const aim = await page.evaluate((s) => window.__cr.aim(s.target ?? null, s.yaw, s.pitch, s.fov), { ...s, fov: toFov(s) });
      await page.waitForTimeout(s.wait ?? 450);
      const picks = await doPick(s);
      await capture(s, "", picks);
      stats[stats.length - 1].rideState = st;
      stats[stats.length - 1].aim = aim;
      await page.evaluate(() => window.__cr.unhide());
      await page.keyboard.press("KeyE");
      await page.waitForTimeout(1300);
    } else if (s.walk) {
      await page.evaluate(([s, y, fov]) => window.__cr.fp(s.walk[0], s.walk[1], y, s.target, fov), [s, s.y ?? 0, toFov(s)]);
      await page.waitForTimeout(s.wait ?? 600);
      if (s.hide) await page.evaluate((rx) => window.__cr.hide(rx), s.hide);
      await page.waitForTimeout(120);
      const picks = await doPick(s);
      await capture(s, "", picks);
      await page.evaluate(() => window.__cr.unhide());
    } else {
      await page.evaluate(([p, t, fov]) => window.__cr.setCam(p, t, fov), [toApp(s), s.target, toFov(s)]);
      await page.waitForTimeout(s.wait ?? 450);
      if (s.hide) await page.evaluate((rx) => window.__cr.hide(rx), s.hide);
      await page.waitForTimeout(120);
      const picks = await doPick(s);
      if (s.burst) {
        for (let i = 0; i < s.burst.n; i++) { await capture(s, `_${i}`, i === 0 ? picks : null); await page.waitForTimeout(s.burst.interval ?? 400); }
      } else await capture(s, "", picks);
      await page.evaluate(() => window.__cr.unhide());
    }
    if (s.hud) await page.evaluate(() => window.__cr.hideHud(true));
  } catch (e) {
    console.log("SHOT_FAIL", s.name, String(e).slice(0, 200));
    stats.push({ file: s.name + ".png", error: String(e).slice(0, 200) });
  }
}
const prev = (() => { try { return JSON.parse(readFileSync(path.join(OUT, "stats.json"), "utf8")); } catch { return []; } })();
const names = new Set(stats.map((s) => s.file));
writeFileSync(path.join(OUT, "stats.json"), JSON.stringify([...prev.filter((p) => !names.has(p.file)), ...stats], null, 1));
console.log(errors.length ? "CONSOLE_ERRORS:\n" + [...new Set(errors)].join("\n") : "no console errors");
await browser.close();
