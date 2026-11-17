// 烟花系统：定时自动秀 + 烟花释放器手动齐射
// Points 粒子池（CPU 模拟, 加色混合, 死粒子染黑即隐形）+ 爆裂闪光点光 + WebAudio 合成音
// 主题四色 + 暖白 + 灵绿, 与品牌色板一致; 零外部素材
import * as THREE from "three";

const MAX = 1600;        // 粒子池容量（环形覆盖, 烟花短命无回收压力）
const GRAV = 3.2;        // 余烬重力（远小于真实 g, 梦幻缓坠）
const DRAG_PER_S = 0.6;  // vel *= DRAG_PER_S^dt 的大气阻尼
const SHELL_G = 7.5;     // 壳体升空重力（减速上升; 顶点 38-68m, 3-4s 后爆裂）

const PALETTE = ["#FFA53B", "#9B5BFF", "#8CFF4A", "#C43B3B", "#FFE9C4", "#8FE3D9"];

function makeGlowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 1, 32, 32, 30);
  // 能量集中内圈: 精灵可读核心 ~70% 半径 (旧渐变 94% 处才归零, 远观只剩针尖)
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.85)");
  grad.addColorStop(0.55, "rgba(255,255,255,0.28)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export function createFireworks(scene, { origin, camera, audio, renderer }) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(MAX * 3).fill(-9999);
  const colA = new Float32Array(MAX * 3);
  const sizeA = new Float32Array(MAX);
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("aColor", new THREE.BufferAttribute(colA, 3));
  geo.setAttribute("aSize", new THREE.BufferAttribute(sizeA, 1));
  // 每粒子尺寸: 尾迹 0.45 / 爆裂火花 1.4-2.1 (统一 PointsMaterial 无法兼顾远近观感)
  const points = new THREE.Points(
    geo,
    new THREE.ShaderMaterial({
      uniforms: { uMap: { value: makeGlowTexture() }, uScale: { value: 720 } },
      vertexShader: /* glsl */ `
        attribute vec3 aColor;
        attribute float aSize;
        uniform float uScale;
        varying vec3 vColor;
        void main() {
          vColor = aColor;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = aSize * (uScale / max(1.0, -mv.z));
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        uniform sampler2D uMap;
        varying vec3 vColor;
        void main() {
          float a = texture2D(uMap, gl_PointCoord).a;
          gl_FragColor = vec4(vColor * a, a);
        }`,
      blending: THREE.AdditiveBlending,
      transparent: true,
      depthWrite: false,
    })
  );
  points.frustumCulled = false;
  scene.add(points);

  const vel = new Float32Array(MAX * 3);
  const life = new Float32Array(MAX);      // <=0 视为空闲
  const life0 = new Float32Array(MAX);
  const base = new Float32Array(MAX * 3);  // 粒子本色（乘淡出系数写入 aColor）
  let cursor = 0;

  // 爆裂瞬时闪光（强度指数衰减, 0 时无开销感知）
  const flash = new THREE.PointLight("#ffffff", 0, 240, 1.8);
  scene.add(flash);

  const shells = [];    // 升空壳体 { p, v, color, acc }
  const pending = [];   // 齐射队列 { at, manual }（at = 距发射秒数）
  let period = 30;      // 自动秀间隔（秒, 0 = 关闭）
  let bright = 1;
  let nextShow = 8;     // 入园后 8s 首秀
  let now = 0;
  let cooldownUntil = -1;

  const _c = new THREE.Color();
  const _v = new THREE.Vector3();

  function spawn(p, v, color, l, size) {
    const i = cursor;
    cursor = (cursor + 1) % MAX;
    const i3 = i * 3;
    pos[i3] = p.x; pos[i3 + 1] = p.y; pos[i3 + 2] = p.z;
    vel[i3] = v.x; vel[i3 + 1] = v.y; vel[i3 + 2] = v.z;
    life[i] = l; life0[i] = l;
    sizeA[i] = size;
    // 固有色提亮 2.2x: 补 ACES 中调压缩, 重叠处推过 bloom 阈值出辉光
    base[i3] = color.r * 2.2; base[i3 + 1] = color.g * 2.2; base[i3 + 2] = color.b * 2.2;
  }

  // 发射一壳：从释放器管口升空（管口朝北 = app -z, 微北偏）
  function launchShell() {
    const color = new THREE.Color(PALETTE[(Math.random() * PALETTE.length) | 0]);
    const p = new THREE.Vector3(
      origin.x + (Math.random() - 0.5) * 1.2,
      origin.y + 0.9,
      origin.z + (Math.random() - 0.5) * 1.2
    );
    const v = new THREE.Vector3(
      (Math.random() - 0.5) * 4.5,
      24 + Math.random() * 8,
      (Math.random() - 0.5) * 4.0 - 1.2
    );
    shells.push({ p, v, color, acc: 0 });
    audio?.fireworkLaunch();
  }

  function burst(sh) {
    const n = 170 + ((Math.random() * 70) | 0);
    for (let k = 0; k < n; k++) {
      const u = Math.random() * 2 - 1;
      const phi = Math.random() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u);
      // 双速层: 25% 内芯慢速, 其余外壳快速 —— 球壳更立体
      const sp = Math.random() < 0.25 ? 4.5 + Math.random() * 3 : 9 + Math.random() * 6;
      _v.set(s * Math.cos(phi) * sp, u * sp * 0.92, s * Math.sin(phi) * sp);
      const c = Math.random() < 0.18 ? _c.set("#FFF6E0") : sh.color;
      spawn(sh.p, _v, c, 1.2 + Math.random() * 1.1, 4.5 + Math.random() * 1.5);
    }
    flash.position.copy(sh.p);
    flash.color.copy(sh.color);
    flash.intensity = 45 * bright;   // 适度闪地, 不糊画面
    const d = camera ? camera.position.distanceTo(sh.p) : 60;
    audio?.fireworkBurst(Math.max(0.12, Math.min(1, 1 - d / 300)));
  }

  function volley(n) {
    let t = 0;
    for (let k = 0; k < n; k++) {
      pending.push({ at: t });
      t += 0.4 + Math.random() * 0.6;
    }
  }

  // 手动齐射（烟花释放器按 F）: 1.6s 装填冷却
  function manualVolley() {
    if (now < cooldownUntil) return false;
    cooldownUntil = now + 1.6;
    volley(3);
    return true;
  }

  function isReady() {
    return now >= cooldownUntil;
  }

  function update(dt, elapsed) {
    now = elapsed;
    // 自动秀调度
    if (period > 0 && elapsed >= nextShow) {
      volley(1 + ((Math.random() * 3) | 0));
      nextShow = elapsed + period * (0.75 + Math.random() * 0.5);
    }
    // 齐射队列
    for (let k = pending.length - 1; k >= 0; k--) {
      pending[k].at -= dt;
      if (pending[k].at <= 0) {
        launchShell();
        pending.splice(k, 1);
      }
    }
    // 壳体升空 + 尾迹 + 顶点爆裂
    for (let k = shells.length - 1; k >= 0; k--) {
      const sh = shells[k];
      sh.v.y -= SHELL_G * dt;
      sh.p.addScaledVector(sh.v, dt);
      sh.acc += dt;
      if (sh.acc > 0.02) {
        sh.acc = 0;
        _v.set((Math.random() - 0.5) * 1.6, (Math.random() - 0.5) * 1.6,
               (Math.random() - 0.5) * 1.6);
        spawn(sh.p, _v, _c.set("#FFD9A0"), 0.35 + Math.random() * 0.3, 0.3);
      }
      if (sh.v.y < 2.5) {
        burst(sh);
        shells.splice(k, 1);
      }
    }
    // 粒子积分 + 淡出着色
    const drag = Math.pow(DRAG_PER_S, dt);
    for (let i = 0; i < MAX; i++) {
      if (life[i] <= 0) continue;
      life[i] -= dt;
      const i3 = i * 3;
      vel[i3 + 1] -= GRAV * dt;
      vel[i3] *= drag; vel[i3 + 1] *= drag; vel[i3 + 2] *= drag;
      pos[i3] += vel[i3] * dt;
      pos[i3 + 1] += vel[i3 + 1] * dt;
      pos[i3 + 2] += vel[i3 + 2] * dt;
      let f = Math.max(0, life[i] / life0[i]);
      f = Math.pow(f, 1.1);   // 缓衰减: 远距离烟花全程可读
      const b = f * bright;
      colA[i3] = base[i3] * b;
      colA[i3 + 1] = base[i3 + 1] * b;
      colA[i3 + 2] = base[i3 + 2] * b;
      if (life[i] <= 0) {
        colA[i3] = colA[i3 + 1] = colA[i3 + 2] = 0;
        pos[i3 + 1] = -9999;
      }
    }
    // uScale = 画布半高(设备像素): gl_PointSize 公式与 three 内部 points 一致
    if (renderer) {
      points.material.uniforms.uScale.value = Math.max(1, renderer.domElement.height / 2);
    }
    geo.attributes.position.needsUpdate = true;
    geo.attributes.aColor.needsUpdate = true;
    geo.attributes.aSize.needsUpdate = true;
    flash.intensity *= Math.exp(-dt * 7);
    if (flash.intensity < 0.05) flash.intensity = 0;
  }

  function applySettings(s) {
    period = Math.max(0, s.fireworkPeriod ?? 30);
    bright = Math.min(2, Math.max(0, s.fireworkBright ?? 100)) / 100;
  }

  return { update, applySettings, manualVolley, isReady };
}
