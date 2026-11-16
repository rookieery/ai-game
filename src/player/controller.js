// 第一人称玩家控制器：WASD 移动 / Shift 疾走 / 指针锁定视角 / 圆碰撞
// 双模式：
//   园区模式 —— 世界坐标行走，圆碰撞表（colliders.json + 站台护栏）
//   舱内模式 —— 摩天轮舱本地坐标行走，解析碰撞（外墙/长椅/中柱），
//               C 键坐/站切换；相机 = 舱世界位姿 × 本地偏移
import * as THREE from "three";

const EYE = 1.65;      // 眼高（园区）
const PR = 0.38;       // 玩家碰撞半径（园区）
const WALK = 4.0;
const SPRINT = 7.2;

// 舱内参数（舱本地坐标，与 ferris_wheel.py v2.2 内饰布局严格一致）：
//   地板 1.58×1.06（半宽 0.79 / 半深 0.53），地板顶相对舱根 -2.34
//   净高 1.62（舱内天花板 = FW_GlowCeil 发光面板，底 -0.72；外饰横梁在其上方，舱内不可见）
//   端墙长椅占 z ∈ [-0.53, -0.11]（座面 -0.11），中柱在原点 r 0.045
const CABIN = {
  FLOOR_Y: -2.34,
  EYE_STAND: 1.40,                // 站姿眼高（1.62 − 眼顶 1.418 − near 0.1 余量 ~0.10 > 0）
  EYE_SIT: 1.18,                  // 坐姿眼高（与旧坐姿相机 -1.16 一致）
  R: 0.15,                        // 舱内玩家半径
  SPEED: 2.2,                     // 舱内步速（Shift 疾走失效）
  BX: 0.62,                       // |x| 界 = 地板半宽 0.79 - R - 0.02
  BZ_LO: 0.04,                    // z 下界 = 长椅座面 -0.11 + R
  BZ_HI: 0.36,                    // z 上界 = 地板半深 0.53 - R - 0.02
  POLE_R: 0.195,                  // 中柱排斥半径 = 柱 0.045 + R
  SEATS: [                        // C 键坐点（长椅两座位）+ 起身落点
    { x: 0.31, z: -0.285, standZ: 0.10 },
    { x: -0.31, z: -0.285, standZ: 0.10 },
  ],
  SPAWN: { x: 0, z: 0.25 },       // 登舱落位（门侧，避开中柱排斥圈）
};

