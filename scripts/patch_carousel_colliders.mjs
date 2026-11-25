// 旋转木马 colliders.json 手工补丁 (2026-11-17 起; 2026-11-25 重写为幂等版并修正几何)
// 幂等: 本补丁加的圆带 src:"carousel", 重跑先清掉自己上次的, 再清 11-17 版留下的无标记旧圆。
// 删: 旧占位剪影碰撞 (平台 r4.5 h0.555 / 中柱 r0.26 / 座椅 r0.35 x6, 距心 <=5.5 且 r<=4.5)
// 加 (全部 src:"carousel", 现共 110 个):
//   平台 r8.0 h0.62 / 中柱 r0.62 (金箍外径 0.61)
//   三级入口台阶: 每级 9 个 r0.335 圆沿切向 0.35m 排开 —— 对齐可见踏步 (径向 0.67 x 切向 2.8 的盒)。
//     圆半径 = 踏步半深, 排得密 (重叠 0.32) 是为了斜着走上台阶时支撑连续不抖; 5 个 r0.30 在 ±8° 斜走会掉格
//     11-17 版用 3 个 r1.35 大圆, 脚高比可见踏步早约 1m 抬升 (入口主路踩空气)
//   围栏 r10.7: 每 4° 一个 r0.16 圆 —— 排斥半径 (r+0.38) 0.54, 圆心距 0.746, 相邻盘重叠 0.33。
//     11-17 版柱 r0.09 + 跨中 r0.30 相邻盘只重叠 3cm, 真键走线在偏离圆心 >=1° 的方位被挤穿
//     (实测 20 个方位 16 个穿透); 入口走廊 180°–228° 断开 (横杆缺口两端的两根立柱处保留圆),
//     实际可走开的方位约 183°–225°, 与横杆缺口对齐
//   招牌立柱 x2
// 骑乘位/铜杆为旋转件 —— 不入静态表, 由 src/rides/carousel.js 每帧动态驱动
// 用法: node scripts/patch_carousel_colliders.mjs   (重跑 park_env.py 之后必须跑; 见 scripts/verify_carousel_colliders.mjs)
import { readFileSync, writeFileSync } from "node:fs";

const path = "model/park_env/colliders.json";
const j = JSON.parse(readFileSync(path, "utf8"));

// --- POI 改名 (剪影 -> 真实设施) ---
for (const p of j.pois ?? []) {
  if (p.label === "carousel_silhouette") p.label = "carousel";
}

const CX = 45, CZ = -18;   // 木马中心 (app 坐标)
const E = 202;             // 入口方位 (Blender 方位角)
const deg = (d) => (d * Math.PI) / 180;
const at = (r, th) => ({ x: +(CX + r * Math.cos(deg(th))).toFixed(4), z: +(CZ - r * Math.sin(deg(th))).toFixed(4) });
const dist = (c) => Math.hypot(c.x - CX, c.z - CZ);

// --- 清旧圆 ---
let removed = 0;
j.circles = (j.circles ?? []).filter((c) => {
  if (c.src === "carousel") { removed++; return false; }
  const d = dist(c);
  if (d <= 5.5 && c.r <= 4.5) { removed++; return false; }   // 旧占位剪影
  // 11-17 版补丁圆 (无标记): 该范围内没有园区生成件
  const legacy = (d < 0.02 && (c.r === 8 || c.r === 0.5))                    // 平台 / 中柱
    || (c.r === 1.35 && d > 7.5 && d < 10.5)                                // 台阶大圆
    || (Math.abs(d - 10.7) < 0.03 && (c.r === 0.09 || c.r === 0.3))          // 围栏柱 / 跨中圆
    || (Math.abs(d - 12.4) < 0.03 && c.r === 0.1);                           // 招牌柱
  if (legacy && d <= 13) { removed++; return false; }
  return true;
});
console.log("removed", removed, "old circles");

// --- 加静态碰撞 ---
const add = [];
const C = (o) => ({ ...o, src: "carousel" });
// 平台 (顶面可站 0.62) + 中柱 (无限高)
add.push(C({ x: CX, z: CZ, r: 8.0, h: 0.62 }));
add.push(C({ x: CX, z: CZ, r: 0.62 }));
// 三级入口台阶 (blender r 8.33/9.0/9.67 @ azimuth 202° -> app (x, -y)); 切向单位向量
const TX = Math.sin(deg(E)), TZ = Math.cos(deg(E));
for (const [rr, h] of [[8.33, 0.465], [9.0, 0.31], [9.67, 0.155]]) {
  const c0 = at(rr, E);
  for (let t = -1.4; t <= 1.401; t += 0.35) {
    add.push(C({ x: +(c0.x + t * TX).toFixed(4), z: +(c0.z + t * TZ).toFixed(4), r: 0.335, h }));
  }
}
// 围栏: 每 4° 一个圆, 入口走廊 (180°, 228°) 内不放 —— 两端立柱处保留, 与横杆缺口对齐
// (立柱在 12° 网格上, 4° 网格覆盖全部立柱方位)
for (let th = 0; th < 360; th += 4) {
  if (th > 180 && th < 228) continue;
  add.push(C({ ...at(10.7, th), r: 0.16 }));
}
// 招牌立柱 x2 (r12.4 @ 202±12°)
for (const sgn of [-1, 1]) {
  add.push(C({ ...at(12.4, E + sgn * 12), r: 0.1 }));
}
j.circles.push(...add);
console.log("added", add.length, "circles");

writeFileSync(path, JSON.stringify(j, null, 1) + "\n");
console.log("written", path, "circles total", j.circles.length);
