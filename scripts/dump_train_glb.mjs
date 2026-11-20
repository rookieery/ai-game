// 只读诊断: 解剖 roller_coaster_train.glb 节点树 / 每车局部包围盒 / 轮组父子关系
// 用法: node scripts/dump_train_glb.mjs [glb路径]
import { readFileSync } from "node:fs";
import * as THREE from "three";

const path = process.argv[2] ?? "model/roller_coaster/roller_coaster_train.glb";
const buf = readFileSync(path);
const jsonLen = buf.readUInt32LE(12);
const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString("utf8"));

const nodes = json.nodes ?? [];
const R = (v, n = 3) => (Array.isArray(v) ? v.map((x) => +(+x).toFixed(n)) : v);

function build(i, parent, depth) {
  const n = nodes[i];
  const o = new THREE.Object3D();
  o.name = n.name ?? `(node${i})`;
  if (n.translation) o.position.fromArray(n.translation);
  if (n.rotation) o.quaternion.fromArray(n.rotation);
  if (n.scale) o.scale.fromArray(n.scale);
  o.updateMatrix();
  o.matrixWorldNeedsUpdate = true;
  parent.add(o);
  if (n.mesh != null) {
    const m = json.meshes[n.mesh];
    // 局部 bbox: 取 POSITION accessor min/max (近似, 忽略非单位缩放)
    const bb = new THREE.Box3();
    for (const p of m.primitives) {
      const acc = json.accessors[p.attributes.POSITION];
      bb.expandByPoint(new THREE.Vector3(...acc.min));
      bb.expandByPoint(new THREE.Vector3(...acc.max));
    }
    o.userData.localBB = bb;
  }
  for (const c of n.children ?? []) build(c, o, depth + 1);
  return o;
}

const root = new THREE.Object3D();
root.name = "SCENE";
for (const s of json.scenes[json.scene ?? 0].nodes) build(s, root, 0);
root.updateMatrixWorld(true);

// 1) 节点树总览
console.log("=== 节点树 (T=平移, Q=四元数, deg=欧拉角) ===");
root.traverse((o) => {
  if (o === root) return;
  const e = new THREE.Euler().setFromQuaternion(o.quaternion);
  const deg = [e.x, e.y, e.z].map((x) => +((x * 180) / Math.PI).toFixed(1));
  const bb = o.userData.localBB;
  const t = o.position.toArray().map((v) => +v.toFixed(2));
  console.log(
    `${o.name.padEnd(24)} T=${JSON.stringify(t)}` +
      ` euler=${JSON.stringify(deg)}` +
      (bb ? ` meshBB=[${[bb.max.x - bb.min.x, bb.max.y - bb.min.y, bb.max.z - bb.min.z].map((v) => +v.toFixed(2))}]` : ""),
  );
});

// 2) 每辆 NL_Car_i: 子树所有 mesh 在【车节点局部系】的联合包围盒 -> 判定长轴
console.log("\n=== 每车局部包围盒 (车节点局部系, 期望 长轴=Y≈2.4+, 上=Z≈1.0+, 宽=X≈1.2) ===");
for (const o of root.children) {
  o.traverse((car) => {
    if (!/^NL_Car_\d$/.test(car.name)) return;
    const inv = car.matrixWorld.clone().invert();
    const bb = new THREE.Box3();
    let meshCount = 0;
    car.traverse((c) => {
      if (c.userData.localBB) {
        meshCount++;
        for (const corner of [
          [c.userData.localBB.min.x, c.userData.localBB.min.y, c.userData.localBB.min.z],
          [c.userData.localBB.max.x, c.userData.localBB.max.y, c.userData.localBB.max.z],
          [c.userData.localBB.min.x, c.userData.localBB.max.y, c.userData.localBB.min.z],
          [c.userData.localBB.max.x, c.userData.localBB.min.y, c.userData.localBB.max.z],
        ]) {
          bb.expandByPoint(new THREE.Vector3(...corner).applyMatrix4(c.matrixWorld).applyMatrix4(inv));
        }
      }
    });
    const sz = [bb.max.x - bb.min.x, bb.max.y - bb.min.y, bb.max.z - bb.min.z].map((v) => +v.toFixed(2));
    console.log(`${car.name} meshes=${meshCount} size(X,Y,Z)=${JSON.stringify(sz)} min=${JSON.stringify([bb.min.x, bb.min.y, bb.min.z].map((v) => +v.toFixed(2)))} max=${JSON.stringify([bb.max.x, bb.max.y, bb.max.z].map((v) => +v.toFixed(2)))}`);
  });
}

// 3) 轮组父子关系抽查
console.log("\n=== NL_Wheel_* 父节点统计 ===");
const wheelParents = {};
root.traverse((o) => {
  if (/^NL_Wheel_/.test(o.name)) {
    const p = o.parent?.name ?? "?";
    (wheelParents[p] ??= []).push(o.name);
  }
});
for (const [p, ws] of Object.entries(wheelParents)) console.log(`${p}: ${ws.length} 个, 如 ${ws.slice(0, 4).join(", ")}`);

// 4) NL_TrainRoot 自身 TRS
const tr = root.children.find((o) => o.name === "NL_TrainRoot");
if (tr) console.log(`\nNL_TrainRoot T=${JSON.stringify(tr.position.toArray().map((v) => +v.toFixed(3)))} Q=${tr.quaternion.toArray().map((v) => +v.toFixed(3))}`);
