// 幽夜游乐场 — 入口
import { createScene, startLoop } from "./core/scene.js";
import { createWorld } from "./core/world.js";
import { loadGLB, createLoadingManager } from "./park/loader.js";
import { createFerrisWheel } from "./rides/ferris.js";
import { createHUD } from "./ui/hud.js";

const canvas = document.getElementById("game-canvas");

const { renderer, scene, camera } = createScene(canvas);
createWorld(scene);

const hud = createHUD();
window.__hud = hud; // 截图验证钩子（开发用）

const manager = createLoadingManager({
  onProgress: (p) => hud.setLoadingProgress(p),
  onLoad: () => hud.setReady(),
});

const updates = [];

// 分阶段显灵进度（多资产后由各加载器真实推进）
hud.setLoadingProgress(0.35); // 阶段：布场
loadGLB("/assets/models/ferris_wheel.glb", manager)
  .then((root) => {
    hud.setLoadingProgress(0.85); // 阶段：召轮
    scene.add(root);
    const ferris = createFerrisWheel(root);
    updates.push(ferris);
  });

hud.onEnter(() => {
  hud.enterPark();
  // P3 在此接入：指针锁定 + 音频启动 + 打卡系统
});

startLoop(renderer, scene, camera, updates);
