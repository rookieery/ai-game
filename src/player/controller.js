// 第一人称玩家控制器：WASD 移动 / Shift 疾走 / 空格跳跃 / 指针锁定视角 / 圆碰撞
// 双模式：
//   园区模式 —— 世界坐标行走，2.5D 解析垂直运动（无物理引擎）：
//               圆碰撞表（colliders.json + 站台护栏）+ 顶面平台（圆 h / 台阶矩形），
//               台阶 ≤0.30 直接迈上，更高的顶面（长椅/干草/木桶/站台…）空格跳上
//               + 眺望塔叠层地面（colliders_tower.json floors：螺旋梯/环廊/栈桥/轿厢，
//               只取「<= 脚底+步高」的最高块为支撑，xz 重叠的上下几圈互不干扰）
//   舱内模式 —— 摩天轮舱本地坐标行走，解析碰撞（外墙/长椅），
//               C 键坐/站切换；相机 = 舱世界位姿 × 本地偏移（舱内禁跳）
import * as THREE from "three";

export const EYE = 1.65; // 眼高（园区; fx/fw_director.js 算塔顶观景眼位要用）
const PR = 0.38;       // 玩家碰撞半径（园区）
const WALK_BASE = 4.0;   // 默认步速（米/秒, 设置面板「步行速度」可调 2-16）
const SPRINT_RATIO = 1.8; // 疾走 = 步速 ×1.8（保持原 4.0/7.2 比例）

// 垂直运动（园区跳跃/台阶）：平台顶面支撑 + 解析式重力积分
const GRAV = 20;       // 重力加速度
const JUMP_V = 6.9;    // 起跳速度（跳高 ≈ JUMP_V²/2G ≈ 1.19m, 覆盖木桶顶 0.955）
const STEP = 0.35;     // 一脚可直接迈上的高度差（登舱台阶每级 0.194; M4: 0.30→0.35 兑现过山车
                       // 0.34 级台阶「可迈上」契约——colliders note 明文 0.34 可迈, 旧值实测迈不上)
const COYOTE = 0.1;    // 土狼时间：离地后仍可起跳的窗口
const BUFFER = 0.15;   // 跳跃预输入缓冲
const GRACE = 0.05;    // 顶面支撑判定的边缘容差

// 舱内参数（舱本地坐标，与 ferris_wheel.py v3 舱体布局严格一致；2026-11-27 舱体重做）：
//   地板 2.10×1.70（半宽 1.05 / 半深 0.85），地板顶相对舱根 -2.70，净高 2.00（天花底 -0.70）
//   长椅侧（-z）端墙长椅占 z ∈ [-0.86, -0.42]（座面顶 -0.42，绒面坐垫高 0.54，靠背到 -0.87）
//   v3 舱内没有中柱；登舱门在 +z 端
export const CABIN = {
  FLOOR_Y: -2.70,
  EYE_STAND: EYE,                 // 站姿眼高 = 园区眼高 1.65（v2 进舱缩到 1.40；净高 2.00 余量 0.25）
  EYE_SIT: 1.20,                  // 坐姿眼高
  R: 0.15,                        // 舱内玩家半径
  SPEED: 2.2,                     // 舱内步速（Shift 疾走失效）
  BX: 0.88,                       // |x| 界 = 地板半宽 1.05 - R - 0.02
  BZ_LO: -0.27,                   // z 下界 = 长椅座面前沿 -0.42 + R
  BZ_HI: 0.68,                    // z 上界 = 地板半深 0.85 - R - 0.02
  SEATS: [                        // C 键坐点（长椅三座位）+ 起身落点
    { x: 0.62, z: -0.64, standZ: -0.20 },
    { x: 0, z: -0.64, standZ: -0.20 },
    { x: -0.62, z: -0.64, standZ: -0.20 },
  ],
  SPAWN: { x: 0, z: 0.35 },       // 登舱落位（门侧）
};

