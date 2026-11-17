// 显灵木马逻辑：程序化驱动旋转 + 马匹起伏 + 顶棚补光 + 动态碰撞（不依赖烘焙动画）
// 约定（与 carousel.py 管线一致）：
//   CR_Spin    —— 机台旋转总根（世界包围盒最薄轴 = 旋转轴, 与 ferris 同款几何检测）
//   CR_Ride_i  —— 每骑乘位起伏根（i0/i5 为座车不起伏; 其余马位 sin 起伏）
//   骑乘位/铜杆随盘旋转, 碰撞圆由本模块每帧改写（player.registerCircles 注册引用,
//   圆坐标直接读 CR_Ride_i 世界位置, 无需手工换算旋转方向）
import * as THREE from "three";

const HORSE_IDX = new Set([1, 2, 3, 4, 6, 7, 8, 9]); // 马位 (i0/i5 = 座车), 与 carousel.py 一致
const RIDE_COUNT = 10;
const DECK_Y = 0.62;      // 起伏基准 = 平台顶
const BOB_AMP = 0.22;     // 起伏幅度 (与 carousel.py 一致)
const BOB_PERIOD = 3.0;   // 起伏周期秒
const BOB_PHASE = 0.7;    // 相邻马位相位差
const SPIN_PERIOD = 18;   // 默认转速 秒/圈
const CANOPY_LIGHT_BASE = 22; // 顶棚补光点光基准强度
// 顶棚补光 ×3 (对应预览 CR_PvLight: blender 方位 202+120k, r4.5, z4.6;
// blender (x,y) -> glTF 本地 (x, -y))
const CANOPY_LIGHTS = [0, 1, 2].map((k) => {
  const a = ((202 + (k * 360) / 3) * Math.PI) / 180;
  return { x: 4.5 * Math.cos(a), z: -4.5 * Math.sin(a) };
});

