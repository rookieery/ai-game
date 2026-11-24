// 眺望塔取证公共库：启动无头 Chrome、入园、自由机位截图、合并网格的顶点扫描
// （配合 scripts/verify_tower_shots.mjs；只在取证脚本里使用，不改游戏源码）
// GAME_URL 环境变量指定 dev server（默认 8767；8765 通常是正在玩的实例）。
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

export const BASE_URL = process.env.GAME_URL ?? "http://127.0.0.1:8767";

// 打开游戏并入园（等到 walk 态；显灵板淡出偶发首击未触发时补一次 DOM click）
export async function openGame(outDir, { width = 1920, height = 1080 } = {}) {
  mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: { width, height } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => {
    const b = document.getElementById("enter-btn");
    return b && !b.disabled;
  }, { timeout: 120000 });
  await page.click("#enter-btn");
  const entered = () => {
    const l = document.getElementById("loading-screen");
    return (window.__game && window.__game.state === "walk") ||
      (l && (l.classList.contains("gone") || getComputedStyle(l).visibility === "hidden"));
  };
  await page.waitForFunction(entered, { timeout: 6000 }).catch(async () => {
    console.log("enter: retry click");
    await page.evaluate(() => document.getElementById("enter-btn").click());
    await page.waitForFunction(entered, { timeout: 8000 });
  });
  await page.waitForTimeout(1600);
  return { browser, page, errors };
}

// 页面内工具 window.__tl（合并后的网格无法按对象取包围盒，要逐顶点看）：
//   worldAABB(root)                —— 对象的世界包围盒（逐网格几何包围盒 8 角 × matrixWorld）
//   vertexScan(root, cx, cz, R)    —— 圆心 (cx,cz) 半径 R 内的顶点按 1.5m 网格聚簇，返回各簇包络
export async function installTools(page) {
  await page.evaluate(() => {
    if (window.__tl) return;
    const worldAABB = (root) => {
      root.updateWorldMatrix(true, true);
      const min = [1e9, 1e9, 1e9];
      const max = [-1e9, -1e9, -1e9];
      root.traverse((o) => {
        if (!o.isMesh || !o.geometry?.attributes?.position) return;
        if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
        const b = o.geometry.boundingBox;
        const e = o.matrixWorld.elements;
        for (let i = 0; i < 8; i++) {
          const x = i & 1 ? b.max.x : b.min.x;
          const y = i & 2 ? b.max.y : b.min.y;
          const z = i & 4 ? b.max.z : b.min.z;
          const wx = e[0] * x + e[4] * y + e[8] * z + e[12];
          const wy = e[1] * x + e[5] * y + e[9] * z + e[13];
          const wz = e[2] * x + e[6] * y + e[10] * z + e[14];
          if (wx < min[0]) min[0] = wx;
          if (wy < min[1]) min[1] = wy;
          if (wz < min[2]) min[2] = wz;
          if (wx > max[0]) max[0] = wx;
          if (wy > max[1]) max[1] = wy;
          if (wz > max[2]) max[2] = wz;
        }
      });
      const r = (v) => +v.toFixed(2);
      return { min: min.map(r), max: max.map(r) };
    };
    const vertexScan = (root, cx, cz, R, cell = 1.5) => {
      root.updateWorldMatrix(true, true);
      const res = [];
      root.traverse((o) => {
        if (!o.isMesh || !o.geometry?.attributes?.position) return;
        const pa = o.geometry.attributes.position;
        const e = o.matrixWorld.elements;
        const cells = new Map();
        for (let i = 0; i < pa.count; i++) {
          const x = pa.getX(i), y = pa.getY(i), z = pa.getZ(i);
          const wx = e[0] * x + e[4] * y + e[8] * z + e[12];
          const wz = e[2] * x + e[6] * y + e[10] * z + e[14];
          const wy = e[1] * x + e[5] * y + e[9] * z + e[13];
          if (Math.hypot(wx - cx, wz - cz) > R) continue;
          const k = `${Math.floor(wx / cell)},${Math.floor(wz / cell)}`;
          let c = cells.get(k);
          if (!c) {
            c = { n: 0, x0: 1e9, x1: -1e9, z0: 1e9, z1: -1e9, y0: 1e9, y1: -1e9 };
            cells.set(k, c);
          }
          c.n++;
          if (wx < c.x0) c.x0 = wx;
          if (wx > c.x1) c.x1 = wx;
          if (wz < c.z0) c.z0 = wz;
          if (wz > c.z1) c.z1 = wz;
          if (wy < c.y0) c.y0 = wy;
          if (wy > c.y1) c.y1 = wy;
        }
        if (!cells.size) return;
        // 相邻格并查集聚簇
        const keys = [...cells.keys()];
        const idx = new Map(keys.map((k, i) => [k, i]));
        const parent = keys.map((_, i) => i);
        const find = (a) => { while (parent[a] !== a) { parent[a] = parent[parent[a]]; a = parent[a]; } return a; };
        keys.forEach((k, i) => {
          const [gx, gz] = k.split(",").map(Number);
          for (const [dx, dz] of [[1, 0], [0, 1], [1, 1], [1, -1]]) {
            const j = idx.get(`${gx + dx},${gz + dz}`);
            if (j !== undefined) { const a = find(i), b = find(j); if (a !== b) parent[a] = b; }
          }
        });
        const cl = new Map();
        keys.forEach((k, i) => {
          const r = find(i);
          const c = cells.get(k);
          let a = cl.get(r);
          if (!a) {
            a = { n: 0, x0: 1e9, x1: -1e9, z0: 1e9, z1: -1e9, y0: 1e9, y1: -1e9 };
            cl.set(r, a);
          }
          a.n += c.n;
          a.x0 = Math.min(a.x0, c.x0); a.x1 = Math.max(a.x1, c.x1);
          a.z0 = Math.min(a.z0, c.z0); a.z1 = Math.max(a.z1, c.z1);
          a.y0 = Math.min(a.y0, c.y0); a.y1 = Math.max(a.y1, c.y1);
        });
        for (const a of cl.values()) {
          res.push({ name: o.name, verts: a.n, min: [+a.x0.toFixed(2), +a.y0.toFixed(2), +a.z0.toFixed(2)],
            max: [+a.x1.toFixed(2), +a.y1.toFixed(2), +a.z1.toFixed(2)] });
        }
      });
      res.sort((p, q) => q.verts - p.verts);
      return res;
    };
    window.__tl = { worldAABB, vertexScan };
  });
}

