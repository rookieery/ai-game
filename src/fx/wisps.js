// 幽灵火 x6：墓园与林间漂浮的蓝绿光球（加色 sprite, 利萨如漂移 + 呼吸明灭）
// 透明度随「地面漂雾」设置联动 —— 雾越浓, 灵火越隐约
import * as THREE from "three";

// app 坐标 (x, z) = blender (x, -y)；据 park_env v3 布局手放
const SPOTS = [
  { x: 30.5, z: 61, y: 1.5, r: 2.2 },  // 墓园彼岸花旁 (2026-11-26 随墓园南迁: 新址椭圆 36x24 心 (37,58))
  { x: 38.5, z: 54, y: 1.2, r: 1.6 },  // 墓园石碑间 (枯树旁)
  { x: 60, z: -45, y: 1.8, r: 2.6 },   // 东北林地蘑菇圈
  { x: -15, z: 70, y: 1.3, r: 2.0 },   // 南外环草地
  { x: -75, z: -10, y: 1.6, r: 2.4 },  // 西侧松林
  { x: 30, z: 80, y: 1.4, r: 1.8 },    // 东南外环
];

function makeWispTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 1, 32, 32, 30);
  grad.addColorStop(0, "rgba(230,255,248,1)");
  grad.addColorStop(0.3, "rgba(143,227,217,0.5)");
  grad.addColorStop(1, "rgba(143,227,217,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export function createWisps(scene) {
  const tex = makeWispTexture();
  const wisps = SPOTS.map((sp, i) => {
    const mat = new THREE.SpriteMaterial({
      map: tex,
      color: "#8FE3D9",
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
    });
    const s = new THREE.Sprite(mat);
    s.scale.setScalar(1.5);
    s.position.set(sp.x, sp.y, sp.z);
    s.frustumCulled = false;
    scene.add(s);
    return { s, sp, phase: i * 1.7, baseOpacity: 0.7, gain: 1 };
  });

  function update(_dt, elapsed) {
    for (const w of wisps) {
      const t = elapsed * 0.5 + w.phase;
      // 利萨如漂移：横向慢椭圆 + 垂直浅呼吸
      w.s.position.set(
        w.sp.x + Math.sin(t * 0.55) * w.sp.r,
        w.sp.y + Math.sin(t * 0.9 + 1.3) * 0.3,
        w.sp.z + Math.cos(t * 0.42 + 0.7) * w.sp.r * 0.7
      );
      const pulse = 0.62 + 0.38 * Math.sin(t * 1.7 + w.phase * 3.1);
      w.s.material.opacity = w.baseOpacity * w.gain * pulse;
    }
  }

  function applySettings(s) {
    // 先除 100 再钳 0–2。旧写法 Math.min(2, Math.max(0, 值)) / 100 是先钳后除: 滑杆 5–200 一律得 0.02,
    // 系数恒为 0.265 —— 灵火自上线(f2703d2)起一直比设计值暗(100% 应为 1.0), 且「地面漂雾」滑杆对它不起作用
    const pct = Math.min(2, Math.max(0, (s.mistDensity ?? 100) / 100));
    for (const w of wisps) {
      w.gain = 0.25 + pct * 0.75;   // 无雾时灵火仍微亮, 不至于消失
    }
  }

  return { update, applySettings };
}
