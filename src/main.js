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

// 分阶段显灵进度（多资产由各阶段真实推进）
hud.setLoadingProgress(0.3); // 阶段：布场

// 园区环境（地面/道路/大门/灯串/道具 + colliders.json 由 P3 消费）
loadGLB("/assets/models/park_env.glb", manager).then((root) => {
  hud.setLoadingProgress(0.6); // 阶段：铺路
  scene.add(root);
});

// 摩天轮
loadGLB("/assets/models/ferris_wheel.glb", manager).then((root) => {
  hud.setLoadingProgress(0.85); // 阶段：召轮
  // 园区地面替代轮盘自带的旧地面圆盘，避免两层地面重叠
  const legacyGround = root.getObjectByName("FW_Ground");
  if (legacyGround) legacyGround.removeFromParent();
  scene.add(root);
  const ferris = createFerrisWheel(root);
  updates.push(ferris);
});

// 碰撞与玩法锚点数据（P3 交互/移动消费）
fetch("/assets/models/colliders.json")
  .then((r) => r.json())
  .then((data) => {
    window.__park = data;
  })
  .catch(() => console.warn("[park] colliders.json 加载失败"));

hud.onEnter(() => {
  hud.enterPark();
  // P3 在此接入：指针锁定 + 音频启动 + 打卡系统
});

startLoop(renderer, scene, camera, updates);