// 接管相机：冻结玩家控制器对相机的写入，之后由 freeShot 直接摆机位
export async function takeCamera(page) {
  await page.evaluate(() => {
    const g = window.__game;
    if (!g.__pu) g.__pu = g.player.update;
    g.player.update = () => {};
  });
}

export async function giveCameraBack(page) {
  await page.evaluate(() => {
    const g = window.__game;
    if (g.__pu) { g.player.update = g.__pu; delete g.__pu; }
    g.player.teleport(0, 60);
    g.player.setView(0, -0.04);
  });
}

// 自由机位截图: 相机 (px,py,pz) 看向 (tx,ty,tz), app 坐标 (y=高度)
export async function freeShot(page, outDir, name, p, t, { fov = 60, wait = 350 } = {}) {
  await page.evaluate(([p, t, fov]) => {
    const g = window.__game;
    if (!g.__pu) g.__pu = g.player.update;
    g.player.update = () => {};
    const c = g.camera;
    c.fov = fov;
    c.updateProjectionMatrix();
    c.position.set(p[0], p[1], p[2]);
    c.lookAt(t[0], t[1], t[2]);
  }, [p, t, fov]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${outDir}/${name}.png` });
  console.log("shot", name);
}

// 第一人称行走机位截图: teleport(x,z) + 视线朝目标点 (眼高由控制器接管)
export async function walkShot(page, outDir, name, x, z, target, { wait = 500, fov = 60 } = {}) {
  await page.evaluate(([x, z, target, fov]) => {
    const g = window.__game;
    if (g.__pu) { g.player.update = g.__pu; delete g.__pu; }
    g.player.teleport(x, z);
    const eye = 1.65 + g.player.pos.y;
    const yaw = Math.atan2(-(target[0] - x), -(target[2] - z));
    const d = Math.hypot(target[0] - x, target[2] - z);
    const pitch = Math.atan2(target[1] - eye, d);
    g.player.setView(yaw, pitch);
    g.camera.fov = fov;
    g.camera.updateProjectionMatrix();
  }, [x, z, target, fov]);
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${outDir}/${name}.png` });
  console.log("shot", name);
}
