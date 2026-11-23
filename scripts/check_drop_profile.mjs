// 诊断: 提升顶->俯冲段竖直剖面 + 全线最低点 (只读 centerline.json, 不改任何东西)
import fs from 'node:fs';

const j = JSON.parse(fs.readFileSync('model/roller_coaster/centerline.json', 'utf8'));
console.log('root keys:', Object.keys(j));

// 结构探测
let samples = null;
if (Array.isArray(j)) samples = j;
else for (const k of Object.keys(j)) if (Array.isArray(j[k]) && j[k].length > 100) samples = j[k];
console.log('samples:', samples.length, 'first:', JSON.stringify(samples[0]).slice(0, 200));

const S = samples.map((p, i) => {
  const pos = p.pos ?? p.p;
  const tan = p.tan ?? p.t;
  const zone = p.zone ?? p.z;
  return { i, s: p.s ?? i * 0.5, x: pos[0], y: pos[1], z: pos[2],
           tx: tan?.[0], ty: tan?.[1], tz: tan?.[2], zone };
});

// ---- 1) 全线每个 zone 的 z 范围
const zones = new Map();
for (const p of S) {
  if (!zones.has(p.zone)) zones.set(p.zone, { n: 0, zmin: 1e9, zmax: -1e9, at: null });
  const q = zones.get(p.zone); q.n++;
  if (p.z < q.zmin) { q.zmin = p.z; q.at = p; }
  q.zmax = Math.max(q.zmax, p.z);
}
console.log('\n== zone z 范围 ==');
for (const [zn, q] of zones) {
  console.log(`${zn.padEnd(10)} n=${String(q.n).padStart(4)}  z ${q.zmin.toFixed(2)} ~ ${q.zmax.toFixed(2)}   最低点@(${q.at.x.toFixed(1)},${q.at.y.toFixed(1)}) s=${q.at.s.toFixed(1)}`);
}

// ---- 2) 全线最低 10 点
const low = [...S].sort((a, b) => a.z - b.z).slice(0, 10);
console.log('\n== 全线 z 最低 10 采样 ==');
for (const p of low) console.log(`z=${p.z.toFixed(3)}  (${p.x.toFixed(2)},${p.y.toFixed(2)})  zone=${p.zone}  s=${p.s.toFixed(1)}`);

// ---- 3) 提升顶->俯冲->谷底 剖面: 找 zone=lift 末尾往前后的窗口
const iLiftEnd = S.findIndex(p => p.zone === 'drop');
console.log('\n== lift 尾 -> drop 段 逐 2m 剖面 (pitch=asin(tz), 航向=atan2(tx,ty)) ==');
let lastPrint = -1e9;
for (const p of S) {
  if (p.i < iLiftEnd - 90 || p.i > iLiftEnd + 130) continue;
  if (p.s - lastPrint < 1.9) continue;
  lastPrint = p.s;
  const pitch = Math.asin(Math.max(-1, Math.min(1, p.tz))) * 180 / Math.PI;
  const hdg = Math.atan2(p.tx, p.ty) * 180 / Math.PI;
  console.log(`s=${p.s.toFixed(1).padStart(6)} z=${p.z.toFixed(2).padStart(7)} (${p.x.toFixed(1)},${p.y.toFixed(1)}) pitch=${pitch.toFixed(1).padStart(6)} hdg=${hdg.toFixed(1).padStart(6)} ${p.zone}`);
}

// ---- 4) 曲率符号检测: 俯冲窗口内竖直剖面拐点 (凹凸转换)
// 用 pitch 沿弧长的导数符号: dPitch/ds > 0 = 拉起(凹), < 0 = 俯压(凸)
console.log('\n== 俯冲窗口 pitch 变化率 (凹/凸判别) ==');
let prevPitch = null, prevS = null;
for (const p of S) {
  if (p.i < iLiftEnd - 60 || p.i > iLiftEnd + 120) continue;
  const pitch = Math.asin(Math.max(-1, Math.min(1, p.tz))) * 180 / Math.PI;
  if (prevPitch !== null) {
    const dp = (pitch - prevPitch) / (p.s - prevS); // deg per m
    const tag = dp > 0.5 ? '凹(拉起)' : dp < -0.5 ? '凸(俯压)' : '—';
    if (p.i % 4 === 0) console.log(`s=${p.s.toFixed(1).padStart(6)} z=${p.z.toFixed(2).padStart(7)} pitch=${pitch.toFixed(1).padStart(6)} dP/ds=${dp.toFixed(2).padStart(6)} ${tag} ${p.zone}`);
  }
  prevPitch = pitch; prevS = p.s;
}
