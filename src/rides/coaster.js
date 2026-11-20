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

  // 弧长 s 处采样 (线性插值 + 重正交)
  function frameAt(s, car) {
    const f = ((s % L) + L) % L / DS;
    const i0 = Math.min(N - 2, Math.floor(f));
    const u = f - i0;
    const i1 = i0 + 1;
    _pos.set(
      P[i0 * 3] + (P[i1 * 3] - P[i0 * 3]) * u,
      P[i0 * 3 + 1] + (P[i1 * 3 + 1] - P[i0 * 3 + 1]) * u,
      P[i0 * 3 + 2] + (P[i1 * 3 + 2] - P[i0 * 3 + 2]) * u,
    );
    _tan.set(
      T[i0 * 3] + (T[i1 * 3] - T[i0 * 3]) * u,
      T[i0 * 3 + 1] + (T[i1 * 3 + 1] - T[i0 * 3 + 1]) * u,
      T[i0 * 3 + 2] + (T[i1 * 3 + 2] - T[i0 * 3 + 2]) * u,
    ).normalize();
    _up.set(
      U[i0 * 3] + (U[i1 * 3] - U[i0 * 3]) * u,
      U[i0 * 3 + 1] + (U[i1 * 3 + 1] - U[i0 * 3 + 1]) * u,
      U[i0 * 3 + 2] + (U[i1 * 3 + 2] - U[i0 * 3 + 2]) * u,
    );
    _up.addScaledVector(_tan, -_up.dot(_tan)).normalize();
    _rv.crossVectors(_tan, _up); // 车局部 +X (右)
    // glb 车局部轴契约 (scripts/dump_train_glb.mjs 实测): X=右, Y=上, Z=-前。
    // (Blender 车局部 (x=右,y=前,z=上) 经 glTF +Y-up 导出换算 (x,z,-y) 后即此约定;
    //  若沿用旧基 makeBasis(rv,tan,up) 会把车长轴掰到轨道竖向 -> 列车倒立)
    _negTan.copy(_tan).negate();
    _m4.makeBasis(
      new THREE.Vector3(_rv.x, _rv.y, _rv.z),
      new THREE.Vector3(_up.x, _up.y, _up.z),
      new THREE.Vector3(_negTan.x, _negTan.y, _negTan.z),
    );
    car.position.copy(_pos);
    car.quaternion.setFromRotationMatrix(_m4);
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
  trainRoot.traverse((o) => {
    const m = o.name && o.name.match(/^NL_Car_(\d)$/);
    if (m) cars[+m[1]] = o;
    else if (o.name && o.name.startsWith("NL_Wheel_")) wheels.push(o);
  });
  if (cars.filter(Boolean).length !== CAR_N) console.warn("[coaster] NL_Car_i 不全:", cars.length);
  if (wheels.length !== 24) console.warn("[coaster] 轮组数:", wheels.length);

  // 手写管件(肩环/灯笼/钩臂)面序不保证一致, Blender 双面渲染无感, three.js 单面会成黑洞 -> 全双面保险
  trainRoot.traverse((o) => {
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) m.side = THREE.DoubleSide;
  });

  const state = {
    phase: "dwell", // dwell | run | crawl(过缝合点后站台爬行, 到停车位再驻留)
    s: sHead,
    v: 0,
    dwellT: DWELL,
    laps: 0,
  };

  // 首帧摆位 (与 Blender 静态停靠一致, 无跳变)
  for (let i = 0; i < CAR_N; i++) frameAt(sHead - i * CAR_GAP, cars[i]);

  return {
    state,
    trainRoot,
    cars,
    update(dt) {
      if (state.phase === "dwell") {
        state.dwellT -= dt;
        state.v = 0;
        if (state.dwellT <= 0) { state.phase = "run"; state.dwellT = DWELL; }
      } else {
        const v = vAt(state.s);
        state.v = v;
        const sPrev = state.s;
        state.s = (state.s + v * dt) % L;
        if (state.phase === "run" && state.s < sPrev) {
          // 过缝合点: 不就地驻留(缝合点=站台门槛, 后5节会留在 -24° 刹车坡上),
          // 转 crawl 以 v 表站台爬行速度滑行到停车位 sHead 再驻留
          state.laps++;
          state.phase = "crawl";
        }
        if (state.phase === "crawl" && state.s >= sHead) {
          state.s = sHead; // 精确对位停正(车厢号停位), 过冲 ≤0.04m 瞬回无感
          state.phase = "dwell";
          state.dwellT = DWELL;
        }
        // 轮转 (rotation.x 契约轴) — 爬行段车轮继续转
        const w = (v / WHEEL_R) * dt;
        for (const wheel of wheels) wheel.rotation.x -= w;
      }
      for (let i = 0; i < CAR_N; i++) frameAt(state.s - i * CAR_GAP, cars[i]);
    },
    // 调试/验收: 把头车 s 直接设到指定弧长 (截图取证用)
    seek(s) { state.s = ((s % L) + L) % L; state.phase = "run"; state.dwellT = DWELL; },
  };
}
