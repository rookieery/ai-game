// 摩天轮逻辑：程序化驱动旋转（不依赖烘焙动画）
// 约定（与 Blender 管线一致）：
//   FW_Wheel        —— 轮体总根
//   FW_CabinRoot_i  —— 每舱的摆正参照根
//   FW_C<i>_<材质>  —— 每舱的网格节点；v3（2026-11-27 舱体重做）起 16 个舱共用同一套网格
//                     （glb 里 16 个节点引用同一个 mesh），载入后合批成每种材质一个 InstancedMesh；
//                     登舱门框 FW_DoorSignal 例外（要逐舱开关灵火青），保留 16 个独立网格
//   FW_BoardGate_L|R —— 登舱闸两扇门（铰链在闸线两端的空节点，子网格是门扇）；只在轮停稳、舱吸附到位时开
// 实现：glTF 导出会带 Y-up/Z-up 转换，空节点的本地轴不可靠。因此：
//   · 旋转轴由几何检测得出：轮体是圆盘，世界包围盒「最薄」的方向即轮轴（水平穿轮心）
//   · 每帧把每个舱根的世界姿态精确设回「初始摆正姿态」（轴无关、绝对水平）
import * as THREE from "three";
import { CABIN, STATION } from "../player/controller.js";

const _pq = new THREE.Quaternion();
const _wq = new THREE.Quaternion();
const _inv = new THREE.Quaternion();
const _gq = new THREE.Quaternion();
const _frame = { pos: new THREE.Vector3(), quat: new THREE.Quaternion() };
const WORLD_UP = new THREE.Vector3(0, 1, 0);

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
  //   舱内照明 = FW_CabinGlow(天花发光盘) + FW_CoveLight(窗顶光槽) + FW_CabinLamp(顶灯)
  //              + FW_RoofLamp(舱檐口灯线 / 雨棚吊灯) —— 随「舱内灯光亮度」
  //   站台灯具 = FW_StationLamp(门楼 / 扶手 / 通道围栏 / 吊灯灯芯) —— 随「站台灯光亮度」（连吊灯点光）
  //   装饰灯效 = 其余 FW_ 发光材质(轮缘/彩点/轮毂/招牌/灯环/舱体漆面/鎏金新月) —— 随「装饰灯亮度」
  //   FW_DoorSignal（登舱门框）/ FW_GateSignal（登舱闸柱灯）不进表：由停靠状态开关（见 applySignal）
  // 轮缘灯管近距离贴脸辉光偏强，基准系数 0.8 (远景观感由 Bloom 兜底)
  const CABIN_LIGHT_BASE = 22; // 所乘舱补光点光基准强度（挂在天花下 0.50 m，向下照）
  const SIGNAL_BASE = 1.1;     // 停靠舱门框灵火青强度（随装饰灯）
  const GATE_SIGNAL_BASE = 1.1;  // 登舱闸柱灯灵火青强度（随装饰灯）
  const STATION_LIGHT_BASE = 38; // 「站台灯光亮度」100% 时每盏吊灯点光的强度（cd，衰减 2、射程 16）
  const GATE_SWEEP_T = 1.1;      // 登舱闸开 / 合一程的时长 s
  const cabinGlowMats = [];
  const decoGlowMats = [];
  const stationGlowMats = [];
  const gateSignalMats = [];   // FW_GateSignal 在静组里是一份材质（闸柱灯 ×2 合并在同一个网格）
  gltfRoot.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) {
      if (m.name === "FW_GateSignal" && !gateSignalMats.includes(m)) gateSignalMats.push(m);
      if (!m.name || !m.name.startsWith("FW_") || m.name === "FW_DoorSignal" || m.name === "FW_GateSignal") continue;
      if (!m.emissive || m.emissive.r + m.emissive.g + m.emissive.b < 1e-3) continue; // 非自发光
      const base = m.emissiveIntensity ?? 1;
      if (/^FW_(CabinGlow|CoveLight|CabinLamp|RoofLamp)$/.test(m.name)) cabinGlowMats.push({ m, base });
      else if (m.name === "FW_StationLamp") stationGlowMats.push({ m, base });
      else decoGlowMats.push({ m, base: m.name.startsWith("FW_Rim") ? base * 0.8 : base });
    }
  });

  // ---------- 舱体合批 ----------
  // 同一种 (网格, 材质) 在每个舱各有一个节点 -> 一个 InstancedMesh（192 个 draw call -> 12）。
  // 原网格留在各舱根下、只置为不可见（setInstanced 可切回逐舱网格做对照）。
  const groups = new Map();   // geometry|material -> { geo, mat, items: [{ mesh, cab }] }
  for (const root of cabins) {
    root.traverse((o) => {
      if (!o.isMesh) return;
      const key = o.geometry.uuid + "|" + o.material.uuid;
      let g = groups.get(key);
      if (!g) { g = { geo: o.geometry, mat: o.material, items: [] }; groups.set(key, g); }
      g.items.push({ mesh: o, cab: root });
    });
  }
  const instanced = [];       // [{ im, cabs }]
  const originals = [];       // 被合批的原网格
  const doorMats = [];        // [{ cab, mat }] 每舱一份门框材质
  for (const g of groups.values()) {
    if (g.mat.name === "FW_DoorSignal") {
      for (const { mesh, cab } of g.items) {
        mesh.material = g.mat.clone();
        mesh.material.emissiveIntensity = 0;   // 平时熄灭
        doorMats.push({ cab, mat: mesh.material });
      }
      continue;
    }
    if (g.items.length !== cabins.length || cabins.length < 2) continue;
    const im = new THREE.InstancedMesh(g.geo, g.mat, cabins.length);
    im.name = "FW_CabinInst_" + g.mat.name;
    im.frustumCulled = false;                  // 实例每帧随舱移动，不能按局部包围盒剔除
    im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    gltfRoot.add(im);
    for (const it of g.items) {
      it.mesh.visible = false;
      originals.push(it);
    }
    instanced.push({ im, cabs: g.items.map((it) => it.cab) });
  }

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

  // ---------- 登舱闸（v3 第 2 批：站台是必经之路）----------
  // 两扇铁艺闸门 FW_BoardGate_L / _R（铰链在闸线两端），只在联锁吸附到位（轮停稳）时开。
  // 绕世界竖轴各转 90°，开位贴回两侧围栏（往南），不侵入停靠舱。和轮体一样走
  // 「世界旋转 -> 反解本地四元数」，不信空节点的本地轴。
  const gateLeaves = [];
  gltfRoot.traverse((o) => {
    const side = o.name === "FW_BoardGate_L" ? "L" : o.name === "FW_BoardGate_R" ? "R" : null;
    if (!side) return;
    gateLeaves.push({
      node: o,
      // L 扇朝 +x 伸、R 扇朝 -x 伸；自由端都要转向 +z（南）。绕 +Y 转 θ: (1,0,0) -> (cosθ,0,-sinθ)
      openAngle: side === "L" ? -Math.PI / 2 : Math.PI / 2,
      rest: o.getWorldQuaternion(new THREE.Quaternion()),
      parentInv: o.parent
        ? o.parent.getWorldQuaternion(new THREE.Quaternion()).invert()
        : new THREE.Quaternion(),
    });
  });
  if (gateLeaves.length !== 2) console.warn("[ferris] FW_BoardGate_L / _R 节点不全:", gateLeaves.length);
  let gateOpen01 = 0;    // 实际开度 0 关 .. 1 开
  let gateTarget = 0;    // 目标开度
  let gateClear = true;  // 闸线带里没人（main.js 每帧给）：有人时不落闸
  function applyGate() {
    const e = gateOpen01 * gateOpen01 * (3 - 2 * gateOpen01); // 缓入缓出
    for (const g of gateLeaves) {
      g.node.quaternion.copy(g.parentInv).multiply(_gq.setFromAxisAngle(WORLD_UP, g.openAngle * e)).multiply(g.rest);
    }
  }

  // ---------- 站台吊灯点光 ×2 ----------
  // 常驻、只调强度（运行时增删灯光会让当帧出问题）；灯体自发光 FW_StationLamp 一起随「站台灯光亮度」
  const stationLights = STATION.LAMPS.map((L) => {
    const pl = new THREE.PointLight("#ffd9a8", 0, 16, 2);
    pl.position.set(L.x, L.y, L.z);
    pl.name = "FW_StationLight";
    gltfRoot.add(pl);
    return pl;
  });

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  const state = {
    theta: 0,
    riding: false,
    idlePeriod: 24,   // 待机周期：秒/圈
    ridePeriod: 75,   // 乘坐周期：秒/圈（约 1.5 分钟一圈）
    cabinLight: 0.4,  // 舱内灯光系数（补光 + 自发光联动）
    decoLight: 1.0,   // 装饰灯系数
    stationLight: 1.0, // 站台吊灯系数（点光 + 灯具自发光）
  };

  const _v = new THREE.Vector3();
  const _d = new THREE.Vector3();
  const _down = new THREE.Vector3();
  const _cr = new THREE.Vector3();
  const _m4 = new THREE.Matrix4();
  const _rootInv = new THREE.Matrix4();
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
  // 有人站在登舱站台时轮体缓停，并把最近的舱吸附到最低点（站台可站立行走；吸附到位后
  // 登舱闸开、闸内 E 登舱）；避免底舱持续掠过站台行人头顶。离开站台后恢复旋转。
  let holdWanted = false;
  let snapTheta = null; // 停靠目标角（非 null 时 theta 向它缓动）
  let signalIdx = -1;   // 当前门框亮灵火青的舱（-1 = 全灭）

  // 停靠舱门框灵火青：只有吸附到位（轮停稳）的最低那一舱亮，其余全灭。
  // 登舱闸柱灯是同一个状态（轮停稳 = 闸开 = 这一舱可上）
  function applySignal() {
    for (const { cab, mat } of doorMats) {
      mat.emissiveIntensity = cab === cabins[signalIdx] ? SIGNAL_BASE * state.decoLight : 0;
    }
    for (const m of gateSignalMats) {
      m.emissiveIntensity = signalIdx >= 0 ? GATE_SIGNAL_BASE * state.decoLight : 0;
    }
  }

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
    spinAxis, // 轮轴 (世界系单位向量, 水平): fx/fw_director.js 算所乘舱离顶时间要用
    // 登舱闸线能否通行（main.js 每帧据此开关闸线碰撞）：开始开就放行，关严才重新挡
    get gatePassable() { return gateOpen01 > 0.02; },
    stationLights, // 站台吊灯点光 ×2（取证 / 回归用）
    instancedMeshes: instanced.map((x) => x.im),
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

      // 合批舱体：每个实例的矩阵 = 对应舱根的世界矩阵（换算到 gltfRoot 本地系）
      if (instanced.length) {
        gltfRoot.updateWorldMatrix(true, false);
        _rootInv.copy(gltfRoot.matrixWorld).invert();
        for (const { im, cabs } of instanced) {
          for (let k = 0; k < cabs.length; k++) {
            cabs[k].updateWorldMatrix(true, false);
            im.setMatrixAt(k, _m4.multiplyMatrices(_rootInv, cabs[k].matrixWorld));
          }
          im.instanceMatrix.needsUpdate = true;
        }
      }

      // 停靠舱门框灵火青：联锁吸附到位（轮停稳）时最低的那一舱亮，其余时候全灭
      const docked = snapTheta !== null && Math.abs(snapTheta - state.theta) < 1e-3
        ? nearestBottomCabin() : -1;
      if (docked !== signalIdx) {
        signalIdx = docked;
        applySignal();
      }

      // 登舱闸：吸附到位（轮停稳）就开。要关的时候如果人还站在闸线带里，只要没关严就（重新）打开；
      // 开合各一程 GATE_SWEEP_T
      if (docked >= 0) gateTarget = 1;
      else gateTarget = gateClear ? 0 : (gateOpen01 > 0 ? 1 : 0);
      if (gateOpen01 !== gateTarget) {
        const dir = Math.sign(gateTarget - gateOpen01);
        gateOpen01 = clamp(gateOpen01 + (dir * dt) / GATE_SWEEP_T, 0, 1);
        applyGate();
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
      // v3：灯挂在舱中央、天花下 0.50 m（略低于站姿眼位）向下照 —— v2 挂在脚边 0.29 m，柱根炸热点；
      //      再高会让深色天花被照成亮板（第 1 批实测：贴天花挂时顶部一条亮带）
      cabLight.position.set(0, CABIN.FLOOR_Y + 1.50, 0);
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
    // 已停靠 = 联锁吸附到位（轮停稳）。登舱闸和「乘坐摩天轮」提示都只在此时有效（main.js / interact.js）
    isDocked: () => signalIdx >= 0,
    // 登舱闸开度 0..1（取证用）
    gateOpen01: () => gateOpen01,
    // 闸线带里有没有人（main.js 每帧给）：有人就不落闸
    setGateClear(clear) { gateClear = !!clear; },
    // 应用设置面板（百分比 -> 实际参数）
    applySettings(s) {
      state.idlePeriod = clamp(s.ferrisIdlePeriod, 12, 60);
      state.ridePeriod = clamp(s.ferrisRidePeriod, 40, 120);
      state.cabinLight = clamp(s.cabinLight, 0, 200) / 100;
      state.decoLight = clamp(s.decoLight, 0, 200) / 100;
      state.stationLight = clamp(s.ferrisStationLight ?? 100, 0, 200) / 100;
      for (const { m, base } of cabinGlowMats) m.emissiveIntensity = base * state.cabinLight;
      for (const { m, base } of decoGlowMats) m.emissiveIntensity = base * state.decoLight;
      for (const { m, base } of stationGlowMats) m.emissiveIntensity = base * state.stationLight;
      for (const pl of stationLights) pl.intensity = STATION_LIGHT_BASE * state.stationLight;
      if (cabLight) cabLight.intensity = CABIN_LIGHT_BASE * state.cabinLight;
      applySignal();
    },
    // 合批开关（取证 / 对照用）：off = 各舱原网格逐个可见
    setInstanced(on) {
      for (const { im } of instanced) im.visible = !!on;
      for (const it of originals) it.mesh.visible = !on;
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
