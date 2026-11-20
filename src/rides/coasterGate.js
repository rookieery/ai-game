// 幽冥回环 A2 验票闸机 (M4): NL_Gate_0/1 锚点 + NL_GateArm_* 转子交互开合
// B0 拆节点后闸臂=独立网格(锚点子节点), 闭合位(转角0)=建模位; 开位 +60°: 三臂让至行进轴
// 两侧, 通道可读为「开」且无烘焙残影。碰撞侧闸线 rect 由 main 接线 setRectDisabled 随开合禁用。
// 锚点本地朝向不可信 (glb-spin-axis 教训): 只取其世界位置定交互点, 旋转直接用本地 X 轴
// (NL_Gate 节点平移+恒等旋转, 本地 X = 世界 X = 闸翼轴, roller_coaster.py A2 段)。
import * as THREE from "three";

const OPEN_ANGLE = Math.PI / 3; // 开位转角 (60°)
const SWEEP_T = 1.0;            // 扫动时长 s (easeOut 开 / easeIn 关)
const AUTO_CLOSE = 6.0;         // 开启后无穿越自动落锁
const HOLD_BAND = 0.9;          // 玩家仍在闸线带 (|z+40.4|<此值) 时挂起落锁, 防夹

export function createCoasterGate(staticRoot, { player, onSolid }) {
  const gates = []; // { node, baseRot }
  staticRoot?.traverse((o) => {
    const m = o.name && o.name.match(/^NL_Gate_(\d)$/);
    if (m) gates[+m[1]] = { node: o, baseRot: o.rotation.x };
  });
  if (gates.filter(Boolean).length !== 2) console.warn("[coasterGate] NL_Gate_* 不全:", gates.length);

  // 交互点 = 闸线中点南侧 0.8m (走廊侧; 站台侧不出提示 = 西口只进不出)
  let spot = { x: 9.4, z: -39.6 };
  if (gates[0]) {
    const p = new THREE.Vector3();
    gates[0].node.getWorldPosition(p);
    spot = { x: +p.x.toFixed(2), z: +(p.z + 0.8).toFixed(2) };
  }

  let state = "closed"; // closed | opening | open | closing
  let t = 0;

  return {
    update(dt) {
      if (!gates.length || state === "closed") return;
      const pz = player?.pos.z ?? 0;
      const inBand = Math.abs(pz + 40.4) < HOLD_BAND;
      if (state === "opening") {
        t += dt;
        const k = Math.min(1, t / SWEEP_T);
        const e = 1 - (1 - k) * (1 - k);
        for (const g of gates) g.node.rotation.x = g.baseRot + OPEN_ANGLE * e;
        if (k >= 1) { state = "open"; t = 0; }
      } else if (state === "open") {
        t += dt;
        if (t > AUTO_CLOSE && !inBand) { state = "closing"; t = 0; }
      } else if (state === "closing") {
        if (inBand) return; // 互锁: 玩家在闸线带内不落锁
        t += dt;
        const k = Math.min(1, t / SWEEP_T);
        const e = k * k;
        for (const g of gates) g.node.rotation.x = g.baseRot + OPEN_ANGLE * (1 - e);
        if (k >= 1) { state = "closed"; onSolid?.(false); }
      }
    },
    tryOpen() {
      if (state !== "closed") return;
      state = "opening";
      t = 0;
      onSolid?.(true); // 闸线碰撞随扫动即禁 (扫动 1s 内玩家尚未走到闸线)
    },
    isClosed: () => state === "closed",
    getSpot: () => spot,
    getState: () => state,
  };
}
