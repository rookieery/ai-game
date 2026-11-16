// 第一人称玩家控制器：WASD 移动 / Shift 疾走 / 指针锁定视角 / 圆碰撞
import * as THREE from "three";

const EYE = 1.65;      // 眼高
const PR = 0.38;       // 玩家碰撞半径
const WALK = 4.0;
const SPRINT = 7.2;

export function createPlayer(camera, input, park) {
  const spawn = park?.spawn ?? { x: 0, z: 60 };
  const pos = new THREE.Vector3(spawn.x, 0, spawn.z);
  let yaw = 0;          // 0 = 面向 -Z (从大门看向园区)
  let pitch = -0.04;
  let riding = false;
  let bobT = 0;

  // 碰撞圆: colliders.json + 摩天轮站台/台阶护栏 (登舱走交互, 不走台阶)
  const extra = [
    { x: 0, z: 0, r: 9.8 },
    { x: 0, z: 11.5, r: 2.7 },
    { x: 0, z: 14.2, r: 2.7 },
  ];
  const circles = [...(park?.circles ?? []), ...extra];
  const boundaryR = park?.boundaryR ?? 60;

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
    setRiding(v) { riding = v; },
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
      if (!riding) {
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
      camera.rotation.order = "YXZ";
      camera.rotation.set(pitch, yaw, 0);
    },
  };
}
