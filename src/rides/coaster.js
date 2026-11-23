// 幽冥回环 NETHER LOOP —— M3 观赏运行动画
// 数据契约 (model/roller_coaster/):
//   centerline.json   1008 样本 @0.5m 闭环 (s, p[3], t[3], u[3], v, zone) — blender 坐标
//   roller_coaster.glb      静态件 (恒等放置, 与园区共享原点: blender +Y 北 = app -Z)
//   roller_coaster_train.glb  NL_TrainRoot > NL_Car_i > (车体网格 + NL_Wheel_* + 锚点)
// 坐标映射: app = (bx, bz, -by)  (glTF 导出烘焙同款, 节点平移已验证一致)
// 运行: v(s) 能量守恒速度表驱动弧长 s; 过缝合点后站台爬行至停车位再驻留 12s; 闭环天然循环 (首末缝合样本)
import * as THREE from "three";
import { loadGLB } from "../park/loader.js";

const CAR_N = 6;
const CAR_GAP = 2.35;
const WHEEL_R = 0.15;
const DWELL = 12.0; // 站台驻留秒数
// ---- M4 乘坐会话常数 ----
const LAPBAR_OPEN = 1.5;      // 压肩开启角 rad (绕 NL_LapBar 锚点局部 X=车右轴, 抬向前上方)
const LAPBAR_CLOSE_T = 0.8;   // 压肩闭合时长 s
const LAPBAR_OPEN_T = 0.7;    // 压肩开启时长 s
const DISPATCH_T = 2.4;       // 压肩锁闭后的发车倒计时 s
const CHASE_BACK = 7.2;       // 追逐机位: 头车后方弧长 m
const CHASE_UP = 1.7;         // 追逐机位: 中心线上方高度 m

// blender 帧 -> app 旋转基 (A: (x,y,z)->(x,z,-y), det+1)
const _m4 = new THREE.Matrix4();
const _pos = new THREE.Vector3();
const _tan = new THREE.Vector3();
const _up = new THREE.Vector3();
const _rv = new THREE.Vector3();
const _negTan = new THREE.Vector3();