export function createCarousel(gltfRoot, { player } = {}) {
  let spin = null;
  const rides = [];
  gltfRoot.traverse((o) => {
    if (o.name === "CR_Spin") spin = o;
    else if (/^CR_Ride_\d+$/.test(o.name)) rides[+o.name.slice(8)] = o;
  });
  if (!spin) console.warn("[carousel] CR_Spin 节点未找到");

  // 自发光材质登记（装饰灯亮度联动）: 全部 CR_ 发光材质
  const glowMats = [];
  gltfRoot.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    for (const m of mats) {
      if (!m.name || !m.name.startsWith("CR_") || !m.emissive) continue;
      if (m.emissive.r + m.emissive.g + m.emissive.b < 1e-3) continue; // 非自发光
      glowMats.push({ m, base: m.emissiveIntensity ?? 1 });
    }
  });

  gltfRoot.updateWorldMatrix(true, true);

  // 旋转轴几何检测（平台盘世界包围盒最薄维度, 轴向无关）
  const box = new THREE.Box3().setFromObject(spin);
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
  const spinAxis = axes[minI];

  // 基准姿态（theta=0 时刻）
  const restWorld = spin.getWorldQuaternion(new THREE.Quaternion());
  const parentInv = spin.parent
    ? spin.parent.getWorldQuaternion(new THREE.Quaternion()).invert()
    : new THREE.Quaternion();

  const state = {
    theta: 0,
    t: 0,                 // 起伏时钟（独立于转角, 转速调整不影响起伏节奏）
    spinPeriod: SPIN_PERIOD,
    decoLight: 1.0,
    cabinLight: 0.4,
  };

  // 顶棚下补光 ×3（静态, 挂根; 随「舱内灯光亮度」联动）
  const canopyLights = CANOPY_LIGHTS.map((L) => {
    const pl = new THREE.PointLight("#FFD9A8", 0, 13, 2);
    pl.position.set(L.x, 4.6, L.z);
    gltfRoot.add(pl);
    return pl;
  });

  // 动态碰撞圆 x20: 每骑乘位 1 圆 + 每铜杆 1 圆
  //   马 r0.55 无限高（顶 ~2.2 跳不上）; 座车 r0.85 h1.40（顶缘可跳站, 随盘转动）
  //   铜杆 r0.10 无限高
  const dyn = [];
  for (let i = 0; i < RIDE_COUNT; i++) {
    dyn.push(HORSE_IDX.has(i)
      ? { x: 0, z: 0, r: 0.55 }
      : { x: 0, z: 0, r: 0.85, h: 1.4 });
    dyn.push({ x: 0, z: 0, r: 0.1 });
  }
  if (player?.registerCircles) player.registerCircles(dyn);
  else console.warn("[carousel] player 未传入, 动态碰撞未注册");

  const _wq = new THREE.Quaternion();
  const _inv = new THREE.Quaternion();
  const _wp = new THREE.Vector3();
  const _fx = new THREE.Vector3();
  const _frame = { pos: new THREE.Vector3(), quat: new THREE.Quaternion(), eye: 2.24, yaw: 0 };

  // ---------- 骑乘（固定座位环游, 摩天轮乘坐模板的第二设施实现） ----------
  // 上马 = 锁定就近骑乘位; 相机帧 = 骑乘位根世界位姿（含起伏）+ 骑坐眼高;
  // 马 eye 2.24（鞍座 ~1.51 + 躯干）, 座车 eye 1.36（座椅 ~0.6 + 躯干）。
  let mountedIdx = -1;

  function nearestRideIdx() {
    let best = 0;
    let bd = Infinity;
    for (let i = 0; i < RIDE_COUNT; i++) {
      if (!rides[i]) continue;
      rides[i].getWorldPosition(_wp);
      const d = player?.pos
        ? Math.hypot(_wp.x - player.pos.x, _wp.z - player.pos.z)
        : i;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  return {
    state,
    spinRoot: spin,
    rideRoots: rides,
    get mounted() { return mountedIdx; },
    // 上马: 锁定就近骑乘位（platform 上按 E 时由 interact 触发）
    board() {
      mountedIdx = nearestRideIdx();
      return mountedIdx;
    },
    // 下马: 返回平台落点（骑乘位方位向外推到 r7.6, 清开马位/铜杆碰撞圈）
    dismountPoint() {
      const r = rides[mountedIdx];
      if (!r) return null;
      r.getWorldPosition(_wp);
      const ox = gltfRoot.position.x;
      const oz = gltfRoot.position.z;
      const dx = _wp.x - ox;
      const dz = _wp.z - oz;
      const d = Math.hypot(dx, dz) || 1;
      return { x: ox + (dx / d) * 7.6, z: oz + (dz / d) * 7.6 };
    },
    dismount() {
      mountedIdx = -1;
    },
    // 骑坐相机帧: 骑乘位根世界位姿（旋转+起伏都在内）, yaw = 行进方向
    getMountFrame() {
      const r = rides[mountedIdx];
      if (!r) return null;
      r.updateWorldMatrix(true, false);
      _frame.pos.setFromMatrixPosition(r.matrixWorld);
      _frame.quat.setFromRotationMatrix(r.matrixWorld);
      _frame.eye = HORSE_IDX.has(mountedIdx) ? 2.24 : 1.36;
      _fx.set(1, 0, 0).applyQuaternion(_frame.quat);
      _frame.yaw = Math.atan2(-_fx.x, -_fx.z); // controller forward=(-sin,-cos)
      return _frame;
    },
    update(dt) {
      if (!spin) return;
      state.t += dt;
      const omega = (2 * Math.PI) / state.spinPeriod;
      state.theta = (state.theta + dt * omega) % (Math.PI * 2);

      // 机台: 绕世界竖轴旋转 -> 反解本地四元数（轴无关, 与 ferris 同款）
      _wq.setFromAxisAngle(spinAxis, state.theta).multiply(restWorld);
      spin.quaternion.copy(_inv.copy(parentInv).multiply(_wq));

      for (let i = 0; i < RIDE_COUNT; i++) {
        const r = rides[i];
        if (!r) continue;
        if (HORSE_IDX.has(i)) {
          // 马位起伏: 直接驱动位置 y（覆盖烘焙动画）
          r.position.y =
            DECK_Y + BOB_AMP * Math.sin((2 * Math.PI * state.t) / BOB_PERIOD + i * BOB_PHASE);
        }
        // 动态碰撞圆跟随骑乘位世界位置（铜杆与骑乘位同方位）
        r.getWorldPosition(_wp);
        dyn[i * 2].x = _wp.x;
        dyn[i * 2].z = _wp.z;
        dyn[i * 2 + 1].x = _wp.x;
        dyn[i * 2 + 1].z = _wp.z;
      }
    },
    // 应用设置面板（百分比 -> 实际参数）
    applySettings(s) {
      state.spinPeriod = clamp(s.carouselSpinPeriod ?? SPIN_PERIOD, 10, 40);
      state.cabinLight = clamp(s.cabinLight, 0, 200) / 100;
      state.decoLight = clamp(s.decoLight, 0, 200) / 100;
      for (const { m, base } of glowMats) m.emissiveIntensity = base * state.decoLight;
      for (const pl of canopyLights) pl.intensity = CANOPY_LIGHT_BASE * state.cabinLight;
    },
  };
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
