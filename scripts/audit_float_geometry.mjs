// 悬空几何审计：解析 GLB,输出每个 mesh 节点的世界包围盒 + 顶点 Y 直方图
// 用法: node scripts/audit_float_geometry.mjs [modelPath ...]
// 判定: 场地地面 ≈ y 0 (park 地坪顶 -0.05, 广场盘顶 +0.03)。
//       mesh 最低点明显高于 0 的静态件 = 悬空候选。
import { readFileSync } from "node:fs";
import * as path from "node:path";

function parseGLB(file) {
  const buf = readFileSync(file);
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (dv.getUint32(0, true) !== 0x46546c67) throw new Error("not GLB");
  let off = 12;
  let json = null;
  let bin = null;
  while (off < buf.byteLength) {
    const len = dv.getUint32(off, true);
    const type = dv.getUint32(off + 4, true);
    const start = off + 8;
    if (type === 0x4e4f534a) json = JSON.parse(buf.slice(start, start + len).toString("utf8"));
    else if (type === 0x004e4942) bin = buf.slice(start, start + len);
    off = start + len;
  }
  return { json, bin };
}

function readPositions(gltf, primitive) {
  const acc = gltf.json.accessors[primitive.attributes.POSITION];
  const bv = gltf.json.bufferViews[acc.bufferView];
  const base = gltf.bin.byteOffset + (bv.byteOffset ?? 0) + (acc.byteOffset ?? 0);
  const stride = (bv.byteStride ?? 12) / 4; // f32 步长(元素数)
  const count = acc.count;
  const f32 = new Float32Array(gltf.bin.buffer); // 整个文件的 ArrayBuffer
  const arr = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const s = base / 4 + i * stride;
    arr[i * 3] = f32[s];
    arr[i * 3 + 1] = f32[s + 1];
    arr[i * 3 + 2] = f32[s + 2];
  }
  return { arr, min: acc.min, max: acc.max };
}

function nodeMatrix(node) {
  if (node.matrix) return node.matrix;
  const t = node.translation ?? [0, 0, 0];
  const q = node.rotation ?? [0, 0, 0, 1];
  const s = node.scale ?? [1, 1, 1];
  const [x, y, z, w] = q;
  const x2 = x + x, y2 = y + y, z2 = z + z;
  const xx = x * x2, xy = x * y2, xz = x * z2;
  const yy = y * y2, yz = y * z2, zz = z * z2;
  const wx = w * x2, wy = w * y2, wz = w * z2;
  return [
    (1 - (yy + zz)) * s[0], (xy + wz) * s[0], (xz - wy) * s[0], 0,
    (xy - wz) * s[1], (1 - (xx + zz)) * s[1], (yz + wx) * s[1], 0,
    (xz + wy) * s[2], (yz - wx) * s[2], (1 - (xx + yy)) * s[2], 0,
    t[0], t[1], t[2], 1,
  ];
}

function mul(a, b) { // a * b (column-major 4x4)
  const out = new Array(16).fill(0);
  for (let c = 0; c < 4; c++)
    for (let r = 0; r < 4; r++)
      for (let k = 0; k < 4; k++) out[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  return out;
}

function xform(m, x, y, z) {
  return [
    m[0] * x + m[4] * y + m[8] * z + m[12],
    m[1] * x + m[5] * y + m[9] * z + m[13],
    m[2] * x + m[6] * y + m[10] * z + m[14],
  ];
}

function audit(file) {
  const gltf = parseGLB(file);
  const { json } = gltf;
  const name = path.basename(file);
  console.log(`\n===== ${name} =====`);
  console.log(`nodes=${json.nodes.length} meshes=${json.meshes.length}`);

  // 世界矩阵
  const world = new Map();
  const visit = (idx, parentM) => {
    const n = json.nodes[idx];
    const m = mul(parentM, nodeMatrix(n));
    world.set(idx, m);
    for (const c of n.children ?? []) visit(c, m);
  };
  for (const s of json.scenes ?? []) {
    for (const idx of s.nodes) visit(idx, [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
  }

  const rows = [];
  for (const [idx, m] of world) {
    const n = json.nodes[idx];
    if (!n.mesh) continue;
    const mesh = json.meshes[n.mesh];
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    let vcount = 0;
    const yHist = new Map(); // Y 区间 -> 顶点数 (0.25m 粒度)
    for (const prim of mesh.primitives) {
      const { arr } = readPositions(gltf, prim);
      vcount += arr.length / 3;
      for (let i = 0; i < arr.length; i += 3) {
        const [wx, wy, wz] = xform(m, arr[i], arr[i + 1], arr[i + 2]);
        minX = Math.min(minX, wx); minY = Math.min(minY, wy); minZ = Math.min(minZ, wz);
        maxX = Math.max(maxX, wx); maxY = Math.max(maxY, wy); maxZ = Math.max(maxZ, wz);
        if (wy >= -1 && wy <= 8) {
          const band = Math.round(wy * 4) / 4;
          yHist.set(band, (yHist.get(band) ?? 0) + 1);
        }
      }
    }
    rows.push({ name: n.name, vcount, minX, minY, minZ, maxX, maxY, maxZ, yHist });
  }

  rows.sort((a, b) => a.minY - b.minY);
  for (const r of rows) {
    console.log(
      `${r.name.padEnd(28)} minY=${r.minY.toFixed(2)} maxY=${r.maxY.toFixed(2)} ` +
      `x=[${r.minX.toFixed(1)},${r.maxX.toFixed(1)}] z=[${r.minZ.toFixed(1)},${r.maxZ.toFixed(1)}] ` +
      `verts=${r.vcount}`
    );
    // 只对“最低点离地 > 0.2m”的静态件打印 Y 直方图(找悬浮分层)
    if (r.minY > 0.2 && r.yHist.size) {
      const bands = [...r.yHist.entries()].sort((a, b) => a[0] - b[0])
        .filter(([, c]) => c > 20)
        .map(([y, c]) => `${y.toFixed(2)}:${c}`);
      console.log(`  Y分布(≥20顶点): ${bands.join(" ")}`);
    }
  }
}

const files = process.argv.slice(2);
if (!files.length) {
  console.log("usage: node scripts/audit_float_geometry.mjs <glb...>");
  process.exit(1);
}
for (const f of files) audit(f);
