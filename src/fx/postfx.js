// 后期：UnrealBloom（自发光辉光）+ 输出
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

export function createPostFX(renderer, scene, camera) {
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const BLOOM = { strength: 0.3, radius: 0.55, threshold: 0.85, exposure: 0.95 };
  const bloom = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight),
    BLOOM.strength,
    BLOOM.radius,
    BLOOM.threshold // 只有较亮的自发光体辉光
  );
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  renderer.toneMappingExposure = BLOOM.exposure;

  window.addEventListener("resize", () => {
    composer.setSize(window.innerWidth, window.innerHeight);
  });

  return {
    render: () => composer.render(),
    // 应用设置面板（百分比 -> 实际参数）
    applySettings(s) {
      const pct = (v, hi) => Math.min(hi, Math.max(0, v ?? 0)) / 100;
      bloom.strength = BLOOM.strength * pct(s.bloomStrength, 200);
      bloom.threshold = pct(s.bloomThreshold, 100); // 绝对值 0-1
      renderer.toneMappingExposure = BLOOM.exposure * pct(s.exposure, 200);
    },
  };
}