export function createPlayer(camera, input, park) {
  const spawn = park?.spawn ?? { x: 0, z: 60 };
  const pos = new THREE.Vector3(spawn.x, 0, spawn.z);
  let yaw = 0;          // 0 = 面向 -Z (从大门看向园区)
  let pitch = -0.04;
  let bobT = 0;

  // 碰撞圆: colliders.json + 摩天轮站台/台阶护栏 (登舱走交互, 不走台阶)
  const extra = [
    { x: 0, z: 0, r: 9.8 },
    { x: 0, z: 11.5, r: 2.7 },
    { x: 0, z: 14.2, r: 2.7 },
  ];
  const circles = [...(park?.circles ?? []), ...extra];
  const boundaryR = park?.boundaryR ?? 60;

  // ---------- 舱内模式状态 ----------
  const cabin = {
    active: false,
    getFrame: null,                  // () => { pos, quat }（ferris.getRideFrame）
    local: new THREE.Vector2(),      // 舱本地偏移 (x, z)
    vel: new THREE.Vector2(),
    seated: false,
    seat: { x: 0, z: 0 },            // 当前吸附坐点
    stand: { x: 0, z: 0 },           // 起身落点（座位前方）
    pose: 1,                         // 坐站插值：0 坐 .. 1 站
  };

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // 舱内碰撞解算：先钳外墙/长椅矩形，再推离中柱圆
  // （local 是 Vector2：.x / .y 即舱本地 x / z）
  function resolveCabin(p) {
    p.x = clamp(p.x, -CABIN.BX, CABIN.BX);
    p.y = clamp(p.y, CABIN.BZ_LO, CABIN.BZ_HI);
    const d = Math.hypot(p.x, p.y);
    if (d < CABIN.POLE_R && d > 1e-4) {
      p.x *= CABIN.POLE_R / d;
      p.y *= CABIN.POLE_R / d;
    }
  }

  // 位移积分（步长 >0.08m 自动细分，防极端 dt 下一步跨过中柱/长椅）
  function stepCabin(dx, dz) {
    const dist = Math.hypot(dx, dz);
    const n = Math.max(1, Math.ceil(dist / 0.08));
    for (let i = 0; i < n; i++) {
      cabin.local.x += dx / n;
      cabin.local.y += dz / n;
      resolveCabin(cabin.local);
    }
  }

  const _dir = new THREE.Vector3();
  const _off = new THREE.Vector3();
  const _qi = new THREE.Quaternion();

  function updateCabin(dt) {
    const fr = cabin.getFrame ? cabin.getFrame() : null;
    if (!fr) return;

    const f = (input.isDown("KeyW") ? 1 : 0) - (input.isDown("KeyS") ? 1 : 0);
    const s = (input.isDown("KeyD") ? 1 : 0) - (input.isDown("KeyA") ? 1 : 0);
    if (cabin.seated && (f || s)) cabin.seated = false; // 移动键直接起身

    // 坐/站过渡插值
    const poseT = cabin.seated ? 0 : 1;
    cabin.pose += (poseT - cabin.pose) * Math.min(1, dt * 6);
    if (Math.abs(poseT - cabin.pose) < 1e-3) cabin.pose = poseT;

    if (cabin.seated || cabin.pose < 0.95) {
      // 坐下吸附 / 起身滑向座位前落点（过渡期不接受移动输入）
      const tx = cabin.seated ? cabin.seat.x : cabin.stand.x;
      const tz = cabin.seated ? cabin.seat.z : cabin.stand.z;
      const k = Math.min(1, dt * 8);
      cabin.local.x += (tx - cabin.local.x) * k;
      cabin.local.y += (tz - cabin.local.y) * k;
      cabin.vel.set(0, 0);
      bobT += dt * 1.2;
    } else if (f || s) {
      // 行走：期望方向取自视线 yaw（世界系），转舱本地系后积分
      const len = Math.hypot(f, s);
      const fx = -Math.sin(yaw), fz = -Math.cos(yaw);   // 前
      const rx = Math.cos(yaw), rz = -Math.sin(yaw);    // 右
      _dir.set((fx * f + rx * s) / len, 0, (fz * f + rz * s) / len);
      _qi.copy(fr.quat).invert();
      _dir.applyQuaternion(_qi);
      cabin.vel.x += (_dir.x * CABIN.SPEED - cabin.vel.x) * Math.min(1, dt * 12);
      cabin.vel.y += (_dir.z * CABIN.SPEED - cabin.vel.y) * Math.min(1, dt * 12);
      stepCabin(cabin.vel.x * dt, cabin.vel.y * dt);
      bobT += dt * 8;
    } else {
      cabin.vel.multiplyScalar(Math.max(0, 1 - dt * 12));
      stepCabin(cabin.vel.x * dt, cabin.vel.y * dt);
      bobT += dt * 1.8;
    }

    // 眼高：坐 1.18 .. 站 1.40；站定行走叠加轻微 head bob
    const bob = cabin.pose > 0.95 ? Math.sin(bobT) * 0.018 : 0;
    const eye = CABIN.EYE_SIT + (CABIN.EYE_STAND - CABIN.EYE_SIT) * cabin.pose + bob;
    _off.set(cabin.local.x, CABIN.FLOOR_Y + eye, cabin.local.y)
      .applyQuaternion(fr.quat);
    camera.position.copy(fr.pos).add(_off);
  }

  // C 键：坐下 / 起身（仅舱内模式生效）
  input.onPress("KeyC", () => {
    if (!cabin.active) return;
    if (cabin.seated) {
      cabin.seated = false;
      return;
    }
    let best = 0;
    let bd = Infinity;
    CABIN.SEATS.forEach((sp, i) => {
      const d = Math.abs(cabin.local.x - sp.x);
      if (d < bd) { bd = d; best = i; }
    });
    const sp = CABIN.SEATS[best];
    cabin.seat = { x: sp.x, z: sp.z };
    cabin.stand = { x: sp.x, z: sp.standZ };
    cabin.seated = true;
    cabin.vel.set(0, 0);
  });

  function updateWorld(dt) {
    const f = (input.isDown("KeyW") ? 1 : 0) - (input.isDown("KeyS") ? 1 : 0);
    const s = (input.isDown("KeyD") ? 1 : 0) - (input.isDown("KeyA") ? 1 : 0);
    const sprint = input.isDown("ShiftLeft") || input.isDown("ShiftRight");
    if (f || s) {
      const len = Math.hypot(f, s);
      const sp = sprint ? SPRINT : WALK;
      const fx = -Math.sin(yaw), fz = -Math.cos(yaw);   // 前
      const rx = Math.cos(yaw), rz = -Math.sin(yaw);    // 右
      tryMove(
        pos.x + ((fx * f + rx * s) / len) * sp * dt,
        pos.z + ((fz * f + rz * s) / len) * sp * dt
      );
      bobT += dt * (sprint ? 11 : 8);
    } else {
      bobT += dt * 1.8;
    }
    camera.position.set(pos.x, EYE + Math.sin(bobT) * 0.035, pos.z);
  }

  function tryMove(nx, nz) {
    for (let it = 0; it < 2; it++) {
      for (const c of circles) {
        const dx = nx - c.x;
        const dz = nz - c.z;
        const d = Math.hypot(dx, dz);
        const min = c.r + PR;
        if (d < min && d > 1e-4) {
          nx = c.x + (dx / d) * min;
          nz = c.z + (dz / d) * min;
        }
      }
      const d0 = Math.hypot(nx, nz);
      const maxD = boundaryR - PR;
      if (d0 > maxD) {
        nx *= maxD / d0;
        nz *= maxD / d0;
      }
    }
    pos.x = nx;
    pos.z = nz;
  }

  return {
    pos,
    enterCabin(getFrame) {
      cabin.active = true;
      cabin.getFrame = getFrame;
      cabin.local.set(CABIN.SPAWN.x, CABIN.SPAWN.z);
      cabin.vel.set(0, 0);
      cabin.seated = false;
      cabin.pose = 1;
    },
    exitCabin() {
      cabin.active = false;
      cabin.getFrame = null;
      cabin.seated = false;
    },
    // 调试/测试钩子：舱本地坐标与坐站态（非舱内模式返回 null）
    cabinLocal() {
      return cabin.active
        ? { x: cabin.local.x, z: cabin.local.y, seated: cabin.seated }
        : null;
    },
    teleport(x, z) {
      pos.x = x;
      pos.z = z;
    },
    setView(y, p) {
      yaw = y;
      pitch = Math.max(-1.25, Math.min(1.25, p));
    },
    update(dt) {
      const m = input.consumeMouse();
      if (input.locked) {
        yaw -= m.dx * 0.0022;
        pitch = Math.max(-1.25, Math.min(1.25, pitch - m.dy * 0.0022));
      }
      if (cabin.active) updateCabin(dt);
      else updateWorld(dt);
      camera.rotation.order = "YXZ";
      camera.rotation.set(pitch, yaw, 0);
    },
  };
}