export function createPlayer(camera, input, park) {
  const spawn = park?.spawn ?? { x: 0, z: 60 };
  const pos = new THREE.Vector3(spawn.x, 0, spawn.z);
  let yaw = 0;          // 0 = 面向 -Z (从大门看向园区)
  let pitch = -0.04;
  let bobT = 0;

  // 垂直状态（园区模式）：pos.y = 脚部离地高度
  let vy = 0;            // 垂直速度
  let grounded = true;   // 是否贴地
  let coyoteT = 0;       // 土狼时间剩余
  let jumpBufT = 0;      // 跳跃缓冲剩余
  let landDip = 0;       // 落地相机下沉

  // 碰撞圆: colliders.json（含可站顶面 h 的圆：长椅/干草/木桶/旋转木马平台）
  // + 摩天轮登舱站台（顶面可站）/排队围栏/售票亭/矮柱灯
  // 圆无 h = 无限高阻挡（树/灯/柱/南瓜…）；有 h = 顶面可站立（详见 park_env.py collider()）
  const booth = { x: 7.6, z: 8.2, r: 1.25 };
  const queueRails = [-2.7, 2.7].flatMap((lx) =>
    [11.0, 12.6, 14.2].map((z) => ({ x: lx, z, r: 0.55 }))
  );
  const bollards = [];
  for (let i = 0; i < 12; i++) {
    if (i === 9) continue; // 南向走廊让位登舱台阶 (管线侧同步跳过, 台阶口两侧另补)
    const th = (i * Math.PI) / 6;
    bollards.push({ x: 10.4 * Math.cos(th), z: -10.4 * Math.sin(th), r: 0.35 });
  }
  bollards.push({ x: 2.69, z: 10.05, r: 0.35 }, { x: -2.69, z: 10.05, r: 0.35 });
  const extra = [
    // 登舱站台 (ferris_wheel.py: platform_r 9.0 / platform_h 1.55)：
    // 侧壁 = 圆推挤（地面走近被挡, 1.55 超出跳高, 只能走台阶），顶面 = 可站立平台
    { x: 0, z: 0, r: 9.0, h: 1.55 },
    booth,
    ...queueRails,
    ...bollards,
  ];
  // 站台家具阻挡小圆: 雨棚角柱 x4 (ferris_wheel.py:334-341) + A 字支腿 x4 (:376-387)
  for (const sx of [1, -1]) {
    for (const sy of [1, -1]) {
      extra.push(
        { x: sx * 6.222, z: sy * 6.222, r: 0.14 },
        { x: sx * 6.2, z: sy * 3.0, r: 0.30 },
      );
    }
  }
  const circles = [...(park?.circles ?? []), ...extra];
  const boundaryR = park?.boundaryR ?? 60;

  // 矩形碰撞体两类：
  //   solid（墙）—— colliders.json rects（市集亭体等精确盒墙, 无 h, 各高度推挤）
  //   平台（顶面）—— 登舱台阶 8 级 (ferris_wheel.py:313-317: 每级 4.4×0.9×0.194,
  //     blender -y 侧 → app +z；第 k 级 z = 9.45 + k*0.9, 顶 = 1.55-(k+1)*0.194),
  //     不推挤, 只做「顶面支撑 + 超高阻挡」（canStand 分轴挡向）
  const stallRects = (park?.rects ?? []).map((r) => ({ ...r, solid: true }));
  const stepRects = [];
  for (let k = 0; k < 8; k++) {
    stepRects.push({ x: 0, z: 9.45 + k * 0.9, hw: 2.2, hd: 0.45, h: 1.55 - (k + 1) * 0.194 });
  }
  // 过山车台阶顶面 (M3: colliders_coaster.json steps — 站台双 deck / 双槽 7 级)
  for (const s of park?.steps ?? []) stepRects.push(s);
  const rects = [...stallRects, ...stepRects];

  // 眺望塔叠层地面（M5: colliders_tower.json floors —— 螺旋梯 / 环廊 / 栈桥 / 轿厢地面）
  // 与上面的「最高顶面获胜」不同：落点处只取「<= 脚底 + 步高」的最高一块为支撑；
  // 高出不足一人高的地面当墙（挡向），更高的可以从下方走过。
  // 螺旋梯上下几圈在 xz 上重叠，旧语义会把上一圈当成墙，所以塔必须走这套。
  //   形状: helix（逐级踏面高 h[k]）/ sector（扇环）/ rect / circle
  //   sticky: 轿厢地面 —— 脚底贴着它就跟随升降，永不当墙
  // 离线参考实现见 scripts/lib_tower_sim.mjs，两处语义须一致
  const floors = [...(park?.floors ?? [])];
  const CLEAR = 1.8;      // 头顶净空：地面高出脚底 (STEP, CLEAR] 即为墙
  const STICKY = 0.6;     // sticky 地面的跟随带

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

  // ---------- 骑乘模式（固定座位, 显灵木马）----------
  // 相机 = 骑乘位世界帧 × (0, eye, 0)，随盘旋转/起伏；WASD 不移动，仅自由环视。
  const mount = {
    active: false,
    getFrame: null,                  // () => { pos, quat, eye }
  };

  // ---------- 乘坐模式（过山车 M4）----------
  // 相机姿态相对车体 (四元数组合): camera.quaternion = fr.quat × 偏移欧拉,
  // 鼠标只改相对偏移 —— 过回环倒挂时世界系 Euler 会翻轴, 必须走四元数。
  // 视线自由环视 (偏移不自动回中, 用户拍板 2026-11-20); R 键强阻尼平滑回正 (resetting)。
  // 体感: 震动振幅 ∝ feel × (v/vmax)², FOV 拉伸 60+16°×feel%×(v/vmax)^1.5 (feel=0 全关)。
  const ride = {
    active: false,
    getFrame: null,        // (dt) => { pos, quat, v } | null (coaster.getRideFrame)
    yawOff: 0, pitchOff: 0,
    resetting: false,      // R 回正动画中 (鼠标一动即取消, 玩家接管)
    feel: 60,
    shakeT: 0,
  };
  const RIDE_VMAX = 21;    // 体感归一 (centerline vmax≈20.96)

  function updateRide(dt) {
    const fr = ride.getFrame ? ride.getFrame(dt) : null;
    if (!fr) return;
    ride.shakeT += dt * (1 + fr.v * 0.35);
    const k = (ride.feel / 100) * Math.pow(Math.min(1, fr.v / RIDE_VMAX), 2);
    const sx = (Math.sin(ride.shakeT * 31.7) + 0.6 * Math.sin(ride.shakeT * 47.3)) * 0.010 * k;
    const sy = (Math.sin(ride.shakeT * 38.1) + 0.6 * Math.sin(ride.shakeT * 52.9)) * 0.008 * k;
    _off.set(sx, sy, 0).applyQuaternion(fr.quat);
    camera.position.copy(fr.pos).add(_off);
    _qi.setFromEuler(_dirE.set(ride.pitchOff, ride.yawOff, 0, "YXZ"));
    camera.quaternion.copy(fr.quat).multiply(_qi);
    // R 回正: 强阻尼 (≈0.25s 归位, 不瞬切不晕); 鼠标一动即取消 (update 分派里置 false)
    if (ride.resetting) {
      const rk = Math.exp(-dt * 12);
      ride.yawOff *= rk;
      ride.pitchOff *= rk;
      if (Math.abs(ride.yawOff) < 0.005 && Math.abs(ride.pitchOff) < 0.005) {
        ride.yawOff = 0;
        ride.pitchOff = 0;
        ride.resetting = false;
      }
    }
    // 速度 FOV 拉伸 (阻尼趋近)
    const fovT = 60 + (ride.feel / 100) * 16 * Math.pow(Math.min(1, fr.v / RIDE_VMAX), 1.5);
    camera.fov += (fovT - camera.fov) * Math.min(1, dt * 6);
    camera.updateProjectionMatrix();
  }
  const _dirE = new THREE.Euler();

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // 舱内碰撞解算：钳外墙 / 长椅矩形（v3 舱内没有中柱，不需要圆排斥）
  // （local 是 Vector2：.x / .y 即舱本地 x / z）
  function resolveCabin(p) {
    p.x = clamp(p.x, -CABIN.BX, CABIN.BX);
    p.y = clamp(p.y, CABIN.BZ_LO, CABIN.BZ_HI);
  }

  // 位移积分（步长 >0.08m 自动细分，防极端 dt 下一步跨过长椅前沿）
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

  // 骑乘模式相机：固定坐点随骑乘位帧（旋转 + 起伏），叠加轻微呼吸浮动
  const _mf = new THREE.Vector3();
  function updateMount(dt) {
    const fr = mount.getFrame ? mount.getFrame() : null;
    if (!fr) return;
    bobT += dt * 1.8;
    _mf.set(0, fr.eye + Math.sin(bobT) * 0.012, 0).applyQuaternion(fr.quat);
    camera.position.copy(fr.pos).add(_mf);
  }

  // 园区步速（设置面板可调; 疾走按固定比例放大）
  let walkSpeed = WALK_BASE;
  let sprintSpeed = WALK_BASE * SPRINT_RATIO;

  function updateWorld(dt) {
    const f = (input.isDown("KeyW") ? 1 : 0) - (input.isDown("KeyS") ? 1 : 0);
    const s = (input.isDown("KeyD") ? 1 : 0) - (input.isDown("KeyA") ? 1 : 0);
    const sprint = input.isDown("ShiftLeft") || input.isDown("ShiftRight");
    const moving = !!(f || s);
    let dx = 0;
    let dz = 0;
    if (moving) {
      const len = Math.hypot(f, s);
      const sp = sprint ? sprintSpeed : walkSpeed;
      const fx = -Math.sin(yaw), fz = -Math.cos(yaw);   // 前
      const rx = Math.cos(yaw), rz = -Math.sin(yaw);    // 右
      dx = ((fx * f + rx * s) / len) * sp;
      dz = ((fz * f + rz * s) / len) * sp;
      // 摆头频率随实际步速等比缩放（默认 4 米/秒时 = 原 8/11 节奏）
      bobT += dt * (sprint ? 11 : 8) * (sp / WALK_BASE);
    } else {
      bobT += dt * 1.8;
    }

    // 水平 + 垂直积分：
    //   贴地 —— 整步水平位移 + 台阶吸附（地面步长远小于场内最小平台面, 无隧穿）
    //   空中 —— ≤16ms 子步交替推进水平/垂直, 防低帧率大 dt 一步跨过木桶等小平台顶
    //   （走出台缘的那一帧, 空中子步会追加本帧位移, 一帧 ~2x 的瞬态, 不可感知）
    jumpBufT = Math.max(0, jumpBufT - dt);
    if (grounded) {
      if (moving) tryMove(pos.x + dx * dt, pos.z + dz * dt);
      coyoteT = COYOTE;
      const g = supportAt(pos.x, pos.z, pos.y, pos.y + STEP);
      if (g < pos.y - STEP && !onSticky(pos.x, pos.z, pos.y)) {
        grounded = false;  // 走出台缘：不瞬移贴地, 转入下落（轿厢下行除外：贴着轿厢地面就跟着走）
        vy = 0;
      } else {
        pos.y = g;         // 台阶吸附（≤一步上吸 / 下行顺台阶走下）
      }
    }
    if (!grounded) {
      coyoteT = Math.max(0, coyoteT - dt);
      const n = Math.max(1, Math.ceil(dt / 0.016));
      const h = dt / n;
      for (let i = 0; i < n; i++) {
        if (moving) tryMove(pos.x + dx * h, pos.z + dz * h);
        vy -= GRAV * h;
        pos.y += vy * h;
        const g = supportAt(pos.x, pos.z, pos.y, pos.y + 0.01); // 腾空：只认不高于脚底的叠层地面
        if (pos.y <= g) {
          pos.y = g;
          landDip = Math.min(0.16, Math.max(0.04, -vy * 0.022)); // 落地下沉 ∝ 坠速
          vy = 0;
          grounded = true;
          break;
        }
      }
    }
    // 起跳：贴地或土狼时间内, 且有未消费的按键缓冲
    if (jumpBufT > 0 && (grounded || coyoteT > 0)) {
      vy = JUMP_V;
      grounded = false;
      coyoteT = 0;
      jumpBufT = 0;
    }

    pushOut(); // 动态圆每帧推挤（静止也被旋转骑乘位推开）

    landDip *= Math.exp(-dt * 7);
    camera.position.set(pos.x, EYE + pos.y + Math.sin(bobT) * 0.035 - landDip, pos.z);
  }

  // 空格：跳跃（仅园区模式；舱内净高 1.62 禁跳；设施可经 setJumpLock 就地禁跳，如塔的轿厢）
  let jumpLock = false;
  input.onPress("Space", () => {
    if (cabin.active || jumpLock) return;
    jumpBufT = BUFFER;
  });

  // ---------- 园区垂直运动：平台支撑 / 台阶吸附 / 跳跃 ----------
  // groundAt: 覆盖 (x,z) 的平台（带 h 的圆或台阶矩形）的最高顶面；无平台处为 0
  function groundAt(x, z) {
    let g = 0;
    for (const c of circles) {
      if (c.h === undefined) continue;
      const dx = x - c.x;
      const dz = z - c.z;
      const rr = c.r + GRACE;
      if (dx * dx + dz * dz <= rr * rr && c.h > g) g = c.h;
    }
    for (const rc of rects) {
      if (
        Math.abs(x - rc.x) <= rc.hw + GRACE &&
        Math.abs(z - rc.z) <= rc.hd + GRACE &&
        rc.h > g
      ) g = rc.h;
    }
    return g;
  }

  // 叠层地面 f 在落点 (x,z) 的全部高度候选（螺旋梯一圈一块，共几圈就几个；其余形状 0 或 1 个）
  const _hs = [];
  function pushFloorHeights(f, x, z, out) {
    if (f.shape === "helix") {
      const dx = x - f.x, dz = z - f.z;
      const r = Math.hypot(dx, dz);
      if (r < f.r0 - GRACE || r > f.r1 + GRACE) return;
      const da = f.da * f.dir;                      // 每级方位增量（带符号，弧度）
      const per = (Math.PI * 2) / Math.abs(da);     // 每圈级数
      let u = (Math.atan2(dz, dx) - f.a0) / da;     // 自梯口走过的级数（可为负）
      u = ((((u / per) + 1e-9) % 1) + 1) % 1 * per; // 折到本圈 [0, per)
      for (let n = 0; u + n * per < f.n; n++) {
        const k = Math.floor(u + n * per);
        if (k < 0 || k >= f.n) break;
        out.push(f.h ? f.h[k] : f.rise * (k + 1));
      }
    } else if (f.shape === "sector") {
      const dx = x - f.x, dz = z - f.z;
      const r = Math.hypot(dx, dz);
      if (r < f.r0 - GRACE || r > f.r1 + GRACE) return;
      if (f.a1 - f.a0 < Math.PI * 2 - 1e-9) {
        const a = ((Math.atan2(dz, dx) % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
        const a0 = ((f.a0 % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
        const a1 = a0 + (f.a1 - f.a0);
        if (!(a >= a0 - 1e-9 && a <= a1 + 1e-9) && !(a + Math.PI * 2 >= a0 - 1e-9 && a + Math.PI * 2 <= a1 + 1e-9)) return;
      }
      out.push(f.h);
    } else if (f.shape === "rect") {
      if (Math.abs(x - f.x) <= f.hw + GRACE && Math.abs(z - f.z) <= f.hd + GRACE) out.push(f.h);
    } else if (f.shape === "circle") {
      if (Math.hypot(x - f.x, z - f.z) <= f.r + GRACE) out.push(f.h);
    }
  }

  // 塔叠层地面判定：{ g: 支撑高度, wall: 是否撞上「高出脚底一步、又不足一人高」的地面 }
  //   limit = 支撑上限（贴地 = 脚底 + STEP；腾空 = 脚底 + 0.01）
  function towerGround(x, z, feet, limit) {
    let g = 0;
    let wall = false;
    for (const f of floors) {
      _hs.length = 0;
      pushFloorHeights(f, x, z, _hs);
      for (const h of _hs) {
        if (h <= limit || (f.sticky && Math.abs(feet - h) <= STICKY)) {
          if (h > g) g = h;
        } else if (!f.sticky && h <= feet + CLEAR) {
          wall = true;   // 迈不上去、又钻不过去 → 挡住
        }
      }
    }
    return wall ? -1 : g;   // -1 = 墙
  }

  // 脚底是否贴着某块 sticky 地面（升降梯轿厢地面）。低帧率下一帧可降 0.45m（> STEP），
  // 不判这一条就会每帧「走出台缘 → 下落 → 落回轿厢」地抖
  function onSticky(x, z, feet) {
    for (const f of floors) {
      if (!f.sticky) continue;
      _hs.length = 0;
      pushFloorHeights(f, x, z, _hs);
      for (const h of _hs) if (Math.abs(feet - h) <= STICKY) return true;
    }
    return false;
  }

  // 综合支撑面：旧平台（最高顶面）与塔叠层地面取高
  function supportAt(x, z, feet, limit) {
    const t = towerGround(x, z, feet, limit);
    const g = groundAt(x, z);
    return t > g ? t : g;   // t = -1（墙）时取旧平台的值，由 canStand 另行挡向
  }

  // 目标点是否可站：平台顶面不得高出「脚部 + 一步」（贴地）；
  // 空中改为不高于脚部（防低空侧穿平台壁，从上方越过不受限）；塔叠层地面不得构成墙
  function canStand(x, z) {
    const limit = pos.y + (grounded ? STEP : 0.01);
    return groundAt(x, z) <= limit && towerGround(x, z, pos.y, limit) >= 0;
  }

  // 静止推挤：动态圆（旋转设施的骑乘位/铜杆）经过静止玩家时也要推开,
  // 否则障碍直接穿身。复用 tryMove 的圆推挤 + 边界钳制, 不含台阶/矩形逻辑。
  function pushOut() {
    let nx = pos.x;
    let nz = pos.z;
    for (let it = 0; it < 2; it++) {
      for (const c of circles) {
        if (c.h !== undefined && pos.y >= c.h - STEP) continue;
        if (c.y0 !== undefined && (pos.y < c.y0 || pos.y > c.y1)) continue;
        const dx = nx - c.x;
        const dz = nz - c.z;
        const d = Math.hypot(dx, dz);
        const min = c.r + PR;
        if (d < min && d > 1e-4) {
          nx = c.x + (dx / d) * min;
          nz = c.z + (dz / d) * min;
        }
      }
    }
    const d0 = Math.hypot(nx, nz);
    const maxD = boundaryR - PR;
    if (d0 > maxD) {
      nx *= maxD / d0;
      nz *= maxD / d0;
    }
    pos.x = nx;
    pos.z = nz;
  }

  function tryMove(nx, nz) {
    // 分轴尝试实现贴墙滑动：目标方向被平台顶面挡住时退回该轴分量
    const okXZ = canStand(nx, nz);
    const okX = okXZ || canStand(nx, pos.z);
    const okZ = okXZ || canStand(pos.x, nz);
    if (!okX) nx = pos.x;
    if (!okZ) nz = pos.z;
    if (!okX && !okZ) return;
    for (let it = 0; it < 2; it++) {
      for (const c of circles) {
        // 顶面在脚部一步范围内或以下的圆不再推挤 —— 可直接迈上/跳上它的顶
        if (c.h !== undefined && pos.y >= c.h - STEP) continue;
        if (c.y0 !== undefined && (pos.y < c.y0 || pos.y > c.y1)) continue; // 高度带外（塔栏杆立柱/笼柱/轿壁）
        const dx = nx - c.x;
        const dz = nz - c.z;
        const d = Math.hypot(dx, dz);
        const min = c.r + PR;
        if (d < min && d > 1e-4) {
          nx = c.x + (dx / d) * min;
          nz = c.z + (dz / d) * min;
        }
      }
      for (const rc of rects) {
        if (!rc.solid || rc.disabled) continue; // 台阶平台不推挤（可走上）; M4 闸线开闸时禁用
        if (rc.blockFrom === "z+" && nz >= pos.z) continue; // M4 单向墙按移动方向放行: +z 南下(含横向)畅通, 仅挡 -z 北上逆爬
        const qx = clamp(nx, rc.x - rc.hw, rc.x + rc.hw);
        const qz = clamp(nz, rc.z - rc.hd, rc.z + rc.hd);
        const ddx = nx - qx;
        const ddz = nz - qz;
        const dd = Math.hypot(ddx, ddz);
        if (dd < PR) {
          if (dd > 1e-4) {
            nx = qx + (ddx / dd) * PR;
            nz = qz + (ddz / dd) * PR;
          } else {
            // 点在盒内: 沿最薄方向推出
            const ox = rc.hw - Math.abs(nx - rc.x);
            const oz = rc.hd - Math.abs(nz - rc.z);
            if (ox < oz) nx = rc.x + (nx >= rc.x ? 1 : -1) * (rc.hw + PR);
            else nz = rc.z + (nz >= rc.z ? 1 : -1) * (rc.hd + PR);
          }
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
      // 回到园区模式：垂直状态归零（登舱前可能站在站台上）
      pos.y = 0;
      vy = 0;
      grounded = true;
      landDip = 0;
    },
    // 固定座位骑乘（显灵木马）：getFrame() => { pos, quat, eye }
    enterMount(getFrame) {
      mount.active = true;
      mount.getFrame = getFrame;
    },
    exitMount() {
      mount.active = false;
      mount.getFrame = null;
      // 回到园区模式：垂直状态归零（下马落点由 main 侧 teleport 给出）
      pos.y = 0;
      vy = 0;
      grounded = true;
      landDip = 0;
    },
    // M4 乘坐（过山车）: 相机姿态相对车体, 偏移由鼠标驱动
    enterRide(getFrame) {
      ride.active = true;
      ride.getFrame = getFrame;
      ride.yawOff = 0;
      ride.pitchOff = 0;
      ride.resetting = false;
      ride.shakeT = 0;
    },
    exitRide() {
      ride.active = false;
      ride.getFrame = null;
      camera.fov = 60;               // 防 FOV 泄漏
      camera.updateProjectionMatrix();
    },
    // R 键/切机位回正: 强阻尼平滑归位 (updateRide 内动画, 鼠标一动即取消)
    resetRideView() {
      if (Math.abs(ride.yawOff) < 0.005 && Math.abs(ride.pitchOff) < 0.005) {
        ride.yawOff = 0;
        ride.pitchOff = 0;
        ride.resetting = false;
        return;
      }
      ride.resetting = true;
    },
    rideActive: () => ride.active,
    setFeel(v) { ride.feel = Math.min(100, Math.max(0, v)); },
    // 调试/取证钩: 视线偏移读写 (仿 cabinLocal 惯例)
    rideView: () => (ride.active ? { yawOff: ride.yawOff, pitchOff: ride.pitchOff, resetting: ride.resetting } : null),
    debugRideView(yaw, pitch) {
      ride.yawOff = yaw;
      ride.pitchOff = pitch;
      ride.resetting = false;
    },
    // 调试/测试钩子：舱本地坐标与坐站态（非舱内模式返回 null）
    cabinLocal() {
      return cabin.active
        ? { x: cabin.local.x, z: cabin.local.y, seated: cabin.seated }
        : null;
    },
    // 可选 y：落到高处叠层地面（塔的环廊/轿厢）必须给脚高 —— 贴地分支只认「<= 脚底 + 步高」的地面，
    // 从 0 传送到 40m 平台上不会上吸，只会落在塔底的地面
    teleport(x, z, y = 0) {
      pos.x = x;
      pos.z = z;
      pos.y = y;
      vy = 0;
      grounded = true;
      landDip = 0;
    },
    setJumpLock(v) { jumpLock = !!v; },
    airborne: () => !grounded, // 只读取证钩子：走线断言用（沿梯行走应全程贴地）
    // 动态碰撞注册（旋转设施用）：圆对象引用就地注册, 设施每帧改写 x/z
    // 即可实现移动阻挡（碰撞循环每帧实时遍历 circles, 无需其他接入）
    registerCircles(list) {
      for (const c of list) circles.push(c);
    },
    // 眺望塔叠层地面注册（升降梯轿厢地面用）：对象引用入表，设施每帧改写 h 即生效
    registerFloors(list) {
      for (const f of list) floors.push(f);
    },
    // M4: 按 tag 开关实心矩形（闸机开闸禁用闸线碰撞）。
    // 内部 rects 是 park.rects 的 spread 拷贝表, 外部改原对象无效, 必须走此 API
    setRectDisabled(tag, disabled) {
      for (const rc of rects) if (rc.tag === tag) rc.disabled = disabled;
    },
    setView(y, p) {
      yaw = y;
      pitch = Math.max(-1.25, Math.min(1.25, p));
    },
    // 应用设置面板（园区步速 + M4 乘坐体感; 接口与 world/mist 等系统一致, main.applyAllSettings 调用）
    applySettings(s) {
      walkSpeed = Math.min(16, Math.max(2, s.walkSpeed ?? WALK_BASE));
      sprintSpeed = walkSpeed * SPRINT_RATIO;
      ride.feel = Math.min(100, Math.max(0, s.coasterFeel ?? 60));
    },
    update(dt) {
      const m = input.consumeMouse();
      if (ride.active) {
        // M4 乘坐: 鼠标只改相对车体的视线偏移, 相机四元数直写 (勿再覆写 Euler)。
        // 自由环视: yaw ±180° 可直视列车正后方, pitch ±1.25 与步行视角一致
        const mouseMoved = input.locked && (m.dx !== 0 || m.dy !== 0);
        if (input.locked) {
          ride.yawOff -= m.dx * 0.0022;
          ride.pitchOff = clamp(ride.pitchOff - m.dy * 0.0022, -1.25, 1.25);
          ride.yawOff = clamp(ride.yawOff, -Math.PI, Math.PI);
        }
        if (mouseMoved) ride.resetting = false; // 玩家接管视角, 取消 R 回正
        updateRide(dt);
        return;
      }
      if (input.locked) {
        yaw -= m.dx * 0.0022;
        pitch = Math.max(-1.25, Math.min(1.25, pitch - m.dy * 0.0022));
      }
      if (mount.active) updateMount(dt);
      else if (cabin.active) updateCabin(dt);
      else updateWorld(dt);
      camera.rotation.order = "YXZ";
      camera.rotation.set(pitch, yaw, 0);
    },
  };
}
