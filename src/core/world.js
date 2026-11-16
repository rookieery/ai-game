// 世界氛围（P0 最小版：夜色背景 + 雾 + 基础光 + 地面）
// P3 阶段扩展：极光天穹 / 星空 / 月亮 / 地面雾片 / 程序纹理
import * as THREE from "three";

export function createWorld(scene) {
  scene.background = new THREE.Color("#060812");
  scene.fog = new THREE.FogExp2("#0a0c1e", 0.012);

  // 月光（微弱蓝白定向光）
  const moon = new THREE.DirectionalLight("#b4c7ff", 0.55);
  moon.position.set(60, 80, -40);
  scene.add(moon);

  // 半球环境光：冷天光 + 地面暗紫反光
  const hemi = new THREE.HemisphereLight("#2a3050", "#141024", 0.5);
  scene.add(hemi);

  // 临时地面（P2 换成 park_env.glb 的真实地面）
  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(220, 64),
    new THREE.MeshStandardMaterial({ color: "#0a0d16", roughness: 0.95 })
  );
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  return { moon, hemi, ground };
}
