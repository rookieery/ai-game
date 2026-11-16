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

const canvas = document.getElementById("game-canvas");

const { renderer, scene, camera } = createScene(canvas);
const world = createWorld(scene);
const postfx = createPostFX(renderer, scene, camera);
const input = createInput(canvas);
const hud = createHUD();
const audio = createAudio(hud);
window.__hud = hud; // 截图验证钩子（开发用）

const manager = createLoadingManager({
  onProgress: (p) => hud.setLoadingProgress(p),
  onLoad: () => hud.setReady(),
});

const updates = [world];

// ---------- 游戏状态 ----------
const game = { state: "boot" }; // boot -> walk -> boarding -> riding -> exiting -> walk
let player = null;
let ferris = null;
let interact = null;

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
  const legacyGround = wheelRoot.getObjectByName("FW_Ground");
  if (legacyGround) legacyGround.removeFromParent();
  scene.add(wheelRoot);
  ferris = createFerrisWheel(wheelRoot);
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
        player.setRiding(true);
        ferris.board();
        hud.showPlaque("幽眠摩天轮", "高空观光 · 移动视角环视 · E 随时下乘");
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
      player.setRiding(false);
      ferris.disembark();
      hud.hidePlaque();
      game.state = "walk";
    });
  });

  // 指针锁定
  let entered = false;
  input.onLockChange((locked) => hud.setLookHint(entered && !locked));
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

  // 乘坐姿态：每帧相机挂舱（在 ferris.update 之后执行）
  updates.push({
    update(dt) {
      player.update(dt);
      ferris.applyRideCamera(camera);
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

// 调试钩子（截图/排错）
window.__game = {
  get state() { return game.state; },
  get player() { return player; },
  get ferris() { return ferris; },
  get interact() { return interact; },
};
