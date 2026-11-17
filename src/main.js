// 幽夜游乐场 — 入口与游戏编排
import { createScene, startLoop } from "./core/scene.js";
import { createWorld } from "./core/world.js";
import { createInput } from "./core/input.js";
import { createPlayer } from "./player/controller.js";
import { createInteract } from "./interact.js";
import { createAudio } from "./core/audio.js";
import { loadGLB, createLoadingManager } from "./park/loader.js";
import { createFerrisWheel } from "./rides/ferris.js";
import { createCarousel } from "./rides/carousel.js";
import { createPostFX } from "./fx/postfx.js";
import { createMist } from "./fx/mist.js";
import { createFireworks } from "./fx/fireworks.js";
import { createWisps } from "./fx/wisps.js";
import { createHUD } from "./ui/hud.js";
import { createSettings } from "./core/config.js";
import { createSettingsPanel } from "./ui/settings.js";

const canvas = document.getElementById("game-canvas");

const { renderer, scene, camera } = createScene(canvas);
const world = createWorld(scene);
const mist = createMist(scene, world);
const postfx = createPostFX(renderer, scene, camera);
const input = createInput(canvas);
const hud = createHUD();
const audio = createAudio(hud);
window.__hud = hud; // 截图验证钩子（开发用）
// 烟花（6 站发射器锚点由 colliders.json 注入, 见 boot() 内 setLaunchers）+ 幽灵火
const fireworks = createFireworks(scene, { camera, audio, renderer });
const wisps = createWisps(scene);

// ---------- 游戏状态 ----------
const game = { state: "boot", ride: null }; // boot -> walk -> boarding -> riding -> exiting -> walk; ride = ferris|carousel
let player = null;
let ferris = null;
let carousel = null;
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
  mist.applySettings(settings.values);
  postfx.applySettings(settings.values);
  fireworks.applySettings(settings.values);
  wisps.applySettings(settings.values);
  if (ferris) ferris.applySettings(settings.values);
  if (carousel) carousel.applySettings(settings.values);
}
applyAllSettings(); // 恢复持久化配置（含舱内灯光默认 40%）
settings.onChange(applyAllSettings);

const manager = createLoadingManager({
  onProgress: (p) => hud.setLoadingProgress(p),
  onLoad: () => hud.setReady(),
});

const updates = [world, mist, fireworks, wisps];

async function boot() {
  // 碰撞与玩法锚点
  let park = null;
  try {
    park = await (await fetch("/assets/models/colliders.json")).json();
  } catch {
    console.warn("[park] colliders.json 加载失败, 使用空碰撞");
  }
  window.__park = park;
  fireworks.setLaunchers(park?.launchers); // 6 站发射器 { id, kind, x, z, dx, dz, mz }

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

  // 显灵木马: 原点建模资产摆到东北园区 (blender (45,18) -> app (45,-18));
  // 平台/中柱/台阶/围栏碰撞为静态表 (colliders.json), 骑乘位/铜杆由 carousel.js 动态驱动
  const carouselRoot = await loadGLB("/assets/models/carousel.glb", manager);
  hud.setLoadingProgress(0.9); // 请灵
  carouselRoot.position.set(45, 0, -18);
  scene.add(carouselRoot);
  carousel = createCarousel(carouselRoot, { player });
  carousel.applySettings(settings.values);
  updates.push(carousel);

  // 交互
  interact = createInteract({
    input, hud, audio,
    player, park, fireworks,
    getState: () => game.state,
    onBoard() {
      if (game.state !== "walk") return;
      game.state = "boarding";
      game.ride = "ferris";
      audio.setRiding(true);
      hud.transition(() => {
        ferris.board();
        player.enterCabin(() => ferris.getRideFrame());
        hud.showPlaque("幽眠摩天轮", "高空观光 · WASD 舱内走动 · C 坐下起身 · E 随时下乘");
        game.state = "riding";
      });
    },
    onBoardCarousel() {
      if (game.state !== "walk") return;
      game.state = "boarding";
      game.ride = "carousel";
      audio.setRiding(true);
      hud.transition(() => {
        carousel.board();
        const fr = carousel.getMountFrame();
        player.enterMount(() => carousel.getMountFrame());
        player.setView(fr.yaw, -0.04); // 初始视线 = 灵兽行进方向
        hud.showPlaque("显灵木马", "灵兽环游 · 自由环视 · E 随时下乘");
        game.state = "riding";
      });
    },
    onCollect(poi, got, total) {
      if (got === total) hud.setStars(total, total);
    },
  });
  updates.push(interact);

  // 乘坐中 E 下客（按 ride 分流: 摩天轮回地面登舱点 / 木马下马回平台）
  input.onPress("KeyE", () => {
    if (game.state !== "riding") return;
    const kind = game.ride;
    game.state = "exiting";
    audio.setRiding(false);
    hud.transition(() => {
      if (kind === "carousel") {
        const drop = carousel.dismountPoint();
        player.exitMount();
        carousel.dismount();
        player.teleport(drop.x, drop.z); // 平台上落点, y 由地面支撑接管
      } else {
        player.exitCabin();
        ferris.disembark();
        // 统一送回地面登舱点（站台登舱后避免落在站台投影内；淡入淡出掩盖位移）
        player.teleport(park?.boarding?.x ?? 0, park?.boarding?.z ?? 16.4);
      }
      game.ride = null;
      hud.hidePlaque();
      game.state = "walk";
    });
  });

  // 烟花发射器：靠近时按 F 单发点射（interact.update 提供就近判定与提示）
  input.onPress("KeyF", () => {
    if (game.state !== "walk") return;
    const lid = interact.nearLauncher();
    if (lid >= 0) fireworks.fire(lid);
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
    hud.toast("欢迎来到幽夜游乐场 · 空格跳跃");
  });

  // 玩家每帧：园区行走或舱内走动（舱内相机由玩家控制器挂舱，ferris.update 先行）
  updates.push({
    update(dt) {
      // 站台安全联锁：站在登舱站台（脚高 > 1.4）时轮体缓停吸附舱位
      ferris.setHold(game.state === "walk" && player.pos.y > 1.4);
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
  get ride() { return game.ride; },
  get player() { return player; },
  get ferris() { return ferris; },
  get carousel() { return carousel; },
  get interact() { return interact; },
  get fireworks() { return fireworks; },
  get camera() { return camera; },
  renderer,
  scene,
};
