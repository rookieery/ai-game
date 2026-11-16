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

  // 近距离贴脸的轮缘灯管辉光偏强, 运行时轻收 (远景观感由 Bloom 兜底)
  gltfRoot.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) {
      if (/^FW_Rim(Amber|Violet)$/.test(m.name) && m.emissiveIntensity != null) {
        m.emissiveIntensity *= 0.8;
      }
    }
  });

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
    speed: (2 * Math.PI) / 24,  // 待机转速：24s/圈
    rideSpeed: (2 * Math.PI) / 75, // 乘坐转速：75s/圈（约 1.5 分钟一圈）
    riding: false,
  };

  const _v = new THREE.Vector3();
  let rideCabIdx = -1;
  let cabLight = null;

  // 找到最低点附近的舱（登舱位置）
  function nearestBottomCabin() {
    let best = -1;
    let by = Infinity;
    for (let i = 0; i < cabins.length; i++) {
      cabins[i].getWorldPosition(_v);
      if (_v.y < by) { by = _v.y; best = i; }
    }
    return best;
  }

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
    // 登舱：锁定最低点舱位，切慢速旋转，挂舱内暖光（glTF 灯偏弱，运行时补一盏）
    board() {
      if (!wheel) return;
      state.riding = true;
      rideCabIdx = nearestBottomCabin();
      state.speed = state.rideSpeed;
      if (!cabLight) {
        cabLight = new THREE.PointLight("#ffe9c4", 16, 7, 2);
      }
      cabLight.position.set(0, -1.25, 0);
      cabins[rideCabIdx].add(cabLight);
    },
    // 下客：恢复待机转速
    disembark() {
      state.riding = false;
      rideCabIdx = -1;
      state.speed = (2 * Math.PI) / 24;
      if (cabLight) cabLight.removeFromParent();
    },
    // 乘坐中：把相机放进舱内第一人称坐姿（舱体保持水平，偏移即世界偏移）
    applyRideCamera(camera) {
      if (!state.riding || rideCabIdx < 0) return;
      const c = cabins[rideCabIdx];
      c.updateWorldMatrix(true, false);
      c.getWorldPosition(_v);
      camera.position.set(_v.x + 0.45, _v.y - 1.16, _v.z - 0.20);
    },
  };
}