export async function createCoaster(scene, manager) {
  const [staticRoot, trainRoot, cl] = await Promise.all([
    loadGLB("/assets/models/roller_coaster.glb", manager),
    loadGLB("/assets/models/roller_coaster_train.glb", manager),
    fetch("/assets/models/roller_coaster_centerline.json").then((r) => r.json()),
  ]);
  scene.add(staticRoot);
  scene.add(trainRoot);

  // ---- 中心线采样表 ----
  const N = cl.samples.length;
  const DS = cl.ds ?? 0.5;
  const L = (N - 1) * DS; // 末样本=缝合样本(=首样本), 运动域 [0, L)
  const P = new Float64Array(N * 3);
  const T = new Float64Array(N * 3);
  const U = new Float64Array(N * 3);
  const V = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    const s = cl.samples[i];
    P[i * 3] = s.p[0]; P[i * 3 + 1] = s.p[2]; P[i * 3 + 2] = -s.p[1]; // app 坐标
    T[i * 3] = s.t[0]; T[i * 3 + 1] = s.t[2]; T[i * 3 + 2] = -s.t[1];
    U[i * 3] = s.u[0]; U[i * 3 + 1] = s.u[2]; U[i * 3 + 2] = -s.u[1];
    V[i] = s.v;
  }

  // 站台中点 = 列车静态停靠基准 (与 Blender mid_i=len//2 语义一致; 必须用中位数——
  // 末样本是缝合样本(zone 沿袭"station"), 混进均值会把停车位拖偏 10.6m)
  let sHead = 0;
  {
    const st = [];
    for (let i = 0; i < N; i++) {
      if (cl.samples[i].zone === "station") st.push(i * DS);
    }
    if (st.length) {
      st.sort((a, b) => a - b);
      sHead = st[Math.floor(st.length / 2)] + (CAR_N / 2 - 0.5) * CAR_GAP;
    }
  }

  // 弧长 s 处采样 (线性插值 + 重正交), 无节点写入版 (追逐机位/锚点合成共用)
  function sampleFrame(s) {
    const f = ((s % L) + L) % L / DS;
    const i0 = Math.min(N - 2, Math.floor(f));
    const u = f - i0;
    const i1 = i0 + 1;
    const pos = new THREE.Vector3(
      P[i0 * 3] + (P[i1 * 3] - P[i0 * 3]) * u,
      P[i0 * 3 + 1] + (P[i1 * 3 + 1] - P[i0 * 3 + 1]) * u,
      P[i0 * 3 + 2] + (P[i1 * 3 + 2] - P[i0 * 3 + 2]) * u,
    );
    const tan = new THREE.Vector3(
      T[i0 * 3] + (T[i1 * 3] - T[i0 * 3]) * u,
      T[i0 * 3 + 1] + (T[i1 * 3 + 1] - T[i0 * 3 + 1]) * u,
      T[i0 * 3 + 2] + (T[i1 * 3 + 2] - T[i0 * 3 + 2]) * u,
    ).normalize();
    const up = new THREE.Vector3(
      U[i0 * 3] + (U[i1 * 3] - U[i0 * 3]) * u,
      U[i0 * 3 + 1] + (U[i1 * 3 + 1] - U[i0 * 3 + 1]) * u,
      U[i0 * 3 + 2] + (U[i1 * 3 + 2] - U[i0 * 3 + 2]) * u,
    );
    up.addScaledVector(tan, -up.dot(tan)).normalize();
    const rv = new THREE.Vector3().crossVectors(tan, up); // 车局部 +X (右)
    // glb 车局部轴契约 (scripts/dump_train_glb.mjs 实测): X=右, Y=上, Z=-前。
    // (Blender 车局部 (x=右,y=前,z=上) 经 glTF +Y-up 导出换算 (x,z,-y) 后即此约定;
    //  若沿用旧基 makeBasis(rv,tan,up) 会把车长轴掰到轨道竖向 -> 列车倒立)
    const negTan = tan.clone().negate();
    const quat = new THREE.Quaternion().setFromRotationMatrix(
      new THREE.Matrix4().makeBasis(rv, up, negTan),
    );
    return { pos, tan, up, quat };
  }

  function frameAt(s, car) {
    const sf = sampleFrame(s);
    car.position.copy(sf.pos);
    car.quaternion.copy(sf.quat);
    car.updateMatrix(); // 子节点(轮/锚点)矩阵链
  }

  function vAt(s) {
    const f = ((s % L) + L) % L / DS;
    const i0 = Math.min(N - 2, Math.floor(f));
    const u = f - i0;
    return V[i0] + (V[i0 + 1] - V[i0]) * u;
  }

  // ---- 列车节点 ----
  const cars = [];
  const wheels = []; // {node, }
  let camPov = null;   // NL_CamPov 头车前排视线锚点 (POV 机位, 车局部 Z=-前)
  const lapBars = [];  // NL_LapBar_* 压肩开合锚点 ×11 (子网格 NL_LapBarMesh/Pad 随转)
  trainRoot.traverse((o) => {
    const m = o.name && o.name.match(/^NL_Car_(\d)$/);
    if (m) cars[+m[1]] = o;
    else if (o.name && o.name.startsWith("NL_Wheel_")) wheels.push(o);
    else if (o.name === "NL_CamPov") camPov = o;
    else if (o.name && o.name.startsWith("NL_LapBar_")) lapBars.push(o);
  });
  if (cars.filter(Boolean).length !== CAR_N) console.warn("[coaster] NL_Car_i 不全:", cars.length);
  if (wheels.length !== 24) console.warn("[coaster] 轮组数:", wheels.length);
  if (!camPov) console.warn("[coaster] NL_CamPov 缺失, POV 机位不可用");
  if (lapBars.length !== 11) console.warn("[coaster] NL_LapBar_* 数:", lapBars.length);

  // 手写管件(肩环/灯笼/钩臂)面序不保证一致, Blender 双面渲染无感, three.js 单面会成黑洞 -> 全双面保险
  trainRoot.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) m.side = THREE.DoubleSide;
  });

  // ---- 装饰灯材质登记 (设置面板「过山车 · 装饰灯亮度」) ----
  // 静态件(磷光描边/南瓜灯串/站牌/地面灯环/迷宫光帽) + 列车(南瓜壳/尾灯/轮磷光) 全部 NL_ 自发光材质
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const decoGlowMats = [];
  for (const root of [staticRoot, trainRoot]) {
    root.traverse((o) => {
      const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
      for (const m of mats) {
        if (!m.name || !m.name.startsWith("NL_") || !m.emissive) continue;
        if (m.emissive.r + m.emissive.g + m.emissive.b < 1e-3) continue; // 非自发光
        decoGlowMats.push({ m, base: m.emissiveIntensity ?? 1 });
      }
    });
  }

  const state = {
    phase: "dwell", // dwell | run | crawl(过缝合点后站台爬行, 到停车位再驻留)
    s: sHead,
    v: 0,
    dwellT: DWELL,
    laps: 0,
    hold: false, // M4 站台联锁 (main 每帧按 walk+站台位置驱动): true=冻结发车倒计时
    session: null, // M4 乘坐会话 (下方 session 对象的活动引用, 取证可读)
  };

  // ============ M4 乘坐会话 ============
  // 乘坐复用观赏运行的 v(s) 物理, 仅在三个既有分支点插桩 (dwell 发车源 / 缝合点停站选择 /
  // crawl 对位停站), 无会话时逐帧等价 M3。下客=仅站台 (用户拍板): 排队后到站停稳 →
  // 压肩开启 → onDisembarkReady 回调, main 接管黑幕转场。
  const session = {
    active: false,
    wantOff: false, // 途中排队下一站下车 (到站停稳前可取消)
    offFired: false,
    lapbar: 1, // 0 开 .. 1 闭 (动画值)
    dispatchT: 0,
  };
  state.session = session;
  let lapbarTarget = 1;
  let onDisembarkReady = null; // main 注入

  // 登车交互点 = 停靠位 NL_Seat_01L 世界坐标 (首帧摆位后解析一次, 停车姿态恒定)
  let boardSpot = null;
  function getBoardSpot() {
    if (!boardSpot) {
      const seat = trainRoot.getObjectByName("NL_Seat_01L");
      if (seat) {
        seat.updateWorldMatrix(true, false);
        const p = seat.getWorldPosition(new THREE.Vector3());
        boardSpot = { x: +p.x.toFixed(3), z: +p.z.toFixed(3) };
      } else {
        boardSpot = { x: 11.16, z: -60.96 }; // 兜底 (dump 实测值)
      }
    }
    return boardSpot;
  }
  const getDropSpot = () => ({ x: 13.2, z: -60.2 }); // 东 deck (站台几何, 与列车无关)

  function stepLapbar(dt) {
    const speed = dt / (lapbarTarget > session.lapbar ? LAPBAR_CLOSE_T : LAPBAR_OPEN_T);
    const d = lapbarTarget - session.lapbar;
    if (d !== 0) {
      session.lapbar = Math.abs(d) <= speed ? lapbarTarget : session.lapbar + Math.sign(d) * speed;
    }
    const rot = LAPBAR_OPEN * (1 - session.lapbar);
    for (const lb of lapBars) lb.rotation.x = rot;
    if (session.active && session.wantOff && session.lapbar <= 0.02 && !session.offFired) {
      session.offFired = true;
      onDisembarkReady?.();
    }
  }

  function startDisembark() {
    lapbarTarget = 0; // 开启 → 开完触发 onDisembarkReady (stepLapbar 内判定)
  }

  let prevHold = false;
  let chaseInit = false;
  const _chasePos = new THREE.Vector3();
  const _worldUp = new THREE.Vector3(0, 1, 0);
  const _upMix = new THREE.Vector3();
  const _view = new THREE.Vector3();
  const _povPos = new THREE.Vector3();
  const _povDummy = new THREE.Object3D();

  // 首帧摆位 (与 Blender 静态停靠一致, 无跳变)
  for (let i = 0; i < CAR_N; i++) frameAt(sHead - i * CAR_GAP, cars[i]);

  return {
    state,
    staticRoot, // M4: 闸机模块从中解析 NL_Gate_*/NL_GateArm_*
    trainRoot,
    cars,
    update(dt) {
      // M4 站台联锁释放补偿: hold 解除时若 dwell 所剩无几, 补到 4s 防瞬间弹射
      if (!state.hold && prevHold && !session.active && state.phase === "dwell" && state.dwellT < 2) {
        state.dwellT = 4;
      }
      prevHold = state.hold;
      stepLapbar(dt);
      if (state.phase === "dwell") {
        if (state.hold) {
          // 站台联锁: 冻结倒计时, 列车保持停靠
        } else if (session.active) {
          // 乘坐会话: 压肩锁闭后计发车倒计时
          if (session.lapbar >= 0.999) {
            session.dispatchT -= dt;
            if (session.dispatchT <= 0) state.phase = "run";
          }
        } else {
          state.dwellT -= dt;
          if (state.dwellT <= 1.5) lapbarTarget = 1; // 观赏循环发车前收压肩 (下客后保持开至临近发车)
          if (state.dwellT <= 0) { state.phase = "run"; state.dwellT = DWELL; }
        }
        state.v = 0;
      } else {
        const v = vAt(state.s);
        state.v = v;
        const sPrev = state.s;
        state.s = (state.s + v * dt) % L;
        if (state.phase === "run" && state.s < sPrev) {
          // 过缝合点: 不就地驻留(缝合点=站台门槛, 后5节会留在 -24° 刹车坡上)。
          // 未乘坐或已排队下车 → crawl 爬行进站; 乘坐未排队 → 连圈不停站
          state.laps++;
          state.phase = (!session.active || session.wantOff) ? "crawl" : "run";
        }
        if (state.phase === "crawl" && state.s >= sHead) {
          state.s = sHead; // 精确对位停正(车厢号停位), 过冲 ≤0.04m 瞬回无感
          state.phase = "dwell";
          state.dwellT = DWELL;
          if (session.active && session.wantOff) startDisembark();
        }
        // 轮转 (rotation.x 契约轴) — 爬行段车轮继续转
        const w = (v / WHEEL_R) * dt;
        for (const wheel of wheels) wheel.rotation.x -= w;
      }
      for (let i = 0; i < CAR_N; i++) frameAt(state.s - i * CAR_GAP, cars[i]);
    },
    // 调试/验收: 把头车 s 直接设到指定弧长 (截图取证用)
    seek(s) { state.s = ((s % L) + L) % L; state.phase = "run"; state.dwellT = DWELL; },

    // 应用设置面板（百分比 -> 实际参数）
    applySettings(s) {
      const k = clamp(s.coasterDecoLight, 0, 200) / 100;
      for (const { m, base } of decoGlowMats) m.emissiveIntensity = base * k;
    },

    // ============ M4 乘坐 API ============
    board() {
      if (session.active) return; // 幂等
      session.active = true;
      session.wantOff = false;
      session.offFired = false;
      lapbarTarget = 1; // 压肩闭合 (0.8s) → 锁闭后 dispatchT 倒计时 → 发车
      session.dispatchT = DISPATCH_T;
    },
    // 途中 E: 排队下一站下车; dwell 期直接开压肩。返回是否入队
    queueDisembark() {
      if (!session.active || session.wantOff) return false;
      session.wantOff = true;
      if (state.phase === "dwell") startDisembark(); // 刚登车就反悔: 立即开压肩
      return true;
    },
    // 再按 E 取消排队 (仅限途中, 到站停稳压肩已开则不可取消)。返回是否取消成功
    cancelDisembark() {
      if (!session.active || !session.wantOff || state.phase === "dwell") return false;
      session.wantOff = false;
      return true;
    },
    // main 在转场黑幕内调用: 清会话; 压肩保持开至观赏循环临近发车 (dwell≤1.5s 收拢)
    disembark() {
      session.active = false;
      session.wantOff = false;
      session.offFired = false;
    },
    setHold(h) { state.hold = !!h; },
    setRideCam(mode) { if (mode === "chase") chaseInit = false; }, // 切追逐: 重置阻尼起点防甩镜
    // 相机帧 (controller.updateRide 每帧调用; 未乘坐返回 null)
    //   pov: NL_CamPov 世界位姿 (车帧 × 锚点局部), 切线看向
    //   chase: 头车后方 CHASE_BACK 弧长 + CHASE_UP 高度, 位置指数阻尼; lookAt 头车,
    //          up = 0.8 世界 Y + 0.2 帧_up (过回环不倒挂, 过螺丝钻/紧回旋不整周滚转; v5.1 调权)
    getRideFrame(mode, dt) {
      if (!session.active) return null;
      if (mode === "chase") {
        const back = sampleFrame(state.s - CHASE_BACK);
        _povPos.copy(back.pos).addScaledVector(back.up, CHASE_UP);
        // v5.1: seek/跳变级位置差 (>5m, 正常帧仅 v*dt≈0.2m) 直接吸附, 防阻尼追赶半途拍到陈旧机位
        if (!chaseInit || _povPos.distanceTo(_chasePos) > 5) { _chasePos.copy(_povPos); chaseInit = true; }
        else _chasePos.lerp(_povPos, 1 - Math.exp(-6 * (dt ?? 0.016)));
        const head = sampleFrame(state.s);
        _view.copy(head.pos).sub(_chasePos).normalize();
        if (_view.y < -0.55) {
          // v5.1: 高位俯视/竖直俯冲段 —— up = 世界Y在视平面上的投影 (crane 连续滚转)。
          // 教训: 陡下视时仍用 (0.8Y+0.2帧up) 正交化会翻滚 (up·z·z.y 乘积项必然为负,
        // v5.1 首测 upCork -0.27/-0.43 即此); 投影式 up 的 y 分量 = 1-vy² ≥ 0 恒不翻
          _upMix.set(0, 1, 0).addScaledVector(_view, -_view.y).normalize();
        } else {
          _upMix.copy(head.up).multiplyScalar(0.2).addScaledVector(_worldUp, 0.8).normalize();
        }
        _m4.lookAt(_chasePos, head.pos, _upMix);
        return { pos: _chasePos, quat: new THREE.Quaternion().setFromRotationMatrix(_m4), v: state.v };
      }
      frameAt(state.s, _povDummy);
      _povPos.copy(camPov.position).applyQuaternion(_povDummy.quaternion).add(_povDummy.position);
      return { pos: _povPos.clone(), quat: _povDummy.quaternion.clone(), v: state.v };
    },
    getBoardSpot,
    getDropSpot,
    set onDisembarkReady(fn) { onDisembarkReady = fn; },
  };
}
