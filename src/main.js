// 幽夜游乐场 — 入口与游戏编排
import { createScene, startLoop } from "./core/scene.js";
import { createWorld } from "./core/world.js";
import { createInput } from "./core/input.js";
import { createPlayer } from "./player/controller.js";
import { createInteract } from "./interact.js";
import { createAudio } from "./core/audio.js";
import { loadGLB, createLoadingManager } from "./park/loader.js";
import { createFerrisWheel } from "./rides/ferris.js";
import { createPostFX } from "./fx/postfx.js";
import { createHUD } from "./ui/hud.js";
import { createSettings } from "./core/config.js";
import { createSettingsPanel } from "./ui/settings.js";

const canvas = document.getElementById("game-canvas");

const { renderer, scene, camera } = createScene(canvas);
const world = createWorld(scene);
const postfx = createPostFX(renderer, scene, camera);
const input = createInput(canvas);
const hud = createHUD();
const audio = createAudio(hud);
window.__hud = hud; // 截图验证钩子（开发用）

// ---------- 游戏状态 ----------
const game = { state: "boot" }; // boot -> walk -> boarding -> riding -> exiting -> walk
let player = null;
let ferris = null;
let interact = null;
let entered = false;

// ---------- 设置面板 ----------
const settings = createSettings();
const settingsUI = createSettingsPanel(settings, {
  // 开合影响视角锁定提示的显隐，关面板时若仍未锁定则恢复提示
  onOpenChange: (open) => {
    if (!open) hud.setLookHint(entered && !input.locked);
  },
});
window.__settings = { store: settings, ui: settingsUI }; // 截图/排错钩子（开发用）

function applyAllSettings() {
  world.applySettings(settings.values);
  postfx.applySettings(settings.values);
  if (ferris) ferris.applySettings(settings.values);
}
applyAllSettings(); // 恢复持久化配置（含舱内灯光默认 40%）
settings.onChange(applyAllSettings);

const manager = createLoadingManager({
  onProgress: (p) => hud.setLoadingProgress(p),
  onLoad: () => hud.setReady(),
});

const updates = [world];

async function boot() {
  // 碰撞与玩法锚点
  let park = null;
  try {
    park = await (await fetch("/assets/models/colliders.json")).json();
  } catch {
    console.warn("[park] colliders.json 加载失败, 使用空碰撞");
  }
  window.__park = park;

  player = createPlayer(camera, input, park);

  // 资产
  hud.setLoadingProgress(0.3); // 布场
  const parkRoot = await loadGLB("/assets/models/park_env.glb", manager);
  hud.setLoadingProgress(0.6); // 铺路
  scene.add(parkRoot);

  const wheelRoot = await loadGLB("/assets/models/ferris_wheel.glb", manager);
  hud.setLoadingProgress(0.85); // 召轮
  // 注: legacy FW_Ground 地面盘已在 Blender 管线导出前移除 (ferris_wheel.py v2.3),
  // app 侧地面由 park_env.glb 提供
  scene.add(wheelRoot);
  ferris = createFerrisWheel(wheelRoot);
  ferris.applySettings(settings.values); // 摩天轮就位后补应用（含持久化配置）
  updates.push(ferris);

  // 交互
  interact = createInteract({
    input, hud, audio,
    player, park,
    getState: () => game.state,
    onBoard() {
      if (game.state !== "walk") return;
      game.state = "boarding";
      audio.setRiding(true);
      hud.transition(() => {
        ferris.board();
        player.enterCabin(() => ferris.getRideFrame());
        hud.showPlaque("幽眠摩天轮", "高空观光 · WASD 舱内走动 · C 坐下起身 · E 随时下乘");
        game.state = "riding";
      });
    },
    onCollect(poi, got, total) {
      if (got === total) hud.setStars(total, total);
    },
  });
  updates.push(interact);

  // 乘坐中 E 下客
  input.onPress("KeyE", () => {
    if (game.state !== "riding") return;
    game.state = "exiting";
    audio.setRiding(false);
    hud.transition(() => {
      player.exitCabin();
      ferris.disembark();
      hud.hidePlaque();
      game.state = "walk";
    });
  });

  // 指针锁定（面板打开时不出「点击画面」提示，避免与抽屉重叠）
  input.onLockChange((locked) => hud.setLookHint(entered && !locked && !settingsUI.isOpen));
  canvas.addEventListener("click", () => {
    if (entered && !input.locked) input.requestLock();
  });

  hud.onEnter(() => {
    entered = true;
    hud.enterPark();
    input.requestLock(); // 用户手势内申请指针锁定
    audio.ensure();      // 音频图需用户手势启动
    game.state = "walk";
    hud.toast("欢迎来到幽夜游乐场");
  });

  // 玩家每帧：园区行走或舱内走动（舱内相机由玩家控制器挂舱，ferris.update 先行）
  updates.push({
    update(dt) {
      player.update(dt);
      interact.update();
    },
  });

  game.state = "loading";
}

boot().then(() => {
  // 资产就绪后由 LoadingManager 触发 onLoad -> setReady
});

// ---------- 主循环 ----------
const clock = { last: performance.now() };
renderer.setAnimationLoop(() => {
  const now = performance.now();
  const dt = Math.min((now - clock.last) / 1000, 0.1);
  clock.last = now;
  const elapsed = now / 1000;
  for (const cb of updates) cb.update(dt, elapsed);
  postfx.render();
});

// 调试钩子（截图/排错/性能核对）
window.__game = {
  get state() { return game.state; },
  get player() { return player; },
  get ferris() { return ferris; },
  get interact() { return interact; },
  get camera() { return camera; },
  renderer,
  scene,
};
