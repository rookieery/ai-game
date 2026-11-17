// 场景骨架：renderer / camera / resize / 渲染循环
import * as THREE from "three";

export function createScene(canvas) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    0.1,
    // 2000: 须大于「天穹半径 700 + 相机离园心最大偏移 ~150」(world.js 穹顶)。
    // v3 扩园后门口 z146 朝北看天穹最远 ~828m, 旧值 800 会裁掉天穹远端,
    // 在门口视角留下硬边多边形黑洞 (2026-11-17 排查, 见 git log)
    2000
  );
  camera.position.set(30, 9, 42);
  camera.lookAt(0, 14, 0);

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  return { renderer, scene, camera };
}

// 主循环：dt 秒；callbacks 为 { update(dt, elapsed) } 数组
// renderFn 可选（后处理管线传入 composer.render）
export function startLoop(renderer, scene, camera, callbacks, renderFn) {
  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.1);
    const elapsed = clock.elapsedTime;
    for (const cb of callbacks) cb.update(dt, elapsed);
    if (renderFn) renderFn();
    else renderer.render(scene, camera);
  });
}
