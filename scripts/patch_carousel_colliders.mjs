// 旋转木马 colliders.json 手工补丁 (2026-11-17, 与 park_env.py 手工同步, 勿重跑 Blender)
// 删: 旧占位剪影碰撞 (平台 r4.5 h0.555 / 中柱 r0.26 / 座椅 r0.35 x6)
// 加: 新平台 r8.0 h0.62 / 中柱 r0.5 / 三级台阶 h0.465·0.31·0.155 /
//     围栏立柱 x28 + 横杆中点 x28 (入口走廊断开) / 招牌立柱 x2
// 骑乘位/铜杆为旋转件 —— 不入静态表, 由 src/rides/carousel.js 每帧动态驱动
// 用法: node scripts/patch_carousel_colliders.mjs
import { readFileSync, writeFileSync } from "node:fs";

const path = "model/park_env/colliders.json";
const j = JSON.parse(readFileSync(path, "utf8"));

// --- POI 改名 (剪影 -> 真实设施) ---
for (const p of j.pois ?? []) {
  if (p.label === "carousel_silhouette") p.label = "carousel";
}

// --- 删旧占位碰撞: 距 (45,-18) <=5.5 且 r<=4.5 ---
const CX = 45, CZ = -18;
const removed = [];
j.circles = (j.circles ?? []).filter((c) => {
  const d = Math.hypot(c.x - CX, c.z - CZ);
  if (d <= 5.5 && c.r <= 4.5) {
    removed.push(c);
    return false;
  }
  return true;
});
console.log("removed", removed.length, "old circles:", JSON.stringify(removed));

// --- 加新静态碰撞 ---
const deg = (d) => (d * Math.PI) / 180;
const add = [];
// 平台 (顶面可站 0.62) + 中柱 (无限高)
add.push({ x: 45, z: -18, r: 8.0, h: 0.62 });
add.push({ x: 45, z: -18, r: 0.5 });
// 三级入口台阶 (blender r 8.33/9.0/9.67 @ azimuth 202° -> app (x, -y))
for (const [rr, h] of [[8.33, 0.465], [9.0, 0.31], [9.67, 0.155]]) {
  add.push({ x: 45 + rr * Math.cos(deg(202)), z: -18 - rr * Math.sin(deg(202)), r: 1.35, h });
}
// 围栏: 立柱 (k*12°, 入口 ±15° 断开) + 横杆中点; r10.7
for (let k = 0; k < 30; k++) {
  const th = k * 12;
  const d = Math.abs(((th - 202 + 540) % 360) - 180); // 与入口方位的角距
  if (d < 15) continue; // 入口走廊 ±15° 断开
  add.push({ x: 45 + 10.7 * Math.cos(deg(th)), z: -18 - 10.7 * Math.sin(deg(th)), r: 0.09 });
  add.push({ x: 45 + 10.7 * Math.cos(deg(th + 6)), z: -18 - 10.7 * Math.sin(deg(th + 6)), r: 0.3 });
}
// 招牌立柱 x2 (r12.4 @ 202±12°)
for (const sgn of [-1, 1]) {
  const th = 202 + sgn * 12;
  add.push({ x: 45 + 12.4 * Math.cos(deg(th)), z: -18 - 12.4 * Math.sin(deg(th)), r: 0.1 });
}
j.circles.push(...add);
console.log("added", add.length, "circles");

writeFileSync(path, JSON.stringify(j, null, 1) + "\n");
console.log("written", path, "circles total", j.circles.length);
