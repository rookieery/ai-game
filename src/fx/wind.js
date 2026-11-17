// 风摆 + 南瓜灯发光联动：按材质名注入 shader / 调 emissiveIntensity
// 资产 glb 不变 —— 草/柳/松/枯树细枝的摆动全部在顶点着色器里做。
// 适用前提：park_env.py 按材质 join 后，网格顶点为世界坐标（物体零变换）。
import * as THREE from "three";

// mode: "up"   = 越高摆幅越大（草叶/松层/细枝：根部锚定）
//       "hang" = 越低摆幅越大（垂柳飘带：顶端锚定，垂梢大幅）
const TARGETS = [
  // tipGlow: 叶尖磷光 (对齐参考图的发光草尖; 磷光绿, 根部不发光) — 仅草启用
  { name: "PE_GrassTuft", amp: 0.10, freq: 1.6, H: 0.7, mode: "up", pow: 1.6, tipGlow: 0.5 },
  { name: "PE_WillowFiber", amp: 0.30, freq: 1.0, H: 4.2, mode: "hang", pow: 1.3 },
  { name: "PE_PineFoliage", amp: 0.06, freq: 0.7, H: 6.5, mode: "up", pow: 2.0 },
  { name: "PE_Twig", amp: 0.03, freq: 1.9, H: 4.0, mode: "up", pow: 1.0 },
];

// 南瓜灯发光联动材质（设置项 pumpkinGlow 的作用点）
const GLOW_MATS = ["PE_PumpGlow", "PE_PumpFace"];

export function createWind(root) {
  const patched = [];
  const glowMats = [];

  root.traverse((o) => {
    if (!o.isMesh || !o.material) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const mat of mats) {
      const t = TARGETS.find((t) => mat.name === t.name);
      if (t && !patched.some((p) => p.mat === mat)) {
        const uTime = { value: 0 };
        const uAmp = { value: t.amp };
        // 程序缓存按材质名隔离: 默认键 = onBeforeCompile.toString(), 四个材质的模板
        // 源码相同会被 three.js 共用同一段编译好的 shader (谁先渲染谁定义) ——
        // 草的叶尖磷光/摆动参数会泄漏到松针/垂柳/枯梢 (踩坑: 松针变亮黄绿发光树)
        mat.customProgramCacheKey = () => "wind_" + t.name;
        mat.onBeforeCompile = (shader) => {
          shader.uniforms.uTime = uTime;
          shader.uniforms.uAmp = uAmp;
          shader.vertexShader = shader.vertexShader
            .replace("#include <common>", "#include <common>\nuniform float uTime;\nuniform float uAmp;\nvarying float vTipN;")
            .replace(
              "#include <begin_vertex>",
              `#include <begin_vertex>
  {
    float phW = position.x * 0.35 + position.z * 0.29;
    float tW = uTime * ${t.freq.toFixed(2)};
    float wW = sin(tW + phW) + 0.35 * sin(tW * 1.83 + phW * 1.7);
    float hN = clamp(position.y / ${t.H.toFixed(2)}, 0.0, 1.0);
    float bendF = ${t.mode === "hang"
                ? `pow(1.0 - hN, ${t.pow.toFixed(1)})`
                : `pow(hN, ${t.pow.toFixed(1)})`};
    float ampW = uAmp * bendF;
    transformed.x += wW * ampW;
    transformed.z += 0.6 * sin(tW * 0.71 + phW * 1.3) * ampW;
    vTipN = hN;
  }`
            );
          if (t.tipGlow) {
            shader.fragmentShader = shader.fragmentShader
              .replace("#include <common>", "#include <common>\nvarying float vTipN;")
              .replace(
                "#include <emissivemap_fragment>",
                `#include <emissivemap_fragment>
  // 叶尖磷光: 高度加权, 根部为零 (磷光绿, 对齐参考图发光草尖)
  totalEmissiveRadiance += vec3(0.35, 0.72, 0.22) * (vTipN * vTipN) * ${t.tipGlow.toFixed(2)};`
              );
          }
        };
        patched.push({ mat, uTime, uAmp, base: t.amp });
      }
      if (GLOW_MATS.includes(mat.name) && !glowMats.some((g) => g.mat === mat)) {
        glowMats.push({ mat, base: mat.emissiveIntensity ?? 1.0 });
      }
    }
  });

  return {
    update(_dt, elapsed) {
      for (const p of patched) p.uTime.value = elapsed;
    },
    applySettings(s) {
      const windK = Math.min(2, Math.max(0, (s.windStrength ?? 100) / 100));
      for (const p of patched) p.uAmp.value = p.base * windK;
      const glowK = Math.min(2, Math.max(0, (s.pumpkinGlow ?? 100) / 100));
      for (const g of glowMats) g.mat.emissiveIntensity = g.base * glowK;
    },
  };
}
