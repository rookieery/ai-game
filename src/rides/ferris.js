// 摩天轮逻辑：程序化驱动旋转（不依赖烘焙动画）
// 约定（与 Blender 管线一致）：
//   FW_Wheel       —— 轮体总根
//   FW_CabinRoot_i —— 每舱的摆正参照根
// 实现：glTF 导出会带 Y-up/Z-up 转换，空节点的本地轴不可靠。因此：
//   · 旋转轴由几何检测得出：轮体是圆盘，世界包围盒「最薄」的方向即轮轴（水平穿轮心）
//   · 每帧把每个舱根的世界姿态精确设回「初始摆正姿态」（轴无关、绝对水平）
import * as THREE from "three";

const _pq = new THREE.Quaternion();
const _wq = new THREE.Quaternion();
const _inv = new THREE.Quaternion();

// 从世界包围盒推导圆盘类资产的轴方向（最薄维度）
function detectDiscAxis(object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const axes = [
    new THREE.Vector3(1, 0, 0),
    new THREE.Vector3(0, 1, 0),
    new THREE.Vector3(0, 0, 1),
  ];
  let minI = 0;
  for (let i = 1; i < 3; i++) {
    if (size.getComponent(i) < size.getComponent(minI)) minI = i;
  }
  return axes[minI];
}

export function createFerrisWheel(gltfRoot) {
  let wheel = null;
  const cabins = [];
  gltfRoot.traverse((o) => {
    if (o.name === "FW_Wheel") wheel = o;
    else if (/^FW_CabinRoot_\d+$/.test(o.name)) cabins.push(o);
  });

  if (!wheel) console.warn("[ferris] FW_Wheel 节点未找到");

  gltfRoot.updateWorldMatrix(true, true);

  // 基准姿态（theta=0 时刻）与旋转轴（几何检测）
  const wheelRestWorld = wheel ? wheel.getWorldQuaternion(new THREE.Quaternion()) : null;
  const wheelParentInv = wheel && wheel.parent
    ? wheel.parent.getWorldQuaternion(new THREE.Quaternion()).invert()
    : new THREE.Quaternion();
  const spinAxis = wheel ? detectDiscAxis(wheel) : new THREE.Vector3(0, 0, 1);
  const cabinRest = cabins.map((c) =>
    c.getWorldQuaternion(new THREE.Quaternion())
  );

  const state = {
    theta: 0,
    speed: (2 * Math.PI) / 24, // 待机转速：24s/圈
    riding: false,
  };

  return {
    state,
    cabinRoots: cabins,
    wheelRoot: wheel,
    update(dt) {
      if (!wheel) return;
      state.theta = (state.theta + dt * state.speed) % (Math.PI * 2);

      // 轮体：绕世界轮轴旋转 -> 反解为本地四元数
      _wq.setFromAxisAngle(spinAxis, state.theta).multiply(wheelRestWorld);
      wheel.quaternion.copy(_inv.copy(wheelParentInv).multiply(_wq));

      // 舱体：世界姿态恒等于初始摆正姿态 -> 反解为本地四元数
      for (let i = 0; i < cabins.length; i++) {
        const c = cabins[i];
        c.parent.getWorldQuaternion(_pq); // 内部会刷新祖先矩阵，含轮体
        c.quaternion.copy(_inv.copy(_pq).invert()).multiply(cabinRest[i]);
      }
    },
  };
}
