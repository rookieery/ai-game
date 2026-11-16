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
const _frame = { pos: new THREE.Vector3(), quat: new THREE.Quaternion() };

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

  // 自发光材质登记（设置面板可调）：
  //   舱内照明 = FW_InteriorGlow(天花/墙板) + FW_RoofLamp(檐灯) —— 随「舱内灯光亮度」
  //   装饰灯效 = 其余 FW_ 发光材质(轮缘/彩点/轮毂/招牌/灯环/舱体涂装) —— 随「装饰灯亮度」
  // 轮缘灯管近距离贴脸辉光偏强，基准系数 0.8 (远景观感由 Bloom 兜底)
  const CABIN_LIGHT_BASE = 16; // 登舱补光点光基准强度
  const cabinGlowMats = [];
  const decoGlowMats = [];
  gltfRoot.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) {
      if (!m.name || !m.name.startsWith("FW_") || !m.emissive) continue;
      if (m.emissive.r + m.emissive.g + m.emissive.b < 1e-3) continue; // 非自发光
      const base = m.emissiveIntensity ?? 1;
      if (/^FW_(InteriorGlow|RoofLamp)$/.test(m.name)) cabinGlowMats.push({ m, base });
      else decoGlowMats.push({ m, base: m.name.startsWith("FW_Rim") ? base * 0.8 : base });
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

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  const state = {
    theta: 0,
    riding: false,
    idlePeriod: 24,   // 待机周期：秒/圈
    ridePeriod: 75,   // 乘坐周期：秒/圈（约 1.5 分钟一圈）
    cabinLight: 0.4,  // 舱内灯光系数（补光 + 自发光联动）
    decoLight: 1.0,   // 装饰灯系数
  };

  const _v = new THREE.Vector3();
  const _d = new THREE.Vector3();
  const _down = new THREE.Vector3();
  const _cr = new THREE.Vector3();
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

  // ---------- 站台安全联锁 ----------
  // 有人站在登舱站台时轮体缓停，并把最近的舱吸附到最低点（站台可站立行走 +
  // 停靠舱旁 E 登舱）；避免底舱持续掠过站台行人头顶。离开站台后恢复旋转。
  let holdWanted = false;
  let snapTheta = null; // 停靠目标角（非 null 时 theta 向它缓动）

  // 最低舱相对「轮面正下方」的角度偏差（rad, 绕 spinAxis；spinAxis 必为水平轴）
  function bottomOffset() {
    const i = nearestBottomCabin();
    if (i < 0) return 0;
    const hub = wheel.getWorldPosition(_v);
    const p = cabins[i].getWorldPosition(_d);
    const d = _d.sub(hub);
    d.addScaledVector(spinAxis, -d.dot(spinAxis)); // 投影到轮面
    if (d.lengthSq() < 1e-6) return 0;
    d.normalize();
    _down.set(0, -1, 0); // 轴水平 ⇒ 世界 -Y 即轮面「正下」
    _cr.crossVectors(_down, d);
    return Math.atan2(_cr.dot(spinAxis), _down.dot(d));
  }

  return {
    state,
    cabinRoots: cabins,
    wheelRoot: wheel,
    update(dt) {
      if (!wheel) return;
      if (snapTheta !== null) {
        // 停靠缓动（初速与待机转速同量级, 无跳变感）; 收敛阈值内硬吸附
        state.theta += (snapTheta - state.theta) * Math.min(1, dt * 2.2);
        if (Math.abs(snapTheta - state.theta) < 1e-3) state.theta = snapTheta;
      } else {
        const omega = (2 * Math.PI) / (state.riding ? state.ridePeriod : state.idlePeriod);
        state.theta = (state.theta + dt * omega) % (Math.PI * 2);
      }

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
    // 登舱：锁定最低点舱位（转速由 update 按 riding 态取用），挂舱内暖光
    board() {
      if (!wheel) return;
      state.riding = true;
      rideCabIdx = nearestBottomCabin();
      if (!cabLight) {
        cabLight = new THREE.PointLight("#ffe9c4", CABIN_LIGHT_BASE * state.cabinLight, 7, 2);
      }
      // 落地灯位（柱脚旁偏门侧）：走动模式下眼位可到舱中心 0.37m 内，
      // 灯挂中心会贴脸照爆（Bloom 过曝）；落地后最近 1.1m，光也更均匀
      cabLight.position.set(0, -2.05, 0.15);
      cabins[rideCabIdx].add(cabLight);
    },
    // 下客：恢复待机转速
    disembark() {
      state.riding = false;
      rideCabIdx = -1;
      if (cabLight) cabLight.removeFromParent();
    },
    // 站台占用联锁（由 main.js 每帧按玩家脚高驱动）
    setHold(h) {
      if (!wheel) return;
      if (h && !holdWanted) snapTheta = state.theta - bottomOffset();
      if (!h) snapTheta = null;
      holdWanted = h;
    },
    // 应用设置面板（百分比 -> 实际参数）
    applySettings(s) {
      state.idlePeriod = clamp(s.ferrisIdlePeriod, 12, 60);
      state.ridePeriod = clamp(s.ferrisRidePeriod, 40, 120);
      state.cabinLight = clamp(s.cabinLight, 0, 200) / 100;
      state.decoLight = clamp(s.decoLight, 0, 200) / 100;
      for (const { m, base } of cabinGlowMats) m.emissiveIntensity = base * state.cabinLight;
      for (const { m, base } of decoGlowMats) m.emissiveIntensity = base * state.decoLight;
      if (cabLight) cabLight.intensity = CABIN_LIGHT_BASE * state.cabinLight;
    },
    // 乘坐中：返回所乘舱的世界位姿（舱根每帧被锁回摆正姿态，quat 恒定）
    // 供玩家控制器做舱内本地走动；非乘坐态返回 null
    getRideFrame() {
      if (!state.riding || rideCabIdx < 0) return null;
      const c = cabins[rideCabIdx];
      c.updateWorldMatrix(true, false);
      c.getWorldPosition(_frame.pos);
      c.getWorldQuaternion(_frame.quat);
      return _frame;
    },
  };
}
